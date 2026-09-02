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
    CROWN_HEIGHT_W,
    CROWN_POINTS,
    CROWN_WIDTH_R,
    MIN_RULE_STUB,
    SEAL_CROWN_DARKEN,
    SEAL_CX,
    SEAL_CY,
    SEAL_RADIUS,
    SEAL_RIM_DARKEN,
    SEAL_RING_DARKEN,
    SEAL_SEED,
    SEAL_TILT,
    SEAT_ORDER,
    check_rule_stub,
    default_layout_path,
    default_piety_config_path,
    first_player_by_seat,
    header_rule_end_x,
    load_piety_config,
    load_piety_track_v2_layout,
    piety_vp_values,
    player_by_id,
    position_center,
    position_center_x,
    position_rule_x,
    render_piety_track_v2_svg,
    render_piety_tracks_v2_html,
    seated_players,
    seats_that_can_hold_the_marker,
    track_geometry,
    variant_by_id,
)
from tools.ui_debug.render_seal import WOBBLE, darken

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
PLAYER_COLORS = ("red", "yellow", "blue", "white")
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


def variant_stack(page: str) -> str:
    """The panels the page stacks for its variants, and nothing else on it.

    Picked out by the class that marks them rather than by cutting the page at the first heading:
    the marker section below has panels of its own, and a boundary measured off a heading's
    position quietly means something else the day a second heading lands between the two.
    """
    return "".join(re.findall(r'<figure class="track-row">.*?</figure>', page, re.S))


def marker_panels(page: str) -> str:
    """The first player marker panels, picked out the same way and for the same reason."""
    return "".join(re.findall(r'<figure class="seal-row">.*?</figure>', page, re.S))


def test_layout_file_exists_and_is_json() -> None:
    assert LAYOUT_JSON.is_file()
    assert default_layout_path() == LAYOUT_JSON
    assert json.loads(LAYOUT_JSON.read_text(encoding="utf-8"))["title"] == "Piety Track"


def test_the_layout_describes_both_player_count_variants() -> None:
    assert [variant["id"] for variant in layout()["variants"]] == list(VARIANT_IDS)
    assert variant_by_id(layout(), "3_4_player")["disc_rows"] == 2
    assert variant_by_id(layout(), "2_player")["disc_rows"] == 2
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
    assert player_by_id(layout(), "player_one")["fill"] == "#C0392B"
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
    # Two rows, one column: the pair stacks vertically and shares a centre x.
    assert len({re.search(r'cx="([\d.]+)"', disc).group(1) for disc in discs}) == 1
    assert len({re.search(r'cy="([\d.]+)"', disc).group(1) for disc in discs}) == 2


def test_discs_start_on_the_position_the_layout_starts_them_on() -> None:
    assert layout()["starting_position"] == 0
    assert layout()["track"]["disc_position"] == layout()["starting_position"]

    for variant_id in VARIANT_IDS:
        _, disc_y = position_center(layout(), variant_id, 0)
        geometry = track_geometry(layout(), variant_by_id(layout(), variant_id)["disc_rows"])
        assert disc_y == geometry["discs_cy"]


def test_explicit_piety_positions_place_discs_on_the_named_steps() -> None:
    expected_positions = {"player_one": 2, "player_two": 7, "player_three": 11}
    panel = render_piety_track_v2_svg(
        layout(),
        config(),
        "3_4_player",
        piety_positions_by_player=expected_positions,
    )
    discs = re.findall(r'<circle[^>]*data-player-disc="true"[^>]*/>', panel)
    by_player = {re.search(r'data-player="(\w+)"', disc).group(1): disc for disc in discs}
    offsets = {player["id"]: player for player in seated_players(layout(), "3_4_player")}

    assert set(by_player) == set(expected_positions)
    for player_id, position in expected_positions.items():
        disc = by_player[player_id]
        assert f'data-piety-position="{position}"' in disc
        x = float(re.search(r'cx="([\d.]+)"', disc).group(1))
        y = float(re.search(r'cy="([\d.]+)"', disc).group(1))
        expected = offsets[player_id]
        assert x == pytest.approx(position_center_x(layout(), position) + expected["cx_offset"], abs=0.05)
        assert y == pytest.approx(expected["cy"], abs=0.05)


