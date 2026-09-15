"""The gothic board picker: the seat, the stones, the turn, the portrait, and how the resource
boxes are drawn.

This does not draw anything. It calls the production assembler to build the board exactly as
`--formats svg` would, then adds a symbol for every candidate asset and gives the page controls that
repoint the relevant `<use>`. The board you look at is therefore the board the assembler makes, not
a second rendering of it that could drift.

    python3 ui/render/gen_picker_2.py --open

Options come from the asset directories and from the assembler's own seat list, so adding a portrait
adds an option and adding a seat colour is a change in one table rather than here:

    assets-gothic/portraits/*.png        the portrait   (portraits/full/ is skipped -- see below)
    assembler SEAT_COLORS                the seat       (drape + dim twin + gemstones, together)
    assembler DISC_FILL_OPACITY          the count's shadow, with that value preselected
    assembler DISC_ICON_INSET            the icon's breathing room, likewise

THE LAST TWO ARE NOT ASSET SWAPS, which is why they arrived late and separately. Everything else
here repoints a `<use>` at a symbol; these are an attribute on four circles and a box on four
icons, and each is ONE CONSTANT in the assembler. They were compared once in two throwaway scripts
that loaded a module by path -- and when that module was deleted, both broke with nothing in the
tree able to say so, one of them still captioning its baseline panel with a design that had been
replaced. A comparison worth keeping belongs where the board already is.

`portraits/full/` holds the 1254 px cuts for the game-start reveal; the board draws the 640 px cuts
beside them, so the picker offers the board's own directory and not the reveal's.

THE TURN CONTROL IS NOT A PREVIEW

Lit and dim are not two boards. Both drapes are inside the one board and the control flips a single
attribute, which is exactly what the play view will do sixty times a game rather than asking for a
new 3.6 MB board each turn. Changing the seat rebuilds nothing either: it repoints the handful of
`<use>` elements a seat decides, at symbols that were embedded up front.

SEAT AND STONES BOTH WRITE THE GEMSTONE SLOT

The seat picks a coloured gemstone overlay; the stones control chooses between that and the shared
black set, which belongs to no seat and has to stay available whichever seat you are on. Two
controls over one `<use>`, so the page keeps them as state and repaints the slot from both -- if
each wrote the slot directly, changing seat would silently drop you back to coloured stones.
"""
import argparse
import base64
import copy
import importlib.util
import json
import pathlib
import xml.etree.ElementTree as ET

HERE = pathlib.Path(__file__).resolve().parent
UI = HERE.parent
SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

# Button swatches, so a seat reads as its colour rather than as its name. Measured means of the
# lit drapes; they are labels for the control, never a source the board draws from.
SWATCH = {"sage": "#7d9b52", "pewter": "#4a6b86", "plum": "#8a5a92", "bone": "#d8cfbe",
          "red": "#a03028", "black": "#2b2b2b"}


