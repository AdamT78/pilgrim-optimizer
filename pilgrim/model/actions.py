"""Action models and stable IDs."""

from __future__ import annotations

from dataclasses import dataclass, field

from pilgrim.model.enums import ActionType


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
