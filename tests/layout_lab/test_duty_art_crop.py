"""The crop script and the committed Clerical pair must not drift apart.

A production crop is only trustworthy while the master plus the recipe still reproduces it. If
someone edits the script's geometry, or replaces a master, or hand-retouches a crop, the pair in
the repository quietly stops being what the recipe says it is -- and nothing would say so, because
the files still open and still look right.
"""
import importlib.util
import json
import pathlib

import numpy as np
import pytest
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

# WHICH FOLDER EACH ACTION USES IS NOT WRITTEN HERE ANY MORE. It was -- a map of eight duties
# with two folders each -- and it was a second copy of a fact attribution.json already owns in
# `slotFolders`, so the two could disagree and only one of them was ever read by anything that
# ships. It also encoded a claim duty_text.json contradicts: that every duty has two actions.
# Taxation and Allocation have one each, which that file has said all along in its
# `singleAction` note, and the leftover taxation/action_b and allocation/special_activity
# folders came from before the wording existed.
def slot_folders() -> dict:
    """attribution.json's map of duty -> {slot: folder}, which is the one place it is kept."""
    doc = json.loads((ART.parent / "attribution.json").read_text(encoding="utf-8"))
    folders = doc.get("slotFolders")
    assert folders, "attribution.json has no slotFolders, so nothing says where art goes"
    return folders


