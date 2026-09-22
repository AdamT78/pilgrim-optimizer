"""What a sculpt's base measures, and how to shrink one without wrecking its edges.

Shared by make_tray_figures.py, which builds the pieces, and check_sculpt.py, which judges a new
generation before it is filed. It was written the third time these functions were copied.

HOW THE PLINTH IS MEASURED, AND WHY NOT THE OBVIOUS WAYS

Width is the WIDEST ROW of the base, not the bottom edge: the plinth is an ellipse seen from
above, so its last row is a chord across the near side and narrower than the disc really is.

Height -- the visible side wall -- resisted three approaches before this one:

  * Silhouette width fails. The robe flares out to nearly the base's own width on these figures,
    so there is no narrowing to find where one ends and the other begins.
  * The silhouette's vertical run fails. It travels straight up through the whole figure, and
    restricting it to the base's robe-free left and right edges does not help either: the run
    GROWS inward, because the disc's top surface is visible and adds to the span.
  * Shading works. The wall is lit flat and even, and there is a sharp specular spike where the
    rounded top rim catches the light. That spike is the top of the wall.

Angle is NOT the rise. `rise` is the drop from the widest row to the bottom of the art, and this
docstring used to call it the semi-minor axis of the base's bottom ellipse. It is not: the plinth
is a cylinder, so its silhouette is equally wide down the whole side wall and `argmax` returns the
TOP of that wall. The rise therefore spans the wall AND the front half of the bottom ellipse.
Measured on player_1's full-size art: widest row at 1262, the silhouette's bottom at the edges at
1292.5, at its centre at 1327 -- so 30.5 of wall and 34.5 of ellipse, and taking the whole 65 as
the semi-minor axis reports a 26 degree camera for a 7 degree one.

`ground_ellipse` measures it properly, off the BOTTOM outline, which is the one curve nothing ever
stands in front of.

Every ratio is against the base's OWN width, so a figure drawn larger or smaller compares
directly with the rest of the set.
"""
import math

import numpy as np
from PIL import Image

ALPHA = 16          # anything fainter is background, not art
PLINTH_BAND = 0.14  # bottom slice of a figure that is base rather than robe

# WHERE THE RIM CAN BE, as a fraction of the plinth's OWN width rather than in pixels.
#
# It was (35, 150) absolute, and that was wrong twice over. Art arrives at whatever size the
# generator felt like, so a fixed window means a different question on every image; and the
# committed set runs 0.11 to 0.16 of the plinth's width, so 150 px sat barely above the band on
# a 600 px plinth and BELOW it on a larger one. Anything genuinely chunky was clipped by the
# window rather than measured.
RIM_SEARCH_RATIO = (0.04, 0.40)
RIM_SEARCH_FLOOR = 8        # px, so a thumbnail still has somewhere to look
RIM_PROMINENCE = 0.5        # how far up from the dark wall a peak must stand to be the rim


def bbox(im):
    m = np.array(im)[..., 3] > ALPHA
    ys, xs = np.nonzero(m)
    assert len(xs), "image is entirely transparent"
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def crop_to_art(im):
    return im.crop(bbox(im))


def _base_row(c):
    """The widest row of the base, and that row's extent. Searched only in the bottom band --
    on a figure with outspread arms the widest row of the WHOLE silhouette is the hands."""
    m = np.array(c)[..., 3] > ALPHA
    h = m.shape[0]
    band = h - int(h * PLINTH_BAND)
    w = m[band:].sum(1)
    y = band + int(np.argmax(w))
    row = np.nonzero(m[y])[0]
    return y, int(w.max()), int(row.min()), int(row.max())


def plinth_width(c):
    """Just the width, for callers that do not need the rest."""
    return _base_row(c)[1]


