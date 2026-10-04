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
