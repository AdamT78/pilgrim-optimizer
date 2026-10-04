#!/usr/bin/env python3
"""The action board at its finished size, with the pictures in it and no controls.

    python3 ui/board_v2/action_board/generate_action_board.py --open
    python3 ui/board_v2/action_board/generate_action_board.py --serve --open

WHAT THIS IS, AND WHAT IT DELIBERATELY IS NOT

It draws ONE board, at 1400 x 1200, from geometry.py -- and it has no sliders, no drag handles,
no inspector and no zoom. That is not an omission to be filled in later: the layout lab exists to
FIND those numbers and has a control for every one of them, and this page exists because the
search finished. A board whose geometry can be nudged is a board nobody can write a game against,
and every reasonable request to "just add a control for" is how the lab reached 3,840 lines.

What it does have is the two things the lab cannot do well: it shows the board as it will
actually be, and it lets you put pictures into it.

A DELIBERATE FORK, AND WHAT IS EXPECTED TO DIVERGE

The wheel drawing and the acolytes are RE-IMPLEMENTED here rather than imported from
layout_lab/. That is not an oversight and it should not be "tidied up" by unifying them.

Two reasons. There is no seam to import through: on the Python side the wheel is seventy lines,
but the figure drawing lives scattered through the lab's template -- "acolytes" appears 29 times
in it, across the render path and three separate CSS rules -- so the half that matters would be
copied either way, just while pretending otherwise. And they are MEANT to diverge: the wheel is
being redesigned, the centre will stop holding acolytes, they will be shown in the City box
instead, and placement will become a function of how many figures occupy a space. Importing
would couple this tool to a design that is on its way out.

The SVG itself is borrowed by path rather than copied, because an asset read from a path couples
nothing. When the redesign lands, geometry.WHEEL_ASSET changes and nothing else does.

THE ART COMES FROM THE REPOSITORY, AND THE RECORD GATES IT

bundled_art() walks duty_actions/ and takes the newest file for each duty and slot -- but only a
file that attribution.json has an entry for. A file with no record is left out and named on
stderr rather than guessed into place. That is the rule, not a limitation: this tree does not
ship a picture nobody can say where it came from. It also means you can fill all twelve empty
slots today without this tool's save button: drop the file in, add its record, re-run.

Twelve of the fourteen action slots are empty at the time of writing, and the empty state is the
one this page spends most of its life in, so it is the state it is designed for.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import pathlib
import re
import sys
import webbrowser

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import geometry as G                                                    # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
BOARD = HERE.parent
ROOT = BOARD.parents[1]
TMPL = HERE / "action_board.html.tmpl"
OUT = HERE / "generated" / "action_board.html"
TEXT_FILE = BOARD / "duty_text.json"
ATTRIB_FILE = BOARD / "attribution.json"
ART_DIR = BOARD / "duty_actions"
TOKEN_DIR = BOARD / "tokens" / "resources"
MANIFEST = BOARD / "metadata" / "action_board.json"

# A duty's marks live under its own folder, beside the pictures of its actions, because they are
# two drawings OF THE SAME ACTION and splitting them would make a slot's art and a slot's mark two
# things to keep in step. The fallback below is the tree as it stood when `seals` was the only kind
# of mark there was; what the tree actually has is attribution.json's business.
MARK_SUBDIR = "seals"


def mark_folders() -> tuple:
    """The folders a duty's tile mark may live in, per attribution.json.

    THERE USED TO BE ONE AND ITS NAME WAS TYPED IN BOTH TOOLS THAT READ THIS TREE. Then a mark arrived that was not
    a wax disc -- a cut-out icon, with no wax, no colour code and nothing to take -- and filing it
    under `seals` would have made the tree say a thing that is not true. It got `icons`, and the
    list of folders to look in went where the other shared facts about this tree already live,
    because the last time a folder name was learned by one tool and not the others the layout lab
    drew a 78px seal as a 590 x 295 action card.
    """
    try:
        got = json.loads(ATTRIB_FILE.read_text(encoding="utf-8")).get("markFolders")
    except Exception:
        got = None
    return tuple(got) if got else (MARK_SUBDIR,)


def non_slot_folders() -> tuple:
    """Folder names under a duty that are NOT one of its actions, per attribution.json.

    THE SKIP IS A SHARED FACT AND SO IS THE LIST ABOVE, and they are still two facts. A mark
    folder is one a mark lives in; a non-slot folder is one that is not an action, which also
    covers `masters`. Every mark folder has to be in here, and a test says so rather than this
    deriving it, because the day something is skipped that holds no mark, deriving breaks.
    Three tools walk this tree. Each carried its own copy of the word "masters", so when `seals`
    appeared only this one was taught about it -- and the layout lab went on to draw a wax
    seal of 78 pixels as Clerical`s 590 x 295 action card. The fallback is the tree as it
    stood before the key existed.
    """
    try:
        got = json.loads(ATTRIB_FILE.read_text(encoding="utf-8")).get("nonSlotFolders")
    except Exception:
        got = None
    return tuple(got) if got else ("masters",) + mark_folders()


def image_suffixes() -> tuple:
    """Extensions an image in this tree may carry, per attribution.json.

    The shipped prints are WebP and the masters are PNG, and three generators plus the tests
    all have to look for both. The list went into attribution.json for the same reason
    nonSlotFolders did: four copies of one fact is four chances to teach three of them.
    """
    try:
        got = json.loads(ATTRIB_FILE.read_text(encoding="utf-8")).get("imageSuffixes")
    except Exception:
        got = None
    return tuple(got) if got else (".png", ".webp")


def images_under(folder: pathlib.Path, deep: bool = True) -> list:
    """Every image under a folder, newest-last by name, whatever it is encoded as."""
    want = set(image_suffixes())
    found = folder.rglob("*") if deep else folder.glob("*")
    return sorted((f for f in found if f.suffix.lower() in want), key=lambda f: f.as_posix())

BUILD_VERSION = "0.1"

# A view, not the asset. Twice the card is 1180 x 590, which is retina on the board and about
# 58 KB a picture instead of 1.2 MB -- the whole page stays near a megabyte with all fourteen in
# it. The cutter, the manifest and the attribution record all still point at the full file.
ART_SCALE = 2
ART_JPEG_Q = 82

# =================================================================================================
# WHICH KEYS THE SAVE WRITES, AND INTO WHAT.
#
# Handed to the page as well as used here, because the button has two paths -- POST to this
# generator when it is serving, download when the page was opened as a file -- and they have to
# write the same keys into the same documents. The placement sheet learned this the hard way:
# its offline path once wrote the wire payload under the name of the placement file, a shape that
# file never has. tests/action_board/test_action_board.py pins the two against this list.
MANIFEST_KEYS = ("art", "seals", "tokens", "acolytes", "city", "selected")
# What one new picture carries when it is posted. The BYTES ARE THE ORIGINAL, never the
# downscaled copy the page is displaying -- see the note on imageFromFile in the template. A save
# that posted what it was showing would quietly replace 1120 x 560 masters with 590 x 295 JPEGs.
# WHAT THE PAGE MAY SEND, and separately what it must. `folder` is needed only for a slot that
# has never held a picture, and `brief` is what makes the record mean anything -- but a save
# without one should land and say so, not be refused.
IMAGE_KEYS = ("kind", "duty", "slot", "filename", "bytes", "folder", "brief")
IMAGE_REQUIRED = ("kind", "duty", "slot", "filename", "bytes")
SAVE_KEYS = {"manifest": list(MANIFEST_KEYS), "image": list(IMAGE_KEYS),
             "manifestFile": str(MANIFEST.relative_to(ROOT)) if ROOT in MANIFEST.parents
                             else "ui/board_v2/metadata/action_board.json"}

WHEEL_PALETTE = {
    "#efe3c8": "#3a3d45",   # face   -> the board's segment slate
    "#e8dcc0": "#23262b",   # centre -> its darker hub
    "#17130d": "#2b2e34",   # ground -> its base ellipse, hidden by default
}


def recolour(text: str, palette: dict | None = None) -> str:
    """Swap the drawing's parchment for the board's slate, and refuse to do it quietly.

    EVERY ENTRY MUST MATCH SOMETHING. A palette that silently stopped applying would leave a
    cream wheel on a black field with no error anywhere, which is the failure this exists to
    prevent -- so the substitutions are counted.
    """
    palette = WHEEL_PALETTE if palette is None else palette
    for old, new in palette.items():
        text, n = re.compile(re.escape(old), re.IGNORECASE).subn(new, text)
        if not n:
            raise SystemExit("the wheel asset has no %s in it, so this palette no longer "
                             "describes the drawing it is colouring" % old)
    return text


def wheel_svg() -> str:
    """The asset, stripped of its XML declaration and recoloured, ready to inline.

    The declaration has to go: left in the middle of a page it is not an error, it is a
    processing instruction the browser ignores, and the wheel would still draw -- so nothing
    would ever tell you it was there.
    """
    if not G.WHEEL_ASSET.is_file():
        raise SystemExit("the wheel drawing is not at %s, and this page is a board without it"
                         % G.WHEEL_ASSET)
    raw = G.WHEEL_ASSET.read_text(encoding="utf-8")
    return recolour(re.sub(r"^\s*<\?xml[^>]*\?>\s*", "", raw).strip())


def duty_text() -> dict:
    """What each action is called and what it does. One file owns this; nothing here restates it."""
    if not TEXT_FILE.is_file():
        raise SystemExit("duty_text.json is not at %s -- the board has nothing to print" % TEXT_FILE)
    d = json.loads(TEXT_FILE.read_text(encoding="utf-8"))["duties"]
    missing = [s for s, _n, _deg in G.DUTIES if s not in d]
    if missing:
        raise SystemExit("duty_text.json has no wording for %s" % ", ".join(missing))
    return d


def slot_of(rel: str, entry: dict) -> str | None:
    """Which slot a recorded file belongs in: left, right, master, or nothing.

    The same three routes the layout lab uses, in the same order -- an explicit `slot`, then
    `_left`/`_right` in the filename as crop_duty_master.py writes them, then the word LEFT or
    RIGHT in the record's prose, which is where the older entries say it. The folder cannot
    decide it: `gain_piety` is Clerical's actionA and `gain_coins` its actionB, which
    alphabetically is backwards.
    """
    slot = entry.get("slot")
    if slot in ("left", "right", "master"):
        return slot
    name = rel.rsplit("/", 1)[-1].lower()
    if "_left" in name:
        return "left"
    if "_right" in name:
        return "right"
    role = (entry.get("role", "") or "") + " " + (entry.get("notes", "") or "")
    if re.search(r"\bLEFT\b|left action", role):
        return "left"
    if re.search(r"\bRIGHT\b|right action", role):
        return "right"
    if "master" in role.lower():
        return "master"
    return None


def _inline(path: pathlib.Path, size: tuple | None, fmt: str = "JPEG") -> str:
    from PIL import Image
    im = Image.open(path)
    im = im.convert("RGB") if fmt == "JPEG" else im.convert("RGBA")
    if size:
        im = im.resize(size, Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, fmt, **({"quality": ART_JPEG_Q, "optimize": True} if fmt == "JPEG"
                         else {"optimize": True}))
    return "data:image/%s;base64,%s" % (fmt.lower() if fmt != "JPEG" else "jpeg",
                                        base64.b64encode(buf.getvalue()).decode("ascii"))


def bundled_art() -> tuple[dict, dict, list]:
    """The newest recorded picture for each duty and slot, inlined at twice the card.

    Missing Pillow or a missing tree is reported rather than fatal: this is still a board
    without pictures, and a page that quietly opened empty is the thing the notes exist to stop.
    """
    notes: list = []
    try:
        import PIL  # noqa: F401
    except ImportError:
        return {}, {}, ["Pillow is not installed, so no artwork is built in. "
                        "pip install pillow, then re-run."]
    if not ART_DIR.is_dir():
        return {}, {}, ["no duty_actions/ folder at %s, so no artwork is built in" % ART_DIR]

    placed: dict = {}
    if ATTRIB_FILE.is_file():
        rec = json.loads(ATTRIB_FILE.read_text(encoding="utf-8")).get("files", {})
        for path, e in rec.items():
            if path.startswith("duty_actions/"):
                placed[path[len("duty_actions/"):]] = slot_of(path[len("duty_actions/"):], e)

    side_to_slot = {"left": "actionA", "right": "actionB"}
    skip = non_slot_folders()
    images: dict = {}
    by_duty: dict = {}
    for slug, _name, _deg in G.DUTIES:
        folder = ART_DIR / slug
        if not folder.is_dir():
            continue
        newest: dict = {}
        for f in images_under(folder):
            # The seals live under the same duty folder and are a different kind of picture, so
            # they are walked by bundled_seals and skipped here. Without this they would arrive
            # recorded as left and right and be inlined as card art -- a 78px wax seal stretched
            # across 590 x 295, which is a thing a test should not have to catch.
            if set(f.relative_to(folder).parts) & set(skip):
                continue
            rel = f.relative_to(ART_DIR).as_posix()
            side = placed.get(rel)
            if side is None and f.parent.name == "masters":
                side = "master"
            if side not in ("left", "right"):
                if side is None:
                    notes.append("%s: no slot recorded, left out" % rel)
                continue
            newest[side] = f                      # sorted ascending, so _v03 beats _v02
        for side, f in newest.items():
            key = "art:%s:%s" % (slug, side_to_slot[side])
            images[key] = _inline(f, (G.ART_W * ART_SCALE, G.ART_H * ART_SCALE))
            by_duty.setdefault(slug, {})[side_to_slot[side]] = [key, f.name]
    return images, by_duty, notes


def bundled_seals() -> tuple[dict, dict, list]:
    """The newest recorded wax seal for each duty and slot, inlined at twice its drawn size.

    THE RECORD GATES THE SEAL, exactly as it gates the card art: a PNG that nobody wrote down is
    a PNG nobody can say where it came from, and the board would rather draw its dashed
    placeholder than show one. `masters/` holds the untouched originals and is recorded as such,
    so the same test keeps them off the board.

    SAME VOCABULARY AS THE ART -- left and right, not actionA and actionB. One slot has one name
    in the records whichever kind of picture is being talked about, and `record()` already maps
    the page's actionA onto it.
    """
    notes: list = []
    try:
        import PIL  # noqa: F401
    except ImportError:
        return {}, {}, []                       # bundled_art has already said why
    if not ART_DIR.is_dir():
        return {}, {}, []

    placed: dict = {}
    grounds: dict = {}
    if ATTRIB_FILE.is_file():
        rec = json.loads(ATTRIB_FILE.read_text(encoding="utf-8")).get("files", {})
        for path, e in rec.items():
            if path.startswith("duty_actions/"):
                rel = path[len("duty_actions/"):]
                placed[rel] = slot_of(rel, e)
                grounds[rel] = ground_of(path, e)

    side_to_slot = {"left": "actionA", "right": "actionB"}
    images: dict = {}
    by_duty: dict = {}
    for slug, _name, _deg in G.DUTIES:
        # THE LATER KIND WINS, AND THE HIGHER NUMBER WINS WITHIN A KIND. Two rules, because a
        # version counts up inside one lineage and nothing else.
        #
        # This was one rule and it was wrong twice. First it sorted filenames, which put
        # `..._icon_v04` before `..._seal_v03` on the letter i. Then it took the highest version
        # across every folder -- which is right inside `seals`, and nonsense between `seals` and
        # `icons`: a brand new icon arrives at v01 and loses to a wax disc on its second
        # generation, so eleven slots silently went on drawing seals with their icons sitting
        # right there. A seal's v02 and an icon's v01 are two unrelated counters.
        #
        # WHICH KIND WINS IS A CHOICE, not something the files can answer, so attribution.json's
        # `markFolders` is read in order and the last one that has a mark for a slot takes it.
        newest: dict = {}
        for sub_dir in mark_folders():
            here: dict = {}
            folder = ART_DIR / slug / sub_dir
            if not folder.is_dir():
                continue
            for f in images_under(folder):
                rel = f.relative_to(ART_DIR).as_posix()
                side = placed.get(rel)
                if side not in ("left", "right"):
                    if side is None:
                        notes.append("%s: no slot recorded, left out" % rel)
                    continue
                if side not in here or version_of(f) > version_of(here[side]):
                    here[side] = f
            newest.update(here)
        for side, f in newest.items():
            key = "seal:%s:%s" % (slug, side_to_slot[side])
            images[key] = _inline(f, (G.SEAL * 2, G.SEAL * 2), "PNG")
            rel = f.relative_to(ART_DIR).as_posix()
            by_duty.setdefault(slug, {})[side_to_slot[side]] = [
                key, f.name, grounds.get(rel, "own")]
    return images, by_duty, notes


GROUNDS = ("own", "board")


def ground_of(where: str, entry: dict) -> str:
    """Whose ground this mark is drawn on: its own, or the board's.

    A wax disc is a thing you could pick up. It carries its ground with it, and dropped on the
    tile it sits on the black like an object. An emblem cut out on transparency carries none, and
    the board has to put something behind it or it floats on nothing.

    WHICH IT IS CANNOT BE MEASURED OFF THE FILE, and the first version of this tried. It looked
    for a real alpha channel and called all forty-three marks cut-outs, because a round disc in a
    square file is a fifth clear at the corners. Asking harder does not help: of the two cut-outs
    the board now draws, one is opaque across 95% of its inner circle and the other across 56%,
    with every wax disc in the tree sitting between those two numbers. The silhouette does not
    know what the picture means.

    SO THE RECORD SAYS IT, in the same breath as it says which slot the seal is for, and `own` is
    the default because that is what every seal in the tree was until these two. An unknown value
    stops the build rather than defaulting: `Board` for `board` would mean a mark drawn on
    nothing, silently, and the only symptom would be a seal that looked wrong on the tile.
    """
    g = entry.get("ground", "own")
    if g not in GROUNDS:
        raise SystemExit("attribution.json gives %s a ground of %r, and a ground is %s"
                         % (where, g, " or ".join(GROUNDS)))
    return g


def bundled_tokens() -> tuple[dict, list]:
    """The three Tithe resources, in both treatments, at twice their drawn size.

    TWO SETS OF ART FOR THE SAME THREE THINGS, and that is deliberate. `seal_*` is a grey wax
    seal and `token_*` is a coin. The board's rule is that a SEAL is something you can take and
    its colour says which kind -- red for a duty action, grey for a resource -- so the Tithe
    column, which is the third choice beside the two actions, draws seals. The coins stay here
    because they are what a resource looks like once it is yours rather than on offer, which is
    a different job on a different surface.

    Both are loaded and the page prefers the seal, so swapping back is a one-line change in the
    template rather than a rebuild of the assets.
    """
    notes: list = []
    out: dict = {}
    if not TOKEN_DIR.is_dir():
        return out, ["no tokens/resources/ at %s, so the Tithe column draws letters" % TOKEN_DIR]
    for kind in ("seal", "token"):
        for name in G.TOKEN_ORDER:
            # THE EXTENSION IS NOT PART OF THE NAME. These were "%s_%s.png" and the day the
            # prints became WebP the Tithe column fell back to drawing letters, with a note
            # saying the files were missing while they sat right there.
            found = [f for f in (TOKEN_DIR / ("%s_%s%s" % (kind, name, sfx))
                                 for sfx in image_suffixes()) if f.is_file()]
            if not found:
                notes.append("%s_%s is missing in every format this tree reads"
                             % (kind, name))
                continue
            f = found[0]
            out["%s:%s" % (kind, name)] = _inline(f, (G.TOKEN * 2, G.TOKEN * 2), "PNG")
    if not any(k.startswith("seal:") for k in out):
        notes.append("no resource seals found, so the Tithe column falls back to the coins")
    return out, notes


def build() -> tuple[str, list]:
    if not TMPL.is_file():
        raise SystemExit("the template is not at %s" % TMPL)
    art, by_duty, notes = bundled_art()
    seals, seal_by_duty, snotes = bundled_seals()
    tokens, tnotes = bundled_tokens()
    notes += snotes + tnotes

    text = duty_text()
    duties = {}
    for slug, name, deg in G.DUTIES:
        said = text[slug]
        entry = {"name": name, "clock": deg,
                 "actions": 1 if said.get("actionB") is None else 2}
        for slot in G.ACTIONS:
            s = said.get(slot) or {"name": None, "shortLabel": ""}
            a = by_duty.get(slug, {}).get(slot)
            w = seal_by_duty.get(slug, {}).get(slot)
            entry[slot] = {"name": s["name"], "shortLabel": s["shortLabel"],
                           # byStrength is carried through untouched. The board prints the
                           # stored line; the numbers are the game's business, not this page's.
                           "byStrength": s.get("byStrength"),
                           "art": a[0] if a else None, "artFile": a[1] if a else None,
                           # ONE WORD, CARRIED WHOLE from attribution.json through to the
                           # page: `own` or `board`. It was a boolean for an afternoon and the
                           # page read it off the wrong shape -- `info[slot][2]` on a dict that
                           # has names, not positions -- so the ground was never drawn and
                           # nothing said so. A named field cannot be read off by accident.
                           "seal": w[0] if w else None, "sealFile": w[1] if w else None,
                           "sealGround": w[2] if w else None}
        duties[slug] = entry

    page = TMPL.read_text(encoding="utf-8")
    fill = {
        "__GEOMETRY__": json.dumps(G.as_dict()),
        "__DUTIES__": json.dumps(duties),
        "__IMAGES__": json.dumps({**art, **seals, **tokens}),
        "__WHEEL_SVG__": json.dumps(wheel_svg()),
        "__SAVEKEYS__": json.dumps(SAVE_KEYS),
        "__BUILD__": json.dumps({"version": BUILD_VERSION, "notes": notes}),
    }
    for token, value in fill.items():
        page = page.replace(token, value)

    # A TOKEN LEFT IN THE PAGE IS A HOLE NOBODY WOULD SEE. The browser would render
    # `__IMAGES__` as text in a script and the page would simply not work, with no error
    # anywhere pointing at the build. So the build is what fails.
    left = sorted(set(re.findall(r"__[A-Z_]+__", page)))
    if left:
        raise SystemExit("the template still has %s in it, so the build is incomplete"
                         % ", ".join(left))
    return page, notes


def serve(page_path: pathlib.Path, port: int, open_it: bool) -> None:
    """Serve the page on localhost and accept its saves.

    Bound to 127.0.0.1 and nothing else. This writes files into the repository when asked, which
    is fine for a tool you started yourself on your own machine and would not be fine on any
    interface a neighbour can reach.
    """
    import http.server

    class Handler(http.server.BaseHTTPRequestHandler):
        def _send(self, code, body, kind="application/json"):
            raw = body if isinstance(body, bytes) else body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):                                            # noqa: N802
            if self.path in ("/", "/index.html"):
                return self._send(200, page_path.read_bytes(), "text/html; charset=utf-8")
            return self._send(404, json.dumps({"error": "not found"}))

        def do_POST(self):                                           # noqa: N802
            if self.path != "/save":
                return self._send(404, json.dumps({"error": "not found"}))
            try:
                n = int(self.headers.get("Content-Length") or 0)
                sent = json.loads(self.rfile.read(n).decode("utf-8"))
                written = save(sent)
            except Exception as exc:                                 # noqa: BLE001
                print("  refused a save: %s" % exc)
                return self._send(400, json.dumps({"error": str(exc)}))
            for w in written:
                print("  wrote %s" % w)
            return self._send(200, json.dumps({"ok": True, "files": written}))

        def log_message(self, *a):                                   # quiet; we print what matters
            return

    srv = http.server.HTTPServer(("127.0.0.1", port), Handler)
    url = "http://127.0.0.1:%d/" % srv.server_address[1]
    print("  serving %s -- the save button writes into the repository" % url)
    print("  ctrl-c to stop")
    if open_it:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  stopped")


def next_version(folder: pathlib.Path, stem: str) -> pathlib.Path:
    """The next _vNN beside what is already there.

    NOTHING IS EVER OVERWRITTEN. A picture that was replaced stays on disk, superseded, the way
    the briefs in duty_art_lab/prompts are kept -- and since this tool has no undo, not
    overwriting IS the undo.
    """
    n = 0
    for f in images_under(folder, deep=False):
        m = re.match(re.escape(stem) + r"_v(\d+)$", f.stem)
        if m:
            n = max(n, int(m.group(1)))
    return folder / ("%s_v%02d.png" % (stem, n + 1))


def version_of(path: pathlib.Path) -> int:
    """The _vNN on the end of a name, or -1 for a file that carries none.

    Used to pick the newest of a slot's marks when they are spread over more than one folder. A
    file with no version loses to every file that has one, which is right: the versioned names
    are the ones this tree manages.
    """
    m = re.search(r"_v(\d+)$", path.stem)
    return int(m.group(1)) if m else -1


def mark_subdir(duty: str, slot: str) -> str:
    """Which of the mark folders this duty's slot already keeps its mark in.

    A MARK ALREADY FILED IS THE ANSWER -- the same evidence slot_folder() prefers for the action
    pictures, and the same reason: the tree knows, and asking it is what keeps a saved picture
    beside its predecessor instead of opening a second home for one slot. A slot with no mark yet
    falls back to `seals`.

    THE SAME PRECEDENCE THE BOARD DRAWS BY, so a save lands beside the mark actually in play
    rather than beside the one with the biggest number on it. Comparing versions across folders
    was how this went wrong the first time.
    """
    if not ATTRIB_FILE.is_file():
        return MARK_SUBDIR
    rec = json.loads(ATTRIB_FILE.read_text(encoding="utf-8")).get("files", {})
    want = {"actionA": "left", "actionB": "right"}.get(slot, slot)
    folders = mark_folders()
    best: dict = {}
    for path, e in rec.items():
        if not path.startswith("duty_actions/%s/" % duty):
            continue
        rel = path[len("duty_actions/"):]
        parts = rel.split("/")
        if len(parts) < 3 or parts[1] not in folders or "masters" in parts:
            continue
        if slot_of(rel, e) != want:
            continue
        v = version_of(pathlib.Path(parts[-1]))
        if parts[1] not in best or v > best[parts[1]]:
            best[parts[1]] = v
    for sub_dir in folders:                    # in order, so the last one that has a mark wins
        if sub_dir in best:
            chosen = sub_dir
    return chosen if best else MARK_SUBDIR


def slot_folder(duty: str, slot: str) -> str | None:
    """Which folder this duty's slot keeps its pictures in.

    A PICTURE ALREADY PLACED IS THE STRONGER EVIDENCE of where its siblings go, so the per-file
    records are read first and attribution.json's `slotFolders` answers the slots that have none
    -- which was twelve of the fourteen. (This docstring used to claim the opposite order to the
    code underneath it. The code was right and the prose had drifted.)

    A SEAL IS NOT AN ACTION PICTURE, and it is recorded in the same vocabulary -- left and right
    -- under the same duty. So the scan steps over the non-slot folders, or the first seal filed
    for a duty with no artwork yet becomes that slot's answer: Give Alms' right action reported
    its folder as "seals", which is where the save would then have written a 590 x 295 card.
    """
    if not ATTRIB_FILE.is_file():
        return None
    doc = json.loads(ATTRIB_FILE.read_text(encoding="utf-8"))
    want = {"actionA": "left", "actionB": "right"}.get(slot, slot)
    skip = set(non_slot_folders())
    for path, e in doc.get("files", {}).items():
        if not path.startswith("duty_actions/%s/" % duty):
            continue
        rel = path[len("duty_actions/"):]
        if set(rel.split("/")) & skip:
            continue
        if slot_of(rel, e) == want:
            return rel.split("/")[1]
    return (doc.get("slotFolders", {}).get(duty) or {}).get(slot)


def empty_folders(duty: str) -> list:
    """The folders this duty already has that hold no picture yet."""
    d = ART_DIR / duty
    if not d.is_dir():
        return []
    return sorted(f.name for f in d.iterdir()
                  if f.is_dir() and f.name != "masters" and not images_under(f))


def _short(p: pathlib.Path) -> str:
    """A path to print back. Relative to the tree when it is in it, whole when it is not --
    a save under test writes to a temporary directory, and relative_to() raises on those."""
    try:
        return str(p.relative_to(BOARD.parent))
    except ValueError:
        return str(p)


def save(sent: dict) -> list:
    """Write the manifest, and any posted picture, into the repository.

    THE NAMING AND THE RECORD ARE DECIDED HERE, not in the page. The page cannot see the folder,
    so it cannot know whether _v03 already exists; it posts what it has and this decides where it
    lands and what attribution.json is told.
    """
    written: list = []
    unknown = [k for k in sent if k not in ("manifest", "images")]
    if unknown:
        raise ValueError("a save may carry `manifest` and `images`, not %s" % ", ".join(unknown))

    for img in sent.get("images") or []:
        missing = [k for k in IMAGE_REQUIRED if k not in img]
        if missing:
            raise ValueError("a posted picture is missing %s" % ", ".join(missing))
        raw = base64.b64decode(img["bytes"].split(",", 1)[-1])
        if img["kind"] == "art":
            # BESIDE ITS PREDECESSOR, under the folder that slot already uses. The existing
            # names are historical and not derivable -- `gain_piety` is Clerical's actionA and
            # `send_on_mission` is Ordination's actionB -- so the folder is looked up from the
            # record rather than invented, and a slot that has never had a picture falls back to
            # the action's own name from duty_text.json.
            # WHICH FOLDER A SLOT USES CANNOT BE DERIVED, and inventing one would quietly put a
            # second folder beside the empty one this tree already made for it. The names are
            # historical and not even consistently ordered -- Clerical's actionA is `gain_piety`
            # and its actionB `gain_coins`, while Produce's actionA is `gain_wheat` and its
            # actionB `gain_stone` -- so for a slot with no recorded file the save has to be
            # told, and is refused until it is.
            folder_name = img.get("folder") or slot_folder(img["duty"], img["slot"])
            if not folder_name:
                raise ValueError(
                    "nothing says which folder %s %s uses. Add it to attribution.json's "
                    "`slotFolders`, or post `folder` with one of: %s"
                    % (img["duty"], img["slot"], ", ".join(empty_folders(img["duty"])) or "none"))
            if "/" in folder_name or folder_name.startswith("."):
                raise ValueError("%r is not a folder name" % folder_name)
            folder = ART_DIR / img["duty"] / folder_name
            side = {"actionA": "left", "actionB": "right"}.get(img["slot"], img["slot"])
            stem = "%s_%s_%s" % (img["duty"], folder_name, side)
        elif img["kind"] == "seal":
            # BESIDE THE MARK THAT IS ALREADY THERE, which is the same rule the action pictures
            # follow and for the same reason: a slot whose mark is an icon would otherwise have a
            # seal saved into `seals/` on top of it, and the tree would be back to calling a
            # cut-out a seal. The word in the filename comes off the folder for the same reason --
            # two places saying what kind of thing this is, is one place too many.
            sub_dir = mark_subdir(img["duty"], img["slot"])
            folder = ART_DIR / img["duty"] / sub_dir
            stem = "%s_%s_%s" % (img["duty"], img["slot"], re.sub(r"s$", "", sub_dir))
        elif img["kind"] == "token":
            folder = TOKEN_DIR
            stem = "token_%s" % img["slot"]
        else:
            raise ValueError("a picture of kind %r has nowhere to go" % img["kind"])
        folder.mkdir(parents=True, exist_ok=True)
        dest = next_version(folder, stem)
        dest.write_bytes(raw)
        written.append(_short(dest))
        record(dest, img)

    man = sent.get("manifest")
    if man is not None:
        bad = [k for k in man if k not in MANIFEST_KEYS]
        if bad:
            raise ValueError("the manifest may carry %s, not %s"
                             % (", ".join(MANIFEST_KEYS), ", ".join(bad)))
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(json.dumps({
            "note": "What the action board shows: which recorded file fills each slot, and where "
                    "the acolytes stand. PATHS, NOT BYTES -- the pictures live in duty_actions/ "
                    "and tokens/, and a manifest carrying them would be megabytes nobody can "
                    "read a diff of. Written by ui/board_v2/action_board, read by whatever "
                    "draws the real board.",
            "version": BUILD_VERSION,
            **{k: man[k] for k in MANIFEST_KEYS if k in man},
        }, indent=2) + "\n", encoding="utf-8")
        written.append(_short(MANIFEST))
    return written


def record(dest: pathlib.Path, img: dict) -> None:
    """Add the picture to attribution.json.

    GENERATED BY CHATGPT UNLESS THE SAVE SAYS OTHERWISE, which is the standing fact about this
    tree's art. `reproducibleBy` names the BRIEF rather than the tool: "ChatGPT" alone is
    reproducible by nobody, and the brief plus its version is the only answer that still means
    something in three months.
    """
    if not ATTRIB_FILE.is_file():
        return
    doc = json.loads(ATTRIB_FILE.read_text(encoding="utf-8"))
    rel = dest.relative_to(BOARD).as_posix()
    files = doc.setdefault("files", {})
    files[rel] = {
        "generator": img.get("generator") or "ChatGPT",
        "slot": {"actionA": "left", "actionB": "right"}.get(img.get("slot"), img.get("slot")),
        "role": img.get("role") or "placed by the action board from %s" % img.get("filename"),
        "reproducibleBy": img.get("brief") or "unrecorded -- name the brief that produced it",
        "addedBy": "ui/board_v2/action_board %s" % BUILD_VERSION,
    }
    ATTRIB_FILE.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--open", action="store_true", help="open the page when it is built")
    ap.add_argument("--serve", nargs="?", type=int, const=8777, default=None, metavar="PORT",
                    help="serve the page on localhost so its save button can write into the "
                         "repository (default port %(const)s); without this the button can only "
                         "download")
    a = ap.parse_args()

    page, notes = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding="utf-8")
    print("  wrote %s  (%d KB)" % (OUT, len(page.encode("utf-8")) // 1024))
    for n in notes:
        print("  note: %s" % n)
    if a.serve is not None:
        serve(OUT, a.serve, a.open)
    else:
        print("  NOT SERVED -- the save button can only download. Add --serve to write "
              "into the repository.")
        if a.open:
            webbrowser.open(OUT.as_uri())


if __name__ == "__main__":
    main()
