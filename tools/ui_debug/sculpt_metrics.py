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

Angle is the rise from the bottom of the art to the widest row, which is the semi-minor axis of
the base's bottom ellipse. Divided by the width it says how far above the piece the camera sits:
a bigger number means more of the top surface is showing.

Every ratio is against the base's OWN width, so a figure drawn larger or smaller compares
directly with the rest of the set.
"""
import numpy as np
from PIL import Image

ALPHA = 16          # anything fainter is background, not art
PLINTH_BAND = 0.14  # bottom slice of a figure that is base rather than robe
RIM_SEARCH = (35, 150)


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
    ks = np.arange(*RIM_SEARCH)
    ks = ks[ks < h]
    wall = int(ks[int(np.argmax([strip[h - 1 - k] for k in ks]))])
    ymid = h - 1 - max(2, wall // 2)
    seg = lum[ymid, xl + int(0.18 * (xr - xl)):xr - int(0.18 * (xr - xl))]
    al = np.array(c)[..., 3]
    return {
        "art_w": w, "art_h": h, "plinth": width, "wall": wall, "rise": h - 1 - y,
        "wall_ratio": wall / width, "rise_ratio": (h - 1 - y) / width, "h_plinth": h / width,
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
