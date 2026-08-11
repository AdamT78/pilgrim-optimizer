import json
import math
import re
from pathlib import Path

import pytest

from tools.ui_debug.generate_piety_track_v2 import (
    default_output_path,
    generate_piety_track_v2_page,
)
from tools.ui_debug.render_alms_table import (
    INK_FONT,
    LABEL_FONT_WEIGHT,
    ORNAMENT_RULE_GAP,
    ORNAMENT_STROKE_OPACITY,
    ORNAMENT_STROKE_WIDTH,
    ORNAMENT_TREFOIL_RADIUS,
    STAR_INNER_RADIUS,
    STAR_LABEL_FONT_SIZE,
    STAR_LABEL_OFFSET,
    STAR_OUTER_RADIUS,
    STEP_NUMBER_FONT_SIZE,
    STEP_RULE_STROKE_OPACITY,
    STEP_RULE_STROKE_WIDTH,
    TITLE_FONT,
    TITLE_FONT_SIZE,
    TITLE_FONT_WEIGHT,
    load_alms_config,
    load_alms_table_layout,
    render_alms_table_svg,
)
from tools.ui_debug.render_donated_buildings import render_star_path
from tools.ui_debug.render_piety_track_v2 import (
    default_layout_path,
    default_piety_config_path,
    load_piety_config,
    load_piety_track_v2_layout,
    piety_vp_values,
    player_by_id,
    position_center,
    position_center_x,
    position_rule_x,
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

ALMS_LAYOUT = load_alms_table_layout()

# What the baseline measured, before the board was restyled to read as the Alms Table does. The
# tests keep these so they can say which way each number moved rather than only pinning it.
BASELINE_PANEL_HEIGHT = 148.78
BASELINE_TITLE_TO_NUMBERS = 26.1
BASELINE_STAR_RADIUS = 16
BASELINE_LABEL_FONT_SIZE = 9

# Where `Piety Track` stops. There is no font metric to compute this from, so it is measured: at
# the title's 15 units of Georgia bold the text runs from x=14.0 to here. It is what the left arm
# of the header rule has to stay clear of.
TITLE_RIGHT_EDGE = 101.4


def label_width(value: int, size: float) -> float:
    """Roughly how wide a printed score comes out.

    Every digit of the family the board sets its ink in is 0.556 of the size across, and the minus
    sign 0.333. Rough is enough: this is only ever asked whether a score fits inside a star.
    """
    text = str(value)
    return size * (0.556 * sum(c.isdigit() for c in text) + 0.333 * text.count("-"))


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


def test_the_numbers_are_set_the_way_the_alms_table_sets_its_steps() -> None:
    """The same family at the same size and weight, from the Alms Table's own constant."""
    content = svg()
    geometry = track_geometry(layout(), 2)
    fill = layout()["track"]["position_label"]["fill"]

    assert STEP_NUMBER_FONT_SIZE > BASELINE_LABEL_FONT_SIZE
    for index in range(POSITION_COUNT):
        assert (
            f'<text x="{position_center_x(layout(), index):.1f}"'
            f' y="{geometry["number_baseline_y"]:.1f}" text-anchor="middle"'
            f' font-family="{INK_FONT}" font-size="{STEP_NUMBER_FONT_SIZE:g}"'
            f' font-weight="{LABEL_FONT_WEIGHT}" fill="{fill}">{index}</text>' in content
        )

    # And the Alms Table numbers its own steps with those same three, which is the whole point of
    # taking them from there: neither board can be restyled without the other following.
    alms = render_alms_table_svg(ALMS_LAYOUT, load_alms_config())
    assert (
        f'font-family="{INK_FONT}" font-size="{STEP_NUMBER_FONT_SIZE:g}"'
        f' font-weight="{LABEL_FONT_WEIGHT}"' in alms
    )


def test_a_hairline_divides_each_position_from_the_next() -> None:
    """The rule the Alms Table puts between two steps, at every boundary between two positions."""
    content = svg()
    geometry = track_geometry(layout(), 2)
    track = layout()["track"]
    box_width = track["box_width"]

    rules = re.findall(r"<line [^>]*/>", content)
    assert len(rules) == POSITION_COUNT - 1
    for index, rule in enumerate(rules):
        x = position_rule_x(layout(), index)
        assert x == pytest.approx(position_center_x(layout(), index) + box_width / 2)
        assert f'<line x1="{x:.1f}"' in rule
        assert f'stroke-opacity="{STEP_RULE_STROKE_OPACITY}"' in rule
        assert f'stroke-width="{STEP_RULE_STROKE_WIDTH:g}"' in rule

    # Between the numbers only: the strip's own two ends are closed by the panel's padding.
    assert position_rule_x(layout(), 0) > position_center_x(layout(), 0)
    with pytest.raises(KeyError):
        position_rule_x(layout(), POSITION_COUNT - 1)

    # A rule stands above the numbers and runs past the discs, so what keeps it off the pieces in
    # a position is width rather than height: both are narrower than the space they stand in.
    assert geometry["rule_y1"] < geometry["number_baseline_y"]
    assert geometry["rule_y2"] > geometry["discs_bottom"]
    disc = track["disc"]
    assert geometry["disc_offset"] + disc["radius"] < box_width / 2
    assert STAR_OUTER_RADIUS * math.cos(math.radians(18)) < box_width / 2


def test_the_title_reads_as_alms_table_does_and_stands_as_far_off_its_numbers() -> None:
    """The board's name at the Alms Table's size, and its track the same drop below it."""
    content = svg()
    geometry = track_geometry(layout(), 2)

    assert (
        f'font-family="{TITLE_FONT}" font-size="{TITLE_FONT_SIZE:g}"'
        f' font-weight="{TITLE_FONT_WEIGHT}"' in content
    )
    assert f">{layout()['title']}</text>" in content

    alms_drop = ALMS_LAYOUT["track"]["number_label_y"] - ALMS_LAYOUT["board"]["title_anchor"]["y"]
    assert layout()["track"]["title_to_numbers"] == alms_drop
    assert geometry["number_baseline_y"] - geometry["title_baseline_y"] == alms_drop
    assert alms_drop > BASELINE_TITLE_TO_NUMBERS


def test_the_header_lobes_and_the_rule_they_break_are_the_alms_tables() -> None:
    """The same three circles at the same size, on a rule of the same weight either side."""
    content = svg()
    geometry = track_geometry(layout(), 2)
    trefoil = re.search(r'<g fill="none" stroke=[^>]*>.*?</g>', content, re.S)
    assert trefoil is not None
    mark = trefoil.group()

    lobes = re.findall(r'<circle cx="[\d.]+" cy="[\d.]+" r="([\d.]+)"', mark)
    assert lobes == [f"{ORNAMENT_TREFOIL_RADIUS:.1f}"] * 3
    assert f'stroke-width="{ORNAMENT_STROKE_WIDTH:.1f}"' in mark
    assert f'stroke-opacity="{ORNAMENT_STROKE_OPACITY}"' in mark

    # Two arms of one length, each held the Alms Table's distance off the lobes it breaks for.
    arms = re.search(r'd="M ([\d.]+),[\d.]+ H ([\d.]+) M ([\d.]+),[\d.]+ H ([\d.]+)"', mark)
    x0, inner_left, inner_right, x1 = (float(value) for value in arms.groups())
    center_x = (x0 + x1) / 2
    # To the tenth of a unit the drawing is written in.
    assert center_x - inner_left == pytest.approx(ORNAMENT_RULE_GAP, abs=0.05)
    assert inner_right - center_x == pytest.approx(ORNAMENT_RULE_GAP, abs=0.05)
    assert inner_left - x0 == pytest.approx(x1 - inner_right, abs=0.1)

    # Clear of the title it runs out from, and of the padding it runs out to.
    assert x0 > TITLE_RIGHT_EDGE
    assert x1 < geometry["panel_width"] - layout()["panel"]["pad_x"]


def test_the_stars_and_the_scores_inside_them_are_the_alms_tables() -> None:
    """The same star at the same size, with the score set inside it the same way."""
    content = svg()
    geometry = track_geometry(layout(), 2)
    star_cy = geometry["star_cy"]

    assert STAR_OUTER_RADIUS > BASELINE_STAR_RADIUS
    for index, vp in enumerate(VP_VALUES):
        center_x = position_center_x(layout(), index)
        assert render_star_path(center_x, star_cy, STAR_OUTER_RADIUS, STAR_INNER_RADIUS) in content
        assert (
            f'<text x="{center_x:.1f}" y="{star_cy + STAR_LABEL_OFFSET:.1f}"'
            f' text-anchor="middle" font-family="{INK_FONT}"'
            f' font-size="{STAR_LABEL_FONT_SIZE:g}"'
            f' fill="{layout()["palette"]["star_label_fill"]}">{vp}</text>' in content
        )

    # Plain where the numbers above are bold, as on the Alms Table: the star is already standing
    # the score out, so the digits do not have to as well.
    scores = re.findall(rf'<text x="[\d.]+" y="{star_cy + STAR_LABEL_OFFSET:.1f}"[^>]*>', content)
    assert len(scores) == POSITION_COUNT
    assert all("font-weight" not in score for score in scores)
    # The widest score sits inside the star's waist rather than across its points.
    assert max(label_width(vp, STAR_LABEL_FONT_SIZE) for vp in VP_VALUES) < 2 * STAR_INNER_RADIUS
    # And the row the stars grew into still sits inside the hairline that runs round the panel.
    star_bottom = star_cy + STAR_OUTER_RADIUS * math.sin(math.radians(54))
    assert star_bottom < geometry["panel_height"] - layout()["ornament"]["inset"]["offset"]


def test_the_stars_stand_level_with_the_second_row_of_the_alms_tables_key() -> None:
    """A score reads across the table at one height, which is what `discs_to_stars` buys.

    The game table stands both panels' tops level and draws them at one scale, so the same y in
    panel coordinates is the same y on screen: this row of stars is the row the Alms Table's `11`
    star sits in. Measured against the Alms Table's own layout, so moving either board's key
    breaks this rather than quietly pulling the two apart.
    """
    key = ALMS_LAYOUT["record"]["scoring_key"]
    second_row_center_y = key["first_row_center_y"] + key["row_height"]

    assert track_geometry(layout(), 2)["star_cy"] == pytest.approx(second_row_center_y)

    # It is bought in the gap over the stars, so the strip is still a stack: a disc row fewer
    # brings them up with it rather than leaving a hole where the row was.
    short = track_geometry(layout(), 1)
    disc = layout()["track"]["disc"]
    assert second_row_center_y - short["star_cy"] == pytest.approx(2 * disc["radius"] + disc["gap"])


def test_the_two_player_panel_is_one_disc_row_shorter() -> None:
    """Dropping a row shortens the panel by exactly that row and nothing else."""
    disc = layout()["track"]["disc"]
    row_step = 2 * disc["radius"] + disc["gap"]

    tall = track_geometry(layout(), 2)
    short = track_geometry(layout(), 1)

    assert tall["panel_height"] - short["panel_height"] == pytest.approx(row_step)
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
def test_the_track_the_baseline_drew_is_still_the_track_here(
    variant_id: str, baseline: Path
) -> None:
    """The strip itself was not touched: the same panel, the same spaces, the same discs.

    The board was restyled to read as the Alms Table does, so it no longer matches the baseline
    byte for byte. What that restyling was not allowed to do is move the track: the panel is the
    same width, the positions fall on the same centres, and the discs are the same discs on the
    same position. Those are checked against the baseline's own numbers rather than against this
    layout, so the two cannot drift together.
    """
    drawn = baseline_svg(baseline)
    generated = strip_data_hooks(svg(variant_id))

    width = float(re.search(r'viewBox="[-\d.]+ [-\d.]+ ([\d.]+)', drawn).group(1))
    assert re.search(rf'viewBox="-20 -20 {width:g} ', generated)

    # Every position's number sits where the baseline puts it horizontally. Disc colours were
    # reseated for the game-table player-count control (red/yellow keep the left column), so the
    # match is by the set of fills and the set of x centres rather than by document order.
    for index in range(POSITION_COUNT):
        x = position_center_x(layout(), index)
        assert f'<text x="{x:.1f}"' in drawn
        assert f'<text x="{x:.1f}"' in generated
    drawn_discs = re.findall(
        r'<circle cx="([\d.]+)" cy="[\d.]+" r="9"[^>]*fill="([^"]+)"[^>]*/>', drawn
    )
    made_discs = re.findall(r"<circle[^>]*data-player-disc[^>]*/>", svg(variant_id))
    made_by_fill = {
        re.search(r'fill="([^"]+)"', disc).group(1): re.search(r'cx="([\d.]+)"', disc).group(1)
        for disc in made_discs
    }
    drawn_by_fill = {fill: cx for cx, fill in drawn_discs}
    assert set(made_by_fill) == set(drawn_by_fill)
    assert set(made_by_fill.values()) == set(drawn_by_fill.values())
    for disc in made_discs:
        assert 'r="9"' in disc
        assert 'stroke-width="1.2"' in disc


def test_the_polish_is_what_moved_the_board_away_from_the_baseline() -> None:
    """And the other side of it: every way the board now differs, and which way it went.

    The baseline drew its numbers and its scores at 9 in a panel whose title sat close over them,
    with a smaller star and no rule between one position and the next. Each of those grew or
    arrived to match the Alms Table, and the panel is taller for it.
    """
    drawn = baseline_svg(BASELINE_SVG)
    generated = svg()
    geometry = track_geometry(layout(), 2)

    assert 'font-size="9"' in drawn
    assert 'font-size="9"' not in generated
    assert f'font-size="{STEP_NUMBER_FONT_SIZE:g}"' in generated
    # The baseline had nothing dividing its positions, and no rule anywhere but the header.
    assert "<line " not in drawn
    assert generated.count("<line ") == POSITION_COUNT - 1
    # A bigger star in a taller panel, and the title further off the numbers than it was.
    assert BASELINE_STAR_RADIUS < STAR_OUTER_RADIUS
    assert BASELINE_PANEL_HEIGHT < geometry["panel_height"]
    assert BASELINE_TITLE_TO_NUMBERS < layout()["track"]["title_to_numbers"]


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
