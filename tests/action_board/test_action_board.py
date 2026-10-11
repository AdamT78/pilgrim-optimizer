"""Guards for ui/board_v2/action_board.

There are few of them on purpose. This tool is deliberately small and most of what it does is
visible the moment you open it; what is NOT visible is the handful of rules it is built on, and
those are what erode. Each test below names the failure it exists to catch and how to falsify it.
"""
import importlib.util
import json
import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOL = ROOT / "ui" / "board_v2" / "action_board"
TMPL = TOOL / "action_board.html.tmpl"
TEXT = ROOT / "ui" / "board_v2" / "duty_text.json"


def _load(name: str):
    spec = importlib.util.spec_from_file_location("_ab_" + name, TOOL / (name + ".py"))
    if spec is None or spec.loader is None:                       # pragma: no cover
        pytest.skip("cannot import %s" % name)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    sys.path.insert(0, str(TOOL))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(TOOL))
    return mod


def decls_for(page: str, sel: str) -> str:
    """Every declaration the page makes for one exact selector, comments stripped, joined.

    EVERY RULE WITH THE SELECTOR, NOT THE FIRST ONE FOUND, and that distinction has bitten. A
    selector gets written more than once when its parts arrive for different reasons -- .seal
    .filled is written twice, once to take the old ground away and once to light it, each with
    its own paragraph. The cascade reads all of them; a guard that reads the first one passes or
    fails on where a line happened to be typed.
    """
    css = re.sub(r"/\*.*?\*/", " ", page, flags=re.S)
    found = re.findall(re.escape(sel) + r"\{([^}]*)\}", css)
    assert found, "%s has no rule" % sel
    return ";".join(found)


@pytest.fixture(scope="module")
def geo():
    return _load("geometry")


@pytest.fixture(scope="module")
def gen():
    return _load("generate_action_board")


# =================================================================================================
# THE SPACING RULE
#
# The board has exactly two distances in it: GAP everywhere, and GAP_WIDE in the one place where
# the distance is carrying a meaning -- between the controls that belong to this turn and the ones
# that are always there. A third value would make that distinction say nothing.
#
# This is the test I most wanted. A spacing rule is not enforced by anybody noticing; it goes one
# box at a time, each change defensible on its own, and by the time it looks wrong there is no
# single commit to point at.

def test_every_gap_on_the_board_is_sixteen_or_thirty_two(geo):
    """Falsified by nudging any box by a pixel: geometry.gaps() names which gap went wrong."""
    assert geo.check() == [], "\n".join(geo.check())
    assert set(geo.gaps().values()) <= {geo.GAP, geo.GAP_WIDE}, geo.gaps()


