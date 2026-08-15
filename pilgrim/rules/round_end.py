"""Round-end phase helpers for excess, trade-route income, and start player."""

from __future__ import annotations

from dataclasses import replace

from pilgrim.model.config import GameConfig
from pilgrim.model.enums import EventType, PlayerId, TurnPhase
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


def start_player_confession_order(state: GameState) -> tuple[PlayerId, ...]:
    """Turn order for the Confession Box phase: clockwise from the round's OWN start player.

    "Turn order" has two readings once a round end is underway, and they name different seats. The
    one meant here is the order the round that just finished was PLAYED in -- clockwise from
    `state.start_player`, which at this moment still names the seat that round began from, because
    nothing has chosen a new one yet and nothing may until the marker is awarded.

    The other reading -- clockwise from whoever begins the round to come -- is not available and
    could not be: the boxes are asked BEFORE the marker, and who begins next is decided after it by
    a player the boxes are still choosing. Ordering by it would need the answer to the question the
    phase exists to ask.
    """
    current_start = _require_start_player(
        state,
        context="Confession Box turn order requires the round's chosen start player.",
    )
    return tuple(
        PlayerId((int(current_start) + offset) % state.player_count)
        for offset in range(state.player_count)
    )


def confession_box_source_for(
    state: GameState,
    config: GameConfig,
    *,
    player: PlayerId,
) -> BuildingAbilitySource | None:
    """How this player could reach a Confession Box right now, or None if they cannot.

    None is the answer that keeps a player out of the phase entirely. It covers all of: the box is
    not in this game, it is donated, nobody has it live yet, and -- the one that changes as the
    phase runs -- they cannot afford the hire, because an earlier player in the same phase may have
    just spent the resource on hiring it themselves.
    """
    source = building_ability_source(
        state,
        config,
        acting_player=player,
        building_key=_BUILDING_CONFESSION_BOX,
    )
    if not source.usable:
        return None
    if not _confession_box_source_is_live_for_start_player_phase(state, source):
        return None
    if source.source_type == "own_active":
        return source
    try:
        apply_building_hire_payment(state, acting_player=player, source=source)
    except ValueError:
        return None
    return source


def begin_start_player_confession(
    state: GameState,
    *,
    config: GameConfig,
) -> GameState | None:
    """Hand the table to the first player with a box to decide about, or say there is nobody.

    None means the phase does not happen: not one player at the table can reach a Confession Box,
    so there is nothing to ask and nothing an answer could change. The caller awards the marker
    directly, which is what every round did before this phase existed.
    """
    pending = start_player_confession_order(state)
    return _advance_start_player_confession(
        state.with_start_player_confession_progress(pending=pending, used=()),
        config=config,
    )


def _advance_start_player_confession(
    state: GameState,
    *,
    config: GameConfig,
) -> GameState | None:
    """Walk the pending list to the next player who actually has something to decide.

    Players with no reachable box are skipped rather than asked and shown one option, and they are
    skipped HERE rather than when the phase begins, because affordability moves during the phase:
    a hire paid by an earlier player can take the last coin off a later one, and asking somebody
    to choose between declining and declining is not a decision.
    """
    pending = state.start_player_confession_pending
    for index, player in enumerate(pending):
        if confession_box_source_for(state, config, player=player) is None:
            continue
        return replace(
            state,
            phase=TurnPhase.START_PLAYER_CONFESSION,
            active_player=player,
            start_player_confession_pending=pending[index:],
        )
    return None


