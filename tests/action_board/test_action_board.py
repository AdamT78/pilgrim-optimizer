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
    # THE ROW NO LONGER FILLS THE WORKING WIDTH, AND THAT IS THE CHANGE. It used to run X0 to
    # X0 + WORK_W, with the Tithe spanning the last two tiles; it now runs from the FIRST tile's
    # centre to the LAST tile's, so it is hung under the eight rather than butted against them.
    #
    # AND IT NOW ENDS IN THE CONTROLS COLUMN. Cards, gap, cards, gap, Tithe, gap, marks -- the
    # three marks took the row's last 72px and the Tithe paid for them, which is the whole of
    # what "tighten Take Tithe" came to. A row that balanced without the column would mean the
    # marks were hanging off the end of it.
    assert (geo.ART_W * 2 + 2 * geo.ART_GAP + geo.TITHE_W + geo.GAP + geo.MARKS_W) == geo.ROW_W, (
        "the two cards, their gaps, the Tithe and the controls column do not fill the row")
    # BOTH ENDS HANG OFF THE RIBBON: the first tile's centre at the left, and the eighth tile's
    # MARK at the right. It briefly ended at the working edge instead, while the controls column
    # was pinned there -- which made the row's right edge agree with the page rather than with the
    # eight tiles the row belongs to, and left no two emblems on the board sharing an axis.
    assert geo.ROW_X == geo.X0 + geo.TILE_W // 2, (
        "the row no longer starts at the first tile's centre")
    assert geo.ROW_END == geo.MARKS_X + geo.MARKS_W, (
        "the row ends at %d and the controls column at %d"
        % (geo.ROW_END, geo.MARKS_X + geo.MARKS_W))
    # AND IT STOPS SHORT OF THE MARGIN, which is the visible price and the thing somebody will be
    # tempted to "fix" by stretching the Tithe into it. The strip is the tile's own right margin
    # round its mark, carried down -- not a round number, and not nothing.
    assert geo.ROW_END < geo.X0 + geo.WORK_W, (
        "the row reaches the working edge again, so the column is back on the margin")
    # THE CARDS ARE STILL EXACTLY THREE TILES, and that is the assertion the column has to pass.
    # ART_H is half ART_W and the wheel takes what the cards leave, so finding 72px by shaving a
    # few pixels off each card -- the cheap way, and the one that looks harmless in a diff --
    # would have shortened the cards, shortened the row and moved the wheel. The Tithe paid for
    # the whole column instead, which is what "tighten Take Tithe" meant.
    assert geo.ART_W == 3 * geo.TILE_W + 2 * geo.TILE_GAP, (
        "a card is %d wide and three tiles are %d -- the column was paid for out of the cards"
        % (geo.ART_W, 3 * geo.TILE_W + 2 * geo.TILE_GAP))
    assert geo.TITHE_W < geo.TILE_PITCH, (
        "the Tithe is %d and a tile and a gap is %d, so nothing was tightened"
        % (geo.TITHE_W, geo.TILE_PITCH))
    # AND THE CARD IS MEASURED OFF THE RIBBON, which is what makes its edges land on tile edges.
    assert geo.ART_W == 3 * geo.TILE_W + 2 * geo.TILE_GAP, (
        "a card is %d wide, which is not three duty tiles and their two gaps" % geo.ART_W)


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
    the ribbon's HEIGHT, which is a number that can be moved. Falsified by shrinking SEAL until a
    row fits across the tile -- at which point this test says so and the marks should go back in a
    row, because stacking would then be costing ribbon height for nothing.
    """
    assert 2 * geo.SEAL + geo.GAP > geo.TILE_INNER_W - 2 * geo.SEAL_INSET, (
        "two marks and a gap now fit across the tile, so the column is buying nothing")
    a, b = geo.seal_slots(2)
    assert b["x"] == a["x"], "the two marks are not in one column"
    assert b["y"] == a["y"] + geo.SEAL + geo.SEAL_INSET, (
        "the second mark is not one inset below the first")


def test_a_seal_stays_inside_its_tile_and_clear_of_the_duty_name(geo):
    """Falsified by raising SEAL or lowering RIBBON_H: check() names which seal left the box."""
    assert geo.check() == [], "\n".join(geo.check())
    for n in (1, 2):
        for s in geo.seal_slots(n):
            assert s["y"] >= geo.TILE_NAME_BOTTOM
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
    """
    a, b = geo.seal_slots(2)
    above = a["y"] - geo.TILE_NAME_BOTTOM
    below = geo.TILE_INNER_H - (b["y"] + geo.SEAL)
    assert above == below, "%d above the top seal and %d below the lower one" % (above, below)
    assert above == geo.SEAL_INSET, "the seals use a margin of their own again"
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


