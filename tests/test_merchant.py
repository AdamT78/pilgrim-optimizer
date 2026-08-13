import json
from dataclasses import replace
from pathlib import Path

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.rules.merchant import (
    advance_merchant_position,
    building_hire_payment_resource,
    current_merchant_duty,
    current_merchant_resource,
    merchant_position_name,
    taxation_board_position,
    trade_route_income_resource,
)

SANDBOX = "scenarios/mancala_sandbox_001.json"


def test_the_merchant_starts_the_game_on_whichever_tile_taxation_landed_on() -> None:
    """Replaces a test that asserted position 0 named `path[0]`.

    The Merchant used to open at index 0 of a fixed list whose first entry happened to be
    "taxation". It now opens on the Taxation TILE, which is a different claim: the tile is dealt
    per game, so the opening position moves with the arrangement instead of always being 0.
    """
    scenario = load_scenario(SANDBOX)
    assert scenario.state.merchant_board_position == taxation_board_position(scenario.config)
    assert current_merchant_duty(scenario.state, scenario.config) == "taxation"


def test_the_merchant_is_never_in_the_city() -> None:
    """0 was a normal opening under the old six-step path and is an impossible state now.

    This is the guard that stops a pre-rename scenario value being read as a board position.
    """
    scenario = load_scenario(SANDBOX)
    with pytest.raises(ValueError, match="never in the City"):
        replace(scenario.state, merchant_board_position=0)
    with pytest.raises(ValueError, match="never in the City"):
        advance_merchant_position(0, scenario.config)


def test_eight_advances_return_the_merchant_to_its_start_having_visited_every_tile() -> None:
    """Replaces the pair of tests that pinned 0 -> 1 and last -> 0 on a six-step path.

    The lap is the board's eight duty tiles now. Walking it must close and must not repeat, which
    is the property the old modulo arithmetic gave for free and a hand-written ordering would not.
    """
    scenario = load_scenario(SANDBOX)
    for start in range(1, 9):
        position = start
        visited = []
        for _ in range(8):
            visited.append(position)
            position = advance_merchant_position(position, scenario.config)
        assert position == start
        assert sorted(visited) == list(range(1, 9))


def test_the_merchant_walks_the_ring_clockwise_by_compass_point() -> None:
    """The direction is derived from board.json's edges, so pin the order it actually produces."""
    scenario = load_scenario(SANDBOX)
    position = scenario.config.board.index_for_name("north")
    names = []
    for _ in range(8):
        names.append(merchant_position_name(position, scenario.config))
        position = advance_merchant_position(position, scenario.config)
    assert names == [
        "north",
        "north_east",
        "east",
        "south_east",
        "south",
        "south_west",
        "west",
        "north_west",
    ]


def test_the_resource_is_the_tithe_counter_on_the_tile_and_nothing_at_taxation() -> None:
    """Replaces two tests that looked the resource up by duty name.

    The resource was a property of the duty ("clerical pays silver"); it is a property of the
    POSITION now, because the generator deals counters onto spaces after shuffling the tiles.
    """
    scenario = load_scenario(SANDBOX)
    counters = scenario.config.tithe_counters
    for position in range(1, 9):
        state = replace(scenario.state, merchant_board_position=position)
        assert current_merchant_resource(
            state, scenario.config
        ) == counters.resource_for_board_index(position)
    taxation = replace(
        scenario.state, merchant_board_position=taxation_board_position(scenario.config)
    )
    assert current_merchant_resource(taxation, scenario.config) is None


def test_future_hooks_reuse_current_merchant_resource() -> None:
    scenario = load_scenario(SANDBOX)
    assert building_hire_payment_resource(scenario.state, scenario.config) == (
        current_merchant_resource(scenario.state, scenario.config)
    )
    assert trade_route_income_resource(scenario.state, scenario.config) == (
        current_merchant_resource(scenario.state, scenario.config)
    )


def test_taxation_scenario_merchant_resource_context_is_none() -> None:
    scenario = load_scenario("scenarios/taxation_merchant_resource_none_001.json")
    assert current_merchant_duty(scenario.state, scenario.config) == "taxation"
    assert current_merchant_resource(scenario.state, scenario.config) is None
    assert building_hire_payment_resource(scenario.state, scenario.config) is None
    assert trade_route_income_resource(scenario.state, scenario.config) is None


def test_a_scenario_that_omits_the_position_starts_the_merchant_at_taxation(
    tmp_path: Path,
) -> None:
    """Replaces a test asserting the default was 0.

    0 was Taxation under the old path, so "default to 0" and "default to Taxation" used to be the
    same sentence. They have come apart: 0 is the City now, and the default has to be looked up.
    """
    setup_raw = json.loads(Path("configs/setups/basic_mancala_sandbox.json").read_text())
    initial_state = dict(setup_raw["initial_state"])
    initial_state.pop("merchant_board_position", None)
    loaded = load_scenario(_write_scenario(tmp_path / "no_position.json", initial_state))
    assert loaded.state.merchant_board_position == taxation_board_position(loaded.config)
    assert current_merchant_duty(loaded.state, loaded.config) == "taxation"


def test_a_scenario_still_carrying_the_old_field_is_refused_rather_than_reinterpreted(
    tmp_path: Path,
) -> None:
    """The two index spaces overlap, so a range check cannot catch this and the name must.

    An old `merchant_position` of 1 meant "produce, pays wheat" and is a legal board position
    today. Left alone it would load in silence, move the Merchant to a tile it was never on, and
    change what the scenario tested without failing.
    """
    setup_raw = json.loads(Path("configs/setups/basic_mancala_sandbox.json").read_text())
    initial_state = dict(setup_raw["initial_state"])
    initial_state.pop("merchant_board_position", None)
    initial_state["merchant_position"] = 1
    scenario_path = _write_scenario(tmp_path / "stale.json", initial_state)

    with pytest.raises(ValueError, match="merchant_position"):
        load_scenario(scenario_path)


def test_the_retired_path_fields_are_refused_in_merchant_config(tmp_path: Path) -> None:
    """`path` and `resource_by_duty` are gone; a config still carrying them is not half-right."""
    merchant_path = tmp_path / "merchant.json"
    merchant_path.write_text(
        json.dumps({"advance_at_round_end": True, "path": ["taxation"]}), encoding="utf-8"
    )
    setup_raw = json.loads(Path("configs/setups/basic_mancala_sandbox.json").read_text())
    scenario_path = _write_scenario(
        tmp_path / "old_config.json",
        dict(setup_raw["initial_state"]),
        merchant_file=str(merchant_path),
    )
    with pytest.raises(ValueError, match="six-step path"):
        load_scenario(scenario_path)


def _write_scenario(path: Path, initial_state: dict, *, merchant_file: str | None = None) -> Path:
    path.write_text(
        json.dumps(
            {
                "scenario_id": path.stem,
                "board_file": str(Path("configs/board.json").resolve()),
                "duties_file": str(Path("configs/duties.json").resolve()),
                "piety_file": str(Path("configs/piety.json").resolve()),
                "alms_file": str(Path("configs/alms.json").resolve()),
                "timing_file": str(Path("configs/timing.json").resolve()),
                "merchant_file": merchant_file or str(Path("configs/merchant.json").resolve()),
                "ship_file": str(Path("configs/ship.json").resolve()),
                "initial_state": initial_state,
            }
        ),
        encoding="utf-8",
    )
    return path
