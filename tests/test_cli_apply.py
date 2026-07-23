from pilgrim.cli import main
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import action_summary
from pilgrim.model.enums import TurnResolutionType
from pilgrim.rules.transition import legal_actions


def test_cli_apply_selects_action_by_one_based_index(capsys) -> None:
    scenario = load_scenario("scenarios/alms_sandbox_001.json")
    first_action = legal_actions(scenario.state, scenario.config)[0]
    first_action_summary = action_summary(first_action, scenario.config)

    exit_code = main(
        [
            "apply",
            "scenarios/alms_sandbox_001.json",
            "--action-index",
            "1",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Apply result for scenario 'alms_sandbox_001'" in output
    assert "Selected action 1:" in output
    assert first_action_summary in output
    assert "State updated successfully." in output
    assert "Next active player: player_two" in output


def test_cli_apply_invalid_action_index_returns_clear_error(capsys) -> None:
    scenario = load_scenario("scenarios/alms_sandbox_001.json")
    action_count = len(legal_actions(scenario.state, scenario.config))
    exit_code = main(
        [
            "apply",
            "scenarios/alms_sandbox_001.json",
            "--action-index",
            "99",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 2
    assert (
        f"Invalid action index 99. Scenario has {action_count} legal actions."
        in captured.err
    )


def test_cli_apply_zero_index_is_invalid_for_one_based_indexing(capsys) -> None:
    scenario = load_scenario("scenarios/alms_sandbox_001.json")
    action_count = len(legal_actions(scenario.state, scenario.config))
    exit_code = main(
        [
            "apply",
            "scenarios/alms_sandbox_001.json",
            "--action-index",
            "0",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 2
    assert (
        f"Invalid action index 0. Scenario has {action_count} legal actions."
        in captured.err
    )


def test_cli_apply_verbose_can_show_alms_events(capsys) -> None:
    scenario = load_scenario("scenarios/alms_sandbox_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    give_alms_index = next(
        index
        for index, action in enumerate(actions, start=1)
        if action.resolution is TurnResolutionType.GIVE_ALMS
    )

    exit_code = main(
        [
            "apply",
            "scenarios/alms_sandbox_001.json",
            "--action-index",
            str(give_alms_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Apply result for scenario 'alms_sandbox_001'" in output
    assert f"Selected action {give_alms_index}:" in output
    assert "action: give_alms" in output
    assert "Events:" in output
    assert "ALMS_PAYMENT:" in output
    assert "ALMS_PROGRESS:" in output
    assert "MERCHANT_ADVANCE:" not in output
    assert "SHIP_ADVANCE:" not in output
    assert "State after action:" in output
    assert "Timing:" in output
    assert "Absolute turn:" in output
    assert "Round:" in output
    assert "Season:" in output
    assert "Turn in round:" in output
    assert "Start player:" in output
    assert "Game over:" in output
    assert "Ship:" in output
    assert "At pilgrimage site:" in output
    assert "At NW pilgrimage site:" in output
    assert "Merchant:" in output
    assert "Dummy acolytes:" in output
    assert "Position:" in output
    assert "Resource:" in output
    assert "Root-player evaluation after action:" in output
    assert "Root-player evaluation breakdown:" not in output
    assert "Total sandbox evaluation:" in output


def test_cli_apply_season_end_scenario_shows_season_and_alms_events(capsys) -> None:
    exit_code = main(
        [
            "apply",
            "scenarios/season_end_alms_001.json",
            "--action-index",
            "1",
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "SEASON_END:" in output
    assert "MERCHANT_ADVANCE: taxation -> produce; current resource=wheat" in output
    assert "DUMMY_ACOLYTE_MOVE:" in output
    assert "ALMS_SEASON_REWARD:" in output
    assert "ALMS_RESET:" in output
    assert "SEASON_ADVANCE:" in output
    assert "INVARIANT_CHECK:" in output
    assert "passed for all players" in output
    assert "player_one=2" in output
    assert "player_two=1" in output
    assert "Next active player: player_two" in output
    assert "Resource: wheat" in output


def test_cli_apply_dummy_season_move_scenario_shows_dummy_events(capsys) -> None:
    exit_code = main(
        [
            "apply",
            "scenarios/dummy_season_move_001.json",
            "--action-index",
            "1",
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Apply result for scenario 'dummy_season_move_001'" in output
    assert "DUMMY_ACOLYTE_MOVE:" in output
    assert "north_group before [north, north_east, east]" in output
    assert "moved north -> south_east" in output
    assert "after [north_east, east, south_east]" in output
    assert "south_group before [south, south_west, west]" in output
    assert "moved south -> north_west" in output
    assert "after [south_west, west, north_west]" in output


def test_cli_apply_game_end_scenario_shows_game_end_and_game_over(capsys) -> None:
    exit_code = main(
        [
            "apply",
            "scenarios/game_end_nw_site_001.json",
            "--action-index",
            "1",
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Apply result for scenario 'game_end_nw_site_001'" in output
    assert "GAME_END:" in output
    assert "ALMS_SEASON_REWARD:" in output
    assert "ALMS_RESET:" in output
    assert "DUMMY_ACOLYTE_MOVE:" not in output
    assert "MERCHANT_ADVANCE:" not in output
    assert "State after action:" in output
    assert "Next active player: none (game over)" in output
    assert "Game over: true" in output


def test_cli_apply_round_end_excess_scenario_shows_round_end_pipeline(capsys) -> None:
    exit_code = main(
        [
            "apply",
            "scenarios/round_end_excess_001.json",
            "--action-index",
            "1",
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "ROUND_END:" in output
    assert "EXCESS_DISCARD:" in output
    assert "SHIP_ADVANCE:" in output
    assert "MERCHANT_ADVANCE:" in output
    assert "START_PLAYER_SELECTION:" in output


def test_cli_apply_allocation_verbose_shows_player_board_sections(capsys) -> None:
    exit_code = main(
        [
            "apply",
            "scenarios/allocation_abbey_to_special_activity_001.json",
            "--action-index",
            "1",
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Apply result for scenario 'allocation_abbey_to_special_activity_001'" in output
    assert "action: allocation" in output
    assert "moves: abbey -> fields" in output
    assert "ALLOCATION: player_one moved 1 acolyte abbey -> fields" in output
    assert "target: city" not in output
    assert "Village:" in output
    assert "Abbey:" in output
    assert "Special Activities: 0" in output
    assert "Special Activities: none" in output
    assert "Special Activities: fields" in output
    assert "Total: 10" in output


def test_cli_apply_allocation_with_occupied_special_activities_counts_them_in_total(capsys) -> None:
    exit_code = main(
        [
            "apply",
            "scenarios/allocation_all_special_occupied_001.json",
            "--action-index",
            "1",
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Special Activities: 6" in output
    assert (
        "Special Activities: "
        "fields, road_engineer, stone_mason, alms_house, engraver, vestry"
    ) in output
    assert "grain, road_engineer" not in output
    assert "Total: 16" in output
    assert "player_one=16" in output


def test_cli_apply_allocation_multi_move_reports_allocation_move_sequence(capsys) -> None:
    exit_code = main(
        [
            "apply",
            "scenarios/allocation_multi_move_001.json",
            "--action-index",
            "1",
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "action: allocation | moves:" in output
    assert "target: city" not in output
    first_index = output.index("ALLOCATION: player_one moved 1 acolyte abbey -> fields")
    second_index = output.index(
        "ALLOCATION: player_one moved 1 acolyte abbey -> road_engineer"
    )
    assert second_index > first_index


def test_cli_apply_alms_house_bonus_event_is_visible(capsys) -> None:
    exit_code = main(
        [
            "apply",
            "scenarios/special_activity_alms_house_001.json",
            "--action-index",
            "1",
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "SPECIAL_ACTIVITY_BONUS:" in output
    assert "alms_house applied to give_alms" in output
    assert "effective duty value 2" in output
    assert "paid extra silver=1, wheat=0" in output
    assert "Special Activities: 1" in output


def test_cli_apply_fields_bonus_does_not_raise_effective_duty_value(capsys) -> None:
    exit_code = main(
        [
            "apply",
            "scenarios/produce_special_activity_fields_001.json",
            "--action-index",
            "1",
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "DUTY_RESOLUTION:" in output
    assert "duty value 2" in output
    assert "effective duty value 3" not in output
    assert "SPECIAL_ACTIVITY_BONUS: fields added wheat +1 to produce_wheat" in output
    assert "RESOURCE_DELTA: player_one wheat +3" in output


def test_cli_apply_stone_mason_bonus_does_not_raise_effective_duty_value(capsys) -> None:
    exit_code = main(
        [
            "apply",
            "scenarios/produce_special_activity_stone_mason_001.json",
            "--action-index",
            "2",
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "DUTY_RESOLUTION:" in output
    assert "duty value 2" in output
    assert "effective duty value 3" not in output
    assert "SPECIAL_ACTIVITY_BONUS: stone_mason added stone +1 to produce_stone" in output
    assert "RESOURCE_DELTA: player_one stone +3" in output


def test_cli_apply_donate_building_verbose_shows_donation_events_and_slot_state(capsys) -> None:
    exit_code = main(
        [
            "apply",
            "scenarios/give_alms_donate_building_001.json",
            "--action-index",
            "1",
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "action: donate_building | building: confession_box" in output
    assert "BUILDING_DONATION: player_one donated Confession Box; donation_vp=2" in output
    assert "ALMS_PROGRESS: player_one row 0 -> 1" in output
    assert "ALMS_PAYMENT:" not in output
    assert "Active buildings: none" in output
    assert "Donated buildings: Confession Box" in output
    assert "Used slots: 1/6" in output


def test_cli_apply_majority_donate_building_forfeits_second_give_alms(capsys) -> None:
    exit_code = main(
        [
            "apply",
            "scenarios/give_alms_donate_building_majority_001.json",
            "--action-index",
            "1",
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "action: donate_building | building: bank" in output
    assert "DUTY_RESOLUTION: selected south (give_alms); relation majority; duty value 2" in output
    assert "BUILDING_DONATION: player_one donated Bank; donation_vp=6" in output
    assert "ALMS_PROGRESS: player_one row 0 -> 1" in output
    assert "ALMS_PAYMENT:" not in output
