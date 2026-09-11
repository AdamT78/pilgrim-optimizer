"""The gothic boards in the game view's own column: four seats, left, at true scale.

This answers one question -- what do four gothic boards cost, and look like, where they will actually
sit -- so it borrows the page rather than inventing one. The canvas, the stage padding, the column
width and the gap between boards all come from `gen_board.py`, and the zoom-to-fit is the same, so
what you see here lands where it would land in the real layout.

    python3 ui/render/gen_board_2.py --open

The four seats wear the four Cloister colours, and one of them is lit. Click a board to hand it the
turn: that is the same attribute flip the play view will make, running against boards built by the
production assembler, so if it works here it works there.

WHY THE ASSETS ARE SHARED

A board is about 3.6 MB, nearly all of it Base64, and four of those built independently would be a
14 MB page holding four copies of the same frame, the same portrait and the same resource icons.
But the four are no longer identical -- each carries its own drape, dim twin and gemstones -- so the
old trick of building one board and pointing four <use> elements at it no longer applies.

Instead every board is built in full and their <defs> are then merged: symbols carrying the same
`data-source` collapse to one, and every <use> that referenced a duplicate is repointed at the
survivor. What is genuinely per-seat stays four times over; everything else is stored once. That is
about 5.5 MB rather than 14.

Merging rather than sharing one <symbol> also keeps the turn toggle working. The toggle is a CSS
rule matching a descendant of `[data-turn]`, and CSS selectors do not reach inside the shadow tree
that a <use> creates -- so a board drawn as a single <use> could not be lit or dimmed at all.
"""
import argparse
import copy
import json
import importlib.util
import pathlib
import xml.etree.ElementTree as ET

HERE = pathlib.Path(__file__).resolve().parent
UI = HERE.parent
SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)

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


def q(tag):
    return f"{{{SVG_NS}}}{tag}"


def board_column_width(default=339.4):
    """COMP_W from gen_board.py: how wide a player board is drawn in the game view."""
    import re
    gen = HERE / "gen_board.py"
    if gen.is_file():
        m = re.search(r"COMP_W = round\(.*?\)\s*#\s*([\d.]+)", gen.read_text())
        if m:
            return float(m.group(1))
    return default


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


def artwork_spec(width, height, border_y, border_x=0.05):
    """The same hole, in the coordinates the artwork will be drawn in.

    The gothic player board is 1905 x 826 for a 339.4 x 147.2 render, so a unit of artwork is 5.612
    px. Keeping that scale means a Special Activities frame drops into the same pipeline unchanged:
    same intrinsic-size reading, same embedding, same everything.
    """
    k = VB_W / width
    canvas_w, canvas_h = VB_W, round(height * k)
    return {
        "canvas": (int(canvas_w), int(canvas_h)),
        "opening": (round(canvas_w * border_x), round(canvas_h * border_y),
                    round(canvas_w * (1 - 2 * border_x)), round(canvas_h * (1 - 2 * border_y))),
        "px_per_unit": round(1 / k, 4),
    }


def saved_layout():
    """`ui/layout.json`, when the layout tool has written one.

    This is what stops that tool being a mockup. The numbers have exactly one home; the tool edits
    it and this reads it, so moving a slider and changing the build are the same act rather than two
    things that have to be kept in agreement by hand. Command-line flags still win, for one-offs.
    """
    path = UI / "layout.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit("%s is not valid JSON: %s" % (path, exc))


