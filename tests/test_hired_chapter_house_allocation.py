from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

import pilgrim.rules.transition as transition
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import FullTurnAction
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules.transition import apply_action, legal_actions
from pilgrim.rules.validation import TransitionValidationError

SCENARIO = "scenarios/allocation_hire_infirmary_chapter_house_bank_001.json"
ACTION_BUILDINGS = frozenset({"infirmary", "chapter_house"})


def _resource_cost(before, after) -> tuple[int, int, int]:
    return (
        before.stone - after.stone,
        before.silver - after.silver,
        before.wheat - after.wheat,
    )


def _named_hire_cost(event) -> tuple[int, int, int]:
    details = dict(event.details)
    amount = int(details["amount"])
    resource = details["resource"]
    return (
        amount if resource == "stone" else 0,
        amount if resource == "silver" else 0,
        amount if resource == "wheat" else 0,
    )


def _action_building_hires(action) -> frozenset[str]:
    if not isinstance(action, FullTurnAction):
        return frozenset()
    return frozenset(
        (
            {action.hired_building_id}
            | {building_id for building_id, _resource in action.hire_payments}
        )
        & ACTION_BUILDINGS
    )


def test_allocation_offers_each_action_building_alone_but_never_both() -> None:
    scenario = load_scenario(SCENARIO)
    actions = [
        action
        for action in legal_actions(scenario.state, scenario.config)
        if action.resolution is TurnResolutionType.ALLOCATION
    ]

    hired_buildings = {_action_building_hires(action) for action in actions}

    assert hired_buildings == {
        frozenset(),
        frozenset({"infirmary"}),
        frozenset({"chapter_house"}),
    }


def test_chapter_house_hires_use_capacity_and_charge_their_named_cost() -> None:
    scenario = load_scenario(SCENARIO)
    chapter_house_hires = [
        action
        for action in legal_actions(scenario.state, scenario.config)
        if action.resolution is TurnResolutionType.ALLOCATION
        and action.hired_building_id == "chapter_house"
    ]

    player_state = scenario.state.player_state(PlayerId.PLAYER_ONE)
    measurements = []
    for action in chapter_house_hires:
        applied = apply_action(scenario.state, action, scenario.config)
        hire_event = next(
            event
            for event in applied.events
            if event.event_type is EventType.BUILDING_HIRED
            and dict(event.details)["building_id"] == "chapter_house"
        )
        measurements.append(
            (
                transition._allocation_sequence_uses_chapter_house(
                    player_state,
                    action.allocation_moves,
                ),
                _named_hire_cost(hire_event),
                _resource_cost(
                    player_state.resources,
                    applied.state.player_state(PlayerId.PLAYER_ONE).resources,
                ),
            )
        )

    assert measurements and all(
        uses_capacity and named_cost == cost
        for uses_capacity, named_cost, cost in measurements
    )


def test_action_building_hire_guard_rejects_a_combined_allocation() -> None:
    scenario = load_scenario(SCENARIO)
    infirmary_hire = next(
        action
        for action in legal_actions(scenario.state, scenario.config)
        if action.resolution is TurnResolutionType.ALLOCATION
        and action.hired_building_id == "infirmary"
        and action.bank_payment_building_id is None
    )
    combined = replace(
        infirmary_hire,
        hire_payments=(
            ("chapter_house", "wheat"),
            ("infirmary", "wheat"),
        ),
    )

    with pytest.raises(TransitionValidationError, match="at most one action building"):
        apply_action(scenario.state, combined, scenario.config)


def test_no_legal_candidate_has_two_action_building_hires() -> None:
    scenario_paths = sorted(Path("scenarios").rglob("*.json"))
    offenders = []
    for path in scenario_paths:
        scenario = load_scenario(path)
        for action in legal_actions(scenario.state, scenario.config):
            hired = _action_building_hires(action)
            if len(hired) > 1:
                offenders.append((path.name, action.action_type.value, tuple(sorted(hired))))

    assert not offenders
