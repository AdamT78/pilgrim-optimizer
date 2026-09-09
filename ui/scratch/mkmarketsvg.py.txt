"""Foot bar for ownership, and the question underneath it: USED and DONATED are not the same kind
of fact, so they should not be the same kind of mark.

`TurnProgress.used_buildings` is cleared by `advance_turn` on every turn boundary, and it is keyed
by BUILDING, not by player -- so "used" means "spent for this turn, by whoever spent it", and it
comes back. `PlayerBoardSlots.donated_buildings` never comes back. One is a thing laid on a tile
and taken off again; the other is what the tile now is.
"""
import math, pathlib, sys
sys.path.insert(0, '.')
from xml.sax.saxutils import escape

from pilgrim.setup.generator import generate_setup_scenario
from tools.ui_debug.render_buildings import (
    HEX_RADIUS as S, TILE_NAME_FONT_SIZE, TILE_NAME_LINE_HEIGHT, TILE_NAME_CENTER_Y_OFFSET,
    load_building_catalog, tile_text_lines, hex_points,
)
from tools.ui_debug.render_pilgrimage_sites import SITE_FILL

SEED, NOW, LAST = 20260730, 12, 26
# The table is now only as wide as it needs to be. Its left and right margins are equal and both
# are the Alms Table's own title inset -- which is what puts "Buildings" exactly above the first
# hex tile rather than adrift in a field of parchment.
BOX_H = 143.68     # the head panels' shared height

# The Alms Table's frame, in ITS units -- outer rect rx 12 stroke 1.4, an inner keyline inset 6 at
# rx 7 stroke 1.1 opacity .30, and a 15px Georgia title at (16, 26). That svg renders at 339.4 for
# a 352 viewBox, so everything is multiplied by 0.9642 to come out the same size on screen here,
# where a unit is a pixel.
_AK = 339.4 / 352.0
FRAME_RX, FRAME_SW = 12 * _AK, 1.4 * _AK
KEY_IN, KEY_RX, KEY_SW = 6 * _AK, 7 * _AK, 1.1 * _AK
TITLE_SIZE, TITLE_X, TITLE_Y = 15 * _AK, 16 * _AK, 26 * _AK
TITLE = "Buildings"
MARGIN = TITLE_X                                  # 15.4: equal both sides, and the title's own x
RIBBON_Y = 41.72                                  # was 34: the tiles hold their place
                                                  # on the board and the title rises
APO = S * math.sin(math.radians(60.0))
PARCH, INK, DEAD, BLACK = "#EFE6CC", "#2A2320", "#8A8371", "#2A2320"
GREEN = "#2E6B34"
# The two states are the same gesture at two weights, because that is what they are: a building
# out of play for good, and one out of play until the turn ends.
DONATED_FILL = "#A8A296"      # dark grey  -- permanent
USED_FILL    = "#D5D0C0"      # light grey -- this turn only
BOX_TOP = 9.5
SEATS = {"red": "#B7382E", "yellow": "#D9B33B", "blue": "#3B6EA5", "white": "#F4EFE2"}
OWNERS  = {"indulgences": "blue", "library": "red", "bank": "white", "mint": "yellow"}
DONATED = {"mint"}
USED    = {"guild", "library"}       # one on the map, one owned -- both spend the same way

sc = generate_setup_scenario(4, SEED)
tl = sc["setup_metadata"]["setup_timeline"]
by_id = {b.get("id", b["name"].lower().replace(" ", "_")): b
         for b in load_building_catalog()["buildings"]}
items = []
for level, entries in tl["building_live_rounds"].items():
    for bid, rnd in entries.items():
        items.append({"round": rnd, "kind": "building", "b": by_id[bid], "id": bid})
for key, rnd in tl["pilgrimage_rounds"].items():
    n = int(key.rsplit("_", 1)[1])
    items.append({"round": LAST if n == 1 else rnd, "kind": "site"})
items.sort(key=lambda i: i["round"])

def pts(x, y, r=S):
    return [(x + (px - x) * r / S, y + (py - y) * r / S) for px, py in hex_points(x, y)]
def hexpath(x, y, r=S):
    q = pts(x, y, r)
    return "M %.2f,%.2f " % q[0] + " ".join("L %.2f,%.2f" % p for p in q[1:]) + " Z"
def text(x, y, size, fill, body, weight="600"):
    return ('<text x="%.1f" y="%.1f" text-anchor="middle" font-family="Helvetica, Arial,'
            ' sans-serif" font-size="%g" font-weight="%s" fill="%s">%s</text>'
            % (x, y, size, weight, fill, escape(body)))

DEFS = ('<defs><pattern id="hatch" width="9" height="9" patternUnits="userSpaceOnUse"'
        ' patternTransform="rotate(-30)">'
        '<line x1="0" y1="0" x2="0" y2="9" stroke="%s" stroke-width="3.4" opacity=".26"/>'
        '</pattern></defs>' % BLACK)