def test_the_hand_check_still_runs_as_a_script():
    """`python geometry.py` prints the gaps and the complaints, and it can break while every
    other test passes.

    THIS IS A REAL FAULT, CAUGHT BY HAND AND NOT BY ANYTHING HERE. A helper that the module body
    does not call -- token_slots(), as it happens -- ended up BELOW the `if __name__` block while
    the Tithe was being tightened. Every import of the module went on working, because check()
    only reaches that helper when it is called and by then the whole file has executed. Run as a
    script, the block fires partway down the file and the name is not bound yet: the gaps print,
    and then it dies on a NameError in the middle of the output.

    Nothing else here can see it. Every other guard imports geometry, which is the one way of
    loading it that cannot fail this way -- so the hand check, which is how these numbers are
    actually read, is the only consumer with no test and the only one that broke.

    Falsified by moving any def below the `if __name__` block.
    """
    import subprocess
    r = subprocess.run([sys.executable, TOOL / "geometry.py"],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, "python geometry.py exits %d:\n%s" % (r.returncode, r.stderr[-800:])
    # AND IT PRINTED THE CHECK, not just the gaps. A script that died after the gaps table exits
    # non-zero, which the line above catches; one that silently stopped CALLING check() would not.
    assert "sound" in r.stdout or "  " in r.stdout.split("\n\n")[-1], (
        "the hand check printed no verdict:\n%s" % r.stdout[-400:])


def test_the_gaps_are_named_rather_than_counted(geo):
    """A set of values alone would pass on a board where two things OVERLAPPED by -16.

    So gaps() returns a mapping and every entry is positive. Falsified by moving the City above
    Hire Building, which leaves the set {16, 32} intact and the board nonsense.
    """
    for name, v in geo.gaps().items():
        assert v > 0, "%s is %d, so those two overlap" % (name, v)


def test_the_card_is_exactly_two_to_one(geo):
    """The masters are generated at 2:1, so `fit: cover` must have nothing to crop.

    Every earlier shape clipped something -- the 375 x 184 slot took 1.9% of the height, a
    600 x 320 box took 6.25% of the width. Falsified by changing ART_W or ART_H alone.
    """
    assert geo.ART_W / geo.ART_H == pytest.approx(2.0, abs=1e-9)
    # THE ROW STARTS ON THE RIBBON'S FIRST COLUMN. It ran from the first tile's CENTRE for a
    # while, which hung the row under the eight rather than butting it against them -- and meant
    # nothing on the board shared a vertical line with anything else.
    #
    # ON THE COLUMN, NOT ON THE DRAWN TILE, WHICH IS A REAL LOSS AND IS WRITTEN DOWN AS ONE.
    # They were one x while the tile filled its column. The tile is 74 and centred, so the card's
    # left edge now agrees with where the ribbon BEGINS -- the backdrop's edge, the unit the
    # cards are three of -- and not with any drawn box. Following the box instead would push the
    # row 40 right and leave 28 before the controls, under GAP_WIDE.
    assert geo.ROW_X == geo.X0, (
        "the card row starts at %d and the ribbon's first column at %d" % (geo.ROW_X, geo.X0))
    assert geo.art_slots()["actionA"]["x"] == geo.ROW_X, "the first card is not at the row's left"
    assert geo.ART_W == 3 * geo.SLICE_W + 2 * geo.TILE_GAP, (
        "a card is %d wide, which is not three of the ribbon's columns" % geo.ART_W)
    # AND IT STILL ENDS IN THE CONTROLS COLUMN -- the eighth tile's mark, carried down. Both ends
    # of the row now land on a tile: Clerical's left edge and Allocation's mark.
    assert geo.ROW_END == geo.MARKS_X + geo.MARKS_W, (
        "the row ends at %d and the controls column at %d"
        % (geo.ROW_END, geo.MARKS_X + geo.MARKS_W))
    # THE ROW IS NO LONGER PACKED, AND THAT IS THE CHANGE. It used to be cards, gap, cards, gap,
    # Tithe, gap, marks with nothing over, so the Tithe was whatever the others did not want.
    # Pulling the row left by 77 while the column stayed on Allocation's mark opened real air
    # between the Tithe and the controls, and the Tithe is now DECLARED rather than derived.
    #
    # SO THE ASSERTION IS THAT THE SLACK IS THERE, not that the parts sum to the whole: a sum that
    # balanced would mean either the Tithe had silently grown into the air or the column had been
    # dragged off its tile. check() owns how much slack is enough; this owns that it exists.
    packed = geo.ART_W * 2 + 2 * geo.ART_GAP + geo.TITHE_W + geo.GAP + geo.MARKS_W
    assert packed < geo.ROW_W, (
        "the row is packed edge to edge again (%d in a row of %d), so either the Tithe took the "
        "air or the column left the eighth tile" % (packed, geo.ROW_W))
    assert geo.TITHE_X + geo.TITHE_W < geo.MARKS_X - geo.GAP, (
        "the Tithe ends at %d and the column starts at %d, which is a gap rather than the space "
        "the row was moved to open" % (geo.TITHE_X + geo.TITHE_W, geo.MARKS_X))
    # AND IT STOPS SHORT OF THE MARGIN, which is the visible price and the thing somebody will be
    # tempted to "fix" by stretching the Tithe into it. The strip is the tile's own right margin
    # round its mark, carried down -- not a round number, and not nothing.
    assert geo.ROW_END < geo.X0 + geo.WORK_W, (
        "the row reaches the working edge again, so the column is back on the margin")
    # THE CARDS ARE STILL EXACTLY THREE TILES. ART_H is half ART_W and the wheel takes what the
    # cards leave, so paying for anything on this row by shaving a few pixels off each card -- the
    # cheap way, and the one that looks harmless in a diff -- would shorten the cards, shorten the
    # row and move the wheel.
    assert geo.ART_W == 3 * geo.SLICE_W + 2 * geo.TILE_GAP, (
        "a card is %d wide and three columns are %d -- the row was paid for out of the cards"
        % (geo.ART_W, 3 * geo.SLICE_W + 2 * geo.TILE_GAP))
    assert geo.TITHE_W < geo.TILE_PITCH, (
        "the Tithe is %d and a tile and a gap is %d, so nothing was tightened"
        % (geo.TITHE_W, geo.TILE_PITCH))
    # AND THE CARD IS MEASURED OFF THE RIBBON, which is what makes its edges land on column
    # edges. On COLUMNS, not on drawn tiles: three tiles and two gaps is 254 now, and the card is
    # three of the units the ribbon is divided into, which is what it always was.
    assert geo.ART_W == 3 * geo.SLICE_W + 2 * geo.TILE_GAP, (
        "a card is %d wide, which is not three of the ribbon's columns and their two gaps"
        % geo.ART_W)


def test_the_wheel_takes_its_shape_from_the_asset_and_not_from_here(geo):
    """The drawing is borrowed by path; a ratio copied into this tree would stop matching it.

    Falsified by hard-coding WHEEL_RATIO: this reads the asset's own viewBox and compares.
    """
    if not geo.WHEEL_ASSET.is_file():
        pytest.skip("the wheel asset is not in this tree")
    m = re.search(r'viewBox\s*=\s*"\s*[-\d.]+\s+[-\d.]+\s+([-\d.]+)\s+([-\d.]+)\s*"',
                  geo.WHEEL_ASSET.read_text(encoding="utf-8"))
    assert m, "the asset has no viewBox"
    assert geo.WHEEL_RATIO == pytest.approx(float(m.group(2)) / float(m.group(1)))
    assert geo.WHEEL_H == pytest.approx(geo.WHEEL_W * geo.WHEEL_RATIO, abs=1.0)


def test_every_duty_stands_on_a_face_the_drawing_actually_has(geo):
    """face_of() is arithmetic rather than a list, but the drawing still has to agree.

    Falsified by renaming a path in the SVG, or by moving a duty off a 45 degree multiple.
    """
    if not geo.WHEEL_ASSET.is_file():
        pytest.skip("the wheel asset is not in this tree")
    svg = geo.WHEEL_ASSET.read_text(encoding="utf-8")
    seen = set()
    for slug, _name, deg in geo.DUTIES:
        face = geo.face_of(deg)
        assert 'id="%s"' % face in svg, "%s stands on %r, which the drawing has no path for" % (
            slug, face)
        assert face not in seen, "two duties stand on %r" % face
        seen.add(face)


# =================================================================================================
# THE SAVE'S TWO PATHS
#
# Served, the button POSTs and the generator writes the files. Opened as a file it can only
# download. They must write the same keys into the same document -- the placement sheet learned
# this the hard way, when its offline path wrote the wire payload under the name of the placement
# file, a shape that file never has.

def test_the_page_is_handed_the_key_lists_rather_than_carrying_its_own(gen):
    """Falsified by typing a key list into the template: then the two paths can disagree."""
    page = TMPL.read_text(encoding="utf-8")
    assert "__SAVEKEYS__" in page, "the template no longer takes the key list from the build"
    for key in gen.MANIFEST_KEYS:
        assert '"%s"' % key not in page.split("var SAVE")[0], (
            "%r is written into the template as well as into the generator" % key)
    assert "SAVE.manifest" in page and "SAVE.image" in page, (
        "the save paths no longer read the key lists they were handed")


def test_a_save_refuses_a_key_the_manifest_has_no_room_for(gen, tmp_path, monkeypatch):
    """Silently dropping an unknown key is how a page comes to think it saved something.

    Falsified by making save() ignore extras instead of raising.
    """
    monkeypatch.setattr(gen, "MANIFEST", tmp_path / "action_board.json")
    with pytest.raises(ValueError):
        gen.save({"manifest": {"art": {}, "nonsense": 1}})
    with pytest.raises(ValueError):
        gen.save({"wire": {}})
    gen.save({"manifest": {"art": {"clerical/actionA": "x.png"}}})
    written = json.loads((tmp_path / "action_board.json").read_text(encoding="utf-8"))
    assert written["art"] == {"clerical/actionA": "x.png"}
    # Checked on the DATA, not on the raw text: the manifest's own note explains why bytes are
    # not in it, so a substring search finds the explanation and calls it the fault.
    assert set(written) <= ({"note", "version"} | set(gen.MANIFEST_KEYS)), sorted(written)
    assert "bytes" not in json.dumps({k: v for k, v in written.items() if k != "note"})


def test_the_manifest_names_files_and_never_carries_them(gen, tmp_path, monkeypatch):
    """PATHS, NOT BYTES. A manifest with pictures in it is megabytes nobody can read a diff of,
    and it is the reason the layout lab's export is 12.8 MB. Falsified by adding a bytes field."""
    monkeypatch.setattr(gen, "MANIFEST", tmp_path / "m.json")
    gen.save({"manifest": {"art": {"clerical/actionA": "clerical_gain_piety_left_v03.png"}}})
    raw = (tmp_path / "m.json").read_text(encoding="utf-8")
    assert "data:image" not in raw and "base64" not in raw
    assert len(raw) < 4096, "a manifest of one entry came to %d bytes" % len(raw)


def test_a_replaced_picture_never_overwrites_the_one_it_replaces(gen, tmp_path):
    """NOTHING IS OVERWRITTEN -- this tool has no undo, and not overwriting IS the undo.

    Falsified by having next_version() return a fixed name.
    """
    (tmp_path / "clerical_gain_piety_left_v03.png").write_bytes(b"old")
    nxt = gen.next_version(tmp_path, "clerical_gain_piety_left")
    assert nxt.name == "clerical_gain_piety_left_v04.png"
    assert not nxt.exists()
    assert gen.next_version(tmp_path, "nothing_here").name == "nothing_here_v01.png"


# =================================================================================================
# THE BUILD

def test_the_build_refuses_a_template_with_a_hole_left_in_it(gen, monkeypatch, tmp_path):
    """A token left in the page is not an error the browser reports -- it renders `__IMAGES__`
    as text inside a script and the page simply does not work, with nothing pointing at the
    build. So the build is what fails. Falsified by removing the check."""
    broken = tmp_path / "t.tmpl"
    broken.write_text(TMPL.read_text(encoding="utf-8") + "\n<!-- __NOT_FILLED__ -->\n",
                      encoding="utf-8")
    monkeypatch.setattr(gen, "TMPL", broken)
    with pytest.raises(SystemExit) as e:
        gen.build()
    assert "__NOT_FILLED__" in str(e.value)


def test_the_page_restates_no_geometry(gen):
    """EVERY NUMBER COMES FROM geometry.py. A pixel typed into the template is a number that
    will differ from the module's the first time one of them moves, and the playable board will
    import the module rather than the page -- so the page is the copy that goes quietly wrong.

    Falsified by writing any of the board's own figures into the template.
    """
    # COMMENTS ARE PROSE, not geometry -- the notes in the template quite reasonably mention
    # "590 x 295" while explaining why the originals must not be posted. Strip them first, so
    # this is a test about the code rather than about the writing.
    page = TMPL.read_text(encoding="utf-8")
    page = re.sub(r"/\*.*?\*/", " ", page, flags=re.S)
    page = re.sub(r"<!--.*?-->", " ", page, flags=re.S)
    page = re.sub(r"(?m)^\s*//.*$", " ", page)
    geo = _load("geometry")
    # MARKS_X AND ROAD_Y STAND WHERE CONFIRM_Y USED TO. The confirm row is gone, and a banned set
    # that quietly shrank when one of its members was deleted would be a guard getting weaker as
    # the board changes -- so the two objects that replaced it are named here instead.
    banned = {geo.CANVAS_W, geo.CANVAS_H, geo.ART_W, geo.ART_H, geo.ART_Y, geo.ROAD_Y,
              geo.MARKS_X, geo.SIDE_X, geo.SIDE_W, geo.WHEEL_Y, geo.TILE_W, geo.RIBBON_Y}
    found = set(int(n) for n in re.findall(r"(?<![\w.#-])(\d{3,4})(?![\w.%])", page))
    overlap = sorted(found & banned)
    assert not overlap, ("the template has %s written into it, and those are geometry.py's"
                         % ", ".join(str(n) for n in overlap))


def test_every_folder_under_a_duty_is_either_an_action_or_declared_not_to_be(gen):
    """A new folder beside a duty's actions silently becomes one of them.

    WHAT HAPPENED. `cutouts/` was added to hold the icons with their painted field knocked out --
    deliberately not on the board, since markFolders still lists only seals and icons. But the
    card art is found by walking every folder under a duty and skipping the ones nonSlotFolders
    names, and `cutouts` was not in that list. The cutouts carry `slot: left` and `slot: right`,
    so they qualified as card art; the walk takes the last match in sorted order; and `cutouts`
    sorts after `action_a`, `build_road` and `construct_building`. Five cards -- Taxation, both
    Build Roads, both Construct -- quietly drew a 68px emblem stretched across 590 x 295. The
    other five survived only because their folder names happen to sort after the letter c.

    THE LISTS ANSWER DIFFERENT QUESTIONS, which is the trap. markFolders is where a tile's MARK
    may come from; nonSlotFolders is which folders are not an ACTION. A folder can need to be in
    the second without being in the first, and that is exactly the case that was missed.

    So this derives the invariant instead of restating a list: every directory that exists under
    a duty is either one of that duty's action folders, or declared not to be one. Falsified by
    adding any folder under a duty without telling nonSlotFolders about it.
    """
    import json
    rec = json.loads((ROOT / "ui" / "board_v2" / "attribution.json").read_text(encoding="utf-8"))
    slot_folders = rec["slotFolders"]
    skip = set(gen.non_slot_folders())
    art_dir = ROOT / "ui" / "board_v2" / "duty_actions"

    stray = []
    for duty_dir in sorted(p for p in art_dir.iterdir() if p.is_dir()):
        mine = set((slot_folders.get(duty_dir.name) or {}).values())
        for sub in sorted(p for p in duty_dir.iterdir() if p.is_dir()):
            if sub.name in mine or sub.name in skip:
                continue
            stray.append("%s/%s" % (duty_dir.name, sub.name))
    assert not stray, (
        "these folders are under a duty and are neither one of its actions nor in "
        "nonSlotFolders, so the card walk will take them for artwork: %s" % sorted(set(stray)))


def test_a_card_is_drawn_from_its_own_slots_folder(gen):
    """The direct statement of what went wrong, asserted on the result rather than the rule.

    attribution.json's slotFolders says which folder holds each action's pictures. Whatever the
    walk does, the file it ends up inlining for a slot has to have come out of that folder --
    which is the one thing the five broken cards were not doing, while every list involved still
    looked correct on its own.

    Falsified by any folder that shadows a slot's own, whatever the reason.
    """
    import json
    rec = json.loads((ROOT / "ui" / "board_v2" / "attribution.json").read_text(encoding="utf-8"))
    slot_folders = rec["slotFolders"]
    _art, by_duty, _notes = gen.bundled_art()
    assert by_duty, "no card art was bundled at all"

    wrong = []
    for duty, slots in sorted(by_duty.items()):
        for slot, (_key, filename) in sorted(slots.items()):
            want = (slot_folders.get(duty) or {}).get(slot)
            if want is None:
                wrong.append("%s %s has art and no folder recorded for it" % (duty, slot))
                continue
            if not (ROOT / "ui" / "board_v2" / "duty_actions" / duty / want / filename).is_file():
                wrong.append("%s %s drew %s, which is not in %s/" % (duty, slot, filename, want))
    assert not wrong, "\n".join(wrong)


def test_every_cutout_still_comes_out_of_the_icon_it_says_it_came_from():
    """The committed cutouts are derived files, so the derivation has to still produce them.

    A derived file in a repository is a claim: run this script on that input and you get these
    bytes. Nothing was checking it. Change a threshold, change the cream, hand-edit one in an
    image editor, or regenerate against a newer icon, and the files and their records would drift
    apart silently -- and because the board does not draw them yet (markFolders lists seals and
    icons only), nothing would look wrong for as long as they sit unused. The day they are
    switched on is the worst possible day to find out.

    PIXELS, NOT BYTES, and deliberately. The obvious guard is a sha256 of a re-encode, and it
    would fail the first time CI's libwebp differed from the machine that wrote the file -- a red
    build that means nothing. What is actually being claimed survives the encoder: the alpha
    channel is carried losslessly by WebP, so it must match exactly, and the colour is a flat
    cream by construction, so it must be that cream everywhere the alpha shows anything.

    Falsified by changing LO, HI or CREAM in the script, or by editing any cutout.
    """
    import importlib.util
    import numpy as np
    from PIL import Image

    spec = importlib.util.spec_from_file_location(
        "_knockout", ROOT / "tools" / "duty_art" / "knockout_icons.py")
    knock = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = knock
    spec.loader.exec_module(knock)

    rec = json.loads((ROOT / "ui" / "board_v2" / "attribution.json").read_text(encoding="utf-8"))
    files = rec["files"]
    art = ROOT / "ui" / "board_v2" / "duty_actions"
    cutouts = sorted(art.glob("*/cutouts/*.webp"))
    assert cutouts, "there are no cutouts in this tree at all"

    for f in cutouts:
        rel = "duty_actions/%s" % f.relative_to(art).as_posix()
        assert rel in files, "%s has no attribution entry" % rel
        entry = files[rel]
        src = f.parent.parent / "icons" / entry["derivedFrom"]
        assert src.is_file(), "%s says it came from %s, which is not there" % (rel, src.name)

        made = knock.knockout(src)
        have = Image.open(f).convert("RGBA")
        assert made.size == have.size, "%s is %s and the derivation gives %s" % (
            f.name, have.size, made.size)

        a, b = np.asarray(made), np.asarray(have)
        # ALPHA EXACTLY, EVERYWHERE. It is the whole content of a cutout -- the emblem is a shape
        # cut in the alpha channel and the colour is a constant -- and lossless WebP carries it
        # bit for bit, so there is nothing to be approximate about.
        assert np.array_equal(a[:, :, 3], b[:, :, 3]), (
            "%s no longer has the alpha the knockout produces from %s" % (f.name, src.name))

        # AND THE COLOUR EXACTLY, WHERE ANY OF IT SHOWS. Not under the fully clear pixels: the
        # encoder drops their colour whatever `exact` is asked for, so the file comes back with
        # 246 where 248 was written in regions nothing draws. Asserting the whole array failed on
        # precisely those pixels, which is a true difference about a thing that cannot be seen.
        #
        # THIS HALF IS STRICT BECAUSE THE FILES ARE LOSSLESS, and they are lossless because the
        # loose version of this guard caught the reason: at quality 90 the cream was written 236
        # and read back 235, so "one flat colour" was not true of what was stored.
        shown = b[:, :, 3] > 0
        assert shown.any(), "%s is entirely transparent" % f.name
        assert np.array_equal(a[:, :, :3][shown], b[:, :, :3][shown]), (
            "%s is no longer the colour the knockout paints" % f.name)
        for i, want in enumerate(knock.CREAM):
            assert (b[:, :, i][shown] == want).all(), (
                "%s is not the flat cream the derivation paints" % f.name)


def test_a_cutouts_record_quotes_the_numbers_the_script_actually_uses():
    """Fourteen records restate the thresholds in prose; the script owns them.

    `modifications` says "alpha ramped from luminance 30 to 180" and names the cream, because a
    record that only said "knocked out" would describe nothing anyone could repeat. But that makes
    the record a second copy of three constants, and the copy cannot answer back: change LO in the
    script and fourteen entries quietly describe a derivation that no longer happened.

    Falsified by editing either side alone.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_knockout2", ROOT / "tools" / "duty_art" / "knockout_icons.py")
    knock = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = knock
    spec.loader.exec_module(knock)

    said_ramp = "luminance %d to %d" % (int(knock.LO), int(knock.HI))
    said_cream = "rgb(%d, %d, %d)" % knock.CREAM

    rec = json.loads((ROOT / "ui" / "board_v2" / "attribution.json").read_text(encoding="utf-8"))
    checked = 0
    for rel, entry in rec["files"].items():
        if "/cutouts/" not in rel:
            continue
        checked += 1
        mod = entry.get("modifications", "")
        assert said_ramp in mod, "%s does not quote the script's ramp (%s)" % (rel, said_ramp)
        assert said_cream in mod, "%s does not quote the script's cream (%s)" % (rel, said_cream)
    assert checked, "no cutout records to check"


def test_the_record_gates_the_art(gen, tmp_path, monkeypatch):
    """A picture with no attribution entry is left out and NAMED, never guessed into place.

    That is the rule this tree runs on -- it does not ship a picture nobody can say where it
    came from -- and it is also what lets the twelve empty slots be filled without this tool.
    Falsified by falling back to the filename when the record is missing.
    """
    art = tmp_path / "duty_actions" / "clerical" / "gain_piety"
    art.mkdir(parents=True)
    from PIL import Image
    Image.new("RGB", (40, 20), (9, 9, 9)).save(art / "clerical_gain_piety_left_v09.png")
    monkeypatch.setattr(gen, "ART_DIR", tmp_path / "duty_actions")
    monkeypatch.setattr(gen, "ATTRIB_FILE", tmp_path / "attribution.json")
    images, by_duty, notes = gen.bundled_art()
    assert by_duty == {}, "an unrecorded picture was placed anyway"
    assert any("no slot recorded" in n for n in notes), notes


# =================================================================================================
# HOVER
#
# This one is a scar. Hover was an enter/leave pair on each element and it had a hole on exactly
# one path -- tile, then its seal, then back to the same tile -- which left the board with nothing
# hovered while the pointer was still sitting on the tile. mouseenter and mouseleave deliberately
# do not fire between a parent and its own child, so going into the seal never left the tile, and
# coming back out of it fired the seal's leave with no matching enter behind it.
#
# The fix was not to patch that path. It was to stop keeping hover state in a history of arrivals
# and departures, because the same hole exists in every other nesting -- a caption inside a card,
# anything ever put inside a tile. mouseover bubbles and fires on every crossing, so the state is
# recomputed from where the pointer is.

def test_hover_is_delegated_rather_than_a_pair_on_every_element():
    """Falsified by adding a mouseenter listener back: that is the shape the bug had."""
    page = TMPL.read_text(encoding="utf-8")
    code = re.sub(r"(?m)^\s*//.*$", "", page)       # the notes above quite properly name the events
    assert 'addEventListener("mouseenter"' not in code, (
        "a mouseenter listener is back, and hover state is a history again")
    assert 'board.addEventListener("mouseover"' in code, (
        "the one delegated hover listener is gone")


def test_everything_hoverable_says_so_in_markup_rather_than_in_a_list():
    """The delegated listener finds the nearest ancestor carrying data-hover-duty or
    data-hover-slot. A list of selectors kept beside it would be a second place to update the
    first time something new became hoverable. Falsified by adding a hoverable element that
    carries neither attribute -- it simply would not light, silently."""
    page = TMPL.read_text(encoding="utf-8")
    for owner in ("tile.dataset.hoverDuty", "seal.dataset.hoverDuty",
                  "art.dataset.hoverSlot", '"data-hover-duty"'):
        assert owner in page, "%s no longer opts in to hover" % owner
    assert "querySelectorAll" not in page.split("function hoverDataOf")[1].split("}")[0], (
        "the hover lookup has grown a selector list")


def test_no_duty_calls_both_of_its_actions_the_same_thing(gen):
    """Two actions with one name is a hole, not a style, and it cost real time.

    Construct's pair were both called "Construct" for as long as nothing had to tell them apart.
    Then two icons arrived named for them and the wording could not say which was which: the slot
    had to be worked out from attribution.json's `slotFolders` instead, and a wrong guess there
    would have put the mason's building on the road action with nothing to notice it. The board
    draws these names side by side on the two action cards, so a duty with one name twice is also
    a board that cannot be read.

    Falsified by giving any duty's two actions the same name again.
    """
    text = gen.duty_text()
    same = []
    for slug, said in sorted(text.items()):
        names = [said[s]["name"] for s in ("actionA", "actionB")
                 if said.get(s) and said[s].get("name")]
        if len(names) == 2 and names[0].strip().lower() == names[1].strip().lower():
            same.append("%s calls both of its actions %r" % (slug, names[0]))
    assert not same, "\n".join(same)


def test_the_map_covers_every_action_the_wording_says_exists(gen):
    """attribution.json's `slotFolders` and duty_text.json have to agree about the board.

    They did not: the tree carried taxation/action_b and allocation/special_activity, left over
    from before the wording existed, so three duties had more folders than actions. Falsified by
    adding an action to duty_text.json without giving it a folder, or the other way round.
    """
    import json as _json
    doc = _json.loads(gen.ATTRIB_FILE.read_text(encoding="utf-8"))
    folders = doc.get("slotFolders")
    assert folders, "attribution.json has no slotFolders"
    text = gen.duty_text()
    for slug, _name, _deg in _load("geometry").DUTIES:
        want = [s for s in ("actionA", "actionB") if text[slug].get(s) is not None]
        assert sorted(folders.get(slug, {})) == sorted(want), (
            "%s has folders for %s and wording for %s"
            % (slug, sorted(folders.get(slug, {})), sorted(want)))
        for slot, name in folders[slug].items():
            assert (gen.ART_DIR / slug / name).is_dir(), (
                "%s %s is mapped to %s/%s, which does not exist" % (slug, slot, slug, name))


def test_the_map_is_what_answers_a_slot_that_has_no_picture_yet(gen):
    """Twelve of the fourteen slots are empty, so the map is the only thing that can answer.

    Falsified by deleting an entry: the save then refuses rather than guessing, which the next
    test covers.
    """
    assert gen.slot_folder("produce", "actionA") == "gain_wheat"
    assert gen.slot_folder("give_alms", "actionB") == "donate_building"
    # and where a picture HAS landed, the file's own record agrees with the map
    assert gen.slot_folder("clerical", "actionA") == "gain_piety"
    assert gen.slot_folder("ordination", "actionB") == "send_on_mission"


def test_a_slot_with_no_record_is_asked_which_folder_rather_than_guessed(gen, tmp_path,
                                                                        monkeypatch):
    """This tree already has a folder for every slot, and the names are not derivable.

    Clerical's actionA is `gain_piety` and its actionB `gain_coins`; Produce's actionA is
    `gain_wheat` and its actionB `gain_stone`. Neither alphabetical nor the action's own name
    gives that, so a guess puts a second folder beside the empty one the tree already made.
    Falsified by inventing a name from the action's title, which is what this did first.
    """
    art = tmp_path / "duty_actions" / "produce"
    (art / "gain_wheat").mkdir(parents=True)
    (art / "gain_stone").mkdir()
    (art / "masters").mkdir()
    monkeypatch.setattr(gen, "ART_DIR", tmp_path / "duty_actions")
    monkeypatch.setattr(gen, "ATTRIB_FILE", tmp_path / "attribution.json")
    assert gen.empty_folders("produce") == ["gain_stone", "gain_wheat"]
    img = {"kind": "art", "duty": "produce", "slot": "actionA", "filename": "w.png",
           "bytes": "data:image/png;base64,aGk="}
    with pytest.raises(ValueError) as e:
        gen.save({"images": [img]})
    assert "gain_wheat" in str(e.value) and "gain_stone" in str(e.value), str(e.value)
    gen.save({"images": [dict(img, folder="gain_wheat")]})
    assert (art / "gain_wheat" / "produce_gain_wheat_left_v01.png").is_file()
    assert not (art / "produce_wheat").exists(), "a folder was invented anyway"


# =================================================================================================
# THE SEALS IN THE TILE
#
# Two marks do not fit side by side in a tile 154 wide, so they stack: centred, each one inset
# from whatever is above it, and the ribbon's height is what buys the room. It was a diagonal,
# which took its separation from the tile's WIDTH and so could not go past 78 -- at 100 the pair
# overlapped by 47.5px and no ribbon height could have helped. Every one of these numbers derives
# from the others, and a mark nudged by hand would break the derivation silently: the picture
# would still draw, just in the wrong place, on eight tiles at once.

def test_two_seals_do_not_fit_in_a_row_which_is_why_they_are_a_column(geo):
    """The reason for the column, asserted rather than left in a comment.

    It was a diagonal, which bought its separation out of the tile's WIDTH and so had a ceiling
    the ribbon could not raise: at SEAL 100 the pair overlapped by 47.5px. A column buys it out of
    the ribbon's HEIGHT, which is a number that can be moved.

    THE ORIGINAL FALSIFICATION HAS NOW FIRED, AND THE REASON HAS MOVED RATHER THAN GONE. This read
    "falsified by shrinking SEAL until a row fits across the tile -- at which point this test says
    so and the marks should go back in a row, because stacking would then be costing ribbon height
    for nothing". The mark is 50 now: 2 x 50 + 16 is 116 against 140 of room, so a row DOES fit,
    and the test said so.

    What it was guarding was the COST, not the arrangement: a column was worth having only while
    the ribbon's height was being spent to get it. It is not being spent. RIBBON_H is held at 186
    -- a deliberate choice, so the tiles did not change height when the marks shrank -- and a
    stacked pair needs only SNUG_RIBBON_H. The column is drawn in height the tile already has.
    So stacking now costs nothing and the original argument has no force either way.

    FALSIFIED NOW BY TAKING THAT SPARE AWAY: shrink RIBBON_H to what a stacked pair actually needs
    and the column starts costing height again, with a row sitting there that fits. Then this test
    fails and the question is live once more. Whether a row LOOKS better in a tile this tall is a
    judgement and is not asserted here -- nothing in the drawings can settle it.
    """
    fits = 2 * geo.SEAL + geo.GAP <= geo.TILE_INNER_W - 2 * geo.SEAL_INSET
    assert not fits or geo.RIBBON_H > geo.SNUG_RIBBON_H, (
        "a row of two marks fits across the tile (%d of %d) AND the ribbon is down to the %d a "
        "column needs, so the column is now buying its height out of the tile for nothing"
        % (2 * geo.SEAL + geo.GAP, geo.TILE_INNER_W - 2 * geo.SEAL_INSET, geo.SNUG_RIBBON_H))
    a, b = geo.seal_slots(2)
    assert b["x"] == a["x"], "the two marks are not in one column"
    assert b["y"] == a["y"] + geo.SEAL + geo.SEAL_INSET, (
        "the second mark is not one inset below the first")


def test_a_seal_stays_inside_the_tile_drawn_round_it(geo):
    """Falsified by raising SEAL or shrinking the tile: check() names which seal left the box.

    IT USED TO SAY "AND CLEAR OF THE DUTY NAME", and the name is what has gone. The tile had a
    line of type across the top and a mark had to start below where it ended; the tile is the
    pair and the air round it now, so the only thing a mark has to be clear of is the box's own
    edge -- which is TILE_PAD away by construction and asserted anyway, because construction is
    two expressions agreeing and not one fact.
    """
    assert geo.check() == [], "\n".join(geo.check())
    for n in (1, 2):
        for s in geo.seal_slots(n):
            assert s["y"] >= geo.SEAL_INSET
            assert 0 <= s["x"] and s["x"] + s["size"] <= geo.TILE_INNER_W
            assert s["y"] + s["size"] <= geo.TILE_INNER_H


def test_a_one_action_duty_gets_one_centred_seal_and_not_an_empty_slot(geo):
    """Taxation and Allocation have one action each and duty_text.json is what says so.

    A second slot left empty beside the first is a hole nobody can fill. Falsified by returning
    two positions for n == 1.
    """
    one = geo.seal_slots(1)
    assert len(one) == 1
    left = one[0]["x"]
    right = geo.TILE_INNER_W - left - geo.SEAL
    assert abs(left - right) <= 1, (
        "the single seal leaves %d one side and %d the other" % (left, right))


def test_the_top_seal_clears_the_name_as_far_as_the_lower_one_clears_the_edge(geo):
    """The pair sat high and lopsided: flush under the line of type, with a margin below it.

    Falsified by starting the top seal at TILE_NAME_BOTTOM again, which is where it began.
    MEASURED INSIDE THE BORDER, because that is where a child of the tile is placed -- the tile
    is a border-box and TILE_W and RIBBON_H are its outer size.

    EQUAL AIR, NOT ONE INSET. It WAS one inset top and bottom, and that was the same claim while
    the tile was exactly as tall as the pair asked for: nothing was left over, so centring the
    pair and hanging it from the name put it in the same place. The tile keeps its height now and
    the mark is 50, so there are 56 spare -- and the two rules have come apart. Hanging gives all
    56 to the bottom; this asserts the half-and-half. What it must never be is NO air, which is
    where it began.
    """
    a, b = geo.seal_slots(2)
    above = a["y"]
    below = geo.TILE_INNER_H - (b["y"] + geo.SEAL)
    assert above == below, "%d above the top seal and %d below the lower one" % (above, below)
    assert above >= geo.SEAL_INSET, (
        "%d above the top seal, which is tighter than the tile's own inset of %d"
        % (above, geo.SEAL_INSET))
    # AND IT IS THE ROOM THAT SAYS HOW MUCH, not a number typed here. Asked of the tile the same
    # way seal_slots() asks it, so a change to the tile's height or the mark's size moves both.
    room = geo.TILE_INNER_H
    assert above == (room - (2 * geo.SEAL + geo.SEAL_INSET)) // 2, (
        "the pair is not centred in the %d of room the tile gives it" % room)
    # ACROSS, THEY ARE CENTRED, NOT INSET. On the diagonal one mark was pushed to each side and the
    # side margin WAS the inset; in a column both sit in the middle of the tile and what is left at
    # the sides is whatever the tile is wider than the mark. Equal is the claim, not equal to six.
    left = a["x"]
    right = geo.TILE_INNER_W - (b["x"] + geo.SEAL)
    assert left == right, "%d one side and %d the other" % (left, right)
    assert left == (geo.TILE_INNER_W - geo.SEAL) // 2, "the marks are not centred in the tile"


# =================================================================================================
# ONE SOLID FRACTION, AND WHY IT IS A TEST RATHER THAN A README
#
# Three sets of discs have now arrived at three different sizes inside their own squares: the
# coins at 0.906, 0.847 and 0.802, the grey resource seals at 0.919, 0.915 and 0.875, the red
# action seals at 0.939 and 0.959. Each set was corrected by hand and each correction was written
# down in prose, and prose is not what the next set will be measured against. A seal and a coin
# are meant to be interchangeable in one slot at one size; nothing in the drawings enforces that.

def gen_suffixes():
    """The extensions this tree's images may carry, from the one place that says so."""
    return _load("generate_action_board").image_suffixes()


def _solid_fraction(path):
    from PIL import Image
    import numpy as np
    a = np.array(Image.open(path).convert("RGBA"))[:, :, 3]
    rows = np.where(a.max(axis=1) > 8)[0]
    cols = np.where(a.max(axis=0) > 8)[0]
    if not len(rows) or not len(cols):
        return 0.0
    w, _h = Image.open(path).size
    return max(rows[-1] - rows[0] + 1, cols[-1] - cols[0] + 1) / w


def _marks():
    """Every seal and token the board can draw, split into the two kinds it now has.

    A DISC brings its own ground and fills 0.906 of its square. A PLATE is an emblem drawn on
    transparency, which brings no ground and is trimmed to fill its square outright.

    WHICH A FILE IS COMES FROM THE RECORD, read through the generator's own `ground_of`, so the
    split here and the ground the board draws can never disagree about one picture. It is not
    read off the pixels, and the two tests below are why it must not be: they measure the
    silhouette, and a split that measured the silhouette too would be agreeing with itself.
    """
    gen = _load("generate_action_board")
    board = ROOT / "ui" / "board_v2"
    rec = json.loads((board / "attribution.json").read_text(encoding="utf-8")).get("files", {})
    want = set(gen_suffixes())
    # EVERY MARK FOLDER, ASKED FOR BY NAME. This used to glob `duty_actions/*/seals/*`, and the
    # day the two cut-outs moved into `icons/` it quietly matched nothing -- so the plate test
    # below found no plates and skipped, passing a run in which nothing was measured. A test that
    # can go quiet when the tree moves underneath it is worse than no test.
    folders = gen.mark_folders()
    files = sorted(p for p in board.glob("tokens/resources/*") if p.suffix.lower() in want)
    for sub_dir in folders:
        files += sorted(p for p in board.glob("duty_actions/*/%s/*" % sub_dir)
                        if p.parent.name == sub_dir and p.suffix.lower() in want)
    files.sort()
    discs, plates = [], []
    for p in files:
        rel = p.relative_to(board).as_posix()
        side = plates if gen.ground_of(rel, rec.get(rel, {})) == "board" else discs
        side.append(p)
    return discs, plates


def test_every_disc_the_board_draws_fills_the_same_fraction_of_its_square(geo):
    """Falsified by dropping in a new seal or coin straight from the generator.

    MASTERS ARE EXCLUDED ON PURPOSE. They are the untouched originals, kept so each correction
    stays reversible, so a master that measured 0.906 would mean the correction was never made.

    PLATES ARE EXCLUDED TOO, and that exclusion is the newer thing. 0.906 is a fact about a wax
    disc: it leaves a margin so a round drawing does not touch the edges of a square slot. An
    emblem on transparency has no disc and no margin to leave -- it is trimmed to its own mark and
    fills the square, and holding it to 0.906 would be holding it to somebody else's shape. The
    test below keeps it honest instead.
    """
    pytest.importorskip("numpy")
    pytest.importorskip("PIL")
    discs, _plates = _marks()
    if not discs:
        pytest.skip("this tree has no discs in it")
    board = ROOT / "ui" / "board_v2"
    bad = []
    for p in discs:
        f = _solid_fraction(p)
        if abs(f - geo.SOLID_FRACTION) > geo.SOLID_TOLERANCE:
            bad.append("%s is %.3f of its square and the board's discs are %.3f"
                       % (p.relative_to(board).as_posix(), f, geo.SOLID_FRACTION))
    assert not bad, "\n".join(bad)


def test_no_mark_on_a_tile_is_given_a_ground(gen):
    """The rule this replaces, and why it went.

    A mark recorded `ground: board` is a cut-out: it carries no ground of its own, so the board
    used to paint one behind it -- and that is why the old guard here required such a mark to fill
    at least 0.98 of its square. A plate behind a trimmed drawing shows as a dark rectangle with
    the emblem floating inside it, which is worse than no plate at all.

    THE PLATE IS NOT PAINTED ANY MORE. The marks are cut-outs on a tile that is glass over a
    landscape, and a ground behind one would be the only square left on it. So the requirement
    that a cut-out fill its square goes too -- it existed only to make the plate safe -- and in
    its place this asserts the thing that now has to stay true: nothing paints a ground.

    THE RECORD STILL SAYS WHICH IS WHICH, and that is deliberate. `ground` is a fact about the
    artwork, not about today's styling; the rule is kept and emptied so there is one place to put
    a ground back if a mark ever needs one.

    Falsified by giving .seal.plate a colour again.
    """
    page = TMPL.read_text(encoding="utf-8")
    css = re.sub(r"/\*.*?\*/", " ", page, flags=re.S)
    m = re.search(r"\.seal\.plate\{([^}]*)\}", css)
    assert m, ".seal.plate is gone entirely -- the record's `ground` now reaches nothing"
    body = m.group(1).replace(" ", "")
    assert "background:none" in body or "background:transparent" in body, (
        "a mark is being given a ground again: %s" % m.group(1).strip())
    assert "var(--plate)" not in body, (
        "the plate colour is back behind the marks: %s" % m.group(1).strip())
    # AND THE RECORDS STILL CARRY THE WORD, so the distinction survives the styling change.
    rec = json.loads((ROOT / "ui" / "board_v2" / "attribution.json").read_text(encoding="utf-8"))
    grounds = {e.get("ground") for k, e in rec["files"].items() if "/cutouts/" in k}
    assert grounds == {"board"}, (
        "the cut-outs no longer record what ground they need: %s" % sorted(grounds))


def test_the_mark_the_board_draws_is_the_one_the_record_points_at(gen):
    """Falsified by sorting filenames, or by comparing versions across folders.

    TWO RULES, NOT ONE, and getting that wrong has now cost two builds. Inside one folder a name
    sorts the way a version does, so `sorted(...)[-1]` was right for as long as every mark lived
    in `seals`; `..._icon_v04` sorts before `..._seal_v03` on the letter i, so that broke first.
    The fix -- highest version anywhere -- then broke the other way, because a version counts up
    inside one lineage and means nothing across two: a new icon at v01 lost to a wax disc at v02
    on eleven slots at once. What decides is the ORDER of markFolders, last wins; the version only
    settles ties inside one folder.
    """
    rec = json.loads(gen.ATTRIB_FILE.read_text(encoding="utf-8"))["files"]
    order = {name: i for i, name in enumerate(gen.mark_folders())}
    best = {}
    for path, e in rec.items():
        if not path.startswith("duty_actions/"):
            continue
        rel = path[len("duty_actions/"):]
        parts = rel.split("/")
        if len(parts) < 3 or parts[1] not in order or "masters" in parts:
            continue
        side = gen.slot_of(rel, e)
        if side not in ("left", "right"):
            continue
        key = (parts[0], {"left": "actionA", "right": "actionB"}[side])
        rank = (order[parts[1]], gen.version_of(pathlib.Path(parts[-1])))
        if key not in best or rank > best[key][0]:
            best[key] = (rank, parts[-1])

    _images, by_duty, _notes = gen.bundled_seals()
    drawn = {(slug, slot): w[1] for slug, slots in by_duty.items() for slot, w in slots.items()}
    assert drawn, "the board bundled no marks at all"
    wrong = ["%s %s: the board draws %s and the record points at %s"
             % (d, s, drawn[(d, s)], best[(d, s)][1])
             for (d, s) in drawn if (d, s) in best and drawn[(d, s)] != best[(d, s)][1]]
    assert not wrong, "\n".join(wrong)


def test_a_newer_kind_of_mark_beats_an_older_one_whatever_the_numbers_say(gen, tmp_path,
                                                                          monkeypatch):
    """A version counts up inside one lineage and means nothing across two.

    This is the bug that shipped for one build. The rule was "highest version wins", which is
    right inside `seals` and nonsense between `seals` and `icons`: a brand new icon arrives at
    v01 and loses to a wax disc on its second generation. Eleven slots went on drawing seals with
    their icons filed right beside them, and the board looked entirely normal.

    Falsified by comparing versions across folders again, or by reversing the precedence. The
    order in attribution.json's `markFolders` is what decides, last wins, and the version only
    settles ties inside one folder.
    """
    art = tmp_path / "duty_actions"
    for duty in ("clerical", "produce"):
        (art / duty / "seals").mkdir(parents=True)
        (art / duty / "icons").mkdir(parents=True)
    # An old seal on its SECOND version against a new icon on its FIRST.
    (art / "clerical" / "seals" / "clerical_actionA_seal_v02.png").write_bytes(b"x")
    (art / "clerical" / "icons" / "clerical_actionA_icon_v01.png").write_bytes(b"x")
    # And a slot with no icon at all, which must stay on its seal.
    (art / "produce" / "seals" / "produce_actionA_seal_v03.png").write_bytes(b"x")
    attrib = tmp_path / "attribution.json"
    attrib.write_text(json.dumps({
        "markFolders": ["seals", "icons"],
        "nonSlotFolders": ["masters", "seals", "icons"],
        "imageSuffixes": [".png", ".webp"],
        "files": {
            "duty_actions/clerical/seals/clerical_actionA_seal_v02.png": {"slot": "left"},
            "duty_actions/clerical/icons/clerical_actionA_icon_v01.png": {"slot": "left",
                                                                         "ground": "board"},
            "duty_actions/produce/seals/produce_actionA_seal_v03.png": {"slot": "left"},
        }}), encoding="utf-8")
    monkeypatch.setattr(gen, "ART_DIR", art)
    monkeypatch.setattr(gen, "ATTRIB_FILE", attrib)
    monkeypatch.setattr(gen, "_inline", lambda *a, **k: "data:,")

    _images, by_duty, _notes = gen.bundled_seals()
    assert by_duty["clerical"]["actionA"][1] == "clerical_actionA_icon_v01.png", \
        "the board drew %s" % by_duty["clerical"]["actionA"][1]
    assert by_duty["clerical"]["actionA"][2] == "board", "and it drew it with no ground"
    assert by_duty["produce"]["actionA"][1] == "produce_actionA_seal_v03.png", \
        "a slot with no icon must keep its seal"
    # A save for that slot follows the same precedence, so it lands beside the mark in play.
    assert gen.mark_subdir("clerical", "actionA") == "icons"
    assert gen.mark_subdir("produce", "actionA") == "seals"


def test_a_slot_that_has_an_icon_is_drawn_with_the_icon(gen):
    """What the precedence is FOR, asserted as the outcome rather than as the mechanism.

    The test above derives its expectation from markFolders, so it moves whenever that list
    moves -- reverse the list and it still passes while the board quietly goes back to wax. This
    one says the thing the list exists to achieve, with the ladder written out HERE rather than
    read off the list: where a slot has more than one kind filed, this is the one the board draws.

    THE LADDER MOVED ONE RUNG, ON PURPOSE, WHICH IS WHAT THIS TEST IS FOR. It used to end at the
    icon; it now ends at the cutout -- the same emblem with its painted black field taken off, so
    it sits on whatever is behind it instead of carrying a square of its own. Fourteen fields were
    fourteen different shapes, which read as fourteen accidents rather than one set.

    So when the direction changes again, THIS is the line you edit, deliberately, rather than
    finding out on the board that a folder sorted later than you expected.
    """
    rec = json.loads(gen.ATTRIB_FILE.read_text(encoding="utf-8"))["files"]
    kinds = {}
    for path, e in rec.items():
        if not path.startswith("duty_actions/"):
            continue
        parts = path[len("duty_actions/"):].split("/")
        if len(parts) < 3 or "masters" in parts:
            continue
        if gen.slot_of(path[len("duty_actions/"):], e) not in ("left", "right"):
            continue
        side = gen.slot_of(path[len("duty_actions/"):], e)
        kinds.setdefault((parts[0], {"left": "actionA", "right": "actionB"}[side]),
                         set()).add(parts[1])

    # THE LADDER, BEST LAST, AND THE INFIX THE FILENAME CARRIES FOR EACH RUNG. Written here and
    # nowhere else in this test, so changing the direction is one line.
    LADDER = (("seals", "_seal_"), ("icons", "_icon_"), ("cutouts", "_cutout_"))

    _images, by_duty, _notes = gen.bundled_seals()
    wrong = []
    tested = 0
    for (duty, slot), have in sorted(kinds.items()):
        rungs = [r for r in LADDER if r[0] in have]
        if len(rungs) < 2:
            continue                      # nothing filed to choose between, so nothing to claim
        tested += 1
        folder, infix = rungs[-1]
        drawn = by_duty.get(duty, {}).get(slot)
        if not drawn or infix not in drawn[1]:
            wrong.append("%s %s has a %s filed and the board draws %s"
                         % (duty, slot, folder.rstrip("s"), drawn[1] if drawn else "nothing"))
    assert tested, "no slot has two kinds filed, so this is not yet testing anything"
    assert not wrong, "\n".join(wrong)


def test_the_board_gives_a_plate_the_ground_it_does_not_carry(gen):
    """A cut-out has no ground of its own, so the page has to supply one.

    Falsified by dropping the class, or by dropping the field the generator sends with each
    seal. Both leave an emblem floating on the tile's black with nothing behind it.

    THE NAME IS CHECKED, NOT JUST THE SHAPE. The first version of this read the ground off a
    three-element list as `info[slot][2]`, and the page's duty entries are objects with names --
    so it was reading `undefined`, the class never went on, the test passed, and the board drew
    the emblems on black. A field asked for by name either exists or does not.
    """
    page = TMPL.read_text(encoding="utf-8")
    built = gen.build()[0]
    assert '"sealGround"' in built, "the built page carries no ground for any seal"
    assert ".seal.plate{" in page, "there is no ground rule for a cut-out seal"
    assert 'seal.classList.add("plate")' in page, "nothing ever applies it"
    assert 'sealGround === "board"' in page, "the page is not reading the recorded ground"


def test_a_ground_the_record_does_not_know_stops_the_build(gen):
    """A mistyped ground is the one failure that would not announce itself.

    `own` and `board` are the two answers. Anything else -- `Board`, `none`, `transparent` --
    would quietly fall back to `own` under a plain `.get`, and the only symptom would be an
    emblem floating on the tile with nothing behind it, which is a thing you have to notice by
    eye. Falsified by giving `ground_of` a default instead of a refusal.
    """
    assert gen.ground_of("a file", {}) == "own", "an unrecorded mark carries its own ground"
    assert gen.ground_of("a file", {"ground": "board"}) == "board"
    with pytest.raises(SystemExit) as e:
        gen.ground_of("duty_actions/x/seals/y.png", {"ground": "Board"})
    assert "duty_actions/x/seals/y.png" in str(e.value), "the refusal does not name the file"


def test_the_record_gates_the_seal_the_same_way_it_gates_the_art(gen, tmp_path, monkeypatch):
    """Falsified by walking the seals folder and trusting the filename."""
    from PIL import Image
    d = tmp_path / "duty_actions" / "clerical" / gen.MARK_SUBDIR
    d.mkdir(parents=True)
    Image.new("RGBA", (40, 40), (9, 9, 9, 255)).save(d / "clerical_actionA_seal_v01.png")
    monkeypatch.setattr(gen, "ART_DIR", tmp_path / "duty_actions")
    monkeypatch.setattr(gen, "ATTRIB_FILE", tmp_path / "attribution.json")
    images, by_duty, notes = gen.bundled_seals()
    assert by_duty == {}, "an unrecorded seal was drawn anyway"
    assert any("no slot recorded" in n for n in notes), notes


def test_a_seal_is_never_mistaken_for_the_card_art(gen, tmp_path, monkeypatch):
    """The seals live under the duty's own folder, which bundled_art walks recursively.

    Without the skip, a seal recorded as `left` would be inlined as the left CARD -- a 78px wax
    seal stretched across 590 x 295. Falsified by removing the mark-folder skip in bundled_art.
    """
    from PIL import Image
    duty = tmp_path / "duty_actions" / "clerical"
    (duty / gen.MARK_SUBDIR).mkdir(parents=True)
    Image.new("RGBA", (40, 40), (9, 9, 9, 255)).save(
        duty / gen.MARK_SUBDIR / "clerical_actionA_seal_v01.png")
    attrib = tmp_path / "attribution.json"
    attrib.write_text(json.dumps({"files": {
        "duty_actions/clerical/%s/clerical_actionA_seal_v01.png" % gen.MARK_SUBDIR:
            {"slot": "left"}}}), encoding="utf-8")
    monkeypatch.setattr(gen, "ART_DIR", tmp_path / "duty_actions")
    monkeypatch.setattr(gen, "ATTRIB_FILE", attrib)
    _images, by_duty, _notes = gen.bundled_art()
    assert by_duty == {}, "a seal was built in as card art"
    _si, seal_by_duty, _sn = gen.bundled_seals()
    assert seal_by_duty["clerical"]["actionA"][0] == "seal:clerical:actionA"


def test_a_container_stops_drawing_once_a_picture_lands_in_it():
    """The wax seals have a scalloped rim; a circular background behind one shows through it.

    The Tithe tokens had exactly this and it showed as a double rim. The class is `filled` and
    NOT `art`, because `.art` is the big card's own rule -- a token marked `.art` was picking up
    `background:#000` and only looked right by specificity. Falsified by reusing `art`.

    ONE CONTAINER LEFT WHERE THERE WERE TWO. `.tok` was the Tithe's three resources and it is
    gone with them; the fault is not, because the duty marks are still pictures in containers
    that would draw behind them. What this test loses is a second witness to the same rule, so
    the remaining one carries it -- and `.tok` is named in the sweep below, so the rule cannot
    come back half-applied under its old name.
    """
    page = TMPL.read_text(encoding="utf-8")
    css = re.sub(r"/\*.*?\*/", " ", page, flags=re.S)
    assert ".seal.filled{" in css, (
        ".seal.filled is gone, so that container draws behind its own artwork")
    assert ".tok" not in css, (
        "the Tithe's token container is back in the stylesheet with nothing drawing it")
    code = re.sub(r"(?m)^\s*//.*$", "", page)
    assert 'classList.add("art")' not in code, (
        "a small container is marked `art` again, which is the big card's class")


def test_the_tile_prints_no_name_and_takes_its_corner_from_geometry():
    """What the tile became when the duty names came off it, asserted at both ends.

    THE NAME WAS A LINE OF TYPE ACROSS THE TOP and geometry measured the marks from where it
    ended. It is off the board. A page that printed it again would not fail anything else here --
    the marks are placed from seal_slots() and would simply be drawn over the top of it -- so
    this is the only thing standing between "removed" and "removed until somebody puts it back".

    AND IT IS NOT GONE WITHOUT TRACE. Eight unlabelled boxes are unreadable until the landscape
    behind them carries the identification, so the name is the tile's title: invisible, costs
    nothing, and answers the question by pointing.

    THE CORNER IS GEOMETRY'S, which is the same argument the frame lost and won. The old tile wore
    a flat 4px and the stylesheet could own that, because 4 at 154 wide and 4 at 74 wide are both
    "slightly softened". This corner is 0.12 OF THE BOX, so a number typed into the CSS is the
    box's shape stated twice and stops following the box the moment the box moves.

    Falsified by printing the name, by dropping the title, or by typing a radius into the page.
    """
    page = TMPL.read_text(encoding="utf-8")
    code = re.sub(r"/\*.*?\*/", " ", page, flags=re.S)
    code = re.sub(r"<!--.*?-->", " ", code, flags=re.S)
    code = re.sub(r"(?m)^\s*//.*$", " ", code)
    body = code.split("function drawTiles()")[1].split("\nfunction ")[0]

    # NOTHING IN THE TILE IS GIVEN TEXT AT ALL. The first version of this read assignments of the
    # form `name.textContent = ...`, which a mutation walked straight through by writing
    # `el("div", "nm", tile).textContent = d.name` -- the character before `.textContent` is a
    # bracket, not a word character, and the pattern wanted a name there. The claim does not need
    # to know what is being assigned to: the tile draws pictures, so any text in it is the thing
    # that was removed coming back.
    assert "textContent" not in body, (
        "the tile writes text into itself again: %s"
        % re.findall(r".{0,60}textContent.{0,40}", body))
    # AND THE NAME IS USED ONCE, FOR THE TITLE AND NOTHING ELSE.
    rest = body.replace("tile.title = d.name;", " ")
    assert "d.name" not in rest, (
        "the duty's name is read somewhere other than the title: %s"
        % re.findall(r".{0,60}d\.name.{0,30}", rest))
    # THE TILE'S OWN .nm RULE, NOT EVERY .nm ON THE PAGE. The action CARD still prints its
    # action's name across the top and `.art .nm` is that rule -- banning the class outright
    # would be banning the card's caption, which is a different thing that did not change.
    assert not re.search(r"\.tile\s+\.nm\b", code), (
        "the duty name's own rule is back in the stylesheet, so something is meant to print it")
    assert re.search(r"tile\.title\s*=\s*d\.name", body), (
        "the tile no longer carries the duty's name at all, so eight boxes say nothing")

    # AND THE CORNER COMES FROM GEOMETRY, read off the assignment so a literal cannot hide in it.
    corner = re.search(r"tile\.style\.borderRadius\s*=\s*([^;]+);", body)
    assert corner, "nothing sets the tile's corner, so it falls back to the stylesheet's"
    assert "GEO.ribbon.radius" in corner.group(1), (
        "the tile's corner is typed into the page: %s" % corner.group(1).strip())
    # AND THE STYLESHEET DOES NOT STATE ONE FOR IT EITHER, or the two disagree the first time
    # either moves and whichever wins is an accident of specificity.
    assert not re.search(r"\.tile\{[^}]*border-radius", code), (
        "the .tile rule carries a radius of its own beside the one geometry sets")


def test_a_mark_on_a_tile_has_no_edge_and_is_lit_like_a_control(gen):
    """The dashed edge is gone, and what replaced it has to be the controls' rule, not a new one.

    The edge did two jobs: it drew the SLOT a mark sits in, and it carried both states -- dashed
    at rest, solid under the pointer and when chosen. With cut-outs on a tile that is glass over a
    landscape there is no slot to draw, so the edge went; and that left the states with nothing to
    say them.

    BRIGHTNESS, AND THE SAME NUMBERS THE CONTROLS USE. The three marks in the controls column
    already answer the pointer this way. A second way of saying "this one" would be two
    vocabularies for one idea on a board where a tile mark and a control are now the same size and
    the same artwork.

    Falsified by giving the marks an edge again, or by lighting them to a different amount than
    the column does.
    """
    page = TMPL.read_text(encoding="utf-8")

    def decls(sel):
        return decls_for(page, sel)

    rest = decls(".seal.filled")
    assert re.search(r"border:\s*0", rest), "a tile mark has an edge again: %s" % rest.strip()

    def lit(sel):
        d = decls(sel)
        f = re.search(r"brightness\(([\d.]+)\)", d)
        assert f, "%s does not light anything: %s" % (sel, d.strip())
        return float(f.group(1))

    # THE SAME AMOUNT IN BOTH PLACES, read off both rather than written here.
    assert lit(".seal.filled") == lit(".mark"), "a mark rests at a different level to a control"
    assert lit(".seal.filled:hover, .seal.filled.on") == lit(".mark:hover"), (
        "a mark lights to a different level than a control does")
    assert lit(".seal.filled:hover, .seal.filled.on") > lit(".seal.filled"), (
        "lighting a mark does not make it brighter")


def test_the_backdrop_is_stretched_to_its_rect_and_the_strip_stops_covering_it(geo):
    """A picture behind two things that cover it, which is a shape nothing else here has.

    STRETCHED, NOT COVERED. The crop was anchored so its painted ground falls exactly where the
    road strip falls -- 83.6% against 83.5%, which is 0.3 px at this size. `cover` preserves the
    picture's aspect and slides that alignment off by however much 5.554:1 and the file's own
    ratio disagree, and it would do it silently, because a backdrop that is merely in the wrong
    place still looks like a backdrop.

    AND THE STRIP HAS TO STOP PAINTING ITSELF. #road filled with --plate, which is the exact band
    of the picture the road is painted on -- so the one part of the valley that must show was the
    one part covered up. It keeps its rect; it gives up its fill.

    Falsified by `cover`/`contain`, by giving the strip a background again, or by drawing
    anything into the board before the backdrop, which paints over it.
    """
    page = TMPL.read_text(encoding="utf-8")
    css = re.sub(r"/\*.*?\*/", " ", page, flags=re.S)
    code = re.sub(r"(?m)^\s*//.*$", "", page)

    bd = re.search(r"#backdrop\{([^}]*)\}", css)
    assert bd, "the backdrop has no rule, so the picture has no size to be drawn at"
    assert "100% 100%" in bd.group(1), (
        "the backdrop is not stretched to its rect: %s" % bd.group(1).strip())
    for wrong in ("cover", "contain"):
        assert wrong not in bd.group(1), (
            "the backdrop uses `%s`, which keeps the picture's own aspect and slides its painted "
            "road off the strip" % wrong)

    road = re.search(r"#road\{([^}]*)\}", css)
    assert road, "#road is gone"
    assert "transparent" in road.group(1) or "background" not in road.group(1), (
        "the road strip paints over the part of the picture the road is painted on: %s"
        % road.group(1).strip())

    # DRAWN FIRST, NOT MERELY BEFORE THE TILES, and the difference cost a caption. These are
    # `#board > *` with no z-index, so append order IS stack order -- and this read "before
    # drawTiles()", which drawStatus() satisfied by sitting in front of the backdrop. That was
    # invisible while the picture started at the top of the TILES and the status line sat at y 10
    # in black air above it. The picture now reaches y 0, the two overlap, and the backdrop
    # painted straight over the line: a caption that was simply not there, with nothing in the
    # console to say so. Everything on this board stands in front of the valley, so the claim is
    # that the valley goes in first.
    draw = code.split("function draw(")[1].split("\n}")[0]
    calls = re.findall(r"\b(draw[A-Z]\w*)\(\)", draw)
    assert calls, "draw() draws nothing"
    assert calls[0] == "drawBackdrop", (
        "the valley is not the first thing drawn, so whatever precedes it is painted over: %s"
        % calls)

    # AND GEOMETRY OWNS WHERE IT GOES. The rect runs from the top of the canvas to the foot of
    # the strip, and it has to reach both: short at the top and the status line is back on black,
    # short at the foot and there is a seam under the road.
    assert geo.BACKDROP["y"] == 0, (
        "the backdrop starts at %d, so there is black above it again" % geo.BACKDROP["y"])
    assert geo.BACKDROP["y"] <= geo.STATUS["y"], "the status line is above the picture"
    assert geo.BACKDROP["y"] + geo.BACKDROP["height"] == geo.ROAD["y"] + geo.ROAD["height"], (
        "the backdrop does not reach the foot of the road strip")

    # AND THE PICTURE IS SQUARE WHERE IT MEETS THE CANVAS'S EDGE. A radius on the top corners
    # cuts two notches of black into the one place the rect was extended to reach.
    radius = re.search(r"border-radius:\s*([^;}]+)", bd.group(1))
    assert radius, "the backdrop has no corner rule, so it takes whatever it inherits"
    tops = radius.group(1).split()[:2] if len(radius.group(1).split()) == 4 else None
    assert tops == ["0", "0"], (
        "the backdrop rounds the corners it shares with the canvas's top edge: %s"
        % radius.group(1).strip())


def test_a_tile_that_drifts_off_the_status_line_is_refused(monkeypatch):
    """The one margin you can see up here, driven directly because nothing else can drive it.

    The picture reaches the top of the canvas, so there is no black edge above the ribbon any
    more and no panel edge below it: the gap between the status line and the tops of the eight
    tiles is the only distance on this part of the board the eye has anything to measure against.

    AND IT IS TRUE BY CONSTRUCTION, WHICH IS WHY THIS EXISTS. TILE_Y is RIBBON_Y and RIBBON_Y is
    the status bar's foot plus GAP, so the complaint cannot fire for any value the module
    produces -- the same dead-looking branch as the tile's two centrings, and dead for the same
    good reason. It stops being dead the moment somebody hangs the tiles at a number of their
    own, which is exactly what they did hang at until this turn.
    """
    g = _load("geometry")
    assert g.check() == [], "the default board is not sound, so this test proves nothing"
    monkeypatch.setattr(g, "TILE_Y", g.RIBBON_Y + 39)
    bad = g.check()
    assert any("under the status line" in line for line in bad), (
        "the tiles hang 39 below where the gap puts them and check() did not say so: %s" % bad)


def test_a_backdrop_that_does_not_reach_both_its_ends_is_refused(monkeypatch):
    """check()'s two complaints about the picture, driven directly because nothing else can.

    BOTH BRANCHES ARE UNREACHABLE THROUGH THE MODULE'S OWN NUMBERS. BACKDROP's y is the literal 0
    and its height is the distance from there to the foot of the road, so the rect is right by
    construction and disabling either condition changes no result anywhere -- which a mutation
    run duly found, twice. That is the same shape as the tile's two centrings: a guard looks like
    dead code exactly when the thing it guards is derived, and it stops being dead the moment
    somebody types a number over the derivation.

    AND THEY ARE TWO COMPLAINTS BECAUSE THEY CATCH TWO FAULTS. A picture that starts late leaves
    the status line back on black -- the thing extending it was for -- and one that ends early
    leaves a seam under the last tile. Either alone would be satisfied by the other's failure.
    """
    g = _load("geometry")
    assert g.check() == [], "the default board is not sound, so this test proves nothing"

    # STARTING AT THE TILES AGAIN, which is where it used to start and is the regression.
    monkeypatch.setitem(g.BACKDROP, "y", g.RIBBON_Y)
    monkeypatch.setitem(g.BACKDROP, "height", g.BACKDROP["height"] - g.RIBBON_Y)
    bad = g.check()
    assert any("the canvas top" in line for line in bad), (
        "the picture starts below the top of the canvas and check() did not say so: %s" % bad)
    monkeypatch.undo()

    # AND TOO SHORT TO COVER WHAT STANDS ON IT. Reaching y 0 is not the same claim: a picture
    # that starts at the top and stops above the ribbon satisfies the first half of the line
    # above and leaves the eight tiles standing on black.
    g = _load("geometry")
    monkeypatch.setitem(g.BACKDROP, "height", g.RIBBON_Y + g.RIBBON_H - 1)
    bad = g.check()
    assert any("the ribbon it stands behind" in line for line in bad), (
        "the picture stops short of the ribbon's foot and check() did not say so: %s" % bad)


def test_the_status_line_reads_against_the_sky_it_is_actually_printed_on(gen):
    """The one line of type on this board that does not sit on the board's own ground.

    THE PICTURE REACHES THE TOP OF THE CANVAS, so these words are on painted SKY -- the lightest
    surface anywhere here. Everything else is cream on dark and needs no thought; this needed a
    colour change, and the colour that is right depends entirely on a file in another folder.

    SO THE TWO ARE MEASURED AGAINST EACH OTHER rather than both being asserted against a number
    typed here. The type's colour is read out of the stylesheet and the sky out of the shipped
    backdrop, at the rows the status box actually covers. Pin either one alone and a replacement
    picture with a night sky passes while the board goes unreadable -- which is exactly the kind
    of change that arrives as "a new backdrop" and touches no code at all.

    AND NO PLATE. A dark box behind the words would be the black strip across the top of the
    picture that extending the picture removed, put back in the one place it was removed from.
    Falsified by giving #status a ground, or by letting the pair fall under 4.5:1.
    """
    from PIL import Image
    import numpy as np

    page = TMPL.read_text(encoding="utf-8")
    rule = decls_for(page, "#status")
    for forbidden in ("background", "border", "backdrop-filter", "outline"):
        assert forbidden not in rule, (
            "the status line has a %s, which is the black strip the picture was extended to "
            "remove: %s" % (forbidden, rule.strip()))

    m = re.search(r"color:\s*#([0-9a-fA-F]{3,6})\b", rule)
    assert m, "the status line states no colour of its own: %s" % rule.strip()
    h = m.group(1)
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    ink = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

    # THE SHIPPED PICTURE, BY THE GENERATOR'S OWN RULE. Reading the newest file any other way
    # would be a second answer to "which backdrop does the board draw".
    found = sorted(f for f in gen.BACKDROP_DIR.glob("ribbon_backdrop_v*")
                   if f.suffix.lower() in gen.image_suffixes())
    assert found, "there is no backdrop to read, so this is testing nothing"
    im = Image.open(found[-1]).convert("RGB")

    geo = _load("geometry")
    bd, st = geo.BACKDROP, geo.STATUS
    assert bd["y"] <= st["y"], "the status line is above the picture, so there is nothing to read"
    # THE ROWS THE BOX ACTUALLY COVERS, mapped through the stretch the page applies. The picture
    # is drawn at the rect with background-size:100% 100%, so a board row is a file row scaled.
    top = round((st["y"] - bd["y"]) / bd["height"] * im.height)
    bot = round((st["y"] + st["height"] - bd["y"]) / bd["height"] * im.height)
    band = np.asarray(im).astype(float)[top:bot]
    assert band.size, "the status band maps to no rows of the picture"

    def rel(c):
        def f(u):
            u = u / 255.0
            return u / 12.92 if u <= 0.03928 else ((u + 0.055) / 1.055) ** 2.4
        r, g, b = (f(x) for x in c)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    # THE WORST ROW, NOT THE AVERAGE. A mean is comfortable about a line that is readable at one
    # end and not the other, which is how a gradient behind type gets through a guard.
    #
    # AND THAT STRICTNESS IS INSURANCE RATHER THAN A MEASURED NEED, which is worth saying because
    # a mutation run says so: flipping this to take the BEST row instead changes no result. The
    # sky behind these words is flat to within a tenth of a point -- 6.57 at its darkest against
    # 6.69 at its lightest -- so on THIS picture the two readings are the same answer. It is kept
    # because the next picture is the whole reason this test reads a file at all, and a sky with
    # a gradient in it is the ordinary case, not the strange one.
    worst = None
    for row in band:
        a, b = rel(ink), rel(row.mean(axis=0))
        hi, lo = max(a, b), min(a, b)
        c = (hi + 0.05) / (lo + 0.05)
        if worst is None or c < worst:
            worst = c
    assert worst >= 4.5, (
        "the status line reads at %.2f:1 against the sky it is printed on, and ordinary text "
        "wants 4.5" % worst)


def test_a_selected_tile_catches_light_and_its_marks_bring_no_ground_of_their_own():
    """Two rules that are only correct together, which is why they are asserted together.

    THE SELECTED TILE IS A GRADIENT, not a block of --plate-lit. That much is taste. What is not
    taste is what it does to the marks: a mark with the `plate` class paints itself a ground so a
    cut-out has something to sit on, and a ground is invisible exactly when it is the same colour
    as what it sits on. Against a gradient there is no one colour to be. --plate-lit would match
    at a single height of the tile and draw a lighter rectangle at every other, on all fourteen
    marks at once -- which is the visible-square fault that naming the plate was meant to end.

    So the ground has to be nothing, and it can only be nothing while the tile behind it is
    painting the light. Put the flat colour back on the tile and `transparent` is still right;
    put a colour back on the ground while the tile is a gradient and fourteen squares return.
    The guard therefore reads both and fails if the ground paints any colour at all.

    AND THE SAME NOW GOES FOR THE SEVEN THAT ARE NOT SELECTED, which is new and is the second
    half of this test. The unselected ground matched its flat tile exactly; the tile is glass
    over the backdrop now, so there is no single colour to match there either. A mark brings no
    ground anywhere on the board -- affordable because the mark is a cutout, the emblem on
    transparency, which never needed a field of its own.

    Falsified by giving either ground a colour or a variable, or by flattening the tile back to
    one colour without saying so here.
    """
    page = TMPL.read_text(encoding="utf-8")
    css = re.sub(r"/\*.*?\*/", " ", page, flags=re.S)

    # THE SELECTOR CARRIES HOVER TOO NOW, so this reads every rule that names .tile.sel rather
    # than matching one exact list. Pinning the list here would make the guard fail the next
    # time a state joins or leaves the plate, which is a question about the plate's OWNERSHIP
    # and belongs in the test below, not in a test about what the plate paints.
    plate = "".join(b for s, b in re.findall(r"([^{}]+)\{([^}]*)\}", css)
                    if ".tile.sel" in s and "background" in b)
    assert plate, ".tile.sel paints no ground at all"
    assert "gradient" in plate, (
        "the selected tile is filled with a flat colour again: %s" % plate.strip())
    for want in ("var(--plate-lit)", "var(--plate)"):
        assert want in plate, (
            "the gradient does not read %s, so the picker's palette no longer reaches the "
            "selected tile" % want)

    ground = re.search(r"\.tile\.sel\s+\.seal\.plate\{([^}]*)\}", css)
    assert ground, "the selected tile's mark ground has no rule, so it keeps the unselected one"
    body = ground.group(1)
    assert "transparent" in body or "none" in body, (
        "the mark ground paints something on a selected tile: %s" % body.strip())
    for forbidden in ("#", "var(", "rgb"):
        assert forbidden not in body, (
            "the mark ground carries a colour (%s) on a gradient tile, so every mark draws a "
            "rectangle where that colour stops matching: %s" % (forbidden, body.strip()))

    # AND THE UNSELECTED GROUND IS NOW NOTHING TOO, which is where this reasoning ended up. It
    # used to be var(--plate), matching the flat tile exactly -- invisible because it agreed with
    # what it sat on. Then the tile became glass over the backdrop, so there was no longer one
    # colour for it to agree with on ANY tile, selected or not, and the ground had the same
    # nothing-to-match problem everywhere. What made that affordable is the mark itself: a cutout
    # is the emblem on transparency and needs no field behind it.
    plain = re.search(r"\n\.seal\.plate\{([^}]*)\}", css)
    assert plain, "an unselected mark's ground has no rule at all"
    body = plain.group(1)
    assert "transparent" in body or "none" in body, (
        "an unselected mark's ground paints something: %s" % body.strip())
    for forbidden in ("#", "var(", "rgb"):
        assert forbidden not in body, (
            "an unselected mark's ground carries a colour (%s) over a tile that is glass, so it "
            "will show as a square on all seven: %s" % (forbidden, body.strip()))


def test_the_controls_are_two_groups_and_a_column_that_forgets_it_is_refused(monkeypatch):
    """Show Map and Hire Building stand; the commit arrives. Spacing has to say so.

    THE THREE USED TO BE ONE EVEN STACK at the foot of the row, and the cost was invisible
    because nothing rendered wrong: the commit appearing simply extended a list upward, so the
    one mark on this board whose APPEARANCE is the message read as a third sibling of two marks
    that are always there. The pair moved to the titles' line and the commit stayed at the foot,
    and the space between them is what makes the arrival news.

    EVERY ONE OF check()'s FOUR COMPLAINTS HERE IS UNREACHABLE THROUGH THE MODULE'S OWN NUMBERS,
    which is the shape this tree keeps meeting: mark_slots() derives the pair's top FROM
    CAP_TEXT_FOOT and the commit's foot FROM the row, so check() is comparing each against the
    expression that produced it and can only ever agree. Moving CAP_TEXT_FOOT does not help --
    both sides move together. So the derivation itself is replaced, which is exactly what a
    later edit to mark_slots() would do.

    Falsified by stacking the three evenly again, by hanging the pair off the top of the row
    rather than off the lettering, by letting the commit drift up with the pair, or by closing
    the space between the two groups.
    """
    g = _load("geometry")
    assert g.check() == [], "the default board is not sound, so this test proves nothing"
    # THE FAKE SLOTS CARRY A BOX, because the real ones do and check() reads it. Built from the
    # same y so a replacement column is internally consistent and the guards under test are the
    # ones that fire, rather than a KeyError standing in for a complaint.
    def slot(y):
        return {"x": g.MARKS_X, "y": y + g.CONTROL_PAD, "width": g.MARK, "height": g.MARK,
                "box": {"x": g.MARKS_X - g.CONTROL_PAD, "y": y,
                        "width": g.CONTROL_BOX, "height": g.CONTROL_BOX}}

    # ONE EVEN STACK AT THE FOOT, which is precisely what this layout replaced.
    pitch = g.CONTROL_BOX + g.MARK_AIR
    foot = g.ART_Y + g.ART_H - g.CONTROL_BOX
    monkeypatch.setattr(g, "mark_slots", lambda: {
        n: slot(foot - (2 - i) * pitch) for i, n in enumerate(g.MARKS_ORDER)})
    bad = g.check()
    assert any("the titles' feet" in line for line in bad), (
        "the three are stacked evenly again and check() did not say so: %s" % bad)
    assert any("reading as a third item" in line for line in bad), (
        "the commit is back in the pair's list and check() did not say so: %s" % bad)
    monkeypatch.undo()

    # THE PAIR HUNG OFF THE TOP OF THE ROW INSTEAD OF OFF THE LETTERING. This is the near miss:
    # six pixels out, nothing overlaps, and the only thing wrong is that the marks no longer
    # line up with the three titles they sit beside.
    g = _load("geometry")
    monkeypatch.setattr(g, "mark_slots", lambda: {
        "map": slot(g.ART_Y), "hire": slot(g.ART_Y + pitch), "commit": slot(foot)})
    bad = g.check()
    assert any("the titles' feet" in line for line in bad), (
        "the pair hangs off the top of the row and check() did not say so: %s" % bad)
    monkeypatch.undo()

    # THE COMMIT CARRIED UP WITH THE PAIR, leaving the foot of the row empty.
    g = _load("geometry")
    top = g.CAP_TEXT_FOOT - g.MARK_AIR
    monkeypatch.setattr(g, "mark_slots", lambda: {
        n: slot(top + i * pitch) for i, n in enumerate(g.MARKS_ORDER)})
    bad = g.check()
    assert any("the action row ends at" in line for line in bad), (
        "the commit left the foot of the row and check() did not say so: %s" % bad)
    monkeypatch.undo()

    # AND THE PAIR BROKEN APART, so "the standing controls" stops being one object.
    g = _load("geometry")
    monkeypatch.setattr(g, "mark_slots", lambda: {
        "map": slot(g.CAP_TEXT_FOOT - g.MARK_AIR),
        "hire": slot(g.CAP_TEXT_FOOT - g.MARK_AIR + pitch + 20),
        "commit": slot(foot)})
    bad = g.check()
    assert any("two standing control boxes are" in line for line in bad), (
        "the pair has come apart and check() did not say so: %s" % bad)


def test_the_titles_line_is_one_fact_and_the_marks_read_it(monkeypatch):
    """CAP_TEXT_FOOT exists so the caption and the controls cannot disagree about one line.

    THE ALTERNATIVE WAS THE CONTROLS RE-DERIVING IT -- ART_Y + BORDER + CAP_PAD_Y + CAP_TEXT_H,
    typed a second time in mark_slots(). Both copies would be correct on the day and the board
    would look right; the fault arrives later, when somebody changes the caption's size or its
    padding and only one of the two copies follows.

    THE BAND IS NOT THE LINE, which is the other thing worth pinning. CAP_H includes the padding
    UNDER the lettering, so a column aligned to the band sits 5px low against titles that look
    aligned to nothing in particular.

    AND IT IS THE BOX THAT LINES UP, NOT THE MARK. Each control stands in a .panel now, and the
    box is the edge the eye follows -- a mark aligned to the titles inside a box that was not
    would read as neither aligned nor deliberate. The mark sits CONTROL_PAD further down.
    """
    g = _load("geometry")
    assert g.CAP_TEXT_FOOT == g.ART_Y + g.BORDER + g.CAP_PAD_Y + g.CAP_TEXT_H
    assert g.CAP_TEXT_FOOT < g.ART_Y + g.CAP_H, (
        "the titles' feet are at or below the caption band's foot, so one of the two is not "
        "what it claims to be")
    assert g.mark_slots()[g.MARKS_ORDER[0]]["box"]["y"] == g.CAP_TEXT_FOOT - g.MARK_AIR

    # THE CAPTION GROWS AND THE MARKS FOLLOW. Nothing in the module reaches CAP_TEXT_FOOT except
    # the Tithe's label height and this column, so a size change that moved one and not the
    # other is the whole fault being guarded.
    g = _load("geometry")
    monkeypatch.setattr(g, "CAP_TEXT_FOOT", g.CAP_TEXT_FOOT + 11)
    assert g.mark_slots()[g.MARKS_ORDER[0]]["box"]["y"] == g.CAP_TEXT_FOOT - g.MARK_AIR, (
        "the standing controls did not follow the titles' line, so the two have separate "
        "answers to where that line is")


def test_hover_and_selection_differ_by_the_rim_alone():
    """Two lit states, one plate between them, and exactly one thing telling them apart.

    HOVER USED TO BE THE LIFT AND NOTHING ELSE, which measured one grey level on the rendered
    tile -- 59 against an untouched 60 -- so a still frame answered the pointer with nothing.
    Hover took the selected tile's plate. That cost the board its answer to "which one is in
    play", which for a while was given by elimination: at most two tiles are lit, the one under
    the pointer is the hovered one. True, and useless in a screenshot, where there is no
    pointer. So selection took a gold rim and got the answer back.

    WHICH LEAVES A SHAPE THAT IS EASY TO ERODE IN EITHER DIRECTION. Give hover anything of its
    own -- a warmer border, a glow, a shade more opacity -- and the board has three appearances
    and names for two. Let the plate be written twice and the same thing happens one edit later.
    The rule being guarded is: ONE plate, shared; ONE extra declaration, on selection only.

    AND THE RIM'S COLOUR IS ASSERTED, WHICH AN EARLIER VERSION OF THIS TEST REFUSED TO DO. The
    refusal sounded principled -- which gold is taste, it was picked by rendering five against
    real tiles, and a threshold here would be a second opinion. It was wrong, and the thing it
    let through is in the history: the tile took a literal #9d7d35 while the selected wheel
    face, the selected action card, the pressed toolbar button and .btn.primary all said
    var(--line). Two golds 16.8 dE apart, both meaning "chosen", neither owning the word.

    SO THE QUESTION THIS GUARDS IS NOT WHICH GOLD, IT IS WHETHER THE BOARD HAS ONE. The tile's
    rim and the wheel face's stroke are read out of the page and required to be the same token,
    so changing the colour stays a one-line edit to --line and changing it in one place only
    does not. Retuning the shade is still free; splitting the vocabulary is not.

    Falsified by giving .tile.lit a look of its own, by splitting the shared plate into two
    rules, by dropping selection's rim so the two states collapse together again, or by letting
    the tile and the wheel disagree about what gold means.
    """
    page = TMPL.read_text(encoding="utf-8")
    css = re.sub(r"/\*.*?\*/", " ", page, flags=re.S)

    rules = [(s.strip(), b) for s, b in re.findall(r"([^{}]+)\{([^}]*)\}", css)]
    paints = ("background", "border", "box-shadow", "filter", "opacity")

    # NOT ::after, WHICH IS THE VACATED STRIP AND NOT A LOOK. Requiring the selector to end at
    # the class matches it out; without that the hit-testing patch reads as a second plate.
    def looks(cls):
        return [(s, b) for s, b in rules
                if re.search(re.escape(cls) + r"\s*(,|$)", s) and any(p in b for p in paints)]

    lit, sel = looks(".tile.lit"), looks(".tile.sel")
    # THE BODY COMES FROM THIS LIST, NOT FROM A LOOKUP BY SELECTOR. `.tile.lit, .tile.sel` is
    # written twice -- once for the plate and once for the lift -- so a dict keyed on the
    # selector keeps whichever came last and this read the transform instead of the gradient.
    shared = [(s, b) for s, b in lit if ".tile.sel" in s]
    assert len(shared) == 1, (
        "the lit plate is not one rule shared by both states (%s), so hover and selection can "
        "drift into a third appearance the board has no name for" % [s for s, _ in lit])
    assert "gradient" in shared[0][1], (
        "the shared rule is not the plate, so hover may be carrying something else entirely")
    shared = [s for s, _ in shared]

    # HOVER OWNS NOTHING. Every rule that paints it must be the shared one.
    assert [s for s, _ in lit] == shared, (
        "hover has a look of its own as well as the shared plate (%s), which is the third "
        "appearance this guard exists to prevent" % [s for s, _ in lit if s not in shared])

    # SELECTION OWNS EXACTLY ONE THING, AND IT IS THE RIM.
    own = [(s, b) for s, b in sel if s not in shared]
    assert len(own) == 1, (
        "selection is distinguished by %d rules, not by the single rim: %s"
        % (len(own), [s for s, _ in own]))
    body = own[0][1]
    decls = {d.split(":")[0].strip(): d.split(":", 1)[1].strip()
             for d in body.split(";") if ":" in d}
    assert set(decls) == {"border-color"}, (
        "selection's own rule sets %s; the rim is meant to be the whole of it, and anything "
        "else here is a second signal saying the same thing" % sorted(decls))

    # ONE GOLD ACROSS THE BOARD. Read from the wheel rather than typed here: a literal in this
    # file would be a third place the colour is written down, which is the fault being guarded.
    face = [b for s, b in rules if "#wheel" in s and ".sel" in s]
    assert face, "the selected wheel face has no rule, so there is nothing to agree with"
    gold = re.search(r"stroke:\s*([^;]+)", face[0])
    assert gold, "the selected wheel face no longer draws a stroke"
    assert decls["border-color"] == gold.group(1).strip(), (
        "the selected tile's rim is %s but the selected wheel face's is %s -- two colours for "
        "one meaning, which is how the board ends up with no word for 'chosen'"
        % (decls["border-color"], gold.group(1).strip()))


def test_the_pointer_lights_a_mark_and_moves_nothing_else(gen):
    """Whatever says "this one", it must not shift the drawing by a pixel.

    This was about the dashed edge closing up: same colour, same width, same box, so the mark
    firmed up without moving. The edge has gone and brightness took over, and the requirement
    survives the change unaltered -- these sit at geometry's own rect, and anything that touched
    the box would move the artwork inside it.

    Falsified by scaling, insetting or re-bordering a mark on hover.
    """
    page = TMPL.read_text(encoding="utf-8")
    css = re.sub(r"/\*.*?\*/", " ", page, flags=re.S)
    m = re.search(r"\.seal\.filled:hover, \.seal\.filled\.on\{([^}]*)\}", css)
    assert m, "the hover and chosen states have no rule"
    body = m.group(1)
    assert "brightness(" in body, "the pointer does not light the mark: %s" % body.strip()
    for moves in ("width", "height", "transform", "padding", "margin", "inset", "border-width"):
        assert moves not in body, (
            "hovering a mark changes %s, so the drawing inside it moves: %s" % (moves, body.strip()))


def test_the_tile_colour_is_one_of_the_icon_labs_plates_taken_whole():
    """The lab is where a plate is chosen; this is where the choice is written down.

    THE PAIR IS THE POINT. The board lifts the SELECTED tile to --plate-lit, and the lab's picker
    used to set --plate and --frame and leave the lit alone -- so carrying a plate across by hand
    gave seven tiles in the new colour and one still in the old. Nothing in either page would have
    said so: the lab reads no --plate-lit, and the board reads no palette.

    Falsified by typing a plate the lab does not offer, or by moving one of the two and not the
    other -- which is the failure this is actually for.
    """
    board = TMPL.read_text(encoding="utf-8")
    lab = (ROOT / "ui" / "board_v2" / "icon_lab" / "tile_column.html.tmpl").read_text("utf-8")
    palette = json.loads(re.search(r"var PALETTE = (\[.*?\]);", lab, re.S).group(1))
    assert palette, "the icon lab offers no plates"
    plate = re.search(r"--plate:(#[0-9A-Fa-f]{6})", board).group(1).upper()
    lit = re.search(r"--plate-lit:(#[0-9A-Fa-f]{6})", board).group(1).upper()
    pairs = {(p["plate"].upper(), p["lit"].upper()): p["name"] for p in palette}
    assert (plate, lit) in pairs, (
        "the board draws plate %s with lit %s, which is not one of the lab's: %s"
        % (plate, lit, sorted((p["plate"], p["lit"], p["name"]) for p in palette)))


def test_every_cue_the_page_plays_has_a_sound_and_a_level():
    """A cue with no gain is silent; a cue with no file is silent. Both read as a broken board.

    THE PAGE NAMES CUES, NOT FILES -- it asks for `hover`, `select` and `confirm`, and the
    generator decides which clip answers. That indirection is worth having and it is exactly what
    lets a cue go missing quietly: adding `sfx("warning")` somewhere compiles, builds, ships and
    does nothing at all. So the call sites are read back out of the template and checked.

    Falsified by playing a cue that SFX_GAIN does not price, or by naming a clip the generator
    cannot find.
    """
    page = TMPL.read_text(encoding="utf-8")
    code = re.sub(r"(?m)^\s*//.*$", "", page)
    cues = set(re.findall(r'\bsfx\("([a-z_]+)"\)', code))
    assert cues, "nothing plays a sound at all"
    priced = re.search(r"var SFX_GAIN = \{([^}]*)\}", code).group(1)
    gains = dict(re.findall(r"(\w+):\s*([0-9.]+)", priced))
    missing = sorted(c for c in cues if c not in gains)
    assert not missing, (
        "these cues are played but have no gain, so they play at nothing: %s" % missing)
    # AND EVERY GAIN IS A LEVEL, not a multiplier. Above 1 the clip clips, and these were cut at
    # their natural peak precisely so the numbers here mean what they say.
    for c, g in gains.items():
        assert 0 < float(g) <= 1, "%s plays at %s, which is not a level" % (c, g)

    # THE CLIP BEHIND EACH CUE HAS TO EXIST. The generator maps cues onto files; this walks the
    # same map rather than assuming the two file names.
    gen = (TOOL / "generate_action_board.py").read_text(encoding="utf-8")
    files = re.findall(r'for cue in \(([^)]*)\)', gen)
    assert files, "bundled_sfx() no longer lists the cues it bundles"
    for name in re.findall(r'"([a-z_]+)"', files[0]):
        f = ROOT / "ui" / "board_v2" / "sfx" / ("%s.ogg" % name)
        assert f.is_file(), "the generator bundles %s.ogg and there is no such file" % name


def test_the_hover_cue_fires_on_the_duty_changing_not_on_every_crossing():
    """mouseover bubbles, so the pointer "arrives" many times over one tile.

    hover() is called from a delegated mouseover, which fires again every time the pointer moves
    between a tile and the mark inside it -- the same duty, twice. A cue fired on arrival rattles
    while you hold still over one tile, and a ribbon of eight turns a slow sweep into a stutter.
    The thing that happened is the duty under the pointer CHANGING.

    Falsified by playing the cue unconditionally in hover(), which is what it would look like if
    somebody simplified the function.
    """
    page = TMPL.read_text(encoding="utf-8")
    code = re.sub(r"(?m)^\s*//.*$", "", page)
    body = code.split("function hover(")[1].split("\nfunction ")[0]
    assert 'sfx("hover")' in body, "hovering a duty plays nothing"
    line = [ln for ln in body.split("\n") if 'sfx("hover")' in ln][0]
    assert "!==" in line or "!=" in line, (
        "the hover cue is not guarded by the duty changing, so it fires on every crossing "
        "between a tile and the mark inside it: %s" % line.strip())
    # AND THE COMPARISON IS AGAINST WHAT IT WAS, captured before hovered is reassigned.
    assert body.index("hovered") < body.index('sfx("hover")'), (
        "the previous duty is not read before `hovered` is overwritten, so the test compares a "
        "value with itself and is always false")


def test_a_sound_in_the_tree_says_where_it_came_from():
    """The same rule the pictures live under, applied to the one asset class that escaped it.

    `tests/layout_lab/test_board_v2_attribution.py` holds every image in ui/board_v2/ to a record
    in attribution.json, and it walks by SUFFIX -- png, jpg, webp, svg, gif, avif. A .ogg is
    invisible to it. So the sounds arrived in a tree whose whole discipline is that an asset
    nobody can account for gets dropped, and nothing would have noticed.

    This is the cheap version of that rule rather than an extension of attribution.json: every
    sound has to be named in its own README, which is where the licence and the cut are recorded.
    Falsified by dropping a clip into sfx/ and saying nothing about it.
    """
    sfx = ROOT / "ui" / "board_v2" / "sfx"
    if not sfx.is_dir():
        pytest.skip("no sfx/ in this tree")
    readme = (sfx / "README.md")
    assert readme.is_file(), "there are sounds in the tree and no record of where they came from"
    said = readme.read_text(encoding="utf-8")
    # NOT _to_delete/ OR ANYTHING UNDER IT. A folder of things on their way out is not an asset.
    clips = [p for p in sorted(sfx.rglob("*.ogg")) if "_to_delete" not in p.parts]
    assert clips, "sfx/ holds no sounds"
    for p in clips:
        assert p.name in said, (
            "%s is in the tree and is not named in sfx/README.md, so nothing says what it is or "
            "what licence it carries" % p.name)
    assert "CC0" in said or "licence" in said.lower() or "license" in said.lower(), (
        "sfx/README.md records no licence for any of it")


def test_the_ribbon_holds_still_and_a_tile_that_moves_is_refused():
    """The tiles do not move. Not on hover, not on selection, not at all.

    THEY USED TO. A hovered tile rose 6px, a selected tile stayed up at the same height, and the
    reasoning was sound: movement is the loudest signal there is and the only one that cannot be
    mistaken for a state, since a state does not rise. It was removed anyway -- the eight tiles
    now hold a fixed line and colour does the whole job.

    SO THIS TEST IS THE OLD ONE TURNED OVER. It used to assert the lift existed, was a transform
    rather than a height, rode on `.lit` so the wheel raised a tile for free, and gave back the
    strip it vacated. Every one of those clauses is now a thing that must NOT be there, and the
    cheapest way for the lift to come back is for someone to reach for the obvious property --
    `top`, `margin-top`, `translateY` -- without knowing it was ever deliberate.

    THE THREE PIECES OF MACHINERY GO TOO, and they are checked because a half-removal is worse
    than either state. `--lift` was the distance; `.tile.lit::after` refilled the strip so a
    pointer on the tile's bottom edge did not set off an un-hover / drop / re-hover shudder; the
    reduced-motion rule turned the transition off for readers who asked for less movement. Left
    behind, the ::after is an invisible 6px band hanging under every lit tile, still catching
    hit-tests for a tile that no longer moves.

    WHAT IS KEPT IS THE CROSS-HIGHLIGHT. `.lit` still exists and still carries the plate, and
    lightFace() still sets it from either end, so hovering a wheel face still lights its tile.
    Removing the movement was not removing the link.

    Falsified by giving a tile a transform or any offsetting property in any state, by leaving
    --lift or the vacated-strip ::after behind, or by moving `lit` onto the tile's own :hover and
    cutting the wheel out of it.
    """
    page = TMPL.read_text(encoding="utf-8")
    css = re.sub(r"/\*.*?\*/", " ", page, flags=re.S)

    assert "--lift" not in css, (
        "--lift is back, so something is measuring a distance a tile is meant to travel")

    # THE PROPERTY, NOT THE WORD. `transition:transform` would be the lift's timing rather than a
    # lift, and an earlier version of this guard counted it and named the wrong fault. Both are
    # gone now and both would be wrong to have, but the message should still be the true one.
    for sel, body in re.findall(r"([^{}]+)\{([^}]*)\}", css):
        if ".tile" not in sel:
            continue
        for prop in ("transform", "margin-top", "margin-bottom", "translate"):
            assert not re.search(r"(^|[;\s])%s\s*:" % prop, body), (
                "`%s` on `%s` moves a tile, and the ribbon is meant to hold still: %s"
                % (prop, sel.strip(), body.strip()))

    assert "::after" not in css.split(".tile.lit")[-1][:200], (
        "the vacated-strip ::after is still under a lit tile -- an invisible band catching "
        "hit-tests for a movement that no longer happens")

    # AND THE CROSS-HIGHLIGHT SURVIVES THE REMOVAL, which is the part most at risk: `.lit` now
    # does one job instead of two, and a reader tidying up could reasonably conclude it does
    # none. It carries the plate, and the wheel is half of where it comes from.
    code = re.sub(r"(?m)^\s*//.*$", "", page)
    assert ".tile:hover" not in css, (
        "hover is on the tile's own :hover, so hovering a wheel face no longer lights it")
    face = code.split("function lightFace(")[1].split("\nfunction ")[0]
    assert 'classList.toggle("lit"' in face and "tile" in face, (
        "lightFace() no longer sets `lit` on the tile, so the cross-highlight has lost the half "
        "of its wiring that comes from the wheel")


def test_clicking_a_mark_selects_the_action_it_stands_for():
    """A mark IS its action, so pressing one has to put that action down.

    THE BUG THIS IS POINTED AT: the mark's handler called pickDuty, which sets the duty and
    CLEARS the slot. So the one thing on the tile that names a single action could not select it,
    and the only way in was the card below -- while the mark lit up under the pointer the whole
    time, which is what made it read as broken rather than as unclickable.

    The TILE's own area still goes through pickDuty, and that is not an oversight: a click on the
    tile is about the duty and names no action. Falsified by wiring the mark back to pickDuty, or
    by having pickAction set the duty without the slot.

    A STATIC CHECK, AND IT SAYS SO. The lab lane installs no browser; the behaviour itself was
    verified by driving the built page.
    """
    page = TMPL.read_text(encoding="utf-8")
    code = re.sub(r"(?m)^\s*//.*$", "", page)
    seal = code.split("function slotClick(")[1].split("\nfunction ")[0]
    assert "pickAction(" in seal, (
        "the mark's handler does not go through pickAction, so it cannot name an action")
    assert "pickDuty(" not in seal, (
        "the mark's handler still calls pickDuty, which sets the duty and clears the slot")
    # AND THE CHOSEN MARK HOLDS ITS SOLID EDGE, by the hover's own rule rather than a second one.
    css = re.sub(r"/\*.*?\*/", " ", page, flags=re.S)
    assert re.search(r"\.seal\.filled:hover\s*,\s*\.seal\.filled\.on\s*\{"
                     r"|\.seal\.filled\.on\s*,\s*\.seal\.filled:hover\s*\{", css), (
        "the chosen mark and the hovered one do not draw their edge from the same rule, so the "
        "two can come to disagree about what a solid edge means")
    # SET FROM THE STATE, NOT WHERE IT IS CLICKED. S.slot is reached three ways -- the mark, the
    # card below it, and picking a duty, which clears it or, for a one-action duty, chooses that
    # action -- and a class set in the click handler is right on one of them. render() answers all
    # three.
    rend = code.split("function render(")[1].split("\nfunction ")[0]
    assert 'classList.toggle("on"' in rend, (
        "the chosen mark's class is not set in render(), so it will be wrong whenever the slot "
        "changes by any route but clicking the mark -- the card below is one")
    assert "pickAction" not in rend, "render() should not be picking anything"
    on = re.search(r'classList\.toggle\("on",([^;]*)\)', rend).group(1)
    assert "S.duty" in on and "S.slot" in on, (
        "the chosen mark is matched on %s -- on the slot alone the same-named mark lights up in "
        "every duty's tile at once" % on.strip())

    body = code.split("function pickAction(")[1].split("\nfunction ")[0]
    assert "S.duty" in body and "S.slot" in body, (
        "pickAction sets only one of the two, so a mark selects a duty or an action but not both")
    # ONE RENDER, NOT TWO. pickDuty followed by select() would have done this as well, by setting
    # the slot, clearing it and setting it again -- drawing the board twice on the way.
    assert body.count("render()") == 1, (
        "pickAction draws the board %d times for one click" % body.count("render()"))


def test_a_click_chooses_and_a_duty_with_one_action_chooses_itself():
    """Two rules that only make sense together, so they are asserted together.

    A CLICK DOES NOT UN-CHOOSE. Both routes into the slot used to toggle, so pressing the same
    mark or the same card twice put the action back down. That was invisible while nothing marked
    the choice, and became a misfire the moment the chosen mark started holding a solid edge.
    Both are asserted, because one that toggles beside one that does not is the same click
    behaving two ways depending on where it landed.

    AND A DUTY WITH ONE ACTION HAS NOTHING TO ASK. Taxation and Allocation have one each, so
    picking the duty picks it; otherwise the board sits on a tile whose single action is unchosen,
    with an empty confirm row beside a dashed mark.

    ASKED OF THE DATA, NOT OF A LIST OF NAMES. A duty gaining or losing a second action must not
    need an edit here -- `actions` is duty_text.json's to say.

    Falsified by putting either toggle back, by typing the two duties' names, or by seeding the
    opening slot to a literal null that happens to be right today.
    """
    page = TMPL.read_text(encoding="utf-8")
    code = re.sub(r"(?m)^\s*//.*$", "", page)

    sel = code.split("function select(")[1].split("\n")[0]
    assert "null" not in sel, "select() still puts the action back down: %s" % sel.strip()
    act = code.split("function pickAction(")[1].split("\nfunction ")[0]
    assert "null" not in act, "pickAction() still toggles: %s" % " ".join(act.split())

    only = code.split("function onlySlot(")[1].split("\nfunction ")[0]
    assert "actions === 1" in only or "actions == 1" in only, (
        "onlySlot() does not ask how many actions the duty has: %s" % " ".join(only.split()))
    for named in ("taxation", "allocation"):
        assert named not in only.lower(), (
            "onlySlot() names %s instead of counting its actions, so a duty that gains a second "
            "one will keep choosing its first" % named)

    duty = code.split("function pickDuty(")[1].split("\nfunction ")[0]
    assert "onlySlot(" in duty, (
        "picking a duty does not ask onlySlot(), so a one-action duty opens unchosen")
    assert "S.slot = null" not in duty, "picking a duty still clears the slot unconditionally"

    # AND THE BOARD OPENS BY THE SAME RULE, rather than on a null that is right only while the
    # first duty on the ribbon happens to have two actions.
    #
    # MATCHED ON ITS ARGUMENT, not just on the call. `S.slot = onlySlot(` also describes the line
    # inside pickDuty(), so the looser pattern passed with the opening line deleted -- it was
    # reading the rule from the wrong place and reporting it as the right one.
    assert re.search(r"S\.slot\s*=\s*onlySlot\(\s*S\.duty\s*\)", code), (
        "the opening slot is not set by onlySlot(S.duty), so the board can open on a one-action "
        "duty with its action unchosen")


def test_the_road_is_drawn_and_nothing_below_it_moved(geo):
    """The strip is empty on purpose, which is exactly why it needs a guard.

    Nothing is drawn in it yet, so there is no artwork whose absence would be noticed and no
    layout that would visibly break if it quietly stopped being reserved.

    IT IS NO LONGER A ROW OF ITS OWN, AND THE TEST'S NAME IS NOW HALF WRONG. The strip used to
    sit BETWEEN the ribbon and the cards with a gap either side, holding open the room a shorter
    ribbon had freed so that nothing below it rode up. It is inside the band now -- the part of
    the valley below the tiles, which is the ground the Merchant actually walks on -- and
    everything below it moved up by the whole row it used to occupy. That was the point of the
    change, so "nothing below it moved" is the one thing this can no longer claim.

    WHAT SURVIVES IS WHAT IT WAS ALWAYS REALLY FOR: that the strip exists, spans what the eight
    tiles span, is thick enough to read as a road rather than a rule, and lies where the picture
    has painted ground for it -- between the tiles' foot and the picture's own foot.

    Falsified by deleting the strip, by flattening it, or by putting it outside the picture.
    """
    assert geo.ROAD["height"] >= geo.GAP, (
        "the road is %d tall, which is thinner than the gaps on this board -- it would read "
        "as a rule rather than as a strip the Merchant travels along" % geo.ROAD["height"])
    assert geo.ROAD["y"] == geo.TILE_Y + geo.TILE_H, (
        "the road does not start at the tiles' foot")
    assert geo.ROAD["y"] + geo.ROAD["height"] == geo.RIBBON_Y + geo.RIBBON_H, (
        "the road does not reach the foot of the band")
    # AND IT IS INSIDE THE PICTURE, which is what lets it stop being a row. A strip below the
    # backdrop would be a band of black with a Merchant walking along it.
    bd = geo.BACKDROP
    assert bd["y"] <= geo.ROAD["y"] and \
        geo.ROAD["y"] + geo.ROAD["height"] <= bd["y"] + bd["height"], (
        "the road runs outside the picture, so the Merchant has no painted ground")
    assert geo.ART_Y == bd["y"] + bd["height"] + geo.GAP, (
        "the cards are not one gap under the picture")
    # FULL WIDTH, because the Merchant rides the eight duty tiles and the strip is the road it
    # travels along -- so it spans what they span rather than what the card row does.
    assert geo.ROAD["x"] == geo.X0 and geo.ROAD["width"] == geo.WORK_W, (
        "the road does not span the working width the eight tiles stand on")
    page = TMPL.read_text(encoding="utf-8")
    assert "#road{" in page, "the road has no rule, so the strip renders as nothing"
    code = re.sub(r"(?m)^\s*//.*$", "", page)
    assert re.search(r"\bdrawRoad\(\)", code.split("function draw()")[1].split("\n}")[0]), (
        "draw() does not draw the road")


def test_a_label_sits_the_same_distance_from_the_top_of_whatever_box_it_is_in(geo):
    """The duty's name in its tile and the action's name on its card are the same kind of thing.

    They were 14 and 6, and nothing anywhere said they were meant to agree, so they didn't --
    which showed as the ribbon's titles floating lower than the captions beside them. Falsified
    by typing a number into either one instead of taking INSET.

    THE DUTY'S NAME IS NO LONGER ONE OF THEM. It was the first half of this pair, and the pair is
    what the test is named for; the names are off the board, so TILE_NAME_TOP is gone and the
    claim narrows to the boxes that still print a label. What the tile contributes instead is its
    MARKS: the air round them is the same inset, twice, which is the same kind of claim about the
    same number and is why this is still one test.
    """
    assert geo.CAP_PAD_Y == geo.INSET
    assert geo.TITHE_LABEL_TOP == geo.INSET - geo.BORDER, (
        "the Tithe's label is no longer the caption's inset, measured inside its border")
    assert geo.SEAL_INSET == geo.INSET, "the seals use a margin of their own again"
    assert geo.TILE_PAD == 2 * geo.SEAL_INSET, (
        "the air round a tile's marks is %d and the marks keep %d between themselves, so the "
        "tile has a margin of its own again" % (geo.TILE_PAD, geo.SEAL_INSET))


def test_the_two_wax_discs_clear_each_other_and_not_merely_their_boxes(geo):
    """A disc is SOLID_FRACTION of its square, so the boxes are not what has to clear.

    The first diagonal passed every box test with its centres 70.0 apart against a sum of radii
    of 70.7 -- the two discs touching, by seven tenths of a pixel, while the arithmetic read
    "corner overlap 18 x 42". Falsified by widening SEAL or by putting SEAL_INSET back up.

    A FLOOR, NOT A VERDICT. The bounding disc is the widest the art ever gets and these seals are
    scalloped, so the drawn rims clear by more than this says. How much daylight looks right is
    not a thing a test can know; that it is more than none is.
    """
    a, b = geo.seal_slots(2)
    dx, dy = b["x"] - a["x"], b["y"] - a["y"]
    centres = (dx * dx + dy * dy) ** 0.5
    touch = geo.SOLID_FRACTION * geo.SEAL
    assert centres - touch >= geo.DISC_CLEARANCE, (
        "the discs clear each other by %.1f and this board wants %d"
        % (centres - touch, geo.DISC_CLEARANCE))
    assert geo.DISC_CLEARANCE >= 0, "a negative floor would permit the fault it exists to catch"


# =================================================================================================
# THE TITHE COLUMN
#
# Three seals and a label in one fixed box. The seals grew from 64 to 78 because a seal is a seal
# whatever it stands for, and at 78 the old spacing no longer fits: three of them plus two GAPs
# plus the label's band comes to 298 in a box of 295. So the gap is a REMAINDER rather than a
# choice, and these are what stop the label being pushed quietly out of the bottom.

# test_a_tithe_seal_is_a_duty_mark_unless_the_box_will_not_take_one IS GONE WITH THE DISCS, and
# the reasoning deserves to outlive them because it is the best worked example in this file of a
# derived size earning its keep.
#
# THE CLAIM WAS: a Tithe resource is the duty mark's size, and the ONLY thing that may make it
# smaller is the box it has to fit in. A figure of its own would have passed "TOKEN <= SEAL" and
# failed here. Three of them stood in a column whose height is ART_H -- a number chosen for the
# artwork, not for them -- so at a mark of 72 the box bound at 66, and at a mark of 50 it did not
# bind at all. The test therefore asked for the binding case DELIBERATELY rather than reading it
# off the board, because a guard that only exercises whichever term happens to bind today stops
# covering the other one the day the board moves.
#
# AND THE HEIGHT TERM WAS THE ONE THAT HAD BEEN WRONG. token_cap()'s width term divided by two,
# left from a side-by-side arrangement, and agreed with the right answer by luck until the Tithe
# narrowed to 120 -- at which point the discs silently went from 66 to 50. A mutation run later
# walked straight through the first replacement for this guard, which asserted the cap was under
# the WIDTH limit: dividing the height by two gives 99, still under the width's 106, while three
# tokens needed 309 in a box of 211. What finally held it was measuring the COLUMN -- three of
# them and their insets against the room -- which is the question the function exists to answer.


def test_the_tithe_is_one_duty_column_wide_and_holds_only_its_label(geo):
    """What is left of the Tithe once the three resources are off it, asserted so it stays left.

    THIS REPLACES test_three_tithe_seals_and_their_label_fit_the_box_they_are_in, and the thing
    it was guarding is worth recording. The three discs grew from 64 to 78 because a seal is a
    seal whatever it stands for, and at 78 three of them plus two gaps plus the label's band came
    to 298 in a box of 295 -- so the gap had to be a REMAINDER rather than a choice, laid out
    from the fixed parts, or the label got pushed quietly out of the bottom. That arithmetic has
    no subject now.

    WHAT REPLACES IT IS THE WIDTH, which is the half of the Tithe that is still a claim. The box
    was 120 because 120 was what a packed row had left after the cards and the controls; nothing
    inside it asks for a width any more, so it takes one duty's column -- the unit the cards are
    three of and the tile used to be one of. A number typed here instead would be the only
    unexplained width on the board.
    """
    assert geo.check() == [], "\n".join(geo.check())
    assert geo.TITHE_W == geo.SLICE_W, (
        "the Tithe is %d wide and a duty's column is %d" % (geo.TITHE_W, geo.SLICE_W))
    # AND NOTHING IS PLACED IN IT. The discs were handed to the page already positioned, which is
    # how a drawing stops inventing a layout -- and is also how a removed thing comes back: a
    # page given three rects is one line from drawing them.
    t = geo.as_dict()["tithe"]
    for gone in ("token", "order", "spread", "slots"):
        assert gone not in t, (
            "the Tithe still publishes %r, so the three resources can be drawn again by "
            "accident" % gone)
    # THE LABEL IS STILL HUNG FROM THE TOP AND STILL FITS. It is the only thing in the box, so
    # the only way it can be wrong is by not having room -- which it cannot fail at today and
    # could the moment somebody shortens the box to suit its new emptiness.
    assert geo.TITHE_LABEL_TOP + geo.TITHE_LABEL_H <= geo.TITHE_INNER_H, (
        "the label ends at %d in a box %d deep"
        % (geo.TITHE_LABEL_TOP + geo.TITHE_LABEL_H, geo.TITHE_INNER_H))


def test_the_tithe_column_states_no_numbers_of_its_own(gen):
    """The seals went 64 -> 78 and the column had a 21 and a 14 typed into the template.

    Nothing in it would have moved, and the label would have been pushed at with no complaint
    from anywhere. Falsified by writing an offset back into the template.
    """
    page = TMPL.read_text(encoding="utf-8")
    # THE TITHE PART OF drawSide, not all of it. The same function goes on to draw the City, whose
    # pawn grid still has four figures typed into it -- a real instance of this fault and a
    # separate piece of work. Widening this test to cover it would be reporting that fault as a
    # regression in the Tithe column, which it is not.
    # THE SPLIT ENDS AT THE CITY, which is where the Tithe's own drawing ends now that the
    # confirm that used to follow it has gone. The marker moved; the boundary did not.
    body = page.split("var t = GEO.tithe;")[1].split("var c = GEO.city;")[0]
    body = re.sub(r"(?m)^\s*//.*$", " ", body)
    # t.slots AND t.order WENT WITH THE THREE RESOURCES, and they were the two this test was
    # really about: where each disc sat was handed over placed, as the duty tile's marks are, so
    # the page read positions rather than recomputing a layout from a start and a repeat. There
    # is nothing to place now, so what is asserted is the absence -- a page that still named
    # t.slots would be one holding positions for things geometry does not publish.
    for key in ("t.labelTop", "t.labelSize"):
        assert key in body, "the Tithe column no longer takes %s from GEO" % key
    for gone in ("t.tokenY", "t.tokenGap", "t.tokenX", "t.slots", "t.order", "t.token"):
        assert gone not in body, (
            "%s is back in the template, so the page is laying the Tithe out itself again" % gone)
    # WHICH EDGE IT IS BOUND TO, not merely that the number is read. `bottom: px(t.labelTop)` takes
    # the value from GEO, reads correctly, passes the line above, and hangs Take Tithe back at the
    # foot of its column -- off the row it is supposed to be standing in.
    assert "top: px(t.labelTop)" in body, (
        "Take Tithe is no longer hung from the top of its box, so it has left the caption row")
    assert "bottom:" not in body, "the Tithe column is measuring from the bottom again"
    stray = [n for n in re.findall(r"(?<![\w.#-])(\d{2,4})(?![\w.%])", body)]
    assert not stray, "the Tithe column has %s typed into it" % ", ".join(stray)


def test_a_bordered_box_measures_its_children_inside_its_border(geo):
    """THE FAULT THAT KEPT COMING BACK, and the only test here that would have caught it.

    A child at `left: 6px` sits 6px from the border's INNER edge, so a grid centred on the box's
    stated width leans by the border on each side -- two pixels. The arithmetic looks symmetrical
    either way, which is why every instance was found by measuring the rendered page instead: the
    duty tile's seals, the City's four pawns and the Tithe's column of three, in that order.

    So what is asserted is not that the margins come out equal -- they do either way, in the
    module's own coordinates -- but that each box's inner size is its outer size less its border.
    Falsified by writing SIDE_W or TILE_W where an inner width belongs.
    """
    assert geo.inner(100, 50) == (100 - 2 * geo.BORDER, 50 - 2 * geo.BORDER)
    for name, inner_wh, outer_wh in (
            # THE TILE'S OWN HEIGHT, NOT THE BAND'S. These were one number while the tile filled
            # its column top to bottom; the tile is 74 x 130 hanging inside a band of 186, so
            # reading RIBBON_H here would be measuring the box's children against a box that is
            # not the box -- which is this test's own fault, met from the other direction.
            ("the duty tile", (geo.TILE_INNER_W, geo.TILE_INNER_H), (geo.TILE_W, geo.TILE_H)),
            ("the City", (geo.CITY_INNER_W, geo.CITY_INNER_H), (geo.SIDE_W, geo.CITY_H)),
            ("the Tithe", (geo.TITHE_INNER_W, geo.TITHE_INNER_H),
             (geo.TITHE_W, geo.ART_H))):
        assert inner_wh == geo.inner(*outer_wh), (
            "%s works on %s inside a box of %s" % (name, inner_wh, outer_wh))


def test_the_city_grid_is_margined_evenly_inside_its_own_border(geo):
    """Falsified by giving the grid a spacing of its own instead of INSET."""
    assert geo.check() == [], "\n".join(geo.check())
    figs = geo.city_figures()
    assert len(figs) == len(geo.PLAYERS), "the grid and the player list disagree"
    # EVENLY MARGINED IS THE CLAIM, AND IT IS NOT "AT THE INSET". The figures are the acolyte's
    # own size now rather than whatever dividing the box up left over, so they no longer fill its
    # width and the side margins are the remainder. They still have to match each other -- that is
    # the two-pixel lean this test was written for -- but they are not six.
    left = figs[0]["x"]
    right = geo.CITY_INNER_W - (figs[1]["x"] + figs[1]["width"])
    assert left == right, "%d on the left and %d on the right" % (left, right)
    between = figs[1]["x"] - (figs[0]["x"] + figs[0]["width"])
    rows = figs[2]["y"] - (figs[0]["y"] + figs[0]["height"])
    foot = geo.CITY_INNER_H - (figs[-1]["y"] + figs[-1]["height"])
    assert between == rows == foot == geo.INSET, (
        "the City has %d between its columns, %d between its rows and %d at its foot"
        % (between, rows, foot))
    # AND A CITY FIGURE IS AN ACOLYTE. It was 67 x 130 against the pawn's own 50 x 120 -- the same
    # drawing stretched 23% wider in one of the two places it appears.
    assert (figs[0]["width"], figs[0]["height"]) == (geo.ACOLYTE_W, geo.ACOLYTE_H), (
        "a City figure is %d x %d and an acolyte on the wheel is %d x %d"
        % (figs[0]["width"], figs[0]["height"], geo.ACOLYTE_W, geo.ACOLYTE_H))


def test_take_tithe_sits_on_the_action_captions_line(geo):
    """The three choices on offer this turn carry one row of titles, so it must BE one row.

    Take Tithe used to be a panel label at the foot of its column, sized with the City's. It is
    now the third title in the action row, which is a different claim and a more fragile one: the
    row holds only while the Tithe's size, its top inset and its line height are the caption's
    rather than copies of them. Falsified by giving the Tithe a size, an inset or a line height
    of its own -- each of which puts the row visibly out of line.
    """
    assert geo.TITHE_LABEL_SIZE == geo.CAP_SIZE
    assert geo.TITHE_LABEL_TOP == geo.CAP_PAD_Y - geo.BORDER
    assert geo.TITHE_LABEL_H == round(geo.CAP_SIZE * geo.CAP_LH)

    d = geo.as_dict()
    tithe, art = d["tithe"], d["art"]
    assert tithe["labelSize"] == art["capSize"], "the titles are not the same size"
    # NOT EQUAL, AND THAT IS THE POINT. The card is unbordered and the panel is not, so a shared
    # inset would put the two titles one pixel apart; the Tithe gives that pixel back.
    assert tithe["labelTop"] == art["capPadY"] - geo.BORDER, (
        "the titles do not land on the same line once the panel's border is counted")
    assert tithe["lh"] == art["capLh"], "the titles are on different line heights"

    # The City is NOT part of that row and must not be dragged into it: it is a panel label on a
    # panel, below the fold, and it kept the 12 the Tithe gave up.
    assert geo.CITY_LABEL_SIZE == 12
    assert d["city"]["labelTop"] == geo.INSET


def test_full_screen_can_always_be_left_again(gen):
    """F takes the chrome off and asks for the display. Those are two different things.

    The fault worth guarding is a page that cannot be got back. Esc leaves full screen WITHOUT
    passing through the key handler, so if the chrome were restored by the keystroke alone the
    board would come back with no toolbar, no save button and no way to reach either. The class is
    therefore driven by fullscreenchange as well.

    And requestFullscreen can be refused -- a file:// page, a policy, a window that is already
    somebody else's full screen -- so the refusal is swallowed and the chrome stays off, because a
    board filling the window is still what was asked for. A page that threw there would leave F
    doing nothing at all.
    """
    page = TMPL.read_text(encoding="utf-8")
    assert 'e.key === "f"' in page, "nothing on the board listens for F"
    assert "body.full #bar" in page, "full screen does not take the toolbar away"
    assert "fullscreenchange" in page, (
        "the chrome is restored by the keystroke alone, so Esc would strand the page without a "
        "toolbar")
    assert "webkitfullscreenchange" in page and "webkitRequestFullscreen" in page, (
        "only the unprefixed API is used, and this is read in Safari")
    # The refusal must be swallowed rather than thrown.
    assert "p.catch" in page, "a refused full-screen request would leave F doing nothing"
    # Not while somebody is typing.
    body = page.split('document.addEventListener("keydown"')[1].split("});")[0]
    assert "isContentEditable" in body and "INPUT" in body, (
        "F is swallowed from text fields, so typing an f would blank the board")


def test_the_board_is_scaled_to_the_window_on_both_axes(gen):
    """The board is 1400 x 1200 and a laptop window is wide and short.

    fit() measured the width alone, so on any screen that could take 1400 across but not 1200 down
    -- which is most of them -- the scale came back 1 and the bottom of the board was off the
    screen, the wheel cut in half with nothing to say so. Falsified by dropping the height from the
    minimum, which is the state this was found in.
    """
    page = TMPL.read_text(encoding="utf-8")
    body = page.split("function fit(){")[1].split("\n}")[0]
    # THE SCALE EXPRESSION, not the function. GEO.canvas.height appears again two lines further
    # down, where the scaled height is written back to the box -- so looking anywhere in fit() for
    # the word passes happily while the height has been dropped from the minimum, which is the
    # exact fault. Asked of the one line that decides the scale instead.
    scale = [l for l in body.splitlines() if "Math.min" in l]
    assert len(scale) == 1, "fit() has %d candidate scale lines" % len(scale)
    assert "GEO.canvas.width" in scale[0] and "GEO.canvas.height" in scale[0], (
        "the scale is not taken from both axes, so the board can run off the bottom of the "
        "window: %s" % scale[0].strip())
    assert "innerHeight" in body, "fit() does not look at how tall the window is"
    # The chrome above the stage is read off the page; a typed allowance goes stale the first time
    # the note bar appears or the toolbar wraps to two rows.
    assert "offsetHeight" in body, "fit() is guessing the height of the chrome above the board"
    stray = [n for n in re.findall(r"(?<![\w.#-])(\d{2,4})(?![\w.%])", body)]
    assert not stray, "fit() has %s typed into it" % ", ".join(stray)


def test_the_caption_is_made_readable_on_the_letters_and_not_over_the_picture(gen):
    """The scrim is gone and must not come back by the front door or the side one.

    A gradient across the top of the card bought the caption its contrast by darkening a strip of
    fourteen pictures, in the corner the briefs reserve for quiet dark ground -- paying for one
    word with the top of every image. The halo pays for it on the glyphs instead. Falsified by
    restoring the gradient, or by dropping the shadow and leaving the ink bare.
    """
    page = TMPL.read_text(encoding="utf-8")
    block = page.split(".art .nm{")[1].split("}")[0]
    assert "text-shadow" in block, "the action caption has no halo and sits bare on the picture"
    assert "background" not in block, (
        "the action caption has a background again -- the scrim was removed on purpose")


def test_the_caption_takes_all_four_of_its_measurements_from_geo(gen):
    """The row holds in geometry.py and can still break in the page.

    capLh was exported for a long time and never applied, so the caption silently took the body's
    1.4 while CAP_H was computed from 1.2. That cost nothing while the caption stood alone. It
    costs the row the moment Take Tithe shares its line, because the Tithe label IS given its line
    height and the caption would not be -- two line heights, one row, visibly out. Falsified by
    dropping any of the four, which is exactly how the first one went missing.
    """
    page = TMPL.read_text(encoding="utf-8")
    body = page.split('nm.className = "nm"')[1].split("art.appendChild(nm)")[0]
    for key in ("GEO.art.capSize", "GEO.art.capLh", "GEO.art.capPadY", "GEO.art.capPadX"):
        assert key in body, "the action caption no longer takes %s from GEO" % key


def test_the_city_states_no_numbers_of_its_own(gen):
    """The last place in the template that still carried geometry. Falsified by typing one back."""
    page = TMPL.read_text(encoding="utf-8")
    body = page.split("var c = GEO.city;")[1].split("\n}")[0]
    body = re.sub(r"(?m)^\s*//.*$", " ", body)
    stray = re.findall(r"(?<![\w.#-])(\d{2,4})(?![\w.%])", body)
    assert not stray, "the City has %s typed into it" % ", ".join(stray)


def test_the_folders_a_walk_must_skip_have_one_owner(gen):
    """`seals` was taught to this tool and not to the layout lab, which then drew a wax seal of
    78 pixels as Clerical's 590 x 295 action card.

    Three generators walk duty_actions/ and a fourth place -- tests/layout_lab -- has to permit
    exactly the same folders. Each carried its own copy of the word "masters", so the first time
    the list grew, three of the four were wrong. attribution.json owns it now.

    Falsified by hard-coding the list back into any of them, or by writing a seal somewhere the
    list does not name: the walk would then inline it as card art.
    """
    doc = json.loads(gen.ATTRIB_FILE.read_text(encoding="utf-8"))
    listed = doc.get("nonSlotFolders")
    assert listed, "attribution.json no longer says which folders are not actions"
    # EVERY MARK FOLDER, not just the one this tool falls back to. `icons` arrived beside
    # `seals` and the two lists are kept separately on purpose -- a non-slot folder need not hold
    # a mark -- so the containment is asserted rather than derived. Falsified by adding a mark
    # folder and forgetting that every walk now has to step over it, which would put a 78px icon
    # through bundled_art as a 590 x 295 card.
    missing = [f for f in gen.mark_folders() if f not in listed]
    assert not missing, (
        "marks live in %s and the walks are not told to skip them" % ", ".join(missing))
    assert gen.MARK_SUBDIR in gen.mark_folders(), "the fallback folder is not a mark folder"
    assert "masters" in listed, "the uncropped originals are not named as a non-slot folder"
    assert tuple(gen.non_slot_folders()) == tuple(listed), "the reader and the file disagree"
    # And no slot folder may share a name with one, or a duty's art would vanish.
    for duty, slots in doc["slotFolders"].items():
        clash = set(slots.values()) & set(listed)
        assert not clash, "%s has an action in %s, which every walk is told to skip" % (
            duty, ", ".join(sorted(clash)))


def test_a_seal_never_becomes_the_answer_to_where_a_slot_keeps_its_art(gen):
    """A seal is recorded as `left` or `right` under its duty, exactly like a picture is.

    So the scan that asks "where does this slot keep its art" found Give Alms' seal and answered
    "seals" -- and that answer is what the save uses to decide where to WRITE a 590 x 295 card.
    Every duty that got its seals before its artwork had the same hole. Falsified by removing the
    non-slot skip from slot_folder.
    """
    doc = json.loads(gen.ATTRIB_FILE.read_text(encoding="utf-8"))
    skip = set(gen.non_slot_folders())
    for duty, slots in doc["slotFolders"].items():
        for slot, folder in slots.items():
            got = gen.slot_folder(duty, slot)
            assert got not in skip, "%s %s says its art lives in %r" % (duty, slot, got)
            assert got == folder, "%s %s: the scan says %r and the map says %r" % (
                duty, slot, got, folder)


def test_every_walk_finds_an_image_whatever_it_is_encoded_as(gen):
    """The shipped prints are WebP and the masters are PNG, and the walks looked for "*.png".

    A walk that stops finding the art says nothing -- the board simply draws its placeholders, the
    Tithe column falls back to letters, and the note it prints says the files are MISSING while
    they sit right there. Falsified by narrowing any glob back to one extension.
    """
    want = gen.image_suffixes()
    assert ".png" in want and ".webp" in want, want
    doc = json.loads(gen.ATTRIB_FILE.read_text(encoding="utf-8"))
    assert tuple(doc["imageSuffixes"]) == tuple(want), "the reader and the file disagree"
    # Every recorded file is one this tree can actually open.
    bad = [p for p in doc["files"] if pathlib.Path(p).suffix.lower() not in set(want) | {".svg"}]
    assert not bad, "recorded but unreadable: %s" % ", ".join(bad)


def test_the_masters_are_never_the_lossy_copy(gen):
    """A master is the archive and a lossy archive is not one.

    The prints are WebP at quality 90, which is invisible at the size the board draws and is not
    something to keep the only copy in. Falsified by re-encoding a master.
    """
    board = gen.ATTRIB_FILE.parent
    lossy = sorted(p.relative_to(board).as_posix()
                   for p in board.glob("duty_actions/*/seals/masters/*")
                   if p.suffix.lower() not in (".png",))
    lossy += sorted(p.relative_to(board).as_posix() for p in board.glob("tokens/masters/*")
                    if p.suffix.lower() not in (".png",))
    assert not lossy, "masters that are not PNG: %s" % ", ".join(lossy)


def test_a_single_mark_stands_on_the_same_line_as_everyone_elses_first(geo):
    """Falsified by centring the one-action tile's mark in the space under its name.

    Taxation and Allocation have one action each. Centring theirs put it half a mark below the
    top mark of every tile beside them, and on a ribbon of eight that reads as two tiles done
    wrong rather than as two tiles that are different. The column hangs from the name, so where a
    mark sits stops depending on how many the tile holds -- and this is the assertion that says
    so, because every other guard here is satisfied by a mark that is merely inside its tile.
    """
    one = geo.seal_slots(1)[0]
    first_of_two = geo.seal_slots(2)[0]
    assert one["y"] == first_of_two["y"], (
        "a single mark sits at y=%d and a first-of-two at y=%d" % (one["y"], first_of_two["y"]))
    assert one["x"] == first_of_two["x"], (
        "a single mark sits at x=%d and a first-of-two at x=%d" % (one["x"], first_of_two["x"]))


def test_the_tile_is_the_plate_seen_through_glass_and_the_mark_adds_nothing_behind_itself(gen):
    """Falsified by painting a ground behind a mark again, or by making the tile opaque.

    THE NAME OF THIS TEST HAS CHANGED TWICE AND BOTH TIMES FOR THE SAME REASON: the claim kept
    outliving its own wording. It was "the same purple" when the plate was purple; then "the same
    plate the marks are grounded on" when the plate went slate and a mark still had a ground. A
    mark has no ground now, so being grounded on the same thing is not a claim any more.

    WHAT SURVIVES IS ONE FACT ABOUT THE TILE. It is --plate at --tile-alpha: the plate's colour,
    seen through glass, with the backdrop behind it. That is what makes a ground behind a mark
    wrong rather than merely unnecessary -- there is no single colour for one to match, at any
    height of any tile, so it would draw a square wherever it stopped agreeing.

    AND THE MARK ADDS NOTHING. A cutout is the emblem on transparency; it needs no field, and the
    board gives it none. Both grounds, selected and not, are asserted in
    test_a_selected_tile_catches_light_and_its_marks_bring_no_ground_of_their_own; what is
    asserted here is only that the RULES exist to say so, so that neither tile can silently fall
    back to the other's.
    """
    page = TMPL.read_text(encoding="utf-8")
    assert "--plate:" in page, "the plate's colour is no longer named on :root"
    import re as _re
    tile = _re.search(r"^\.tile\{([^}]*)\}", page, _re.M | _re.S)
    assert tile, "the tile has no rule of its own"
    assert "var(--plate)" in tile.group(1), (
        "the duty tile is not drawn from the plate: %s" % " ".join(tile.group(1).split()))
    assert "--tile-alpha" in tile.group(1), (
        "the tile is opaque again, so the backdrop behind it cannot be seen at all: %s"
        % " ".join(tile.group(1).split()))
    assert _re.search(r"\n\.seal\.plate\{", page), "the mark's ground has no rule of its own"
    assert ".tile.sel .seal.plate{" in page, (
        "the selected tile's ground has no rule of its own, so it keeps the unselected one and "
        "the square comes back the moment the tile stops being that colour")


def test_a_duty_can_be_picked_from_the_wheel_as_well_as_the_ribbon(gen):
    """Falsified by wiring the face to anything but pickDuty, or by leaving it unclickable.

    A duty tile and a wheel face are two handles on ONE duty. The tile could already be clicked
    and the face could not -- it carried a hover highlight and `cursor: default`, which is a thing
    that lights up under the pointer and then refuses to be pressed. Both go through pickDuty, so
    the selection, the action cards and the wheel all follow from one piece of state rather than
    from whichever handle was used.
    """
    page = TMPL.read_text(encoding="utf-8")
    assert "#wheel path[data-face]{cursor:pointer" in page, (
        "the wheel's faces are not offered as clickable")
    wheel = page.split("function drawWheel()")[1].split("function drawFigures()")[0]
    assert "pickDuty(slug)" in wheel, (
        "a wheel face does not go through pickDuty, so the two handles can disagree")


def test_picking_a_duty_lights_it_on_the_wheel_and_in_the_ribbon(gen):
    """Falsified by painting the tile's selection and not the wheel's, which is where it started.

    `sel` on the tile has existed since there was a board; the face had no selected state at all,
    so picking a duty lit the ribbon and left the wheel saying nothing. Both are now set from the
    SAME loop -- two loops would be two answers the first time one of them was edited, which is
    the rule lightFace() already states for the hover pair.
    """
    page = TMPL.read_text(encoding="utf-8")
    assert '#wheel path[data-face].sel{' in page, "the wheel face has no selected state"
    # SELECTION AND HOVER HAVE TO BE TELLABLE APART. Both light the face; while you hover one face
    # with another selected, identical highlights would leave the board showing two and saying
    # which is which nowhere.
    sel = page.split('#wheel path[data-face].sel{')[1].split('}')[0]
    assert "stroke:" in sel, (
        "a selected face is only brightened, so it is the same picture as a hovered one")
    # ONE LOOP, BOTH PAINTED.
    i = page.index('tile.classList.toggle("sel", d.slug === S.duty)')
    nearby = page[i:i + 600]
    assert 'face.classList.toggle("sel", d.slug === S.duty)' in nearby, (
        "the wheel's selection is not painted beside the tile's, so they can drift apart")


def test_the_controls_are_one_column_of_marks_and_the_old_buttons_are_gone(geo, gen):
    """Five objects became one, and the half-done version of that change still renders.

    WHAT THIS REPLACES. There were three Confirm buttons -- one under each action card, one under
    the Tithe, only ever one of them visible -- and two standing buttons, Show Map and Hire
    Building, in the side column. They are now three marks in a column at the working edge. The
    confirm row's 64px went to the road, which is why nothing below the ribbon moved.

    THE FAILURE IT CATCHES IS A HALF-DONE REMOVAL. A template still reading GEO.confirm against a
    geometry that no longer publishes it throws inside a draw function, and the board comes up
    with everything before the throw drawn and everything after it missing -- a page that looks
    like a layout bug rather than an error. So both sides are asserted: geometry publishes the
    column and not the old objects, and the template draws from the column and names none of them.
    """
    page = TMPL.read_text(encoding="utf-8")
    code = re.sub(r"/\*.*?\*/", " ", page, flags=re.S)
    code = re.sub(r"<!--.*?-->", " ", code, flags=re.S)
    code = re.sub(r"(?m)^\s*//.*$", " ", code)

    # GEOMETRY'S SIDE. The column is published whole -- its slots, its order and its size -- so
    # the page has nothing left to work out.
    marks = geo.as_dict()["marks"]
    assert list(marks["order"]) == list(geo.MARKS_ORDER), "the column's order is not geometry's"
    # A CONTROL IS A TILE'S MARK, FULL STOP. This used to be SEAL - 2*SEAL_BORDER: a mark on a
    # tile wore a frame and was border-box, so it showed that much artwork, and a control with no
    # frame had to be that size to come out the same. Neither wears a frame now, so the correction
    # has nothing left to correct and the two are one number -- which is the better state, since a
    # subtraction that evaluates to the thing it is subtracted from is a trap waiting for whoever
    # next changes one side of it.
    # READ OFF THE RECTS, because the rects are the only place the size is published. It was also
    # published as a bare `size` beside them for a while and read by nobody -- one number stated
    # twice, which is how two numbers start.
    for name in marks["order"]:
        assert marks[name]["width"] == marks[name]["height"] == geo.MARK, (
            "%s is not a MARK-sized square" % name)
        assert marks[name]["width"] == geo.SEAL, (
            "a control is %d and a tile's mark is %d" % (marks[name]["width"], geo.SEAL))
    assert "size" not in marks, (
        "the column's size is published beside the rects as well as in them, so the two can drift")
    # AND IT STANDS ON ALLOCATION'S, to the pixel. This is the claim the section is built on: the
    # column is the eighth tile's artwork carried down, not merely near it or centred under it.
    # ASKED OF tile_x(), which is two steps from the pitch now: the column, then the tile centred
    # in it, then the mark centred in the tile. Adding BORDER to the pitch directly -- which is
    # what this did -- lands 40 to the left of the mark and calls a correct board broken.
    art_x = geo.tile_x(geo.TILES - 1) + geo.BORDER + geo.seal_slots(1)[0]["x"]
    for name in marks["order"]:
        assert marks[name]["x"] == art_x, (
            "%s is at %d and Allocation's artwork at %d" % (name, marks[name]["x"], art_x))
    # THE AIR BETWEEN THEM IS THE AIR A TILE KEEPS BETWEEN PICTURES, and that is now the same 6
    # the boxes are apart. It was SEAL_INSET plus the two frames the pair spent -- 10 of clear
    # space between two framed pictures where the boxes were 6 apart -- and matching the 6 back
    # then matched the arithmetic and not the eye, which the column did at first. With no frames
    # the clear space and the box gap are the same number again.
    # AND IT IS MEASURED BETWEEN THE BOXES, which is the change. It used to be between the marks,
    # because a mark was all there was; each one now stands in a .panel of its own, so the gap
    # the eye sees is box to box and the marks sit a pad further apart than they look. Measured
    # on the marks this reads 18 and means nothing.
    #
    # AND ONLY WITHIN THE STANDING PAIR. The commit is deliberately far below -- check() holds
    # that distance to GAP_WIDE, and it is what makes its arrival read as news -- so a loop over
    # all three would be asserting the two-group layout away.
    boxes = [marks[n]["box"] for n in marks["order"]]
    for a, b in zip(boxes[:-2], boxes[1:-1]):
        air = b["y"] - (a["y"] + a["height"])
        assert air == geo.SEAL_INSET, (
            "two standing control boxes are %d apart and a tile keeps %d of clear air"
            % (air, geo.SEAL_INSET))
    # AND THE OLD OBJECTS ARE NOT STILL THERE UNUSED. A rect left in as_dict() with nothing
    # drawing it is the state this page spent a version in before anyone noticed.
    published = geo.as_dict()
    for gone in ("confirm", "showMap", "hire", "standing"):
        assert gone not in published, (
            "geometry still publishes %r, so something can still be drawing it" % gone)
    for gone in ("CONFIRM_Y", "CONFIRM_H", "STANDING_H", "HIRE_Y", "MAP_Y", "confirm_for"):
        assert not hasattr(geo, gone), "geometry still carries %s" % gone

    # THE TEMPLATE'S SIDE. Drawn from the published slots, by the published order.
    body = code.split("function drawMarks()")[1].split("\nfunction ")[0]
    assert "M.order.forEach" in body, (
        "the column is not drawn by geometry's own order, so a fourth mark would need an edit here")
    assert "box(at)" in body, "a mark is not placed at the rect geometry gives it"
    # NOT REBUILT HERE. The stack is one multiplication, which is exactly the kind of arithmetic
    # that gets retyped into a drawing and then disagrees with the module that owns it.
    for sign in ("GEO.marks.size", "SEAL", "+ i *", "* (", "inset"):
        assert sign not in body.replace("M.order", ""), (
            "drawMarks() is working the column out rather than reading it: %r" % sign)

    # ONLY THE COMMIT SPEAKS. A board where all three marks make the confirm sound teaches that
    # the sound means "pressed" rather than "committed", which is the one thing it is for.
    assert body.count('sfx("confirm")') == 1, (
        "%d marks play the confirm cue" % body.count('sfx("confirm")'))
    assert "name === COMMIT" in body, "the cue is not bound to the commit mark in particular"

    # THERE IS NO FRAME, AND THE WAY THAT IS HELD HAS TURNED OVER. The frame used to be geometry's
    # number -- SEAL_BORDER set a border in the stylesheet and a WIDTH in the column -- so this
    # asserted that the rule read var(--seal-border) rather than a typed 2px, because two owners
    # of one fact meant the border could move while the column went on being sized off the old
    # value: a page that renders perfectly with the control no longer equal to the artwork.
    #
    # NOW THE FACT IS THAT THERE IS NO NUMBER AT ALL, so what has to be asserted is the absence,
    # at both ends: the stylesheet must not grow a border back, and geometry must not go on
    # publishing one for it to grow back FROM. A leftover sealBorder in the ribbon dict is the
    # half-done state this whole test exists to catch.
    rule = decls_for(page, ".seal.filled")
    assert re.search(r"border:\s*0", rule), "the mark's frame is back: %r" % rule
    assert not re.search(r"border(-\w+)?:\s*[1-9]", rule), (
        "the mark has been given a border width again: %r" % rule)
    assert "--seal-border" not in code, (
        "the page still carries --seal-border, so a frame can come back in one line")
    assert "sealBorder" not in json.dumps(geo.as_dict()), (
        "geometry still publishes sealBorder, which is a frame width for a mark that has no frame")

    # AND NOTHING IN THE PAGE STILL REACHES FOR WHAT GEOMETRY DROPPED.
    for gone in ("GEO.confirm", "GEO.showMap", "GEO.hire", "GEO.standing", "fitConfirm",
                 "btn standing", "confirm-tithe"):
        assert gone not in code, (
            "the page still uses %r, which geometry no longer publishes" % gone)


def test_each_control_draws_its_own_mark_and_says_so_when_it_cannot(geo, gen):
    """Three emblems that were one borrowed emblem, and a fallback that has to stay honest.

    WHAT THIS REPLACES. The column drew Allocation's mark three times while the real icons were
    being made. That was right -- an empty column looks finished and a wrong emblem does not --
    and it is exactly the kind of scaffolding that gets left in, because the board goes on
    rendering beautifully either way and nobody is told which of the three pictures is a stand-in.

    SO BOTH HALVES ARE ASSERTED: the cuts are bundled and drawn, AND the fallback is still there
    for a mark with no cut, AND a mark using it is drawn differently so you can see which.

    Falsified by hard-coding the three keys in the template, which would pass the drawing and lose
    the fallback; or by dropping the stand-in class, which loses nothing you can see until the day
    somebody ships a column with two real marks and one borrowed one.
    """
    page = TMPL.read_text(encoding="utf-8")
    body = page.split("function drawMarks()")[1].split("\nfunction ")[0]

    # EACH MARK ASKS FOR ITS OWN, BY ITS OWN NAME. Built from the loop variable rather than
    # listed, so a fourth control needs no edit here and cannot be half-wired.
    #
    # ON THE ASSIGNMENT, NOT ON THE WHOLE FUNCTION, and that distinction is the test. Written as
    # `"..." in body` this passed while the drawing was `var src = placeholder` -- because the
    # control key still appeared further down, in the line that marks a stand-in, and a substring
    # search cannot tell a value that is USED from one that is merely mentioned. Both halves of
    # the fallback have to be in the expression that actually decides the picture.
    m = re.search(r"var src = ([^;]+);", body)
    assert m, "drawMarks() no longer decides a src in one place"
    chooses = m.group(1)
    assert 'IMAGES["control:" + name]' in chooses, (
        "a control does not draw its own art -- src is %r" % chooses)
    assert "placeholder" in chooses, (
        "a control with no cut yet would draw nothing at all -- src is %r" % chooses)
    assert re.search(r"var placeholder = IMAGES\[", body), "the placeholder is not looked up"

    # AND THE GENERATOR ACTUALLY BUNDLES THEM. The template could ask for a key nothing supplies
    # and the board would quietly draw three placeholders -- which is what it did before this.
    images, notes = gen.bundled_controls()
    for name in geo.MARKS_ORDER:
        assert "control:%s" % name in images, (
            "the generator bundles no art for the %s mark: %s" % (name, notes))
        assert images["control:%s" % name].startswith("data:image/png;base64,"), name
    assert len(set(images.values())) == len(geo.MARKS_ORDER), (
        "two controls are bundled with the same bytes, so one of them is the other's picture")

    # A STAND-IN IS MARKED AND LOOKS LIKE ONE.
    assert 'classList.toggle("stand-in"' in body, (
        "a control falling back to the placeholder is not marked, so the board cannot show "
        "which of its marks is still borrowed")
    assert ".mark.stand-in{" in page, (
        "the stand-in class has no rule, so marking it changes nothing a person can see")

    # THE WORDING IS duty_text.json'S. A `labels` object typed into the page is the fault that
    # file exists to end, and the icon lab reads the same three strings for its card titles.
    assert "CONTROLS[name]" in body, "the controls' names are not read from the shared wording"
    for typed in ('"Show Map"', '"Hire Building"', '"Confirm"'):
        assert typed not in page, (
            "%s is typed into the template again, so it can differ from duty_text.json" % typed)
    said = gen.control_text()
    assert [said[k]["name"] for k in geo.MARKS_ORDER] == ["Show Map", "Hire Building", "Confirm"]


def test_an_unrecorded_control_is_left_out_and_named(gen, tmp_path, monkeypatch):
    """The record gates a control exactly as it gates every other picture on this board.

    Falsified by bundling whatever is in the folder, which survived the first pass of mutations
    here: an icon somebody dropped in and never recorded would be drawn, and the column would look
    finished with a picture nobody can say the provenance of. The board's own rule is that art
    without a record is left out and NAMED -- and a column of three is not an exception to it.
    """
    icons = tmp_path / "controls" / "icons"
    icons.mkdir(parents=True)
    from PIL import Image
    for key in ("map", "hire"):
        Image.new("RGBA", (40, 40), (9, 9, 9, 255)).save(icons / ("control_%s_icon_v01.webp" % key))
    attrib = tmp_path / "attribution.json"
    attrib.write_text(json.dumps({"imageSuffixes": [".png", ".webp"], "files": {
        "controls/icons/control_map_icon_v01.webp": {"slot": "control"}}}), encoding="utf-8")
    monkeypatch.setattr(gen, "CONTROL_DIR", icons)
    monkeypatch.setattr(gen, "ATTRIB_FILE", attrib)

    images, notes = gen.bundled_controls()
    assert list(images) == ["control:map"], images
    assert any("control_hire_icon_v01.webp" in n and "no attribution entry" in n
               for n in notes), notes
    # AND THE COMMIT, WHICH HAS NO FILE AT ALL, is reported rather than passed over in silence --
    # that is the difference between a mark that falls back and a mark nobody noticed was missing.
    assert any("commit" in n and "placeholder" in n for n in notes), notes


def test_a_control_without_wording_stops_the_build(gen, tmp_path, monkeypatch):
    """Falsified by falling back to the key, which is invisible on the board.

    The emblem is the same whether or not the mark has a name -- the name is the title and the
    alt text -- so a missing one shows up in a screen reader and a tooltip nobody checks, which
    is to say never. The build is the only place it can be noticed.
    """
    bad = tmp_path / "duty_text.json"
    full = json.loads(TEXT.read_text(encoding="utf-8"))
    full["controls"].pop("commit")
    bad.write_text(json.dumps(full), encoding="utf-8")
    monkeypatch.setattr(gen, "TEXT_FILE", bad)
    with pytest.raises(SystemExit) as e:
        gen.control_text()
    assert "commit" in str(e.value), "the refusal should name the mark that has no wording"


def test_a_blended_overlay_is_isolated_to_what_it_is_blending_with(gen):
    """A mix-blend-mode element blends with its nearest STACKING CONTEXT, not with its parent.

    WHAT WENT WRONG. Each action card carries a `lift` overlay at mix-blend-mode:screen, to raise
    the flames in that card's own picture. `.art` is position:absolute with z-index:auto, which
    does NOT open a stacking context -- so the overlay was blending against everything painted
    beneath it across the whole board: the backdrop valley, the road, the ribbon. The effect was
    reaching outside the card it belongs to, and nothing looked obviously wrong, because screening
    a 4%-opacity warm wash over a dark backdrop looks much like screening it over a dark picture.

    WHAT MADE IT VISIBLE was the flicker. A blending group spans its whole stacking context and has
    to be rasterised together, so anything that changes compositing elsewhere on the board -- a
    tile taking its hover transform, a control animating its filter -- invalidates it. Both cards
    flashed while it was rebuilt: a black rectangle on each side of the action row, on every hover.

    THE GUARD IS GENERAL, not a note about this one overlay. Any rule that blends has to have its
    container isolated, and the container is the selector it hangs off. A second blended overlay
    added later gets the same check without anybody remembering this.

    Falsified by dropping `isolation:isolate` from .art, which is the whole fix and reads like a
    tidy-up.
    """
    page = TMPL.read_text(encoding="utf-8")
    css = page.split("<style>")[1].split("</style>")[0]
    css = re.sub(r"/\*.*?\*/", " ", css, flags=re.S)

    blended = [m.group(1).strip() for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css)
               if "mix-blend-mode" in m.group(2)]
    assert blended, "nothing blends any more -- has the lift overlay gone?"
    for sel in blended:
        parts = sel.split()
        assert len(parts) > 1, (
            "%r blends and is not inside anything, so it blends with the whole page" % sel)
        holder = parts[0]
        rules = [m.group(2) for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css)
                 if m.group(1).strip() == holder]
        assert rules, "%r blends inside %s and there is no rule for %s" % (sel, holder, holder)
        body = " ".join(rules)
        assert "isolation:isolate" in body.replace(" ", ""), (
            "%s blends, and %s does not isolate -- so it blends with everything painted under "
            "the board rather than with its own card" % (sel, holder))


