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


# ---------------------------------------------------------------------------------------------
# THE FIELD MOVED OFF THE STAGE AND ONTO THE PAGE, and the guards below are for that move.
#
# The stage is a fixed 1600 x 1200 canvas that #gv-fit zoom-to-fits, so a background painted on it
# is a background painted on a rectangle in the middle of the screen. On a 3440-wide display the
# fit leaves 840 px either side, and those 840 px were flat colour -- which is what "the ground is
# clipped and I have black at the edges" was. `gen_tile_offsets` never had the fault because its
# own #stage is `flex:1` on the page, so the same declaration there always filled the viewport.
#
# So the ground is now on `html,body`, the stage is transparent, and the picture is a panorama
# composed for the shape of a widescreen rather than a tiling field. Four things can undo that
# silently, and each has a guard:
#
#   the stage paints again        one element owns the ground; a colour on the stage -- even the
#                                 same #0b0a08 -- puts the canvas rectangle back as a visible edge
#   the order flips               gen_board.py's lifted stylesheet sets `html,body{...background}`
#                                 too, at the same specificity, so ONLY document order decides
#   the colour moves first        in a multi-layer `background` shorthand the colour must be last;
#                                 first, the whole declaration is dropped and the page goes white
#   the asset is replaced         the composition keeps its subjects in the outer quarters and its
#                                 middle empty, which is only true of something near 2.6:1
#
# All four fail in the same shape: the page still renders, and it renders wrong in a way that reads
# as an art problem.