def load_assembler(path):
    """Import the production assembler as a module, so the picker cannot drift from it."""
    spec = importlib.util.spec_from_file_location("assembler", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def q(tag):
    return f"{{{SVG_NS}}}{tag}"


def build_board(asm, assets_dir, config_path, seat):
    """The assembler's own build, stopping short of writing a file."""
    config = copy.deepcopy(asm.read_json(config_path))
    for role in ("frame_base", "frame_ornaments", "cloth_lit", "cloth_dim", "gems"):
        config.pop(role, None)
    config["seat"] = seat
    config["turn"] = "lit"
    asm.apply_seat(config)
    layout = asm.read_json(assets_dir / "metadata" / "layout.json")
    root = ET.parse(assets_dir / "template" / "player_board_template.svg").getroot()
    asm.apply_config(root, config, layout, assets_dir)
    asm.embed_assets_once(root, assets_dir)
    asm.assert_no_duplicated_payloads(root)
    return root, config


def add_symbol(asm, defs, symbol_id, asset, preserve="xMidYMid meet"):
    """One more symbol in <defs>, built the way the assembler builds its own."""
    if defs.find(f"*[@id='{symbol_id}']") is not None:
        return symbol_id
    w, h = asm.intrinsic_size(asset)
    sym = ET.SubElement(defs, q("symbol"), {
        "id": symbol_id,
        "viewBox": f"0 0 {asm.fmt(w)} {asm.fmt(h)}",
        "preserveAspectRatio": preserve,
        "data-source": asset.name,
    })
    img = ET.SubElement(sym, q("image"), {
        "x": "0", "y": "0", "width": asm.fmt(w), "height": asm.fmt(h),
        "preserveAspectRatio": "none",
    })
    asm.set_href(img, asm.data_uri(asset))
    return symbol_id


def use_by_role(root, role):
    for node in root.iter(q("use")):
        if node.get("data-asset-role") == role:
            return node
    raise SystemExit(f"no <use> carries data-asset-role={role!r}; did the template change?")


PAGE = """<!doctype html>
<meta charset="utf-8"><title>Pilgrim gothic &mdash; board picker</title><style>
body{margin:0;background:#123d2c;color:#EDE6D6;font:14px/1.55 Georgia,serif;padding:22px 26px 44px}
h1{font-size:19px;margin:0 0 4px}.sub{color:#9FC49A;font-size:12px;margin:0 0 18px;max-width:660px}
.panel{background:#E5D8B9;color:#2A2320;border:1.35px solid #2A2320;border-radius:11px;
  padding:13px 16px 15px;display:inline-block;margin-bottom:20px}
.row{display:flex;align-items:center;gap:12px;margin:9px 0}
.lab{width:74px;font-weight:700;font-size:13px}
.opts{display:flex;gap:8px;flex-wrap:wrap}
button.opt{padding:0 8px;cursor:pointer;background:#EFE6CC;border:1px solid #A89B7E;
  border-radius:8px;color:#2A2320;display:grid;place-items:center;font:12px Georgia,serif;
  min-width:56px;height:60px;gap:3px}
button.opt:hover{background:#F6EFD9}
button.opt[aria-pressed="true"]{border-color:#2A2320;box-shadow:inset 0 0 0 2px #2A2320}
button.opt img{height:44px;width:auto;display:block;border-radius:4px}
button.opt .sw{width:24px;height:24px;border-radius:50%%;border:1px solid #2A2320}
.stage{background:#123d2c}
.note{color:#CFE0C8;font-size:12px;max-width:820px;margin:14px 0 0}
code{background:#1b4b37;padding:1px 5px;border-radius:3px;font-size:11.5px}
</style>
<h1>Pilgrim gothic &mdash; board picker</h1>
<p class="sub">The board is built by the production assembler, then given a symbol per candidate.
Portraits are whatever sits in the asset directory; seats are whatever the assembler knows.</p>
<div class="panel">%(rows)s</div>
<div class="stage">%(board)s</div>
<p class="note">Changing the seat repoints every <code>&lt;use&gt;</code> the seat decides &mdash;
drape, dim drape, gemstones and the acolyte cube &mdash; at symbols already embedded, so the frame
and portrait are never re-sent. The stones control overrides just the gemstones with the shared
black set, and survives a change of seat. The turn control sets one attribute, <code>data-turn</code>, and a stylesheet inside the
board shows the matching drape; that is the whole mechanism the play view needs. The portrait keeps
the template's box and <code>xMidYMid meet</code>, so a replacement with different proportions fits
by its own aspect &mdash; but it fits its <b>canvas</b>, not its visible ink, so artwork with
different transparent margins will look smaller or offset. Do not fix that by moving the template's
coordinates.</p>
<p class="note"><b>Count shadow</b> moves the quarter disc's opacity <i>and</i> the numeral's
colour, because the assembler derives the second from the first &mdash; it darkens the box's own
fill by the opacity and picks parchment or ink by contrast against that. Moving the opacity alone
would show you a numeral the board would never draw. <b>Icon inset</b> is the gap between the icon
and its box on all four sides. Both open on the value the assembler is set to, so whatever is
preselected is what the board actually has; the other buttons are its neighbours. Neither control
writes anything &mdash; changing a constant in <code>gen_board_gothic.py</code> is what makes a
choice real.</p>
<script>
const OPTS = %(opts)s;
const board = document.querySelector('.stage svg');
// Every holder: the drape is one, the portrait's ground is another. Setting only the first is how
// a dim board would keep a lit seat's portrait behind the leader's head.
const turnHolders = [...board.querySelectorAll('[data-turn]')];
const slot = r => board.querySelector('[data-asset-role="' + r + '"]');

// Seat and stones are two settings over one <use>, so they are kept as state and the gemstone slot
// is repainted from both. Letting each control write the slot directly is what would make changing
// seat silently drop you back to coloured stones.
const state = {seat: null, stones: 'colour'};
const bySeat = v => OPTS.seat.find(o => o.value === v);

function paintStones(){
  const black = (OPTS.stones || []).find(o => o.value === 'black');
  const id = (state.stones === 'black' && black) ? black.id : bySeat(state.seat).parts.gems;
  slot('gems').setAttribute('href', '#' + id);
}
function paintSeat(){
  const o = bySeat(state.seat);
  board.setAttribute('data-seat', o.value);
  // Every role the seat decides, whatever they turn out to be -- naming them here is how the
  // acolyte cube got left behind on the previous seat's colour when the stones control arrived.
  // `gems` is the exception: paintStones owns that slot, because two controls write it.
  for (const [r, id] of Object.entries(o.parts))
    if (r !== 'gems') slot(r).setAttribute('href', '#' + id);
  // ...and the fills the seat decides. Both ovals are repainted, not just the visible one: the
  // turn control shows the other a click later and must not find the previous seat's colour.
  const oval = {portrait_background_lit: 'underlay-portrait-lit',
                portrait_background_dim: 'underlay-portrait-dim'};
  for (const [k, id] of Object.entries(oval))
    board.querySelector('[id="' + id + '"]').setAttribute('fill', o.fills[k]);
  const sw = document.getElementById('sw-seatcolour');
  if (sw) sw.style.background = o.swatch;   // the swatch follows whichever seat is selected
  paintStones();
}
function choose(role, i){
  const o = OPTS[role][i];
  if (role === 'turn')          turnHolders.forEach(h => h.dataset.turn = o.value);
  else if (role === 'seat')   { state.seat = o.value; paintSeat(); }
  else if (role === 'stones') { state.stones = o.value; paintStones(); }
  // The disc's opacity AND the numeral's colour, together. The assembler derives the second from
  // the first -- it darkens the box's fill by the opacity and picks parchment or ink by contrast
  // against that -- so moving the opacity alone would show a numeral the board would not draw.
  else if (role === 'shadow') {
    board.querySelectorAll('[data-resource-disc]').forEach(d => {
      d.setAttribute('fill-opacity', o.opacity);
      const t = d.parentNode.querySelector('text');
      if (t) t.setAttribute('fill', o.inks[d.getAttribute('data-resource-disc')]);
    });
  }
  else if (role === 'icon') {
    for (const name of Object.keys(o.geo)) {
      const el = board.querySelector('[data-asset-role="resource:' + name + '"]');
      if (!el) continue;
      for (const [k, v] of Object.entries(o.geo[name])) el.setAttribute(k, v);
    }
  }
  else {
    const el = slot(role);
    if (o.id) { el.setAttribute('href', '#' + o.id); el.style.display = ''; }
    else      { el.style.display = 'none'; }
  }
  document.querySelectorAll('button.opt[data-role="' + role + '"]').forEach(b =>
    b.setAttribute('aria-pressed', b.dataset.i === String(i)));
}
document.querySelectorAll('button.opt').forEach(b =>
  b.onclick = () => choose(b.dataset.role, +b.dataset.i));
// Seat first: everything else is painted relative to it.
['seat', 'stones', 'turn', 'portrait', 'shadow', 'icon'].forEach(r => {
  if (!OPTS[r]) return;
  const i = OPTS[r].findIndex(o => o.on);
  choose(r, i < 0 ? 0 : i);
});
</script>
"""


def thumb(path, px=120):
    """A small preview for the button. Falls back to no image if Pillow is absent."""
    try:
        from PIL import Image
    except ImportError:
        return None
    import io
    im = Image.open(path).convert("RGBA")
    im.thumbnail((px, px), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


# What the panel calls each control. Only the two that are not one word need saying.
ROW_LABELS = {"shadow": "Count shadow", "icon": "Icon inset"}


def resource_boxes(asm, root):
    """Each resource box's coloured field, by name: origin, size and fill, read from the board.

    Every number below comes from here rather than from a constant, for the reason the assembler
    gives about the same numbers: a box's height written into this file is a second statement of
    something the template already owns, and the experiment script this control replaces had
    exactly that -- a hard-coded 179.0 it fell back to when the template's shape changed under it.
    """
    out = {}
    for name in asm.RESOURCE_NAMES:
        grp = root.find(".//%s[@id='resource-%s']" % (q("g"), name))
        if grp is None:
            continue
        rects = [c for c in grp if c.tag == q("rect")]
        if not rects:
            continue
        box = rects[0]
        out[name] = {"x": float(box.get("x")), "y": float(box.get("y")),
                     "w": float(box.get("width")), "h": float(box.get("height")),
                     "fill": box.get("fill") or "#808080"}
    return out


def shadow_options(asm, root, boxes, parchment):
    """How dark the count's corner disc is, with the numeral colour DERIVED for every choice.

    The assembler does not set the numeral beside the disc and hope they match -- it darkens the
    box's own fill by the disc's opacity and then picks parchment or ink by contrast against that.
    So a control that changed only the opacity would show a numeral the board would never draw,
    and it would be wrong in the exact case the derivation exists for: a dark numeral on a dark
    ground. The colour is therefore computed here, per resource, by calling the assembler's own
    darken() and contrast() rather than a copy of them.

    Returns None when the board has no discs -- `resource_layout: "strip"` is a supported setting
    and this control has nothing to act on there.
    """
    if not any(c.get("data-resource-disc") for c in root.iter(q("circle"))):
        return None
    shipped = float(asm.DISC_FILL_OPACITY)
    entries = []
    for opacity in sorted({0.20, 0.32, 0.45, shipped, 0.75}):
        inks = {}
        for name, box in boxes.items():
            ground = (asm.darken(str(box["fill"]), opacity)
                      if asm.DISC_FILL == "#000000" else asm.DISC_FILL)
            inks[name] = (parchment if asm.contrast(parchment, ground) >= asm.contrast(asm.INK, ground)
                          else asm.INK)
        entries.append({"value": "%.2f" % opacity, "label": "%d%%" % round(opacity * 100),
                        "opacity": opacity, "inks": inks,
                        "on": abs(opacity - shipped) < 1e-9})
    return entries


def icon_options(asm, boxes):
    """How much breathing room the icon leaves inside its box, in the board's own units.

    The geometry is precomputed per option rather than left to arithmetic in the page, so the
    control cannot disagree with the assembler about where a box starts.
    """
    if not boxes:
        return None
    shipped = float(asm.DISC_ICON_INSET)
    entries = []
    for inset in sorted({0.0, shipped, 20.0, 30.0}):
        geo = {name: {"x": b["x"] + inset, "y": b["y"] + inset,
                      "width": b["w"] - 2 * inset, "height": b["h"] - 2 * inset}
               for name, b in boxes.items()}
        entries.append({"value": "%g" % inset, "label": "%g px" % inset, "geo": geo,
                        "on": abs(inset - shipped) < 1e-9})
    return entries


def row(role, entries):
    btns = []
    for i, e in enumerate(entries):
        if e.get("thumb"):
            inner = '<img src="%s" alt="">' % e["thumb"]
        elif e.get("swatch"):
            inner = ('<span class="sw"%s style="background:%s"></span><span>%s</span>'
                     % (' id="%s"' % e["swatch_id"] if e.get("swatch_id") else "",
                        e["swatch"], e["label"]))
        else:
            inner = e["label"]
        btns.append('<button class="opt" data-role="%s" data-i="%d" title="%s">%s</button>'
                    % (role, i, e["label"], inner))
    return ('<div class="row"><div class="lab">%s</div><div class="opts">%s</div></div>'
            % (ROW_LABELS.get(role, role.capitalize()), "".join(btns)))


def main():
    ap = argparse.ArgumentParser(description="Swap assets on the gothic player board.")
    ap.add_argument("--assets-dir", default=str(UI / "assets-gothic"))
    ap.add_argument("--assembler", default=None, help="path to gen_board_gothic.py")
    ap.add_argument("--config", default=None)
    ap.add_argument("--output", default=None)
    ap.add_argument("--board-width", type=int, default=1000,
                    help="how wide to draw the board on the page; the viewBox is unchanged")
    ap.add_argument("--open", action="store_true")
    args = ap.parse_args()

    assets_dir = pathlib.Path(args.assets_dir).expanduser().resolve()
    asm_path = pathlib.Path(args.assembler) if args.assembler else HERE / "gen_board_gothic.py"
    if not asm_path.is_file():
        raise SystemExit(f"assembler not found: {asm_path} (use --assembler)")
    asm = load_assembler(asm_path)

    config_path = pathlib.Path(args.config) if args.config else \
        assets_dir / "production_test_config.json"
    start_seat = str(asm.read_json(config_path).get("seat") or asm.SEAT_COLORS[0])
    root, config = build_board(asm, assets_dir, config_path, start_seat)

    defs = root.find(q("defs"))
    opts = {}

    # Seats. One button carries all three of the assets a seat colour decides, so the drape, its
    # dim twin and the gemstones can never end up disagreeing about which seat this is.
    entries = []
    for seat in asm.SEAT_COLORS:
        parts = {}
        for role, rel in asm.seat_layers(seat).items():
            if role in ("frame_base", "frame_ornaments"):
                continue        # colour-neutral: every seat draws the same file
            parts[role] = add_symbol(asm, defs, f"opt_{role}_{seat}", assets_dir / rel)
        # The portrait's ground is a FILL, not an asset, so it cannot ride on `parts` -- those are
        # all <use> targets. It travels on the same button all the same, because it is one more
        # thing the seat decides and the whole point of this button is that they move together.
        entries.append({"value": seat, "label": seat, "parts": parts,
                        "fills": asm.seat_fills(seat),
                        "swatch": SWATCH.get(seat, "#8a7f62"), "on": seat == start_seat})
    opts["seat"] = entries

    # Stones. The seat decides which coloured overlay exists; this decides whether the board wears
    # it or the black set. Black is a shared asset, not a seat's, which is exactly why it is a
    # second control rather than a fifth seat: it has to be available to whichever seat you are on.
    entries = [{"value": "colour", "label": "seat colour", "swatch": SWATCH.get(start_seat),
                "swatch_id": "sw-seatcolour", "on": True}]
    black = assets_dir / "frames" / "stones_black.png"
    if black.is_file():
        entries.append({"value": "black", "label": "black",
                        "id": add_symbol(asm, defs, "opt_gems_black", black),
                        "swatch": SWATCH["black"], "on": False})
    if len(entries) > 1:
        opts["stones"] = entries

    opts["turn"] = [
        {"value": "lit", "label": "to play", "on": True},
        {"value": "dim", "label": "waiting", "on": False},
    ]

    # Portraits: the board's own directory. `full/` is the reveal cut, not a board candidate.
    entries = []
    for p in sorted(assets_dir.joinpath("portraits").glob("*.png")):
        sid = add_symbol(asm, defs, "opt_portrait_" + p.stem, p)
        entries.append({"id": sid, "label": p.stem.replace("leader_", "").replace("_", " "),
                        "thumb": thumb(p), "on": p.name == pathlib.Path(config["portrait"]).name})
    if not entries:
        raise SystemExit(f"no portraits found in {assets_dir / 'portraits'}")
    opts["portrait"] = entries

    # The two settings the resource boxes are drawn by. Neither is an asset, so neither can ride on
    # a <use> the way everything above does -- they are an attribute on four circles and a box on
    # four icons. Both are one constant in the assembler, and both were compared once in throwaway
    # scripts that then broke silently; the comparison belongs where the board already is.
    boxes = resource_boxes(asm, root)
    shadow = shadow_options(asm, root, boxes,
                            str(config.get("resource_value_fill", "#ead8b4")))
    if shadow:
        opts["shadow"] = shadow
    icon = icon_options(asm, boxes)
    if icon:
        opts["icon"] = icon

    # The swappable slots must be addressable by role after the assembler has rewritten them.
    for role in ("cloth_lit", "cloth_dim", "gems", "portrait"):
        use_by_role(root, role)

    root.set("width", str(args.board_width))
    root.attrib.pop("height", None)
    svg = ET.tostring(root, encoding="unicode")

    rows = "".join(row(role, opts[role])
                   for role in ("seat", "stones", "turn", "portrait", "shadow", "icon")
                   if role in opts)
    page = PAGE % {"rows": rows, "board": svg, "opts": json.dumps(opts)}

    out = pathlib.Path(args.output) if args.output else \
        UI / "generated" / "gothic-board-picker.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print("written %s  (%.1f MB)" % (out, out.stat().st_size / 1024 / 1024))
    for role in opts:
        print("  %-9s %d options" % (role, len(opts[role])))
    url = out.resolve().as_uri()
    print("\n%s" % url)
    if args.open:
        import webbrowser
        webbrowser.open(url)


if __name__ == "__main__":
    main()