def test_the_commit_appears_only_when_there_is_something_to_commit(geo, gen):
    """It is the confirm button, so it keeps the confirm button's one behaviour.

    The three it replaced were drawn `display:none` until their own slot was chosen -- one under
    each card, one under the Tithe. Collapsing them into a single mark at the end of the row made
    it easy to lose that: a mark that is always there reads as a button that is always pressable,
    on a board whose whole grammar is choose-then-confirm, and it would offer to commit nothing.

    Map and Hire are NOT gated: they are standing offers, available whatever is chosen.

    Falsified by drawing all three unconditionally, which is how the column was first built, or by
    gating on the wrong thing -- the duty rather than the slot -- which looks right on a one-action
    duty and is wrong on the other six.
    """
    page = TMPL.read_text(encoding="utf-8")
    code = re.sub(r"(?m)^\s*//.*$", " ", re.sub(r"/\*.*?\*/", " ", page, flags=re.S))

    # THE NAME IS NOT TYPED TWICE. Two rules turn on which mark commits -- its cue and whether it
    # shows -- and the second arrived much later, which is when a second copy gets written.
    m = re.search(r'var COMMIT = "([a-z]+)"', code)
    assert m, "the commit mark is not named once"
    assert m.group(1) in geo.MARKS_ORDER, (
        "the template commits %r and geometry's marks are %s" % (m.group(1), geo.MARKS_ORDER))
    assert code.count('"commit"') == 1, (
        "the commit's name is written into the page more than once, so the two can disagree")

    # GATED ON THE SLOT, in render(), where everything else that follows the selection is set.
    body = code.split("function render()")[1].split("\nfunction ")[0]
    g = re.search(r'getElementById\("mark-" \+ COMMIT\)\.classList\.toggle\("off", ([^)]+)\)',
                  body)
    assert g, "render() does not show or hide the commit mark"
    assert g.group(1).strip() == "!S.slot", (
        "the commit is gated on %r rather than on whether a slot is chosen" % g.group(1).strip())
    assert ".mark.off{display:none}" in page.replace(" ", ""), (
        "the off class has no rule, so the commit is always on show")
    # AND NOTHING GATES THE OTHER TWO.
    for other in [n for n in geo.MARKS_ORDER if n != m.group(1)]:
        assert ('"mark-%s"' % other) not in body, (
            "render() touches the %s mark, which is a standing offer and should always show"
            % other)


