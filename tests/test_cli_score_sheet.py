from pilgrim.cli import main


def test_cli_score_command_prints_breakdown_and_deferred_categories(capsys) -> None:
    exit_code = main(["score", "scenarios/scoring_basic_breakdown_001.json"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Score sheet for scenario 'scoring_basic_breakdown_001'" in output
    assert "player_one" in output
    assert "Acolytes in Abbey / City / Duty tiles: 5 VP" in output
    assert "Piety track: 9 VP" in output
    assert "Alms table: 11 VP" in output
    assert "Donated buildings: 6 VP" in output
    assert "Resources: 2 VP" in output
    assert "Total implemented score: 33 VP" in output
    assert "Deferred / not yet implemented:" in output
    assert "Pilgrim Trails" in output
    assert "Pilgrimage Sites" in output
    assert "Cardinal Favours" in output
    assert "Road / Shrine / Market Port placement scoring" in output
    assert "Total sandbox evaluation:" not in output
    assert "Objective: maximize root player sandbox evaluation" not in output


def test_cli_score_command_works_for_in_progress_snapshot(capsys) -> None:
    exit_code = main(["score", "scenarios/scoring_resources_001.json"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Score sheet for scenario 'scoring_resources_001'" in output
    assert "player_one" in output
    assert "player_two" in output
    assert "Resources: 1 VP" in output
    assert "Total implemented score:" in output
