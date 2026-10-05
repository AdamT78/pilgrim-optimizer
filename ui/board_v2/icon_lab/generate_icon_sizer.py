#!/usr/bin/env python3
"""Build the icon sizer: one page for choosing how a cut-out icon is framed in its tile slot.

    python3 ui/board_v2/icon_lab/generate_icon_sizer.py
    python3 ui/board_v2/icon_lab/generate_icon_sizer.py --open

WHAT THIS LAB IS FOR. The wax seals were drawn to fill their own square and needed no decisions --
tools/duty_art/file_seals.py scales every one of them to the discs' 0.906 and that is the end of
it. An icon is different: the generator returns a 1254 square with the mark somewhere inside it
and a wide transparent margin, and the framing -- how much of that square the board draws, and
which part -- is a judgement nobody can make from the file alone. This page is where that
judgement is made and, more to the point, where it is written down.

IT SEEDS FROM THE MASTERS. The shipped icon is already a cut; opening it here and cutting again
would be cutting a cut, and every pass costs resolution that cannot come back. The master is the
untouched download, so a framing chosen here is always one trim away from the generator's own
pixels however many times it is revisited -- including for an icon whose cut was accepted weeks
ago.

A MASTER WITH NO CUT YET IS THE NORMAL CASE, not an edge one. Five arrived at once with nothing
cut from any of them, and a lab that only knew how to re-frame an accepted cut would have shown
an empty page on the day it was most wanted.
"""
import argparse
import base64
import json
import pathlib
import re
import sys
import webbrowser

HERE = pathlib.Path(__file__).resolve().parent
BOARD = HERE.parent
ART_DIR = BOARD / "duty_actions"
CONTROL_DIR = BOARD / "controls"
ATTRIB_FILE = BOARD / "attribution.json"
TEXT_FILE = BOARD / "duty_text.json"
TMPL = HERE / "icon_sizer.html.tmpl"
FRAMING_FILE = HERE / "framing.json"
OUT = HERE / "generated" / "icon_sizer.html"

# WHICH MARKS ARE FRAMED BY HAND, which is this lab's question and nobody else's.
#
# attribution.json owns the list of folders a tile mark may live in, because the board and the
# duty art lab both have to agree about it. This is a narrower fact and it stays here: a `seals`
# master has no framing to choose, since file_seals.py normalises it on the way in, and that
# difference is the whole reason the two folders are separate. If a third kind of hand-framed mark
# ever appears it joins this list, and the tree need not be told.
FRAMED_SUBDIRS = ("icons",)
MASTERS = "masters"

# WHAT A CUT IS SAVED AS, and it is not what a master is saved as. attribution.json's
# imageSuffixesNote owns the reasoning -- the prints are WebP at quality 90 and the archive is
# PNG, because a lossy archive is not one -- and `master_of` below hard-codes `.png` for the same
# reason from the other end. The page encodes it; this only has to agree about the name.
PRINT_SUFFIX = ".webp"


def image_suffixes() -> tuple:
    """Extensions an image in this tree may carry, per attribution.json.

    The same list the action board reads, from the same place. It is here because a walk that
    takes whatever a folder contains takes macOS's `.DS_Store` too, and this one did: the build
    reported it as a cut with no master, which is true and useless.
    """
    try:
        got = json.loads(ATTRIB_FILE.read_text(encoding="utf-8")).get("imageSuffixes")
    except Exception:
        got = None
    return tuple(got) if got else (".png", ".webp")


def _records() -> dict:
    if not ATTRIB_FILE.is_file():
        raise SystemExit("there is no attribution.json at %s" % ATTRIB_FILE)
    return json.loads(ATTRIB_FILE.read_text(encoding="utf-8")).get("files", {})


def master_of(rel: str, entry: dict | None = None) -> str:
    """Where the untouched original of a shipped mark lives.

    THE RECORD FIRST, THE NAME AS A FALLBACK, and that order is newer than this function. The
    name was the link for as long as a cut and its master carried the same version. Then Build
    Roads' FIFTH cut was made from its FOURTH master -- `next_cut` takes the next free cut number
    and a master keeps its own, so the two came apart the first time a slot was re-cut -- and
    `..._icon_v05.png` went looking for a `..._icon_master_v05.png` that will never exist. A cut
    that says which master it came from is the honest answer, and the name still answers for the
    ninety-odd files recorded before the field existed.

    THE SUFFIX DOES NOT CARRY OVER, and assuming it did is how this was first written. The shipped
    prints are WebP and the masters are PNG -- attribution.json's imageSuffixesNote says why, and
    it is the whole point of a master: a lossy archive is not one. So fourteen marks whose masters
    were sitting right there were reported missing, because the lab went looking for a .webp
    beside a .png.
    """
    folder, _, name = rel.rpartition("/")
    if entry and entry.get("master"):
        return "%s/%s/%s" % (folder, MASTERS, entry["master"])
    stem = name.rsplit(".", 1)[0]
    return "%s/%s/%s.png" % (folder, MASTERS, re.sub(r"_(v\d+)$", r"_master_\1", stem))


