# Original vector placeholder portraits for Pilgrim player boards.
# Drawn from scratch as parametric geometry -- NOT traced from, and containing no
# fragment of, the licensed PNG set. Safe to commit.
INK = "#2B2620"

def _hatch(d, op=0.13):
    return '<path d="%s" fill="none" stroke="%s" stroke-width="1.5" ' \
           'stroke-linecap="round" opacity="%s"/>' % (d, INK, op)

def _eye(cx, cy, w=6.0, h=3.4, droop=0.0, lid=1.0):
    """Almond eye with an upper lid line; droop lowers the outer corner."""
    o = ('<path d="M%.1f %.1f Q%.1f %.1f %.1f %.1f Q%.1f %.1f %.1f %.1f Z" '
         'fill="#FBF6EC" stroke="%s" stroke-width="1.1" stroke-linejoin="round"/>'
         % (cx - w, cy, cx, cy - h, cx + w, cy + droop,
            cx, cy + h * 0.72, cx - w, cy, INK))
    o += '<circle cx="%.1f" cy="%.1f" r="1.9" fill="%s"/>' % (cx, cy + 0.3, INK)
    if lid:
        o += ('<path d="M%.1f %.1f Q%.1f %.1f %.1f %.1f" fill="none" stroke="%s" '
              'stroke-width="1.5" stroke-linecap="round" opacity=".8"/>'
              % (cx - w - 1, cy - 1.4, cx, cy - h - 2.2, cx + w + 1, cy - 1.4 + droop, INK))
    return o

def _brow(cx, cy, w, lift, weight=2.6, col=None):
    return ('<path d="M%.1f %.1f Q%.1f %.1f %.1f %.1f" fill="none" stroke="%s" '
            'stroke-width="%s" stroke-linecap="round"/>'
            % (cx - w, cy, cx, cy - lift, cx + w, cy + 0.6, col or INK, weight))

def _nose(x, top, bot, flare=3.4):
    return ('<path d="M%.1f %.1f Q%.1f %.1f %.1f %.1f q%.1f 2.4 %.1f 0" fill="none" '
            'stroke="%s" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" '
            'opacity=".9"/>'
            % (x - 1.2, top, x - 2.6, bot - 3, x + 0.6, bot, -flare * 0.2, flare, INK))

def _mouth(x, y, w, curve=1.6, weight=1.9):
    return ('<path d="M%.1f %.1f Q%.1f %.1f %.1f %.1f" fill="none" stroke="%s" '
            'stroke-width="%s" stroke-linecap="round" opacity=".85"/>'
            % (x - w, y, x, y + curve, x + w, y, INK, weight))

def _cowl(cloth, dark, neck, spread=0.0):
    """Shoulders and hood collar behind the head."""
    s = spread
    return ('<path d="M60 %.1f c-7 0 -11 3 -13 6 L%.1f 120 H%.1f L%.1f %.1f '
            'c-2 -3 -6 -6 -13 -6 Z" fill="%s"/>'
            % (neck, 4 - s, 116 + s, 73, neck, dark)
            + '<path d="M%.1f 120 C%.1f 104 %.1f 96 60 96 c%.1f 0 %.1f 8 %.1f 24 Z" '
              'fill="%s"/>' % (10 - s, 12 - s, 34, 26, 22, 50 + s, cloth))

def _skull(halfw, top, chin, cheek=0.0):
    """Face outline: rounded cranium tapering to a chin."""
    return ('M60 %.1f C%.1f %.1f %.1f %.1f %.1f %.1f '
            'C%.1f %.1f %.1f %.1f 60 %.1f '
            'C%.1f %.1f %.1f %.1f %.1f %.1f '
            'C%.1f %.1f %.1f %.1f 60 %.1f Z'
            % (top,
               60 + halfw * 0.86, top, 60 + halfw, top + 13, 60 + halfw, top + 26,
               60 + halfw, chin - 22 + cheek, 60 + halfw * 0.52, chin, chin,
               60 - halfw * 0.52, chin, 60 - halfw, chin - 22 + cheek,
               60 - halfw, top + 26,
               60 - halfw, top + 13, 60 - halfw * 0.86, top, top))


# --------------------------------------------------------------------------
# Four characters. Each returns a group in a 120x120 box, head centred at x=60.
# --------------------------------------------------------------------------

