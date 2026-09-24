"""The cards handed to the image model when a new acolyte sculpt is generated.

    python3 tools/ui_debug/generate_sculpt_reference.py
    python3 tools/ui_debug/generate_sculpt_reference.py --only base_scale_reference_27_wall_120

WHY A PICTURE AND NOT A SENTENCE

Every photograph of a miniature ever taken is at eye level, and a brief that asks for anything
else in words loses to that prior: sculpts came back at 9 degrees however the brief was worded.
What works is attaching a diagram of the BASE alone, drawn at the wanted ellipse ratio, with the
instruction to keep it exactly as it is. The base pins the camera and the figure follows it.

THIS FILE USED TO SAY "a figurine's camera cannot be steered by text", FLATLY, AND THAT IS
WRONG. What cannot steer it is a number of DEGREES. What steers it precisely is a bound stated
as an ellipse ratio -- see the next section but one. The old sentence generalised from the only
experiment that had been run, which happened to be the one that does not work, and it then sat
here for weeks being quoted as settled.

Only the base is drawn. Three attempts at including a schematic FIGURE produced two traffic cones
and a lampshade, any of which an image model might have copied, so the card carries the base, the
empty room above it, and nothing else.

WHY 27 DEGREES WHEN THE TARGET IS 32 -- DO NOT "CORRECT" THIS

The number on these cards is deliberately BELOW the target in
`tools/ui_debug/generate_asset_check.py`, and it is not a mistake left behind by a target that
moved. It was set to 27 while the target was 29, to correct a measured +3.1 degree bias. What
then happened is more useful than the arithmetic: the ask turned out not to steer the result at
all. Two batches of ten, with cards drawn to match, landed at 32.1 from a card of 30 and 31.9
from a card of 27 -- three degrees of instruction bought two tenths of a degree. This generator
has an attractor near 32 for a hooded figurine and will not be argued out of DEGREES, which is
why the target moved to 32 rather than the card moving to 32. It can be argued out of the angle
itself, just not in that unit.

So: every sculpt in ui/assets-gothic/sculpts/ was generated from a card reading 27, and each one
measures within 2.5 degrees of 32. Redrawing these cards at 32 has been measured to change nothing
about the output, while breaking the one property that matters -- that the committed sculpts and
the committed cards agree about how they were made.

WHAT THE CARD DIMENSIONS GETS COPIED; WHAT IT DOESN'T GETS INVENTED

The first card drew a side wall but never said how thick it was, and the bases that came back
were all over the place. Marking the wall as a measured dimension -- a witness line, a number,
and a sentence saying it is a measurement rather than a style choice -- changed the model's
behaviour from interpreting the picture to copying it: three of five reproduced the marked value
to within a pixel. That is the single most useful thing learned here, and it is why `wall` is a
parameter rather than a constant.

The copy is not perfect. The model over-reproduces the marked wall by roughly 7%, and it renders
at its own ~32-34 degrees rather than the card's 27, so the UPRIGHT wall ratio that
generate_asset_check.py reports comes out above the marked value on both counts. A card is
therefore drawn at the value wanted upright, times cos(the camera actually expected), divided by
the over-copy -- not at the value wanted.

EVERYTHING THIS SECTION USED TO SAY ABOUT THE BASE WAS A MEASUREMENT BUG

It read: 0.127 is a cliff edge, below it the card stops being read, a ceiling without a floor
costs the plinth, and four batches were tabulated as evidence. The tabulated bases were wrong.

sculpt_metrics.measure() found the plinth's lit rim by taking the brightest row in a band fixed
at 35 to 150 PIXELS above the bottom edge. That band cannot fail -- when the brightest thing in
view was a lit robe hem, argmax returned the last row searched, and the caller got the window's
own boundary back as a wall about twice the real one. Re-measured after the fix, the batches
that were called a collapse of the base are:

    card 0.110            5 of 5 bases in band   (reported as 1 of 5)
    card 0.120            4 of 5                 (reported as 1 of 5)
    cues + ceiling 0.53   4 of 5, and 4 passing both  (reported as 0 of 5)
    v2, first batch      10 of 10, all passing both   (reported as 3 of 10)

So there was no cliff, no anti-correlation being exploited, and no plinth cost. THE BASE WAS
ALMOST NEVER THE PROBLEM: eleven of fourteen monk batches have four in five or better once
measured correctly. What actually varied was the camera, and the card's wall value barely
moved it.

WHAT SURVIVES is the narrower claim this file opened with, which was measured on the drawing
rather than on the output: dimensioning the wall changed the model from interpreting the card
to copying it. The committed sculpts still reproduce their recorded numbers exactly under the
fixed measurement -- twenty-two of twenty-two -- so the art on file and the cards beside it are
unaffected. It is the conclusions drawn from the failures that were built on a broken ruler.

The lesson worth keeping is not about cards at all: a measurement that cannot return "I did not
find it" will return something, and something is indistinguishable from a reading.

THE SCALE LINE, AND WHAT IT ACTUALLY PRODUCES

The line sits at 2.4 x the base width. It was set there as a correction: the model appeared to
undershoot the scale it was given, a card marked 2.2 having produced figures at 2.01, and aiming
past a known undershoot is the fix for one. 2.2 was the number wanted because that is what the
concept art in ui/concept/ measures.

MEASURED AFTERWARDS, THE CORRECTION OVERSHOT. The three sculpts the first card produced come out
at 2.32 raw and 2.75 with the camera divided out -- not an undershoot of 2.4 but a 15% overshoot
of it, and 26% above the 2.2 the correction was aiming at. The earlier "2.01" was measured before
the camera was divided out and at a camera near 9 degrees, where the correction is worth about
1%; at 32 degrees it is worth 18%, so the two numbers were never comparable and the undershoot
they seemed to show was mostly the camera moving.

SO 2.2 IS NO LONGER AN ACTIVE TARGET, and nothing in the toolchain now enforces a proportion.
generate_asset_check.py measures height and reports it, and its verdict was withdrawn precisely
because a median cannot settle what the figures should look like -- the concept set at 2.18 and
the first card's output at 2.75 are two answers to a question of taste, not a right and a wrong
one. At a fixed board height the choice is really about base width: 2.18 gives a 114 px plinth
where 2.75 gives 90, and five acolytes have to share one tile's floor.

A CARD IS NEVER REDRAWN IN PLACE

Every card that has ever been attached to a brief stays in CARDS, at the numbers it was drawn
with, under its own filename. A card's value is that it still says what was actually asked, so
changing one would silently rewrite the provenance of every sculpt generated from it. A new
number means a new entry, and the `made` field records which sculpts came out of which card.

That is also why the first card is still reproduced with its wall left undimensioned. It is the
worst card of the three and it is kept exactly as it was, because player_3_lantern_at_waist.png
was generated from it and nothing else in the repo can say so.

The base is drawn dark because the prompt says to keep it exactly as it is, so its tone is
inherited without needing an instruction of its own. Pale bases were the loudest thing on a duty
tile -- four of them merged into a single bright mass with the figures seeming to float above it.
It is dark enough to sit under a pale robe and light enough to read against the card's own
background, which near-black was not.
"""
import argparse
import math
import pathlib

