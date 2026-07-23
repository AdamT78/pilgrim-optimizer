"""Round-end phase helpers for excess, trade-route placeholders, and start player."""

from __future__ import annotations

from dataclasses import replace

from pilgrim.model.enums import EventType, PlayerId
from pilgrim.model.events import GameEvent, make_event_details
from pilgrim.model.resources import Resources
from pilgrim.model.state import GameState

EXCESS_RESOURCE_CAP = 6
START_PLAYER_POLICY = "highest_piety_selects_self"


def apply_excess_resource_caps(
    state: GameState,
    *,
    actor: PlayerId,
    action_id: str,
) -> tuple[GameState, tuple[GameEvent, ...]]:
    """Cap stone and wheat to 6 for each player at round end."""
    updated_state = state
    events: list[GameEvent] = []

    for player_id in _real_players(state):
        player_state = updated_state.player_state(player_id)
        resource_updates = _resource_cap_updates(player_state.resources)
        if not resource_updates:
            continue

        stone_after = (
            resource_updates["stone"][1]
            if "stone" in resource_updates
            else player_state.resources.stone
        )
        wheat_after = (
            resource_updates["wheat"][1]
            if "wheat" in resource_updates
            else player_state.resources.wheat
        )
        new_resources = Resources(
            stone=stone_after,
            silver=player_state.resources.silver,
            wheat=wheat_after,
        )
        updated_state = updated_state.with_player_state(
            player_id,
            replace(player_state, resources=new_resources),
        )

        for resource_name, (before, after) in resource_updates.items():
            events.append(
                GameEvent(
                    event_type=EventType.EXCESS_DISCARD,
                    actor=actor,
                    action_id=action_id,
                    details=make_event_details(
                        player=player_id.name.lower(),
                        resource=resource_name,
                        before=before,
                        after=after,
                        returned=before - after,
                    ),
                )
            )

    if not events:
        events.append(
            GameEvent(
                event_type=EventType.EXCESS_CHECK,
                actor=actor,
                action_id=action_id,
                details=make_event_details(no_excess=True),
            )
        )
    return updated_state, tuple(events)


def resolve_trade_route_income(
    state: GameState,
    *,
    actor: PlayerId,
    action_id: str,
) -> tuple[GameState, tuple[GameEvent, ...]]:
    """No-op placeholder for deferred trade-route income phase."""
    event = GameEvent(
        event_type=EventType.TRADE_ROUTE_INCOME_SKIPPED,
        actor=actor,
        action_id=action_id,
        details=make_event_details(reason="trade routes not implemented"),
    )
    return state, (event,)


def select_next_start_player(
    state: GameState,
    *,
    actor: PlayerId,
    action_id: str,
) -> tuple[GameState, tuple[GameEvent, ...], PlayerId]:
    """
    Deterministically select next start player.

    Placeholder policy: highest piety selector selects themselves.
    """
    players = _real_players(state)
    highest_piety = max(state.player_state(player).piety for player in players)
    tied = tuple(player for player in players if state.player_state(player).piety == highest_piety)

    events: list[GameEvent] = []
    if len(tied) == 1:
        deciding_player = tied[0]
    else:
        deciding_player = _clockwise_tie_break(tied_players=tied, current_start=state.start_player)
        events.append(
            GameEvent(
                event_type=EventType.START_PLAYER_TIE_BREAK,
                actor=actor,
                action_id=action_id,
                details=make_event_details(
                    tied_players=",".join(player.name.lower() for player in tied),
                    current_start_player=state.start_player.name.lower(),
                    deciding_player=deciding_player.name.lower(),
                ),
            )
        )

    selected_start_player = deciding_player
    next_state = replace(
        state,
        start_player=selected_start_player,
        active_player=selected_start_player,
    )
    events.append(
        GameEvent(
            event_type=EventType.START_PLAYER_SELECTION,
            actor=actor,
            action_id=action_id,
            details=make_event_details(
                policy=START_PLAYER_POLICY,
                highest_piety=highest_piety,
                deciding_player=deciding_player.name.lower(),
                selected_start_player=selected_start_player.name.lower(),
            ),
        )
    )
    return next_state, tuple(events), selected_start_player


def _resource_cap_updates(resources: Resources) -> dict[str, tuple[int, int]]:
    updates: dict[str, tuple[int, int]] = {}
    if resources.stone > EXCESS_RESOURCE_CAP:
        updates["stone"] = (resources.stone, EXCESS_RESOURCE_CAP)
    if resources.wheat > EXCESS_RESOURCE_CAP:
        updates["wheat"] = (resources.wheat, EXCESS_RESOURCE_CAP)
    return updates


def _real_players(state: GameState) -> tuple[PlayerId, ...]:
    return tuple(PlayerId(index) for index in range(state.player_count))


def _clockwise_tie_break(
    *,
    tied_players: tuple[PlayerId, ...],
    current_start: PlayerId,
) -> PlayerId:
    candidate_order = tuple(
        PlayerId((int(current_start) + offset) % len(PlayerId))
        for offset in range(1, len(PlayerId) + 1)
    )
    for player in candidate_order:
        if player in tied_players:
            return player
    raise ValueError("No tied player found during start-player tie-break.")