def test_a_control_is_a_button_and_a_tile_mark_is_a_choice(gen):
    """The two look alike and must not read alike.

    A mark on a duty tile wears a dashed border that firms up when you hover or choose it: the
    border is the SLOT, and the thing inside it is an action you select. The three controls are
    the same artwork at the same size with no border at all, because they are pressed rather than
    chosen. Give them the tile's edge and the board grows three more selectable-looking squares
    in a grammar that is entirely select-then-confirm.

    Falsified by drawing a control with class `seal filled`, which is the obvious way to get the
    sizing for free and the exact mistake that would cost the distinction.
    """
    page = TMPL.read_text(encoding="utf-8")
    body = page.split("function drawMarks()")[1].split("\nfunction ")[0]
    assert '"mark"' in body, "a control is not drawn as a mark"
    # THE CLASS, NOT THE WORD. The placeholder is borrowed from a duty tile and its key is
    # "seal:allocation:actionA", so a bare substring test here fails on the thing it is meant to
    # allow. What must not appear is `seal` as a CLASS -- which is "seal" or "seal filled", never
    # followed by a colon.
    assert not re.search(r'"seal(?!:)', body), (
        "a control is drawn with the duty tile's seal class, so it wears the slot's dashed edge "
        "and reads as something you select")
    rule = page.split(".mark{")[1].split("}")[0]
    assert "border" not in rule, "the controls column has a frame, which is not what was asked for"
    # AND THE HOVER MOVES NOTHING. Same box, same place: these sit at geometry's rect and are
    # border-box, so an edge appearing under the pointer would shift the artwork inside it.
    hov = page.split(".mark:hover{")[1].split("}")[0]
    for moves in ("border", "width", "height", "transform", "padding", "margin"):
        assert moves not in hov, (
            "hovering a control changes %s, so the drawing inside it moves" % moves)


