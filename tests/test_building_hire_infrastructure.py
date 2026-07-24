from __future__ import annotations

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import PlayerId
from pilgrim.rules.buildings import (
    BuildingHireTurnContext,
    apply_building_hire_payment,
    available_building_ability_sources,
    building_ability_source,
    building_hire_cost,
    building_hire_payment,
    can_hire_building_this_turn,
    can_use_building_ability,
    record_hired_building_this_turn,
    validate_hire_sequence_for_turn,
)
from pilgrim.rules.merchant import current_merchant_duty, current_merchant_resource


def test_own_active_building_source_is_free_and_usable() -> None:
    scenario = load_scenario("scenarios/building_hire_own_active_001.json")
    source = building_ability_source(
        scenario.state,
        scenario.config,
        acting_player=PlayerId.PLAYER_ONE,
        building_key="well",
    )

    assert source.source_type == "own_active"
    assert source.owner == "player_one"
    assert source.hire_resource is None
    assert source.hire_cost == 0
    assert source.payable_to is None
    assert source.usable is True
    assert source.reason == ""
    assert can_use_building_ability(
        scenario.state,
        scenario.config,
        acting_player=PlayerId.PLAYER_ONE,
        building_key="well",
    )


def test_own_active_building_still_works_when_merchant_resource_none() -> None:
    scenario = load_scenario("scenarios/building_hire_own_active_001.json")
    assert current_merchant_duty(scenario.state, scenario.config.merchant) == "taxation"
    assert current_merchant_resource(scenario.state, scenario.config.merchant) is None

    source = building_ability_source(
        scenario.state,
        scenario.config,
        acting_player=PlayerId.PLAYER_ONE,
        building_key="well",
    )
    assert source.source_type == "own_active"
    assert source.usable is True
    assert source.hire_cost == 0
    assert source.reason == ""


def test_live_market_building_hire_uses_merchant_resource_and_pays_bank() -> None:
    scenario = load_scenario("scenarios/building_hire_live_market_001.json")
    source = building_ability_source(
        scenario.state,
        scenario.config,
        acting_player=PlayerId.PLAYER_ONE,
        building_key="well",
    )
    available = available_building_ability_sources(
        scenario.state,
        scenario.config,
        acting_player=PlayerId.PLAYER_ONE,
        building_key="well",
    )
    hire_resource, hire_cost = building_hire_cost(
        scenario.state,
        scenario.config,
        acting_player=PlayerId.PLAYER_ONE,
        building_key="well",
    )

    assert source.source_type == "live_market_hire"
    assert source.owner is None
    assert source.hire_resource == "wheat"
    assert source.hire_cost == 1
    assert source.payable_to == "bank"
    assert source.usable is True
    assert available == (source,)
    assert (hire_resource, hire_cost) == ("wheat", 1)


def test_opponent_active_building_hire_targets_owner() -> None:
    scenario = load_scenario("scenarios/building_hire_opponent_owned_001.json")
    source = building_ability_source(
        scenario.state,
        scenario.config,
        acting_player=PlayerId.PLAYER_ONE,
        building_key="well",
    )
    payment = building_hire_payment(
        scenario.state,
        acting_player=PlayerId.PLAYER_ONE,
        source=source,
    )

    assert source.source_type == "opponent_active_hire"
    assert source.owner == "player_two"
    assert source.hire_resource == "wheat"
    assert source.hire_cost == 1
    assert source.payable_to == "player_two"
    assert source.usable is True
    assert payment.payee == "player_two"
    assert payment.resource == "wheat"
    assert payment.amount == 1


def test_donated_building_is_unavailable() -> None:
    scenario = load_scenario("scenarios/building_hire_donated_001.json")
    source = building_ability_source(
        scenario.state,
        scenario.config,
        acting_player=PlayerId.PLAYER_ONE,
        building_key="well",
    )

    assert source.source_type == "unavailable"
    assert source.reason == "donated"
    assert source.usable is False


