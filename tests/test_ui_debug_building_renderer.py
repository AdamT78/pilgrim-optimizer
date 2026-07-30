from pathlib import Path

from tools.ui_debug.generate_buildings import default_output_path, generate_building_tiles_page
from tools.ui_debug.render_buildings import (
    default_catalog_path,
    load_building_catalog,
    render_building_catalog_svg,
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
