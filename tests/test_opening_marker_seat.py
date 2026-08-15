"""Which seat the First Player marker opens on, asserted by the COLOUR of the board it sits on.

The rule names a colour: at the start of a game the marker sits on the first player board, and the
first player board is red. Engine player ids carry no colour, and the two orders do not line up --
`player_one` is WHITE and sits at the far END of the row of seats, so "the first board" and "the
first player id" name different seats at every player count. An assertion written against the id
passes under both readings, which is how the marker came to open on white while a test watched.

So every assertion here goes through the colour, and the colour comes from the layout the boards
are actually drawn from rather than from a table retyped into this file.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import PlayerId
from pilgrim.rules.round_end import award_first_player_marker
from pilgrim.rules.validation import TransitionValidationError
from pilgrim.setup.generator import generate_setup_scenario
from tools.ui_debug.render_player_boards_v2 import load_player_boards_v2_layout
from tools.ui_debug.render_table_layout import SEATED_PLAYERS

_CONFIG_PATH_FIELDS: tuple[str, ...] = (
    "board_file",
    "duties_file",
    "piety_file",
    "alms_file",
    "timing_file",
    "merchant_file",
    "ship_file",
    "buildings_file",
)

BOARD_COLOUR = {
    str(player["id"]): str(player["color"]) for player in load_player_boards_v2_layout()["players"]
}


def _opening_holder(player_count: int) -> str:
    generated = generate_setup_scenario(player_count=player_count, seed=7)
    return str(generated["initial_state"]["active_player"])  # type: ignore[index]


def _opening_scenario(tmp_path: Path, player_count: int):
    generated = generate_setup_scenario(player_count=player_count, seed=7)
    repo_root = Path.cwd().resolve()
    for field in _CONFIG_PATH_FIELDS:
        generated[field] = str((repo_root / str(generated[field])).resolve())  # type: ignore[index]
    scenario_path = tmp_path / f"opening_{player_count}p.json"
    scenario_path.write_text(json.dumps(generated, indent=2) + "\n", encoding="utf-8")
    return load_scenario(scenario_path)


def test_the_first_board_and_the_first_player_id_are_different_seats() -> None:
    """The premise every other test here depends on, checked rather than assumed.

    If white were seated first, or if the seating order ran in id order, a by-colour assertion
    would be worth no more than a by-id one and the rest of this file could be deleted. It is worth
    something precisely because these two disagree.
    """
    assert BOARD_COLOUR["player_one"] == "white"
    assert BOARD_COLOUR[SEATED_PLAYERS[0]] == "red"
    assert SEATED_PLAYERS[0] != "player_one"


@pytest.mark.parametrize("player_count", [2, 3, 4])
def test_a_generated_game_opens_with_the_marker_on_the_red_board(player_count: int) -> None:
    """Red at two, three and four players, because the colour does not move when a seat empties.

    Two players is the count that separates the readings hardest: the engine seats `player_one` and
    `player_two`, white and red, which are seats 4 and 1 -- the two ENDS of the row. Anything that
    reached for "the first two seats" would name red and yellow, and yellow is not playing.
    """
    holder = _opening_holder(player_count)

    assert BOARD_COLOUR[holder] == "red"
    assert holder == SEATED_PLAYERS[0]
    assert int(PlayerId.from_string(holder)) < player_count


@pytest.mark.parametrize("player_count", [2, 3, 4])
def test_round_end_marker_award_refuses_to_run_before_a_start_player_is_chosen(
    tmp_path: Path,
    player_count: int,
) -> None:
    """A game open has no chosen start player, so clockwise tie-break has no anchor yet."""
    scenario = _opening_scenario(tmp_path, player_count)
    assert scenario.state.start_player is None
    with pytest.raises(TransitionValidationError):
        award_first_player_marker(
            scenario.state,
            config=scenario.config,
            actor=scenario.state.active_player,
            action_id="opening_marker_probe",
        )


@pytest.mark.parametrize("player_count", [2, 3, 4])
def test_the_marker_holder_is_not_written_in_as_the_start_player(player_count: int) -> None:
    """The opening is a decision, so the seat that decides is not yet the seat that begins."""
    generated = generate_setup_scenario(player_count=player_count, seed=7)
    initial_state = generated["initial_state"]  # type: ignore[index]

    assert initial_state["phase"] == "start_player_selection"
    assert BOARD_COLOUR[str(initial_state["active_player"])] == "red"
    assert "start_player_id" not in initial_state