def slot_in_name(name: str) -> str | None:
    """Which of a duty's two actions a file is for, from its own name.

    EVERY MARK IN THIS TREE CARRIES IT -- `build_roads_actionA_icon_master_v04` -- and for a
    master it is the only place it is written: the record files a master under `slot: "master"`,
    which says what kind of file it is and not which action it belongs to. A file that does not
    say is left out and named rather than guessed into a slot.
    """
    m = re.search(r"_(action[AB])_", name)
    return m.group(1) if m else None


def next_cut(duty: str, slot: str, sub_dir: str) -> str:
    """What the tree would call the next cut of this mark.

    A cut saved over the file it was cut from would orphan that file's recorded sha256 and leave
    attribution.json describing pixels that are gone. The lab offers the next free number instead,
    the same way the action board's save does, so a framing can be tried without anything being
    overwritten to try it. A slot with nothing cut yet starts at v01.
    """
    base = "%s_%s_%s" % (duty, slot, re.sub(r"s$", "", sub_dir))
    folder = ART_DIR / duty / sub_dir
    n = 0
    if folder.is_dir():
        for f in folder.iterdir():
            m = re.match(re.escape(base) + r"_v(\d+)$", f.stem)
            if m:
                n = max(n, int(m.group(1)))
    return "%s_v%02d%s" % (base, n + 1, PRINT_SUFFIX)


def names() -> dict:
    """What each action is called, from the file that owns the wording."""
    doc = json.loads(TEXT_FILE.read_text(encoding="utf-8")).get("duties", {})
    out = {}
    for slug, said in doc.items():
        for slot in ("actionA", "actionB"):
            s = said.get(slot)
            if s and s.get("name"):
                out["%s:%s" % (slug, slot)] = s["name"]
    return out


def control_names() -> dict:
    """What the three marks in the controls column are called, from the same file.

    READ, NOT LISTED. "Show Map", "Hire Building" and "Confirm" were a JS object typed into
    action_board.html.tmpl, and a second copy here would have been the same fault twice. They are
    in duty_text.json's `controls` block now, which is where the board reads them too -- so a
    rename reaches the card in this lab and the title on the board from one edit.
    """
    return json.loads(TEXT_FILE.read_text(encoding="utf-8")).get("controls", {})


def saved_framing() -> dict:
    """The framing last written back into the lab, if there is one.

    THIS FILE IS THE RECORD AND THE BROWSER IS A SCRATCHPAD. The page remembers your last framing
    in the browser so that reopening it simply works, but a browser store is not something you can
    read, diff or commit, and this project does not keep facts where they cannot be seen. So the
    page also hands back a framing.json, this reads it, and the page says out loud which of the two
    it is showing whenever they differ. Nothing is silently preferred.
    """
    if not FRAMING_FILE.is_file():
        return {}
    try:
        return json.loads(FRAMING_FILE.read_text(encoding="utf-8"))
    except ValueError as e:
        raise SystemExit("%s is not readable as JSON: %s" % (FRAMING_FILE, e))


def _card(master: pathlib.Path, label: str, out_name: str) -> dict:
    """One master, as the page wants it. The only place a seed's shape is written."""
    return {"name": label,
            "file": master.name,
            "out": out_name,
            "src": "data:image/png;base64," + base64.b64encode(master.read_bytes()).decode()}


