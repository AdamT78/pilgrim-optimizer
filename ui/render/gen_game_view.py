"""The game view: the gothic boards, the duty grid, and the panels between them, on one ground.

    python3 ui/render/gen_game_view.py --open

WHY THIS IS A NEW FILE AND NOT A COPY OF gen_board.py

`gen_board.py` already draws a complete board, and the temptation was to copy it and edit. That
would fork 1,360 lines, and most of what you would copy is exactly what is being replaced -- the
circular wheel and the old card-style player boards -- so the first day's work would be deleting.
Worse, the two files would then drift: a fix made in one and not the other is the failure mode
every forked generator in this repo has eventually had.

So this file OWNS only what is new, and borrows everything that already works:

    the gothic player boards     here                    build_board + merge_defs
    the Special Activities hole  here                    special_placeholder
    the duty grid                import gen_duty_grid    duty_grid_svg
    the alms table, the market,  exec gen_board.py       module-level strings
    the action box, the log,
    the stylesheet, the text

Four of those five are ordinary imports. Only the last needs the exec, because those pieces are
module-level strings inside `gen_board.py` rather than functions -- and `gen_picker.py` already
lifts a card out of that file the same way, so this is a pattern the repo has rather than one
invented here. `gen_board.py` is not modified and keeps producing its own page unchanged.

THE EXEC WRITES A FILE, AND THAT HAS TO BE REDIRECTED

`gen_board.py` writes its page at module level, not under a `__main__` guard -- the guard only
suppresses the URL print. So exec'ing it rebuilds `board-3-2-step1.html` as a side effect. Left
alone that would make this generator quietly rebuild another generator's page every run, which is
the sort of thing that makes a rebuild sweep report changes nobody made. `OUTNAME` redirects it to
a scratch name, which is what that environment variable is for.

WHERE THE NUMBERS COME FROM

`ui/layout.json`, which the layout tool writes. That is the standing arrangement in this repo --
the tool edits the file and the build reads it, so moving a slider and changing the board are the
same act. This reads considerably more of it than the four-board page did, because this draws all
three columns rather than one.
"""

import argparse
import contextlib
import copy
import importlib.util
import io
import json
import os
import pathlib
import re
import sys
import xml.etree.ElementTree as ET

HERE = pathlib.Path(__file__).resolve().parent
UI = HERE.parent
REPO = UI.parent
sys.path.insert(0, str(HERE))

import gen_duty_grid as dg                                          # noqa: E402

# The player board's artwork runs 1905 units wide, and its gold frame -- the part that reads as the
# board rather than as overhang -- starts at 620 and ends at 1839. The panels beside the column are
# drawn to that inner width, not to the board's full width, or they sit visibly proud of it.
FRAME_START, FRAME_END = 620 / 1905, 1839 / 1905
MAP_ASPECT = 1014 / 1149          # the map's viewBox; taller than it is wide

DEFAULTS = {
    "canvas_width": 1600, "canvas_height": 1200,
    "board_width": 405.0, "board_gap": 30.0, "seats": 4,
    "special_height": 178.0,
    "frame_border_y": 0.1, "frame_border_x": 0.0,
    "width_whole_board": False,
    # One gap after the board column and one after the action box, and both rows take the same
    # pair: the same gap after a cell of the same width lands the next cell on the same vertical
    # line in both rows, without either row being told where the other one put anything.
    "column_gap_1": 30.0, "column_gap_2": 0.0,
    # `row_gap` is now ONLY the left column's gap under Special Activities. It used to also be the
    # gap between the top row and the main row on the right, and those two have parted company:
    # on the right that band is the info banner, which has its own height. One number could not be
    # both without a taller banner silently pushing the player boards down the page.
    "row_gap": 36.8,
    "banner_height": 88.0,
    "margin_top": 28.0, "margin_bottom": 28.0,
    "act_rule": 7.0,
    "wheel_slack_to_boxes": True,
}



# --------------------------------------------------------------------------------------------
# THE FOUR GOTHIC BOARDS, AND THE SPECIAL ACTIVITIES HOLE.
#
# These came from gen_board_2.py, which was a standalone page answering one question -- what do four
# gothic boards cost, and look like, where they will actually sit. This file answers it and more, so
# that page was deleted and the parts of it this file was already importing moved here rather than
# being left in a module nothing else used.
#
# Namespace registration and `q` come with them: merge_defs walks the assembler's own namespaced
# tree, so it needs the same names the assembler registers.
SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)


def q(tag):
    return f"{{{SVG_NS}}}{tag}"


# The game view's own numbers, read from the generator that owns them rather than copied -- with
# one deliberate exception. gen_board.py's canvas is 1600 x 1067, and the gothic boards do not fit
# that column: they stand 147.2 px against the current cards' 135, which is 48.8 px more over four
# seats, before a Special Activities panel is asked for at all.
#
# 1600 x 1200 is that column with room. The choice is an ASPECT, not a resolution: the stage is
# zoom-to-fit, so 1600 x 1200 and 3200 x 2400 are the same picture, and on every screen worth
# testing the height term wins the fit -- which is also why an ultrawide scores exactly the same as
# a 1440p monitor here, and why extra width buys nothing. A taller canvas buys column space by
# rendering everything smaller: 4:3 costs about 11% of apparent size against 3:2.
CANVAS_W, CANVAS_H = 1600, 1200
STAGE_PAD = 14
BOARD_GAP = 30
VB_W, VB_H = 1905.0, 826.0

# Measured from the current game view: the Special Activities panel is already the head of this
# column, at exactly the boards' width, and the log already sits at the column's foot with no slack.
SA_TODAY_H = 153.9
LOG_H = 210.7

# The Special Activities table's own geometry, from gen_board.py. Six activities are the columns and
# four seats the rows -- transposed that way deliberately, because a row-per-activity grid needs 194
# units and would not fit the column at all. These are what decide how big a hole the artwork has to
# leave: the table is 316 x 147.6 units inside a 352 x 159.6 canvas, which is about 90% x 92%
# full-bleed. Very little of a gothic frame can be border.
SA_VB_W, SA_VB_H = 352.0, 159.6
SA_W, SA_H = 316.0, 147.6
SA_ROW1, SA_PITCH, SA_CUBE, SA_CUBE_GAP = 82.0, 16.5, 11.96, 3.59
SA_ACTIVITIES, SA_SEATS = 6, 4

# The seat swatches, for the placeholder's cubes only -- this draws no real asset.
SA_SWATCH = ("#7d9b52", "#4a6b86", "#8a5a92", "#d8cfbe")

