"""Structured game event records for replay/logging."""

from __future__ import annotations

from dataclasses import dataclass

from pilgrim.model.enums import EventType, PlayerId

type EventValue = str | int | bool
type EventDetails = tuple[tuple[str, EventValue], ...]


@dataclass(frozen=True, slots=True)
class GameEvent:
    """Deterministic transition event entry."""

    event_type: EventType
    actor: PlayerId
    action_id: str
    details: EventDetails = ()


def make_event_details(**kwargs: EventValue) -> EventDetails:
    """Convert keyword detail fields into stable sorted tuples."""
    return tuple(sorted(kwargs.items(), key=lambda pair: pair[0]))
