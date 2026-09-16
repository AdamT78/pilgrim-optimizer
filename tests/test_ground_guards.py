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

    bare = g.duty_grid_svg(tiles_dir=None, palettes=())
    assert "-ground" not in bare, (
        "duty_grid_svg() emitted a ground element at its defaults. Whatever the wheel sits on can "
        "no longer be seen through it.")

    painted = g.duty_grid_svg(tiles_dir=None, palettes=(), background="#123456")
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


def panorama_drawn():
    """The panorama the board actually paints, which is no longer a fixed file.

    Two are committed now and one is chosen, so a guard naming `panorama.webp` is a guard about
    the picture that happens to be OLDER rather than about the picture on screen. Asked of
    gen_panorama, which is the one place that answers it.
    """
    return render_module("gen_panorama").panorama_set()["out"]


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
    # The rule carries the ground, whatever the ground is: the page can be given the panorama or
    # a flat colour, and which it gets is a layout decision. What must not change is WHERE it is
    # painted, so this asks that the html,body rule still has a background at all, and separately
    # that asking for the picture still produces the picture.
    assert page and "background:%(ground)s" in page, (
        "gen_game_view's `html,body` rule no longer paints the ground. That rule is the ground "
        "for the whole view; without it the page has none.")
    lit = dict(gv.layout()); lit["ground_color"] = None
    assert "url(data:image/webp" in gv.ground_css(lit), (
        "asked for the panorama, the page ground came out without it (%r). The picture is gone "
        "and the flat colour is all that is left." % gv.ground_css(lit)[:80])
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
    # ASKED OF `ground_css`, not of the template. The rule now reads `background:%(ground)s` and
    # the shorthand is assembled in that function, so the template no longer contains the ordering
    # this guard is about -- it would pass on a string with no colour in it at all.
    L = dict(gv.layout()); L["ground_color"] = None
    body = gv.ground_css(L)
    assert body.rstrip().endswith("#0b0a08"), (
        "the colour is not the final value of the background shorthand: %r. Put the colour last, "
        "or the declaration is invalid and dropped and the page renders white." % body.strip())
    # and the flat alternative is a bare colour, with nothing after it to invalidate
    L["ground_color"] = "#4d4844"
    flat = gv.ground_css(L)
    assert flat.strip() == "#4d4844" and "url(" not in flat, (
        "a flat ground came out as %r; it has to be the whole value, or the image and the colour "
        "are both in the shorthand and the picture wins." % flat)


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
    drawn = panorama_drawn()
    uri = dg.panorama_uri()
    assert uri.startswith("data:image/webp;base64,"), (
        "panorama_uri() returned %r... -- either the asset is missing (the fallback is a "
        "transparent pixel) or it stopped being embedded." % uri[:60])
    assert base64.b64decode(uri.split(",", 1)[1]) == drawn.read_bytes(), (
        "panorama_uri() does not embed %s, which is the set gen_panorama names as the default. "
        "Some other file is being served as the ground." % drawn.name)


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
    # EVERY committed set, not just the one drawn. A panorama that is not the default today is
    # a panorama somebody switches to, and the shape is the part that cannot be judged by eye
    # afterwards -- at the wrong aspect the board covers the subjects and nothing says so.
    for p in [spec["out"] for spec in render_module("gen_panorama").SETS.values()]:
        if not p.is_file():
            continue
        w, h = Image.open(p).size
        assert 2.55 <= w / h <= 2.65, (
            "%s is %dx%d = %.3f:1. It is composed as two %.2f:1 halves butted together and "
            "its subjects sit in the outer quarters; at another aspect the board covers them."
            % (p.name, w, h, w / h, w / h / 2))


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
    drawn = panorama_drawn()
    assert dg.panorama_path().resolve() == drawn.resolve(), (
        "gen_duty_grid.panorama_path() points at %s, not %s, which is the set gen_panorama names "
        "as the default." % (dg.panorama_path(), drawn))
    assert tool.panorama_uri() == dg.panorama_uri(), (
        "the layout tool embeds a different file from gen_duty_grid.panorama_uri(). The two paths "
        "have drifted; one of them is pointing somewhere that no longer exists.")