def test_not_live_market_building_is_unavailable() -> None:
    scenario = load_scenario("scenarios/building_hire_not_live_001.json")
    source = building_ability_source(
        scenario.state,
        scenario.config,
        acting_player=PlayerId.PLAYER_ONE,
        building_key="well",
    )

    assert source.source_type == "unavailable"
    assert source.reason == "not_live"
    assert source.usable is False


def test_merchant_none_prevents_hiring() -> None:
    scenario = load_scenario("scenarios/building_hire_merchant_none_001.json")
    assert current_merchant_duty(scenario.state, scenario.config.merchant) == "taxation"
    assert current_merchant_resource(scenario.state, scenario.config.merchant) is None

    source = building_ability_source(
        scenario.state,
        scenario.config,
        acting_player=PlayerId.PLAYER_ONE,
        building_key="well",
    )

    assert source.source_type == "unavailable"
    assert source.reason == "merchant_resource_none"
    assert source.hire_cost == 1
    assert source.usable is False


def test_opponent_owned_hire_is_unavailable_when_merchant_on_taxation() -> None:
    scenario = load_scenario("scenarios/building_hire_opponent_owned_001.json")
    taxation_state = scenario.state.with_merchant_position(0)

    assert current_merchant_duty(taxation_state, scenario.config.merchant) == "taxation"
    assert current_merchant_resource(taxation_state, scenario.config.merchant) is None

    source = building_ability_source(
        taxation_state,
        scenario.config,
        acting_player=PlayerId.PLAYER_ONE,
        building_key="well",
    )
    assert source.source_type == "unavailable"
    assert source.reason == "merchant_resource_none"
    assert source.usable is False


def test_insufficient_resource_prevents_hiring() -> None:
    scenario = load_scenario("scenarios/building_hire_insufficient_resource_001.json")
    source = building_ability_source(
        scenario.state,
        scenario.config,
        acting_player=PlayerId.PLAYER_ONE,
        building_key="well",
    )

    assert source.source_type == "unavailable"
    assert source.reason == "insufficient_resource"
    assert source.hire_resource == "wheat"
    assert source.hire_cost == 1
    assert source.usable is False


def test_not_selected_building_is_unavailable() -> None:
    scenario = load_scenario("scenarios/building_hire_live_market_001.json")
    source = building_ability_source(
        scenario.state,
        scenario.config,
        acting_player=PlayerId.PLAYER_ONE,
        building_key="mill",
    )

    assert source.source_type == "unavailable"
    assert source.reason == "not_selected"
    assert source.usable is False


def test_building_ability_source_result_is_deterministic() -> None:
    scenario = load_scenario("scenarios/building_hire_opponent_owned_001.json")
    source_a = building_ability_source(
        scenario.state,
        scenario.config,
        acting_player=PlayerId.PLAYER_ONE,
        building_key="well",
    )
    source_b = building_ability_source(
        scenario.state,
        scenario.config,
        acting_player=PlayerId.PLAYER_ONE,
        building_key="well",
    )
    available_a = available_building_ability_sources(
        scenario.state,
        scenario.config,
        acting_player=PlayerId.PLAYER_ONE,
        building_key="well",
    )
    available_b = available_building_ability_sources(
        scenario.state,
        scenario.config,
        acting_player=PlayerId.PLAYER_ONE,
        building_key="well",
    )
    assert source_a == source_b
    assert available_a == available_b


def test_apply_market_hire_payment_reduces_actor_resource_only() -> None:
    scenario = load_scenario("scenarios/building_hire_live_market_001.json")
    source = building_ability_source(
        scenario.state,
        scenario.config,
        acting_player=PlayerId.PLAYER_ONE,
        building_key="well",
    )

    next_state, payment = apply_building_hire_payment(
        scenario.state,
        acting_player=PlayerId.PLAYER_ONE,
        source=source,
    )
    assert payment.payee == "bank"
    assert payment.resource == "wheat"
    assert payment.amount == 1
    assert next_state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 0
    assert next_state.player_state(PlayerId.PLAYER_TWO).resources.wheat == 0


