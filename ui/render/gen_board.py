"""Rebuild, step 1: alms table, four player boards under it, action box to the right.

Everything is sized from one decision -- the action box's body text -- and the two SVG
components are SCALED so their own numerals come out the same size as it.
"""
import sys, importlib, importlib.util, pathlib, math, os

HERE = pathlib.Path(__file__).resolve().parent      # ui/render
UI = HERE.parent                                    # ui
OUT = str(UI / "generated") + "/"
pathlib.Path(OUT).mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(HERE))

# Pre-rendered stages of the pipeline -- the duty wheel, the populated map, the market hex, the
# log body. Each is produced by its own generator; they live here as files so this one can be run
# without re-running all of them, which is the only reason a generated artifact is in the tree.
def IN(name):
    p = UI / "inputs" / name
    if not p.exists():
        raise SystemExit("missing pipeline input %s -- see ui/inputs/README.md" % p)
    return p.read_text()

import gen_board_kit as gb            # colours, pills, cubes, numerals -- see its docstring
import gen_portraits_svg as gp; importlib.reload(gp)
import gen_alms_panel as ap;   importlib.reload(ap)
import gen_population_marks as pop; importlib.reload(pop)
import re as _re
wheel = IN("duty-wheel.svg")
for _a,_b in {"#b23a2d":"#B7382E","#d7b24a":"#D9B33B","#2f5e8e":"#3B6EA5"}.items():
    wheel=wheel.replace(_a,_b)
wheel=_re.sub(r'\swidth="[^"]*"','',wheel,count=1)
wheel=_re.sub(r'\sheight="[^"]*"','',wheel,count=1)
wheel=wheel.replace('<svg','<svg class="wheel"',1)
# Every duty tile is drawn 150 square and placed at scale(.74). Growing it grows the tile in
# place -- the ring positions do not move -- so the headroom is the gap between neighbours, and
# what is spent goes to the arrows and the city inside the ring.
# 0.80 was chosen and adopted (variant B of the scale-up study: tiles 174.5 -> 188.7 px, the
# neighbour gap 32.2 -> 18.1; 0.86 was rejected at a gap of 3.9 with the arrows crushed). It is a
# default rather than an env var because an adopted decision that only holds while you remember to
# export a variable is a decision that silently reverts -- which it did, once.
TILE_S = os.environ.get("TILE_S", "0.80").strip()
if TILE_S:
    wheel = wheel.replace('scale(.74)', 'scale(%s)' % TILE_S)
# Scaling the tile does NOT relieve a crowded title: the type grows with everything else, so the
# gap between the title and the first act keeps its proportion and only gains a pixel or so. The
# lever that actually opens it is the type itself.
TITLE_SZ = os.environ.get("TITLE_SZ", "11.4").strip()   # adopted with the scale-up, as above
if TITLE_SZ:
    wheel = _re.sub(r'(<text x="12" y="22" font-size=")12\.5(")',
                    lambda m: m.group(1) + TITLE_SZ + m.group(2), wheel)

# --- capacity test: taller tallies on the duty tiles, and a stacked city --------------------------
CUBE_PX, PITCH = 10, 13
# The duty tiles get a pitch of their own. With the acts moved up onto the title's line they now
# stand over the cube columns, ending at y 38.6; at pitch 13 a full five-stack plus its overflow
# figure reaches 36.1 and collides. At 11 -- the pitch the wheel drew before -- the figure tops
# out at 44.3, which clears by 5.7. The city keeps 13.
TILE_PITCH = 11
# ...and columns centred on the rule. XCOL spans -33..31, a centre of -1 against a rule centred
# on 0, so the block sat a unit light to the left. The city keeps XCOL.
TCOL = [-32.0, -14.0, 4.0, 22.0]
# the columns open from a 15-unit pitch to 18: the overflow mark is now set at the
# player boards' own figure size, and a "+2" at that size is wider than a cube.
XCOL   = [-33.0, -15.0, 3.0, 21.0]
SEATS4 = ["#B7382E", "#D9B33B", "#3B6EA5", "#F4EFE2"]
COUNTS = [[1,1,3,0],[2,1,0,1],[5,0,2,1],[0,3,1,7],[1,2,2,0],
          [3,0,9,1],[0,1,1,2],[2,5,0,1],[1,1,4,2]]      # two columns now run past the cap
# A duty tile draws at most five cubes in a column and the city at most eight; anything beyond
# that is a "+n" over the stack. Eleven pieces can in principle reach one position -- eight
# village serfs and three abbey acolytes -- and no tile can draw eleven at a legible cube size,
# so the cap is what makes the drawing bounded whatever the engine reports. It is presentation
# only: the true count stays in the state, and the inspector is where an exact number belongs.
TILE_CAP, CITY_CAP = 3, 8
# and the mark is set in the player boards' own figure: they render at 16.7 px, and a
# tile unit draws 1.422 px, so 11.74 here -- the city takes the same times its scale.
MORE_SIZE = 11.74
def _more(x, y, n, size):
    """The overflow mark, centred over its own column so it stays with the right seat."""
    return ('<text x="%.1f" y="%.1f" font-size="%.1f" text-anchor="middle" fill="#2a2320" '
            'font-weight="700" font-family="Georgia,serif">+%d</text>'
            % (x, y, size, n))
def _tally(counts):
    o=['<line x1="-36" y1="0.8" x2="36" y2="0.8" stroke="#2a2320" stroke-width="1"></line>']
    for c,(x,fill) in enumerate(zip(TCOL, SEATS4)):
        n=counts[c]; shown=min(n, TILE_CAP)
        for i in range(shown):
            o.append('<rect x="%s" y="%s" width="%s" height="%s" fill="%s" stroke="#2a2320" '
                     'stroke-width="0.5"></rect>'%(x, -CUBE_PX - i*TILE_PITCH, CUBE_PX, CUBE_PX,
                                                   fill))
        if n > shown:
            o.append(_more(x + CUBE_PX/2.0, -CUBE_PX - (shown-1)*TILE_PITCH - 5.5,
                           n - shown, MORE_SIZE))
    return "".join(o)
# The tally's rule lifts clear of the foot. It used to stand on the wagon's own ground at 138,
# with the resource and the wagon queueing above it down the right rail; now the acts have gone
# to the title's line, the foot below the rule belongs to those two alone -- resource left,
# wagon right, on one centre line.
# Recomputed for the cap of 3 and the dropped act row: the band is 45.9 deep (three cubes at
# pitch 11 plus the overflow figure), the acts now end at 52.6 and the foot starts at 116. That
# is 63.4 of room for 45.9, so 107 is the rule that splits the 17.5 of slack evenly.
TALLY_Y = 107
# ...and it moves to the tile's own centre. The group sat at x 55 on a 150-wide tile, so the whole
# block -- rule and columns together -- stood 20 left of centre, which was invisible while the
# right rail was full of icons and obvious the moment they left. 75 is also exactly halfway
# between the two marks on the foot, the resource at 26 and the wagon at 124.
TALLY_X = 75
_n=[0]
def _sub(m):
    i=_n[0]; _n[0]+=1
    return '<g transform="translate(%s %s)">%s</g>'%(TALLY_X, TALLY_Y,
                                                            _tally(COUNTS[i%len(COUNTS)]))
wheel=_re.sub(r'<g transform="translate\(55 128\)">.*?</g>', _sub, wheel, flags=_re.S)

# --- every duty tile, rebuilt around what its rail actually says --------------------------
# Three kinds of thing live in a tile's rail and they should not look alike:
#   ACTIONS  -- what the tile lets you do. Pills, because a pill is what this UI already
#               means by "you may pick this", gathered in one shaded region at the top.
#   TITHE    -- the stock the tithe action pays here, drawn the way the PLAYER BOARD draws
#               that stock and bare, because it is a fact about a payout, not a thing to
#               press. No amount: the tithe always pays one. Taxation pays none, so it has
#               no glyph at all. The wheel already assigned these and the spread is the one
#               asked for: stone on Clerical and Produce, wheat on Build Roads and Give
#               Alms, silver on Allocation and Ordination, the cornucopia on Construct.
#   MERCHANT -- the slot a merchant disc goes in: the disc's own round outline in the
#               merchant's own purple, alone at the foot and unshaded, because it reports
#               board state rather than offering anything.
# The tithe and the socket sit at the same y on every tile, so the eye finds them in one
# place across the wheel however many actions a tile happens to have.
import json as _json
def _gspan(s, i):
    """End index of the balanced <g ...>...</g> element that starts at i."""
    depth = 0; j = i
    while True:
        m = _re.compile(r'<g\b|</g>').search(s, j)
        if not m: return len(s)
        depth += -1 if m.group(0) == '</g>' else 1
        if depth == 0: return m.end()
        j = m.end()

# --- the player board's own three resource glyphs, in the duty tile's frame ---------------
_WT = ((-0.55, -0.65), (-0.25, -0.85), (0.05, -0.9), (0.35, -0.8), (0.6, -0.55))
def _wheat(cx, cy, size, ink="#2a2320"):
    bx, by = cx, cy + size*0.55
    o = []
    for dx, dy in _WT:
        tx, ty = cx + dx*size, cy + dy*size
        o.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="%.2f" '
                 'stroke-linecap="round"/>' % (bx, by, tx, ty, ink, max(size*0.09, 1.2)))
        o.append('<ellipse cx="%.1f" cy="%.1f" rx="%.2f" ry="%.2f" fill="%s" '
                 'transform="rotate(%.0f %.1f %.1f)"/>'
                 % (tx, ty, size*0.13, size*0.22, ink, dx*40, tx, ty))
    o.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="%.2f"/>'
             % (bx - size*0.3, by + size*0.05, bx + size*0.3, by + size*0.05, ink,
                max(size*0.1, 1.2)))
    return "".join(o)

_FACES = ("0.9", "0.55", "0.75")
def _cube(cx, cy, size, ink="#2a2320"):
    half = size*0.62; wide = half*0.87
    faces = (((cx, cy-half), (cx+wide, cy-half*0.5), (cx, cy), (cx-wide, cy-half*0.5)),
             ((cx+wide, cy-half*0.5), (cx+wide, cy+half*0.5), (cx, cy+half), (cx, cy)),
             ((cx-wide, cy-half*0.5), (cx, cy), (cx, cy+half), (cx-wide, cy+half*0.5)))
    return "".join('<path d="M %s Z" fill="%s" fill-opacity="%s" stroke="%s" stroke-width="1" '
                   'stroke-linejoin="round"/>'
                   % (" L ".join("%.1f,%.1f" % pt for pt in corners), ink, op, ink)
                   for corners, op in zip(faces, _FACES))

def _coin(cx, cy, size, ink="#2a2320"):
    r = size*0.62; sx, sy = cx + r*0.42, cy - r*0.5; arm = r*0.22
    return ('<circle cx="%.1f" cy="%.1f" r="%.2f" fill="none" stroke="%s" stroke-width="%.2f"/>'
            '<circle cx="%.1f" cy="%.1f" r="%.2f" fill="none" stroke="%s" stroke-width="%.2f"/>'
            '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1" '
            'stroke-linecap="round"/>'
            '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1" '
            'stroke-linecap="round"/>'
            % (cx, cy, r, ink, max(r*0.16, 1.3), cx, cy, r*0.68, ink, max(r*0.08, 0.9),
               sx-arm, sy, sx+arm, sy, ink, sx, sy-arm, sx, sy+arm, ink))

