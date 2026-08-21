"""Immutable game state containers."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from pilgrim.model.buildings import PlayerBoardSlots
from pilgrim.model.dummy import DummyAcolyteGroups
from pilgrim.model.duties import DEFAULT_TAXATION_BOARD_POSITION, DUTY_POSITIONS
from pilgrim.model.enums import PlayerId, TurnPhase
from pilgrim.model.events import GameEvent
from pilgrim.model.resources import Resources
from pilgrim.model.special_activities import SpecialActivities
from pilgrim.model.timing import TimingState
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
    alms_position: int = 0
    victory_points: int = 0
    special_activities: SpecialActivities = field(default_factory=SpecialActivities)
    player_board_slots: PlayerBoardSlots = field(default_factory=PlayerBoardSlots)
    trade_routes_count: int = 0

    def __post_init__(self) -> None:
        if self.piety < 0 or self.victory_points < 0 or self.alms_position < 0:
            raise ValueError("Piety, Alms position, and victory points cannot be negative.")
        if self.trade_routes_count < 0:
            raise ValueError("trade_routes_count cannot be negative.")

    @property
    def mancala_acolytes(self) -> PlayerVector:
        """Backward-compatible access to mancala pools."""
        return self.workforce.mancala


@dataclass(frozen=True, slots=True)
class TurnProgress:
    """Immutable progress and events accumulated inside one active turn."""

    used_buildings: frozenset[str] = frozenset()
    events: tuple[GameEvent, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.used_buildings, frozenset):
            object.__setattr__(self, "used_buildings", frozenset(self.used_buildings))
        if not isinstance(self.events, tuple):
            object.__setattr__(self, "events", tuple(self.events))


@dataclass(frozen=True, slots=True)
class GameState:
    """Hashable full game state used by transitions and exact search memoization."""

    active_player: PlayerId
    phase: TurnPhase
    players: tuple[PlayerState, ...]
    # The seat the round is played from, once one has been chosen. A generated game opens by
    # asking who begins; before that answer exists this is None rather than a seed value that reads
    # like a fact and cannot be told apart from one.
    start_player: PlayerId | None = None
    # Who holds the First Player marker, which is NOT who begins the round. It is won at a round
    # end on effective piety and then sits with that player until the next round end takes it away,
    # so it outlives the phase where they were asked to name a start player -- and it stays put
    # when they name somebody else, which is the whole of what the marker is worth.
    #
    # `None` means UNKNOWN rather than nobody. The holder was settled at a round end from piety
    # values that have moved since, so a state that never carried one cannot have it worked out
    # afterwards: the answer would be who would win it now, presented as who won it then. Scenario
    # files written before the field existed load with `None` and the seal is simply not drawn.
    first_player_marker: PlayerId | None = None
    timing: TimingState = field(default_factory=TimingState)
    table_player_count: int = 4
    dummy_acolytes: DummyAcolyteGroups = field(default_factory=DummyAcolyteGroups)
    merchant_board_position: int = DEFAULT_TAXATION_BOARD_POSITION
    ship_position: int = 0
    completed_rounds: int = 0
    game_over: bool = False
    setup_sow_required: bool = False
    setup_sow_complete: bool = True
    setup_sow_completed_by: tuple[PlayerId, ...] = ()
    # The Confession Box round-end phase, which is a cursor and a tally, the same two things setup
    # sow keeps. `pending` is who has NOT yet been asked, in the order they will be, so the head of
    # it is whoever the table is waiting on; empty means the phase is over or never started.
    # `used` is who bought the two piety and has already paid for it.
    #
    # Both are cleared when the marker is awarded. They describe one round end and nothing else --
    # the piety they stand for is spent the instant it is counted, so carrying either into the next
    # round would lend a bonus to a decision it was never bought for.
    start_player_confession_pending: tuple[PlayerId, ...] = ()
    start_player_confession_used: tuple[PlayerId, ...] = ()
    building_market: tuple[str, ...] = ()
    building_availability: tuple[tuple[str, int], ...] = ()
    pilgrimage_rounds: tuple[int, ...] = ()
    turn: int = 0
    turn_progress: TurnProgress = field(default_factory=TurnProgress)

    def __post_init__(self) -> None:
        if len(self.players) < 2 or len(self.players) > 4:
            raise ValueError("Real player count must be between 2 and 4.")
        if self.turn < 0:
            raise ValueError("Turn cannot be negative.")

        if self.timing == TimingState():
            if self.turn != self.timing.absolute_turn:
                object.__setattr__(
                    self,
                    "timing",
                    replace(self.timing, absolute_turn=self.turn),
                )
        elif self.turn != self.timing.absolute_turn:
            object.__setattr__(self, "turn", self.timing.absolute_turn)

        if self.timing.turn_in_round >= len(self.players):
            raise ValueError("turn_in_round must be less than number of players.")
        if int(self.active_player) >= len(self.players):
            raise ValueError("active_player must be one of the real players in state.")
        if self.start_player is not None and int(self.start_player) >= len(self.players):
            raise ValueError("start_player must be one of the real players in state.")
        if self.first_player_marker is not None and int(self.first_player_marker) >= len(
            self.players
        ):
            raise ValueError("first_player_marker must be one of the real players in state.")
        if self.table_player_count not in (2, 3, 4):
            raise ValueError("table_player_count must be one of: 2, 3, 4.")
        if self.ship_position < 0:
            raise ValueError("ship_position cannot be negative.")
        if self.completed_rounds < 0:
            raise ValueError("completed_rounds cannot be negative.")
        # The Merchant rides the eight duty tiles and never enters the City, so 0 is not a
        # low value here -- it is an impossible one. This is also the guard that catches a state
        # built from a pre-rename scenario, whose values indexed a six-step path.
        if not 1 <= self.merchant_board_position <= len(DUTY_POSITIONS):
            raise ValueError(
                "merchant_board_position must be a duty tile, 1..8; the Merchant is never in "
                f"the City. Got {self.merchant_board_position}."
            )
        if len(set(self.setup_sow_completed_by)) != len(self.setup_sow_completed_by):
            raise ValueError("setup_sow_completed_by cannot contain duplicates.")
        for player_id in self.setup_sow_completed_by:
            if int(player_id) >= len(self.players):
                raise ValueError("setup_sow_completed_by contains unknown player id.")
        availability_keys = [building_id for building_id, _live_round in self.building_availability]
        if len(set(availability_keys)) != len(availability_keys):
            raise ValueError("building_availability cannot contain duplicate building ids.")
        live_round_to_building: dict[int, str] = {}
        for building_id, live_round in self.building_availability:
            if not building_id:
                raise ValueError("building_availability cannot contain empty building ids.")
            if live_round < 0:
                raise ValueError("building_availability live rounds cannot be negative.")
            already = live_round_to_building.get(live_round)
            if already is not None:
                raise ValueError(
                    "building_availability cannot place two buildings on one live round: "
                    f"round {live_round} has both {already!r} and {building_id!r}."
                )
            live_round_to_building[live_round] = building_id
        if len(set(self.pilgrimage_rounds)) != len(self.pilgrimage_rounds):
            raise ValueError("pilgrimage_rounds cannot contain duplicate entries.")
        for round_number in self.pilgrimage_rounds:
            if round_number < 1:
                raise ValueError("pilgrimage_rounds must be positive round numbers.")

    def player_state(self, player_id: PlayerId) -> PlayerState:
        return self.players[int(player_id)]

    def player_vector(self, player_id: PlayerId) -> PlayerVector:
        return self.player_state(player_id).workforce.mancala

    @property
    def acolytes(self) -> tuple[PlayerVector, ...]:
        """Backward-compatible acolyte vectors from workforce mancala pools."""
        return tuple(
            self.players[int(player_id)].workforce.mancala
            for player_id in (PlayerId(index) for index in range(self.player_count))
        )

    def total_acolytes(self, player_id: PlayerId) -> int:
        player_state = self.player_state(player_id)
        return total_acolytes(player_state.workforce) + player_state.special_activities.count

    @property
    def round_number(self) -> int:
        return self.timing.round_number

    @property
    def season_number(self) -> int:
        return self.timing.season_number

    @property
    def turn_in_round(self) -> int:
        return self.timing.turn_in_round

    @property
    def player_count(self) -> int:
        return len(self.players)

    @property
    def dummy_total(self) -> int:
        return self.dummy_acolytes.total_count

    def dummy_at_position(self, position: int) -> int:
        return self.dummy_acolytes.dummy_at_position(position)

    @property
    def used_buildings_this_turn(self) -> frozenset[str]:
        """Building ids already committed during this turn."""
        return self.turn_progress.used_buildings

    @property
    def used_buildings(self) -> frozenset[str]:
        """Short alias for the immutable per-turn building-use set."""
        return self.turn_progress.used_buildings

    @property
    def turn_events(self) -> tuple[GameEvent, ...]:
        """Events emitted by committed steps in the active turn."""
        return self.turn_progress.events

    @property
    def events(self) -> tuple[GameEvent, ...]:
        """The committed-step portion of the normal event log."""
        return self.turn_progress.events

    def with_timing(self, timing: TimingState) -> GameState:
        return replace(self, timing=timing, turn=timing.absolute_turn)

    def with_merchant_board_position(self, merchant_board_position: int) -> GameState:
        return replace(self, merchant_board_position=merchant_board_position)

    def with_ship_position(self, ship_position: int) -> GameState:
        return replace(self, ship_position=ship_position)

    def with_start_player(self, start_player: PlayerId) -> GameState:
        return replace(self, start_player=start_player)

    def with_first_player_marker(self, first_player_marker: PlayerId) -> GameState:
        """Hand the marker to a player. Deliberately no way to say "and the start player too".

        The two move on different occasions -- the marker at a round end, the start player when the
        holder names one -- and a helper that set both would make keeping them in step the easy
        thing to write. Keeping them in step is the bug.
        """
        return replace(self, first_player_marker=first_player_marker)

    def with_game_over(self, game_over: bool) -> GameState:
        return replace(self, game_over=game_over)

    def with_completed_rounds(self, completed_rounds: int) -> GameState:
        return replace(self, completed_rounds=completed_rounds)

    def with_building_market(self, building_market: tuple[str, ...]) -> GameState:
        return replace(self, building_market=building_market)

    def with_building_availability(
        self,
        building_availability: tuple[tuple[str, int], ...],
    ) -> GameState:
        return replace(self, building_availability=building_availability)

    def with_pilgrimage_rounds(
        self,
        pilgrimage_rounds: tuple[int, ...],
    ) -> GameState:
        return replace(self, pilgrimage_rounds=pilgrimage_rounds)

    def with_dummy_acolytes(self, dummy_acolytes: DummyAcolyteGroups) -> GameState:
        return replace(self, dummy_acolytes=dummy_acolytes)

    def with_start_player_confession_progress(
        self,
        *,
        pending: tuple[PlayerId, ...],
        used: tuple[PlayerId, ...],
    ) -> GameState:
        return replace(
            self,
            start_player_confession_pending=pending,
            start_player_confession_used=used,
        )

    def with_setup_sow_progress(
        self,
        *,
        setup_sow_complete: bool,
        setup_sow_completed_by: tuple[PlayerId, ...],
    ) -> GameState:
        return replace(
            self,
            setup_sow_complete=setup_sow_complete,
            setup_sow_completed_by=setup_sow_completed_by,
        )

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
        next_turn_in_round = self.timing.turn_in_round + 1
        next_round_number = self.timing.round_number
        if next_turn_in_round >= len(self.players):
            next_round_number += 1
            next_turn_in_round = 0
        next_player = PlayerId((int(self.active_player) + 1) % self.player_count)
        next_timing = TimingState(
            absolute_turn=self.timing.absolute_turn + 1,
            round_number=next_round_number,
            season_number=self.timing.season_number,
            turn_in_round=next_turn_in_round,
        )
        return replace(
            self,
            active_player=next_player,
            phase=TurnPhase.SOW,
            timing=next_timing,
            turn=next_timing.absolute_turn,
            turn_progress=TurnProgress(),
        )
