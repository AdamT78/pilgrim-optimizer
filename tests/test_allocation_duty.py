from __future__ import annotations

from dataclasses import replace

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import action_summary
from pilgrim.model.enums import PlayerId, TurnResolutionType
from pilgrim.model.special_activities import SpecialActivities
from pilgrim.rules.special_activities import apply_allocation_move, legal_allocation_moves
from pilgrim.rules.transition import apply_action, legal_actions


def _allocation_actions(scenario_path: str):
    scenario = load_scenario(scenario_path)
    actions = [
        action
        for action in legal_actions(scenario.state, scenario.config)
        if action.resolution is TurnResolutionType.ALLOCATION
    ]
    return scenario, actions


def test_allocation_move_legality_matrix() -> None:
    scenario = load_scenario("scenarios/allocation_abbey_to_special_activity_001.json")
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)

    moves = legal_allocation_moves(player_one)
    assert any(move.source == "abbey" and move.destination == "fields" for move in moves)
    assert all(move.source != "fields" or move.destination != "abbey" for move in moves)

    occupied_fields = replace(
        player_one,
        special_activities=SpecialActivities(fields=True),
    )
    occupied_moves = legal_allocation_moves(occupied_fields)
    assert any(move.source == "fields" and move.destination == "abbey" for move in occupied_moves)
    assert any(
        move.source == "fields" and move.destination == "engraver"
        for move in occupied_moves
    )
    assert not any(
        move.source == "fields" and move.destination == "fields" for move in occupied_moves
    )

    occupied_pair = replace(
        player_one,
        special_activities=SpecialActivities(fields=True, engraver=True),
    )
    occupied_pair_moves = legal_allocation_moves(occupied_pair)
    assert not any(
        move.source == "fields" and move.destination == "engraver"
        for move in occupied_pair_moves
    )


def test_allocation_to_city_is_not_generated() -> None:
    scenario, actions = _allocation_actions("scenarios/allocation_abbey_to_special_activity_001.json")
    assert actions
    for action in actions:
        summary = action_summary(action, scenario.config)
        assert "target: city" not in summary
        assert all(move.source != "city" and move.destination != "city" for move in action.allocation_moves)


def test_duty_value_one_generates_only_one_move_actions() -> None:
    _scenario, actions = _allocation_actions("scenarios/allocation_abbey_to_special_activity_001.json")
    assert actions
    assert all(len(action.allocation_moves) == 1 for action in actions)


def test_duty_value_two_generates_one_and_two_move_actions() -> None:
    _scenario, actions = _allocation_actions("scenarios/allocation_multi_move_001.json")
    assert any(len(action.allocation_moves) == 1 for action in actions)
    assert any(len(action.allocation_moves) == 2 for action in actions)


def test_duty_value_two_step_legality_is_enforced_during_generation() -> None:
    scenario, actions = _allocation_actions("scenarios/allocation_multi_move_001.json")
    base_player = scenario.state.player_state(PlayerId.PLAYER_ONE)

    for action in actions:
        if len(action.allocation_moves) < 2:
            continue
        rolling_state = base_player
        for move in action.allocation_moves:
            legal_now = legal_allocation_moves(rolling_state)
            assert move in legal_now
            rolling_state = apply_allocation_move(rolling_state, move)


def test_allocation_multi_move_two_abbey_transfers_consume_two_abbey() -> None:
    scenario, actions = _allocation_actions("scenarios/allocation_multi_move_001.json")
    two_abbey_move_action = next(
        action
        for action in actions
        if len(action.allocation_moves) == 2
        and action.allocation_moves[0].source == "abbey"
        and action.allocation_moves[1].source == "abbey"
    )

    before = scenario.state.player_state(PlayerId.PLAYER_ONE)
    result = apply_action(scenario.state, two_abbey_move_action, scenario.config)
    after = result.state.player_state(PlayerId.PLAYER_ONE)

    assert after.workforce.abbey == before.workforce.abbey - 2
    assert after.special_activities.fields is True
    assert after.special_activities.road_engineer is True


