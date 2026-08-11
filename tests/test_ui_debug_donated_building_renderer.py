import re
from pathlib import Path

import pytest

from tools.ui_debug.generate_donated_buildings import (
    default_output_path,
    generate_donated_building_tiles_page,
)
from tools.ui_debug.render_donated_buildings import (
    HEX_RADIUS,
    STAR_OUTER_RADIUS,
    TITLE,
    VP_TEXT_FONT_SIZE,
    VP_TEXT_OFFSET,
    default_data_path,
    load_donated_building_tiles,
    render_donated_building_contents,
    render_donated_building_tiles_svg,
    render_star_path,
    tiles_of,
)
from tools.ui_debug.render_pilgrimage_sites import STAR_OUTER_RADIUS as SITE_STAR_RADIUS
from tools.ui_debug.render_pilgrimage_sites import VP_TEXT_FONT_SIZE as SITE_VP_FONT_SIZE
from tools.ui_debug.render_pilgrimage_sites import VP_TEXT_OFFSET as SITE_VP_OFFSET

REPO_ROOT = Path(__file__).resolve().parents[1]
UI_DEBUG_DIR = REPO_ROOT / "tools" / "ui_debug"
DATA_PATH = UI_DEBUG_DIR / "donated_building_tiles.json"
BASELINE_PROTOTYPE = UI_DEBUG_DIR / "prototypes" / "donated_building_tiles.html"

EXPECTED_COLOR_GROUPS = ["light_blue", "light_red", "light_green"]
EXPECTED_VP = [2, 4, 6]
BUILDING_FILLS = ("#AEE0F7", "#F7B9B9", "#BFE8B4")


def _svg_body(path: Path) -> str:
    match = re.search(r"(<svg\b.*?</svg>)", path.read_text(encoding="utf-8"), re.S)
    assert match is not None
    return match.group(1)


def test_donated_building_tiles_data_file_exists() -> None:
    assert DATA_PATH.is_file()
    assert default_data_path() == DATA_PATH


def test_data_contains_exactly_three_tiles() -> None:
    assert len(tiles_of(load_donated_building_tiles())) == 3


def test_vp_values_are_two_four_six() -> None:
    tiles = tiles_of(load_donated_building_tiles())
    assert [tile["vp"] for tile in tiles] == EXPECTED_VP


def test_color_groups_match_building_levels() -> None:
    tiles = tiles_of(load_donated_building_tiles())
    assert [tile["color_group"] for tile in tiles] == EXPECTED_COLOR_GROUPS
    assert [tile["level"] for tile in tiles] == [1, 2, 3]


def test_tiles_of_accepts_a_bare_list() -> None:
    tiles = tiles_of(load_donated_building_tiles())
    assert tiles_of(tiles) == tiles


def test_render_star_path_returns_a_closed_star() -> None:
    star = render_star_path(0.0, 0.0, 24.0, 10.8)
    assert star.startswith("<path")
    assert "#F4D03F" in star
    assert star.count("L ") == 9
    assert " Z" in star


def test_the_vp_is_set_inside_the_star_at_the_proportion_a_site_sets_its_own() -> None:
    """The two stars are different sizes in their tiles' units, so this is what can be compared.

    What each renderer's own units come out as on the page is the composed table's business, and
    `test_ui_debug_game_table.py` is where the two are measured against each other. Here the star
    and the number inside it only have to stand in the same relation on both tiles.
    """
    assert VP_TEXT_FONT_SIZE / STAR_OUTER_RADIUS == pytest.approx(
        SITE_VP_FONT_SIZE / SITE_STAR_RADIUS
    )
    assert VP_TEXT_OFFSET / VP_TEXT_FONT_SIZE == pytest.approx(SITE_VP_OFFSET / SITE_VP_FONT_SIZE)


def test_the_star_stands_in_the_middle_of_the_hex() -> None:
    """A site's star hangs below its ship marker; this one has no ship over it to clear."""
    contents = render_donated_building_contents(tiles_of(load_donated_building_tiles())[0])
    star = re.search(r'<path d="M ([-\d.]+),([-\d.]+)', contents)
    number = re.search(r'<text x="([-\d.]+)" y="([-\d.]+)"', contents)
    assert star is not None and number is not None

    # a star is drawn from its top point, standing its outer radius above its middle
    assert float(star.group(1)) == pytest.approx(0.0, abs=0.01)
    assert float(star.group(2)) == pytest.approx(-STAR_OUTER_RADIUS, abs=0.01)
    assert float(number.group(1)) == pytest.approx(0.0, abs=0.05)
    assert float(number.group(2)) == pytest.approx(VP_TEXT_OFFSET, abs=0.05)


