"""The crop script and the committed Clerical pair must not drift apart.

A production crop is only trustworthy while the master plus the recipe still reproduces it. If
someone edits the script's geometry, or replaces a master, or hand-retouches a crop, the pair in
the repository quietly stops being what the recipe says it is -- and nothing would say so, because
the files still open and still look right.
"""
import importlib.util
import pathlib

from PIL import Image, ImageChops

# IMPORTED, NOT importorskip'd. Three of the guards below used to reach for pillow that way, so
# on any machine without it -- CI, as it turned out -- they skipped, and a skip reads as green.
# The lane that runs them installs pillow; if it ever stops, these must go red rather than
# quietly stop checking that the committed crops are still what the recipe produces. Same
# argument the dev extras make for scipy: the test of a thing cannot degrade with it.

# tests/layout_lab/ -> tests/ -> the repo root. This lives beside the other layout lab guards
# so that adding duty art runs it in the lab lane rather than dragging the whole engine suite
# along: art lands in ui/board_v2/, which CI routes as design-only.
ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "duty_art" / "crop_duty_master.py"
ART = ROOT / "ui" / "board_v2" / "duty_actions"
# V03, cut ADJACENT. The v01 and v02 pairs were retired when the cut changed: they were
# 1120 x 560, a ratio of 2.000 against the slot's 2.038, so the board clipped about 3.5 px off
# every one of them with `fit: cover` and nobody saw it.
MASTER = ART / "clerical" / "masters" / "clerical_master_v03.png"
LEFT = ART / "clerical" / "gain_piety" / "clerical_gain_piety_left_v03.png"
RIGHT = ART / "clerical" / "gain_coins" / "clerical_gain_coins_right_v03.png"
# The one thing about the cut that is a choice rather than a consequence.
CROP_Y = 101

DUTY_ACTIONS = {
    "clerical": ("gain_piety", "gain_coins"),
    "taxation": ("action_a", "action_b"),
    "produce": ("gain_wheat", "gain_stone"),
    "build_roads": ("build_road", "build_shrine"),
    "construct": ("construct_building", "construct_road"),
    "give_alms": ("give_alms", "donate_building"),
    "ordination": ("ordain", "send_on_mission"),
    "allocation": ("relocate_acolytes", "special_activity"),
}