def apply_start_player_confession_box(
    state: GameState,
    *,
    config: GameConfig,
    use: bool,
    source_label: str | None,
    actor: PlayerId,
    action_id: str,
) -> tuple[GameState, tuple[GameEvent, ...], bool]:
    """One player's answer, applied. The third value says whether anybody is still to be asked.

    A use is PAID FOR HERE rather than banked until the marker is counted. The player has decided
    and the resource has left them, and holding the payment back would let a later player in the
    same phase see money that is already spent -- which is exactly the affordability the skip above
    depends on being current.
    """
    source = confession_box_source_for(state, config, player=actor)
    if source is None:
        raise TransitionValidationError(
            f"Confession Box is unavailable for {actor.name.lower()} in current state."
        )

    events: list[GameEvent] = []
    next_state = state
    if use:
        expected_source = _confession_box_source_label_for_ability_source(source)
        if source_label != expected_source:
            raise TransitionValidationError(
                "Confession Box source selection is invalid for "
                f"{actor.name.lower()}: expected {expected_source}, got {source_label}."
            )
        if source.source_type != "own_active":
            try:
                next_state, hire_payment = apply_building_hire_payment(
                    next_state,
                    acting_player=actor,
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
                        source=expected_source,
                        payee=hire_payment.payee,
                        resource=hire_payment.resource or "none",
                        amount=hire_payment.amount,
                    ),
                )
            )
        base_piety = next_state.player_state(actor).piety
        events.append(
            GameEvent(
                event_type=EventType.CONFESSION_BOX_BONUS,
                actor=actor,
                action_id=action_id,
                details=make_event_details(
                    player=actor.name.lower(),
                    source=expected_source,
                    base_piety=base_piety,
                    temporary_bonus=_CONFESSION_BOX_TEMPORARY_PIETY_BONUS,
                    effective_piety=base_piety + _CONFESSION_BOX_TEMPORARY_PIETY_BONUS,
                ),
            )
        )
        used = (*next_state.start_player_confession_used, actor)
    else:
        if source_label is not None:
            raise TransitionValidationError("Declining the Confession Box cannot name a source.")
        events.append(
            GameEvent(
                event_type=EventType.CONFESSION_BOX_DECLINED,
                actor=actor,
                action_id=action_id,
                details=make_event_details(player=actor.name.lower()),
            )
        )
        used = next_state.start_player_confession_used

    next_state = next_state.with_start_player_confession_progress(
        pending=next_state.start_player_confession_pending[1:],
        used=used,
    )
    advanced = _advance_start_player_confession(next_state, config=config)
    if advanced is None:
        return next_state, tuple(events), False
    return advanced, tuple(events), True


def award_first_player_marker(
    state: GameState,
    *,
    config: GameConfig,
    actor: PlayerId,
    action_id: str,
) -> tuple[GameState, tuple[GameEvent, ...], PlayerId]:
    """Give the First Player marker to the highest effective piety, and say who has it.

    This decides who DECIDES, and stops there. Who actually begins the next round is that player's
    to say, and they may say anyone, so nothing here may write `start_player`: doing so is what the
    placeholder did, and it is why the marker used to mean nothing.

    Effective piety is real piety plus two for each seat in `start_player_confession_used`, and
    those two are added HERE and stored nowhere. Real piety is not touched, at this round end or
    any later one -- the bonus exists for the length of this comparison and then is gone.

    Ties walk clockwise from the CURRENT start player, which is why this runs before anything sets
    a new one -- the seat the walk starts from is the one the round was played from.
    """
    players = _real_players(state)
    current_start = _require_start_player(
        state,
        context="First Player marker tie-break requires the round's chosen start player.",
    )
    bonus_players = set(state.start_player_confession_used)
    events: list[GameEvent] = []

    def effective_piety(player_id: PlayerId) -> int:
        bonus = _CONFESSION_BOX_TEMPORARY_PIETY_BONUS if player_id in bonus_players else 0
        return state.player_state(player_id).piety + bonus

    highest_effective_piety = max(effective_piety(player) for player in players)
    tied = tuple(player for player in players if effective_piety(player) == highest_effective_piety)
    if len(tied) == 1:
        deciding_player = tied[0]
    else:
        deciding_player = _clockwise_tie_break(
            tied_players=tied,
            current_start=current_start,
            player_count=state.player_count,
        )
        events.append(
            GameEvent(
                event_type=EventType.START_PLAYER_TIE_BREAK,
                actor=actor,
                action_id=action_id,
                details=make_event_details(
                    tied_players=",".join(player.name.lower() for player in tied),
                    current_start_player=current_start.name.lower(),
                    deciding_player=deciding_player.name.lower(),
                    highest_effective_piety=highest_effective_piety,
                ),
            )
        )

    # Three writes, and only two of them are about right now. `first_player_marker` is the durable
    # one: it says who holds the marker for the round that follows, and nothing before the next
    # round end takes it off them. `active_player` says who acts, which at this instant is the same
    # player only because the thing being waited for is their choice.
    #
    # `start_player` is deliberately left alone: it still names the seat the round just played
    # from, which is what the next tie-break will walk from, and it is not replaced until somebody
    # chooses.
    #
    # The Confession Box tallies are cleared in the same breath they are last read. They were about
    # this award and no other, and the next round end builds its own.
    next_state = replace(
        state,
        phase=TurnPhase.START_PLAYER_SELECTION,
        active_player=deciding_player,
        first_player_marker=deciding_player,
        start_player_confession_pending=(),
        start_player_confession_used=(),
    )
    events.append(
        GameEvent(
            event_type=EventType.START_PLAYER_MARKER,
            actor=actor,
            action_id=action_id,
            details=make_event_details(
                highest_effective_piety=highest_effective_piety,
                deciding_player=deciding_player.name.lower(),
                current_start_player=current_start.name.lower(),
            ),
        )
    )
    return next_state, tuple(events), deciding_player


