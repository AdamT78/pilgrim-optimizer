"""The two resource-box layouts, and the rule that keeps them from becoming a coordinate table.

WHAT IS ACTUALLY AT RISK HERE

Not the picture -- the picture is obvious the moment you look at a board. What is at risk is the
thing that made the second layout cheap: every number in it is DERIVED from the rectangle the
template already declares for that box. The disc sits on the box's own lower-right corner, the icon
insets from the box's own edges, the numeral lands a fixed fraction along its diagonal.

The failure that would matter is someone, in a hurry, writing the four positions out by hand --
because it works, and because nothing then complains. The board looks identical and the cost is
invisible until a fifth resource arrives and needs a fifth set of coordinates, and a sixth after
that, and the layout stops being a rule and becomes a table nobody dares edit.

So these tests do not check that the disc is at x 914. They check that it is at the corner of
whatever rectangle that resource's box happens to be, for every resource, which is a thing a
hand-written table would fail the moment two boxes differ in width -- and two of them do: piety is
205 wide and the other three are 215.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
UI = REPO / "ui"
ASSETS = UI / "assets-gothic"
SVG_NS = "http://www.w3.org/2000/svg"


def q(tag: str) -> str:
    return f"{{{SVG_NS}}}{tag}"


@pytest.fixture(scope="module")
def asm():
    path = UI / "render" / "gen_board_gothic.py"
    if not path.is_file() or not ASSETS.is_dir():
        pytest.skip("the gothic tree is not in this checkout")
    spec = importlib.util.spec_from_file_location("gothic_assembler", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build(asm, layout):
    config = copy.deepcopy(json.loads((ASSETS / "production_test_config.json").read_text()))
    if layout is None:
        config.pop("resource_layout", None)
    else:
        config["resource_layout"] = layout
    asm.apply_seat(config)
    board_layout = asm.read_json(ASSETS / "metadata" / "layout.json")
    root = ET.parse(ASSETS / "template" / "player_board_template.svg").getroot()
    asm.apply_config(root, config, board_layout)
    return root


def groups(asm, root):
    return {name: root.find(f".//{q('g')}[@id='resource-{name}']") for name in asm.RESOURCE_NAMES}


def test_the_default_is_the_strip_and_draws_no_disc(asm):
    """A config that says nothing about layout gets exactly what it always got."""
    for group in groups(asm, build(asm, None)).values():
        assert group.find(q("circle")) is None, "the strip layout drew a disc"
        assert group.find(q("line")) is not None, "the strip layout lost its rule"
        assert len([r for r in group if r.tag == q("rect")]) >= 3


def test_an_unknown_layout_is_refused(asm):
    """Silently falling back to the strip would hide a typo in a config for as long as it lived."""
    with pytest.raises(asm.BuildError):
        build(asm, "quarter-moon")


def test_the_disc_sits_on_each_boxs_own_corner(asm):
    """The whole point: position is a rule about the box, not a table of four positions.

    Piety's box is 205 wide and the other three are 215, so a hand-written table that happened to
    be right for one of them is wrong for the others -- which is exactly what this would catch.
    """
    for name, group in groups(asm, build(asm, "disc")).items():
        rects = [r for r in group if r.tag == q("rect")]
        box = rects[0]
        x, y = float(box.get("x")), float(box.get("y"))
        w, h = float(box.get("width")), float(box.get("height"))
        disc = group.find(q("circle"))
        assert disc is not None, f"{name}: the disc layout drew no disc"
        assert float(disc.get("cx")) == pytest.approx(x + w), (
            f"{name}: the disc is at cx {disc.get('cx')}, but its box's right edge is {x + w}")
        assert float(disc.get("cy")) == pytest.approx(y + h), (
            f"{name}: the disc is at cy {disc.get('cy')}, but its box's foot is {y + h}")
        assert float(disc.get("r")) == pytest.approx(asm.DISC_RADIUS)


def test_the_count_lands_inside_the_visible_quadrant(asm):
    """A numeral outside the disc is on the icon, which is the one place it must not be.

    Checked as geometry rather than by eye: the text's anchor must be inside the circle, and up and
    left of the corner, which together is the quarter the box's clip actually shows.
    """
    for name, group in groups(asm, build(asm, "disc")).items():
        disc = group.find(q("circle"))
        text = group.find(q("text"))
        cx, cy, r = (float(disc.get(k)) for k in ("cx", "cy", "r"))
        tx, ty = float(text.get("x")), float(text.get("y"))
        assert tx < cx and ty < cy, f"{name}: the count is outside the visible quadrant"
        assert ((tx - cx) ** 2 + (ty - cy) ** 2) ** 0.5 < r, (
            f"{name}: the count sits {((tx - cx) ** 2 + (ty - cy) ** 2) ** 0.5:.1f} from the "
            f"corner, outside the disc's {r:.0f}")


def test_the_numeral_clears_the_box_it_is_clipped_by(asm):
    """The constraint the first sizing pass could not see, and so did not check.

    The quadrant has three edges -- the arc, the box's foot, the box's right side -- and the ink
    check that sized this measured only the first, because it looked for the numeral's pixels
    INSIDE the box's own crop and anything the box clipped was therefore invisible to it. It
    reported room. What it missed was the numeral sitting twelve units off the foot, which at a
    405 px board is under three pixels and reads as a number sinking out of its disc.

    Checked here as the distance from the numeral's baseline to the box's foot, which is the
    quantity that shrank: no rendering needed, and it fails if either the placement or the font
    moves the numeral back down.
    """
    for name, group in groups(asm, build(asm, "disc")).items():
        rects = [r for r in group if r.tag == q("rect")]
        foot = float(rects[0].get("y")) + float(rects[0].get("height"))
        text = group.find(q("text"))
        baseline = float(text.get("y"))
        clearance = foot - baseline
        assert clearance >= 15, (
            f"{name}: the numeral's baseline is only {clearance:.1f} above the box's foot. Below "
            f"about 15 it reads as falling out of the disc at a realistic board width.")


def test_the_numeral_is_readable_on_whatever_the_disc_leaves_under_it(asm):
    """The count's colour is derived from its ground, so the two cannot drift apart.

    The disc is a shadow rather than a patch, which means the numeral's ground is a different colour
    in every box -- each field darkened by its own amount. Setting the numeral's colour beside the
    shadow's and trusting them to stay compatible is the failure this forecloses: deepen the shadow
    later and a dark numeral quietly becomes unreadable on the one box nobody rendered.

    4.5:1 is the WCAG threshold for body text. These numerals are large and bold, where 3:1 would
    pass, so the margin here is deliberate -- the count renders near 8 px on a laptop and is already
    at the legibility floor the layout tool warns about.
    """
    for name, group in groups(asm, build(asm, "disc")).items():
        rects = [r for r in group if r.tag == q("rect")]
        field = rects[0].get("fill")
        ground = asm.darken(field, asm.DISC_FILL_OPACITY)
        numeral = group.find(q("text")).get("fill")
        ratio = asm.contrast(numeral, ground)
        assert ratio >= 4.5, (
            f"{name}: the count is {numeral} on {ground} -- {ratio:.1f}:1. Either the shadow moved "
            f"or the numeral's colour stopped being derived from it.")


def test_the_disc_layout_keeps_the_counts_and_the_icons(asm):
    """Restructuring a box must not quietly drop what the box is FOR."""
    strip = groups(asm, build(asm, None))
    disc = groups(asm, build(asm, "disc"))
    for name in asm.RESOURCE_NAMES:
        was = strip[name].find(q("text")).text
        now = disc[name].find(q("text")).text
        assert was == now, f"{name}: the count changed from {was!r} to {now!r}"
        icon = disc[name].find(f".//*[@data-asset-role='resource:{name}']")
        assert icon is not None, f"{name}: the disc layout lost its icon"
        assert float(icon.get("width")) > float(strip[name].find(
            f".//*[@data-asset-role='resource:{name}']").get("width")), (
            f"{name}: the icon did not grow, so the layout bought nothing")


def test_the_strip_furniture_is_gone_in_the_disc_layout(asm):
    """Left behind, the parchment band would sit under the icon and show at the box's foot."""
    for name, group in groups(asm, build(asm, "disc")).items():
        assert group.find(q("line")) is None, f"{name}: the strip's rule survived"
        rects = [r for r in group if r.tag == q("rect")]
        heights = {float(r.get("height")) for r in rects}
        assert len(heights) == 1, (
            f"{name}: the box still has rects of differing heights {sorted(heights)}, so the "
            f"parchment band was not removed")
