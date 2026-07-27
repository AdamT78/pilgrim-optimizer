from __future__ import annotations

import random

from pilgrim.setup.timeline import (
    TOTAL_BORDER_ROUNDS,
    assign_building_live_rounds,
    build_abstract_setup_timeline,
    generate_pilgrimage_rolls,
    pilgrimage_rounds_from_rolls,
)


def test_pilgrimage_round_mapping_matches_example_one() -> None:
    rounds = pilgrimage_rounds_from_rolls(
        {
            "nw": 1,
            "ne": 4,
            "se": 2,
            "sw": 4,
        }
    )
    assert rounds == {
        "site_1": 1,
        "site_2": 10,
        "site_3": 15,
        "site_4": 23,
    }


def test_pilgrimage_round_mapping_handles_adjacent_site_two_case() -> None:
    rounds = pilgrimage_rounds_from_rolls(
        {
            "nw": 6,
            "ne": 1,
            "se": 6,
            "sw": 6,
        }
    )
    assert rounds["site_1"] == 1
    assert rounds["site_2"] == 2


def test_generated_pilgrimage_rolls_use_d6_for_all_quadrants() -> None:
    rng = random.Random(123)
    for _ in range(200):
        rolls = generate_pilgrimage_rolls(rng)
        assert 1 <= rolls["nw"] <= 6
        assert 1 <= rolls["ne"] <= 6
        assert 1 <= rolls["se"] <= 6
        assert 1 <= rolls["sw"] <= 6


def test_building_live_rounds_match_example_one() -> None:
    building_market, building_levels = _example_market_and_levels()
    rounds = pilgrimage_rounds_from_rolls({"nw": 1, "ne": 4, "se": 2, "sw": 4})
    timeline = build_abstract_setup_timeline(
        pilgrimage_rounds=rounds,
        building_market=building_market,
        building_levels=building_levels,
    )
    availability = assign_building_live_rounds(
        timeline=timeline,
        building_market=building_market,
    )

    level_1_rounds = [availability[building_id] for building_id in building_market[:4]]
    level_2_rounds = [availability[building_id] for building_id in building_market[4:8]]
    level_3_rounds = [availability[building_id] for building_id in building_market[8:12]]
    assert level_1_rounds == [3, 4, 5, 6]
    assert level_2_rounds == [12, 13, 14, 17]
    assert level_3_rounds == [19, 20, 21, 22]


def test_adjacent_site_two_placement_starts_level_one_at_round_four() -> None:
    building_market, building_levels = _example_market_and_levels()
    rounds = pilgrimage_rounds_from_rolls({"nw": 6, "ne": 1, "se": 6, "sw": 6})
    timeline = build_abstract_setup_timeline(
        pilgrimage_rounds=rounds,
        building_market=building_market,
        building_levels=building_levels,
    )
    availability = assign_building_live_rounds(
        timeline=timeline,
        building_market=building_market,
    )
    slots = {slot.round_number: slot for slot in timeline}

    assert rounds["site_2"] == 2
    assert slots[1].kind == "pilgrimage_site"
    assert slots[2].kind == "pilgrimage_site"
    assert slots[3].kind == "empty_after_pilgrimage"
    assert availability[building_market[0]] == 4
    assert availability[building_market[4]] == 9


def test_timeline_invariants_hold_for_example_mapping() -> None:
    building_market, building_levels = _example_market_and_levels()
    rounds = pilgrimage_rounds_from_rolls({"nw": 1, "ne": 4, "se": 2, "sw": 4})
    timeline = build_abstract_setup_timeline(
        pilgrimage_rounds=rounds,
        building_market=building_market,
        building_levels=building_levels,
    )
    availability = assign_building_live_rounds(
        timeline=timeline,
        building_market=building_market,
    )

    site_rounds = set(rounds.values())
    level_1_rounds = [availability[building_id] for building_id in building_market[:4]]
    level_2_rounds = [availability[building_id] for building_id in building_market[4:8]]
    level_3_rounds = [availability[building_id] for building_id in building_market[8:12]]

    assert len(availability) == len(building_market)
    assert set(availability) == set(building_market)
    assert len(set(availability.values())) == len(building_market)

    for live_round in availability.values():
        assert live_round not in site_rounds
        assert live_round - 1 not in site_rounds

    assert max(level_1_rounds) < min(level_2_rounds)
    assert max(level_2_rounds) < min(level_3_rounds)

    first_level_2 = min(level_2_rounds)
    first_level_3 = min(level_3_rounds)
    assert first_level_2 >= max(
        max(level_1_rounds) + 2,
        _round_after_site_gap(rounds["site_2"], site_rounds),
    )
    assert first_level_3 >= max(
        max(level_2_rounds) + 2,
        _round_after_site_gap(rounds["site_3"], site_rounds),
    )
    assert all(1 <= live_round <= TOTAL_BORDER_ROUNDS for live_round in availability.values())


def _example_market_and_levels() -> tuple[list[str], dict[str, int]]:
    market = [
        "l1_a",
        "l1_b",
        "l1_c",
        "l1_d",
        "l2_a",
        "l2_b",
        "l2_c",
        "l2_d",
        "l3_a",
        "l3_b",
        "l3_c",
        "l3_d",
    ]
    levels = {
        "l1_a": 1,
        "l1_b": 1,
        "l1_c": 1,
        "l1_d": 1,
        "l2_a": 2,
        "l2_b": 2,
        "l2_c": 2,
        "l2_d": 2,
        "l3_a": 3,
        "l3_b": 3,
        "l3_c": 3,
        "l3_d": 3,
    }
    return market, levels


def _round_after_site_gap(site_round: int, all_site_rounds: set[int]) -> int:
    candidate = site_round + 1
    while candidate in all_site_rounds:
        candidate += 1
    return candidate + 1