def special_placeholder(width, height, border_y, border_x=0.05):
    """The Special Activities panel as a hole, drawn before the artwork exists.

    The point of drawing this first is that the artwork cannot be judged on its own. A gothic frame
    for this panel is handsome or not, but what decides whether it is USABLE is whether the clear
    area inside it still holds a six-by-four table of cubes at a size anyone can see. So this draws
    the frame's footprint, the interior a given border allowance would leave, and the real table at
    its real size inside -- and says plainly whether the second fits the first.

    `border_y` is the fraction of the height spent on frame above and below, `border_x` the fraction
    of the width spent on it left and right. The first is the one to argue about: the gothic player
    board spends 26% of its height above its first opening, all arch and stonework, and at that
    allowance this table would need a panel nearly 300 px tall. The sides are cheaper -- that frame
    spends about 5% there -- but they are a control and not a constant, because a table 90% as wide
    as its canvas has very little to give either.
    """
    scale = width / SA_VB_W                    # px per table unit, at this render width
    table_w, table_h = SA_W * scale, SA_H * scale
    inner_x, inner_w = width * border_x, width * (1 - 2 * border_x)
    inner_y, inner_h = height * border_y, height * (1 - 2 * border_y)
    fits = table_w <= inner_w + 0.05 and table_h <= inner_h + 0.05

    ink = "#c9a227" if fits else "#d05a4a"
    o = ['<svg width="%.1f" height="%.1f" viewBox="0 0 %.1f %.1f" class="sa-placeholder">'
         % (width, height, width, height)]
    o.append('<rect x="0.5" y="0.5" width="%.1f" height="%.1f" rx="9" fill="#2a2c26" '
             'stroke="#6b6250" stroke-width="1"/>' % (width - 1, height - 1))
    o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#1d2a22" stroke="%s" '
             'stroke-width="1" stroke-dasharray="4 3"/>' % (inner_x, inner_y, inner_w, inner_h, ink))

    # The table itself, centred, at the size it actually needs.
    tx, ty = (width - table_w) / 2, (height - table_h) / 2
    o.append('<g transform="translate(%.2f %.2f) scale(%.4f)">' % (tx, ty, scale))
    o.append('<rect x="0" y="0" width="%.1f" height="%.1f" fill="none" stroke="%s" '
             'stroke-width="%.2f"/>' % (SA_W, SA_H, ink, 1 / scale))
    col_w = SA_W / SA_ACTIVITIES
    for c in range(SA_ACTIVITIES):
        cx = col_w * (c + 0.5)
        o.append('<circle cx="%.1f" cy="%.1f" r="8" fill="none" stroke="#8b8570" '
                 'stroke-width="%.2f"/>' % (cx, SA_ROW1 - 34, 1 / scale))
        for r in range(SA_SEATS):
            y = SA_ROW1 + r * SA_PITCH - SA_CUBE / 2
            if (c + r) % 3:                    # a sparse table, which is how it actually looks
                continue
            o.append('<rect x="%.1f" y="%.1f" width="%.2f" height="%.2f" fill="%s" stroke="#2A2320"'
                     ' stroke-width="%.2f"/>' % (cx - SA_CUBE / 2, y, SA_CUBE, SA_CUBE,
                                                 SA_SWATCH[r], 0.6))
    o.append("</g></svg>")

    spec = {
        "width": width, "height": height, "border": border_y, "border_x": border_x,
        "interior_px": (round(inner_w, 1), round(inner_h, 1)),
        "table_px": (round(table_w, 1), round(table_h, 1)),
        "cube_px": round(SA_CUBE * scale, 2),
        "fits": fits,
        "height_needed": round(table_h / (1 - 2 * border_y), 1),
        "width_needed": round(table_w / (1 - 2 * border_x), 1),
    }
    return "".join(o), spec