def _duty_seeds(rec: dict) -> tuple[list, list]:
    """The duty actions' icon masters: eight folders, two slots each, named from duty_text.json."""
    label = names()
    out, notes = [], []
    want = set(image_suffixes())
    if not ART_DIR.is_dir():
        return out, ["there is no %s, so there are no duty icons to frame" % ART_DIR]

    for duty_dir in sorted(p for p in ART_DIR.iterdir() if p.is_dir()):
        duty = duty_dir.name
        for sub_dir in FRAMED_SUBDIRS:
            masters = duty_dir / sub_dir / MASTERS
            if not masters.is_dir():
                continue

            # A CUT WITHOUT A MASTER CANNOT BE REVISITED, only re-cut, and that is worth saying
            # out loud rather than leaving somebody to wonder why their icon has no card.
            for f in sorted((duty_dir / sub_dir).glob("*")):
                if not f.is_file() or f.suffix.lower() not in want:
                    continue
                crel = f.relative_to(ART_DIR).as_posix()
                if not (ART_DIR / master_of(crel, rec.get("duty_actions/" + crel))).is_file():
                    notes.append("%s has no master, so its framing cannot be revisited here "
                                 "without cutting a cut" % f.name)

            for f in sorted(masters.glob("*")):
                if not f.is_file() or f.suffix.lower() not in want:
                    continue
                rel = f.relative_to(ART_DIR).as_posix()
                if "duty_actions/" + rel not in rec:
                    notes.append("%s: no attribution entry, left out" % rel)
                    continue
                slot = slot_in_name(f.name)
                if slot is None:
                    notes.append("%s: the name does not say which action, left out" % rel)
                    continue
                out.append(_card(f, label.get("%s:%s" % (duty, slot), "%s %s" % (duty, slot)),
                                 next_cut(duty, slot, sub_dir)))
    return out, notes


def _control_seeds(rec: dict) -> tuple[list, list]:
    """The controls column's three marks, which are not duty actions and are not shaped like them.

    A DUTY ICON IS FOUND BY ITS DUTY AND ITS SLOT -- `allocation/icons/masters/allocation_actionA_
    icon_master_v01.png` -- and neither of those exists here. These three belong to the board, not
    to a duty, and there is no actionA/actionB to be: pressing a mark in that column is not a move
    the engine scores. Hanging them off a ninth folder under duty_actions/ would have made this
    walk shorter and every OTHER walk in the tree need an exception, so they have a root.

    WHAT IS THE SAME is everything that matters to this page: a 1254 square with a mark somewhere
    inside it and a transparent margin, a judgement to make about how much of it the board draws,
    and a record saying where it came from. So they get the same card, by the same rules, and the
    page cannot tell them apart -- which is right. The framing question does not care whose icon
    it is.

    THE KEY IS THE MARK'S OWN NAME, from geometry.py's MARKS_ORDER by way of duty_text.json:
    `control_commit_icon_master_v01.png` is the commit's. A file whose key is not one of the three
    is named and left out rather than guessed at, exactly as a duty master with no slot is.
    """
    out, notes = [], []
    want = set(image_suffixes())
    masters = CONTROL_DIR / "icons" / MASTERS
    if not masters.is_dir():
        return out, notes

    said = control_names()
    for f in sorted((CONTROL_DIR / "icons").glob("*")):
        if not f.is_file() or f.suffix.lower() not in want:
            continue
        crel = f.relative_to(CONTROL_DIR).as_posix()
        if not (CONTROL_DIR / master_of(crel, rec.get("controls/" + crel))).is_file():
            notes.append("%s has no master, so its framing cannot be revisited here without "
                         "cutting a cut" % f.name)

    for f in sorted(masters.glob("*")):
        if not f.is_file() or f.suffix.lower() not in want:
            continue
        rel = f.relative_to(CONTROL_DIR).as_posix()
        if "controls/" + rel not in rec:
            notes.append("%s: no attribution entry, left out" % rel)
            continue
        m = re.match(r"control_([a-z0-9]+)_icon_master_v\d+$", f.stem)
        if not m or m.group(1) not in said:
            notes.append("%s: the name does not say which control, left out -- duty_text.json's "
                         "controls block knows %s" % (rel, ", ".join(sorted(said)) or "none"))
            continue
        key = m.group(1)
        out.append(_card(f, said[key].get("name") or key, next_control_cut(key)))
    return out, notes


def next_control_cut(key: str) -> str:
    """What the tree would call the next cut of a control mark.

    The same rule next_cut() follows for a duty's, and separate from it because the names are
    shaped differently: a control has no duty and no slot, so there is nothing for that function's
    arguments to be. Both answer the same question -- never hand back a name that would overwrite
    a file whose sha256 is already recorded.
    """
    base = "control_%s_icon" % key
    folder = CONTROL_DIR / "icons"
    n = 0
    if folder.is_dir():
        for f in folder.iterdir():
            m = re.match(re.escape(base) + r"_v(\d+)$", f.stem)
            if m:
                n = max(n, int(m.group(1)))
    return "%s_v%02d%s" % (base, n + 1, PRINT_SUFFIX)


