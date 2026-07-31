import re
from pathlib import Path

from tools.ui_debug.generate_ship_marker import (
    default_output_path,
    generate_ship_marker_page,
)
from tools.ui_debug.render_ship_marker import (
    SHIP_COLOR,
    TITLE,
    default_data_path,
    load_ship_marker_examples,
    render_ship_icon,
    render_ship_marker_examples_svg,
    tiles_of,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
UI_DEBUG_DIR = REPO_ROOT / "tools" / "ui_debug"
DATA_PATH = UI_DEBUG_DIR / "ship_marker_examples.json"
BASELINE_PROTOTYPE = UI_DEBUG_DIR / "prototypes" / "ship_marker.html"

EXPECTED_BUILDING_IDS = ["confession_box", "brewery", "bank"]
EXPECTED_COLOR_GROUPS = ["light_blue", "light_red", "light_green"]
EXPECTED_LEVEL_LABELS = ["I", "II", "III"]
BUILDING_FILLS = ("#AEE0F7", "#F7B9B9", "#BFE8B4")


def _svg_body(path: Path) -> str:
    match = re.search(r"(<svg\b.*?</svg>)", path.read_text(encoding="utf-8"), re.S)
    assert match is not None
    return match.group(1)


def test_ship_marker_examples_data_file_exists() -> None:
    assert DATA_PATH.is_file()
    assert default_data_path() == DATA_PATH


def test_data_contains_exactly_three_example_tiles() -> None:
    assert len(tiles_of(load_ship_marker_examples())) == 3


def test_example_building_ids_are_the_first_tile_of_each_colour() -> None:
    tiles = tiles_of(load_ship_marker_examples())
    assert [tile["building_id"] for tile in tiles] == EXPECTED_BUILDING_IDS
    assert [tile["name"] for tile in tiles] == ["Confession Box", "Brewery", "Bank"]


def test_color_groups_and_levels_match_building_levels() -> None:
    tiles = tiles_of(load_ship_marker_examples())
    assert [tile["color_group"] for tile in tiles] == EXPECTED_COLOR_GROUPS
    assert [tile["level"] for tile in tiles] == [1, 2, 3]
    assert [tile["level_label"] for tile in tiles] == EXPECTED_LEVEL_LABELS


def test_tiles_of_accepts_a_bare_list() -> None:
    tiles = tiles_of(load_ship_marker_examples())
    assert tiles_of(tiles) == tiles


def test_render_ship_icon_returns_a_standalone_fragment() -> None:
    icon = render_ship_icon(0.0, 0.0)

    assert icon.startswith("<path")
    assert SHIP_COLOR in icon
    assert icon.count("<line") == 4  # bowsprit plus three masts
    assert icon.count("<path") == 5  # hull, three sails, pennant
    assert "<svg" not in icon


def test_render_ship_icon_scales_and_recolours() -> None:
    small = render_ship_icon(0.0, 0.0, scale=0.5, color="#123456")

    assert "#123456" in small
    assert SHIP_COLOR not in small
    assert small != render_ship_icon(0.0, 0.0, color="#123456")


def test_render_ship_marker_examples_svg_returns_svg_string() -> None:
    svg = render_ship_marker_examples_svg(load_ship_marker_examples())

    assert isinstance(svg, str)
    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")


def test_rendered_svg_contains_tile_colours_and_ship_colour() -> None:
    svg = render_ship_marker_examples_svg(load_ship_marker_examples())
    for color in (*BUILDING_FILLS, SHIP_COLOR):
        assert color in svg


def test_rendered_svg_contains_wrapped_labels_and_level_numerals() -> None:
    svg = render_ship_marker_examples_svg(load_ship_marker_examples())
    labels = re.findall(r"<text[^>]*>([^<]*)</text>", svg)

    assert labels == ["I", "Confession", "Box", "II", "Brewery", "III", "Bank"]


def test_generator_default_output_is_generated_ship_marker_page() -> None:
    assert default_output_path() == UI_DEBUG_DIR / "generated" / "ship_marker.html"


def test_generator_writes_generated_page(tmp_path: Path) -> None:
    output_path = tmp_path / "generated" / "ship_marker.html"
    written = generate_ship_marker_page(output_path=output_path)

    assert written == output_path
    assert output_path.is_file()
    content = output_path.read_text(encoding="utf-8")
    assert "<svg" in content
    assert TITLE in content


def test_baseline_prototype_is_untouched() -> None:
    assert BASELINE_PROTOTYPE.is_file()
    content = BASELINE_PROTOTYPE.read_text(encoding="utf-8")
    assert "PILGRIM — Ship Building Tiles" in content
    assert "ship silhouette" in content


def test_generated_page_matches_baseline_facts(tmp_path: Path) -> None:
    """Coarse parity check against the baseline: same title, colours, labels, and elements."""
    generated = generate_ship_marker_page(output_path=tmp_path / "ship_marker.html")
    baseline_text = BASELINE_PROTOTYPE.read_text(encoding="utf-8")
    generated_text = generated.read_text(encoding="utf-8")

    for text in (TITLE, *BUILDING_FILLS, SHIP_COLOR):
        assert text in baseline_text
        assert text in generated_text

    baseline_svg = _svg_body(BASELINE_PROTOTYPE)
    generated_svg = _svg_body(generated)
    assert generated_svg.split(">", 1)[0] == baseline_svg.split(">", 1)[0]  # same viewBox and size

    baseline_labels = re.findall(r"<text[^>]*>([^<]*)</text>", baseline_svg)
    assert re.findall(r"<text[^>]*>([^<]*)</text>", generated_svg) == baseline_labels

    for tag in ("path", "line", "text", "rect"):
        assert len(re.findall(rf"<{tag}\b", generated_svg)) == len(
            re.findall(rf"<{tag}\b", baseline_svg)
        )