def ground_ellipse(im, base_band=True, inset=0.03, span=0.02):
    """The ellipse the base draws on the ground, and so where the camera is.

    A circle on the ground seen from `theta` above the horizon draws an ellipse whose height is
    sin(theta) times its width. The top of that ellipse is hidden by whatever stands on the base,
    but the BOTTOM outline never is: at the horizontal extremes it sits at the foot of the wall,
    and at the centre it sits one semi-minor axis lower. The difference is the semi-minor axis,
    and nothing about the figure above enters the measurement.

    `base_band` restricts the search for the widest row to the bottom of the art, which is right
    for a figure whose robe is wider than its plinth and wrong for a bare ground plate, which is
    all base. The caller knows which it has.

    HOW FAR TO TRUST IT. On a turned plinth the bottom outline IS an ellipse arc and the answer is
    exact: the four sculpts agree to within a degree, which is what one camera should look like.
    On a ground plate whose edge is ragged cobble or stepped stone the outline is not an ellipse,
    the measurement under-reads, and it should be treated as a sanity check with the overlay
    looked at rather than as a number to accept. The honest reading of a plate is the aspect of a
    square paving stone on its surface, and that still wants an eye.

    `inset` keeps the edge samples off the extreme column, where a single stray pixel would move
    the answer; `span` averages a few columns at the centre for the same reason.
    """
    c = crop_to_art(im)
    m = np.array(c)[..., 3] > ALPHA
    h, w = m.shape
    if base_band:
        widest, width, lo, hi = _base_row(c)
    else:
        # A BARE PLATE IS ALL BASE. Restricting the search to the bottom band, which is right for
        # a figure standing on a plinth, cuts a ground plate off below its widest row and returns
        # a chord: measured that way the cobbles read 11 degrees against 25 for the whole outline.
        rows = m.sum(1)
        widest = int(np.argmax(rows))
        width = int(rows[widest])
        cols = np.nonzero(m[widest])[0]
        lo, hi = int(cols.min()), int(cols.max())

    def bottom(x):
        col = np.nonzero(m[:, x])[0]
        return int(col.max()) if len(col) else None

    pad = max(1, int(inset * width))
    edges = [v for v in (bottom(lo + pad), bottom(hi - pad)) if v is not None]
    mid = (lo + hi) // 2
    reach = max(1, int(span * width))
    centres = [v for v in (bottom(x) for x in range(mid - reach, mid + reach + 1))
               if v is not None]
    if not edges or not centres or width <= 0:
        return None
    edge = float(np.mean(edges))
    centre = float(np.mean(centres))
    a = (hi - lo) / 2.0
    t = max(0.0, min(1.0, (a - pad) / a)) if a > 0 else 0.0
    shortfall = 1.0 - math.sqrt(max(0.0, 1.0 - t * t))
    if shortfall <= 1e-6 or centre <= edge:
        return None
    minor = 2.0 * (centre - edge) / shortfall
    sin_theta = min(1.0, max(0.0, minor / width))
    return {
        "width": width, "minor": minor, "sin_theta": sin_theta,
        "degrees": math.degrees(math.asin(sin_theta)),
        # where the measurement landed, so a caller can draw it and see for itself
        "widest_row": widest, "bottom_edge": edge, "bottom_centre": centre,
        "left": lo, "right": hi, "art_w": w, "art_h": h,
    }


def _rim(strip, h, width):
    """How far above the bottom edge the rim highlight sits, or None when there isn't one.

    A RIM IS A PEAK, NOT THE EDGE OF A SEARCH WINDOW. This used to be a plain argmax over a
    band fixed in PIXELS, which cannot fail and therefore cannot be trusted: when the brightest
    thing in view was a lit robe hem above the window, argmax returned the last row searched and
    the caller got that boundary back as a measurement. It read as a plinth about twice as thick
    as the one in the picture -- plausible enough to be believed, and 21 of 128 monk
    measurements in one evening were exactly this, every one of them reported as a base that had
    failed its check.

    AND THE RIM IS NOT THE BRIGHTEST THING, which is the trap in the obvious repair. Widen the
    window and the robe wins: on the three sculpts on file the rim sits at 145, 149 and 175
    while folds above it reach 172, 146 and 200. The old narrow band was hiding that by keeping
    the robe out of view, so widening it alone turned a 0.14 base into a 0.37 one.

    What actually identifies the rim is that it is the FIRST strong thing above the bottom edge.
    Below it is the plinth's own dark wall, a flat low run; the rim is a sharp bright line on
    top of it. So: take the lowest local maximum that stands at least RIM_PROMINENCE of the way
    from that dark floor up to the brightest peak in view. Ties and noise inside the wall sit
    far below the threshold and are skipped.

    Returns None when nothing qualifies, or when the winner is hard against either end of the
    window -- there is no peak in view and the answer must say so. None is the point: a wall
    that could not be found must not be indistinguishable from a wall that was measured.
    """
    lo = max(RIM_SEARCH_FLOOR, int(RIM_SEARCH_RATIO[0] * width))
    hi = min(h - 1, int(RIM_SEARCH_RATIO[1] * width))
    if hi - lo < 5:
        return None
    ks = np.arange(lo, hi + 1)
    vals = np.array([strip[h - 1 - k] for k in ks], dtype=np.float64)
    inner = np.arange(1, len(ks) - 1)
    peaks = inner[(vals[1:-1] >= vals[:-2]) & (vals[1:-1] >= vals[2:])]
    if not len(peaks):
        return None
    floor = float(np.percentile(vals, 10))
    ceiling = float(vals[peaks].max())
    if ceiling - floor < 1e-6:
        return None
    strong = [i for i in peaks if vals[i] >= floor + RIM_PROMINENCE * (ceiling - floor)]
    if not strong:
        return None
    first = int(strong[0])
    if first <= 0 or first >= len(ks) - 1:
        return None
    return int(ks[first])


