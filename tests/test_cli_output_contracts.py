from __future__ import annotations

from collections.abc import Callable

import pytest

from pilgrim.cli import main
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import FullTurnAction, StartPlayerConfessionBoxUse
from pilgrim.model.enums import PlayerId, TurnResolutionType
from pilgrim.rules.transition import legal_actions


ActionPredicate = Callable[[FullTurnAction], bool]


def _run_cli(args: list[str], capsys) -> str:
    exit_code = main(args)
    captured = capsys.readouterr()
    assert exit_code == 0, captured.err
    return captured.out


def _find_action_index(path: str, *, predicate: ActionPredicate) -> int:
    scenario = load_scenario(path)
    for index, action in enumerate(legal_actions(scenario.state, scenario.config), start=1):
        if not isinstance(action, FullTurnAction):
            continue
        if predicate(action):
            return index
    raise AssertionError(f"No matching action found for scenario: {path}")


def _apply_verbose_output(
    path: str,
    *,
    predicate: ActionPredicate,
    capsys,
) -> tuple[str, int]:
    action_index = _find_action_index(path, predicate=predicate)
    output = _run_cli(
        ["apply", path, "--action-index", str(action_index), "--verbose"],
        capsys,
    )
    return output, action_index


def _assert_in_order(output: str, fragments: list[str]) -> None:
    cursor = 0
    for fragment in fragments:
        index = output.find(fragment, cursor)
        assert index >= 0, f"Expected fragment not found in order: {fragment}"
        cursor = index + len(fragment)


def _matching_lines(output: str, *, contains: str) -> list[str]:
    return [line for line in output.splitlines() if contains in line]


def _first_matching_line(output: str, *, contains: str) -> str:
    for line in output.splitlines():
        if contains in line:
            return line
    raise AssertionError(f"No line matched substring: {contains}")


def test_cli_scriptorium_legal_actions_contract_prunes_no_op_variants_output(capsys) -> None:
    scenario_path = "scenarios/scriptorium_taxation_majority_other_tiles_001.json"
    output = _run_cli(["legal-actions", scenario_path], capsys)
    scriptorium_lines = _matching_lines(
        output,
        contains="use building: scriptorium for +1 effective acolyte on occupied Duty tiles",
    )

    assert scriptorium_lines
    assert any("| action: taxation" in line and "; bonus:" in line for line in scriptorium_lines)
    assert all("| action: tithe" not in line for line in scriptorium_lines)
    assert all("| action: give_alms_donate_building" not in line for line in scriptorium_lines)
    assert any(
        "| action: tithe" in line and "use building: scriptorium" not in line
        for line in output.splitlines()
    )
    assert any(
        "| action: give_alms_donate_building" in line
        and "use building: scriptorium" not in line
        for line in output.splitlines()
    )


def test_cli_scriptorium_apply_contract_taxation_majority_bonus_is_virtual_only(capsys) -> None:
    output, _index = _apply_verbose_output(
        "scenarios/scriptorium_taxation_majority_other_tiles_001.json",
        predicate=lambda action: (
            action.effective_acolyte_building_id == "scriptorium"
            and action.resolution is TurnResolutionType.TAXATION
            and action.taxation_step1_resource == "wheat"
            and action.taxation_step2_resources == ("stone", "silver")
        ),
        capsys=capsys,
    )

    assert (
        "BUILDING_BONUS: scriptorium added +1 effective acolyte on occupied Duty tiles this turn"
        in output
    )
    assert (
        "DUTY_RESOLUTION: selected north (taxation); relation majority; duty value 2; "
        "silver cost 0; action taxation"
    ) in output
    assert "TAXATION: player_one took bonus resources stone, silver from other majority duty tiles" in output
    assert "INVARIANT_CHECK: passed" in output
    assert "WORKFORCE_MOVE:" not in output
    assert "for free with Pulpit" not in output
    _assert_in_order(
        output,
        [
            "BUILDING_BONUS: scriptorium added +1 effective acolyte on occupied Duty tiles this turn",
            "SOWING:",
            "DUTY_RESOLUTION: selected north (taxation); relation majority",
            "TAXATION: player_one took bonus resources stone, silver from other majority duty tiles",
            "INVARIANT_CHECK: passed",
        ],
    )


