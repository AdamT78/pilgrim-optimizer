"""The player-board picker: swap any mark on the card and watch the card, at 1:1.

Options come from the asset library and nowhere else -- one directory per slot, so adding a file
adds an option and no code changes. Anything whose licence is still `unverified` in assets.json is
skipped, so an asset that has not been cleared cannot reach a page by accident.

Every mark on the card sits in a `<g class="pslot" data-slot="...">` at its own centre, so choosing
an option is one innerHTML swap and never a repositioning. Two sizing rules, because the two kinds
of asset normalise differently (see ../hybrid-svg-png.md):

    fit   resources   drawn into the pill's ICON_H box; preserveAspectRatio does the work
    ink   population  drawn at FIG_H of visible ink, width following each figure's own aspect
    disc  portrait    fills the portrait circle, clipped to it
    frame overlay     placed by its own ring so that ring lands on the portrait circle
"""
import base64, io, json, os, pathlib, re, contextlib, sys

HERE = pathlib.Path(__file__).resolve().parent      # ui/render
UI = HERE.parent                                    # ui
OUT = str(UI / "generated") + "/"
ASSETS = UI / "assets"
pathlib.Path(OUT).mkdir(parents=True, exist_ok=True)

MKR = HERE / "gen_board.py"

os.environ.setdefault("TILE_S", "0.80")
os.environ.setdefault("TITLE_SZ", "11.4")
os.environ["OUTNAME"] = "_picker_scratch.html"
# `__file__` has to be seeded: the board generator locates its own inputs relative to itself, and
# an exec namespace does not get one for free.
NS = {"__file__": str(MKR), "__name__": "gen_board"}
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(MKR.read_text(), str(MKR), 'exec'), NS)

ICON_H = NS['gb'].ICON_H
FIG_H = NS['pop'].FIG_H
PR = NS['PR']                      # the portrait circle's radius, in card units
PX, PY = NS['PX'], NS['PY']
NS['FRAME_ROOM'] = True            # a frame overhangs the card; give the viewBox room for it
CARD = NS['player_card'](NS['P'][0])
POP_DEFS = NS['_POP_DEFS']

META = json.loads((ASSETS / "assets.json").read_text())
BLOCKED = {a["src"] for a in META["assets"].values() if a.get("licence") == "unverified"}

ROWS = [("portrait", "Portrait", "portraits/leaders", "disc"),
        ("frame", "Frame", "frames/player_board", "frame"),
        ("serf", "Serf", "icons/population/serf", "ink"),
        ("acolyte", "Acolyte", "icons/population/acolyte", "ink"),
        ("piety", "Piety", "icons/resources/piety", "fit"),
        ("wheat", "Wheat", "icons/resources/wheat", "fit"),
        ("stone", "Stone", "icons/resources/stone", "fit"),
        ("silver", "Silver", "icons/resources/silver", "fit")]



def placement(kind, asp, rel):
    """How big a mark is drawn, and where its slot sits -- both in card units.

    Each kind measures itself differently, and the differences are the point:

        fit     a resource fills the pill's icon box, aspect preserved by the viewport
        ink     a population figure is drawn at a fixed height of VISIBLE ink, width following
        disc    a portrait fills the portrait circle and is clipped to it
        frame   a frame is placed by its portrait OPENING, not by its own box, so that its ring
                lands on the card's portrait however the frame is proportioned
    """
    if kind == "ink":
        return FIG_H * asp, FIG_H, None
    if kind == "disc":
        return 2.0 * PR, 2.0 * PR, None
    if kind == "frame":
        return frame_place(rel, "ring")
    return ICON_H, ICON_H, None


# What the card's frame has to contain, in card units: the panel rect and the counts under it.
CARD_TOP, CARD_BOT = 16.0, 128.0


def frame_place(rel, how):
    """Size and place a frame two ways, because one frame cannot do both.

    A frame of this shape has two openings, and their proportions are fixed relative to each
    other. The card's are not the same proportions, so:

        ring    the ring lands exactly on the portrait circle -- and the panel opening comes out
                47 units short of the card, cutting the pills and their counts
        panel   the panel opening contains the card -- which needs 1.73x more scale, making the
                frame 597 units wide against a 316-unit card and pushing the ring off it entirely

    Only "ring" is offered. "panel" stays here because it is the measurement that settles the
    question, and because a differently proportioned frame might make it the better one.
    """
    meta = next(a for a in META["assets"].values() if a["src"] == rel)
    cx, cy, r = meta["openingCirclePx"]
    px0, py0, pw, ph = meta["panelOpeningPx"]
    cw, ch = meta["canvasPx"]
    k = PR / r if how == "ring" else (CARD_BOT - CARD_TOP) / ph
    w, h = cw * k, ch * k
    if how == "ring":
        ox, oy = PX - cx * k, PY - cy * k
    else:
        # centre the panel opening on the card's own rect
        ox = (0 + 316.0) / 2.0 - (px0 + pw / 2.0) * k
        oy = (CARD_TOP + CARD_BOT) / 2.0 - (py0 + ph / 2.0) * k
    return w, h, (ox + w / 2.0, oy + h / 2.0)


