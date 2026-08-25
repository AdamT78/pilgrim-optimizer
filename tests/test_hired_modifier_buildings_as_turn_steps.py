from __future__ import annotations

from dataclasses import replace

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import BuildingActivationStep, FullTurnAction
from pilgrim.model.enums import EventType, PlayerId
from pilgrim.rules.transition import apply_action, apply_turn_step, legal_actions, turn_steps


def _activation_step(state, config, building_id: str) -> BuildingActivationStep:
    return next(
        step
        for step in turn_steps(state, config)
        if isinstance(step, BuildingActivationStep) and step.building_id == building_id
    )


def _building_hires(state):
    return [event for event in state.turn_progress.events if event.event_type is EventType.BUILDING_HIRED]


def _assert_opponent_hire_payment(before, after, *, building_id: str) -> None:
    event = next(event for event in _building_hires(after) if dict(event.details)["building_id"] == building_id)
    details = dict(event.details)
    assert details["payee"] == "player_two"
    resource = details["resource"]
    assert getattr(after.player_state(PlayerId.PLAYER_TWO).resources, resource) == (
        getattr(before.player_state(PlayerId.PLAYER_TWO).resources, resource) + 1
    )


def _assert_market_hire_pays_bank(after, *, building_id: str) -> None:
    event = next(event for event in _building_hires(after) if dict(event.details)["building_id"] == building_id)
    details = dict(event.details)
    assert details["source"] == "market"
    assert details["payee"] == "bank"


def _pre_resolution_state(scenario):
    return replace(
        scenario.state,
        turn_progress=replace(scenario.state.turn_progress, resolution_committed=True),
    )


def test_hired_scriptorium_only_changes_actions_after_its_step() -> None:
    scenario = load_scenario("scenarios/scriptorium_hire_opponent_majority_selected_duty_001.json")

    assert not any(
        action.effective_acolyte_building_id == "scriptorium"
        for action in legal_actions(scenario.state, scenario.config)
        if isinstance(action, FullTurnAction)
    )

    after = apply_turn_step(
        scenario.state,
        scenario.config,
        _activation_step(scenario.state, scenario.config, "scriptorium"),
    )
    enabled = [
        action
        for action in legal_actions(after, scenario.config)
        if isinstance(action, FullTurnAction) and action.effective_acolyte_building_id == "scriptorium"
    ]
    assert enabled
    assert all(action.effective_acolyte_building_source is None for action in enabled)


def test_hired_scriptorium_pays_its_opponent_and_market_sources() -> None:
    opponent = load_scenario("scenarios/scriptorium_hire_opponent_majority_selected_duty_001.json")
    after_opponent = apply_turn_step(
        opponent.state,
        opponent.config,
        _activation_step(opponent.state, opponent.config, "scriptorium"),
    )
    _assert_opponent_hire_payment(opponent.state, after_opponent, building_id="scriptorium")

    market = load_scenario("scenarios/scriptorium_hire_market_majority_selected_duty_001.json")
    after_market = apply_turn_step(
        market.state,
        market.config,
        _activation_step(market.state, market.config, "scriptorium"),
    )
    _assert_market_hire_pays_bank(after_market, building_id="scriptorium")


def test_owned_scriptorium_is_free_immediate_and_step_free() -> None:
    scenario = load_scenario("scenarios/scriptorium_active_majority_selected_duty_001.json")

    assert not [step for step in turn_steps(scenario.state, scenario.config) if step.building_id == "scriptorium"]
    assert any(
        action.effective_acolyte_building_id == "scriptorium"
        and action.effective_acolyte_building_source == "own_active"
        for action in legal_actions(scenario.state, scenario.config)
        if isinstance(action, FullTurnAction)
    )


def test_unaffordable_scriptorium_hire_is_not_offered() -> None:
    scenario = load_scenario("scenarios/scriptorium_insufficient_hire_resource_001.json")

    assert not [step for step in turn_steps(scenario.state, scenario.config) if step.building_id == "scriptorium"]


def test_scriptorium_hire_window_closes_after_resolution() -> None:
    scenario = load_scenario("scenarios/scriptorium_hire_opponent_majority_selected_duty_001.json")

    assert not [step for step in turn_steps(_pre_resolution_state(scenario), scenario.config) if step.building_id == "scriptorium"]


def test_hired_customs_house_only_changes_actions_after_its_step() -> None:
    scenario = load_scenario("scenarios/customs_house_hire_opponent_taxation_majority_001.json")

    assert not any(
        action.taxation_majority_building_id == "customs_house"
        for action in legal_actions(scenario.state, scenario.config)
        if isinstance(action, FullTurnAction)
    )

    after = apply_turn_step(
        scenario.state,
        scenario.config,
        _activation_step(scenario.state, scenario.config, "customs_house"),
    )
    enabled = [
        action
        for action in legal_actions(after, scenario.config)
        if isinstance(action, FullTurnAction) and action.taxation_majority_building_id == "customs_house"
    ]
    assert enabled
    assert all(action.taxation_majority_building_source is None for action in enabled)


