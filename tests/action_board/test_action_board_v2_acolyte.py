"""Guards for which acolyte the v2 board stands on its tiles, and how it is recoloured.

WHY THESE. The board can now be built with either of two figures, and everything that can go
wrong between them goes wrong QUIETLY. A drawn acolyte whose layers are missing falls back to the
hood, deliberately, so a board with no figures is not the failure mode -- a board with the WRONG
figure is, and it looks entirely normal. A shadow that stopped following the seat would give four
players the same green shade, which reads as a slightly muddy palette rather than as a bug. A
layer re-cut from a reshaped master would letterbox every figure by a pixel or two. None of these
raises, none of them logs, and none of them is visible without putting two builds side by side.

WHAT IS NOT HERE. How a figure is SIZED and where its feet go are the grid's business and are
guarded in test_action_board_v2_grid.py against whichever figure is configured; both publish the
same numbers, so those guards do not care which is drawn. This file covers the choosing and the
recolouring, which is what is new.
"""
import importlib.util
import json
import pathlib
import re
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOL = ROOT / "ui" / "board_v2" / "action_board"
TMPL = TOOL / "action_board_v2.html.tmpl"
ACOLYTES = ROOT / "ui" / "board_v2" / "tokens" / "acolytes"


def _load(name: str, where: pathlib.Path = TOOL):
    spec = importlib.util.spec_from_file_location("_abv2a_" + name, where / (name + ".py"))
    if spec is None or spec.loader is None:                       # pragma: no cover
        pytest.skip("cannot import %s" % name)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    sys.path.insert(0, str(where))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(where))
    return mod


def _function(text: str, name: str) -> str:
    head = "function %s(" % name
    assert text.count(head) == 1, "%s is declared %d times" % (name, text.count(head))
    i = text.index(head)
    j = text.index("{", i)
    depth = 0
    while True:
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                break
        j += 1
    return text[i:j + 1]


def _code(text: str) -> str:
    """The same JavaScript with its whole-line `//` comments dropped.

    The sibling suite has tripped on its own prose four times; the comments in this board's
    figure block name `data:` and the mask properties while explaining why they are where they
    are, so every guard below that asks whether a form appears asks about the CODE.
    """
    return "\n".join(ln for ln in text.split("\n") if not ln.strip().startswith("//"))


@pytest.fixture(scope="module")
def gen():
    return _load("generate_action_board_v2")


@pytest.fixture(scope="module")
def friar():
    return _load("friar")


@pytest.fixture(scope="module")
def hood():
    return _load("hood")


@pytest.fixture(scope="module")
def tmpl():
    return TMPL.read_text(encoding="utf-8")


def test_the_board_builds_whichever_figure_it_is_asked_for(gen, monkeypatch):
    """Both settings produce a board, and each produces the figure it was asked for.

    THE FALLBACK IS WHY THIS IS NOT OBVIOUS. A missing drawing is deliberately not fatal -- the
    board draws the hood and says so in the build line -- so "it built" proves nothing about
    which figure came out. The page's own figure object is what is read, because that is what
    the page branches on when it draws one.
    """
    seen = {}
    for choice in ("hood", "friar"):
        monkeypatch.setattr(gen, "ACOLYTE", choice)
        page, notes = gen.build()
        m = re.search(r"^var HOOD = (\{.*?\});\s*$", page, re.M)
        assert m, "the built page has no figure object to read"
        seen[choice] = json.loads(m.group(1))
    assert seen["hood"]["kind"] == "hood"
    assert seen["friar"]["kind"] == "friar", (
        "asked for the drawn acolyte and got %r. If its layers are missing the generator says "
        "so in its notes and falls back on purpose -- run tools/duty_art/split_acolyte.py "
        "--write and record the three files -- but a tree that HAS them should never land here."
        % seen["friar"]["kind"])


