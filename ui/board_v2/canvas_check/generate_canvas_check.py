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

The duty wheel is the real drawing: the same vendored SVG the layout lab inlines, recoloured the
same way, at the position and size the module's own geometry gives it. Everything else -- the
status line, the eight duty cards, the two action artworks, Tithe and the City -- is a correctly
sized labelled box. That is the same bargain tools/ui_debug/generate_wheel_space_check.py strikes,
and for the same reason: the question is how much room is left over, and art inside the module
cannot change the answer.

NOTHING IS RETYPED

Every number on the page comes from somewhere that already owned it. The module's size and the
position of each object come from the layout lab's own default_state(), so composing a card
differently in the lab and re-running this reproduces it. The three canvases come from
ui/render/gen_game_view.py through geometry(), heights included, which is the route
generate_wheel_space_check_v3.py takes -- so if a canvas ever stops being 1200 tall this page
follows without being edited, and the page says so rather than cropping quietly.

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
LAB = HERE.parent / "layout_lab" / "generate_layout_lab.py"
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


def lab():
    if not LAB.is_file():
        raise SystemExit("the layout lab generator is not at %s -- this page draws the module "
                         "from its geometry and has nothing to draw without it" % LAB)
    return _load(LAB, "_canvas_check_lab")


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

    Read off default_state() rather than off the module-level constants wherever the state has an
    opinion: the state is what the lab actually composes, and the constants are only its starting
    point. Where they agree this is the same picture; where somebody has moved something in the
    lab and re-run, this follows.
    """
    S = m.default_state()
    parts = []

    def box(x, y, w, h, label):
        parts.append(
            '<div class=box style="left:%dpx;top:%dpx;width:%dpx;height:%dpx"><i>%s</i></div>'
            % (round(x), round(y), round(w), round(h), html.escape(label)))

    st = S["status"]
    box(st["x"], st["y"], st["width"], st["height"], "status")

    for slug, duty in S["duties"].items():
        card = duty["card"]
        if card.get("visible", True):
            box(card["x"], card["y"], card["width"], card["height"], duty.get("name", slug))

    # The action row. The two artwork slots live in display, the other two are top-level objects;
    # all four are the same band and are drawn the same way.
    for key, label in (("artLeft", "action art L"), ("artRight", "action art R")):
        a = S["display"][key]
        box(a["x"], a["y"], a["width"], a["height"], label)
    for key, label in (("tithe", "tithe"), ("city", "city")):
        o = S[key]
        if o.get("visible", True):
            box(o["x"], o["y"], o["width"], o["height"], label)

    # THE ONE REAL DRAWING. Same vendored SVG the lab inlines, same recolour, at the state's own
    # wheel rect -- so this is the wheel at the size the module actually gives it.
    w = S["wheel"]
    parts.append('<div class=wheel style="left:%dpx;top:%dpx;width:%dpx;height:%dpx">%s</div>'
                 % (round(w["x"]), round(w["y"]), round(w["width"]), round(w["height"]),
                    m.wheel_svg()))
    return "\n".join(parts)


def build() -> str:
    m = lab()
    cans = canvases()
    page = TMPL.read_text(encoding="utf-8")
    for token, value in (
        ("__CANVASES__", json.dumps(cans)),
        ("__MODULE_W__", str(m.CANVAS_W)),
        ("__MODULE_H__", str(m.CANVAS_H)),
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
    lab_mod = lab()
    for i, c in enumerate(cans, 1):
        gap = c["w"] - lab_mod.CANVAS_W
        print("  %d  canvas %4d x %d   free to the left %4d x %d  (%.1f%%)"
              % (i, c["w"], c["h"], max(0, gap), c["h"], 100 * max(0, gap) / c["w"]))
    print("  press 1, 2 and 3 in the page to switch; h hides the chrome")
    if args.open:
        webbrowser.open(out.resolve().as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
