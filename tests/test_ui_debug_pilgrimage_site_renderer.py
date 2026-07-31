import re
from pathlib import Path

from tools.ui_debug.generate_pilgrimage_sites import (
    default_output_path,
    generate_pilgrimage_sites_page,
)
from tools.ui_debug.render_pilgrimage_sites import (
    SITE_FILL,
    SITE_STROKE,
    TITLE,
    default_data_path,
    load_pilgrimage_sites,
    render_pilgrimage_site_tile,
    render_pilgrimage_sites_svg,
    sites_of,
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


def _svg_body(path: Path) -> str:
    match = re.search(r"(<svg\b.*?</svg>)", path.read_text(encoding="utf-8"), re.S)
    assert match is not None
    return match.group(1)


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


def test_generated_svg_is_the_baseline_svg(tmp_path: Path) -> None:
    """Parity is exact here, so the check can be exact: same SVG, element for element."""
    generated = generate_pilgrimage_sites_page(output_path=tmp_path / "pilgrimage_sites.html")

    assert _svg_body(generated) == _svg_body(BASELINE_PROTOTYPE)


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