def choosable_start_players(state: GameState) -> tuple[PlayerId, ...]:
    """Everyone the marker holder may name, which is everyone.

    Including the holder. That is not an extra option bolted on beside the others -- it falls out
    of "may be anyone", and writing it as a case would be inventing a rule to then have to keep.
    """
    return _real_players(state)


def apply_start_player_selection(
    state: GameState,
    *,
    chosen_start_player: PlayerId,
    actor: PlayerId,
    action_id: str,
    next_phase: TurnPhase,
) -> tuple[GameState, tuple[GameEvent, ...]]:
    """Set who begins, and hand the table to them.

    Two writes, both meant: `start_player` is the seat the next round is played from and the seat a
    future tie-break walks from, and `active_player` is who moves now. They agree here because the
    round is about to start with the player who was chosen, and they are still not the same fact.

    `first_player_marker` is NOT among them, and must not become one. The holder keeps the marker
    through the round they have just given away, and a line here that moved it along to the chosen
    player would delete the only occasion on which the two ever visibly differ -- which is to say,
    it would delete the rule.
    """
    if chosen_start_player not in choosable_start_players(state):
        raise TransitionValidationError(
            f"Chosen start player is not a real player: {chosen_start_player!r}."
        )
    next_state = replace(
        state,
        start_player=chosen_start_player,
        active_player=chosen_start_player,
        phase=next_phase,
    )
    return next_state, (
        GameEvent(
            event_type=EventType.START_PLAYER_SELECTION,
            actor=actor,
            action_id=action_id,
            # Two names and no flag saying whether they match. A `chose_self` boolean beside them
            # is the same fact a third time, and its only reader was a shorter wording for the
            # self-selection case -- the wording that made a self-selection and a dropped name
            # indistinguishable. Anyone who needs the answer compares the two names.
            details=make_event_details(
                deciding_player=actor.name.lower(),
                selected_start_player=chosen_start_player.name.lower(),
            ),
        ),
    )


def _resource_cap_updates(resources: Resources) -> dict[str, tuple[int, int]]:
    updates: dict[str, tuple[int, int]] = {}
    if resources.stone > EXCESS_RESOURCE_CAP:
        updates["stone"] = (resources.stone, EXCESS_RESOURCE_CAP)
    if resources.wheat > EXCESS_RESOURCE_CAP:
        updates["wheat"] = (resources.wheat, EXCESS_RESOURCE_CAP)
    return updates


def _real_players(state: GameState) -> tuple[PlayerId, ...]:
    return tuple(PlayerId(index) for index in range(state.player_count))


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


def _require_start_player(state: GameState, *, context: str) -> PlayerId:
    """The chosen start player, which some round-end steps cannot proceed without."""
    if state.start_player is None:
        raise TransitionValidationError(context)
    return state.start_player
