"""How much room the duty wheel actually gets, with everything else at its true size.

    python3 tools/ui_debug/generate_wheel_space_check.py --open

A measuring instrument, not a view of the game. It draws the oval duty wheel where the game view
puts it, the four player boards beside it, and a plain box at the correct size for every other
component, then reports what each one measures in real device pixels on whatever screen the page
is opened on.

WHAT IS REAL HERE AND WHAT IS A BOX

The player boards are built the way gen_game_view builds them -- build_board() per seat, then
merge_defs() -- so they are the same artwork at the same 1905 x 826 aspect, sized from
geometry() rather than from anything chosen here. Special Activities is gen_game_view's own
special_placeholder(), which reports for itself whether the six-by-four cube table still fits the
panel it is given. The alms table, market, banner and action box are plain boxes: correct size,
no art.

THE SLIDER IS A REAL LEVER

It moves board_width, and geometry() is stamped for every width it can reach, so nothing here
re-implements the layout. Widen a board and the action box widens with it -- it is drawn as a
fraction of the board's width -- and the wheel gets what is left. The action-box button goes
further: turning it off drops the panel_w term out of wheel_room, which is the same formula
gen_game_view uses with one term removed rather than a number invented here.

The wheel is centred in its column and lifted so its own centre line -- which is the west face's
-- lands in the gap between the second and third player boards.

THE ASPECT IS NOT SETTLED

Two wheels are carried: duty_wheel_v2_layout.json at 1.778, and duty_wheel_v2_1500_layout.json
at 1.500. Both come out of build_duty_wheel_v2.py -- the second with
`--aspect 1.5 --out duty_wheel_v2_1500_layout.json` -- and a test rebuilds both and compares
bytes, so neither can drift from the constants that make it. Which aspect the game takes is a
separate question, and it does not pay for itself until the canvas moves with it.

The page it writes goes to generated/, which this folder already treats as local debug output:
git-ignored, rebuilt on demand, never committed. It is ~9 MB and carries the portrait art, which
is the other reason it is not committed.
"""
import argparse
import json
import pathlib
import re
import sys
import webbrowser

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "ui" / "render"))
import gen_game_view as gv                                          # noqa: E402

# Into generated/, which this folder already treats as local debug output: git-ignored,
# rebuilt on demand, never committed. NOT into ~/Downloads -- a python.org interpreter has no
# macOS TCC grant for that folder and write_text() fails with "Operation not permitted".
OUT = HERE / "generated" / "wheel_space_check.html"
WIDTHS = list(range(200, 505, 5))
CANVASES = (1600, 2039, 2283)
SHIP = 0.06315                                  # one shipped tile / the square wheel box

# The boards, exactly as gen_game_view builds them. Sizes are stripped off the roots because
# the page sets them per slider stop; merge_defs gives the one shared <defs> they all point into.
import xml.etree.ElementTree as ET                                  # noqa: E402

ASSETS = ROOT / "ui" / "assets-gothic"
asm = gv.load_assembler(ROOT / "ui" / "render" / "gen_board_gothic.py")
seats = list(asm.SEAT_COLORS)[:int(gv.DEFAULTS["seats"])]
roots = [gv.build_board(asm, ASSETS, ASSETS / "production_test_config.json",
                        s, "lit" if s == seats[0] else "dim") for s in seats]
defs, _unique, _saved = gv.merge_defs(asm, roots)
DEFS = ET.tostring(defs, encoding="unicode")
boards = []
for root in roots:
    root.attrib.pop("width", None)
    root.attrib.pop("height", None)
    boards.append(ET.tostring(root, encoding="unicode"))
assert len(boards) == 4, "expected four boards, found %d" % len(boards)

L, SA = {}, {}
for cw in CANVASES:
    for bw in WIDTHS:
        D = dict(gv.DEFAULTS)
        D["canvas_width"], D["board_width"] = cw, float(bw)
        G = gv.geometry(D)
        L["%d|%d" % (cw, bw)] = {
            "cw": cw, "ch": D["canvas_height"], "pad": G["pad"], "mt": D["margin_top"],
            "inner_w": G["inner_w"], "top_h": G["top_h"], "main_h": G["main_h"],
            "banner_h": G["banner_h"], "act_h": G["act_h"], "bw": G["bw"], "bh": G["bh"],
            "panel_w": G["panel_w"], "overhang": G["overhang"],
            "gap1": D["column_gap_1"], "gap2": D["column_gap_2"],
            "board_gap": D["board_gap"], "left_top": G["left_top"], "left_h": G["left_h"],
            "left_lift": G["left_lift"], "wheel_room": G["wheel_room"],
            "square_wheel": G["wheel"],
        }
        if bw not in SA:
            # THE REAL PLACEHOLDER, not a grey box of my own: gen_game_view draws this one and
            # it goes red when the six-by-four cube table stops fitting the panel it is given.
            # special_placeholder returns (markup, spec); the second is its own verdict text
            SA[bw] = gv.special_placeholder(
                G["panel_w"], G["top_h"], D["frame_border_y"], D["frame_border_x"])[0]

WH = {}
for a, name in ((1.5, "duty_wheel_v2_1500_layout.json"),
                (1.778, "duty_wheel_v2_layout.json")):
    d = json.loads((HERE / name).read_text(encoding="utf-8"))
    WH[str(a)] = {"box": d["box"], "box_h": d["box_h"],
                  "faces": [{"d": c["d"], "pos": c["position"],
                             "frac": c["area"] / (d["box"] * d["box_h"])} for c in d["cells"]]}

page = ((HERE / "wheel_space_check.html.tmpl").read_text(encoding="utf-8")
        .replace("__DEFS__", DEFS)
        .replace("__LAYOUTS__", json.dumps(L))
        .replace("__WHEELS__", json.dumps(WH))
        .replace("__BOARDS__", json.dumps(boards))
        .replace("__SA__", json.dumps({str(k): v for k, v in SA.items()}))
        .replace("__WIDTHS__", json.dumps(WIDTHS))
        .replace("__SHIP__", repr(SHIP)))
left = re.findall(r"__[A-Z_]+__", page)
assert not left, "placeholders left unsubstituted: %s" % sorted(set(left))

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("--out", default=None, help="where to write the page (default: beside this file)")
ap.add_argument("--open", action="store_true", help="open the page when it is written")
args = ap.parse_args()

OUT = pathlib.Path(args.out).expanduser() if args.out else OUT
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(page, encoding="utf-8")
print("wrote %s  (%.0f KB)" % (OUT, len(page) / 1024))
print("  %d layouts, %d SA placeholders, %d boards, defs %.1f MB"
      % (len(L), len(SA), len(boards), len(DEFS) / 1e6))
if args.open:
    webbrowser.open(OUT.resolve().as_uri())