def symbol(sid, path):
    """A symbol plus its aspect. SVG keeps its own viewBox; PNG gets its canvas as one."""
    if path.suffix == ".png":
        raw = path.read_bytes()
        w = int.from_bytes(raw[16:20], "big"); h = int.from_bytes(raw[20:24], "big")
        body = ('<image href="data:image/png;base64,%s" x="0" y="0" width="%d" height="%d"/>'
                % (base64.b64encode(raw).decode(), w, h))
        vb = "0 0 %d %d" % (w, h)
    else:
        s = path.read_text()
        m = re.search(r'viewBox="([^"]+)"', s)
        vb = m.group(1) if m else "0 0 16 16"
        body = s[s.index('>', s.index('<svg')) + 1:s.rindex('</svg>')]
        w, h = [float(v) for v in vb.split()[2:4]]
    return '<symbol id="%s" viewBox="%s">%s</symbol>' % (sid, vb, body), w / h


# The picker must OPEN on what the board actually draws, so the first click is a comparison and
# not a correction. For population that file is named in gen_population_marks.DEFAULT; for the
# resources it is the generator's own mark, which carries the `pilgrim_` prefix by convention.
ON_BOARD = {k: v.split("/")[-1] for k, v in NS['pop'].DEFAULT.items()}


def _order(p):
    """Board default first, then the rest alphabetically."""
    return (0 if p.name == ON_BOARD.get(slot, "") or p.stem == "pilgrim_" + slot else 1, p.name)


syms, opts, rows_html = [], {}, []
for slot, label, rel, kind in ROWS:
    d = ASSETS / rel
    files = sorted((p for p in d.glob("*") if p.suffix in (".svg", ".png")), key=_order) \
        if d.is_dir() else []
    entries = [{"id": "", "label": "NULL", "kind": kind, "asp": 1, "w": 0, "h": 0, "at": None}]
    for p in files:
        if str(p.relative_to(ASSETS)) in BLOCKED:
            continue
        sid = "opt_%s_%s" % (slot, re.sub(r"\W+", "_", p.stem))
        mk, asp = symbol(sid, p)
        syms.append(mk)
        rel_p = str(p.relative_to(ASSETS))
        if kind == "frame":
            # "panel" is kept in frame_place and deliberately NOT offered: sizing this frame's
            # panel to contain the card makes the whole frame 597 units wide against a 316-unit
            # card, with the ring far off the left edge. It is not a candidate, it is the proof
            # that the ring placement is the only one this artwork supports.
            for how in ("ring",):
                w, h, at = frame_place(rel_p, how)
                entries.append({"id": sid, "label": "%s (%s)" % (p.stem, how), "kind": kind,
                                "asp": round(asp, 4), "w": round(w, 3), "h": round(h, 3),
                                "at": [round(at[0], 3), round(at[1], 3)], "how": how})
            continue
        w, h, at = placement(kind, asp, rel_p)
        entries.append({"id": sid, "label": p.stem, "kind": kind, "asp": round(asp, 4),
                        "w": round(w, 3), "h": round(h, 3),
                        "at": [round(at[0], 3), round(at[1], 3)] if at else None})
    opts[slot] = entries
    btns = []
    for i, e in enumerate(entries):
        if e["id"]:
            if kind == "frame":
                H = 22.0; W = H * e["asp"]           # wide: show the whole frame, not a crop
            elif kind == "ink":
                H = 34.0; W = H * e["asp"]
            else:
                H = W = 34.0
            clip = ('<clipPath id="sw%s"><circle cx="%.1f" cy="%.1f" r="%.1f"/></clipPath>'
                    % (e["id"], W / 2, H / 2, W / 2)) if kind == "disc" else ""
            g = ('<g clip-path="url(#sw%s)">' % e["id"]) if clip else "<g>"
            inner = ('<svg viewBox="0 0 %.1f %.1f" width="%.1f" height="%.1f"><defs>%s</defs>%s'
                     '<use href="#%s" width="%.1f" height="%.1f"/></g></svg>'
                     % (W, H, W, H, clip, g, e["id"], W, H))
        else:
            inner = '<span class="nul">&empty;</span>'
        btns.append('<button class="opt" data-slot="%s" data-i="%d" title="%s">%s</button>'
                    % (slot, i, e["label"], inner))
    rows_html.append('<div class="row"><div class="lab">%s</div><div class="opts">%s</div></div>'
                     % (label, "".join(btns)))

rows_html.append('<div class="rule"></div>')
rows_html.append('<div class="row"><div class="lab"></div><div class="opts">'
                 '<button class="reset">Reset to the board</button></div></div>')

# What the board itself draws in each slot: its own mark, except the frame, which it does not
# draw at all. "Reset to the board" has to mean the board, not the first thing in the directory.
DEFAULTS = {slot: (0 if slot == "frame" else min(1, len(opts[slot]) - 1)) for slot in opts}

