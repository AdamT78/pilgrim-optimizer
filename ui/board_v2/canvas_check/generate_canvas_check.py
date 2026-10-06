#!/usr/bin/env python3
"""How much screen is left beside the board_v2 module, at each of the three canvases.

    python3 ui/board_v2/canvas_check/generate_canvas_check.py --open

A measuring instrument, not a view of the game, and a much smaller one than
tools/ui_debug/generate_wheel_space_check.py -- which measures what the WHEEL gets once the
player boards and everything else have taken their share. This asks the opposite question. The
board_v2 module is a settled 1400 x 1200 composition; drop it into a canvas, push it flush right,
and see what is left on the left for player boards and the rest.

Keys 1, 2 and 3 switch canvas, exactly as they do on the v1 space check, and for the same three.

WHAT IS REAL HERE AND WHAT IS A BOX

The duty wheel is the real drawing: the same vendored SVG the action board inlines, through its
own wheel_svg(), at the position and size geometry.py gives it. Everything else -- the status
line, the eight duty tiles, the two action artworks, the three controls, Tithe and the City -- is a
correctly sized labelled box. That is the same bargain tools/ui_debug/generate_wheel_space_check.py strikes,
and for the same reason: the question is how much room is left over, and art inside the module
cannot change the answer.

NOTHING IS RETYPED

Every number on the page comes from somewhere that already owned it. The module's size and the
position of each object come from ui/board_v2/action_board/geometry.py, reached through the
action board's own handle on it, so this page shows the board that actually ships rather than a
second opinion about it. The three canvases come from
ui/render/gen_game_view.py through geometry(), heights included, which is the route
generate_wheel_space_check_v3.py takes -- so if a canvas ever stops being 1200 tall this page
follows without being edited, and the page says so rather than cropping quietly.

IT USED TO READ THE LAYOUT LAB'S default_state(). That was right while the lab was where the
composition was decided, and wrong once the action board became the thing that ships: the lab can
be dragged about, and a measuring instrument reporting a draggable layout measures nothing in
particular. geometry.py owns these numbers and refuses to be nudged, which is exactly the property
this page needs. The objects differ accordingly -- a ribbon of eight tiles and a controls column
where the lab had eight cards and neither.

There is deliberately no fallback if either import fails. A page that silently drew hard-coded
canvases would be worth less than no page: it would keep agreeing with itself while the numbers
it is supposed to be reporting moved underneath it.

THE FREE STRIP IS EMPTY ON PURPOSE

It is drawn as a dashed hole with its size called out and nothing inside. Sketching a player board
in there would answer a question that was not asked, and would make a claim about fit that this
file has no business making -- the board geometry lives in ui/render, and the moment it is drawn
here the two can disagree.
"""
from __future__ import annotations

import argparse
import html
import importlib.util
import json
import pathlib
import sys
import webbrowser

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BOARD_GEN = HERE.parent / "action_board" / "generate_action_board.py"
TMPL = HERE / "canvas_check.html.tmpl"
OUT = HERE / "generated" / "canvas_check.html"

BUILD_VERSION = "1.0"


