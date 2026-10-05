"""The icon lab: what it puts on the page, what it would call what you save, and what it remembers.

This page is a tool rather than shipped art, so what is guarded is narrow: the string rules it uses
to find a master, read a slot and name a cut, and the contract between what the page writes down
and what it reads back. All of them are silent when they are wrong. A `master_of` that misses sends
the lab to re-cut an already-cut file, which costs resolution nobody will see going. A `next_cut`
that returns a number already in use writes over a file whose sha256 is recorded, leaving
attribution.json describing pixels that no longer exist. And a framing restored by anything other
than the filename lands on the wrong picture the moment a new master arrives.
"""
import importlib.util
import json
import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
BOARD = ROOT / "ui" / "board_v2"
LAB = BOARD / "icon_lab"
TMPL = LAB / "icon_sizer.html.tmpl"
ART = BOARD / "duty_actions"


@pytest.fixture(scope="module")
def gen():
    spec = importlib.util.spec_from_file_location(
        "generate_icon_sizer", LAB / "generate_icon_sizer.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def rec():
    return json.loads((BOARD / "attribution.json").read_text(encoding="utf-8"))["files"]


def _mark_folders():
    doc = json.loads((BOARD / "attribution.json").read_text(encoding="utf-8"))
    return tuple(doc.get("markFolders") or ("seals",))


def test_a_shipped_mark_points_at_the_master_beside_it(gen):
    """Falsified by changing either half of the naming convention without the other."""
    assert gen.master_of("build_roads/icons/build_roads_actionA_icon_v04.png") == \
        "build_roads/icons/masters/build_roads_actionA_icon_master_v04.png"
    # A WEBP PRINT HAS A PNG MASTER. The suffix is not carried over, because the shipped file is
    # lossy and the archive is not -- which is the one thing a master is for.
    assert gen.master_of("produce/seals/produce_actionB_seal_v03.webp") == \
        "produce/seals/masters/produce_actionB_seal_master_v03.png"
    # THE RECORD WINS WHERE THERE IS ONE, because the versions come apart as soon as a slot is
    # re-cut: Build Roads' fifth cut was taken from its fourth master, and the name rule would
    # send this looking for a fifth master that will never exist.
    assert gen.master_of("build_roads/icons/build_roads_actionA_icon_v05.png",
                         {"master": "build_roads_actionA_icon_master_v04.png"}) == \
        "build_roads/icons/masters/build_roads_actionA_icon_master_v04.png"


def test_every_master_the_lab_points_at_is_really_there(gen, rec):
    """The rule above is a convention, not a guarantee, so the tree is asked whether it holds.

    Falsified by committing a mark whose master is filed under any other name and recording no
    `master` for it. The lab would still work -- it says so in its notes and carries on -- but the
    framing of that mark could then only be revisited by cutting a cut.
    """
    folders = _mark_folders()
    missing = []
    for path, e in rec.items():
        if not path.startswith("duty_actions/") or e.get("slot") not in ("left", "right"):
            continue
        rel = path[len("duty_actions/"):]
        parts = rel.split("/")
        if len(parts) < 3 or parts[1] not in folders or "masters" in parts:
            continue
        if not (ART / gen.master_of(rel, e)).is_file():
            missing.append(rel)
    assert not missing, "no master filed for:\n" + "\n".join(missing)


def test_a_file_says_which_action_it_is_for(gen):
    """A master is recorded under `slot: "master"`, which says what KIND of file it is.

    Which of a duty's two actions it belongs to is written only in its name, so that is where the
    lab reads it -- and a name that does not say is left out and named rather than guessed into a
    slot, because a guess puts somebody's Ordain under Mission and nothing complains.
    """
    assert gen.slot_in_name("ordination_actionB_icon_master_v01.png") == "actionB"
    assert gen.slot_in_name("build_roads_actionA_icon_v04.png") == "actionA"
    assert gen.slot_in_name("clerical_master_v04.png") is None


def test_the_next_cut_never_lands_on_a_file_that_exists(gen):
    """Falsified by returning the highest version rather than the one above it.

    The lab offers a name to save under, and the one thing that name must not be is the name of a
    mark already on the record.
    """
    folders = _mark_folders()
    clashes = []
    for duty_dir in sorted(p for p in ART.iterdir() if p.is_dir()):
        for sub_dir in folders:
            if not (duty_dir / sub_dir).is_dir():
                continue
            for slot in ("actionA", "actionB"):
                nxt = duty_dir / sub_dir / gen.next_cut(duty_dir.name, slot, sub_dir)
                if nxt.exists():
                    clashes.append("%s would be written over" % nxt.relative_to(ART).as_posix())
    assert not clashes, "\n".join(clashes)

    # AND THE SHAPE OF THE ANSWER, worked out rather than quoted, because the tree moves. These
    # used to name v01 and v05 outright and went stale the hour the first cuts were filed.
    suffix = gen.PRINT_SUFFIX
    for duty, slot in (("clerical", "actionA"), ("build_roads", "actionA")):
        here = ART / duty / "icons"
        base = "%s_%s_icon" % (duty, slot)
        have = [int(f.stem[len(base) + 2:]) for f in here.glob(base + "_v*" + suffix)] \
            if here.is_dir() else []
        assert gen.next_cut(duty, slot, "icons") == \
            "%s_v%02d%s" % (base, (max(have) if have else 0) + 1, suffix)
    # A slot with nothing cut starts at v01 rather than at v00 or at its master's number.
    assert gen.next_cut("nobody", "actionA", "icons") == "nobody_actionA_icon_v01" + suffix


def test_the_lab_puts_every_icon_master_on_the_page(gen, rec):
    """A master with no cut yet is the normal case, not an edge one.

    Five arrived at once with nothing cut from any of them, and the first version of this lab
    seeded from the SHIPPED marks -- so it would have shown an empty page on the day it was most
    wanted. Falsified by going back to seeding from the cuts, or by keeping a list of icons here:
    a list is a second place to say which marks exist, and the day a fifteenth master lands only
    one of the two learns about it.
    """
    want = sorted(pathlib.PurePosixPath(p).name for p in rec
                  if p.startswith("duty_actions/")
                  and "/icons/masters/" in p
                  and gen.slot_in_name(pathlib.PurePosixPath(p).name))
    seed, notes = gen.seeds()
    assert sorted(s["file"] for s in seed) == want, notes
    assert want, "this tree has no icon masters in it at all"
    # Every card knows what to call itself and what a cut of it would be called.
    for s in seed:
        assert s["name"] and not s["name"].startswith("duty_actions"), s
        # A CUT AND ITS MASTER NEVER SHARE A SUFFIX. The print is WebP at quality 90 and the
        # archive is PNG, because a lossy archive is not one -- so a cut offered with the
        # master's extension means one of the two ends has forgotten which it is.
        assert s["out"].endswith(gen.PRINT_SUFFIX), s
        assert not s["out"].endswith(".png"), "a cut is being offered in the archive's format"
        assert "_master_" not in s["out"], s
        assert s["file"].endswith(".png"), "a master is being read from a lossy file"
        assert s["src"].startswith("data:image/png;base64,"), s["file"]


def test_a_master_with_no_record_is_left_out_and_named(gen, tmp_path, monkeypatch):
    """The record gates the art here exactly as it does on the board.

    Falsified by seeding whatever is on disk: an icon somebody dropped in and never recorded would
    then be framed, cut and shipped without anyone ever having said where it came from.
    """
    art = tmp_path / "duty_actions"
    masters = art / "clerical" / "icons" / "masters"
    masters.mkdir(parents=True)
    (masters / "clerical_actionA_icon_master_v01.png").write_bytes(b"x")
    (masters / "clerical_actionB_icon_master_v01.png").write_bytes(b"x")
    attrib = tmp_path / "attribution.json"
    attrib.write_text(json.dumps({"imageSuffixes": [".png", ".webp"], "files": {
        "duty_actions/clerical/icons/masters/clerical_actionA_icon_master_v01.png": {
            "slot": "master"}}}), encoding="utf-8")
    monkeypatch.setattr(gen, "ART_DIR", art)
    monkeypatch.setattr(gen, "ATTRIB_FILE", attrib)

    seed, notes = gen.seeds()
    assert [s["file"] for s in seed] == ["clerical_actionA_icon_master_v01.png"]
    assert any("clerical_actionB_icon_master_v01.png" in n and "no attribution entry" in n
               for n in notes), notes


def test_the_walk_only_looks_at_images(gen, tmp_path, monkeypatch):
    """Falsified by taking whatever a folder contains, which is what this did.

    macOS drops a `.DS_Store` into any folder you open in Finder, and two of the icons folders had
    one. The build duly reported it as a cut with no master -- true, useless, and the kind of line
    that teaches you to stop reading the build output.
    """
    art = tmp_path / "duty_actions"
    icons = art / "clerical" / "icons"
    (icons / "masters").mkdir(parents=True)
    (icons / "masters" / "clerical_actionA_icon_master_v01.png").write_bytes(b"x")
    (icons / "clerical_actionA_icon_v01.png").write_bytes(b"x")
    (icons / ".DS_Store").write_bytes(b"x")
    (icons / "masters" / ".DS_Store").write_bytes(b"x")
    (icons / "notes.txt").write_text("not a picture", encoding="utf-8")
    attrib = tmp_path / "attribution.json"
    attrib.write_text(json.dumps({"imageSuffixes": [".png", ".webp"], "files": {
        "duty_actions/clerical/icons/masters/clerical_actionA_icon_master_v01.png":
            {"slot": "master"},
        "duty_actions/clerical/icons/clerical_actionA_icon_v01.png": {"slot": "left"},
    }}), encoding="utf-8")
    monkeypatch.setattr(gen, "ART_DIR", art)
    monkeypatch.setattr(gen, "ATTRIB_FILE", attrib)

    seed, notes = gen.seeds()
    assert [s["file"] for s in seed] == ["clerical_actionA_icon_master_v01.png"], seed
    assert not notes, notes


def test_a_framing_file_that_cannot_be_read_stops_the_build(gen, tmp_path, monkeypatch):
    """Falsified by swallowing the error and building a page with no framing in it.

    Silently dropping the saved framing would look exactly like never having saved one, and the
    first thing you would do is reframe fourteen icons that were already framed.
    """
    bad = tmp_path / "framing.json"
    bad.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(gen, "FRAMING_FILE", bad)
    with pytest.raises(SystemExit) as e:
        gen.saved_framing()
    assert "framing.json" in str(e.value)

    monkeypatch.setattr(gen, "FRAMING_FILE", tmp_path / "nothing-here.json")
    assert gen.saved_framing() == {}, "a lab with no framing yet is not an error"


def test_the_page_restores_a_framing_by_filename_and_says_where_it_came_from(gen):
    """Two places can hold a framing, and the page is not allowed to prefer one quietly.

    The browser store is a convenience and `framing.json` is the record. Falsified by restoring
    by index -- a new master reorders the seed and every framing lands on the wrong picture --
    or by dropping the line that says which of the two is in force, which is what keeps the
    convenience from becoming a second owner nobody can see.
    """
    page = TMPL.read_text(encoding="utf-8")
    assert "__FRAMING__" in page, "the build has nowhere to put the saved framing"
    assert "SOURCE.doc.icons[ic.file]" in page, "a framing is restored by something other than name"
    # BOTH THE DEFINITION AND THE CALL, and the definition spelled with its parentheses. The
    # first version of this looked for "function tellSource" and a mutation that renamed it to
    # tellSourceX sailed straight through on the prefix, leaving a page that throws on load.
    assert "function tellSource()" in page, "nothing works out which framing is in force"
    assert "\ntellSource();" in page, "the page never says so on load"
    assert "id=where" in page, "there is nowhere for it to say it"
    assert "getElementById('save').onclick = saveSettings" in page, \
        "the save button is wired to nothing"
    assert "localStorage.removeItem(STORE)" in page, "there is no way back to the file"
    # The three numbers that ARE the framing; everything else in the file is arithmetic.
    for k in ("scale:", "ox:", "oy:"):
        assert k in page, "the saved framing no longer carries %s" % k


def test_what_the_page_writes_is_what_the_page_reads_back(gen, tmp_path, monkeypatch):
    """The generator and the page have to agree about the shape of framing.json.

    Falsified by either end renaming a key. The page would then open fitted to the mark with no
    complaint, which reads exactly like a framing that was never saved.
    """
    f = tmp_path / "framing.json"
    f.write_text(json.dumps({
        "savedAt": "2026-10-03T21:22:28.183Z", "iconSize": 132,
        "icons": {"build_roads_actionA_icon_master_v04.png":
                  {"scale": 1.77, "ox": -0.31, "oy": -0.22}}}), encoding="utf-8")
    monkeypatch.setattr(gen, "FRAMING_FILE", f)
    doc = gen.saved_framing()
    assert doc["icons"]["build_roads_actionA_icon_master_v04.png"]["scale"] == 1.77

    page, _notes = gen.build()
    assert '"savedAt": "2026-10-03T21:22:28.183Z"' in page, "the framing never reached the page"
    assert '"iconSize": 132' in page
    assert "__FRAMING__" not in page, "the token survived the build"


def test_download_everything_does_not_hand_back_what_the_repository_already_has(gen):
    """A seeded icon's raw came out of the tree and is still there; a dropped one has no home.

    The button handed back all fourteen masters as well as the cuts -- eighteen megabytes of
    byte-identical copies of files already committed -- which was useful for exactly as long as
    the masters were not in the repository. Falsified by dropping the distinction, which brings
    the duplicates back, or by extending it to dropped files, which would make the one copy of
    something unreachable.
    """
    page = TMPL.read_text(encoding="utf-8")
    assert "if (!ic.seeded) jobs.push" in page, "download everything is copying the tree back out"
    assert "seeded:!!seeded" in page, "nothing records whether an icon came from the tree"
    assert "add(s.name, s.src, s.file, s.out, true)" in page, "the seeds are not marked as seeded"
    # The per-card raw button is how you still get one on purpose.
    assert "act('raw', 'dl', function(){ save(ic.src, ic.file); });" in page, \
        "the only way to get a raw back has gone"


def test_the_page_is_only_opened_when_it_is_asked_for(gen, monkeypatch, tmp_path):
    """Falsified by opening on every build, or by dropping the flag.

    The action board spells it `--open` and so does this, because two generators in one tree that
    disagree about how to open their own output is a thing you look up every time.
    """
    opened = []
    monkeypatch.setattr(gen.webbrowser, "open", lambda u: opened.append(u))
    monkeypatch.setattr(gen, "OUT", tmp_path / "generated" / "icon_sizer.html")

    monkeypatch.setattr(sys, "argv", ["generate_icon_sizer.py"])
    assert gen.main() == 0
    assert opened == [], "a plain build opened a browser"

    monkeypatch.setattr(sys, "argv", ["generate_icon_sizer.py", "--open"])
    assert gen.main() == 0
    assert len(opened) == 1 and opened[0].endswith("icon_sizer.html"), opened


def test_a_build_says_when_the_board_is_behind_the_framing(gen, monkeypatch, tmp_path, capsys):
    """A framing changes this page and nothing else, and the build says so rather than implying.

    framing.json decides what the cards show and what `cut` hands back. The board draws the file
    in the icons folder, which was cut at whatever framing was in force then. So there are two
    ways to be behind -- never cut, or cut and since reframed -- and both are things you can see
    here and nowhere else.

    THE FIRST VERSION ASKED THE WRONG QUESTION. It checked whether the NEXT cut name was free,
    which it always is, because next_cut picks it for being free; so once anything had been cut
    the line listed all fourteen every build and told you nothing. Falsified by going back to
    that, or by dropping either branch.
    """
    monkeypatch.setattr(gen, "OUT", tmp_path / "generated" / "icon_sizer.html")
    monkeypatch.setattr(sys, "argv", ["generate_icon_sizer.py"])
    seed = gen.seeds()[0]
    assert seed, "this tree has no icon masters to reason about"

    # (a) a framing nothing on disk was cut at: every master is named, one way or the other.
    held = {s["file"]: {"scale": 1.2, "ox": 0.0, "oy": 0.0, "crop": {"x": 0, "y": 0, "w": 900}}
            for s in seed}
    monkeypatch.setattr(gen, "saved_framing",
                        lambda: {"savedAt": "2026-10-03T22:38:29.612Z", "icons": held})
    assert gen.main() == 0
    out = capsys.readouterr().out
    assert "not what is in framing.json" in out, out
    for s in seed:
        cut = gen._cut_from(s["file"])
        if cut is None:
            assert s["name"] in out, "%s has no cut and was not named:\n%s" % (s["name"], out)
        else:
            assert cut[0] in out, "%s was cut at %s, framed at 900, and was not named:\n%s" % (
                cut[0], cut[1], out)

    # (b) nothing to say when every cut was taken at the framing that is held.
    agreed = {}
    for s in seed:
        cut = gen._cut_from(s["file"])
        if cut:
            agreed[s["file"]] = {"scale": 1.0, "ox": 0.0, "oy": 0.0, "crop": cut[1]}
    monkeypatch.setattr(gen, "saved_framing",
                        lambda: {"savedAt": "2026-10-03T22:38:29.612Z", "icons": agreed})
    assert gen.main() == 0
    quiet = capsys.readouterr().out
    assert "the framing has moved" not in quiet, quiet
    assert "framed but never cut" not in quiet, quiet

    # (c) and nothing at all when nothing is framed.
    monkeypatch.setattr(gen, "saved_framing", lambda: {})
    assert gen.main() == 0
    silent = capsys.readouterr().out
    assert "not what is in framing.json" not in silent, silent


def test_a_cut_is_matched_to_its_master_by_the_record(gen, rec):
    """Falsified by matching on anything but the recorded `master`.

    Dropping that condition does not look like a bug from outside: every cut still has a crop, so
    the search still finds one, and what it hands back is simply the highest-numbered cut in the
    whole tree for every master you ask about. The build then compares Taxation's framing with
    Build Roads' crop and reports whatever that comparison happens to say. A test that only read
    the build's output could not tell the difference, so this asks the function directly.
    """
    cuts = {p.rsplit("/", 1)[-1]: e for p, e in rec.items()
            if "/icons/" in p and "/masters/" not in p and e.get("master") and e.get("crop")}
    assert cuts, "this tree has no recorded cuts to check"
    for name, e in sorted(cuts.items()):
        got = gen._cut_from(e["master"])
        assert got is not None, "%s is recorded as cut from %s and nothing found it" % (
            name, e["master"])
        found, crop = got
        assert cuts[found]["master"] == e["master"], (
            "asked for the cut of %s and got %s, which came from %s"
            % (e["master"], found, cuts[found]["master"]))
        assert crop == cuts[found]["crop"], "the crop came back from a different record"
    # A master nothing was cut from has no cut, rather than somebody else's.
    assert gen._cut_from("nothing_actionA_icon_master_v09.png") is None


def test_a_cut_ships_lossy_and_a_master_stays_lossless(gen, rec):
    """Falsified by filing a cut as PNG, which is how the first sixteen went in.

    attribution.json's imageSuffixesNote settled this before icons existed and the icons did not
    follow it: 22.2 MB of PNG where 2.3 MB of WebP carries the same picture to within 6 of 255 at
    the size the board draws. The rule is not about icons -- it is about which file is the archive
    -- so it is asserted over every mark in the tree rather than over this folder.
    """
    cuts, masters = [], []
    for path, e in rec.items():
        if not path.startswith("duty_actions/") or "/seals/" not in path and "/icons/" not in path:
            continue
        (masters if "/masters/" in path else cuts).append(path)
    assert cuts and masters, "this tree has no marks to check"
    lossless = [p for p in cuts if p.endswith(".png")]
    assert not lossless, "shipped as the archive format:\n" + "\n".join(lossless)
    lossy = [p for p in masters if not p.endswith(".png")]
    assert not lossy, "archived in a lossy format:\n" + "\n".join(lossy)
    # And every one of them is really where the record says, in the format the record says.
    board = LAB.parent
    for path in cuts + masters:
        assert (board / path).is_file(), "%s is recorded and not on disk" % path

    # THE PAGE'S END OF IT, because the records above only see what somebody already filed. A
    # page that went back to emitting PNG would not fail anything until the next cut was filed,
    # and by then it is a 1.5 MB file in a tree that thinks it ships 100 KB ones.
    page = TMPL.read_text(encoding="utf-8")
    assert 'PRINT = {suffix: ".webp", type: "image/webp", quality: 0.9}' in page, \
        "the cut button no longer encodes the shipping format"
    assert "PRINT.type, PRINT.quality" in page, "the encoder is named somewhere other than PRINT"
    assert "'image/png'" not in page, "the page is still encoding the archive format somewhere"
    assert "_cut' + PRINT.suffix" in page, "a dropped file is named apart from how it is encoded"
    assert gen.PRINT_SUFFIX == ".webp", "the name the generator offers and the page's have parted"
    # AND THE FRAMING CARRIES NO NAME THAT GOES STALE. `out` is the next free version at the
    # moment of saving: wrong as soon as you use it, and wrong twice over once the format moved.
    assert "out: ic.out" not in page, "framing.json is being written with a name that goes stale"


# =================================================================================================
# THE SIZE CHECK, the lab's other page. The sizer decides a mark's CROP; this one decides how big
# that mark is DRAWN, and its output is a number for geometry.py rather than a file.

SIZE_TMPL = LAB / "size_check.html.tmpl"


def _code(path):
    """A template with its prose taken out.

    COMMENTS ARE PROSE, NOT CODE, and the comments on these pages quite reasonably say things
    like "1400 x 1200" and "a canvas" while explaining why neither is typed in. The action board's
    guards strip them for the same reason; a test about the code should not be a test about the
    writing.
    """
    s = path.read_text(encoding="utf-8")
    s = re.sub(r"/\*.*?\*/", " ", s, flags=re.S)
    s = re.sub(r"<!--.*?-->", " ", s, flags=re.S)
    s = re.sub(r"(?m)^\s*//.*$", " ", s)
    return s


@pytest.fixture(scope="module")
def size():
    spec = importlib.util.spec_from_file_location(
        "generate_size_check", LAB / "generate_size_check.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_the_size_check_shows_the_mark_the_board_would_draw(size, rec):
    """Falsified by looking only in icons/, which is what it did first.

    That is right while every slot has an icon and silently wrong the first time one falls back
    to its wax seal: the page would show thirteen marks and say nothing about the fourteenth, so
    a size chosen on it would have been chosen without looking at the mark it most affects.
    """
    import sys as _sys
    _sys.argv = ["generate_size_check.py"]
    assert size.main() == 0
    page = size.OUT.read_text(encoding="utf-8")
    drawn = [p for p, e in rec.items()
             if p.startswith("duty_actions/") and e.get("slot") in ("left", "right")
             and "/masters/" not in p]
    # Every slot the record places has a mark on the page, named by its action.
    names = set()
    for slug, said in json.loads((BOARD / "duty_text.json").read_text(encoding="utf-8"))[
            "duties"].items():
        for slot in ("actionA", "actionB"):
            if said.get(slot):
                names.add(said[slot]["name"])
    missing = [n for n in names if '"name": "%s"' % n not in page]
    assert not missing, "not on the size check page: %s" % ", ".join(sorted(missing))
    assert drawn, "the record places no marks at all"


def test_the_size_check_takes_the_canvas_from_geometry(size):
    """Falsified by typing the canvas back into the template.

    The page works out the board's own fit for the window it is open in, which needs the canvas
    the board scales to. That was 1400 x 1200 typed into the template for an hour -- correct on
    the day, wrong the moment the canvas moves, and nothing would have noticed. Every other
    number on the page already came from the build; this was the only exception.
    """
    tmpl = _code(SIZE_TMPL)
    assert "__CANVAS__" in tmpl, "the canvas is no longer filled in at build time"
    canvas = size.G.as_dict()["canvas"]
    for n in (canvas["width"], canvas["height"]):
        assert str(n) not in tmpl, "%d is typed into the template and it is geometry.py's" % n
    import sys as _sys
    _sys.argv = ["generate_size_check.py"]
    assert size.main() == 0
    page = size.OUT.read_text(encoding="utf-8")
    want = json.dumps(size.G.as_dict()["canvas"])
    assert "var CANVAS = " + want in page, "the page and geometry.py disagree about the canvas"


def test_the_size_check_does_not_export_baked_marks(size):
    """A VIEWER THAT BECAME A SOURCE WOULD UNDO FOUR THINGS, so it is held to being a viewer.

    Baking the drawn size into a file takes it from geometry.py, so changing SEAL would stop
    restyling the marks and start needing every one re-cut. Baking the ground takes it from the
    record's `ground` field and the single CSS rule that owns the colour -- the thing the board
    only just stopped guessing from pixels. Baking a border turns a style into art. And a file at
    exactly its drawn size is soft on a retina screen, which is why the board inlines at SEAL * 2.

    This test is the decision written down. Falsified by adding an export: if that is ever wanted
    for a rules sheet or print-and-play, it needs its own page and this test should be the thing
    that makes you say so out loud.
    """
    tmpl = _code(SIZE_TMPL)
    for sign in ("toBlob", "download", "URL.createObjectURL", "createElement('canvas')"):
        assert sign not in tmpl, "the size check looks like it has grown an export (%r)" % sign
    src = (LAB / "generate_size_check.py").read_text(encoding="utf-8")
    assert "Image.new" not in src and ".save(" not in src, \
        "the size check builder is writing image files"


def test_the_size_check_falls_back_to_a_seal_when_a_slot_has_no_icon(size, monkeypatch):
    """Falsified by narrowing the walk back to icons/ alone.

    On this tree both rules give the same answer, because every slot has an icon -- so a test
    that only read this tree could not tell them apart, and the first version of it could not.
    A slot holding nothing but a wax seal is the case that separates them.
    """
    monkeypatch.setattr(size, "FOLDERS", ["seals", "icons"])
    monkeypatch.setattr(size, "REC", {
        "duty_actions/clerical/seals/clerical_actionA_seal_v02.webp": {"slot": "left"},
        "duty_actions/clerical/icons/clerical_actionA_icon_v01.webp": {"slot": "left"},
        # Produce's left action never got an icon, so its seal is what the board draws.
        "duty_actions/produce/seals/produce_actionA_seal_v03.webp": {"slot": "left"},
    })
    got = {k: v[1].rsplit("/", 1)[-1] for k, v in size.marks().items()}
    assert got[("clerical", "actionA")] == "clerical_actionA_icon_v01.webp", got
    assert got[("produce", "actionA")] == "produce_actionA_seal_v03.webp", \
        "a slot with only a seal fell off the page entirely: %s" % got


# =================================================================================================
# THE TILE COLUMN, the lab's third page: where a duty's two marks sit.

COL_TMPL = LAB / "tile_column.html.tmpl"


@pytest.fixture(scope="module")
def column():
    spec = importlib.util.spec_from_file_location(
        "generate_tile_column", LAB / "generate_tile_column.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_the_tile_column_opens_at_geometrys_mark_size(column):
    """The size is a slider now, so what has to hold is that it OPENS on the board's number.

    THIS GUARD USED TO SAY THE OPPOSITE, and the reason it changed is worth keeping. It asserted
    `var size = GEO.seal` -- the size was fixed here, on the argument that SEAL had been decided
    and a page drawing anything else would be a sketch of a board that does not exist. That was
    right while editing geometry.py was the only way to draw a different size.
    generate_action_board.py --icons made it a real choice, so the number needs somewhere to be
    chosen, and this is the page that can show it against the tile it has to fit.

    What still has to be true is everything that stopped it being a sketch: it opens at the
    board's SEAL rather than a number typed here, the page is told geometry at build time, and it
    still says what size WOULD fit. Falsified by hard-coding the slider's start, or by letting the
    page invent a size again.
    """
    tmpl = _code(COL_TMPL)
    assert "var size = V('size');" in tmpl, "the mark size is not read from its slider"
    assert "__START_SEAL__" in tmpl, "the slider no longer opens on a value filled in at build time"
    assert "Math.floor((avail - gap) / 2)" in tmpl, \
        "the page no longer says what size WOULD fit, which is the useful half of a refusal"
    assert "__GEO__" in tmpl, "the geometry is no longer filled in at build time"
    assert "GEO.seal" in tmpl, \
        "the page no longer mentions the board's own SEAL, so a slider pushed away from it reads "\
        "as the board rather than as a proposal"
    assert column.START_SEAL == column.G.SEAL, \
        "the page opens at %d while the board draws %d" % (column.START_SEAL, column.G.SEAL)
    assert column.GEO["seal"] == column.G.SEAL, "the page's geometry and geometry.py disagree"


def test_the_tile_column_says_when_a_column_does_not_fit(column, capsys, monkeypatch, tmp_path):
    """Both on the page and on the build, because either alone can be missed.

    At SEAL 100 two marks need 208 px against the 116 the tile has under its name. A build that
    printed nothing while that was true would be a build that looked fine, and a page that only
    said it in a readout is a page you scroll past while the marks hang out of their tiles.
    """
    tmpl = _code(COL_TMPL)
    assert "DOES NOT FIT" in tmpl, "the page no longer refuses out loud"
    assert "classList.toggle('over'" in tmpl, "nothing marks the overflow in the picture"
    page = COL_TMPL.read_text(encoding="utf-8")
    assert "body.over .tile{outline" in page, "there is no style for the refusal"
    # AND THE MARKS HAVE TO BE ABLE TO SPILL. The tile clips, as the board does, and a clipped
    # mark reads as one drawn smaller rather than one that did not fit.
    assert "body.over .tile{overflow:visible}" in page, \
        "the overflow is clipped, so the refusal is a red outline round a tidy picture"

    import sys as _sys
    monkeypatch.setattr(column, "OUT", tmp_path / "generated" / "tile_column.html")
    monkeypatch.setattr(_sys, "argv", ["generate_tile_column.py"])
    assert column.main() == 0
    out = capsys.readouterr().out
    g = column.GEO
    # THE GAP, NOT THE INSET -- the same number the generator uses. The column hangs from the name
    # at GAP, and this read sealInset: two arithmetics for one layout, which agreed only because
    # at the old ribbon height both of them said "does not fit". The board got taller and they
    # stopped agreeing, and the test went red for the page being right.
    avail = g["innerH"] - (g["nameTop"] + round(g["nameSize"] * g["nameLh"]) + column.GAP) \
        - g["sealInset"]
    if 2 * column.G.SEAL > avail:
        assert "need" in out and "RIBBON_H" in out, \
            "two marks do not fit and the build said nothing:\n%s" % out
    else:
        assert "RIBBON_H" not in out, "the build warned about a column that fits:\n%s" % out


def test_the_tile_column_opens_on_a_proposal_and_says_so(column, monkeypatch, tmp_path):
    """Falsified by a page that opens at a height nobody has agreed to without naming the real one.

    The slider used to start at RIBBON_H, so the first thing on screen was the board you have.
    The board you have does not fit a column -- that is the whole finding -- so starting there
    meant opening on the problem and dragging to the answer before you could look at anything.
    It now opens at START_H, which is a proposal, and a proposal is a fine thing to open on
    PROVIDED the page never lets you mistake it for the board: the readout prints RIBBON_H beside
    it and says what the difference costs the wheel. Drop that and the page becomes a picture of a
    board that does not exist, which is the one thing it was built not to be.
    """
    page = COL_TMPL.read_text(encoding="utf-8")
    assert re.search(r'id=tall[^>]*value="__START_H__"', page), \
        "the height slider's starting value is typed into the template"
    # THE REAL NUMBER STAYS ON SCREEN BESIDE THE PROPOSED ONE.
    assert "RIBBON_H is ' + GEO.height" in _code(COL_TMPL), \
        "the readout no longer names the board's own ribbon, so the proposal reads as the board"

    import sys as _sys
    out_file = tmp_path / "generated" / "tile_column.html"
    monkeypatch.setattr(column, "OUT", out_file)
    monkeypatch.setattr(_sys, "argv", ["generate_tile_column.py"])
    assert column.main() == 0
    built = out_file.read_text(encoding="utf-8")
    assert "__START_H__" not in built, "the token survived the build"
    assert 'id=tall type=range min="120" max="320" value="%d"' % column.START_H in built, \
        "the built page opens at some height other than START_H"

    # AND THE SLIDER HAS TO REACH BOTH ENDS OF THE ARGUMENT: the height it opens on, and the
    # board's own, which is what you drag back to when you want to see what you are giving up.
    lo, hi = 120, 320
    for name, v in (("START_H", column.START_H), ("RIBBON_H", column.G.RIBBON_H)):
        assert lo <= v <= hi, "the slider cannot reach %s (%d), which is outside %d..%d" % (
            name, v, lo, hi)

    # THE PROPOSAL HAS TO BE ONE. A START_H that does not fit the column it exists to show is
    # worse than opening on the board, because it looks like the answer and is not.
    geo = column.GEO
    top = geo["nameTop"] + round(geo["nameSize"] * geo["nameLh"]) + column.GAP
    avail = (column.START_H - 2 * column.G.BORDER) - top - geo["sealInset"]
    assert 2 * column.G.SEAL + column.GAP <= avail, \
        "the page opens on a height where the column still does not fit: needs %d, has %d" % (
            2 * column.G.SEAL + column.GAP, avail)

    # LAST, BECAUSE IT MOVES THE NUMBER EVERYTHING ABOVE READS. str(START_H) and a typed "265" are
    # the same bytes while START_H is 265, so the only way to tell them apart is to change it --
    # and doing that any earlier quietly points every assertion above at the height this check
    # invented rather than the one the page ships with. It did, for one run.
    monkeypatch.setattr(column, "START_H", 300)
    assert column.main() == 0
    assert 'id=tall type=range min="120" max="320" value="300"' in \
        out_file.read_text(encoding="utf-8"), "the slider did not follow START_H"


def test_the_tile_column_says_who_pays_for_a_taller_tile(column, capsys, monkeypatch, tmp_path):
    """Falsified by a height slider that moves the tile and reports only how far it moved.

    Nothing below the ribbon shrinks when it grows: ART_Y is RIBBON_Y + RIBBON_H + GAP and the
    rest of the board follows down from there. The wheel is the one elastic thing, because WHEEL_H
    is whatever the canvas has left over -- so the wheel pays every pixel, and it keeps its asset's
    aspect, so it narrows by about twice what it loses. "Grown 92 px" is the one number in that
    sentence nobody can hold an opinion about; 1106 x 586 becoming 932 x 494 is not.
    """
    G, geo = column.G, column.GEO
    assert (geo["wheelH"], geo["wheelW"]) == (G.WHEEL_H, G.WHEEL_W), \
        "the page is not handed the wheel, so it cannot price a height"
    assert geo["wheelRatio"] == G.WHEEL_RATIO, "the page cannot narrow the wheel as it shortens"
    assert geo["border"] == G.BORDER, "the tile's inner height is guessed rather than derived"

    tmpl = _code(COL_TMPL)
    assert "GEO.wheelH - grew" in tmpl, "the page does not take the growth off the wheel"
    assert "wheelH / GEO.wheelRatio" in tmpl, "the wheel keeps its width as it loses height"

    # EVERY BRANCH, NOT SOMEWHERE IN THE FILE. "GEO.wheelW appears and so does c.wheelW" passed a
    # mutant that reported bare growth for a taller tile and named both wheels only in the two
    # branches nobody looks at -- shorter, and exactly as the board is. The branch that matters is
    # the one you reach by dragging the slider the way it is meant to be dragged, so each return
    # out of cost() has to name the wheel it was and the wheel it becomes.
    body = re.search(r"function cost\(c\)\{(.*?)\n\}", tmpl, re.S)
    assert body, "cost() is gone, so nothing turns a height into the wheel's numbers"
    rets = [r.strip() for r in re.findall(r"return (.*?);", body.group(1), re.S)]
    assert len(rets) == 3, "cost() no longer answers all three of taller, shorter and unchanged"
    for r in rets:
        assert re.search(r"GEO\.wheelW|\bwas\b", r), \
            "a branch of cost() reports a height without naming the wheel:\n%s" % r
    # THE LAST ONE IS THE ONE THAT MATTERS. cost() returns early for a tile at the board's own
    # height, where the wheel is unchanged and naming it twice would be silly, and for a shorter
    # one; what is left is the taller tile, which is the only reason anyone drags the slider, and
    # it has to name the wheel it was and the wheel it becomes.
    assert re.search(r"c\.wheelW|\bnow\b", rets[-1]) and re.search(r"GEO\.wheelW|\bwas\b",
                                                                    rets[-1]), \
        "a taller tile is reported without saying what the wheel becomes:\n%s" % rets[-1]

    # AND THE BUILD SAYS IT TOO, in numbers this test can check rather than words it can match.
    import sys as _sys
    monkeypatch.setattr(column, "OUT", tmp_path / "generated" / "tile_column.html")
    monkeypatch.setattr(_sys, "argv", ["generate_tile_column.py"])
    assert column.main() == 0
    out = capsys.readouterr().out
    avail = geo["innerH"] - (geo["nameTop"] + round(geo["nameSize"] * geo["nameLh"])
                             + geo["sealInset"]) - geo["sealInset"]
    if 2 * G.SEAL <= avail:
        pytest.skip("a column already fits, so there is no height to price")
    want = (geo["nameTop"] + round(geo["nameSize"] * geo["nameLh"]) + column.GAP
            + 2 * G.SEAL + column.GAP + geo["sealInset"] + 2 * G.BORDER)
    tall = G.WHEEL_H - (want - G.RIBBON_H)
    assert "%d x %d becomes %d x %d" % (G.WHEEL_W, G.WHEEL_H,
                                        round(tall / G.WHEEL_RATIO), tall) in out, \
        "the build asks for a taller ribbon without saying what it costs:\n%s" % out


def test_the_height_slider_actually_moves_the_tiles(column):
    """Falsified by leaving the tiles at geometry's RIBBON_H while the readout reports the slider.

    This is the whole of the feature and it was the mutant that survived first time round: pinning
    the tile's height back to GEO.height left every number on the page right and every tile on the
    page wrong, and twenty-three assertions sailed past it. The readout is the easy half to get
    right and the useless half to get right alone.

    IT IS A SHAPE CHECK, NOT A RENDERING CHECK. The lab lane installs no browser on purpose -- it
    is the lane you run when you add a duty's pair, and it takes seconds -- so this reads the
    template rather than driving it: every assignment to a tile's height has to come from the
    column, which reads the slider, and none may read RIBBON_H. The picture itself was checked by
    driving the page headless, which is a thing done by hand and not in CI.
    """
    tmpl = _code(COL_TMPL)
    # IN COLUMN(), NOT ANYWHERE IN THE FILE. "V('tall') appears" passed a mutant that pinned the
    # column to GEO.height, because the slider's own label still read its value to print it: the
    # number beside the slider moved and nothing else did.
    col = re.search(r"function column\(\)\{(.*?)\n\}", tmpl, re.S)
    assert col, "column() is gone"
    assert "V('tall')" in col.group(1), \
        "the column no longer reads the height slider, so only its label moves"

    sets = re.findall(r"tile\.style\.height = ([^;]+);", tmpl)
    assert len(sets) >= 2, \
        "the tile's height is set in fewer places than it is drawn, so one of build() and " \
        "place() leaves it behind: %s" % sets
    for rhs in sets:
        assert "c.h" in rhs, \
            "a tile takes its height from something other than the column: %s" % rhs.strip()
        assert "GEO.height" not in rhs, \
            "a tile is pinned to RIBBON_H, so the slider moves a number and not a tile"

    # AND THE PAGE HAS TO GROW WITH THEM, or taller tiles slide under the note below.
    assert re.search(r"scroll'\)\.style\.height = \(c\.h \* s", tmpl), \
        "the scroller still reserves geometry's height, so the tiles overflow the page"

    # AND A PRICE WORTH NOTICING IS MARKED. Not an error -- nothing is broken by a smaller wheel --
    # but a cost rendered in the same grey as everything else is a cost you read past, which is
    # the failure this whole readout exists to avoid.
    # AND THE SLIDER HAS TO REDRAW. A handler that moves its own label and nothing else leaves
    # the number under your thumb telling the truth about a picture that has not changed.
    h = re.search(r"getElementById\('tall'\)\.addEventListener\('input', function\(\)\{(.*?)\}\);",
                  tmpl, re.S)
    assert h, "the height slider has no handler, so it does nothing at all"
    assert "place()" in h.group(1), \
        "the height slider updates its label and leaves the tiles where they were"

    mark = re.search(r"classList\.toggle\('([a-z]+)', c\.grew > 0", tmpl)
    assert mark, "nothing marks a height whose cost is worth looking at"
    assert "body.%s #read" % mark.group(1) in COL_TMPL.read_text(encoding="utf-8"), \
        "the mark is set and never styled, so it says nothing"


def test_one_gap_does_both_jobs_and_every_first_mark_shares_a_line(column, capsys, monkeypatch,
                                                                    tmp_path):
    """Falsified by hanging the column from SEAL_INSET, or by centring it in what is left over.

    Two separate failures with one cause, which is why they are one test. The space under the duty
    name used to be SEAL_INSET while the space between the two marks was the slider's, so the two
    went visibly out of step the moment you touched the slider -- a tile with a tight title and a
    loose middle, or the reverse, and never a rhythm. And the marks were then centred in whatever
    was left, which is fine while every tile holds two: Taxation and Allocation hold one each, so
    theirs sat half a mark lower than the top mark of every tile beside them. On a ribbon of eight
    that reads as two tiles done wrong rather than as two tiles that are different.

    Both go away by hanging the column from the name at the gap and letting it fall from there:
    where a mark sits stops depending on how many the tile has.
    """
    tmpl = _code(COL_TMPL)
    col = re.search(r"function column\(\)\{(.*?)\n\}", tmpl, re.S).group(1)
    assert re.search(r"top = GEO\.nameTop \+ nameH \+ gap", col), \
        "the space under the name is not the gap, so the two spacings can drift apart again"
    assert "sealInset" not in col.split("var top")[0], \
        "something above the name's own inset is deciding where the column starts"

    place = re.search(r"function place\(\)\{(.*?)\n\}", tmpl, re.S).group(1)
    assert ".length" not in place, \
        "where a mark sits depends on how many the tile has, so the single-action tiles drop " \
        "off the line their neighbours sit on"
    assert re.search(r"style\.top = \(c\.top \+ i \* \(c\.size \+ c\.gap\)\)", place), \
        "the column no longer hangs from the name at the gap"

    # THE SLIDER AND THE BUILD'S ARITHMETIC START FROM THE SAME NUMBER, or the build reports on a
    # page nobody is looking at.
    import sys as _sys
    out_file = tmp_path / "generated" / "tile_column.html"
    monkeypatch.setattr(column, "OUT", out_file)
    monkeypatch.setattr(_sys, "argv", ["generate_tile_column.py"])
    assert column.main() == 0
    built = out_file.read_text(encoding="utf-8")
    assert "__GAP__" not in built, "the token survived the build"
    assert 'id=gap type=range min="0" max="40" value="%d"' % column.GAP in built, \
        "the gap slider opens on a number the build does not use"

    # MOVE THE ONE NUMBER AND WATCH BOTH FOLLOW. Asserting the arithmetic matches GAP is no test
    # while GAP is 8 and the old literal was 8 too -- the two are indistinguishable until the
    # number changes. So change it, and require the slider and the height the build asks for to
    # move together.
    G, geo = column.G, column.GEO
    monkeypatch.setattr(column, "GAP", 20)
    assert column.main() == 0
    built = out_file.read_text(encoding="utf-8")
    assert 'id=gap type=range min="0" max="40" value="20"' in built, \
        "the slider did not follow the gap"
    want = (geo["nameTop"] + round(geo["nameSize"] * geo["nameLh"]) + 20
            + 2 * G.SEAL + 20 + geo["sealInset"] + 2 * G.BORDER)
    assert "RIBBON_H of about %d" % want in capsys.readouterr().out, \
        "the build's arithmetic kept a gap of its own, so it reports on a page nobody is looking at"


def test_the_icon_border_has_one_owner():
    """The slider is the thickness AND whether there is a border; the button only moves it.

    A BUTTON THAT TOGGLED ITS OWN CLASS would be a second answer to "is there a border", and the
    two drift the moment you drag the slider to 0 with the button still reading pressed. The page
    has made this mistake in a neighbouring form before -- the comment above column() records a
    gap that was `SEAL_INSET` under the name and the slider's value between, two numbers nobody
    chose together that went visibly out of step.

    A static check, because the lab lane installs no browser; the behaviour itself was driven in
    one. Falsified by giving the button back a classList.toggle of its own, or by letting the
    border be a fixed width again.
    """
    tmpl = _code(COL_TMPL)
    assert "var(--edge-w" in tmpl, "the border is a fixed width again, so it cannot be dragged"
    assert "classList.toggle('edged', w > 0)" in tmpl, \
        "whether there is a border no longer follows the slider's own number"
    toggle = tmpl.split("getElementById('edgetoggle').onclick")[1].split("};")[0]
    assert "classList.toggle" not in toggle, \
        "the button toggles a class of its own again, so it can disagree with the slider"
    assert "applyEdge()" in toggle, "the button no longer goes through the one function that sets it"


def test_a_thicker_icon_border_eats_the_mark_rather_than_growing_it():
    """Everything here is border-box, and the fit arithmetic depends on it.

    column() reports whether two marks of `size` fit the tile. If a border grew the mark's box
    instead of being drawn inside it, every one of those numbers would be short by twice the
    thickness and the page would say a column fits while the marks hung out of the tile -- the
    exact failure the red outline exists to make unmissable. Falsified by dropping the
    border-box rule, or by putting the border on something that is not the mark's own box.
    """
    tmpl = _code(COL_TMPL)
    assert "*{box-sizing:border-box}" in tmpl, \
        "border-box is gone, so a thicker border now grows the mark past where it was placed"
    assert "body.edged .mark{border:var(--edge-w" in tmpl, \
        "the border is no longer on the mark's own box"


def _lstar(hexcol):
    """CIE L* of an sRGB hex colour. Twenty lines rather than a dependency, as elsewhere here."""
    r, g, b = (int(hexcol[i:i + 2], 16) / 255 for i in (1, 3, 5))
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
    y = 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    return 116 * (y ** (1 / 3)) - 16 if y > 0.008856 else 903.3 * y


def test_every_plate_in_the_picker_is_the_same_weight():
    """Choosing a colour must not quietly be choosing how legible the marks are.

    The five plates were built at one lightness on purpose -- L* 10.8, which is today's violet
    measured rather than guessed, and within a tenth of the fourteen cards' own median. Because
    they share it, the bone-white mark reads the same distance above every one of them, so the
    picker changes hue and nothing else. A plate dropped in at a different lightness would make
    one option legible and another not, and it would look like a palette preference rather than
    the mistake it is.

    Falsified by adding a plate off the line, or by making a frame lighter than its plate.
    """
    tmpl = COL_TMPL.read_text(encoding="utf-8")
    m = re.search(r"var PALETTE = (\[.*?\]);", tmpl, re.S)
    assert m, "the page no longer carries a PALETTE for the picker"
    pal = json.loads(m.group(1))
    assert len(pal) == 5, "expected five plates, found %d" % len(pal)

    ls = [_lstar(p["plate"]) for p in pal]
    assert max(ls) - min(ls) < 1.0, (
        "the five plates span %.1f L*, so the marks do not read the same against all of them: %s"
        % (max(ls) - min(ls), ["%s %.1f" % (p["name"], l) for p, l in zip(pal, ls)]))

    for p in pal:
        assert _lstar(p["frame"]) < _lstar(p["plate"]), (
            "%s's frame is not darker than its plate, so the edge reads as raised rather than "
            "as a cut line" % p["name"])
    assert any(p["plate"].upper() == "#1E1935" for p in pal), (
        "today's violet is not among the five, so the others cannot be compared against it")
