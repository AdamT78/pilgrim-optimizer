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
    assert "MERCHANT_ADVANCE:" in output
    assert "State after action:" in output
    assert "Timing:" in output
    assert "Absolute turn:" in output
    assert "Round:" in output
    assert "Season:" in output
    assert "Turn in round:" in output
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
