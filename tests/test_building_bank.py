from __future__ import annotations

from collections import Counter
from dataclasses import replace

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import BuildingActivationStep, FullTurnAction, action_summary
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules import transition
from pilgrim.rules.buildings import building_ability_source
from pilgrim.rules.merchant import taxation_board_position
from pilgrim.rules.transition import (
    TransitionValidationError,
    _costs_with_bank_substitution,
    apply_action,
    apply_turn_step,
    legal_actions,
    turn_steps,
)


def _events_of_type(events, event_type: EventType):
    return [event for event in events if event.event_type is event_type]


def _first_action(actions, predicate):
    return next(action for action in actions if predicate(action))


def _bank_actions(path: str):
    scenario = load_scenario(path)
    actions = [
        action
        for action in legal_actions(scenario.state, scenario.config)
        if isinstance(action, FullTurnAction)
    ]
    bank_actions = [action for action in actions if action.bank_payment_building_id == "bank"]
    return scenario, actions, bank_actions


def _inline_hired_bank_actions(path: str):
    scenario = load_scenario(path)
    actions = [
        action
        for action in legal_actions(scenario.state, scenario.config)
        if isinstance(action, FullTurnAction)
    ]
    bank_actions = [action for action in actions if action.bank_payment_building_id == "bank"]
    return scenario, actions, bank_actions


def test_minority_fee_shortage_leaves_only_tithe_actions() -> None:
    scenario = load_scenario("scenarios/bank_hire_market_construct_substitution_001.json")
    acting_player = scenario.state.active_player
    player = scenario.state.player_state(acting_player)
    no_silver_state = scenario.state.with_player_state(
        acting_player,
        replace(player, resources=replace(player.resources, silver=0)),
    )

    affordable_counts = Counter(
        action.resolution for action in legal_actions(scenario.state, scenario.config)
    )
    no_silver_counts = Counter(
        (action.selected_duty, action.resolution)
        for action in legal_actions(no_silver_state, scenario.config)
    )

    assert affordable_counts == Counter(
        {
            TurnResolutionType.CONSTRUCT_BUILDING: 28,
            TurnResolutionType.CONSTRUCT_ROAD_DEFERRED: 2,
            TurnResolutionType.TITHE: 5,
            TurnResolutionType.GIVE_ALMS_PAID: 4,
            TurnResolutionType.PRODUCE_WHEAT: 1,
            TurnResolutionType.PRODUCE_STONE: 1,
        }
    )
    assert no_silver_counts == Counter({(4, TurnResolutionType.TITHE): 1})


def _legacy_paid_bank_step(scenario) -> BuildingActivationStep:
    """Build the retired paid Bank step so its outcome set remains directly comparable."""
    source = building_ability_source(
        scenario.state,
        scenario.config,
        acting_player=scenario.state.active_player,
        building_key="bank",
    )
    assert source.source_type in {"live_market_hire", "opponent_active_hire"}
    assert source.hire_resource is not None
    return BuildingActivationStep(
        building_id="bank",
        source="market" if source.source_type == "live_market_hire" else source.owner or "unknown",
        hire_payment=source.hire_resource,
    )


def _outcome_without_action_id_spellings(state):
    """Compare event content while allowing the retired step's action IDs to change."""
    return replace(
        state,
        turn_progress=replace(
            state.turn_progress,
            # The event list's sort order also follows its action ID, so normalize that ordering
            # after clearing the spelling that changes when the committed step becomes an action.
            events=tuple(
                sorted(
                    (replace(event, action_id="") for event in state.turn_progress.events),
                    key=repr,
                )
            ),
        ),
    )


def _physical_outcome(state):
    """Compare board and player state without treating two audit traces as distinct endpoints."""
    return replace(state, turn_progress=replace(state.turn_progress, events=()))


