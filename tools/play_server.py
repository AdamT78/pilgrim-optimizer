"""A thin local process serving setup + live play views from one in-memory session.

Standard library only. The repo declares no dependencies at all -- `pyproject.toml` has
`dependencies = []` -- so bringing in a framework to serve four routes would be the first one, and
`http.server` is enough for one local page playing one game.

    GET  /              setup page (when no game loaded) or play view (when one is loaded)
    GET  /state.json    the payload the adapter was handed, verbatim
    GET  /actions.json  the legal actions, structured, with an id each and a token for the state
    POST /start         start from setup choices or a saved test position
    POST /new-game      clear the loaded game and return to setup
    POST /action        apply one of them, by id, quoting the token it was read from

ONE GAME, IN MEMORY, NO PERSISTENCE. Restarting the process loses the position. That is a real
limitation and is left rather than papered over: saving would mean choosing a format and a place to
put it, and a local process for looking at a board does not need to have that argued out yet.

WHY THIS FILE IS NOT UNDER tools/ui_debug

It imports the engine, and nothing under `tools/ui_debug` may. That rule is what keeps the whole UI
testable against hand-written JSON with no engine in the room, and it is enforced by a test. This
is the seam: the engine on one side, a plain dict crossing it, the renderers on the other. Living
one directory up is how the seam stays visible rather than becoming a convention people remember.

Run from the repo root:

    python3 tools/play_server.py
    python3 tools/play_server.py /tmp/scenario.json
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import enum
import hashlib
import json
import random
import socketserver
import sys
import tempfile
import threading
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pilgrim.io.event_text import format_event_for_players  # noqa: E402
from pilgrim.model.enums import CANONICAL_POSITION_NAMES, EventType  # noqa: E402
from pilgrim.io.scenarios import load_scenario  # noqa: E402
from pilgrim.io.view import view_payload  # noqa: E402
from pilgrim.setup.generator import SUPPORTED_PLAYER_COUNTS, generate_setup_scenario  # noqa: E402
from pilgrim.rules.ordination import ordination_outcome  # noqa: E402
from pilgrim.rules.special_activities import allocation_outcome  # noqa: E402
from pilgrim.rules.sow_routes import (  # noqa: E402
    _allowed_cloisters_omission_locations,
    cloisters_actual_placements_after_omission,
    cloisters_candidate_omissions,
    cloisters_candidate_placements,
    kogge_cloisters_candidate_placements,
)
from pilgrim.model.actions import (  # noqa: E402
    FullTurnAction,
    SetupSowAction,
    StartPlayerConfessionBoxAction,
    StartPlayerSelectionAction,
    action_id,
    action_choice_summary_for_players,
    action_summary_for_players,
)
from pilgrim.rules.buildings import building_ability_source, building_by_id  # noqa: E402
from pilgrim.rules.transition import (  # noqa: E402
    _turn_step_id,
    apply_action,
    apply_turn_step as apply_engine_turn_step,
    legal_actions,
    turn_steps,
)
from tools.ui_debug.render_play_view import SEAT_COLOURS, render_play_view_from_payload  # noqa: E402
from tools.ui_debug.render_table_layout import SEATED_PLAYERS  # noqa: E402

DEFAULT_PORT = 8765
SETUP_MODE_RANDOM = "random"
SETUP_MODE_BASIC = "basic"
ROLE_HUMAN = "human"
ROLE_BOT = "bot"
SEAT_ROLE_OPTIONS: tuple[str, ...] = (ROLE_HUMAN, ROLE_BOT)
SCENARIO_PATH_FIELDS: tuple[str, ...] = (
    "board_file",
    "duties_file",
    "piety_file",
    "alms_file",
    "timing_file",
    "merchant_file",
    "ship_file",
    "buildings_file",
)
PLAYTEST_SCENARIOS_DIR = Path(__file__).resolve().parents[1] / "scenarios" / "playtest"


@dataclasses.dataclass(slots=True)
class SessionState:
    """Local UI-session facts that are intentionally not part of the engine state.

    `game_loaded` and seat roles belong beside the server process, never in `GameState` and never
    in scenario JSON. If they crossed the seam, search would see bot seats and evaluate a different
    game than the one a human is playing.
    """

    game_loaded: bool = False
    seat_roles: dict[str, str] = dataclasses.field(default_factory=dict)
    setup_mode: str = SETUP_MODE_RANDOM
    player_count: int = 4
    seed: int | None = None


@dataclasses.dataclass(frozen=True, slots=True)
class PlaytestPosition:
    """One saved local test position offered on the setup page."""

    name: str
    path: Path
    label: str
    player_count: int | None
    seed: int | None


def _plain(value: Any) -> Any:
    """JSON-able, and structured all the way down.

    Tuples become lists and enums become their values; nothing is flattened into a sentence. The
    summary string the CLI prints is deliberately absent: a client that parsed it to decide what an
    action does would be a rules parser wearing a disguise, and the fields it would be parsing back
    out are right here already.
    """
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, tuple | list):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    return value


def state_token(payload: dict) -> str:
    """A short name for exactly this position.

    The next PR needs to reject a submission quoting a list that has since gone stale, and the only
    honest way to do that is to name the state the list came from. It is a digest of the payload,
    so it changes when anything drawn changes and cannot be guessed from a turn number.
    """
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def actions_document(state: Any, config: Any, payload: dict) -> dict:
    """The legal actions as data, each with a stable readable id.

    The id is what a client quotes back, rather than a position in this list: a menu index means
    nothing once the list is regenerated, and `setup_sow:sow:0:1->2->3->4->5` means the same thing
    for as long as the action does.
    """
    actions = legal_actions(state, config)
    return {
        "state_token": state_token(payload),
        "count": len(actions),
        "actions": [
            {
                "action_id": action_id(action),
                "action_type": type(action).__name__,
                "fields": _plain(dataclasses.asdict(action)),
            }
            for action in actions
        ],
    }


def turn_steps_payload(state: Any, config: Any) -> list[dict[str, Any]]:
    """The committed conversions currently legal, each with the id the client may quote back."""
    payload = []
    player = state.active_player
    before = state.player_state(player)
    for step in turn_steps(state, config):
        result = apply_engine_turn_step(state, config, step)
        after_step = result.player_state(player)
        total_silver_delta = after_step.resources.silver - before.resources.silver
        hire_silver_delta = sum(
            -int(dict(event.details).get("amount", 0))
            for event in result.events
            if event.event_type is EventType.BUILDING_HIRED
            and event.action_id == _turn_step_id(step)
            and dict(event.details).get("resource") == "silver"
        )
        payload.append({
            "step_id": _turn_step_id(step),
            "building_id": step.building_id,
            "source": step.source,
            "direction": step.direction,
            "amount": step.amount,
            "hire_payment": step.hire_payment,
            "piety_destination": after_step.piety,
            # Describe the conversion separately from the optional building hire fee. Both values
            # come from the engine: the total state delta and the BUILDING_HIRED event details.
            "silver_delta": total_silver_delta - hire_silver_delta,
        })
    return payload


class StaleStateToken(Exception):
    """The submission quoted a list that is no longer the one on offer."""


class UnknownAction(Exception):
    """The submission named an action that is not legal in the position now held."""


class UnknownTurnStep(Exception):
    """The submission named a conversion step that is not legal in the position now held."""


def _default_seat_roles(player_count: int) -> dict[str, str]:
    return {SEATED_PLAYERS[index]: ROLE_HUMAN for index in range(player_count)}


def _prefill_seed() -> int:
    """Server-side seed suggestion for the setup form."""
    return random.SystemRandom().randint(1000, 9999)


def _optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _available_playtest_positions() -> list[PlaytestPosition]:
    """Saved test positions discovered from `scenarios/playtest/*.json`.

    Discovery is by directory listing, not hard-coded names, so adding a new position is dropping a
    file into that folder.
    """
    if not PLAYTEST_SCENARIOS_DIR.exists():
        return []
    positions: list[PlaytestPosition] = []
    for path in sorted(PLAYTEST_SCENARIOS_DIR.glob("*.json")):
        label = path.stem
        player_count = None
        seed = None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                scenario_id = raw.get("scenario_id")
                if isinstance(scenario_id, str) and scenario_id.strip():
                    label = scenario_id
                player_count = _optional_int(raw.get("player_count"))
                setup_metadata = raw.get("setup_metadata")
                if isinstance(setup_metadata, dict):
                    seed = _optional_int(setup_metadata.get("seed"))
        except Exception:
            # The sweep test ensures every discovered file is valid. If one is malformed meanwhile,
            # keep setup usable and fall back to stem label + no metadata.
            pass
        positions.append(
            PlaytestPosition(
                name=path.name,
                path=path.resolve(),
                label=label,
                player_count=player_count,
                seed=seed,
            )
        )
    return positions


def _playtest_position_by_name(
    name: str,
    positions: list[PlaytestPosition],
) -> PlaytestPosition | None:
    for position in positions:
        if position.name == name:
            return position
    return None


def _rewrite_generated_paths_absolute(generated: dict[str, Any]) -> None:
    """Make generated config file paths loadable from any temporary scenario location."""
    repo_root = Path(__file__).resolve().parents[1]
    for field_name in SCENARIO_PATH_FIELDS:
        raw = generated.get(field_name)
        if not isinstance(raw, str):
            raise ValueError(f"Generated scenario field '{field_name}' must be a string path.")
        path = Path(raw)
        generated[field_name] = str((path if path.is_absolute() else (repo_root / path)).resolve())


def _render_setup_page(
    *,
    suggested_seed: int,
    playtest_positions: list[PlaytestPosition],
) -> str:
    """The pre-game setup form served when no game is loaded in this session."""
    count_options = "".join(
        f'<option value="{count}"{" selected" if count == 4 else ""}>{count}</option>'
        for count in SUPPORTED_PLAYER_COUNTS
    )
    test_position_options = [
        '<option value="" selected>Deal a fresh game</option>',
    ]
    for position in playtest_positions:
        player_attr = (
            f' data-player-count="{position.player_count}"'
            if position.player_count is not None
            else ""
        )
        seed_attr = f' data-seed="{position.seed}"' if position.seed is not None else ""
        test_position_options.append(
            f'<option value="{escape(position.name)}"{player_attr}{seed_attr}>'
            f"{escape(position.label)}"
            "</option>"
        )
    playtest_options = "".join(test_position_options)
    seat_rows = []
    for seat, player_id in enumerate(SEATED_PLAYERS, start=1):
        colour = SEAT_COLOURS[player_id]
        seat_rows.append(
            "<div class=\"seat-row\" data-seat-row=\"{seat}\">"
            "<span class=\"seat-label\">Seat {seat} ({colour})</span>"
            "<select name=\"seat_{seat}_role\">"
            "<option value=\"human\" selected>Human</option>"
            "<option value=\"bot\" disabled>Bot (disabled)</option>"
            "</select></div>".format(seat=seat, colour=escape(colour))
        )
    rows = "".join(seat_rows)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Pilgrim Optimizer - Start Game</title>
<style>
  body {{
    margin: 0; padding: 24px; background: #151515; color: #F2EEDF;
    font: 14px/1.5 Helvetica, Arial, sans-serif;
    display: flex; justify-content: center;
  }}
  .setup-card {{
    width: min(680px, 100%);
    background: #101010; border: 1px solid #333333; border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0,0,0,.5); padding: 20px 22px;
  }}
  h1 {{ margin: 0 0 8px 0; font-size: 22px; }}
  p {{ margin: 0 0 16px 0; color: #C9C4B4; }}
  .field {{ margin-bottom: 14px; display: flex; flex-direction: column; gap: 6px; }}
  label {{ color: #D5D0BE; }}
  select, input, button {{
    font: inherit; border-radius: 8px; border: 1px solid #4A4A4A;
    background: #1D1D1D; color: #F2EEDF; padding: 8px 10px;
  }}
  select:disabled, input:disabled {{
    opacity: 0.65;
  }}
  .seat-rows {{
    border: 1px solid #2F2F2F; border-radius: 8px; padding: 10px;
    display: flex; flex-direction: column; gap: 8px;
  }}
  .seat-row {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; }}
  /* `.seat-row` sets an author display, so `[hidden]` needs an explicit author override too. */
  .seat-row[hidden] {{ display: none; }}
  .seat-label {{ font-weight: 600; color: #DFD5BD; }}
  .actions {{ margin-top: 18px; display: flex; justify-content: flex-end; }}
  button {{
    background: #2E7B76; border-color: #2E7B76; color: #F2EEDF; font-weight: 600;
    cursor: pointer;
  }}
  button:hover {{ filter: brightness(1.08); }}
</style>
</head>
<body>
  <main class="setup-card">
    <h1>Start A New Game</h1>
    <p>Leave Test position blank to deal a fresh setup, or start from a saved position.</p>
    <form method="post" action="/start">
      <div class="field">
        <label for="test_position">Test position</label>
        <select id="test_position" name="test_position">{playtest_options}</select>
      </div>
      <div class="field">
        <label id="player_count_label" for="player_count">Player count</label>
        <select id="player_count" name="player_count">{count_options}</select>
      </div>
      <div class="field">
        <label>Seat roles</label>
        <div class="seat-rows" id="seat-rows">{rows}</div>
      </div>
      <div class="field">
        <label for="setup_mode">Setup</label>
        <select id="setup_mode" name="setup_mode">
          <option value="{SETUP_MODE_RANDOM}" selected>Random</option>
          <option value="{SETUP_MODE_BASIC}" disabled>Basic (disabled)</option>
        </select>
      </div>
      <div class="field">
        <label id="seed_label" for="seed">Seed</label>
        <input id="seed" name="seed" type="number" required value="{suggested_seed}">
      </div>
      <div class="actions">
        <button type="submit">Start game</button>
      </div>
    </form>
  </main>
<script>
  (function () {{
    var testPosition = document.getElementById('test_position');
    var count = document.getElementById('player_count');
    var seed = document.getElementById('seed');
    var countLabel = document.getElementById('player_count_label');
    var seedLabel = document.getElementById('seed_label');
    var rows = document.querySelectorAll('[data-seat-row]');
    function selectedPosition() {{
      var option = testPosition.options[testPosition.selectedIndex];
      if (!option || option.value === '') {{ return null; }}
      return option;
    }}
    function effectivePlayerCount() {{
      var position = selectedPosition();
      if (position) {{
        var fromPosition = Number(position.getAttribute('data-player-count') || 0);
        if (fromPosition > 0) {{ return fromPosition; }}
      }}
      return Number(count.value || 4);
    }}
    function refreshRows() {{
      var selected = effectivePlayerCount();
      Array.prototype.forEach.call(rows, function (row) {{
        row.hidden = Number(row.getAttribute('data-seat-row')) > selected;
      }});
    }}
    function refreshPositionOverrides() {{
      var position = selectedPosition();
      if (!position) {{
        count.disabled = false;
        seed.disabled = false;
        countLabel.textContent = 'Player count';
        seedLabel.textContent = 'Seed';
        refreshRows();
        return;
      }}
      count.disabled = true;
      seed.disabled = true;
      var positionCount = position.getAttribute('data-player-count');
      var positionSeed = position.getAttribute('data-seed');
      countLabel.textContent = positionCount
        ? ('Player count (from selected test position: ' + positionCount + ')')
        : 'Player count (from selected test position)';
      seedLabel.textContent = positionSeed
        ? ('Seed (from selected test position: ' + positionSeed + ')')
        : 'Seed (from selected test position)';
      refreshRows();
    }}
    count.addEventListener('change', refreshRows);
    testPosition.addEventListener('change', refreshPositionOverrides);
    refreshPositionOverrides();
  }})();
</script>
</body>
</html>
"""


