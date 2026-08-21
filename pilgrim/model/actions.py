"""Action models and stable IDs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pilgrim.model.config import GameConfig
from pilgrim.model.duties import duty_category_at_position
from pilgrim.model.enums import ActionType, DutyEffect, PlayerId, TurnResolutionType, position_name
from pilgrim.model.special_activities import SPECIAL_ACTIVITY_IDS

if TYPE_CHECKING:
    from pilgrim.model.state import GameState

_ALLOCATION_SOURCE_PREFIX = "abbey"


@dataclass(frozen=True, slots=True)
class StartPlayerConfessionBoxAction:
    """One player's own answer to whether they will spend on the Confession Box.

    The player is not named on it. Whoever is being waited on is `state.active_player`, exactly as
    with a setup sow, so a submission cannot claim to be answering for somebody else -- which is
    the failure the tuple this replaced invited, since it let one player's turn carry every other
    player's decision.

    `source` is where the box is reached from -- `own_active`, `market`, or an opponent's player
    id -- and is set only when using. Declining names no source because there is nothing to name.
    """

    use: bool
    source: str | None = None
    action_type: ActionType = field(default=ActionType.START_PLAYER_CONFESSION, init=False)


@dataclass(frozen=True, slots=True)
class FullTurnAction:
    """
    One complete simplified sandbox turn.

    Flow:
        sow from origin over route -> select duty -> resolve duty effect or tithe
    """

    origin: int
    route: tuple[int, ...]
    selected_duty: int
    resolution: TurnResolutionType
    alms_payment_silver: int = 0
    alms_payment_wheat: int = 0
    alms_house_extra_silver: int = 0
    alms_house_extra_wheat: int = 0
    donate_building_id: str | None = None
    ordination_steps: tuple[str, ...] = ()
    taxation_step1_resource: str | None = None
    taxation_step2_resources: tuple[str, ...] = ()
    allocation_moves: tuple[AllocationMove, ...] = ()
    construct_plan: str | None = None
    construct_building_id: str | None = None
    start_turn_building_id: str | None = None
    start_turn_building_source: str | None = None
    start_turn_relocation_from: int | None = None
    start_turn_relocation_to: int | None = None
    end_turn_building_id: str | None = None
    end_turn_building_source: str | None = None
    end_turn_relocation_from: int | None = None
    end_turn_relocation_to: int | str | None = None
    sow_route_building_id: str | None = None
    sow_route_building_source: str | None = None
    sow_route_secondary_building_id: str | None = None
    sow_route_secondary_building_source: str | None = None
    sow_route_omitted_location: int | None = None
    bank_payment_building_id: str | None = None
    bank_payment_building_source: str | None = None
    bank_payment_replaced_resource: str | None = None
    bank_payment_silver_amount: int | None = None
    effective_acolyte_building_id: str | None = None
    effective_acolyte_building_source: str | None = None
    taxation_majority_building_id: str | None = None
    taxation_majority_building_source: str | None = None
    free_hire_enabler_building_id: str | None = None
    free_hire_target_building_id: str | None = None
    free_hire_target_building_source: str | None = None
    merchant_advance_building_id: str | None = None
    merchant_advance_building_source: str | None = None
    workforce_move_building_id: str | None = None
    workforce_move_building_source: str | None = None
    hired_building_id: str | None = None
    hired_building_source: str | None = None
    # One payment per hired building: (building_id, resource), sorted by building id.
    #
    # The key is the building id because a building is hired at most once in one turn; see
    # transition validation, which rejects an action that names the same hired building twice.
    hire_payments: tuple[tuple[str, str], ...] = ()
    # What a TITHE gains. Set on EVERY tithe, including the tiles carrying a plain counter where
    # only one resource was ever possible, because the point is that apply pays what the action
    # says rather than looking the tile up again. A wildcard read twice is read differently the
    # second time, which is exactly how the Merchant hire choice was lost once already.
    #
    # Not `hire_payments`. That is a payment for a building and this is a gain from a
    # tile; they are two decisions that happen to have the same three answers.
    tithe_resource: str | None = None
    action_type: ActionType = field(default=ActionType.FULL_TURN, init=False)

    def __getattr__(self, name: str):
        # The play-server residue sweep still names the retired fields while this engine-only
        # branch deliberately leaves that server file unchanged. They are not dataclass fields and
        # never carry a value; the compatibility read keeps old residue inspection harmless.
        if name in {
            "building_conversion_id",
            "building_conversion_source",
            "building_conversion_direction",
            "building_conversion_amount",
        }:
            return None
        raise AttributeError(name)


@dataclass(frozen=True, slots=True)
class BuildingConversionStep:
    """One committed use of a building conversion during the active turn.

    ``hire_payment`` records the resource paid for a hired source. It is ``None`` only for an
    own-active source; a Cornucopia choice is resolved before the step is committed.
    """

    building_id: str
    source: str
    direction: str
    amount: int
    hire_payment: str | None = None


TurnStep = BuildingConversionStep


@dataclass(frozen=True, slots=True)
class SetupSowAction:
    """One pre-game setup sow from city only."""

    origin: int
    route: tuple[int, ...]
    action_type: ActionType = field(default=ActionType.SETUP_SOW, init=False)


@dataclass(frozen=True, slots=True)
class StartPlayerSelectionAction:
    """Who begins this round, said by whoever holds the First Player marker.

    One field, because one thing is being decided. The player saying it is not carried here: it is
    the active player, the way it is for every other action, and holding it twice would let a
    submission name a chooser the state does not agree with.

    The marker holder may name themselves. That is not a special case and is not written down as
    one anywhere -- they are simply one of the players who may be chosen.
    """

    chosen_start_player: PlayerId
    action_type: ActionType = field(default=ActionType.START_PLAYER_SELECTION, init=False)


@dataclass(frozen=True, slots=True)
class AllocationMove:
    """One allocation sub-move between Abbey and special-activity slots."""

    source: str
    destination: str

    def __post_init__(self) -> None:
        if self.source == self.destination:
            raise ValueError("Allocation move cannot have same source and destination.")
        if self.source != _ALLOCATION_SOURCE_PREFIX and self.source not in SPECIAL_ACTIVITY_IDS:
            raise ValueError(f"Unknown allocation move source: {self.source}")
        if (
            self.destination != _ALLOCATION_SOURCE_PREFIX
            and self.destination not in SPECIAL_ACTIVITY_IDS
        ):
            raise ValueError(f"Unknown allocation move destination: {self.destination}")
        if (
            self.source == _ALLOCATION_SOURCE_PREFIX
            and self.destination == _ALLOCATION_SOURCE_PREFIX
        ):
            raise ValueError("Allocation move abbey -> abbey is not legal.")


GameAction = (
    FullTurnAction | SetupSowAction | StartPlayerConfessionBoxAction | StartPlayerSelectionAction
)


def action_id(action: GameAction) -> str:
    """Generate a stable readable action ID."""
    if isinstance(action, SetupSowAction):
        route = "->".join(str(position) for position in action.route)
        return f"setup_sow:sow:{action.origin}:{route}"

    if isinstance(action, StartPlayerConfessionBoxAction):
        if not action.use:
            return "start_player_confession:decline"
        return f"start_player_confession:use:{action.source}"

    if isinstance(action, StartPlayerSelectionAction):
        return f"start_player_selection:{action.chosen_start_player.name.lower()}"

    # Full-turn actions only below.
    route = "->".join(str(position) for position in action.route)
    payment_suffix = ""
    if action.resolution is TurnResolutionType.GIVE_ALMS_PAID:
        payment_suffix = (
            f":pay_silver:{action.alms_payment_silver}:pay_wheat:{action.alms_payment_wheat}"
        )
        if action.alms_house_extra_silver or action.alms_house_extra_wheat:
            payment_suffix += (
                f":alms_house_extra_silver:{action.alms_house_extra_silver}"
                f":alms_house_extra_wheat:{action.alms_house_extra_wheat}"
            )
    donation_suffix = ""
    if action.resolution is TurnResolutionType.GIVE_ALMS_DONATE_BUILDING:
        donation_suffix = f":building:{action.donate_building_id or 'none'}"
    ordination_suffix = ""
    if action.resolution is TurnResolutionType.ORDINATION:
        ordination_suffix = ":steps:" + (
            ",".join(action.ordination_steps) if action.ordination_steps else "none"
        )
    taxation_suffix = ""
    if action.resolution is TurnResolutionType.TAXATION:
        step_1 = action.taxation_step1_resource or "none"
        step_2 = (
            ",".join(action.taxation_step2_resources) if action.taxation_step2_resources else "none"
        )
        taxation_suffix = f":take:{step_1}:bonus:{step_2}"
    allocation_suffix = ""
    if action.resolution is TurnResolutionType.ALLOCATION:
        if action.allocation_moves:
            allocation_suffix = ":allocation_moves:" + ",".join(
                f"{move.source}>{move.destination}" for move in action.allocation_moves
            )
        else:
            allocation_suffix = ":allocation_moves:none"
    construct_suffix = ""
    if action.resolution is TurnResolutionType.CONSTRUCT_ROAD_DEFERRED:
        plan = action.construct_plan or "none"
        construct_suffix = ":construct_plan:" + plan.replace(" + ", "+").replace(" ", "_")
    elif action.resolution is TurnResolutionType.CONSTRUCT_BUILDING:
        construct_suffix = f":construct_building:{action.construct_building_id or 'none'}"
    elif action.resolution is TurnResolutionType.CONSTRUCT_BUILDING_AND_ROAD_DEFERRED:
        plan = action.construct_plan or "none"
        construct_suffix = (
            f":construct_building:{action.construct_building_id or 'none'}"
            + ":construct_plan:"
            + plan.replace(" + ", "+").replace(" ", "_")
        )
    start_turn_suffix = ""
    if (
        action.start_turn_building_id is not None
        or action.start_turn_building_source is not None
        or action.start_turn_relocation_from is not None
        or action.start_turn_relocation_to is not None
    ):
        start_turn_suffix = (
            f":start_turn_building:{action.start_turn_building_id or 'none'}"
            f":source:{action.start_turn_building_source or 'unknown'}"
            f":from:{action.start_turn_relocation_from if action.start_turn_relocation_from is not None else 'none'}"
            f":to:{action.start_turn_relocation_to if action.start_turn_relocation_to is not None else 'none'}"
        )
    end_turn_suffix = ""
    if (
        action.end_turn_building_id is not None
        or action.end_turn_building_source is not None
        or action.end_turn_relocation_from is not None
        or action.end_turn_relocation_to is not None
    ):
        end_turn_suffix = (
            f":end_turn_building:{action.end_turn_building_id or 'none'}"
            f":source:{action.end_turn_building_source or 'unknown'}"
            f":from:{action.end_turn_relocation_from if action.end_turn_relocation_from is not None else 'none'}"
            f":to:{action.end_turn_relocation_to if action.end_turn_relocation_to is not None else 'none'}"
        )
    sow_route_suffix = ""
    if (
        action.sow_route_building_id is not None
        or action.sow_route_building_source is not None
        or action.sow_route_secondary_building_id is not None
        or action.sow_route_secondary_building_source is not None
        or action.sow_route_omitted_location is not None
    ):
        sow_route_suffix = (
            f":sow_route_building:{action.sow_route_building_id or 'none'}"
            f":from:{action.sow_route_building_source or 'unknown'}"
        )
        if (
            action.sow_route_secondary_building_id is not None
            or action.sow_route_secondary_building_source is not None
        ):
            sow_route_suffix += (
                f":secondary_building:{action.sow_route_secondary_building_id or 'none'}"
                f":secondary_from:{action.sow_route_secondary_building_source or 'unknown'}"
            )
        if action.sow_route_omitted_location is not None:
            sow_route_suffix += f":skip:{action.sow_route_omitted_location}"
    bank_payment_suffix = ""
    if (
        action.bank_payment_building_id is not None
        or action.bank_payment_building_source is not None
        or action.bank_payment_replaced_resource is not None
        or action.bank_payment_silver_amount is not None
    ):
        bank_payment_suffix = (
            f":bank_payment_building:{action.bank_payment_building_id or 'none'}"
            f":from:{action.bank_payment_building_source or 'unknown'}"
            f":replace:{action.bank_payment_replaced_resource or 'unknown'}"
            f":silver:{action.bank_payment_silver_amount if action.bank_payment_silver_amount is not None else 'none'}"
        )
    merchant_advance_suffix = ""
    if (
        action.effective_acolyte_building_id is not None
        or action.effective_acolyte_building_source is not None
    ):
        effective_acolyte_suffix = (
            f":effective_acolyte_building:{action.effective_acolyte_building_id or 'none'}"
            f":from:{action.effective_acolyte_building_source or 'unknown'}"
        )
    else:
        effective_acolyte_suffix = ""
    if (
        action.taxation_majority_building_id is not None
        or action.taxation_majority_building_source is not None
    ):
        taxation_majority_suffix = (
            f":taxation_majority_building:{action.taxation_majority_building_id or 'none'}"
            f":from:{action.taxation_majority_building_source or 'unknown'}"
        )
    else:
        taxation_majority_suffix = ""
    if (
        action.free_hire_enabler_building_id is not None
        or action.free_hire_target_building_id is not None
        or action.free_hire_target_building_source is not None
    ):
        free_hire_suffix = (
            f":free_hire_enabler:{action.free_hire_enabler_building_id or 'none'}"
            f":target:{action.free_hire_target_building_id or 'none'}"
            f":target_source:{action.free_hire_target_building_source or 'unknown'}"
        )
    else:
        free_hire_suffix = ""
    if (
        action.merchant_advance_building_id is not None
        or action.merchant_advance_building_source is not None
    ):
        merchant_advance_suffix = (
            f":merchant_advance_building:{action.merchant_advance_building_id or 'none'}"
            f":from:{action.merchant_advance_building_source or 'unknown'}"
        )
    workforce_move_suffix = ""
    if (
        action.workforce_move_building_id is not None
        or action.workforce_move_building_source is not None
    ):
        workforce_move_suffix = (
            f":workforce_move_building:{action.workforce_move_building_id or 'none'}"
            f":from:{action.workforce_move_building_source or 'unknown'}"
        )
    hire_suffix = ""
    if action.hired_building_id is not None or action.hired_building_source is not None:
        hire_suffix = (
            f":hire_building:{action.hired_building_id or 'none'}"
            f":from:{action.hired_building_source or 'unknown'}"
        )
    if action.hire_payments:
        payments = ",".join(
            f"{building_id}={resource}" for building_id, resource in action.hire_payments
        )
        hire_suffix += f":hire_payments:{payments}"
    # Every tithe now names what it takes, so every tithe id changes. That is not churn to be
    # minimised: two tithes on the same tile that gain different resources are different moves,
    # and an id that could not tell them apart would be the one thing wrong with it.
    tithe_suffix = ""
    if action.tithe_resource is not None:
        tithe_suffix = f":gain:{action.tithe_resource}"
    return (
        f"turn:sow:{action.origin}:{route}:"
        f"duty:{action.selected_duty}:action:{action.resolution.value}"
        f"{payment_suffix}{donation_suffix}{ordination_suffix}"
        f"{taxation_suffix}{allocation_suffix}{construct_suffix}{start_turn_suffix}"
        f"{end_turn_suffix}"
        f"{sow_route_suffix}{bank_payment_suffix}{effective_acolyte_suffix}"
        f"{taxation_majority_suffix}{free_hire_suffix}"
        f"{merchant_advance_suffix}{workforce_move_suffix}{hire_suffix}"
        f"{tithe_suffix}"
    )


def readable_route(
    origin: int,
    route: tuple[int, ...],
    *,
    positions: tuple[str, ...] | None = None,
) -> str:
    """Format a route as readable position names."""
    path = (origin, *route)
    return " -> ".join(position_name(position_id, positions) for position_id in path)


# KEEP THESE TWO TOGETHER.
# `action_summary` is the CLI/developer voice and `action_summary_for_players` is the in-page
# player voice. They are a pair by design: changing one without checking the other is drift.
def _player_wording(value: str) -> str:
    return value.replace("_", " ").strip().title()


_SMALL_NUMBER_WORDS: tuple[str, ...] = (
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
)


def _spoken_count(value: int) -> str:
    if 0 <= value < len(_SMALL_NUMBER_WORDS):
        return _SMALL_NUMBER_WORDS[value]
    return str(value)


def _actor_name(actor: PlayerId | str | None) -> str:
    if isinstance(actor, PlayerId):
        return actor.name.lower()
    if actor is None:
        return "unknown"
    return str(actor).strip() or "unknown"


def _board_label_for_position(config: GameConfig, position: int) -> str:
    """What a player sees printed on that board slot."""
    if position == 0:
        return "City"
    return _player_wording(duty_category_at_position(config, position))


def _actor_id(actor: PlayerId | str | None) -> PlayerId | None:
    if isinstance(actor, PlayerId):
        return actor
    if isinstance(actor, str):
        try:
            return PlayerId.from_string(actor.strip())
        except ValueError:
            return None
    return None


def _active_buildings_for_actor(
    state: GameState | None, actor: PlayerId | str | None
) -> tuple[str, ...]:
    if state is None:
        return ()
    player_id = _actor_id(actor)
    if player_id is None or not hasattr(state, "player_state"):
        return ()
    try:
        player_state = state.player_state(player_id)  # type: ignore[attr-defined]
    except Exception:
        return ()
    slots = getattr(player_state, "player_board_slots", None)
    if slots is None:
        return ()
    return tuple(getattr(slots, "active_buildings", ()) or ())


def _ordination_cost_phrase(
    action: FullTurnAction, *, state: GameState | None, actor: PlayerId | str | None
) -> str:
    due = len(action.ordination_steps)
    has_mill = "mill" in _active_buildings_for_actor(state, actor) or action.hired_building_id == "mill"
    waived = min(2, due) if has_mill else 0
    after_mill = max(0, due - waived)
    bank_wheat_replaced = (
        action.bank_payment_silver_amount
        if (
            action.bank_payment_building_id == "bank"
            and action.bank_payment_replaced_resource == "wheat"
            and action.bank_payment_silver_amount is not None
        )
        else 0
    )
    paid = max(0, after_mill - bank_wheat_replaced)
    if waived > 0:
        return f"paid {paid} wheat ({due} due, {waived} waived by the Mill)"
    return f"paid {paid} wheat"


def action_choice_summary_for_players(
    action: GameAction,
    config: GameConfig,
    *,
    actor: PlayerId | str | None = None,
) -> str:
    """Return the short player-facing line naming only what was chosen."""
    speaker = _actor_name(actor)

    if isinstance(action, SetupSowAction):
        count = len(action.route)
        noun = "acolyte" if count == 1 else "acolytes"
        origin = _board_label_for_position(config, action.origin)
        ending = _board_label_for_position(config, action.route[-1] if action.route else action.origin)
        origin_phrase = f"the {origin}" if origin == "City" else origin
        return (
            f"{speaker} sowed {_spoken_count(count)} {noun} "
            f"from {origin_phrase}, ending at {ending}."
        )

    if isinstance(action, StartPlayerConfessionBoxAction):
        if not action.use:
            return f"{speaker} declined the Confession Box."
        if action.source == "own_active":
            return f"{speaker} used the Confession Box."
        if action.source == "market":
            return f"{speaker} hired the Confession Box from market."
        return f"{speaker} hired the Confession Box from {action.source}."

    if isinstance(action, StartPlayerSelectionAction):
        chosen = action.chosen_start_player.name.lower()
        return f"{speaker} chose {chosen} to begin this round."

    duty = _player_wording(duty_category_at_position(config, action.selected_duty))
    if action.resolution is TurnResolutionType.TITHE:
        gained = action.tithe_resource or "a resource"
        return f"{speaker} took the tithe at {duty} and gained {gained}."

    action_name = _player_wording(action.resolution.value)
    if action.resolution is TurnResolutionType.PRODUCE_WHEAT:
        return f"{speaker} chose {action_name} at {duty} and gained wheat."
    if action.resolution is TurnResolutionType.PRODUCE_STONE:
        return f"{speaker} chose {action_name} at {duty} and gained stone."
    return f"{speaker} chose {action_name} at {duty}."


def action_summary_for_players(
    action: GameAction,
    config: GameConfig,
    *,
    actor: PlayerId | str | None = None,
    state: GameState | None = None,
) -> str:
    """Return the full player-facing sentence shown before confirming an action."""
    summary = action_choice_summary_for_players(action, config, actor=actor)
    if not isinstance(action, FullTurnAction):
        return summary
    if action.resolution is not TurnResolutionType.ORDINATION:
        return summary

    ordain_count = action.ordination_steps.count("ordain")
    mission_count = action.ordination_steps.count("mission")
    step_clauses: list[str] = []
    if ordain_count > 0:
        noun = "serf" if ordain_count == 1 else "serfs"
        step_clauses.append(f"ordained {ordain_count} {noun} into the Abbey")
    if mission_count > 0:
        noun = "acolyte" if mission_count == 1 else "acolytes"
        step_clauses.append(f"sent {mission_count} {noun} on mission to the City")
    if not step_clauses:
        step_clauses.append("made no ordination steps")
    step_clauses.append(_ordination_cost_phrase(action, state=state, actor=actor))
    return f"{summary[:-1]} \u2014 {'; '.join(step_clauses)}."


def action_summary(action: GameAction, config: GameConfig) -> str:
    """Return a human-readable action summary for CLI/debug output."""
    if isinstance(action, BuildingConversionStep):
        if action.direction == "sell_wheat_for_silver":
            conversion = f"sell {action.amount} wheat for {action.amount * 2} silver"
        elif action.direction.startswith("buy_"):
            resource = action.direction.removeprefix("buy_")
            conversion = f"buy {action.amount} {resource} for {action.amount} silver"
        elif action.direction.startswith("sell_"):
            resource = action.direction.removeprefix("sell_")
            conversion = f"sell {action.amount} {resource} for {action.amount} silver"
        else:
            conversion = f"{action.direction} {action.amount}"
        summary = f"use building: {action.building_id} to {conversion}"
        if action.source != "own_active":
            summary += f" | hire building: {action.building_id} from {action.source}"
        return summary

    positions = config.board.positions
    if isinstance(action, SetupSowAction):
        return f"Setup sow: sow {readable_route(action.origin, action.route, positions=positions)}"

    if isinstance(action, StartPlayerConfessionBoxAction):
        if not action.use:
            return "Confession Box: decline"
        if action.source == "own_active":
            return "Confession Box: use own active Confession Box"
        if action.source == "market":
            return "Confession Box: hire from market"
        return f"Confession Box: hire from {action.source}"

    if isinstance(action, StartPlayerSelectionAction):
        return (
            "Start player selection: "
            f"{action.chosen_start_player.name.lower()} begins this round"
        )

    # Full-turn actions only below.
    selected_duty = position_name(action.selected_duty, positions)
    duty_category = duty_category_at_position(config, action.selected_duty)

    def _source_for_route_building(building_id: str) -> str | None:
        if action.sow_route_building_id == building_id:
            return action.sow_route_building_source
        if action.sow_route_secondary_building_id == building_id:
            return action.sow_route_secondary_building_source
        return None

    kogge_source = _source_for_route_building("kogge")
    cloisters_source = _source_for_route_building("cloisters")
    has_combined_kogge_cloisters = (
        kogge_source is not None
        and cloisters_source is not None
        and action.sow_route_omitted_location is not None
    )

    route_summary = f"Turn: sow {readable_route(action.origin, action.route, positions=positions)}"
    if has_combined_kogge_cloisters:
        route_summary += " | use building: kogge"
        route_summary += (
            " | use building: cloisters to skip "
            f"{position_name(action.sow_route_omitted_location, positions)}"
        )
    elif cloisters_source is not None and action.sow_route_omitted_location is not None:
        route_summary += (
            f" | skip {position_name(action.sow_route_omitted_location, positions)} with cloisters"
        )
    if (
        action.free_hire_enabler_building_id == "wagon_yard"
        and action.free_hire_target_building_id is not None
        and action.free_hire_target_building_source is not None
    ):
        route_summary += (
            " | use building: wagon_yard to hire "
            f"{action.free_hire_target_building_id} "
            f"from {action.free_hire_target_building_source} for free"
        )
    if action.effective_acolyte_building_id == "scriptorium":
        route_summary += (
            " | use building: scriptorium for +1 effective acolyte on occupied Duty tiles"
        )
    if action.taxation_majority_building_id == "customs_house":
        route_summary += (
            " | use building: customs_house for Taxation majority on occupied Duty tiles"
        )
    if action.merchant_advance_building_id == "guild":
        route_summary += " | use building: guild to move merchant +1"
    if action.workforce_move_building_id == "pulpit":
        route_summary += " | use building: pulpit to move 1 serf village -> abbey for free"
    if (
        action.bank_payment_building_id == "bank"
        and action.bank_payment_replaced_resource is not None
        and action.bank_payment_silver_amount is not None
    ):
        amount = action.bank_payment_silver_amount
        replaced_resource = action.bank_payment_replaced_resource
        route_summary += (
            " | use building: bank "
            f"to replace {amount} {replaced_resource} with {amount} silver for this transaction"
        )
    summary = (
        f"{route_summary} | "
        f"selected duty: {selected_duty} ({duty_category}) | action: {action.resolution.value}"
    )
    # A tithe reads as a bare "action: tithe" otherwise, which is the one thing about it a player
    # needs told: on a cornucopia three of them differ in nothing else.
    if action.resolution is TurnResolutionType.TITHE and action.tithe_resource is not None:
        summary += f" | gain {action.tithe_resource}"
    if action.resolution is TurnResolutionType.GIVE_ALMS_PAID:
        summary += f" | pay silver={action.alms_payment_silver}, wheat={action.alms_payment_wheat}"
        if action.alms_house_extra_silver or action.alms_house_extra_wheat:
            summary += (
                " | alms_house extra "
                f"silver={action.alms_house_extra_silver}, "
                f"wheat={action.alms_house_extra_wheat}"
            )
    if action.resolution is TurnResolutionType.GIVE_ALMS_DONATE_BUILDING:
        summary += f" | building: {action.donate_building_id or 'unknown'}"
    if action.resolution is TurnResolutionType.ORDINATION:
        summary += " | steps: " + (
            "; ".join(action.ordination_steps) if action.ordination_steps else "none"
        )
    if action.resolution is TurnResolutionType.TAXATION:
        summary += f" | take: {action.taxation_step1_resource or 'unknown'}"
        if action.taxation_step2_resources:
            summary += "; bonus: " + ", ".join(action.taxation_step2_resources)
    if action.resolution is TurnResolutionType.ALLOCATION:
        if action.allocation_moves:
            summary += " | moves: " + "; ".join(
                f"{move.source} -> {move.destination}" for move in action.allocation_moves
            )
        else:
            summary += " | moves: none"
    if action.resolution is TurnResolutionType.CONSTRUCT_ROAD_DEFERRED:
        summary += f" | plan: {action.construct_plan or 'none'}"
    if action.resolution is TurnResolutionType.CONSTRUCT_BUILDING:
        summary += f" | building: {action.construct_building_id or 'unknown'}"
    if action.resolution is TurnResolutionType.CONSTRUCT_BUILDING_AND_ROAD_DEFERRED:
        summary += f" | building: {action.construct_building_id or 'unknown'}"
        summary += f" | deferred plan: {action.construct_plan or 'none'}"
    if has_combined_kogge_cloisters:
        if kogge_source != "own_active":
            summary += f" | hire building: kogge from {kogge_source}"
        if cloisters_source != "own_active":
            summary += f" | hire building: cloisters from {cloisters_source}"
    else:
        if kogge_source is not None:
            if kogge_source == "own_active":
                summary += " | use building: kogge"
            else:
                summary += f" | hire building: kogge from {kogge_source}"
        if cloisters_source is not None and cloisters_source != "own_active":
            summary += f" | hire building: cloisters from {cloisters_source}"
    if action.hired_building_id and action.hired_building_source:
        summary += (
            f" | hire building: {action.hired_building_id} from {action.hired_building_source}"
        )
    if (
        action.effective_acolyte_building_id == "scriptorium"
        and action.effective_acolyte_building_source is not None
        and action.effective_acolyte_building_source != "own_active"
    ):
        summary += f" | hire building: scriptorium from {action.effective_acolyte_building_source}"
    if (
        action.taxation_majority_building_id == "customs_house"
        and action.taxation_majority_building_source is not None
        and action.taxation_majority_building_source != "own_active"
    ):
        summary += (
            f" | hire building: customs_house from {action.taxation_majority_building_source}"
        )
    if (
        action.merchant_advance_building_id == "guild"
        and action.merchant_advance_building_source is not None
        and action.merchant_advance_building_source != "own_active"
    ):
        summary += f" | hire building: guild from {action.merchant_advance_building_source}"
    if (
        action.workforce_move_building_id == "pulpit"
        and action.workforce_move_building_source is not None
        and action.workforce_move_building_source != "own_active"
    ):
        summary += f" | hire building: pulpit from {action.workforce_move_building_source}"
    if (
        action.bank_payment_building_id == "bank"
        and action.bank_payment_building_source is not None
        and action.bank_payment_building_source != "own_active"
    ):
        summary += f" | hire building: bank from {action.bank_payment_building_source}"
    if action.hired_building_id == "mill":
        required_wheat = 0
        if action.resolution is TurnResolutionType.GIVE_ALMS_PAID:
            required_wheat = action.alms_payment_wheat + action.alms_house_extra_wheat
        elif action.resolution is TurnResolutionType.ORDINATION:
            required_wheat = len(action.ordination_steps)
        summary += f" | mill wheat spent={max(0, required_wheat - 2)}"
    if (
        action.start_turn_building_id is not None
        and action.start_turn_relocation_from is not None
        and action.start_turn_relocation_to is not None
        and action.start_turn_building_source is not None
    ):
        start_summary = (
            f"start: {action.start_turn_building_id} "
            f"{position_name(action.start_turn_relocation_from, positions)} -> "
            f"{position_name(action.start_turn_relocation_to, positions)}"
        )
        if action.start_turn_building_source != "own_active":
            start_summary += (
                f" | hire building: {action.start_turn_building_id} "
                f"from {action.start_turn_building_source}"
            )
        summary = f"{start_summary} | {summary}"
    if (
        action.end_turn_building_id is not None
        and action.end_turn_relocation_from is not None
        and action.end_turn_relocation_to is not None
        and action.end_turn_building_source is not None
    ):
        from_name = position_name(action.end_turn_relocation_from, positions)
        to_value = action.end_turn_relocation_to
        to_name = to_value if isinstance(to_value, str) else position_name(to_value, positions)
        summary += f" | end: {action.end_turn_building_id} {from_name} -> {to_name}"
        if action.end_turn_building_source != "own_active":
            summary += (
                f" | hire building: {action.end_turn_building_id} "
                f"from {action.end_turn_building_source}"
            )
    return summary


def resolution_from_effect(effect: DutyEffect) -> TurnResolutionType:
    """Map configured duty effect to the corresponding full-turn resolution."""
    if effect is DutyEffect.PRODUCE:
        # Legacy duty effect mapping defaults to the explicit wheat option.
        return TurnResolutionType.PRODUCE_WHEAT
    return TurnResolutionType(effect.value)
