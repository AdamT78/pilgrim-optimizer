from __future__ import annotations

from pilgrim.io.scenarios import load_scenario
from pilgrim.setup.generator import generate_setup_scenario


def test_generate_setup_timeline_same_seed_is_deterministic() -> None:
    generated_a = generate_setup_scenario(player_count=2, seed=123)
    generated_b = generate_setup_scenario(player_count=2, seed=123)

    metadata_a = generated_a["setup_metadata"]["setup_timeline"]  # type: ignore[index]
    metadata_b = generated_b["setup_metadata"]["setup_timeline"]  # type: ignore[index]
    availability_a = generated_a["initial_state"]["building_availability"]  # type: ignore[index]
    availability_b = generated_b["initial_state"]["building_availability"]  # type: ignore[index]

    assert metadata_a["pilgrimage_rolls"] == metadata_b["pilgrimage_rolls"]
    assert metadata_a["pilgrimage_rounds"] == metadata_b["pilgrimage_rounds"]
    assert availability_a == availability_b


def test_generate_setup_timeline_different_seed_can_change_rolls() -> None:
    generated_a = generate_setup_scenario(player_count=2, seed=123)
    generated_b = generate_setup_scenario(player_count=2, seed=124)

    rolls_a = generated_a["setup_metadata"]["setup_timeline"]["pilgrimage_rolls"]  # type: ignore[index]
    rolls_b = generated_b["setup_metadata"]["setup_timeline"]["pilgrimage_rolls"]  # type: ignore[index]
    availability_a = generated_a["initial_state"]["building_availability"]  # type: ignore[index]
    availability_b = generated_b["initial_state"]["building_availability"]  # type: ignore[index]

    assert rolls_a != rolls_b or availability_a != availability_b


def test_generate_setup_timeline_metadata_contains_rolls_rounds_and_levels() -> None:
    generated = generate_setup_scenario(player_count=2, seed=123)
    timeline = generated["setup_metadata"]["setup_timeline"]  # type: ignore[index]
    rounds = timeline["pilgrimage_rounds"]
    level_rounds = timeline["building_live_rounds"]

    assert set(timeline["pilgrimage_rolls"]) == {"nw", "ne", "se", "sw"}
    assert rounds["site_1"] == 1
    assert set(rounds) == {"site_1", "site_2", "site_3", "site_4"}
    assert set(level_rounds) == {"level_1", "level_2", "level_3"}
    assert len(level_rounds["level_1"]) == 4
    assert len(level_rounds["level_2"]) == 4
    assert len(level_rounds["level_3"]) == 4


def test_loader_fallback_without_building_availability_remains_round_two() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    state = scenario.state

    assert len(state.building_availability) == len(state.building_market)
    assert all(live_round == 2 for _, live_round in state.building_availability)