from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REFS = ROOT / "ui" / "assets-gothic" / "references"

BG = (17, 16, 14)
INK = (216, 208, 192)
FAINT = (112, 106, 96)
GOLD = (220, 188, 122)
STONE = (104, 99, 90)       # dark enough to sit under a pale robe, light enough to read
SIDE = (64, 61, 55)

THETA = 27.0
PROPORTION = 2.4

# Every card ever attached to a brief, at the numbers it was drawn with. The NUMBERS are frozen
# -- see "A CARD IS NEVER REDRAWN IN PLACE" above -- but `made` is a log and gets written as
# batches land, including the ones that failed. It is the only record linking a batch of art to
# the instruction that produced it, so a card that produced nothing usable still says so here.
CARDS = (
    {"name": "base_scale_reference_27.png",
     "wall": 24.0 / 360.0, "dimension_wall": False,
     "made": "the three seat-3 sculpts filed as player_3_lantern_at_waist.png, "
             "player_3_lantern_and_strap.png and player_3_staff_and_lantern.png until "
             "2026-09-24 -- now at sculpts/candidates/, each with _c01 appended, and replaced "
             "by player_3_v1.png, player_3_v2.png and player_3_v3.png"},
    {"name": "base_scale_reference_27_wall_127.png",
     "wall": 0.127, "dimension_wall": True,
     "made": "player_2_v1.png, and the two sculpts filed as player_2_v2_a.png and player_2_v2_b.png until 2026-09-23 -- now at sculpts/candidates/player_2_v2_a_c01.png and player_2_v2_b_c01.png"},
    {"name": "base_scale_reference_27_wall_120.png",
     "wall": 0.120, "dimension_wall": True,
     "made": "nothing usable. Five monks, 2026-09-22: one copied the wall, four ignored it at 0.217-0.227, and the camera fell to 23.2 -- the worst of the four cards. Kept as the record that the legibility floor it was drawn to test does not exist"},
)