def _crop_module():
    spec = importlib.util.spec_from_file_location("crop_duty_master", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_every_duty_has_a_master_and_two_action_folders():
    """The shape of the tree, asserted so a half-created duty is noticed at once.

    Empty directories do not survive a clone, so each leaf that holds no art yet carries a
    keep-file. Asserting the directories exist would pass on a machine where they were created by
    hand and fail on a fresh checkout; asserting the keep-files exist is what actually travels.
    """
    assert ART.is_dir(), "ui/board_v2/duty_actions is missing"
    for duty, (a, b) in DUTY_ACTIONS.items():
        for leaf in ("masters", a, b):
            d = ART / duty / leaf
            assert d.is_dir(), "missing folder: %s" % d.relative_to(ROOT)
            kept = list(d.glob("*"))
            assert kept, "%s is empty and would not survive a clone" % d.relative_to(ROOT)


def test_the_crop_script_is_installed_and_runnable():
    assert SCRIPT.is_file(), "tools/duty_art/crop_duty_master.py is missing"
    assert (SCRIPT.parent / "README.md").is_file(), "tools/duty_art/README.md is missing"
    mod = _crop_module()
    # NO CROP SIZE CONSTANTS ANY MORE, and their absence is the point. The script used to carry
    # DEFAULT_CROP_W = 1120 and DEFAULT_CROP_H = 560, which is a 2.000 ratio typed into a tool
    # whose output goes into a 2.038 box -- the board clipped every image and nothing noticed.
    # The size is read from the layout lab's own state now, so there is nothing here to drift.
    assert not hasattr(mod, "DEFAULT_CROP_W"), (
        "a crop size is hard-coded in the script again; it belongs to the layout lab")
    band = mod.band()
    assert set(band) == {"card_w", "card_h", "gap", "span"}, sorted(band)
    assert band["span"] == band["card_w"] * 2 + band["gap"]


def test_the_committed_clerical_pair_is_what_the_recipe_produces(tmp_path):
    """Re-crop the master and compare to the committed pair, pixel by pixel.

    NOT byte by byte: PNG encoders differ between Pillow versions, so identical pixels can land in
    different files. Pixels are the thing being claimed.
    """
    for p in (MASTER, LEFT, RIGHT):
        assert p.is_file(), "missing committed asset: %s" % p.relative_to(ROOT)

    mod = _crop_module()
    left, right = mod.crop_duty_master(
        input_path=MASTER, out_dir=tmp_path,
        left_name="left.png", right_name="right.png", y=CROP_Y, quiet=True)

    band = mod.band()
    slot_ratio = band["card_w"] / band["card_h"]
    for made, committed, label in ((left, LEFT, "gain_piety"), (right, RIGHT, "gain_coins")):
        a = Image.open(made).convert("RGBA")
        b = Image.open(committed).convert("RGBA")
        assert a.size == b.size, (label, a.size, b.size)
        assert ImageChops.difference(a, b).getbbox() is None, (
            "%s no longer matches what the master and the script produce" % label)
        # THE SHAPE IS THE SLOT'S SHAPE, which is what the adjacent cut exists to give and what
        # the old 1120 x 560 pair did not have.
        #
        # MEASURED AS PIXELS CLIPPED, NOT AS A RATIO. A percentage was tried and is the wrong
        # instrument: the card's width is a whole number of master pixels, so its ratio can only
        # ever land NEAR the slot's, and how near depends on the master's width rather than on
        # anything anybody decided. What matters is what `fit: cover` actually throws away, and
        # that is a number of slot pixels -- under half of one is invisible. The old pair lost
        # about three and a half.
        s = max(band["card_w"] / a.width, band["card_h"] / a.height)
        clip = max(a.width * s - band["card_w"], a.height * s - band["card_h"])
        assert clip < 0.5, (
            "%s is %.5f against the slot's %.5f, so `fit: cover` clips %.2f slot pixels"
            % (label, a.width / a.height, slot_ratio, clip))

    assert Image.open(LEFT).size == Image.open(RIGHT).size, (
        "the two cards are different sizes, so the board would scale them differently")


def test_the_geometry_the_readme_documents_is_the_geometry_the_script_uses():
    """The numbers in tools/duty_art/README.md, checked rather than trusted.

    The script's own docstring still describes a 2048 x 682 master with a 192 px overlap. That was
    an earlier master; this one is 2172 x 724 and the overlap is 68. Documentation that disagrees
    with the code is how the wrong crop box gets used a year from now, so the real numbers are
    asserted here and stated in the README.
    """
    w, h = Image.open(MASTER).size
    assert (w, h) == (2172, 724), (w, h)

    crop_w, crop_h = 1120, 560
    y0 = (h - crop_h) // 2
    assert (y0, y0 + crop_h) == (82, 642)
    assert (0, crop_w) == (0, 1120)
    assert (w - crop_w, w) == (1052, 2172)
    assert crop_w * 2 - w == 68

    readme = (SCRIPT.parent / "README.md").read_text(encoding="utf-8")
    for fact in ("2172 x 724", "82 → 642", "1052 → 2172", "68 px"):
        assert fact in readme, "the README no longer states %r" % fact


def test_the_two_crops_do_not_overlap_and_the_gap_hides_what_is_between_them():
    """The cut is ADJACENT now, and this is the assertion that changed shape with it.

    It used to prove the two crops SHARED a strip, which was how the pair read as one place. The
    strip was a leftover rather than a decision -- 78 px on one master, 200 on another, neither
    chosen -- and the board has a 15 px gap between the cards that it was not accounting for.

    The cut splits the master where that gap falls, so the two crops share nothing and the gap
    hides a sliver instead. What has to be true now is that they are genuinely adjacent: the
    pixel after the left card's last column, plus the hidden sliver, is the right card's first.
    """
    mod = _crop_module()
    m = Image.open(MASTER)
    g = mod.boxes(m.width, m.height, mod.band(), CROP_Y)
    a, b = Image.open(LEFT), Image.open(RIGHT)

    assert g["left"][2] <= g["right"][0], (
        "the two cards overlap by %d px; this cut is meant to be adjacent"
        % (g["left"][2] - g["right"][0]))
    assert g["gap_w"] > 0, "there is nothing between the two cards for the board's gap to hide"

    # And what the gap hides really is the master's own middle, not something re-invented.
    hidden = m.convert("RGB").crop((g["left"][2], g["top"], g["right"][0], g["top"] + g["band_h"]))
    assert hidden.size == (g["gap_w"], g["band_h"])

    # The three pieces, laid back side by side, must reconstruct the band exactly -- which is
    # the strongest statement that nothing was lost or duplicated in the cut.
    rebuilt = Image.new("RGB", (m.width, g["band_h"]))
    rebuilt.paste(a.convert("RGB"), (0, 0))
    rebuilt.paste(hidden, (g["left"][2], 0))
    rebuilt.paste(b.convert("RGB"), (g["right"][0], 0))
    band = m.convert("RGB").crop((0, g["top"], m.width, g["top"] + g["band_h"]))
    assert ImageChops.difference(rebuilt, band).getbbox() is None, (
        "the two cards plus the hidden sliver do not add back up to the master's band")