def test_cli_customs_house_legal_actions_contract_prunes_non_taxation_variants_output(capsys) -> None:
    scenario_path = "scenarios/customs_house_active_taxation_majority_001.json"
    output = _run_cli(["legal-actions", scenario_path], capsys)
    customs_house_lines = _matching_lines(
        output,
        contains="use building: customs_house for Taxation majority on occupied Duty tiles",
    )

    assert customs_house_lines
    assert all("| action: taxation" in line for line in customs_house_lines)
    assert all("| action: tithe" not in line for line in customs_house_lines)
    assert any(
        "| action: tithe" in line and "use building: customs_house" not in line
        for line in output.splitlines()
    )


def test_cli_customs_house_apply_contract_hire_bonus_and_taxation_order(capsys) -> None:
    output, _index = _apply_verbose_output(
        "scenarios/customs_house_hire_market_taxation_majority_001.json",
        predicate=lambda action: (
            action.taxation_majority_building_id == "customs_house"
            and action.taxation_majority_building_source == "market"
            and action.resolution is TurnResolutionType.TAXATION
            and action.taxation_step1_resource == "wheat"
            and action.taxation_step2_resources == ("stone", "silver")
        ),
        capsys=capsys,
    )

    assert (
        "BUILDING_BONUS: customs_house claimed Taxation majority on occupied Duty tiles this turn"
        in output
    )
    assert (
        "DUTY_RESOLUTION: selected north (taxation); relation majority; duty value 2; "
        "silver cost 0; action taxation"
    ) in output
    assert "TAXATION: player_one took bonus resources stone, silver from other majority duty tiles" in output
    assert "INVARIANT_CHECK: passed" in output
    _assert_in_order(
        output,
        [
            "BUILDING_HIRED: player_one hired Customs House from market; paid wheat 1 to bank",
            "BUILDING_BONUS: customs_house claimed Taxation majority on occupied Duty tiles this turn",
            "SOWING:",
            "DUTY_RESOLUTION: selected north (taxation); relation majority",
            "TAXATION: player_one took bonus resources stone, silver from other majority duty tiles",
            "RESOURCE_DELTA:",
        ],
    )


def test_cli_wagon_yard_legal_actions_contract_labels_free_hire_target(capsys) -> None:
    scenario_path = "scenarios/wagon_yard_active_free_hire_market_brewery_001.json"
    output = _run_cli(["legal-actions", scenario_path], capsys)
    wagon_lines = _matching_lines(
        output,
        contains="use building: wagon_yard to hire brewery from market for free",
    )

    assert wagon_lines
    assert all("use building: brewery to sell 1 wheat for 2 silver" in line for line in wagon_lines)


def test_cli_wagon_yard_apply_contract_free_hire_bonus_and_order(capsys) -> None:
    output, _index = _apply_verbose_output(
        "scenarios/wagon_yard_active_free_hire_market_brewery_001.json",
        predicate=lambda action: (
            action.free_hire_enabler_building_id == "wagon_yard"
            and action.free_hire_target_building_id == "brewery"
            and action.free_hire_target_building_source == "market"
            and action.building_conversion_id == "brewery"
            and action.resolution is TurnResolutionType.TITHE
        ),
        capsys=capsys,
    )

    assert "BUILDING_HIRED: player_one hired Brewery from market for free with Wagon Yard" in output
    assert "BUILDING_BONUS: brewery sold 1 wheat for 2 silver" in output
    assert "RESOURCE_DELTA: player_one silver +2; wheat -1" in output
    assert "paid wheat 1 to bank" not in output
    _assert_in_order(
        output,
        [
            "BUILDING_HIRED: player_one hired Brewery from market for free with Wagon Yard",
            "BUILDING_BONUS: brewery sold 1 wheat for 2 silver",
            "RESOURCE_DELTA: player_one silver +2; wheat -1",
            "SOWING:",
            "DUTY_RESOLUTION:",
        ],
    )


def test_cli_pulpit_contract_reports_free_workforce_move(capsys) -> None:
    legal_output = _run_cli(
        ["legal-actions", "scenarios/pulpit_active_move_serf_001.json"],
        capsys,
    )
    assert "use building: pulpit to move 1 serf village -> abbey for free" in legal_output

    output, _index = _apply_verbose_output(
        "scenarios/pulpit_active_move_serf_001.json",
        predicate=lambda action: (
            action.workforce_move_building_id == "pulpit"
            and action.workforce_move_building_source == "own_active"
            and action.resolution is TurnResolutionType.TITHE
        ),
        capsys=capsys,
    )

    assert "WORKFORCE_MOVE: player_one moved 1 serf village -> abbey for free with Pulpit" in output
    assert "INVARIANT_CHECK: passed" in output
    assert "BUILDING_HIRED:" not in output
    assert "paid wheat 1 to" not in output
    _assert_in_order(
        output,
        [
            "BUILDING_BONUS: pulpit moved 1 serf village -> abbey for free",
            "WORKFORCE_MOVE: player_one moved 1 serf village -> abbey for free with Pulpit",
            "SOWING:",
            "DUTY_RESOLUTION:",
        ],
    )


