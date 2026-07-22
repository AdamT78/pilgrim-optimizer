"""Action models and stable IDs."""

from __future__ import annotations

from dataclasses import dataclass, field

from pilgrim.model.config import GameConfig
from pilgrim.model.enums import ActionType, position_name


@dataclass(frozen=True, slots=True)
class SowingAction:
    """Pick up all acolytes at source and sow over an exact route."""

    source: int
    route: tuple[int, ...]
    action_type: ActionType = field(default=ActionType.SOW, init=False)


@dataclass(frozen=True, slots=True)
class ResolveDutyAction:
    """Resolve a duty at the selected duty position."""

    duty_position: int
    action_type: ActionType = field(default=ActionType.RESOLVE_DUTY, init=False)


@dataclass(frozen=True, slots=True)
class TitheAction:
    """Placeholder tithe action that intentionally skips recall."""

    duty_position: int
    action_type: ActionType = field(default=ActionType.TITHE, init=False)


GameAction = SowingAction | ResolveDutyAction | TitheAction


def action_id(action: GameAction) -> str:
    """Generate a stable readable action ID."""
    if isinstance(action, SowingAction):
        route = "->".join(str(position) for position in action.route)
        return f"sow:{action.source}:{route}"
    if isinstance(action, ResolveDutyAction):
        return f"resolve-duty:{action.duty_position}"
    return f"tithe:{action.duty_position}"


def readable_route(
    source: int,
    route: tuple[int, ...],
    *,
    positions: tuple[str, ...] | None = None,
) -> str:
    """Format a route as readable position names."""
    path = (source, *route)
    return " -> ".join(position_name(position_id, positions) for position_id in path)


def action_summary(action: GameAction, config: GameConfig) -> str:
    """Return a human-readable action summary for CLI/debug output."""
    positions = config.board.positions
    if isinstance(action, SowingAction):
        return f"Sow: {readable_route(action.source, action.route, positions=positions)}"

    selected_duty = position_name(action.duty_position, positions)
    if isinstance(action, ResolveDutyAction):
        duty = config.duty_for_position(action.duty_position)
        if duty is None:
            return f"Resolve Duty: selected duty: {selected_duty}"
        return (
            f"Resolve Duty: selected duty: {selected_duty} | "
            f"action: {duty.effect.value}"
        )

    return f"Tithe: selected duty: {selected_duty}"
