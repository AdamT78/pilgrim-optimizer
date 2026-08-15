"""Which seat the First Player marker opens on, asserted by the COLOUR of that board.

The rule names a colour: at game open the marker sits on the first player board, and the first
player board is red. Player ids are UI mapping and may be remapped again; colour is what the rule
itself says, so this file keeps asserting through colour even when id order and seat order align.
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
LAYOUT_FILES = (
    "player_boards_v2_layout.json",
    "alms_table_layout.json",
    "duty_wheel_layout.json",
    "piety_track_v2_layout.json",
)


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


def test_seat_one_is_player_one_and_red_at_two_three_and_four_players() -> None:
    """Seat 1 is deliberately aligned to player_one, and that board is red."""
    assert SEATED_PLAYERS[0] == "player_one"
    assert BOARD_COLOUR["player_one"] == "red"
    for player_count in (2, 3, 4):
        holder = _opening_holder(player_count)
        assert holder == "player_one"
        assert BOARD_COLOUR[holder] == "red"


def _id_to_colour(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(player["id"]): str(player["color"]) for player in data["players"]}


def test_all_four_layout_files_share_one_id_to_colour_mapping() -> None:
    """Read from files, not retyped: all four copies of this fact have to agree."""
    root = Path(__file__).resolve().parents[1] / "tools" / "ui_debug"
    mappings = {name: _id_to_colour(root / name) for name in LAYOUT_FILES}
    first = next(iter(mappings.values()))
    for name, mapping in mappings.items():
        assert mapping == first, f"{name} drifted from the shared id-to-colour mapping"
    assert first == {
        "player_one": "red",
        "player_two": "yellow",
        "player_three": "blue",
        "player_four": "white",
    }


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
