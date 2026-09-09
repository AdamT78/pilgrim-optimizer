"""Market iteration: the twelve building CARDS become the twelve building HEX TILES, and the four
pilgrimage sites join them.

Same 1193 x 127 footprint the current strip occupies, so a finished variant drops straight in.
Everything comes from the same seeded setup as the map (seed 20260730), so a name in the market is
the same name on the map's edge, on the same round.
"""
import math, sys
sys.path.insert(0, '.')
from xml.sax.saxutils import escape

from pilgrim.setup.generator import generate_setup_scenario
from tools.ui_debug.render_buildings import (
    HEX_RADIUS as S, TILE_NAME_FONT_SIZE, TILE_NAME_LINE_HEIGHT, TILE_NAME_CENTER_Y_OFFSET,
    load_building_catalog, palette_for, tile_text_lines, hex_points,
)
from tools.ui_debug.render_pilgrimage_sites import (
    SITE_FILL, SITE_STROKE, render_pilgrimage_site_contents,
    load_pilgrimage_sites, site_by_index,
)

SEED, NOW = 20260730, 12                     # the board's own round, from the action box
BOX_W, BOX_H = 1193.0, 127.0                 # the strip the current market occupies

sc = generate_setup_scenario(4, SEED)
tl = sc["setup_metadata"]["setup_timeline"]
cat = load_building_catalog()
by_id = {b.get("id", b["name"].lower().replace(" ", "_")): b for b in cat["buildings"]}
sites = load_pilgrimage_sites()

# one chronological list of the sixteen occupied rounds
items = []
for level, entries in tl["building_live_rounds"].items():
    for bid, rnd in entries.items():
        items.append({"round": rnd, "kind": "building", "b": by_id[bid],
                      "level": int(level.rsplit("_", 1)[1])})
# `pilgrimage_rounds_from_rolls` normalises so site_1 is ALWAYS round 1 -- that is not a season
# end, it is where the ship starts. The game runs the full 26 rounds, one lap of the map's edge,
# and the lap closing IS the fourth season end. So site_1's marker is moved to round 26.
LAST_ROUND = 26
for key, rnd in tl["pilgrimage_rounds"].items():
    n = int(key.rsplit("_", 1)[1])
    items.append({"round": LAST_ROUND if n == 1 else rnd, "kind": "site", "n": n})
items.sort(key=lambda i: i["round"])

# state: the board is on round 12, so anything later has not woken yet. Two level-1 buildings are
# already hired, which is what the current market's "gone" tiles say and what carries a seat colour.
HIRED = {"infirmary": "#B7382E", "mint": "#D9B33B"}
for it in items:
    late = it["round"] > NOW
    it["state"] = "future" if late else "live"
    if it["kind"] == "building":
        bid = next(k for k, v in by_id.items() if v is it["b"])
        if bid in HIRED and not late:
            it["state"], it["owner"] = "gone", HIRED[bid]

APO = S * math.sin(math.radians(60.0))       # flat-to-flat half-height

def hexpath(x, y):
    pts = hex_points(x, y)
    return "M %.2f,%.2f " % pts[0] + " ".join("L %.2f,%.2f" % p for p in pts[1:]) + " Z"

def tile(it, x, y):
    """One hex, its contents, and the round it wakes on -- in the upper half the tile leaves free."""
    out = []
    if it["kind"] == "building":
        pal = palette_for(it["b"])
        fill, stroke = pal.fill, pal.stroke
    else:
        fill, stroke = SITE_FILL, SITE_STROKE
    out.append('<path d="%s" fill="%s" stroke="%s" stroke-width="2.5" stroke-linejoin="round"/>'
               % (hexpath(x, y), fill, stroke))
    if it["kind"] == "building":
        for i, line in enumerate(tile_text_lines(it["b"])):
            out.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-family="Helvetica,'
                       ' Arial, sans-serif" font-size="%g" font-weight="600" fill="%s">%s</text>'
                       % (x, y + TILE_NAME_CENTER_Y_OFFSET + i * TILE_NAME_LINE_HEIGHT,
                          TILE_NAME_FONT_SIZE, stroke, escape(line)))
        # the round it wakes on, in the free upper half
        if it["state"] != "gone":
            out.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-family="Helvetica,'
                       ' Arial, sans-serif" font-size="17" font-weight="700" fill="%s"'
                       ' opacity=".55">%d</text>' % (x, y - 14, stroke, it["round"]))
    else:
        # the site's own values (its VP star, its piety and stone) say which of the three site
        # variants it is, which is not the market's business: the market says WHEN. So the tile
        # keeps only its colour, and takes its words where a building takes its name.
        for i, line in enumerate(("Season", "End")):
            out.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-family="Helvetica,'
                       ' Arial, sans-serif" font-size="%g" font-weight="600" fill="%s">%s</text>'
                       % (x, y + TILE_NAME_CENTER_Y_OFFSET + i * TILE_NAME_LINE_HEIGHT,
                          TILE_NAME_FONT_SIZE, SITE_STROKE, line))
        out.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-family="Helvetica, Arial,'
                   ' sans-serif" font-size="17" font-weight="700" fill="%s" opacity=".55">%d</text>'
                   % (x, y - 14, SITE_STROKE, it["round"]))
    g = "".join(out)
    if it["state"] == "future":
        # not woken yet: the tile fades toward the panel it sits on rather than going grey, so a
        # level's colour is still readable in a tile that has not arrived
        return '<g opacity=".38">%s</g>' % g
    if it["state"] == "gone":
        # hired: the seat that took it takes the round badge's place, because a building that has
        # been taken no longer has a round anyone is waiting for
        return (g + '<circle cx="%.1f" cy="%.1f" r="12" fill="%s" stroke="#2A2320" '
                'stroke-width="1.4"/>' % (x, y - 19, it["owner"]))
    return g