def test_hired_customs_house_pays_its_opponent_and_market_sources() -> None:
    opponent = load_scenario("scenarios/customs_house_hire_opponent_taxation_majority_001.json")
    after_opponent = apply_turn_step(
        opponent.state,
        opponent.config,
        _activation_step(opponent.state, opponent.config, "customs_house"),
    )
    _assert_opponent_hire_payment(opponent.state, after_opponent, building_id="customs_house")

    market = load_scenario("scenarios/customs_house_hire_market_taxation_majority_001.json")
    after_market = apply_turn_step(
        market.state,
        market.config,
        _activation_step(market.state, market.config, "customs_house"),
    )
    _assert_market_hire_pays_bank(after_market, building_id="customs_house")


def test_owned_customs_house_is_free_immediate_and_step_free() -> None:
    scenario = load_scenario("scenarios/customs_house_active_taxation_majority_001.json")

    assert not [step for step in turn_steps(scenario.state, scenario.config) if step.building_id == "customs_house"]
    assert any(
        action.taxation_majority_building_id == "customs_house"
        and action.taxation_majority_building_source == "own_active"
        for action in legal_actions(scenario.state, scenario.config)
        if isinstance(action, FullTurnAction)
    )


def test_unaffordable_customs_house_hire_is_not_offered() -> None:
    scenario = load_scenario("scenarios/customs_house_insufficient_hire_resource_001.json")

    assert not [step for step in turn_steps(scenario.state, scenario.config) if step.building_id == "customs_house"]


def test_customs_house_hire_window_closes_after_resolution() -> None:
    scenario = load_scenario("scenarios/customs_house_hire_opponent_taxation_majority_001.json")

    assert not [step for step in turn_steps(_pre_resolution_state(scenario), scenario.config) if step.building_id == "customs_house"]


def test_hired_bank_only_changes_actions_after_its_step() -> None:
    scenario = load_scenario("scenarios/bank_hire_opponent_ordination_001.json")

    assert not any(
        action.bank_payment_building_id == "bank"
        for action in legal_actions(scenario.state, scenario.config)
        if isinstance(action, FullTurnAction)
    )

    after = apply_turn_step(
        scenario.state,
        scenario.config,
        _activation_step(scenario.state, scenario.config, "bank"),
    )
    enabled = [
        action
        for action in legal_actions(after, scenario.config)
        if isinstance(action, FullTurnAction) and action.bank_payment_building_id == "bank"
    ]
    assert enabled
    assert all(action.bank_payment_building_source is None for action in enabled)


def test_hired_bank_pays_its_opponent_and_market_sources() -> None:
    opponent = load_scenario("scenarios/bank_hire_opponent_ordination_001.json")
    after_opponent = apply_turn_step(
        opponent.state,
        opponent.config,
        _activation_step(opponent.state, opponent.config, "bank"),
    )
    _assert_opponent_hire_payment(opponent.state, after_opponent, building_id="bank")

    market = load_scenario("scenarios/bank_hire_market_ordination_001.json")
    after_market = apply_turn_step(
        market.state,
        market.config,
        _activation_step(market.state, market.config, "bank"),
    )
    _assert_market_hire_pays_bank(after_market, building_id="bank")


def test_owned_bank_is_free_immediate_and_step_free() -> None:
    scenario = load_scenario("scenarios/bank_active_ordination_substitution_001.json")

    assert not [step for step in turn_steps(scenario.state, scenario.config) if step.building_id == "bank"]
    assert any(
        action.bank_payment_building_id == "bank" and action.bank_payment_building_source == "own_active"
        for action in legal_actions(scenario.state, scenario.config)
        if isinstance(action, FullTurnAction)
    )


def test_unaffordable_bank_hire_is_not_offered() -> None:
    scenario = load_scenario("scenarios/bank_hire_opponent_ordination_001.json")
    player = scenario.state.player_state(PlayerId.PLAYER_ONE)
    without_silver = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(player, resources=replace(player.resources, silver=0)),
    )

    assert not [step for step in turn_steps(without_silver, scenario.config) if step.building_id == "bank"]


def test_bank_hire_window_closes_after_resolution() -> None:
    scenario = load_scenario("scenarios/bank_hire_opponent_ordination_001.json")

    assert not [step for step in turn_steps(_pre_resolution_state(scenario), scenario.config) if step.building_id == "bank"]


def test_hired_bank_pays_first_then_changes_the_later_transaction() -> None:
    scenario = load_scenario("scenarios/bank_hire_opponent_ordination_001.json")
    after_hire = apply_turn_step(
        scenario.state,
        scenario.config,
        _activation_step(scenario.state, scenario.config, "bank"),
    )
    action = next(
        action
        for action in legal_actions(after_hire, scenario.config)
        if isinstance(action, FullTurnAction)
        and action.bank_payment_building_id == "bank"
        and action.bank_payment_replaced_resource == "wheat"
    )
    result = apply_action(after_hire, action, scenario.config)
    events = _building_hires(result.state)

    assert dict(events[0].details)["building_id"] == "bank"
    assert dict(events[0].details)["payee"] == "player_two"
    assert any(
        dict(event.details).get("building") == "bank"
        and dict(event.details).get("action") == "payment_substitution"
        for event in result.events
    )