def test_the_phase_row_is_rebuilt_rather_than_added_to():
    """drawPhases() is its own click handler, so it must clear before it appends.

    WHAT HAPPENED WITHOUT THIS. Every click on Ready / City, Sowing or Action Selection appended
    a second set of three buttons, so the row grew by three each time. The real damage was
    quieter: a loop at the end of the function walked holder.children -- six, then nine -- against
    GEO.phases[i], which is three, threw on the undefined, and took note() and setStatus() down
    with it. The phase line and the placeholder note therefore stopped updating the moment the
    first duplicate appeared, which is the kind of thing that reads as "the phases do nothing"
    rather than as an error.

    A STATIC CHECK, AND IT SAYS SO. The lab lane installs no browser, so this reads the template
    rather than clicking the button; the behaviour itself was verified by driving the built page.
    Falsified by deleting the clear, or by putting the second aria-pressed pass back.
    """
    page = TMPL.read_text(encoding="utf-8")
    body = page.split("function drawPhases()")[1].split("\nfunction ")[0]
    code = re.sub(r"(?m)^\s*//.*$", "", body)

    assert re.search(r'holder\.(textContent\s*=\s*""|innerHTML\s*=\s*""|replaceChildren\(\))', code), (
        "drawPhases() appends into #phases without emptying it first, so every click adds "
        "another set of phase buttons")
    assert code.index("holder.appendChild") > code.index("holder."), (
        "the clear has to come before the appends")
    assert "GEO.phases[i]" not in code, (
        "the second aria-pressed pass is back: it indexes GEO.phases by a holder.children index, "
        "which throws as soon as the two lengths disagree")
    assert code.count('setAttribute("aria-pressed"') == 1, (
        "aria-pressed is set in more than one place, so the two can disagree")