@pytest.mark.parametrize("position", [-1, 13])
def test_renderer_refuses_out_of_range_piety_positions(position: int) -> None:
    with pytest.raises(
        ValueError, match=rf"player_one piety position {position} is outside the drawn range 0..12"
    ):
        render_piety_track_v2_svg(
            layout(),
            config(),
            "2_player",
            piety_positions_by_player={"player_one": position, "player_two": 0},
        )


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
                f'<text data-piety-position-label="{index}" x="{position_center_x(layout(), index):.1f}"'
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

    # It is bought in the gap over the stars, so the strip is still a stack: asking for a row
    # fewer brings the stars up with it rather than leaving a hole where the row was.
    short = track_geometry(layout(), 1)
    disc = layout()["track"]["disc"]
    assert second_row_center_y - short["star_cy"] == pytest.approx(2 * disc["radius"] + disc["gap"])


def test_the_two_player_panel_keeps_the_three_four_player_height() -> None:
    """With two stacked rows at 2P, both variants now stand at the same panel height."""
    tall = track_geometry(layout(), 2)
    two_player = track_geometry(layout(), variant_by_id(layout(), "2_player")["disc_rows"])

    assert two_player["panel_height"] == pytest.approx(tall["panel_height"])
    assert two_player["panel_width"] == pytest.approx(tall["panel_width"])


def test_the_page_stacks_every_variant() -> None:
    content = render_piety_tracks_v2_html(layout(), config())

    # Counted on the stack rather than on every `<svg>` on the page: the first player marker has
    # its own section below with a panel per seat, and this is about the stack at the top of it.
    assert content.count('class="track-row"') == len(VARIANT_IDS)
    # Captioned like every other panel here, rather than named by position in the subtitle: the
    # page grew a second section, so "top" and "bottom" stopped identifying anything.
    for variant_id in VARIANT_IDS:
        label = variant_by_id(layout(), variant_id)["label"]
        assert f"<figcaption>{label}</figcaption>" in content
    assert "Top: " not in content and "Bottom: " not in content
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
    [("3_4_player", BASELINE_SVG)],
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


def test_the_two_player_track_intentionally_differs_from_the_old_baseline() -> None:
    """The 2P discs now stack on one step, so this variant is no longer baseline-identical."""
    drawn = baseline_svg(BASELINE_2P_SVG)
    generated = strip_data_hooks(svg("2_player"))

    assert generated != drawn
    discs = re.findall(r'<circle[^>]*data-player-disc="true"[^>]*/>', svg("2_player"))
    xs = {re.search(r'cx="([\d.]+)"', disc).group(1) for disc in discs}
    ys = {re.search(r'cy="([\d.]+)"', disc).group(1) for disc in discs}
    assert len(xs) == 1
    assert len(ys) == 2


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
        "data-piety-position-label",
        "data-piety-score-row",
    }


def test_the_page_and_the_baseline_page_agree_on_what_is_drawn() -> None:
    """Coarse parity: the same two tracks, the same labels, the same VP values.

    Measured on the stack the baseline drew and not on the whole page, which has since grown a
    marker section the baseline never had. What is being compared is still two tracks against two.
    """
    generated = variant_stack(render_piety_tracks_v2_html(layout(), config()))
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


# --- the first player marker --------------------------------------------------------------------


def sealed(seat: int, variant_id: str = "3_4_player") -> str:
    return render_piety_track_v2_svg(layout(), config(), variant_id, seat)


def test_a_panel_told_nothing_about_the_marker_is_the_panel_it_was_before() -> None:
    """The marker is an addition, not a rearrangement: without a seat, nothing about this moved.

    Byte equality rather than a look at the seal's own elements, because what is being claimed is
    that the header, the title, the rule, the numbers, the discs and the stars are all untouched --
    which is a claim about everything on the panel, not about the part that was added.
    """
    for variant_id in VARIANT_IDS:
        plain = render_piety_track_v2_svg(layout(), config(), variant_id)

        assert plain == render_piety_track_v2_svg(layout(), config(), variant_id, None)
        assert "first-player" not in plain
        assert "data-first-player-seat" not in plain


def test_the_seal_is_struck_in_the_colour_of_whichever_seat_is_named() -> None:
    """One attribute in, one seat's wax out. Four seats, four seals, no two the same colour."""
    waxes = set()
    for seat, colour in enumerate(("red", "yellow", "blue", "white"), start=1):
        panel = sealed(seat)
        player = first_player_by_seat(layout(), seat)

        assert player["color"] == colour
        assert f'data-first-player-seat="{seat}"' in panel
        assert f'data-first-player-seal="true" data-player="{player["id"]}"' in panel
        assert f'fill="{player["fill"]}"' in panel
        waxes.add(player["fill"])

    assert len(waxes) == 4


