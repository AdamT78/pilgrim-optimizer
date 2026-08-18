"""A thin local process serving setup + live play views from one in-memory session.

Standard library only. The repo declares no dependencies at all -- `pyproject.toml` has
`dependencies = []` -- so bringing in a framework to serve four routes would be the first one, and
`http.server` is enough for one local page playing one game.

    GET  /              setup page (when no game loaded) or play view (when one is loaded)
    GET  /state.json    the payload the adapter was handed, verbatim
    GET  /actions.json  the legal actions, structured, with an id each and a token for the state
    POST /start         generate a scenario from setup choices and load it into this session
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
import dataclasses
import enum
import hashlib
import json
import random
import socketserver
import sys
import tempfile
import threading
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
from pilgrim.model.actions import (  # noqa: E402
    SetupSowAction,
    StartPlayerConfessionBoxAction,
    StartPlayerSelectionAction,
    action_id,
    action_choice_summary_for_players,
    action_summary_for_players,
)
from pilgrim.rules.transition import apply_action, legal_actions  # noqa: E402
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


class StaleStateToken(Exception):
    """The submission quoted a list that is no longer the one on offer."""


class UnknownAction(Exception):
    """The submission named an action that is not legal in the position now held."""


def _default_seat_roles(player_count: int) -> dict[str, str]:
    return {SEATED_PLAYERS[index]: ROLE_HUMAN for index in range(player_count)}


def _prefill_seed() -> int:
    """Server-side seed suggestion for the setup form."""
    return random.SystemRandom().randint(1000, 9999)


def _rewrite_generated_paths_absolute(generated: dict[str, Any]) -> None:
    """Make generated config file paths loadable from any temporary scenario location."""
    repo_root = Path(__file__).resolve().parents[1]
    for field_name in SCENARIO_PATH_FIELDS:
        raw = generated.get(field_name)
        if not isinstance(raw, str):
            raise ValueError(f"Generated scenario field '{field_name}' must be a string path.")
        path = Path(raw)
        generated[field_name] = str((path if path.is_absolute() else (repo_root / path)).resolve())


def _render_setup_page(*, suggested_seed: int) -> str:
    """The pre-game setup form served when no game is loaded in this session."""
    count_options = "".join(
        f'<option value="{count}"{" selected" if count == 4 else ""}>{count}</option>'
        for count in SUPPORTED_PLAYER_COUNTS
    )
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
    <p>Choose seats and a seed, then deal a fresh setup.</p>
    <form method="post" action="/start">
      <div class="field">
        <label for="player_count">Player count</label>
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
        <label for="seed">Seed</label>
        <input id="seed" name="seed" type="number" required value="{suggested_seed}">
      </div>
      <div class="actions">
        <button type="submit">Start game</button>
      </div>
    </form>
  </main>
<script>
  (function () {{
    var count = document.getElementById('player_count');
    var rows = document.querySelectorAll('[data-seat-row]');
    function refreshRows() {{
      var selected = Number(count.value || 4);
      Array.prototype.forEach.call(rows, function (row) {{
        row.hidden = Number(row.getAttribute('data-seat-row')) > selected;
      }});
    }}
    count.addEventListener('change', refreshRows);
    refreshRows();
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
RESOLUTION_PROMPT = "Action or Tithe."
RESOURCE_PROMPT = "choose a resource."
BUILDING_PROMPT = "choose a building."
COMBINATION_PROMPT = "choose one."
SEAT_PROMPT = "choose first player for this round."
ARRANGEMENT_PROMPT = (
    "move acolytes from the Abbey to Special Activity and/or between Special Activities."
)
ORDINATION_PROMPT = "ordain from Village and send from Abbey; City updates as a preview."

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


def _combination_step(verb: str, amounts: list[tuple[str, int]]) -> dict:
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
        # thing the labels are describing, kept in step by hand.
        "prompt": COMBINATION_PROMPT,
    }


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


def _presented(action: Any) -> list[tuple[dict, tuple[str, ...]]]:
    """Each further question this page can put about one action, with the fields it answers.

    Emitted after the resolution because they are answers to it: which stock a tithe takes is only
    a question once tithe is what is happening. Whether a step appears at all is therefore settled
    by the resolution, which is an earlier step, so every action in a group carries the same ones.

    The fields are kept BESIDE the step rather than inside it. They are this side's business -- how
    the refusal knows what has been asked -- and a page holding the name of a field would be a page
    that could come to depend on it, which is how the next one ends up being a special case.
    """
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
    for name in RESOURCE_CHOICE_FIELDS:
        value = getattr(action, name, None)
        if value is not None:
            presented.append(
                ({"kind": "resource", "value": value, "prompt": RESOURCE_PROMPT}, (name,))
            )
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
        presented.append((_combination_step(verb, amounts), tuple(name for name, _noun in fields)))
    for resolution, verb, name in COUNTED_COMBINATION_STEPS:
        if action.resolution.value != resolution:
            continue
        taken = tuple(getattr(action, name, ()) or ())
        amounts = [(noun, taken.count(noun)) for noun in COMBINATION_STOCKS]
        presented.append((_combination_step(verb, amounts), (name,)))
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


def _presented_steps(action: Any) -> list[dict]:
    return [step for step, _fields in _presented(action)]


def _position_name(position: int) -> str:
    """Engine position name for one index, in the canonical order view payloads carry."""
    return CANONICAL_POSITION_NAMES[position]


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


def _covered_fields(action: Any) -> set[str]:
    """Which residue fields this action's steps actually answer.

    Read off the steps that were really emitted, so a field the page can ask about in principle but
    did not ask about here still belongs in the refusal.
    """
    return {name for _step, fields in _presented(action) for name in fields}


def _residue_fields(action: Any) -> tuple[str, ...]:
    """Everything an action carries that the page does not ask about by name.

    Read off the action in hand rather than off one type, because there is more than one kind of
    action now: a start-player selection carries one field and a full turn some forty, and the page
    presents a handful of the second and none of the first.
    """
    return tuple(
        field.name
        for field in dataclasses.fields(action)
        if field.name not in DECIDED_FIELDS and field.name != "action_type"
    )


def decision_steps(action: Any, player_id: str) -> list[dict]:
    """The questions this action is an answer to, in the order the page asks them.

    Origin, then the route one space at a time, then which duty was selected, then what to do with
    it, then whatever that resolution goes on to ask. A setup sow stops after the route because
    that is all it has.

    Each step says what KIND of thing it is, because they are not answered in the same place -- and
    one pair now share a place and still have to be told apart on it. `origin` and `duty` are both
    answered by pointing at a wheel space, and are distinct kinds so the page can mark "where to
    lift from" differently from "which duty to take" without consulting field names or writing a
    second copy of what either one means. The others are still separated by where they are answered:
    a resolution is beside the board, a stock is on the asking seat's own board, a seat is a whole
    board, a building is a hex on the round track, and a combination is a set of amounts that only
    go together one way.

    Route length is not fixed. It is however many acolytes were lifted, so it varies by origin and
    by turn, and nothing here or on the page may assume a number.
    """
    # A start-player selection is one question and nothing before it. There is no origin to lift
    # from and no duty to resolve: whoever holds the marker names a player, and that is the whole
    # of the action.
    if isinstance(action, (StartPlayerConfessionBoxAction, StartPlayerSelectionAction)):
        return _address_steps(_presented_steps(action), player_id)
    # The route still walks spaces by index. What changed is the kind names for the two space
    # questions around it: where to lift from (`origin`) and which duty to take (`duty`).
    route = tuple(action.route)
    counter = _counter_start(action)
    steps = [
        {
            "kind": "origin",
            "value": action.origin,
            "prompt": ORIGIN_PROMPT,
            # What the counter reads once the origin is taken and the hand is lifted.
            "counter": counter,
        }
    ]
    path = (action.origin, *route)
    steps += [
        {
            "kind": "edge",
            "value": f"{_position_name(path[index])}->{_position_name(path[index + 1])}",
            "prompt": ROUTE_PROMPT,
            # Read by the page verbatim. No counting in JavaScript.
            "counter": counter - (index + 1),
        }
        for index in range(len(route))
    ]
    if isinstance(action, SetupSowAction):
        return _address_steps(steps, player_id)
    steps.append({"kind": "duty", "value": action.selected_duty, "prompt": DUTY_PROMPT})
    steps.append(
        {"kind": "resolution", "value": action.resolution.value, "prompt": RESOLUTION_PROMPT}
    )
    steps += _presented_steps(action)
    return _address_steps(steps, player_id)


def _unresolved_fields(members: list[Any]) -> list[str]:
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
    covered = _covered_fields(members[0])
    return [
        name
        for name in _residue_fields(members[0])
        if name not in covered and len({getattr(member, name) for member in members}) > 1
    ]


def turn_candidates(state: Any, config: Any) -> list[dict]:
    """The moves on offer, grouped by the decisions the page can actually put to a player.

    One candidate per distinct answer to the four questions above, which is not one per legal
    action: several actions can share all four and differ only further down. Those arrive here as
    one candidate carrying the count and the disagreement, so the page can refuse it honestly
    instead of picking one of them on the player's behalf.

    The summary is player-facing. It is the same sentence the transcript writes for this action.
    """
    grouped: dict[tuple, list[Any]] = {}
    player_id = _speaking_player_id(state)
    for action in legal_actions(state, config):
        # THE KEY IS THE STEP VALUES AND STAYS THE STEP VALUES. A step carries words to read as
        # well as a value to match, and the words must not get in here: two spellings of one
        # question would then be two candidates, and a player would be shown the same choice twice
        # because the sentence above it differed.
        key = tuple(
            tuple(step["value"]) if isinstance(step["value"], tuple) else step["value"]
            for step in decision_steps(action, player_id)
        )
        grouped.setdefault(key, []).append(action)

    candidates = []
    for members in grouped.values():
        unresolved = _unresolved_fields(members) if len(members) > 1 else []
        settled = not unresolved
        candidates.append(
            {
                "steps": decision_steps(members[0], player_id),
                # The count before any route step is followed. The page reads this value directly
                # rather than deriving it from route length.
                "counter_start": _counter_start(members[0]),
                # Nothing to submit while the choice is incomplete, so there is no id to quote and
                # no summary to agree to. The page has to say so rather than send something.
                "action_id": action_id(members[0]) if settled else None,
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
        # Threaded, so two submissions can arrive at once even from one browser. Reading the legal
        # set and replacing the state have to be one step, or the loser of the race applies a move
        # chosen against a board the winner has already moved.
        self._applying = threading.Lock()
        if scenario_path is not None:
            self._load_scenario_file(scenario_path)

    def _load_scenario_file(self, scenario_path: Path, *, intro_line: str | None = None) -> None:
        scenario = load_scenario(str(scenario_path))
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

    def _clear_game(self) -> None:
        self.state = None
        self.config = None
        self.state_payload = {}
        self.token = ""
        self.payload = {}
        self.log_lines = []
        self.log_blocks = []
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

    def has_game(self) -> bool:
        return self.session.game_loaded and self.state is not None and self.config is not None

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
                page = _render_setup_page(suggested_seed=_prefill_seed())
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
        if route not in {"/action", "/start", "/new-game"}:
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
                _render_setup_page(suggested_seed=_prefill_seed()),
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
                player_count = int(source.get("player_count", "4"))
                seed = int(source.get("seed", "0"))
                setup_mode = source.get("setup_mode", SETUP_MODE_RANDOM)
                seat_roles = {
                    SEATED_PLAYERS[index]: source.get(f"seat_{index + 1}_role", ROLE_HUMAN)
                    for index in range(player_count)
                }
                self.server._start_generated_game(
                    player_count=player_count,
                    seed=seed,
                    setup_mode=setup_mode,
                    seat_roles=seat_roles,
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
            self.server.apply(str(body.get("action_id", "")), str(body.get("state_token", "")))
        except StaleStateToken as stale:
            # 409, not 400: the request was well formed and would have been fine a moment ago.
            self._reject(409, str(stale))
            return
        except UnknownAction as unknown:
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
