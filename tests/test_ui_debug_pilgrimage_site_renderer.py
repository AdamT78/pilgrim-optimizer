import math
import re
from pathlib import Path

import pytest

from tools.ui_debug.generate_pilgrimage_sites import (
    default_output_path,
    generate_pilgrimage_sites_page,
)
from tools.ui_debug.render_alms_table import STAR_LABEL_FONT_SIZE as TRACK_STAR_FONT_SIZE
from tools.ui_debug.render_alms_table import STAR_OUTER_RADIUS as TRACK_STAR_RADIUS
from tools.ui_debug.render_buildings import HEX_RADIUS, TILE_NAME_FONT_SIZE, TILE_NAME_LINE_HEIGHT
from tools.ui_debug.render_pilgrimage_sites import (
    CAP_HEIGHT_RATIO,
    HEX_APOTHEM,
    HEX_STROKE_WIDTH,
    LABEL_COLUMN_X,
    LABEL_GAP,
    LABEL_LETTER_Y,
    LABEL_LINE_HEIGHT,
    LABEL_VALUE_Y,
    SITE_FILL,
    SITE_STROKE,
    STAR_FOOT_RATIO,
    STAR_OUTER_RADIUS,
    STAR_SHIP_CLEARANCE,
    STAR_STROKE_WIDTH,
    TEXT_FONT_SIZE,
    TITLE,
    VP_TEXT_FONT_SIZE,
    VP_TEXT_OFFSET,
    default_data_path,
    load_pilgrimage_sites,
    render_pilgrimage_site_contents,
    render_pilgrimage_site_tile,
    render_pilgrimage_sites_svg,
    sites_of,
    star_center,
)
from tools.ui_debug.render_ship_marker import (
    SHIP_ANCHOR_OFFSET_Y,
    SHIP_BOTTOM_Y,
    render_ship_icon,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
UI_DEBUG_DIR = REPO_ROOT / "tools" / "ui_debug"
DATA_PATH = UI_DEBUG_DIR / "pilgrimage_sites.json"
BASELINE_PROTOTYPE = UI_DEBUG_DIR / "prototypes" / "pilgrimage_sites.html"
BASELINE_SOURCE = UI_DEBUG_DIR / "prototype_sources" / "pilgrimage_sites.py.txt"

EXPECTED_VP = [5, 5, 5, 6, 7]
EXPECTED_PIETY_AND_STONE = [(3, 3), (3, 3), (4, 4), (3, 4), (4, 5)]
STAR_FILL = "#F4D03F"
STAR_STROKE = "#B8960C"

# What the tile's parts measured while it still matched the baseline exactly.
BASELINE_STAR_RADIUS = 18.0
BASELINE_VP_FONT_SIZE = 9.0
BASELINE_LABEL_FONT_SIZE = 9.0
# Each tile prints its VP first, then the piety value, `P`, the stone value, and `S`.
TEXTS_PER_TILE = 5


def _svg_body(path: Path) -> str:
    match = re.search(r"(<svg\b.*?</svg>)", path.read_text(encoding="utf-8"), re.S)
    assert match is not None
    return match.group(1)


def _star_paths(svg: str) -> list[str]:
    return re.findall(rf'<path[^>]*fill="{STAR_FILL}"[^>]*/>', svg)


def _hex_paths(svg: str) -> list[str]:
    return re.findall(rf'<path[^>]*fill="{SITE_FILL}"[^>]*/>', svg)


def _text_elements(svg: str) -> list[str]:
    return re.findall(r"<text[^>]*>[^<]*</text>", svg)


def _hull_path(ship: str) -> str:
    """The hull is the first thing the ship draws, ahead of its rigging and sails."""
    match = re.search(r"<path[^>]*/>", ship)
    assert match is not None
    return match.group(0)


def _printed(svg: str) -> list[str]:
    """What the tiles say, with nothing about how it is set."""
    return re.findall(r"<text[^>]*>([^<]*)</text>", svg)


def _side_values(svg: str) -> list[str]:
    """Every printed element except each tile's VP: the P and S values and their letters."""
    texts = _text_elements(svg)
    return [text for index, text in enumerate(texts) if index % TEXTS_PER_TILE != 0]


def _vp_values(svg: str) -> list[str]:
    texts = _text_elements(svg)
    return [text for index, text in enumerate(texts) if index % TEXTS_PER_TILE == 0]


def test_pilgrimage_sites_data_file_exists() -> None:
    assert DATA_PATH.is_file()
    assert default_data_path() == DATA_PATH


def test_data_contains_exactly_five_sites() -> None:
    sites = sites_of(load_pilgrimage_sites())

    assert len(sites) == 5
    assert [site["id"] for site in sites] == [f"pilgrimage_site_{n}" for n in range(1, 6)]


def test_vp_values_run_five_five_five_six_seven() -> None:
    sites = sites_of(load_pilgrimage_sites())

    assert [site["vp"] for site in sites] == EXPECTED_VP


def test_piety_and_stone_values_match_the_baseline() -> None:
    sites = sites_of(load_pilgrimage_sites())

    assert [(site["piety"], site["stone"]) for site in sites] == EXPECTED_PIETY_AND_STONE


def test_sites_of_accepts_a_bare_list() -> None:
    sites = sites_of(load_pilgrimage_sites())

    assert sites_of(sites) == sites


def test_one_tile_carries_its_hex_star_and_three_values() -> None:
    site = sites_of(load_pilgrimage_sites())[4]
    tile = render_pilgrimage_site_tile(site, 0.0, 0.0)

    assert tile.count("<path") == 2, "one hex and one star"
    assert [text for text in re.findall(r"<text[^>]*>([^<]*)</text>", tile)] == [
        "7",
        "4",
        "P",
        "5",
        "S",
    ]


def test_render_pilgrimage_sites_svg_returns_svg_string() -> None:
    svg = render_pilgrimage_sites_svg(load_pilgrimage_sites())

    assert isinstance(svg, str)
    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")


def test_rendered_svg_carries_the_site_and_star_colours() -> None:
    svg = render_pilgrimage_sites_svg(load_pilgrimage_sites())

    for color in (SITE_FILL, SITE_STROKE, STAR_FILL, STAR_STROKE):
        assert color in svg
    assert (SITE_FILL, SITE_STROKE) == ("#F7CBA0", "#A85D1D")


def test_rendered_svg_carries_the_printed_values() -> None:
    svg = render_pilgrimage_sites_svg(load_pilgrimage_sites())

    for value in ("5", "6", "7", "P", "S"):
        assert f">{value}<" in svg
    assert svg.count(">P<") == 5
    assert svg.count(">S<") == 5


def test_generator_default_output_is_the_generated_pilgrimage_sites_page() -> None:
    assert default_output_path() == UI_DEBUG_DIR / "generated" / "pilgrimage_sites.html"


def test_generator_writes_generated_page(tmp_path: Path) -> None:
    output_path = tmp_path / "generated" / "pilgrimage_sites.html"
    written = generate_pilgrimage_sites_page(output_path=output_path)

    assert written == output_path
    assert output_path.is_file()
    content = output_path.read_text(encoding="utf-8")
    assert "<svg" in content
    assert TITLE in content


def test_baseline_prototype_is_untouched() -> None:
    assert BASELINE_PROTOTYPE.is_file()
    content = BASELINE_PROTOTYPE.read_text(encoding="utf-8")

    assert "PILGRIM — Pilgrimage Sites" in content
    assert "Pilgrimage Site" in content


def test_baseline_prototype_source_is_untouched() -> None:
    assert BASELINE_SOURCE.is_file()
    content = BASELINE_SOURCE.read_text(encoding="utf-8")

    assert 'Generate the Pilgrim "Pilgrimage Sites" special tiles' in content
    assert "N_TILES = 5" in content


def test_the_star_and_its_vp_are_set_the_way_the_piety_track_sets_its_own() -> None:
    """Both grew, and the VP keeps the track's share of its star and the same drop below it."""
    assert STAR_OUTER_RADIUS > BASELINE_STAR_RADIUS
    assert VP_TEXT_FONT_SIZE > BASELINE_VP_FONT_SIZE
    assert VP_TEXT_FONT_SIZE / STAR_OUTER_RADIUS == pytest.approx(
        TRACK_STAR_FONT_SIZE / TRACK_STAR_RADIUS
    )
    assert VP_TEXT_OFFSET == pytest.approx(VP_TEXT_FONT_SIZE / 3.0)


def test_the_star_hangs_below_the_ship_marker() -> None:
    """A map hex can carry both, so the star clears the ship rather than running up into it."""
    site = sites_of(load_pilgrimage_sites())[0]
    _, star_y = star_center(0.0, 0.0)

    drawn = _star_paths(render_pilgrimage_site_contents(site))[0]
    corners = [float(y) for y in re.findall(r"[-\d.]+,(-?[\d.]+)", drawn)]
    top, foot = min(corners), max(corners)

    assert top == pytest.approx(star_y - STAR_OUTER_RADIUS, abs=0.01)
    assert foot == pytest.approx(star_y + STAR_FOOT_RATIO * STAR_OUTER_RADIUS, abs=0.01)
    assert top - SHIP_BOTTOM_Y == pytest.approx(STAR_SHIP_CLEARANCE, abs=0.01)


def test_the_ships_keel_is_measured_off_the_hull_it_is_drawn_from() -> None:
    """What the star clears is the drawn ship, not a figure kept alongside it."""
    hull = _hull_path(render_ship_icon(0.0, 0.0))
    lowest = max(float(y) for _, y in re.findall(r"(-?[\d.]+),(-?[\d.]+)", hull))
    # The keel is a curve, so it dips below its own corners, to half its control point's depth.
    assert SHIP_BOTTOM_Y == pytest.approx(SHIP_ANCHOR_OFFSET_Y + lowest / 2.0)


def test_the_star_fits_the_hex_it_is_drawn_in() -> None:
    """Dropping it clear of the ship still has to land it inside the tile."""
    site = sites_of(load_pilgrimage_sites())[0]
    drawn = _star_paths(render_pilgrimage_site_contents(site))[0]
    corners = [(float(x), float(y)) for x, y in re.findall(r"(-?[\d.]+),(-?[\d.]+)", drawn)]
    room = HEX_APOTHEM - HEX_STROKE_WIDTH / 2.0 - STAR_STROKE_WIDTH / 2.0

    for x, y in corners:
        assert abs(y) < room
        # The hex narrows towards its points, so the width at a corner's own height is the bound.
        assert abs(x) < HEX_RADIUS * (1.0 - abs(y) / (2.0 * HEX_APOTHEM))


def test_the_p_and_s_values_are_set_the_size_a_building_tile_sets_its_name() -> None:
    assert TEXT_FONT_SIZE == TILE_NAME_FONT_SIZE
    assert TEXT_FONT_SIZE > BASELINE_LABEL_FONT_SIZE
    assert LABEL_LINE_HEIGHT == TILE_NAME_LINE_HEIGHT

    values = _side_values(render_pilgrimage_sites_svg(load_pilgrimage_sites()))
    assert all(f'font-size="{TEXT_FONT_SIZE:g}"' in value for value in values)


def test_each_value_stands_above_the_mid_line_and_its_letter_hangs_below() -> None:
    """The two rows straddle the middle of the hex rather than sitting under it."""
    caps = CAP_HEIGHT_RATIO * TEXT_FONT_SIZE

    assert LABEL_VALUE_Y < 0.0 and LABEL_VALUE_Y - caps < 0.0
    assert LABEL_LETTER_Y > 0.0 and LABEL_LETTER_Y - caps > 0.0
    # And they straddle it evenly: as much of the pair stands above the line as hangs below.
    assert (LABEL_VALUE_Y - caps) + LABEL_LETTER_Y == pytest.approx(0.0)

    tile = _side_values(render_pilgrimage_site_contents(sites_of(load_pilgrimage_sites())[0]))
    rows = {float(re.search(r'y="(-?[\d.]+)"', value).group(1)) for value in tile}
    assert rows == {round(LABEL_VALUE_Y, 1), round(LABEL_LETTER_Y, 1)}


def test_the_values_stand_clear_of_the_star_they_flank() -> None:
    tile = _side_values(render_pilgrimage_site_contents(sites_of(load_pilgrimage_sites())[0]))
    columns = {re.search(r'x="(-?[\d.]+)"', value).group(1) for value in tile}

    assert columns == {f"{-LABEL_COLUMN_X:.1f}", f"{LABEL_COLUMN_X:.1f}"}
    assert LABEL_COLUMN_X - STAR_OUTER_RADIUS * math.sin(math.radians(72.0)) == pytest.approx(
        LABEL_GAP
    )
    assert LABEL_COLUMN_X + TEXT_FONT_SIZE / 2.0 < HEX_RADIUS


def test_the_hex_is_the_baseline_and_the_setting_of_its_contents_is_not(tmp_path: Path) -> None:
    """What a tile prints has not changed; how the star and the values are set has."""
    generated = _svg_body(generate_pilgrimage_sites_page(output_path=tmp_path / "sites.html"))
    baseline = _svg_body(BASELINE_PROTOTYPE)

    assert _hex_paths(generated) == _hex_paths(baseline)
    assert len(_star_paths(generated)) == len(EXPECTED_VP)
    assert _star_paths(generated) != _star_paths(baseline)

    assert _printed(generated) == _printed(baseline)
    assert _text_elements(generated) != _text_elements(baseline)
    assert all(
        f'font-size="{round(VP_TEXT_FONT_SIZE, 2):g}"' in value for value in _vp_values(generated)
    )


def test_generated_page_matches_baseline_facts(tmp_path: Path) -> None:
    """The page around the SVG says the same things the baseline says."""
    generated = generate_pilgrimage_sites_page(output_path=tmp_path / "pilgrimage_sites.html")
    baseline_text = BASELINE_PROTOTYPE.read_text(encoding="utf-8")
    generated_text = generated.read_text(encoding="utf-8")

    for text in (TITLE, SITE_FILL, SITE_STROKE, STAR_FILL, STAR_STROKE, "5 special"):
        assert text in baseline_text
        assert text in generated_text

    printed = re.findall(r"<text[^>]*>([^<]*)</text>", _svg_body(generated))
    assert printed == ["5", "3", "P", "3", "S"] * 2 + [
        "5",
        "4",
        "P",
        "4",
        "S",
        "6",
        "3",
        "P",
        "4",
        "S",
        "7",
        "4",
        "P",
        "5",
        "S",
    ]
