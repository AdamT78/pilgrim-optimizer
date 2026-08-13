import ast
import re
from pathlib import Path

import pytest

from tools.ui_debug import render_seal as seal_module
from tools.ui_debug.generate_seal_prototypes import (
    default_output_path,
    generate_seal_prototypes_page,
)
from tools.ui_debug.render_seal import (
    GLYPH_BOX,
    RIM_STROKE_R,
    RING_R,
    RING_STROKE_R,
    SEAL_R,
    WAX,
    WAX_DEEP,
    WAX_RIM,
    WOBBLE,
    check_clearance,
    render_seal,
)
from tools.ui_debug.render_seal_prototypes import (
    BACKGROUNDS,
    GLYPH,
    GLYPHS,
    HEX_GREEN,
    KEY,
    PAGE_BLACK,
    PARCHMENT,
    SEAL_PX,
    TREATMENTS,
    g_square,
    render_seal_prototypes_html,
    seal,
    svg,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
UI_DEBUG_DIR = REPO_ROOT / "tools" / "ui_debug"
SEAL_MODULE = UI_DEBUG_DIR / "render_seal.py"
PROTOTYPES_MODULE = UI_DEBUG_DIR / "render_seal_prototypes.py"
COMMITTED_PAGE = UI_DEBUG_DIR / "prototypes" / "seal_prototypes.html"

GLYPH_NAMES = ["square", "shield", "S", "A"]


def _polygon_points(drawn: str) -> list[str]:
    match = re.search(r'<polygon points="([^"]*)"', drawn)
    assert match is not None
    return match.group(1).split(" ")


def _imports_the_seal(module: Path) -> bool:
    """Matched on the import rather than the filename, which `render_seal_prototypes` shadows."""
    tree = ast.parse(module.read_text(encoding="utf-8"))
    return any(
        isinstance(node, ast.ImportFrom) and node.module == "tools.ui_debug.render_seal"
        for node in ast.walk(tree)
    )


def _imports_of(module: Path) -> set[str]:
    tree = ast.parse(module.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
        elif isinstance(node, ast.Import):
            imported.update(name.name.split(".")[0] for name in node.names)
    return imported


def test_the_page_the_repo_ships_is_the_page_this_generator_writes(tmp_path: Path) -> None:
    """Byte for byte, which is a stronger claim than the other renderers here are held to.

    They are judged against a baseline someone drew by hand, so the most that can be asked is that
    they agree about the drawing. This page had no such baseline: it came off this code, so the
    committed file is output rather than reference, and anything short of exact equality would mean
    the file in the repo is not the file the code makes.
    """
    written = generate_seal_prototypes_page(output_path=tmp_path / "seal_prototypes.html")

    assert written.read_bytes() == COMMITTED_PAGE.read_bytes()


def test_the_tuning_constants_are_the_ones_the_artwork_was_agreed_at() -> None:
    """Pinned by name and by value, because they are what the page is a review of.

    Nothing reads them from a file and nothing computes them, so the only record of what was agreed
    is the numbers themselves; a change here should have to be made twice on purpose.
    """
    assert SEAL_R == 20.0
    assert RING_R == 0.78
    assert GLYPH_BOX == 18.0
    assert WOBBLE == (0.045, 0.026)
    assert SEAL_PX == 96


def test_the_glyph_is_measured_to_its_corner_and_left_clear_of_the_ring() -> None:
    """A square's corners reach further than its side, and the corners are what meet the ring."""
    corner, ring, clear = check_clearance()

    assert corner == pytest.approx(GLYPH_BOX / 2 * 2**0.5)
    assert ring == pytest.approx(SEAL_R * RING_R)
    assert clear == pytest.approx(ring - corner)
    # 12.73 inside 15.60, leaving about three units of bare wax between glyph and ring.
    assert (round(corner, 2), round(ring, 2), round(clear, 2)) == (12.73, 15.60, 2.87)


def test_a_glyph_too_big_for_the_ring_stops_the_render_rather_than_spoiling_it() -> None:
    """The assertion is load-bearing, so this is the test that it still fires at runtime.

    `GLYPH_BOX = 23` is the version this was written against: its corners reach 16.26 and cross a
    ring sitting at 15.60. That is not an error any later step notices — it renders perfectly well
    and merely looks wrong — so the failure has to happen here or not at all. No page comes out.
    """
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(seal_module, "GLYPH_BOX", 23.0)

        with pytest.raises(AssertionError) as raised:
            check_clearance()
        assert "16.26" in str(raised.value)
        assert "15.60" in str(raised.value)

        with pytest.raises(AssertionError):
            render_seal_prototypes_html()


def test_the_page_is_written_only_after_the_clearance_is_checked(tmp_path: Path) -> None:
    """So a seal that fails the check cannot reach the disk, even part-written."""
    destination = tmp_path / "seal_prototypes.html"

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(seal_module, "GLYPH_BOX", 23.0)
        with pytest.raises(AssertionError):
            generate_seal_prototypes_page(output_path=destination)

    assert not destination.exists()


def test_four_glyphs_are_drawn_and_none_of_them_is_keylined() -> None:
    assert [name for name, _ in GLYPHS] == GLYPH_NAMES
    assert TREATMENTS == [False]

    page = render_seal_prototypes_html()
    assert re.findall(r"<figcaption>([^<]*)</figcaption>", page) == GLYPH_NAMES
    assert page.count("<svg") == len(GLYPH_NAMES)
    assert KEY not in page


def test_the_keyline_is_still_wired_up_though_this_page_asks_for_none() -> None:
    """Kept switchable rather than deleted: it is a variant to compare, not code left behind.

    Two reds at a small size may still need a light line between them, and the way to find out is
    to turn `TREATMENTS` back on and look. That is one line only while the path below still works.
    """
    keylined = seal(g_square, keyline=True)
    plain = seal(g_square, keyline=False)

    assert KEY in keylined
    assert KEY not in plain
    assert 'stroke-width="1.9"' in keylined


def test_the_grounds_this_page_does_not_stand_the_seals_on_are_still_named() -> None:
    """Same reason as the keyline: adding the green or the page black back is one row here."""
    assert [title for title, _, _ in BACKGROUNDS] == ["On the tile parchment"]
    assert BACKGROUNDS[0][1] == PARCHMENT
    assert (HEX_GREEN, PAGE_BLACK) == ("#8FBF6B", "#000000")

    page = render_seal_prototypes_html()
    assert page.count(f"background:{PARCHMENT}") == len(GLYPH_NAMES)
    assert HEX_GREEN not in page


def test_a_seal_is_wax_then_ring_then_glyph_about_the_origin() -> None:
    """Drawn around nothing in particular so it can later be dropped onto a tile at any point."""
    drawn = seal(g_square)

    assert drawn.startswith("<polygon")
    assert drawn.index(WAX) < drawn.index(WAX_DEEP) < drawn.index(GLYPH)
    assert f'r="{SEAL_R * RING_R:.2f}"' in drawn
    assert '<circle cx="0" cy="0"' in drawn


def test_the_seal_can_be_struck_at_a_point_rather_than_only_about_the_origin() -> None:
    """Which is the whole of what the extraction changed, and what the next panel needs.

    Wax and ring move together: a seal that placed its blob and left its impression behind would be
    a seal in two halves, so the ring is asked for at the same centre rather than assumed at 0,0.
    """
    here = render_seal(0, 0, SEAL_R)
    there = render_seal(140, 62, SEAL_R)

    assert '<circle cx="140" cy="62"' in there
    assert '<circle cx="0" cy="0"' in here
    moved = [
        (round(float(x) - 140, 2), round(float(y) - 62, 2))
        for x, y in (point.split(",") for point in _polygon_points(there))
    ]
    assert moved == [(float(x), float(y)) for x, y in (p.split(",") for p in _polygon_points(here))]


def test_the_two_lines_on_a_seal_thicken_with_it_and_the_ring_keeps_its_share() -> None:
    """A seal struck smaller should be the same drawing, not the same drawing under a heavier pen.

    The ratios are chosen to land on the widths the seal has always been drawn with, so at the
    agreed radius they must still emit those exact literals -- `2`, not `2.00`, which would be the
    same width and a different file.
    """
    at_agreed = render_seal(0, 0, SEAL_R)
    assert 'stroke-width="2"' in at_agreed
    assert 'stroke-width="1.6"' in at_agreed
    assert f'r="{SEAL_R * RING_R:.2f}"' in at_agreed

    halved = render_seal(0, 0, SEAL_R / 2)
    assert f'stroke-width="{SEAL_R / 2 * RIM_STROKE_R:g}"' in halved
    assert f'stroke-width="{SEAL_R / 2 * RING_STROKE_R:g}"' in halved
    assert f'r="{SEAL_R / 2 * RING_R:.2f}"' in halved


def test_the_wobble_is_what_stops_the_wax_reading_as_a_circle() -> None:
    """Twenty-six points off a modulated radius: never round, never the same shape twice over."""
    points = _polygon_points(render_seal(0, 0, SEAL_R))
    radii = {
        round((float(x) ** 2 + float(y) ** 2) ** 0.5, 2)
        for x, y in (point.split(",") for point in points)
    }

    assert len(points) == 26
    assert len(radii) > 1
    assert min(radii) > SEAL_R * RING_R  # the wax never dips inside its own impression ring
    assert max(radii) < SEAL_R * (1 + sum(WOBBLE))


def test_the_prototype_strikes_the_shared_seal_at_the_size_it_was_agreed_at() -> None:
    """The page is one caller of the seal now, not the place the seal lives."""
    assert seal(g_square).startswith(render_seal(0, 0, SEAL_R))
    assert WAX_RIM in render_seal(0, 0, SEAL_R)


def test_nothing_in_the_shared_module_sits_there_without_a_caller() -> None:
    """It was split out to be used from more than one place, so nothing in it may be used from none.

    Which modules count as callers is read off their imports rather than listed here, so the Piety
    Track picking the seal up is something this notices by itself. What it will not let through is a
    function added to the shared module ahead of the code that was supposed to call it.
    """
    callers = [
        module
        for module in sorted(UI_DEBUG_DIR.glob("*.py"))
        if module != SEAL_MODULE and _imports_the_seal(module)
    ]
    assert callers, "the shared seal module is not imported by anything"

    calling_source = "\n".join(module.read_text(encoding="utf-8") for module in callers)
    for node in ast.parse(SEAL_MODULE.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            assert node.name in calling_source, node.name


def test_the_seal_is_vector_at_whatever_size_it_is_asked_for() -> None:
    """The pixel figure sets the box, not the drawing, so a later size is exact, not resampled."""
    small = svg(g_square, False, 24)
    large = svg(g_square, False, 512)
    box = re.compile(r'viewBox="([^"]*)"')

    assert 'width="24" height="24"' in small
    assert 'width="512" height="512"' in large
    assert box.search(small).group(1) == box.search(large).group(1)


def test_the_geometry_is_printed_on_the_page_beside_the_seals() -> None:
    """Which is what makes it a debug view rather than four pictures."""
    corner, ring, clear = check_clearance()
    page = render_seal_prototypes_html()

    assert f"<b>{ring:.2f}</b>" in page
    assert f"<b>{corner:.2f}</b>" in page
    assert f"<b>{clear:.2f}</b>" in page
    for colour in (WAX, GLYPH, WAX_DEEP):
        assert f"<code>{colour}</code>" in page


def test_the_renderer_reads_nothing_and_so_cannot_disagree_with_anything() -> None:
    """Self-contained on purpose: the seal can be tuned here without the duty wheel around it.

    It is the only renderer here with no layout JSON, which is why there is no parity check between
    data and drawing to be had — there is only the drawing.
    """
    for module in (SEAL_MODULE, PROTOTYPES_MODULE):
        source = module.read_text(encoding="utf-8")
        assert "import json" not in source, module.name
        assert "open(" not in source, module.name
        assert "read_text" not in source, module.name

    assert render_seal_prototypes_html() == render_seal_prototypes_html()


def test_the_generator_writes_the_committed_page_by_default() -> None:
    """The one generator here pointed at `prototypes/` rather than the git-ignored `generated/`."""
    assert default_output_path() == COMMITTED_PAGE


def test_the_generator_writes_where_it_is_told_and_makes_the_way_there(tmp_path: Path) -> None:
    destination = tmp_path / "generated" / "seal_prototypes.html"
    written = generate_seal_prototypes_page(output_path=destination)

    assert written == destination
    assert destination.is_file()
    assert destination.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")


def test_the_seals_know_nothing_about_the_game_they_will_be_struck_in() -> None:
    """A seal is a mark drawn on a tile, not a rule about the tile.

    Read off the imports rather than the text, so the docstrings stay free to talk about the game
    the drawing is for without the test mistaking the mention for a dependency.
    """
    assert _imports_of(SEAL_MODULE) == {"__future__", "math"}
    # The page reaches for the wax and nothing else; the drawing is all in the standard library.
    assert _imports_of(PROTOTYPES_MODULE) == {"__future__", "collections", "tools"}
