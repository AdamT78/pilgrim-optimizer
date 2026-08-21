from dataclasses import fields

from pilgrim.io.event_text import format_event
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import TurnResolutionType
from pilgrim.model.actions import FullTurnAction
from pilgrim.rules.transition import apply_action, apply_turn_step, turn_steps, legal_actions


def _step_output(path: str, *, source: str, direction: str, amount: int) -> str:
    scenario = load_scenario(path)
    step = next(
        step
        for step in turn_steps(scenario.state, scenario.config)
        if step.source == source and step.direction == direction and step.amount == amount
    )
    state = apply_turn_step(scenario.state, scenario.config, step)
    action = next(
        action
        for action in legal_actions(state, scenario.config)
        if action.resolution is TurnResolutionType.TITHE
    )
    result = apply_action(state, action, scenario.config)
    return "\n".join(
        text
        for event in result.events
        if (text := format_event(event, scenario.config)) is not None
    )


def test_stone_yard_is_a_committed_step_not_a_cli_full_turn_field() -> None:
    names = {field.name for field in fields(FullTurnAction)}
    assert not names & {
        "building_conversion_id", "building_conversion_source",
        "building_conversion_direction", "building_conversion_amount",
    }
    scenario = load_scenario("scenarios/stone_yard_active_sell_stone_001.json")
    assert any(step.building_id == "stone_yard" for step in turn_steps(scenario.state, scenario.config))


def test_cli_apply_own_active_stone_yard_sell_shows_bonus_and_delta_before_sowing() -> None:
    output = _step_output(
        "scenarios/stone_yard_active_sell_stone_001.json",
        source="own_active",
        direction="sell_stone",
        amount=2,
    )
    assert "BUILDING_HIRED" not in output
    assert "BUILDING_BONUS: stone_yard sold 2 stone for 2 silver" in output
    assert "RESOURCE_DELTA: player_one stone -2; silver +2" in output
    assert "SOWING: picked up 1 from north; route north -> north_east" in output
    assert output.index("BUILDING_BONUS: stone_yard sold 2 stone for 2 silver") < output.index(
        "RESOURCE_DELTA: player_one stone -2; silver +2"
    ) < output.index("SOWING:")


def test_cli_apply_market_hired_stone_yard_buy_shows_hire_then_bonus_then_delta() -> None:
    output = _step_output(
        "scenarios/stone_yard_hire_market_buy_stone_001.json",
        source="market",
        direction="buy_stone",
        amount=1,
    )
    assert "BUILDING_HIRED: player_one hired Stone Yard from market; paid silver 1 to bank" in output
    assert "BUILDING_BONUS: stone_yard bought 1 stone for 1 silver" in output
    assert "RESOURCE_DELTA: player_one stone +1; silver -1" in output
    assert output.index("BUILDING_HIRED:") < output.index("BUILDING_BONUS:") < output.index(
        "RESOURCE_DELTA: player_one stone +1; silver -1"
    )


def test_cli_apply_opponent_hired_stone_yard_buy_shows_owner_payment() -> None:
    output = _step_output(
        "scenarios/stone_yard_hire_opponent_buy_stone_001.json",
        source="player_two",
        direction="buy_stone",
        amount=2,
    )
    assert "BUILDING_HIRED: player_one hired Stone Yard from player_two; paid silver 1 to player_two" in output
    assert "BUILDING_BONUS: stone_yard bought 2 stone for 2 silver" in output


def test_cli_apply_stone_yard_buy_above_six_round_end_cap_shows_cap_event() -> None:
    output = _step_output(
        "scenarios/stone_yard_buy_above_six_then_round_end_cap_001.json",
        source="own_active",
        direction="buy_stone",
        amount=1,
    )
    assert "BUILDING_BONUS: stone_yard bought 1 stone for 1 silver" in output
    assert "RESOURCE_DELTA: player_two stone +1; silver -1" in output
    assert "EXCESS_RESOURCE_CAP: player_two stone 7 -> 6" in output