# =================================================================================================
# THE ONE NUMBER THAT CAN BE SET AT LAUNCH
#
# geometry.configure() exists so a mark size can be tried without editing geometry.py and
# remembering to put it back. These load their own copy of the module, because configure()
# reassigns module globals and the `geo` fixture is module-scoped -- a test that configured the
# shared one would quietly change the board every test after it measures.

# test_the_tithe_tokens_move_with_the_tile_marks IS GONE WITH THE THREE RESOURCES. It held one
# lever to two sizes: a flag that resized the eight tiles' marks and left the Tithe's discs where
# they were reads as a layout fault rather than as a setting, so configure() had to move TOKEN
# with SEAL, and above the box's cap the lever had to stop at the box rather than run past it.
#
# THE CLAIM IT MADE HAS NOT GONE, ONLY ITS SECOND SUBJECT. "One lever moves everything on the
# mark's chain" is now test_setting_the_mark_size_moves_everything_derived_from_it_and_nothing_
# else, which derives that chain from the source instead of listing it -- so the tile, which took
# the discs' place as the thing that must move with the mark, is covered without anybody
# remembering to add it.


def test_a_mark_too_big_for_the_tile_is_refused_rather_than_drawn():
    """The ribbon does not grow to fit a bigger mark -- it overflows, and check() is what says so.

    This is the guard the --icons flag leans on instead of doing its own arithmetic, which is why
    it is asserted here rather than trusted. Falsified by making configure() grow RIBBON_H, or by
    check() forgetting the tile.

    THE THRESHOLD IS DERIVED, NOT TYPED. It used to be 110, a round number above a RIBBON_H of
    242. RIBBON_H is now computed from the mark it has to hold, so a typed 110 would have gone on
    passing while testing a size far further over the line than it claimed.

    AND THERE ARE TWO THRESHOLDS, WHICH IS WHAT WRITING IT THIS WAY FOUND. The mark stops keeping
    the tile's rhythm at 73 and does not actually leave the tile until 76, so for three sizes the
    board drew a tile that was visibly wrong and check() said nothing. Both are asserted, and
    separately, because a single "it complains" would be satisfied by either.
    """
    g = _load("geometry")
    assert g.check() == [], "the default board is not sound, so this test proves nothing"
    # THE TILE IS NO LONGER EXACTLY AS TALL AS WHAT IT HOLDS, and that is a decision rather than a
    # drift. This read `SEAL == fits` -- the default mark was the biggest the tile would take at
    # the tile's own rhythm, because RIBBON_H was derived from the mark. The mark went to 50 and
    # the tile KEPT its height, so there are 22 of headroom and the two numbers have come apart.
    #
    # WHAT IS ASSERTED INSTEAD IS THE DIRECTION, which is the half that matters to this test: the
    # board's mark must be one the tile takes. Equality would now fail on a deliberate choice;
    # dropping the line altogether would let the default drift over the thresholds below and
    # leave them measuring a board that was already broken.
    fits = (g.RIBBON_H - (g.TILE_Y - g.RIBBON_Y) - g.SEAL_INSET - 2 * g.TILE_PAD) // 2
    assert g.SEAL <= fits, (
        "the band holds a mark of %d and the board draws %d, so the default board is over the "
        "first threshold before this test starts" % (fits, g.SEAL))

    # ONE PIXEL OVER, AND THE BAND IS WHAT IT IS OVER. The complaint used to be about the TILE:
    # a mark could crowd its box and then leave it, two thresholds three pixels apart, and the
    # board was visibly wrong for the sizes in between while check() said nothing. Neither can
    # happen now -- the tile is DERIVED from the mark, so a mark can no more overflow its tile
    # than a hand can outgrow its glove. What it can still outgrow is the band the tile hangs in,
    # which is declared, and that is the one threshold left.
    g.configure(seal=fits + 1)
    bad = g.check()
    assert any("past the band" in line for line in bad), (
        "a %d px mark asks for a tile taller than the band and check() did not say so: %s"
        % (fits + 1, bad))

    # AND FAR OVER IT, which is the complaint the --icons flag quotes back. Asserted separately
    # from the pixel above because a guard that only fires at the boundary and a guard that only
    # fires far past it are different guards, and "it complains" would be satisfied by either.
    g.configure(seal=fits * 2)
    bad = g.check()
    assert any("past the band" in line for line in bad), (
        "a %d px mark is far past the band and check() did not notice: %s" % (fits * 2, bad))
    # THE TWO THRESHOLDS THAT WENT, recorded because losing a guard quietly is how the next one
    # gets lost. The second was "the mark spans the tile", and it has no case left to catch: the
    # tile grows with the mark, so seal_slots() keeps the pair inside its box at every size. The
    # guard is still in check() -- it costs nothing and it is the thing that would notice
    # seal_slots() and the tile's derivation disagreeing -- but nothing drives it from here.
    # NOT JUST "A LINE SAYING spans". The controls column has a complaint of its own at this size
    # and it says "spans" too, so a looser match reported the tile guard firing when it was the
    # column's -- which is the same fault this test's old version was written against, met from
    # the opposite side.
    assert not any("spans" in line and "inside a tile" in line for line in bad), (
        "a mark has left its own tile, which the tile being derived from it should make "
        "impossible: %s" % bad)