def test_the_field_is_cropped_and_not_stretched():
    """`cover`, and this is the one property of the background that varies with the screen.

    `100% 100%` stretches: a 2.600:1 panorama on a 1.758:1 laptop is squashed by a third, every
    figure short and wide and the engraving's line weight anisotropic. `cover` keeps the aspect and
    crops to the middle instead -- which is also where the composition is empty, so it is the
    better picture rather than a consolation. Measured through the real exposed ground inside the
    duty wheel, stretching put 15.5% of the channel area over L50 at 1512x860 against a CEILING of
    50; cropping puts the board on the composed middle at every size.

    A revert to `100% 100%` is invisible on the screen this was composed for -- the crop there is
    3 px of height -- so it would be found on a laptop, months later, as "the art looks wrong".
    """
    gv = render_module("gen_game_view")
    tool = render_module("gen_layout_tool")
    # gen_game_view's is built rather than written, so it is asked for with the panorama on --
    # the flat-colour case has no size to state and nothing for `cover` to be wrong about.
    gv_L = dict(gv.layout()); gv_L["ground_color"] = None
    for name, css, selector in (("gen_game_view", "x{background:%s}" % gv.ground_css(gv_L), "x"),
                                ("gen_layout_tool", tool.PAGE, "#screen")):
        decl = rule(css, selector)
        assert decl and "/cover" in decl, (
            "%s's `%s` does not size the panorama with `cover` (%r). `100%% 100%%` stretches the "
            "picture to the viewport and squashes it on anything narrower than 2.6:1."
            % (name, selector, (decl or "").strip()))
        assert "100% 100%" not in decl.replace("%%", "%"), (
            "%s's `%s` still carries a `100%% 100%%` size alongside `cover`." % (name, selector))

    # AND THE PAGE, not only the template it came from. Everything above reads the SOURCE string,
    # where `%%` is how a literal percent is written -- so a template that is correct there can
    # still emit `50.0%% 50%%/cover`, which is not a CSS length and drops the whole declaration.
    # That shipped, and every guard in this file stayed green while it did: the escaping depends
    # on how many times the string is formatted, and CSS is one `%` pass here and two elsewhere.
    # The general form of the fault is a doubled percent surviving into the output, so that is
    # what this looks for rather than the one declaration that had it.
    page = REPO / "ui" / "generated" / "game-view.html"
    if not page.is_file():
        pytest.skip("the game view has not been built in this checkout")
    # The WHOLE file, not a prefix. The first attempt read the first 200 KB and passed the
    # falsification, because the embedded panorama is half a megabyte of base64 and pushes the
    # rule that had the fault well past any prefix worth guessing at. base64 has no percent in
    # its alphabet, so scanning all of it costs a moment and cannot collide.
    head = page.read_text(encoding="utf-8")
    assert "%%" not in head, (
        "the built game view carries a doubled percent in its CSS, which is not a valid length: "
        "%r. A template escaped for two format passes was given one, or the other way round."
        % head[max(0, head.find("%%") - 70):head.find("%%") + 12])


def wheel_in_panorama(screen, fit):
    """Which rectangle of the panorama the duty wheel covers, as fractions of the picture.

    Both the board and the background are centred on the viewport, so this is arithmetic rather
    than rendering: the board is zoom-to-fitted to the canvas, and the background is laid out by
    `fit` -- either stretched to the viewport or `cover`-scaled and centre-cropped.
    """
    import json
    SW, SH = screen
    L = json.load(open(REPO / "ui" / "layout.json"))
    gv = render_module("gen_game_view")
    G = gv.geometry(L)
    CW, CH = L["canvas_width"], L["canvas_height"]
    zoom = min(SW / CW, SH / CH)
    ox, oy = (SW - CW * zoom) / 2, (SH - CH * zoom) / 2
    wx1 = CW - G["pad"]; wx0 = wx1 - G["wheel"]
    wy0 = G["top_h"] + G["banner_h"]; wy1 = wy0 + G["wheel"]
    sx0, sx1 = ox + wx0 * zoom, ox + wx1 * zoom
    sy0, sy1 = oy + wy0 * zoom, oy + wy1 * zoom
    if fit == "stretch":                       # the picture is the viewport
        return sx0 / SW, sx1 / SW, sy0 / SH, sy1 / SH
    from PIL import Image
    PW, PH = Image.open(PANORAMA).size         # cover: scaled to cover, then centre-cropped
    s = max(SW / PW, SH / PH)
    dw, dh = PW * s, PH * s
    px, py = (SW - dw) / 2, (SH - dh) / 2      # negative: the picture overhangs the viewport
    return (sx0 - px) / dw, (sx1 - px) / dw, (sy0 - py) / dh, (sy1 - py) / dh