# the cornucopia is the wheel's own, horn path and all, out of the layout it already ships in
_HORN = _json.load(open(str(gb._ROOT / 'tools/ui_debug/duty_wheel_layout.json')))['artwork']['cornucopia_horn_path']
_FRUIT = ((9.48, -7.31, 2.94), (4.98, -11.18, 2.10), (10.95, -1.69, 2.03))
def _cornu(ink="#2a2320"):
    return ('<path d="%s" fill="none" stroke="%s" stroke-width="1.7" stroke-linecap="round" '
            'stroke-linejoin="round"/>'
            '<ellipse cx="2.21" cy="-3.11" rx="7.0" ry="3.15" transform="rotate(-120.0 2.21 -3.11)" '
            'fill="none" stroke="%s" stroke-width="1.6"/>%s'
            % (_HORN, ink, ink,
               "".join('<circle cx="%.2f" cy="%.2f" r="%.2f" fill="none" stroke="%s" '
                       'stroke-width="1.4"/>' % (cx, cy, r, ink) for cx, cy, r in _FRUIT)))

# --- geometry ------------------------------------------------------------------------------
# the pill is the player board's resource key at the size it renders there (42.9 x 39.3 px);
# the glyphs are the board's at the size they render there. Both came from the rendered boxes.
_PW, _PH, _PRX, _PSW = 30.1, 27.6, 2.82, 1.15
_WSIZE = round(17.26 * 0.8182 / 1.3199, 2)     # 10.70 -- the board's wheat, on a tile
# the cube and the coin needed measuring rather than converting: the board draws them at a
# size its own constant does not predict, so this is what puts a tile cube's face on the
# board cube's 22.8 px. It makes the stone and the silver 18.0 units tall, which is where the
# wheat already stands, so the three tithe glyphs carry the same weight.
_CSIZE = 14.76
_CORN_S = 0.677                                # the horn stands 26.6 units raw; 18 drawn
_PAD, _GAP = 3.0, 3.0
_CAPW, _CAPX, _CAPY = _PW + 2*_PAD, 142 - (_PW + 2*_PAD), 8.0
# The acts sit BELOW the line the title stands on -- its baseline is y 22 -- rather than
# straddling it. Their box opens 3 under the baseline, so the title keeps the full width of the
# tile and the row reads as what the title introduces rather than as something beside it.
_ROW_TOP = 25.0
_CX = round(_CAPX + _CAPW/2, 1)
# The tithe leaves the rail for the foot's left corner and grows 1.35, which is what stops it
# being read as one more cube now that it stands near the tally's own ground.
_TITHE_X, _TITHE_Y, _SLOT_Y, _TITHE_K = 26.0, 129.0, 129.0, 1.35
_RAIL = ('<rect x="108" y="8" width="34" height="134" rx="17" fill="#cdbc95" '
         'opacity=".45"></rect>')
# The merchant is the Noun Project wagon (Alzam), with its sixteen spoke subpaths dropped and
# the wheel interiors masked out so the tyres read as rings. It is defined once and placed with
# <use>, tinted through currentColor: the tile that holds the merchant draws it solid in the
# token's edge purple, the seven that do not draw the same shape as a wash.
_WAGON_D = IN("wagon-path.txt").strip()
_WK = 0.26                                  # 100 art units -> the marker's 26 tile units
# and the path is stroked in its own colour: at 0.26 the drawing's own line comes out
# about 0.7 px, where every other glyph on a tile is drawn at just under 2. Stroking by
# 2.6 art units thickens all of it together without redrawing anything.
_WAGON_DEFS = ('<defs><mask id="wgnM" maskUnits="userSpaceOnUse" x="0" y="1.94" width="100" '
               'height="96.11"><rect x="0" y="1.94" width="100" height="96.11" fill="#fff"/>'
               '<circle cx="18.7" cy="79.94" r="14" fill="#000"/>'
               '<circle cx="81.2" cy="79.94" r="14" fill="#000"/></mask>'
               '<g id="wgn"><path d="%s" fill="currentColor" stroke="currentColor" '
               'stroke-width="2.6" stroke-linejoin="round" mask="url(#wgnM)"/></g></defs>'
               % _WAGON_D)
def _slot(here):
    return ('<use href="#wgn" transform="translate(%.1f %.1f) scale(%s)" color="%s"%s/>'
            % (_CX - 50*_WK, _SLOT_Y - 50.0*_WK, _WK,
               "#5A3E8C" if here else "#8E63D7", "" if here else ' opacity=".22"'))

def _pill(dashed=False):
    return ('<rect x="%.1f" y="%.1f" width="%s" height="%s" rx="%s" fill="%s" stroke="%s" '
            'stroke-width="%s"%s></rect>'
            % (-_PW/2, -_PH/2, _PW, _PH, _PRX, "#EFE4C6",
               "#A89B7E" if dashed else "#A08F6A", _PSW,
               ' stroke-dasharray="3 2.6"' if dashed else ''))

def _tithe(kind):
    if kind is None: return ''
    if kind == 'wheat':
        return '<g>%s</g>' % _wheat(_TITHE_X, _TITHE_Y + 0.2622*_WSIZE*_TITHE_K, _WSIZE*_TITHE_K)
    if kind == 'stone':
        return '<g>%s</g>' % _cube(_TITHE_X, _TITHE_Y - 0.01*_CSIZE*_TITHE_K, _CSIZE*_TITHE_K)
    if kind == 'silver':
        return '<g>%s</g>' % _coin(_TITHE_X, _TITHE_Y - 0.01*_CSIZE*_TITHE_K, _CSIZE*_TITHE_K)
    return ('<g transform="translate(%s %s) scale(%s)">%s</g>'
            % (_TITHE_X, _TITHE_Y, round(_CORN_S*_TITHE_K, 4), _cornu()))

MERCHANT_ON = "Taxation"          # duty_wheel_layout.json: merchant_token starts_on

def _rebuild(seg):
    """One duty tile's rail, in the three-tier language."""
    _name = _re.search(r'<text x="12" y="22"[^>]*>([^<]+)</text>', seg).group(1)
    # what the tile already pays as its tithe -- read off the token it carries at y 126
    k = seg.find('<g transform="translate(125 126)">'); kb = _gspan(seg, k)
    tok = seg[k:kb]
    kind = (None if 'stroke-dasharray' in tok and 'fill="none"' in tok else
            'cornucopia' if 'C0-10' in tok else
            'stone' if 'M0-8 L7-4' in tok else
            'wheat' if 'M0 8 V-8' in tok else 'silver')
    seg = seg[:k] + _tithe(kind) + _slot(_name == MERCHANT_ON) + seg[kb:]

    # the actions: every icon in the rail bar the token, and never one on an inked disc --
    # that treatment said "this one is different" in a language the pills no longer speak
    acts, drop = [], []
    for m in _re.finditer(r'<g transform="translate\(125 (\d+)\)">', seg):
        if m.group(1) == '126': continue
        span = (m.start(), _gspan(seg, m.start()))
        body = seg[span[0]:span[1]]
        (drop if '<circle r="12.5" fill="#2a2320"' in body else acts).append(
            span + (m.group(1), body))
    for a, b, _y, _body in reversed(drop):          # the inked disc goes, it does not just move
        seg = seg[:a] + seg[b:]
        acts = [(x - (b - a) if x > a else x, y - (b - a) if y > a else y, yy, bd)
                for x, y, yy, bd in acts]
    # One row, on the title's own line, filled from the RIGHT so the last act always lands on
    # _CX -- the wagon's axis. That gives the tile's right side a spine: act, cube column, wagon.
    _ROW_Y = round(_ROW_TOP + _PH/2, 1)
    cols = [round(_CX - (len(acts) - 1 - i)*(_PW + _GAP), 1) for i in range(len(acts))]
    for i in range(len(acts) - 1, -1, -1):
        a, b, y, body = acts[i]
        dashed = 'stroke-dasharray' in body.split('<g stroke=')[0]
        body = _re.sub(r'<circle r="[\d.]+"(?![^>]*\scx=)[^>]*></circle>', '', body)
        body = body.replace('transform="scale(0.8)"', 'transform="scale(1.15)"')
        # and drawn nimbly, the way the player board draws: the glyphs came at stroke 2.125,
        # which under the 1.15 scale renders 3.5 px against the board's 1.8-2.7. 1.5 puts them
        # inside that range instead of twice its top.
        body = body.replace('stroke-width="2.125"', 'stroke-width="1.2"')
        body = body.replace('stroke-width="2.8333333333333335"', 'stroke-width="2.0"')
        body = body.replace('<g transform="translate(125 %s)">' % y,
                            '<g class="act" data-duty="%s" data-i="%s" '
                            'transform="translate(%s %s)">' % (_name, i, cols[i], _ROW_Y), 1)
        body = body.replace('><g>', '><g>' + _pill(dashed), 1)
        seg = seg[:a] + body + seg[b:]

    # one shaded region, sized to the actions it holds, and no tethers between anything
    w = round(len(acts)*_PW + (len(acts) - 1)*_GAP + 2*_PAD, 1)
    seg = seg.replace(_RAIL, '<rect x="%s" y="%s" width="%s" height="%s" rx="6" fill="#cdbc95" '
                             'opacity=".45"></rect>'
                             % (round(142 - w, 1), round(_ROW_TOP - _PAD, 1), w,
                                round(_PH + 2*_PAD, 1)))
    return _re.sub(r'<line x1="1(?:16|25)"[^>]*></line>', '', seg)

# Clerical's second action is the Silversmith, and the wheel drew it as a placeholder: muted
# ink, a dashed rim and a strike across it, which in this language reads "unavailable". It is
# a live action, so it becomes a normal one -- ink, solid rim, no strike -- carrying the anvil.
_OLD = ('<g transform="translate(125 61)"><g><circle r="12.5" fill="#e5d8b9" stroke="#a89b7e" '
        'stroke-width="1.1" stroke-dasharray="2.5 2.5"></circle><g stroke="#a89b7e">'
        '<g fill="none" stroke-width="2.125" stroke-linejoin="round" stroke-linecap="round" '
        'transform="scale(0.8)"><path d="M-6 7 L2-1"></path>'
        '<path d="M-1-6 L5-8 L8-4 L3-1 L0-3 Z"></path></g></g>'
        '<path d="M-8.75 8.75 L8.75 -8.75" stroke="#a89b7e" stroke-width="1"></path></g></g>')
_NEW = ('<g transform="translate(125 61)"><g><circle r="12.5" fill="#e5d8b9" stroke="#2a2320" '
        'stroke-width="1.1"></circle><g stroke="#2a2320"><g fill="none" stroke-width="2.125" '
        'stroke-linejoin="round" stroke-linecap="round" transform="scale(0.8)">'
        '<path d="M-7-4.5 H3 L7-1.5 L3 1.5 H-7 Z"></path>'      # the body, with its horn
        '<path d="M-2.5 1.5 V4.5"></path>'                       # the stem
        '<path d="M-6.5 4.5 H1.5"></path></g></g></g></g>')      # the base
assert _OLD in wheel, "Clerical's placeholder icon not found"
wheel = wheel.replace(_OLD, _NEW)

# Ordination gains its second action. Both of its actions move a person one step along the
# same chain, so the two icons differ only in where the arrow points: out of the village
# toward the abbey, then into the city. Written in the source's own idiom -- a disc, scale
# 0.8, stroke 2.125 -- so the rebuild below converts them exactly as it does every other one.
def _act(y, paths):
    return ('<g transform="translate(125 %s)"><g><circle r="12.5" fill="#e5d8b9" '
            'stroke="#2a2320" stroke-width="1.1"></circle><g stroke="#2a2320">'
            '<g fill="none" stroke-width="2.125" stroke-linejoin="round" stroke-linecap="round" '
            'transform="scale(0.8)">%s</g></g></g></g>' % (y, paths))