def _render_board_page(payload: dict, *, allow_reset_to_setup: bool) -> str:
    """Render the play board, optionally with a session-level return-to-setup control."""
    page = render_play_view_from_payload(payload)
    if not allow_reset_to_setup:
        return page
    style = """
<style>
  .session-reset {
    position: fixed;
    top: 12px;
    right: 12px;
    z-index: 20;
  }
  .session-reset button {
    font: 12px/1.2 Helvetica, Arial, sans-serif;
    border: 1px solid #5B3D2B;
    border-radius: 8px;
    background: #2A1A14;
    color: #EACFB7;
    padding: 8px 10px;
    cursor: pointer;
  }
  .session-reset button:hover { filter: brightness(1.08); }
</style>
"""
    control = (
        '<form class="session-reset" method="post" action="/new-game">'
        '<button type="submit">Start a new game (discard this game)</button></form>'
    )
    return page.replace("</head>", f"{style}</head>", 1).replace("<body>", f"<body>{control}", 1)


DECIDED_FIELDS = ("origin", "route", "selected_duty", "resolution")

# Fields answered by picking one stock out of the three. "Which stock grows" is the same question
# whichever field is asking it, so both are the same KIND of step and the page reveals the same
# affordance for either. A `None` here means this action has no such choice to make -- the field is
# optional precisely because most resolutions never ask -- so no step is emitted for it.
RESOURCE_CHOICE_FIELDS: tuple[str, ...] = ("tithe_resource", "taxation_step1_resource")

# Fields answered by pointing at a building where it stands on the round track. Same kind of step
# whichever field asks it, as with the stocks, and a `None` means this action does not ask -- a
# Construct that only lays road carries no building at all.
BUILDING_CHOICE_FIELDS: tuple[str, ...] = ("construct_building_id",)
HIRE_FIELDS: tuple[str, ...] = ("hired_building_id", "hired_building_source", "hire_payments")
HIRE_PAYMENT_FIELDS: tuple[str, ...] = ("hire_payments",)
# Action fields that identify one potentially hired building and where it is sourced from.
HIRE_PAYMENT_OWNER_FIELDS: tuple[tuple[str, str], ...] = (
    ("hired_building_id", "hired_building_source"),
    ("start_turn_building_id", "start_turn_building_source"),
    ("end_turn_building_id", "end_turn_building_source"),
    ("sow_route_building_id", "sow_route_building_source"),
    ("sow_route_secondary_building_id", "sow_route_secondary_building_source"),
    ("building_conversion_id", "building_conversion_source"),
    ("bank_payment_building_id", "bank_payment_building_source"),
    ("merchant_advance_building_id", "merchant_advance_building_source"),
    ("workforce_move_building_id", "workforce_move_building_source"),
    ("free_hire_target_building_id", "free_hire_target_building_source"),
    ("effective_acolyte_building_id", "effective_acolyte_building_source"),
)
START_TURN_RELOCATION_CHOICE_FIELDS: tuple[str, ...] = (
    "start_turn_building_id",
    "start_turn_building_source",
)
START_TURN_RELOCATION_TARGET_FIELDS: tuple[str, ...] = (
    "start_turn_relocation_from",
    "start_turn_relocation_to",
)
END_TURN_RELOCATION_CHOICE_FIELDS: tuple[str, ...] = (
    "end_turn_building_id",
    "end_turn_building_source",
)
END_TURN_RELOCATION_TARGET_FIELDS: tuple[str, ...] = (
    "end_turn_relocation_from",
    "end_turn_relocation_to",
)

# Fields that are only legal in certain COMBINATIONS, offered whole rather than one at a time.
# Setting one number and then the other would walk through states the engine never offered, and
# deciding which second number goes with a given first is a rule -- the engine's rule, which the
# page would then be keeping a second copy of. So the combinations that exist are the ones offered.
#
# Keyed off the resolution rather than off the values, the way `action_id` and `action_summary`
# already are, because zero is a legal amount and so cannot stand for "this action never asks".
#
# The verb travels with the row because these are not the same event: a paid alms hands stocks over
# and a Taxation bonus collects them, and a button reading "pay stone and silver" for the one that
# gives you both would be worse than no words at all.
COMBINATION_STEPS: tuple[tuple[str, str, tuple[tuple[str, str], ...]], ...] = (
    (
        "give_alms_paid",
        "pay",
        (("alms_payment_silver", "silver"), ("alms_payment_wheat", "wheat")),
    ),
)

# Combinations the engine states as a RUN OF NAMES rather than as a set of amounts: one name per
# unit, so ("stone", "stone") is two stone. Counted into amounts here and then offered exactly like
# the alms pair, because they are the same kind of question -- several stocks that are only legal
# together -- wearing a different spelling.
#
# Offered WHOLE, and this is the part that matters. The engine writes these runs canonically, in
# the order below, so ("silver", "stone") is spelled stone-first. Filtering them name by name would
# turn that spelling into a rule the player has to obey: press silver first and stone would go out,
# though a stone-and-silver bonus is perfectly legal. The mix is one answer and is asked for once.
COUNTED_COMBINATION_STEPS: tuple[tuple[str, str, str], ...] = (
    ("taxation", "take", "taxation_step2_resources"),
)

# The order amounts are spoken and encoded in. A display order only -- what may be taken is the
# engine's business, and every mix it offers is offered whichever way round this reads.
COMBINATION_STOCKS: tuple[str, ...] = ("stone", "silver", "wheat")
_ROUTE_BUILDING_CLOISTERS = "cloisters"
_ROUTE_BUILDING_KOGGE = "kogge"

# WHAT EACH QUESTION IS ASKING, IN WORDS. One per construction site below, and each is written
# beside the step it belongs to.
#
# Here rather than in the page because what a question ASKS is a fact about the action. The page
# knows a step is answered by pointing at a space; it does not know, and must not have to be told,
# that this particular space is where acolytes are lifted from. That is why three of these are the
# same KIND -- a position -- and say three different things.
#
# These are sentence tails. The actor is prefixed in `decision_steps` from `state.active_player`,
# so the visible line is always "player_id: <question>" and the page never composes one itself.
ORIGIN_PROMPT = "choose a space to lift acolytes from."
ROUTE_PROMPT = "follow an arrow."
DUTY_PROMPT = "choose a duty to take."
SKIP_PROMPT = "choose the City or Duty space on your route to leave unsown."
RESOLUTION_PROMPT = "Action or Tithe."
RESOURCE_PROMPT = "choose a resource."
BUILDING_PROMPT = "choose a building."
COMBINATION_PROMPT = "choose one."
MERCHANT_ADVANCE_PROMPT = "choose whether to use Guild."
SEAT_PROMPT = "choose first player for this round."
ARRANGEMENT_PROMPT = (
    "move acolytes from the Abbey to Special Activity and/or between Special Activities."
)
ORDINATION_PROMPT = "choose a serf to ordain, or an acolyte to send on mission."
START_RELOCATION_CHOICE_PROMPT = "choose a before-sow move, or move no one."
START_RELOCATION_SPACE_PROMPT = "choose the duty space for that move."
END_RELOCATION_CHOICE_PROMPT = "choose an after-turn move, or move no one."
END_RELOCATION_SPACE_PROMPT = "choose a duty space, or the Abbey, for that move."

_NUMBER_WORDS: tuple[str, ...] = ("zero", "one", "two", "three", "four", "five", "six")


def _amounts_in_words(verb: str, amounts: list[tuple[str, int]]) -> str:
    """A combination said in words, because a row of numbers is not a thing to read off a button.

    One of something is said without the number: "take stone and silver" rather than "take 1 stone
    and 1 silver", which is how anyone would say it out loud and is the whole reason for spelling
    these out at all. Beyond the small words it falls back to digits rather than growing a table of
    English numerals no mix on this board reaches.
    """
    spoken = []
    for noun, amount in amounts:
        if not amount:
            continue
        if amount == 1:
            spoken.append(noun)
        elif amount < len(_NUMBER_WORDS):
            spoken.append(f"{_NUMBER_WORDS[amount]} {noun}")
        else:
            spoken.append(f"{amount} {noun}")
    return f"{verb} {' and '.join(spoken)}" if spoken else f"{verb} nothing"


def _combination_step(
    verb: str,
    amounts: list[tuple[str, int]],
    *,
    prompt: str = COMBINATION_PROMPT,
) -> dict:
    """One whole combination as a step: a scalar to match it by and a sentence to read."""
    return {
        "kind": "combination",
        # A step value is matched with `===` in the page, so it has to be one scalar. Spelled out
        # rather than hashed, so a transcript of a turn stays readable. Every noun is written even
        # at zero, so two mixes cannot collide by one of them leaving a stock out.
        "value": ",".join(f"{noun}={amount}" for noun, amount in amounts),
        "label": _amounts_in_words(verb, amounts),
        # The label already says what each option does, so the prompt only has to say that one of
        # them is what is wanted. Naming the resolution here would be a second description of the
        # thing the labels are describing, kept in step by hand. Taxation's pill question is the
        # exception: its pills have no labels, so its prompt names the resource count instead.
        "prompt": prompt,
    }


