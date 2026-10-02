"""The canvas check must keep agreeing with the two files it borrows its numbers from.

It retypes nothing: the module's size and every object's position come from
ui/board_v2/action_board/geometry.py, reached through the action board generator, and the three
canvases come from ui/render/gen_game_view.py through geometry().
That is the whole value of it -- a page that quietly drew its own copies would go on agreeing
with itself while the layout moved underneath it -- and it is exactly the property that rots
without a guard, because the page still renders beautifully when its numbers are stale.

Neither import is heavy: gen_game_view pulls in no numpy, scipy, pillow or playwright, so this
belongs in the fast lane with the rest of the layout lab guards.
"""
import importlib.util
import json
import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
GEN = ROOT / "ui" / "board_v2" / "canvas_check" / "generate_canvas_check.py"
TMPL = ROOT / "ui" / "board_v2" / "canvas_check" / "canvas_check.html.tmpl"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def cc():
    return _load(GEN, "_cc_under_test")


@pytest.fixture(scope="module")
def page(cc):
    return cc.build()


def test_the_page_builds_with_every_token_filled(page):
    """A template token left in the output is a page that renders and lies."""
    assert page.lstrip().startswith("<!doctype html>")
    leftover = re.findall(r"__[A-Z_]+__", page)
    assert not leftover, "unfilled template tokens: %s" % sorted(set(leftover))


def test_the_canvases_are_the_ones_gen_game_view_gives(cc):
    """Read independently here and compared, rather than trusted.

    The heights matter as much as the widths: every canvas being 1200 tall is why the module
    fills the height and the leftover is a single vertical strip. If that ever changes this
    fails, which is the moment to look at the page again rather than after.
    """
    sys.path.insert(0, str(ROOT))
    import ui.render.gen_game_view as gv

    expected = []
    for width in (1600, 2039, 2283):
        d = dict(gv.DEFAULTS)
        d["canvas_width"] = width
        gv.geometry(d)
        expected.append({"w": width, "h": int(round(d["canvas_height"]))})
    assert cc.canvases() == expected


def test_the_canvases_reach_the_page_as_data(cc, page):
    """The page drives itself off this array; a mismatch would show wrong numbers in the bar."""
    m = re.search(r"var CANVASES = (\[.*?\]);", page)
    assert m, "the page no longer carries a CANVASES array"
    assert json.loads(m.group(1)) == cc.canvases()


def test_the_module_is_the_boards_module_and_every_object_is_drawn(cc, page):
    """Not just the size: every object geometry.py places has to appear.

    The failure this catches is a renamed or dropped constant -- G.CONFIRM_Y going away, say --
    which would drop a box from the picture without raising anything, leaving a page that looks
    finished and is missing a region.
    """
    b = cc.board()
    G = b.G
    # Matched on the assignment rather than on `var MODULE_W = ...`: the template declares both
    # on one line, so anchoring to `var` asserted the declaration style instead of the number.
    assert re.search(r"MODULE_W\s*=\s*%d\b" % G.CANVAS_W, page), "module width is not geometry's"
    assert re.search(r"MODULE_H\s*=\s*%d\b" % G.CANVAS_H, page), "module height is not geometry's"

    # All eight tiles, under the names G.DUTIES gives them and in its order.
    for _slug, name, _deg in G.DUTIES:
        assert ">%s<" % name in page, "%s has no tile on the page" % name
    for label in ("status", "action art L", "action art R", "confirm", "tithe", "city"):
        assert ">%s<" % label in page, "no box labelled %r" % label

    # THE RIBBON IS ON ONE PITCH, asserted rather than assumed: eight tiles evenly spaced is the
    # one thing a loop off G could get wrong while every individual number stayed right.
    for i, (_slug, _name, _deg) in enumerate(G.DUTIES):
        assert ('style="left:%dpx;top:%dpx;width:%dpx;height:%dpx"'
                % (G.X0 + i * G.TILE_PITCH, G.RIBBON_Y, G.TILE_W, G.RIBBON_H)) in page, (
            "tile %d is not at the board's own pitch" % i)

    # The one real drawing, at geometry's own rect.
    assert "<svg" in page, "the wheel SVG is not inlined"
    assert ('style="left:%dpx;top:%dpx;width:%dpx;height:%dpx"'
            % (G.WHEEL_X, G.WHEEL_Y, G.WHEEL_W, G.WHEEL_H)) in page


def test_every_rect_geometry_publishes_is_on_the_page(cc, page):
    """The guard that the hand-written list needed and did not have.

    The first version of this page listed its objects by hand and quietly lost two of them --
    Show Map and Hire Building -- which nothing failed on, because a box that is never drawn
    raises nothing and leaves a page that still looks finished. Reading them off as_dict() fixes
    that instance; this fixes the class, by asking geometry what it publishes rather than
    agreeing with whatever the generator happened to loop over.

    Top level only. The nested rects -- the City's four figures, the confirm bar's two halves --
    sit inside a box that is drawn, and drawing them would answer a question this page is not
    asking.
    """
    G = cc.board().G
    published = {k: v for k, v in G.as_dict().items()
                 if isinstance(v, dict) and {"x", "y", "width", "height"} <= set(v)}
    assert len(published) >= 6, (
        "geometry publishes only %d top-level rects, which is fewer than when this was written "
        "-- has one been renamed?" % len(published))
    missing = [k for k, r in published.items()
               if 'style="left:%dpx;top:%dpx;width:%dpx;height:%dpx"'
               % (r["x"], r["y"], r["width"], r["height"]) not in page]
    assert not missing, "geometry publishes these rects and the page does not draw them: %s" % missing


def test_the_module_fits_the_canvases_it_is_dropped_into(cc):
    """The arithmetic the page exists to show, asserted where it can be read.

    Height first: the page reports an overrun rather than cropping, but a module taller than
    every canvas would make the whole exercise meaningless and should fail here instead.
    """
    G = cc.board().G
    for c in cc.canvases():
        assert c["h"] >= G.CANVAS_H, (
            "canvas %d is %d tall and the module is %d -- the page would report an overrun"
            % (c["w"], c["h"], G.CANVAS_H))
        assert c["w"] >= G.CANVAS_W, (
            "canvas %d is narrower than the %d-wide module" % (c["w"], G.CANVAS_W))


def test_it_refuses_rather_than_inventing_a_canvas(cc, monkeypatch):
    """No fallback is the design: hard-coded canvases would be worse than no page.

    EXERCISED, not pattern-matched. The first version of this read the source for a `raise
    SystemExit` and a suspicious `except`, and a mutation that replaced the raise with
    `return [{"w": 1600, "h": 1200}]` sailed past it -- the phrase still appeared elsewhere in
    the file and the except clause was spelled differently than the regex expected. Breaking the
    import for real is both simpler and the thing actually being claimed.
    """
    monkeypatch.setitem(sys.modules, "ui.render.gen_game_view", None)
    with pytest.raises(SystemExit) as e:
        cc.canvases()
    assert "gen_game_view" in str(e.value), (
        "the refusal should name the file that owns these numbers")