def card(theta=THETA, proportion=PROPORTION, wall_ratio=24.0 / 360.0, dimension_wall=False):
    """One card. `wall_ratio` is the side wall as a fraction of the base's WIDTH.

    `dimension_wall` is not a style switch. It is the difference between a card the model
    interprets and a card it copies, and it is a parameter only so that the undimensioned
    original stays reproducible -- see the docstring.
    """
    # The dimensioned card is taller: the wall costs a numbered item in the copy list and a
    # second footer line, and the dimension itself needs room under the base.
    H = 1560 if dimension_wall else 1450
    top = 330.0 if dimension_wall else 300.0
    gap = 52 if dimension_wall else 40
    W = 900

    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im, "RGBA")
    s = math.sin(math.radians(theta))
    cx, R = W * 0.52, 180.0
    base_w = 2 * R
    # Rounded so that the original's 24/360 comes back as exactly 24.0 rather than as
    # 24.000000000000004, which would move a pixel and break the committed file's bytes.
    wall = round(wall_ratio * base_w, 6)
    cy = top + proportion * base_w

    d.ellipse([cx-R, cy-R*s+wall, cx+R, cy+R*s+wall], fill=SIDE)
    d.rectangle([cx-R, cy, cx+R, cy+wall], fill=SIDE)
    d.ellipse([cx-R, cy-R*s, cx+R, cy+R*s], fill=STONE, outline=(140, 134, 124), width=3)
    d.line([(cx-R, cy), (cx-R, cy+wall)], fill=(140, 134, 124), width=3)
    d.line([(cx+R, cy), (cx+R, cy+wall)], fill=(140, 134, 124), width=3)

    xg = cx - R - 86
    d.line([(xg, top), (xg, cy)], fill=GOLD, width=3)
    for y in (top, cy):
        d.line([(xg-13, y), (xg+13, y)], fill=GOLD, width=3)
    d.line([(cx-R, top), (cx+R, top)], fill=GOLD + (110,), width=2)
    d.text((xg-78, (top+cy)/2 - 26), "%.1f x W" % proportion, fill=GOLD)
    d.text((cx-R+8, top+10), "top of the hood reaches this line", fill=GOLD)

    yb = cy + R*s + wall + gap
    d.line([(cx-R, yb), (cx+R, yb)], fill=GOLD, width=3)
    for x in (cx-R, cx+R):
        d.line([(x, yb-11), (x, yb+11)], fill=GOLD, width=3)
    d.text((cx-42, yb+13), "width  W", fill=GOLD)
    xr = cx + R + 70
    d.line([(xr, cy-R*s), (xr, cy+R*s)], fill=GOLD, width=3)
    for y in (cy-R*s, cy+R*s):
        d.line([(xr-11, y), (xr+11, y)], fill=GOLD, width=3)
    d.text((xr+16, cy-9), "%.3f x W" % s, fill=GOLD)

    if dimension_wall:
        # On the LEFT, where the scale line already is, so the eye reads both as measurements
        # of the same drawing rather than as decoration on opposite sides of it.
        xw = cx - R - 40
        ytop, ybot = cy + R*s, cy + R*s + wall
        d.line([(xw, ytop), (xw, ybot)], fill=GOLD, width=3)
        for y in (ytop, ybot):
            d.line([(xw-11, y), (xw+11, y)], fill=GOLD, width=3)
        d.line([(xw, ybot+2), (cx-R+4, ybot+2)], fill=GOLD + (120,), width=2)
        d.line([(xw, ytop-2), (cx-R+4, ytop-2)], fill=GOLD + (120,), width=2)
        d.text((xw-146, (ytop+ybot)/2 - 9), "%.3f x W" % wall_ratio, fill=GOLD)
        d.text((xw-146, (ytop+ybot)/2 + 9), "side wall", fill=GOLD)

    d.text((46, 40), "BASE AND SCALE  -  CAMERA %d DEGREES ABOVE THE HORIZON" % round(theta),
           fill=INK)
    lines = [
        "The base of the figurine, and the room the figure must fill. The figure itself is",
        "deliberately not drawn -- sculpt it fully, in your own detail.",
        "",
        "Copy %s things from this image, and nothing else:" % ("four" if dimension_wall
                                                               else "three"),
        "1.  The base's SHAPE. A circle lying flat, seen from %d degrees above, so it draws"
        % round(theta),
        "    an ellipse whose height is %.3f of its width, its whole top face open." % s,
    ]
    n = 2
    if dimension_wall:
        lines += [
            "2.  The base's THICKNESS. The side wall is %.3f of the base's width -- as drawn"
            % wall_ratio,
            "    here. Match it. Thicker is wrong; thinner is also wrong.",
        ]
        n = 3
    lines += [
        "%d.  The base's TONE. It is dark stone -- darker than the figure standing on it." % n,
        "%d.  The SCALE. The figure's head reaches the marked line: %.1f times the base's"
        % (n + 1, proportion),
        "    width. Do not draw it squatter than that, and do not widen the base.",
    ]
    for i, t in enumerate(lines):
        d.text((46, 80 + i*23), t, fill=FAINT if i else INK)

    foot = ["If the base reads as a thin sliver, the camera is too low."]
    if dimension_wall:
        foot.append("The side wall is a measurement, not a style choice: match the mark.")
    for i, t in enumerate(foot):
        d.text((46, H - 40 - 24*(len(foot) - 1 - i)), t, fill=GOLD)
    return im


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None, help="folder to write into (default: %s)"
                    % REFS.relative_to(ROOT))
    ap.add_argument("--only", default=None,
                    help="draw one card by name, with or without its .png")
    args = ap.parse_args()

    out_dir = pathlib.Path(args.out).expanduser() if args.out else REFS
    out_dir.mkdir(parents=True, exist_ok=True)

    wanted = CARDS
    if args.only:
        stem = args.only[:-4] if args.only.endswith(".png") else args.only
        wanted = tuple(c for c in CARDS if c["name"][:-4] == stem)
        if not wanted:
            raise SystemExit("no card called %s -- have %s"
                             % (args.only, ", ".join(c["name"][:-4] for c in CARDS)))

    for spec in wanted:
        path = out_dir / spec["name"]
        card(wall_ratio=spec["wall"], dimension_wall=spec["dimension_wall"]).save(path)
        print("wrote %s" % path)
        print("    side wall %.3f x W%s  ->  %.3f upright at the 32 deg this model renders at"
              % (spec["wall"], "" if spec["dimension_wall"] else "  (NOT dimensioned)",
                 spec["wall"] / math.cos(math.radians(32.0))))
        print("    made: %s" % spec["made"])
    print("camera %.0f deg, ellipse ratio %.3f, scale line %.1f x W on every card"
          % (THETA, math.sin(math.radians(THETA)), PROPORTION))
    print("27 is deliberate and below the 32 target; cards are appended, never redrawn --")
    print("see this file's docstring before changing either")


if __name__ == "__main__":
    raise SystemExit(main())
