from dataclasses import fields

from pilgrim.io.event_text import format_event
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import FullTurnAction
from pilgrim.model.enums import TurnResolutionType
from pilgrim.rules.transition import apply_action, apply_turn_step, legal_actions, turn_steps


def _step_output(path: str, *, source: str, direction: str, amount: int, resolution) -> str:
    scenario = load_scenario(path)
    step = next(
        step
        for step in turn_steps(scenario.state, scenario.config)
        if step.source == source and step.direction == direction and step.amount == amount
    )
    state = apply_turn_step(scenario.state, scenario.config, step)
    action = next(action for action in legal_actions(state, scenario.config) if action.resolution is resolution)
    result = apply_action(state, action, scenario.config)
    return "\n".join(
        text
        for event in result.events
        if (text := format_event(event, scenario.config)) is not None
    )


def test_grain_store_is_a_committed_step_not_a_cli_full_turn_field() -> None:
    names = {field.name for field in fields(FullTurnAction)}
    assert not names & {
        "building_conversion_id", "building_conversion_source",
        "building_conversion_direction", "building_conversion_amount",
    }
    scenario = load_scenario("scenarios/grain_store_active_sell_wheat_001.json")
    assert any(step.building_id == "grain_store" for step in turn_steps(scenario.state, scenario.config))


def test_cli_apply_own_active_grain_store_sell_shows_bonus_and_delta_before_sowing() -> None:
    output = _step_output(
        "scenarios/grain_store_active_sell_wheat_001.json",
        source="own_active",
        direction="sell_wheat",
        amount=2,
        resolution=TurnResolutionType.TITHE,
    )
    assert "BUILDING_HIRED" not in output
    assert "BUILDING_BONUS: grain_store sold 2 wheat for 2 silver" in output
    assert "RESOURCE_DELTA: player_one silver +2; wheat -2" in output
    assert "SOWING: picked up 1 from north; route north -> north_east" in output
    assert output.index("BUILDING_BONUS:") < output.index("RESOURCE_DELTA:") < output.index("SOWING:")


def test_cli_apply_market_hired_grain_store_buy_shows_hire_then_bonus_then_delta() -> None:
    output = _step_output(
        "scenarios/grain_store_hire_market_buy_wheat_001.json",
        source="market",
        direction="buy_wheat",
        amount=1,
        resolution=TurnResolutionType.TITHE,
    )
    assert "BUILDING_HIRED: player_one hired Grain Store from market; paid silver 1 to bank" in output
    assert "BUILDING_BONUS: grain_store bought 1 wheat for 1 silver" in output
    assert "RESOURCE_DELTA: player_one silver -1; wheat +1" in output
    assert output.index("BUILDING_HIRED:") < output.index("BUILDING_BONUS:") < output.index(
        "RESOURCE_DELTA: player_one silver -1; wheat +1"
    )


def test_cli_apply_opponent_hired_grain_store_buy_shows_owner_payment() -> None:
    output = _step_output(
        "scenarios/grain_store_hire_opponent_buy_wheat_001.json",
        source="player_two",
        direction="buy_wheat",
        amount=2,
        resolution=TurnResolutionType.TITHE,
    )
    assert "BUILDING_HIRED: player_one hired Grain Store from player_two; paid silver 1 to player_two" in output
    assert "BUILDING_BONUS: grain_store bought 2 wheat for 2 silver" in output


def test_cli_apply_grain_store_buy_then_ordination_shows_ordination_wheat_delta() -> None:
    output = _step_output(
        "scenarios/grain_store_buy_then_ordination_001.json",
        source="own_active",
        direction="buy_wheat",
        amount=1,
        resolution=TurnResolutionType.ORDINATION,
    )
    assert "BUILDING_BONUS: grain_store bought 1 wheat for 1 silver" in output
    assert "RESOURCE_DELTA: player_one silver -1; wheat +1" in output
    assert "ORDINATION: player_one ordained 1 serf village -> abbey; paid wheat=1" in output
    assert "RESOURCE_DELTA: player_one wheat -1" in output