def _resource_delta(before: Any, after: Any) -> dict[str, int]:
    return {
        resource: getattr(after.resources, resource) - getattr(before.resources, resource)
        for resource in COMBINATION_STOCKS
    }


_PREVIEW_EFFECT_FIELDS: tuple[str, ...] = (
    "resource_delta",
    "building_constructed",
    "merchant_advance",
    "alms_progress",
    "alms_threshold_reward",
)

# These are the action values that can change the effects previewed on a turn step. The values that
# do affect a payment or bonus stay here even when their own question is not currently shown by the
# page. The full route is summarized separately below: sowing moves acolytes, and only its settled
# effect on the selected duty can alter a resource diff.
_PREVIEW_EFFECT_ACTION_FIELDS: tuple[str, ...] = (
    "selected_duty",
    "resolution",
    "alms_payment_silver",
    "alms_payment_wheat",
    "donate_building_id",
    "ordination_steps",
    "taxation_step1_resource",
    "taxation_step2_resources",
    "construct_building_id",
    "start_turn_building_id",
    "start_turn_building_source",
    "end_turn_building_id",
    "end_turn_building_source",
    "sow_route_building_id",
    "sow_route_building_source",
    "sow_route_secondary_building_id",
    "sow_route_secondary_building_source",
    "bank_payment_building_id",
    "bank_payment_building_source",
    "bank_payment_replaced_resource",
    "bank_payment_silver_amount",
    "taxation_majority_building_id",
    "taxation_majority_building_source",
    "free_hire_enabler_building_id",
    "free_hire_target_building_id",
    "free_hire_target_building_source",
    "merchant_advance_building_id",
    "merchant_advance_building_source",
    "effective_acolyte_building_id",
    "effective_acolyte_building_source",
    "workforce_move_building_id",
    "workforce_move_building_source",
    "hired_building_id",
    "hired_building_source",
    "hire_payments",
    "tithe_resource",
)


def _preview_effect_action_key(action: Any) -> tuple[Any, ...] | None:
    if not isinstance(action, FullTurnAction):
        return None
    route = tuple(action.route or ())
    selected_duty = action.selected_duty
    return (
        *(getattr(action, field) for field in _PREVIEW_EFFECT_ACTION_FIELDS),
        # The route itself is a sequence of visible steps, but only its effect on the selected
        # duty can affect this diff. Keep that compact fact in the cache key so different route
        # spellings with the same settled duty value still share the engine application.
        len(route),
        action.origin == selected_duty,
        route.count(selected_duty),
        action.start_turn_relocation_from,
        action.start_turn_relocation_to,
    )