_A, _E = ap.ORD_SERF, ap.ORD_ACOLYTE
_oi = wheel.find('Ordination</text>')
_oe = wheel.find('<rect width="150"', _oi)
_oseg = wheel[_oi:_oe]
_oa = _oseg.find('<g transform="translate(125 90)">')
assert _oa > 0, "Ordination's action not found"
_oseg = _oseg[:_oa] + _act(90, _A) + _act(61, _E) + _oseg[_gspan(_oseg, _oa):]
wheel = wheel[:_oi] + _oseg + wheel[_oe:]

# Give Alms' second action is a building given away, so it cannot be used. It used to be a
# house with an arrow off its right side -- the very composition Ordination's first action now
# carries, and at 24 px the two were the same picture. The X lies across the whole building.
# the same house Construct draws, so one building means one picture wherever it appears
_DONATED = ('<path d="M-7 1 L0-6 L7 1 V8 H-7 Z"></path><path d="M-2 8 V3 H2 V8"></path>'
            '<path d="M-7-6 L7 8 M7-6 L-7 8"></path>')
_gg = wheel.find('Give Alms</text>')
_ge2 = wheel.find('<rect width="150"', _gg)
_gseg = wheel[_gg:_ge2]
_ga = _gseg.find('<g transform="translate(125 61)">')
assert _ga > 0, "Give Alms' second action not found"
_gseg = _gseg[:_ga] + _act(61, _DONATED) + _gseg[_gspan(_gseg, _ga):]
wheel = wheel[:_gg] + _gseg + wheel[_ge2:]

# The copy is the rules, not invention: every line below is taken from
# docs/rules/DutyTiles.md ("Canonical Action Names" and "Runtime implications"), with the
# building modifiers from docs/rules/Buildings.md and the amounts confirmed against
# pilgrim/rules/duties.py, where devotion moves piety by duty value, the silversmith adds
# duty value in silver, and produce sets wheat or stone delta to duty value.

# --- resource icons, inline in the copy ------------------------------------------------------
# The same drawings the boards and tiles use, in a 16-unit box sized to sit on a line of the
# action box's body type. Naming a stock in words and drawing it a few units away in the same
# panel taught the player two things for one; this teaches one.
def _ico(kind):
    if kind == "wheat":  body = _wheat(8, 8 + 0.2622*8.1, 8.1)
    elif kind == "stone": body = _cube(8, 8, 11.5)
    elif kind == "silver": body = _coin(8, 8, 11.5)
    else: body = ('<circle cx="8" cy="8" r="6" fill="none" stroke="#2a2320" stroke-width="1.5"/>'
                  '<path d="M8 4.2V11.8M4.2 8H11.8" stroke="#2a2320" stroke-width="2" '
                  'stroke-linecap="round"/>')
    return ('<svg class="ico" viewBox="0 0 16 16" width="15" height="15">%s</svg>' % body)

def _icons(text):
    """Swap the four stock names for their glyphs, longest first so nothing half-matches.

    A glyph that follows a figure is set on a hair space rather than a word space: "3 wheat"
    is one quantity, and a full space made it read as two things standing side by side.
    """
    for word in ("piety", "silver", "stone", "wheat"):
        text = _re.sub(r'(\d)\s+\b%s\b' % word,
                       lambda m: m.group(1) + "&#8202;" + _ico(word), text, flags=_re.I)
        text = _re.sub(r'\b%s\b' % word, _ico(word), text, flags=_re.I)
    return text

DUTY_TEXT = {
    "Allocation|0": (
        "Allocation",
        "Move acolytes between the Abbey and your Special Activities, one move per point of "
        "duty value.",
        "A usable Infirmary adds +1 duty value."),
    "Clerical|0": (
        "Devotion",
        "Gain piety equal to your duty value.",
        "Chapel adds +1 piety &middot; Vestry +1 per acolyte."),
    "Clerical|1": (
        "Silversmith",
        "Gain silver equal to your duty value.",
        "Mint adds +1 silver."),
    "Construct|0": (
        "Construct a building",
        "Take one live building from the market and pay stone equal to its level: 1, 2 or 3.",
        "One building per Construct action."),
    "Construct|1": (
        "Construct a road",
        "Plan a road alongside the building, at duty value 2.",
        "Deferred: the building resolves, the road does not."),
    "Build Roads|0": (
        "Build Roads",
        "Build, upgrade or demolish roads, bridges, fords and shrines.",
        "Deferred: duty relation and recall apply, nothing is placed."),
    "Ordination|0": (
        "Ordain",
        "Pay 1 wheat and move a serf from the Village to the Abbey.",
        "One Ordination sequences up to duty-value steps."),
    "Ordination|1": (
        "Mission",
        "Pay 1 wheat and move an acolyte from the Abbey to the City.",
        "Mill waives up to 2 wheat across the sequence."),
    "Produce|0": (
        "Produce wheat",
        "Take wheat equal to your duty value. Duty value cannot be split across resources.",
        "Well adds +1 wheat."),
    "Produce|1": (
        "Produce stone",
        "Take stone equal to your duty value. Duty value cannot be split across resources.",
        "Quarry adds +1 stone."),
    "Taxation|0": (
        "Taxation",
        "Take one resource of your choice, then duty value more from the tithe counters on "
        "other tiles where you hold majority.",
        "At most 1 + duty value in all &middot; no piety, no Alms."),
    "Give Alms|0": (
        "Give Alms",
        "Pay silver and wheat equal to your duty value and move that many rows up the Alms "
        "track.",
        "Mill waives up to 2 wheat."),
    "Give Alms|1": (
        "Donate a building",
        "Give away one active building and advance the Alms track exactly one row.",
        "Always one row, whatever the duty value."),
}

# --- the Special Activities table --------------------------------------------------------
# The six spaces are per-player state, so this is a table of seats, not board furniture: the
# six activities are the COLUMNS and the four seats the rows. Transposed that way it stands
# 148 units instead of the 194 a row-per-activity grid needs, which is what lets it sit under
# the player boards at all. Each activity carries the glyph of the duty action it boosts.
# The card's width so the column has one right edge, and the Alms Table's height so the two
# panels at the head of their columns are the same object. 166 -> 139.6 is 26.4 units to find,
# and the gap between the icons and the first row -- the obvious place -- only holds 17 of them
# before the cubes touch the glyphs. So the row PITCH gives the rest: 20 -> 16.5.
SA_W, SA_H = 316, 147.6          # 143.68 px of ink, the head panels' shared height
SA_ROW1, SA_PITCH = 82.0, 16.5   # row 1 was 74: the cubes hold their place and the glyphs rise
# a duty tile cube is 10 units in the tile frame; this is what draws the same
# width in the player board frame the table is written in.
SA_CUBE = 11.96
# and the gap between two of them is the duty tiles' own: a tile stacks at pitch 13 on a
# 10-unit cube, which is 4.27 px of air, and a board unit here draws 1.1909 px.
SA_GAP = 3.59
SA_CANDLE = '<path d="M-3 8 V0 H3 V8"/><path d="M0-1 C-3-4 -2-7 0-9 C2-7 3-4 0-1 Z"/>'
SA_ANVIL = ('<path d="M-7-4.5 H3 L7-1.5 L3 1.5 H-7 Z"/><path d="M-2.5 1.5 V4.5"/>'
            '<path d="M-6.5 4.5 H1.5"/>')
SA_BOWL = '<path d="M-7 2 C-7 8 7 8 7 2 Z"/><circle cx="0" cy="-4" r="3"/>'
SA_ROAD = '<path d="M-6 8 L-2-8 M6 8 L2-8"/><path d="M0-7 V-4 M0-1 V2 M0 5 V8"/>'
SA_ACTS = [("Vestry", ("s", SA_CANDLE)), ("Engraver", ("s", SA_ANVIL)),
           ("Fields", ("w", None)), ("Stone Mason", ("c", None)),
           ("Alms House", ("s", SA_BOWL)), ("Road Engineer", ("s", SA_ROAD))]
SA_OCC = [[1, 0, 0, 0, 1, 0], [0, 0, 2, 0, 0, 1], [0, 1, 0, 0, 0, 0], [0, 0, 0, 0, 1, 0]]

# The column glyphs are drawn at the size the DUTY TILES draw them, which is not a single
# number: the wheat and the stone are the player board's own (this panel is written in board
# units, so they take the board's sizes directly), and the stroke glyphs take a scale measured
# off the rendered tile -- a tile glyph draws 27.84 px tall, which is 23.4 board units here.
# The player board draws its resource icons inside a nested scale(0.741), so the board's own
# numbers cannot be used here unscaled -- these are what actually render the same as a tile's.
SA_STROKE_K = 1.3755        # a tile glyph draws 27.84 px tall; so does 16 units at this scale
SA_WHEAT, SA_STONE = 12.77, 17.75
def _sa_glyph(kind, cx, cy, size, ink="#2A2320"):
    k, paths = kind
    if k == "w": return _wheat(cx, cy + 0.2622*SA_WHEAT, SA_WHEAT, ink)
    if k == "c": return _cube(cx, cy - 0.01*SA_STONE, SA_STONE, ink)
    return ('<g transform="translate(%.1f %.1f) scale(%.3f)" fill="none" stroke="%s" '
            'stroke-width="%.2f" stroke-linejoin="round" stroke-linecap="round">%s</g>'
            % (cx, cy, SA_STROKE_K, ink, 1.20, paths))

def sa_panel(ink="#2A2320", parch="#E5D8B9"):
    """The table, with no row labels: the rows run in player-board order, and a cube's own
    colour says whose it is the moment one is placed. The cells are squares at the duty tile's
    cube size, so a cube means the same thing wherever it is standing on the table."""
    seats = ["#B7382E", "#D9B33B", "#3B6EA5", "#F4EFE2"]
    x0, x1 = 16.0, SA_W - 16.0
    colw = (x1 - x0)/6.0
    rows = [SA_ROW1 + i*SA_PITCH for i in range(4)]
    o = ['<rect x="0" y="0" width="%s" height="%s" rx="12" fill="%s" stroke="%s" '
         'stroke-width="1.4"/>' % (SA_W, SA_H, parch, ink),
         '<rect x="6" y="6" width="%s" height="%s" rx="7" fill="none" stroke="%s" '
         'stroke-opacity=".30" stroke-width="1.1"/>' % (SA_W - 12, SA_H - 12, ink),
         '<text x="16" y="26" font-size="15" fill="%s" font-weight="700" '
         'font-family="Georgia,serif">Special Activities</text>' % ink]
    for c, (_nm, g) in enumerate(SA_ACTS):
        cx = x0 + colw*c + colw/2
        o.append(_sa_glyph(g, cx, 52, 15, ink))
        if c:
            o.append('<path d="M%.1f %.1f V%.1f" stroke="%s" stroke-opacity=".18" '
                     'stroke-width="1"/>'
                     % (x0 + colw*c, SA_ROW1 - SA_CUBE/2 - 3, SA_H - 8, ink))
    for r, y in enumerate(rows):
        for c in range(6):
            cx = x0 + colw*c + colw/2
            n = SA_OCC[r][c]
            yy = y - SA_CUBE/2
            if n:
                # a second acolyte is a second cube, not a numeral on the first
                span = n*SA_CUBE + (n - 1)*SA_GAP
                for k in range(n):
                    o.append('<rect x="%.1f" y="%.1f" width="%s" height="%s" fill="%s" '
                             'stroke="%s" stroke-width="0.6"/>'
                             % (cx - span/2 + k*(SA_CUBE + SA_GAP), yy, SA_CUBE, SA_CUBE,
                                seats[r], ink))
            # an empty space draws nothing: the column rules and the row order already say
            # where a cube would stand, and dashed outlines in every cell made a table that is
            # mostly empty read as mostly full
    return ('<svg class="sa" viewBox="-30 -8 352 %s" width="%s" height="%.1f">%s</svg>'
            % (SA_H + 12, COMP_W, (SA_H + 12)*COMP_W/352.0, "".join(o)))