def _crop_module():
    spec = importlib.util.spec_from_file_location("crop_duty_master", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_every_duty_has_a_master_and_a_folder_for_each_action_it_actually_has():
    """The shape of the tree, asserted so a half-created duty is noticed at once.

    Empty directories do not survive a clone, so each leaf that holds no art yet carries a
    keep-file. Asserting the directories exist would pass on a machine where they were created by
    hand and fail on a fresh checkout; asserting the keep-files exist is what actually travels.

    EACH ACTION IT HAS, not two. This asserted two for every duty and was wrong for three of
    them: Taxation and Allocation have one action each, and Ordination had two retired folders
    beside its two real ones. The count now comes from attribution.json's `slotFolders`, and the
    test below pins that against duty_text.json so neither can drift alone.
    """
    assert ART.is_dir(), "ui/board_v2/duty_actions is missing"
    for duty, slots in slot_folders().items():
        for leaf in ["masters"] + sorted(slots.values()):
            d = ART / duty / leaf
            assert d.is_dir(), "missing folder: %s" % d.relative_to(ROOT)
            kept = list(d.glob("*"))
            assert kept, "%s is empty and would not survive a clone" % d.relative_to(ROOT)


def test_the_folder_map_and_the_wording_describe_the_same_board():
    """`slotFolders` and duty_text.json each say how many actions a duty has. One answer.

    Falsified by giving a duty a second action in the wording without a folder for it, or by
    leaving a folder behind for an action that was dropped -- which is exactly how
    taxation/action_b and allocation/special_activity survived.
    """
    text = json.loads((ART.parent / "duty_text.json").read_text(encoding="utf-8"))["duties"]
    for duty, slots in slot_folders().items():
        said = [s for s in ("actionA", "actionB") if text[duty].get(s) is not None]
        assert sorted(slots) == sorted(said), (
            "%s has folders for %s and wording for %s" % (duty, sorted(slots), sorted(said)))
    assert sorted(slot_folders()) == sorted(text), (
        "the folder map and the wording do not cover the same duties")


def test_no_duty_carries_a_folder_the_map_does_not_name():
    """A folder nobody can place is art waiting to go missing.

    `masters` is the one exception, and it is named here rather than inferred so that adding a
    second exception is a decision somebody writes down.
    """
    folders = slot_folders()
    for duty, slots in folders.items():
        found = sorted(f.name for f in (ART / duty).iterdir()
                       if f.is_dir() and f.name != "masters")
        assert found == sorted(slots.values()), (
            "%s has %s on disk and %s in the map" % (duty, found, sorted(slots.values())))


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


# =================================================================================================
# TINT MATCHING
#
# The point of this feature is a restraint -- that L* does not move -- so that is what most of
# these check. A transfer that also shifted the tone would be worse than none: it would quietly
# flatten the engraving on every duty, and the numbers it was added to fix would still look right.


def test_lab_round_trips_exactly_and_agrees_with_the_textbook_values():
    """The conversion is hand-written in numpy, so it has to be shown to be right.

    scikit-image would have given this for free and is not a dependency of this project -- the
    dev extras carry numpy, scipy, pillow and playwright and nothing else -- so adding one for
    twenty lines of arithmetic would be the more expensive choice. The price of writing it out
    is having to prove it.
    """
    m = _crop_module()
    rng = np.random.default_rng(0)
    a = rng.integers(0, 256, (64, 64, 3)).astype(np.uint8)
    back = m.lab_to_rgb(m.rgb_to_lab(a))
    assert np.abs(back - a).max() < 1e-6, "sRGB -> CIELAB -> sRGB is not the identity"

    # Anchors anyone can check: white is L*100 and neutral, black is L*0, and mid grey is
    # neutral with an L* near 53.4.
    # 1e-4, not 1e-6: the sRGB primaries are published rounded, so their rows do not sum to the
    # white point to the last bit and white lands at L* 100.000004. Demanding exactness here
    # would be demanding that the standard's own constants be more precise than they are.
    white, black, grey = (m.rgb_to_lab(np.array([[[255, 255, 255]]]))[0, 0],
                          m.rgb_to_lab(np.array([[[0, 0, 0]]]))[0, 0],
                          m.rgb_to_lab(np.array([[[128, 128, 128]]]))[0, 0])
    assert abs(white[0] - 100) < 1e-4, "white came back at L* %.6f" % white[0]
    assert abs(white[1]) < 1e-3 and abs(white[2]) < 1e-3, "white is not neutral"
    assert abs(black[0]) < 1e-9
    assert abs(grey[0] - 53.585) < 0.01, "mid grey came back at L* %.3f" % grey[0]
    assert abs(grey[1]) < 1e-3 and abs(grey[2]) < 1e-3, "mid grey is not neutral"


def _matched(tmp_path, strength=1.0):
    m = _crop_module()
    out = tmp_path / "m"
    return m, m.crop_duty_master(MASTER, out, "l.png", "r.png", CROP_Y, True,
                                 match=MASTER, match_strength=strength)


def test_matching_does_not_touch_the_tone(tmp_path):
    """THE WHOLE GUARANTEE. L* is the engraving; only the chroma may move."""
    m = _crop_module()
    plain = m.crop_duty_master(MASTER, tmp_path / "a", "l.png", "r.png", CROP_Y, True)
    # A different picture as the reference, so the transform is a real one rather than a no-op.
    ref = ART / "ordination" / "masters" / "ordination_master_v02.png"
    if not ref.is_file():
        pytest.skip("no second master in the tree to match against")
    tinted = m.crop_duty_master(MASTER, tmp_path / "b", "l.png", "r.png", CROP_Y, True,
                                match=ref)
    for before, after in zip(plain, tinted):
        lb = m.rgb_to_lab(np.asarray(Image.open(before).convert("RGB")))[..., 0]
        la = m.rgb_to_lab(np.asarray(Image.open(after).convert("RGB")))[..., 0]
        worst = np.abs(lb - la).max()
        assert worst < 1.0, ("%s moved by up to %.3f L*; tint matching must leave the tone "
                             "alone or it is silently re-grading the artwork" % (after.name, worst))
        assert not ImageChops.difference(Image.open(before).convert("RGB"),
                                         Image.open(after).convert("RGB")).getbbox() is None, (
            "the tinted crop is byte-identical to the plain one, so nothing was matched")


def test_matching_puts_the_chroma_where_the_reference_has_it(tmp_path):
    """And it lands on the reference rather than merely moving towards it."""
    m = _crop_module()
    ref = ART / "ordination" / "masters" / "ordination_master_v02.png"
    if not ref.is_file():
        pytest.skip("no second master in the tree to match against")
    left, _right = m.crop_duty_master(MASTER, tmp_path / "b", "l.png", "r.png", CROP_Y, True,
                                      match=ref)
    want = m.chroma_stats(np.asarray(Image.open(ref).convert("RGB")
                                     .crop((0, CROP_Y, 2172, CROP_Y + 522))))
    got = m.chroma_stats(np.asarray(Image.open(left).convert("RGB")))
    for i, ch in enumerate("ab"):
        assert abs(got[i][0] - want[i][0]) < 0.6, (
            "%s* mean came out %+.2f against the reference's %+.2f" % (ch, got[i][0], want[i][0]))


def test_matching_at_zero_strength_changes_nothing(tmp_path):
    """The dial has to have a real off position, or 'a little' cannot be trusted either."""
    m = _crop_module()
    plain = m.crop_duty_master(MASTER, tmp_path / "a", "l.png", "r.png", CROP_Y, True)
    none = m.crop_duty_master(MASTER, tmp_path / "b", "l.png", "r.png", CROP_Y, True,
                              match=ART / "ordination" / "masters" / "ordination_master_v02.png"
                              if (ART / "ordination" / "masters"
                                  / "ordination_master_v02.png").is_file() else MASTER,
                              match_strength=0.0)
    for a, b in zip(plain, none):
        assert ImageChops.difference(Image.open(a).convert("RGB"),
                                     Image.open(b).convert("RGB")).getbbox() is None, (
            "--match-strength 0 still altered %s" % b.name)


def test_a_strength_outside_the_dial_is_refused(tmp_path):
    """Silently clamping 1.5 to 1.0 would hide a typo in a recipe that gets written down."""
    m = _crop_module()
    for bad in (-0.1, 1.5):
        with pytest.raises(SystemExit):
            m.crop_duty_master(MASTER, tmp_path / str(bad), "l.png", "r.png", CROP_Y, True,
                               match=MASTER, match_strength=bad)


def test_the_reference_is_fitted_on_its_band_not_the_whole_file():
    """The overscan is thrown away on both sides, so it has no vote in what the colour should be.

    Measured on the Clerical master the two differ -- a* mean 2.32 over the whole file against
    2.45 over the band -- small, and small in a direction nobody would notice until two duties
    cut from differently proportioned masters failed to agree.
    """
    m = _crop_module()
    whole = np.asarray(Image.open(MASTER).convert("RGB"))
    band_only = whole[CROP_Y:CROP_Y + 522]
    assert m.chroma_stats(whole) != m.chroma_stats(band_only), (
        "this master's band and its overscan happen to have identical chroma, so this test "
        "cannot tell the two apart -- pick another reference")