def test_own_active_bank_generates_partial_and_full_ordination_substitution_variants() -> None:
    _scenario, actions, bank_actions = _bank_actions(
        "scenarios/bank_active_ordination_substitution_001.json"
    )
    two_step_bank_variants = [
        action
        for action in bank_actions
        if action.resolution is TurnResolutionType.ORDINATION
        and action.ordination_steps == ("ordain", "ordain")
    ]

    assert two_step_bank_variants
    assert {
        action.bank_payment_silver_amount for action in two_step_bank_variants
    } == {1}
    assert all(action.bank_payment_replaced_resource == "wheat" for action in two_step_bank_variants)
    assert all(action.bank_payment_building_source == "own_active" for action in two_step_bank_variants)
    assert not any(
        action.resolution is TurnResolutionType.ORDINATION
        and action.ordination_steps == ("ordain", "ordain")
        and action.bank_payment_building_id is None
        for action in actions
    )

    _scenario_full, actions_full, bank_actions_full = _bank_actions(
        "scenarios/bank_active_ordination_full_substitution_001.json"
    )
    full_two_step_variants = [
        action
        for action in bank_actions_full
        if action.resolution is TurnResolutionType.ORDINATION
        and action.ordination_steps == ("ordain", "ordain")
    ]
    assert {action.bank_payment_silver_amount for action in full_two_step_variants} == {2}
    assert not any(
        action.resolution is TurnResolutionType.ORDINATION
        and action.ordination_steps == ("ordain", "ordain")
        and action.bank_payment_building_id is None
        for action in actions_full
    )


def test_apply_own_active_bank_partial_substitution_deducts_silver_and_remaining_wheat() -> None:
    scenario, _actions, bank_actions = _bank_actions("scenarios/bank_active_ordination_substitution_001.json")
    action = _first_action(
        bank_actions,
        lambda candidate: (
            candidate.resolution is TurnResolutionType.ORDINATION
            and candidate.ordination_steps == ("ordain", "ordain")
            and candidate.bank_payment_replaced_resource == "wheat"
            and candidate.bank_payment_silver_amount == 1
        ),
    )
    summary = action_summary(action, scenario.config)
    assert "use building: bank to replace 1 wheat with 1 silver for this transaction" in summary
    assert "hire building: bank" not in summary

    result = apply_action(scenario.state, action, scenario.config)
    bonus_event = _first_action(
        _events_of_type(result.events, EventType.BUILDING_BONUS),
        lambda event: dict(event.details).get("building") == "bank",
    )
    delta_event = _events_of_type(result.events, EventType.RESOURCE_DELTA)[0]
    sow_event = _events_of_type(result.events, EventType.SOWING)[0]
    bonus_details = dict(bonus_event.details)
    delta_details = dict(delta_event.details)

    assert bonus_details["replaced_resource"] == "wheat"
    assert bonus_details["silver_amount"] == 1
    assert delta_details == {"stone": 0, "silver": -1, "wheat": -1}
    assert result.events.index(bonus_event) < result.events.index(sow_event)
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 0
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.silver == 0


