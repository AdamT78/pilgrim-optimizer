import json
import re
from pathlib import Path

from tools.ui_debug.generate_duty_wheel import (
    default_output_path,
    generate_duty_wheel_page,
)
from tools.ui_debug.render_duty_wheel import (
    default_layout_path,
    duties_of,
    duty_position_by_id,
    load_duty_wheel_layout,
    render_duty_wheel_html,
    render_duty_wheel_svg,
    ring_duties,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
UI_DEBUG_DIR = REPO_ROOT / "tools" / "ui_debug"
LAYOUT_JSON = UI_DEBUG_DIR / "duty_wheel_layout.json"
PROTOTYPE_HTML = UI_DEBUG_DIR / "prototypes" / "duty_wheel.html"
PROTOTYPE_SVG = UI_DEBUG_DIR / "prototypes" / "duty_wheel.svg"
BUILD_SOURCE = UI_DEBUG_DIR / "prototype_sources" / "duty_wheel_build.py.txt"
RENDER_SOURCE = UI_DEBUG_DIR / "prototype_sources" / "duty_wheel_render.py.txt"

RING_DUTY_LABELS = (
    "Produce",
    "Allocation",
    "Clerical",
    "Build Roads",
    "Taxation",
    "Ordination",
    "Construct",
    "Give Alms",
)
PLAYER_FILLS = {
    "white": "#FFFFFF",
    "red": "#C94C4C",
    "yellow": "#E3C64A",
    "blue": "#3B6EA5",
}
MERCHANT_PURPLE = "#8E63D7"
ALLOWED_DRIFT = 0.1


def layout() -> dict:
    return load_duty_wheel_layout()


def generated_svg() -> str:
    return render_duty_wheel_svg(layout())


def baseline_svg() -> str:
    content = PROTOTYPE_SVG.read_text(encoding="utf-8")
    return content[content.index("<svg") :]


def drawing_elements(svg: str) -> list[tuple[str, tuple[float, ...]]]:
    """Every drawn element as its tag plus the numbers in its attributes, in document order."""
    flat = re.sub(r"\s+", " ", svg)
    return [
        (
            match.group(1),
            tuple(float(number) for number in re.findall(r"-?\d+\.?\d*", match.group(2))),
        )
        for match in re.finditer(r"<(path|rect|circle|line|ellipse|text)\b([^>]*)>", flat)
    ]


def test_duty_wheel_layout_exists_and_is_the_renderer_default() -> None:
    assert LAYOUT_JSON.is_file()
    assert default_layout_path() == LAYOUT_JSON
    assert json.loads(LAYOUT_JSON.read_text(encoding="utf-8")) == layout()


def test_layout_holds_nine_duty_positions_including_the_city() -> None:
    duties = duties_of(layout())

    assert len(duties) == 9
    assert {duty["id"] for duty in duties} == {
        "produce",
        "allocation",
        "clerical",
        "build_roads",
        "taxation",
        "ordination",
        "construct",
        "give_alms",
        "city",
    }
    for duty in duties:
        assert len(duty["center"]) == 2


def test_layout_labels_every_duty_and_the_city() -> None:
    data = layout()
    labels = [duty["label"] for duty in duties_of(data)]

    assert set(RING_DUTY_LABELS) <= set(labels)
    assert duty_position_by_id(data, data["city_id"])["label"] == "City"


def test_layout_orders_the_ring_clockwise_from_produce() -> None:
    data = layout()

    assert data["clockwise_order"][0] == "produce"
    assert [duty["label"] for duty in ring_duties(data)] == list(RING_DUTY_LABELS)
    assert data["city_id"] not in data["clockwise_order"]


def test_layout_describes_the_merchant_token() -> None:
    merchant = layout()["merchant_token"]

    assert merchant["label"] == "Merchant token"
    assert merchant["color"] == MERCHANT_PURPLE
    assert merchant["starts_on"] == "produce"
    assert merchant["skips"] == ["taxation"]


def test_layout_names_the_four_players_with_their_cube_colours() -> None:
    players = layout()["players"]

    assert [player["id"] for player in players] == ["white", "red", "yellow", "blue"]
    assert {player["id"]: player["fill"] for player in players} == PLAYER_FILLS


def test_layout_gives_every_ring_duty_a_tithe_icon_except_taxation() -> None:
    data = layout()
    icons = {duty["id"]: duty["tithe_icon"] for duty in ring_duties(data)}

    assert icons["taxation"] is None
    assert set(icons.values()) - {None} <= set(data["tithe_icons"])
    assert icons["clerical"] == "cornucopia"


def test_rendered_svg_is_an_svg_document() -> None:
    svg = generated_svg()

    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")
    assert 'data-component="duty-wheel"' in svg


def test_rendered_svg_names_the_city_every_duty_and_both_arrow_families() -> None:
    svg = generated_svg()

    assert ">City</text>" in svg
    for label in RING_DUTY_LABELS:
        assert f">{label}</text>" in svg
    assert 'aria-label="Clockwise outer arrows"' in svg
    assert 'aria-label="Middle directional arrows"' in svg


def test_rendered_svg_draws_nine_spaces_eight_ring_arrows_and_four_middle_arrows() -> None:
    svg = generated_svg()

    assert svg.count('class="board-circle"') == 9
    assert len(re.findall(r'data-ring-arrow="', svg)) == 8
    assert len(re.findall(r'data-middle-arrow="', svg)) == 4
    # Each arrow is drawn twice: a black outline with the white interior on top.
    assert svg.count('class="arrow-border"') == 12
    assert svg.count('class="arrow-interior"') == 12


def test_rendered_svg_carries_the_merchant_token_on_produce() -> None:
    svg = generated_svg()

    assert 'data-merchant-token="produce"' in svg
    assert MERCHANT_PURPLE in svg
    assert svg.count('data-token="merchant"') == 1


def test_rendered_svg_marks_the_tithe_token_icons() -> None:
    svg = generated_svg()

    assert 'data-tithe-token="coin"' in svg
    assert 'data-tithe-token="cornucopia"' in svg
    assert 'data-tithe-token="wheat"' in svg
    assert 'data-tithe-token="stone"' in svg
    # Taxation is the one duty with no capsule, which is also the one the Merchant will skip.
    assert 'data-duty="taxation"' in svg
    assert "taxation-tithe-shape" not in svg


def test_rendered_svg_tallies_cubes_in_every_player_colour() -> None:
    svg = generated_svg()

    for fill in PLAYER_FILLS.values():
        assert f'fill="{fill}"' in svg
    assert len(re.findall(r'data-cube-tally="', svg)) == 8


def test_rendered_html_wraps_the_board_and_explains_what_it_is_not() -> None:
    html = render_duty_wheel_html(layout())

    assert html.startswith("<!DOCTYPE html>")
    assert "<svg" in html
    assert "Duty Wheel" in html
    assert "Merchant token" in html
    assert "Tithe tokens" in html
    assert "no GameState" in html
    assert "<iframe" not in html


def test_generator_writes_the_page_to_a_temp_path(tmp_path: Path) -> None:
    written = generate_duty_wheel_page(output_path=tmp_path / "duty_wheel.html")

    assert written == tmp_path / "duty_wheel.html"
    assert written.is_file()
    assert "Produce" in written.read_text(encoding="utf-8")
    assert default_output_path() == UI_DEBUG_DIR / "generated" / "duty_wheel.html"


def test_generator_creates_a_missing_output_directory(tmp_path: Path) -> None:
    written = generate_duty_wheel_page(output_path=tmp_path / "generated" / "duty_wheel.html")

    assert written.is_file()


def test_generated_board_matches_the_baseline_element_for_element() -> None:
    """Coarse parity: the same shapes at the same coordinates, in the same order.

    The one tolerated gap is the Allocation title, which the baseline puts 0.1px above the offset
    its other eight titles share; the renderer uses the shared offset rather than reproducing that.
    """
    generated = drawing_elements(generated_svg())
    baseline = drawing_elements(baseline_svg())

    assert len(generated) == len(baseline)
    for mine, theirs in zip(generated, baseline, strict=True):
        assert mine[0] == theirs[0]
        assert len(mine[1]) == len(theirs[1])
        for value, expected in zip(mine[1], theirs[1], strict=True):
            assert abs(round(value - expected, 6)) <= ALLOWED_DRIFT


def test_generated_and_baseline_share_their_identifying_text() -> None:
    generated = generated_svg()
    baseline = baseline_svg()

    for fragment in (
        "City",
        "Produce",
        "Taxation",
        "Clockwise outer arrows",
        "Middle directional arrows",
        MERCHANT_PURPLE,
    ):
        assert fragment in generated
        assert fragment in baseline


def test_baseline_prototype_files_are_still_there_and_untouched() -> None:
    html = PROTOTYPE_HTML.read_text(encoding="utf-8")
    svg = PROTOTYPE_SVG.read_text(encoding="utf-8")

    for content in (html, svg):
        assert "PILGRIM" in content
        assert "City" in content
        assert "Produce" in content
        assert "Taxation" in content
    # The baseline knows nothing about the renderer's tagging.
    assert "data-component" not in html
    assert "data-duty" not in svg


def test_prototype_sources_are_still_reference_only_copies() -> None:
    assert "Build the Pilgrim board" in BUILD_SOURCE.read_text(encoding="utf-8")
    assert "Render pilgrim_board.html" in RENDER_SOURCE.read_text(encoding="utf-8")