def test_the_star_scales_whole_with_the_slot_it_is_drawn_into() -> None:
    """A board slot asks for the contents at its own size; nothing inside is sized separately."""
    tile = tiles_of(load_donated_building_tiles())[0]
    half = render_donated_building_contents(tile, scale=0.5)

    star = re.search(r'<path d="M ([-\d.]+),([-\d.]+)', half)
    assert star is not None
    assert float(star.group(2)) == pytest.approx(-STAR_OUTER_RADIUS / 2, abs=0.01)
    assert f'font-size="{VP_TEXT_FONT_SIZE / 2:g}"' in half


def test_the_hex_keeps_its_size_and_its_colours() -> None:
    """Only the star was polished: the tile it stands on is untouched."""
    assert HEX_RADIUS == 60.0

    svg = render_donated_building_tiles_svg(load_donated_building_tiles())
    for fill in BUILDING_FILLS:
        assert fill in svg
    corner = max(
        float(x) for x, _ in re.findall(r"[ML] ([-\d.]+),([-\d.]+)", svg[: svg.index("<text")])
    )
    assert corner == pytest.approx(HEX_RADIUS)


def test_render_donated_building_tiles_svg_returns_svg_string() -> None:
    svg = render_donated_building_tiles_svg(load_donated_building_tiles())
    assert isinstance(svg, str)
    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")


def test_rendered_svg_contains_tile_and_star_colors() -> None:
    svg = render_donated_building_tiles_svg(load_donated_building_tiles())
    for color in (*BUILDING_FILLS, "#F4D03F"):
        assert color in svg


def test_rendered_svg_contains_vp_numbers() -> None:
    svg = render_donated_building_tiles_svg(load_donated_building_tiles())
    for value in EXPECTED_VP:
        assert f">{value}<" in svg


def test_generator_default_output_is_generated_donated_building_tiles_page() -> None:
    assert default_output_path() == UI_DEBUG_DIR / "generated" / "donated_building_tiles.html"


def test_generator_writes_generated_page(tmp_path: Path) -> None:
    output_path = tmp_path / "generated" / "donated_building_tiles.html"
    written = generate_donated_building_tiles_page(output_path=output_path)

    assert written == output_path
    assert output_path.is_file()
    content = output_path.read_text(encoding="utf-8")
    assert "<svg" in content
    assert TITLE in content


def test_baseline_prototype_is_untouched() -> None:
    assert BASELINE_PROTOTYPE.is_file()
    content = BASELINE_PROTOTYPE.read_text(encoding="utf-8")
    assert "PILGRIM — Special Tiles" in content
    assert "Special Tiles" in content


def test_generated_page_matches_baseline_facts(tmp_path: Path) -> None:
    """Coarse parity check against the baseline: same title, colours, and VP numbers."""
    generated = generate_donated_building_tiles_page(
        output_path=tmp_path / "donated_building_tiles.html"
    )
    baseline_text = BASELINE_PROTOTYPE.read_text(encoding="utf-8")
    generated_text = generated.read_text(encoding="utf-8")

    for text in (TITLE, *BUILDING_FILLS, "#F4D03F"):
        assert text in baseline_text
        assert text in generated_text

    baseline_svg = _svg_body(BASELINE_PROTOTYPE)
    generated_svg = _svg_body(generated)
    baseline_numbers = re.findall(r"<text[^>]*>([^<]*)</text>", baseline_svg)
    generated_numbers = re.findall(r"<text[^>]*>([^<]*)</text>", generated_svg)
    assert baseline_numbers == ["2", "4", "6"]
    assert generated_numbers == baseline_numbers

    for tag in ("path", "text", "rect"):
        assert len(re.findall(rf"<{tag}\b", generated_svg)) == len(
            re.findall(rf"<{tag}\b", baseline_svg)
        )