def test_a_pair_hung_from_the_name_instead_of_centred_is_refused(monkeypatch):
    """The other half of the tile's complaint, which no mark size can reach.

    check() minds two different things about the pair -- that it is centred in the room under the
    name, and that it keeps at least the tile's own inset at both ends -- and the test above walks
    the mark size up until the SECOND one fires. The first cannot be reached that way at all:
    seal_slots() centres the pair by construction, so every size it is asked for comes back
    centred, however tight. A mutation run is what found this: breaking the centring condition
    changed no result anywhere, because nothing was asking the question.

    SO THE DERIVATION IS BROKEN DIRECTLY. The placement is replaced with the rule it REPLACED --
    hang the pair one inset below the name and leave the remainder at the foot, which is what this
    did while the tile was exactly as tall as the pair asked for and is wrong now that it is not.
    That is the real regression this complaint guards, and it arrives by somebody editing
    seal_slots(), not by moving the one lever.
    """
    g = _load("geometry")
    assert g.check() == [], "the default board is not sound, so this test proves nothing"

    def hung(n):
        top = g.SEAL_INSET
        out = [{"x": (g.TILE_INNER_W - g.SEAL) // 2, "y": top, "size": g.SEAL}]
        if n == 2:
            out.append({"x": out[0]["x"], "y": top + g.SEAL + g.SEAL_INSET, "size": g.SEAL})
        return out

    monkeypatch.setattr(g, "seal_slots", hung)
    bad = g.check()
    assert any("not centred" in line for line in bad), (
        "the pair hangs from the name with all the spare height at the foot and check() did not "
        "say so: %s" % bad)
    # AND IT IS THE CENTRING THAT COMPLAINED, not the tightness -- the two were one condition and
    # one message until a mark of 73 showed the message naming the wrong fault. A pair hung from
    # the name is roomy at the top and merely lopsided.
    assert not any("tighter than" in line for line in bad), (
        "check() called a roomy pair tight, so the two complaints are back to one: %s" % bad)


def test_a_tile_hung_off_centre_in_its_column_is_refused(monkeypatch):
    """The other centring, and it is unreachable by the one lever for exactly the same reason.

    There are two centrings between the ribbon's pitch and a mark: the tile in its column, and
    the pair in the tile. Both are true by construction -- tile_x() and seal_slots() each divide
    the room in half -- so no mark size can make either fail, and check()'s complaints about them
    look like dead code until something breaks the derivation. A mutation run found this one
    exactly as it found the pair's: disabling the condition changed no result anywhere.

    WHAT THEY GUARD IS THE PAIR OF EXPRESSIONS AGREEING, not the arithmetic of either. tiles()
    places the box and MARKS_X places the controls off the same two divisions; if tile_x() stops
    centring, every mark on the ribbon slides 40 to the left while each box still looks
    correctly drawn, and the controls column goes with them.
    """
    g = _load("geometry")
    assert g.check() == [], "the default board is not sound, so this test proves nothing"
    monkeypatch.setattr(g, "tile_x", lambda i: g.X0 + i * g.TILE_PITCH)
    bad = g.check()
    assert any("from one side of its column" in line for line in bad), (
        "every tile is jammed against the left of its column and check() did not say so: %s"
        % bad)


def _seal_derived(src):
    """Every module-level constant whose value is an expression over SEAL, read off the source.

    WHY THIS IS PARSED RATHER THAN LISTED. The list it replaces was typed -- {"SEAL", "TOKEN",
    "TOKEN_SPREAD"} -- and a typed list of what a lever moves is a list of what somebody
    remembered. Six more constants came to hang off SEAL when the controls column was placed off
    Allocation's mark, configure() went on moving three of them, and the typed list PASSED: it
    was asserting the omission. The board it produced put the column where the old mark had been
    and check() reported a strip of 52 against a margin of 41, which reads as a broken board
    rather than as a flag that did half its job.

    TRANSITIVELY, AND THROUGH CALLS. MARKS_W is MARK is SEAL, so the chain has to be followed; and
    MARKS_X asks seal_slots() rather than naming SEAL at all, so a function that reads SEAL makes
    its callers derived too. Both were real cases here, not hypotheticals.
    """
    import ast
    tree = ast.parse(src)

    def names_in(node):
        return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}

    reads_seal = {f.name for f in tree.body
                  if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))
                  and "SEAL" in names_in(f)}

    derived = {"SEAL"}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        touched = names_in(node.value)
        if not (touched & derived or touched & reads_seal):
            continue
        for t in node.targets:
            # TUPLE TARGETS TOO, which is how two of these slipped through. TILE_INNER_W and
            # TILE_INNER_H are assigned together off one call -- `A, B = inner(...)` -- so the
            # target is a Tuple and not a Name, and a walker that only looked at Names declared
            # them not derived while configure() dutifully moved them. The guard then failed for
            # configure() doing the right thing, which is the most expensive kind of wrong guard.
            for n in (t.elts if isinstance(t, ast.Tuple) else [t]):
                if isinstance(n, ast.Name) and n.id.isupper():
                    derived.add(n.id)
    return derived


