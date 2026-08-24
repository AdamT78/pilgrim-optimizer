from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Iterable

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import (
    EndTurnAction,
    FullTurnAction,
    GameAction,
    StartPlayerConfessionBoxAction,
    StartPlayerSelectionAction,
    action_id,
)
from pilgrim.model.config import GameConfig
from pilgrim.model.enums import EventType, PlayerId, TurnPhase, TurnResolutionType
from pilgrim.model.events import GameEvent
from pilgrim.model.state import GameState
from pilgrim.rules.buildings import future_buildings, is_building_live, live_buildings
from pilgrim.rules.transition import TransitionResult, apply_action, legal_actions

Selector = Callable[[GameState, tuple[GameAction, ...]], GameAction]


@dataclass(frozen=True, slots=True)
class ScriptedStep:
    step: int
    state_before: GameState
    legal_action_ids: tuple[str, ...]
    selected_action: GameAction
    result: TransitionResult

    @property
    def selected_action_id(self) -> str:
        return action_id(self.selected_action)


def find_action(
    actions: Iterable[GameAction],
    predicate: Callable[[GameAction], bool],
    label: str,
) -> GameAction:
    matches = [candidate for candidate in actions if predicate(candidate)]
    if not matches:
        available = ", ".join(action_id(candidate) for candidate in actions) or "<none>"
        raise AssertionError(f"Could not find action for '{label}'. Available: {available}")
    return min(matches, key=action_id)


def select_action(
    label: str,
    predicate: Callable[[GameAction], bool],
) -> Selector:
    return lambda _state, actions: find_action(actions, predicate, label)


