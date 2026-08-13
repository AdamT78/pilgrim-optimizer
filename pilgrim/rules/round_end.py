"""Round-end phase helpers for excess, trade-route income, and start player."""

from __future__ import annotations

from dataclasses import replace

from pilgrim.model.actions import StartPlayerConfessionBoxUse
from pilgrim.model.config import GameConfig
from pilgrim.model.enums import EventType, PlayerId
from pilgrim.model.events import GameEvent, make_event_details
from pilgrim.model.resources import Resources
from pilgrim.model.state import GameState
from pilgrim.rules.buildings import (
    BuildingAbilitySource,
    apply_building_hire_payment,
    building_ability_source,
    building_live_round,
    is_building_live,
)
from pilgrim.rules.merchant import CORNUCOPIA_COUNTER, trade_route_income_resource
from pilgrim.rules.validation import TransitionValidationError

EXCESS_RESOURCE_CAP = 6
START_PLAYER_POLICY = "highest_piety_selects_self"
_BUILDING_CONFESSION_BOX = "confession_box"
_CONFESSION_BOX_TEMPORARY_PIETY_BONUS = 2


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
    config: GameConfig,
    actor: PlayerId,
    action_id: str,
) -> tuple[GameState, tuple[GameEvent, ...]]:
    """Apply post-merchant trade-route income in the Merchant's current resource."""
    resource = trade_route_income_resource(state, config)
    if resource is None:
        return state, ()

    if resource == CORNUCOPIA_COUNTER:
        # A cornucopia here would need each player to choose what their routes pay in, and that
        # choice deliberately does not exist: every trade_routes_count is 0 until map tile
        # placement lands, so there is nothing to choose about and no income to pay. Adding a
        # per-player round-end prompt now would be a phase built for no one. When trade routes
        # arrive, this is where the choice goes.
        #
        # Hiring makes the same choice and does have it, because hiring happens on a turn where
        # one player is acting and can be asked. This is round end, where every player would have
        # to answer at once.
        return state, (
            GameEvent(
                event_type=EventType.TRADE_ROUTE_INCOME_SKIPPED,
                actor=actor,
                action_id=action_id,
                details=make_event_details(reason="cornucopia_income_choice_not_implemented"),
            ),
        )

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
    config: GameConfig,
    actor: PlayerId,
    action_id: str,
    confession_box_uses: tuple[StartPlayerConfessionBoxUse, ...] = (),
) -> tuple[GameState, tuple[GameEvent, ...], PlayerId]:
    """
    Deterministically select next start player.

    Placeholder policy: highest piety selector selects themselves.
    """
    players = _real_players(state)
    ordered_players = _start_player_order(state)
    use_by_player = _confession_box_use_by_player(
        state,
        confession_box_uses=confession_box_uses,
    )

    next_state = state
    events: list[GameEvent] = []
    temporary_bonus_by_player: dict[PlayerId, int] = {player_id: 0 for player_id in players}
    for player_id in ordered_players:
        directive = use_by_player.get(player_id)
        if directive is None:
            continue
        source = building_ability_source(
            next_state,
            config,
            acting_player=player_id,
            building_key=_BUILDING_CONFESSION_BOX,
        )
        if not source.usable:
            raise TransitionValidationError(
                f"Confession Box is unavailable for {player_id.name.lower()} in current state."
            )
        if not _confession_box_source_is_live_for_start_player_phase(next_state, source):
            raise TransitionValidationError(
                f"Confession Box is not live for {player_id.name.lower()} in current state."
            )
        expected_source = _confession_box_source_label_for_ability_source(source)
        if directive.source != expected_source:
            raise TransitionValidationError(
                "Confession Box source selection is invalid for "
                f"{player_id.name.lower()}: expected {expected_source}, got {directive.source}."
            )
        if source.source_type != "own_active":
            try:
                next_state, hire_payment = apply_building_hire_payment(
                    next_state,
                    acting_player=player_id,
                    source=source,
                )
            except ValueError as exc:
                raise TransitionValidationError(str(exc)) from exc
            events.append(
                GameEvent(
                    event_type=EventType.BUILDING_HIRED,
                    actor=actor,
                    action_id=action_id,
                    details=make_event_details(
                        building_id=_BUILDING_CONFESSION_BOX,
                        building_name=config.buildings.name_for_id(_BUILDING_CONFESSION_BOX),
                        source=directive.source,
                        payee=hire_payment.payee,
                        resource=hire_payment.resource or "none",
                        amount=hire_payment.amount,
                    ),
                )
            )
        base_piety = next_state.player_state(player_id).piety
        effective_piety = base_piety + _CONFESSION_BOX_TEMPORARY_PIETY_BONUS
        temporary_bonus_by_player[player_id] = _CONFESSION_BOX_TEMPORARY_PIETY_BONUS
        events.append(
            GameEvent(
                event_type=EventType.CONFESSION_BOX_BONUS,
                actor=actor,
                action_id=action_id,
                details=make_event_details(
                    player=player_id.name.lower(),
                    source=directive.source,
                    base_piety=base_piety,
                    temporary_bonus=_CONFESSION_BOX_TEMPORARY_PIETY_BONUS,
                    effective_piety=effective_piety,
                ),
            )
        )

    highest_effective_piety = max(
        next_state.player_state(player).piety + temporary_bonus_by_player[player]
        for player in players
    )
    tied = tuple(
        player
        for player in players
        if next_state.player_state(player).piety + temporary_bonus_by_player[player]
        == highest_effective_piety
    )
    if len(tied) == 1:
        deciding_player = tied[0]
    else:
        deciding_player = _clockwise_tie_break(
            tied_players=tied,
            current_start=next_state.start_player,
            player_count=next_state.player_count,
        )
        events.append(
            GameEvent(
                event_type=EventType.START_PLAYER_TIE_BREAK,
                actor=actor,
                action_id=action_id,
                details=make_event_details(
                    tied_players=",".join(player.name.lower() for player in tied),
                    current_start_player=next_state.start_player.name.lower(),
                    deciding_player=deciding_player.name.lower(),
                    highest_effective_piety=highest_effective_piety,
                ),
            )
        )

    selected_start_player = deciding_player
    next_state = replace(
        next_state,
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
                highest_piety=highest_effective_piety,
                highest_effective_piety=highest_effective_piety,
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


def _start_player_order(state: GameState) -> tuple[PlayerId, ...]:
    return tuple(
        PlayerId((int(state.start_player) + offset) % state.player_count)
        for offset in range(state.player_count)
    )


def _confession_box_use_by_player(
    state: GameState,
    *,
    confession_box_uses: tuple[StartPlayerConfessionBoxUse, ...],
) -> dict[PlayerId, StartPlayerConfessionBoxUse]:
    order = _start_player_order(state)
    order_index = {player_id: index for index, player_id in enumerate(order)}
    use_by_player: dict[PlayerId, StartPlayerConfessionBoxUse] = {}
    max_seen_order = -1
    for directive in confession_box_uses:
        player_id = directive.player
        if player_id not in order_index:
            raise TransitionValidationError(
                f"Confession Box directive references non-real player: {player_id!r}."
            )
        if player_id in use_by_player:
            raise TransitionValidationError(
                f"Confession Box directive duplicates player {player_id.name.lower()}."
            )
        player_order_index = order_index[player_id]
        if player_order_index <= max_seen_order:
            raise TransitionValidationError(
                "Confession Box directives must be listed in start-player turn order."
            )
        max_seen_order = player_order_index
        if directive.source in {"own_active", "market"}:
            use_by_player[player_id] = directive
            continue
        try:
            source_player = PlayerId.from_string(directive.source)
        except ValueError as exc:
            raise TransitionValidationError(
                f"Confession Box source must be own_active, market, or opponent player id; got {directive.source}."
            ) from exc
        if source_player == player_id:
            raise TransitionValidationError(
                "Confession Box source cannot reference the same player as opponent source."
            )
        if source_player not in order_index:
            raise TransitionValidationError(
                f"Confession Box source references non-real opponent: {directive.source}."
            )
        use_by_player[player_id] = directive
    return use_by_player


def _confession_box_source_label_for_ability_source(source: BuildingAbilitySource) -> str:
    if source.source_type == "own_active":
        return "own_active"
    if source.source_type == "live_market_hire":
        return "market"
    if source.source_type == "opponent_active_hire":
        if source.owner is None:
            raise TransitionValidationError(
                "Confession Box opponent-hire source is missing owner label."
            )
        return source.owner
    raise TransitionValidationError(
        f"Confession Box source cannot be used from {source.source_type}."
    )


def _confession_box_source_is_live_for_start_player_phase(
    state: GameState,
    source: BuildingAbilitySource,
) -> bool:
    if source.source_type not in {"own_active", "opponent_active_hire"}:
        return True
    live_round = building_live_round(state, _BUILDING_CONFESSION_BOX)
    if live_round is None:
        return True
    return is_building_live(state, _BUILDING_CONFESSION_BOX)


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
