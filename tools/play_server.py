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
from pilgrim.model.enums import CANONICAL_POSITION_NAMES, EventType, TurnPhase  # noqa: E402
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
    BuildingActivationStep,
    BuildingConversionStep,
    BuildingRelocationStep,
    EndTurnAction,
    FullTurnAction,
    SetupSowAction,
    StartPlayerConfessionBoxAction,
    StartPlayerSelectionAction,
    action_id,
    action_choice_summary_for_players,
    action_summary_for_players,
)
from pilgrim.rules.buildings import (  # noqa: E402
    BUILDING_ABILITY_REASONS,
    BuildingAbilityReason,
    building_ability_source,
    building_by_id,
    is_building_live,
)
from pilgrim.rules.merchant import CORNUCOPIA_COUNTER  # noqa: E402
from pilgrim.rules.transition import (  # noqa: E402
    _HIRED_MODIFIER_BUILDING_IDS,
    _ROUTE_BUILDING_IDS as _ENGINE_ROUTE_BUILDING_IDS,
    turn_step_id,
    apply_action,
    apply_turn_step as apply_engine_turn_step,
    legal_actions,
    taxation_majority_unlocks_for_action,
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
_WAGON_YARD_ONE_SHOT_FREE_HIRE_BUILDING_ID = "wagon_yard"


@dataclasses.dataclass(frozen=True, slots=True)
class _RouteFamilyDeclaration:
    """The complete server-owned identity and presentation of one route family."""

    building_id: str
    i: int
    paint: str
    priority: int
    # State-only wording: the description states the effect and the ability line says whether it
    # is live. Owning the building makes it free by the rules, so the page does not restate what
    # the board already enforces.
    owned_status_text: str

    @property
    def mask(self) -> int:
        """Return this family's bit in the compact, server-written selection masks."""
        return 1 << self.i


# Add a route family here, then re-read its permitter wording below.  The payload palette, compact
# candidate indexes, offered-building lookup, and automatic-mask bits all derive from this list.
_ROUTE_FAMILIES = (
    _RouteFamilyDeclaration(
        "kogge",
        i=0,
        paint="route-opening",
        priority=1,
        owned_status_text="Yours: in effect every turn.",
    ),
    _RouteFamilyDeclaration(
        "cloisters",
        i=1,
        paint="route-extra-step",
        priority=2,
        owned_status_text="Yours: in effect every turn.",
    ),
)
_ROUTE_FAMILY_BY_BUILDING_ID = {family.building_id: family for family in _ROUTE_FAMILIES}
_ROUTE_FAMILY_BY_INDEX = {family.i: family for family in _ROUTE_FAMILIES}
_ROUTE_BUILDING_IDS = tuple(family.building_id for family in _ROUTE_FAMILIES)
_ROUTE_BUILDING_PRESENTATION = tuple(
    {
        "i": family.i,
        "building_id": family.building_id,
        "paint": family.paint,
        "priority": family.priority,
    }
    for family in _ROUTE_FAMILIES
)
_REVIEWED_HIRED_MODIFIER_BUILDING_IDS = ("scriptorium", "customs_house", "bank", "wagon_yard")

if _ENGINE_ROUTE_BUILDING_IDS != _ROUTE_BUILDING_IDS:
    raise RuntimeError("Review permitter tile wording after changing the route-building tuple.")
if _HIRED_MODIFIER_BUILDING_IDS != _REVIEWED_HIRED_MODIFIER_BUILDING_IDS:
    raise RuntimeError("Review permitter tile wording after changing the modifier-building tuple.")

_PERMITTER_BUILDING_IDS = frozenset(
    (*_ROUTE_BUILDING_IDS, *_HIRED_MODIFIER_BUILDING_IDS)
) - {_WAGON_YARD_ONE_SHOT_FREE_HIRE_BUILDING_ID}
_REVIEWED_PERMITTER_BUILDING_IDS = frozenset(
    {"kogge", "cloisters", "scriptorium", "customs_house", "bank"}
)
_PERMITTER_STATUS_TEXT = "In effect for the rest of this turn."

if _PERMITTER_BUILDING_IDS != _REVIEWED_PERMITTER_BUILDING_IDS:
    raise RuntimeError("Review permitter tile wording after changing the permitter-building set.")


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
    """The committed building steps currently legal, each with the id the client may quote back."""
    payload = []
    player = state.active_player
    before = state.player_state(player)
    for step in turn_steps(state, config):
        result = apply_engine_turn_step(state, config, step)
        after_step = result.player_state(player)
        source = building_ability_source(
            state,
            config,
            acting_player=state.active_player,
            building_key=step.building_id,
        )
        building_name = building_by_id(config.buildings, step.building_id).name
        total_silver_delta = after_step.resources.silver - before.resources.silver
        hire_silver_delta = sum(
            -int(dict(event.details).get("amount", 0))
            for event in result.events
            if event.event_type is EventType.BUILDING_HIRED
            and event.action_id == turn_step_id(step)
            and dict(event.details).get("resource") == "silver"
        )
        entry = {
            "step_id": turn_step_id(step),
            "building_id": step.building_id,
            "source": step.source,
            "hire_payment": step.hire_payment,
            # This is the complete sequence the page may ask about this committed step. It is
            # deliberately ordered here so the browser narrows engine variants without deciding
            # whether a hire, direction, or amount comes first.
            "answers": _turn_step_answers(step, building_name, after_step),
            # A hire is described before any of its answer controls are drawn. In particular, a
            # Merchant-named payment is stated rather than turned into a one-option question.
            "hire_text": _building_hire_sentence(building_name, source),
            # Applying the exact enumerated step is what carries a Cornucopia payer's concrete
            # stock choice. Looking the source up again would find the Merchant's wildcard, so
            # hand the page this applied source rather than asking it to reconstruct a payment.
            "ability": _turn_step_ability_payload(state, config, step, result),
        }
        if isinstance(step, BuildingActivationStep):
            prompt = (
                "Activate Guild: move the Merchant clockwise +1 Duty tile."
                if step.building_id == "guild"
                else "Activate Pulpit."
                if step.building_id == "pulpit"
                else f"Hire {building_name}: pay to use its ability this turn."
            )
            entry.update(
                kind="activation",
                prompt=prompt,
            )
        elif isinstance(step, BuildingRelocationStep):
            if step.building_id == "dormitory":
                prompt = (
                    f"{building_name}: return an acolyte to City from the selected Duty space."
                )
            elif step.building_id == "library":
                prompt = (
                    f"{building_name}: move an acolyte from City to the selected Duty space or "
                    "Abbey."
                )
            else:
                prompt = f"{building_name}: move an acolyte from City to the selected Duty space."
            entry.update(
                kind="relocation",
                selected_position=step.selected_position,
                prompt=prompt,
            )
        else:
            entry.update(
                kind="conversion",
                direction=step.direction,
                amount=step.amount,
                piety_destination=after_step.piety,
                # Describe the conversion separately from the optional building hire fee. Both
                # values come from the engine: the total state delta and the hire event details.
                silver_delta=total_silver_delta - hire_silver_delta,
            )
        payload.append(entry)
    return payload


def _building_ability_party_name(party: str | None) -> str | None:
    """Name an ability's owner or payee exactly as the player-facing log does."""
    if party is None or party == "bank":
        return party
    return SEAT_COLOURS.get(party, party)


def _building_hire_cost_phrase(source: Any) -> str | None:
    """Render the price an engine-resolved building source asks the player to pay."""
    if source.hire_cost <= 0 or source.hire_resource is None:
        return None
    if source.hire_resource == CORNUCOPIA_COUNTER and not source.hire_resource_chosen:
        return f"{source.hire_cost} resource of your choice"
    return f"{source.hire_cost} {source.hire_resource}"


def _building_ability_status_text(source: Any) -> str:
    """One player-facing status sentence from an engine-resolved ability source.

    The browser receives this finished sentence with the source fields. It may place the sentence
    beside a building, but it must never turn a rule code into player language itself.
    """
    if source.usable:
        payee = _building_ability_party_name(source.payable_to)
        cost_phrase = _building_hire_cost_phrase(source)
        if cost_phrase is not None and payee:
            return f"Usable: pay {cost_phrase} to {payee}."
        return "Usable: no payment."

    reason = source.reason or None
    if reason is None:
        return ""
    if reason not in BUILDING_ABILITY_REASONS:
        raise ValueError(f"Unknown building ability reason: {reason!r}")
    if reason == BuildingAbilityReason.NOT_LIVE:
        return "Cannot be hired: this building is not live yet."
    if reason == BuildingAbilityReason.NOT_SELECTED:
        return "Cannot be hired: this building was not selected for this game."
    if reason == BuildingAbilityReason.DONATED:
        owner_name = _building_ability_party_name(source.owner)
        owner = f" by {owner_name}" if owner_name else ""
        return f"Cannot be hired: this building was donated{owner}."
    if reason == BuildingAbilityReason.INSUFFICIENT_RESOURCE:
        payee = _building_ability_party_name(source.payable_to)
        if source.hire_cost > 0 and source.hire_resource is not None and payee:
            return (
                f"Cannot be hired: insufficient {source.hire_resource} to pay {source.hire_cost} "
                f"{source.hire_resource} to {payee}."
            )
        return "Cannot be hired: the hire payment cannot be afforded."
    if reason == BuildingAbilityReason.MERCHANT_RESOURCE_NONE:
        return "Cannot be hired: the Merchant names no hire resource."
    if reason == BuildingAbilityReason.END_OF_TURN_NOT_REACHED:
        return "Cannot be used: End of Turn has not begun."
    if reason == BuildingAbilityReason.BEGINNING_OF_TURN_PASSED:
        return "Cannot be used: Beginning of Turn has passed."
    if reason == BuildingAbilityReason.MID_SOW:
        return "Cannot be used: sowing is in progress."
    if reason == BuildingAbilityReason.ALREADY_USED:
        return "Cannot be used: already used this turn."
    if reason == BuildingAbilityReason.EFFECT_APPLIES_FOR_REST_OF_TURN:
        if source.building_key not in _PERMITTER_BUILDING_IDS:
            raise AssertionError(f"Permitter has no player-facing status: {source.building_key!r}")
        return _PERMITTER_STATUS_TEXT
    raise AssertionError(f"Known building ability reason has no player-facing status: {reason!r}")


def _building_hire_sentence(building_name: str, source: Any) -> str:
    """State an offered building hire without asking the page to write the price.

    A Cornucopia still names its price here, but not a false resource: its later answer is the
    payer's choice. The concrete turn steps each carry are not allowed to leak that future choice
    into the sentence shown when the building is first selected.
    """
    if source.source_type == "own_active":
        return ""
    if source.source_type == "live_market_hire":
        hire_source = "market"
    elif source.source_type == "opponent_active_hire":
        hire_source = _building_ability_party_name(source.owner)
    else:
        return ""
    cost_phrase = _building_hire_cost_phrase(source)
    if cost_phrase is None or not hire_source:
        return ""
    return f"Hire {building_name} from {hire_source} for {cost_phrase}."


def _route_hire_sentence(action: FullTurnAction, state: Any, config: Any) -> str:
    """State the hires an already-chosen route carries; the page only reads this engine fact."""
    sentences: list[str] = []
    for building_id, source_label in (
        (action.sow_route_building_id, action.sow_route_building_source),
        (action.sow_route_secondary_building_id, action.sow_route_secondary_building_source),
    ):
        if building_id is None or source_label in (None, "own_active"):
            continue
        source = building_ability_source(
            state,
            config,
            acting_player=state.active_player,
            building_key=building_id,
        )
        cost_phrase = _building_hire_cost_phrase(source)
        payee = _building_ability_party_name(source.payable_to)
        if cost_phrase is None or not payee:
            continue
        building_name = building_by_id(config.buildings, building_id).name
        if not sentences:
            sentences.append(f"This route uses {building_name} — {cost_phrase} to {payee}.")
        else:
            sentences.append(f"and the {building_name} — {cost_phrase} to {payee}.")
    return "\n".join(sentences)


def _turn_step_direction_label(direction: str) -> str:
    """The server's player-facing label for an engine conversion direction."""
    return direction.replace("_", " ").capitalize()


def _conversion_amount_resource(direction: str) -> str:
    """The stock surface an amount answer uses, read from the engine's direction value."""
    verb, separator, resource = direction.partition("_")
    if verb not in {"buy", "sell"} or not separator or not resource:
        raise ValueError(f"Conversion direction has no amount resource: {direction!r}")
    return resource.split("_", 1)[0]


def _turn_step_answers(
    step: Any,
    building_name: str,
    after_step: Any,
) -> list[dict[str, str | int]]:
    """Ordered, server-owned answers for exactly one committed building step."""
    answers: list[dict[str, str | int]] = [
        {"field": "building", "label": building_name, "value": step.building_id}
    ]
    if step.hire_payment is not None:
        answers.append(
            {
                "field": "hire_payment",
                "label": str(step.hire_payment),
                "value": str(step.hire_payment),
            }
        )
    if isinstance(step, BuildingActivationStep):
        return answers
    if isinstance(step, BuildingRelocationStep):
        answers.append(
            {
                "field": "selected_position",
                "label": str(step.selected_position),
                "value": str(step.selected_position),
            }
        )
        return answers
    if not isinstance(step, BuildingConversionStep):
        raise TypeError(f"Unsupported turn step type: {type(step)!r}")

    answers.append(
        {
            "field": "direction",
            "label": _turn_step_direction_label(step.direction),
            "value": step.direction,
        }
    )
    if step.direction.endswith("_piety"):
        answers.append(
            {
                "field": "piety_destination",
                "label": str(after_step.piety),
                "value": after_step.piety,
            }
        )
    else:
        answers.append(
            {
                "field": "amount",
                "label": _conversion_amount_resource(step.direction),
                "value": step.amount,
            }
        )
    return answers


def _building_ability_is_greyed(source: Any) -> bool:
    """Whether this source needs the page's unavailable-building treatment."""
    return source.reason in {
        BuildingAbilityReason.INSUFFICIENT_RESOURCE,
        BuildingAbilityReason.MERCHANT_RESOURCE_NONE,
        BuildingAbilityReason.END_OF_TURN_NOT_REACHED,
        BuildingAbilityReason.BEGINNING_OF_TURN_PASSED,
        BuildingAbilityReason.MID_SOW,
        BuildingAbilityReason.ALREADY_USED,
        BuildingAbilityReason.EFFECT_APPLIES_FOR_REST_OF_TURN,
    }


_PAID_BANK_TILE_STATUS_TEXT = "Usable: choose it when an action asks how to pay."
_BANK_WITHOUT_PAYMENT_ACTION_STATUS_TEXT = "Cannot be used: no action this turn can use the Bank."


def _paid_bank_hire_source(source: Any) -> bool:
    """Whether this is the paid Bank source now selected inside a full-turn action.

    Wagon Yard's free Bank hire remains a committed step. It resolves as an ``unavailable``
    generic source while its enumerated step is the authority, so it deliberately does not enter
    this inline-payment presentation.
    """
    return (
        source.building_key == "bank"
        and source.source_type in {"live_market_hire", "opponent_active_hire"}
        and source.hire_cost > 0
    )


def _building_ability_source_payload(
    source: Any,
    *,
    paid_bank_payment_on_offer: bool = False,
) -> dict[str, Any]:
    """Serialize every fact the browser needs to describe one resolved building source."""
    payload = {
        "building_id": source.building_key,
        "source_type": source.source_type,
        "owner": source.owner,
        "hire_resource": source.hire_resource,
        "hire_resource_chosen": source.hire_resource_chosen,
        "hire_cost": source.hire_cost,
        "payable_to": source.payable_to,
        "usable": source.usable,
        "reason": source.reason or None,
        # This is an affordance state settled beside the source, not a browser-side reading of a
        # reason code. The page applies the supplied treatment to every rendering of this tile.
        "greyed": _building_ability_is_greyed(source),
        # This is deliberately a value, not a browser-side mapping from `reason`: an absent
        # engine reason produces no sentence instead of a helpful-looking fiction.
        "status_text": _building_ability_status_text(source),
    }
    if (
        source.building_key == "bank"
        and source.reason == BuildingAbilityReason.INSUFFICIENT_RESOURCE
    ):
        return payload | {"status_text": _BANK_WITHOUT_PAYMENT_ACTION_STATUS_TEXT}
    if not _paid_bank_hire_source(source) or source.reason == BuildingAbilityReason.MID_SOW:
        return payload
    if paid_bank_payment_on_offer:
        return payload | {"status_text": _PAID_BANK_TILE_STATUS_TEXT}

    # A paid Bank source is useful only through an enumerated full-turn payment choice. Its
    # generic source may still be affordable even when no action asks for a replaceable resource,
    # so the tile's affordance has to follow that action set rather than quote the stale hire fee.
    return payload | {
        "usable": False,
        "reason": None,
        "greyed": True,
        "status_text": _BANK_WITHOUT_PAYMENT_ACTION_STATUS_TEXT,
    }


def _building_is_live_market_tile(state: Any, config: Any, building_key: str) -> bool:
    """Whether this ability source is drawn on a usable building tile in the live market."""
    return building_key in state.building_market and is_building_live(state, building_key)


def _building_ability_map_fields(state: Any, config: Any, building: Any) -> dict[str, Any]:
    """Serialize the map-only facts for one building without asking the page where it is."""
    on_map = building.id in state.building_market
    fields: dict[str, Any] = {
        "map_tile": _building_is_live_market_tile(state, config, building.id),
    }
    if on_map:
        fields["construct_cost_text"] = f"Construct for {building.stone_cost} stone."
    return fields


def _used_building_ability_reason(building_id: str) -> BuildingAbilityReason:
    """Name whether a completed tile is spent or continues to permit its turn effect."""
    if building_id in _PERMITTER_BUILDING_IDS:
        return BuildingAbilityReason.EFFECT_APPLIES_FOR_REST_OF_TURN
    return BuildingAbilityReason.ALREADY_USED


def _route_buildings_used_by_committed_sow(state: Any) -> frozenset[str]:
    """Read completed route effects from the engine event that records their use.

    Route buildings are chosen as fields of a FullTurnAction, rather than as turn steps, so they
    intentionally do not enter ``used_buildings``. The transition emits this building-bonus event
    only while applying that action; a browser preview has no corresponding committed event.
    """
    return frozenset(
        building_id
        for event in state.turn_progress.events
        if event.event_type is EventType.BUILDING_BONUS
        and (details := dict(event.details)).get("action") == "sowing"
        and isinstance(building_id := details.get("building"), str)
        and building_id in _ROUTE_BUILDING_IDS
    )


def _buildings_with_spent_turn_abilities(state: Any) -> frozenset[str]:
    """Name buildings whose allowance was spent by either committed turn representation.

    ``used_buildings`` records ordinary committed turn steps.  Route buildings instead travel on
    a sow action, so their committed ``BUILDING_BONUS`` events are the second source; widening
    ``used_buildings`` would erase that distinction from the engine state.
    """
    return frozenset(
        state.turn_progress.used_buildings | _route_buildings_used_by_committed_sow(state)
    )


def _building_ability_source_after_turn_use(state: Any, source: Any) -> Any:
    """Keep a completed building effect unavailable on the page without changing engine lookups.

    The lookup after a hire can report its source unaffordable because the committed step paid its
    fee, so this cannot rely on `source.usable`. Corpus measurement currently finds no committed
    step that overwrites a `DONATED`, `NOT_LIVE`, or `NOT_SELECTED` source; that is an observed
    invariant, not one this function constructs.
    """
    if source.building_key not in _buildings_with_spent_turn_abilities(state):
        return source
    return dataclasses.replace(
        source,
        usable=False,
        reason=_used_building_ability_reason(source.building_key),
    )


def _route_family_ability_fields(
    source: Any, route_family_building_ids: set[str] | None
) -> dict[str, Any]:
    """Server-written interaction state for an offered Kogge or Cloisters route family."""
    if (
        not route_family_building_ids
        or source.building_key not in route_family_building_ids
    ):
        return {}
    in_effect = _PERMITTER_STATUS_TEXT
    if source.reason == BuildingAbilityReason.EFFECT_APPLIES_FOR_REST_OF_TURN:
        return {
            "family_visibility": "in_effect",
            "in_effect_status_text": in_effect,
        }
    if source.source_type == "own_active":
        return {
            # Ownership is a source fact, not a visual deduction from where the tile was drawn.
            # `building_ability_source` resolves donation before this branch, so a donated tile
            # remains unavailable even though it still sits on its former owner's board.
            "family_visibility": "always",
            "owned_status_text": (
                _ROUTE_FAMILY_BY_BUILDING_ID[source.building_key].owned_status_text
            ),
            "in_effect_status_text": in_effect,
            "greyed": False,
        }
    cost_phrase = _building_hire_cost_phrase(source)
    payee = _building_ability_party_name(source.payable_to)
    if cost_phrase is None or payee is None:
        raise AssertionError(
            "An offered hired route family must carry a resolved hire cost and payee."
        )
    payment = f"{cost_phrase} to {payee}"
    return {
        "family_visibility": "toggle",
        # The page switches among these finished server sentences; its only local fact is which
        # already-offered family the player clicked.
        "toggle_waiting_text": (
            "Pick up acolytes first, then show the routes it opens — "
            f"{payment} if you use one."
        ),
        "toggle_off_text": (
            "After choosing an origin, show the routes it opens — "
            f"{payment} if you use one."
        ),
        "toggle_on_text": (
            "Routes shown — click to hide and restart your sow. "
            "Nothing is paid until you use one."
        ),
        "in_effect_status_text": in_effect,
        # The toggle controls a candidate family, rather than activating the building at this
        # cursor. Its usable route is still open during sow, so the server keeps its tile vivid.
        "greyed": False,
    }


def building_abilities_payload(
    state: Any,
    config: Any,
    *,
    route_family_building_ids: set[str] | None = None,
    actions: tuple[Any, ...] | list[Any] | None = None,
) -> list[dict[str, Any]]:
    """Resolve every catalogue building for the active player in this exact window."""
    available_actions = tuple(legal_actions(state, config) if actions is None else actions)
    paid_bank_payment_on_offer = _paid_bank_payment_on_offer(available_actions)
    return [
        _building_ability_source_payload(
            source,
            paid_bank_payment_on_offer=paid_bank_payment_on_offer,
        )
        | _building_ability_map_fields(state, config, building)
        | _route_family_ability_fields(source, route_family_building_ids)
        for building in config.buildings.catalogue
        for source in (
            _building_ability_source_after_turn_use(
                state,
                building_ability_source(
                    state,
                    config,
                    acting_player=state.active_player,
                    building_key=building.id,
                ),
            ),
        )
    ]


def building_ability_windows_payload(
    state: Any,
    config: Any,
    *,
    route_family_building_ids: set[str] | None = None,
    actions: tuple[Any, ...] | list[Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Describe the building availability the page may reveal at each server-named turn window.

    The sow itself is held in browser preview state until Confirm. Its availability therefore has
    to travel alongside the candidate phases: a browser that inferred the restriction from its
    local cursor would be holding a second copy of the turn rule.
    """
    available_actions = tuple(legal_actions(state, config) if actions is None else actions)
    paid_bank_payment_on_offer = _paid_bank_payment_on_offer(available_actions)
    sources = tuple(
        _building_ability_source_after_turn_use(
            state,
            building_ability_source(
                state,
                config,
                acting_player=state.active_player,
                building_key=building.id,
            ),
        )
        for building in config.buildings.catalogue
    )
    static_reasons = {
        BuildingAbilityReason.NOT_LIVE,
        BuildingAbilityReason.NOT_SELECTED,
        BuildingAbilityReason.DONATED,
    }
    sow_sources = tuple(
        source
        if source.reason in static_reasons
        else dataclasses.replace(
            source,
            usable=False,
            reason=BuildingAbilityReason.MID_SOW,
        )
        for source in sources
    )

    window_states = {
        "beginning": dataclasses.replace(
            state,
            turn_progress=dataclasses.replace(state.turn_progress, resolution_committed=False),
        ),
        "end": dataclasses.replace(
            state,
            turn_progress=dataclasses.replace(state.turn_progress, resolution_committed=True),
        ),
    }
    window_reasons = {
        "beginning": BuildingAbilityReason.END_OF_TURN_NOT_REACHED,
        "end": BuildingAbilityReason.BEGINNING_OF_TURN_PASSED,
    }
    offered_by_window = {
        window_name: {
            step.building_id for step in turn_steps(window_state, config)
        }
        for window_name, window_state in window_states.items()
    }
    opposite_window = {"beginning": "end", "end": "beginning"}

    def entries_for_window(window_name: str) -> tuple[Any, ...]:
        """Project sources onto one engine-enumerated turn window."""
        entries = []
        for source in sources:
            if source.building_key in offered_by_window[window_name]:
                # Some legacy step enumerators know a free activation that the generic source
                # lookup cannot price. The enumerated step is the authority for this window.
                entries.append(dataclasses.replace(source, usable=True, reason=None))
            elif source.building_key in offered_by_window[opposite_window[window_name]]:
                entries.append(
                    dataclasses.replace(
                        source,
                        usable=False,
                        reason=window_reasons[window_name],
                    )
                )
            else:
                entries.append(source)
        return tuple(entries)

    def window(*, offered: bool, entries: tuple[Any, ...]) -> dict[str, Any]:
        return {
            "turn_steps_offered": offered,
            "abilities": [
                _building_ability_source_payload(
                    source,
                    paid_bank_payment_on_offer=paid_bank_payment_on_offer,
                )
                | _building_ability_map_fields(
                    state,
                    config,
                    building_by_id(config.buildings, source.building_key),
                )
                | _route_family_ability_fields(source, route_family_building_ids)
                for source in entries
            ],
        }

    return {
        "beginning": window(offered=True, entries=entries_for_window("beginning")),
        "sow": window(offered=False, entries=sow_sources),
        "end": window(offered=True, entries=entries_for_window("end")),
    }


def _turn_step_ability_payload(state: Any, config: Any, step: Any, result: Any) -> dict[str, Any]:
    """Serialize the source an enumerated step actually applies, including a Cornucopia pick."""
    source = building_ability_source(
        state,
        config,
        acting_player=state.active_player,
        building_key=step.building_id,
    )
    payload = _building_ability_source_payload(source)
    hire_event = next(
        (
            event
            for event in result.events
            if event.event_type is EventType.BUILDING_HIRED
            and event.action_id == turn_step_id(step)
        ),
        None,
    )
    if hire_event is None:
        return payload

    details = dict(hire_event.details)
    resource = str(details.get("resource", "none"))
    amount = int(details.get("amount", 0))
    payee = str(details.get("payee", "none"))
    if amount <= 0 or resource == "none":
        return payload | {
            "usable": True,
            "reason": None,
            "hire_resource": None,
            "hire_resource_chosen": False,
            "hire_cost": 0,
            "payable_to": None,
            "status_text": "Usable: no payment.",
        }

    # `resource` is the payment on the applied step's event. It is not re-resolved from the
    # source, which matters when the Merchant's Cornucopia let the payer choose this stock.
    payee_name = _building_ability_party_name(payee)
    return payload | {
        "usable": True,
        "reason": None,
        "hire_resource": resource,
        "hire_resource_chosen": resource != source.hire_resource,
        "hire_cost": amount,
        "payable_to": payee,
        "status_text": f"Usable: pay {amount} {resource} to {payee_name}.",
    }


class StaleStateToken(Exception):
    """The submission quoted a list that is no longer the one on offer."""


class UnknownAction(Exception):
    """The submission named an action that is not legal in the position now held."""


class UnknownTurnStep(Exception):
    """The submission named a committed building step that is not legal in the position now held."""


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
            '<div class="seat-row" data-seat-row="{seat}">'
            '<span class="seat-label">Seat {seat} ({colour})</span>'
            '<select name="seat_{seat}_role">'
            '<option value="human" selected>Human</option>'
            '<option value="bot" disabled>Bot (disabled)</option>'
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

# An undecided candidate is a server-owned explanation for why the page refuses to choose. These
# are not labels the renderer may invent: a new residue field must stop payload construction until
# it gets player wording, rather than exposing an engine identifier at the table.
UNRESOLVED_FIELD_TEXT = {
    "donate_building_id": "which building to donate",
    "construct_plan": "which roads to build",
    "effective_acolyte_building_id": "which building adds the extra acolytes",
    "effective_acolyte_building_source": "where that building is hired from",
    "free_hire_enabler_building_id": "which building grants the free hire",
    "free_hire_target_building_id": "which building to hire for free",
    "free_hire_target_building_source": "where the free-hired building comes from",
    "bank_payment_building_id": "which building the Bank pays for",
    "bank_payment_building_source": "where that building is hired from",
    "bank_payment_replaced_resource": "which resource the silver replaces",
    "bank_payment_silver_amount": "how much silver to pay",
}

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
BANK_PAYMENT_FIELDS: tuple[str, ...] = (
    "bank_payment_building_id",
    "bank_payment_building_source",
    "bank_payment_replaced_resource",
    "bank_payment_silver_amount",
    "hire_payments",
)
BANK_PAYMENT_PROMPT = "Choose how to pay."
ROUTE_HIRE_FIELDS: tuple[str, ...] = (
    "sow_route_building_id",
    "sow_route_building_source",
    "sow_route_secondary_building_id",
    "sow_route_secondary_building_source",
    "hire_payments",
)
# Action fields that identify one potentially hired building and where it is sourced from.
HIRE_PAYMENT_OWNER_FIELDS: tuple[tuple[str, str], ...] = (
    ("hired_building_id", "hired_building_source"),
    ("sow_route_building_id", "sow_route_building_source"),
    ("sow_route_secondary_building_id", "sow_route_secondary_building_source"),
    ("building_conversion_id", "building_conversion_source"),
    ("bank_payment_building_id", "bank_payment_building_source"),
    ("free_hire_target_building_id", "free_hire_target_building_source"),
    ("effective_acolyte_building_id", "effective_acolyte_building_source"),
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
ORIGIN_PROMPT = "Choose a space to lift acolytes from."
ROUTE_PROMPT = "Follow an arrow."
DUTY_PROMPT = "Choose a duty to take."
SKIP_PROMPT = "Choose the City or Duty space on your route to leave unsown."
RESOLUTION_PROMPT = "Action or Tithe."
RESOURCE_PROMPT = "Choose a resource."
BUILDING_PROMPT = "Choose a building."
HIRE_PROMPT = "Choose whether to hire a building."
CONFESSION_BOX_PROMPT = "Choose whether to use the Confession Box."
ALMS_PAYMENT_PROMPT = "Choose payment."
SEAT_PROMPT = "Choose first player for this round."
ORDINATION_PROMPT = "Choose Duty Action"
ORDINATION_CHOICES: tuple[dict[str, str], ...] = (
    {
        "value": "ordain",
        "label": "Move a serf from the Village to the Abbey",
    },
    {
        "value": "mission",
        "label": "Move an Acolyte from the Abbey to the City",
    },
)

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
    prompt: str,
) -> dict:
    """One whole combination as a step: a scalar to match it by and a sentence to read."""
    return {
        "kind": "combination",
        # A step value is matched with `===` in the page, so it has to be one scalar. Spelled out
        # rather than hashed, so a transcript of a turn stays readable. Every noun is written even
        # at zero, so two mixes cannot collide by one of them leaving a stock out.
        "value": ",".join(f"{noun}={amount}" for noun, amount in amounts),
        "label": _amounts_in_words(verb, amounts),
        # The label says what each option does, but the prompt still names the choice itself.  The
        # browser cannot infer that question from a generic combination kind.
        "prompt": prompt,
    }


def _spoken_position_list(positions: tuple[str, ...]) -> str:
    """Name engine-provided board positions without giving the page a wording job."""
    if len(positions) == 1:
        return positions[0]
    if len(positions) == 2:
        return f"{positions[0]} and {positions[1]}"
    return ", ".join(positions[:-1]) + f", and {positions[-1]}"


def _taxation_step_two_prompt(
    action: FullTurnAction,
    state: Any,
    config: Any,
) -> str:
    """Put the engine's modifier-only Taxation explanation into the step-II question."""
    unlocks = taxation_majority_unlocks_for_action(state, config, action)
    resource_count = len(action.taxation_step2_resources)
    if not unlocks:
        return "Taxation step 2. No other Duty tile is a majority."

    reasons = {unlock.majority_reason for unlock in unlocks}
    unknown_reasons = reasons - {"real_count", "scriptorium", "customs_house"}
    if unknown_reasons:
        raise ValueError(f"Unknown Taxation majority reason: {unknown_reasons.pop()!r}")

    if "customs_house" in reasons:
        explanation = "The Customs House makes your occupied tiles majorities."
    else:
        scriptorium_positions = tuple(
            config.board.positions[unlock.duty_position].replace("_", " ")
            for unlock in unlocks
            if unlock.majority_reason == "scriptorium"
        )
        if not scriptorium_positions:
            explanation = ""
        elif len(scriptorium_positions) == 1:
            explanation = (
                f"The Scriptorium makes {_spoken_position_list(scriptorium_positions)} a majority."
            )
        else:
            explanation = (
                "The Scriptorium makes "
                f"{_spoken_position_list(scriptorium_positions)} majorities."
            )

    prefix = "Taxation step 2."
    if explanation:
        prefix += f" {explanation}"
    return f"{prefix} {_resource_choice_prompt(resource_count)}."


def _number_in_words(number: int) -> str:
    return _NUMBER_WORDS[number] if number < len(_NUMBER_WORDS) else str(number)


def _resource_choice_prompt(resource_count: int) -> str:
    noun = "resource" if resource_count == 1 else "resources"
    return f"Choose {_number_in_words(resource_count)} {noun}"


def _arrangement_prompt(action: FullTurnAction) -> str:
    move_count = len(action.allocation_moves)
    noun = "acolyte" if move_count == 1 else "acolytes"
    return (
        f"Move {_number_in_words(move_count)} {noun} from the Abbey to Special Activity "
        "and/or between Special Activities"
    )


def _resource_delta(before: Any, after: Any) -> dict[str, int]:
    return {
        resource: getattr(after.resources, resource) - getattr(before.resources, resource)
        for resource in COMBINATION_STOCKS
    }


_PREVIEW_EFFECT_FIELDS: tuple[str, ...] = (
    "resource_delta",
    "building_constructed",
    "building_donation",
    "piety_delta",
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
    "effective_acolyte_building_id",
    "effective_acolyte_building_source",
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
    )


def _can_split_ordination_cost_preview(action: Any, *, offer_bank_payment: bool) -> bool:
    """Keep every Bank payment path on its existing preview representation."""
    if offer_bank_payment or not isinstance(action, FullTurnAction):
        return False
    bank_fields = (
        "bank_payment_building_id",
        "hired_building_id",
        "free_hire_target_building_id",
    )
    if any(getattr(action, field, None) == "bank" for field in bank_fields):
        return False
    return not any(
        building_id == "bank" for building_id, _resource in tuple(action.hire_payments or ())
    )


def _turn_action_preview_effects(
    action: Any,
    state: Any,
    config: Any,
    *,
    cache: dict[tuple[Any, ...], dict[str, Any]] | None = None,
    split_ordination_cost: bool = False,
) -> dict[str, Any]:
    """The state changes this complete action can expose on one of its steps.

    The action is applied once at the seam and the effects are diffed from the position the page
    started from. Round-end consequences are deliberately removed: they happen after the turn's
    choice has resolved and are not part of the preview surface.
    """
    preview_key = _preview_effect_action_key(action)
    cache_key = (preview_key, split_ordination_cost) if preview_key is not None else None
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
    if split_ordination_cost and action.resolution.value == "ordination":
        # The Ordination events carry the paid wheat for this exact offered outcome. Keep it
        # separate from route and hire residue so its preview waits for the player's sequence.
        ordination_wheat_paid = sum(
            int(dict(event.details).get("wheat_paid", 0))
            for event in result.events
            if event.event_type is EventType.ORDINATION and event.actor is player
        )
        if ordination_wheat_paid:
            effects["ordination_resource_delta"] = {
                "stone": 0,
                "silver": 0,
                "wheat": -ordination_wheat_paid,
            }
            resource_delta["wheat"] += ordination_wheat_paid
    if any(resource_delta.values()):
        effects["resource_delta"] = resource_delta

    before_buildings = before_player.player_board_slots.active_buildings
    after_buildings = after_player.player_board_slots.active_buildings
    constructed = [
        building_id for building_id in after_buildings if building_id not in before_buildings
    ]
    if len(constructed) == 1 and getattr(action, "construct_building_id", None) == constructed[0]:
        effects["building_constructed"] = constructed[0]

    piety_event = next(
        (
            event
            for event in result.events
            if event.event_type is EventType.PIETY_DELTA and event.actor is player
        ),
        None,
    )
    if piety_event is not None:
        effects["piety_delta"] = dict(piety_event.details)

    before_donated = before_player.player_board_slots.donated_buildings
    after_donated = after_player.player_board_slots.donated_buildings
    donated = [building_id for building_id in after_donated if building_id not in before_donated]
    if len(donated) == 1 and getattr(action, "donate_building_id", None) == donated[0]:
        effects["building_donation"] = donated[0]

    if (
        getattr(action, "resolution", None) is not None
        and action.resolution.value == "give_alms_paid"
    ):
        progress_event = next(
            (event for event in result.events if event.event_type is EventType.ALMS_PROGRESS),
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
    ordination_resource_delta = effects.get("ordination_resource_delta")
    if ordination_resource_delta is not None:
        for step in steps:
            if step["kind"] == "ordination":
                step["resource_delta"] = ordination_resource_delta
                break
    resource_delta = effects.get("resource_delta")
    if resource_delta is not None and not any(
        "resource_delta" in step and step["kind"] != "ordination" for step in steps
    ):
        for step in reversed(steps):
            if step["kind"] in {
                "resolution",
                "hire",
                "resource",
                "combination",
                "building",
            }:
                step["resource_delta"] = resource_delta
                break
    building_id = effects.get("building_constructed")
    if building_id is not None:
        for step in steps:
            if step["kind"] == "building" and step["value"] == building_id:
                step["building_constructed"] = building_id
                break
    donated_building_id = effects.get("building_donation")
    if donated_building_id is not None:
        attached = False
        for step in steps:
            if step["kind"] == "building" and step["value"] == donated_building_id:
                step["building_donation"] = donated_building_id
                attached = True
                break
        if not attached:
            for step in steps:
                if step["kind"] == "resolution":
                    step["building_donation"] = donated_building_id
                    break
    piety_delta = effects.get("piety_delta")
    if piety_delta is not None:
        for step in steps:
            if step["kind"] == "resolution":
                step["piety_delta"] = piety_delta
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
        details["resource"] for details in taxation_events if details.get("step") == "step_1"
    )
    step_2_text = next(
        details.get("resources", "")
        for details in taxation_events
        if details.get("step") == "step_2"
    )
    step_2 = tuple(resource for resource in step_2_text.split(",") if resource)

    def one_unit(resource: str) -> dict[str, int]:
        return {name: int(name == resource) for name in COMBINATION_STOCKS}

    return {
        "taxation_step1_resource": {"resource_delta": one_unit(step_1)},
        "taxation_step2_resources": {
            "resource_delta": {resource: step_2.count(resource) for resource in COMBINATION_STOCKS},
            "resource_unit_deltas": {
                resource: one_unit(resource) for resource in COMBINATION_STOCKS
            },
        },
    }


def _hire_source_phrase(source: str) -> str:
    if source == "market":
        return "market"
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
                "prompt": HIRE_PROMPT,
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
    building_name = building_by_id(config.buildings, building_id).name
    cost_phrase = _building_hire_cost_phrase(source)
    return (
        {
            "kind": "hire",
            # One scalar so the page can match with `===`.
            "value": f"{building_id}:{source_label}",
            "label": (
                f"Hire {building_name} from {_hire_source_phrase(source_label)} for {cost_phrase}"
            ),
            "prompt": HIRE_PROMPT,
        },
        HIRE_FIELDS,
    )


def _hire_payment_map(action: FullTurnAction) -> dict[str, str]:
    """Hire payment resources keyed by hired building id for one action."""
    return {building_id: resource for building_id, resource in tuple(action.hire_payments or ())}


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


def _arrangement_value(action: Any) -> str:
    """Allocation answer encoded as one scalar, keyed by where cubes end up and not by move order."""
    outcome = allocation_outcome(action.allocation_moves)
    if not outcome:
        return "none"
    return ",".join(f"{slot}={delta:+d}" for slot, delta in outcome)


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


def _resource_payment_label(action: FullTurnAction, state: Any, config: Any) -> str:
    """Read this action's ordinary resource cost from the engine transaction it enumerated."""
    result = apply_action(state, action, config)
    resource_costs = {resource: 0 for resource in COMBINATION_STOCKS}
    for event in result.events:
        if event.event_type is not EventType.RESOURCE_DELTA or event.action_id != action_id(action):
            continue
        for resource in COMBINATION_STOCKS:
            resource_costs[resource] += max(0, -int(dict(event.details).get(resource, 0)))

    before_player = state.player_state(state.active_player)
    after_player = result.state.player_state(state.active_player)
    piety_cost = max(0, before_player.piety - after_player.piety)
    costs = [
        f"{amount} {resource}"
        for resource, amount in resource_costs.items()
        if amount > 0
    ]
    if piety_cost:
        costs.append(f"{piety_cost} piety")
    if not costs:
        raise AssertionError(
            "A Bank payment choice must have an engine-reported ordinary resource cost."
        )
    return ", ".join(costs)


def _bank_hire_silver_amount(action: FullTurnAction) -> int:
    """Read the Bank hire's silver from the payment tuple carried by this exact action."""
    amount = sum(
        building_id == "bank" and resource == "silver"
        for building_id, resource in tuple(action.hire_payments or ())
    )
    if amount <= 0:
        raise AssertionError("A paid Bank action must carry its silver hire payment.")
    return amount


def _bank_hire_fact(action: FullTurnAction) -> str:
    """State the Bank hire and substitution with the source and amounts the action selected."""
    source = action.bank_payment_building_source
    replaced_resource = action.bank_payment_replaced_resource
    substitution_silver = action.bank_payment_silver_amount
    if source is None or replaced_resource is None or substitution_silver is None:
        raise AssertionError("A Bank hire fact requires its source, replaced resource, and silver.")
    hire_source = "the market" if source == "market" else _building_ability_party_name(source)
    if not hire_source:
        raise AssertionError("A Bank hire fact requires a player-facing hire source.")
    hire_silver = _bank_hire_silver_amount(action)
    return (
        "This action uses the Bank — "
        f"{hire_silver} silver to hire it from {hire_source}, and "
        f"{substitution_silver} silver in place of {substitution_silver} {replaced_resource}."
    )


def _bank_payment_step(
    action: FullTurnAction,
    *,
    state: Any,
    config: Any,
) -> tuple[dict, tuple[str, ...]]:
    """Present the ordinary cost or the atomic Bank hire-and-substitution it replaces."""
    if action.bank_payment_building_id is None:
        value = "none"
        label = _resource_payment_label(action, state, config)
        hire_text = ""
    else:
        source = action.bank_payment_building_source
        replaced_resource = action.bank_payment_replaced_resource
        substitution_silver = action.bank_payment_silver_amount
        if source is None or replaced_resource is None or substitution_silver is None:
            raise AssertionError("A Bank payment action must carry its complete payment choice.")
        value = ":".join(
            (
                source,
                replaced_resource,
                str(substitution_silver),
            )
        )
        total_silver = _bank_hire_silver_amount(action) + substitution_silver
        label = f"{total_silver} silver, hires the Bank"
        hire_text = _bank_hire_fact(action)
    return (
        {
            "kind": "combination",
            "value": value,
            "label": label,
            "prompt": BANK_PAYMENT_PROMPT,
            **({"hire_text": hire_text} if hire_text else {}),
        },
        BANK_PAYMENT_FIELDS,
    )


def _presented(
    action: Any,
    *,
    state: Any | None = None,
    config: Any | None = None,
    offer_hire: bool = False,
    offer_bank_payment: bool = False,
    hire_payment_buildings: tuple[str, ...] = (),
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
        _resource_step_metadata(action, state, config) if include_preview_effects else {}
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
                    "prompt": CONFESSION_BOX_PROMPT,
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
    if isinstance(action, EndTurnAction):
        return [
            (
                {
                    "kind": "resolution",
                    "value": "end_turn",
                    "prompt": "End the turn.",
                    # The engine has no further choice to put to the player: Confirm submits this
                    # already-settled action directly instead of opening the Action split.
                    "direct_confirm": True,
                },
                (),
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
            prompt=ALMS_PAYMENT_PROMPT,
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
        prompt = _resource_choice_prompt(len(taken))
        if resolution == "taxation" and state is not None and config is not None:
            if not isinstance(action, FullTurnAction):
                raise ValueError("Taxation step-II presentation requires a full turn action.")
            prompt = _taxation_step_two_prompt(action, state, config)
        step = _combination_step(
            verb,
            amounts,
            prompt=prompt,
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
                    "prompt": _arrangement_prompt(action),
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
                    "choices": ORDINATION_CHOICES,
                },
                ("ordination_steps",),
            )
        )
    if offer_bank_payment and isinstance(action, FullTurnAction):
        if state is None or config is None:
            raise ValueError("state and config are required to present Bank payment choices.")
        presented.append(_bank_payment_step(action, state=state, config=config))
    return presented


def _presented_rows(
    action: Any,
    *,
    state: Any | None = None,
    config: Any | None = None,
    offer_hire: bool = False,
    offer_bank_payment: bool = False,
    hire_payment_buildings: tuple[str, ...] = (),
    include_preview_effects: bool = True,
) -> list[tuple[dict, tuple[str, ...]]]:
    """Call `_presented`, while still allowing tests to monkeypatch the old one-arg shape."""
    try:
        return _presented(
            action,
            state=state,
            config=config,
            offer_hire=offer_hire,
            offer_bank_payment=offer_bank_payment,
            hire_payment_buildings=hire_payment_buildings,
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
    offer_bank_payment: bool = False,
    hire_payment_buildings: tuple[str, ...] = (),
    include_preview_effects: bool = True,
) -> list[dict]:
    return [
        step
        for step, _fields in _presented_rows(
            action,
            state=state,
            config=config,
            offer_hire=offer_hire,
            offer_bank_payment=offer_bank_payment,
            hire_payment_buildings=hire_payment_buildings,
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
    if not (isinstance(action, FullTurnAction) and action.sow_route_omitted_location is not None):
        return route, None
    combined_with_kogge = (
        action.sow_route_building_id == "kogge"
        and action.sow_route_secondary_building_id == "cloisters"
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


def _steps_key(steps: list[dict]) -> tuple[Any, ...]:
    return tuple(
        tuple(step["value"]) if isinstance(step["value"], tuple) else step["value"]
        for step in steps
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


def _bank_payment_context_key(action: FullTurnAction) -> tuple[Any, ...]:
    """Identify one complete action apart from the atomic Bank payment choice it may add."""
    return tuple(
        getattr(action, field.name)
        for field in dataclasses.fields(FullTurnAction)
        if field.name not in {*BANK_PAYMENT_FIELDS, "action_type"}
    )


def _is_paid_bank_payment_action(action: Any) -> bool:
    """Whether a full-turn action atomically hires the Bank and uses its payment effect."""
    return (
        isinstance(action, FullTurnAction)
        and action.bank_payment_building_id == "bank"
        and action.bank_payment_building_source not in (None, "own_active")
    )


def _paid_bank_payment_on_offer(actions: tuple[Any, ...] | list[Any]) -> bool:
    """Whether this exact action list contains a paid Bank payment choice."""
    return any(_is_paid_bank_payment_action(action) for action in actions)


def _steps_before_hire_payment_questions(
    action: Any,
    player_id: str,
    *,
    state: Any,
    config: Any,
    offer_hire: bool = False,
    include_preview_effects: bool = True,
) -> list[dict]:
    """Decision steps through the hire choice, stopping before any hire-payment stock choice."""
    if isinstance(
        action,
        (EndTurnAction, StartPlayerConfessionBoxAction, StartPlayerSelectionAction),
    ):
        return _address_steps(
            _presented_steps(
                action,
                state=state,
                config=config,
                offer_hire=offer_hire,
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
    steps.append(
        {
            "kind": "origin",
            "value": action.origin,
            "prompt": ORIGIN_PROMPT,
            "counter": counter,
        }
    )
    steps += _route_edge_steps(
        action,
        edge_values=edge_values,
        edge_destinations=edge_destinations,
        edge_counters=edge_counters,
        state=state,
        config=config,
    )
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
    return _address_steps(steps, player_id)


def _hire_payment_question_buildings_by_action_id(
    actions: list[Any],
    *,
    player_id: str,
    state: Any,
    config: Any,
    offer_hire_by_action_id: dict[str, bool],
    include_preview_effects: bool = True,
) -> dict[str, tuple[str, ...]]:
    """Per action, which hired buildings still need a stock-choice question."""
    action_with_ids = [(action, action_id(action)) for action in actions]
    by_action_id: dict[str, tuple[str, ...]] = {
        move_id: tuple() for _action, move_id in action_with_ids
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
                include_preview_effects=include_preview_effects,
            )
        )
        if isinstance(action, FullTurnAction):
            members_by_context.setdefault(key, []).append((action, move_id))

    for members in members_by_context.values():
        if not members:
            continue
        payment_map_by_action_id = {
            move_id: _hire_payment_map(member) for member, move_id in members
        }

        shared_open: set[str] = set()
        shared_buildings = set(payment_map_by_action_id[members[0][1]])
        for _member, move_id in members[1:]:
            shared_buildings &= set(payment_map_by_action_id[move_id])
        for building_id in shared_buildings:
            if (
                len(
                    {payment_map_by_action_id[move_id][building_id] for _member, move_id in members}
                )
                > 1
            ):
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


def _route_building_ids(action: Any) -> tuple[str, ...]:
    """The route permitters an action uses, in the action's own primary/secondary order."""
    if not isinstance(action, FullTurnAction):
        return tuple()
    return tuple(
        building_id
        for building_id in (
            action.sow_route_building_id,
            action.sow_route_secondary_building_id,
        )
        if building_id is not None
    )


def _route_edge_metadata(
    action: Any,
    *,
    edge_destinations: tuple[int, ...],
    index: int,
    config: Any,
) -> dict[str, Any]:
    """Describe the route building this exact edge needs, without asking the page to infer it."""
    route_building_ids = _route_building_ids(action)
    if not route_building_ids:
        return {}

    building_id = None
    # The extra candidate hop is Cloisters' effect. It wins over a Kogge reversal at that hop
    # because the player is using their extra movement there, not merely crossing the river.
    if "cloisters" in route_building_ids and index == len(edge_destinations) - 1:
        building_id = "cloisters"
    elif "kogge" in route_building_ids:
        origin = action.origin if index == 0 else edge_destinations[index - 1]
        if edge_destinations[index] not in config.board.neighbors(origin):
            building_id = "kogge"

    if building_id is None:
        return {}
    route_building_index = _ROUTE_FAMILY_BY_BUILDING_ID[building_id].i
    # The compact index points into the server-written palette on the page payload. Repeating the
    # full id, paint, and priority on every route candidate pushed the largest play page past its
    # established size ceiling.
    return {"family": route_building_index}


def _route_edge_steps(
    action: Any,
    *,
    edge_values: tuple[str, ...],
    edge_destinations: tuple[int, ...],
    edge_counters: tuple[int, ...],
    state: Any,
    config: Any,
) -> list[dict]:
    """Return route decisions, with a hired route's server-written cost on its first hop."""
    hire_text = (
        _route_hire_sentence(action, state, config) if isinstance(action, FullTurnAction) else ""
    )
    return [
        {
            "kind": "edge",
            "value": value,
            "prompt": ROUTE_PROMPT,
            "counter": edge_counters[index],
            **({"hire_text": hire_text} if index == 0 and hire_text else {}),
            **_route_edge_metadata(
                action,
                edge_destinations=edge_destinations,
                index=index,
                config=config,
            ),
        }
        for index, value in enumerate(edge_values)
    ]


def _covered_fields(
    action: Any,
    state: Any,
    config: Any,
    *,
    offer_hire: bool = False,
    offer_bank_payment: bool = False,
    hire_payment_buildings: tuple[str, ...] = (),
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
            offer_bank_payment=offer_bank_payment,
            hire_payment_buildings=hire_payment_buildings,
            include_preview_effects=include_preview_effects,
        )
        for name in fields
    }
    if isinstance(action, FullTurnAction) and action.sow_route_building_id is not None:
        covered.update(ROUTE_HIRE_FIELDS)
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
        if field.name not in DECIDED_FIELDS and field.name != "action_type"
    )


def decision_steps(
    action: Any,
    player_id: str,
    *,
    state: Any,
    config: Any,
    offer_hire: bool = False,
    offer_bank_payment: bool = False,
    hire_payment_buildings: tuple[str, ...] = (),
    preview_effects: dict[str, Any] | None = None,
    include_preview_effects: bool = True,
) -> list[dict]:
    """The questions this action is an answer to, in the order the page asks them.

    Origin, then the route one space at a time, then (for Cloisters walks) which City/Duty space is
    left unsown, then which duty was selected, then what to do with it, then any explicit hire and
    wildcard-hire stock choices, then whatever that resolution goes on to ask. A setup sow stops
    after the route because that is all it has.

    Each step says what KIND of thing it is, because they are not answered in the same place -- and
    Three of them now share one surface and still have to stay distinct on it. `origin`, `skip`,
    and `duty` are all answered by pointing at a wheel space, and are distinct kinds so the page can
    mark each question differently without consulting field names or writing a second copy of what
    any one means. The others are still separated by where they are answered: a resolution is beside
    the board, a stock is on the asking seat's own board, a seat is a whole board, a building is a
    hex on the round track, and a combination is a set of amounts that only go together one way.

    Route length is not fixed. It is however many acolytes were lifted, so it varies by origin and
    by turn, and nothing here or on the page may assume a number.
    """
    # A start-player selection is one question and nothing before it. There is no origin to lift
    # from and no duty to resolve: whoever holds the marker names a player, and that is the whole
    # of the action.
    if isinstance(
        action,
        (EndTurnAction, StartPlayerConfessionBoxAction, StartPlayerSelectionAction),
    ):
        return _address_steps(
            _presented_steps(
                action,
                state=state,
                config=config,
                offer_hire=offer_hire,
                offer_bank_payment=offer_bank_payment,
                hire_payment_buildings=hire_payment_buildings,
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
    steps += [
        {
            "kind": "origin",
            "value": action.origin,
            "prompt": ORIGIN_PROMPT,
            # What the counter reads once the origin is taken and the hand is lifted.
            "counter": counter,
        }
    ]
    steps += _route_edge_steps(
        action,
        edge_values=edge_values,
        edge_destinations=edge_destinations,
        edge_counters=edge_counters,
        state=state,
        config=config,
    )
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
        offer_bank_payment=offer_bank_payment,
        hire_payment_buildings=hire_payment_buildings,
        include_preview_effects=include_preview_effects,
    )
    if preview_effects is None and include_preview_effects:
        preview_effects = _turn_action_preview_effects(
            action,
            state,
            config,
            split_ordination_cost=_can_split_ordination_cost_preview(
                action,
                offer_bank_payment=offer_bank_payment,
            ),
        )
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
    offer_bank_payment: bool = False,
    hire_payment_buildings: tuple[str, ...] = (),
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
        offer_bank_payment=offer_bank_payment,
        hire_payment_buildings=hire_payment_buildings,
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
        name for name in DECIDED_FIELDS if len({getattr(member, name) for member in members}) > 1
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


def _unresolved_field_text(name: str) -> str:
    """Return the server-written player name for one field blocking a candidate."""
    try:
        return UNRESOLVED_FIELD_TEXT[name]
    except KeyError as error:
        raise RuntimeError(f"Unresolved field {name!r} has no player-facing name.") from error


def _align_implicit_taxation_step_two_prompts(candidates: list[dict]) -> None:
    """Give one UI frontier the positive engine explanation when a passive branch is implicit.

    Scriptorium and Customs House are neither offered nor confirmed.  Their positive Taxation
    actions therefore share every visible answer before step II with an unmodified no-bonus
    action.  The pills can only complete the positive branch, but candidate order used to choose
    the no-bonus sentence.  Select the positive branch's server-written prompt for that shared
    frontier; this changes neither actions nor the browser's generic prompt-reveal logic.
    """
    grouped: collections.defaultdict[tuple[Any, ...], list[tuple[dict, int]]] = (
        collections.defaultdict(list)
    )
    for candidate in candidates:
        steps = candidate["steps"]
        for index, step in enumerate(steps):
            if step["kind"] != "combination" or "resource_total" not in step:
                continue
            prefix = tuple(
                tuple(previous["value"])
                if isinstance(previous["value"], tuple)
                else previous["value"]
                for previous in steps[:index]
            )
            grouped[prefix].append((candidate, index))
            break

    for frontier in grouped.values():
        positive_prompts = {
            candidate["steps"][index]["prompt"]
            for candidate, index in frontier
            if candidate["steps"][index]["resource_total"] > 0
        }
        if not positive_prompts:
            continue
        if len(positive_prompts) != 1:
            raise AssertionError(
                "Taxation step-II candidates at one visible frontier disagree about their "
                "positive explanation."
            )
        prompt = positive_prompts.pop()
        for candidate, index in frontier:
            candidate["steps"][index]["prompt"] = prompt


def _frontier_value(value: Any) -> Any:
    """Make a turn-step value usable as part of a frontier key."""
    if isinstance(value, (list, tuple)):
        return tuple(_frontier_value(part) for part in value)
    return value


def _mark_unambiguous_edge_steps(candidates: list[dict]) -> list[int]:
    """Name the family selections that make a movement continuation automatic.

    The page filters route candidates by the family's current visibility before it offers an
    answer.  A marker made from every candidate would therefore describe a different frontier
    from the one the player sees.  Enumerating the (at most two) offered route families keeps the
    decision on the server while letting the page match its current selection to an explicit
    server-written set.  The returned indexes are that exact enumeration, for the payload to carry
    instead of scanning candidates again.
    """
    offered_families = sorted(
        {
            family
            for candidate in candidates
            for family in candidate.get("family", ())
        }
    )
    selections = [
        (
            sum(
                _ROUTE_FAMILY_BY_INDEX[family].mask
                for index, family in enumerate(offered_families)
                if mask & (1 << index)
            ),
            frozenset(
                family for index, family in enumerate(offered_families) if mask & (1 << index)
            ),
        )
        for mask in range(1 << len(offered_families))
    ]

    for selection_mask, selection in selections:
        frontiers: collections.defaultdict[tuple[Any, ...], list[dict]] = collections.defaultdict(
            list
        )
        for candidate in candidates:
            if not set(candidate.get("family", ())).issubset(selection):
                continue
            prefix: list[Any] = []
            for step in candidate["steps"]:
                frontiers[tuple(prefix)].append(step)
                prefix.append(_frontier_value(step["value"]))

        for steps in frontiers.values():
            offered: collections.defaultdict[tuple[Any, Any], list[dict]] = collections.defaultdict(
                list
            )
            for step in steps:
                offered[(step["kind"], _frontier_value(step["value"]))].append(step)
            if len(offered) != 1:
                continue
            sole_steps = next(iter(offered.values()))
            sole_option = sole_steps[0]
            if (
                sole_option["kind"] != "edge"
                # An action-carried hire is a player choice even when its route continuation is
                # otherwise forced: following it is what commits to paying on Confirm.  This is
                # deliberately checked among this selection's variants, before no-family routes
                # can be collapsed with their hired sibling.
                or any("hire_text" in step for step in sole_steps)
            ):
                continue
            for step in sole_steps:
                # `auto` is a compact set of route-family bit masks.  This lives on every marked
                # candidate in the largest play payload, where repeating long key names or nested
                # family lists breaches the page-size ceiling.
                step.setdefault("auto", []).append(selection_mask)
    return offered_families


def _route_family_building_ids(family_indexes: list[int]) -> set[str]:
    """Map the automatic marker's exact offered-family list to its building IDs."""
    return {
        _ROUTE_FAMILY_BY_INDEX[index].building_id
        for index in family_indexes
    }


def _turn_candidates_and_auto_family_indexes(
    state: Any,
    config: Any,
    *,
    actions: tuple[Any, ...] | list[Any] | None = None,
    include_preview_effects: bool = True,
) -> tuple[list[dict], list[int]]:
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
    bank_payment_contexts = {
        _bank_payment_context_key(action)
        for action in actions
        if _is_paid_bank_payment_action(action)
    }
    steps_by_action_id: dict[str, list[dict]] = {}
    offer_hire_by_action_id: dict[str, bool] = {}
    offer_bank_payment_by_action_id: dict[str, bool] = {}
    preview_effects_by_action_id: dict[str, dict[str, Any]] = {}
    preview_effect_cache: dict[tuple[Any, ...], dict[str, Any]] = {}
    hire_payment_buildings_by_action_id: dict[str, tuple[str, ...]] = {}
    for action in actions:
        move_id = action_id(action)
        offered_hire = isinstance(action, FullTurnAction) and (
            _resolution_context_key(action, config) in hire_contexts
        )
        offer_hire_by_action_id[move_id] = offered_hire
        offer_bank_payment_by_action_id[move_id] = isinstance(action, FullTurnAction) and (
            _bank_payment_context_key(action) in bank_payment_contexts
        )
        preview_effects_by_action_id[move_id] = (
            _turn_action_preview_effects(
                action,
                state,
                config,
                cache=preview_effect_cache,
                split_ordination_cost=_can_split_ordination_cost_preview(
                    action,
                    offer_bank_payment=offer_bank_payment_by_action_id[move_id],
                ),
            )
            if include_preview_effects and isinstance(action, FullTurnAction)
            else {}
        )
    hire_payment_buildings_by_action_id = _hire_payment_question_buildings_by_action_id(
        actions,
        player_id=player_id,
        state=state,
        config=config,
        offer_hire_by_action_id=offer_hire_by_action_id,
        include_preview_effects=include_preview_effects,
    )
    for action in actions:
        move_id = action_id(action)
        steps = decision_steps(
            action,
            player_id,
            state=state,
            config=config,
            offer_hire=offer_hire_by_action_id[move_id],
            offer_bank_payment=offer_bank_payment_by_action_id[move_id],
            hire_payment_buildings=hire_payment_buildings_by_action_id[move_id],
            preview_effects=preview_effects_by_action_id[move_id],
            include_preview_effects=include_preview_effects,
        )
        steps_by_action_id[move_id] = steps
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
                offer_bank_payment=offer_bank_payment_by_action_id[move_id],
                hire_payment_buildings=hire_payment_buildings_by_action_id[move_id],
                include_preview_effects=include_preview_effects,
            )
            if len(members) > 1
            else []
        )
        settled = not unresolved
        steps = [dict(step) for step in steps_by_action_id[move_id]]
        member_steps = [steps_by_action_id[action_id(member)] for member in members]
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
        route_buildings = [
            _ROUTE_FAMILY_BY_BUILDING_ID[building_id].i
            for building_id in _route_building_ids(members[0])
        ]
        candidates.append(
            {
                "steps": steps,
                # The page uses this server-known action property only to decide which optional
                # route families a toggle reveals. Individual edge dependencies stay on their
                # exact edge below, so an arrow never needs to infer a cost from its endpoints.
                **({"family": route_buildings} if route_buildings else {}),
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
                **(
                    {"unresolved_text": [_unresolved_field_text(name) for name in unresolved]}
                    if unresolved
                    else {}
                ),
                "variants": len(members),
            }
        )
    _align_implicit_taxation_step_two_prompts(candidates)
    if state.phase is TurnPhase.SOW and not state.turn_progress.resolution_committed:
        for candidate in candidates:
            for index, step in enumerate(candidate["steps"]):
                # The page has to move the phase marker while it narrows candidates locally.  Give
                # it the engine-side answer at each cursor position instead of teaching it that a
                # first answer means an acolyte was picked up.
                step["turn_phase"] = "beginning" if index == 0 else "sow"
            # Once every decision in a full turn is named, its resolution is still only previewed.
            # Confirm is the engine boundary that replaces this page with the End of Turn window.
            candidate["settled_turn_phase"] = "sow"
    auto_family_indexes = _mark_unambiguous_edge_steps(candidates)
    return candidates, auto_family_indexes


def turn_candidates(
    state: Any,
    config: Any,
    *,
    actions: tuple[Any, ...] | list[Any] | None = None,
    include_preview_effects: bool = True,
) -> list[dict]:
    """Return the candidate list without exposing the payload-only automatic-mask metadata."""
    candidates, _auto_family_indexes = _turn_candidates_and_auto_family_indexes(
        state,
        config,
        actions=actions,
        include_preview_effects=include_preview_effects,
    )
    return candidates


def route_family_payload(
    state: Any,
    config: Any,
    *,
    actions: tuple[Any, ...] | list[Any] | None = None,
    include_preview_effects: bool = True,
) -> dict[str, Any]:
    """Assemble the server-written route-family data a play page consumes together.

    Candidates decide which route building families are offered.  The matching ability state and
    automatic-mask indexes must come from that same candidate set, so callers cannot safely build
    any one of these fields in isolation.
    """
    available_actions = tuple(legal_actions(state, config) if actions is None else actions)
    candidates, auto_family_indexes = _turn_candidates_and_auto_family_indexes(
        state,
        config,
        actions=available_actions,
        include_preview_effects=include_preview_effects,
    )
    route_family_building_ids = _route_family_building_ids(auto_family_indexes)
    return {
        "turn_candidates": candidates,
        "families": _ROUTE_BUILDING_PRESENTATION,
        "auto_family_indexes": auto_family_indexes,
        "building_abilities": building_abilities_payload(
            state,
            config,
            route_family_building_ids=route_family_building_ids,
            actions=available_actions,
        ),
        "building_ability_windows": building_ability_windows_payload(
            state,
            config,
            route_family_building_ids=route_family_building_ids,
            actions=available_actions,
        ),
    }


_TURN_PHASE_ROWS = (
    ("beginning", "Beginning of Turn"),
    ("sow", "Sow"),
    ("end", "End of Turn"),
)
_ROUND_END_EVENT_ROWS = (
    (EventType.EXCESS_RESOURCE_CAP, "excess", "Excess resources returned"),
    (EventType.SHIP_ADVANCE, "round_marker", "Round marker advanced"),
    (EventType.ALMS_SEASON_END, "season_end", "Season end"),
    (EventType.MERCHANT_ADVANCE, "merchant", "Merchant advanced"),
    (EventType.TRADE_ROUTE_INCOME, "trade_route_income", "Trade route income paid"),
    (EventType.CONFESSION_BOX_PHASE, "confession", "Confession"),
)


def _turn_window_prompt(
    *,
    resolution_committed: bool,
    available_turn_steps: list[dict[str, Any]],
) -> str:
    """Write the short, window-level instruction from enumerated building steps.

    The client may not turn step metadata into claims about what buildings are usable.  These are
    deliberately counts rather than names: on a late board a complete list would bury the useful
    fact that a hire or free activation exists.
    """
    hire_count = sum(step.get("hire_payment") is not None for step in available_turn_steps)
    free_activation_count = sum(
        step.get("hire_payment") is None for step in available_turn_steps
    )
    can_hire = hire_count > 0
    can_activate_for_free = free_activation_count > 0

    def availability_sentence(count: int, singular: str, plural: str) -> str:
        return singular if count == 1 else plural

    hire_sentence = availability_sentence(
        hire_count,
        "A building can be hired here.",
        "Buildings can be hired here.",
    )
    activation_sentence = availability_sentence(
        free_activation_count,
        "A building can be used here, free.",
        "Buildings can be used here, free.",
    )
    both_sentence = "Buildings can be used here — some free, some hired."
    if not resolution_committed:
        sentences = ["Pick up acolytes for sowing."]
        if can_hire and can_activate_for_free:
            sentences.append(both_sentence)
        elif can_hire:
            sentences.append(hire_sentence)
        elif can_activate_for_free:
            sentences.append(activation_sentence)
        return " ".join(sentences)

    if can_hire and can_activate_for_free:
        return both_sentence
    if can_hire:
        return hire_sentence
    if can_activate_for_free:
        return activation_sentence
    return ""


def phase_column_payload(
    state: Any,
    log_blocks: list[dict[str, Any]],
    available_turn_steps: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Describe the phase column the page must draw for this outstanding decision.

    The engine state says whether the table is in a turn, a round-end question, or neither. The
    round-end history is read from the marked log block's structured event types, so a later
    Confession answer cannot erase the work completed before the first Confession question.
    """
    phase = state.phase
    if state.game_over or phase is TurnPhase.SETUP_SOW:
        return {
            "scope": "inactive",
            "rows": [
                {"key": key, "label": label, "current": False} for key, label in _TURN_PHASE_ROWS
            ],
        }
    if phase is TurnPhase.SOW:
        current = "end" if state.turn_progress.resolution_committed else "beginning"
        window_prompt = _turn_window_prompt(
            resolution_committed=state.turn_progress.resolution_committed,
            available_turn_steps=available_turn_steps or [],
        )
        return {
            "scope": "turn",
            "rows": [
                {"key": key, "label": label, "current": key == current}
                for key, label in _TURN_PHASE_ROWS
            ],
            "prompts": {current: window_prompt} if window_prompt else {},
        }
    if phase not in {TurnPhase.START_PLAYER_CONFESSION, TurnPhase.START_PLAYER_SELECTION}:
        return {
            "scope": "inactive",
            "rows": [
                {"key": key, "label": label, "current": False} for key, label in _TURN_PHASE_ROWS
            ],
        }

    round_end_event_types = set()
    for block in reversed(log_blocks):
        if block.get("round_end"):
            round_end_event_types = {str(event_type) for event_type in block.get("event_types", ())}
            break
    current = "confession" if phase is TurnPhase.START_PLAYER_CONFESSION else "choose_first_player"
    rows = [
        {"key": key, "label": label, "current": key == current}
        for event_type, key, label in _ROUND_END_EVENT_ROWS
        if event_type.value in round_end_event_types
    ]
    if phase is TurnPhase.START_PLAYER_SELECTION:
        rows.append(
            {
                "key": "choose_first_player",
                "label": "Choose first player",
                "current": True,
            }
        )
    return {"scope": "round_end", "rows": rows}


class PlayServer(ThreadingHTTPServer):
    """Holds the one loaded position every route answers from, and the log of how it got there."""

    daemon_threads = True

    def __init__(self, address: tuple[str, int], scenario_path: Path | None = None) -> None:
        super().__init__(address, PlayHandler)
        self._setup_door_enabled = scenario_path is None
        self._session_workspace = tempfile.TemporaryDirectory(prefix="play-server-session-")
        self._workspace_path = Path(self._session_workspace.name)
        self._latest_generated_scenario: dict[str, Any] | None = None
        self._setup_metadata: dict[str, Any] | None = None
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
            if not self.session.seat_roles or len(self.session.seat_roles) != player_count:
                self.session.seat_roles = _default_seat_roles(player_count)
        if intro_line:
            self.log_lines = [intro_line]
            self.log_blocks = [{"lines": [intro_line], "round_end": False, "event_types": []}]
        else:
            self.log_lines = []
            self.log_blocks = []
        self.session.game_loaded = True
        self._refresh()
        self._capture_turn_start()

    def _load_scenario_file(self, scenario_path: Path, *, intro_line: str | None = None) -> None:
        scenario_path = Path(scenario_path)
        try:
            raw = json.loads(scenario_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = None
        self._setup_metadata = (
            raw.get("setup_metadata")
            if isinstance(raw, dict) and isinstance(raw.get("setup_metadata"), dict)
            else None
        )
        self._load_loaded_scenario(load_scenario(str(scenario_path)), intro_line=intro_line)

    def _clear_game(self) -> None:
        self.state = None
        self.config = None
        self._setup_metadata = None
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
        self._setup_metadata = None
        try:
            raw = json.loads(position.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = None
        if isinstance(raw, dict) and isinstance(raw.get("setup_metadata"), dict):
            self._setup_metadata = raw["setup_metadata"]
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
            dict(
                block,
                lines=list(block["lines"]),
                event_types=list(block.get("event_types", ())),
            )
            for block in self.log_blocks
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
        available_turn_steps = turn_steps_payload(self.state, self.config)
        route_payload = route_family_payload(self.state, self.config)
        self.payload = dict(
            self.state_payload,
            state_token=self.token,
            **route_payload,
            turn_steps=available_turn_steps,
            log=list(self.log_lines),
            log_blocks=[
                dict(
                    block,
                    lines=list(block["lines"]),
                    event_types=list(block.get("event_types", ())),
                )
                for block in self.log_blocks
            ],
            phase_column=phase_column_payload(
                self.state, self.log_blocks, available_turn_steps=available_turn_steps
            ),
        )
        if self._setup_metadata is not None:
            self.payload["setup_metadata"] = self._setup_metadata

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
        turn_before = self.state.turn
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
                if not (has_taxation_event and event.event_type is EventType.RESOURCE_DELTA)
            )
            if line is not None
        ]
        player_lines = [summary_line] + [
            line for line in event_lines if line.strip() and line != summary_line
        ]
        if player_lines:
            round_end = any(
                event.event_type
                in {EventType.ROUND_END, EventType.ROUND_ADVANCE, EventType.SHIP_ADVANCE}
                for event in result.events
            )
            self.log_lines.extend(player_lines)
            self.log_blocks.append(
                {
                    "lines": player_lines,
                    "round_end": round_end,
                    "event_types": [event.event_type.value for event in result.events],
                }
            )
        self._refresh()
        if self.state.turn != turn_before:
            self._capture_turn_start()

    def apply_turn_step(self, submitted_id: str, submitted_token: str) -> None:
        """Apply one currently legal committed building step, named by its stable step id."""
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
                    if turn_step_id(step) == submitted_id
                ),
                None,
            )
            if chosen is None:
                raise UnknownTurnStep(
                    f"no legal turn step with id {submitted_id!r} in this position"
                )
            self.state = apply_engine_turn_step(self.state, self.config, chosen)
            event_lines = [
                line
                for line in (
                    format_event_for_players(event, self.config)
                    for event in self.state.events
                    if event.action_id == submitted_id
                )
                if line is not None
            ]
            if event_lines:
                self.log_lines.extend(event_lines)
                self.log_blocks.append(
                    {
                        "lines": event_lines,
                        "round_end": False,
                        "event_types": [
                            event.event_type.value
                            for event in self.state.events
                            if event.action_id == submitted_id
                        ],
                    }
                )
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
                dict(
                    block,
                    lines=list(block["lines"]),
                    event_types=list(block.get("event_types", ())),
                )
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
        try:
            socketserver.TCPServer.server_bind(self)
        except OSError as exc:
            exc.add_note(f"PlayServer could not bind {self.server_address!r}.")
            raise
        self.server_name, self.server_port = self.server_address[:2]

    def server_close(self) -> None:
        try:
            super().server_close()
        finally:
            session_workspace = getattr(self, "_session_workspace", None)
            if session_workspace is not None:
                session_workspace.cleanup()


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
                        for key, values in parse_qs(
                            raw.decode("utf-8"), keep_blank_values=True
                        ).items()
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
