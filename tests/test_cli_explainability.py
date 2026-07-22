from pilgrim.cli import main
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import FullTurnAction, action_summary, readable_route
from pilgrim.model.enums import TurnResolutionType, position_name
from pilgrim.search.exact import solve_exact


def test_position_id_to_name_conversion() -> None:
    assert position_name(0) == "city"
    assert position_name(3) == "east"
    assert position_name(8) == "north_west"


def test_readable_route_formatting() -> None:
    route_text = readable_route(0, (1, 2, 3))
    assert route_text == "city -> north -> north_east -> east"


def test_readable_action_summary() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    summary = action_summary(
        FullTurnAction(
            origin=0,
            route=(1, 2, 3),
            selected_duty=3,
            resolution=TurnResolutionType.CLERICAL_SILVERSMITH,
        ),
        scenario.config,
    )
    assert summary == (
        "Turn: sow city -> north -> north_east -> east | "
        "selected duty: east | action: clerical_silversmith"
    )


def test_cli_legal_actions_returns_readable_output(capsys) -> None:
    exit_code = main(["legal-actions", "scenarios/mancala_sandbox_001.json"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Legal actions for scenario 'mancala_sandbox_001':" in output
    assert "1. Turn: sow city -> north -> north_east -> east" in output
    assert "selected duty: north" in output
    assert "action: produce" in output
    assert "action: give_alms" in output
    assert "pay silver=" in output
    assert "action: tithe" in output
    assert "Total legal actions: 12" in output


def test_cli_solve_returns_readable_best_action(capsys) -> None:
    exit_code = main(["solve", "scenarios/mancala_sandbox_001.json", "--depth", "3"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Solve result for scenario 'mancala_sandbox_001'" in output
    assert "Root player: player_one" in output
    assert "Objective: maximize root player sandbox evaluation" in output
    assert "Opponent model: sandbox_active_player_max" in output
    assert "Depth: 3" in output
    assert "Best first full turn:" in output
    assert "Turn: sow city -> north -> north_east -> east" in output
    assert "selected duty:" in output
    assert "Best line:" in output
    assert "1. player_one: Turn:" in output
    assert "Best-line final evaluation:" in output


def test_exact_search_returns_principal_variation() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    result = solve_exact(scenario.state, scenario.config, depth=3)

    assert len(result.principal_variation) >= 1
    assert result.principal_variation[0] == result.best_action
    assert result.principal_variation_ids[0] == result.best_action_id
    assert len(result.principal_variation) == 3


def test_cli_solve_verbose_includes_events_and_state(capsys) -> None:
    exit_code = main(
        [
            "solve",
            "scenarios/mancala_sandbox_001.json",
            "--depth",
            "3",
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Events for best first full turn:" in output
    assert "SOWING:" in output
    assert "DUTY_RESOLUTION:" in output
    assert "MERCHANT_ADVANCE:" in output
    assert "INVARIANT_CHECK:" in output
    assert "+0 piety" not in output
    assert "State after best first full turn:" in output
    assert "Acted player: player_one" in output
    assert "Next active player: player_two" in output
    assert "Timing:" in output
    assert "Absolute turn:" in output
    assert "Round:" in output
    assert "Season:" in output
    assert "Turn in round:" in output
    assert "Merchant:" in output
    assert "Position:" in output
    assert "Resource:" in output
    assert "Acted player state:" in output
    assert "Next active player state:" in output
    assert "Piety position:" in output
    assert "Piety track VP:" in output
    assert "Alms position:" in output
    assert "Alms table acolytes:" in output
    assert "Alms table VP:" in output
    assert "Workforce:" in output
    assert "Mancala total:" in output
    assert "Committed:" in output
    assert "Root-player evaluation after best first full turn:" in output
    assert "Root-player evaluation breakdown:" not in output
    assert "Player: player_one" in output
    assert "Alms table VP:" in output
    assert "Total sandbox evaluation:" in output
    assert "Active player:" not in output
    assert "Mancala: city=" in output