def measure(im):
    """Every number this project asks of a sculpt, from an image already cropped to its art."""
    c = crop_to_art(im) if im.size != (bbox(im)[2] - bbox(im)[0], bbox(im)[3] - bbox(im)[1]) else im
    a = np.array(c).astype(np.float64)
    h, w = a.shape[:2]
    y, width, xl, xr = _base_row(c)
    lum = 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
    # A strip rather than one column: flutes and noise average out, the rim highlight does not.
    cx = (xl + xr) // 2
    strip = lum[:, max(0, cx - 12):cx + 13].mean(1)
    wall = _rim(strip, h, width)
    ymid = h - 1 - max(2, (wall if wall is not None else int(0.12 * width)) // 2)
    seg = lum[ymid, xl + int(0.18 * (xr - xl)):xr - int(0.18 * (xr - xl))]
    al = np.array(c)[..., 3]
    return {
        "art_w": w, "art_h": h, "plinth": width, "wall": wall, "rise": h - 1 - y,
        # None rather than a number when no rim was found -- see _rim
        "wall_ratio": (wall / width) if wall is not None else None,
        "rise_ratio": (h - 1 - y) / width, "h_plinth": h / width,
        # fluting shows as a high ripple, a smooth disc as a low one
        "ripple": float(np.abs(np.diff(seg)).mean()) if len(seg) > 1 else 0.0,
        "clear_pct": 100.0 * float((al == 0).mean()),
        "corner_alpha": [int(al[2, 2]), int(al[2, -3]), int(al[-3, 2]), int(al[-3, -3])],
    }


def resize(im, w, h):
    """Premultiply, resample, un-premultiply -- with the colour and the alpha resampled as two
    SEPARATE images.

    Handing PIL one RGBA image makes it weight the colour channels by alpha itself, so data that
    is already premultiplied gets premultiplied a second time; the un-premultiply then divides by
    an alpha the colour no longer matches, and the quotient runs away exactly where alpha is
    small. On a synthetic half-covered edge that turns a true colour of 110 into 1575, which
    clips to white -- a pale rim around everything. Two separate resizes give 105.
    """
    w, h = max(1, int(w)), max(1, int(h))
    a = np.array(im).astype(np.float64)
    pm = a[..., :3] * (a[..., 3:4] / 255.0)
    c = np.array(Image.fromarray(np.clip(pm, 0, 255).round().astype(np.uint8), "RGB")
                 .resize((w, h), Image.LANCZOS)).astype(np.float64)
    aa = np.array(Image.fromarray(a[..., 3].round().astype(np.uint8), "L")
                  .resize((w, h), Image.LANCZOS)).astype(np.float64)[..., None]
    sa = aa / 255.0
    rgb = np.divide(c, sa, out=np.zeros_like(c), where=sa > 0.004)
    return Image.fromarray(np.clip(np.concatenate([rgb, aa], 2), 0, 255).astype(np.uint8), "RGBA")


def down(im, w, h, what):
    """Refuse to invent pixels. Reaching a size by upscaling would put the resampler's guess on
    screen under a label claiming a true size, which is the one thing these pages must not do."""
    assert h <= im.height + 0.5, (
        "%s: %d px is taller than its %d px source -- that would be an UPSCALE. Use a bigger "
        "original or drop the size." % (what, h, im.height))
    return resize(im, w, h)


def fringe(im):
    """How much lighter the part-transparent rim is than the solid body, in luminance. The art
    itself runs NEGATIVE -- an edge is shaded, so it is darker than what it surrounds -- so a
    positive number means the pipeline put light pixels there that the original never had."""
    a = np.array(im).astype(np.float64)
    al = a[..., 3]
    lum = 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
    core, rim = al > 240, (al > 8) & (al < 240)
    if not core.any() or not rim.any():
        return 0.0
    return float(lum[rim].mean() - lum[core].mean())