def test_apply_opponent_hire_payment_transfers_resource_to_owner() -> None:
    scenario = load_scenario("scenarios/building_hire_opponent_owned_001.json")
    source = building_ability_source(
        scenario.state,
        scenario.config,
        acting_player=PlayerId.PLAYER_ONE,
        building_key="well",
    )

    next_state, payment = apply_building_hire_payment(
        scenario.state,
        acting_player=PlayerId.PLAYER_ONE,
        source=source,
    )
    assert payment.payee == "player_two"
    assert payment.resource == "wheat"
    assert payment.amount == 1
    assert next_state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 0
    assert next_state.player_state(PlayerId.PLAYER_TWO).resources.wheat == 1


def test_apply_payment_rejects_unavailable_source() -> None:
    scenario = load_scenario("scenarios/building_hire_not_live_001.json")
    source = building_ability_source(
        scenario.state,
        scenario.config,
        acting_player=PlayerId.PLAYER_ONE,
        building_key="well",
    )

    with pytest.raises(ValueError, match="not usable|cannot be hired"):
        apply_building_hire_payment(
            scenario.state,
            acting_player=PlayerId.PLAYER_ONE,
            source=source,
        )


def test_first_hire_of_building_this_turn_is_allowed() -> None:
    context = BuildingHireTurnContext()
    assert can_hire_building_this_turn(context, building_key="well")

    updated = record_hired_building_this_turn(context, building_key="well")
    assert context.hired_buildings == ()
    assert updated.hired_buildings == ("well",)


def test_second_hire_of_same_building_this_turn_is_rejected() -> None:
    context = BuildingHireTurnContext(hired_buildings=("well",))
    assert not can_hire_building_this_turn(context, building_key="well")
    with pytest.raises(ValueError, match="already hired this turn"):
        record_hired_building_this_turn(context, building_key="well")


def test_different_buildings_can_each_be_hired_once() -> None:
    context = BuildingHireTurnContext()
    after_well = record_hired_building_this_turn(context, building_key="well")
    after_chapel = record_hired_building_this_turn(after_well, building_key="chapel")

    assert after_well.hired_buildings == ("well",)
    assert after_chapel.hired_buildings == ("well", "chapel")
    assert not can_hire_building_this_turn(after_chapel, building_key="well")
    assert can_hire_building_this_turn(after_chapel, building_key="mint")


def test_hire_turn_context_normalizes_building_keys() -> None:
    context = BuildingHireTurnContext()
    updated = record_hired_building_this_turn(context, building_key=" Well ")
    assert updated.hired_buildings == ("well",)
    assert not can_hire_building_this_turn(updated, building_key="WELL")
    assert not can_hire_building_this_turn(updated, building_key="well")

    with pytest.raises(ValueError, match="duplicates"):
        BuildingHireTurnContext(hired_buildings=("Well", "well"))


def test_hire_turn_helpers_are_deterministic_and_pure() -> None:
    base_context = BuildingHireTurnContext(hired_buildings=("well",))
    assert can_hire_building_this_turn(base_context, building_key="chapel")
    assert can_hire_building_this_turn(base_context, building_key="Chapel")

    next_context_a = record_hired_building_this_turn(base_context, building_key="chapel")
    next_context_b = record_hired_building_this_turn(base_context, building_key="Chapel")
    assert base_context.hired_buildings == ("well",)
    assert next_context_a == next_context_b
    assert next_context_a.hired_buildings == ("well", "chapel")


def test_validate_hire_sequence_for_turn() -> None:
    assert validate_hire_sequence_for_turn(("well", "chapel"))
    assert not validate_hire_sequence_for_turn(("well", "well"))
    assert not validate_hire_sequence_for_turn(("well", "chapel", "well"))