def test_cover_puts_the_wheel_on_the_same_piece_of_picture_at_every_size():
    """The invariant `cover` actually buys, and the reason it is not merely an aesthetic choice.

    Stretched, the share of the panorama the board covers grows as the screen narrows, because the
    canvas is 4:3 and zoom-fitted while the picture is pinned to the viewport: at 3440x1320 the
    wheel sits over 47.1%-75.1% of the picture, and at 1512x860 over 45.6%-87.3% -- which is out
    past where the right half's shrine begins. Under `cover` both the board and the picture scale
    with the screen's height, so the wheel lands on the SAME rectangle of the painting on every
    display narrower than the panorama.

    That is what made the ceiling reading stop varying. Measured through the real exposed ground
    inside the wheel, over L50: 2.2%, 2.8%, 14.5%, 14.3%, 15.5% stretched across the five screens
    in gen_layout_tool.SCREENS; 2.2%, 2.8%, 2.9%, 2.9%, 2.9% cropped.

    Tested as geometry rather than as a render because it IS geometry: the mapping from canvas to
    picture is arithmetic, and a browser would only render the same numbers more slowly.

    NOT because a browser is unavailable. The ui lane installs chromium for the picker guards, so
    the exposed-ground reading quoted above could be taken here. It is not, and the reason is the
    threshold rather than the mechanism: the residual 2.8% sits ABOVE the CEILING of 50 that
    gen_ground enforces on the flat field, so a guard for it would have to be given a number
    chosen to pass -- which is a guard that protects nothing. The numbers are recorded until that
    is decided rather than pinned at a value nobody argued for.
    """
    # `cover` needs the picture's own aspect, which means reading the file. This runs in the lane
    # that installs neither numpy nor Pillow as well as the ui one, and a bare `from PIL import`
    # there is an ERROR rather than a skip -- which is the same dependency escaping that has now
    # turned a run red twice.
    if not PANORAMA.is_file():
        pytest.skip("the committed panorama is not in this checkout")
    pytest.importorskip("PIL", reason="reading the panorama's aspect needs Pillow")
    narrow = [(2560, 1300), (1920, 940), (1512, 860)]
    boxes = [wheel_in_panorama(s, "cover") for s in narrow]
    for got, screen in zip(boxes[1:], narrow[1:]):
        assert all(abs(a - b) < 1e-6 for a, b in zip(got, boxes[0])), (
            "under `cover` the wheel covers %s of the panorama at %s but %s at %s. Both the board "
            "and the picture are meant to scale with the screen's height, so this rectangle is "
            "supposed to be the same on every display narrower than 2.6:1."
            % (tuple(round(v, 4) for v in got), screen,
               tuple(round(v, 4) for v in boxes[0]), narrow[0]))

    # and the guard has to know that this was NOT already true, or it is asserting a tautology
    spread = [wheel_in_panorama(s, "stretch") for s in narrow]
    assert not all(abs(a - b) < 1e-6 for a, b in zip(spread[-1], spread[0])), (
        "stretched, the wheel already covers the same piece of the panorama at every size -- so "
        "this guard is not distinguishing `cover` from `100%% 100%%` and proves nothing. Check "
        "whether the canvas stopped being zoom-fitted.")


