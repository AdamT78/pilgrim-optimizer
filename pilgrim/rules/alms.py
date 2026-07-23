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
    """Resolved Alms movement payload for donate_building."""

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
    """Resolve deterministic +1 Alms movement for donate_building."""
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


def resolve_alms_season_end(state: GameState, config: AlmsConfig) -> AlmsSeasonEndResult:
    """
    Resolve season-end Alms reward with deterministic tie-breakers.

    Tie-break model for this milestone:
    1) highest Alms position
    2) highest piety position
    3) earliest in current turn order (active player first)
    """
    winner = _determine_alms_leader(state, config)
    updated_state = state
    events: list[GameEvent] = []

    winner_state = updated_state.player_state(winner)
    moved_to_alms_table = False
    if winner_state.workforce.abbey > 0:
        committed = winner_state.workforce.committed
        workforce = replace(
            winner_state.workforce,
            abbey=winner_state.workforce.abbey - 1,
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
            replace(winner_state, workforce=workforce),
        )
        moved_to_alms_table = True

    for player_id in PlayerId:
        player_state = updated_state.player_state(player_id)
        if player_state.alms_position != 0:
            updated_state = updated_state.with_player_state(
                player_id,
                replace(player_state, alms_position=0),
            )

    events.append(
        GameEvent(
            event_type=EventType.ALMS_SEASON_REWARD,
            actor=winner,
            action_id="alms:season_end",
            details=make_event_details(
                winner=winner.name.lower(),
                moved=moved_to_alms_table,
            ),
        )
    )
    events.append(
        GameEvent(
            event_type=EventType.ALMS_RESET,
            actor=winner,
            action_id="alms:season_end",
            details=make_event_details(reset_to=0),
        )
    )

    return AlmsSeasonEndResult(
        state=updated_state,
        winner=winner,
        moved_to_alms_table=moved_to_alms_table,
        events=tuple(events),
    )


def _determine_alms_leader(state: GameState, config: AlmsConfig) -> PlayerId:
    turn_order = _current_turn_order(state.active_player)
    order_index = {player_id: index for index, player_id in enumerate(turn_order)}

    return max(
        PlayerId,
        key=lambda player_id: (
            clamp_alms_position(state.player_state(player_id).alms_position, config),
            state.player_state(player_id).piety,
            -order_index[player_id],
        ),
    )


def _current_turn_order(active_player: PlayerId) -> tuple[PlayerId, PlayerId]:
    if active_player is PlayerId.PLAYER_ONE:
        return (PlayerId.PLAYER_ONE, PlayerId.PLAYER_TWO)
    return (PlayerId.PLAYER_TWO, PlayerId.PLAYER_ONE)