# Taxation carried a small inked disc on its face -- the one icon on the wheel still drawn as
# a filled token with the glyph knocked out of it. Nothing else speaks that language now.
_xi = wheel.find('Taxation</text>')
_xe = wheel.find('<rect width="150"', _xi)
_xseg = wheel[_xi:_xe]
_xa = _xseg.find('<g transform="translate(20 92)">')
assert _xa > 0, "Taxation's inked disc not found"
_xseg = _xseg[:_xa] + _xseg[_gspan(_xseg, _xa):]
wheel = wheel[:_xi] + _xseg + wheel[_xe:]

wheel = _re.sub(r'(<svg class="wheel"[^>]*>)', lambda m: m.group(1) + _WAGON_DEFS, wheel, count=1)

_starts = [m.start() for m in _re.finditer(r'<rect width="150"', wheel)]
for _st, _en in reversed(list(zip(_starts, _starts[1:] + [wheel.index('<circle r="92"')]))):
    wheel = wheel[:_st] + _rebuild(wheel[_st:_en]) + wheel[_en:]

# --- Produce: its two actions ARE the stocks they yield, so they carry the player board's own
# wheat and stone rather than invented pictures. Both are drawn at the size the tithe glyphs
# use, which is also the height every other action glyph occupies, so nothing changes weight.
_pi = wheel.find('Produce</text>')
_pe = wheel.find('<rect width="150"', _pi)
_ps = wheel.rfind('<rect width="150"', 0, _pi)
_seg = wheel[_ps:_pe]
for _i, _glyph in enumerate((_wheat(0, 0.2622*_WSIZE, _WSIZE), _cube(0, -0.01*_CSIZE, _CSIZE))):
    # found by the tag the rebuild left on it, not by its transform: the rebuild now writes a
    # class and data attributes before the transform, so matching on the transform silently
    # missed and spliced at -1, which quietly duplicated the tile's actions four times over.
    _a = _seg.find('<g class="act" data-duty="Produce" data-i="%d"' % _i)
    assert _a > 0, "Produce action %d not found" % _i
    _b = _gspan(_seg, _a)
    _inner = _seg[_a:_b]
    _g0 = _inner.find('<g stroke=')
    _seg = (_seg[:_a] + _inner[:_g0] + '<g>' + _glyph + '</g>'
            + _inner[_gspan(_inner, _g0):] + _seg[_b:])
wheel = wheel[:_ps] + _seg + wheel[_pe:]

# the city loses its church and its label, and gains four stacks of ten drawn at the tiles'
# own cube size -- a tile is scaled by .74 inside the wheel, so the cubes there are 7.4 units
TILE_SCALE = 0.74
wheel=wheel.replace('<g fill="none" stroke="#2a2320" stroke-width="1.2">'
                    '<path d="M-14 22 V-6 L0-20 L14-6 V22 Z"></path>'
                    '<path d="M-4 22 V8 H4 V22 M0-20 V-32 M-4-27 H4"></path></g>', '')
wheel=_re.sub(r'<text y="42".*?</text>', '', wheel, flags=_re.S)
_c, _p = CUBE_PX*TILE_SCALE, TILE_PITCH*TILE_SCALE   # one cube spacing everywhere
_city=['<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="#2a2320" stroke-width="1"></line>'
       % (-36*TILE_SCALE, 0.8*TILE_SCALE, 36*TILE_SCALE, 0.8*TILE_SCALE)]
CITY_COUNTS = [10, 8, 5, 12]        # two seats past the city's cap of eight
for x, fill, n in zip(XCOL, SEATS4, CITY_COUNTS):
    shown = min(n, CITY_CAP)
    for i in range(shown):
        _city.append('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" fill="%s" '
                     'stroke="#2a2320" stroke-width="0.5"></rect>'
                     % (x*TILE_SCALE, -_c - i*_p, _c, _c, fill))
    if n > shown:
        _city.append(_more((x + CUBE_PX/2.0)*TILE_SCALE,
                           -_c - (shown-1)*_p - 5.5*TILE_SCALE, n - shown,
                           MORE_SIZE*TILE_SCALE))
# the city is drawn at the tiles' own scale, so it moves by the same 10 tile units:
# 10 * TILE_SCALE = 7.4 wheel units, from 40 to 47.4
# --- the city takes the duty tiles' shape ---------------------------------------------------
# A rounded square instead of a disc, at the tiles' own proportions: their rx is 9 on a 150
# side, so 6 per cent, which on the city's 144 comes to 8.6. One border, like a tile's. The
# ring of rim markers is gone with the disc it belonged to. The label is the tiles' own --
# 12.5 inside a tile scaled .74, so 9.25 out here where nothing is scaled.
# Sized off the arrows, not chosen: the ring arrows clear the Give Alms tile by 8.99 and 8.80
# units (measured, the artwork is not quite symmetric), so 8.9 is the gap the middle arrows
# should keep too. The middle arrow keeps its 0.55 scale, so its half-length is 44*.55 = 24.2;
# a clearance of 8.9 at the tile end puts its centre at 130.5 - 24.2 - 8.9 = 97.4, and the same
# clearance at the city end puts the city's edge at 97.4 - 24.2 - 8.9 = 64.3. rx stays the
# tiles' 6 per cent of the side.
CITY_H, CITY_RX = 64.3, 7.7
_city_sq = ('<rect x="%s" y="%s" width="%s" height="%s" rx="%s" fill="#e5d8b9" stroke="#2a2320" '
            'stroke-width="1.4"></rect>' % (-CITY_H, -CITY_H, CITY_H*2, CITY_H*2, CITY_RX))
_marks = []
_marks.append('<text x="0" y="%.1f" font-size="9.25" text-anchor="middle" fill="#2a2320" '
              'letter-spacing=".3" font-family="Georgia,serif">City</text>'
              % (-CITY_H + 22*0.74))   # the tiles' own 22, at their own scale
wheel = wheel.replace('<circle r="92" fill="#e5d8b9" stroke="#2a2320" stroke-width="1.4">'
                      '</circle>', _city_sq + "".join(_marks))
wheel = wheel.replace('<circle r="83" fill="none" stroke="#2a2320" stroke-width=".7"></circle>', '')
wheel = _re.sub(r'<rect x="-?[\d.]+e?-?\d*" y="-?[\d.]+e?-?\d*" width="6" height="6" '
                r'fill="#e5d8b9" stroke="#2a2320" stroke-width="\.8" '
                r'transform="rotate\([^"]*\)"></rect>', '', wheel)

wheel=wheel.replace('</svg>', '<g transform="translate(0 47.4)">'+"".join(_city)+'</g></svg>')

# --- the market, as a single row of compact tiles: badge, level chip and name only -------------
_mkt=IN("market-panel.html")
def _tiles(html):
    out=[]; i=0
    while True:
        m0=_re.compile(r'<div class="tile[ "]').search(html, i)
        if not m0: break
        i=m0.start(); depth=0; j=i
        while True:
            m=_re.compile(r'<div\b|</div>').search(html, j)
            if not m: break
            if m.group(0)=='</div>':
                depth-=1; j=m.end()
                if depth==0: break
            else:
                depth+=1; j=m.end()
        out.append(html[i:j]); i=j
    return out
_ts=_tiles(_mkt); assert len(_ts)==12, len(_ts)
_ts=[_re.sub(r'<div class="d">.*?</div>','',t,flags=_re.S) for t in _ts]   # the rule text goes
_groups=""
for _g in range(3):
    _groups+=('<div class="grp"><div class="glab">Level %d</div><div class="four">'%(_g+1)
              + "".join(_ts[_g*4:_g*4+4]) + '</div></div>')
# --- the four middle arrows, city to duty and duty to city -----------------------------------
# The previous design's own artwork: duty_wheel_layout.json's middle_arrow_path, drawn twice --
# a heavy black border and a white interior -- so it reads over the green table. The path is 88
# long and points to +x; the gap between the city's edge (64.3) and an orthogonal tile's
# inner edge (130.5) is 66.2, so at 0.55 it leaves 8.9 clear at each end, centred at 97.4.
# Direction follows configs/board.json: the city flows OUT to north and south, and east and
# west flow IN to the city. Here that is Clerical north, Build Roads east, Produce south and
# Give Alms west.
_ARROW_D = _json.load(open(str(gb._ROOT / 'tools/ui_debug/duty_wheel_layout.json')))['artwork']['middle_arrow_path']
_ARROW_K, _ARROW_R = 0.55, 97.4
_ARROWS = []
for _ax, _ay, _rot in ((0, -_ARROW_R, -90),      # city -> Clerical
                       (_ARROW_R, 0, 180),       # Build Roads -> city
                       (0, _ARROW_R, 90),        # city -> Produce
                       (-_ARROW_R, 0, 0)):       # Give Alms -> city
    _ARROWS.append('<g transform="translate(%s %s) rotate(%s) scale(%s)">'
                   '<path d="%s" fill="none" stroke="#000000" stroke-width="6" '
                   'stroke-linejoin="round"></path>'
                   '<path d="%s" fill="#FFFFFF"></path></g>'
                   % (_ax, _ay, _rot, _ARROW_K, _ARROW_D, _ARROW_D))
wheel = wheel.replace('</svg>', "".join(_ARROWS) + '</svg>')

# --- the eight ring arrows, one between each pair of neighbouring duty tiles -----------------
# Also the previous design's own artwork: ring_arrow_path, which is written in that board's
# absolute coordinates around its centre (551.5, 718.7) with its tiles at radius 324.2. Ours
# sit at 186, so the whole thing is translated to the origin and scaled by 186/324.2 = 0.5737,
# then stepped round in eight 45-degree turns. The path already carries the clockwise sweep and
# the head, so nothing is redrawn -- and its 6-unit border comes out at 3.4 here, which is
# where the middle arrows' border landed too.
_RING_D = _json.load(open(str(gb._ROOT / 'tools/ui_debug/duty_wheel_layout.json')))['artwork']['ring_arrow_path']
_RING_K = round(186.0/324.2, 4)
_RINGS = []
for _i in range(8):
    _RINGS.append('<g transform="rotate(%s) scale(%s) translate(-551.5 -718.7)">'
                  '<path d="%s" fill="none" stroke="#000000" stroke-width="6" '
                  'stroke-linejoin="round"></path>'
                  '<path d="%s" fill="#FFFFFF"></path></g>'
                  % (_i*45, _RING_K, _RING_D, _RING_D))
wheel = wheel.replace('</svg>', "".join(_RINGS) + '</svg>')