def test_cli_guild_hired_contract_reports_hire_bonus_and_effect_order(capsys) -> None:
    legal_output = _run_cli(
        ["legal-actions", "scenarios/guild_hire_market_move_merchant_001.json"],
        capsys,
    )
    assert "use building: guild to move merchant +1" in legal_output

    output, _index = _apply_verbose_output(
        "scenarios/guild_hire_market_move_merchant_001.json",
        predicate=lambda action: (
            action.merchant_advance_building_id == "guild"
            and action.merchant_advance_building_source == "market"
            and action.resolution is TurnResolutionType.TITHE
        ),
        capsys=capsys,
    )

    _assert_in_order(
        output,
        [
            "BUILDING_HIRED: player_one hired Guild from market; paid wheat 1 to bank",
            "BUILDING_BONUS: guild moved Merchant clockwise +1",
            "MERCHANT_ADVANCE: produce -> clerical (north_east); current resource=silver; cause=guild",
            "SOWING:",
            "DUTY_RESOLUTION:",
        ],
    )


def test_cli_guild_round_end_contract_shows_two_merchant_movements(capsys) -> None:
    output, _index = _apply_verbose_output(
        "scenarios/guild_round_end_moves_merchant_twice_001.json",
        predicate=lambda action: (
            action.merchant_advance_building_id == "guild"
            and action.merchant_advance_building_source == "own_active"
            and action.resolution is TurnResolutionType.TITHE
        ),
        capsys=capsys,
    )
    merchant_lines = _matching_lines(output, contains="MERCHANT_ADVANCE:")

    assert len(merchant_lines) == 2
    assert any("cause=guild" in line for line in merchant_lines)
    assert any("cause=guild" not in line for line in merchant_lines)
    assert "MERCHANT_ADVANCE: taxation -> produce (north); current resource=wheat; cause=guild" in output
    assert "MERCHANT_ADVANCE: produce -> clerical (north_east); current resource=silver" in output


def test_cli_brewery_contract_reports_conversion_and_resource_delta(capsys) -> None:
    legal_output = _run_cli(
        ["legal-actions", "scenarios/brewery_active_sell_wheat_001.json"],
        capsys,
    )
    assert "use building: brewery to sell 1 wheat for 2 silver" in legal_output

    output, _index = _apply_verbose_output(
        "scenarios/brewery_active_sell_wheat_001.json",
        predicate=lambda action: (
            action.building_conversion_id == "brewery"
            and action.building_conversion_source == "own_active"
            and action.building_conversion_direction == "sell_wheat_for_silver"
            and action.resolution is TurnResolutionType.TITHE
        ),
        capsys=capsys,
    )

    assert "BUILDING_BONUS: brewery sold 1 wheat for 2 silver" in output
    assert "RESOURCE_DELTA: player_one silver +2; wheat -1" in output
    _assert_in_order(
        output,
        [
            "BUILDING_BONUS: brewery sold 1 wheat for 2 silver",
            "RESOURCE_DELTA: player_one silver +2; wheat -1",
            "SOWING:",
            "DUTY_RESOLUTION:",
        ],
    )


@pytest.mark.parametrize(
    ("scenario_path", "building_id", "direction", "target_resource"),
    (
        (
            "scenarios/grain_store_active_buy_wheat_001.json",
            "grain_store",
            "buy_wheat",
            "wheat",
        ),
        (
            "scenarios/indulgences_active_buy_piety_001.json",
            "indulgences",
            "buy_piety",
            "piety",
        ),
        (
            "scenarios/stone_yard_active_buy_stone_001.json",
            "stone_yard",
            "buy_stone",
            "stone",
        ),
    ),
)
def test_cli_conversion_buy_contract_is_clear(
    capsys,
    scenario_path: str,
    building_id: str,
    direction: str,
    target_resource: str,
) -> None:
    legal_output = _run_cli(["legal-actions", scenario_path], capsys)
    assert f"use building: {building_id} to buy" in legal_output

    output, _index = _apply_verbose_output(
        scenario_path,
        predicate=lambda action: (
            action.building_conversion_id == building_id
            and action.building_conversion_source == "own_active"
            and action.building_conversion_direction == direction
            and action.resolution is TurnResolutionType.TITHE
        ),
        capsys=capsys,
    )

    assert f"BUILDING_BONUS: {building_id} bought" in output
    delta_line = _first_matching_line(output, contains="RESOURCE_DELTA:")
    assert "silver -" in delta_line
    assert f"{target_resource} +" in delta_line