def _turn_action_preview_effects(
    action: Any,
    state: Any,
    config: Any,
    *,
    cache: dict[tuple[Any, ...], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """The state changes this complete action can expose on one of its steps.

    The action is applied once at the seam and the effects are diffed from the position the page
    started from. Round-end consequences are deliberately removed: they happen after the turn's
    choice has resolved and are not part of the preview surface.
    """
    cache_key = _preview_effect_action_key(action)
    if cache is not None and cache_key is not None and cache_key in cache:
        return dict(cache[cache_key])

    player = state.active_player
    before_player = state.player_state(player)
    try:
        result = apply_action(state, action, config)
    except ValueError:
        # A few enumerated modifier combinations are retained by the engine's action list even
        # though their final payment cannot be replayed from this position. They have no state
        # effect to preview; keep the existing legal-action surface intact and leave this step
        # undecorated rather than making page rendering reject the whole position.
        return {}
    after_player = result.state.player_state(player)
    effects: dict[str, Any] = {}

    resource_delta = _resource_delta_excluding_round_end(
        before_player,
        after_player,
        result.events,
        player_name=player.name.lower(),
    )
    if any(resource_delta.values()):
        effects["resource_delta"] = resource_delta

    before_buildings = before_player.player_board_slots.active_buildings
    after_buildings = after_player.player_board_slots.active_buildings
    constructed = [building_id for building_id in after_buildings if building_id not in before_buildings]
    if len(constructed) == 1 and getattr(action, "construct_building_id", None) == constructed[0]:
        effects["building_constructed"] = constructed[0]

    if getattr(action, "merchant_advance_building_id", None) == "guild":
        guild_event = next(
            (
                event
                for event in result.events
                if event.event_type is EventType.MERCHANT_ADVANCE
                and dict(event.details).get("cause") == "guild"
            ),
            None,
        )
        if guild_event is not None:
            to_position = dict(guild_event.details).get("to_position")
            if to_position in config.board.positions:
                effects["merchant_advance"] = config.board.positions.index(to_position)
    if getattr(action, "resolution", None) is not None and action.resolution.value == "give_alms_paid":
        progress_event = next(
            (
                event
                for event in result.events
                if event.event_type is EventType.ALMS_PROGRESS
            ),
            None,
        )
        if progress_event is not None:
            effects["alms_progress"] = dict(progress_event.details)
        threshold_rewards = [
            dict(event.details)
            for event in result.events
            if event.event_type is EventType.ALMS_THRESHOLD_REWARD
        ]
        if threshold_rewards:
            effects["alms_threshold_reward"] = threshold_rewards
    if cache is not None and cache_key is not None:
        cache[cache_key] = dict(effects)
    return effects


def _resource_delta_excluding_round_end(
    before: Any,
    after: Any,
    events: Any,
    *,
    player_name: str,
) -> dict[str, int]:
    """Diff resources while excluding cap and income consequences of ending a round."""
    resource_delta = _resource_delta(before, after)
    for event in events:
        details = dict(event.details)
        if event.event_type is EventType.EXCESS_RESOURCE_CAP:
            if details.get("player") != player_name:
                continue
            for resource in ("stone", "wheat"):
                before_key = f"{resource}_before"
                after_key = f"{resource}_after"
                if before_key in details and after_key in details:
                    resource_delta[resource] -= int(details[after_key]) - int(details[before_key])
        elif event.event_type is EventType.TRADE_ROUTE_INCOME:
            if details.get("player") != player_name:
                continue
            resource = str(details.get("resource", ""))
            if resource in resource_delta:
                resource_delta[resource] -= int(details.get("amount", 0))
    return resource_delta


def _attach_turn_action_preview_effects(
    steps: list[dict],
    effects: dict[str, Any],
) -> list[dict]:
    """Put effects on the step that settles them, never on the candidate envelope."""
    if not steps:
        return steps
    resource_delta = effects.get("resource_delta")
    if resource_delta is not None and not any("resource_delta" in step for step in steps):
        for step in reversed(steps):
            if step["kind"] in {
                "resolution",
                "hire",
                "resource",
                "combination",
                "building",
                "merchant_advance",
            }:
                step["resource_delta"] = resource_delta
                break
    building_id = effects.get("building_constructed")
    if building_id is not None:
        for step in steps:
            if step["kind"] == "building" and step["value"] == building_id:
                step["building_constructed"] = building_id
                break
    merchant_position = effects.get("merchant_advance")
    if merchant_position is not None:
        for step in steps:
            if step["kind"] == "merchant_advance":
                step["merchant_advance"] = merchant_position
                break
    alms_step = next(
        (
            step
            for step in steps
            if step["kind"] == "combination"
            and step.get("resource_allocation")
            and step.get("resource_allocation_any_total")
        ),
        None,
    )
    if alms_step is not None:
        if effects.get("alms_progress") is not None:
            alms_step["alms_progress"] = effects["alms_progress"]
        if effects.get("alms_threshold_reward") is not None:
            alms_step["alms_threshold_reward"] = effects["alms_threshold_reward"]
    return steps


def _resource_step_metadata(
    action: Any, state: Any | None, config: Any | None
) -> dict[str, dict[str, Any]]:
    """Attach engine-derived resource effects to the steps that expose them to the page.

    The action is applied and its player-resource state is diffed here, as with conversion silver.
    Taxation's engine events then separate that total into Step I and Step II gains; the page gets
    those maps and, for a partial Step II allocation, the one-unit maps it may replay per pill.
    """
    if state is None or config is None:
        return {}
    if not (
        getattr(action, "tithe_resource", None) is not None
        or getattr(action, "resolution", None) is not None
        and getattr(action.resolution, "value", None) == "taxation"
    ):
        return {}

    player = state.active_player
    before = state.player_state(player)
    result = apply_action(state, action, config)
    after = result.state.player_state(player)
    applied_delta = _resource_delta_excluding_round_end(
        before,
        after,
        result.events,
        player_name=player.name.lower(),
    )

    if action.resolution.value == "tithe":
        return {"tithe_resource": {"resource_delta": applied_delta}}

    taxation_events = [
        dict(event.details)
        for event in result.events
        if event.event_type is EventType.TAXATION and event.actor is player
    ]
    step_1 = next(
        details["resource"]
        for details in taxation_events
        if details.get("step") == "step_1"
    )
    step_2_text = next(
        details.get("resources", "")
        for details in taxation_events
        if details.get("step") == "step_2"
    )
    step_2 = tuple(resource for resource in step_2_text.split(",") if resource)

    def one_unit(resource: str) -> dict[str, int]:
        return {
            name: int(name == resource)
            for name in COMBINATION_STOCKS
        }

    return {
        "taxation_step1_resource": {"resource_delta": one_unit(step_1)},
        "taxation_step2_resources": {
            "resource_delta": {
                resource: step_2.count(resource) for resource in COMBINATION_STOCKS
            },
            "resource_unit_deltas": {
                resource: one_unit(resource) for resource in COMBINATION_STOCKS
            },
        },
    }


def _hire_source_phrase(source: str) -> str:
    if source == "market":
        return "the market"
    if source == "own_active":
        return "your board"
    return source


def _hire_step(
    action: FullTurnAction,
    state: Any,
    config: Any,
) -> tuple[dict, tuple[str, ...]]:
    if action.hired_building_id is None:
        return (
            {
                "kind": "hire",
                "value": "none",
                "label": "Don't hire",
                "prompt": COMBINATION_PROMPT,
            },
            HIRE_FIELDS,
        )

    building_id = action.hired_building_id
    source_label = action.hired_building_source or "unknown"
    source = building_ability_source(
        state,
        config,
        acting_player=state.active_player,
        building_key=building_id,
    )
    payment_resource = source.hire_resource or "unknown"
    building_name = building_by_id(config.buildings, building_id).name
    return (
        {
            "kind": "hire",
            # One scalar so the page can match with `===`.
            "value": f"{building_id}:{source_label}",
            "label": (
                f"Hire the {building_name} from {_hire_source_phrase(source_label)}"
                f" - {source.hire_cost} {payment_resource}"
            ),
            "prompt": COMBINATION_PROMPT,
        },
        HIRE_FIELDS,
    )


def _hire_payment_map(action: FullTurnAction) -> dict[str, str]:
    """Hire payment resources keyed by hired building id for one action."""
    return {
        building_id: resource
        for building_id, resource in tuple(action.hire_payments or ())
    }


def _hire_payment_resource_steps(
    action: FullTurnAction,
    *,
    asked_buildings: tuple[str, ...],
) -> list[tuple[dict, tuple[str, ...]]]:
    """One stock-choice step per open hire payment resource question."""
    payments = _hire_payment_map(action)
    steps: list[tuple[dict, tuple[str, ...]]] = []
    for building_id in asked_buildings:
        resource = payments.get(building_id)
        if resource is None:
            raise ValueError(
                f"Missing hire payment for asked building {building_id!r} on action {action_id(action)}."
            )
        steps.append(
            (
                {"kind": "resource", "value": resource, "prompt": RESOURCE_PROMPT},
                HIRE_PAYMENT_FIELDS,
            )
        )
    return steps


def _merchant_advance_step(action: FullTurnAction) -> tuple[dict, tuple[str, ...]]:
    """The optional Guild use, offered as one whole choice beside other combinations."""
    building_id = action.merchant_advance_building_id
    source = action.merchant_advance_building_source
    if building_id is None:
        return (
            {
                "kind": "merchant_advance",
                "value": "guild:none",
                "label": "Do not use Guild",
                "prompt": MERCHANT_ADVANCE_PROMPT,
            },
            ("merchant_advance_building_id", "merchant_advance_building_source"),
        )
    source_text = _hire_source_phrase(source or "unknown")
    return (
        {
            "kind": "merchant_advance",
            "value": f"{building_id}:{source or 'unknown'}",
            "label": f"Use Guild from {source_text} to move the Merchant",
            "prompt": MERCHANT_ADVANCE_PROMPT,
        },
        ("merchant_advance_building_id", "merchant_advance_building_source"),
    )


def _start_relocation_phrase(building_id: str) -> str:
    if building_id == "dormitory":
        return "bring an acolyte into the City"
    if building_id == "inquisition":
        return "send an acolyte out of the City"
    return "move one acolyte along a City spoke"


def _end_relocation_phrase(building_id: str) -> str:
    if building_id == "library":
        return "send an acolyte out of the City after this turn resolves"
    return "move one acolyte along a City spoke after this turn resolves"


def _relocation_choice_value(
    action: FullTurnAction,
    *,
    building_id: str,
    source_label: str,
) -> str:
    return f"{building_id}:{source_label}"


def _relocation_choice_label(
    action: FullTurnAction,
    state: Any,
    config: Any,
    *,
    building_id: str,
    source_label: str,
    phrase: str,
) -> str:
    building_name = building_by_id(config.buildings, building_id).name
    if source_label == "own_active":
        return f"{building_name}, your board: {phrase}"
    source = building_ability_source(
        state,
        config,
        acting_player=state.active_player,
        building_key=building_id,
    )
    paid_resource = source.hire_resource or "unknown"
    return (
        f"{building_name}, hire from {_hire_source_phrase(source_label)}"
        f" for {source.hire_cost} {paid_resource}: {phrase}"
    )


def _start_turn_relocation_choice_step(
    action: FullTurnAction,
    state: Any,
    config: Any,
) -> tuple[dict, tuple[str, ...]]:
    if action.start_turn_building_id is None:
        return (
            {
                "kind": "start_relocation_choice",
                "value": "none",
                "label": "Move no one",
                "prompt": START_RELOCATION_CHOICE_PROMPT,
            },
            START_TURN_RELOCATION_CHOICE_FIELDS,
        )
    building_id = action.start_turn_building_id
    source_label = action.start_turn_building_source or "unknown"
    return (
        {
            "kind": "start_relocation_choice",
            "value": _relocation_choice_value(
                action,
                building_id=building_id,
                source_label=source_label,
            ),
            "label": _relocation_choice_label(
                action,
                state,
                config,
                building_id=building_id,
                source_label=source_label,
                phrase=_start_relocation_phrase(building_id),
            ),
            "prompt": START_RELOCATION_CHOICE_PROMPT,
        },
        START_TURN_RELOCATION_CHOICE_FIELDS,
    )


def _start_turn_relocation_target_step(
    action: FullTurnAction,
) -> tuple[dict, tuple[str, ...]] | None:
    if action.start_turn_building_id is None:
        return None
    building_id = action.start_turn_building_id
    if building_id == "dormitory":
        value = action.start_turn_relocation_from
    elif building_id == "inquisition":
        value = action.start_turn_relocation_to
    else:
        raise ValueError(f"Unsupported start-turn relocation building {building_id!r}.")
    if value is None:
        raise ValueError("Start-turn relocation target is missing.")
    return (
        {
            "kind": "start_relocation_space",
            "value": value,
            "prompt": START_RELOCATION_SPACE_PROMPT,
        },
        START_TURN_RELOCATION_TARGET_FIELDS,
    )


def _end_turn_relocation_choice_step(
    action: FullTurnAction,
    state: Any,
    config: Any,
) -> tuple[dict, tuple[str, ...]]:
    if action.end_turn_building_id is None:
        return (
            {
                "kind": "end_relocation_choice",
                "value": "none",
                "label": "Move no one",
                "prompt": END_RELOCATION_CHOICE_PROMPT,
            },
            END_TURN_RELOCATION_CHOICE_FIELDS,
        )
    building_id = action.end_turn_building_id
    source_label = action.end_turn_building_source or "unknown"
    return (
        {
            "kind": "end_relocation_choice",
            "value": _relocation_choice_value(
                action,
                building_id=building_id,
                source_label=source_label,
            ),
            "label": _relocation_choice_label(
                action,
                state,
                config,
                building_id=building_id,
                source_label=source_label,
                phrase=_end_relocation_phrase(building_id),
            ),
            "prompt": END_RELOCATION_CHOICE_PROMPT,
        },
        END_TURN_RELOCATION_CHOICE_FIELDS,
    )


def _end_turn_relocation_target_step(
    action: FullTurnAction,
) -> tuple[dict, tuple[str, ...]] | None:
    if action.end_turn_building_id is None:
        return None
    value = action.end_turn_relocation_to
    if value is None:
        raise ValueError("End-turn relocation target is missing.")
    return (
        {
            "kind": "end_relocation_space",
            "value": value,
            "prompt": END_RELOCATION_SPACE_PROMPT,
        },
        END_TURN_RELOCATION_TARGET_FIELDS,
    )


def _arrangement_value(action: Any) -> str:
    """Allocation answer encoded as one scalar, keyed by where cubes end up and not by move order."""
    outcome = allocation_outcome(action.allocation_moves)
    if not outcome:
        return "none"
    return ",".join(
        f"{slot}={delta:+d}"
        for slot, delta in outcome
    )


def _ordination_value(action: Any) -> str:
    """Ordination answer encoded as one scalar, keyed by outcome and not by step order."""
    counts = dict(ordination_outcome(action.ordination_steps))
    ordain = int(counts.get("ordain", 0))
    mission = int(counts.get("mission", 0))
    parts: list[str] = []
    if ordain:
        parts.append(f"ordain={ordain}")
    if mission:
        parts.append(f"mission={mission}")
    return ",".join(parts) if parts else "none"


def _confession_in_words(action: Any) -> str:
    """The one sentence a player reads to make this choice, source and all.

    The source is spelled out rather than left to be inferred from the board, because the three of
    them cost different things and are owed to different people: your own is free, the market's is
    paid to the bank, and another player's is paid to that player.
    """
    if not action.use:
        return "decline the Confession Box"
    if action.source == "own_active":
        return "use your own Confession Box"
    if action.source == "market":
        return "hire the Confession Box from the market"
    # The seat is left in the engine's own name. It used to be spelled out here as "player one",
    # which read better than the id and was wrong in the same way -- white is not the first chair
    # -- and it was a second place that decided what a seat is called. The page has one door for
    # that now, and this goes through it like every other sentence.
    return f"hire the Confession Box from {action.source}"


def _presented(
    action: Any,
    *,
    state: Any | None = None,
    config: Any | None = None,
    offer_hire: bool = False,
    hire_payment_buildings: tuple[str, ...] = (),
    offer_merchant_advance: bool = False,
    include_preview_effects: bool = True,
) -> list[tuple[dict, tuple[str, ...]]]:
    """Each further question this page can put about one action, with the fields it answers.

    Emitted after the resolution because they are answers to it: which stock a tithe takes is only
    a question once tithe is what is happening. Whether a step appears at all is therefore settled
    by the resolution, which is an earlier step, so every action in a group carries the same ones.

    The fields are kept BESIDE the step rather than inside it. They are this side's business -- how
    the refusal knows what has been asked -- and a page holding the name of a field would be a page
    that could come to depend on it, which is how the next one ends up being a special case.
    """
    resource_step_metadata = (
        _resource_step_metadata(action, state, config)
        if include_preview_effects
        else {}
    )
    if isinstance(action, StartPlayerConfessionBoxAction):
        # A `combination` and not a kind of its own, because the shape is the one the alms pair and
        # the taxation mix already have: several fields that only go together one way, offered whole
        # as a labelled option. Splitting `use` from `source` would put a question to a player who
        # declined about where they were not going to hire it from.
        #
        # The turn panel, deliberately. The three places a box can be reached from -- your own
        # board, the market on the map, another player's board -- are three different surfaces, so
        # no one of them can hold the choice; putting it on the map would light the market copy and
        # quietly hide that using your own is even an option.
        return [
            (
                {
                    "kind": "combination",
                    "value": "decline" if not action.use else f"use:{action.source}",
                    "label": _confession_in_words(action),
                    "prompt": COMBINATION_PROMPT,
                },
                ("use", "source"),
            )
        ]
    if isinstance(action, StartPlayerSelectionAction):
        # Answered by pointing at a player's board, so it is a `seat` the way a duty is a
        # `position` -- the kind says where the answer is given and nothing about what it means.
        # The value is the player, because that is what the engine is asking for and what the
        # boards are already stamped with; which chair that player sits in is the page's business
        # and is settled by the seating order there, not translated into a number here.
        return [
            (
                {
                    "kind": "seat",
                    "value": action.chosen_start_player.name.lower(),
                    "prompt": SEAT_PROMPT,
                },
                ("chosen_start_player",),
            )
        ]
    presented: list[tuple[dict, tuple[str, ...]]] = []
    if offer_hire and isinstance(action, FullTurnAction):
        if state is None or config is None:
            raise ValueError("state and config are required to present hire choices.")
        # ASK HIRE BEFORE RESOLUTION-SPECIFIC EFFECT STEPS.
        #
        # A branch that spends to modify a duty asks that cost first, even if only one spend path
        # survives. For outcomes keyed by net effect (allocation/ordination) this keeps the price
        # decision ahead of the outcome question; for counted/composed effects (alms payments) it
        # keeps "pay this cost" ahead of "spend these stocks".
        presented.append(_hire_step(action, state, config))
    if isinstance(action, FullTurnAction) and hire_payment_buildings:
        # Wildcard hires (Cornucopia) are paid from a chosen stock. Ask that stock before any
        # resolution-specific effect steps spend or award resources.
        presented.extend(
            _hire_payment_resource_steps(
                action,
                asked_buildings=hire_payment_buildings,
            )
        )
    if offer_merchant_advance and isinstance(action, FullTurnAction):
        presented.append(_merchant_advance_step(action))
    for name in RESOURCE_CHOICE_FIELDS:
        value = getattr(action, name, None)
        if value is not None:
            step = {"kind": "resource", "value": value, "prompt": RESOURCE_PROMPT}
            step.update(resource_step_metadata.get(name, {}))
            presented.append((step, (name,)))
    for name in BUILDING_CHOICE_FIELDS:
        value = getattr(action, name, None)
        if value is not None:
            presented.append(
                ({"kind": "building", "value": value, "prompt": BUILDING_PROMPT}, (name,))
            )
    for resolution, verb, fields in COMBINATION_STEPS:
        if action.resolution.value != resolution:
            continue
        amounts = [(noun, getattr(action, name)) for name, noun in fields]
        step = _combination_step(
            verb,
            amounts,
            prompt=("choose payment." if resolution == "give_alms_paid" else COMBINATION_PROMPT),
        )
        if resolution == "give_alms_paid":
            step["resource_allocation"] = True
            step["resource_allocation_any_total"] = True
        presented.append((step, tuple(name for name, _noun in fields)))
    for resolution, verb, name in COUNTED_COMBINATION_STEPS:
        if action.resolution.value != resolution:
            continue
        taken = tuple(getattr(action, name, ()) or ())
        amounts = [(noun, taken.count(noun)) for noun in COMBINATION_STOCKS]
        step = _combination_step(
            verb,
            amounts,
            prompt=f"choose {len(taken)} resources.",
        )
        step["resource_allocation"] = True
        step["resource_total"] = len(taken)
        step.update(resource_step_metadata.get(name, {}))
        presented.append((step, (name,)))
    if action.resolution.value == "allocation":
        presented.append(
            (
                {
                    "kind": "arrangement",
                    "value": _arrangement_value(action),
                    "prompt": ARRANGEMENT_PROMPT,
                },
                ("allocation_moves",),
            )
        )
    if action.resolution.value == "ordination":
        presented.append(
            (
                {
                    "kind": "ordination",
                    "value": _ordination_value(action),
                    "prompt": ORDINATION_PROMPT,
                },
                ("ordination_steps",),
            )
        )
    return presented


def _presented_rows(
    action: Any,
    *,
    state: Any | None = None,
    config: Any | None = None,
    offer_hire: bool = False,
    hire_payment_buildings: tuple[str, ...] = (),
    offer_merchant_advance: bool = False,
    include_preview_effects: bool = True,
) -> list[tuple[dict, tuple[str, ...]]]:
    """Call `_presented`, while still allowing tests to monkeypatch the old one-arg shape."""
    try:
        return _presented(
            action,
            state=state,
            config=config,
            offer_hire=offer_hire,
            hire_payment_buildings=hire_payment_buildings,
            offer_merchant_advance=offer_merchant_advance,
            include_preview_effects=include_preview_effects,
        )
    except TypeError as exc:
        if "unexpected keyword argument" not in str(exc):
            raise
        return _presented(action)


def _presented_steps(
    action: Any,
    *,
    state: Any | None = None,
    config: Any | None = None,
    offer_hire: bool = False,
    hire_payment_buildings: tuple[str, ...] = (),
    offer_merchant_advance: bool = False,
    include_preview_effects: bool = True,
) -> list[dict]:
    return [
        step
        for step, _fields in _presented_rows(
            action,
            state=state,
            config=config,
            offer_hire=offer_hire,
            hire_payment_buildings=hire_payment_buildings,
            offer_merchant_advance=offer_merchant_advance,
            include_preview_effects=include_preview_effects,
        )
    ]


def _position_name(position: int) -> str:
    """Engine position name for one index, in the canonical order view payloads carry."""
    return CANONICAL_POSITION_NAMES[position]


def _route_step_values(origin: int, route: tuple[int, ...]) -> tuple[str, ...]:
    path = (origin, *route)
    return tuple(
        f"{_position_name(path[index])}->{_position_name(path[index + 1])}"
        for index in range(len(route))
    )


@lru_cache(maxsize=4096)
def _cloisters_candidate_walk_lookup(
    *,
    origin: int,
    actual_route: tuple[int, ...],
    omitted_location: int,
    board: Any,
    combined_with_kogge: bool,
) -> tuple[tuple[int, ...], int]:
    """Recover the N+1 candidate walk that produced one Cloisters action.

    Keyed by exactly what the action carries (`origin`, actual route, omitted location). The key is
    expected to map to one and only one candidate walk; this is asserted loudly rather than guessed.
    """
    picked_up = len(actual_route)
    key = (origin, actual_route, omitted_location)
    matches: set[tuple[tuple[int, ...], int]] = set()
    if combined_with_kogge:
        allowed_locations = _allowed_cloisters_omission_locations(board)
        for candidate_walk in kogge_cloisters_candidate_placements(
            origin=origin,
            picked_up=picked_up,
            board=board,
        ):
            for omitted_index, candidate_omission in enumerate(candidate_walk):
                if candidate_omission not in allowed_locations:
                    continue
                actual = cloisters_actual_placements_after_omission(
                    candidate_walk,
                    omitted_index=omitted_index,
                )
                if (origin, actual, candidate_omission) == key:
                    matches.add((candidate_walk, omitted_index))
    else:
        for candidate_walk in cloisters_candidate_placements(
            origin=origin,
            picked_up=picked_up,
            board=board,
        ):
            for omitted_index, candidate_omission in cloisters_candidate_omissions(
                origin=origin,
                candidate_placements=candidate_walk,
            ):
                actual = cloisters_actual_placements_after_omission(
                    candidate_walk,
                    omitted_index=omitted_index,
                )
                if (origin, actual, candidate_omission) == key:
                    matches.add((candidate_walk, omitted_index))
    if not matches:
        raise AssertionError(
            "No candidate Cloisters walk matched action key "
            f"(origin={origin}, route={actual_route}, omitted={omitted_location}, "
            f"combined_with_kogge={combined_with_kogge})."
        )
    if len(matches) != 1:
        raise AssertionError(
            "Expected one candidate Cloisters walk per action key, found "
            f"{len(matches)} for (origin={origin}, route={actual_route}, omitted={omitted_location}, "
            f"combined_with_kogge={combined_with_kogge})."
        )
    return next(iter(matches))


def _route_destinations_for_steps(action: Any, config: Any) -> tuple[tuple[int, ...], int | None]:
    """Destinations for offered edge steps, plus omitted index where Cloisters skipped one."""
    route = tuple(getattr(action, "route", ()) or ())
    if not (
        isinstance(action, FullTurnAction)
        and action.sow_route_omitted_location is not None
    ):
        return route, None
    combined_with_kogge = (
        action.sow_route_building_id == _ROUTE_BUILDING_KOGGE
        and action.sow_route_secondary_building_id == _ROUTE_BUILDING_CLOISTERS
    )
    return _cloisters_candidate_walk_lookup(
        origin=action.origin,
        actual_route=route,
        omitted_location=action.sow_route_omitted_location,
        board=config.board,
        combined_with_kogge=combined_with_kogge,
    )


def _resolution_context_key(action: FullTurnAction, config: Any) -> tuple[Any, ...]:
    edge_destinations, _omitted_index = _route_destinations_for_steps(action, config)
    return (
        action.origin,
        *_route_step_values(action.origin, edge_destinations),
        action.selected_duty,
        action.resolution.value,
    )


def _action_hires_building(action: FullTurnAction) -> bool:
    return action.hired_building_id is not None


def _action_uses_start_turn_relocation(action: FullTurnAction) -> bool:
    return action.start_turn_building_id is not None


def _action_uses_end_turn_relocation(action: FullTurnAction) -> bool:
    return action.end_turn_building_id is not None


def _steps_key(steps: list[dict]) -> tuple[Any, ...]:
    return tuple(
        tuple(step["value"]) if isinstance(step["value"], tuple) else step["value"] for step in steps
    )


_FULL_TURN_FIELDS_EXCEPT_ROUTE: tuple[str, ...] = tuple(
    field.name for field in dataclasses.fields(FullTurnAction) if field.name != "route"
)


def _cloisters_route_outcome_key(action: FullTurnAction) -> tuple[Any, ...] | None:
    """Outcome key for Cloisters spellings where route order can be presentation-only."""
    if action.sow_route_omitted_location is None:
        return None
    route = tuple(action.route or ())
    return (
        tuple(sorted(route)),
        *(getattr(action, name) for name in _FULL_TURN_FIELDS_EXCEPT_ROUTE),
    )


def _dedupe_cloisters_route_spellings(members: list[Any]) -> list[Any]:
    """Drop duplicate Cloisters spellings that differ only by route-order permutation.

    Candidate groups are already partitioned by asked step values, so this runs within one decision
    frontier and keeps first-seen order. Non-Cloisters actions are returned untouched.
    """
    if len(members) < 2:
        return members
    deduped: list[Any] = []
    seen: set[tuple[Any, ...]] = set()
    for member in members:
        if not isinstance(member, FullTurnAction):
            deduped.append(member)
            continue
        key = _cloisters_route_outcome_key(member)
        if key is None:
            deduped.append(member)
            continue
        if key in seen:
            continue
        seen.add(key)
        deduped.append(member)
    return deduped


def _hire_contexts(actions: list[Any], config: Any) -> set[tuple[Any, ...]]:
    """Prefixes where at least one legal action hires a building.

    A cost is asked before it is paid, even where hire would otherwise be inferred from a single
    surviving branch. Context-level so "Don't hire" is available beside each hire option.
    """
    return {
        _resolution_context_key(action, config)
        for action in actions
        if isinstance(action, FullTurnAction) and _action_hires_building(action)
    }


def _steps_before_hire_payment_questions(
    action: Any,
    player_id: str,
    *,
    state: Any,
    config: Any,
    offer_hire: bool = False,
    offer_start_turn_relocation: bool = False,
    offer_merchant_advance: bool = False,
    include_preview_effects: bool = True,
) -> list[dict]:
    """Decision steps through the hire choice, stopping before any hire-payment stock choice."""
    if isinstance(action, (StartPlayerConfessionBoxAction, StartPlayerSelectionAction)):
        return _address_steps(
            _presented_steps(
                action,
                state=state,
                config=config,
                offer_hire=offer_hire,
                offer_merchant_advance=offer_merchant_advance,
                include_preview_effects=include_preview_effects,
            ),
            player_id,
        )

    edge_destinations, omitted_edge_index = _route_destinations_for_steps(action, config)
    edge_values = _route_step_values(action.origin, edge_destinations)
    edge_counters = _edge_counters(
        action,
        edge_destinations=edge_destinations,
        omitted_edge_index=omitted_edge_index,
    )
    counter = _counter_start(action)
    steps: list[dict] = []
    if isinstance(action, FullTurnAction) and offer_start_turn_relocation:
        start_choice, _fields = _start_turn_relocation_choice_step(action, state, config)
        steps.append(start_choice)
        start_target = _start_turn_relocation_target_step(action)
        if start_target is not None:
            steps.append(start_target[0])
    steps.append(
        {
            "kind": "origin",
            "value": action.origin,
            "prompt": ORIGIN_PROMPT,
            "counter": counter,
        }
    )
    steps += [
        {
            "kind": "edge",
            "value": value,
            "prompt": ROUTE_PROMPT,
            "counter": edge_counters[index],
        }
        for index, value in enumerate(edge_values)
    ]
    if isinstance(action, SetupSowAction):
        return _address_steps(steps, player_id)
    if action.sow_route_omitted_location is not None:
        steps.append(
            {
                "kind": "skip",
                "value": action.sow_route_omitted_location,
                "prompt": SKIP_PROMPT,
            }
        )
    steps.append({"kind": "duty", "value": action.selected_duty, "prompt": DUTY_PROMPT})
    steps.append(
        {"kind": "resolution", "value": action.resolution.value, "prompt": RESOLUTION_PROMPT}
    )
    if offer_hire and isinstance(action, FullTurnAction):
        hire_step, _fields = _hire_step(action, state, config)
        steps.append(hire_step)
    if offer_merchant_advance and isinstance(action, FullTurnAction):
        merchant_step, _fields = _merchant_advance_step(action)
        steps.append(merchant_step)
    return _address_steps(steps, player_id)


def _hire_payment_question_buildings_by_action_id(
    actions: list[Any],
    *,
    player_id: str,
    state: Any,
    config: Any,
    offer_hire_by_action_id: dict[str, bool],
    offer_start_turn_relocation: bool,
    offer_merchant_advance_by_action_id: dict[str, bool] | None = None,
    include_preview_effects: bool = True,
) -> dict[str, tuple[str, ...]]:
    """Per action, which hired buildings still need a stock-choice question."""
    action_with_ids = [(action, action_id(action)) for action in actions]
    offer_merchant_advance_by_action_id = offer_merchant_advance_by_action_id or {}
    by_action_id: dict[str, tuple[str, ...]] = {
        move_id: tuple()
        for _action, move_id in action_with_ids
    }
    members_by_context: dict[tuple[Any, ...], list[tuple[FullTurnAction, str]]] = {}
    for action, move_id in action_with_ids:
        key = _steps_key(
            _steps_before_hire_payment_questions(
                action,
                player_id,
                state=state,
                config=config,
                offer_hire=offer_hire_by_action_id[move_id],
                offer_start_turn_relocation=offer_start_turn_relocation,
                offer_merchant_advance=offer_merchant_advance_by_action_id.get(move_id, False),
                include_preview_effects=include_preview_effects,
            )
        )
        if isinstance(action, FullTurnAction):
            members_by_context.setdefault(key, []).append((action, move_id))

    for members in members_by_context.values():
        if not members:
            continue
        payment_map_by_action_id = {
            move_id: _hire_payment_map(member)
            for member, move_id in members
        }

        shared_open: set[str] = set()
        shared_buildings = set(payment_map_by_action_id[members[0][1]])
        for _member, move_id in members[1:]:
            shared_buildings &= set(payment_map_by_action_id[move_id])
        for building_id in shared_buildings:
            if len(
                {
                    payment_map_by_action_id[move_id][building_id]
                    for _member, move_id in members
                }
            ) > 1:
                shared_open.add(building_id)

        resources_by_key: collections.defaultdict[tuple[str, str, Any], set[str]] = (
            collections.defaultdict(set)
        )
        for other, other_id in members:
            payments = payment_map_by_action_id[other_id]
            for id_field, source_field in HIRE_PAYMENT_OWNER_FIELDS:
                building_id = getattr(other, id_field)
                if building_id is None or building_id not in payments:
                    continue
                key = (id_field, building_id, getattr(other, source_field))
                resources_by_key[key].add(payments[building_id])

        for member, move_id in members:
            asked: set[str] = set(shared_open)
            payments = payment_map_by_action_id[move_id]
            for id_field, source_field in HIRE_PAYMENT_OWNER_FIELDS:
                building_id = getattr(member, id_field)
                if building_id is None or building_id not in payments:
                    continue
                source = getattr(member, source_field)
                if len(resources_by_key[(id_field, building_id, source)]) > 1:
                    asked.add(building_id)

            ordered = tuple(
                building_id
                for building_id, _resource in tuple(member.hire_payments or ())
                if building_id in asked
            )
            by_action_id[move_id] = ordered

    return by_action_id


def _speaking_player_id(state: Any) -> str:
    """The acting player as an engine id string."""
    active = getattr(state, "active_player", None)
    if isinstance(active, enum.Enum):
        return active.name.lower()
    return str(active)


def _addressed(prompt: str, player_id: str) -> str:
    """One prompt as the seat's own spoken line."""
    return f"{player_id}: {prompt}"


def _address_steps(steps: list[dict], player_id: str) -> list[dict]:
    """A copy of these steps with each prompt prefixed by the acting player id."""
    addressed = []
    for step in steps:
        if "prompt" in step:
            addressed.append(dict(step, prompt=_addressed(step["prompt"], player_id)))
        else:
            addressed.append(dict(step))
    return addressed


def _counter_start(action: Any) -> int:
    """How many cubes this route lifts before any edge is followed."""
    route = tuple(getattr(action, "route", ()) or ())
    return len(route)


def _edge_counters(
    action: Any,
    *,
    edge_destinations: tuple[int, ...],
    omitted_edge_index: int | None = None,
) -> tuple[int, ...]:
    """Counter value after each offered edge step for this action."""
    counter = _counter_start(action)
    if omitted_edge_index is None:
        return tuple(counter - (index + 1) for index in range(len(edge_destinations)))
    values: list[int] = []
    remaining = counter
    for index, _destination in enumerate(edge_destinations):
        # Before skip is answered several candidates can still stand, and they can genuinely
        # disagree on cubes-in-hand at the same click because they are skipping different spaces.
        if index != omitted_edge_index:
            remaining -= 1
        values.append(remaining)
    return tuple(values)


def _covered_fields(
    action: Any,
    state: Any,
    config: Any,
    *,
    offer_hire: bool = False,
    hire_payment_buildings: tuple[str, ...] = (),
    offer_start_turn_relocation: bool = False,
    offer_end_turn_relocation: bool = False,
    offer_merchant_advance: bool = False,
    include_preview_effects: bool = True,
) -> set[str]:
    """Which residue fields this action's steps actually answer.

    Read off the steps that were really emitted, so a field the page can ask about in principle but
    did not ask about here still belongs in the refusal.
    """
    covered = {
        name
        for _step, fields in _presented_rows(
            action,
            state=state,
            config=config,
            offer_hire=offer_hire,
            hire_payment_buildings=hire_payment_buildings,
            offer_merchant_advance=offer_merchant_advance,
            include_preview_effects=include_preview_effects,
        )
        for name in fields
    }
    if isinstance(action, FullTurnAction) and offer_start_turn_relocation:
        covered.update(START_TURN_RELOCATION_CHOICE_FIELDS)
        if action.start_turn_building_id is not None:
            covered.update(START_TURN_RELOCATION_TARGET_FIELDS)
    if isinstance(action, FullTurnAction) and offer_end_turn_relocation:
        covered.update(END_TURN_RELOCATION_CHOICE_FIELDS)
        if action.end_turn_building_id is not None:
            covered.update(END_TURN_RELOCATION_TARGET_FIELDS)
    if isinstance(action, FullTurnAction) and action.sow_route_omitted_location is not None:
        covered.add("sow_route_omitted_location")
    return covered


def _residue_fields(action: Any) -> tuple[str, ...]:
    """Everything an action carries that the page does not ask about by name.

    Read off the action in hand rather than off one type, because there is more than one kind of
    action now: a start-player selection carries one field and a full turn some forty, and the page
    presents a handful of the second and none of the first.
    """
    return tuple(
        field.name
        for field in dataclasses.fields(action)
        if field.name not in DECIDED_FIELDS
        and field.name != "action_type"
    )


def decision_steps(
    action: Any,
    player_id: str,
    *,
    state: Any,
    config: Any,
    offer_hire: bool = False,
    hire_payment_buildings: tuple[str, ...] = (),
    offer_start_turn_relocation: bool = False,
    offer_end_turn_relocation: bool = False,
    offer_merchant_advance: bool = False,
    preview_effects: dict[str, Any] | None = None,
    include_preview_effects: bool = True,
) -> list[dict]:
    """The questions this action is an answer to, in the order the page asks them.

    A start-turn relocation choice (where offered), then origin, then the route one space at a
    time, then (for Cloisters walks) which City/Duty space is left unsown, then which duty was
    selected, then what to do with it, then any explicit hire and wildcard-hire stock choices, then
    whatever that resolution goes on to ask, then the Library relocation choice (where offered). A
    setup sow stops after the route because that is all it has.

    Each step says what KIND of thing it is, because they are not answered in the same place -- and
    five of them now share one surface and still have to stay distinct on it. `origin`, `skip`,
    `duty`, `start_relocation_space` and `end_relocation_space` are all answered by pointing at a
    wheel space (with `end_relocation_space=abbey` answered on an Abbey token), and are distinct
    kinds so the page can mark each question differently without consulting field names or writing a
    second copy of what any one means. The others are still separated by where they are answered: a
    resolution is beside the board, a stock is on the asking seat's own board, a seat is a whole
    board, a building is a hex on the round track, and a combination is a set of amounts that only
    go together one way.

    Route length is not fixed. It is however many acolytes were lifted, so it varies by origin and
    by turn, and nothing here or on the page may assume a number.
    """
    # A start-player selection is one question and nothing before it. There is no origin to lift
    # from and no duty to resolve: whoever holds the marker names a player, and that is the whole
    # of the action.
    if isinstance(action, (StartPlayerConfessionBoxAction, StartPlayerSelectionAction)):
        return _address_steps(
            _presented_steps(
                action,
                state=state,
                config=config,
                offer_hire=offer_hire,
                hire_payment_buildings=hire_payment_buildings,
                offer_merchant_advance=offer_merchant_advance,
                include_preview_effects=include_preview_effects,
            ),
            player_id,
        )
    # The route still walks spaces by index. What changed is the kind names for the two space
    # questions around it: where to lift from (`origin`) and which duty to take (`duty`).
    edge_destinations, omitted_edge_index = _route_destinations_for_steps(action, config)
    edge_values = _route_step_values(action.origin, edge_destinations)
    edge_counters = _edge_counters(
        action,
        edge_destinations=edge_destinations,
        omitted_edge_index=omitted_edge_index,
    )
    counter = _counter_start(action)
    steps: list[dict] = []
    if isinstance(action, FullTurnAction) and offer_start_turn_relocation:
        start_choice, _fields = _start_turn_relocation_choice_step(action, state, config)
        steps.append(start_choice)
        start_target = _start_turn_relocation_target_step(action)
        if start_target is not None:
            steps.append(start_target[0])
    steps += [
        {
            "kind": "origin",
            "value": action.origin,
            "prompt": ORIGIN_PROMPT,
            # What the counter reads once the origin is taken and the hand is lifted.
            "counter": counter,
        }
    ]
    steps += [
        {
            "kind": "edge",
            "value": value,
            "prompt": ROUTE_PROMPT,
            # Read by the page verbatim. No counting in JavaScript.
            "counter": edge_counters[index],
        }
        for index, value in enumerate(edge_values)
    ]
    if isinstance(action, SetupSowAction):
        return _address_steps(steps, player_id)
    if action.sow_route_omitted_location is not None:
        # Route first, duty later: Cloisters legality says the chosen duty must still have at least
        # one non-omitted placement, so the skipped wheel space has to be fixed before duty is asked.
        # Same wheel, third question. Distinct kind so this can be marked differently from origin
        # and duty without the page learning field names.
        steps.append(
            {
                "kind": "skip",
                "value": action.sow_route_omitted_location,
                "prompt": SKIP_PROMPT,
            }
        )
    steps.append({"kind": "duty", "value": action.selected_duty, "prompt": DUTY_PROMPT})
    steps.append(
        {"kind": "resolution", "value": action.resolution.value, "prompt": RESOLUTION_PROMPT}
    )
    steps += _presented_steps(
        action,
        state=state,
        config=config,
        offer_hire=offer_hire,
        hire_payment_buildings=hire_payment_buildings,
        offer_merchant_advance=offer_merchant_advance,
        include_preview_effects=include_preview_effects,
    )
    if isinstance(action, FullTurnAction) and offer_end_turn_relocation:
        end_choice, _fields = _end_turn_relocation_choice_step(action, state, config)
        steps.append(end_choice)
        end_target = _end_turn_relocation_target_step(action)
        if end_target is not None:
            steps.append(end_target[0])
    if preview_effects is None and include_preview_effects:
        preview_effects = _turn_action_preview_effects(action, state, config)
    if preview_effects is None:
        preview_effects = {}
    _attach_turn_action_preview_effects(steps, preview_effects)
    return _address_steps(steps, player_id)


def _unresolved_fields(
    members: list[Any],
    state: Any,
    config: Any,
    *,
    offer_hire: bool = False,
    hire_payment_buildings: tuple[str, ...] = (),
    offer_start_turn_relocation: bool = False,
    offer_end_turn_relocation: bool = False,
    offer_merchant_advance: bool = False,
    include_preview_effects: bool = True,
) -> list[str]:
    """Which fields the actions in one group still disagree about.

    `FullTurnAction` carries some forty optional fields and this page presents a handful of them,
    so answering everything asked can still leave several actions standing, alike in everything
    asked and different in something never asked. This names those differences rather than guessing
    between them: the list IS the backlog, worked out from the position in front of the player
    instead of from anyone's memory of what is unbuilt, and it shrinks as each field gets a way to
    be chosen.

    Presented fields are excluded because a step for them is part of the group key, so they cannot
    differ within a group. Excluded one group at a time, from the steps actually emitted, so a
    field goes unmentioned only where it was really asked.
    """
    covered = _covered_fields(
        members[0],
        state,
        config,
        offer_hire=offer_hire,
        hire_payment_buildings=hire_payment_buildings,
        offer_start_turn_relocation=offer_start_turn_relocation,
        offer_end_turn_relocation=offer_end_turn_relocation,
        offer_merchant_advance=offer_merchant_advance,
        include_preview_effects=include_preview_effects,
    )
    unresolved = [
        name
        for name in _residue_fields(members[0])
        if name not in covered and len({getattr(member, name) for member in members}) > 1
    ]
    # A decided field is ordinarily absent here because the page asked it earlier. If actions in the
    # same candidate still disagree in one, the earlier answers did not separate them and this
    # candidate is not genuinely settled.
    unresolved.extend(
        name
        for name in DECIDED_FIELDS
        if len({getattr(member, name) for member in members}) > 1
    )
    if "hire_payments" in unresolved:
        other_unresolved = [name for name in unresolved if name != "hire_payments"]
        if other_unresolved:
            hire_payments_is_independent = False
            seen_hire_payments_by_other_values: dict[tuple[Any, ...], Any] = {}
            missing = object()
            for member in members:
                key = tuple(getattr(member, name) for name in other_unresolved)
                hire_payments = getattr(member, "hire_payments")
                previous = seen_hire_payments_by_other_values.get(key, missing)
                if previous is not missing and previous != hire_payments:
                    hire_payments_is_independent = True
                    break
                seen_hire_payments_by_other_values[key] = hire_payments
            if not hire_payments_is_independent:
                unresolved = [name for name in unresolved if name != "hire_payments"]
    return unresolved


def turn_candidates(
    state: Any,
    config: Any,
    *,
    actions: tuple[Any, ...] | list[Any] | None = None,
    include_preview_effects: bool = True,
) -> list[dict]:
    """The moves on offer, grouped by the decisions the page can actually put to a player.

    One candidate per distinct answer to the currently askable questions, which is not one per legal
    action: several actions can share the same asked answers and differ only further down. Those
    arrive here as
    one candidate carrying the count and the disagreement, so the page can refuse it honestly
    instead of picking one of them on the player's behalf.

    The summary is player-facing. It is the same sentence the transcript writes for this action.

    Effect fields are included by default for the play page. Structural corpus callers can leave
    them out: they still get the same candidate grouping and step values, without replaying every
    complete turn merely to inspect those values.
    """
    grouped: dict[tuple[Any, ...], list[Any]] = {}
    player_id = _speaking_player_id(state)
    actions = list(legal_actions(state, config) if actions is None else actions)
    hire_contexts = _hire_contexts(actions, config)
    merchant_advance_contexts = {
        _resolution_context_key(action, config)
        for action in actions
        if isinstance(action, FullTurnAction)
        and action.merchant_advance_building_id is not None
    }
    offer_start_turn_relocation = any(
        isinstance(action, FullTurnAction) and _action_uses_start_turn_relocation(action)
        for action in actions
    )
    steps_by_action_id: dict[str, list[dict]] = {}
    offer_hire_by_action_id: dict[str, bool] = {}
    offer_merchant_advance_by_action_id: dict[str, bool] = {}
    preview_effects_by_action_id: dict[str, dict[str, Any]] = {}
    preview_effect_cache: dict[tuple[Any, ...], dict[str, Any]] = {}
    hire_payment_buildings_by_action_id: dict[str, tuple[str, ...]] = {}
    offer_end_turn_relocation_by_action_id: dict[str, bool] = {}
    pre_end_turn_key_by_action_id: dict[str, tuple[Any, ...]] = {}
    for action in actions:
        move_id = action_id(action)
        offered_hire = isinstance(action, FullTurnAction) and (
            _resolution_context_key(action, config) in hire_contexts
        )
        offer_hire_by_action_id[move_id] = offered_hire
        offer_merchant_advance_by_action_id[move_id] = isinstance(action, FullTurnAction) and (
            _resolution_context_key(action, config) in merchant_advance_contexts
        )
        preview_effects_by_action_id[move_id] = (
            _turn_action_preview_effects(action, state, config, cache=preview_effect_cache)
            if include_preview_effects and isinstance(action, FullTurnAction)
            else {}
        )
    hire_payment_buildings_by_action_id = _hire_payment_question_buildings_by_action_id(
        actions,
        player_id=player_id,
        state=state,
        config=config,
        offer_hire_by_action_id=offer_hire_by_action_id,
        offer_start_turn_relocation=offer_start_turn_relocation,
        offer_merchant_advance_by_action_id=offer_merchant_advance_by_action_id,
        include_preview_effects=include_preview_effects,
    )
    for action in actions:
        move_id = action_id(action)
        pre_end_turn_key_by_action_id[move_id] = _steps_key(
            decision_steps(
                action,
                player_id,
                state=state,
                config=config,
                offer_hire=offer_hire_by_action_id[move_id],
                hire_payment_buildings=hire_payment_buildings_by_action_id[move_id],
                offer_start_turn_relocation=offer_start_turn_relocation,
                offer_end_turn_relocation=False,
                offer_merchant_advance=offer_merchant_advance_by_action_id[move_id],
                preview_effects={},
                include_preview_effects=include_preview_effects,
            )
        )
    end_turn_contexts = {
        pre_end_turn_key_by_action_id[action_id(action)]
        for action in actions
        if isinstance(action, FullTurnAction) and _action_uses_end_turn_relocation(action)
    }
    for action in actions:
        move_id = action_id(action)
        offered_end_turn_relocation = isinstance(action, FullTurnAction) and (
            pre_end_turn_key_by_action_id[move_id] in end_turn_contexts
        )
        steps = decision_steps(
            action,
            player_id,
            state=state,
            config=config,
            offer_hire=offer_hire_by_action_id[move_id],
            hire_payment_buildings=hire_payment_buildings_by_action_id[move_id],
            offer_start_turn_relocation=offer_start_turn_relocation,
            offer_end_turn_relocation=offered_end_turn_relocation,
            offer_merchant_advance=offer_merchant_advance_by_action_id[move_id],
            preview_effects=preview_effects_by_action_id[move_id],
            include_preview_effects=include_preview_effects,
        )
        steps_by_action_id[move_id] = steps
        offer_end_turn_relocation_by_action_id[move_id] = offered_end_turn_relocation
        # THE KEY IS THE STEP VALUES AND STAYS THE STEP VALUES. A step carries words to read as
        # well as a value to match, and the words must not get in here: two spellings of one
        # question would then be two candidates, and a player would be shown the same choice twice
        # because the sentence above it differed.
        key = _steps_key(steps)
        grouped.setdefault(key, []).append(action)

    candidates = []
    for members in grouped.values():
        members = _dedupe_cloisters_route_spellings(members)
        move_id = action_id(members[0])
        unresolved = (
            _unresolved_fields(
                members,
                state,
                config,
            offer_hire=offer_hire_by_action_id[move_id],
            hire_payment_buildings=hire_payment_buildings_by_action_id[move_id],
            offer_start_turn_relocation=offer_start_turn_relocation,
                offer_end_turn_relocation=offer_end_turn_relocation_by_action_id[move_id],
                offer_merchant_advance=offer_merchant_advance_by_action_id[move_id],
                include_preview_effects=include_preview_effects,
            )
            if len(members) > 1
            else []
        )
        settled = not unresolved
        steps = [dict(step) for step in steps_by_action_id[move_id]]
        member_steps = [
            steps_by_action_id[action_id(member)]
            for member in members
        ]
        for index, step in enumerate(steps):
            for effect_field in _PREVIEW_EFFECT_FIELDS:
                values = [
                    member_steps[member_index][index].get(effect_field)
                    if index < len(member_steps[member_index])
                    else None
                    for member_index in range(len(member_steps))
                ]
                if not values or any(value != values[0] for value in values[1:]):
                    step.pop(effect_field, None)
        candidates.append(
            {
                "steps": steps,
                # The count before any route step is followed. The page reads this value directly
                # rather than deriving it from route length.
                "counter_start": _counter_start(members[0]),
                # Nothing to submit while the choice is incomplete, so there is no id to quote and
                # no summary to agree to. The page has to say so rather than send something.
                "action_id": move_id if settled else None,
                # Candidate summaries are shown BEFORE apply, when no event lines exist yet, so this
                # carries the full player sentence for what confirming would commit.
                "summary": (
                    action_summary_for_players(
                        members[0], config, actor=state.active_player, state=state
                    )
                    if settled
                    else None
                ),
                "unresolved": unresolved,
                "variants": len(members),
            }
        )
    return candidates


class PlayServer(ThreadingHTTPServer):
    """Holds the one loaded position every route answers from, and the log of how it got there."""

    daemon_threads = True

    def __init__(self, address: tuple[str, int], scenario_path: Path | None = None) -> None:
        super().__init__(address, PlayHandler)
        self._setup_door_enabled = scenario_path is None
        self._session_workspace = tempfile.TemporaryDirectory(prefix="play-server-session-")
        self._workspace_path = Path(self._session_workspace.name)
        self._latest_generated_scenario: dict[str, Any] | None = None
        self.session = SessionState(
            game_loaded=False,
            seat_roles=_default_seat_roles(4),
            setup_mode=SETUP_MODE_RANDOM,
            player_count=4,
            seed=None,
        )
        self.state: Any | None = None
        self.config: Any | None = None
        self.state_payload: dict[str, Any] = {}
        self.token = ""
        self.payload: dict[str, Any] = {}
        self.log_lines: list[str] = []
        self.log_blocks: list[dict[str, Any]] = []
        self._turn_start_state: Any | None = None
        self._turn_start_log_lines: list[str] = []
        self._turn_start_log_blocks: list[dict[str, Any]] = []
        # Threaded, so two submissions can arrive at once even from one browser. Reading the legal
        # set and replacing the state have to be one step, or the loser of the race applies a move
        # chosen against a board the winner has already moved.
        self._applying = threading.Lock()
        if scenario_path is not None:
            self._load_scenario_file(scenario_path)

    def _load_loaded_scenario(self, scenario: Any, *, intro_line: str | None = None) -> None:
        self.state = scenario.state
        self.config = scenario.config
        player_count = len(tuple(getattr(self.state, "players", ()) or ()))
        if player_count:
            self.session.player_count = player_count
            if (
                not self.session.seat_roles
                or len(self.session.seat_roles) != player_count
            ):
                self.session.seat_roles = _default_seat_roles(player_count)
        if intro_line:
            self.log_lines = [intro_line]
            self.log_blocks = [{"lines": [intro_line], "round_end": False}]
        else:
            self.log_lines = []
            self.log_blocks = []
        self.session.game_loaded = True
        self._refresh()
        self._capture_turn_start()

    def _load_scenario_file(self, scenario_path: Path, *, intro_line: str | None = None) -> None:
        self._load_loaded_scenario(load_scenario(str(scenario_path)), intro_line=intro_line)

    def _clear_game(self) -> None:
        self.state = None
        self.config = None
        self.state_payload = {}
        self.token = ""
        self.payload = {}
        self.log_lines = []
        self.log_blocks = []
        self._turn_start_state = None
        self._turn_start_log_lines = []
        self._turn_start_log_blocks = []
        self.session = SessionState(
            game_loaded=False,
            seat_roles=_default_seat_roles(4),
            setup_mode=SETUP_MODE_RANDOM,
            player_count=4,
            seed=None,
        )

    def _start_generated_game(
        self,
        *,
        player_count: int,
        seed: int,
        setup_mode: str,
        seat_roles: dict[str, str],
    ) -> None:
        if player_count not in SUPPORTED_PLAYER_COUNTS:
            raise ValueError(
                f"Unsupported player count {player_count}. Supported: {SUPPORTED_PLAYER_COUNTS}."
            )
        if setup_mode != SETUP_MODE_RANDOM:
            raise ValueError("Only Random setup is available in this build.")
        if any(role not in SEAT_ROLE_OPTIONS for role in seat_roles.values()):
            raise ValueError("Unknown seat role in request.")
        if any(role != ROLE_HUMAN for role in seat_roles.values()):
            raise ValueError("Bot seats are not available in this build.")

        generated = generate_setup_scenario(player_count=player_count, seed=seed)
        _rewrite_generated_paths_absolute(generated)
        scenario_path = self._workspace_path / "generated_scenario.json"
        scenario_path.write_text(json.dumps(generated, indent=2) + "\n", encoding="utf-8")
        self._latest_generated_scenario = json.loads(json.dumps(generated))
        self.session = SessionState(
            game_loaded=True,
            seat_roles=dict(seat_roles),
            setup_mode=setup_mode,
            player_count=player_count,
            seed=seed,
        )
        self._load_scenario_file(
            scenario_path,
            intro_line=f"New game - {player_count} players, seed {seed}.",
        )

    def _start_playtest_game(
        self,
        *,
        position_name: str,
        setup_mode: str,
        seat_roles: dict[str, str],
        playtest_positions: list[PlaytestPosition],
    ) -> None:
        if setup_mode != SETUP_MODE_RANDOM:
            raise ValueError("Only Random setup is available in this build.")
        position = _playtest_position_by_name(position_name, playtest_positions)
        if position is None:
            raise ValueError(
                f"Unknown test position {position_name!r}. Choose one listed on the setup page."
            )
        scenario = load_scenario(str(position.path))
        player_count = len(tuple(getattr(scenario.state, "players", ()) or ()))
        if player_count not in SUPPORTED_PLAYER_COUNTS:
            raise ValueError(
                f"Unsupported player count {player_count}. Supported: {SUPPORTED_PLAYER_COUNTS}."
            )
        chosen_roles = {
            SEATED_PLAYERS[index]: seat_roles.get(SEATED_PLAYERS[index], ROLE_HUMAN)
            for index in range(player_count)
        }
        if any(role not in SEAT_ROLE_OPTIONS for role in chosen_roles.values()):
            raise ValueError("Unknown seat role in request.")
        if any(role != ROLE_HUMAN for role in chosen_roles.values()):
            raise ValueError("Bot seats are not available in this build.")

        self._latest_generated_scenario = None
        self.session = SessionState(
            game_loaded=True,
            seat_roles=dict(chosen_roles),
            setup_mode=setup_mode,
            player_count=player_count,
            seed=position.seed,
        )
        self._load_loaded_scenario(
            scenario,
            intro_line=f"Loaded test position - {position.label}.",
        )

    def has_game(self) -> bool:
        return self.session.game_loaded and self.state is not None and self.config is not None

    def _capture_turn_start(self) -> None:
        self._turn_start_state = self.state
        self._turn_start_log_lines = list(self.log_lines)
        self._turn_start_log_blocks = [
            dict(block, lines=list(block["lines"])) for block in self.log_blocks
        ]

    def _refresh(self) -> None:
        """Re-read everything the page is drawn from, after the position has changed."""
        if not self.has_game():
            self.state_payload = {}
            self.token = ""
            self.payload = {}
            return
        self.state_payload = view_payload(self.state, self.config)
        self.token = state_token(self.state_payload)
        self.payload = dict(
            self.state_payload,
            state_token=self.token,
            turn_candidates=turn_candidates(self.state, self.config),
            turn_steps=turn_steps_payload(self.state, self.config),
            log=list(self.log_lines),
            log_blocks=[dict(block, lines=list(block["lines"])) for block in self.log_blocks],
        )

    def apply(self, submitted_id: str, submitted_token: str) -> None:
        """Apply one action, named by id and vouched for by the token it was read from.

        The token is checked first and refused rather than worked around. A submission quoting a
        stale list was decided against a board that has since moved, and re-deriving what its author
        "must have meant" would be this process inventing a move on their behalf.

        The action is then LOOKED UP in the current legal set, never rebuilt from what was sent.
        Reconstructing one from client fields would make the client the author of moves, and the
        first illegal one would arrive as a crash somewhere far from here instead of a refusal.
        """
        with self._applying:
            self._apply_locked(submitted_id, submitted_token)

    def _apply_locked(self, submitted_id: str, submitted_token: str) -> None:
        if not self.has_game():
            raise UnknownAction("no game is loaded; start a game first")
        if submitted_token != self.token:
            raise StaleStateToken(
                f"state token {submitted_token!r} is not the current {self.token!r}; "
                "the position moved after that list was read"
            )
        chosen = next(
            (
                action
                for action in legal_actions(self.state, self.config)
                if action_id(action) == submitted_id
            ),
            None,
        )
        if chosen is None:
            raise UnknownAction(f"no legal action with id {submitted_id!r} in this position")

        actor = self.state.active_player
        # Applied-log lead line sits directly above event lines that already name steps and costs,
        # so it stays short and only says which duty action was chosen.
        summary_line = action_choice_summary_for_players(chosen, self.config, actor=actor)
        result = apply_action(self.state, chosen, self.config)
        self.state = result.state
        has_taxation_event = any(event.event_type is EventType.TAXATION for event in result.events)
        # None means the event is not for players' transcript.
        event_lines = [
            line
            for line in (
                format_event_for_players(event, self.config)
                for event in result.events
                if not (
                    has_taxation_event and event.event_type is EventType.RESOURCE_DELTA
                )
            )
            if line is not None
        ]
        player_lines = [summary_line] + [
            line for line in event_lines if line.strip() and line != summary_line
        ]
        if player_lines:
            round_end = any(
                event.event_type in {EventType.ROUND_END, EventType.ROUND_ADVANCE}
                for event in result.events
            )
            self.log_lines.extend(player_lines)
            self.log_blocks.append({"lines": player_lines, "round_end": round_end})
        self._refresh()
        self._capture_turn_start()

    def apply_turn_step(self, submitted_id: str, submitted_token: str) -> None:
        """Apply one currently legal committed conversion, named by its stable step id."""
        with self._applying:
            if not self.has_game():
                raise UnknownTurnStep("no game is loaded; start a game first")
            if submitted_token != self.token:
                raise StaleStateToken(
                    f"state token {submitted_token!r} is not the current {self.token!r}; "
                    "the position moved after that list was read"
                )
            chosen = next(
                (
                    step
                    for step in turn_steps(self.state, self.config)
                    if _turn_step_id(step) == submitted_id
                ),
                None,
            )
            if chosen is None:
                raise UnknownTurnStep(
                    f"no legal turn step with id {submitted_id!r} in this position"
                )
            self.state = apply_engine_turn_step(self.state, self.config, chosen)
            self._refresh()

    def reset_turn(self, submitted_token: str) -> None:
        """Restore the immutable snapshot captured at the beginning of the active turn."""
        with self._applying:
            if not self.has_game():
                raise UnknownAction("no game is loaded; start a game first")
            if submitted_token != self.token:
                raise StaleStateToken(
                    f"state token {submitted_token!r} is not the current {self.token!r}; "
                    "the position moved after that list was read"
                )
            if self._turn_start_state is None:
                raise UnknownAction("no turn-start snapshot is available")
            self.state = self._turn_start_state
            self.log_lines = list(self._turn_start_log_lines)
            self.log_blocks = [
                dict(block, lines=list(block["lines"]))
                for block in self._turn_start_log_blocks
            ]
            self._refresh()

    def server_bind(self) -> None:
        """Bind without asking the network what this machine is called.

        `HTTPServer.server_bind` resolves the bound host to a fully qualified name, and on a
        machine whose resolver will not answer for 127.0.0.1 that reverse lookup sits there until
        it times out -- thirty-five seconds here, before the first request is even possible. The
        name is only ever used to fill in a default Host header, so the literal we were given is
        both faster and more accurate than whatever the resolver would eventually have said.
        """
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]

    def server_close(self) -> None:
        try:
            super().server_close()
        finally:
            self._session_workspace.cleanup()


class PlayHandler(BaseHTTPRequestHandler):
    server: PlayServer

    def _no_game_document(self, *, route: str) -> dict[str, Any]:
        return {
            "status": "no_game_loaded",
            "route": route,
            "message": "No game is loaded. Start one from the setup page.",
        }

    def do_GET(self) -> None:  # noqa: N802 -- BaseHTTPRequestHandler's own spelling
        route = self.path.split("?", 1)[0]
        if route == "/":
            if self.server.has_game():
                page = _render_board_page(
                    self.server.payload,
                    allow_reset_to_setup=self.server._setup_door_enabled,
                )
            elif self.server._setup_door_enabled:
                page = _render_setup_page(
                    suggested_seed=_prefill_seed(),
                    playtest_positions=_available_playtest_positions(),
                )
            else:
                # Scenario mode is expected to open straight to a board.
                self._send(
                    409,
                    "application/json",
                    json.dumps(
                        self._no_game_document(route=route)
                        | {"message": "No game is loaded in scenario mode."}
                    ),
                )
                return
            self._send(200, "text/html; charset=utf-8", page)
        elif route == "/state.json":
            if not self.server.has_game():
                self._send(
                    409,
                    "application/json",
                    json.dumps(self._no_game_document(route=route), indent=1),
                )
                return
            # The state as the engine describes it, without the token, the candidates or the log:
            # those are this process's bookkeeping, and a test comparing two positions should not
            # have to look past them to see whether anything moved.
            self._send(200, "application/json", json.dumps(self.server.state_payload, indent=1))
        elif route == "/actions.json":
            if not self.server.has_game():
                self._send(
                    409,
                    "application/json",
                    json.dumps(
                        self._no_game_document(route=route) | {"count": 0, "actions": []},
                        indent=1,
                    ),
                )
                return
            document = actions_document(
                self.server.state, self.server.config, self.server.state_payload
            )
            self._send(200, "application/json", json.dumps(document, indent=1))
        else:
            self._send(404, "text/plain; charset=utf-8", f"no route {route}\n")

    def do_POST(self) -> None:  # noqa: N802 -- BaseHTTPRequestHandler's own spelling
        route = self.path.split("?", 1)[0]
        if route not in {"/action", "/turn-step", "/reset-turn", "/start", "/new-game"}:
            self._send(404, "text/plain; charset=utf-8", f"no route {route}\n")
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length > 0 else b""

        if route == "/new-game":
            if not self.server._setup_door_enabled:
                self._send(404, "text/plain; charset=utf-8", f"no route {route}\n")
                return
            self.server._clear_game()
            self._send(
                200,
                "text/html; charset=utf-8",
                _render_setup_page(
                    suggested_seed=_prefill_seed(),
                    playtest_positions=_available_playtest_positions(),
                ),
            )
            return

        if route == "/start":
            if not self.server._setup_door_enabled:
                self._send(404, "text/plain; charset=utf-8", f"no route {route}\n")
                return
            try:
                content_type = str(self.headers.get("Content-Type", ""))
                if "application/json" in content_type:
                    body = json.loads(raw or b"{}")
                    if not isinstance(body, dict):
                        raise ValueError("body must be a JSON object")
                    source = {str(k): str(v) for k, v in body.items()}
                else:
                    source = {
                        key: values[-1]
                        for key, values in parse_qs(raw.decode("utf-8"), keep_blank_values=True).items()
                    }
                test_position = source.get("test_position", "").strip()
                setup_mode = source.get("setup_mode", SETUP_MODE_RANDOM)
                seat_roles = {
                    SEATED_PLAYERS[index]: source.get(f"seat_{index + 1}_role", ROLE_HUMAN)
                    for index in range(len(SEATED_PLAYERS))
                }
                playtest_positions = _available_playtest_positions()
                if test_position:
                    self.server._start_playtest_game(
                        position_name=test_position,
                        setup_mode=setup_mode,
                        seat_roles=seat_roles,
                        playtest_positions=playtest_positions,
                    )
                else:
                    player_count = int(source.get("player_count", "4"))
                    seed = int(source.get("seed", "0"))
                    self.server._start_generated_game(
                        player_count=player_count,
                        seed=seed,
                        setup_mode=setup_mode,
                        seat_roles={
                            SEATED_PLAYERS[index]: seat_roles[SEATED_PLAYERS[index]]
                            for index in range(player_count)
                        },
                    )
            except Exception as exc:
                self._reject(422, str(exc))
                return
            self._send(
                200,
                "text/html; charset=utf-8",
                _render_board_page(self.server.payload, allow_reset_to_setup=True),
            )
            return

        if not self.server.has_game():
            self._reject(409, "no game is loaded; start a game first")
            return
        try:
            body = json.loads(raw or b"{}")
        except (ValueError, TypeError):
            self._reject(400, "body must be JSON")
            return
        if not isinstance(body, dict):
            self._reject(400, "body must be a JSON object")
            return

        try:
            submitted_token = str(body.get("state_token", ""))
            if route == "/action":
                self.server.apply(str(body.get("action_id", "")), submitted_token)
            elif route == "/turn-step":
                self.server.apply_turn_step(str(body.get("step_id", "")), submitted_token)
            else:
                self.server.reset_turn(submitted_token)
        except StaleStateToken as stale:
            # 409, not 400: the request was well formed and would have been fine a moment ago.
            self._reject(409, str(stale))
            return
        except (UnknownAction, UnknownTurnStep) as unknown:
            self._reject(422, str(unknown))
            return

        # The whole page, redrawn from the new state. The client swaps it in rather than patching
        # the board, so nothing it does can put a piece somewhere the engine did not.
        self._send(
            200,
            "text/html; charset=utf-8",
            _render_board_page(
                self.server.payload,
                allow_reset_to_setup=self.server._setup_door_enabled,
            ),
        )

    def _reject(self, status: int, reason: str) -> None:
        """Say what was wrong. A refusal that changed nothing should read like one."""
        self._send(status, "application/json", json.dumps({"error": reason, "applied": False}))

    def _send(self, status: int, content_type: str, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 -- the base class's name
        sys.stderr.write(f"{self.address_string()} {format % args}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "scenario",
        type=Path,
        nargs="?",
        help="Scenario JSON, from `pilgrim.cli generate-setup`.",
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args(argv)

    server = PlayServer((args.host, args.port), args.scenario)
    if args.scenario is None:
        print(f"serving setup page on http://{args.host}:{args.port}/")
    else:
        document = actions_document(server.state, server.config, server.state_payload)
        print(f"serving {args.scenario} on http://{args.host}:{args.port}/")
        print(f"state token {document['state_token']}; {document['count']} legal actions")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
