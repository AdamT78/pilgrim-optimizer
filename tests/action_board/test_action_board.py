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
    # THE BOX BESIDE THE CARDS IS THE TITHE. It used to be the side column, which was the same
    # thing while the column ran the full height of this row; the Tithe spans two tiles now and
    # the column below it spans one, so the row is cards, gap, cards, gap, TITHE_W.
    assert geo.ART_W * 2 + geo.ART_GAP + geo.GAP + geo.TITHE_W == geo.WORK_W, (
        "the two cards, their gaps and the Tithe do not fill the working width")
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
    banned = {geo.CANVAS_W, geo.CANVAS_H, geo.ART_W, geo.ART_H, geo.ART_Y,
              geo.CONFIRM_Y, geo.SIDE_X, geo.SIDE_W, geo.WHEEL_Y, geo.TILE_W, geo.RIBBON_Y}
    found = set(int(n) for n in re.findall(r"(?<![\w.#-])(\d{3,4})(?![\w.%])", page))
    overlap = sorted(found & banned)
    assert not overlap, ("the template has %s written into it, and those are geometry.py's"
                         % ", ".join(str(n) for n in overlap))


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

def test_the_tithe_seals_are_the_same_size_as_the_duty_action_seals(geo):
    """Falsified by giving TOKEN a figure of its own.

    They were 64 against 78, which made the third choice on the row look like a lesser kind of
    thing than the two beside it. Taking the tithe is the same sort of move.
    """
    assert geo.TOKEN == geo.SEAL


def test_three_tithe_seals_and_their_label_fit_the_box_they_are_in(geo):
    """Falsified by picking a gap instead of deriving one, or by growing TOKEN again.

    check() names the overlap; this also pins the shape of the arithmetic so a future change has
    to go through the derivation rather than round the numbers until they look close enough.
    """
    assert geo.check() == [], "\n".join(geo.check())
    # THE LABEL IS ABOVE THE SEALS NOW, so the two ends that can collide have swapped: the label
    # must finish before the column starts, and the column must finish inside the box.
    # ASK THE SLOTS, NOT A STACK. The three sit on a triangle now -- two below, one centred over --
    # so there is no TOKEN_Y plus three tokens and two gaps to add up. Reading the slots keeps this
    # true of whatever the arrangement becomes, which is the mistake the old version made.
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
    # AND THEY ARE THE DUTY MARKS' OWN SIZE. The Tithe is the third choice on this row, not a
    # lesser kind of thing; this is the assertion the old narrow column could not have passed.
    assert geo.TOKEN == geo.SEAL, (
        "a Tithe resource is %d and a duty mark is %d" % (geo.TOKEN, geo.SEAL))


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
    body = page.split("var t = GEO.tithe;")[1].split("var tc = GEO.confirm.tithe;")[0]
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


def test_the_tile_carries_the_same_purple_the_marks_are_grounded_on(gen):
    """Falsified by leaving the tile near-black under a mark that is given a purple ground.

    A cut-out brings no ground, so the board supplies one -- and while the tile was #0b0a09 that
    ground was a visible purple square sitting behind each mark. The tile carries the colour now,
    so the square stops being a square and the mark simply sits on the tile. The two have to be
    the SAME colour, which is why it is a variable rather than a literal written twice: this
    asserts they cannot drift, not that either is any particular value.
    """
    page = TMPL.read_text(encoding="utf-8")
    assert "--plate:" in page, "the plate's purple is no longer named on :root"
    import re as _re
    tile = _re.search(r"^\.tile\{([^}]*)\}", page, _re.M)
    assert tile, "the tile has no rule of its own"
    assert "background:var(--plate)" in tile.group(1), (
        "the duty tile is not drawn on the plate's purple: %s" % tile.group(1))
    assert ".seal.plate{background:var(--plate)" in page, (
        "the mark's ground is no longer the same colour the tile is")
    # AND THE SELECTED TILE TAKES ITS PLATE WITH IT. It lifts to --plate-lit, and a plate left
    # behind on --plate turns back into the visible square -- on the one tile you are looking at.
    assert ".tile.sel .seal.plate{background:var(--plate-lit)}" in page, (
        "the selected tile's plate does not follow it, so the square comes back when you select")


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