# --- the map, as the wheel's other face -------------------------------------------------------
# Not an overlay. render_map's own SVG goes into the wheel's slot and the two swap, so the player
# boards, the alms table, the market and the action box never move -- only the middle changes.
# The map is HEIGHT-bound (its viewBox is 1013.8 x 1149.3, an aspect of 0.882), and the slot is
# already as tall as the row, so covering the left column would buy it nothing: at the action
# box's height it wants ~0.882 of that in width, which the wheel's own square more than holds.
# Its black backing rect goes, so it sits on the same green table the wheel does.
# The map arrives already populated: /tmp/mkmap.py runs the REAL setup generator
# (pilgrim.setup.generator, seed 20260730, 4 players) on 3.13 and writes the finished SVG, the
# same way the duty wheel arrives as /tmp/wheel1.svg. Sixteen of the twenty-six edge hexes are
# occupied -- twelve buildings, four sites -- and the buildings recolour their hex rather than
# lying on top of it, which is the setup page's own rule.
_map_svg = IN("map-populated.svg")
_mvb = _re.search(r'viewBox="([-\d.]+) ([-\d.]+) ([\d.]+) ([\d.]+)"', _map_svg)
MAP_W, MAP_H = float(_mvb.group(3)), float(_mvb.group(4))
MAP_ASPECT = round(MAP_W / MAP_H, 4)
_map_svg = _re.sub(r'<rect x="[-\d.]+" y="[-\d.]+" width="[\d.]+" height="[\d.]+" '
                   r'fill="#000000"/>\s*', '', _map_svg, count=1)
_map_svg = _re.sub(r'\swidth="[^"]*"', '', _map_svg, count=1)
_map_svg = _re.sub(r'\sheight="[^"]*"', '', _map_svg, count=1)
_map_svg = _map_svg.replace('<svg', '<svg class="map"', 1)





# --- the market, rebuilt as the map's own hex tiles -------------------------------------------
# Sixteen tiles in round order -- twelve buildings and four season ends -- from the same seeded
# setup the map is drawn from, so a name here is that name on the map's edge, on that round.
# Ownership is the foot bar; state is the field: dark grey donated, light grey used this turn.
# /tmp/mkmarketsvg.py builds it against the panel's content box, so it drops in at 1:1.
_mktsvg = IN("market-hex.svg")
_mvb2 = _re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', _mktsvg)
MKT_W, MKT_H = float(_mvb2.group(1)), float(_mvb2.group(2))
_mktsvg = _re.sub(r'\swidth="[\d.]+"', '', _mktsvg, count=1)
_mktsvg = _re.sub(r'\sheight="[\d.]+"', '', _mktsvg, count=1)
MARKET = '<div class="strip"><div class="mkt mkthex">' + _mktsvg + '</div></div>'

# --- the log, at the foot of the player column ------------------------------------------------
# Real events from scenarios/play_view_reference_4p_001.json played out with random legal actions,
# rewritten into the log rule's voice: actor, took, the DUTY TILE, and what happened. The seat is
# carried by the alms table's own player disc rather than by the name's colour -- on parchment the
# yellow and white seats measure 1.4:1 and 1.2:1, which is not a text colour.
# The log speaks the action box's language: the four stock names become the same inline glyphs,
# and the Merchant becomes the wagon the duty tiles carry. Two proper nouns have to be shielded
# first -- Stone Mason is a special activity and Stone Yard a building, and neither is a stone.
_logbody = IN("log-body.html")

# A special activity becomes its own icon from the table above -- but BOXED. Two of the six are
# drawn with a stock glyph (Fields is the wheat, Stone Mason the stone cube), and in the Special
# Activities table a column heading cannot be mistaken for a resource, while in a sentence it can.
# The box is the duty tiles' own action pill, and it says "a space" rather than "a thing".
def _sa_ico(name, tight=False):
    glyph = dict((n, g) for n, g in SA_ACTS)[name]
    return ('<span class="sabox%s" title="%s"><svg viewBox="0 0 26 26" width="17" height="17">%s'
            '</svg></span>' % (" tight" if tight else "", name,
                               _sa_glyph(glyph, 13, 13, 15, "#2A2320")))

# Names are swapped for TOKENS first and expanded to markup only at the end. Substituting the
# markup directly puts the name back into the document inside the span's own title, where the
# next pass finds it again and eats half the tag.
_SA_NAMES = sorted((n for n, _g in SA_ACTS), key=len, reverse=True)   # longest first
for _i, _nm in enumerate(_SA_NAMES):
    # a box before a full stop or comma drops its right margin, or the punctuation is left adrift
    _logbody = _re.sub(r"\s*\b%s\b\s*(?=[.,])" % _nm, "\x10%dT\x11" % _i, _logbody)
    _logbody = _re.sub(r"\s*\b%s\b\s*" % _nm, "\x10%dL\x11" % _i, _logbody)

# Stone Yard is a BUILDING, not a stock and not a space, so it is shielded from the stock pass
_GUARD = {"Stone Yard": "\x02"}
for _phrase, _mark in _GUARD.items():
    _logbody = _logbody.replace(_phrase, _mark)
_logbody = _icons(_logbody)
for _phrase, _mark in _GUARD.items():
    _logbody = _logbody.replace(_mark, _phrase)
_logbody = _re.sub(r"\x10(\d+)([TL])\x11",
                   lambda m: _sa_ico(_SA_NAMES[int(m.group(1))], tight=m.group(2) == "T"),
                   _logbody)
# the wagon travels as its own symbol so it does not depend on the duty wheel's defs, which are
# display:none whenever the map is showing
_WGN_DEFS = ('<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>'
             '<mask id="wgnLogM" maskUnits="userSpaceOnUse" x="0" y="1.94" width="100" '
             'height="96.11"><rect x="0" y="1.94" width="100" height="96.11" fill="#fff"/>'
             '<circle cx="18.7" cy="79.94" r="14" fill="#000"/>'
             '<circle cx="81.2" cy="79.94" r="14" fill="#000"/></mask>'
             '<g id="wgnLog"><path d="%s" fill="currentColor" stroke="currentColor" '
             'stroke-width="2.6" stroke-linejoin="round" mask="url(#wgnLogM)"/></g>'
             '</defs></svg>' % _WAGON_D)
_logbody = _logbody.replace(
    "The Merchant",
    '<svg class="ico wgn" viewBox="0 0 100 100" width="17" height="17">'
    '<use href="#wgnLog"/></svg>')

# the processed body is kept so the standalone study renders exactly what the board renders
pathlib.Path(os.environ.get('LOG_OUT') or (OUT + '_log_final.html')).write_text(_WGN_DEFS + _logbody)
_CHEV = ('<svg class="chev" width="13" height="13" viewBox="0 0 24 24" fill="none" '
         'stroke="#6B6355" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">'
         '<path d="M6 15 L12 9 L18 15"/></svg>')
LOG = ('<div class="log">' + _WGN_DEFS
       + '<div class="lhead" id="lhead" title="Expand the log">'
         '<span>Log</span>' + _CHEV + '</div><div class="lwrap">'
       '<div class="lbody" id="logBody">' + _logbody + '</div></div></div>')


P,SEAT,INK,PARCH,PALE = gb.PLAYERS, gb.SEAT, gb.INK, gb.PARCH, gb.PALE
LIGHT="#F0E7D2"; PALEGLYPH="#A89B7E"

def _seat_disc(seat, mid=False):
    """The log's player mark, built from the board's OWN seat palette so the two cannot drift.
    Every gap around a disc is a margin, never a space character -- a literal space is ~3.4px at
    this size and the margin is 6, which is what made three different gaps in the log."""
    f, s = SEAT[seat]
    return ('<span class="disc%s" style="background:%s;border-color:%s"></span>'
            % (" mid" if mid else "", f, s))
# One margin governs the card's right and bottom edges, and it is the Buildings table's own:
# 15.4 px, which in this frame (a unit renders 0.9642) is 15.97. The card was 320 wide and left
# 20.0 between the silver pill and its edge; 316 leaves 15.97, and the resource row is anchored to
# the same figure below rather than centred in what is left.
MARGIN = round(15.4 / (339.4 / 352.0), 2)        # 15.97
TOP=16; W=316; H=112
# The piety pill joins the resources on the bottom row, so that row carries four slots and the
# top band only the two cube counts. The cubes come down to the duty tiles' own cube size --
# 11.96 board units draws the 14.24 px a tile cube draws -- and the band, sized for 18-unit
# cubes, comes down with them from 56 to 40.
# With the figures under the pills rather than beside them a slot is only as wide as its
# pill, so the four re-centre in the space the portrait leaves: span 90..300 in a card whose
# usable width starts at the collar's edge, 71, and ends at 320.
# The portrait came INSIDE the card so the expanded log covers it (see below), which cost the
# pill row 20 units on its left. The right margin is fixed -- the silver pill keeps the card's
# own 16 -- so the row absorbs it by closing up: pitch 58 -> 51.33, and the gap between pills
# 22 -> 15.33 units (21.2 -> 14.8 px). The first pill still stands 19 units off the collar,
# the gap it always kept.
COLS=(128,179.3,230.7,282)      # the bottom row: piety, wheat, stone, silver
CUBE_COLS=(128,179.3)           # the top band: serfs, acolytes, on the same two centres
CUBE_SZ=11.96; BAND_H=40
# A slot is now a block of mark + gap + figure rather than the mark alone, so each row centres
# that block in the area it owns: the cubes in the coloured band, the pills in the parchment
# under it. FIGGAP is measured from the mark's own edge, so both rows share one gap.
FIGGAP=15; FIGCAP=11
R1=TOP+(BAND_H-(CUBE_SZ+FIGGAP))/2+CUBE_SZ/2
# hung from the bottom margin, not centred: the figures' baseline sits MARGIN above the card's
# lower edge, which is the same gap the silver pill keeps from its right edge
R2=TOP+H-MARGIN-FIGGAP-gb.PILL_H/2
# The medallion is pulled INSIDE the card so that nothing of it shows when the expanded log
# covers the column. The log's open rectangle is the card's own left edge and 8 units above its
# top edge (7.7 px, measured), so the collar has to clear x=0 and y=8; at r=45 that puts its
# centre at 45,53 exactly tangent to both. One unit of clearance on each kills the rounding
# sliver, hence 46,54. The cost is the badge: the collar no longer breaks the card's frame.
PR=38; PX,PY=46,54; COLLAR=PR+7      # the portrait, a little smaller than 44
SR=18; SA=44.0                       # and its seal with it, so the rim reads the same
SX=round(PX+PR*math.cos(math.radians(SA)),1); SY=round(PY+PR*math.sin(math.radians(SA)),1)
DARKSEAT={"red":False,"blue":False,"yellow":True,"white":True}

# --- the sizing decision -----------------------------------------------------------------------
CANVAS_W, CANVAS_H = 1600, 1067          # 3:2
BODY = 13.5                              # the action box's body type, in canvas units
BOARD_NUM = 14.0                         # a player board draws its figures at 14 of its own units
SVG_BOX = 352.0                          # both components are drawn in a 352-wide frame
COMP_W = round(SVG_BOX * BODY / BOARD_NUM, 1)   # 339.4 -> the two components' width
PANEL_W = 305                            # the action box
K = COMP_W/SVG_BOX                       # the components' scale
ALMS_INSET = round(8*K,1)                # the alms panel's own top inset inside its svg
ALMS_H = round(132*K,1)                  # the alms panel's visible height
GAP = 40                                 # the gutter between the action box and the wheel
GAP1 = 24                                # ...and a narrower one before the action box

_u=[0]
def circ_path(cx,cy,r):
    return "M%s %s A%s %s 0 1 0 %s %s A%s %s 0 1 0 %s %s Z"%(cx-r,cy,r,r,cx+r,cy,r,r,cx-r,cy)
def card_path(w,h):
    return ("M9 %s H%s A9 9 0 0 1 %s %s V%s A9 9 0 0 1 %s %s H9 A9 9 0 0 1 0 %s V%s A9 9 0 0 1 9 %s Z"
            % (TOP,w-9,w,TOP+9,TOP+h-9,w-9,TOP+h,TOP+h-9,TOP+9,TOP))
def hole_clip(hole,w,h):
    _u[0]+=1; cid="hc%d"%_u[0]
    big="M-70 -70 H%s V%s H-70 Z"%(w+70,h+TOP+70)
    return cid,'<clipPath id="%s"><path clip-rule="evenodd" d="%s %s"/></clipPath>'%(cid,big,hole)