def elder(sk="#D8B893", sh="#B08F68", hair="#8E8378",
          hair2="#6F665C", cloth="#7C6B54", cd="#5E5240"):
    """Full beard, long hair. The patriarch."""
    o = _cowl(cloth, cd, 92)
    o += '<path d="M52 78 h16 v18 h-16 Z" fill="%s"/>' % sh          # neck
    o += '<path d="%s" fill="%s"/>' % (_skull(25, 20, 88), sk)
    o += '<ellipse cx="35.5" cy="54" rx="4" ry="6.5" fill="%s"/>' % sk
    o += '<ellipse cx="84.5" cy="54" rx="4" ry="6.5" fill="%s"/>' % sk
    # beard: jaw to jaw, hanging past the chin
    o += ('<path d="M37 52 c-1 16 2 30 9 39 c5 7 10 11 14 11 c4 0 9 -4 14 -11 '
          'c7 -9 10 -23 9 -39 c-3 12 -8 17 -23 17 c-15 0 -20 -5 -23 -17 Z" fill="%s"/>' % hair)
    o += ('<path d="M46 84 c4 6 9 10 14 10 c5 0 10 -4 14 -10 c-4 3 -9 4 -14 4 '
          'c-5 0 -10 -1 -14 -4 Z" fill="%s" opacity=".55"/>' % hair2)
    # moustache
    o += ('<path d="M48 68 c4 -3 8 -4 12 -4 c4 0 8 1 12 4 c-4 4 -8 5 -12 5 '
          'c-4 0 -8 -1 -12 -5 Z" fill="%s"/>' % hair)
    # hair mass over the cranium and down past the ears
    o += ('<path d="M60 12 c-16 0 -26 11 -26 26 c0 6 1 11 2 15 c1 -9 2 -15 4 -19 '
          'c6 4 14 6 20 6 c6 0 14 -2 20 -6 c2 4 3 10 4 19 c1 -4 2 -9 2 -15 '
          'c0 -15 -10 -26 -26 -26 Z" fill="%s"/>' % hair)
    o += _brow(50, 47, 7.5, 3.4, 3.0, hair2) + _brow(70, 47, 7.5, 3.4, 3.0, hair2)
    o += _eye(50, 55) + _eye(70, 55)
    o += _nose(60, 52, 68, 3.6)
    o += _hatch("M78 44 q4 8 3 18") + _hatch("M42 44 q-4 8 -3 18")
    return o


def tonsured(sk="#E0C2A0", sh="#BC9C7C", hair="#B9B2A6", hair2="#918A7E",
             cloth="#6E6A5E", cd="#514E45"):
    """Shaved crown, clean-shaven, hollow cheeks. The old bursar."""
    o = _cowl(cloth, cd, 92, spread=2)
    o += '<path d="M52 78 h16 v18 h-16 Z" fill="%s"/>' % sh
    o += '<path d="%s" fill="%s"/>' % (_skull(23.5, 17, 90, cheek=-3), sk)
    o += '<ellipse cx="37" cy="55" rx="4" ry="7" fill="%s"/>' % sk
    o += '<ellipse cx="83" cy="55" rx="4" ry="7" fill="%s"/>' % sk
    # ring of hair only
    o += ('<path d="M36.5 42 c-1 11 0 20 2 27 c-4 -3 -6 -12 -6 -22 '
          'c0 -3 1 -5 4 -5 Z" fill="%s"/>' % hair)
    o += ('<path d="M83.5 42 c1 11 0 20 -2 27 c4 -3 6 -12 6 -22 '
          'c0 -3 -1 -5 -4 -5 Z" fill="%s"/>' % hair)
    o += ('<path d="M36 46 c0 -8 3 -14 8 -17 c-3 5 -4 11 -4 17 Z" fill="%s"/>' % hair2)
    o += ('<path d="M84 46 c0 -8 -3 -14 -8 -17 c3 5 4 11 4 17 Z" fill="%s"/>' % hair2)
    o += _brow(50, 46, 7, 1.6, 2.4, hair2) + _brow(70, 46, 7, 1.6, 2.4, hair2)
    o += _eye(50, 54, 5.6, 3.0, droop=1.2) + _eye(70, 54, 5.6, 3.0, droop=-1.2)
    o += _nose(60, 51, 70, 3.2)
    o += _mouth(60, 79, 8, 1.2)
    # hollow cheeks and crow's feet
    o += _hatch("M45 62 q2 8 4 12", .16) + _hatch("M75 62 q-2 8 -4 12", .16)
    o += _hatch("M41 51 q-2 2 -3 5", .22) + _hatch("M79 51 q2 2 3 5", .22)
    o += _hatch("M52 84 q8 4 16 0", .14)
    return o


