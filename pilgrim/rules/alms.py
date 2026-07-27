"""Alms track helpers for movement, rewards, and season-end resolution."""

from __future__ import annotations

from dataclasses import dataclass, replace

from pilgrim.model.config import AlmsConfig
from pilgrim.model.enums import EventType, PlayerId
from pilgrim.model.events import GameEvent, make_event_details
from pilgrim.model.resources import Resources
from pilgrim.model.state import GameState, PlayerState
from pilgrim.model.workforce import CommittedAcolytes


@dataclass(frozen=True, slots=True)
class AlmsPayment:
    """Resource payment used when resolving a Give Alms action."""

    silver: int = 0
    wheat: int = 0

    def __post_init__(self) -> None:
        if self.silver < 0 or self.wheat < 0:
            raise ValueError("Alms payment values cannot be negative.")

    @property
    def total(self) -> int:
        return self.silver + self.wheat


@dataclass(frozen=True, slots=True)
class AlmsThresholdOutcome:
    """Outcome for one crossed Alms threshold row."""

    threshold: int
    reward_key: str
    moved: bool
    description: str


@dataclass(frozen=True, slots=True)
class GiveAlmsResolution:
    """Resolved Give Alms payload used by transition logic."""

    player_state: PlayerState
    resource_delta: tuple[int, int, int]
    old_position: int
    new_position: int
    threshold_outcomes: tuple[AlmsThresholdOutcome, ...]


@dataclass(frozen=True, slots=True)
class DonateBuildingAlmsResolution:
    """Resolved Alms movement payload for give_alms_donate_building."""

    player_state: PlayerState
    old_position: int
    new_position: int
    threshold_outcomes: tuple[AlmsThresholdOutcome, ...]


@dataclass(frozen=True, slots=True)
class AlmsSeasonEndResult:
    """Result of season-end Alms reward and track reset."""

    state: GameState
    winner: PlayerId
    moved_to_alms_table: bool
    events: tuple[GameEvent, ...]


@dataclass(frozen=True, slots=True)
class _AlmsLeaderSelection:
    winner: PlayerId
    tie_break: str
    winning_alms_position: int
    winning_piety: int


def clamp_alms_position(position: int, config: AlmsConfig) -> int:
    """Clamp an Alms row to the configured track range."""
    return config.clamp(position)


def move_alms_position(old_position: int, amount: int, config: AlmsConfig) -> int:
    """Advance Alms by amount, capped by configured max row."""
    if amount < 0:
        raise ValueError("Alms movement amount cannot be negative.")
    return clamp_alms_position(old_position + amount, config)


def crossed_alms_thresholds(
    old_position: int,
    new_position: int,
    config: AlmsConfig,
) -> tuple[int, ...]:
    """Return threshold rows crossed during Alms movement."""
    if new_position < old_position:
        raise ValueError("Alms position cannot move backward in Give Alms.")
    crossed = [
        threshold
        for threshold, _ in config.threshold_rewards
        if old_position < threshold <= new_position
    ]
    return tuple(crossed)


def score_alms_table(acolytes_on_alms_table: int, config: AlmsConfig) -> int:
    """Return VP from committed Alms-table acolytes."""
    if acolytes_on_alms_table < 0:
        raise ValueError("Alms table acolytes cannot be negative.")
    return config.score(acolytes_on_alms_table)


def apply_alms_threshold_reward(
    player: PlayerState,
    threshold: int,
    config: AlmsConfig,
) -> tuple[PlayerState, AlmsThresholdOutcome]:
    """Apply one configured threshold reward to one player state."""
    reward_key = config.threshold_reward_for_row(threshold)
    if reward_key is None:
        raise ValueError(f"No Alms threshold reward configured for row {threshold}.")

    workforce = player.workforce
    moved = False
    description: str

    if reward_key == "village_to_abbey":
        if workforce.village > 0:
            workforce = replace(
                workforce,
                village=workforce.village - 1,
                abbey=workforce.abbey + 1,
            )
            moved = True
            description = "crossed row 2; moved 1 worker village -> abbey"
        else:
            description = "crossed row 2; no village serf available"
    elif reward_key == "abbey_to_city":
        if workforce.abbey > 0:
            city_mancala = list(workforce.mancala)
            city_mancala[0] += 1
            workforce = replace(
                workforce,
                mancala=tuple(city_mancala),
                abbey=workforce.abbey - 1,
            )
            moved = True
            description = "crossed row 4; moved 1 acolyte abbey -> city"
        else:
            description = "crossed row 4; no abbey acolyte available"
    elif reward_key == "village_to_city":
        if workforce.village > 0:
            city_mancala = list(workforce.mancala)
            city_mancala[0] += 1
            workforce = replace(
                workforce,
                mancala=tuple(city_mancala),
                village=workforce.village - 1,
            )
            moved = True
            description = "crossed row 6; moved 1 worker village -> city"
        else:
            description = "crossed row 6; no village serf available"
    else:
        raise ValueError(f"Unknown Alms threshold reward: {reward_key}")

    return (
        replace(player, workforce=workforce),
        AlmsThresholdOutcome(
            threshold=threshold,
            reward_key=reward_key,
            moved=moved,
            description=description,
        ),
    )


