"""Round-end phase helpers for excess, trade-route income, and start player."""

from __future__ import annotations

from dataclasses import replace

from pilgrim.model.config import MerchantConfig
from pilgrim.model.enums import EventType, PlayerId
from pilgrim.model.events import GameEvent, make_event_details
from pilgrim.model.resources import Resources
from pilgrim.model.state import GameState
from pilgrim.rules.merchant import trade_route_income_resource

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
        details: dict[str, str | int | bool] = {"player": player_id.name.lower()}
        if "stone" in resource_updates:
            stone_before, stone_after = resource_updates["stone"]
            details["stone_before"] = stone_before
            details["stone_after"] = stone_after
        if "wheat" in resource_updates:
            wheat_before, wheat_after = resource_updates["wheat"]
            details["wheat_before"] = wheat_before
            details["wheat_after"] = wheat_after
        events.append(
            GameEvent(
                event_type=EventType.EXCESS_RESOURCE_CAP,
                actor=actor,
                action_id=action_id,
                details=make_event_details(**details),
            )
        )
    return updated_state, tuple(events)


def resolve_trade_route_income(
    state: GameState,
    *,
    merchant_config: MerchantConfig,
    actor: PlayerId,
    action_id: str,
) -> tuple[GameState, tuple[GameEvent, ...]]:
    """Apply post-merchant trade-route income by current Merchant resource."""
    resource = trade_route_income_resource(state, merchant_config)
    if resource is None:
        return state, ()

    next_state = state
    events: list[GameEvent] = []
    for player_id in _real_players(state):
        player_state = next_state.player_state(player_id)
        trade_routes_count = player_state.trade_routes_count
        if trade_routes_count <= 0:
            continue
        if resource == "wheat":
            next_resources = player_state.resources.add(wheat=trade_routes_count)
        elif resource == "silver":
            next_resources = player_state.resources.add(silver=trade_routes_count)
        elif resource == "stone":
            next_resources = player_state.resources.add(stone=trade_routes_count)
        else:
            raise ValueError(f"Unknown trade-route income resource: {resource}.")
        next_state = next_state.with_player_state(
            player_id,
            replace(player_state, resources=next_resources),
        )
        events.append(
            GameEvent(
                event_type=EventType.TRADE_ROUTE_INCOME,
                actor=actor,
                action_id=action_id,
                details=make_event_details(
                    player=player_id.name.lower(),
                    resource=resource,
                    amount=trade_routes_count,
                    trade_routes=trade_routes_count,
                ),
            )
        )
    return next_state, tuple(events)


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
        deciding_player = _clockwise_tie_break(
            tied_players=tied,
            current_start=state.start_player,
            player_count=state.player_count,
        )
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
    player_count: int,
) -> PlayerId:
    candidate_order = tuple(
        PlayerId((int(current_start) + offset) % player_count)
        for offset in range(1, player_count + 1)
    )
    for player in candidate_order:
        if player in tied_players:
            return player
    raise ValueError("No tied player found during start-player tie-break.")
