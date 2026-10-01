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
    assert geo.ART_W * 2 + geo.ART_GAP + geo.GAP + geo.SIDE_W == geo.WORK_W, (
        "the two cards, their gap, the column and its gap do not fill the working width")


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
