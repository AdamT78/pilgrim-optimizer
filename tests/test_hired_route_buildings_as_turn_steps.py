from __future__ import annotations

from pathlib import Path

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import FullTurnAction
from pilgrim.model.enums import EventType, PlayerId
from pilgrim.rules import transition as transition_module
from pilgrim.rules.transition import apply_action, legal_actions, turn_steps

ROUTE_BUILDINGS = ("kogge", "cloisters")


def _route_actions(state, config, *, building_id: str) -> list[FullTurnAction]:
    return [
        action
        for action in legal_actions(state, config)
        if isinstance(action, FullTurnAction)
        and transition_module._action_has_route_building(action, building_id)
    ]


def _combined_kogge_route_requires_kogge(action: FullTurnAction, config) -> bool:
    return (
        action.sow_route_building_id == "kogge"
        and action.sow_route_secondary_building_id == "cloisters"
        and action.sow_route_omitted_location is not None
        and transition_module._is_legal_route_with_kogge_and_cloisters_skip(
            origin=action.origin,
            route=action.route,
            board=config.board,
            omitted_location=action.sow_route_omitted_location,
        )
    )


def test_route_hire_is_carried_by_the_sow_action_and_not_a_turn_step() -> None:
    scenario = load_scenario("scenarios/kogge_hire_opponent_city_to_west_001.json")

    assert not [
        step
        for step in turn_steps(scenario.state, scenario.config)
        if step.building_id in ROUTE_BUILDINGS
    ]
    actions = _route_actions(scenario.state, scenario.config, building_id="kogge")

    assert actions
    assert all(action.sow_route_building_source == "player_two" for action in actions)
    assert all(action.hire_payments == (("kogge", "wheat"),) for action in actions)


def test_route_hire_pays_only_when_its_action_is_confirmed_and_marks_the_tile_used() -> None:
    scenario = load_scenario("scenarios/kogge_hire_opponent_city_to_west_001.json")
    player = scenario.state.active_player
    owner = PlayerId.PLAYER_TWO if player is PlayerId.PLAYER_ONE else PlayerId.PLAYER_ONE
    before_owner_wheat = scenario.state.player_state(owner).resources.wheat
    action = _route_actions(scenario.state, scenario.config, building_id="kogge")[0]

    result = apply_action(scenario.state, action, scenario.config)
    hire_event = next(
        event for event in result.events if event.event_type is EventType.BUILDING_HIRED
    )

    assert scenario.state.player_state(owner).resources.wheat == before_owner_wheat
    assert dict(hire_event.details)["payee"] == "player_two"
    assert result.state.player_state(owner).resources.wheat == before_owner_wheat + 1
    assert "kogge" in result.state.turn_progress.used_buildings


def test_combined_route_pays_each_hired_building_with_the_confirmed_action() -> None:
    scenario = load_scenario("scenarios/kogge_cloisters_hire_both_market_001.json")
    action = next(
        action
        for action in legal_actions(scenario.state, scenario.config)
        if isinstance(action, FullTurnAction)
        and action.sow_route_building_id == "kogge"
        and action.sow_route_secondary_building_id == "cloisters"
    )

    result = apply_action(scenario.state, action, scenario.config)
    hire_events = [event for event in result.events if event.event_type is EventType.BUILDING_HIRED]

    assert action.hire_payments == (("cloisters", "wheat"), ("kogge", "wheat"))
    assert {dict(event.details)["building_id"] for event in hire_events} == set(ROUTE_BUILDINGS)
    assert result.state.turn_progress.used_buildings >= set(ROUTE_BUILDINGS)


def test_route_building_fields_are_present_if_and_only_if_the_route_requires_them() -> None:
    """No route action can pay for a permission it does not actually consume."""
    checked = 0
    for scenario_path in sorted(Path("scenarios").rglob("*.json")):
        scenario = load_scenario(scenario_path)
        for action in legal_actions(scenario.state, scenario.config):
            if not isinstance(action, FullTurnAction):
                continue
            requires_kogge = transition_module._route_requires_kogge(action, scenario.config)
            requires_kogge = requires_kogge or _combined_kogge_route_requires_kogge(
                action, scenario.config
            )
            requires_cloisters = action.sow_route_omitted_location is not None
            assert transition_module._action_has_route_building(action, "kogge") is requires_kogge
            assert (
                transition_module._action_has_route_building(action, "cloisters")
                is requires_cloisters
            )
            route_hire_sources = {
                building_id: source_label
                for building_id, source_label in (
                    (action.sow_route_building_id, action.sow_route_building_source),
                    (
                        action.sow_route_secondary_building_id,
                        action.sow_route_secondary_building_source,
                    ),
                )
                if building_id is not None
            }
            payments = dict(action.hire_payments)
            assert {
                building_id
                for building_id, source_label in route_hire_sources.items()
                if source_label not in (None, "own_active")
            } == set(payments) & set(ROUTE_BUILDINGS)
            checked += 1

    # This is every current initial corpus action, including playtests; keep the property a
    # population walk if future action compaction changes the exact count.
    assert checked >= 7_000, f"only {checked} corpus actions were checked"