def seeds() -> tuple[list, list]:
    """Every icon master in the tree, as the page wants it.

    TWO ROOTS, ONE PAGE. The duty actions' icons and the board's three controls are filed apart
    because everything else in the tree treats them differently; they are framed together because
    this lab's question -- how much of a 1254 square does the board draw -- is the same for both.
    """
    rec = _records()
    duty, dnotes = _duty_seeds(rec)
    ctrl, cnotes = _control_seeds(rec)
    out = duty + ctrl
    notes = dnotes + cnotes
    if not out:
        notes.append("no icon master is filed under %s or %s, so there is nothing to frame; "
                     "the page still takes files dropped onto it" % (ART_DIR, CONTROL_DIR))
    return out, notes


def build() -> tuple[str, list]:
    if not TMPL.is_file():
        raise SystemExit("the template is not at %s" % TMPL)
    seed, notes = seeds()
    page = TMPL.read_text(encoding="utf-8")
    fill = {"__SEED__": json.dumps(seed), "__FRAMING__": json.dumps(saved_framing())}
    for token, value in fill.items():
        if token not in page:
            raise SystemExit("the template has no %s in it, so the build would be dropped on the "
                             "floor" % token)
        page = page.replace(token, value)
    return page, notes


def main() -> int:
    # SAME FLAG AND SAME SPELLING AS THE ACTION BOARD'S, because two generators in one tree that
    # disagree about how to open their own output is a thing you have to look up every time.
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--open", action="store_true", help="open the page when it is built")
    a = ap.parse_args()

    page, notes = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding="utf-8")
    print("  wrote %s  (%d KB)" % (OUT, len(page.encode("utf-8")) // 1024))
    held = saved_framing().get("icons") or {}
    print("  %d icon master(s);  %s"
          % (len(seeds()[0]),
             "framing.json holds %d of them" % len(held) if held
             else "no framing.json yet, so every card opens fitted to its own mark"))
    for n in notes:
        print("  %s" % n)

    # NOTHING IS CUT UNTIL SOMETHING IS CUT, which is worth saying on every build. A framing in
    # framing.json changes what this page shows and what its `cut` button hands back; it does not
    # change a single pixel the board draws. That only happens when a cut is filed into the icons
    # folder and recorded, and until then the board goes on drawing whatever is there.
    #
    # THE QUESTION IS NOT WHETHER THE NEXT NAME IS FREE, which is what this asked first. Of course
    # it is free -- `next_cut` picked it for being free -- so once anything had been cut the line
    # listed all fourteen every time and meant nothing. What matters is whether the cut on disk
    # was taken at the framing now on the page.
    never, moved = [], []
    for s in seeds()[0]:
        want = (held.get(s["file"]) or {}).get("crop")
        if not want:
            continue
        cut = _cut_from(s["file"])
        if cut is None:
            never.append(s["name"])
        elif cut[1] != want:
            moved.append("%s (cut at %d,%d %d square; framed at %d,%d %d)"
                         % (cut[0], cut[1]["x"], cut[1]["y"], cut[1]["w"],
                            want["x"], want["y"], want["w"]))
    if never:
        print("  framed but never cut: %s" % ", ".join(sorted(never)))
    if moved:
        print("  the framing has moved since these were cut:")
        for m in sorted(moved):
            print("    %s" % m)
    if never or moved:
        print("  the board draws what is in the icons folders, not what is in framing.json")

    if a.open:
        webbrowser.open(OUT.as_uri())
    return 0


def _cut_from(master_name: str) -> tuple | None:
    """The newest cut taken from this master, and the crop it was taken at.

    ASKED OF THE RECORD, NOT OF THE FILENAMES. A cut names its master in a field precisely because
    the two versions come apart -- Build Roads' fifth cut was taken from its fourth master -- so
    walking the folder and matching numbers would find the wrong one or none at all.

    BOTH ROOTS, which this missed when the controls arrived. It filtered on `duty_actions/`, so the
    three control cuts were invisible to it and the build reported them "framed but never cut" with
    the cuts sitting right there -- a line that is worse than silence, because it reads as a job
    still to do. The lesson is the one the seeds walk already learned: a second root is a second
    place every path filter in this file has to know about.
    """
    best = None
    for path, e in _records().items():
        if "/masters/" in path:
            continue
        if not (path.startswith("duty_actions/") or path.startswith("controls/")):
            continue
        if e.get("master") != master_name or not e.get("crop"):
            continue
        name = path.rsplit("/", 1)[-1]
        if not (BOARD / path).is_file():
            continue
        v = version_of(name)
        if best is None or v > best[0]:
            best = (v, name, e["crop"])
    return (best[1], best[2]) if best else None


def version_of(name: str) -> int:
    """The _vNN on the end of a name, or -1 for a name that carries none."""
    m = re.search(r"_v(\d+)\.", name)
    return int(m.group(1)) if m else -1


if __name__ == "__main__":
    sys.exit(main())