def in_clip(shape):
    _u[0]+=1; cid="ic%d"%_u[0]
    return cid,'<clipPath id="%s"><path d="%s"/></clipPath>'%(cid,shape)
def slot(cx,y,mark,val,dx=23,below=False,half=None):
    """gb.slot, with the figure either beside the mark or centred beneath it.

    Beneath, a slot is only as wide as its mark, which is what lets the bottom row hold four.
    The offset is open because a 12-unit cube does not want a gap sized for a 36-unit pill.
    """
    g = '<g transform="translate(%s %s)">%s</g>' % (cx, y, mark)
    if below:
        return g + gb.num(cx, y + (gb.PILL_H/2 if half is None else half) + FIGGAP,
                          val, anchor="middle")
    return g + gb.num(cx+dx, y+5, val)
_POP_DEFS, _POP_ASP = pop.defs()

def _pill_slot(kind, pill):
    """Split a pill into its shell and its mark, and make the mark swappable.

    The shell is one self-closing rect, so the split is the first '/>'. The shell keeps the pill's
    colour and shape; only the mark inside it is a slot, which is what an icon picker changes."""
    i = pill.index("/>") + 2
    return pill[:i] + '<g class="pslot" data-slot="%s">%s</g>' % (kind, pill[i:])

def rows(p):
    f,s=SEAT[p["seat"]]; ac=s if p["seat"]!="white" else "#8B7B4E"
    o=[pop.band(COLS, CUBE_SZ, TOP, BAND_H, INK, gb.num,
                (gb.cube(gb.SERF_F, gb.SERF_S, CUBE_SZ), gb.cube(f, ac, CUBE_SZ)),
                (p["serfs"], p["acolytes"]), _POP_ASP),
       slot(COLS[0],R2,_pill_slot("piety", gb.pietyPill("cross")),p["piety"],below=True)]
    for x,k in zip(COLS[1:],("wheat","stone","silver")):
        o.append(slot(x,R2,_pill_slot(k, gb.resPill(k)),p[k],below=True))
    return "".join(o)

# Room for a frame to be laid over the card. Off by default, so the board is unchanged; the
# picker turns it on, because a frame overhangs the card on every side and would otherwise be
# cut off by the viewBox.
FRAME_ROOM = False
CARD_VIEWBOX = "-30 -8 352 140"
CARD_VIEWBOX_FRAMED = "-30 -20 352 158"


def portrait(p):
    """The portrait disc, with its mark in a swappable slot.

    The mark is the only seat-coloured thing on the card, so the colour sits on the SLOT rather
    than in the file: the drawn figure is stored as `pilgrim_portrait.svg` with currentColor and
    picks the seat up from here, while a photographic portrait ignores it. Both are clipped by the
    group, so a swap cannot leak outside the disc.
    """
    f,s=SEAT[p["seat"]]; act=p.get("active")
    glyph=(s if DARKSEAT[p["seat"]] else LIGHT) if act else PALEGLYPH
    cid,defs=in_clip(circ_path(PX,PY,PR))
    o=defs+'<circle cx="%s" cy="%s" r="%s" fill="%s"/>'%(PX,PY,PR,f if act else LIGHT)
    # The clip stays on its own untransformed group. A clip-path resolves in the user space the
    # element itself establishes, so putting it on the translated group moved the clipping circle
    # to (2*PX, 2*PY) and quietly cut the figure -- 8669 pixels different, and invisible in a diff
    # of the markup.
    o+=('<g clip-path="url(#%s)">'
        '<g class="pslot" data-slot="portrait" color="%s" transform="translate(%s %s)">'
        '<g transform="scale(%s)" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="0" cy="-4" r="6.5"/><path d="M-11 14 V9 a11 11 0 0 1 22 0 V14"/></g></g></g>'
        %(cid,glyph,PX,PY,PR/19.8))
    return o


def frame_slot():
    """An empty slot for a player-board frame, laid over the finished card.

    A frame of this kind has a portrait opening, so it is positioned by that opening rather than
    by its own box -- the picker computes the translate from `openingCirclePx` in assets.json and
    sizes the image so the opening lands on the portrait circle. Empty here: the board draws no
    frame, and only a page that offers one fills it.
    """
    return '<g class="pslot" data-slot="frame"></g>' 
def player_card(p):
    f,_=SEAT[p["seat"]]
    CARD=card_path(W,H); COL=circ_path(PX,PY,COLLAR)
    c1,d1=hole_clip(COL,W,H); c2,d2=hole_clip(CARD,W,H); cid,d3=in_clip(CARD)
    o='<defs>%s%s%s</defs>'%(d1,d2,d3)
    o+='<path d="%s" fill="%s"/>'%(CARD,PARCH)
    # the seat spine runs to the portrait's own centre line -- it was a literal 26 back when the
    # portrait sat at 26, and the medallion straddling the spine's edge is the whole shape
    o+=('<g clip-path="url(#%s)"><path d="M0 %s H%s V%s H0 Z" fill="%s"/></g>'
        '<circle cx="%s" cy="%s" r="%s" fill="%s"/>'%(cid,TOP,PX,TOP+H,f,PX,PY,COLLAR,f))
    o+=('<g clip-path="url(#%s)"><path d="M0 %s H%s V%s H0 Z" fill="%s" opacity=".18"/></g>'
        %(cid,TOP,W,TOP+BAND_H,f))
    o+=rows(p)+portrait(p)
    o+='<circle cx="%s" cy="%s" r="%s" fill="none" stroke="%s" stroke-width="1.2"/>'%(PX,PY,PR,INK)
    o+=('<g clip-path="url(#%s)"><path d="%s" fill="none" stroke="%s" stroke-width="1.4"/></g>'
        '<g clip-path="url(#%s)"><path d="%s" fill="none" stroke="%s" stroke-width="1.4"/></g>'
        %(c1,CARD,INK,c2,COLLAR,INK))
    if p.get("seal"): o+=gb.seal(SX,SY,SR)
    # The frame goes last: it has a portrait opening and an open panel, so it is an overlay the
    # card shows through, not a backdrop.
    o+=frame_slot()
    # `color` on the card, not on the page: third-party marks are stored with fill="currentColor"
    # so the renderer can recolour them, and without this they inherit whatever colour the
    # surrounding page happens to use -- which on a dark page painted them near-invisible in the
    # pills. Carrying it on the card means the card is right wherever it is embedded.
    vb = CARD_VIEWBOX_FRAMED if FRAME_ROOM else CARD_VIEWBOX
    vh = float(vb.split()[3])
    return '<svg class="seat" color="%s" viewBox="%s" width="%s" height="%s">%s</svg>'%(
        INK, vb, COMP_W, round(vh*COMP_W/SVG_BOX,1), o)

alms=ap.panel_svg(P, SEAT, INK, PARCH, positions={"red":0,"yellow":0,"blue":0,"white":0},
                  width=COMP_W, win_seats=["blue"])
boards="".join(player_card(p) for p in P)

TURN='''<div class="turn">
  <div class="phase now first">Sow</div>
  <div class="stage-row"><span class="tick">&#10003;</span>Use or hire buildings</div>
  <div class="stage-row"><span class="tick">&#10003;</span><span class="hand"><span>Lift acolytes</span><i class="dot">&middot;</i><span>In hand</span><svg viewBox="0 0 16 16" width="13" height="13"><rect x=".6" y=".6" width="14.8" height="14.8" fill="#B9B2A2" stroke="#2A2320" stroke-width="1.1"/></svg><b>&times;&nbsp;3</b></span></div>
  <div class="stage-row"><span class="tick">&#10003;</span>Walk the route</div>
  <div class="stage-row now"><span class="tick">&#9654;</span>Take a duty</div>
  <div class="stage-row"><span class="tick"></span>Action or Tithe</div>
  <div class="phase">End of Turn</div>
  <div class="stage-row"><span class="tick"></span>Use or hire buildings</div>
  <div class="stage-row"><span class="tick"></span>End the turn</div>
  <hr class="sep">
  <p class="ask"><b>Take a duty.</b> Your two acolytes stopped on Clerical &mdash; take it, or
    walk on and pay a tithe.</p>
  <div class="btns">
    <button class="btn">Take Clerical</button>
    <button class="btn ghost">Walk on &middot; pay 1 tithe</button>
  </div>
  <div class="hire">
    <div class="lab">Hire</div>
    <div class="what">%s</div>
    <div class="btns" style="margin:0">
      <button class="btn">Hire the Chapel</button>
      <button class="btn ghost">Don&rsquo;t hire</button>
    </div>
  </div>
  <div class="inspect" id="inspect"><span class="lab">Duty</span>
    <div class="body" id="inspectBody"><span class="rest">Point at a duty action or building
    to read it.</span></div>
  </div>
  <div class="last"><span class="lab">Last</span><span class="msg">%s</span></div>
</div>'''

INSPECT_JS_TMPL = """
(function(){
  var T = TABLE;
  var body = document.getElementById('inspectBody');
  var rest = body.innerHTML;
  Array.prototype.forEach.call(document.querySelectorAll('.wheel .act'), function (g) {
    g.addEventListener('mouseenter', function () {
      var d = T[g.getAttribute('data-duty') + '|' + g.getAttribute('data-i')];
      if (!d) { return; }
      body.innerHTML = '<b>' + d[0] + '</b> \\u2014 ' + d[1]
        + (d[2] ? '<div class="sub">' + d[2] + '</div>' : '');
    });
    g.addEventListener('mouseleave', function () { body.innerHTML = rest; });
  });
})();
"""

