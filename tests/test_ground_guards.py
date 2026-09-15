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


# THREE GUARDS USED TO LIVE BELOW THIS ONE and were removed with the thing they guarded: the
# library ornament at the foot of the player column. They checked that it painted no ground of its
# own, that it was `contain`-fitted rather than cropped, and that its slot was exactly what the
# four boards left over. None of that has an object any more -- `corner_ornament`, `.gv-corner` and
# `corner_h` are all gone from gen_game_view.
#
# What the first of them recorded is worth keeping, because it outlives the picture: that band is
# 405 x 136.8 px of bare ground now, and the plan for it was acolyte counters or majority markers.
# Whatever goes there will need `pointer-events` thought about, which is what that guard existed
# to stop anyone quietly deleting.
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
