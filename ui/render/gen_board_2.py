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
import importlib.util
import pathlib
import xml.etree.ElementTree as ET

HERE = pathlib.Path(__file__).resolve().parent
UI = HERE.parent
SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)

# The game view's own numbers, read from the generator that owns them rather than copied.
CANVAS_W, CANVAS_H = 1600, 1067
STAGE_PAD = 14
BOARD_GAP = 30
VB_W, VB_H = 1905.0, 826.0


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
.left{display:flex;flex-direction:column;flex:0 0 %(bw)spx}
.boards{display:flex;flex-direction:column;gap:%(gap)spx}
.boards svg{display:block;cursor:pointer}
.hint{position:fixed;right:10px;bottom:8px;font-size:11px;color:#7d8f80;
  font-family:ui-monospace,Menlo,monospace;text-align:right;line-height:1.7}
</style>
<div class="stage" id="stage">
  <div class="left"><div class="boards" id="boards">%(boards)s</div></div>
</div>
<div class="hint">%(hint)s</div>
<svg width="0" height="0" style="position:absolute" aria-hidden="true">%(defs)s</svg>
<script>
// The same fit as the game view: scale the fixed canvas into whatever window you have.
const CW = %(cw)s, CH = %(ch)s, stage = document.getElementById('stage');
function fit(){ stage.style.transform = 'scale(' + Math.min(innerWidth/CW, innerHeight/CH) + ')'; }
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
    ap = argparse.ArgumentParser(description="Four gothic player boards in the game view's column.")
    ap.add_argument("--assets-dir", default=str(UI / "assets-gothic"))
    ap.add_argument("--assembler", default=None)
    ap.add_argument("--config", default=None)
    ap.add_argument("--seats", default=None,
                    help="comma-separated seat colours; defaults to every seat the assembler knows")
    ap.add_argument("--lit", default=None, help="which seat starts with the turn (default: first)")
    ap.add_argument("--board-width", type=float, default=board_column_width())
    ap.add_argument("--output", default=None)
    ap.add_argument("--open", action="store_true")
    args = ap.parse_args()

    assets_dir = pathlib.Path(args.assets_dir).expanduser().resolve()
    asm_path = pathlib.Path(args.assembler) if args.assembler else HERE / "gen_board_gothic.py"
    if not asm_path.is_file():
        raise SystemExit(f"assembler not found: {asm_path} (use --assembler)")
    asm = load_assembler(asm_path)

    seats = [s.strip() for s in args.seats.split(",")] if args.seats else list(asm.SEAT_COLORS)
    lit = args.lit or seats[0]
    if lit not in seats:
        raise SystemExit(f"--lit {lit!r} is not among the seats being drawn: {', '.join(seats)}")

    config_path = pathlib.Path(args.config) if args.config else \
        assets_dir / "production_test_config.json"

    roots = [build_board(asm, assets_dir, config_path, seat, "lit" if seat == lit else "dim")
             for seat in seats]
    defs, unique_assets, saved = merge_defs(asm, roots)

    bw = args.board_width
    bh = round(bw * VB_H / VB_W, 1)
    markup = []
    for root in roots:
        root.set("width", str(bw))
        root.set("height", str(bh))
        markup.append(ET.tostring(root, encoding="unicode"))

    used = len(seats) * bh + (len(seats) - 1) * BOARD_GAP
    hint = ("%d seats at %g x %s, gap %d &rarr; %.0f px of the column; canvas %dx%d<br>"
            "%d assets stored once, saving %.1f MB &middot; click a board to give it the turn"
            % (len(seats), bw, bh, BOARD_GAP, used, CANVAS_W, CANVAS_H,
               unique_assets, saved / 1024 / 1024))

    page = PAGE % {"pad": STAGE_PAD, "cw": CANVAS_W, "ch": CANVAS_H, "bw": bw,
                   "gap": BOARD_GAP, "boards": "\n    ".join(markup), "hint": hint,
                   "defs": ET.tostring(defs, encoding="unicode")}

    out = pathlib.Path(args.output) if args.output else UI / "generated" / "gothic-four-boards.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print("written %s  (%.1f MB)" % (out, out.stat().st_size / 1024 / 1024))
    print("  seats: %s, lit: %s" % (", ".join(seats), lit))
    print("  %d assets stored once; merging saved %.1f MB" % (unique_assets, saved / 1024 / 1024))
    url = out.resolve().as_uri()
    print("\n%s" % url)
    if args.open:
        import webbrowser
        webbrowser.open(url)


if __name__ == "__main__":
    main()
