"""The crop script and the committed Clerical pair must not drift apart.

A production crop is only trustworthy while the master plus the recipe still reproduces it. If
someone edits the script's geometry, or replaces a master, or hand-retouches a crop, the pair in
the repository quietly stops being what the recipe says it is -- and nothing would say so, because
the files still open and still look right.
"""
import importlib.util
import pathlib

import pytest

# tests/layout_lab/ -> tests/ -> the repo root. This lives beside the other layout lab guards
# so that adding duty art runs it in the lab lane rather than dragging the whole engine suite
# along: art lands in ui/board_v2/, which CI routes as design-only.
ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "duty_art" / "crop_duty_master.py"
ART = ROOT / "ui" / "board_v2" / "duty_actions"
MASTER = ART / "clerical" / "masters" / "clerical_master_v01.png"
LEFT = ART / "clerical" / "gain_piety" / "clerical_gain_piety_v01.png"
RIGHT = ART / "clerical" / "gain_coins" / "clerical_gain_coins_v01.png"

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
    assert mod.DEFAULT_CROP_W == 1120, mod.DEFAULT_CROP_W
    assert mod.DEFAULT_CROP_H == 560, mod.DEFAULT_CROP_H


def test_the_committed_clerical_pair_is_what_the_recipe_produces(tmp_path):
    """Re-crop the master and compare to the committed pair, pixel by pixel.

    NOT byte by byte: PNG encoders differ between Pillow versions, so identical pixels can land in
    different files. Pixels are the thing being claimed.
    """
    Image = pytest.importorskip("PIL.Image", reason="pillow is needed to compare the crops")
    ImageChops = pytest.importorskip("PIL.ImageChops")
    for p in (MASTER, LEFT, RIGHT):
        assert p.is_file(), "missing committed asset: %s" % p.relative_to(ROOT)

    mod = _crop_module()
    left, right = mod.crop_duty_master(
        input_path=MASTER, out_dir=tmp_path,
        left_name="left.png", right_name="right.png")

    for made, committed, label in ((left, LEFT, "gain_piety"), (right, RIGHT, "gain_coins")):
        a = Image.open(made).convert("RGBA")
        b = Image.open(committed).convert("RGBA")
        assert a.size == b.size == (1120, 560), (label, a.size, b.size)
        assert ImageChops.difference(a, b).getbbox() is None, (
            "%s no longer matches what the master and the script produce" % label)


def test_the_geometry_the_readme_documents_is_the_geometry_the_script_uses():
    """The numbers in tools/duty_art/README.md, checked rather than trusted.

    The script's own docstring still describes a 2048 x 682 master with a 192 px overlap. That was
    an earlier master; this one is 2172 x 724 and the overlap is 68. Documentation that disagrees
    with the code is how the wrong crop box gets used a year from now, so the real numbers are
    asserted here and stated in the README.
    """
    Image = pytest.importorskip("PIL.Image")
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


def test_the_two_crops_actually_overlap_and_share_that_strip():
    """The overlap is the whole point, so prove the shared strip is genuinely shared.

    A crop pair that merely abuts would satisfy every dimension check above and still lose the
    continuity the master exists to provide.
    """
    Image = pytest.importorskip("PIL.Image")
    ImageChops = pytest.importorskip("PIL.ImageChops")
    overlap = 1120 * 2 - 2172
    assert overlap > 0, "the crops do not overlap at all"
    a = Image.open(LEFT).convert("RGBA")
    b = Image.open(RIGHT).convert("RGBA")
    # the right-hand `overlap` columns of LEFT are the left-hand `overlap` columns of RIGHT
    tail = a.crop((a.width - overlap, 0, a.width, a.height))
    head = b.crop((0, 0, overlap, b.height))
    assert ImageChops.difference(tail, head).getbbox() is None, (
        "the shared strip differs between the two crops, so they are not windows onto one scene")
