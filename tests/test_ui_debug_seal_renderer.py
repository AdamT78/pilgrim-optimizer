import ast
import re
from pathlib import Path

import pytest

from tools.ui_debug import render_seal_prototypes
from tools.ui_debug.generate_seal_prototypes import (
    default_output_path,
    generate_seal_prototypes_page,
)
from tools.ui_debug.render_seal_prototypes import (
    BACKGROUNDS,
    GLYPH,
    GLYPH_BOX,
    GLYPHS,
    HEX_GREEN,
    KEY,
    PAGE_BLACK,
    PARCHMENT,
    RING_R,
    SEAL_PX,
    SEAL_R,
    TREATMENTS,
    WAX,
    WAX_DEEP,
    WOBBLE,
    check_clearance,
    g_square,
    render_seal_prototypes_html,
    seal,
    svg,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
UI_DEBUG_DIR = REPO_ROOT / "tools" / "ui_debug"
COMMITTED_PAGE = UI_DEBUG_DIR / "prototypes" / "seal_prototypes.html"

GLYPH_NAMES = ["square", "shield", "S", "A"]


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
        patch.setattr(render_seal_prototypes, "GLYPH_BOX", 23.0)

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
        patch.setattr(render_seal_prototypes, "GLYPH_BOX", 23.0)
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
    source = (UI_DEBUG_DIR / "render_seal_prototypes.py").read_text(encoding="utf-8")

    assert "import json" not in source
    assert "open(" not in source
    assert "read_text" not in source
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
    tree = ast.parse((UI_DEBUG_DIR / "render_seal_prototypes.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
        elif isinstance(node, ast.Import):
            imported.update(name.name.split(".")[0] for name in node.names)

    assert imported == {"__future__", "math", "collections"}
