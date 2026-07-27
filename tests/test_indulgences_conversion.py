from __future__ import annotations

from dataclasses import replace

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import action_summary
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules.transition import TransitionValidationError, apply_action, legal_actions


def _events_of_type(events, event_type: EventType):
    return [event for event in events if event.event_type is event_type]


def _indulgences_actions(path: str):
    scenario = load_scenario(path)
    actions = legal_actions(scenario.state, scenario.config)
    conversions = [
        action
        for action in actions
        if action.building_conversion_id == "indulgences"
    ]
    return scenario, actions, conversions


def _first_action(actions, predicate):
    return next(action for action in actions if predicate(action))


def test_own_active_indulgences_generates_sell_variants_for_each_piety_amount() -> None:
    _scenario, _actions, conversions = _indulgences_actions(
        "scenarios/indulgences_active_sell_piety_001.json"
    )

    sell_amounts = {
        action.building_conversion_amount
        for action in conversions
        if action.building_conversion_direction == "sell_piety"
    }
    assert sell_amounts == {1, 2, 3}
    assert all(action.building_conversion_source == "own_active" for action in conversions)
    assert all((action.building_conversion_amount or 0) >= 1 for action in conversions)


def test_own_active_indulgences_generates_buy_variants_for_each_amount() -> None:
    _scenario, _actions, conversions = _indulgences_actions(
        "scenarios/indulgences_active_buy_piety_001.json"
    )

    buy_amounts = {
        action.building_conversion_amount
        for action in conversions
        if action.building_conversion_direction == "buy_piety"
    }
    assert buy_amounts == {1, 2}
    assert all(action.building_conversion_source == "own_active" for action in conversions)
    assert all((action.building_conversion_amount or 0) >= 1 for action in conversions)


def test_hired_market_indulgences_generates_sell_variants_when_payable() -> None:
    _scenario, _actions, conversions = _indulgences_actions(
        "scenarios/indulgences_hire_market_sell_piety_001.json"
    )

    sell_amounts = {
        action.building_conversion_amount
        for action in conversions
        if action.building_conversion_direction == "sell_piety"
    }
    assert sell_amounts == {1, 2}
    assert all(action.building_conversion_source == "market" for action in conversions)


def test_hired_opponent_indulgences_generates_buy_variants_when_payable() -> None:
    _scenario, _actions, conversions = _indulgences_actions(
        "scenarios/indulgences_hire_opponent_buy_piety_001.json"
    )

    buy_amounts = {
        action.building_conversion_amount
        for action in conversions
        if action.building_conversion_direction == "buy_piety"
    }
    assert buy_amounts == {1, 2, 3}
    assert all(action.building_conversion_source == "player_two" for action in conversions)


def test_own_active_indulgences_source_priority_blocks_hired_variants() -> None:
    scenario = load_scenario("scenarios/indulgences_hire_market_sell_piety_001.json")
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    state_with_own_indulgences = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(
            player_one,
            player_board_slots=replace(
                player_one.player_board_slots,
                active_buildings=("indulgences",),
            ),
        ),
    )
    actions = legal_actions(state_with_own_indulgences, scenario.config)
    conversions = [
        action
        for action in actions
        if action.building_conversion_id == "indulgences"
    ]

    assert conversions
    assert all(action.building_conversion_source == "own_active" for action in conversions)


def test_merchant_none_insufficient_donated_and_not_live_block_hired_indulgences() -> None:
    blocked_paths = (
        "scenarios/indulgences_merchant_none_no_hire_001.json",
        "scenarios/indulgences_insufficient_after_hire_001.json",
        "scenarios/indulgences_donated_no_conversion_001.json",
        "scenarios/indulgences_not_live_no_conversion_001.json",
    )
    for path in blocked_paths:
        _scenario, actions, conversions = _indulgences_actions(path)
        assert conversions == []
        assert any(action.building_conversion_id is None for action in actions)


def test_sell_variants_not_generated_at_piety_zero() -> None:
    _scenario, _actions, conversions = _indulgences_actions(
        "scenarios/indulgences_active_buy_piety_001.json"
    )
    sell_amounts = {
        action.building_conversion_amount
        for action in conversions
        if action.building_conversion_direction == "sell_piety"
    }
    assert sell_amounts == set()


