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


# A MEASURING RING, drawn around a plate purely so it can be measured and then thrown away.
#
# ground_ellipse reads a plate's own outline, which is exact on a clean ellipse and meaningless
# on a ragged one -- the docstring above says so. A ring solves that by not asking the art to be
# measurable at all: the generator draws a clean ellipse well clear of the tile, the ring is
# measured, and then it is deleted by COLOUR. Colour, not shape: every attempt to recover the
# tile's geometry by eroding or fitting its silhouette failed, because a silhouette is exactly
# the thing a ragged plate does not have.
#
# Spring green because it is the furthest any common key sits from this game's palette. Measured
# across all 81 committed PNGs in ui/assets-gothic/, the closest pixel to it is 182 away in
# stones_sage.png, where magenta comes within 34 of stones_plum.png -- plum being a purple. A key
# that lives inside the palette is a trap for the first person who points this at the wrong file.
RING_KEY = (0, 255, 128)
RING_TOLERANCE = 150        # sum of per-channel differences; the palette's closest is 182


def _ring_mask(im):
    a = np.array(im.convert("RGBA")).astype(int)
    d = np.abs(a[..., :3] - np.array(RING_KEY)).sum(2)
    return (d < RING_TOLERANCE) & (a[..., 3] > ALPHA), a


def has_measuring_ring(im, least=0.0005):
    """Whether this image carries a ring at all. Everything else depends on this being cheap
    and certain: a plate with no ring must take exactly the path it took before rings existed."""
    m, _ = _ring_mask(im)
    return bool(m.mean() >= least)


def _fit_ellipse(mask):
    """Least-squares conic through a ring's pixels, returning (major, minor) in pixels.

    No new dependency: this is the ordinary algebraic conic fit solved by SVD on the design
    matrix. cv2.fitEllipse does the same job and OpenCV is not in pyproject.toml. Points are
    centred and scaled first, because the fit is badly conditioned in raw pixel coordinates --
    x*x on a 1600 px canvas is 2.5e6 and the constant column is 1.
    """
    ys, xs = np.nonzero(mask)
    if len(xs) < 50:
        return None
    x = xs.astype(np.float64)
    y = ys.astype(np.float64)
    mx, my = x.mean(), y.mean()
    sc = max(x.std(), y.std())
    if sc <= 0:
        return None
    x = (x - mx) / sc
    y = (y - my) / sc
    d = np.column_stack([x * x, x * y, y * y, x, y, np.ones_like(x)])
    try:
        _, _, v = np.linalg.svd(d, full_matrices=False)
    except np.linalg.LinAlgError:
        return None
    a, b, c, dd, e, f = v[-1]
    m = np.array([[a, b / 2.0], [b / 2.0, c]])
    try:
        cen = np.linalg.solve(2 * m, [-dd, -e])
    except np.linalg.LinAlgError:
        return None
    val = (a * cen[0] ** 2 + b * cen[0] * cen[1] + c * cen[1] ** 2
           + dd * cen[0] + e * cen[1] + f)
    ev = np.linalg.eigvalsh(m)
    if np.any(ev == 0):
        return None
    q = -val / ev
    if np.any(q <= 0) or not np.all(np.isfinite(q)):
        return None                      # the conic is a hyperbola or degenerate, not an ellipse
    ax = np.sqrt(q) * sc
    return float(max(ax)) * 2.0, float(min(ax)) * 2.0