CSS = """
*{box-sizing:border-box}
html,body{height:100%%;margin:0;overflow:hidden;background:#0C0F0A;
  font:14px/1.5 "Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;color:#E8E2D3}
.stage{position:absolute;top:0;left:0;transform-origin:top left;background:#2F5237;
  display:flex;flex-direction:column;padding:14px}
.left{display:flex;flex-direction:column;flex:0 0 %(cw)spx;align-self:stretch;position:relative}
.boards{display:flex;flex-direction:column;gap:30px}
/* Three panels across the head of the board, one over each column and all on one line: Special
   Activities over the player cards, the Alms Table over the action box, Buildings over the wheel.
   Both of the left two are taken out of flow so only the Buildings table sets the row's height,
   and both are nudged the same 0.7 -- their strokes sit ON their edges, the Buildings frame's
   sits inside. */
.sa{display:block}
.top>svg.sa{position:absolute;left:0;top:-7.04px}
.seat,.alms{display:block}
.wheel{display:block;flex:0 0 auto}
.row{display:flex;gap:%(gap)spx;align-items:flex-start;flex:1;min-height:0}
.row>.left{margin-right:%(gapdiff)spx}
.top{display:flex;gap:%(gap)spx;margin-bottom:%(gap)spx;align-items:flex-start}
.top .alms{flex:0 0 auto}
/* The Alms Table leaves the player-board column and takes the action box's. It keeps its own
   339.4 -- that width is what makes its numerals come out the size of the action box's body
   text, and shrinking it to the box's 305 would break the one rule the whole layout is built
   on -- so it is CENTRED over the box rather than fitted to it. */
.top{position:relative}
.top>svg.alms{position:absolute;left:%(almsx)spx;top:-7.04px}
.strip{flex:0 0 %(mktw)spx;margin-left:auto;margin-top:0;height:%(mkth)spx}
.mkt{height:100%%;display:flex;flex-direction:column}
.mkt{background:#E5D8B9;border:1.4px solid #2A2320;border-radius:9px;padding:10px 12px;
  color:#2A2320}
.mkthex{padding:0;background:none;border:none;border-radius:0}
/* The log gives the player column its foot back -- the job Special Activities used to do before
   it went to the head of the board -- so the three columns end on one line again. */
.log{flex:1;min-height:0;margin:30px 0 0 28.9px;width:304.7px;position:relative;
  background:#E5D8B9;border:1.35px solid #2A2320;border-radius:11.6px;
  display:flex;flex-direction:column;box-sizing:border-box}
.log::after{content:'';position:absolute;inset:5.78px;border:1.06px solid rgba(42,35,32,.30);
  border-radius:6.75px;pointer-events:none}
.lhead{font:700 14.46px Georgia,serif;color:#2A2320;padding:13px 14.05px 7px;
  display:flex;align-items:center;justify-content:space-between;cursor:pointer;user-select:none}
/* Expanded, the log takes the whole player column. top:0 works because the column starts on the
   SAME line as the action box row (its first child carries a -15.4 margin), so the panel's top
   edge lands on a rule the board already has rather than one of its own choosing -- only the
   seat rings' outer arc rides above it, and those overhang their own cards everywhere else too.
   The BOTTOM is pinned, so the newest entry -- where the eye already is -- stays put and history
   opens above it. */
.log.big{position:absolute;top:0;bottom:0;left:28.9px;width:304.7px;margin:0;z-index:5}
.log .chev{flex:0 0 auto;opacity:.55;transition:transform .15s ease,opacity .15s ease}
.lhead:hover .chev{opacity:1}
.log.big .chev{transform:rotate(180deg)}
/* The scroll region is INSET so its bar can never land on the keyline, the bar is the board's own
   #A89B7E at 6px on a transparent track, and the top edge is masked so entries dissolve into the
   parchment instead of being sliced by the frame. */
/* The fade is an OVERLAY, not a mask on the scroll box: a mask clips the scrollbar with the
   content, which is how the bar disappeared entirely on the first attempt. */
.lwrap{position:relative;flex:1;min-height:0;display:flex;margin:0 9.6px 9.6px 0}
.lbody{flex:1;min-width:0;overflow-y:auto;padding:0 5px 3px 14.05px;
  font:13.5px/19.575px Georgia,serif;color:#2A2320;
  scrollbar-width:thin;scrollbar-color:#8A7F62 #DACDAB;scroll-snap-type:y proximity}
.log .e,.log .ev,.log .rule{scroll-snap-align:start}
/* Hanging indent: a wrapped entry's second line lines up with its own first WORD, not under the
   disc, so an entry reads as one block the way the action box's Duty and Last lines do. The
   indent is the mark's width plus its margin -- 16 for a disc, 22 for the wagon. */
.log .e,.log .ev{padding:0 0 0 16px;text-indent:-16px;margin:3.5px 0}
.log .ev.merch{padding-left:22px;text-indent:-22px}
.log .ev{color:#6B6355;font-style:italic}
/* the duty tile is the word the eye scans for, so it takes the weight the action box gives the
   actor's name -- the actor being a disc here, which carries its own */
.log .e b{font-weight:700}
.log .sabox{display:inline-block;border:1px solid #A08F6A;border-radius:3px;background:#EFE4C6;
  line-height:0;padding:1px;margin:0 5px;vertical-align:-5px;text-indent:0}
.log .sabox.tight{margin-right:1px}
.log .nm{font-weight:700}
/* the disc is the whole name now, so it stands a little larger. Its spacing is ALL margin --
   the text either side carries no space of its own -- so every gap around every disc is 6. */
.log .disc,.last .disc{display:inline-block;width:10px;height:10px;border-radius:50%%;
  border:1.25px solid;vertical-align:-0.5px;margin-right:6px}
.log .disc.mid,.last .disc.mid{margin-left:6px}
/* the stock glyphs sit on the text's own baseline; the wagon is wider than tall so
   it gets its own size and a hair of lift */
.log .ico{vertical-align:-2.5px;margin:0 1px 0 0}
.log .ico.wgn{color:#5A3E8C;vertical-align:-4px;margin-right:3px}
.log .rule{display:flex;align-items:center;gap:9px;margin:9px 0 5px;color:#6B6355;
  font:700 11.5px Georgia,serif;letter-spacing:.09em;text-transform:uppercase}
.log .rule::before,.log .rule::after{content:'';flex:1;height:1px;background:#A89B7E;opacity:.6}
.mkthex svg{display:block;width:100%%;height:100%%}
.tiles1{flex:1;min-height:0}
.four{flex:1;min-height:0}
.tiles1{display:flex;gap:20px}
.grp{flex:1;display:flex;flex-direction:column;gap:7px;min-width:0}
.glab{font-size:11.5px;letter-spacing:.09em;text-transform:uppercase;color:#6B6355}
.four{display:grid;grid-template-columns:repeat(4,1fr);gap:7px}
.tiles1 .tile{position:relative;border:1px solid #A89B7E;border-radius:8px;background:#EFE6CC;
  padding:7px 7px 8px;display:flex;flex-direction:column;gap:5px;min-height:0;
  background-repeat:no-repeat}
.tiles1 .tile.future{background-color:#E2D7B8}
.tiles1 .tile.gone{background-color:#D9CFB2;border-color:#BCB093}
.tiles1 .tile.gone .nm{color:#7A7263}
.tiles1 .tile.livet{border-color:#5A8A58}
.tiles1 .th{display:flex;align-items:center;gap:5px;flex-wrap:wrap}
.tiles1 .nm{font-size:13px;font-weight:600;line-height:1.2;flex-basis:100%%;color:#2A2320}
.tiles1 .rd{position:absolute;right:7px;bottom:7px;display:inline-flex;align-items:center;
  justify-content:center;min-width:22px;height:19px;padding:0 4px;border-radius:5px;
  font-size:12px;font-weight:700;border:1px solid #A89B7E;background:#DCD0AC;color:#6B6355}
.tiles1 .rd.live{border-color:#5A8A58;background:#CBDCC0;color:#2F5237}

.turn{flex:0 0 %(pw)spx;align-self:stretch;display:flex;flex-direction:column;background:#E5D8B9;
  border:1.4px solid #2A2320;border-radius:9px;padding:13px 14px;color:#2A2320;position:relative}
.turn::after{content:"";position:absolute;inset:7px;border:.9px solid #A89B7E;border-radius:5px;
  pointer-events:none}
.turn>*{position:relative;z-index:1}
.phase.first{margin-top:0}
.phase{font-size:12px;letter-spacing:.07em;text-transform:uppercase;color:#6B6355;
  margin:9px 0 4px}
.phase.now{color:#2A2320;font-weight:700}
.stage-row{display:flex;align-items:center;gap:9px;font-size:13.5px;color:#6B6355;
  padding:2.5px 0 2.5px 4px}
.stage-row .tick{width:15px;text-align:center;font-size:12.5px;color:#7E9A72}
.stage-row.now{color:#2A2320;font-weight:700}
.stage-row.now .tick{color:#2A2320}
.sep{border:0;border-top:1px solid #A89B7E;margin:11px 0 10px}
.ask{font-size:13.5px;line-height:1.45;margin:0 0 10px}
.btns{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:4px}
.btn{font:inherit;font-size:13.5px;color:#2A2320;background:#F0E7D2;border:1.2px solid #2A2320;
  border-radius:6px;padding:7px 12px;cursor:pointer}
.btn:hover{background:#FBF4E2}
.btn.ghost{border-style:dashed;color:#6B6355}
.hire{margin-top:11px;padding:10px 11px;background:#DCCFA8;border:1px solid #A89B7E;
  border-left:4px solid #C9A227;border-radius:6px}
.hire .lab{font-size:11.5px;letter-spacing:.09em;text-transform:uppercase;color:#6B6355;
  margin-bottom:6px}
.hire .what{font-size:13.5px;margin-bottom:8px}
/* the same shape as Last: the label holds its own column and the text hangs beside it, so a
   line that wraps starts under the first word rather than under the label */
.inspect{margin-top:auto;display:flex;align-items:baseline;gap:7px;padding-top:10px;
  border-top:1px solid #A89B7E;height:196px;flex:0 0 auto;overflow:hidden}
.inspect .lab{flex:0 0 auto;font-size:11px;letter-spacing:.09em;text-transform:uppercase;
  color:#8A7F62}
.inspect .body{flex:1;min-width:0;font-size:13.5px;line-height:1.45;color:#2A2320}
.inspect .body b{font-weight:700}
.inspect .rest{color:#B7382E;font-style:italic}\n.inspect .sub{margin-top:3px;font-size:12.5px;color:#6B6355}
.ico{display:inline-block;vertical-align:-3px;margin:0 1px 0 0}
/* the map is the wheel's other face: same slot, one shown at a time. The stage keeps the
   class, so everything else on the table is untouched by the swap. */
.map{display:none;flex:0 0 auto}
/* the map's 18xx hex coordinates are build-time furniture: they name a hex while the map is
   being drawn, and nothing in play refers to one. Hidden, not deleted -- they are still in the
   file to switch back on when a hex has to be named. */
.map .hexref{display:none}
.stage.mapview .wheel{display:none}
.stage.mapview .map{display:block}
/* the view button lives on the table, not in the debug hud, so it scales with the board and
   sits in the empty green under the wheel. It names the view you would GET, as a door does. */
.viewbtn{position:absolute;right:14px;bottom:14px;display:inline-flex;align-items:center;gap:8px;
  font:600 15px/1 Georgia,serif;letter-spacing:.02em;color:#2A2320;background:#E8DEC2;
  border:1.4px solid #2A2320;border-radius:9px;padding:9px 15px 9px 12px;cursor:pointer;
  box-shadow:0 1px 0 rgba(0,0,0,.25)}
.viewbtn:hover{background:#F5EDD8}
.viewbtn svg{display:block;flex:0 0 auto}
/* a hidden copy of the longer name holds the width open, so the button does not resize
   under the cursor when the view changes; the live label is right-aligned inside it */
.vbw{position:relative;display:inline-block}
.vbw .ghost{visibility:hidden}
.vbw #vbl{position:absolute;right:0;top:0;white-space:nowrap}
.wheel .act{cursor:pointer}
.wheel .act rect{transition:fill .08s linear,stroke .08s linear}
.wheel .act:hover rect{fill:#F8F1DC;stroke:#6B5C3E;stroke-width:1.8}
/* Cubes in hand: one readout for the turn, and it rides on the step that creates it --
   lifting acolytes is what puts cubes in the hand. The cube is
   a neutral stone, as it was before: a handful lifted off a duty tile can hold more than one
   seat's colour, and painting it in one of them would say something the count does not. */

/* one inline-flex row, so the gap either side of the dot is the same number and
   "In hand" inherits the step's own type rather than the small-caps label style */
.hand{display:inline-flex;align-items:center;gap:7px;line-height:1}
.hand .dot{font-style:normal;color:#A89B7E}
.hand b{font-size:13.5px;font-weight:700;color:#2A2320}
.hand svg{display:block;flex:0 0 auto}
/* the label keeps its own column, so a message that runs to a second line hangs
   under the first word rather than under the label */
.last{display:flex;align-items:baseline;gap:7px;padding-top:10px;
  border-top:1px solid #A89B7E;font-size:13px;color:#4A4238;line-height:1.45}
.last .msg{flex:1;min-width:0}
.last .lab{flex:0 0 auto;font-size:11px;letter-spacing:.09em;text-transform:uppercase;
  color:#8A7F62}
.last i{font-style:normal;font-weight:700;color:#2A2320}
/* Last speaks the log's sentence, so it takes the log's marks: the actor is a disc, the duty
   tile carries the weight the actor's name used to. One voice in both places. */
.last b{font-weight:700;color:#2A2320}
.hud{position:fixed;right:150px;bottom:10px;font:11px/1.4 ui-monospace,Menlo,monospace;
  color:#B9C7B4;background:rgba(10,14,10,.6);padding:4px 8px;border-radius:5px;z-index:9}
.hud b{color:#F0E7D2;font-weight:600}
.hud button{font:inherit;color:#E8E2D3;background:#3A4A38;border:1px solid #5A6B57;
  border-radius:4px;padding:1px 6px;margin-left:8px;cursor:pointer}
""" % {"cw":COMP_W, "pw":PANEL_W, "gap":GAP, "gapdiff":GAP1-GAP, "mktw":MKT_W, "mkth":MKT_H,
        "almsx":round(COMP_W + GAP1 - 30*COMP_W/352, 1),
}

