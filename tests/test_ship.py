import json
from pathlib import Path

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.config import ShipConfig
from pilgrim.rules.ship import advance_ship_position, is_nw_pilgrimage_site, is_pilgrimage_site


def test_ship_config_loads_expected_defaults() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    ship = scenario.config.ship
    assert ship.path_length == 26
    assert ship.start_position == 0
    assert ship.nw_pilgrimage_site_position == 0
    assert ship.pilgrimage_site_positions == (4, 8, 13, 17, 21, 0)


def test_ship_advances_and_wraps_by_one_per_round() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    ship = scenario.config.ship
    assert advance_ship_position(0, ship) == 1
    assert advance_ship_position(25, ship) == 0


@pytest.mark.parametrize(
    ("scenario_path", "expected_position", "expected_rounds"),
    (
        ("scenarios/dummy_season_move_001.json", 2, 2),
        ("scenarios/season_end_alms_001.json", 2, 2),
        ("scenarios/playtest/conversions_2p.json", 1, 1),
    ),
)
def test_ship_fixture_position_matches_its_completed_rounds(
    scenario_path: str,
    expected_position: int,
    expected_rounds: int,
) -> None:
    """Fixtures retain the round-marker position that their complete-round count reached."""
    initial_state = json.loads(Path(scenario_path).read_text(encoding="utf-8"))["initial_state"]
    scenario = load_scenario(scenario_path)

    assert (
        int(initial_state["ship_position"]),
        int(initial_state["completed_rounds"]),
    ) == (expected_position, expected_rounds)
    assert (scenario.state.ship_position, scenario.state.completed_rounds) == (
        expected_position,
        expected_rounds,
    )
    assert scenario.state.ship_position == (
        scenario.config.ship.start_position
        + scenario.state.completed_rounds * scenario.config.ship.advance_per_round
    ) % scenario.config.ship.path_length


def test_ship_pilgrimage_site_lookup() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    ship = scenario.config.ship
    assert is_pilgrimage_site(4, ship) is True
    assert is_pilgrimage_site(5, ship) is False
    assert is_nw_pilgrimage_site(0, ship) is True
    assert is_nw_pilgrimage_site(4, ship) is False


def test_invalid_ship_config_requires_nw_site_in_pilgrimage_sites() -> None:
    with pytest.raises(ValueError):
        ShipConfig(
            path_length=26,
            start_position=0,
            nw_pilgrimage_site_position=0,
            pilgrimage_site_positions=(4, 8, 13),
            advance_per_round=1,
        )