def test_hired_wagon_yard_only_grants_free_hires_after_its_step() -> None:
    scenario = load_scenario("scenarios/wagon_yard_hire_opponent_free_hire_market_scriptorium_001.json")

    assert not any(
        action.free_hire_enabler_building_id == "wagon_yard"
        for action in legal_actions(scenario.state, scenario.config)
        if isinstance(action, FullTurnAction)
    )

    after = apply_turn_step(
        scenario.state,
        scenario.config,
        _activation_step(scenario.state, scenario.config, "wagon_yard"),
    )
    step = _activation_step(after, scenario.config, "scriptorium")

    assert step.source == "market"
    assert step.hire_payment is None
    assert not any(
        action.free_hire_enabler_building_id == "wagon_yard"
        and action.free_hire_target_building_id == "scriptorium"
        for action in legal_actions(after, scenario.config)
        if isinstance(action, FullTurnAction)
    )


def test_hired_wagon_yard_pays_its_opponent_and_market_sources() -> None:
    opponent = load_scenario("scenarios/wagon_yard_hire_opponent_free_hire_market_scriptorium_001.json")
    after_opponent = apply_turn_step(
        opponent.state,
        opponent.config,
        _activation_step(opponent.state, opponent.config, "wagon_yard"),
    )
    _assert_opponent_hire_payment(opponent.state, after_opponent, building_id="wagon_yard")

    market = load_scenario("scenarios/wagon_yard_market_not_hireable_001.json")
    after_market = apply_turn_step(
        market.state,
        market.config,
        _activation_step(market.state, market.config, "wagon_yard"),
    )
    _assert_market_hire_pays_bank(after_market, building_id="wagon_yard")


def test_owned_wagon_yard_is_free_immediate_and_step_free() -> None:
    scenario = load_scenario("scenarios/wagon_yard_active_free_hire_market_scriptorium_001.json")

    assert not [step for step in turn_steps(scenario.state, scenario.config) if step.building_id == "wagon_yard"]
    step = _activation_step(scenario.state, scenario.config, "scriptorium")

    assert step.hire_payment is None
    after = apply_turn_step(scenario.state, scenario.config, step)
    assert any(
        action.effective_acolyte_building_id == "scriptorium"
        for action in legal_actions(after, scenario.config)
        if isinstance(action, FullTurnAction)
    )


def test_unaffordable_wagon_yard_hire_is_not_offered() -> None:
    scenario = load_scenario("scenarios/wagon_yard_hire_opponent_free_hire_market_scriptorium_001.json")
    player = scenario.state.player_state(PlayerId.PLAYER_ONE)
    without_wheat = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(player, resources=replace(player.resources, wheat=0)),
    )

    assert not [step for step in turn_steps(without_wheat, scenario.config) if step.building_id == "wagon_yard"]


def test_wagon_yard_hire_window_closes_after_resolution() -> None:
    scenario = load_scenario("scenarios/wagon_yard_hire_opponent_free_hire_market_scriptorium_001.json")

    assert not [step for step in turn_steps(_pre_resolution_state(scenario), scenario.config) if step.building_id == "wagon_yard"]


def test_hired_wagon_yard_pays_before_its_free_hire() -> None:
    scenario = load_scenario("scenarios/wagon_yard_hire_opponent_free_hire_market_scriptorium_001.json")
    after_hire = apply_turn_step(
        scenario.state,
        scenario.config,
        _activation_step(scenario.state, scenario.config, "wagon_yard"),
    )
    after_free_hire = apply_turn_step(
        after_hire,
        scenario.config,
        _activation_step(after_hire, scenario.config, "scriptorium"),
    )
    action = next(
        action
        for action in legal_actions(after_free_hire, scenario.config)
        if isinstance(action, FullTurnAction) and action.effective_acolyte_building_id == "scriptorium"
    )
    result = apply_action(after_free_hire, action, scenario.config)
    events = _building_hires(result.state)
    wagon_event = next(event for event in events if dict(event.details)["building_id"] == "wagon_yard")
    scriptorium_event = next(
        event for event in events if dict(event.details)["building_id"] == "scriptorium"
    )

    assert after_hire.player_state(PlayerId.PLAYER_ONE).resources.wheat == 0
    assert after_free_hire.player_state(PlayerId.PLAYER_ONE).resources.wheat == 0
    assert dict(wagon_event.details)["payee"] == "player_two"
    assert dict(scriptorium_event.details)["payee"] == "none"
    assert dict(scriptorium_event.details)["amount"] == 0
