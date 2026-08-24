from __future__ import annotations

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.rules.building_turn_modifiers import (
    all_building_turn_modifiers,
    implemented_turn_modifiers,
    scaffolded_turn_modifiers,
    turn_modifiers_for_building,
    turn_modifiers_for_category,
    turn_modifiers_for_phase,
)
from pilgrim.rules.transition import legal_actions


def _signature(entry) -> tuple[str, str, str, str, str, str]:
    return (
        entry.building_key,
        entry.category,
        entry.phase,
        entry.effect,
        entry.status,
        entry.notes,
    )


def test_turn_modifier_registry_contains_expected_entries() -> None:
    signatures = {_signature(entry) for entry in all_building_turn_modifiers()}
    assert signatures == {
        (
            "kogge",
            "sow_route_modifier",
            "during_sow",
            "adds city -> east and city -> west sow options",
            "implemented",
            "implemented in transition sow-route generation and apply validation/events.",
        ),
        (
            "cloisters",
            "sow_route_modifier",
            "during_sow",
            "may skip one Duty tile or the city when moving acolytes to Duty actions",
            "implemented",
            (
                "implemented as optional sow-route skip modifier using candidate N+1 placements "
                "with one omitted placement."
            ),
        ),
        (
            "dormitory",
            "start_turn_relocation",
            "start_of_turn",
            "may return 1 acolyte from any Duty action to City",
            "implemented",
            "implemented as an optional committed step before resolution.",
        ),
        (
            "inquisition",
            "start_turn_relocation",
            "start_of_turn",
            "may move 1 acolyte from City to any Duty",
            "implemented",
            "implemented as an optional committed step before resolution.",
        ),
        (
            "library",
            "end_turn_relocation",
            "end_of_turn",
            "may move 1 acolyte from City directly to a Duty action or back to Abbey",
            "implemented",
            "implemented as optional post-turn end-turn relocation action suffix.",
        ),
    }


def test_turn_modifier_category_and_phase_groupings() -> None:
    assert {entry.building_key for entry in turn_modifiers_for_category("sow_route_modifier")} == {
        "kogge",
        "cloisters",
    }
    assert {
        entry.building_key for entry in turn_modifiers_for_category("start_turn_relocation")
    } == {"dormitory", "inquisition"}
    assert {entry.building_key for entry in turn_modifiers_for_category("end_turn_relocation")} == {
        "library"
    }

    assert {entry.building_key for entry in turn_modifiers_for_phase("during_sow")} == {
        "kogge",
        "cloisters",
    }
    assert {entry.building_key for entry in turn_modifiers_for_phase("start_of_turn")} == {
        "dormitory",
        "inquisition",
    }
    assert {entry.building_key for entry in turn_modifiers_for_phase("end_of_turn")} == {"library"}


def test_turn_modifier_lookup_by_building_is_normalized() -> None:
    kogge_entries = turn_modifiers_for_building(" KOGGE ")
    assert len(kogge_entries) == 1
    assert kogge_entries[0].phase == "during_sow"
    assert turn_modifiers_for_building("cloisters")
    with pytest.raises(ValueError, match="cannot be empty"):
        turn_modifiers_for_building("  ")


def test_turn_modifier_status_helpers() -> None:
    assert {entry.building_key for entry in implemented_turn_modifiers()} == {
        "kogge",
        "cloisters",
        "dormitory",
        "inquisition",
        "library",
    }
    assert scaffolded_turn_modifiers() == ()


def test_turn_modifier_registry_has_no_duplicate_exact_entries() -> None:
    entries = all_building_turn_modifiers()
    assert len(entries) == len(set(entries))


def test_all_turn_modifiers_are_implemented_in_registry() -> None:
    scenario = load_scenario("scenarios/ordination_mill_active_two_steps_free_001.json")
    base_actions = legal_actions(scenario.state, scenario.config)
    assert base_actions
    assert scaffolded_turn_modifiers() == ()