def test_a_figure_states_everything_the_grid_measures_it_by(gen, monkeypatch):
    """Both figures answer the same questions, so nothing downstream has to ask which it is.

    THIS IS THE CONTRACT THAT LETS THE REST OF THE BOARD IGNORE THE CHOICE. drawFigures sizes a
    figure, stacks a pile and places feet entirely out of these numbers. A figure that published
    only some of them would not fail here -- it would fail in the grid, as a row of acolytes
    0 pixels wide, which is a long way from the cause.
    """
    need = {"kind", "h", "swatch", "order", "step", "lean", "gap"}
    for choice in ("hood", "friar"):
        monkeypatch.setattr(gen, "ACOLYTE", choice)
        page, _ = gen.build()
        fig = json.loads(re.search(r"^var HOOD = (\{.*?\});\s*$", page, re.M).group(1))
        missing = sorted(need - set(fig))
        assert not missing, "the %s figure publishes no %s" % (choice, ", ".join(missing))
        assert fig["h"] > 0 and fig["swatch"] and fig["order"]


def test_the_shadow_is_each_seat_s_own_colour_with_the_light_taken_out(friar, hood):
    """Not a fixed second palette: a plum acolyte has plum shadows.

    THE FAILURE THIS CATCHES IS A QUIET ONE. Tint only the lit robe, or give every seat the
    master's own dark green, and the board still draws four acolytes in four colours -- each
    with a green shadow on it. It reads as a muddy palette rather than as a bug, and it is the
    single most likely way for this to be got wrong, because the shadow is the one colour that
    has to be computed rather than looked up.
    """
    import colorsys

    shades = {k: friar.shade_of(v) for k, v in hood.SEAT_SWATCH.items()}
    assert len(set(shades.values())) == len(shades), (
        "two seats share a shadow: %s. The shadow has to be derived from the seat's own colour, "
        "or the players stop being told apart in exactly the places the figure is darkest."
        % shades)
    for seat, base in hood.SEAT_SWATCH.items():
        def hls(c):
            return colorsys.rgb_to_hls(*[int(c[i:i + 2], 16) / 255 for i in (1, 3, 5)])
        bh, bl, _ = hls(base)
        sh, sl, _ = hls(shades[seat])
        assert sl < bl, "%s's shadow (%s) is not darker than %s" % (seat, shades[seat], base)
        # THE HUE IS THE PART THAT MATTERS and it must not drift: a shadow is the same cloth
        # with less light on it. Wrapping is allowed for, because hue is a circle and bone sits
        # near the join.
        drift = min(abs(sh - bh), 1 - abs(sh - bh))
        assert drift < 0.06, ("%s's shadow is hue %.3f against the robe's %.3f -- a shadow that "
                              "changes colour is a second swatch, not a shadow" % (seat, sh, bh))


def test_the_layers_on_disk_are_the_shape_the_module_publishes(friar):
    """FRIAR_H is a number in a file and the layers are pictures; they have to agree.

    IF THEY DRIFT, EVERY FIGURE LETTERBOXES. The board sizes a figure's box from this number and
    stretches the layers to fill it, so a master re-cut at a different aspect does not fail --
    it squashes all forty-two acolytes by however much the two disagree, which is invisible
    until it is a pixel or two and then looks like bad drawing rather than bad arithmetic.
    """
    Image = pytest.importorskip("PIL.Image", reason="Pillow is not installed")
    sizes = {}
    for layer in friar.LAYERS:
        found = sorted(ACOLYTES.glob("%s_%s_v*.webp" % (friar.STEM, layer)))
        assert found, ("no %s layer under %s -- run tools/duty_art/split_acolyte.py --write"
                       % (layer, ACOLYTES))
        sizes[layer] = Image.open(found[-1]).size
    assert len(set(sizes.values())) == 1, (
        "the three layers are different sizes (%s). They are cut from one master in one pass and "
        "are stacked on top of each other, so any difference is a file that did not come from "
        "this master." % sizes)
    w, h = next(iter(sizes.values()))
    assert abs((h / w) - friar.FRIAR_H) < 0.002, (
        "the layers are %d x %d, an aspect of %.4f, and friar.FRIAR_H says %.4f. Re-cutting a "
        "reshaped master means moving that number too -- nothing downstream re-measures the "
        "picture." % (w, h, h / w, friar.FRIAR_H))