def test_the_committed_panorama_is_the_one_the_script_makes():
    """Re-join it from the two halves and compare bytes, because the record now says you can.

    The same guard ground.webp has, for the same reason: `reproducibleBy` promises the script
    rebuilds the file byte for byte, and that promise is what lets the repo treat the picture as a
    convenience and the join as the source. It matters more here than there. The join is not a
    concatenation -- a de-vignette and a level match sit between the halves and the result, both
    derived by measuring the images -- so if someone re-encodes the picture, edits it, or changes
    EDGE or FADE without rebuilding, the record starts describing a file that no longer exists and
    nothing else would notice.

    It also guards the halves themselves. They are committed LOSSLESS precisely because the level
    match is measured off their inner 16 columns; re-encoding either of them lossy would move that
    measurement and this comparison would fail, which is the intended outcome rather than a
    nuisance.
    """
    import sys as _sys
    if not (RENDER / "gen_panorama.py").is_file():
        pytest.skip("gen_panorama.py is not in this checkout")
    if not PANORAMA.is_file():
        pytest.skip("the committed panorama is not in this checkout")
    pytest.importorskip("numpy", reason="the join is numpy")
    pytest.importorskip("PIL", reason="encoding the result needs Pillow")
    _sys.path.insert(0, str(RENDER))
    import gen_panorama

    # EVERY set, because the promise is per picture. The one that is not the default is the one
    # nobody looks at, so it is the one whose halves quietly stop reproducing it.
    checked = 0
    for name, spec in sorted(gen_panorama.SETS.items()):
        if not spec["out"].is_file():
            continue
        for half in (spec["left"], spec["right"]):
            assert half.is_file(), (
                "%s is missing. The halves are diffusion output with no seed on record: without "
                "them the %s panorama cannot be rebuilt, only restored." % (half, name))

        im, _step, seam = gen_panorama.join(pano_set=name)
        assert gen_panorama.encode(im) == spec["out"].read_bytes(), (
            "%s is not what gen_panorama.py now produces (%d bytes committed, %d regenerated). "
            "Either the join changed and the picture was not rebuilt, or the picture was edited "
            "outside the script -- and its attribution record claims the two are interchangeable. "
            "Run `python3 ui/render/gen_panorama.py --set %s`."
            % (spec["out"].name, spec["out"].stat().st_size,
               len(gen_panorama.encode(im)), name))
        assert max(abs(v) for v in seam.values()) < 0.5, (
            "the %s join leaves a step of %.2f grey levels at the seam. Both corrections are "
            "supposed to bring it to zero; a step this size means one of them stopped applying."
            % (name, max(abs(v) for v in seam.values())))
        checked += 1
    assert checked >= 2, (
        "only %d panorama set(s) were checked. Two are committed, and a set whose picture is "
        "missing from the tree is skipped here -- so this passing means less than it looks."
        % checked)


def test_the_devignette_is_not_a_no_op_and_not_a_free_hand():
    """The correction that removes the crease has to do something, and only near the edge.

    This one is worth guarding separately because it is invisible in the result: the crease it
    removes is 2 levels deep, so a de-vignette that quietly stopped working would leave a picture
    that still looks right in every thumbnail and shows a soft seam at full size. The first
    assertion is that it moves the edge columns at all; the second is that it leaves the middle of
    the half alone, which is what makes it a correction rather than a filter.
    """
    import sys as _sys
    if not (RENDER / "gen_panorama.py").is_file():
        pytest.skip("gen_panorama.py is not in this checkout")
    np = pytest.importorskip("numpy", reason="the join is numpy")
    pytest.importorskip("PIL", reason="reading the halves needs Pillow")
    _sys.path.insert(0, str(RENDER))
    import gen_panorama
    from PIL import Image
    left = gen_panorama.panorama_set()["left"]
    if not left.is_file():
        pytest.skip("the halves are not in this checkout")

    a = np.asarray(Image.open(left).convert("RGB")).astype(float)
    b = gen_panorama.devignette(a, "right")
    edge = np.abs(b[:, -gen_panorama.EDGE:, :] - a[:, -gen_panorama.EDGE:, :]).mean()
    rest = np.abs(b[:, :-gen_panorama.EDGE, :] - a[:, :-gen_panorama.EDGE, :]).max()
    assert edge > 0.2, (
        "de-vignetting the left half's inner edge changed it by %.3f levels on average -- that is "
        "nothing. Either EDGE no longer covers the ramp, or the halves were re-encoded and the "
        "ramp is gone, in which case this correction should be removed rather than left inert."
        % edge)
    assert rest == 0.0, (
        "de-vignetting touched pixels outside its %d-column window (max change %.3f). It is meant "
        "to lift a ramp at one edge, not to grade the picture." % (gen_panorama.EDGE, rest))