def test_buy_variants_not_generated_at_piety_cap() -> None:
    scenario = load_scenario("scenarios/indulgences_active_buy_piety_001.json")
    max_piety = scenario.config.piety.max_position
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    capped_state = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(player_one, piety=max_piety),
    )
    actions = legal_actions(capped_state, scenario.config)
    buy_amounts = {
        action.building_conversion_amount
        for action in actions
        if action.building_conversion_id == "indulgences"
        and action.building_conversion_direction == "buy_piety"
    }
    assert buy_amounts == set()


def test_apply_own_active_sell_two_piety_emits_bonus_then_delta_before_sowing() -> None:
    scenario, _actions, conversions = _indulgences_actions(
        "scenarios/indulgences_active_sell_piety_001.json"
    )
    north_east = scenario.config.board.index_for_name("north_east")
    action = _first_action(
        conversions,
        lambda candidate: (
            candidate.building_conversion_direction == "sell_piety"
            and candidate.building_conversion_amount == 2
            and candidate.selected_duty == north_east
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)

    bonus_event = _first_action(
        _events_of_type(result.events, EventType.BUILDING_BONUS),
        lambda event: dict(event.details).get("building") == "indulgences",
    )
    delta_event = _events_of_type(result.events, EventType.RESOURCE_DELTA)[0]
    sowing_event = _events_of_type(result.events, EventType.SOWING)[0]
    delta_details = dict(delta_event.details)

    assert _events_of_type(result.events, EventType.BUILDING_HIRED) == []
    assert delta_details["stone"] == 0
    assert delta_details["silver"] == 2
    assert delta_details["wheat"] == 0
    assert delta_details["piety"] == -2
    assert result.events.index(bonus_event) < result.events.index(delta_event)
    assert result.events.index(delta_event) < result.events.index(sowing_event)
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.silver == 2
    assert result.state.player_state(PlayerId.PLAYER_ONE).piety == 1
    invariant_event = _events_of_type(result.events, EventType.INVARIANT_CHECK)[-1]
    assert dict(invariant_event.details)["acolytes_conserved"] is True


def test_apply_own_active_buy_one_piety_converts_resources() -> None:
    scenario, _actions, conversions = _indulgences_actions(
        "scenarios/indulgences_active_buy_piety_001.json"
    )
    action = _first_action(
        conversions,
        lambda candidate: (
            candidate.building_conversion_direction == "buy_piety"
            and candidate.building_conversion_amount == 1
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)
    delta_details = dict(_events_of_type(result.events, EventType.RESOURCE_DELTA)[0].details)

    assert delta_details["silver"] == -1
    assert delta_details["wheat"] == 0
    assert delta_details["piety"] == 1
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.silver == 1
    assert result.state.player_state(PlayerId.PLAYER_ONE).piety == 1


def test_hired_market_indulgences_pays_bank_before_conversion() -> None:
    scenario, _actions, conversions = _indulgences_actions(
        "scenarios/indulgences_hire_market_sell_piety_001.json"
    )
    action = _first_action(
        conversions,
        lambda candidate: (
            candidate.building_conversion_source == "market"
            and candidate.building_conversion_direction == "sell_piety"
            and candidate.building_conversion_amount == 2
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)

    hired_event = _events_of_type(result.events, EventType.BUILDING_HIRED)[0]
    bonus_event = _first_action(
        _events_of_type(result.events, EventType.BUILDING_BONUS),
        lambda event: dict(event.details).get("building") == "indulgences",
    )
    delta_event = _events_of_type(result.events, EventType.RESOURCE_DELTA)[0]
    hired_details = dict(hired_event.details)

    assert hired_details["building_id"] == "indulgences"
    assert hired_details["source"] == "market"
    assert hired_details["payee"] == "bank"
    assert result.events.index(hired_event) < result.events.index(bonus_event)
    assert result.events.index(bonus_event) < result.events.index(delta_event)
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 0
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.silver == 2
    assert result.state.player_state(PlayerId.PLAYER_ONE).piety == 0


def test_hired_opponent_indulgences_pays_owner_before_conversion() -> None:
    scenario, _actions, conversions = _indulgences_actions(
        "scenarios/indulgences_hire_opponent_buy_piety_001.json"
    )
    action = _first_action(
        conversions,
        lambda candidate: (
            candidate.building_conversion_source == "player_two"
            and candidate.building_conversion_direction == "buy_piety"
            and candidate.building_conversion_amount == 2
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)
    hired_details = dict(_events_of_type(result.events, EventType.BUILDING_HIRED)[0].details)

    assert hired_details["source"] == "player_two"
    assert hired_details["payee"] == "player_two"
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.silver == 1
    assert result.state.player_state(PlayerId.PLAYER_ONE).piety == 2
    assert result.state.player_state(PlayerId.PLAYER_TWO).resources.silver == 1


def test_apply_rejects_buy_conversion_that_cannot_pay_after_hire() -> None:
    scenario = load_scenario("scenarios/indulgences_insufficient_after_hire_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    base_action = _first_action(actions, lambda candidate: candidate.resolution is TurnResolutionType.TITHE)
    invalid_action = replace(
        base_action,
        building_conversion_id="indulgences",
        building_conversion_source="market",
        building_conversion_direction="buy_piety",
        building_conversion_amount=1,
    )

    with pytest.raises(
        TransitionValidationError,
        match="Indulgences buy conversion requires enough silver after hire payment",
    ):
        apply_action(scenario.state, invalid_action, scenario.config)


def test_apply_rejects_sell_conversion_below_zero_piety() -> None:
    scenario = load_scenario("scenarios/indulgences_active_buy_piety_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    base_action = _first_action(actions, lambda candidate: candidate.resolution is TurnResolutionType.TITHE)
    invalid_action = replace(
        base_action,
        building_conversion_id="indulgences",
        building_conversion_source="own_active",
        building_conversion_direction="sell_piety",
        building_conversion_amount=1,
    )

    with pytest.raises(
        TransitionValidationError,
        match="Indulgences sell conversion requires enough piety after hire payment",
    ):
        apply_action(scenario.state, invalid_action, scenario.config)


def test_apply_rejects_buy_conversion_above_piety_cap() -> None:
    scenario = load_scenario("scenarios/indulgences_active_buy_piety_001.json")
    max_piety = scenario.config.piety.max_position
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    capped_state = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(player_one, piety=max_piety, resources=player_one.resources.add(silver=1)),
    )
    actions = legal_actions(capped_state, scenario.config)
    base_action = _first_action(actions, lambda candidate: candidate.resolution is TurnResolutionType.TITHE)
    invalid_action = replace(
        base_action,
        building_conversion_id="indulgences",
        building_conversion_source="own_active",
        building_conversion_direction="buy_piety",
        building_conversion_amount=1,
    )

    with pytest.raises(
        TransitionValidationError,
        match="Indulgences buy conversion exceeds piety track maximum",
    ):
        apply_action(capped_state, invalid_action, scenario.config)


def test_converted_piety_can_change_round_end_start_player_selection() -> None:
    scenario, actions, conversions = _indulgences_actions(
        "scenarios/indulgences_buy_then_round_end_start_player_001.json"
    )
    buy_action = _first_action(
        conversions,
        lambda candidate: (
            candidate.building_conversion_direction == "buy_piety"
            and candidate.building_conversion_amount == 1
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    no_conversion_action = _first_action(
        actions,
        lambda candidate: (
            candidate.building_conversion_id is None
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )

    with_conversion = apply_action(scenario.state, buy_action, scenario.config)
    without_conversion = apply_action(scenario.state, no_conversion_action, scenario.config)

    assert with_conversion.state.start_player is PlayerId.PLAYER_TWO
    assert without_conversion.state.start_player is PlayerId.PLAYER_ONE
    selection_event = _first_action(
        _events_of_type(with_conversion.events, EventType.START_PLAYER_SELECTION),
        lambda _event: True,
    )
    assert dict(selection_event.details)["selected_start_player"] == "player_two"


def test_action_summary_includes_indulgences_conversion_and_hire_suffix() -> None:
    own_scenario, _own_actions, own_conversions = _indulgences_actions(
        "scenarios/indulgences_active_sell_piety_001.json"
    )
    own_action = _first_action(
        own_conversions,
        lambda candidate: (
            candidate.building_conversion_direction == "sell_piety"
            and candidate.building_conversion_amount == 2
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    own_summary = action_summary(own_action, own_scenario.config)
    assert "use building: indulgences to sell 2 piety for 2 silver" in own_summary
    assert "hire building: indulgences" not in own_summary

    hired_scenario, _hired_actions, hired_conversions = _indulgences_actions(
        "scenarios/indulgences_hire_market_buy_piety_001.json"
    )
    hired_action = _first_action(
        hired_conversions,
        lambda candidate: (
            candidate.building_conversion_direction == "buy_piety"
            and candidate.building_conversion_amount == 1
            and candidate.building_conversion_source == "market"
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    hired_summary = action_summary(hired_action, hired_scenario.config)
    assert "use building: indulgences to buy 1 piety for 1 silver" in hired_summary
    assert "hire building: indulgences from market" in hired_summary