@pytest.mark.parametrize(
    ("scenario_path", "building_id", "direction", "target_resource"),
    (
        (
            "scenarios/grain_store_active_sell_wheat_001.json",
            "grain_store",
            "sell_wheat",
            "wheat",
        ),
        (
            "scenarios/indulgences_active_sell_piety_001.json",
            "indulgences",
            "sell_piety",
            "piety",
        ),
        (
            "scenarios/stone_yard_active_sell_stone_001.json",
            "stone_yard",
            "sell_stone",
            "stone",
        ),
    ),
)
def test_cli_conversion_sell_contract_is_clear(
    capsys,
    scenario_path: str,
    building_id: str,
    direction: str,
    target_resource: str,
) -> None:
    legal_output = _run_cli(["legal-actions", scenario_path], capsys)
    assert f"use building: {building_id} to sell" in legal_output

    output, _index = _apply_verbose_output(
        scenario_path,
        predicate=lambda action: (
            action.building_conversion_id == building_id
            and action.building_conversion_source == "own_active"
            and action.building_conversion_direction == direction
            and action.resolution is TurnResolutionType.TITHE
        ),
        capsys=capsys,
    )

    assert f"BUILDING_BONUS: {building_id} sold" in output
    delta_line = _first_matching_line(output, contains="RESOURCE_DELTA:")
    assert "silver +" in delta_line
    assert f"{target_resource} -" in delta_line


def test_cli_kogge_cloisters_contract_reports_both_route_modifiers(capsys) -> None:
    legal_output = _run_cli(
        ["legal-actions", "scenarios/kogge_cloisters_own_own_skip_duty_001.json"],
        capsys,
    )
    assert "use building: kogge | use building: cloisters to skip" in legal_output

    output, _index = _apply_verbose_output(
        "scenarios/kogge_cloisters_own_own_skip_duty_001.json",
        predicate=lambda action: (
            action.sow_route_building_id == "kogge"
            and action.sow_route_building_source == "own_active"
            and action.sow_route_secondary_building_id == "cloisters"
            and action.sow_route_secondary_building_source == "own_active"
            and action.resolution is TurnResolutionType.PRODUCE_STONE
        ),
        capsys=capsys,
    )

    assert "BUILDING_BONUS: kogge enabled" in output
    assert "BUILDING_BONUS: cloisters skipped" in output
    assert "SOWING: picked up 2 from city; route city ->" in output
    assert "with Cloisters" in output
    assert "DUTY_RESOLUTION: selected north (produce);" in output
    _assert_in_order(
        output,
        [
            "BUILDING_BONUS: kogge enabled",
            "BUILDING_BONUS: cloisters skipped",
            "SOWING:",
            "DUTY_RESOLUTION: selected north (produce);",
        ],
    )


def test_cli_infirmary_contract_is_distinct_from_pulpit_reporting(capsys) -> None:
    legal_output = _run_cli(
        ["legal-actions", "scenarios/allocation_hire_infirmary_market_001.json"],
        capsys,
    )
    assert "hire building: infirmary from market" in legal_output

    output, _index = _apply_verbose_output(
        "scenarios/allocation_infirmary_001.json",
        predicate=lambda action: (
            action.resolution is TurnResolutionType.ALLOCATION and len(action.allocation_moves) == 2
        ),
        capsys=capsys,
    )

    assert "BUILDING_BONUS: infirmary added duty value +1 to allocation" in output
    assert "effective duty value 2" in output
    assert "WORKFORCE_MOVE:" not in output
    assert "for free with Pulpit" not in output
    _assert_in_order(
        output,
        [
            "DUTY_RESOLUTION: selected north_west (allocation);",
            "BUILDING_BONUS: infirmary added duty value +1 to allocation",
            "ALLOCATION: player_one moved 1 acolyte abbey -> fields",
        ],
    )