def test_setting_the_mark_size_moves_everything_derived_from_it_and_nothing_else():
    """One lever, not a settings system -- but a lever that reaches everything on its own chain.

    Falsified in BOTH directions, which is the point: configure() touching a number that does not
    hang off the mark, and configure() leaving one that does.

    THE SIZE HAS TO BE ONE THEY ALL MOVE FOR. At 70 the Tithe's cap holds TOKEN at 66 where it
    already was, so a size that changed nothing but SEAL would satisfy a subset check and let
    configure() quietly stop moving the token at all. 40 moves every one of them.
    """
    g = _load("geometry")
    want = _seal_derived(pathlib.Path(g.__file__).read_text(encoding="utf-8"))
    assert len(want) > 1, "nothing was found to hang off the mark, so this is testing nothing"

    # DICTS AS WELL AS NUMBERS, which the chain made necessary. ROAD is a rect published as a
    # dict and it is now derived from the mark; a sweep that looked only at ints and floats could
    # not see it move, so the parsed chain named it and the comparison could never contain it --
    # the guard failed for a reason that was its own blind spot rather than configure()'s.
    def snap():
        return {k: (dict(v) if isinstance(v, dict) else v) for k, v in vars(g).items()
                if k.isupper() and isinstance(v, (int, float, dict, tuple))}
    before = snap()
    g.configure(seal=40)
    after = snap()
    moved = {k for k in before if before[k] != after[k]}
    assert moved == want, (
        "configure() moved %s and the mark's own chain is %s -- it left %s standing at the old "
        "size and moved %s that is not derived from the mark"
        % (sorted(moved), sorted(want), sorted(want - moved), sorted(moved - want)))


def test_setting_the_mark_size_to_the_size_it_already_is_changes_nothing():
    """configure() restates its derivations, so this is what holds the two copies together.

    EVERY LINE IN configure() IS A SECOND COPY of an expression the module body already has, and
    two copies of one expression is the shape of fault this file exists to prevent. They are kept
    rather than factored out because each one in the body carries the paragraph that explains it,
    and a function would take the number away from its reason.

    SO THE DUPLICATION IS ASSERTED INSTEAD OF AVOIDED. Setting the mark to the size it already is
    must leave the module byte for byte as it was: if configure()'s copy of MARKS_X ever says
    something different from the body's, this is where the two stop agreeing.
    """
    g = _load("geometry")
    def snap():
        return {k: (dict(v) if isinstance(v, dict) else v) for k, v in vars(g).items()
                if k.isupper() and isinstance(v, (int, float, dict, tuple))}
    before = snap()
    g.configure(seal=g.SEAL)
    after = snap()
    drifted = {k: (before[k], after[k]) for k in before if before[k] != after[k]}
    assert not drifted, (
        "configure() asked for the size the board already draws and changed %s, so its copy of "
        "one of these expressions disagrees with the module's" % drifted)
    assert g.check() == [], "\n".join(g.check())
