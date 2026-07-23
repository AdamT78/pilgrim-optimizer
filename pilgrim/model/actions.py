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
    if action.resolution is TurnResolutionType.GIVE_ALMS:
        payment_suffix = (
            f":pay_silver:{action.alms_payment_silver}:pay_wheat:{action.alms_payment_wheat}"
        )
        if action.alms_house_extra_silver or action.alms_house_extra_wheat:
            payment_suffix += (
                f":alms_house_extra_silver:{action.alms_house_extra_silver}"
                f":alms_house_extra_wheat:{action.alms_house_extra_wheat}"
            )
    donation_suffix = ""
    if action.resolution is TurnResolutionType.DONATE_BUILDING:
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
    if action.resolution is TurnResolutionType.CONSTRUCT_DEFERRED:
        plan = action.construct_plan or "none"
        construct_suffix = ":construct_plan:" + plan.replace(" + ", "+").replace(" ", "_")
    return (
        f"turn:sow:{action.origin}:{route}:"
        f"duty:{action.selected_duty}:action:{action.resolution.value}"
        f"{payment_suffix}{donation_suffix}{ordination_suffix}"
        f"{taxation_suffix}{allocation_suffix}{construct_suffix}"
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
    summary = (
        f"Turn: sow {readable_route(action.origin, action.route, positions=positions)} | "
        f"selected duty: {selected_duty} ({duty_category}) | action: {action.resolution.value}"
    )
    if action.resolution is TurnResolutionType.GIVE_ALMS:
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
    if action.resolution is TurnResolutionType.DONATE_BUILDING:
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
    if action.resolution is TurnResolutionType.CONSTRUCT_DEFERRED:
        summary += f" | plan: {action.construct_plan or 'none'}"
    return summary


def resolution_from_effect(effect: DutyEffect) -> TurnResolutionType:
    """Map configured duty effect to the corresponding full-turn resolution."""
    if effect is DutyEffect.PRODUCE:
        # Legacy duty effect mapping defaults to the explicit wheat option.
        return TurnResolutionType.PRODUCE_WHEAT
    return TurnResolutionType(effect.value)