def test_cli_taxation_contract_base_bonus_path_is_clear(capsys) -> None:
    legal_output = _run_cli(
        ["legal-actions", "scenarios/taxation_majority_bonus_001.json"],
        capsys,
    )
    assert "action: taxation | take: stone; bonus: stone, stone" in legal_output

    output, _index = _apply_verbose_output(
        "scenarios/taxation_majority_bonus_001.json",
        predicate=lambda action: (
            action.resolution is TurnResolutionType.TAXATION
            and action.taxation_step1_resource == "stone"
            and action.taxation_step2_resources == ("stone", "stone")
        ),
        capsys=capsys,
    )

    assert (
        "DUTY_RESOLUTION: selected north (taxation); relation majority; duty value 2"
        in output
    )
    assert "TAXATION: player_one took step 1 resource stone" in output
    assert "TAXATION: player_one took bonus resources stone, stone from other majority duty tiles" in output
    assert "INVARIANT_CHECK: passed" in output


def test_cli_give_alms_and_season_end_contracts_are_clear(capsys) -> None:
    give_alms_legal = _run_cli(["legal-actions", "scenarios/give_alms_paid_001.json"], capsys)
    assert "action: give_alms_paid" in give_alms_legal

    give_alms_output, _index = _apply_verbose_output(
        "scenarios/give_alms_paid_001.json",
        predicate=lambda action: action.resolution is TurnResolutionType.GIVE_ALMS_PAID,
        capsys=capsys,
    )
    assert "ALMS_PAYMENT:" in give_alms_output
    assert "ALMS_PROGRESS:" in give_alms_output
    assert "DUTY_RESOLUTION: selected south (give_alms);" in give_alms_output

    season_end_output = _run_cli(
        [
            "apply",
            "scenarios/alms_season_end_unique_leader_001.json",
            "--action-index",
            "1",
            "--verbose",
        ],
        capsys,
    )
    _assert_in_order(
        season_end_output,
        [
            "ROUND_ADVANCE:",
            "ALMS_SEASON_END:",
            "ALMS_SEASON_REWARD:",
            "ALMS_RESET:",
            "MERCHANT_ADVANCE:",
            "START_PLAYER_MARKER:",
        ],
    )


def test_cli_round_end_trade_route_income_contract_orders_after_merchant(capsys) -> None:
    output, _index = _apply_verbose_output(
        "scenarios/round_end_trade_route_income_basic_001.json",
        predicate=lambda action: action.resolution is TurnResolutionType.TITHE,
        capsys=capsys,
    )

    assert "TRADE_ROUTE_INCOME: player_one gained wheat +1 from 1 trade route" in output
    _assert_in_order(
        output,
        [
            "MERCHANT_ADVANCE:",
            "TRADE_ROUTE_INCOME: player_one gained wheat +1 from 1 trade route",
            "START_PLAYER_MARKER:",
            "TURN_ADVANCE:",
        ],
    )


def test_cli_confession_box_start_player_contract_hire_bonus_and_selection_order(capsys) -> None:
    output, _index = _apply_verbose_output(
        "scenarios/confession_box_hire_market_start_player_001.json",
        predicate=lambda action: action.start_player_confession_box_uses
        == (
            StartPlayerConfessionBoxUse(
                player=PlayerId.PLAYER_TWO,
                source="market",
            ),
        ),
        capsys=capsys,
    )

    assert "CONFESSION_BOX_BONUS:" in output
    _assert_in_order(
        output,
        [
            "BUILDING_HIRED: player_two hired Confession Box from market; paid wheat 1 to bank",
            "CONFESSION_BOX_BONUS: player_two used Confession Box from market; temporary piety 9 + 2 = 11 for start-player selection",
            "START_PLAYER_MARKER: player_two takes the First Player marker on effective "
            "piety 11 and must choose who begins the next round",
        ],
    )


def test_cli_building_availability_contract_shows_owned_live_scriptorium(capsys) -> None:
    output, _index = _apply_verbose_output(
        "scenarios/scriptorium_active_majority_selected_duty_001.json",
        predicate=lambda action: action.resolution is TurnResolutionType.CLERICAL_DEVOTION,
        capsys=capsys,
    )

    assert "Building availability:" in output
    assert "Owned/live: Scriptorium (player_one)" in output
