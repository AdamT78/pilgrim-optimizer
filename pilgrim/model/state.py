"""Immutable game state containers."""

from __future__ import annotations

from dataclasses import dataclass, replace

from pilgrim.model.enums import PlayerId, TurnPhase
from pilgrim.model.resources import Resources

POSITION_COUNT = 9
PlayerVector = tuple[int, ...]


@dataclass(frozen=True, slots=True)
class PlayerState:
    """Per-player scalar values and resources."""

    resources: Resources = Resources()
    piety: int = 0
    victory_points: int = 0

    def __post_init__(self) -> None:
        if self.piety < 0 or self.victory_points < 0:
            raise ValueError("Piety and victory points cannot be negative.")

    def value_score(self) -> int:
        """Temporary objective used by the exact search scaffold."""
        return self.victory_points + self.piety + self.resources.score()


@dataclass(frozen=True, slots=True)
class GameState:
    """Hashable full game state used by transitions and exact search memoization."""

    active_player: PlayerId
    phase: TurnPhase
    players: tuple[PlayerState, PlayerState]
    acolytes: tuple[PlayerVector, PlayerVector]
    turn: int = 0

    def __post_init__(self) -> None:
        if len(self.players) != 2:
            raise ValueError("Exactly two players are required.")
        if len(self.acolytes) != 2:
            raise ValueError("Exactly two acolyte vectors are required.")
        for vector in self.acolytes:
            if len(vector) != POSITION_COUNT:
                raise ValueError(f"Acolyte vectors must have {POSITION_COUNT} positions.")
            if any(value < 0 for value in vector):
                raise ValueError("Acolyte counts cannot be negative.")
        if self.turn < 0:
            raise ValueError("Turn cannot be negative.")

    def player_state(self, player_id: PlayerId) -> PlayerState:
        return self.players[int(player_id)]

    def player_vector(self, player_id: PlayerId) -> PlayerVector:
        return self.acolytes[int(player_id)]

    def total_acolytes(self, player_id: PlayerId) -> int:
        return sum(self.player_vector(player_id))

    def with_player_state(self, player_id: PlayerId, player_state: PlayerState) -> GameState:
        players = list(self.players)
        players[int(player_id)] = player_state
        return replace(self, players=tuple(players))  # type: ignore[arg-type]

    def with_player_vector(self, player_id: PlayerId, vector: PlayerVector) -> GameState:
        if len(vector) != POSITION_COUNT:
            raise ValueError(f"Acolyte vectors must have {POSITION_COUNT} positions.")
        acolytes = list(self.acolytes)
        acolytes[int(player_id)] = vector
        return replace(self, acolytes=tuple(acolytes))  # type: ignore[arg-type]

    def next_player_turn(self) -> GameState:
        return replace(
            self,
            active_player=self.active_player.opponent(),
            phase=TurnPhase.SOW,
            turn=self.turn + 1,
        )