def test_allocation_special_to_abbey_then_abbey_to_special_is_legal() -> None:
    scenario = load_scenario("scenarios/allocation_multi_move_001.json")
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    mutated_player_one = replace(
        player_one,
        workforce=replace(player_one.workforce, abbey=0),
        special_activities=SpecialActivities(fields=True),
    )
    mutated_state = scenario.state.with_player_state(PlayerId.PLAYER_ONE, mutated_player_one)

    actions = [
        action
        for action in legal_actions(mutated_state, scenario.config)
        if action.resolution is TurnResolutionType.ALLOCATION and len(action.allocation_moves) == 2
    ]
    sequence_action = next(
        action
        for action in actions
        if action.allocation_moves[0].source == "fields"
        and action.allocation_moves[0].destination == "abbey"
        and action.allocation_moves[1].source == "abbey"
        and action.allocation_moves[1].destination == "engraver"
    )

    result = apply_action(mutated_state, sequence_action, scenario.config)
    after = result.state.player_state(PlayerId.PLAYER_ONE)
    assert after.special_activities.fields is False
    assert after.special_activities.engraver is True
    assert after.workforce.abbey == 0


def test_allocation_application_variants_and_recall() -> None:
    abbey_scenario, abbey_actions = _allocation_actions(
        "scenarios/allocation_abbey_to_special_activity_001.json"
    )
    abbey_action = abbey_actions[0]
    before_abbey = abbey_scenario.state.player_state(PlayerId.PLAYER_ONE)
    abbey_result = apply_action(abbey_scenario.state, abbey_action, abbey_scenario.config)
    after_abbey = abbey_result.state.player_state(PlayerId.PLAYER_ONE)
    north_west = abbey_scenario.config.board.index_for_name("north_west")
    assert after_abbey.workforce.abbey == before_abbey.workforce.abbey - 1
    assert after_abbey.special_activities.fields is True
    assert after_abbey.workforce.mancala[0] == before_abbey.workforce.mancala[0] + 1
    assert after_abbey.workforce.mancala[north_west] == 0
    assert abbey_scenario.state.total_acolytes(PlayerId.PLAYER_ONE) == abbey_result.state.total_acolytes(
        PlayerId.PLAYER_ONE
    )

    to_abbey_scenario, to_abbey_actions = _allocation_actions(
        "scenarios/allocation_special_activity_to_abbey_001.json"
    )
    to_abbey_result = apply_action(
        to_abbey_scenario.state,
        to_abbey_actions[0],
        to_abbey_scenario.config,
    )
    to_abbey_after = to_abbey_result.state.player_state(PlayerId.PLAYER_ONE)
    assert to_abbey_after.special_activities.fields is False
    assert to_abbey_after.workforce.abbey == 1

    to_special_scenario, to_special_actions = _allocation_actions(
        "scenarios/allocation_special_activity_to_special_activity_001.json"
    )
    to_special_result = apply_action(
        to_special_scenario.state,
        to_special_actions[0],
        to_special_scenario.config,
    )
    to_special_after = to_special_result.state.player_state(PlayerId.PLAYER_ONE)
    assert to_special_after.special_activities.fields is False
    assert to_special_after.special_activities.engraver is True
    assert to_special_after.workforce.abbey == 0


def test_allocation_minority_silver_cost_applies() -> None:
    scenario = load_scenario("scenarios/allocation_abbey_to_special_activity_001.json")
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    player_two = scenario.state.player_state(PlayerId.PLAYER_TWO)
    minority_state = scenario.state.with_player_state(
        PlayerId.PLAYER_TWO,
        replace(
            player_two,
            workforce=replace(player_two.workforce, mancala=(0, 0, 0, 0, 0, 0, 0, 0, 2)),
        ),
    )
    action = next(
        action
        for action in legal_actions(minority_state, scenario.config)
        if action.resolution is TurnResolutionType.ALLOCATION
    )
    result = apply_action(minority_state, action, scenario.config)
    after = result.state.player_state(PlayerId.PLAYER_ONE)

    assert after.resources.silver == player_one.resources.silver - 1
