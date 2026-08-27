"""Passive building boundaries, exercised through the same actions a player can take."""

from __future__ import annotations

from dataclasses import replace

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import FullTurnAction
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules.transition import apply_action, legal_actions


def _actions_for(
    state,
    config,
    resolution: TurnResolutionType,
    *,
    without_hire: bool = False,
) -> list[FullTurnAction]:
    return [
        action
        for action in legal_actions(state, config)
        if isinstance(action, FullTurnAction)
        and action.resolution is resolution
        and (not without_hire or action.hired_building_id is None)
    ]


def _bonus_events(result, building_id: str):
    return [
        event
        for event in result.events
        if event.event_type is EventType.BUILDING_BONUS
        and dict(event.details).get("building") == building_id
    ]


def _state_with_building_locations(
    state,
    building_id: str,
    *,
    own_active: bool = False,
    own_donated: bool = False,
    opponent_active: bool = False,
):
    """Move one fixture building between the three ownership states relevant to a passive."""

    def slots_for(player, *, active: bool, donated: bool):
        slots = player.player_board_slots
        active_buildings = tuple(item for item in slots.active_buildings if item != building_id)
        donated_buildings = tuple(item for item in slots.donated_buildings if item != building_id)
        if active:
            active_buildings += (building_id,)
        if donated:
            donated_buildings += (building_id,)
        return replace(
            player,
            player_board_slots=replace(
                slots,
                active_buildings=active_buildings,
                donated_buildings=donated_buildings,
            ),
        )

    own = slots_for(
        state.player_state(PlayerId.PLAYER_ONE), active=own_active, donated=own_donated
    )
    opponent = slots_for(
        state.player_state(PlayerId.PLAYER_TWO), active=opponent_active, donated=False
    )
    return state.with_player_state(PlayerId.PLAYER_ONE, own).with_player_state(
        PlayerId.PLAYER_TWO, opponent
    )


def _not_selected_state(state, building_id: str):
    no_owner = _state_with_building_locations(state, building_id)
    return no_owner.with_building_market(
        tuple(item for item in no_owner.building_market if item != building_id)
    )


@pytest.mark.parametrize(
    (
        "building_id",
        "scenario_path",
        "resolution",
        "unrelated_resolution",
        "bonus_field",
    ),
    (
        (
            "chapel",
            "scenarios/clerical_devotion_chapel_001.json",
            TurnResolutionType.CLERICAL_DEVOTION,
            TurnResolutionType.CLERICAL_SILVERSMITH,
            "piety_bonus",
        ),
        (
            "mint",
            "scenarios/clerical_silversmith_mint_001.json",
            TurnResolutionType.CLERICAL_SILVERSMITH,
            TurnResolutionType.CLERICAL_DEVOTION,
            "silver_bonus",
        ),
        (
            "quarry",
            "scenarios/produce_stone_quarry_001.json",
            TurnResolutionType.PRODUCE_STONE,
            TurnResolutionType.PRODUCE_WHEAT,
            "stone_bonus",
        ),
        (
            "well",
            "scenarios/produce_wheat_well_001.json",
            TurnResolutionType.PRODUCE_WHEAT,
            TurnResolutionType.PRODUCE_STONE,
            "wheat_bonus",
        ),
    ),
)
def test_simple_passive_applies_only_on_its_owned_duty_and_not_other_locations(
    building_id: str,
    scenario_path: str,
    resolution: TurnResolutionType,
    unrelated_resolution: TurnResolutionType,
    bonus_field: str,
) -> None:
    scenario = load_scenario(scenario_path)
    own_actions = _actions_for(scenario.state, scenario.config, resolution, without_hire=True)

    assert own_actions
    assert all(
        dict(
            _bonus_events(
                apply_action(scenario.state, action, scenario.config),
                building_id,
            )[0].details
        )[bonus_field]
        == 1
        for action in own_actions
    )

    blocked_states = (
        (
            "donated",
            _state_with_building_locations(scenario.state, building_id, own_donated=True),
        ),
        (
            "opponent-owned",
            _state_with_building_locations(
                scenario.state,
                building_id,
                opponent_active=True,
            ),
        ),
        ("not-selected", _not_selected_state(scenario.state, building_id)),
    )
    blocked_actions = [
        (label, action)
        for label, state in blocked_states
        for action in _actions_for(state, scenario.config, resolution, without_hire=True)
    ]

    assert len(blocked_actions) >= len(blocked_states)
    assert all(
        not _bonus_events(
            apply_action(
                dict(blocked_states)[label],
                action,
                scenario.config,
            ),
            building_id,
        )
        for label, action in blocked_actions
    )

    unrelated_actions = _actions_for(
        scenario.state,
        scenario.config,
        unrelated_resolution,
        without_hire=True,
    )
    assert unrelated_actions
    assert all(
        not _bonus_events(apply_action(scenario.state, action, scenario.config), building_id)
        for action in unrelated_actions
    )


def test_scriptorium_only_changes_occupied_duties_when_its_source_is_available() -> None:
    scenario = load_scenario("scenarios/scriptorium_taxation_majority_other_tiles_001.json")
    boosted_actions = [
        action
        for action in _actions_for(
            scenario.state,
            scenario.config,
            TurnResolutionType.TAXATION,
        )
        if action.effective_acolyte_building_id == "scriptorium"
    ]

    assert boosted_actions
    assert all(
        _bonus_events(apply_action(scenario.state, action, scenario.config), "scriptorium")
        for action in boosted_actions
    )

    unavailable_states = (
        _state_with_building_locations(scenario.state, "scriptorium", own_donated=True),
        _state_with_building_locations(scenario.state, "scriptorium", opponent_active=True),
        _not_selected_state(scenario.state, "scriptorium"),
        load_scenario("scenarios/scriptorium_no_occupied_duty_no_modifier_001.json").state,
    )
    unavailable_actions = [
        action for state in unavailable_states for action in legal_actions(state, scenario.config)
    ]

    assert len(unavailable_actions) >= len(unavailable_states)
    assert all(action.effective_acolyte_building_id is None for action in unavailable_actions)

    tithe_actions = _actions_for(
        scenario.state,
        scenario.config,
        TurnResolutionType.TITHE,
        without_hire=True,
    )
    assert tithe_actions
    assert all(action.effective_acolyte_building_id is None for action in tithe_actions)


