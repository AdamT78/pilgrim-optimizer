import json
import re
from pathlib import Path

import pytest

from tools.ui_debug.generate_piety_track_v2 import (
    default_output_path,
    generate_piety_track_v2_page,
)
from tools.ui_debug.render_piety_track_v2 import (
    default_layout_path,
    default_piety_config_path,
    load_piety_config,
    load_piety_track_v2_layout,
    piety_vp_values,
    player_by_id,
    position_center,
    position_center_x,
    render_piety_track_v2_svg,
    render_piety_tracks_v2_html,
    track_geometry,
    variant_by_id,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
UI_DEBUG_DIR = REPO_ROOT / "tools" / "ui_debug"
PROTOTYPES_DIR = UI_DEBUG_DIR / "prototypes"

LAYOUT_JSON = UI_DEBUG_DIR / "piety_track_v2_layout.json"
BASELINE_HTML = PROTOTYPES_DIR / "piety_tracks_v2.html"
BASELINE_SVG = PROTOTYPES_DIR / "piety_track_v2.svg"
BASELINE_2P_SVG = PROTOTYPES_DIR / "piety_track_2p_v2.svg"
BASELINE_SOURCE = UI_DEBUG_DIR / "prototype_sources" / "piety_tracks_v2.py.txt"

VARIANT_IDS = ("3_4_player", "2_player")
PLAYER_IDS = ("player_one", "player_two", "player_three", "player_four")
PLAYER_COLORS = ("white", "red", "yellow", "blue")
POSITION_COUNT = 13
VP_VALUES = (-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5, 7, 9)


def layout() -> dict:
    return load_piety_track_v2_layout()


def config() -> dict:
    return load_piety_config()


def svg(variant_id: str = "3_4_player") -> str:
    return render_piety_track_v2_svg(layout(), config(), variant_id)


def baseline_svg(path: Path) -> str:
    """The baseline as the renderer emits it: no XML declaration, no trailing newline."""
    content = path.read_text(encoding="utf-8")
    return content.replace('<?xml version="1.0" encoding="UTF-8"?>\n', "").rstrip("\n")


def strip_data_hooks(content: str) -> str:
    return re.sub(r'\s*data-[a-z-]+="[^"]*"', "", content)


def test_layout_file_exists_and_is_json() -> None:
    assert LAYOUT_JSON.is_file()
    assert default_layout_path() == LAYOUT_JSON
    assert json.loads(LAYOUT_JSON.read_text(encoding="utf-8"))["title"] == "Piety Track"


def test_the_layout_describes_both_player_count_variants() -> None:
    assert [variant["id"] for variant in layout()["variants"]] == list(VARIANT_IDS)
    assert variant_by_id(layout(), "3_4_player")["disc_rows"] == 2
    assert variant_by_id(layout(), "2_player")["disc_rows"] == 1
    with pytest.raises(KeyError):
        variant_by_id(layout(), "5_player")


def test_every_variant_runs_from_position_zero_to_twelve() -> None:
    assert layout()["track"]["position_count"] == POSITION_COUNT

    for variant_id in VARIANT_IDS:
        content = svg(variant_id)
        for index in range(POSITION_COUNT):
            assert f">{index}</text>" in content
        # The track is a row: every position sits to the right of the one before it.
        centers = [position_center_x(layout(), index) for index in range(POSITION_COUNT)]
        assert centers == sorted(centers)

    with pytest.raises(KeyError):
        position_center_x(layout(), POSITION_COUNT)


def test_the_layout_names_four_players_by_colour() -> None:
    players = layout()["players"]

    assert [player["id"] for player in players] == list(PLAYER_IDS)
    assert [player["color"] for player in players] == list(PLAYER_COLORS)
    assert player_by_id(layout(), "player_one")["fill"] == "#FFFFFF"
    with pytest.raises(KeyError):
        player_by_id(layout(), "player_five")


def test_the_three_four_player_variant_seats_four_discs_on_position_zero() -> None:
    variant = variant_by_id(layout(), "3_4_player")
    content = svg("3_4_player")

    assert [seat["player"] for seat in variant["seats"]] == list(PLAYER_IDS)
    discs = re.findall(r'<circle[^>]*data-player-disc="true"[^>]*/>', content)
    assert len(discs) == len(PLAYER_IDS)
    assert all('data-piety-position="0"' in disc for disc in discs)
    # Two rows of two, so no disc shares a centre with another.
    assert len({(re.search(r'cx="([\d.]+)" cy="([\d.]+)"', disc).groups()) for disc in discs}) == 4


def test_the_two_player_variant_seats_two_discs_on_position_zero() -> None:
    variant = variant_by_id(layout(), "2_player")
    content = svg("2_player")

    assert [seat["player"] for seat in variant["seats"]] == ["player_one", "player_two"]
    discs = re.findall(r'<circle[^>]*data-player-disc="true"[^>]*/>', content)
    assert len(discs) == 2
    assert all('data-piety-position="0"' in disc for disc in discs)
    # One row, so both discs sit at the same height.
    assert len({re.search(r'cy="([\d.]+)"', disc).group(1) for disc in discs}) == 1


def test_discs_start_on_the_position_the_layout_starts_them_on() -> None:
    assert layout()["starting_position"] == 0
    assert layout()["track"]["disc_position"] == layout()["starting_position"]

    for variant_id in VARIANT_IDS:
        _, disc_y = position_center(layout(), variant_id, 0)
        geometry = track_geometry(layout(), variant_by_id(layout(), variant_id)["disc_rows"])
        assert disc_y == geometry["discs_cy"]


def test_vp_values_come_from_the_piety_config_not_the_layout() -> None:
    """The engine's own table, parsed with the engine's own reader, so the two cannot disagree."""
    assert default_piety_config_path() == REPO_ROOT / "configs" / "piety.json"
    assert tuple(piety_vp_values(config())) == VP_VALUES

    raw = LAYOUT_JSON.read_text(encoding="utf-8")
    assert "score_by_position" not in raw
    assert '"vp"' not in raw


def test_the_renderer_refuses_a_config_that_does_not_fit_the_track() -> None:
    short = {"max_position": 3, "score_by_position": {str(i): i for i in range(4)}}

    with pytest.raises(ValueError, match="4 VP values but the layout draws 13"):
        render_piety_track_v2_svg(layout(), short, "3_4_player")


def test_each_variant_renders_one_svg_carrying_its_own_name() -> None:
    for variant_id in VARIANT_IDS:
        content = svg(variant_id)
        assert content.startswith("<svg")
        assert content.endswith("</svg>")
        assert content.count("<svg") == 1
        assert 'data-component="piety-track-v2"' in content
        assert f'data-piety-variant="{variant_id}"' in content

    with pytest.raises(KeyError):
        svg("nope")


def test_the_panel_wears_the_house_ornament() -> None:
    """The point of v2: the title in the artwork, the hairline, and the trefoil header."""
    content = svg()
    ornament = layout()["ornament"]

    assert ">Piety Track</text>" in content
    inset = ornament["inset"]["offset"]
    assert f'<rect x="{inset}" y="{inset}"' in content
    assert f'stroke-opacity="{ornament["inset"]["stroke_opacity"]}"' in content
    # Three lobes between two rules.
    trefoil = re.search(r"<g fill=\"none\".*?</g>", content, re.S)
    assert trefoil is not None
    assert trefoil.group().count("<circle") == 3
    assert trefoil.group().count(" H ") == 2


def test_the_two_player_panel_is_one_disc_row_shorter() -> None:
    """Dropping a row shortens the panel by exactly that row and nothing else."""
    disc = layout()["track"]["disc"]
    row_step = 2 * disc["radius"] + disc["gap"]

    tall = track_geometry(layout(), 2)
    short = track_geometry(layout(), 1)

    assert tall["panel_height"] - short["panel_height"] == row_step
    assert tall["panel_width"] == short["panel_width"]


def test_the_page_stacks_every_variant() -> None:
    content = render_piety_tracks_v2_html(layout(), config())

    assert content.count("<svg") == len(VARIANT_IDS)
    assert content.count('class="track-row"') == len(VARIANT_IDS)
    for variant_id in VARIANT_IDS:
        assert f'data-piety-variant="{variant_id}"' in content
    assert "Piety Track" in content
    assert 'data-component="piety-track-v2"' in content
    assert 'data-player="player_one"' in content
    assert 'data-player-disc="true"' in content
    assert "piety_track_v2_layout.json" in content
    assert "configs/piety.json" in content


def test_generator_writes_the_page_to_a_temp_path(tmp_path: Path) -> None:
    destination = tmp_path / "piety_tracks_v2.html"
    written = generate_piety_track_v2_page(output_path=destination)

    assert written == destination
    content = destination.read_text(encoding="utf-8")
    assert "Piety Track" in content
    assert 'data-component="piety-track-v2"' in content


def test_generator_creates_a_missing_output_directory(tmp_path: Path) -> None:
    destination = tmp_path / "generated" / "piety_tracks_v2.html"
    generate_piety_track_v2_page(output_path=destination)

    assert destination.is_file()
    assert default_output_path() == UI_DEBUG_DIR / "generated" / "piety_tracks_v2.html"


@pytest.mark.parametrize(
    ("variant_id", "baseline"),
    [("3_4_player", BASELINE_SVG), ("2_player", BASELINE_2P_SVG)],
)
def test_generated_svg_matches_its_baseline_byte_for_byte(variant_id: str, baseline: Path) -> None:
    """The data hooks are the only thing the extraction adds to the drawing."""
    assert strip_data_hooks(svg(variant_id)) == baseline_svg(baseline)


def test_the_data_hooks_are_the_only_difference_from_the_baseline() -> None:
    generated = svg()

    assert generated != baseline_svg(BASELINE_SVG)
    hooks = set(re.findall(r"data-[a-z-]+", generated))
    assert hooks == {
        "data-component",
        "data-piety-variant",
        "data-piety-position",
        "data-player",
        "data-player-disc",
        "data-player-color",
    }


def test_the_page_and_the_baseline_page_agree_on_what_is_drawn() -> None:
    """Coarse parity: the same two tracks, the same labels, the same VP values."""
    generated = render_piety_tracks_v2_html(layout(), config())
    baseline = BASELINE_HTML.read_text(encoding="utf-8")

    for content in (generated, baseline):
        assert content.count("<svg") == 2
        assert ">Piety Track</text>" in content
        assert ">0</text>" in content
        assert ">12</text>" in content
        for vp in VP_VALUES:
            assert f">{vp}</text>" in content


def test_v2_does_not_disturb_the_current_piety_track() -> None:
    """v2 is a second view, not a replacement: v1 keeps its layout, renderer, and generator."""
    for path in ("piety_track_layout.json", "render_piety_track.py", "generate_piety_track.py"):
        assert (UI_DEBUG_DIR / path).is_file()

    v1 = json.loads((UI_DEBUG_DIR / "piety_track_layout.json").read_text(encoding="utf-8"))
    assert [variant["id"] for variant in v1["variants"]] == ["three_four_player", "two_player"]


def test_baseline_prototypes_are_still_present_and_untouched() -> None:
    for path in (BASELINE_HTML, BASELINE_SVG, BASELINE_2P_SVG):
        content = path.read_text(encoding="utf-8")
        assert "Piety" in content
        assert "Piety Track" in content
        assert "data-component" not in content


def test_prototype_source_is_still_the_reference_copy() -> None:
    content = BASELINE_SOURCE.read_text(encoding="utf-8")

    assert "Piety Track" in content
    assert "Piety track with the house ornament applied" in content