def load_assembler(path):
    spec = importlib.util.spec_from_file_location("assembler", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# A face per seat, so a column of four boards is four PLAYERS rather than one man four times.
#
# Not a rule about who sits where -- a real game deals these -- but a placeholder cast, and it lives
# here rather than in the layout tool because the tool exists to show what the build produces. A
# tool showing four faces against a build that draws one would be a mockup, which is the one thing
# it promises not to be. The fifth portrait is spare; there are five leaders and four seats.

SEAT_PORTRAITS = {
    "sage": "portraits/leader_male_shaven.png",
    "pewter": "portraits/leader_female_hooded.png",
    "plum": "portraits/leader_male_hooded.png",
    "bone": "portraits/leader_female_blindfolded.png",
}


def build_board(asm, assets_dir, config_path, seat, turn, portrait=None):
    """One complete board for one seat, exactly as the production assembler would write it."""
    config = copy.deepcopy(asm.read_json(config_path))
    for role in ("frame_base", "frame_ornaments", "cloth_lit", "cloth_dim", "gems"):
        config.pop(role, None)
    config["seat"] = seat
    config["turn"] = turn
    chosen = portrait or SEAT_PORTRAITS.get(seat)
    if chosen:
        config["portrait"] = chosen
    config["id"] = f"gothic-{seat}"
    config["aria_label"] = f"Pilgrim gothic player board, {seat} seat"
    asm.apply_seat(config)

    layout = asm.read_json(assets_dir / "metadata" / "layout.json")
    root = ET.parse(assets_dir / "template" / "player_board_template.svg").getroot()
    asm.apply_config(root, config, layout, assets_dir)
    asm.embed_assets_once(root, assets_dir)
    asm.assert_no_duplicated_payloads(root)
    return root

def merge_defs(asm, roots):
    """Lift every board's <defs> into one, collapsing assets that appear more than once.

    Symbols are matched on `data-source` and `preserveAspectRatio` -- the pair the assembler itself
    keys on -- so two boards drawing the same file at the same fit share one payload. Everything
    else in <defs> (clip paths, the gradient, the filter, the turn stylesheet) is identical for
    every board and is kept once, which also stops four copies of the same id going into one
    document where only the first would ever be used.
    """
    shared = ET.Element(q("defs"))
    by_source, by_id, tags_once = {}, set(), set()
    bytes_before = 0

    for root in roots:
        defs = root.find(q("defs"))
        root.remove(defs)
        bytes_before += len(ET.tostring(defs))
        remap = {}
        for node in list(defs):
            if node.tag == q("symbol"):
                key = (node.get("data-source"), node.get("preserveAspectRatio"))
                if key in by_source:
                    remap[node.get("id")] = by_source[key]
                    continue
                new_id = "sym-%d" % len(by_source)
                remap[node.get("id")] = new_id
                node.set("id", new_id)
                by_source[key] = new_id
                shared.append(node)
                continue
            node_id = node.get("id")
            if node_id:
                if node_id in by_id:
                    continue
                by_id.add(node_id)
            elif node.tag in tags_once:
                continue           # <style> and friends: one copy is document-wide anyway
            else:
                tags_once.add(node.tag)
            shared.append(node)

        for use in root.iter(q("use")):
            target = (use.get("href") or "")[1:]
            if target in remap:
                asm.set_href(use, "#" + remap[target])

    saved = bytes_before - len(ET.tostring(shared))
    return shared, len(by_source), saved

def borrow():
    """`gen_board.py`'s finished components, without running it as a program.

    Returns the exec namespace. `OUTNAME` sends its side-effect page write to a scratch file (see
    the module docstring); stdout is swallowed because it announces that write, and a generator
    that prints another generator's output line is a generator whose log cannot be trusted.
    """
    gen = HERE / "gen_board.py"
    if not gen.is_file():
        raise SystemExit(
            "gen_game_view.py borrows the alms table, the market, the action box and the log from "
            "%s, which is not in this checkout." % gen)
    env_before = os.environ.get("OUTNAME")
    os.environ["OUTNAME"] = "_gen_game_view_scratch.html"
    ns = {"__file__": str(gen), "__name__": "gen_board"}
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            exec(compile(gen.read_text(encoding="utf-8"), str(gen), "exec"), ns)
    finally:
        if env_before is None:
            os.environ.pop("OUTNAME", None)
        else:
            os.environ["OUTNAME"] = env_before
    missing = [k for k in ("CSS", "TURN", "LOG", "MARKET", "alms", "sa_panel", "DUTY_TEXT",
                           "INSPECT_JS_TMPL") if k not in ns]
    if missing:
        raise SystemExit(
            "gen_board.py no longer defines %s at module level, so this file cannot borrow it. "
            "Either it was renamed -- update the names here -- or the piece moved into a function, "
            "in which case call it instead." % ", ".join(missing))
    return ns


def layout():
    """DEFAULTS, overlaid with whatever the layout tool has saved."""
    out = dict(DEFAULTS)
    path = UI / "layout.json"
    if path.is_file():
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SystemExit("%s is not valid JSON: %s" % (path, exc))
        # One gap became two, and a file written before that split still means the pair.
        if "column_gap" in saved:
            saved.setdefault("column_gap_1", saved["column_gap"])
            saved.setdefault("column_gap_2", saved["column_gap"])
            saved.pop("column_gap")
        out.update({k: v for k, v in saved.items() if k in DEFAULTS or k == "framed"})
    return out


def geometry(L):
    """Every measurement the page needs, and the coupling that makes them interesting.

    The duty wheel is not sized by hand. It takes the width the board column and the action box
    leave, and because it is SQUARE that width becomes its height -- which is the height the whole
    main row then has to live in. Widen a board and the wheel narrows by more than you gained,
    because the action box is drawn to a fraction of the board's width and narrows with it.

    The banner comes out of the wheel's height, one for one, for the same reason: a square that
    cannot grow sideways cannot absorb a band above it.
    """
    pad = STAGE_PAD
    inner_w = L["canvas_width"] - 2 * pad
    inner_h = L["canvas_height"] - L["margin_top"] - L["margin_bottom"]

    bw = float(L["board_width"])
    left_frac = 0.0 if L["width_whole_board"] else FRAME_START
    panel_w = bw * (FRAME_END - left_frac)
    overhang = bw * left_frac
    bh = round(bw * VB_H / VB_W, 1)

    top_h = float(L["special_height"])
    main_h = inner_h - top_h                       # the top row and the main row share one edge
    banner_h = float(L["banner_height"])
    wheel_room = inner_w - bw - panel_w - L["column_gap_1"] - L["column_gap_2"]
    wheel = max(0.0, min(wheel_room, main_h - banner_h))
    bound_by = "width" if wheel_room <= main_h - banner_h else "height"

    # THE ACTION BOX ENDS ON THE ACOLYTES' FEET, not at the bottom of the row.
    #
    # The wheel's box is not its visible foot: the figures hang below the last row of tiles, and
    # that lower edge is the line the eye reads as the bottom of the component. Asked for rather
    # than measured off a render, because the tiles carry per-tile offsets AND an arrangement
    # shift -- both of which move the rows -- so a constant here would be right until the next
    # time anyone opened the drag tool, and then quietly wrong.
    grid_box = dg.load()["box"]
    act_h = round(banner_h + wheel * (dg.acolyte_foot() / grid_box), 1)

    seats = int(L["seats"])
    boards_h = seats * bh + (seats - 1) * L["board_gap"]

    return {
        "pad": pad, "inner_w": inner_w, "inner_h": inner_h,
        "bw": bw, "bh": bh, "panel_w": panel_w, "overhang": overhang,
        "top_h": top_h, "main_h": main_h, "banner_h": banner_h,
        "wheel_room": wheel_room, "wheel": wheel, "bound_by": bound_by, "act_h": act_h,
        "seats": seats, "boards_h": boards_h,
        # what the wheel could not reach, given to the boxes rather than left as ground
        "slack": max(0.0, (main_h - banner_h) - wheel),
        # fitted to the wheel's height, because the map is the one component taller than it is wide
        "map_w": wheel * MAP_ASPECT,
        "left_top": float(L["row_gap"]),
    }


# The info banner. One line of the duty or building under the pointer, in the wheel's own width.
#
# The qualifier runs INLINE after the description rather than on its own line, and that is what
# makes the band affordable: stacked, the longest entry needs 94 px at this size; inline it needs
# 69. The separator is a space, not a middot -- several qualifiers already use middots internally
# ("Chapel adds +1 piety - Vestry +1 per acolyte"), so a leading one puts three in a row doing two
# different jobs. The size drop and the colour shift carry the break, and every description ends
# in a full stop anyway.
# The map button lives at the banner's right end, and it is ICON ONLY for a measured reason.
# The banner's body has 791 px and its tallest entry needs 57.1 of a 59.2 box. A 36 px icon leaves
# 738 and nothing moves. Add the word "Map" or a key badge and the body drops to 716, at which
# point six entries tip from two lines to three and the tallest jumps to 85.5 -- a cliff, not a
# slope, and one a taller band does not rescue: even 104 px leaves a 75.2 box. The label lives in
# the tooltip and the shortcut in the keyboard instead, and the wheel keeps its 877.8.
MAP_ICON = ('<svg viewBox="0 0 24 24" fill="none" stroke="#2A2320" stroke-width="1.7" '
            'stroke-linejoin="round"><path d="M9 4 L3 6.5 V20 L9 17.5 L15 20 L21 17.5 V4 '
            'L15 6.5 Z"/><path d="M9 4 V17.5 M15 6.5 V20"/></svg>')
WHEEL_ICON = ('<svg viewBox="0 0 24 24" fill="none" stroke="#2A2320" stroke-width="1.7">'
              '<rect x="3" y="3" width="6" height="6" rx="1"/><rect x="9.5" y="3" width="5" '
              'height="6" rx="1"/><rect x="15" y="3" width="6" height="6" rx="1"/>'
              '<rect x="3" y="9.5" width="6" height="5" rx="1"/><rect x="9.5" y="9.5" width="5" '
              'height="5" rx="1"/><rect x="15" y="9.5" width="6" height="5" rx="1"/>'
              '<rect x="3" y="15" width="6" height="6" rx="1"/><rect x="9.5" y="15" width="5" '
              'height="6" rx="1"/><rect x="15" y="15" width="6" height="6" rx="1"/></svg>')
VIEW_BUTTON = ('<button id="gv-viewbtn" type="button" title="Map (M)" aria-label="Show the map">'
               '<span class="ico ico-map">%s</span><span class="ico ico-wheel">%s</span>'
               '</button>' % (MAP_ICON, WHEEL_ICON))

BANNER = ('<div class="gv-banner" id="gv-banner">'
          '<span class="lab" id="gv-banner-lab">Duty</span>'
          '<div class="bd" id="gv-banner-body"><span class="rest">Point at a duty action or '
          'building to read it.</span></div>' + VIEW_BUTTON + '</div>')

CSS = """
/* The page's own chrome. Everything below this block is either the ground, or an override of a
   rule gen_board.py wrote for ITS layout -- its components are wanted, its page is not. */
*{box-sizing:border-box}

/* THE GROUND, and it is one surface owned by one element -- THE PAGE, not the stage.
   The duty grid draws no ground of its own (gen_duty_grid.BACKGROUND is None) and the stage is
   transparent, so this shows through the channels between the nine tiles and down every gutter,
   as one connected region of about 32%% of the canvas, AND fills whatever the stage does not
   reach. Any component that paints its own ground punches an opaque hole in it.

   IT MOVED HERE FROM `.gv-stage`, and that is the whole change.
   `.gv-stage` is a fixed %(can_w_note)s canvas that #gv-fit then zoom-to-fits, so a background on it
   is a background on a rectangle in the middle of the screen: on a 3440-wide display the fit
   leaves about 840 px either side, and those 840 px were the flat colour. The picture looked
   clipped because it was -- clipped to the canvas, not to the screen. On `html,body` it is
   stretched to the viewport instead, which is what `gen_tile_offsets` has always done with its
   own `#stage{flex:1}` and why the ground looked right there and wrong here. Same declaration,
   different element, and the element was the bug.

   `cover`, NOT `100%% 100%%`, and the difference is the whole behaviour on anything but an
   ultrawide. `100%% 100%%` stretches the picture to the viewport, so a 2.600:1 panorama on a
   1.758:1 laptop is squashed by a third -- every figure short and wide, and the engraving's line
   weight anisotropic. `cover` keeps the aspect and crops instead: the screen gets the MIDDLE of
   the panorama at true proportions, and what falls off the ends is the outer quarter each prompt
   was told to put the subject in.

   That crop is not a consolation, it is the better picture on those screens, and it is measurable.
   The canvas is 4:3 and zoom-to-fitted, so the narrower the display the WIDER the share of it the
   board takes -- 24.4%%-75.6%% at 3440x1320 against 12.1%%-87.9%% at 1512x860. Stretched, that put
   the right half's shrine and candles directly under the duty wheel's channels: measured through
   the real exposed ground inside the wheel, 15.5%% of it sat over L50 against a CEILING of 50 and
   a tile-edge luminance of 53.4. Cropped, the board lands on the composed middle at every size.

   On a 2.606:1 display the crop is 3 px of height, so this changes nothing about the screen it
   was composed for.

   The colour comes LAST. In a multi-layer `background` shorthand the colour must be the final
   value; put it first, as the old stage rule could because it had one layer, and the whole
   declaration is dropped and the page is white. */
html,body{height:100%%;margin:0;overflow:hidden;
  background:url(%(panorama)s) center/cover no-repeat #0b0a08}
#gv-fit{position:absolute;inset:0}

/* Transparent, deliberately and not by omission: `background:none` on a stage that used to paint
   is what lets the page's field run under the board unbroken. A colour here -- even the same
   #0b0a08 -- puts the canvas rectangle back as a visible edge against the picture. */
.gv-stage{position:absolute;top:0;left:0;transform-origin:top left;
  background:none;
  display:flex;flex-direction:column}
.gv-top,.gv-main{display:flex;align-items:flex-start}
.gv-left{display:flex;flex-direction:column}
.gv-wheelcol{display:flex;flex-direction:column}

/* gen_board.py's own layout rules, unwound. Its components were written as flex items of its
   rows and carry the margins and widths that suited them there; here the slot is the authority. */
.gv-stage .stage,.gv-stage .top,.gv-stage .row,.gv-stage .left,.gv-stage .boards{all:unset}
.gv-stage .strip{flex:none;margin:0;height:auto;width:100%%}
.gv-stage svg.alms{position:static;margin:0}
.gv-stage svg.sa{position:static;margin:0}

/* The action box and the log are ONE panel with two sections, not two panels that touch.
   The box gives up its foot, the log its head, and the log's own top border becomes the rule
   between them. Both draw an inset hairline with ::after, so those need the matching edge
   removed too or the inner rule closes twice, a few px apart, at the join. */
.gv-stage .turn{display:flex;flex-direction:column;height:100%%;margin:0;width:100%%}
.gv-stage .turn>.log{flex:1 1 auto;min-height:0;margin:0;width:auto;border:0;background:none;
  border-radius:0;border-top:1px solid rgba(42,35,32,.28);padding-top:2px}
.gv-stage .turn>.log::after{display:none}
.gv-stage .turn>.last{display:none}
/* The duty line moved OUT of the box and became the banner over the wheel, where it has the
   width for one line at 20px instead of four at 13.5. Left here it would say the same thing
   twice -- and it carries margin-top:auto, so it would also swallow the slack the log now uses. */
.gv-stage .turn>.inspect{display:none}

.gv-banner{display:flex;align-items:center;gap:14px;position:relative;box-sizing:border-box;
  background:#E5D8B9;border:1.4px solid #2A2320;border-radius:9px;padding:13px 18px;
  font:20px/1.42 "Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;color:#2A2320}
.gv-banner::after{content:'';position:absolute;inset:5px;border:1px solid rgba(42,35,32,.30);
  border-radius:5px;pointer-events:none}
.gv-banner .lab{flex:0 0 auto;font-size:11px;letter-spacing:.09em;text-transform:uppercase;
  color:#6B6355}
.gv-banner .bd{flex:1;min-width:0}
.gv-banner .bd b{font-weight:700}
.gv-banner .sub{font-size:18px;color:#6B6355}
.gv-banner .rest{color:#B7382E;font-style:italic}
.gv-wheel svg{display:block;width:100%%;height:100%%}
#gv-viewbtn{flex:0 0 auto;display:flex;align-items:center;justify-content:center;
  width:36px;height:36px;padding:0;cursor:pointer;background:#EFE6CC;
  border:1.2px solid #2A2320;border-radius:7px;box-shadow:0 1px 0 rgba(42,35,32,.22)}
#gv-viewbtn:hover{background:#F7EFD8}
#gv-viewbtn .ico{display:none;line-height:0}
#gv-viewbtn .ico svg{width:19px;height:19px;display:block}
#gv-viewbtn .ico-map{display:block}                      /* the wheel is showing: offer the map */
.mapview #gv-viewbtn .ico-map{display:none}
.mapview #gv-viewbtn .ico-wheel{display:block}
/* Both views stay in the DOM and one is hidden, so switching costs nothing -- the map is 100 KB
   of markup and rebuilding it on every toggle would be felt. */
#gv-map{display:none;align-items:center;justify-content:center}
#gv-map svg{display:block;width:100%%;height:100%%}
.mapview #gv-wheel{display:none}
.mapview #gv-map{display:flex}
.gv-cell{flex:0 0 auto}
.gv-cell-mkt .strip,.gv-cell-mkt .mkt{height:100%%;width:100%%}
.gv-cell-alms svg.alms{width:100%%;height:100%%}

/* THE ORNAMENT AT THE FOOT OF THE BOARD COLUMN.
   Positioned, not flowed. #gv-left is a flex column with a 30 px gap between boards, and adding
   the ornament as another flex child would give it that gap as well -- eating 30 of the 136.8 px
   that are actually there and leaving the picture in a 3.8:1 slot it was never cropped for. Out of
   flow it gets the real leftover, and it cannot push the boards above it.

   `contain`, so the box may be any shape and the picture keeps its own. The alternative is `cover`,
   which crops -- and what it would crop is exactly the feathered border that makes this sit on the
   ground instead of on top of it, replacing a soft edge with a hard one. Letterboxed bars are
   transparent here, so they are simply more ground.

   No background, no border, no shadow: one element owns the ground and this is not it. */
.gv-left{position:relative}
"""

# The measurements, emitted rather than left to the components. Every one of these comes out of
# geometry(), so the page and the figures the generator prints cannot disagree -- which is the
# whole reason the numbers live in one function instead of being written twice.
SIZES = """
#gv-stage{width:%(can_w).1fpx;height:%(can_h).1fpx;padding:%(mt).1fpx %(pad).1fpx %(mb).1fpx}
#gv-top{height:%(top_h).1fpx}
#gv-main{height:%(main_h).1fpx}
.gv-cell-sa{width:%(bw).1fpx}
.gv-cell-sa>svg{margin-left:%(overhang).1fpx}
.gv-cell-alms{width:%(panel_w).1fpx;height:%(top_h).1fpx;margin-left:%(gap1).1fpx}
.gv-cell-mkt{width:%(wheel_room).1fpx;height:%(top_h).1fpx;margin-left:%(gap2).1fpx}
#gv-left{width:%(bw).1fpx;margin-top:%(left_top).1fpx;height:%(left_h).1fpx;gap:%(board_gap).1fpx}
#gv-act{width:%(panel_w).1fpx;height:%(act_h).1fpx;margin-left:%(gap1).1fpx}
#gv-wheelcol{width:%(wheel_room).1fpx;height:%(main_h).1fpx;margin-left:%(gap2).1fpx}
#gv-banner{height:%(banner_h).1fpx}
#gv-wheel{width:%(wheel).1fpx;height:%(wheel).1fpx}
/* The map is 1014 x 1149 -- TALLER than it is wide, unlike everything else on this board. Fitted
   to the wheel's width it would stand 995 px in an 878 px box and be cut off, so it is fitted to
   the HEIGHT instead and comes out narrower, with ground either side. The banner stays put: it
   carries the button that switches back. */
#gv-map{width:%(wheel).1fpx;height:%(wheel).1fpx}
#gv-map .map{width:%(map_w).1fpx;height:%(wheel).1fpx}
"""


PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>Pilgrim &mdash; game view</title>
<style>%(board_css)s</style>
<style>%(css)s</style>
<style>%(sizes)s</style>
</head><body>
<div id="gv-fit"><div class="gv-stage" id="gv-stage">
  <div class="gv-top" id="gv-top">
    <div class="gv-cell gv-cell-sa">%(sa)s</div>
    <div class="gv-cell gv-cell-alms">%(alms)s</div>
    <div class="gv-cell gv-cell-mkt">%(market)s</div>
  </div>
  <div class="gv-main" id="gv-main">
    <div class="gv-left" id="gv-left">%(boards)s</div>
    <div class="gv-act" id="gv-act">%(turn)s</div>
    <div class="gv-wheelcol" id="gv-wheelcol">%(banner)s<div class="gv-wheel" id="gv-wheel">%(wheel)s</div><div id="gv-map">%(map)s</div></div>
  </div>
</div></div>
<svg width="0" height="0" style="position:absolute" aria-hidden="true">%(defs)s</svg>
<script>%(fit)s</script>
<script>%(inspect)s</script>
<script>%(view)s</script>
</body></html>
"""

# Zoom to fit, which is what the real view does: the canvas is an ASPECT, not a resolution, so the
# stage is laid out at its true size and then scaled. Every px figure the generator prints is
# therefore true of the layout even when the window shows it smaller.
FIT_JS = """
(function(){
  var stage = document.getElementById('gv-stage'), W = %(can_w)s, H = %(can_h)s;
  function fit(){
    var k = Math.min(window.innerWidth / W, window.innerHeight / H);
    stage.style.transform = 'translate(' + ((window.innerWidth - W*k)/2).toFixed(1) + 'px,'
                          + ((window.innerHeight - H*k)/2).toFixed(1) + 'px) scale(' + k + ')';
  }
  fit(); window.addEventListener('resize', fit);
})();
"""

# The hover readout, ported.
#
# gen_board.py binds `.wheel .act` -- the circular wheel's twelve wedges. The duty grid has no such
# elements: it emits one group per tile carrying `data-duty-name`, with `.dg-hit-l` / `.dg-hit-r`
# halves inside the five two-action tiles and a single `.dg-hit-f` in the rest. So the key is the
# tile's NAME plus which half, which is exactly how DUTY_TEXT is already keyed ("Clerical|0").
#
# Thirteen of the fourteen hit areas resolve. The City has no entry -- it is the one tile that is
# not a duty -- and a miss leaves the banner as it was rather than blanking it.
INSPECT_JS = """
(function(){
  var DUTY = %(duty)s, BLD = %(bld)s;
  var banner = document.getElementById('gv-banner-body'),
      lab = document.getElementById('gv-banner-lab');
  if (!banner) { return; }
  var rest = banner.innerHTML, restLab = lab ? lab.textContent : '';
  // The label is content, not decoration -- it says WHICH KIND of thing is being read, and left
  // fixed at "Duty" it captions every building with the wrong word.
  var show = function (d, kind) {
    if (lab) { lab.textContent = kind; }
    banner.innerHTML = '<b>' + d[0] + '</b> \\u2014 ' + d[1]
      + (d[2] ? ' <span class="sub">' + d[2] + '</span>' : '');
  };
  var bind = function (el, entry, kind) {
    if (!entry) { return; }
    el.addEventListener('mouseenter', function () { show(entry, kind); });
    el.addEventListener('mouseleave', function () {
      banner.innerHTML = rest;
      if (lab) { lab.textContent = restLab; }
    });
  };

  // The duty tiles. gen_board.py bound `.wheel .act` -- the circular wheel's wedges, which the
  // grid does not have. The grid gives one group per tile carrying data-duty-name, with
  // .dg-hit-l / .dg-hit-r halves in the five two-action tiles and a single .dg-hit-f in the rest,
  // so the key is the tile's NAME plus which half -- exactly how DUTY_TEXT is already keyed.
  Array.prototype.forEach.call(document.querySelectorAll('.dg-hit'), function (hit) {
    var tile = hit.closest('[data-duty-name]');
    if (!tile) { return; }
    var half = hit.classList.contains('dg-hit-r') ? '1' : '0';
    bind(hit, DUTY[tile.getAttribute('data-duty-name') + '|' + half], 'Duty');
  });

  // The buildings. stamp_buildings() has put data-building on every element that draws a hex --
  // its two paths, its name and its level badge -- because market-hex.svg is one flat group with
  // no per-hex nesting to bind to. Season-end tiles carry no stamp and stay inert.
  Array.prototype.forEach.call(document.querySelectorAll('[data-building]'), function (el) {
    bind(el, BLD[el.getAttribute('data-building')], 'Building');
  });
})();
"""

def building_text():
    """What each building does, from `configs/buildings.json` -- the catalogue the ENGINE reads.

    gen_board.py keeps its duty text as a hand-written dict, which is reasonable for nine tiles
    whose wording is UI copy. Buildings are not that: their descriptions, levels, costs and
    donation values are game data, and a second copy here would be a second copy to keep right.
    The one that drifts is always the one nobody is looking at.

    Season-end tiles share the market strip with the buildings and are not in the catalogue, so
    they simply do not resolve -- and a miss leaves the banner as it was rather than blanking it.
    """
    path = REPO / "configs" / "buildings.json"
    if not path.is_file():
        print("no %s -- buildings will not respond to the pointer." % path)
        return {}
    cat = json.loads(path.read_text(encoding="utf-8"))["catalogue"]
    out = {}
    for b in cat:
        stone = "%d stone" % b["stone_cost"] if b["stone_cost"] != 1 else "1 stone"
        sub = "Level %d &middot; %s &middot; %d VP donated" % (b["level"], stone, b["donation_vp"])
        # A building whose effect the engine does not yet apply says so, because a reader who
        # trusts this line and then watches nothing happen has been told something false.
        if b.get("effect_status") != "implemented":
            sub += " &middot; effect deferred"
        # The catalogue writes resources as {stone}, {silver}, {wheat}: its own markup for "this
        # is a token, not a word". gen_board's _icons() swaps the bare WORD for a glyph, so left
        # alone it substitutes inside the braces and leaves them stranded around the picture --
        # "{}" with a cube in the middle. Unwrapping first lets the same renderer do its job.
        desc = re.sub(r"\{(silver|stone|wheat|piety)\}", r"\1", b["description"])
        out[b["name"]] = [b["name"], desc, sub]
    return out


# The four seats, and the one place their colours are written down for this page.
#
# Every value here comes from a committed asset rather than being picked: the fills are
# SA_SWATCH, which the Special Activities placeholder already uses for exactly this
# kind of static swatch, and the strokes are the dark face of each seat's own acolyte cube in
# ui/assets-gothic/ui/. They are the DIM tones on purpose. A market strip or an alms disc says
# whose it is, not whose turn it is, so tying them to the lit/dim state would animate ownership
# every time the turn passed.
SEAT_INK = {"sage": "#4a7f24", "pewter": "#215482", "plum": "#7c227f", "bone": "#a59d92"}

# What the borrowed components still paint in, and what it becomes.
#
# ONE MAPPING, USED EVERYWHERE. The market strip, the alms discs and the log's seat discs all say
# the same thing -- which player -- so an old seat has to become the same new seat in all three or
# the board contradicts itself: a red disc in the log beside a plum disc on the track, both
# meaning the same person.
#
# The market's art is older still and carries a green that was never in gen_board's own SEAT
# table; the market has no white strip, so green takes the seat white would have had.
OLD_TO_SEAT = {
    "red": "sage", "yellow": "pewter", "blue": "plum", "white": "bone",
}
# Two greys carry a building's STATE, not its owner. gen_board.py's market comment is the
# authority: "Ownership is the foot bar; state is the field: dark grey donated, light grey used
# this turn." #A8A296 is the darker of the two.
DONATED_GREY = "#A8A296"
USED_GREY = "#D5D0C0"

# Bone was #d8cfbe, and on the market's #EFE6CC parchment it was all but invisible -- a strip you
# had to hunt for. It takes the donated grey instead, which reads at a glance.
#
# That collides in exactly one case: a DONATED building owned by this seat would be a dark grey
# strip on a dark grey field. There it takes the lighter used-grey instead, which is the only
# other tone already in this palette and so does not introduce a fifth grey to the board.
BONE_FILL = DONATED_GREY
BONE_ON_DONATED = USED_GREY

# The round badge. It is GREEN when the building goes live this round -- when its number equals the
# round in the strip's top corner -- and parchment otherwise. The art has that baked in for Brewery
# because the sample is round 12, which is why it survived as a literal green until it was mistaken
# for an owner strip and recoloured. Computed here instead, so it stays true if the round moves.
LIVE_GREEN = "#2E6B34"
BADGE_PARCHMENT = "#EFE6CC"


def recolour_seats(markup, old_seats, fills):
    """Swap every old seat colour for its current one, fill and stroke together.

    A colour substitution and nothing else -- no geometry, no structure. Both halves of each pair
    have to move: the discs carry a fill and a darker border, and changing only the fill leaves a
    plum disc ringed in the old red.

    Case-insensitive, because market-hex.svg writes its hexes upper-case and the palette here is
    lower. Longest-first is not needed -- these are six-digit hexes and cannot overlap -- but the
    old value must not be a colour anything else uses, which is why white is matched as its PAIR
    rather than as "#FFFFFF" on its own.
    """
    import re
    n = 0
    for old_name, seat in OLD_TO_SEAT.items():
        if old_name not in old_seats:
            continue
        old_fill, old_stroke = old_seats[old_name]
        new_fill, new_stroke = fills[seat]
        if old_fill.lower() == "#ffffff":
            # The white seat is matched by its BORDER, not its fill, and that is not fussiness.
            # gen_board's SEAT table says its fill is #FFFFFF, but nothing ever draws that: a white
            # disc on parchment needs an off-white, so what actually reaches the page is #F4EFE2 --
            # a tone the market also uses for an unowned hex. Keying on the fill therefore matched
            # nothing at all (the disc stayed pale and the log kept a seat the board no longer had),
            # and keying on #F4EFE2 alone would repaint a building. The border #8B7B4E belongs to
            # this seat and to nothing else on the page, so the pair is found by its second half.
            for pat, rep in (
                    (r"(background:)#[0-9a-fA-F]{6}(;border-color:)" + re.escape(old_stroke),
                     r"\g<1>%s\g<2>%s" % (new_fill, new_stroke)),
                    (r'(fill=")#[0-9a-fA-F]{6}(" stroke=")' + re.escape(old_stroke),
                     r'\g<1>%s\g<2>%s' % (new_fill, new_stroke))):
                markup, hits = re.subn(pat, rep, markup, flags=re.I)
                n += hits
            continue
        for a, b in ((old_fill, new_fill), (old_stroke, new_stroke)):
            markup, hits = re.subn(re.escape(a), b, markup, flags=re.I)
            n += hits
    return markup, n


def live_badges(market):
    """Colour each round badge by whether its building goes live THIS round.

    The rule is the one the art already implied: the strip says "Round 12" in its corner, and the
    building whose badge reads 12 is the one that becomes available now. That was a literal green
    fill on one hexagon rather than a rule, so it was indistinguishable from an owner strip -- and
    duly got recoloured as one. Reading the round out of the strip and deriving every badge from it
    makes the green mean something, and makes it follow if the round changes.

    A badge is a <rect> immediately followed by its number <text>, which is what lets them be found
    without any per-hex structure to hang off (see stamp_buildings for why there is none).
    """
    import re
    m = re.search(r">\s*Round\s+(\d+)\s*</text>", market)
    if not m:
        print("  the market strip has no 'Round N' label, so no badge can be called live")
        return market, (0, 0)
    rnd = int(m.group(1))
    live = waiting = 0
    out, last = [], 0
    for b in re.finditer(r'(<rect\b[^>]*?/>)(\s*<text\b[^>]*?>)(\d+)(</text>)', market):
        rect, open_t, num, close_t = b.groups()
        want = LIVE_GREEN if int(num) == rnd else BADGE_PARCHMENT
        fixed = re.sub(r'fill="[^"]*"', 'fill="%s"' % want, rect, count=1)
        if int(num) == rnd:
            live += 1
        else:
            waiting += 1
        out.append(market[last:b.start()])
        out.append(fixed + open_t + num + close_t)
        last = b.end()
    out.append(market[last:])
    return "".join(out), (live, waiting)


def donated_owner_strips(market, seat_fill, on_donated):
    """A donated building owned by the grey seat: give its STRIP the lighter grey.

    Dark-on-dark is the one combination this palette cannot show. The field says donated and the
    strip says who, and when both are the donated grey the strip vanishes into it -- so the strip
    takes the used-grey instead. Nothing else moves.

    THE TRAP, AND WHY THIS IS NOT A SEARCH-AND-REPLACE. Since this seat's colour IS the donated
    grey, the two are indistinguishable by value: a blunt substitution inside the hex repaints the
    FIELD, which is the very thing that says "donated". So the field is identified positionally --
    it is the first filled path of the pair -- and only a LATER path of the same colour is treated
    as the strip. On the sample market that is none of them: the art carries three owner strips and
    this seat has no building.
    """
    hits = 0
    grey = re.compile(re.escape(DONATED_GREY), re.I)
    pair = re.compile(r'(<path\b[^>]*?fill="%s"[^>]*?/>)((?:\s*<path\b[^>]*?/>){1,3})'
                      % re.escape(DONATED_GREY), re.I)

    def swap(m):
        nonlocal hits
        field, rest = m.group(1), m.group(2)          # field first, never touched
        if not grey.search(rest):
            return m.group(0)
        hits += 1
        return field + grey.sub(on_donated, rest)

    return pair.sub(swap, market), hits


def stamp_buildings(market, names):
    """Give every market hex its name, as an attribute on the elements that draw it.

    WHY THIS IS NEEDED AT ALL

    `market-hex.svg` is one flat <g> of 92 siblings -- two paths, a name <text>, a badge <rect> and
    a level <text> per tile, all at the same depth. There is no group per hex, so a hex cannot be
    addressed: reading the name out of the <text> and binding to its parent binds all sixteen tiles
    to the same node, and the last one wins. (It does exactly that, silently: every hex reports
    whichever building was bound last.)

    Re-nesting the markup into per-hex groups would be the tidy fix and is the risky one -- it
    means re-serialising an SVG this file does not own, whose generator no longer exists. Stamping
    an attribute onto the elements that are already there changes no structure and no geometry.

    The rule is positional, because position is all the markup gives us: a name <text> is preceded
    by its stroke path and its fill path, and followed by its level badge. Anything that does not
    match a catalogue name -- the season-end tiles, the "Buildings" heading, the round number --
    is left alone.
    """
    import re
    tags = [(m.start(), m.end(), m.group(1), m.group(0))
            for m in re.finditer(r"<(path|text|rect|g|clipPath)\b[^>]*?>", market)]
    text_body = {m.start(): m.group(1).strip()
                 for m in re.finditer(r"<text\b[^>]*?>([^<]*)</text>", market)}
    stamps = []                      # (position of the tag's '>', building name)
    for i, (start, end, tag, raw) in enumerate(tags):
        if tag != "text" or text_body.get(start) not in names:
            continue
        name = text_body[start]
        want = [i]                                           # the name itself
        for j in (i - 1, i - 2):                             # the stroke and fill paths
            if j >= 0 and tags[j][2] == "path":
                want.append(j)
        for j in (i + 1, i + 2):                             # the level badge and its numeral
            if j < len(tags) and tags[j][2] in ("rect", "text"):
                want.append(j)
        for j in want:
            # BEFORE the '/' of a self-closing tag, not before the '>'. Inserting between them
            # turns `<path ... />` into `<path ... / data-building="x">` -- an OPEN element, so
            # every sibling after it nests inside and the strip collapses to one hex. The hover
            # still worked perfectly while the market was wrecked, which is why this is checked
            # below rather than trusted.
            end = tags[j][1]
            stamps.append((end - 2 if market[end - 2] == "/" else end - 1, name))
    if not stamps:
        return market, 0
    out, last = [], 0
    for pos, name in sorted(stamps):
        out.append(market[last:pos])
        out.append(' data-building="%s"' % name.replace('"', "&quot;"))
        last = pos
    out.append(market[last:])
    stamped = "".join(out)
    before, after = market.count("/>"), stamped.count("/>")
    if before != after:
        raise SystemExit(
            "stamping changed the number of self-closing tags in the market (%d -> %d), which "
            "means an attribute landed between a '/' and its '>' and opened an element that "
            "should have closed. The strip would render as one hex." % (before, after))
    return stamped, len({n for _, n in stamps})


def asm_seats():
    """SEAT_COLORS, from the assembler that defines them -- not a fifth copy of the same tuple."""
    import gen_board_gothic
    return list(gen_board_gothic.SEAT_COLORS)


def alms_panel(gb, fills, width):
    """The alms table with the current seats, built rather than borrowed.

    gen_board.py builds its own `alms` string against red / yellow / blue / white -- its four
    seats, which this board does not have. The panel is a function, not a fixed asset, so the
    honest fix is to call it with the seats this board actually uses instead of recolouring its
    output by search-and-replace.

    The player rows come from gen_board's sample game and carry the old seat names, so they are
    renamed in the same order: the data is which player sits where and how far up the track they
    are, and that is unchanged by what colour they wear.
    """
    import gen_alms_panel as ap
    order = list(fills)                                   # sage, pewter, plum, bone
    old = [p["seat"] for p in gb["P"]]
    rename = dict(zip(old, order))
    players = [dict(p, seat=rename[p["seat"]]) for p in gb["P"]]
    seats = {k: fills[k] for k in order}
    return ap.panel_svg(players, seats, gb["INK"], gb["PARCH"],
                        positions={k: 0 for k in order},
                        width=width, win_seats=[rename.get("blue", order[1])])


VIEW_JS = """
(function(){
  // The same mechanism gen_board.py uses: one class on the stage, both views in the DOM, and M on
  // the keyboard. The button always shows what you would switch TO, which is what its old label
  // said in words -- so the icon flips rather than staying put.
  var stage = document.getElementById('gv-stage'), btn = document.getElementById('gv-viewbtn');
  if (!stage || !btn) { return; }
  var set = function (toMap) {
    stage.classList.toggle('mapview', toMap);
    btn.title = toMap ? 'Duty wheel (M)' : 'Map (M)';
    btn.setAttribute('aria-label', toMap ? 'Show the duty wheel' : 'Show the map');
  };
  btn.addEventListener('click', function () {
    set(!stage.classList.contains('mapview'));
  });
  addEventListener('keydown', function (e) {
    // not while someone is typing, and not on a shortcut meant for the browser
    if (e.metaKey || e.ctrlKey || e.altKey) { return; }
    var t = e.target;
    if (t && (t.isContentEditable || /^(input|textarea|select)$/i.test(t.tagName))) { return; }
    if (e.key === 'm' || e.key === 'M') {
      e.preventDefault();
      set(!stage.classList.contains('mapview'));
    }
  });
})();
"""


def _data_uri(p):
    """A file as a data: URI. Every image on this page is embedded, not linked.

    The page is written to ui/generated/ and then opened from wherever it happens to be -- a
    file:// URL, a copy on a desktop, an attachment. A relative src would work in the first case
    and silently show nothing in the others, which is the failure that looks like an art problem.
    """
    import base64
    import mimetypes
    kind = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    return "data:%s;base64,%s" % (kind, base64.b64encode(p.read_bytes()).decode("ascii"))


def _image_size(p):
    """(w, h) of an image, or None if Pillow is not here.

    Soft, because this is used only to PRINT what was drawn. A generator that refuses to build a
    board because it cannot measure a decoration for its own log has its priorities backwards.
    """
    try:
        from PIL import Image
    except ImportError:
        return None
    with Image.open(p) as im:
        return im.size


def _unsize(svg):
    """Strip a component's baked-in width and height so its slot can size it.

    gen_board.py draws the alms table at 339.4 px because that is what ITS column is. Here the
    cell decides, and an svg carrying both a viewBox and explicit dimensions ignores the cell.
    """
    import re
    return re.sub(r'\s(width|height)="[\d.]+"', "", svg, count=2)


def sized(markup, w, h):
    """A component in a box of this size. The slot is the authority, not the component."""
    return ('<div class="gv-box" style="width:%.1fpx;height:%.1fpx;overflow:hidden">%s</div>'
            % (w, h, markup))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--assets-dir", default=str(UI / "assets-gothic"))
    ap.add_argument("--assembler", default=None)
    ap.add_argument("--config", default=None)
    ap.add_argument("--seats", default=None, help="comma-separated seat colours")
    ap.add_argument("--lit", default=None, help="which seat has the turn (default: the first)")
    ap.add_argument("--duty-version", default=dg.VERSION,
                    help="which duty tile set to draw (default: gen_duty_grid.VERSION, %(default)s)")
    ap.add_argument("--output", default=None)
    ap.add_argument("--open", action="store_true")
    z = ap.parse_args()

    L = layout()
    G = geometry(L)
    gb = borrow()
    buildings = building_text()
    fills = {seat: (swatch, SEAT_INK[seat])
             for seat, swatch in zip(asm_seats(), SA_SWATCH)}
    fills["bone"] = (BONE_FILL, fills["bone"][1])
    old_seats = dict(gb["SEAT"])
    market, n_mkt = recolour_seats(gb["MARKET"], old_seats, fills)
    market, n_live = live_badges(market)
    market, n_dark = donated_owner_strips(market, fills["bone"][0], BONE_ON_DONATED)
    log, n_log = recolour_seats(gb["LOG"], old_seats, fills)
    market, stamped = stamp_buildings(market, set(buildings))
    turn, n_turn = recolour_seats(
        gb["TURN"] % (gb["_icons"]("Chapel &mdash; +1 piety on Clerical &amp; Devotion. "
                                   "Costs 1 silver."),
                      gb["_icons"](gb["_seat_disc"]("blue")
                                   + "<b>Produce</b>, gained 3 wheat.")),
        old_seats, fills)

    assets_dir = pathlib.Path(z.assets_dir).expanduser().resolve()
    asm_path = pathlib.Path(z.assembler) if z.assembler else HERE / "gen_board_gothic.py"
    asm = load_assembler(asm_path)
    seats = [s.strip() for s in z.seats.split(",")] if z.seats else \
        list(asm.SEAT_COLORS)[:G["seats"]]
    lit = z.lit or seats[0]
    config_path = pathlib.Path(z.config) if z.config else assets_dir / "production_test_config.json"

    roots = [build_board(asm, assets_dir, config_path, s, "lit" if s == lit else "dim")
             for s in seats]
    defs, unique_assets, saved = merge_defs(asm, roots)
    boards = []
    for root in roots:
        root.set("width", "%.1f" % G["bw"])
        root.set("height", "%.1f" % G["bh"])
        boards.append(ET.tostring(root, encoding="unicode"))

    # At the BOARD's width this panel would sit proud of the action box below it. The cell is a
    # board wide -- that is what puts the alms table and the market on the same two vertical
    # lines as the action box and the wheel -- but the panel inside it is the action box's width.
    sa, sa_spec = special_placeholder(G["panel_w"], G["top_h"],
                                         L["frame_border_y"], L["frame_border_x"])
    # ACOLYTES ON THE DUTY TILES, and the counts are a FIXTURE, not the engine's.
    #
    # The engine does hold this: `Workforce.mancala` is nine counts per player. What it does not
    # hold in any one place is which mancala index is which duty. Duties are keyed by compass
    # position and the categories are shuffled onto them at setup, and this repo already carries
    # THREE arrangements that disagree -- `_DEFAULT_DUTY_TILES` in pilgrim/model/duties.py,
    # `duties` in tools/ui_debug/duty_wheel_layout.json, and DUTY_NAMES here -- none of which
    # feeds the rules. Picking one would draw a player's acolytes on the wrong duty and nothing
    # would say so, which is the Taxation bug again with a different face.
    #
    # So the drawing takes counts keyed by DUTY, the caller supplies them, and this caller is
    # still a fixture. Wiring it to a real GameState is a rules question first: given a state,
    # which duty is mancala position n.
    #
    # Written out for all four seats and then PROJECTED onto the ones actually playing, rather
    # than sliced. `--seats` can name any subset in any order, so `row[:len(seats)]` would hand
    # the third player's counts to whoever happens to be third in the list -- right for the
    # default order and wrong for every other, which is the quiet kind of wrong.
    FIXTURE = {
        "sage":   [2, 1, 0, 3, 0, 1, 2, 0, 1],
        "pewter": [1, 0, 2, 0, 0, 1, 0, 1, 0],
        "plum":   [0, 0, 1, 2, 0, 1, 0, 0, 3],
        "bone":   [3, 0, 0, 1, 0, 1, 0, 2, 0],
    }
    acolytes = [[FIXTURE[seat][i] for seat in seats] for i in range(9)]
    # `active=lit`, the SAME value that decides which player board is drawn lit. Whose turn it is
    # is one fact, and the wheel and the boards now read it from one place -- so a board can never
    # be lit for one seat while the wheel stays open to another. Passing it also closes every duty
    # that seat has no acolytes on: those tiles are drawn exactly as before and simply stop
    # responding, because a duty you have nobody standing on is not one you can act through.
    # `seats` and `active=lit` are the SAME values the player boards are built from, so the wheel
    # cannot disagree with them about who is playing or whose turn it is. At two or three players
    # the row under each tile is that many figures, centred; a seat with none on a tile is drawn
    # as nothing at all rather than as a figure labelled 0.
    wheel = dg.duty_grid_svg(labels=dg.DUTY_NAMES, version=z.duty_version, klass="wheel gv-grid",
                             acolytes=acolytes, active=lit, seats=tuple(seats))
    drawn = len(dg.find_tiles(version=z.duty_version))

    page = PAGE % {
        "board_css": gb["CSS"],
        # dg.panorama_uri(), not a local copy: the layout tool paints the same field on its
        # simulated screen, and a second definition of where it lives is a second thing to keep
        # in step. can_w_note is the canvas size quoted in the comment above the rule, read from
        # the geometry rather than typed, so the prose cannot drift from the numbers.
        "css": CSS % {"panorama": dg.panorama_uri(), "pad": G["pad"],
                      "can_w_note": "%.0f x %.0f" % (L["canvas_width"], L["canvas_height"])},
        "sizes": SIZES % {
            "can_w": L["canvas_width"], "can_h": L["canvas_height"],
            "pad": G["pad"], "mt": L["margin_top"], "mb": L["margin_bottom"],
            "top_h": G["top_h"], "main_h": G["main_h"], "bw": G["bw"],
            "overhang": G["overhang"], "panel_w": G["panel_w"],
            "wheel_room": G["wheel_room"], "wheel": G["wheel"],
            "gap1": L["column_gap_1"], "gap2": L["column_gap_2"],
            "left_top": G["left_top"], "left_h": G["main_h"] - G["left_top"],
            "board_gap": L["board_gap"], "banner_h": G["banner_h"],
            "map_w": G["map_w"], "act_h": G["act_h"]},
        "sa": sa,
        "alms": _unsize(alms_panel(gb, fills, G["panel_w"])),
        "market": market,
        "boards": "\n      ".join(boards),
        "turn": turn,
        "banner": BANNER,
        "wheel": wheel,
        "map": gb["_map_svg"],
        "defs": ET.tostring(defs, encoding="unicode"),
        "fit": FIT_JS % {"can_w": L["canvas_width"], "can_h": L["canvas_height"]},
        "inspect": INSPECT_JS % {
            "duty": json.dumps({k: [v[0], gb["_icons"](v[1]), gb["_icons"](v[2])]
                                for k, v in gb["DUTY_TEXT"].items()}),
            # the same glyph pass the duty text gets, so "1 stone" draws its cube here too
            "bld": json.dumps({k: [v[0], gb["_icons"](v[1]), gb["_icons"](v[2])]
                               for k, v in buildings.items()})},
        "view": VIEW_JS,
    }

    # The log lives inside the action box now, and the borrowed TURN does not contain it.
    page = page.replace('<div class="last">', log + '<div class="last">', 1)

    out = pathlib.Path(z.output) if z.output else UI / "generated" / "game-view.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print("written %s  (%.1f MB)" % (out, out.stat().st_size / 1024 / 1024))
    print("  canvas %g x %g, margins %g / %g"
          % (L["canvas_width"], L["canvas_height"], L["margin_top"], L["margin_bottom"]))
    print("  columns  %.1f |%g| %.1f |%g| %.1f"
          % (G["bw"], L["column_gap_1"], G["panel_w"], L["column_gap_2"], G["wheel_room"]))
    print("  top row  %g tall   main row %.1f tall" % (G["top_h"], G["main_h"]))
    print("  banner   %.1f      duty wheel %.1f square (%s-bound, %.1f px spare)"
          % (G["banner_h"], G["wheel"], G["bound_by"], G["slack"]))
    # Said out loud, because a version with no files is not an error here -- the wheel draws its
    # flat region colours and carries on, which looks like a deliberate placeholder board rather
    # than a wrong --duty-version.
    print("  tiles    version %s, %d of 9 drawn%s"
          % (z.duty_version, drawn, "" if drawn else "   <- no art found for this version"))
    print("  boards   %d x %.1f + gaps = %.1f, starting %.1f below the top row"
          % (G["seats"], G["bh"], G["boards_h"], G["left_top"]))
    print("  %d assets stored once, saving %.1f MB" % (unique_assets, saved / 1024 / 1024))
    print("  hover: %d duty actions, %d buildings in the catalogue, %d on the market"
          % (len(gb["DUTY_TEXT"]), len(buildings), stamped))
    print("  seats: %s" % ", ".join("%s %s" % (k, v[0]) for k, v in fills.items()))
    print("  recoloured %d swatches in the market, %d in the log, %d in the action box"
          % (n_mkt, n_log, n_turn))
    print("  round badges: %d live this round, %d waiting" % n_live)
    print("  donated buildings owned by the grey seat: %d" % n_dark)
    if not sa_spec["fits"]:
        print("  NOTE the Special Activities table does not fit these borders")
    url = out.resolve().as_uri()
    print("\n%s" % url)
    if z.open:
        import webbrowser
        webbrowser.open(url)


if __name__ == "__main__":
    main()
