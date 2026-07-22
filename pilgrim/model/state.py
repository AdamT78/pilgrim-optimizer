"""Immutable game state containers."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from pilgrim.model.enums import PlayerId, TurnPhase
from pilgrim.model.resources import Resources
from pilgrim.model.workforce import (
    MANCALA_POSITION_COUNT,
    Workforce,
    replace_mancala,
    total_acolytes,
)

POSITION_COUNT = MANCALA_POSITION_COUNT
PlayerVector = tuple[int, ...]


@dataclass(frozen=True, slots=True)
class PlayerState:
    """Per-player scalar values and resources."""

    resources: Resources = Resources()
    workforce: Workforce = field(
        default_factory=lambda: Workforce(mancala=(0,) * MANCALA_POSITION_COUNT)
    )
    piety: int = 0
    victory_points: int = 0

    def __post_init__(self) -> None:
        if self.piety < 0 or self.victory_points < 0:
            raise ValueError("Piety and victory points cannot be negative.")

    @property
    def mancala_acolytes(self) -> PlayerVector:
        """Backward-compatible access to mancala pools."""
        return self.workforce.mancala


@dataclass(frozen=True, slots=True)
class GameState:
    """Hashable full game state used by transitions and exact search memoization."""

    active_player: PlayerId
    phase: TurnPhase
    players: tuple[PlayerState, PlayerState]
    turn: int = 0

    def __post_init__(self) -> None:
        if len(self.players) != 2:
            raise ValueError("Exactly two players are required.")
        if self.turn < 0:
            raise ValueError("Turn cannot be negative.")

    def player_state(self, player_id: PlayerId) -> PlayerState:
        return self.players[int(player_id)]

    def player_vector(self, player_id: PlayerId) -> PlayerVector:
        return self.player_state(player_id).workforce.mancala

    @property
    def acolytes(self) -> tuple[PlayerVector, PlayerVector]:
        """Backward-compatible acolyte vectors from workforce mancala pools."""
        return (
            self.players[int(PlayerId.PLAYER_ONE)].workforce.mancala,
            self.players[int(PlayerId.PLAYER_TWO)].workforce.mancala,
        )

    def total_acolytes(self, player_id: PlayerId) -> int:
        return total_acolytes(self.player_state(player_id).workforce)

    def with_player_state(self, player_id: PlayerId, player_state: PlayerState) -> GameState:
        players = list(self.players)
        players[int(player_id)] = player_state
        return replace(self, players=tuple(players))  # type: ignore[arg-type]

    def with_player_vector(self, player_id: PlayerId, vector: PlayerVector) -> GameState:
        if len(vector) != POSITION_COUNT:
            raise ValueError(f"Acolyte vectors must have {POSITION_COUNT} positions.")
        player_state = self.player_state(player_id)
        updated_workforce = replace_mancala(player_state.workforce, vector)
        return self.with_player_state(
            player_id,
            replace(player_state, workforce=updated_workforce),
        )

    def next_player_turn(self) -> GameState:
        return replace(
            self,
            active_player=self.active_player.opponent(),
            phase=TurnPhase.SOW,
            turn=self.turn + 1,
        )