def test_every_plate_the_board_draws_fills_its_square(geo):
    """The other half of the rule, so neither kind of mark goes unmeasured.

    A plate is trimmed to its own mark and padded to a square, so its longer side spans the slot.
    One that measured well under 1.0 arrived untrimmed and would sit small beside its neighbours --
    which is exactly how the first pair of these came in, at 0.77 and 0.92.

    THIS TEST CAUGHT THE CLASSIFIER, not a picture. On the day it was written every mark in the
    tree failed it, because the generator was deciding disc or plate by looking for an alpha
    channel and a round disc in a square file has one. What is measured here is the silhouette;
    what decides which list a file is in is the record. Keep those two apart.
    """
    pytest.importorskip("numpy")
    pytest.importorskip("PIL")
    _discs, plates = _marks()
    # NO SKIP. The skip that used to be here fired the moment the plates moved folders, and a
    # green run said nothing was wrong. This tree has plates; if it ever genuinely has none, the
    # honest change is to delete this test, not to let it pass by looking away.
    assert plates, ("no mark in %s is recorded as standing on the board's ground, and two are"
                    % ", ".join(_load("generate_action_board").mark_folders()))
    board = ROOT / "ui" / "board_v2"
    bad = []
    for p in plates:
        f = _solid_fraction(p)
        if f < 0.98:
            bad.append("%s fills %.3f of its square; a plate is trimmed to fill it"
                       % (p.relative_to(board).as_posix(), f))
    assert not bad, "\n".join(bad)


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
    one says the thing the list exists to achieve: where a slot has both kinds filed, the icon is
    what the board draws. That is this tree's direction, and when the direction changes this test
    is what you change, on purpose, rather than discovering it later on the board.
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

    both = {k for k, v in kinds.items() if {"seals", "icons"} <= v}
    assert both, "no slot has both a seal and an icon, so this is not yet testing anything"
    _images, by_duty, _notes = gen.bundled_seals()
    wrong = []
    for duty, slot in sorted(both):
        drawn = by_duty.get(duty, {}).get(slot)
        if not drawn or "_icon_" not in drawn[1]:
            wrong.append("%s %s has an icon filed and the board draws %s"
                         % (duty, slot, drawn[1] if drawn else "nothing"))
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
    """
    page = TMPL.read_text(encoding="utf-8")
    css = re.sub(r"/\*.*?\*/", " ", page, flags=re.S)
    for sel in (".seal.filled{", ".tok.filled{"):
        assert sel in css, "%s is gone, so that container draws behind its own artwork" % sel
    code = re.sub(r"(?m)^\s*//.*$", "", page)
    assert 'classList.add("art")' not in code, (
        "a small container is marked `art` again, which is the big card's class")


def test_the_board_draws_the_mark_edge_the_icon_lab_settled_on():
    """Two pages, one rule, and the lab is the one that decides it.

    THE EDGE WAS CHOSEN IN icon_lab/tile_column.html.tmpl -- dashed, in the guides' own colour --
    and the board has to draw the same thing or the lab stops being where that question is
    answered and becomes a page that looks like the board used to. Falsified by giving the board
    a colour of its own, a solid border, or by letting --guide be written out twice.
    """
    page = TMPL.read_text(encoding="utf-8")
    css = re.sub(r"/\*.*?\*/", " ", page, flags=re.S)
    assert re.search(r"--guide:#[0-9a-fA-F]{6}", css), "--guide is not defined at the root"
    assert len(re.findall(r"--guide:#[0-9a-fA-F]{6}", css)) == 1, (
        "the guide colour is written out more than once, so the two rules can disagree")
    m = re.search(r"\.seal\.filled\{([^}]*)\}", css)
    assert m, ".seal.filled is gone"
    assert "dashed var(--guide)" in m.group(1), (
        "the mark's edge is not the guides' dashed line: %s" % m.group(1).strip())
    # AND IT IS THE LAB'S COLOUR, read from the lab rather than copied into this test, so the two
    # files cannot drift apart while both of their own guards stay green.
    lab = (ROOT / "ui" / "board_v2" / "icon_lab" / "tile_column.html.tmpl").read_text("utf-8")
    want = re.search(r"--guide:(#[0-9a-fA-F]{6})", lab).group(1)
    got = re.search(r"--guide:(#[0-9a-fA-F]{6})", css).group(1)
    assert got == want, "the board's guide is %s and the icon lab's is %s" % (got, want)


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

    Falsified by `cover`/`contain`, by giving the strip a background again, or by drawing the
    backdrop after the tiles so it covers them instead.
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

    # DRAWN BEFORE THE TILES, so the board's own order puts it behind them. A z-index would work
    # and would be a second place to look when something covers something else.
    draw = code.split("function draw(")[1].split("\n}")[0]
    assert "drawBackdrop()" in draw, "draw() never draws the backdrop"
    assert draw.index("drawBackdrop()") < draw.index("drawTiles()"), (
        "the backdrop is drawn after the tiles, so it covers them")

    # AND GEOMETRY OWNS WHERE IT GOES. The rect spans the ribbon and the strip together, and
    # check() holds the picture's ground line to the strip -- this asserts the rect reaches both.
    assert geo.BACKDROP["y"] == geo.RIBBON_Y, "the backdrop does not start at the tiles"
    assert geo.BACKDROP["y"] + geo.BACKDROP["height"] == geo.ROAD["y"] + geo.ROAD["height"], (
        "the backdrop does not reach the foot of the road strip")


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

    Falsified by giving the ground a colour or a variable, or by flattening the tile back to one
    colour without saying so here.
    """
    page = TMPL.read_text(encoding="utf-8")
    css = re.sub(r"/\*.*?\*/", " ", page, flags=re.S)

    sel = re.search(r"\.tile\.sel\{([^}]*)\}", css)
    assert sel, ".tile.sel is gone"
    assert "gradient" in sel.group(1), (
        "the selected tile is filled with a flat colour again: %s" % sel.group(1).strip())
    for want in ("var(--plate-lit)", "var(--plate)"):
        assert want in sel.group(1), (
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

    # AND THE UNSELECTED GROUND STILL MATCHES ITS FLAT TILE, which is the case this one is derived
    # from -- deleting that would make the squares appear on the other seven tiles instead.
    plain = re.search(r"\n\.seal\.plate\{([^}]*)\}", css)
    assert plain and "var(--plate)" in plain.group(1), (
        "an unselected mark's ground is no longer the plate's own colour, so it will show as a "
        "square on every tile that is not selected")


def test_the_pointer_closes_the_mark_s_dashes_and_moves_nothing_else():
    """The hover firms the border up. It must not also resize it.

    THE FAULT THIS IS FOR is a hover that sets `border` rather than `border-style` -- which looks
    identical in a screenshot and is not the same thing. A mark is a border-box, so a hover that
    restated the width would let a stale or rounded number through and shift the artwork inside by
    a pixel as the pointer crossed it; one that restated the colour would quietly take the mark
    off --guide for as long as you were looking at it, which is the one state you are looking at.

    Falsified by widening or recolouring on hover, or by dropping the rule.
    """
    page = TMPL.read_text(encoding="utf-8")
    css = re.sub(r"/\*.*?\*/", " ", page, flags=re.S)
    m = re.search(r"\.seal\.filled:hover[^{]*\{([^}]*)\}", css)
    assert m, "a mark does not go solid under the pointer"
    body = m.group(1)
    assert "solid" in body, "the hover rule does not make the edge solid: %s" % body.strip()
    for forbidden, why in (("px", "a width"), ("#", "a colour"), ("var(", "another variable")):
        assert forbidden not in body, (
            "the hover rule carries %s as well as the style (%s), so the mark changes size or "
            "hue under the pointer instead of only firming up" % (why, body.strip()))
    # AND THE RESTING RULE IS STILL THE ONE THAT OWNS THE WIDTH AND THE COLOUR.
    rest = re.search(r"\.seal\.filled\{([^}]*)\}", css).group(1)
    assert "dashed" in rest and "var(--guide)" in rest, (
        "the resting mark is no longer the guides' dashed line: %s" % rest.strip())


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


def test_a_hovered_tile_rises_without_taking_any_room_to_do_it():
    """The lift is a transform, it rides on the cross-highlight, and it gives back what it takes.

    THREE CLAIMS, AND EACH ONE IS A FAULT AVOIDED.

    It is a TRANSFORM, so the tile moves what it draws and not what it reserves. Everything below
    RIBBON_Y is derived from it, so a lift written as a height, a margin or a top would ripple
    down through the road, the cards and the wheel -- or fight the inline `top` the generator
    writes from geometry.

    It rides on `.lit`, which is what makes "lift it when its wheel face is hovered" free.
    lightFace() already answers which duty the pointer is on from either end, so the second
    direction needs no listener of its own; one would be the two-places-one-fact fault that class
    exists to prevent.

    And `::after` refills the strip the tile vacates, because hover is recomputed from what the
    pointer is OVER: slide a tile out from under a pointer resting in its lowest few pixels and it
    un-hovers, drops, re-hovers and shudders. Measured in a browser, and the first measurement was
    wrong -- with a perfectly still pointer nothing re-hit-tests and it looks fine. Moving the
    pointer a pixel, as a hand does, flickers across a band exactly --lift tall.

    Falsified by lifting with anything but a transform, by hanging it off a second listener, or by
    letting the strip and the lift stop being the same number.
    """
    page = TMPL.read_text(encoding="utf-8")
    css = re.sub(r"/\*.*?\*/", " ", page, flags=re.S)
    assert len(re.findall(r"--lift:\s*\d+px", css)) == 1, "--lift is not defined exactly once"

    lit = re.search(r"\.tile\.lit[^{]*\{([^}]*)\}", css)
    assert lit, ".tile.lit is gone"
    assert "transform:translateY" in lit.group(1), (
        "the tile does not rise by a transform: %s" % lit.group(1).strip())
    assert "var(--lift)" in lit.group(1), "the lift is not read from --lift"
    for owned in ("top:", "bottom:", "margin", "height:"):
        assert owned not in lit.group(1), (
            "the lift sets %s, which is geometry's to place, not the hover's to move" % owned)

    # THE SELECTED TILE RISES BY THE SAME RULE, which is what stops a click moving anything. You
    # are pointing at a tile when you click it, so it is already up; if selection had a height of
    # its own the tile would jerk under your finger at the moment you pressed it. Asserted as ONE
    # RULE rather than two equal values, because two values that happen to match today are exactly
    # how they stop matching tomorrow.
    assert re.search(r"\.tile\.lit\s*,\s*\.tile\.sel\s*\{"
                     r"|\.tile\.sel\s*,\s*\.tile\.lit\s*\{", css), (
        "the hover and the selection do not rise by the same rule, so clicking a tile you are "
        "pointing at will move it")
    sel = re.search(r"\.tile\.sel\{([^}]*)\}", css)
    if sel:
        assert "transform" not in sel.group(1), (
            "the selected tile has a transform of its own as well: %s" % sel.group(1).strip())

    strip = re.search(r"\.tile\.lit::after[^{]*\{([^}]*)\}", css)
    assert strip, (
        "the tile does not give back the strip it rises out of, so a pointer in its bottom few "
        "pixels will un-hover it and the tile will shudder")
    assert "top:100%" in strip.group(1), "the strip is not where the tile's lower edge was"
    assert "height:var(--lift)" in strip.group(1), (
        "the strip's height is not --lift itself, so it can stop matching the distance the tile "
        "rises: %s" % strip.group(1).strip())

    # THE SECOND DIRECTION IS NOT A SECOND LISTENER. If a future change moves the lift onto its
    # own :hover rule, this still passes the CSS checks above and the wheel stops lifting tiles.
    code = re.sub(r"(?m)^\s*//.*$", "", page)
    assert ".tile:hover" not in css, (
        "the lift is on the tile's own :hover, so hovering a wheel face no longer raises it")
    face = code.split("function lightFace(")[1].split("\nfunction ")[0]
    assert 'classList.toggle("lit"' in face and "tile" in face, (
        "lightFace() no longer sets `lit` on the tile, so the lift has lost the half of its "
        "wiring that comes from the wheel")

    assert re.search(r"@media\s*\(prefers-reduced-motion:\s*reduce\)", css), (
        "the tile animates with no way for a reader who asked for less motion to turn it off")


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
    layout that would visibly break if it quietly stopped being reserved. What it is FOR is the
    room the shorter ribbon freed: the ribbon came down from 242 to 186, and rather than letting
    the cards, the confirm row and the wheel all ride up 56 pixels, the road holds it open.

    Falsified by deleting the strip, by flattening it, or by drawing it anywhere but between the
    ribbon and the cards.

    AND THE HEIGHT IS ASSERTED SEPARATELY, because the two position lines below cannot see it:
    ART_Y is DERIVED from ROAD_H, so setting the road to zero moves the cards up and both lines
    go on passing. Mutating it to 0 is what found that. There is no honest way to assert "the
    cards did not move" from inside a file where they are measured off the thing that moved, so
    what is asserted instead is the weaker true thing: a road thinner than a gap is not a road.
    """
    assert geo.ROAD["height"] >= geo.GAP, (
        "the road is %d tall, which is thinner than the gaps either side of it -- it would read "
        "as a rule rather than as a strip the Merchant travels along" % geo.ROAD["height"])
    assert geo.ROAD["y"] == geo.RIBBON_Y + geo.RIBBON_H + geo.GAP, (
        "the road is not under the ribbon")
    assert geo.ART_Y == geo.ROAD["y"] + geo.ROAD["height"] + geo.GAP, (
        "the cards are not under the road")
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
    """
    assert geo.TILE_NAME_TOP == geo.INSET
    assert geo.CAP_PAD_Y == geo.INSET
    assert geo.SEAL_INSET == geo.INSET, "the seals use a margin of their own again"


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

def test_a_tithe_seal_is_a_duty_mark_unless_the_box_will_not_take_one(geo):
    """Falsified by giving TOKEN a figure of its own, or by letting one escape token_cap().

    THEY USED TO BE FLATLY EQUAL and this test used to say so. It cannot any more, and the reason
    is worth keeping rather than deleting: at one tile wide with the three in a column, what binds
    is the box's HEIGHT, and that height is ART_H -- a number chosen for the artwork. 72 does not
    fit three times with its gaps, so a Tithe resource is 66.

    The claim that replaces it is the one actually worth holding: a token is the mark's size, and
    the ONLY thing that may make it smaller is the box it has to fit in. A figure of TOKEN's own
    would pass `TOKEN <= SEAL` and fails here.
    """
    assert geo.TOKEN == geo.token_cap(geo.SEAL), "TOKEN did not come out of token_cap()"
    assert geo.TOKEN <= geo.SEAL, (
        "a Tithe resource is %d against a duty mark of %d -- it may never be the bigger of the two"
        % (geo.TOKEN, geo.SEAL))
    # WHERE THE BOX IS NOT THE CONSTRAINT, THE TWO ARE STILL EQUAL. Without this the test above
    # would pass just as well for a cap that always shaved a few pixels off for no reason.
    small = geo.SEAL // 2
    assert geo.token_cap(small) == small, (
        "a mark of %d leaves the box room to spare and still came back as %d"
        % (small, geo.token_cap(small)))
    # AND THE CAP BITES ON HEIGHT, not on width. The width term alone reports 67 and would let a
    # column of three overflow the box by 11, which is the fault this function was written for.
    assert geo.token_cap(10 ** 6) == geo.TOKEN, (
        "an absurd mark size came back as something other than the box's own limit")


def test_three_tithe_seals_and_their_label_fit_the_box_they_are_in(geo):
    """Falsified by picking a gap instead of deriving one, or by growing TOKEN again.

    check() names the overlap; this also pins the shape of the arithmetic so a future change has
    to go through the derivation rather than round the numbers until they look close enough.
    """
    assert geo.check() == [], "\n".join(geo.check())
    # THE LABEL IS ABOVE THE SEALS NOW, so the two ends that can collide have swapped: the label
    # must finish before the column starts, and the column must finish inside the box.
    # ASK THE SLOTS, NOT A STACK. A row, then a triangle, now a column -- and the arrangement has
    # changed under this test three times without it needing an edit, because it reads the slots
    # rather than rebuilding their arithmetic. That is the mistake the first version made.
    label_end = geo.TITHE_LABEL_TOP + geo.TITHE_LABEL_H
    slots = geo.token_slots()
    assert len(slots) == 3, "the Tithe no longer offers three resources"
    top = min(d["y"] for d in slots)
    end = max(d["y"] + d["size"] for d in slots)
    assert top >= label_end, (
        "the label ends at %d and the seals start at %d" % (label_end, top))
    assert end <= geo.TITHE_INNER_H - geo.INSET, (
        "the seals end at %d and the box's inner edge is at %d"
        % (end, geo.TITHE_INNER_H - geo.INSET))
    assert geo.TOKEN <= geo.TITHE_W - 2 * geo.INSET, "a seal of %d does not fit a box %d wide" \
        % (geo.TOKEN, geo.TITHE_W)
    # AND THE COLUMN IS CENTRED IN WHAT IS LEFT UNDER THE LABEL, rather than hung from the top
    # with the slack falling to the bottom. Measured off the slots, so it survives the next
    # rearrangement the way the block above did.
    #
    # WITHIN A PIXEL, AND THE PIXEL IS REAL RATHER THAN SLOP: the column's own slack is 1, which
    # cannot be halved into two integer positions. Writing this as an equality failed, and the
    # honest reading of that failure is that the board is centred and the arithmetic is odd.
    above = top - (label_end + geo.INSET)
    below = (geo.TITHE_INNER_H - geo.INSET) - end
    assert abs(above - below) <= 1, (
        "the column has %d above it and %d below" % (above, below))


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
    # t.tokenY AND t.tokenGap ARE GONE WITH THE STACK. Where each resource sits is handed over
    # placed, as the duty tile's marks already were, so the page reads positions rather than
    # recomputing a layout from a start and a repeat.
    for key in ("t.slots", "t.labelTop", "t.order"):
        assert key in body, "the Tithe column no longer takes %s from GEO" % key
    for gone in ("t.tokenY", "t.tokenGap", "t.tokenX"):
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
            ("the duty tile", (geo.TILE_INNER_W, geo.TILE_INNER_H), (geo.TILE_W, geo.RIBBON_H)),
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


def test_the_tile_carries_the_same_plate_the_marks_are_grounded_on(gen):
    """Falsified by leaving the tile near-black under a mark that is given a ground of its own.

    A cut-out brings no ground, so the board supplies one -- and while the tile was #0b0a09 that
    ground was a visible square sitting behind each mark. The tile carries the colour now, so the
    square stops being a square and the mark simply sits on the tile. The two have to be the SAME
    colour, which is why it is a variable rather than a literal written twice: this asserts they
    cannot drift, not that either is any particular value.

    IT USED TO BE CALLED "the same purple". The plate has been slate since the picker's palette
    was taken up, and the name outlived the colour -- which is the whole reason the rule is a
    variable, so it is a poor thing for its own guard to have got wrong.
    """
    page = TMPL.read_text(encoding="utf-8")
    assert "--plate:" in page, "the plate's colour is no longer named on :root"
    import re as _re
    tile = _re.search(r"^\.tile\{([^}]*)\}", page, _re.M | _re.S)
    assert tile, "the tile has no rule of its own"
    assert "var(--plate)" in tile.group(1), (
        "the duty tile is not drawn from the plate: %s" % " ".join(tile.group(1).split()))
    assert ".seal.plate{background:var(--plate)" in page, (
        "the mark's ground is no longer drawn from the plate the tile is")

    # THEY ARE NO LONGER THE SAME COLOUR, AND THAT IS THE POINT NOW. The tile became glass over
    # the backdrop -- --plate at --tile-alpha -- and the mark's ground stayed opaque, so a cut-out
    # keeps a solid dark field to read against instead of competing with a lit valley. What still
    # cannot drift is the SOURCE: both are drawn from --plate, so changing the palette moves both.
    # The original claim, that the two match exactly, was true only while nothing was behind them.
    assert "--tile-alpha" in tile.group(1), (
        "the tile is opaque again, so the backdrop behind it cannot be seen at all: %s"
        % " ".join(tile.group(1).split()))
    # THE SELECTED TILE IS NOT ASSERTED HERE, AND THAT IS DELIBERATE. This line used to pin
    # `.tile.sel .seal.plate{background:var(--plate-lit)}`, which was right while a selected tile
    # was one flat colour and is wrong now that it is a gradient -- there is no single colour for
    # the ground to match, so the ground has to be nothing at all. The rule still holds, it is
    # just no longer "the same colour": it is "whatever the tile is showing".
    #
    # That case lives in test_a_selected_tile_catches_light_and_its_marks_bring_no_ground_of_
    # their_own, in one place rather than half-stated in two.
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
    # A CONTROL IS A TILE'S MARK WITHOUT ITS FRAME. The marks are border-box, so a SEAL-sized mark
    # on a tile shows SEAL - 2*SEAL_BORDER of artwork; a control carries no frame, so it IS that
    # size. Asserted as the subtraction rather than as 68, because 68 is the answer and this is
    # the reason -- and because the column was 72 for a while, which drew the same emblem four
    # pixels larger than the tile above it was drawing it.
    # READ OFF THE RECTS, because the rects are the only place the size is published. It was also
    # published as a bare `size` beside them for a while and read by nobody -- one number stated
    # twice, which is how two numbers start.
    for name in marks["order"]:
        assert marks[name]["width"] == marks[name]["height"] == geo.MARK, (
            "%s is not a MARK-sized square" % name)
        assert marks[name]["width"] == geo.SEAL - 2 * geo.SEAL_BORDER, (
            "a control is %d and a tile's mark shows %d of artwork inside its frame"
            % (marks[name]["width"], geo.SEAL - 2 * geo.SEAL_BORDER))
    assert "size" not in marks, (
        "the column's size is published beside the rects as well as in them, so the two can drift")
    # AND IT STANDS ON ALLOCATION'S, to the pixel. This is the claim the section is built on: the
    # column is the eighth tile's artwork carried down, not merely near it or centred under it.
    tile_x = geo.X0 + (geo.TILES - 1) * geo.TILE_PITCH
    art_x = tile_x + geo.BORDER + geo.seal_slots(1)[0]["x"] + geo.SEAL_BORDER
    for name in marks["order"]:
        assert marks[name]["x"] == art_x, (
            "%s is at %d and Allocation's artwork at %d" % (name, marks[name]["x"], art_x))
    # THE AIR BETWEEN THEM IS THE AIR A TILE KEEPS BETWEEN PICTURES, which is SEAL_INSET plus the
    # two frames it spends -- 10, not the 6 the boxes are apart. Matching the 6 matches the
    # arithmetic and not the eye, and the column did exactly that at first.
    ys = [marks[n]["y"] for n in marks["order"]]
    air = ys[1] - ys[0] - marks[marks["order"][0]]["height"]
    assert air == geo.SEAL_INSET + 2 * geo.SEAL_BORDER, (
        "the controls are %d apart and a tile's marks keep %d of clear air"
        % (air, geo.SEAL_INSET + 2 * geo.SEAL_BORDER))
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

    # THE FRAME IS GEOMETRY'S NUMBER, NOT THE STYLESHEET'S. SEAL_BORDER sets a border here and a
    # WIDTH in the controls column, so a `2px` typed back into this rule is two owners for one
    # fact: the border would move and the column would go on being sized off the old value, which
    # renders perfectly and quietly stops the control being the artwork it is supposed to equal.
    # The ordinary no-geometry guard cannot see this -- it bans the board's three- and four-digit
    # numbers, and this one is a 2.
    rule = page.split(".seal.filled{")[1].split("}")[0]
    assert "var(--seal-border)" in rule, (
        "the mark's frame is typed into the stylesheet again: %r" % rule)
    assert "GEO.ribbon.sealBorder" in code, (
        "nothing sets --seal-border from geometry, so the rule above falls back to nothing")

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

def test_the_tithe_tokens_move_with_the_tile_marks():
    """A seal and a coin are one size, so one lever has to move both.

    THE BUG THIS IS POINTED AT is a flag that resizes the eight tiles' marks and leaves the
    Tithe's three where they were, which reads as a layout fault rather than as a setting -- the
    exact thing the comment above TOKEN in geometry.py was written for. Falsified by having
    configure() set SEAL alone.
    """
    g = _load("geometry")
    # MEASURED BELOW THE TITHE BOX'S OWN LIMIT, so the two are free to be equal and this test is
    # about the lever rather than about the cap. At the default they are NOT equal -- the column
    # of three is height-bound at 66 against a mark of 72 -- and a test that set 70 here would be
    # asserting the cap's number while believing it was asserting the lever's.
    small = 40
    assert g.token_cap(small) == small, "%d is capped, so this test proves nothing" % small
    g.configure(seal=small)
    assert g.SEAL == small, "configure() did not set the mark size"
    assert g.TOKEN == small, (
        "the Tithe's tokens stayed at their old size while the tile marks moved")
    assert g.TOKEN_SPREAD == small + g.INSET, "the spacing the three tokens stand on did not follow"
    assert g.as_dict()["ribbon"]["seal"] == small, "the page is still told the old size"
    assert g.as_dict()["tithe"]["token"] == small, "the page is still told the old token size"
    # AND ABOVE THE CAP THE LEVER STOPS AT THE BOX rather than running past it. The flag may make
    # the Tithe's resources smaller than the duty marks; it may never make them not fit.
    g.configure(seal=g.SEAL)
    big = g.token_cap(10 ** 6) + 10
    g.configure(seal=big)
    assert g.SEAL == big, "configure() did not set the mark size"
    assert g.TOKEN == g.token_cap(big) < big, (
        "a mark of %d put a Tithe resource of %d in a box that cannot hold three"
        % (big, g.TOKEN))


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
    # THE DEFAULT MARK IS THE BIGGEST THE TILE TAKES AT THE TILE'S OWN RHYTHM, which is what it
    # means for RIBBON_H to be derived from it rather than chosen.
    fits = (g.TILE_INNER_H - g.TILE_NAME_BOTTOM - 3 * g.SEAL_INSET) // 2
    assert g.SEAL == fits, (
        "the tile holds a mark of %d and the board draws %d, so the ribbon's height is no longer "
        "the height of what it holds" % (fits, g.SEAL))

    # ONE PIXEL OVER: still inside the tile, no longer at its rhythm.
    g.configure(seal=fits + 1)
    bad = g.check()
    assert any("leaves" in line and "inside a tile" in line for line in bad), (
        "a %d px mark leaves less under it than the pair keep between them and check() did not "
        "say so: %s" % (fits + 1, bad))

    # FAR ENOUGH OVER TO LEAVE THE BOX, which is the complaint the --icons flag quotes back.
    spills = g.TILE_INNER_H - g.TILE_NAME_BOTTOM - 2 * g.SEAL_INSET - g.SEAL_INSET // 2
    g.configure(seal=spills)
    bad = g.check()
    assert bad, "a %d px mark overflows its tile and check() did not notice" % spills
    # NOT just "a line mentioning seals". The Tithe's own guard also says "seals", and it fires at
    # this size too -- so a looser match passed while the tile guard was disabled, which is what
    # mutating RIBBON_H revealed. The complaint has to be about the TILE, and about SPANNING it.
    assert any("spans" in line and "inside a tile" in line for line in bad), (
        "check() complained, but not that the mark overflows its tile: %s" % bad)


def test_setting_the_mark_size_does_not_move_anything_else():
    """One lever, not a settings system. Falsified by configure() touching a second number.

    THE SIZE HAS TO BE ONE ALL THREE MOVE FOR. At 70 the Tithe's cap holds TOKEN at 66 where it
    already was, so `moved` came back as {"SEAL"} alone -- which passes a subset check and would
    have let configure() quietly stop moving the token at all.
    """
    g = _load("geometry")
    before = {k: v for k, v in vars(g).items() if k.isupper() and isinstance(v, (int, float))}
    g.configure(seal=40)
    after = {k: v for k, v in vars(g).items() if k.isupper() and isinstance(v, (int, float))}
    moved = {k for k in before if before[k] != after[k]}
    assert moved == {"SEAL", "TOKEN", "TOKEN_SPREAD"}, (
        "configure() changed %s; it may only move the mark size and what is derived from it"
        % sorted(moved))