def resolve_give_alms(
    player: PlayerState,
    *,
    duty_value: int,
    payment: AlmsPayment,
    minority_silver_cost: int,
    config: AlmsConfig,
) -> GiveAlmsResolution:
    """Resolve Give Alms resource payment, track movement, and thresholds."""
    if duty_value <= 0:
        raise ValueError("Give Alms requires a positive duty value.")
    if minority_silver_cost < 0:
        raise ValueError("Minority silver cost cannot be negative.")
    if payment.total != duty_value:
        raise ValueError("Alms payment amount must equal duty value.")

    silver_after_cost = player.resources.silver - minority_silver_cost
    if silver_after_cost < payment.silver:
        raise ValueError("Insufficient silver for minority cost plus Alms payment.")
    if player.resources.wheat < payment.wheat:
        raise ValueError("Insufficient wheat for Alms payment.")

    old_position = clamp_alms_position(player.alms_position, config)
    new_position = move_alms_position(old_position, duty_value, config)
    total_silver_cost = minority_silver_cost + payment.silver

    resources = Resources(
        stone=player.resources.stone,
        silver=player.resources.silver - total_silver_cost,
        wheat=player.resources.wheat - payment.wheat,
    )
    updated_player = replace(
        player,
        resources=resources,
        alms_position=new_position,
    )

    outcomes: list[AlmsThresholdOutcome] = []
    for threshold in crossed_alms_thresholds(old_position, new_position, config):
        updated_player, outcome = apply_alms_threshold_reward(updated_player, threshold, config)
        outcomes.append(outcome)

    return GiveAlmsResolution(
        player_state=updated_player,
        resource_delta=(0, -total_silver_cost, -payment.wheat),
        old_position=old_position,
        new_position=new_position,
        threshold_outcomes=tuple(outcomes),
    )


def resolve_donate_building_alms(
    player: PlayerState,
    *,
    config: AlmsConfig,
) -> DonateBuildingAlmsResolution:
    """Resolve deterministic +1 Alms movement for give_alms_donate_building."""
    old_position = clamp_alms_position(player.alms_position, config)
    new_position = move_alms_position(old_position, 1, config)
    updated_player = replace(player, alms_position=new_position)

    outcomes: list[AlmsThresholdOutcome] = []
    for threshold in crossed_alms_thresholds(old_position, new_position, config):
        updated_player, outcome = apply_alms_threshold_reward(updated_player, threshold, config)
        outcomes.append(outcome)

    return DonateBuildingAlmsResolution(
        player_state=updated_player,
        old_position=old_position,
        new_position=new_position,
        threshold_outcomes=tuple(outcomes),
    )