def test_a_figure_s_markup_carries_no_picture_of_its_own(tmpl):
    """The masks are stylesheet, once, not markup repeated per figure.

    FORTY-TWO FIGURES IS WHAT MAKES THIS WORTH A GUARD. A mask-image is a data URI of about
    twenty kilobytes; set in each figure's own style attribute the page would carry it forty-two
    times and still look exactly right, which is how a megabyte goes missing without anybody
    seeing a symptom. The overlay is an <img> and points at one string, which is the same
    bargain made the other way round.
    """
    draw = _code(_function(tmpl, "friarLayers"))
    assert "data:" not in draw, (
        "friarLayers writes a data URI into every figure it draws. The two masks belong in the "
        "two custom properties the stylesheet sets once; only the overlay is a src, and it is "
        "one string the markup points at.")
    assert "mask-image" not in draw, (
        "friarLayers sets a mask on the figure itself. That is the stylesheet's job -- see the "
        "--robe-mask and --shade-mask rules -- or it is written once per figure.")
    style = tmpl[:tmpl.index("</style>")]
    for prop in ("--robe-mask", "--shade-mask"):
        assert prop in style, "the stylesheet never reads %s, so a mask would have to be set " \
                              "per figure" % prop


def test_a_pile_zigzags_evenly_from_the_ground_up(gen, tmpl):
    """Every step up a stack is the same size, including the first one.

    THE FIRST STEP USED TO BE HALF THE OTHERS. The jog alternated a figure LEFT or RIGHT of its
    column -- minus a lean, plus a lean, minus a lean -- and the figure standing on the line was
    exempted at zero, because a seat's feet must not move when its count changes. That exemption
    is right and the arithmetic it caused was not: the offsets ran 0, +lean, -lean, +lean, so
    the first step was one lean and every step above it was two. A stack that is supposed to
    zigzag evenly did not, and it was reported as the bottom pair looking misaligned against a
    row that looked fine from the second figure up.

    THE FEET ARE STILL CHECKED, because the fix must not buy evenness with the thing the
    exemption was protecting. The figure on the line sits on its column exactly, whatever the
    depth.

    IT RUNS THE TEMPLATE'S OWN EXPRESSION rather than restating it, so any rule that is even and
    leaves the ground row alone will pass -- which is correct. What is being guarded is the
    shape of the stack, not one way of writing it.

    Falsify: exempt any row from the jog, or make the offsets alternate about the column again.
    """
    page, _ = gen.build()
    fig = json.loads(re.search(r"^var HOOD = (\{.*?\});\s*$", page, re.M).group(1))
    body = _function(tmpl, "drawFigures")
    m = re.search(r"var side = (.+?);", body)
    assert m, "drawFigures no longer computes a `side` for each figure in a pile"
    expr = m.group(1)

    def sides(n):
        script = ("var lean = %r, out = [];\n"
                  "for (var up = 0; up < %d; up++){ var side = %s; out.push(side); }\n"
                  "process.stdout.write(JSON.stringify(out));\n" % (fig["lean"], n, expr))
        done = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
        return json.loads(done.stdout)

    for n in range(1, 7):
        s = sides(n)
        assert s[0] == 0, (
            "in a pile %d deep the figure on the line is offset by %g. Its feet have to stay on "
            "the column, or a seat's foot moves sideways when it gains an acolyte and the row "
            "of feet the eye compares heights against stops being a row." % (n, s[0]))
        steps = [abs(round(s[i + 1] - s[i], 9)) for i in range(len(s) - 1)]
        assert len(set(steps)) <= 1, (
            "a pile %d deep steps by %s. The steps have to be equal or the stack reads as "
            "misaligned at whichever end is the odd one out -- which is how this was found: the "
            "first step was half the rest and the bottom two figures looked wrong against a "
            "stack that looked right above them."
            % (n, ", ".join("%g" % v for v in steps)))
    assert sides(2)[1] != 0, (
        "nothing is nudged at all, so a pile is one smeared silhouette rather than several "
        "people. An even jog of nothing is even and is not a jog.")
    # AND THE PILE STAYS OVER ITS COLUMN. Even steps alone do not say that: a staircase --
    # `up * lean` -- steps evenly, leaves the ground row alone, and walks the top of a four-deep
    # pile three leans off the column it belongs to, which leans the whole stack. That passed an
    # earlier version of this test, which is how the clause got here.
    worst = max(abs(v) for v in sides(6))
    assert worst <= abs(fig["lean"]) + 1e-9, (
        "a figure is nudged %g from its column against a lean of %g. The jog is meant to break a "
        "stack up, not to carry it sideways -- past one lean the pile stops standing over the "
        "feet it is built on." % (worst, fig["lean"]))
