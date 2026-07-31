import re
from pathlib import Path

import pytest

from tools.ui_debug.generate_piety_track import (
    default_output_path,
    generate_piety_track_page,
)
from tools.ui_debug.render_piety_track import (
    default_layout_path,
    default_piety_config_path,
    load_piety_config,
    load_piety_track_layout,
    piety_vp_values,
    render_piety_track_svg,
    render_piety_track_variant_svg,
    render_star_path,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
UI_DEBUG_DIR = REPO_ROOT / "tools" / "ui_debug"
LAYOUT_PATH = UI_DEBUG_DIR / "piety_track_layout.json"
PIETY_CONFIG_PATH = REPO_ROOT / "configs" / "piety.json"
BASELINE_PROTOTYPE = UI_DEBUG_DIR / "prototypes" / "piety_tracks.html"
BASELINE_SOURCE = UI_DEBUG_DIR / "prototype_sources" / "piety_tracks.py.txt"

EXPECTED_VP_VALUES = [-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5, 7, 9]
KEY_COLORS = ("#B9B9B4", "#F4D03F", "#C0392B", "#2E86C1")
TITLE = "Piety tracks"


def _svg_bodies(path: Path) -> list[str]:
    return re.findall(r"(<svg\b.*?</svg>)", path.read_text(encoding="utf-8"), re.S)


def _rendered_svg() -> str:
    return render_piety_track_svg(load_piety_track_layout(), load_piety_config())


def test_layout_and_piety_config_files_exist() -> None:
    assert LAYOUT_PATH.is_file()
    assert default_layout_path() == LAYOUT_PATH
    assert PIETY_CONFIG_PATH.is_file()
    assert default_piety_config_path() == PIETY_CONFIG_PATH


def test_vp_values_are_read_from_the_piety_config() -> None:
    assert piety_vp_values(load_piety_config()) == EXPECTED_VP_VALUES


def test_layout_does_not_carry_the_vp_table() -> None:
    """VP numbers belong to configs/piety.json; the layout only describes geometry."""
    layout_text = LAYOUT_PATH.read_text(encoding="utf-8")

    assert "score_by_position" not in layout_text
    assert "-5" not in layout_text


def test_renderer_follows_the_config_rather_than_hardcoding_vp() -> None:
    layout = load_piety_track_layout()
    patched = {"max_position": 12, "score_by_position": {str(i): i * 100 for i in range(13)}}
    svg = render_piety_track_svg(layout, patched)

    assert ">1200<" in svg
    assert ">-5<" not in svg


def test_renderer_rejects_a_config_that_does_not_fit_the_track() -> None:
    layout = load_piety_track_layout()
    short_config = {"max_position": 4, "score_by_position": {str(i): i for i in range(5)}}

    with pytest.raises(ValueError, match="5 VP values"):
        render_piety_track_svg(layout, short_config)


def test_render_star_path_returns_a_closed_star() -> None:
    star = render_star_path(0.0, 0.0, 16.0, 7.2)

    assert star.startswith("<path")
    assert "#F4D03F" in star
    assert star.count("L ") == 9
    assert " Z" in star


def test_render_piety_track_svg_returns_svg_string() -> None:
    svg = _rendered_svg()

    assert isinstance(svg, str)
    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")
    assert svg.count("<svg") == 2  # one strip per player-count variant


def test_rendered_svg_contains_vp_labels_and_key_colours() -> None:
    svg = _rendered_svg()

    for vp in EXPECTED_VP_VALUES:
        assert f">{vp}<" in svg
    for color in KEY_COLORS:
        assert color in svg


def test_rendered_svg_labels_every_piety_position() -> None:
    layout = load_piety_track_layout()
    variant = layout["variants"][0]
    svg = render_piety_track_variant_svg(layout, EXPECTED_VP_VALUES, variant)
    labels = re.findall(r"<text[^>]*>([^<]*)</text>", svg)

    positions = [str(index) for index in range(13)]
    assert labels[0::2] == positions
    assert labels[1::2] == [str(vp) for vp in EXPECTED_VP_VALUES]


def test_variants_differ_only_by_token_rows() -> None:
    layout = load_piety_track_layout()
    three_four, two = layout["variants"]
    svgs = [
        render_piety_track_variant_svg(layout, EXPECTED_VP_VALUES, variant)
        for variant in (three_four, two)
    ]

    assert three_four["token_rows"] == 2
    assert two["token_rows"] == 1
    assert svgs[0].count("<circle") == 4
    assert svgs[1].count("<circle") == 2
    assert "#2E86C1" not in svgs[1]  # blue token only exists on the second row


def test_generator_default_output_is_generated_piety_tracks_page() -> None:
    assert default_output_path() == UI_DEBUG_DIR / "generated" / "piety_tracks.html"


def test_generator_writes_generated_page(tmp_path: Path) -> None:
    output_path = tmp_path / "generated" / "piety_tracks.html"
    written = generate_piety_track_page(output_path=output_path)

    assert written == output_path
    assert output_path.is_file()
    content = output_path.read_text(encoding="utf-8")
    assert "<svg" in content
    assert TITLE in content
    assert "3-4 player" in content
    assert "2 player" in content


def test_baseline_prototype_and_source_are_untouched() -> None:
    assert BASELINE_PROTOTYPE.is_file()
    content = BASELINE_PROTOTYPE.read_text(encoding="utf-8")
    assert "Pilgrim — Piety Tracks" in content
    assert TITLE in content
    assert "Top: 3-4 player track. Bottom: 2 player track." in content

    assert BASELINE_SOURCE.is_file()
    source = BASELINE_SOURCE.read_text(encoding="utf-8")
    assert "Horizontal 12-square score/progress track" in source
    assert "render_fused" in source


def test_generated_page_matches_baseline_facts(tmp_path: Path) -> None:
    """Parity check against the baseline: same title, variants, VP labels, colours, and SVG."""
    generated = generate_piety_track_page(output_path=tmp_path / "piety_tracks.html")
    baseline_text = BASELINE_PROTOTYPE.read_text(encoding="utf-8")
    generated_text = generated.read_text(encoding="utf-8")

    for text in (TITLE, "3-4 player", "2 player", *KEY_COLORS):
        assert text in baseline_text
        assert text in generated_text
    for vp in EXPECTED_VP_VALUES:
        assert f">{vp}<" in baseline_text
        assert f">{vp}<" in generated_text

    assert _svg_bodies(generated) == _svg_bodies(BASELINE_PROTOTYPE)