def _load(path: pathlib.Path, name: str):
    """Import a generator by path, the way the lab's own tests do.

    By path rather than by package, because ui/ is not an importable package and adding one
    would be a change to the tree for this file's convenience.
    """
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:          # pragma: no cover - unreachable in practice
        raise SystemExit("could not load %s" % path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def board():
    """The action board generator, which is how this page reaches geometry.py.

    Through the generator rather than importing geometry.py directly, because the generator is
    what inlines and recolours the wheel -- taking the numbers from one module and the drawing
    from another would be two imports where the board itself manages with one. Its `G` is that
    geometry module, and geometry.py remains the sole owner of every figure below.

    The import is cheap: generate_action_board pulls in Pillow only inside the functions that
    resize art, none of which this page calls, so loading it here costs no more than the lab did.
    """
    if not BOARD_GEN.is_file():
        raise SystemExit("the action board generator is not at %s -- this page draws the module "
                         "from its geometry and has nothing to draw without it" % BOARD_GEN)
    return _load(BOARD_GEN, "_canvas_check_board")


def canvases() -> list[dict]:
    """The three canvases, with their heights read back rather than assumed.

    LOUD ON FAILURE. ui/render/gen_game_view.py owns these numbers; if it cannot be imported the
    honest outcome is no page, not a page carrying three integers copied here months ago.
    """
    sys.path.insert(0, str(ROOT))
    try:
        import ui.render.gen_game_view as gv          # noqa: PLC0415 - deliberately late
    except Exception as exc:                          # noqa: BLE001 - the message is the point
        raise SystemExit(
            "cannot import ui/render/gen_game_view.py, which owns the canvas sizes: %s\n"
            "Nothing is hard-coded here on purpose, so there is no page to write without it."
            % exc)
    out = []
    for width in (1600, 2039, 2283):
        d = dict(gv.DEFAULTS)
        d["canvas_width"] = width
        gv.geometry(d)
        height = d.get("canvas_height")
        if not height:
            raise SystemExit("canvas %d came back from geometry() with no height" % width)
        out.append({"w": int(width), "h": int(round(height))})
    return out


def module_html(m) -> str:
    """The module, drawn once at 1400 x 1200 in its own coordinates.

    Straight off geometry.py's constants. There is no state to read: the action board composes
    one board and only one, which is the whole reason it replaced the lab as this page's source.
    Every rect below is an expression in G, never a literal, so a tile that changes width here
    changes because the board changed.
    """
    G = m.G
    parts = []

    def box(x, y, w, h, label, cls="box"):
        parts.append(
            '<div class=%s style="left:%dpx;top:%dpx;width:%dpx;height:%dpx"><i>%s</i></div>'
            % (cls, round(x), round(y), round(w), round(h), html.escape(label)))

    # ASKED ONCE. Everything below that is not a bare constant comes out of here, so the page and
    # the board cannot disagree about a rect without geometry.py itself disagreeing with it.
    rects = G.as_dict()

    # THE BACKDROP FIRST, because it is the one object here that other objects stand in front of.
    # Drawn before them so the page's own stacking puts it behind, the same order the board uses.
    bd = rects["backdrop"]
    box(bd["x"], bd["y"], bd["width"], bd["height"], "backdrop")

    st = G.STATUS
    box(st["x"], st["y"], st["width"], st["height"], "status")

    # THE RIBBON. Eight tiles on one pitch, in G.DUTIES' order and under G.DUTIES' names -- the
    # same tuple the board itself loops over, so the strip here reads left to right exactly as
    # the board does. The lab called these cards and let them be hidden; a tile is not optional.
    for i, (_slug, name, _deg) in enumerate(G.DUTIES):
        box(G.X0 + i * G.TILE_PITCH, G.RIBBON_Y, G.TILE_W, G.RIBBON_H, name)

    # THE ROAD, between the ribbon and the action row. Reserved for the Merchant and empty on
    # purpose, so what this page has to show about it is that it is there and how much room it
    # takes -- which is the one question this page exists to answer.
    rd = G.ROAD
    box(rd["x"], rd["y"], rd["width"], rd["height"], "road")

    # The action row.
    #
    # ASKED FOR RATHER THAN REBUILT. These two were `G.X0` and `G.X0 + ART_W + ART_GAP`, which was
    # the same arithmetic art_slots() does and stopped being true the moment the row moved off the
    # margin and onto the first tile's centre. The page went on drawing them at the old x without
    # failing anything, because a box in the wrong place still renders.
    for key, label in (("actionA", "action art L"), ("actionB", "action art R")):
        r = G.art_slots()[key]
        box(r["x"], r["y"], r["width"], r["height"], label)

    # THE CONTROLS COLUMN, at the end of the same row. Three marks where there used to be a confirm
    # row under the cards and two standing buttons in the side column -- so this page now shows one
    # object where it showed five, which is the point of the change and the thing it has to show.
    #
    # DRAWN AT mark_slots() AND NOT AT A STACK REBUILT HERE, for the same reason the two art boxes
    # are: the arithmetic is one line and that is exactly what makes retyping it tempting and
    # invisible when it rots. MARKS_ORDER gives the order, so a fourth mark appears here by itself.
    marks = rects["marks"]
    for name in marks["order"]:
        r = marks[name]
        box(r["x"], r["y"], r["width"], r["height"], "mark %s" % name)

    # THE RIGHT-HAND COLUMN: Tithe beside the art, and the City below. Taken from as_dict() rather
    # than listed by hand -- the first version of this page WAS a hand-written list and it silently
    # lost Show Map and Hire Building, which is precisely what a hand-written list of someone
    # else's objects does. Those two are marks now, drawn just above.
    for key, label in (("tithe", "tithe"), ("city", "city")):
        r = rects[key]
        box(r["x"], r["y"], r["width"], r["height"], label)

    # THE ONE REAL DRAWING. The board's own wheel_svg() -- same asset, same recolour, at the rect
    # geometry gives it -- so this is the wheel at the size the module actually grants it.
    parts.append('<div class=wheel style="left:%dpx;top:%dpx;width:%dpx;height:%dpx">%s</div>'
                 % (round(G.WHEEL_X), round(G.WHEEL_Y), round(G.WHEEL_W), round(G.WHEEL_H),
                    m.wheel_svg()))
    return "\n".join(parts)


def build() -> str:
    m = board()
    cans = canvases()
    page = TMPL.read_text(encoding="utf-8")
    for token, value in (
        ("__CANVASES__", json.dumps(cans)),
        ("__MODULE_W__", str(m.G.CANVAS_W)),
        ("__MODULE_H__", str(m.G.CANVAS_H)),
        ("__MODULE__", module_html(m)),
        ("__BUILD__", BUILD_VERSION),
    ):
        if token not in page:
            raise SystemExit("the template no longer has %s in it" % token)
        page = page.replace(token, value)
    left = [t for t in ("__CANVASES__", "__MODULE_W__", "__MODULE_H__", "__MODULE__", "__BUILD__")
            if t in page]
    if left:
        raise SystemExit("tokens left unfilled: %s" % left)
    return page


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None,
                    help="where to write the page (default: %s)" % OUT.relative_to(ROOT))
    ap.add_argument("--open", action="store_true", help="open the page when it is written")
    args = ap.parse_args(argv)

    page = build()
    out = pathlib.Path(args.out) if args.out else OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")

    cans = canvases()
    try:
        shown = out.relative_to(ROOT)
    except ValueError:
        shown = out
    print("wrote %s  (%d KB)" % (shown, len(page.encode("utf-8")) // 1024))
    mod = board()
    for i, c in enumerate(cans, 1):
        gap = c["w"] - mod.G.CANVAS_W
        print("  %d  canvas %4d x %d   free to the left %4d x %d  (%.1f%%)"
              % (i, c["w"], c["h"], max(0, gap), c["h"], 100 * max(0, gap) / c["w"]))
    print("  press 1, 2 and 3 in the page to switch; h hides the chrome")
    if args.open:
        webbrowser.open(out.resolve().as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