def select_tithe() -> Selector:
    return select_action(
        "tithe",
        lambda candidate: (
            isinstance(candidate, FullTurnAction)
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )


def whoever_holds_the_marker_keeps_it(state: GameState) -> PlayerId:
    """One way a table could answer, chosen here so these scripts stay about turns.

    A SCRIPT, NOT A RULE. The holder is free to name anyone, and the tests for that live with the
    rule. Fixing an answer here keeps a six-turn sequencing test from also being a test of who
    begins each round, and picking the holder is the answer that leaves the seating alone.
    """
    return state.active_player


def apply_scripted_turns(
    initial_state: GameState,
    config: GameConfig,
    selectors: Iterable[Selector],
    *,
    who_begins: Callable[[GameState], PlayerId] = whoever_holds_the_marker_keeps_it,
) -> tuple[ScriptedStep, ...]:
    steps: list[ScriptedStep] = []
    state = initial_state
    for step_index, selector in enumerate(selectors, start=1):
        # A round end stops the table on the marker holder. Answered here rather than counted as a
        # scripted step, so that one selector still means one player turn and the round numbers
        # these tests assert keep meaning what they did. What the answer produces is asserted where
        # the rule is tested, not here.
        if state.phase is TurnPhase.START_PLAYER_SELECTION:
            state = apply_action(
                state,
                StartPlayerSelectionAction(chosen_start_player=who_begins(state)),
                config,
            ).state
        actions = legal_actions(state, config)
        if not actions:
            raise AssertionError(f"No legal actions at scripted step {step_index}.")

        legal_ids = tuple(action_id(candidate) for candidate in actions)
        if len(set(legal_ids)) != len(legal_ids):
            raise AssertionError(f"Duplicate action IDs found at scripted step {step_index}.")

        selected_action = selector(state, actions)
        selected_id = action_id(selected_action)
        if selected_id not in legal_ids:
            raise AssertionError(
                f"Selector returned action outside legal set at step {step_index}: {selected_id}"
            )

        result = apply_action(state, selected_action, config)
        if result.state.turn_progress.resolution_committed:
            passed = apply_action(result.state, EndTurnAction(), config)
            result = TransitionResult(
                state=passed.state,
                events=(*result.events, *passed.events),
            )
        # The Confession Box questions belong to the turn that ended the round rather than to the
        # turn after it. Declined here -- the answer that changes nothing -- and folded into this
        # step's events, so a script that never mentions the boxes still sees the round end it
        # always saw, marker and all, in the step that caused it.
        while result.state.phase is TurnPhase.START_PLAYER_CONFESSION:
            answered = apply_action(result.state, StartPlayerConfessionBoxAction(use=False), config)
            result = TransitionResult(
                state=answered.state,
                events=(*result.events, *answered.events),
            )
        steps.append(
            ScriptedStep(
                step=step_index,
                state_before=state,
                legal_action_ids=legal_ids,
                selected_action=selected_action,
                result=result,
            )
        )
        state = result.state
    return tuple(steps)


def event_types(events: tuple[GameEvent, ...]) -> tuple[EventType, ...]:
    return tuple(event.event_type for event in events)


def assert_event_order(
    events: tuple[GameEvent, ...], expected_order: tuple[EventType, ...]
) -> None:
    search_from = 0
    for expected_event in expected_order:
        for index in range(search_from, len(events)):
            if events[index].event_type is expected_event:
                search_from = index + 1
                break
        else:
            raise AssertionError(f"Missing expected event order item: {expected_event.value}")


def branching_trace(
    initial_state: GameState,
    config: GameConfig,
    selectors: Iterable[Selector],
) -> tuple[dict[str, object], ...]:
    scripted = apply_scripted_turns(initial_state, config, selectors)
    return tuple(
        {
            "step": entry.step,
            "absolute_turn": entry.state_before.timing.absolute_turn,
            "round_number": entry.state_before.timing.round_number,
            "turn_in_round": entry.state_before.timing.turn_in_round,
            "active_player": entry.state_before.active_player.name.lower(),
            "legal_action_count": len(entry.legal_action_ids),
            "legal_action_ids": entry.legal_action_ids,
            "selected_action_id": entry.selected_action_id,
        }
        for entry in scripted
    )


def test_scripted_basic_two_player_round_flow_over_six_turns() -> None:
    scenario = load_scenario("scenarios/alms_sandbox_001.json")
    selectors = tuple(select_tithe() for _ in range(6))
    scripted = apply_scripted_turns(scenario.state, scenario.config, selectors)

    assert scripted[0].state_before.active_player is PlayerId.PLAYER_ONE
    assert scripted[1].state_before.active_player is PlayerId.PLAYER_TWO
    assert [step.result.state.timing.round_number for step in scripted] == [1, 2, 2, 3, 3, 4]
    # The Merchant opens on Taxation, which this arrangement puts at north_west (8), and its
    # first round-end step carries it round to north (1). The old sequence opened at 0 because
    # Taxation was the first entry of a six-step list; the walk's shape is unchanged, not its start.
    assert [step.result.state.merchant_board_position for step in scripted] == [8, 1, 1, 2, 2, 3]

    round_end_steps = 0
    for step in scripted:
        step_events = event_types(step.result.events)
        assert EventType.INVARIANT_CHECK in step_events
        if EventType.ROUND_ADVANCE in step_events:
            round_end_steps += 1
            assert EventType.MERCHANT_ADVANCE in step_events
            assert EventType.START_PLAYER_MARKER in step_events
            assert step.result.state.timing.turn_in_round == 0
            # Stopped on the marker holder rather than run on into the next round.
            assert step.result.state.phase is TurnPhase.START_PLAYER_SELECTION
        else:
            assert EventType.MERCHANT_ADVANCE not in step_events
            assert EventType.START_PLAYER_MARKER not in step_events

    assert round_end_steps == 3


def test_scripted_resource_cap_applies_only_on_round_end() -> None:
    scenario = load_scenario("scenarios/round_end_excess_caps_001.json")
    starting_state = replace(
        scenario.state,
        active_player=PlayerId.PLAYER_ONE,
        timing=replace(
            scenario.state.timing,
            absolute_turn=2,
            turn_in_round=0,
        ),
    )
    scripted = apply_scripted_turns(
        starting_state,
        scenario.config,
        (select_tithe(), select_tithe()),
    )

    first_turn_events = event_types(scripted[0].result.events)
    second_turn_events = event_types(scripted[1].result.events)
    assert EventType.EXCESS_RESOURCE_CAP not in first_turn_events
    assert EventType.EXCESS_RESOURCE_CAP in second_turn_events

    capped_state = scripted[1].result.state
    player_one = capped_state.player_state(PlayerId.PLAYER_ONE)
    player_two = capped_state.player_state(PlayerId.PLAYER_TWO)
    assert player_one.resources.stone == 6
    assert player_one.resources.wheat == 6
    assert player_one.resources.silver == 9
    assert player_two.resources.stone == 6
    assert player_two.resources.wheat == 6
    assert player_two.resources.silver == 3

    cap_events = [
        event
        for event in scripted[1].result.events
        if event.event_type is EventType.EXCESS_RESOURCE_CAP
    ]
    assert len(cap_events) == 2


def test_scripted_season_end_sequence_runs_in_expected_order_after_two_turns() -> None:
    scenario = load_scenario("scenarios/alms_season_end_unique_leader_001.json")
    pre_round_end_state = replace(
        scenario.state,
        active_player=PlayerId.PLAYER_ONE,
        timing=replace(
            scenario.state.timing,
            absolute_turn=16,
            turn_in_round=0,
        ),
    )
    scripted = apply_scripted_turns(
        pre_round_end_state,
        scenario.config,
        (select_tithe(), select_tithe()),
    )

    assert EventType.ALMS_SEASON_END not in event_types(scripted[0].result.events)
    season_turn_events = scripted[1].result.events
    assert_event_order(
        season_turn_events,
        (
            EventType.ROUND_ADVANCE,
            EventType.ALMS_SEASON_END,
            EventType.ALMS_SEASON_REWARD,
            EventType.ALMS_RESET,
            EventType.MERCHANT_ADVANCE,
            # The turn advances to the first player owed a Confession Box question, and the marker
            # is awarded by whoever answers last -- so the marker now falls on the far side of the
            # advance rather than before it.
            EventType.TURN_ADVANCE,
            EventType.START_PLAYER_MARKER,
        ),
    )

    season_state = scripted[1].result.state
    assert season_state.timing.round_number == 10
    assert season_state.timing.season_number == 2
    assert season_state.phase is TurnPhase.START_PLAYER_SELECTION
    assert season_state.player_state(PlayerId.PLAYER_ONE).alms_position == 0
    assert season_state.player_state(PlayerId.PLAYER_TWO).alms_position == 0


def test_scripted_building_availability_becomes_live_as_round_advances() -> None:
    scenario = load_scenario("scenarios/building_availability_future_001.json")
    initial_state = scenario.state
    initial_availability = initial_state.building_availability
    assert is_building_live(initial_state, "chapel") is False
    assert ("chapel", 4) in future_buildings(initial_state)

    scripted = apply_scripted_turns(
        initial_state,
        scenario.config,
        (select_tithe(), select_tithe()),
    )

    assert is_building_live(scripted[0].result.state, "chapel") is False
    round_four_state = scripted[1].result.state
    assert round_four_state.timing.round_number == 4
    assert is_building_live(round_four_state, "chapel") is True
    assert "chapel" in live_buildings(round_four_state)
    assert all(building_id != "chapel" for building_id, _ in future_buildings(round_four_state))
    assert round_four_state.building_availability == initial_availability


def test_scripted_branching_trace_is_deterministic_and_has_unique_action_ids() -> None:
    scenario = load_scenario("scenarios/alms_sandbox_001.json")
    selectors = tuple(select_tithe() for _ in range(6))
    trace_a = branching_trace(scenario.state, scenario.config, selectors)
    trace_b = branching_trace(scenario.state, scenario.config, selectors)

    assert trace_a == trace_b
    assert len(trace_a) == 6
    for row in trace_a:
        legal_action_ids = row["legal_action_ids"]
        assert isinstance(legal_action_ids, tuple)
        assert row["legal_action_count"] > 0
        assert len(legal_action_ids) == len(set(legal_action_ids))
        assert row["selected_action_id"] in legal_action_ids


def test_library_end_turn_relocation_persists_across_next_player_turn() -> None:
    scenario = load_scenario("scenarios/library_active_city_to_duty_001.json")
    north = scenario.config.board.index_for_name("north")
    player_two = scenario.state.player_state(PlayerId.PLAYER_TWO)
    state_with_opponent_action = scenario.state.with_player_state(
        PlayerId.PLAYER_TWO,
        replace(
            player_two,
            workforce=replace(
                player_two.workforce,
                mancala=(0, 0, 0, 0, 1, 0, 0, 0, 0),
            ),
        ),
    )
    scripted = apply_scripted_turns(
        state_with_opponent_action,
        scenario.config,
        (
            select_action(
                "library produce wheat relocate to north",
                lambda candidate: (
                    isinstance(candidate, FullTurnAction)
                    and candidate.resolution is TurnResolutionType.PRODUCE_WHEAT
                    and candidate.end_turn_building_id == "library"
                    and candidate.end_turn_relocation_to == north
                ),
            ),
            select_tithe(),
        ),
    )

    assert EventType.END_TURN_RELOCATION in event_types(scripted[0].result.events)
    assert scripted[0].result.state.player_vector(PlayerId.PLAYER_ONE)[north] == 1
    assert scripted[1].result.state.player_vector(PlayerId.PLAYER_ONE)[north] == 1
