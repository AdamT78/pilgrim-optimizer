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
    assert "Invalid action index 99. Scenario has 2 legal actions." in captured.err


def test_cli_apply_zero_index_is_invalid_for_one_based_indexing(capsys) -> None:
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
    assert "Invalid action index 0. Scenario has 2 legal actions." in captured.err


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
    assert "ALMS_THRESHOLD_REWARD:" in output
    assert "State after action:" in output
    assert "Root-player evaluation breakdown:" in output
