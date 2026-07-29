from __future__ import annotations

from pilgrim.cli import main
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import FullTurnAction, StartPlayerConfessionBoxUse
from pilgrim.model.enums import PlayerId, TurnResolutionType
from pilgrim.rules.transition import legal_actions


def _confession_action_index(path: str, *, uses: tuple[StartPlayerConfessionBoxUse, ...]) -> int:
    scenario = load_scenario(path)
    for index, action in enumerate(legal_actions(scenario.state, scenario.config), start=1):
        if not isinstance(action, FullTurnAction):
            continue
        if action.resolution is not TurnResolutionType.TITHE:
            continue
        if action.start_player_confession_box_uses == uses:
            return index
    raise AssertionError(f"No matching Confession Box action found in {path}.")


def test_cli_apply_owned_confession_box_shows_temporary_piety_above_twelve(capsys) -> None:
    action_index = _confession_action_index(
        "scenarios/confession_box_owned_temp_piety_above_12_001.json",
        uses=(
            StartPlayerConfessionBoxUse(
                player=PlayerId.PLAYER_ONE,
                source="own_active",
            ),
        ),
    )
    exit_code = main(
        [
            "apply",
            "scenarios/confession_box_owned_temp_piety_above_12_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert (
        "CONFESSION_BOX_BONUS: player_one used own active Confession Box; temporary piety "
        "12 + 2 = 14 for start-player selection"
    ) in output
    assert "BUILDING_HIRED: player_one hired Confession Box" not in output
    assert "START_PLAYER_SELECTION: player_one selected player_one as next start player" in output
    assert "Piety position: 12" in output


def test_cli_apply_market_hired_confession_box_shows_hire_then_bonus(capsys) -> None:
    action_index = _confession_action_index(
        "scenarios/confession_box_hire_market_start_player_001.json",
        uses=(
            StartPlayerConfessionBoxUse(
                player=PlayerId.PLAYER_TWO,
                source="market",
            ),
        ),
    )
    exit_code = main(
        [
            "apply",
            "scenarios/confession_box_hire_market_start_player_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    hire_text = "BUILDING_HIRED: player_two hired Confession Box from market; paid wheat 1 to bank"
    bonus_text = (
        "CONFESSION_BOX_BONUS: player_two used Confession Box from market; temporary piety "
        "9 + 2 = 11 for start-player selection"
    )
    assert hire_text in output
    assert bonus_text in output
    assert output.index(hire_text) < output.index(bonus_text) < output.index(
        "START_PLAYER_SELECTION:"
    )


def test_cli_apply_opponent_hired_confession_box_shows_owner_payment(capsys) -> None:
    action_index = _confession_action_index(
        "scenarios/confession_box_hire_opponent_start_player_001.json",
        uses=(
            StartPlayerConfessionBoxUse(
                player=PlayerId.PLAYER_TWO,
                source="player_one",
            ),
        ),
    )
    exit_code = main(
        [
            "apply",
            "scenarios/confession_box_hire_opponent_start_player_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert (
        "BUILDING_HIRED: player_two hired Confession Box from player_one; "
        "paid wheat 1 to player_one"
    ) in output
    assert (
        "CONFESSION_BOX_BONUS: player_two used Confession Box from player_one; temporary piety "
        "9 + 2 = 11 for start-player selection"
    ) in output


def test_cli_apply_confession_box_tie_break_orders_bonus_before_tie_break(capsys) -> None:
    action_index = _confession_action_index(
        "scenarios/confession_box_effective_piety_tie_break_001.json",
        uses=(
            StartPlayerConfessionBoxUse(
                player=PlayerId.PLAYER_ONE,
                source="own_active",
            ),
        ),
    )
    exit_code = main(
        [
            "apply",
            "scenarios/confession_box_effective_piety_tie_break_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    bonus_text = (
        "CONFESSION_BOX_BONUS: player_one used own active Confession Box; temporary piety "
        "8 + 2 = 10 for start-player selection"
    )
    tie_break_text = "START_PLAYER_TIE_BREAK:"
    selection_text = "START_PLAYER_SELECTION: player_one selected player_one as next start player"
    assert bonus_text in output
    assert tie_break_text in output
    assert selection_text in output
    assert output.index(bonus_text) < output.index(tie_break_text) < output.index(selection_text)
