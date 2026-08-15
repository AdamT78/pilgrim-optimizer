"""What the CLI prints while the table is going round the Confession Boxes.

The command applies one action, so a round end that stops to ask a question can no longer show the
answer in the same run -- and that is the change rather than a limitation to work around. So these
point the CLI at two different moments: the round-ending turn, which now ends by naming who is
being waited on, and the paused table itself, which is written out here and handed straight back.
"""

from __future__ import annotations

import json
from pathlib import Path

from pilgrim.cli import main
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import StartPlayerConfessionBoxAction
from pilgrim.model.enums import PlayerId, TurnPhase, TurnResolutionType
from pilgrim.model.state import GameState
from pilgrim.rules.transition import apply_action, legal_actions


def _round_ended(path: str, *, waiting_on: PlayerId | None = None) -> GameState:
    """The paused table, wound on by declining until the named player is the one being asked."""
    scenario = load_scenario(path)
    action = next(
        candidate
        for candidate in legal_actions(scenario.state, scenario.config)
        if candidate.resolution is TurnResolutionType.TITHE
    )
    state = apply_action(scenario.state, action, scenario.config).state
    while (
        waiting_on is not None
        and state.phase is TurnPhase.START_PLAYER_CONFESSION
        and state.active_player is not waiting_on
    ):
        state = apply_action(
            state, StartPlayerConfessionBoxAction(use=False), scenario.config
        ).state
    return state


def _scenario_of(state: GameState, *, source_path: str, tmp_path: Path) -> str:
    """Write the paused table back out as a scenario the CLI can be pointed at."""
    raw = json.loads(Path(source_path).read_text())
    initial = raw["initial_state"]
    initial["active_player"] = state.active_player.name.lower()
    initial["start_player_id"] = state.start_player.name.lower()
    initial["phase"] = state.phase.value
    initial["merchant_board_position"] = state.merchant_board_position
    initial["ship_position"] = state.ship_position
    initial["completed_rounds"] = state.completed_rounds
    initial["timing"] = {
        "absolute_turn": state.timing.absolute_turn,
        "round_number": state.timing.round_number,
        "season_number": state.timing.season_number,
        "turn_in_round": state.timing.turn_in_round,
    }
    initial["start_player_confession"] = {
        "pending": [player.name.lower() for player in state.start_player_confession_pending],
        "used": [player.name.lower() for player in state.start_player_confession_used],
    }
    for name, record in initial["players"].items():
        player = state.player_state(PlayerId.from_string(name))
        record["piety"] = player.piety
        record["resources"] = {
            "stone": player.resources.stone,
            "silver": player.resources.silver,
            "wheat": player.resources.wheat,
        }
    # A scenario finds its setup file, and that setup file its configs, by walking up from where it
    # sits -- so the copy has to sit somewhere with the same shape above it.
    root = Path(source_path).resolve().parent.parent
    scenarios = tmp_path / "scenarios"
    scenarios.mkdir(exist_ok=True)
    configs = tmp_path / "configs"
    if not configs.exists():
        configs.symlink_to(root / "configs")
    written = scenarios / "paused.json"
    written.write_text(json.dumps(raw))
    return str(written)


def _applied(path: str, *, action_index: int, capsys) -> str:
    exit_code = main(["apply", path, "--action-index", str(action_index), "--verbose"])
    output = capsys.readouterr().out
    assert exit_code == 0
    return output


def _index_of(path: str, *, use: bool) -> int:
    scenario = load_scenario(path)
    for index, action in enumerate(legal_actions(scenario.state, scenario.config), start=1):
        if action.use is use:
            return index
    raise AssertionError(f"No Confession Box action with use={use} in {path}.")


def _tithe_index(path: str) -> int:
    scenario = load_scenario(path)
    for index, action in enumerate(legal_actions(scenario.state, scenario.config), start=1):
        if action.resolution is TurnResolutionType.TITHE:
            return index
    raise AssertionError(f"No round-ending tithe in {path}.")


def test_cli_round_end_names_who_is_being_waited_on_and_stops(capsys) -> None:
    source = "scenarios/confession_box_owned_temp_piety_above_12_001.json"
    output = _applied(source, action_index=_tithe_index(source), capsys=capsys)

    assert "CONFESSION_BOX_PHASE:" in output
    assert "waiting on player_one" in output
    assert "START_PLAYER_MARKER:" not in output, "the marker was awarded before anyone answered"


