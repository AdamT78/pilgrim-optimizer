"""The canvas check must keep agreeing with the two files it borrows its numbers from.

It retypes nothing: the module's size and every object's position come from the layout lab's
default_state(), and the three canvases come from ui/render/gen_game_view.py through geometry().
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


def test_the_module_is_the_lab_module_and_every_object_is_drawn(cc, page):
    """Not just the size: each object the state says is visible has to appear.

    The failure this catches is a renamed state key -- `display.artLeft` moving, say -- which
    would drop a box from the picture without raising anything, leaving a page that looks
    finished and is missing a region.
    """
    lab = cc.lab()
    # Matched on the assignment rather than on `var MODULE_W = ...`: the template declares both
    # on one line, so anchoring to `var` asserted the declaration style instead of the number.
    assert re.search(r"MODULE_W\s*=\s*%d\b" % lab.CANVAS_W, page), "module width is not the lab's"
    assert re.search(r"MODULE_H\s*=\s*%d\b" % lab.CANVAS_H, page), "module height is not the lab's"

    S = lab.default_state()
    for duty in S["duties"].values():
        if duty["card"].get("visible", True):
            assert duty["name"] in page, "%s has no box on the page" % duty["name"]
    for label in ("status", "action art L", "action art R", "tithe", "city"):
        assert ">%s<" % label in page, "no box labelled %r" % label

    # The one real drawing, at the state's own rect.
    w = S["wheel"]
    assert "<svg" in page, "the wheel SVG is not inlined"
    assert ('style="left:%dpx;top:%dpx;width:%dpx;height:%dpx"'
            % (w["x"], w["y"], w["width"], w["height"])) in page


def test_the_module_fits_the_canvases_it_is_dropped_into(cc):
    """The arithmetic the page exists to show, asserted where it can be read.

    Height first: the page reports an overrun rather than cropping, but a module taller than
    every canvas would make the whole exercise meaningless and should fail here instead.
    """
    lab = cc.lab()
    for c in cc.canvases():
        assert c["h"] >= lab.CANVAS_H, (
            "canvas %d is %d tall and the module is %d -- the page would report an overrun"
            % (c["w"], c["h"], lab.CANVAS_H))
        assert c["w"] >= lab.CANVAS_W, (
            "canvas %d is narrower than the %d-wide module" % (c["w"], lab.CANVAS_W))


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
