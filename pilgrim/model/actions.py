"""Action models and stable IDs."""

from __future__ import annotations

from dataclasses import dataclass, field

from pilgrim.model.config import GameConfig
from pilgrim.model.duties import duty_category_at_position
from pilgrim.model.enums import ActionType, DutyEffect, TurnResolutionType, position_name


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
    allocation_target: str | None = None
    action_type: ActionType = field(default=ActionType.FULL_TURN, init=False)


GameAction = FullTurnAction


def action_id(action: GameAction) -> str:
    """Generate a stable readable action ID."""
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
    allocation_suffix = ""
    if action.resolution is TurnResolutionType.ALLOCATION:
        allocation_target = action.allocation_target or "unknown"
        allocation_suffix = f":allocation_target:{allocation_target}"
    return (
        f"turn:sow:{action.origin}:{route}:"
        f"duty:{action.selected_duty}:action:{action.resolution.value}"
        f"{payment_suffix}{allocation_suffix}"
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
    if action.resolution is TurnResolutionType.ALLOCATION:
        allocation_target = action.allocation_target or "unknown"
        summary += f" | target: {allocation_target}"
    return summary


def resolution_from_effect(effect: DutyEffect) -> TurnResolutionType:
    """Map configured duty effect to the corresponding full-turn resolution."""
    if effect is DutyEffect.PRODUCE:
        # Legacy duty effect mapping defaults to the explicit wheat option.
        return TurnResolutionType.PRODUCE_WHEAT
    return TurnResolutionType(effect.value)