def render_module(name):
    """A generator module, loaded by path and not run as a program."""
    import importlib.util
    path = RENDER / ("%s.py" % name)
    if not path.is_file():
        pytest.skip("%s.py is not in this checkout" % name)
    sys.path.insert(0, str(RENDER))
    spec = importlib.util.spec_from_file_location("_ground_%s" % name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rule(css, selector):
    """The declaration block for `selector`, or None. Selectors here are literal, not patterns."""
    import re
    m = re.search(re.escape(selector) + r"\{([^}]*)\}", css)
    return m.group(1) if m else None


PANORAMA = REPO / "ui" / "assets-gothic" / "ui" / "panorama.webp"


def test_the_page_paints_the_field_and_the_stage_does_not():
    """One surface, and after this change it is the page rather than the stage.

    Both halves matter. Asserting only that `html,body` carries the picture would pass just as
    well with the stage still painting its own copy underneath -- and that is not a harmless
    duplicate: the stage's copy is stretched to the canvas, so it would draw a second, differently
    scaled crop of the same picture inside the first, with a hard edge where the canvas ends.
    """
    gv = render_module("gen_game_view")
    page = rule(gv.CSS, "html,body")
    stage = rule(gv.CSS, ".gv-stage")
    assert page and "url(%(panorama)s)" in page, (
        "gen_game_view's `html,body` rule no longer paints the panorama. That rule is the ground "
        "for the whole view; without it the page is the flat colour and the picture is gone.")
    assert stage is not None, ".gv-stage has no rule at all -- the stage is what gets zoom-fitted"
    assert "url(" not in stage, (
        "`.gv-stage` paints a background image again (%r). The stage is the 1600x1200 canvas, so a "
        "picture here is clipped to the canvas and drawn at a different scale from the page's -- "
        "which is the fault this change removed, plus a visible seam where the canvas ends."
        % stage.strip())


def test_the_colour_comes_last_in_the_shorthand():
    """A multi-layer `background` with the colour first is not a weaker rule, it is no rule.

    The declaration is invalid and the whole thing is dropped, so the page falls through to the
    browser default and goes WHITE -- not to #0b0a08, which is the one outcome that would have
    looked like a near miss. The old stage rule could write `#0b0a08 url(...)` because it had one
    layer; this one cannot, and the difference is invisible in a diff.
    """
    gv = render_module("gen_game_view")
    page = rule(gv.CSS, "html,body")
    decl = [d for d in page.split(";") if d.strip().startswith("background")]
    assert decl, "no `background` declaration in `html,body`"
    body = decl[0].split(":", 1)[1]
    assert body.rstrip().endswith("#0b0a08"), (
        "the colour is not the final value of the background shorthand: %r. Put the colour last, "
        "or the declaration is invalid and dropped and the page renders white." % body.strip())


def test_the_page_rule_is_written_after_the_stylesheet_it_has_to_beat():
    """gen_board.py's lifted stylesheet sets `html,body{...background...}` too, at equal weight.

    Two rules, one selector, same specificity: the later one wins and nothing else decides it. The
    page template emits `board_css` and then `css`, and if those two ever swapped the board's flat
    #0C0F0A would win and the panorama would simply never appear -- with both rules still present
    and correct, so a search for the picture would find it.

    The second assertion is what keeps this guard honest. If gen_board stopped setting a background
    on `html,body` there would be nothing to beat, and an ordering guard with no competitor passes
    forever while enforcing nothing.
    """
    import re
    gv = render_module("gen_game_view")
    i_board = gv.PAGE.index("%(board_css)s")
    i_own = gv.PAGE.index("%(css)s")
    assert i_board < i_own, (
        "the page emits its own stylesheet BEFORE gen_board's lifted one, so the lifted "
        "`html,body` background wins on document order and the panorama never shows.")
    board = (RENDER / "gen_board.py")
    if not board.is_file():
        pytest.skip("gen_board.py is not in this checkout")
    m = re.search(r"html,body\{([^}]*)\}", board.read_text(encoding="utf-8"))
    assert m and "background" in m.group(1), (
        "gen_board.py no longer sets a background on `html,body`, so the ordering above is not "
        "protecting anything. Either the competitor moved -- find where it went -- or this guard "
        "should be retired rather than left passing.")


def test_the_panorama_is_embedded_and_is_the_committed_file():
    """Linked would resolve in exactly one of the places these pages get opened from.

    Every generated page is written to ui/generated/ and then opened from wherever it lands, often
    as a file:// URL after being copied elsewhere. A relative href works in the tree and nowhere
    else, and the only symptom is a duller page.
    """
    import base64
    dg = grid_module()
    if not PANORAMA.is_file():
        pytest.skip("the committed panorama is not in this checkout")
    uri = dg.panorama_uri()
    assert uri.startswith("data:image/webp;base64,"), (
        "panorama_uri() returned %r... -- either the asset is missing (the fallback is a "
        "transparent pixel) or it stopped being embedded." % uri[:60])
    assert base64.b64decode(uri.split(",", 1)[1]) == PANORAMA.read_bytes(), (
        "panorama_uri() does not embed ui/assets-gothic/ui/panorama.webp. Some other file is "
        "being served as the ground.")


def test_the_panorama_is_the_shape_its_composition_assumes():
    """2.60:1, and that is a fact about the picture rather than a preference.

    Both halves were composed to keep every subject -- statue, candles, kneeling figures, deer --
    in the OUTER QUARTER of their frame, with the inner half empty fog, so that the board can sit
    on the middle without anything competing behind it. That arrangement only holds at the aspect
    it was drawn for. The canvas is 4:3 and zoom-to-fitted, so the narrower the screen the WIDER
    the share of it the board takes: 24.4%-75.6% on a 3440x1320 display, 12.1%-87.9% on a
    1512x860 laptop. Measured through the exposed ground inside the wheel, that is the difference
    between 2.8% of the channel area over L50 and 15.5% of it.

    So a 16:9 replacement dropped in here would put the candles under the tiles on every screen
    rather than only the small ones, and nothing else in the tree would notice.
    """
    if not PANORAMA.is_file():
        pytest.skip("the committed panorama is not in this checkout")
    pytest.importorskip("PIL", reason="reading the asset's size needs Pillow")
    from PIL import Image
    w, h = Image.open(PANORAMA).size
    assert 2.55 <= w / h <= 2.65, (
        "the panorama is %dx%d = %.3f:1. It is composed as two %.2f:1 halves butted together and "
        "its subjects sit in the outer quarters; at another aspect the board covers them."
        % (w, h, w / h, w / h / 2))


def test_the_layout_tool_shows_the_field_the_page_shows():
    """The tool that answers 'what will this look like on that screen' must not answer for a
    different ground.

    Its #screen is sized to the chosen screen's vw x vh in JS, so it is that tool's viewport and
    the exact analogue of `html,body` here; `.t-stage` is the exact analogue of `.gv-stage`. Before
    this change both modules painted the canvas and both were wrong in the same way, which is why
    the tool never showed the fault. If only one of them is fixed the tool is wrong in a NEW way --
    it would show a screen whose edges are flat black while the real page fills them -- and every
    judgement made in it about what reaches the edges would be made against the wrong picture.

    This repo has paid for two implementations of one picture three times: `gen_tile_offsets`
    drawing its own figures, the population rows reaching one assembler of four, and `place`
    before that. Same fault, third surface.
    """
    tool = render_module("gen_layout_tool")
    screen = rule(tool.PAGE, "#screen")
    stage = rule(tool.PAGE, ".t-stage")
    assert screen and "url(%(panorama)s)" in screen, (
        "the layout tool's #screen no longer paints the panorama, so its simulated screen shows a "
        "ground the real page does not.")
    assert stage is not None and "url(" not in stage, (
        "the layout tool's .t-stage paints a background image again (%r) -- the same clipped-to-"
        "the-canvas fault gen_game_view just had." % (stage or "").strip())


def test_both_modules_read_the_same_panorama():
    """gen_layout_tool cannot import gen_duty_grid, so the path is written twice. Hold them equal.

    The tool loads gen_game_view by PATH rather than importing the render package, so it carries
    its own copy of the embedding helper -- a duplication that predates this change and that the
    ground had too. Duplicated is survivable; duplicated and drifting is not, and the way it drifts
    is that one of them is moved or renamed and the other silently falls back to a flat colour and
    prints a line nobody reads.
    """
    dg = grid_module()
    tool = render_module("gen_layout_tool")
    if not PANORAMA.is_file():
        pytest.skip("the committed panorama is not in this checkout")
    assert dg.PANORAMA.resolve() == PANORAMA.resolve(), (
        "gen_duty_grid.PANORAMA points at %s, not the committed asset." % dg.PANORAMA)
    assert tool.panorama_uri() == dg.panorama_uri(), (
        "the layout tool embeds a different file from gen_duty_grid.panorama_uri(). The two paths "
        "have drifted; one of them is pointing somewhere that no longer exists.")
