import re
from pathlib import Path

from tools.ui_debug.generate_map import default_output_path, generate_map_page
from tools.ui_debug.render_map import (
    TITLE,
    default_layout_path,
    generate_hexes,
    hex_label,
    label_to_coord,
    load_map_layout,
    render_map_svg,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
UI_DEBUG_DIR = REPO_ROOT / "tools" / "ui_debug"
LAYOUT_PATH = UI_DEBUG_DIR / "map_layout.json"
PROTOTYPES_DIR = UI_DEBUG_DIR / "prototypes"
BASELINE_PROTOTYPE = PROTOTYPES_DIR / "map.html"

EXPECTED_LABELS = ("B6", "C6", "G4", "G8", "L6", "F1", "G11")
HIDDEN_LABELS = ("F5", "F6", "F7", "G5", "G6", "G7", "H6")
RIVER_LABELS = ("C6", "D6", "E6", "I6", "J6", "K6")
TRACK_LABELS = ("G2", "G3", "G4", "G8", "F9", "G10")


def _svg_body(path: Path) -> str:
    match = re.search(r"(<svg\b.*?</svg>)", path.read_text(encoding="utf-8"), re.S)
    assert match is not None
    return match.group(1)


def test_map_layout_file_exists() -> None:
    assert LAYOUT_PATH.is_file()
    assert default_layout_path() == LAYOUT_PATH


def test_generated_hex_count_is_91() -> None:
    assert len(generate_hexes(load_map_layout())) == 91


def test_label_mapping_contains_expected_labels() -> None:
    coords = label_to_coord(load_map_layout())
    for label in EXPECTED_LABELS:
        assert label in coords


def test_label_function_keeps_prototype_orientation() -> None:
    """The previous extraction attempt drifted to A3/A4-style top labels."""
    layout = load_map_layout()
    hexes = {item["label"]: item for item in generate_hexes(layout)}

    topmost = min(hexes.values(), key=lambda item: item["cy"])
    bottommost = max(hexes.values(), key=lambda item: item["cy"])
    assert topmost["label"] == "B6"
    assert bottommost["label"] == "L6"
    assert hex_label(0, 0) == "G6"
    assert hexes["G1"]["cx"] < hexes["G6"]["cx"] < hexes["G11"]["cx"]


def test_hidden_labels_resolve_to_generated_labels() -> None:
    layout = load_map_layout()
    generated = {item["label"] for item in generate_hexes(layout)}
    hidden = {item["label"] for item in generate_hexes(layout) if item["hidden"]}

    for label in HIDDEN_LABELS:
        assert label in generated
    assert hidden == set(HIDDEN_LABELS)


def test_river_labels_resolve_to_generated_labels() -> None:
    layout = load_map_layout()
    coords = label_to_coord(layout)
    river_labels = [label for river in layout["rivers"] for label in river["hexes"]]

    assert river_labels == ["C6", "D6", "E6", "I6", "J6", "K6"]
    for label in RIVER_LABELS:
        assert label in coords


def test_track_labels_resolve_to_generated_labels() -> None:
    layout = load_map_layout()
    coords = label_to_coord(layout)
    track_labels = {segment["label"] for segment in layout["track_segments"]}
    track_labels |= {segment["label"] for segment in layout["curve_segments"]}

    assert track_labels == set(TRACK_LABELS)
    for label in TRACK_LABELS:
        assert label in coords


def test_render_map_svg_returns_svg_string() -> None:
    svg = render_map_svg(load_map_layout())
    assert isinstance(svg, str)
    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")


def test_rendered_svg_contains_key_labels() -> None:
    svg = render_map_svg(load_map_layout())
    for label in ("B6", "L6", "C6", "G4", "G8"):
        assert f">{label}</text>" in svg


def test_rendered_svg_hides_center_cluster_labels() -> None:
    svg = render_map_svg(load_map_layout())
    for label in HIDDEN_LABELS:
        assert f">{label}</text>" not in svg


def test_rendered_svg_uses_baseline_colors() -> None:
    svg = render_map_svg(load_map_layout())
    for color in ("#F5D94E", "#B9B9B4", "#8FBF6B", "#3E7CA6"):
        assert color in svg


def test_generator_default_output_is_generated_map_page() -> None:
    assert default_output_path() == UI_DEBUG_DIR / "generated" / "map.html"


def test_generator_writes_generated_map_page(tmp_path: Path) -> None:
    output_path = tmp_path / "generated" / "map.html"
    written = generate_map_page(output_path=output_path)

    assert written == output_path
    assert output_path.is_file()
    content = output_path.read_text(encoding="utf-8")
    assert "<svg" in content
    assert TITLE in content


def test_baseline_prototype_is_untouched() -> None:
    assert BASELINE_PROTOTYPE.is_file()
    assert "PILGRIM — Hex Grid" in BASELINE_PROTOTYPE.read_text(encoding="utf-8")


def test_generated_map_matches_coarse_baseline_facts(tmp_path: Path) -> None:
    """Coarse parity check against the baseline: same title, labels, and element counts."""
    generated = generate_map_page(output_path=tmp_path / "map.html")
    baseline_text = BASELINE_PROTOTYPE.read_text(encoding="utf-8")
    generated_text = generated.read_text(encoding="utf-8")

    assert TITLE in baseline_text
    assert TITLE in generated_text
    for label in ("B6", "L6"):
        assert label in baseline_text
        assert label in generated_text

    baseline_svg = _svg_body(BASELINE_PROTOTYPE)
    generated_svg = _svg_body(generated)
    for tag in ("path", "line", "text"):
        baseline_count = len(re.findall(rf"<{tag}\b", baseline_svg))
        generated_count = len(re.findall(rf"<{tag}\b", generated_svg))
        assert generated_count == baseline_count

    baseline_labels = sorted(re.findall(r"<text[^>]*>([^<]*)</text>", baseline_svg))
    generated_labels = sorted(re.findall(r"<text[^>]*>([^<]*)</text>", generated_svg))
    assert generated_labels == baseline_labels
