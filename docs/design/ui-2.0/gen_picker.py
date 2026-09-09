"""The player-board picker: swap any mark on the card and watch the card, at 1:1.

Options come from the asset library and nowhere else -- one directory per slot, so adding a file
adds an option and no code changes. Anything whose licence is still `unverified` in assets.json is
skipped, which is why the leader portraits do not appear yet.

Every mark on the card sits in a `<g class="pslot" data-slot="...">` at its own centre, so choosing
an option is one innerHTML swap and never a repositioning. Two sizing rules, because the two kinds
of asset normalise differently (see ../hybrid-svg-png.md):

    fit   resources   drawn into the pill's ICON_H box; preserveAspectRatio does the work
    ink   population  drawn at FIG_H of visible ink, width following each figure's own aspect
"""
import base64, io, json, os, pathlib, re, contextlib, sys

HERE = pathlib.Path(__file__).resolve().parent
OUT = str(HERE) + "/"
ASSETS = HERE / "assets"

# The board generator is still a scratch file. Prefer a copy sitting beside this one, so that the
# day it moves into the repo nothing here has to change.
MKR = HERE / "gen_board.py"
if not MKR.exists():
    MKR = pathlib.Path("/tmp/mkR.py")

os.environ.setdefault("TILE_S", "0.80")
os.environ.setdefault("TITLE_SZ", "11.4")
os.environ["OUTNAME"] = "_picker_scratch.html"
NS = {}
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(MKR.read_text(), str(MKR), 'exec'), NS)

ICON_H = NS['gb'].ICON_H
FIG_H = NS['pop'].FIG_H
CARD = NS['player_card'](NS['P'][0])
POP_DEFS = NS['_POP_DEFS']

META = json.loads((ASSETS / "assets.json").read_text())
BLOCKED = {a["src"] for a in META["assets"].values() if a.get("licence") == "unverified"}

ROWS = [("serf", "Serf", "icons/population/serf", "ink"),
        ("acolyte", "Acolyte", "icons/population/acolyte", "ink"),
        ("piety", "Piety", "icons/resources/piety", "fit"),
        ("wheat", "Wheat", "icons/resources/wheat", "fit"),
        ("stone", "Stone", "icons/resources/stone", "fit"),
        ("silver", "Silver", "icons/resources/silver", "fit")]

# Slots the card has but the library cannot yet fill. They are listed rather than omitted so the
# page says WHERE a file goes to become an option -- an empty row is an instruction, a missing row
# is a thing you have to remember.
PENDING = [("Portrait", "portraits/leaders/", "licence unverified"),
           ("Frame", "frames/player_board/", "licence unverified")]


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
    entries = [{"id": "", "label": "NULL", "kind": kind, "asp": 1}]
    for p in files:
        if str(p.relative_to(ASSETS)) in BLOCKED:
            continue
        sid = "opt_%s_%s" % (slot, re.sub(r"\W+", "_", p.stem))
        mk, asp = symbol(sid, p)
        syms.append(mk)
        entries.append({"id": sid, "label": p.stem, "kind": kind, "asp": round(asp, 4)})
    opts[slot] = entries
    btns = []
    for i, e in enumerate(entries):
        if e["id"]:
            H = 34.0; W = H * (e["asp"] if kind == "ink" else 1)
            inner = ('<svg viewBox="0 0 %.1f %.1f" width="%.1f" height="%.1f">'
                     '<use href="#%s" width="%.1f" height="%.1f"/></svg>'
                     % (W, H, W, H, e["id"], W, H))
        else:
            inner = '<span class="nul">&empty;</span>'
        btns.append('<button class="opt" data-slot="%s" data-i="%d" title="%s">%s</button>'
                    % (slot, i, e["label"], inner))
    rows_html.append('<div class="row"><div class="lab">%s</div><div class="opts">%s</div></div>'
                     % (label, "".join(btns)))

rows_html.append('<div class="rule"></div>')
for label, where, why in PENDING:
    rows_html.append('<div class="row pend"><div class="lab">%s</div>'
                     '<div class="opts">no options &mdash; %s. A file dropped in '
                     '<code>assets/%s</code> becomes one.</div></div>' % (label, why, where))
rows_html.append('<div class="row"><div class="lab"></div><div class="opts">'
                 '<button class="reset">Reset to the board</button></div></div>')

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
they line up however differently they are proportioned.</p>
<svg width="0" height="0" style="position:absolute"><defs>%s</defs></svg>%s
<script>
const OPTS=%s, ICON_H=%g, FIG_H=%g;
function mark(o){ if(!o.id) return '';
  const H=(o.kind==='ink')?FIG_H:ICON_H, W=(o.kind==='ink')?H*o.asp:H;
  return '<use href="#'+o.id+'" x="'+(-W/2)+'" y="'+(-H/2)+'" width="'+W+'" height="'+H+'"/>'; }
function apply(slot,i){
  const o=OPTS[slot][i];
  document.querySelectorAll('.pslot[data-slot="'+slot+'"]').forEach(g=>{g.innerHTML=mark(o);});
  document.querySelectorAll('.opt[data-slot="'+slot+'"]').forEach(b=>
    b.setAttribute('aria-pressed', b.dataset.i===String(i)));
}
document.querySelectorAll('.opt').forEach(b=>
  b.onclick=()=>apply(b.dataset.slot, +b.dataset.i));
// open on what the board actually draws: index 1 is ordered to be the board's own mark
function reset(){ Object.keys(OPTS).forEach(s=>{ if(OPTS[s].length>1) apply(s,1); }); }
document.querySelector('.reset').onclick=reset;
reset();
</script>
""" % ("".join(rows_html), CARD, ICON_H, FIG_H, "".join(syms), POP_DEFS,
       json.dumps(opts), ICON_H, FIG_H))

print("written player-board-picker.html")
for slot, label, _r, _k in ROWS:
    print("  %-8s %d options (incl NULL)" % (slot, len(opts[slot])))