def test_cli_apply_owned_confession_box_shows_temporary_piety_above_twelve(
    tmp_path: Path, capsys
) -> None:
    source = "scenarios/confession_box_owned_temp_piety_above_12_001.json"
    paused = _scenario_of(_round_ended(source), source_path=source, tmp_path=tmp_path)
    output = _applied(paused, action_index=_index_of(paused, use=True), capsys=capsys)

    assert (
        "CONFESSION_BOX_BONUS: player_one used own active Confession Box; temporary piety "
        "12 + 2 = 14 for start-player selection"
    ) in output
    assert "BUILDING_HIRED: player_one hired Confession Box" not in output
    assert (
        "START_PLAYER_MARKER: player_one takes the First Player marker on effective "
        "piety 14 and must choose who begins this round"
    ) in output
    assert "Piety position: 12" in output


def test_cli_apply_declining_says_so_rather_than_saying_nothing(tmp_path: Path, capsys) -> None:
    """A player who was asked and refused must not read the same as one never asked."""
    source = "scenarios/confession_box_owned_temp_piety_above_12_001.json"
    paused = _scenario_of(_round_ended(source), source_path=source, tmp_path=tmp_path)
    output = _applied(paused, action_index=_index_of(paused, use=False), capsys=capsys)

    assert "CONFESSION_BOX_DECLINED: player_one declined the Confession Box" in output
    assert "CONFESSION_BOX_BONUS:" not in output
    assert "START_PLAYER_MARKER:" in output


def test_cli_apply_market_hired_confession_box_shows_hire_then_bonus(
    tmp_path: Path, capsys
) -> None:
    source = "scenarios/confession_box_hire_market_start_player_001.json"
    paused = _scenario_of(_round_ended(source), source_path=source, tmp_path=tmp_path)
    output = _applied(paused, action_index=_index_of(paused, use=True), capsys=capsys)

    hire_text = "BUILDING_HIRED: player_two hired Confession Box from market; paid wheat 1 to bank"
    bonus_text = (
        "CONFESSION_BOX_BONUS: player_two used Confession Box from market; temporary piety "
        "9 + 2 = 11 for start-player selection"
    )
    assert hire_text in output
    assert bonus_text in output
    assert output.index(hire_text) < output.index(bonus_text) < output.index("START_PLAYER_MARKER:")


def test_cli_apply_opponent_hired_confession_box_shows_owner_payment(
    tmp_path: Path, capsys
) -> None:
    source = "scenarios/confession_box_hire_opponent_start_player_001.json"
    # The owner is asked first and declines; the hire is the question after that one.
    paused = _scenario_of(
        _round_ended(source, waiting_on=PlayerId.PLAYER_TWO),
        source_path=source,
        tmp_path=tmp_path,
    )
    output = _applied(paused, action_index=_index_of(paused, use=True), capsys=capsys)

    assert (
        "BUILDING_HIRED: player_two hired Confession Box from player_one; "
        "paid wheat 1 to player_one"
    ) in output
    assert (
        "CONFESSION_BOX_BONUS: player_two used Confession Box from player_one; temporary piety "
        "9 + 2 = 11 for start-player selection"
    ) in output


def test_cli_apply_confession_box_tie_break_orders_bonus_before_tie_break(
    tmp_path: Path, capsys
) -> None:
    source = "scenarios/confession_box_effective_piety_tie_break_001.json"
    paused = _scenario_of(_round_ended(source), source_path=source, tmp_path=tmp_path)
    output = _applied(paused, action_index=_index_of(paused, use=True), capsys=capsys)

    bonus_text = (
        "CONFESSION_BOX_BONUS: player_one used own active Confession Box; temporary piety "
        "8 + 2 = 10 for start-player selection"
    )
    tie_break_text = "START_PLAYER_TIE_BREAK:"
    marker_text = "START_PLAYER_MARKER: player_one takes the First Player marker"
    assert bonus_text in output
    assert tie_break_text in output
    assert marker_text in output
    assert output.index(bonus_text) < output.index(tie_break_text) < output.index(marker_text)
