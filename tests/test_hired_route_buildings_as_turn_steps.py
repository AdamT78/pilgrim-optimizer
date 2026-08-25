from __future__ import annotations

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import EndTurnAction, FullTurnAction, action_id
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules.transition import (
    apply_action,
    apply_turn_step,
    full_turn_actions,
    legal_actions,
    turn_steps,
)


ROUTE_BUILDINGS = ("kogge", "cloisters")


def _route_step(state, config, *, building_id: str):
    return next(step for step in turn_steps(state, config) if step.building_id == building_id)


def _reversed_kogge_actions(state, config) -> list[FullTurnAction]:
    board = config.board
    city = board.index_for_name("city")
    return [
        action
        for action in legal_actions(state, config)
        if isinstance(action, FullTurnAction)
        and action.origin == city
        and action.route
        and board.positions[action.route[0]] in {"east", "west"}
    ]


def _state_at_yellows_opening_after_reds_settled_turn(scenario):
    """The hand-played movement_2p prefix where Yellow can hire Red's Cloisters."""
    board = scenario.config.board
    red_action = next(
        action
        for action in legal_actions(scenario.state, scenario.config)
        if isinstance(action, FullTurnAction)
        and action.origin == board.index_for_name("city")
        and action.route == (board.index_for_name("north"),)
        and action.selected_duty == board.index_for_name("south_east")
        and action.resolution is TurnResolutionType.CONSTRUCT_ROAD_DEFERRED
    )
    after_red_action = apply_action(scenario.state, red_action, scenario.config).state
    return apply_action(after_red_action, EndTurnAction(), scenario.config).state


def test_hired_kogge_routes_only_appear_after_its_committed_hire() -> None:
    scenario = load_scenario("scenarios/kogge_hire_opponent_city_to_west_001.json")
    step = _route_step(scenario.state, scenario.config, building_id="kogge")

    assert not _reversed_kogge_actions(scenario.state, scenario.config)

    after_hire = apply_turn_step(scenario.state, scenario.config, step)
    actions = _reversed_kogge_actions(after_hire, scenario.config)

    assert actions
    assert all(action.sow_route_building_id == "kogge" for action in actions)
    assert all(action.sow_route_building_source is None for action in actions)
    assert all(action.hire_payments == () for action in actions)


def test_hired_cloisters_skip_routes_only_appear_after_its_committed_hire() -> None:
    scenario = load_scenario("scenarios/playtest/movement_2p.json")
    yellow_opening = _state_at_yellows_opening_after_reds_settled_turn(scenario)

    before_hire = [
        action
        for action in legal_actions(yellow_opening, scenario.config)
        if isinstance(action, FullTurnAction) and action.sow_route_omitted_location is not None
    ]
    after_hire = apply_turn_step(
        yellow_opening,
        scenario.config,
        _route_step(yellow_opening, scenario.config, building_id="cloisters"),
    )
    after_hire_skip_routes = [
        action
        for action in legal_actions(after_hire, scenario.config)
        if isinstance(action, FullTurnAction) and action.sow_route_omitted_location is not None
    ]

    assert not before_hire, "unhired Cloisters must not generate skip routes"
    assert len(after_hire_skip_routes) == 1_658, "hired Cloisters must generate its skip routes"


def test_route_hire_step_pays_the_named_opponent() -> None:
    scenario = load_scenario("scenarios/kogge_hire_opponent_city_to_west_001.json")
    player = scenario.state.active_player
    owner = PlayerId.PLAYER_TWO if player is PlayerId.PLAYER_ONE else PlayerId.PLAYER_ONE
    before_owner_wheat = scenario.state.player_state(owner).resources.wheat

    after_hire = apply_turn_step(
        scenario.state,
        scenario.config,
        _route_step(scenario.state, scenario.config, building_id="kogge"),
    )
    hire_event = next(
        event for event in after_hire.turn_progress.events if event.event_type is EventType.BUILDING_HIRED
    )

    assert dict(hire_event.details)["payee"] == "player_two"
    assert after_hire.player_state(owner).resources.wheat == before_owner_wheat + 1


def test_market_route_hire_pays_the_bank() -> None:
    scenario = load_scenario("scenarios/kogge_cloisters_hire_both_market_001.json")

    after_hire = apply_turn_step(
        scenario.state,
        scenario.config,
        _route_step(scenario.state, scenario.config, building_id="kogge"),
    )
    hire_event = next(
        event for event in after_hire.turn_progress.events if event.event_type is EventType.BUILDING_HIRED
    )

    assert dict(hire_event.details)["payee"] == "bank"


def test_owned_route_buildings_are_free_immediate_and_offer_no_step() -> None:
    scenario = load_scenario("scenarios/kogge_cloisters_own_own_skip_city_001.json")
    actions = legal_actions(scenario.state, scenario.config)

    assert not [step for step in turn_steps(scenario.state, scenario.config) if step.building_id in ROUTE_BUILDINGS]
    assert any(action.sow_route_building_id == "kogge" for action in actions)
    assert any(action.sow_route_building_id == "cloisters" for action in actions)


def test_both_hired_route_buildings_can_be_paid_for_separately_in_one_turn() -> None:
    scenario = load_scenario("scenarios/kogge_cloisters_hire_both_opponent_001.json")
    player = scenario.state.active_player
    owner = PlayerId.PLAYER_TWO if player is PlayerId.PLAYER_ONE else PlayerId.PLAYER_ONE
    before_owner_wheat = scenario.state.player_state(owner).resources.wheat

    after_kogge = apply_turn_step(
        scenario.state,
        scenario.config,
        _route_step(scenario.state, scenario.config, building_id="kogge"),
    )
    after_both = apply_turn_step(
        after_kogge,
        scenario.config,
        _route_step(after_kogge, scenario.config, building_id="cloisters"),
    )

    assert after_both.turn_progress.used_buildings >= set(ROUTE_BUILDINGS)
    assert after_both.player_state(owner).resources.wheat == before_owner_wheat + 2
    assert any(
        action.sow_route_building_id == "kogge"
        and action.sow_route_secondary_building_id == "cloisters"
        for action in legal_actions(after_both, scenario.config)
    )


def test_route_hire_steps_close_when_resolution_is_committed() -> None:
    scenario = load_scenario("scenarios/kogge_cloisters_hire_both_market_001.json")
    action = legal_actions(scenario.state, scenario.config)[0]
    resolved = apply_action(scenario.state, action, scenario.config).state

    assert resolved.turn_progress.resolution_committed
    assert not [step for step in turn_steps(resolved, scenario.config) if step.building_id in ROUTE_BUILDINGS]


def test_composed_actions_do_not_carry_hired_route_sources_or_action_ids() -> None:
    scenario = load_scenario("scenarios/kogge_cloisters_hire_both_market_001.json")
    after_hire = apply_turn_step(
        scenario.state,
        scenario.config,
        _route_step(scenario.state, scenario.config, building_id="kogge"),
    )
    actions = [
        action
        for action in full_turn_actions(after_hire, scenario.config)
        if isinstance(action, FullTurnAction)
    ]

    assert actions
    assert all(
        action.sow_route_building_source in {None, "own_active"}
        and action.sow_route_secondary_building_source in {None, "own_active"}
        for action in actions
    )
    kogge_actions = [action for action in actions if action.sow_route_building_id == "kogge"]
    assert kogge_actions
    assert all(":from:market" not in action_id(action) for action in kogge_actions)
    assert all(":secondary_from:market" not in action_id(action) for action in kogge_actions)