def test_the_seal_takes_its_colour_from_the_same_players_the_discs_are_drawn_from() -> None:
    """There is one seat-colour table on this board, and the seal reads that one.

    A second copy would let the marker and the disc it stands for drift apart, which is the one
    way this element could contradict the board it is drawn on.
    """
    for seat, player_id in enumerate(SEAT_ORDER, start=1):
        assert first_player_by_seat(layout(), seat) == player_by_id(layout(), player_id)

    assert set(SEAT_ORDER) == set(PLAYER_IDS)
    assert [player_by_id(layout(), pid)["fill"] for pid in SEAT_ORDER] == [
        "#C0392B",
        "#F4D03F",
        "#2E86C1",
        "#FFFFFF",
    ]


def test_the_seat_order_is_the_one_the_game_table_seats_its_players_in() -> None:
    """Named here because the renderer cannot import the page that composes it, so it is checked.

    Red is seat 1 there and it must be seat 1 here, or the same marker would name one player on
    the panel and another on the page around it.
    """
    from tools.ui_debug.render_table_layout import SEATED_PLAYERS

    assert SEAT_ORDER == SEATED_PLAYERS


def test_nothing_in_this_renderer_already_pairs_a_seat_with_a_player() -> None:
    """The premise `SEAT_ORDER` rests on, checked rather than asserted in a comment.

    The panel tags a disc with whose it is, never with which seat: `data-player-seat` is stamped on
    afterwards by the game table, onto markup this module has already finished with. The layout's
    own `seats` are the 2x2 cluster -- where a disc sits next to the others -- and carry no seat
    number to read one off. If that ever changes, this fails and `SEAT_ORDER` should go.
    """
    panel = render_piety_track_v2_svg(layout(), config(), "3_4_player")

    assert "data-player-seat" not in panel
    assert panel.count('data-player-disc="true"') == 4  # whose, not which seat
    for variant in layout()["variants"]:
        for seat in variant["seats"]:
            assert set(seat) == {"player", "row", "column"}


def test_the_rest_of_the_seal_is_the_seat_colour_pulled_toward_black() -> None:
    """Three shades off one colour, so a re-tuned palette needs nothing rewritten here."""
    wax = first_player_by_seat(layout(), 3)["fill"]
    panel = sealed(3)

    assert (SEAL_RIM_DARKEN, SEAL_RING_DARKEN, SEAL_CROWN_DARKEN) == (0.45, 0.72, 0.50)
    assert f'stroke="{darken(wax, SEAL_RIM_DARKEN)}"' in panel
    assert f'stroke="{darken(wax, SEAL_RING_DARKEN)}"' in panel
    assert f'fill="{darken(wax, SEAL_CROWN_DARKEN)}"' in panel


def test_the_seal_is_struck_where_it_was_approved_and_nowhere_else() -> None:
    """Pinned by value: the position was settled by eye, so nothing computes it back."""
    assert (SEAL_CX, SEAL_CY, SEAL_RADIUS, SEAL_SEED, SEAL_TILT) == (516.0, 27.0, 22.0, 1.1, -14.0)

    panel = sealed(1)
    assert f'<g transform="rotate({SEAL_TILT:g} {SEAL_CX:g} {SEAL_CY:g})">' in panel
    assert f'<circle cx="{SEAL_CX:g}" cy="{SEAL_CY:g}"' in panel
    assert panel.count("data-first-player-seal") == 1


def test_the_crown_is_one_closed_outline_rather_than_a_shape_on_a_band() -> None:
    """Two shapes leave a seam across the middle at this size, which reads as a crack in the wax."""
    panel = sealed(1)
    width = SEAL_RADIUS * CROWN_WIDTH_R
    height = width * CROWN_HEIGHT_W
    points = " ".join(
        f"{SEAL_CX + fx * width:.2f},{SEAL_CY + fy * height:.2f}" for fx, fy in CROWN_POINTS
    )

    assert len(CROWN_POINTS) == 7
    assert f'<polygon points="{points}"' in panel
    # Drawn last, over the wax and the ring rather than under either.
    assert panel.index(points) > panel.index(f'<circle cx="{SEAL_CX:g}" cy="{SEAL_CY:g}"')