def tile(it, x, y, used_mode=None):
    out = []
    site = it["kind"] == "site"
    donated = it.get("id") in DONATED
    used = it.get("id") in USED
    fill = SITE_FILL if site else (DONATED_FILL if donated else
                                   (USED_FILL if used else PARCH))
    out.append('<path d="%s" fill="%s" stroke="%s" stroke-width="2.6" stroke-linejoin="round"/>'
               % (hexpath(x, y), fill, BLACK))
    seat = OWNERS.get(it.get("id"))
    if seat:                                   # ownership is untouched by either state
        out.append('<rect x="%.1f" y="%.1f" width="34" height="7.5" rx="3.2" fill="%s"'
                   ' stroke="%s" stroke-width="1.5"/>'
                   % (x - 17, y + APO - 14, SEATS[seat], BLACK))
    lines = ("Season", "End") if site else tile_text_lines(it["b"])
    ink = INK                                   # one ink on the whole strip
    for i, line in enumerate(lines):
        out.append(text(x, y + TILE_NAME_CENTER_Y_OFFSET + i * TILE_NAME_LINE_HEIGHT,
                        TILE_NAME_FONT_SIZE, ink, line))
    if donated:
        out.append(text(x, y + TILE_NAME_CENTER_Y_OFFSET + len(lines) * TILE_NAME_LINE_HEIGHT,
                        12.5, INK, "Donated", weight="700"))
    now = it["round"] == NOW
    w = 15.5 + 6.5 * len(str(it["round"]))
    out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="21" rx="5" fill="%s" stroke="%s"'
               ' stroke-width="1.4"/>'
               % (x - w/2, y - APO + BOX_TOP, w, GREEN if now else (SITE_FILL if site else PARCH),
                  BLACK))
    out.append(text(x, y - APO + BOX_TOP + 15.5, 15, PARCH if now else INK,
                    str(it["round"]), weight="700"))
    return "".join(out)

def layout(sep=46.0):
    xs, x = [], S
    for i, it in enumerate(items):
        if i and items[i - 1]["kind"] == "site":
            x += sep
        xs.append(x); x += 1.5 * S
    return xs, xs[-1] + S

# A map hex draws 68.85 px wide on the 1600x1067 canvas (46 units at the map's 0.7487 px/unit,
# measured on screen, not converted). The market SVG's viewBox unit renders 1:1 there, so matching
# the two is one constant: 2*S*k = 68.85. Both boards are fixed in design space and the stage
# scales them together, so matching at one canvas size matches at every zoom.
MAP_HEX_W = 68.85
K_MAP = MAP_HEX_W / (2 * S)                      # 0.662

def frame():
    """The Alms Table's own frame, to the unit: they are two tables on one board."""
    return ('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" rx="%.2f" fill="#E5D8B9"'
            ' stroke="%s" stroke-width="%.2f"/>'
            '<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" rx="%.2f" fill="none"'
            ' stroke="%s" stroke-opacity=".30" stroke-width="%.2f"/>'
            '<text x="%.1f" y="%.1f" font-size="%.1f" text-anchor="start" fill="%s"'
            ' font-weight="700" font-family="Georgia,serif">%s</text>'
            # the round rides the table's other shoulder: this is the board's round track, so the
            # number belongs on it rather than in the action box, which is about the turn
            '<text x="%.1f" y="%.1f" font-size="%.1f" text-anchor="end" fill="%s"'
            ' font-weight="700" font-family="Georgia,serif">Round %d</text>'
            % (FRAME_SW / 2, FRAME_SW / 2, BOX_W - FRAME_SW, BOX_H - FRAME_SW, FRAME_RX,
               BLACK, FRAME_SW,
               KEY_IN, KEY_IN, BOX_W - 2 * KEY_IN, BOX_H - 2 * KEY_IN, KEY_RX, BLACK, KEY_SW,
               TITLE_X, TITLE_Y, TITLE_SIZE, BLACK, escape(TITLE),
               BOX_W - MARGIN, TITLE_Y, TITLE_SIZE, BLACK, NOW))

def strip(used_mode=None, sep=0.0):
    """The ribbon under its title, with the same margin left and right."""
    xs, w = layout(sep)
    k = K_MAP
    body = "".join(tile(it, xs[i], APO + (APO if i % 2 else 0), used_mode)
                   for i, it in enumerate(items))
    return ('<svg viewBox="0 0 %.1f %.1f" width="%.1f" height="%.1f">%s%s'
            '<g transform="translate(%.2f %.2f) scale(%.4f)">%s</g></svg>'
            % (BOX_W, BOX_H, BOX_W, BOX_H, DEFS, frame(), MARGIN, RIBBON_Y, k, body))

RIBBON_W = layout(0.0)[1] * K_MAP
BOX_W = RIBBON_W + 2 * MARGIN

SVG = strip()
pathlib.Path('/tmp/market_hex.svg').write_text(SVG)

open('/home/claude/ui-2.0/market-hex-final.html', 'w').write("""<!doctype html>
<meta charset="utf-8"><title>Pilgrim &mdash; Buildings</title><style>
body{margin:0;background:#2F5237;color:#EDE6D6;font:14px/1.5 Georgia,serif;padding:26px 30px 60px}
h1{font-size:22px;margin:0 0 4px}h1+p{margin:0 0 22px;color:#BBCBB6;max-width:1193px}
.hold{width:1193px}
.foot{color:#9FB39B;font-size:12.5px;max-width:1193px;margin-top:22px}
</style>
<h1>Buildings</h1>
<p>The Alms Table's frame, to the unit &mdash; same radius, same keyline, same 15px Georgia title,
all multiplied by the 0.9642 that table is rendered at, so the two come out identical on screen.
Tiles at the map's own hex size; the ribbon right-aligned, which collects the slack on the left
where the title lives.</p>
<div class="hold">%s</div>
<p class="foot">Guild is used and unowned, Library used and red's, Indulgences blue's, Bank white's,
Mint yellow's and donated, Brewery the current round.</p>
""" % SVG)
print("written | hex r=%.1f px  ribbon %.1f px wide  left edge at strip %.1f" %
      (S * K_MAP, layout(0.0)[1] * K_MAP, BOX_W - 6.0 - layout(0.0)[1] * K_MAP))