def svg(body, w, h, k, tx=0.0, ty=0.0):
    return ('<svg class="strip" viewBox="0 0 %.1f %.1f" width="%.1f" height="%.1f">'
            '<g transform="translate(%.2f %.2f) scale(%.4f)">%s</g></svg>'
            % (BOX_W, BOX_H, BOX_W, BOX_H, tx, ty, k, body))

# ---- A: the round track unrolled -- sixteen hexes interlocked, exactly as they sit on the map --
def variant_a():
    n = len(items); pitch = 1.5 * S
    w = pitch * (n - 1) + 2 * S
    h = 2 * APO + APO                                   # two rows of a honeycomb
    k = min(BOX_W / w, BOX_H / h)
    body = "".join(tile(it, S + i * pitch, APO + (APO if i % 2 else 0))
                   for i, it in enumerate(items))
    return svg(body, w, h, k, (BOX_W - w * k) / 2, (BOX_H - h * k) / 2), k

# ---- B: a straight row, hexes point to point -----------------------------------------------
def variant_b(gap=7.0):
    n = len(items); pitch = 2 * S + gap
    w = pitch * (n - 1) + 2 * S
    h = 2 * APO
    k = min(BOX_W / w, BOX_H / h)
    body = "".join(tile(it, S + i * pitch, APO) for i, it in enumerate(items))
    return svg(body, w, h, k, (BOX_W - w * k) / 2, (BOX_H - h * k) / 2), k

# ---- C: four seasons, each led by its pilgrimage site --------------------------------------
def variant_c(sep=46.0):
    pitch = 1.5 * S
    xs, x = [], S
    for i, it in enumerate(items):
        if i and items[i - 1]["kind"] == "site":
            x += sep                      # the break falls after the season end, not before it
        xs.append(x); x += pitch
    w = xs[-1] + S
    h = 2 * APO + APO
    k = min(BOX_W / w, BOX_H / h)
    body = "".join(tile(it, xs[i], APO + (APO if i % 2 else 0)) for i, it in enumerate(items))
    return svg(body, w, h, k, (BOX_W - w * k) / 2, (BOX_H - h * k) / 2), k

VARIANTS = [
    ("A &mdash; the round track unrolled", variant_a,
     "Sixteen hexes interlocked the way they sit on the map's edge, in round order. The four "
     "season ends break the ribbon by themselves, so nothing else has to mark one."),
    ("B &mdash; a straight row", variant_b,
     "Flat-top hexes cannot interlock along a row, so they meet point to point. Reads as beads "
     "rather than as a track, and the name pays for it."),
    ("C &mdash; four seasons, broken after each end", variant_c,
     "A's ribbon cut after each season end. The break is explicit; the tiles pay a little size for it."),
]

rows = []
for title, fn, note in VARIANTS:
    s, k = fn()
    rows.append('<section><h2>%s</h2><p>%s <b>Hex radius %.1f px, name %.1f px.</b></p>'
                '<div class="frame">%s</div></section>'
                % (title, note, S * k, TILE_NAME_FONT_SIZE * k, s))

html = """<!doctype html><meta charset="utf-8"><title>Pilgrim &mdash; market as hex tiles</title>
<style>
body{margin:0;background:#2F5237;color:#EDE6D6;font:14px/1.5 Georgia,serif;padding:26px 30px 60px}
h1{font-size:22px;margin:0 0 4px}
h1+p{margin:0 0 26px;color:#BBCBB6;max-width:1193px}
section{margin:0 0 30px}
h2{font-size:16px;margin:0 0 4px;font-weight:600}
section>p{margin:0 0 9px;color:#BBCBB6;max-width:1193px;font-size:13px}
section>p b{color:#EDE6D6;font-weight:600}
.frame{width:1193px;height:127px;background:#E5D8B9;border-radius:10px;outline:1px dashed rgba(237,230,214,.35)}
.strip{display:block}
.foot{color:#9FB39B;font-size:12.5px;max-width:1193px;margin-top:26px}
</style>
<h1>The market, as hex tiles</h1>
<p>The twelve building cards become the twelve building tiles, and the four pilgrimage sites join
them. Every name, level and round is the same seeded setup the map is drawn from (seed %d), so a
tile here is the same tile on the map's edge. Each frame is the <b>1193 &times; 127</b> the current
strip occupies, so a chosen variant drops straight in.</p>
%s
<p class="foot">The board is on round 12: tiles later than that are dimmed because they have not
woken yet, and Infirmary and Mint carry the seat that hired them. A season end is where the Alms
Table scores and resets. The generator always puts site&nbsp;1 on round&nbsp;1, which is where the
<i>ship starts</i> rather than a season ending, so that marker is shown at <b>round 26</b> instead
&mdash; the ship closing its lap of the map is the fourth season end and the end of the game.</p>
""" % (SEED, "".join(rows))

open('/home/claude/ui-2.0/market-hex-tiles.html', 'w').write(html)
print("written market-hex-tiles.html")
for title, fn, _ in VARIANTS:
    s, k = fn()
    print("  %-46s k=%.4f  hex r=%.1f px  name=%.1f px" % (title.replace('&mdash;','-'), k, S*k, TILE_NAME_FONT_SIZE*k))