def test_apply_own_active_bank_full_substitution_can_resolve_without_wheat() -> None:
    scenario, _actions, bank_actions = _bank_actions(
        "scenarios/bank_active_ordination_full_substitution_001.json"
    )
    action = _first_action(
        bank_actions,
        lambda candidate: (
            candidate.resolution is TurnResolutionType.ORDINATION
            and candidate.ordination_steps == ("ordain", "ordain")
            and candidate.bank_payment_replaced_resource == "wheat"
            and candidate.bank_payment_silver_amount == 2
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)
    delta_details = dict(_events_of_type(result.events, EventType.RESOURCE_DELTA)[0].details)

    assert delta_details["silver"] == -2
    assert delta_details["wheat"] == 0
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 0
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.silver == 0


def test_bank_construct_substitution_spends_silver_and_not_stone() -> None:
    scenario, actions, bank_actions = _bank_actions(
        "scenarios/bank_active_construct_minority_substitution_001.json"
    )
    construct_bank_actions = [
        action
        for action in bank_actions
        if action.resolution is TurnResolutionType.CONSTRUCT_BUILDING
        and action.construct_building_id == "well"
    ]
    assert construct_bank_actions
    assert {action.bank_payment_replaced_resource for action in construct_bank_actions} == {"stone"}
    assert {action.bank_payment_silver_amount for action in construct_bank_actions} == {1}
    assert not any(
        action.resolution is TurnResolutionType.CONSTRUCT_BUILDING
        and action.construct_building_id == "well"
        and action.bank_payment_building_id is None
        for action in actions
    )

    action = construct_bank_actions[0]
    result = apply_action(scenario.state, action, scenario.config)
    delta_details = dict(_events_of_type(result.events, EventType.RESOURCE_DELTA)[0].details)
    assert delta_details == {"stone": 0, "silver": -2, "wheat": 0}
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.stone == 0
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.silver == 0
    assert "well" in result.state.player_state(PlayerId.PLAYER_ONE).player_board_slots.active_buildings


def test_hired_market_bank_construct_substitution_is_reachable_with_the_hire_in_its_cost() -> None:
    scenario, _actions, bank_actions = _inline_hired_bank_actions(
        "scenarios/bank_hire_market_construct_substitution_001.json"
    )
    construct_bank_actions = [
        action
        for action in bank_actions
        if action.resolution is TurnResolutionType.CONSTRUCT_BUILDING
    ]

    def action_for_building(building_id: str) -> FullTurnAction:
        return _first_action(
            construct_bank_actions,
            lambda candidate: candidate.construct_building_id == building_id,
        )

    observed_costs = {}
    for building_id in ("well", "brewery", "customs_house"):
        action = action_for_building(building_id)
        result = apply_action(scenario.state, action, scenario.config)
        before_resources = scenario.state.player_state(scenario.state.active_player).resources
        resources = result.state.player_state(PlayerId.PLAYER_ONE).resources
        payment = {
            resource: max(0, getattr(before_resources, resource) - getattr(resources, resource))
            for resource in ("stone", "silver", "wheat")
        }
        observed_costs[building_id] = {
            "payment": payment,
            "total": sum(payment.values()),
            "retained_stone": resources.stone,
        }

    observed = {
        "building_ids": {action.construct_building_id for action in construct_bank_actions},
        "count": len(construct_bank_actions),
        "sources": {action.bank_payment_building_source for action in construct_bank_actions},
        "replaced_resources": {
            action.bank_payment_replaced_resource for action in construct_bank_actions
        },
        "substitution_silver": {
            action.bank_payment_silver_amount for action in construct_bank_actions
        },
        "hire_payments": {action.hire_payments for action in construct_bank_actions},
        "costs": observed_costs,
    }
    assert observed == {
        "building_ids": {
            "bank",
            "brewery",
            "chapel",
            "cloisters",
            "customs_house",
            "dormitory",
            "grain_store",
            "inquisition",
            "mint",
            "quarry",
            "wagon_yard",
            "well",
        },
        "count": 12,
        "sources": {"market"},
        "replaced_resources": {"stone"},
        "substitution_silver": {1},
        "hire_payments": {(("bank", "silver"),)},
        "costs": {
            "well": {
                "payment": {"stone": 0, "silver": 3, "wheat": 0},
                "total": 3,
                "retained_stone": 2,
            },
            "brewery": {
                "payment": {"stone": 1, "silver": 3, "wheat": 0},
                "total": 4,
                "retained_stone": 1,
            },
            "customs_house": {
                "payment": {"stone": 2, "silver": 3, "wheat": 0},
                "total": 5,
                "retained_stone": 0,
            },
        },
    }


def test_bank_helper_supports_one_resource_type_substitution_including_piety() -> None:
    wheat_sub = _costs_with_bank_substitution(
        required_stone=1,
        required_wheat=2,
        replaced_resource="wheat",
        silver_amount=2,
    )
    stone_sub = _costs_with_bank_substitution(
        required_stone=1,
        required_wheat=2,
        replaced_resource="stone",
        silver_amount=1,
    )
    piety_sub = _costs_with_bank_substitution(
        required_piety=2,
        replaced_resource="piety",
        silver_amount=1,
    )
    assert wheat_sub == (1, 2, 0, 0)
    assert stone_sub == (0, 1, 2, 0)
    assert piety_sub == (0, 1, 0, 1)
    with pytest.raises(ValueError, match="exceeds required stone"):
        _costs_with_bank_substitution(
            required_stone=1,
            replaced_resource="stone",
            silver_amount=2,
        )


def test_bank_variants_only_exist_for_supported_payment_resolutions() -> None:
    scenario, actions, _bank_actions_all = _bank_actions(
        "scenarios/bank_active_construct_minority_substitution_001.json"
    )
    legal_bank_resolutions = {
        TurnResolutionType.ORDINATION,
        TurnResolutionType.CONSTRUCT_BUILDING,
        TurnResolutionType.CONSTRUCT_BUILDING_AND_ROAD_DEFERRED,
    }
    for action in actions:
        if action.bank_payment_building_id is None:
            continue
        assert action.resolution in legal_bank_resolutions
        assert action.bank_payment_replaced_resource in {"wheat", "stone", "piety"}
        assert action.bank_payment_replaced_resource != "silver"
        assert (action.bank_payment_silver_amount or 0) >= 1
    assert scenario is not None


def test_hired_market_bank_pays_hire_before_substitution_and_cannot_use_merchant_none() -> None:
    scenario, _actions, bank_actions = _inline_hired_bank_actions(
        "scenarios/bank_hire_market_ordination_001.json"
    )
    action = _first_action(
        bank_actions,
        lambda candidate: (
            candidate.resolution is TurnResolutionType.ORDINATION
            and candidate.ordination_steps == ("ordain", "ordain")
            and candidate.bank_payment_building_source == "market"
            and candidate.bank_payment_replaced_resource == "wheat"
            and candidate.bank_payment_silver_amount == 1
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)
    hired_event = _events_of_type(result.events, EventType.BUILDING_HIRED)[0]
    bonus_event = _first_action(
        _events_of_type(result.events, EventType.BUILDING_BONUS),
        lambda event: dict(event.details).get("building") == "bank",
    )
    sow_event = _events_of_type(result.events, EventType.SOWING)[0]
    hired_details = dict(hired_event.details)
    assert hired_details["building_id"] == "bank"
    assert hired_details["source"] == "market"
    assert hired_details["payee"] == "bank"
    assert result.events.index(hired_event) < result.events.index(bonus_event)
    assert result.events.index(bonus_event) < result.events.index(sow_event)
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 0
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.silver == 0

    # 0 used to be Taxation, the first entry of the retired six-step path. It is the City now,
    # which the Merchant can never occupy, so the tile offering nothing is looked up instead.
    merchant_none_state = scenario.state.with_merchant_board_position(
        taxation_board_position(scenario.config)
    )
    assert not [step for step in turn_steps(merchant_none_state, scenario.config) if step.building_id == "bank"]


def test_hired_opponent_bank_pays_owner_before_substitution() -> None:
    scenario, _actions, bank_actions = _inline_hired_bank_actions(
        "scenarios/bank_hire_opponent_ordination_001.json"
    )
    action = _first_action(
        bank_actions,
        lambda candidate: (
            candidate.resolution is TurnResolutionType.ORDINATION
            and candidate.ordination_steps == ("ordain", "ordain")
            and candidate.bank_payment_building_source == "player_two"
            and candidate.bank_payment_replaced_resource == "wheat"
            and candidate.bank_payment_silver_amount == 1
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)
    hired_details = dict(_events_of_type(result.events, EventType.BUILDING_HIRED)[0].details)
    assert hired_details["building_id"] == "bank"
    assert hired_details["source"] == "player_two"
    assert hired_details["payee"] == "player_two"
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 0
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.silver == 0
    assert result.state.player_state(PlayerId.PLAYER_TWO).resources.silver == 1


def test_paid_bank_hire_outcomes_are_atomic_and_the_paid_non_use_outcomes_are_removed() -> None:
    paid_hire_scenarios = (
        "bank_hire_market_ordination_001.json",
        "bank_hire_opponent_ordination_001.json",
        "kogge_donated_no_extra_routes_001.json",
        "kogge_hire_opponent_city_to_west_001.json",
        "stone_yard_buy_then_construct_001.json",
    )
    preserved_non_bank_outcomes = 0
    preserved_paid_bank_outcomes = 0
    removed_paid_non_use_actions = 0
    removed_paid_non_use_end_states = 0
    added_actions: list[FullTurnAction] = []

    for scenario_name in paid_hire_scenarios:
        scenario = load_scenario(f"scenarios/{scenario_name}")
        legacy_step = _legacy_paid_bank_step(scenario)
        assert legacy_step.hire_payment is not None
        legacy_state = apply_turn_step(
            scenario.state,
            scenario.config,
            legacy_step,
        )
        legacy_actions = [
            action
            for action in legal_actions(legacy_state, scenario.config)
            if isinstance(action, FullTurnAction)
        ]
        legacy_bank_use_outcomes = {
            _outcome_without_action_id_spellings(
                apply_action(legacy_state, action, scenario.config).state
            )
            for action in legacy_actions
            if action.bank_payment_building_id == "bank"
        }
        legacy_paid_non_use_outcomes = {
            _physical_outcome(apply_action(legacy_state, action, scenario.config).state)
            for action in legacy_actions
            if action.bank_payment_building_id is None
        }

        baseline_actions = [
            action
            for action in transition._legal_full_turn_actions_for_state(
                scenario.state,
                scenario.config,
                allow_scriptorium_modifier=True,
                allow_customs_house_modifier=True,
                allow_wagon_yard_modifier=True,
                allow_bank_modifier=False,
                uses_scriptorium_effective_counts=False,
                uses_customs_house_taxation_override=False,
            )
            if isinstance(action, FullTurnAction)
        ]
        current_actions = [
            action
            for action in legal_actions(scenario.state, scenario.config)
            if isinstance(action, FullTurnAction)
        ]
        inline_bank_actions = [
            action
            for action in current_actions
            if action.bank_payment_building_id == "bank"
            and action.bank_payment_building_source not in (None, "own_active")
        ]
        legacy_inline_bank_actions = [
            action
            for action in inline_bank_actions
            if action.bank_payment_hired_building_id is None
        ]
        current_non_bank_actions = [
            action for action in current_actions if action not in inline_bank_actions
        ]

        assert {
            apply_action(scenario.state, action, scenario.config).state
            for action in current_non_bank_actions
        } == {
            apply_action(scenario.state, action, scenario.config).state
            for action in baseline_actions
        }
        assert {
            _outcome_without_action_id_spellings(
                apply_action(scenario.state, action, scenario.config).state
            )
            for action in legacy_inline_bank_actions
        } == legacy_bank_use_outcomes
        assert legacy_paid_non_use_outcomes.isdisjoint(
            {
                _physical_outcome(apply_action(scenario.state, action, scenario.config).state)
                for action in current_actions
                if action.bank_payment_hired_building_id is None
            }
        )

        added_actions.extend(
            action for action in legacy_inline_bank_actions if action not in baseline_actions
        )
        preserved_non_bank_outcomes += len(baseline_actions)
        preserved_paid_bank_outcomes += len(legacy_bank_use_outcomes)
        removed_paid_non_use_actions += sum(
            action.bank_payment_building_id is None for action in legacy_actions
        )
        removed_paid_non_use_end_states += len(legacy_paid_non_use_outcomes)

    assert preserved_non_bank_outcomes == 70
    assert preserved_paid_bank_outcomes == 6
    assert removed_paid_non_use_actions == 24
    assert removed_paid_non_use_end_states == 20
    assert all(action.bank_payment_building_id == "bank" for action in added_actions)
    assert all(
        action.bank_payment_building_source in {"market", "player_two"}
        for action in added_actions
    )
    assert all(action.bank_payment_replaced_resource is not None for action in added_actions)
    assert all(action.bank_payment_silver_amount is not None for action in added_actions)
    assert all(dict(action.hire_payments).get("bank") is not None for action in added_actions)
    assert len(added_actions) == 6


@pytest.mark.parametrize(
    "scenario_name",
    (
        "kogge_donated_no_extra_routes_001.json",
        "kogge_hire_opponent_city_to_west_001.json",
    ),
)
def test_paid_market_bank_hire_that_pays_in_its_replaced_resource_is_refused(
    scenario_name: str,
) -> None:
    """The two Kogge lines are each worse than their surviving no-Bank twin."""
    scenario = load_scenario(f"scenarios/{scenario_name}")
    actions = legal_actions(scenario.state, scenario.config)
    twin = _first_action(
        actions,
        lambda candidate: (
            isinstance(candidate, FullTurnAction)
            and candidate.resolution is TurnResolutionType.GIVE_ALMS_PAID
            and candidate.hired_building_id == "mill"
            and candidate.hired_building_source == "market"
            and candidate.bank_payment_building_id is None
            and candidate.alms_payment_silver == 0
            and candidate.alms_payment_wheat == 1
        ),
    )
    refused_bank_action = replace(
        twin,
        bank_payment_building_id="bank",
        bank_payment_building_source="market",
        bank_payment_replaced_resource="wheat",
        bank_payment_silver_amount=1,
        bank_payment_hired_building_id="mill",
        hire_payments=tuple(sorted((*twin.hire_payments, ("bank", "wheat")))),
    )

    assert twin in actions
    assert refused_bank_action not in actions

    before = scenario.state.player_state(PlayerId.PLAYER_ONE).resources
    twin_after = apply_action(scenario.state, twin, scenario.config).state.player_state(
        PlayerId.PLAYER_ONE
    ).resources
    bank_after = apply_action(
        scenario.state,
        refused_bank_action,
        scenario.config,
    ).state.player_state(PlayerId.PLAYER_ONE).resources
    twin_spend = {
        resource: getattr(before, resource) - getattr(twin_after, resource)
        for resource in ("stone", "silver", "wheat")
    }
    bank_spend = {
        resource: getattr(before, resource) - getattr(bank_after, resource)
        for resource in ("stone", "silver", "wheat")
    }

    assert (twin_spend, bank_spend) == (
        ({"stone": 0, "silver": 0, "wheat": 1}, {"stone": 0, "silver": 1, "wheat": 1})
    )


def test_paid_market_bank_hire_with_a_different_resource_remains_a_real_trade() -> None:
    scenario = load_scenario(
        "scenarios/bank_hire_market_ordination_different_resource_001.json"
    )
    actions = legal_actions(scenario.state, scenario.config)
    ordinary_action = _first_action(
        actions,
        lambda candidate: (
            isinstance(candidate, FullTurnAction)
            and candidate.resolution is TurnResolutionType.ORDINATION
            and candidate.ordination_steps == ("ordain",)
            and candidate.bank_payment_building_id is None
        ),
    )
    bank_action = _first_action(
        actions,
        lambda candidate: (
            isinstance(candidate, FullTurnAction)
            and candidate.resolution is TurnResolutionType.ORDINATION
            and candidate.ordination_steps == ("ordain",)
            and candidate.bank_payment_building_id == "bank"
            and candidate.bank_payment_building_source == "market"
            and candidate.bank_payment_replaced_resource == "wheat"
            and dict(candidate.hire_payments).get("bank") == "stone"
        ),
    )

    before = scenario.state.player_state(PlayerId.PLAYER_ONE).resources
    ordinary_after = apply_action(
        scenario.state,
        ordinary_action,
        scenario.config,
    ).state.player_state(PlayerId.PLAYER_ONE).resources
    bank_after = apply_action(scenario.state, bank_action, scenario.config).state.player_state(
        PlayerId.PLAYER_ONE
    ).resources
    ordinary_spend = {
        resource: getattr(before, resource) - getattr(ordinary_after, resource)
        for resource in ("stone", "silver", "wheat")
    }
    bank_spend = {
        resource: getattr(before, resource) - getattr(bank_after, resource)
        for resource in ("stone", "silver", "wheat")
    }

    assert (ordinary_spend, bank_spend) == (
        ({"stone": 0, "silver": 0, "wheat": 1}, {"stone": 1, "silver": 1, "wheat": 0})
    )
    assert bank_spend["wheat"] < ordinary_spend["wheat"]


def test_wagon_yard_can_free_hire_bank_and_apply_substitution() -> None:
    scenario = load_scenario(
        "scenarios/wagon_yard_active_free_hire_market_bank_ordination_001.json"
    )
    free_hire = next(
        step for step in turn_steps(scenario.state, scenario.config) if step.building_id == "bank"
    )
    assert free_hire.source == "market"
    assert free_hire.hire_payment is None
    state = apply_turn_step(scenario.state, scenario.config, free_hire)
    bank_actions = [
        action
        for action in legal_actions(state, scenario.config)
        if isinstance(action, FullTurnAction) and action.bank_payment_building_id == "bank"
    ]
    action = _first_action(
        bank_actions,
        lambda candidate: (
            candidate.bank_payment_building_source is None
            and candidate.resolution is TurnResolutionType.ORDINATION
            and candidate.ordination_steps == ("ordain", "ordain")
            and candidate.bank_payment_silver_amount == 2
        ),
    )
    result = apply_action(state, action, scenario.config)
    hired_event = _events_of_type(result.events, EventType.BUILDING_HIRED)[0]
    hired_details = dict(hired_event.details)
    assert hired_details["building_id"] == "bank"
    assert hired_details["source"] == "market"
    assert hired_details["resource"] == "none"
    assert hired_details["amount"] == 0
    assert hired_details["payee"] == "none"
    assert hired_details["free_with_wagon_yard"] is True
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 0
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.silver == 0


def test_apply_rejects_bank_fields_on_unsupported_resolution() -> None:
    scenario = load_scenario("scenarios/bank_active_ordination_substitution_001.json")
    base_action = _first_action(
        [
            action
            for action in legal_actions(scenario.state, scenario.config)
            if isinstance(action, FullTurnAction)
        ],
        lambda candidate: candidate.resolution is TurnResolutionType.TITHE,
    )
    invalid_action = replace(
        base_action,
        bank_payment_building_id="bank",
        bank_payment_building_source="own_active",
        bank_payment_replaced_resource="wheat",
        bank_payment_silver_amount=1,
    )
    with pytest.raises(
        TransitionValidationError,
        match="Bank payment substitution is only supported for Ordination and Construct building actions",
    ):
        apply_action(scenario.state, invalid_action, scenario.config)


def test_bank_replaces_a_hired_mill_payment_without_changing_total_spend() -> None:
    scenario = load_scenario("scenarios/bank_active_give_alms_hire_mill_market_wheat3_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    ordinary_action = _first_action(
        actions,
        lambda action: (
            isinstance(action, FullTurnAction)
            and action.resolution is TurnResolutionType.GIVE_ALMS_PAID
            and action.hired_building_id == "mill"
            and action.bank_payment_building_id is None
            and action.alms_payment_silver == 0
            and action.alms_payment_wheat == 3
        ),
    )
    bank_action = _first_action(
        actions,
        lambda action: (
            isinstance(action, FullTurnAction)
            and action.resolution is TurnResolutionType.GIVE_ALMS_PAID
            and action.hired_building_id == "mill"
            and action.bank_payment_building_id == "bank"
            and action.bank_payment_hired_building_id == "mill"
            and action.alms_payment_silver == 0
            and action.alms_payment_wheat == 3
        ),
    )

    before = scenario.state.player_state(PlayerId.PLAYER_ONE).resources
    ordinary_result = apply_action(scenario.state, ordinary_action, scenario.config)
    bank_result = apply_action(scenario.state, bank_action, scenario.config)
    ordinary_after = ordinary_result.state.player_state(PlayerId.PLAYER_ONE).resources
    bank_after = bank_result.state.player_state(PlayerId.PLAYER_ONE).resources
    ordinary_spend = {
        resource: getattr(before, resource) - getattr(ordinary_after, resource)
        for resource in ("stone", "silver", "wheat")
    }
    bank_spend = {
        resource: getattr(before, resource) - getattr(bank_after, resource)
        for resource in ("stone", "silver", "wheat")
    }

    assert ordinary_spend == {"stone": 0, "silver": 0, "wheat": 2}
    assert bank_spend == {"stone": 0, "silver": 1, "wheat": 1}
    assert sum(bank_spend.values()) == sum(ordinary_spend.values())


def test_bank_hire_variants_name_one_hired_payment_target() -> None:
    scenario = load_scenario("scenarios/bank_active_give_alms_hire_mill_market_wheat3_001.json")
    bank_actions = [
        action
        for action in legal_actions(scenario.state, scenario.config)
        if isinstance(action, FullTurnAction) and action.bank_payment_building_id == "bank"
    ]

    assert bank_actions
    assert all(action.bank_payment_hired_building_id == "mill" for action in bank_actions)
    assert all(action.hired_building_id == "mill" for action in bank_actions)
    assert all(action.bank_payment_replaced_resource == "wheat" for action in bank_actions)
    assert all(action.bank_payment_silver_amount == 1 for action in bank_actions)


def test_bank_cannot_substitute_its_own_hire_cost() -> None:
    scenario = load_scenario("scenarios/bank_hire_market_ordination_001.json")
    bank_action = _first_action(
        legal_actions(scenario.state, scenario.config),
        lambda action: (
            isinstance(action, FullTurnAction)
            and action.bank_payment_building_id == "bank"
            and action.bank_payment_building_source == "market"
        ),
    )
    invalid_action = replace(bank_action, bank_payment_hired_building_id="bank")

    with pytest.raises(TransitionValidationError, match="Bank cannot substitute its own hire cost"):
        apply_action(scenario.state, invalid_action, scenario.config)
