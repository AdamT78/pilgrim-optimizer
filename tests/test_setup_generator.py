from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.duties import DUTY_CATEGORIES, DUTY_POSITIONS
from pilgrim.model.enums import TurnResolutionType
from pilgrim.rules.buildings import load_building_config
from pilgrim.rules.transition import legal_actions
from pilgrim.setup.generator import generate_setup_scenario


def test_setup_generator_same_seed_produces_same_output() -> None:
    generated_a = generate_setup_scenario(player_count=2, seed=123)
    generated_b = generate_setup_scenario(player_count=2, seed=123)
    assert generated_a == generated_b


def test_setup_generator_different_seed_changes_layout_or_market_or_counters() -> None:
    generated_a = generate_setup_scenario(player_count=2, seed=123)
    generated_b = generate_setup_scenario(player_count=2, seed=124)

    differs = (
        generated_a["duty_tiles"] != generated_b["duty_tiles"]
        or generated_a["tithe_counters"] != generated_b["tithe_counters"]
        or generated_a["initial_state"]["building_market"]  # type: ignore[index]
        != generated_b["initial_state"]["building_market"]  # type: ignore[index]
        or generated_a["initial_state"]["building_availability"]  # type: ignore[index]
        != generated_b["initial_state"]["building_availability"]  # type: ignore[index]
    )
    assert differs


def test_setup_generator_does_not_use_global_random_state() -> None:
    random.seed(789)
    _ = random.random()
    expected_next = random.random()

    random.seed(789)
    _ = random.random()
    generate_setup_scenario(player_count=2, seed=123)
    actual_next = random.random()

    assert actual_next == expected_next


@pytest.mark.parametrize(
    ("player_count", "expected_player_ids"),
    (
        (2, ("player_one", "player_two")),
        (3, ("player_one", "player_two", "player_three")),
        (4, ("player_one", "player_two", "player_three", "player_four")),
    ),
)
def test_setup_generator_player_count_controls_generated_player_ids(
    player_count: int,
    expected_player_ids: tuple[str, ...],
) -> None:
    generated = generate_setup_scenario(player_count=player_count, seed=123)
    players = generated["initial_state"]["players"]  # type: ignore[index]
    assert tuple(players.keys()) == expected_player_ids


@pytest.mark.parametrize("player_count", (2, 3, 4))
def test_setup_generator_uses_string_root_player_id(player_count: int) -> None:
    generated = generate_setup_scenario(player_count=player_count, seed=123)
    assert generated["root_player_id"] == "player_one"


def test_setup_generator_rejects_invalid_player_count() -> None:
    with pytest.raises(ValueError, match="Unsupported player count"):
        generate_setup_scenario(player_count=5, seed=123)


def test_setup_generator_duty_tiles_have_complete_unique_layout() -> None:
    generated = generate_setup_scenario(player_count=2, seed=123)
    duty_tiles = generated["duty_tiles"]  # type: ignore[index]

    assert set(duty_tiles.keys()) == set(DUTY_POSITIONS)
    assert "city" not in duty_tiles
    assert set(duty_tiles.values()) == set(DUTY_CATEGORIES)
    assert len(set(duty_tiles.values())) == len(DUTY_CATEGORIES)


def test_setup_generator_tithe_counter_pool_and_taxation_gap() -> None:
    generated = generate_setup_scenario(player_count=2, seed=123)
    duty_tiles = generated["duty_tiles"]  # type: ignore[index]
    tithe_counters = generated["tithe_counters"]  # type: ignore[index]
    taxation_position = next(
        position for position, category in duty_tiles.items() if category == "taxation"
    )

    assert taxation_position not in tithe_counters
    assert set(tithe_counters).issubset(set(DUTY_POSITIONS))
    values = list(tithe_counters.values())
    assert values.count("stone") == 2
    assert values.count("wheat") == 2
    assert values.count("silver") == 2
    assert values.count("cornucopia") == 1


def test_setup_generator_building_market_is_12_with_4_per_level_and_no_duplicates() -> None:
    generated = generate_setup_scenario(player_count=2, seed=123)
    building_market = generated["initial_state"]["building_market"]  # type: ignore[index]
    building_availability = generated["initial_state"]["building_availability"]  # type: ignore[index]
    building_config = load_building_config(
        json.loads(Path("configs/buildings.json").read_text(encoding="utf-8"))
    )

    assert len(building_market) == 12
    assert len(set(building_market)) == 12
    level_counts = {1: 0, 2: 0, 3: 0}
    for building_id in building_market:
        level_counts[building_config.definition_by_id(building_id).level] += 1
    assert level_counts == {1: 4, 2: 4, 3: 4}
    assert set(building_availability) == set(building_market)
    assert all(2 <= int(live_round) <= 26 for live_round in building_availability.values())


@pytest.mark.parametrize(
    ("player_count", "expected_per_group"),
    ((2, 3), (3, 2), (4, 0)),
)
def test_setup_generator_dummy_acolytes_match_player_count(
    player_count: int,
    expected_per_group: int,
) -> None:
    generated = generate_setup_scenario(player_count=player_count, seed=123)
    dummy = generated["initial_state"]["dummy_acolytes"]  # type: ignore[index]
    assert sum(dummy["north_group"]) == expected_per_group
    assert sum(dummy["south_group"]) == expected_per_group
    assert dummy["north_group"][0] == 0
    assert dummy["south_group"][0] == 0