def ring_ellipse(im):
    """The camera, read off the ring rather than off the tile.

    THE RING IS FITTED, NOT BOUNDED, and the difference is bigger than the tolerance a plate
    is held to. The first version filled the ring and handed the result to ground_ellipse,
    which takes the widest ROW and the bounding height. Filling an annulus recovers its OUTER
    edge -- and an outer edge is a fatter ellipse than the centreline it was drawn around,
    because adding half-stroke t to both semi-axes gives (b+t)/(a+t), which is larger than b/a
    whenever b < a. So every reading was biased toward a STEEPER camera, by an amount that
    grows with the stroke.

    Measured against rings whose centreline is known exactly -- the band between the (a-t, b-t)
    and (a+t, b+t) ellipses -- the old method erred by +0.27 to +0.48 degrees at t=9, and by
    +0.70 at t=18, which is what a "2% of the tile's width" brief can produce. This fit errs by
    0.01. On the real generated rings the shift is smaller, -0.02 to -0.44, because a soft edge
    pulls the keyed mask inward and partly cancels the bias; on the plank plate it was -0.43,
    and the fitted number agreed with an independent measurement to 0.01.

    WHY THE TEST SUITE NEVER CAUGHT IT: the fixture drew its ring with PIL's ellipse outline,
    which strokes INWARD from the bounding box, so filling it recovered the box exactly and the
    round trip was perfect. The fixture was not representative of the thing being measured. It
    now draws the band between two ellipses, so the centreline is known and the bias is visible.

    THE FILL IS STILL USED, for what it is actually good at: deciding whether the loop is
    closed. Returns None when it is not, which in practice means the tile is sitting on top of
    the ring. The ring's height is 2 x radius x sin(theta), so at a shallow camera a ring that
    looks generous side to side is still shorter than the tile it encircles: at 1.04 times the
    tile's height a 32 degree ring read 6.0, and at 1.20 it read 31.9. The brief asks for a
    clear gap all the way round for this reason, and a broken ring must refuse rather than
    report the number occlusion produces.
    """
    try:
        from scipy import ndimage
    except ModuleNotFoundError:
        return None
    m, _ = _ring_mask(im)
    if not m.any():
        return None
    filled = ndimage.binary_fill_holes(m)
    if filled.sum() <= m.sum() * 1.5:
        return None                      # nothing was enclosed: the ring is not a closed loop
    got = _fit_ellipse(m)
    if got is None:
        return None
    major, minor = got
    if major <= 0 or minor <= 0 or minor > major:
        return None
    s = minor / major
    if not 0.0 < s <= 1.0:
        return None
    return {"width": major, "height": minor, "sin_theta": s,
            "degrees": round(math.degrees(math.asin(s)), 2)}


RING_FEATHER = 4            # px of dilation; the generator's ring edge measured 2-3 px wide
RING_SOLID = 200            # inside that band, only a near-opaque pixel is tile rather than ring


def without_ring(im):
    """The tile with the ring deleted -- INCLUDING the ring's own antialiased edge.

    The colour key alone is not enough, and the failure is quiet. A pixel halfway along the
    ring's soft edge is a BLEND of spring green and transparent background: its alpha is low
    but nonzero, and its RGB has been pulled far enough off the key to sit outside
    RING_TOLERANCE. So it survives the strip, and what is left is a faint ghost of the ring
    exactly where the ring was.

    Measured on the cobbles candidate of 2026-09-23: the ring's own ellipse is 1382 px wide,
    and after the old strip the image's alpha>8 box was 1382 x 730 while the SOLID plate was
    1159 x 616. The ghost was not near the ring, it WAS the ring, and it padded the bounding
    box by 16%.

    It never moved a measured angle -- ground_ellipse fits the shape rather than taking a box,
    and the ghost is 0.8% of the ink, too sparse and too thin to shift the fit. Re-measuring
    fifteen candidates across three batches with this fix returned every angle identical to a
    tenth of a degree. What it did corrupt was anything that CROPS: a preview trimmed at
    alpha>8 came out 16% too wide and made the plate look small beside its neighbours.

    So: dilate the keyed mask, and inside that band only, drop whatever is not near-opaque.
    Solid tile is untouched because the brief keeps the ring clear of the tile -- and a ring
    that does touch the tile is refused by ring_ellipse before it ever gets here.
    """
    m, a = _ring_mask(im)
    b = a.copy()
    b[m, 3] = 0
    try:
        from scipy import ndimage
    except ModuleNotFoundError:
        return Image.fromarray(b.astype(np.uint8), "RGBA")
    k = 2 * RING_FEATHER + 1
    band = ndimage.binary_dilation(m, np.ones((k, k), bool))
    b[band & (b[..., 3] < RING_SOLID), 3] = 0
    return Image.fromarray(b.astype(np.uint8), "RGBA")


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