SCRIPT = """
const CW=%(canvas_w)s, CH=%(canvas_h)s, BODY=%(body)s, NUM=%(num)s;
// how far the COLLAR's top sits below the svg's own top edge, in card units: the viewBox starts
// at y -8 and the collar's top is PY-COLLAR. It was the portrait circle that was pinned here,
// but the collar is 7 units larger, so pinning the inner disc left the outer ring standing 7
// units proud of the action box -- 6.75 px that the expanded log could never cover. The outer
// ink is the thing to align anyway. The extra -1 drops the collar a unit below the line so the
// log's edge covers it outright rather than meeting it exactly.
const PTOP=%(ptop)s;
const stage=document.querySelector('.stage');
let zoom=1, one=false;
function fit(){
  // measure on the wheel's face, always: the map's box is derived from it
  const wasMap=stage.classList.contains('mapview'); if(wasMap) stage.classList.remove('mapview');
  zoom = one ? 1 : Math.min(innerWidth/CW, innerHeight/CH);
  stage.style.width=CW+'px'; stage.style.height=CH+'px';
  stage.style.transform='translate('+((innerWidth-CW*zoom)/2).toFixed(1)+'px,'
    +((innerHeight-CH*zoom)/2).toFixed(1)+'px) scale('+zoom.toFixed(4)+')';
  // the action box runs from the alms panel's top edge to the last board's bottom edge
  const svgs=document.querySelectorAll('.boards svg');
  const k=%(comp_w)s/352;
  const turn=document.querySelector('.turn');
  const row=document.querySelector('.row').getBoundingClientRect();
  turn.style.height='';                          // measure with it stretched to the row
  // the first collar's top edge meets the action box's own top edge
  const boards=document.querySelector('.boards');
  boards.style.marginTop='0px';
  const rule=turn.getBoundingClientRect().top;
  const nowTop=svgs[0].getBoundingClientRect().y + PTOP*k*zoom;
  boards.style.marginTop=((rule-nowTop)/zoom).toFixed(1)+'px';
  // The action box used to stop where the left column stopped, because Special Activities held
  // that column's foot. It sits at the head of the board now, so the four cards keep their own
  // spacing and end where they end, and the box takes the ROW's height instead -- the same height
  // the wheel takes. Nothing in the column is stretched to reach it.
  const H=row.height/zoom;
  turn.style.height=H.toFixed(1)+'px';
  // the wheel is sized so its TOP and BOTTOM duty tiles meet the action box's top and bottom
  // edges -- its own box carries empty margin above and below those tiles, so the box has to be
  // larger than the span we are matching. The margin is measured, not assumed.
  const room=CW-28-%(comp_w)s-%(gap)s-%(gap1)s-%(panel_w)s;
  const w=document.querySelector('.wheel');
  const tiles=()=>{let t=Infinity,b=-Infinity;
    w.querySelectorAll('rect').forEach(e=>{const r=e.getBoundingClientRect();
      if(r.width>60*zoom&&r.height>60*zoom){if(r.y<t)t=r.y; if(r.bottom>b)b=r.bottom;}});
    return [t,b];};
  let side=Math.min(room, row.height/zoom);
  w.style.width=side+'px'; w.style.height=side+'px'; w.style.marginTop='0px';
  let [tt,tb]=tiles();
  const want=H*zoom, span=tb-tt;
  side=Math.min(room, row.height/zoom, side*want/span);
  w.style.width=side+'px'; w.style.height=side+'px';
  [tt,tb]=tiles();
  // The wheel WANTS its top and bottom tiles on the action box's top and bottom edges, but it
  // cannot always have that: it is width-limited here (it needs all 848 of the slot, and the box
  // is 860 tall), so the tiles fall short of the box and the leftover has to go somewhere. Top-
  // aligning put all of it under Produce. Centring splits it, which is what the map does, and the
  // two views then sit on the same axis both ways. When the wheel is tall enough to span the box
  // this line is a no-op, because the leftover is zero.
  w.style.marginTop=((turn.getBoundingClientRect().y+(want-(tb-tt))/2-tt)/zoom).toFixed(1)+'px';
  // Horizontally the wheel takes its axis from the Buildings table above it. The table's own
  // margins are equal, so its box centre IS its ribbon's centre, and centring the wheel on the
  // strip centres it on the tiles. Measured, not assumed: the wheel may be width- or height-bound
  // depending on the window, and only one of those fills the slot.
  const strip=document.querySelector('.strip').getBoundingClientRect();
  w.style.marginLeft='0px';
  const wb=w.getBoundingClientRect();
  w.style.marginLeft=(((strip.x+strip.width/2)-(wb.x+wb.width/2))/zoom).toFixed(1)+'px';
  // The map is measured off the wheel, so it is sized while the wheel is still on screen and
  // the swap is a pure show/hide afterwards. Full height of the action box, its own aspect for
  // the width, and the leftover width of the wheel's slot split evenly so it stays centred
  // where the wheel was.
  const mp=document.querySelector('.map');
  if(mp){ const mw=H*%(map_aspect)s;
    mp.style.height=H.toFixed(1)+'px'; mp.style.width=mw.toFixed(1)+'px';
    mp.style.marginTop=((turn.getBoundingClientRect().y-row.y)/zoom).toFixed(1)+'px';
    mp.style.marginLeft=((side-mw)/2).toFixed(1)+'px'; }
  document.getElementById('rd').innerHTML=
    'canvas <b>'+CW+'&times;'+CH+'</b> &middot; zoom <b>'+zoom.toFixed(2)+'&times;</b> &middot; '+
    'action text <b>'+(BODY*zoom).toFixed(1)+'px</b> &middot; board figure <b>'
    +(NUM*k*zoom).toFixed(1)+'px</b> &middot; alms figure <b>'+(14*k*zoom).toFixed(1)+'px</b>'+
    ' &middot; action box <b>'+Math.round(H)+'</b> &middot; wheel <b>'+Math.round(side)+'</b>';
  if(wasMap) stage.classList.add('mapview');
}
document.getElementById('z1').onclick=e=>{one=!one;e.target.textContent=one?'fit window':'1:1';fit();};
// the swap itself: one class on the stage. Nothing is torn down and nothing reloads, so a
// half-made choice in the action box survives a look at the map and comes back untouched.
const vb=document.getElementById('vb'), vbl=document.getElementById('vbl');
function setView(toMap){ stage.classList.toggle('mapview', toMap);
  vbl.textContent = toMap ? 'Duty Wheel' : 'Map'; }
vb.onclick=()=>setView(!stage.classList.contains('mapview'));
addEventListener('keydown',e=>{ if(e.key==='m'||e.key==='M') setView(!stage.classList.contains('mapview')); });
addEventListener('resize',fit);
fit();
// the log opens at its foot, where the newest entry is -- after fit(), which is what
// gives the panel its height
const lb=document.getElementById('logBody');
const foot=()=>{ if(lb) lb.scrollTop=lb.scrollHeight; };
addEventListener('resize',foot); foot();
// Expand/collapse. The panel grows UPWARD -- bottom pinned -- so the invariant to hold across
// the resize is the distance from the foot of the list, not scrollTop. Hold that and whatever
// line you were reading stays on the same pixel while history opens above it; hold scrollTop
// instead and the newest entry slides out from under the eye.
const lgp=document.querySelector('.log'), lhd=document.getElementById('lhead');
function toggleLog(){
  const d = lb ? lb.scrollHeight - lb.scrollTop - lb.clientHeight : 0;
  lgp.classList.toggle('big');
  lhd.title = lgp.classList.contains('big') ? 'Collapse the log' : 'Expand the log';
  if(lb) lb.scrollTop = lb.scrollHeight - lb.clientHeight - d;
}
if(lhd) lhd.onclick=toggleLog;
addEventListener('keydown',e=>{ if(e.key==='l'||e.key==='L') toggleLog(); });
""" % {"canvas_w":CANVAS_W,"canvas_h":CANVAS_H,"body":BODY,"num":BOARD_NUM,"comp_w":COMP_W,
        "gap":GAP,"gap1":GAP1,"panel_w":PANEL_W,"ptop":(PY-COLLAR)+8-1,"map_aspect":MAP_ASPECT}

html=("<!doctype html><html><head><meta charset='utf-8'><title>Pilgrim &mdash; 3:2, step 1</title>"
 "<style>%s</style></head><body>"
 "<div class='stage'><div class='top'>%s%s%s</div>"
 "<div class='row'><div class='left'><div class='boards'>%s</div>%s</div>%s%s%s</div>"
 "<button class='viewbtn' id='vb'><svg width='19' height='19' viewBox='0 0 24 24' fill='none' stroke='#2A2320' stroke-width='1.5' stroke-linejoin='round' stroke-linecap='round'><path d='M9 4 L3 6.4 V20 L9 17.6 L15 20 L21 17.6 V4 L15 6.4 Z'/><path d='M9 4 V17.6'/><path d='M15 6.4 V20'/></svg><span class='vbw'><span class='ghost'>Duty Wheel</span><span id='vbl'>Map</span></span></button></div>"
 "<div class='hud'><span id='rd'></span><button id='z1'>1:1</button></div>"
 "<script>%s</script><script>%s</script></body></html>"
  % (CSS, sa_panel(), alms, MARKET, boards, LOG,
     TURN % (_icons("Chapel &mdash; +1 piety on Clerical &amp; Devotion. Costs 1 silver."),
             # the action's own name needs no glyph: the gain a few words later says it.
             # Last is one line of the log, so it obeys the log's rules -- seat as a disc
             # (yellow reads 1.42 and white 1.23 against parchment, so colour has to be a
             # shape with an outline, not ink on a word), no "took" before the tile, the tile
             # in bold, then the result clause.
             _icons(_seat_disc("blue") + "<b>Produce</b>, gained 3 wheat.")),
     wheel, _map_svg, SCRIPT,
     INSPECT_JS_TMPL.replace("TABLE", _json.dumps(
         {k: [v[0], _icons(v[1]), _icons(v[2])] for k, v in DUTY_TEXT.items()}))))
html = html.replace("<body>", "<body>" + _POP_DEFS, 1)
p=pathlib.Path(OUT+os.environ.get("OUTNAME","board-3-2-step1.html")); p.write_text(html)
print("written", p, p.stat().st_size//1024, "KB", "| component width", COMP_W)

# Only when run directly. `gen_picker.py` execs this file to lift one card out of it, and under
# that exec __name__ is "gen_board" -- without the guard, building the picker would print the
# board's URL and, with --open, open the wrong page.
if __name__ == "__main__":
    URL = p.resolve().as_uri()
    print("\n%s" % URL)
    if "--open" in sys.argv or os.environ.get("OPEN_BOARD"):
        import webbrowser
        webbrowser.open(URL)
