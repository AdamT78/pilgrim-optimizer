"""Action models and stable IDs."""

from __future__ import annotations

from dataclasses import dataclass, field

from pilgrim.model.config import GameConfig
from pilgrim.model.duties import duty_category_at_position
from pilgrim.model.enums import ActionType, DutyEffect, TurnResolutionType, position_name
from pilgrim.model.special_activities import SPECIAL_ACTIVITY_IDS

_ALLOCATION_SOURCE_PREFIX = "abbey"


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
    building_conversion_id: str | None = None
    building_conversion_source: str | None = None
    building_conversion_direction: str | None = None
    building_conversion_amount: int | None = None
    merchant_advance_building_id: str | None = None
    merchant_advance_building_source: str | None = None
    hired_building_id: str | None = None
    hired_building_source: str | None = None
    action_type: ActionType = field(default=ActionType.FULL_TURN, init=False)


@dataclass(frozen=True, slots=True)
class SetupSowAction:
    """One pre-game setup sow from city only."""

    origin: int
    route: tuple[int, ...]
    action_type: ActionType = field(default=ActionType.SETUP_SOW, init=False)


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
        if self.source == _ALLOCATION_SOURCE_PREFIX and self.destination == _ALLOCATION_SOURCE_PREFIX:
            raise ValueError("Allocation move abbey -> abbey is not legal.")


GameAction = FullTurnAction | SetupSowAction


def action_id(action: GameAction) -> str:
    """Generate a stable readable action ID."""
    if isinstance(action, SetupSowAction):
        route = "->".join(str(position) for position in action.route)
        return f"setup_sow:sow:{action.origin}:{route}"

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
            ",".join(action.taxation_step2_resources)
            if action.taxation_step2_resources
            else "none"
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
    conversion_suffix = ""
    if (
        action.building_conversion_id is not None
        or action.building_conversion_source is not None
        or action.building_conversion_direction is not None
        or action.building_conversion_amount is not None
    ):
        conversion_suffix = (
            f":building_conversion:{action.building_conversion_id or 'none'}"
            f":from:{action.building_conversion_source or 'unknown'}"
            f":direction:{action.building_conversion_direction or 'unknown'}"
            f":amount:{action.building_conversion_amount if action.building_conversion_amount is not None else 'none'}"
        )
    merchant_advance_suffix = ""
    if (
        action.merchant_advance_building_id is not None
        or action.merchant_advance_building_source is not None
    ):
        merchant_advance_suffix = (
            f":merchant_advance_building:{action.merchant_advance_building_id or 'none'}"
            f":from:{action.merchant_advance_building_source or 'unknown'}"
        )
    hire_suffix = ""
    if action.hired_building_id is not None or action.hired_building_source is not None:
        hire_suffix = (
            f":hire_building:{action.hired_building_id or 'none'}"
            f":from:{action.hired_building_source or 'unknown'}"
        )
    return (
        f"turn:sow:{action.origin}:{route}:"
        f"duty:{action.selected_duty}:action:{action.resolution.value}"
        f"{payment_suffix}{donation_suffix}{ordination_suffix}"
        f"{taxation_suffix}{allocation_suffix}{construct_suffix}{start_turn_suffix}"
        f"{end_turn_suffix}"
        f"{sow_route_suffix}{conversion_suffix}{merchant_advance_suffix}{hire_suffix}"
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


def action_summary(action: GameAction, config: GameConfig) -> str:
    """Return a human-readable action summary for CLI/debug output."""
    positions = config.board.positions
    if isinstance(action, SetupSowAction):
        return f"Setup sow: sow {readable_route(action.origin, action.route, positions=positions)}"

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
            f" | skip {position_name(action.sow_route_omitted_location, positions)} "
            "with cloisters"
        )
    if (
        action.building_conversion_id == "grain_store"
        and action.building_conversion_direction is not None
        and action.building_conversion_amount is not None
    ):
        amount = action.building_conversion_amount
        if action.building_conversion_direction == "sell_wheat":
            route_summary += (
                " | use building: grain_store "
                f"to sell {amount} wheat for {amount} silver"
            )
        elif action.building_conversion_direction == "buy_wheat":
            route_summary += (
                " | use building: grain_store "
                f"to buy {amount} wheat for {amount} silver"
            )
    if (
        action.building_conversion_id == "indulgences"
        and action.building_conversion_direction is not None
        and action.building_conversion_amount is not None
    ):
        amount = action.building_conversion_amount
        if action.building_conversion_direction == "sell_piety":
            route_summary += (
                " | use building: indulgences "
                f"to sell {amount} piety for {amount} silver"
            )
        elif action.building_conversion_direction == "buy_piety":
            route_summary += (
                " | use building: indulgences "
                f"to buy {amount} piety for {amount} silver"
            )
    if (
        action.building_conversion_id == "stone_yard"
        and action.building_conversion_direction is not None
        and action.building_conversion_amount is not None
    ):
        amount = action.building_conversion_amount
        if action.building_conversion_direction == "sell_stone":
            route_summary += (
                " | use building: stone_yard "
                f"to sell {amount} stone for {amount} silver"
            )
        elif action.building_conversion_direction == "buy_stone":
            route_summary += (
                " | use building: stone_yard "
                f"to buy {amount} stone for {amount} silver"
            )
    if (
        action.building_conversion_id == "brewery"
        and action.building_conversion_direction is not None
        and action.building_conversion_amount is not None
    ):
        if action.building_conversion_direction == "sell_wheat_for_silver":
            route_summary += " | use building: brewery to sell 1 wheat for 2 silver"
    if action.merchant_advance_building_id == "guild":
        route_summary += " | use building: guild to move merchant +1"
    summary = (
        f"{route_summary} | "
        f"selected duty: {selected_duty} ({duty_category}) | action: {action.resolution.value}"
    )
    if action.resolution is TurnResolutionType.GIVE_ALMS_PAID:
        summary += (
            f" | pay silver={action.alms_payment_silver}, "
            f"wheat={action.alms_payment_wheat}"
        )
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
            summary += (
                " | hire building: kogge "
                f"from {kogge_source}"
            )
        if cloisters_source != "own_active":
            summary += (
                " | hire building: cloisters "
                f"from {cloisters_source}"
            )
    else:
        if kogge_source is not None:
            if kogge_source == "own_active":
                summary += " | use building: kogge"
            else:
                summary += (
                    " | hire building: kogge "
                    f"from {kogge_source}"
                )
        if cloisters_source is not None and cloisters_source != "own_active":
            summary += (
                " | hire building: cloisters "
                f"from {cloisters_source}"
            )
    if action.hired_building_id and action.hired_building_source:
        summary += (
            f" | hire building: {action.hired_building_id} "
            f"from {action.hired_building_source}"
        )
    if (
        action.building_conversion_id
        in ("grain_store", "indulgences", "stone_yard", "brewery")
        and action.building_conversion_source is not None
        and action.building_conversion_source != "own_active"
    ):
        summary += (
            f" | hire building: {action.building_conversion_id} "
            f"from {action.building_conversion_source}"
        )
    if (
        action.merchant_advance_building_id == "guild"
        and action.merchant_advance_building_source is not None
        and action.merchant_advance_building_source != "own_active"
    ):
        summary += (
            " | hire building: guild "
            f"from {action.merchant_advance_building_source}"
        )
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
        to_name = (
            to_value
            if isinstance(to_value, str)
            else position_name(to_value, positions)
        )
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