def test_infirmary_only_extends_allocation_or_a_paid_extra_ordination_step() -> None:
    allocation = load_scenario("scenarios/allocation_infirmary_001.json")
    boosted_allocation_actions = [
        action
        for action in _actions_for(
            allocation.state,
            allocation.config,
            TurnResolutionType.ALLOCATION,
            without_hire=True,
        )
        if len(action.allocation_moves) == 2
    ]

    assert boosted_allocation_actions
    assert all(
        _bonus_events(apply_action(allocation.state, action, allocation.config), "infirmary")
        for action in boosted_allocation_actions
    )

    unavailable_states = (
        _state_with_building_locations(allocation.state, "infirmary", own_donated=True),
        _state_with_building_locations(allocation.state, "infirmary", opponent_active=True),
        _not_selected_state(allocation.state, "infirmary"),
    )
    unavailable_actions = [
        action
        for state in unavailable_states
        for action in _actions_for(
            state,
            allocation.config,
            TurnResolutionType.ALLOCATION,
            without_hire=True,
        )
    ]

    assert len(unavailable_actions) >= len(unavailable_states)
    assert all(
        len(action.allocation_moves) == 1
        and not _bonus_events(apply_action(state, action, allocation.config), "infirmary")
        for state in unavailable_states
        for action in _actions_for(
            state,
            allocation.config,
            TurnResolutionType.ALLOCATION,
            without_hire=True,
        )
    )

    ordination = load_scenario("scenarios/ordination_infirmary_extra_step_001.json")
    ordinary_ordination_actions = [
        action
        for action in _actions_for(
            ordination.state,
            ordination.config,
            TurnResolutionType.ORDINATION,
            without_hire=True,
        )
        if len(action.ordination_steps) == 1
    ]

    assert ordinary_ordination_actions
    assert all(
        not _bonus_events(apply_action(ordination.state, action, ordination.config), "infirmary")
        for action in ordinary_ordination_actions
    )

    boosted_ordination_actions = [
        action
        for action in _actions_for(
            ordination.state,
            ordination.config,
            TurnResolutionType.ORDINATION,
            without_hire=True,
        )
        if len(action.ordination_steps) == 2
    ]
    assert boosted_ordination_actions
    assert all(
        dict(
            _bonus_events(
                apply_action(ordination.state, action, ordination.config),
                "infirmary",
            )[0].details
        )["extra_wheat_cost_paid"]
        is True
        for action in boosted_ordination_actions
    )

    tithe_actions = _actions_for(
        allocation.state,
        allocation.config,
        TurnResolutionType.TITHE,
        without_hire=True,
    )
    assert tithe_actions
    assert all(
        not _bonus_events(apply_action(allocation.state, action, allocation.config), "infirmary")
        for action in tithe_actions
    )


def test_mill_waives_wheat_only_for_paid_alms_and_ordination() -> None:
    alms = load_scenario("scenarios/give_alms_mill_active_wheat3_spend1_001.json")
    waived_alms_actions = [
        action
        for action in _actions_for(
            alms.state,
            alms.config,
            TurnResolutionType.GIVE_ALMS_PAID,
            without_hire=True,
        )
        if action.alms_payment_wheat > 0
    ]

    assert waived_alms_actions
    assert all(
        dict(_bonus_events(apply_action(alms.state, action, alms.config), "mill")[0].details)[
            "wheat_waived"
        ]
        == min(2, action.alms_payment_wheat)
        for action in waived_alms_actions
    )

    ordination = load_scenario("scenarios/ordination_mill_active_two_steps_free_001.json")
    waived_ordination_actions = [
        action
        for action in _actions_for(
            ordination.state,
            ordination.config,
            TurnResolutionType.ORDINATION,
            without_hire=True,
        )
        if len(action.ordination_steps) == 2
    ]
    assert waived_ordination_actions
    assert all(
        dict(
            _bonus_events(
                apply_action(ordination.state, action, ordination.config),
                "mill",
            )[0].details
        )["wheat_waived"]
        == 2
        for action in waived_ordination_actions
    )

    unavailable_states = (
        _state_with_building_locations(alms.state, "mill", own_donated=True),
        _state_with_building_locations(alms.state, "mill", opponent_active=True),
        _not_selected_state(alms.state, "mill"),
    )
    unavailable_actions = [
        action
        for state in unavailable_states
        for action in _actions_for(
            state,
            alms.config,
            TurnResolutionType.GIVE_ALMS_PAID,
            without_hire=True,
        )
    ]

    assert len(unavailable_actions) >= len(unavailable_states)
    assert all(
        not _bonus_events(apply_action(state, action, alms.config), "mill")
        for state in unavailable_states
        for action in _actions_for(
            state,
            alms.config,
            TurnResolutionType.GIVE_ALMS_PAID,
            without_hire=True,
        )
    )

    unrelated_actions = _actions_for(
        alms.state,
        alms.config,
        TurnResolutionType.GIVE_ALMS_DONATE_BUILDING,
        without_hire=True,
    )
    assert unrelated_actions
    assert all(
        not _bonus_events(apply_action(alms.state, action, alms.config), "mill")
        for action in unrelated_actions
    )