def test_the_crown_turns_with_the_wax_because_it_came_off_the_same_die_as_the_ring() -> None:
    """A tilt that moved the ring and left the crown square would depict half a die turning.

    It is undetectable on the ring alone, which is a circle, so the crown is the only place the
    strike can be seen to be at an angle. It is handed to the seal as its impression rather than
    appended after it, which is what puts it inside the one rotation.
    """
    panel = sealed(1)
    turn = f'<g transform="rotate({SEAL_TILT:g} {SEAL_CX:g} {SEAL_CY:g})">'
    struck = panel[panel.index(turn) + len(turn) : panel.index("</g></g>")]

    assert panel.count(turn) == 1  # one turn for the whole strike, not one per piece
    crown_fill = darken(first_player_by_seat(layout(), 1)["fill"], SEAL_CROWN_DARKEN)
    assert f'fill="{crown_fill}"' in struck  # the crown is inside it, not after it


def test_the_wax_goes_on_over_the_header_rule_and_lets_it_out_the_far_side() -> None:
    """Wax is pressed onto an edge, not parked in a gap left for it.

    The rule is untouched -- it runs to where it always ran -- and the seal laps the inner hairline
    at the top by a couple of units, which is what applying it over an edge looks like.
    """
    geometry = track_geometry(layout(), 2)
    rule_end = header_rule_end_x(layout(), geometry)
    panel = sealed(1)

    assert rule_end == pytest.approx(575.3)
    assert f"H {rule_end:.1f}" in panel
    assert SEAL_CX + SEAL_RADIUS < rule_end  # the rule comes out the right of the wax
    hairline = layout()["ornament"]["inset"]["offset"]
    assert SEAL_CY - SEAL_RADIUS == pytest.approx(hairline - 2.5)  # laps it, on purpose


def test_the_seal_clears_everything_it_was_measured_against() -> None:
    """The four clearances the position was approved on, so a nudge has to move a number here."""
    geometry = track_geometry(layout(), 2)
    inset = layout()["ornament"]["inset"]["offset"]
    inner_right = geometry["panel_width"] - inset
    number_cap_y = geometry["number_baseline_y"] - 8.0  # cap height of the "12", at 11px

    assert round(check_rule_stub(layout(), geometry), 1) == 38.9
    assert round(number_cap_y - (SEAL_CY + SEAL_RADIUS), 1) == 10.0
    assert round(inner_right - (SEAL_CX + SEAL_RADIUS), 1) == 51.8
    assert round(SEAL_CY - SEAL_RADIUS, 1) == 5.0


