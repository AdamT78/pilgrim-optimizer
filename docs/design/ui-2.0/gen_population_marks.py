"""The serf and acolyte marks across the player card's band.

Three marks per population, left to right: a **figure**, its **square**, its **count**. The two
groups are split by a divider, and both are pinned to the resource pills below them so the band and
the pill row read on the same columns:

    serf figure   over the piety pill          acolyte figure  over the stone pill
    serf square   between piety and wheat      acolyte square  between stone and silver

Everything else falls out of the band. The row sits on the band's own centre -- `TOP + BAND_H/2`,
not the upper half it used to occupy -- and the figures share that centre line rather than standing
on a baseline: at two and a half times the square, a baseline alignment leaves the figure towering
beside it, while a shared centre makes each group read as one row.

The figure's height is what the band allows, not a number picked by eye. Centred on 36 in a band
running 16..56, a 30-unit figure clears the card's frame top by 5 and the band's foot by 5.

PNGs are placed through a `<symbol>` whose viewBox is the file's own canvas -- the production cuts
are alpha-tight, so canvas and ink are the same box. See `../hybrid-svg-png.md`; the short version
is that a `<use>` cannot size a bare `<image>`, only a `<symbol>`, and a padded PNG would report a
box it does not fill.
"""
import base64
import pathlib

FIG_H = 30.0        # figure ink height, in card units
NUM_GAP = 3.5       # square to its count
DIV_HALF = 15.0     # the divider's half-height
_NUM_W = 8.0        # a single numeral, for finding the gap the divider splits

ASSETS = pathlib.Path(__file__).parent / "assets" / "icons" / "population"
DEFAULT = {"serf": "serf/serf_wide_hat.png",
           "acolyte": "acolyte/acolyte_hood_cross.png"}


def _png(rel):
    """Bytes and pixel size, without importing Pillow: the IHDR of a PNG is at a fixed offset."""
    raw = (ASSETS / rel).read_bytes()
    w = int.from_bytes(raw[16:20], "big")
    h = int.from_bytes(raw[20:24], "big")
    return raw, w, h


def defs(choice=None):
    """The symbol defs, and the aspect of each figure. Put the markup in the PAGE, not in a card:
    `fit()` aligns the player column from `.boards svg[0]`, so a zero-size defs element inside
    `.boards` becomes the thing it measures."""
    choice = {**DEFAULT, **(choice or {})}
    out, asp = [], {}
    for kind, rel in choice.items():
        raw, w, h = _png(rel)
        asp[kind] = w / h
        out.append('<symbol id="pop%s" viewBox="0 0 %d %d"><image href="data:image/png;base64,%s"'
                   ' x="0" y="0" width="%d" height="%d"/></symbol>'
                   % (kind.capitalize(), w, h, base64.b64encode(raw).decode(), w, h))
    return ('<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>%s'
            '</defs></svg>' % "".join(out)), asp


def band(cols, cube_sz, top, band_h, ink, num, cubes, counts, asp):
    """One card's band.

    `cols` are the four pill centres (piety, wheat, stone, silver); `cubes` and `counts` are the
    serf and acolyte pairs; `num` is the board's own numeral helper; `asp` comes from `defs`.
    """
    row_y = top + band_h / 2.0
    fig_cx = (cols[0], cols[2])                                   # over piety, over stone
    sq_cx = ((cols[0] + cols[1]) / 2.0, (cols[2] + cols[3]) / 2.0)  # between the pairs
    o = []
    for i, kind in enumerate(("serf", "acolyte")):
        w = FIG_H * asp[kind]
        # translated group with the mark centred inside it, so a picker can swap the mark
        # without recomputing where it goes
        o.append('<g class="pslot" data-slot="%s" transform="translate(%.2f %.2f)">'
                 '<use href="#pop%s" x="%.2f" y="%.2f" width="%.2f" height="%.2f"/></g>'
                 % (kind, fig_cx[i], row_y, kind.capitalize(), -w / 2.0, -FIG_H / 2.0, w, FIG_H))
        o.append('<g transform="translate(%s %s)">%s</g>' % (sq_cx[i], row_y, cubes[i]))
        o.append(num(sq_cx[i] + cube_sz / 2.0 + NUM_GAP, row_y + 5, counts[i], anchor="start"))
    # the divider splits the air BETWEEN the groups -- which is not the midpoint of the squares,
    # since each group runs from its figure's left edge to the right of its count
    x = ((sq_cx[0] + cube_sz / 2.0 + NUM_GAP + _NUM_W)
         + (fig_cx[1] - FIG_H * asp["acolyte"] / 2.0)) / 2.0
    o.append('<path d="M%.1f %.1f V%.1f" stroke="%s" stroke-opacity=".35" stroke-width="1"/>'
             % (x, row_y - DIV_HALF, row_y + DIV_HALF, ink))
    return "".join(o)
