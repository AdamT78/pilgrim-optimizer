from __future__ import annotations

from pilgrim.rules.duty_enhancements import (
    DutyEnhancement,
    all_duty_enhancements,
    enhancements_by_source,
    enhancements_for_action,
    enhancements_for_duty,
    implemented_enhancements,
    unimplemented_enhancements,
)


def _signature(entry: DutyEnhancement) -> tuple[str, str, str, str, str, str]:
    return (
        entry.duty,
        entry.action_key,
        entry.source_type,
        entry.source_key,
        entry.effect,
        entry.status,
    )


def test_registry_contains_all_required_entries() -> None:
    signatures = {_signature(entry) for entry in all_duty_enhancements()}
    expected = {
        ("produce", "produce_wheat", "special_activity", "fields", "+1 wheat", "implemented"),
        ("produce", "produce_stone", "special_activity", "stone_mason", "+1 stone", "implemented"),
        ("clerical", "clerical_devotion", "special_activity", "vestry", "+1 piety", "implemented"),
        (
            "clerical",
            "clerical_silversmith",
            "special_activity",
            "engraver",
            "+1 silver",
            "implemented",
        ),
        (
            "give_alms",
            "give_alms",
            "special_activity",
            "alms_house",
            "optional +1 effective Duty Value with extra payment",
            "implemented",
        ),
        (
            "build_roads",
            "build_roads_deferred",
            "special_activity",
            "road_engineer",
            "+1 effective Duty Value",
            "implemented_scaffolded",
        ),
        (
            "construct",
            "construct_deferred",
            "special_activity",
            "road_engineer",
            "extra deferred road only if road already included",
            "implemented_scaffolded",
        ),
        (
            "allocation",
            "allocation",
            "building",
            "infirmary",
            "+1 effective Duty Value",
            "known_unimplemented",
        ),
        (
            "allocation",
            "all_special_activity_spaces",
            "building",
            "chapter_house",
            "affects all Special Activity spaces",
            "deferred_special_activity_system",
        ),
        (
            "clerical",
            "clerical_silversmith",
            "building",
            "mint",
            "+1 silver",
            "known_unimplemented",
        ),
        (
            "clerical",
            "clerical_devotion",
            "building",
            "chapel",
            "+1 piety",
            "known_unimplemented",
        ),
        ("give_alms", "give_alms", "building", "mill", "deferred", "known_unimplemented"),
        ("ordination", "ordination", "building", "mill", "deferred", "known_unimplemented"),
        (
            "ordination",
            "ordination",
            "building",
            "infirmary",
            "+1 effective Duty Value if wheat cost is paid",
            "known_unimplemented",
        ),
        ("produce", "produce_wheat", "building", "well", "+1 wheat", "known_unimplemented"),
        ("produce", "produce_stone", "building", "quarry", "+1 stone", "known_unimplemented"),
    }

    assert signatures == expected


def test_building_effects_are_registered_but_not_marked_implemented() -> None:
    building_entries = [
        entry for entry in all_duty_enhancements() if entry.source_type == "building"
    ]
    assert len(building_entries) == 9
    assert all(
        entry.status not in {"implemented", "implemented_scaffolded"} for entry in building_entries
    )
    assert any(
        entry.source_key == "chapter_house"
        and entry.status == "deferred_special_activity_system"
        for entry in building_entries
    )


def test_implemented_special_activity_effects_appear_in_registry() -> None:
    implemented = {
        (entry.source_key, entry.action_key, entry.status) for entry in implemented_enhancements()
    }
    expected_special_activity_entries = {
        ("fields", "produce_wheat", "implemented"),
        ("stone_mason", "produce_stone", "implemented"),
        ("vestry", "clerical_devotion", "implemented"),
        ("engraver", "clerical_silversmith", "implemented"),
        ("alms_house", "give_alms", "implemented"),
        ("road_engineer", "build_roads_deferred", "implemented_scaffolded"),
        ("road_engineer", "construct_deferred", "implemented_scaffolded"),
    }

    assert expected_special_activity_entries <= implemented


def test_registry_has_no_duplicate_exact_entries() -> None:
    entries = all_duty_enhancements()
    assert len(entries) == len(set(entries))


def test_lookup_helpers_return_expected_subsets() -> None:
    produce_entries = enhancements_for_duty("produce")
    assert [entry.source_key for entry in produce_entries] == [
        "fields",
        "stone_mason",
        "well",
        "quarry",
    ]

    give_alms_entries = enhancements_for_action("give_alms")
    assert [(entry.source_type, entry.source_key) for entry in give_alms_entries] == [
        ("special_activity", "alms_house"),
        ("building", "mill"),
    ]

    road_engineer_entries = enhancements_by_source("road_engineer")
    assert [(entry.duty, entry.action_key) for entry in road_engineer_entries] == [
        ("build_roads", "build_roads_deferred"),
        ("construct", "construct_deferred"),
    ]

    implemented = set(implemented_enhancements())
    unimplemented = set(unimplemented_enhancements())
    assert implemented.isdisjoint(unimplemented)
    assert implemented | unimplemented == set(all_duty_enhancements())