def resolve_alms_season_end(
    state: GameState,
    config: AlmsConfig,
    *,
    actor: PlayerId | None = None,
    action_id: str = "alms:season_end",
    round_number: int | None = None,
    season_site_index: int | None = None,
) -> AlmsSeasonEndResult:
    """
    Resolve season-end Alms reward with deterministic tie-breakers.

    Tie-break model for this milestone:
    1) highest Alms position
    2) highest piety position
    3) earliest in current turn order (start player first)
    """
    leader = _determine_alms_leader(state, config)
    winner = leader.winner
    event_actor = winner if actor is None else actor
    effective_round = state.round_number if round_number is None else round_number
    updated_state = state
    events: list[GameEvent] = []
    winner_state_before = updated_state.player_state(winner)

    moved_to_alms_table = False
    if winner_state_before.workforce.abbey > 0:
        committed = winner_state_before.workforce.committed
        workforce = replace(
            winner_state_before.workforce,
            abbey=winner_state_before.workforce.abbey - 1,
            committed=CommittedAcolytes(
                roads=committed.roads,
                shrines=committed.shrines,
                market_ports=committed.market_ports,
                pilgrimage_sites=committed.pilgrimage_sites,
                alms_table=committed.alms_table + 1,
            ),
        )
        updated_state = updated_state.with_player_state(
            winner,
            replace(winner_state_before, workforce=workforce),
        )
        moved_to_alms_table = True

    details: dict[str, str | int | bool] = {
        "winner": winner.name.lower(),
        "winning_alms_position": leader.winning_alms_position,
        "winning_piety": leader.winning_piety,
        "tie_break": leader.tie_break,
        "round": effective_round,
    }
    if season_site_index is not None:
        details["season_site"] = season_site_index
    events.append(
        GameEvent(
            event_type=EventType.ALMS_SEASON_END,
            actor=event_actor,
            action_id=action_id,
            details=make_event_details(**details),
        )
    )

    winner_state_after_reward = updated_state.player_state(winner)
    alms_table_after = winner_state_after_reward.workforce.committed.alms_table
    end_game_vp = score_alms_table(alms_table_after, config)
    reward_details: dict[str, str | int | bool] = {
        "winner": winner.name.lower(),
        "moved": moved_to_alms_table,
    }
    if moved_to_alms_table:
        reward_details.update(
            {
                "from_pool": "abbey",
                "to_pool": "alms_table",
                "alms_table_acolytes": alms_table_after,
                "end_game_vp": end_game_vp,
            }
        )
    else:
        reward_details["forfeited"] = True
        reward_details["reason"] = "no_abbey_acolyte"
    events.append(
        GameEvent(
            event_type=EventType.ALMS_SEASON_REWARD,
            actor=event_actor,
            action_id=action_id,
            details=make_event_details(**reward_details),
        )
    )

    for player_id in (PlayerId(index) for index in range(state.player_count)):
        player_state = updated_state.player_state(player_id)
        if player_state.alms_position != 0:
            updated_state = updated_state.with_player_state(
                player_id,
                replace(player_state, alms_position=0),
            )

    events.append(
        GameEvent(
            event_type=EventType.ALMS_RESET,
            actor=event_actor,
            action_id=action_id,
            details=make_event_details(reset_to=0),
        )
    )

    return AlmsSeasonEndResult(
        state=updated_state,
        winner=winner,
        moved_to_alms_table=moved_to_alms_table,
        events=tuple(events),
    )


def _determine_alms_leader(state: GameState, config: AlmsConfig) -> _AlmsLeaderSelection:
    players = tuple(PlayerId(index) for index in range(state.player_count))
    highest_alms = max(
        clamp_alms_position(state.player_state(player).alms_position, config)
        for player in players
    )
    alms_tied = tuple(
        player
        for player in players
        if clamp_alms_position(state.player_state(player).alms_position, config) == highest_alms
    )
    if len(alms_tied) == 1:
        winner = alms_tied[0]
        return _AlmsLeaderSelection(
            winner=winner,
            tie_break="highest_alms_position",
            winning_alms_position=highest_alms,
            winning_piety=state.player_state(winner).piety,
        )

    highest_piety = max(state.player_state(player).piety for player in alms_tied)
    piety_tied = tuple(
        player for player in alms_tied if state.player_state(player).piety == highest_piety
    )
    if len(piety_tied) == 1:
        winner = piety_tied[0]
        return _AlmsLeaderSelection(
            winner=winner,
            tie_break="higher_piety",
            winning_alms_position=highest_alms,
            winning_piety=highest_piety,
        )

    turn_order = _current_turn_order_from_start_player(
        start_player=state.start_player,
        player_count=state.player_count,
    )
    winner = next(player for player in turn_order if player in piety_tied)
    return _AlmsLeaderSelection(
        winner=winner,
        tie_break="turn_order",
        winning_alms_position=highest_alms,
        winning_piety=highest_piety,
    )


def _current_turn_order_from_start_player(
    *,
    start_player: PlayerId,
    player_count: int,
) -> tuple[PlayerId, ...]:
    return tuple(
        PlayerId((int(start_player) + offset) % player_count)
        for offset in range(player_count)
    )