def lank(sk="#D3B491", sh="#AE8F6F", hair="#7E7468",
         hair2="#5F584E", cloth="#5F6B62", cd="#464F48"):
    """Long face, lank shoulder-length hair, clean-shaven. The clerk."""
    o = _cowl(cloth, cd, 92)
    o += '<path d="M53 78 h14 v18 h-14 Z" fill="%s"/>' % sh
    o += '<path d="%s" fill="%s"/>' % (_skull(22.5, 18, 92, cheek=-2), sk)
    o += '<ellipse cx="36.5" cy="55" rx="3.6" ry="6.5" fill="%s"/>' % sk
    o += '<ellipse cx="83.5" cy="55" rx="3.6" ry="6.5" fill="%s"/>' % sk
    # curtain of hair down both sides
    o += ('<path d="M60 11 c-15 0 -24 10 -25 24 c-1 12 -2 24 -5 34 c6 -2 9 -8 10 -16 '
          'c1 -8 1 -16 2 -21 c6 5 12 7 18 7 c6 0 12 -2 18 -7 c1 5 1 13 2 21 '
          'c1 8 4 14 10 16 c-3 -10 -4 -22 -5 -34 c-1 -14 -10 -24 -25 -24 Z" fill="%s"/>' % hair)
    o += ('<path d="M40 36 c5 5 12 7 20 7 c8 0 15 -2 20 -7 c-6 3 -12 4 -20 4 '
          'c-8 0 -14 -1 -20 -4 Z" fill="%s" opacity=".5"/>' % hair2)
    o += _brow(50, 47, 6.8, 2.0, 2.4, hair2) + _brow(70, 47, 6.8, 2.6, 2.4, hair2)
    o += _eye(50, 55, 5.8, 3.2) + _eye(70, 55, 5.8, 3.2)
    o += _nose(60, 52, 72, 3.4)
    o += _mouth(60, 81, 7, -0.8)
    o += _hatch("M47 63 q2 9 3 13", .15) + _hatch("M73 63 q-2 9 -3 13", .15)
    return o


def ascetic(sk="#C9A882", sh="#A5865F", hair2="#6B6156",
            cloth="#6B5B4A", cd="#4F4237"):
    """Bald, clean-shaven, heavy jaw. The lay brother."""
    o = _cowl(cloth, cd, 90, spread=4)
    o += '<path d="M51 76 h18 v20 h-18 Z" fill="%s"/>' % sh
    o += '<path d="%s" fill="%s"/>' % (_skull(25.5, 16, 88, cheek=2), sk)
    o += '<ellipse cx="35" cy="54" rx="4.2" ry="7" fill="%s"/>' % sk
    o += '<ellipse cx="85" cy="54" rx="4.2" ry="7" fill="%s"/>' % sk
    o += _brow(50, 46, 7.8, 2.2, 3.0, hair2) + _brow(70, 46, 7.8, 2.2, 3.0, hair2)
    o += _eye(50, 54, 6.0, 3.2) + _eye(70, 54, 6.0, 3.2)
    o += _nose(60, 51, 68, 4.0)
    o += _mouth(60, 78, 9, 1.0, 2.2)
    # shaved-scalp sheen and stubble shadow on the jaw
    o += ('<path d="M45 24 c4 -5 10 -8 15 -8 c-9 1 -15 5 -19 11 Z" '
          'fill="#FFFFFF" opacity=".22"/>')
    o += ('<path d="M38 62 c2 14 10 26 22 26 c12 0 20 -12 22 -26 '
          'c-4 14 -11 20 -22 20 c-11 0 -18 -6 -22 -20 Z" fill="%s" opacity=".16"/>' % hair2)
    o += _hatch("M44 60 q2 9 4 13", .16) + _hatch("M76 60 q-2 9 -4 13", .16)
    return o


FACES = {"elder": elder, "tonsured": tonsured, "lank": lank, "ascetic": ascetic}
ORDER = ["elder", "tonsured", "lank", "ascetic"]

_uid = [0]

def portrait_svg(cx, cy, r, kind, ring=None, ring_w=1.6, ground="#B9AE97"):
    """The face, clipped to a circle of radius r centred on (cx, cy)."""
    _uid[0] += 1
    cid = "fc%d" % _uid[0]
    k = r / 60.0
    o = ('<defs><clipPath id="%s"><circle cx="%s" cy="%s" r="%s"/></clipPath></defs>'
         % (cid, cx, cy, r))
    o += ('<g clip-path="url(#%s)"><rect x="%s" y="%s" width="%s" height="%s" fill="%s"/>'
          '<g transform="translate(%s %s) scale(%s)">%s</g></g>'
          % (cid, cx - r, cy - r, 2 * r, 2 * r, ground, cx - r, cy - r, k, FACES[kind]()))
    if ring:
        o += ('<circle cx="%s" cy="%s" r="%s" fill="none" stroke="%s" stroke-width="%s"/>'
              % (cx, cy, r, ring, ring_w))
    return o


def standalone(kind, size=120):
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%s" height="%s" '
            'viewBox="0 0 120 120">%s</svg>' % (size, size, FACES[kind]()))