def load_assembler(path):
    spec = importlib.util.spec_from_file_location("assembler", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build_board(asm, assets_dir, config_path, seat, turn):
    """One complete board for one seat, exactly as the production assembler would write it."""
    config = copy.deepcopy(asm.read_json(config_path))
    for role in ("frame_base", "frame_ornaments", "cloth_lit", "cloth_dim", "gems"):
        config.pop(role, None)
    config["seat"] = seat
    config["turn"] = turn
    config["id"] = f"gothic-{seat}"
    config["aria_label"] = f"Pilgrim gothic player board, {seat} seat"
    asm.apply_seat(config)

    layout = asm.read_json(assets_dir / "metadata" / "layout.json")
    root = ET.parse(assets_dir / "template" / "player_board_template.svg").getroot()
    asm.apply_config(root, config, layout)
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


PAGE = """<!doctype html>
<meta charset="utf-8"><title>Pilgrim gothic &mdash; four seats in the column</title><style>
*{box-sizing:border-box}
html,body{height:100%%;margin:0;overflow:hidden;background:#0C0F0A;
  font:14px/1.5 "Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;color:#E8E2D3}
.stage{position:absolute;top:0;left:0;transform-origin:top left;background:#2F5237;
  display:flex;flex-direction:column;padding:%(pad)spx;width:%(cw)spx;height:%(ch)spx}
.left{display:flex;flex-direction:column;width:%(bw)spx;flex:0 0 auto;gap:%(gap)spx}
.boards{display:flex;flex-direction:column;gap:%(gap)spx}
.sa-placeholder{display:block}
.boards svg{display:block;cursor:pointer}
.hint{position:fixed;right:10px;bottom:8px;font-size:11px;color:#7d8f80;
  font-family:ui-monospace,Menlo,monospace;text-align:right;line-height:1.7}
</style>
<div class="stage" id="stage">
  <div class="left">%(special)s<div class="boards" id="boards">%(boards)s</div></div>
</div>
<div class="hint">%(hint)s</div>
<svg width="0" height="0" style="position:absolute" aria-hidden="true">%(defs)s</svg>
<script>
// The same fit as the game view, centring included -- gen_board.py has always translated the
// stage to the middle of the window, and this had only been scaling it, so on a wide screen the
// board sat against the left edge with the rest of the window black.
const CW = %(cw)s, CH = %(ch)s, stage = document.getElementById('stage');
function fit(){
  const zoom = Math.min(innerWidth/CW, innerHeight/CH);
  stage.style.transform = 'translate(' + ((innerWidth - CW*zoom)/2).toFixed(1) + 'px,'
    + ((innerHeight - CH*zoom)/2).toFixed(1) + 'px) scale(' + zoom.toFixed(4) + ')';
}
addEventListener('resize', fit); fit();

// Whose turn it is. This is the whole mechanism: one attribute, no rebuild, no fetch. The play
// view does exactly this and nothing more.
const boards = [...document.querySelectorAll('#boards > svg')];
function giveTurn(board){
  for (const b of boards) b.querySelector('[data-turn]').dataset.turn = (b === board) ? 'lit' : 'dim';
}
for (const b of boards) b.addEventListener('click', () => giveTurn(b));
</script>
"""


def main():
    layout = saved_layout()
    ap = argparse.ArgumentParser(description="Four gothic player boards in the game view's column.")
    ap.add_argument("--assets-dir", default=str(UI / "assets-gothic"))
    ap.add_argument("--assembler", default=None)
    ap.add_argument("--config", default=None)
    ap.add_argument("--seats", default=None,
                    help="comma-separated seat colours; defaults to every seat the assembler knows")
    ap.add_argument("--lit", default=None, help="which seat starts with the turn (default: first)")
    ap.add_argument("--board-width", type=float,
                    default=layout.get("board_width", board_column_width()))
    ap.add_argument("--board-gap", type=float, default=layout.get("board_gap", BOARD_GAP))
    ap.add_argument("--special-height", type=float, default=layout.get("special_height"),
                    help="height of the Special Activities panel; default is the player board's "
                         "own aspect on the same canvas")
    ap.add_argument("--special-border", type=float,
                    default=layout.get("frame_border_y", layout.get("special_border", 0.10)),
                    help="fraction of the height spent on frame, above and below")
    ap.add_argument("--special-border-x", type=float, default=layout.get("frame_border_x", 0.05),
                    help="fraction of the width spent on frame, left and right")
    ap.add_argument("--no-special", action="store_true", help="draw the boards alone")
    ap.add_argument("--canvas-height", type=float,
                    default=layout.get("canvas_height", CANVAS_H),
                    help="the stage's height; the aspect against 1600 is what actually decides "
                         "how large everything renders")
    ap.add_argument("--log-height", type=float, default=None,
                    help="the log panel at the column's foot. Omitted, it takes whatever the boards "
                         "leave, which is what a scrolling panel should do and what the layout tool "
                         "now assumes; give a number to model a fixed one instead")
    ap.add_argument("--output", default=None)
    ap.add_argument("--open", action="store_true")
    args = ap.parse_args()

    assets_dir = pathlib.Path(args.assets_dir).expanduser().resolve()
    asm_path = pathlib.Path(args.assembler) if args.assembler else HERE / "gen_board_gothic.py"
    if not asm_path.is_file():
        raise SystemExit(f"assembler not found: {asm_path} (use --assembler)")
    asm = load_assembler(asm_path)

    seats = [s.strip() for s in args.seats.split(",")] if args.seats else \
        list(asm.SEAT_COLORS)[:int(layout.get("seats", len(asm.SEAT_COLORS)))]
    lit = args.lit or seats[0]
    if lit not in seats:
        raise SystemExit(f"--lit {lit!r} is not among the seats being drawn: {', '.join(seats)}")

    config_path = pathlib.Path(args.config) if args.config else \
        assets_dir / "production_test_config.json"

    roots = [build_board(asm, assets_dir, config_path, seat, "lit" if seat == lit else "dim")
             for seat in seats]
    defs, unique_assets, bytes_saved = merge_defs(asm, roots)

    bw = args.board_width
    bh = round(bw * VB_H / VB_W, 1)
    markup = []
    for root in roots:
        root.set("width", str(bw))
        root.set("height", str(bh))
        markup.append(ET.tostring(root, encoding="unicode"))

    sa_h = args.special_height if args.special_height else round(bw * VB_H / VB_W, 1)
    special, spec = ("", None)
    if not args.no_special:
        special, spec = special_placeholder(bw, sa_h, args.special_border,
                                            args.special_border_x)

    boards_px = len(seats) * bh + (len(seats) - 1) * args.board_gap
    used = boards_px + (0 if args.no_special else sa_h + args.board_gap)
    budget = args.canvas_height - 2 * STAGE_PAD
    # The log takes the remainder unless someone pins it. A fixed log could only ever be set wrong:
    # ask for one the column has no room for and the report hands your own request back as an
    # overflow, which tells you nothing you did not already type in.
    log_h = args.log_height if args.log_height is not None else max(0.0, budget - used
                                                                    - args.board_gap)
    spare = budget - used - (log_h + args.board_gap if log_h else 0)

    hint = ("%d seats at %g x %s, gap %d &rarr; %.0f px&nbsp;&middot;&nbsp;"
            "special %g x %s&nbsp;&middot;&nbsp;log %g&nbsp;&middot;&nbsp;canvas %dx%d<br>"
            "column budget %d, %s %.0f px%s<br>"
            "%d assets stored once, saving %.1f MB &middot; click a board to give it the turn"
            % (len(seats), bw, bh, args.board_gap, boards_px, bw, sa_h, log_h,
               CANVAS_W, args.canvas_height,
               budget, "spare" if spare >= 0 else "OVER BY", abs(spare),
               "" if spec is None or spec["fits"] else
               " &middot; the table does not fit this border",
               unique_assets, bytes_saved / 1024 / 1024))

    page = PAGE % {"pad": STAGE_PAD, "cw": CANVAS_W, "ch": args.canvas_height, "bw": bw,
                   "gap": args.board_gap, "boards": "\n    ".join(markup), "hint": hint,
                   "special": special, "defs": ET.tostring(defs, encoding="unicode")}

    if special and 'class="sa-placeholder"' not in page:
        raise SystemExit("the placeholder was built but never reached the page -- the PAGE template "
                         "has no %(special)s slot")

    out = pathlib.Path(args.output) if args.output else UI / "generated" / "gothic-four-boards.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print("written %s  (%.1f MB)" % (out, out.stat().st_size / 1024 / 1024))
    print("  seats: %s, lit: %s%s" % (", ".join(seats), lit,
          "   (defaults from ui/layout.json)" if layout else ""))
    print("  %d assets stored once; merging saved %.1f MB" % (unique_assets, bytes_saved / 1024 / 1024))
    if spec:
        art = artwork_spec(bw, sa_h, args.special_border, args.special_border_x)
        print("\nSPECIAL ACTIVITIES, as a hole")
        print("  panel            %g x %g px   (today it is %g x %g)"
              % (bw, sa_h, bw, SA_TODAY_H))
        print("  borders          %g%% top/bottom, %g%% left/right  ->  interior %g x %g px"
              % (round(args.special_border * 1000) / 10, round(args.special_border_x * 1000) / 10,
                 *spec["interior_px"]))
        print("  the table needs  %g x %g px, cubes %g px"
              % (*spec["table_px"], spec["cube_px"]))
        print("  %s" % ("it fits" if spec["fits"] else
                        "IT DOES NOT FIT: at these borders the panel needs %g px of height "
                        "or %g px of width" % (spec["height_needed"], spec["width_needed"])))
        print("  artwork canvas   %d x %d, clear opening x %d y %d w %d h %d"
              % (*art["canvas"], *art["opening"]))
        print("\nCOLUMN")
        print("  special %g + gap %d + boards %g + gap %d + log %g = %g of %d  (%s %.0f)"
              % (sa_h, args.board_gap, boards_px, args.board_gap, log_h,
                 used + (log_h + args.board_gap if log_h else 0), budget,
                 "spare" if spare >= 0 else "OVER BY", abs(spare)))
        print("  canvas  %d x %g   (gen_board.py stays at 1600 x 1067)"
              % (CANVAS_W, args.canvas_height))
    url = out.resolve().as_uri()
    print("\n%s" % url)
    if args.open:
        import webbrowser
        webbrowser.open(url)


if __name__ == "__main__":
    main()
