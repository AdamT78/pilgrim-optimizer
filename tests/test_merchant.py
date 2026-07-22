import json
from dataclasses import replace
from pathlib import Path

from pilgrim.io.scenarios import load_scenario
from pilgrim.rules.merchant import (
    advance_merchant_position,
    building_hire_payment_resource,
    current_merchant_duty,
    current_merchant_resource,
    merchant_position_name,
    trade_route_income_resource,
)


def test_merchant_position_zero_maps_to_first_path_entry() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    assert merchant_position_name(0, scenario.config.merchant) == scenario.config.merchant.path[0]
    assert current_merchant_duty(scenario.state, scenario.config.merchant) == "taxation"


def test_merchant_advances_from_zero_to_one() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    assert advance_merchant_position(0, scenario.config.merchant) == 1


def test_merchant_advancement_wraps_from_last_to_zero() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    last_position = len(scenario.config.merchant.path) - 1
    assert advance_merchant_position(last_position, scenario.config.merchant) == 0


def test_current_resource_lookup_for_normal_duty() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    state = replace(scenario.state, merchant_position=1)
    assert current_merchant_duty(state, scenario.config.merchant) == "produce"
    assert current_merchant_resource(state, scenario.config.merchant) == "wheat"


def test_current_resource_lookup_returns_none_at_taxation() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    taxation_position = scenario.config.merchant.path.index("taxation")
    state = replace(scenario.state, merchant_position=taxation_position)
    assert current_merchant_duty(state, scenario.config.merchant) == "taxation"
    assert current_merchant_resource(state, scenario.config.merchant) is None


def test_future_hooks_reuse_current_merchant_resource() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    assert (
        building_hire_payment_resource(scenario.state, scenario.config.merchant)
        == current_merchant_resource(scenario.state, scenario.config.merchant)
    )
    assert (
        trade_route_income_resource(scenario.state, scenario.config.merchant)
        == current_merchant_resource(scenario.state, scenario.config.merchant)
    )


def test_missing_merchant_position_defaults_to_zero(tmp_path: Path) -> None:
    setup_raw = json.loads(Path("configs/setups/basic_mancala_sandbox.json").read_text())
    initial_state = dict(setup_raw["initial_state"])
    initial_state.pop("merchant_position", None)

    scenario_path = tmp_path / "scenario_without_merchant_position.json"
    scenario_path.write_text(
        json.dumps(
            {
                "scenario_id": "tmp_missing_merchant_position",
                "board_file": str(Path("configs/board.json").resolve()),
                "duties_file": str(Path("configs/duties.json").resolve()),
                "piety_file": str(Path("configs/piety.json").resolve()),
                "alms_file": str(Path("configs/alms.json").resolve()),
                "timing_file": str(Path("configs/timing.json").resolve()),
                "merchant_file": str(Path("configs/merchant.json").resolve()),
                "initial_state": initial_state,
            }
        ),
        encoding="utf-8",
    )

    loaded = load_scenario(scenario_path)
    assert loaded.state.merchant_position == 0
