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
    images: dict = {}
    by_duty: dict = {}
    for slug, _name, _deg in G.DUTIES:
        folder = ART_DIR / slug
        if not folder.is_dir():
            continue
        newest: dict = {}
        for f in sorted(folder.rglob("*.png")):
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


def bundled_tokens() -> tuple[dict, list]:
    """The three Tithe resources, at twice their drawn size, with their alpha kept."""
    notes: list = []
    out: dict = {}
    if not TOKEN_DIR.is_dir():
        return out, ["no tokens/resources/ at %s, so the Tithe column draws discs" % TOKEN_DIR]
    for name in G.TOKEN_ORDER:
        f = TOKEN_DIR / ("token_%s.png" % name)
        if not f.is_file():
            notes.append("token_%s.png is missing, so that resource draws as a disc" % name)
            continue
        out["token:%s" % name] = _inline(f, (G.TOKEN * 2, G.TOKEN * 2), "PNG")
    return out, notes


def build() -> tuple[str, list]:
    if not TMPL.is_file():
        raise SystemExit("the template is not at %s" % TMPL)
    art, by_duty, notes = bundled_art()
    tokens, tnotes = bundled_tokens()
    notes += tnotes

    text = duty_text()
    duties = {}
    for slug, name, deg in G.DUTIES:
        said = text[slug]
        entry = {"name": name, "clock": deg,
                 "actions": 1 if said.get("actionB") is None else 2}
        for slot in G.ACTIONS:
            s = said.get(slot) or {"name": None, "shortLabel": ""}
            a = by_duty.get(slug, {}).get(slot)
            entry[slot] = {"name": s["name"], "shortLabel": s["shortLabel"],
                           # byStrength is carried through untouched. The board prints the
                           # stored line; the numbers are the game's business, not this page's.
                           "byStrength": s.get("byStrength"),
                           "art": a[0] if a else None, "artFile": a[1] if a else None,
                           "seal": None, "sealFile": None}
        duties[slug] = entry

    page = TMPL.read_text(encoding="utf-8")
    fill = {
        "__GEOMETRY__": json.dumps(G.as_dict()),
        "__DUTIES__": json.dumps(duties),
        "__IMAGES__": json.dumps({**art, **tokens}),
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
    for f in folder.glob("%s_v*.png" % stem):
        m = re.search(r"_v(\d+)\.png$", f.name)
        if m:
            n = max(n, int(m.group(1)))
    return folder / ("%s_v%02d.png" % (stem, n + 1))


def slot_folder(duty: str, slot: str) -> str | None:
    """Which folder this duty's slot keeps its pictures in.

    attribution.json's `slotFolders` is the answer and is checked first, because it covers the
    slots that have no picture yet -- which is twelve of the fourteen. The per-file records are
    the fallback, and they agree with it for the two that do; a file already placed is the
    stronger evidence of where its siblings go, so a disagreement is worth knowing about and
    the map wins only where nothing has landed.
    """
    if not ATTRIB_FILE.is_file():
        return None
    doc = json.loads(ATTRIB_FILE.read_text(encoding="utf-8"))
    want = {"actionA": "left", "actionB": "right"}.get(slot, slot)
    for path, e in doc.get("files", {}).items():
        if not path.startswith("duty_actions/%s/" % duty):
            continue
        rel = path[len("duty_actions/"):]
        if slot_of(rel, e) == want:
            return rel.split("/")[1]
    return (doc.get("slotFolders", {}).get(duty) or {}).get(slot)


def empty_folders(duty: str) -> list:
    """The folders this duty already has that hold no picture yet."""
    d = ART_DIR / duty
    if not d.is_dir():
        return []
    return sorted(f.name for f in d.iterdir()
                  if f.is_dir() and f.name != "masters" and not any(f.glob("*.png")))


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
            folder = ART_DIR / img["duty"] / "seals"
            stem = "%s_%s_seal" % (img["duty"], img["slot"])
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