def test_setup_generator_initial_state_and_metadata_defaults() -> None:
    generated = generate_setup_scenario(player_count=2, seed=123)
    initial_state = generated["initial_state"]  # type: ignore[index]
    metadata = generated["setup_metadata"]  # type: ignore[index]
    players = initial_state["players"]

    assert initial_state["active_player"] == "player_one"
    assert initial_state["start_player_id"] == "player_one"
    assert initial_state["phase"] == "setup_sow"
    assert initial_state["setup"] == {
        "setup_sow_required": True,
        "setup_sow_complete": False,
        "setup_sow_completed_by": [],
    }
    assert initial_state["ship_position"] == 0
    assert initial_state["merchant_position"] == 0
    assert initial_state["completed_rounds"] == 0
    assert initial_state["game_over"] is False
    assert initial_state["timing"]["absolute_turn"] == 0
    assert initial_state["timing"]["round_number"] == 1
    assert initial_state["timing"]["season_number"] == 1
    assert initial_state["timing"]["turn_in_round"] == 0
    assert len(initial_state["building_availability"]) == len(initial_state["building_market"])

    assert metadata["generated"] is True
    assert metadata["setup_sow_required"] is True
    assert metadata["setup_sow_implemented"] is True
    assert "note" in metadata

    for player_id in ("player_one", "player_two"):
        player_state = players[player_id]
        assert player_state["resources"] == {"stone": 1, "silver": 1, "wheat": 1}
        assert player_state["workforce"]["mancala"] == [5, 0, 0, 0, 0, 0, 0, 0, 0]
        assert player_state["workforce"]["village"] == 8
        assert player_state["workforce"]["abbey"] == 3


def test_cornucopia_is_valid_counter_and_unlocks_all_step2_resource_types(tmp_path: Path) -> None:
    scenario_raw = _absolute_base_scenario_raw()
    scenario_raw["scenario_id"] = "tmp_taxation_cornucopia"
    scenario_raw["player_count"] = 4
    scenario_raw["duty_tiles"] = {
        "north": "taxation",
        "north_east": "clerical",
        "east": "build_roads",
        "south_east": "construct",
        "south": "give_alms",
        "south_west": "ordination",
        "west": "allocation",
        "north_west": "produce",
    }
    scenario_raw["tithe_counters"] = {
        "west": "cornucopia",
    }
    scenario_raw["initial_state"] = {
        "active_player": "player_one",
        "start_player_id": "player_one",
        "phase": "sow",
        "merchant_position": 0,
        "ship_position": 0,
        "completed_rounds": 0,
        "game_over": False,
        "timing": {
            "absolute_turn": 0,
            "round_number": 1,
            "season_number": 1,
            "turn_in_round": 0,
        },
        "players": {
            "player_one": {
                "resources": {"stone": 0, "silver": 0, "wheat": 0},
                "workforce": {
                    "mancala": [1, 0, 0, 0, 0, 0, 0, 1, 0],
                    "village": 0,
                    "abbey": 0,
                },
            },
            "player_two": {
                "resources": {"stone": 0, "silver": 0, "wheat": 0},
                "workforce": {
                    "mancala": [0, 0, 0, 0, 0, 0, 0, 0, 0],
                    "village": 0,
                    "abbey": 0,
                },
            },
        },
    }
    scenario_path = tmp_path / "tmp_taxation_cornucopia.json"
    scenario_path.write_text(json.dumps(scenario_raw), encoding="utf-8")
    scenario = load_scenario(scenario_path)

    taxation_actions = [
        action
        for action in legal_actions(scenario.state, scenario.config)
        if action.resolution is TurnResolutionType.TAXATION
        and action.taxation_step1_resource == "stone"
    ]
    step2_choices = {action.taxation_step2_resources for action in taxation_actions}
    assert step2_choices == {
        ("stone", "stone"),
        ("stone", "silver"),
        ("stone", "wheat"),
        ("silver", "silver"),
        ("silver", "wheat"),
        ("wheat", "wheat"),
    }
    assert all("cornucopia" not in action.taxation_step2_resources for action in taxation_actions)


def _absolute_base_scenario_raw() -> dict[str, object]:
    root = Path.cwd().resolve()
    return {
        "board_file": str((root / "configs" / "board.json").resolve()),
        "duties_file": str((root / "configs" / "duties.json").resolve()),
        "piety_file": str((root / "configs" / "piety.json").resolve()),
        "alms_file": str((root / "configs" / "alms.json").resolve()),
        "timing_file": str((root / "configs" / "timing.json").resolve()),
        "merchant_file": str((root / "configs" / "merchant.json").resolve()),
        "ship_file": str((root / "configs" / "ship.json").resolve()),
        "buildings_file": str((root / "configs" / "buildings.json").resolve()),
        "root_player_id": 0,
        "opponent_model": {"type": "sandbox_active_player_max"},
    }