pathlib.Path(OUT + "player-board-picker.html").write_text("""<!doctype html>
<meta charset="utf-8"><title>Pilgrim &mdash; player board picker</title><style>
body{margin:0;background:#2F5237;color:#EDE6D6;font:14px/1.5 Georgia,serif;padding:24px 28px 50px}
h1{font-size:20px;margin:0 0 4px}.sub{color:#9FC49A;font-size:12px;margin:0 0 20px}
.wrap{display:flex;gap:34px;align-items:flex-start;flex-wrap:wrap}
.panel{background:#E5D8B9;color:#2A2320;border:1.35px solid #2A2320;border-radius:11px;
  padding:14px 16px 16px;width:430px}
.row{display:flex;align-items:center;gap:12px;margin:11px 0}
.lab{width:66px;font-weight:700;font-size:13px}
.opts{display:flex;gap:8px;flex-wrap:wrap}
.opt{width:52px;height:52px;padding:0;display:grid;place-items:center;cursor:pointer;
  background:#EFE6CC;border:1px solid #A89B7E;border-radius:8px;color:#2A2320}
.opt:hover{background:#F6EFD9}
.opt[aria-pressed="true"]{border-color:#2A2320;box-shadow:inset 0 0 0 2px #2A2320}
.nul{color:#8A7F62;font-size:19px}
.rule{height:1px;background:#A89B7E;opacity:.5;margin:16px 0 4px}
.pend .opts{font-size:12px;color:#6E6455;font-style:italic;max-width:340px;display:block}
.pend code{font-style:normal;font-size:11.5px;background:#EFE6CC;padding:1px 4px;border-radius:3px}
.reset{font:12px Georgia,serif;padding:5px 11px;cursor:pointer;color:#2A2320;
  background:#EFE6CC;border:1px solid #A89B7E;border-radius:6px}
.stage{background:#2F5237;padding:2px}
.note{color:#CFE0C8;font-size:12px;max-width:430px;margin:16px 0 0}
b{color:#F0E7D2}
</style>
<h1>Player board &mdash; asset picker</h1>
<p class="sub">The card is 1:1, exactly as the game draws it. Options come from the asset library
only; nothing whose licence is unverified is offered.</p>
<div class="wrap">
  <div class="panel">%s</div>
  <div class="stage">%s</div>
</div>
<p class="note">Every mark sits in its own centred slot, so a choice is a swap and never a
reposition. Resources are fitted into the pill's %g-unit box; population figures are drawn at
%g units of <b>visible ink</b>, each one's width following its own aspect &mdash; which is why
they line up however differently they are proportioned. The portrait fills the disc and is clipped
to it. The frame is placed by its own <b>ring</b>, not its box, so the ring lands on the portrait
circle whatever the frame's proportions &mdash; and at that scale its panel opening comes out
47 units shorter than the card, which is why the counts sit below the lower rail.</p>
<svg width="0" height="0" style="position:absolute"><defs>%s</defs></svg>%s
<script>
const OPTS=%s, DEFAULTS=%s, ICON_H=%g, FIG_H=%g;
function mark(o){ if(!o.id) return '';
  return '<use href="#'+o.id+'" x="'+(-o.w/2)+'" y="'+(-o.h/2)+'" width="'+o.w
       + '" height="'+o.h+'"/>'; }
function apply(slot,i){
  const o=OPTS[slot][i];
  document.querySelectorAll('.pslot[data-slot="'+slot+'"]').forEach(g=>{
    // A frame is positioned by its own opening, so its slot moves with the choice. Every other
    // slot is fixed by the card and only its contents change.
    if(o.at) g.setAttribute('transform','translate('+o.at[0]+' '+o.at[1]+')');
    else if(o.kind==='frame') g.removeAttribute('transform');
    g.innerHTML=mark(o);});
  document.querySelectorAll('.opt[data-slot="'+slot+'"]').forEach(b=>
    b.setAttribute('aria-pressed', b.dataset.i===String(i)));
}
document.querySelectorAll('.opt').forEach(b=>
  b.onclick=()=>apply(b.dataset.slot, +b.dataset.i));
// open on what the board actually draws: index 1 is ordered to be the board's own mark
function reset(){ Object.keys(OPTS).forEach(s=>apply(s, DEFAULTS[s])); }
document.querySelector('.reset').onclick=reset;
reset();
</script>
""" % ("".join(rows_html), CARD, ICON_H, FIG_H, "".join(syms), POP_DEFS,
       json.dumps(opts), json.dumps(DEFAULTS), ICON_H, FIG_H))

OUT_PATH = pathlib.Path(OUT + "player-board-picker.html")
print("written %s" % OUT_PATH.name)
for slot, label, _r, _k in ROWS:
    print("  %-8s %d options (incl NULL)" % (slot, len(opts[slot])))

# A path is not a thing you can click. Print the URL, and open it when asked -- `webbrowser`
# rather than `open`, so this works the same on a mac, a Linux box and a CI container that
# quietly does nothing.
URL = OUT_PATH.resolve().as_uri()
print("\n%s" % URL)
if "--open" in sys.argv or os.environ.get("OPEN_PICKER"):
    import webbrowser
    webbrowser.open(URL)
