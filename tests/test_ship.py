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