def test_a_seal_shoved_up_against_the_end_of_the_rule_stops_the_render(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The assertion is load-bearing, so this is the test that it fires at runtime.

    Nothing downstream notices a rule that stops just short of the wax: it renders perfectly well
    and merely looks like a stray hair on the seal, so the failure has to happen here or not at
    all. `+18` past the trough is where the run of line stops being enough to read as a line.
    """
    module = "tools.ui_debug.render_piety_track_v2"
    geometry = track_geometry(layout(), 2)
    trough = SEAL_RADIUS * (1 - WOBBLE[0] - WOBBLE[1])
    last_good = header_rule_end_x(layout(), geometry) - MIN_RULE_STUB - trough

    monkeypatch.setattr(f"{module}.SEAL_CX", last_good)
    assert check_rule_stub(layout(), geometry) == pytest.approx(MIN_RULE_STUB)

    monkeypatch.setattr(f"{module}.SEAL_CX", last_good + 0.5)
    with pytest.raises(AssertionError) as raised:
        check_rule_stub(layout(), geometry)
    assert "17.5" in str(raised.value)

    # And no panel comes out of it, rather than a panel with a hair on the seal.
    with pytest.raises(AssertionError):
        render_piety_track_v2_svg(layout(), config(), "3_4_player", 1)


def test_the_stub_is_measured_at_the_trough_of_the_wobble_not_at_the_radius() -> None:
    """At the nominal radius a seal can be declared clear and still show a hair where wax runs wide.

    The factor comes off `WOBBLE`, so re-tuning the ripple re-tunes this rather than leaving a
    check that was true of the old edge.
    """
    geometry = track_geometry(layout(), 2)
    trough = SEAL_RADIUS * (1 - WOBBLE[0] - WOBBLE[1])

    assert trough < SEAL_RADIUS
    assert check_rule_stub(layout(), geometry) == pytest.approx(
        header_rule_end_x(layout(), geometry) - (SEAL_CX + trough)
    )
    assert MIN_RULE_STUB == 18.0


def test_no_seat_outside_the_table_can_be_given_the_marker() -> None:
    for seat in (0, 5, -1):
        with pytest.raises(KeyError):
            first_player_by_seat(layout(), seat)


def test_the_debug_page_shows_the_marker_at_every_seat_that_can_hold_it() -> None:
    """Nothing sets the attribute yet, so without these the seal renders nowhere to be looked at.

    The absence case is on the page for the same reason as the four seats: a reviewer has to see
    that no one holding the marker leaves nothing behind, which is not visible from a seal.
    """
    section = marker_panels(render_piety_tracks_v2_html(layout(), config()))

    assert section.count('class="seal-row"') == 7  # one absent, four seats, two on the 2p panel
    assert section.count("data-first-player-seal") == 6
    for seat, colour in enumerate(("red", "yellow", "blue", "white"), start=1):
        assert f"<figcaption>3–4 player track — seat {seat}, {colour}</figcaption>" in section
    assert "<figcaption>3–4 player track — no seat set, no seal struck</figcaption>" in section


def test_the_page_shows_the_marker_on_whichever_seats_a_variant_actually_sits() -> None:
    """Read from seated discs, so a variant controls which seats can hold the marker."""
    assert seats_that_can_hold_the_marker(layout(), "3_4_player") == [1, 2, 3, 4]
    assert seats_that_can_hold_the_marker(layout(), "2_player") == [1, 2]

    section = marker_panels(render_piety_tracks_v2_html(layout(), config()))
    assert "<figcaption>2 player track — seat 1, red</figcaption>" in section
    assert "<figcaption>2 player track — seat 2, yellow</figcaption>" in section
    assert "2 player track — seat 4" not in section


def test_the_marker_section_renders_the_real_panel_rather_than_a_picture_of_one() -> None:
    """So what is reviewed is what would ship. Same renderer, same call, only a seat added."""
    section = marker_panels(render_piety_tracks_v2_html(layout(), config()))

    for variant_id, seat in (("3_4_player", 1), ("2_player", 2), ("3_4_player", None)):
        assert render_piety_track_v2_svg(layout(), config(), variant_id, seat) in section


def test_captioning_the_old_panels_did_not_touch_what_they_draw() -> None:
    """A caption is chrome around a panel, not part of it: the SVG is the same SVG to the byte."""
    stack = variant_stack(render_piety_tracks_v2_html(layout(), config()))
    drawn = re.findall(r"<svg\b.*?</svg>", stack, re.S)

    assert drawn == [svg(variant_id) for variant_id in VARIANT_IDS]
    assert "<figcaption>" not in "".join(drawn)


def test_the_marker_section_is_an_addition_and_leaves_the_stack_above_it_alone() -> None:
    """The two panels the page already showed are the same two panels, drawn the same way."""
    stack = variant_stack(render_piety_tracks_v2_html(layout(), config()))

    for variant_id in VARIANT_IDS:
        assert svg(variant_id) in stack
    assert "data-first-player-seat" not in stack
    assert stack.count("<svg") == len(VARIANT_IDS)


def test_asking_for_every_seat_strikes_every_seal_and_hides_all_but_the_holders() -> None:
    """So a page can move the marker without restriking wax in JavaScript.

    Emitting only the holder's seal would leave a page that wants to move it re-deriving rim, ring
    and crown from a seat colour in a second language, and then keeping that copy agreeing with
    `darken()`. Striking all four here leaves the page nothing to do but show one and hide three.
    """
    panel = render_piety_track_v2_svg(layout(), config(), "3_4_player", 2, interactive=True)
    groups = re.findall(r"<g data-first-player-seal=[^>]*>", panel)

    assert len(groups) == 4
    assert sum('visibility="hidden"' in group for group in groups) == 3
    for seat in (1, 2, 3, 4):
        player = first_player_by_seat(layout(), seat)
        assert f'data-player-seat="{seat}"' in panel
        assert f'fill="{player["fill"]}"' in panel  # every seat's wax, not only the holder's
    held = next(group for group in groups if 'visibility="hidden"' not in group)
    assert 'data-player-seat="2"' in held and 'data-player-color="yellow"' in held


def test_every_seal_in_that_mode_is_struck_at_the_one_approved_position() -> None:
    """Only the colour and the hidden flag differ. Nothing is offset to make room for the others."""
    panel = render_piety_track_v2_svg(layout(), config(), "3_4_player", 1, interactive=True)
    turn = f'<g transform="rotate({SEAL_TILT:g} {SEAL_CX:g} {SEAL_CY:g})">'

    assert panel.count(turn) == 4
    assert panel.count(f'<circle cx="{SEAL_CX:g}" cy="{SEAL_CY:g}"') == 4
    assert len(set(re.findall(r'<circle cx="516" cy="27" r="([\d.]+)"', panel))) == 1


def test_which_seats_get_a_seal_comes_from_who_is_seated_not_from_counting_to_four() -> None:
    """The same source that decides which discs a variant seats, so the two cannot disagree."""
    two = render_piety_track_v2_svg(layout(), config(), "2_player", 1, interactive=True)
    seats = [
        int(seat) for seat in re.findall(r'data-first-player-seal[^>]*data-player-seat="(\d)"', two)
    ]

    assert seats == seats_that_can_hold_the_marker(layout(), "2_player") == [1, 2]


def test_asking_for_every_seat_but_naming_none_hides_the_lot() -> None:
    """A page mid-build, not a game state: the marker always sits with someone at a real table."""
    panel = render_piety_track_v2_svg(layout(), config(), "3_4_player", None, interactive=True)
    groups = re.findall(r"<g data-first-player-seal=[^>]*>", panel)

    assert len(groups) == 4
    assert all('visibility="hidden"' in group for group in groups)
    assert "data-first-player-seat" not in panel


def test_the_lone_seal_is_still_what_a_panel_draws_unless_asked_otherwise() -> None:
    """The default is untouched, which is what leaves every standalone page byte-identical."""
    for seat in (None, 1, 4):
        plain = render_piety_track_v2_svg(layout(), config(), "3_4_player", seat)

        assert "data-player-seat" not in plain
        assert "visibility" not in plain
        assert plain.count("data-first-player-seal") == (0 if seat is None else 1)


def test_the_marker_is_the_only_thing_the_seat_changes_about_the_panel() -> None:
    """Nothing else on the board reads it: no restyled disc, no second highlight, no CSS hook."""
    plain = render_piety_track_v2_svg(layout(), config(), "3_4_player")
    marked = sealed(1)

    # The seal is struck last, so lifting it off is a cut from where it starts to the end of the
    # drawing. What is left has to be the panel as it was, attribute and all.
    struck_at = marked.index("<g data-first-player-seal")
    without = marked[:struck_at] + marked[marked.index("\n</svg>") :]

    assert without.replace(' data-first-player-seat="1"', "") == plain
    assert marked.count("data-player-disc") == plain.count("data-player-disc") == 4


def test_destination_variants_share_one_pill_and_always_show_conversion_silver() -> None:
    panel = render_piety_track_v2_svg(
        layout(),
        config(),
        "2_player",
        piety_choice_steps=[
            {"piety_destination": 2, "silver_delta": 2, "hire_payment": "stone"},
            {"piety_destination": 2, "silver_delta": 2, "hire_payment": "silver"},
            {"piety_destination": 1, "silver_delta": 1, "hire_payment": None},
        ],
    )

    assert panel.count('data-piety-choice-template="true"') == 2
    assert panel.count('data-piety-choice-pill="true"') == 0
    destination_two = re.search(
        r'data-piety-choice-destination="2".*?data-piety-choice-silver="true"[^>]*>(.*?)</text>',
        panel,
    )
    destination_one = re.search(
        r'data-piety-choice-destination="1".*?data-piety-choice-silver="true"[^>]*>(.*?)</text>',
        panel,
    )
    assert destination_two and destination_two.group(1) == "+2"
    assert destination_one and destination_one.group(1) == "+1"
    assert "data-piety-choice-piety" not in panel
    assert "data-piety-choice-silver-settled" not in panel


def test_piety_choice_pills_do_not_take_a_stock_hue() -> None:
    panel = render_piety_track_v2_svg(
        layout(),
        config(),
        "2_player",
        piety_choice_steps=[
            {"piety_destination": 1, "silver_delta": 1, "hire_payment": None},
        ],
    )

    key = re.search(
        r'<rect data-resource-choice-key="silver"[^>]* fill="([^"]+)"'
        r' stroke="([^"]+)" stroke-width="([^"]+)"',
        panel,
    )
    observed = None if key is None else (key.group(1), key.group(2), float(key.group(3)))

    assert observed == ("#B9B9B4", "#858582", 1.6)
