import re
from pathlib import Path

from tools.ui_debug.generate_buildings import default_output_path, generate_building_tiles_page
from tools.ui_debug.render_buildings import (
    COLOR_GROUP_PALETTES,
    HEX_HALF_HEIGHT,
    TILE_NAME_CENTER_Y_OFFSET,
    TILE_NAME_FONT_SIZE,
    TILE_NAME_LINE_HEIGHT,
    ColorPalette,
    default_catalog_path,
    load_building_catalog,
    render_building_catalog_svg,
    render_building_tile,
    tile_text_lines,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
UI_DEBUG_DIR = REPO_ROOT / "tools" / "ui_debug"
CATALOG_PATH = UI_DEBUG_DIR / "building_catalog.json"
BASELINE_PROTOTYPE = UI_DEBUG_DIR / "prototypes" / "building_tiles.html"

EXPECTED_IDS = (
    "bank",
    "reliquary",
    "chapter_house",
    "confession_box",
    "scriptorium",
    "wagon_yard",
)

TWO_WORD_NAMES = ("Chapter House", "Stone Yard", "Wagon Yard", "Customs House", "Confession Box")

# The size the name was set at while the label was still headed by a level numeral.
WRAPPED_LABEL_FONT_SIZE = 10.0
# Helvetica's capitals stand about this fraction of the font size above the baseline.
CAP_HEIGHT_RATIO = 0.72


def _texts(svg: str) -> list[str]:
    return re.findall(r"<text[^>]*>([^<]*)</text>", svg)


def _baselines(svg: str) -> list[float]:
    return [float(y) for y in re.findall(r'<text x="[-\d.]+" y="(-?[\d.]+)"', svg)]


def test_building_catalog_file_exists() -> None:
    assert CATALOG_PATH.is_file()
    assert default_catalog_path() == CATALOG_PATH


def test_catalog_contains_exactly_24_buildings() -> None:
    catalog = load_building_catalog()
    assert len(catalog["buildings"]) == 24


def test_catalog_contains_expected_building_ids() -> None:
    catalog = load_building_catalog()
    ids = {building["id"] for building in catalog["buildings"]}
    for expected_id in EXPECTED_IDS:
        assert expected_id in ids


def test_catalog_levels_are_grouped_eight_by_eight() -> None:
    catalog = load_building_catalog()
    levels = [building["level"] for building in catalog["buildings"]]
    assert levels.count(1) == 8
    assert levels.count(2) == 8
    assert levels.count(3) == 8


def test_render_building_catalog_svg_returns_svg_string() -> None:
    svg = render_building_catalog_svg(load_building_catalog())
    assert isinstance(svg, str)
    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")


def test_rendered_svg_contains_group_labels_and_building_names() -> None:
    svg = render_building_catalog_svg(load_building_catalog())
    for expected_text in ("Light Blue", "Light Red", "Light Green", "Bank", "Reliquary"):
        assert expected_text in svg
    assert "Chapter" in svg
    assert "House" in svg


def test_a_tile_says_its_name_and_nothing_else() -> None:
    """The level is in the tile's colour, so the numeral it used to head the label with is gone."""
    catalog = load_building_catalog()

    for building in catalog["buildings"]:
        assert tile_text_lines(building) == building["name"].split()

    assert not {"I", "II", "III"}.intersection(_texts(render_building_catalog_svg(catalog)))


def test_a_name_breaks_between_words_and_never_inside_one() -> None:
    """A two-word name takes two lines; no line is part of a word, and nothing is hyphenated."""
    catalog = load_building_catalog()
    svg = render_building_catalog_svg(catalog)
    every_word = {word for building in catalog["buildings"] for word in building["name"].split()}

    for name in TWO_WORD_NAMES:
        assert tile_text_lines({"name": name}) == name.split()

    for line in _texts(svg):
        assert "-" not in line
        assert line in every_word or line in {group["label"] for group in catalog["color_groups"]}


def test_a_one_word_name_stays_on_one_line() -> None:
    for name in ("Inquisition", "Scriptorium", "Bank"):
        assert tile_text_lines({"name": name}) == [name]


def test_every_building_in_the_catalog_is_labelled_once() -> None:
    catalog = load_building_catalog()
    words = [word for building in catalog["buildings"] for word in building["name"].split()]
    group_labels = [group["label"] for group in catalog["color_groups"]]

    assert sorted(_texts(render_building_catalog_svg(catalog))) == sorted(words + group_labels)


def test_the_name_is_set_larger_than_the_label_it_replaced() -> None:
    building = load_building_catalog()["buildings"][0]

    assert TILE_NAME_FONT_SIZE > WRAPPED_LABEL_FONT_SIZE
    assert f'font-size="{TILE_NAME_FONT_SIZE:g}"' in render_building_tile(building, 0.0, 0.0)


def test_the_label_starts_below_the_centre_and_runs_down_from_there() -> None:
    """The ship rides above the middle of a hex, so the label is set below it and never above."""
    catalog = load_building_catalog()
    two_word = next(b for b in catalog["buildings"] if len(b["name"].split()) == 2)

    # The first line clears the hex centre, which is as low as the ship marker's hull reaches.
    assert TILE_NAME_CENTER_Y_OFFSET - CAP_HEIGHT_RATIO * TILE_NAME_FONT_SIZE > 0.0

    baselines = _baselines(render_building_tile(two_word, 0.0, 100.0))
    assert baselines == [
        100.0 + TILE_NAME_CENTER_Y_OFFSET,
        100.0 + TILE_NAME_CENTER_Y_OFFSET + TILE_NAME_LINE_HEIGHT,
    ]


def test_the_longest_label_still_sits_inside_the_hex() -> None:
    catalog = load_building_catalog()
    deepest = max(len(building["name"].split()) for building in catalog["buildings"])
    last_baseline = TILE_NAME_CENTER_Y_OFFSET + (deepest - 1) * TILE_NAME_LINE_HEIGHT

    assert deepest == 2
    assert last_baseline < HEX_HALF_HEIGHT


def test_a_tile_is_one_hex_and_a_line_of_text_per_word() -> None:
    catalog = load_building_catalog()

    for name in ("Bank", "Chapter House"):
        building = next(b for b in catalog["buildings"] if b["name"] == name)
        tile = render_building_tile(building, 0.0, 0.0)

        assert tile.count("<path") == 1
        assert tile.count("<text") == len(name.split())


def test_the_level_colours_are_unchanged() -> None:
    assert COLOR_GROUP_PALETTES == {
        "light_blue": ColorPalette(fill="#AEE0F7", stroke="#1E5A78"),
        "light_red": ColorPalette(fill="#F7B9B9", stroke="#7A2020"),
        "light_green": ColorPalette(fill="#BFE8B4", stroke="#2E5C24"),
    }


def test_generator_default_output_is_generated_building_tiles_page() -> None:
    assert default_output_path() == UI_DEBUG_DIR / "generated" / "building_tiles.html"


def test_generator_writes_generated_building_tiles_page(tmp_path: Path) -> None:
    output_path = tmp_path / "generated" / "building_tiles.html"
    written = generate_building_tiles_page(output_path=output_path)

    assert written == output_path
    assert output_path.is_file()
    content = output_path.read_text(encoding="utf-8")
    assert "<svg" in content
    assert "PILGRIM — Building Tiles" in content


def test_baseline_prototype_is_untouched() -> None:
    assert BASELINE_PROTOTYPE.is_file()
    assert "PILGRIM — Building Tiles" in BASELINE_PROTOTYPE.read_text(encoding="utf-8")
