"""The ground under the whole board, and the two properties it silently depends on.

WHAT THE GROUND IS

The duty wheel draws no ground of its own. `gen_duty_grid.BACKGROUND` is None, so the component
emits no rect, and whatever the wheel sits on shows through the channels between the nine tiles --
about 32% of the canvas, as one connected region that also runs down every gutter. The stage paints
it, once, and that single declaration is what becomes a picture later.

WHY THAT NEEDS GUARDING RATHER THAN DOCUMENTING

Both properties it rests on fail quietly, and both fail in a way that looks like an art problem
rather than a code problem.

    the ceiling        The tiles are read by their torn silhouettes. Over a 5 px band just inside
                       every outline that silhouette has a median luminance of 53.4, so a ground
                       brighter than that stops the edge separating -- and not everywhere at once,
                       only where the field happens to be bright. One corner of the board goes soft
                       and the rest is fine, which reads as a bad tile rather than a bad ground.
                       This is not hypothetical: the first field generated looked right in
                       isolation and measured L 61.5 where it actually shows.

    the one surface    Exactly one element may paint the ground. Any component that paints its own
                       punches an opaque hole in it -- invisible today, because the hole is the
                       same colour as the ground, and obvious the day the colour becomes a picture.
                       That is the worst shape a fault can have: introduced under one setting, paid
                       for under another, with nothing in between to connect them.

The committed image is a convenience; `ui/render/gen_ground.py` is the source, and its attribution
record claims the two are interchangeable. A claim in a record that nothing re-tests is a claim
about the past.

AND THE ONE THING THAT SITS ON THE GROUND

The library ornament at the foot of the player column is the first component placed ON the ground
rather than beside it, so it is the first that can break the arrangement from the other side. Its
guards are here rather than in a file of their own for two reasons: what they enforce is the
ground's own rule -- paint nothing, intercept nothing, let the field show through -- and this file
is already named in the `ui` lane of .github/workflows/tests.yml, which runs an explicit list. A
new file would need a line added there, or it would run nowhere on exactly the design-only pull
request that touches it.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
RENDER = REPO / "ui" / "render"
GROUND = REPO / "ui" / "assets-gothic" / "ui" / "ground.webp"


def ground_module():
    if not (RENDER / "gen_ground.py").is_file():
        pytest.skip("gen_ground.py is not in this checkout")
    pytest.importorskip("numpy", reason="the field is numpy")
    pytest.importorskip("PIL", reason="measuring pixels needs Pillow")
    sys.path.insert(0, str(RENDER))
    import gen_ground
    return gen_ground


def grid_module():
    if not (RENDER / "gen_duty_grid.py").is_file():
        pytest.skip("gen_duty_grid.py is not in this checkout")
    sys.path.insert(0, str(RENDER))
    import gen_duty_grid
    return gen_duty_grid


def view_module():
    if not (RENDER / "gen_game_view.py").is_file():
        pytest.skip("gen_game_view.py is not in this checkout")
    sys.path.insert(0, str(RENDER))
    import gen_game_view
    return gen_game_view


def test_the_committed_ground_is_the_one_the_script_makes():
    """Re-generate it and compare bytes, because the attribution record says you can.

    `reproducibleBy` on ui/ground.webp promises the script rebuilds it byte for byte, which is what
    lets the repo treat the image as a convenience and the generator as the source. If someone
    re-encodes the file, edits it by hand, or changes a default in the generator without rebuilding,
    that promise quietly stops being true and the record starts describing a file that no longer
    exists. Nothing else would notice: the board still renders, and it renders with whatever is
    actually committed.
    """
    g = ground_module()
    if not GROUND.is_file():
        pytest.skip("the committed ground is not in this checkout")
    im = g.field(g.W * 2, g.H * 2)          # --scale 2, the committed setting
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=88, method=6)
    assert buf.getvalue() == GROUND.read_bytes(), (
        "ui/assets-gothic/ui/ground.webp is not what gen_ground.py now produces (%d bytes "
        "committed, %d regenerated). Either the generator changed and the image was not rebuilt, "
        "or the image was edited outside the generator -- and its attribution record claims the "
        "two are interchangeable. Run `python3 ui/render/gen_ground.py`."
        % (GROUND.stat().st_size, len(buf.getvalue())))


def test_the_ground_stays_under_the_ceiling_the_tiles_need():
    """The committed field must not rise above the luminance where tile edges stop separating.

    THIS IS THE WEAKER OF THE TWO READINGS AND THAT IS DELIBERATE. `gen_ground.py --check` measures
    the field through the real exposed-ground mask -- the only pixels that are actually visible --
    and that is the reading that decides. It needs a knocked-out render of the whole board, which is
    not committed and would be stale the moment the layout moved, so it cannot live here.

    What is left is the whole-field reading, which includes the 68% the panels cover. It is
    forgiving: a field far too bright in the gutters is dragged down by the covered majority and
    would pass. It still catches the failure that matters here -- someone raising --gain, or
    dropping in a brighter field -- because this field is fairly uniform, so the two readings track
    each other closely (47.4 against 47.1 when this was written). Do not mistake that for the
    guarantee. The guarantee is --check.
    """
    g = ground_module()
    if not GROUND.is_file():
        pytest.skip("the committed ground is not in this checkout")
    from PIL import Image

    # `ceiling=` passed explicitly, not left to the default. `under_ceiling`'s default argument is
    # bound at import, so a test that changes CEILING and calls it bare compares against the old
    # value while REPORTING the new one -- which is how this guard first passed a deliberately
    # lowered ceiling. Reading the same constant the message quotes is the whole point.
    med, p99, ok = g.under_ceiling(Image.open(GROUND), ceiling=g.CEILING)
    assert ok, (
        "the committed ground reaches L %.1f at its 99th percentile, over the %.1f ceiling. The "
        "tile silhouettes have a median edge luminance of 53.4, so above that they stop separating "
        "-- in whichever region the field is bright, not everywhere, which is why this is measured "
        "rather than looked at. Median is %.1f." % (p99, g.CEILING, med))


def test_the_wheel_draws_no_ground_of_its_own():
    """One element owns the ground, and it is not this one.

    The hole a second ground punches is invisible while both are the same flat colour, and the
    whole point of the arrangement is that one day one of them is a picture. So the check has to be
    that the component draws NOTHING, not that it draws something matching.

    The second half matters as much as the first. Asserting only that the default emits no ground
    would pass just as well if the ground element had been deleted outright -- the guard would then
    be enforcing a behaviour the code no longer has, and nobody would find out until they wanted a
    wheel that carries its own sheet. So an explicit colour must still produce one.
    """
    g = grid_module()
    assert g.BACKGROUND is None, (
        "gen_duty_grid.BACKGROUND is %r. The wheel is meant to draw no ground so the stage's own "
        "background -- a colour now, a picture later -- shows through the channels between the "
        "tiles. A colour here paints over it." % (g.BACKGROUND,))

    bare = g.duty_grid_svg(tiles_dir=None, arrows=False, palettes=())
    assert "-ground" not in bare, (
        "duty_grid_svg() emitted a ground element at its defaults. Whatever the wheel sits on can "
        "no longer be seen through it.")

    painted = g.duty_grid_svg(tiles_dir=None, arrows=False, palettes=(), background="#123456")
    assert 'id="dg-ground"' in painted and "#123456" in painted, (
        "duty_grid_svg(background=...) no longer draws a ground. The component is still supposed "
        "to be able to carry its own sheet -- None means 'let the page show through', not 'this "
        "feature is gone'.")


def _rule(css, selector):
    """The declarations of one CSS rule, as written. Enough for a stylesheet built by hand."""
    import re
    m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert m, "%s is no longer in gen_game_view.CSS at all" % selector
    return m.group(1)


def test_the_ornament_neither_paints_the_ground_nor_catches_the_pointer():
    """The picture at the foot of the board column is decoration, and must behave like it.

    BOTH HALVES FAIL INVISIBLY TODAY, WHICH IS WHY THEY ARE TESTED RATHER THAN TRUSTED.

        paints nothing     It sits ON the ground, so a background, border or shadow on it is a
                           second ground -- the exact hole this file's other guard keeps out of the
                           duty wheel. Today the ornament's own art is opaque in the middle and its
                           alpha edge does the blending, so a background colour behind it would be
                           hidden by the art and visible only as a faint rectangle in the feather.
                           That is not a bug anyone finds by looking.

        catches nothing    `pointer-events:none`. Right now nothing interactive is underneath it,
                           so removing this changes precisely nothing -- until something is put
                           there. The known plan for that 405 x 136.8 band is acolyte counters or
                           majority markers, which are the things you would want to click. The
                           symptom then is a control that ignores the mouse in one corner, with the
                           cause a stylesheet line deleted months earlier for being inert.
    """
    v = view_module()
    box = _rule(v.CSS, ".gv-corner")
    assert "pointer-events:none" in box.replace(" ", ""), (
        "`.gv-corner` no longer sets pointer-events:none, so the ornament is now on top of "
        "whatever goes into the foot of the player column and will swallow its clicks and hovers. "
        "It is a picture; it should be transparent to the mouse. Rule reads: %s" % box.strip())
    for painted in ("background", "border", "box-shadow"):
        assert painted not in box, (
            "`.gv-corner` sets %s. One element owns the ground on this page and it is the stage; "
            "anything the ornament paints is a second ground, and because the picture's own art "
            "covers the middle you would see it only as a rectangle inside the feathered edge. "
            "Rule reads: %s" % (painted, box.strip()))


def test_the_ornament_is_fitted_and_never_cropped():
    """`contain`, not `cover` -- and the difference is the feathered edge, not a few pixels.

    The picture's edges sit at L 7 against a ground of L 23 under that corner, so it is committed
    with a soft alpha border that lets it die into the field. `cover` fills the box exactly and
    crops whatever does not fit, and what does not fit is that border: roughly 15 drawn px off the
    top and bottom at today's numbers. The result still looks like a picture, still fills its slot,
    and reads as a dark panel laid on the board instead of part of it. A reviewer comparing
    screenshots sees a slightly tighter crop, not a broken rule.

    `cover` is also what you would reach for if you wanted it to fill the slot edge to edge, which
    is a reasonable-sounding thing to want. Hence a guard rather than a comment.
    """
    v = view_module()
    img = _rule(v.CSS, ".gv-corner img").replace(" ", "")
    assert "object-fit:contain" in img, (
        "`.gv-corner img` is not object-fit:contain. If this is `cover`, the ornament is being "
        "cropped to fill its slot, and what gets cropped is the feathered alpha border that makes "
        "it sit ON the ground rather than on top of it. Rule reads: %s" % img)


def test_the_ornaments_slot_is_exactly_what_the_boards_leave():
    """Its height is a residue, and a residue that stops matching is a residue that overlaps.

    The ornament is placed out of flow at the bottom of #gv-left, so nothing in the browser stops
    it sliding under the last player board -- flow would have, which is exactly what was given up
    to stop the flex gap eating 30 px of it. What keeps them apart is arithmetic: corner_h is the
    column's height minus the boards, so the two tile the column exactly.

    If someone changes how boards_h is computed and not this, the ornament does not move; the
    boards grow down through it. The picture is dark and its top edge is feathered, so the first
    symptom is a player board looking slightly grubby along its bottom rail.

    The floor is checked in the same breath because it is the other end of the same number. Below
    it the picture is not smaller, it is letterboxed into a band -- worse than the bare ground it
    replaced -- so it must not be emitted at all.
    """
    v = view_module()
    L = v.layout()
    G = v.geometry(L)
    column_h = G["main_h"] - G["left_top"]
    assert abs(G["boards_h"] + G["corner_h"] - column_h) < 1e-6, (
        "the boards and the ornament no longer tile the player column: %.1f + %.1f = %.1f against "
        "a column %.1f tall. The ornament is positioned at the column's foot, so a gap here is a "
        "gap the page will not show you -- it is an overlap, and the boards are on top."
        % (G["boards_h"], G["corner_h"], G["boards_h"] + G["corner_h"], column_h))

    if not (REPO / "ui" / "assets-gothic" / "ui" / "library_corner.webp").is_file():
        pytest.skip("the ornament is not in this checkout")

    drawn, fit = v.corner_ornament(G["bw"], G["corner_h"])
    assert drawn and fit, (
        "nothing is drawn into the %.1f x %.1f the boards leave, though the picture is committed."
        % (G["bw"], G["corner_h"]))
    assert fit["h"] <= G["corner_h"] + 0.05 and fit["w"] <= G["bw"] + 0.05, (
        "the ornament is reported as %.1f x %.1f in a %.1f x %.1f slot, which means the generator "
        "and the browser disagree about what `contain` does."
        % (fit["w"], fit["h"], G["bw"], G["corner_h"]))

    squeezed, none_fit = v.corner_ornament(G["bw"], 12.0)
    assert squeezed == "" and none_fit is None, (
        "the ornament is still drawn into a 12 px slot. At that height it is not a small picture, "
        "it is a letterboxed band, and bare ground looks better. There is meant to be a floor.")
