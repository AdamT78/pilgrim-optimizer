#!/usr/bin/env python3
"""Every duty's action art on one page, with the blanks showing.

    python3 ui/board_v2/duty_art_lab/generate_duty_art_board.py --open

Sixteen action images and eight masters, at the size the board draws them, in the wheel's own
order. WHAT IS NOT THERE IS THE POINT: an empty slot is a dashed frame carrying the action's
name, so the page reads as a list of what still has to be drawn rather than as a gallery of what
has been.

WHERE EACH THING COMES FROM, and none of it from here:

  the eight duties and their order   action_board/geometry.py's DUTIES
  the card's size and the gap        the same file's ART_W, ART_H and ART_GAP
  which slot a recorded file is in   generate_action_board.py's slot_of()
  which file each slot is drawn with its bundled_art(), so this page reports what SHIPS
  what each action is called         ui/board_v2/duty_text.json
  how many actions a duty offers     the same file -- a null actionB means one
  the art itself                     ui/board_v2/duty_actions/<duty>/<folder>/

WHICH SLOT A FILE BELONGS IN is the one thing that cannot be derived, and the page says so where
it has had to guess. The folders are named after what the action does -- `gain_piety`,
`gain_coins` -- and those names came from wording that has since changed, so they neither match
duty_text.json nor sort into slot order: Clerical's LEFT is `gain_piety` and its RIGHT is
`gain_coins`, which alphabetically is backwards. Three things are tried, in order:

  1. an explicit `slot` on the file's attribution.json entry: "left", "right" or "master"
  2. `_left` or `_right` in the filename, the naming crop_duty_master.py established before it
     was retired; the convention outlived the script and every card still follows it
  3. the word LEFT or RIGHT in the entry's `role` prose, which is where the existing six say it

Anything still unplaced is shown under the duty, marked, rather than dropped or guessed at.
"""
from __future__ import annotations

import argparse
import base64
import importlib.util
import io
import json
import pathlib
import re
import sys
import webbrowser

from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BOARD = HERE.parent
ART = BOARD / "duty_actions"
ATTRIB = BOARD / "attribution.json"
PROMPTS = HERE / "prompts"
SUBJECTS = HERE / "subjects.json"


# ======================================================================================
# THE BRIEFS, THE SUBJECTS AND THE SHAPE PARAGRAPH
#
# These four functions lived in generate_duty_art_lab.py and were imported from here. That was
# right while two pages wanted them; the viewfinder has been retired and this is the only caller
# left, so they live where they are used rather than in a module kept alive to lend them out.
#
# The DATA has not moved: prompts/ and subjects.json are where they always were, beside this file.
# ======================================================================================


def prompts(folder: pathlib.Path | None = None) -> list[dict]:
    """Every brief in prompts/, in filename order.

    MORE THAN ONE, AND KEPT RATHER THAN EDITED. A brief that produced a picture somebody liked
    is evidence, and evidence gets superseded rather than overwritten: the next idea goes in a
    new file beside this one so the two can be run against each other. The numeric prefix is
    ordering and is stripped from the title.

    The geometry paragraph is deliberately NOT in any of them -- it is computed in the page from
    the same band the cut uses, so a brief and the cut can never describe different pictures.
    """
    folder = PROMPTS if folder is None else folder
    if not folder.is_dir():
        raise SystemExit("there are no briefs at %s" % folder)
    out = []
    for f in sorted(folder.glob("*.md")):
        if f.name.lower() == "readme.md":
            continue                       # a note to whoever edits the folder, not a brief
        text = f.read_text(encoding="utf-8")
        # AN ARCHIVAL BRIEF IS EXEMPT, and has to be. It is somebody's text as they wrote it,
        # kept because it produced a particular picture, so the fields the page would otherwise
        # fill in are already spelled out in it and must stay that way. It gets a button and no
        # substitution; the page says what it is. Everything else must carry the full set, or
        # the page would hand out a brief with a hole in it.
        archival = re.search(r"<!--\s*archival:\s*(.+?)\s*-->", text, re.S)
        if not archival:
            for token in ("{{GEOMETRY}}", "{{LEFT_ACTION}}", "{{RIGHT_ACTION}}",
                          "{{LEFT_SUBJECT}}", "{{RIGHT_SUBJECT}}"):
                if token not in text:
                    raise SystemExit("%s has no %s in it, so the page cannot fill it in. If it "
                                     "is a record of a brief somebody ran, mark it with an "
                                     "<!-- archival: why --> comment and it is exempt."
                                     % (f.name, token))
        m = re.search(r"<!--\s*title:\s*(.+?)\s*-->", text)
        title = m.group(1) if m else re.sub(r"^\d+[-_]", "", f.stem).replace("-", " ")
        # The HTML comments are notes to whoever edits the file, not instructions to a model.
        body = re.sub(r"<!--.*?-->\s*", "", text, flags=re.S).lstrip()
        out.append({"title": title, "file": f.name, "text": body,
                    "archival": re.sub(r"\s+", " ", archival.group(1)) if archival else None})
    if not out:
        raise SystemExit("%s has no .md files in it" % folder)
    return out


def seal_prompts() -> list[dict]:
    """The briefs that produced the wax seals, each one verbatim.

    A SEPARATE FOLDER BECAUSE THEY ARE A DIFFERENT KIND OF DOCUMENT. The briefs in prompts/ are
    ONE text run against eight duties, with the duty's own names substituted in. The seal briefs
    are not: measured section by section they share between 13% and 67% of their words, so there
    is no template to pull out of them -- they are separate prompts that borrow a vocabulary. Each
    is kept as sent and marked archival, which is the exemption this module already has for
    exactly that. prompts/seals/README.md has the measurements and what they imply.

    They are also kept out of prompts/ so they are never offered as an action-card brief: the
    per-duty buttons substitute a duty's names in, and an archival text has nothing to
    substitute. The viewfinder enforced this by not looking in seals/; the filter in build()
    does it here.
    """
    folder = PROMPTS / "seals"
    if not folder.is_dir():
        return []
    got = prompts(folder)
    for b in got:
        for key in ("produces", "reference"):
            m = re.search(r"<!--\s*%s:\s*(.+?)\s*-->" % key,
                          (folder / b["file"]).read_text(encoding="utf-8"), re.S)
            b[key] = re.sub(r"\s+", " ", m.group(1)) if m else None
    return got


def geometry_text(band: dict, aspect: float) -> str:
    """The shape-and-zones paragraph, written from the band rather than typed.

    IN PYTHON, AND IN ONE PLACE. It was built in the page's JavaScript, which was fine while one
    page needed it and became a duplicated formula the moment the art board wanted the same
    paragraph. Two implementations of one piece of arithmetic is how a brief and a cut come to
    describe different pictures, which is the exact failure this paragraph exists to prevent.

    EXPRESSED IN PROPORTIONS, NOT PIXELS, and that is not a style choice: a 2544 x 848 was asked
    for and 2172 x 724 came back, because the generator honours the ASPECT and works to a fixed
    pixel budget. Pixel dimensions in a brief are noise.
    """
    band_aspect = band["span"] / band["card_h"]
    kept = aspect / band_aspect
    over = (1 - kept) / 2
    card_pct = 100 * band["card_w"] / band["span"]
    seam_pct = 100 * band["gap"] / band["span"]
    return (
        "======================================================================\n"
        "SHAPE AND ZONES - CRITICAL\n"
        "======================================================================\n"
        "\n"
        "Generate ONE wide landscape image at an aspect ratio of %.1f : 1.\n"
        "\n"
        "Fill the whole frame. Do not letterbox it, do not add borders, and do not\n"
        "leave empty margins at the sides.\n"
        "\n"
        "Do not worry about pixel dimensions. Only the RATIO matters.\n"
        "\n"
        "The image will be cut into TWO CARDS that sit side by side on the board with\n"
        "a narrow gap between them. Think of the width in three parts:\n"
        "\n"
        "  LEFT CARD      the leftmost  %.1f%% of the width\n"
        "  SEAM           the middle    %.1f%% of the width  (hidden by the gap)\n"
        "  RIGHT CARD     the rightmost %.1f%% of the width\n"
        "\n"
        "The seam is NARROW. It is a hairline, not a corridor. Do not leave a wide\n"
        "empty band down the middle of the picture: almost all of the middle is seen,\n"
        "and dead floor there is dead floor on the finished cards.\n"
        "\n"
        "VERTICAL SAFE BAND\n"
        "\n"
        "Only the middle %.0f%% of the height survives the crop. The top %.1f%% and the\n"
        "bottom %.1f%% are overscan and will be discarded.\n"
        "\n"
        "Keep every indispensable element - faces, hands, flames, tools, the focal\n"
        "detail of any statue or fixture - comfortably inside that central band.\n"
        "Architecture and floor may run to the top and bottom edges; narrative must\n"
        "not." % (aspect, card_pct, seam_pct, card_pct,
                  100 * kept, 100 * over, 100 * over))


def subjects() -> dict:
    """What each duty's two scenes show, from subjects.json.

    ONE OWNER. The Clerical pair was once hard-coded into a template as a worked example while
    this file needed the same words; a second copy is how two pages come to offer different
    briefs for the same duty. One page is left and the file still owns it.
    """
    if not SUBJECTS.is_file():
        raise SystemExit("the subject descriptions are not at %s" % SUBJECTS)
    return json.loads(SUBJECTS.read_text(encoding="utf-8")).get("duties", {})


def non_slot_folders(attrib_file) -> tuple:
    """Folder names under a duty that are NOT one of its actions.

    attribution.json owns this, because every tool that walks duty_actions/ has to agree about it
    and each one used to carry its own copy of the word "masters". When `seals` appeared, the
    action board was taught about it and this walk was not, and a 78px wax seal was drawn as a
    590 x 295 action card. The fallback is what the tree looked like before the key existed.
    """
    try:
        import json as _json
        got = _json.loads(attrib_file.read_text(encoding="utf-8")).get("nonSlotFolders")
    except Exception:
        got = None
    return tuple(got) if got else ("masters", "seals")


def mark_folders(attrib_file) -> tuple:
    """The folders a duty's tile mark may live in, per attribution.json.

    The same list the action board reads, from the same place, for the same reason that
    nonSlotFolders is not three copies of the word "masters". This lab shows every version of a
    duty's mark beside the board's choice, so a lab that knew about `seals` and not `icons` would
    show Build Roads as having no marks at all while the board drew two.
    """
    try:
        import json as _json
        got = _json.loads(attrib_file.read_text(encoding="utf-8")).get("markFolders")
    except Exception:
        got = None
    return tuple(got) if got else ("seals",)


def image_suffixes(attrib_file) -> tuple:
    """Extensions an image in this tree may carry, per attribution.json.

    The shipped prints are WebP and the masters are PNG. This walk looked for "*.png" and
    would simply have stopped finding the art, quietly, with nothing to say about it.
    """
    try:
        import json as _json
        got = _json.loads(attrib_file.read_text(encoding="utf-8")).get("imageSuffixes")
    except Exception:
        got = None
    return tuple(got) if got else (".png", ".webp")


def images_under(folder, attrib_file) -> list:
    """Every image under a folder, newest-last by name, whatever it is encoded as."""
    want = set(image_suffixes(attrib_file))
    return sorted((f for f in folder.rglob("*") if f.suffix.lower() in want),
                  key=lambda f: f.as_posix())


# WHAT THIS PAGE SKIPS IS NOT THE WHOLE NON-SLOT LIST. `nonSlotFolders` names the folders under a
# duty that are not one of its ACTIONS -- masters and seals -- and the board's own walk skips both.
# This page is the one that deliberately SHOWS the master: it has a bucket for it, the headline
# counts them, and applying the list wholesale blanked the top of every duty and took the page
# from 1984 KB to 557 with nothing to say about it. So what is skipped here is the non-slot
# folders this page has nowhere to put.
BUCKETED = ("masters",)
SKIP = tuple(n for n in non_slot_folders(ATTRIB) if n not in BUCKETED)
TEXT = BOARD / "duty_text.json"
TMPL = HERE / "duty_art_board.html.tmpl"
OUT = HERE / "generated" / "duty_art_board.html"

BUILD_VERSION = "0.1"
# Thumbnails are for judging composition at board size, so they are built at twice the card and
# no larger. Sixteen full-resolution crops inlined would be 20 MB of page to show 750px pictures.
THUMB_SCALE = 2
JPEG_Q = 82


def board():
    """The action board's generator, which is what this page is a list of.

    IT USED TO BE THE LAYOUT LAB, and the difference is not cosmetic. The lab was a composition you
    could drag about, so "what the lab will open with" was a statement about a saved state. The
    action board draws one board from geometry.py and only one, so this page now reports what
    SHIPS -- which is what somebody looking for missing art actually wants to know.

    Everything this page borrows comes from here: the duty order and names, the card shape, the
    slot rule, and which file each slot is currently drawn with.
    """
    p = HERE.parent / "action_board" / "generate_action_board.py"
    if not p.is_file():
        raise SystemExit("the action board generator is not at %s -- it owns the duty order, the "
                         "card size and the slot rule, and this page is a list of all three" % p)
    spec = importlib.util.spec_from_file_location("_board_gen", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_board_gen"] = mod
    spec.loader.exec_module(mod)
    return mod


def slots_from_attribution(m) -> dict:
    """Which slot each recorded file sits in -- ASKED OF THE BOARD, not worked out again here.

    This used to carry its own copy of the rule. The action board needs the same answer, to decide
    which artwork to build into the board, and two copies of one rule is how this page comes to
    show art the board does not draw. Its job is to report what the board will do, so it has to be
    asking the same question of the same function.
    """
    out = {}
    if not ATTRIB.is_file():
        return out
    files = json.loads(ATTRIB.read_text(encoding="utf-8")).get("files", {})
    for path, e in files.items():
        if not path.startswith("duty_actions/"):
            continue
        rel = path[len("duty_actions/"):]
        out[rel] = {"slot": m.slot_of(rel, e),
                    "declared": e.get("slot") in ("left", "right", "master")}
    return out


def thumb(path: pathlib.Path, w: int, h: int | None) -> str:
    im = Image.open(path).convert("RGB")
    im = im.resize((w, h), Image.LANCZOS) if h else \
        im.resize((w, max(1, round(w * im.height / im.width))), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=JPEG_Q, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def disc_thumb(path: pathlib.Path, size: int) -> str:
    """A seal, small, WITH ITS TRANSPARENCY. thumb() flattens to RGB and encodes JPEG,
    which is right for a rectangular card and wrong for a scalloped wax disc: it would put a
    hard box behind every seal on the page and the thing this band is for -- the shape of the
    rim -- is the first thing to go."""
    im = Image.open(path).convert("RGBA").resize((size, size), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=88, method=4)
    return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def seal_size() -> int:
    """The size the board actually draws a seal at, from the module that owns it.

    Imported by path, like the layout lab above, so this page shows the
    seals at the size they are judged at rather than at a number typed in here."""
    p = ART.parent / "action_board" / "geometry.py"
    if not p.is_file():
        return 78
    spec = importlib.util.spec_from_file_location("_board_geo", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_board_geo"] = mod
    spec.loader.exec_module(mod)
    return int(mod.SEAL)


def seal_briefs() -> dict:
    """Which brief produced which seal, keyed by the file it names.

    FROM THE BRIEF'S OWN `produces:` HEADER, not from a list kept beside it. A brief that names a
    file nobody has filed shows as a brief with nothing under it, which is the right way round:
    the text is the thing that was written first.
    """
    out = {}
    for b in seal_prompts():
        if b.get("produces"):
            out[b["produces"]] = {"file": b["file"], "title": b["title"], "text": b["text"],
                                  "reference": b.get("reference")}
    return out


def unfiled_briefs() -> list:
    """Briefs in the folder that have produced nothing yet.

    A brief with no `produces:` attaches to no seal, so without this it would sit in the tree
    showing nowhere -- which is how a revision written and then forgotten disappears. The page
    says it is there and waiting rather than leaving it to a directory listing.
    """
    return [{"file": b["file"], "title": b["title"], "text": b["text"]}
            for b in seal_prompts() if not b.get("produces")]


def version_of(path) -> int:
    """The _vNN on the end of a name, or -1 for a file that carries none."""
    import re as _re
    m = _re.search(r"_v(\d+)$", path.stem)
    return int(m.group(1)) if m else -1


def seals_for(duty: str, placed: dict, size: int, briefs: dict) -> dict:
    """Every version of this duty's seals, newest first, by the slot they are recorded in.

    NEWEST FIRST BECAUSE NEWEST IS WHAT DRAWS. The action board picks a duty's mark by the
    highest _vNN across every mark folder, so the first entry here IS the one on the board and the
    rest are what it superseded. The page says which, rather than leaving the reader to work out
    that a filename sorts.

    BY VERSION AND NOT BY NAME, which is a correction rather than a refinement. This used to walk
    one folder and reverse it, and a name sorts the same way a version does only while there is
    one folder: with `icons` beside `seals`, `..._icon_v04` sorts before `..._seal_v03`, and this
    page would have shown the superseded wax disc at the head of the row with the icon behind it,
    disagreeing with the board about which mark is in play."""
    out = {"left": [], "right": []}
    found = {"left": [], "right": []}
    order = {name: i for i, name in enumerate(mark_folders(ATTRIB))}
    for sub_dir in mark_folders(ATTRIB):
        folder = ART / duty / sub_dir
        if not folder.is_dir():
            continue
        for f in sorted(folder.glob("*")):
            if not f.is_file() or f.suffix.lower() not in set(image_suffixes(ATTRIB)):
                continue
            info = placed.get(f.relative_to(ART).as_posix())
            slot = info["slot"] if info else None
            if slot not in out:
                continue
            found[slot].append(f)
    # THE BOARD'S OWN ORDER: the later kind first, then the higher version inside it. Sorting by
    # version alone put a wax disc's v02 ahead of an icon's v01 and disagreed with the board about
    # which mark is in play -- the same mistake the board itself made for one build.
    for slot, files in found.items():
        for f in sorted(files, key=lambda p: (-order.get(p.parent.name, -1), -version_of(p), p.name)):
            info = placed.get(f.relative_to(ART).as_posix())
            out[slot].append({"file": f.name, "src": disc_thumb(f, size * 2),
                              "recorded": info is not None,
                              "brief": briefs.get(f.relative_to(ART.parent).as_posix())})
    return out


def tithe_seals(size: int, briefs: dict) -> list:
    """The three resource seals, which follow the OTHER convention and say so here.

    A duty seal carries its version in the print and the newest draws. A resource seal has a
    stable name -- generate_action_board looks it up as seal_wheat -- so the version lives on
    the master and replacing the print is the change. One band showing both would imply they
    work the same way, so this one names its master instead of its version."""
    tokens = ART.parent / "tokens"
    want = set(image_suffixes(ATTRIB))
    out = []
    for name in ("wheat", "stone", "silver"):
        shipped = [p for p in (tokens / "resources").glob("seal_%s.*" % name)
                   if p.suffix.lower() in want]
        masters = sorted(p.name for p in (tokens / "masters").glob("seal_%s_v*" % name))
        out.append({"name": name,
                    "file": shipped[0].name if shipped else None,
                    "src": disc_thumb(shipped[0], size * 2) if shipped else None,
                    "masters": masters,
                    "brief": briefs.get(shipped[0].relative_to(ART.parent).as_posix())
                    if shipped else None})
    return out


def collect(m) -> dict:
    G = m.G
    band = {"card_w": G.ART_W, "card_h": G.ART_H, "gap": G.ART_GAP}
    if not TEXT.is_file():
        raise SystemExit("duty_text.json is not at %s -- it owns what the actions are called"
                         % TEXT)
    TXT = json.loads(TEXT.read_text(encoding="utf-8"))["duties"]
    placed = slots_from_attribution(m)

    # WHAT THE BOARD WILL DRAW, from the board's own walk rather than inferred. If these two ever
    # disagree this page is the thing that is wrong, so it is better to ask than to reconstruct.
    _art, bundled, art_notes = m.bundled_art()

    seal_px = seal_size()
    briefs = seal_briefs()
    waiting = unfiled_briefs()
    duties = []
    # THE ORDER COMES OFF G.DUTIES, the same tuple the action board loops over, so this page reads
    # top to bottom as the ribbon reads left to right. A page listing duties in a different order
    # from the board would be a quiet lie about which slot is which.
    for slug, duty_name, _deg in G.DUTIES:
        t = TXT.get(slug, {})
        a, b = t.get("actionA") or {}, t.get("actionB")
        folder = ART / slug
        found = {"left": [], "right": [], "master": [], "unplaced": []}
        if folder.is_dir():
            for f in images_under(folder, ATTRIB):
                if set(f.relative_to(folder).parts) & set(SKIP):
                    continue          # a seal is not this duty's card art
                rel = f.relative_to(ART).as_posix()
                info = placed.get(rel)
                slot = info["slot"] if info else None
                if slot is None and f.parent.name == "masters":
                    slot = "master"          # the folder says so, and that one IS a convention
                item = {"file": f.name, "folder": f.parent.name,
                        "recorded": info is not None,
                        "guessed": bool(info) and not info["declared"],
                        "src": thumb(f, band["card_w"] * THUMB_SCALE,
                                     band["card_h"] * THUMB_SCALE)
                        if slot in ("left", "right") else thumb(f, 520, None)}
                found[slot if slot in found else "unplaced"].append(item)
        drawn = bundled.get(slug, {})
        duties.append({
            "slug": slug, "name": duty_name,
            # filename the action board draws in each slot, or None
            "inBoard": {"left": (drawn.get(G.ACTIONS[0]) or [None, None])[1],
                        "right": (drawn.get(G.ACTIONS[1]) or [None, None])[1]},
            "actions": 1 if b is None else 2,
            "left": {"name": (a.get("name") or "").strip(),
                     "label": (a.get("shortLabel") or "").strip(),
                     "folder": None, "art": found["left"]},
            "right": None if b is None else {
                "name": (b.get("name") or "").strip(),
                "label": (b.get("shortLabel") or "").strip(),
                "folder": None, "art": found["right"]},
            "masters": found["master"], "unplaced": found["unplaced"],
            "seals": seals_for(slug, placed, seal_px, briefs),
            "folders": sorted(p.name for p in folder.iterdir() if p.is_dir())
            if folder.is_dir() else [],
        })
    return {"band": band, "duties": duties, "artNotes": art_notes,
            "sealPx": seal_px, "titheSeals": tithe_seals(seal_px, briefs),
            "sealBriefs": sorted(briefs.values(), key=lambda b: b["file"]) + waiting,
            "sealBriefsWaiting": waiting}


def build() -> str:
    data = collect(board())
    band = dict(data["band"], span=data["band"]["card_w"] * 2 + data["band"]["gap"])
    # THE BOARD DOES NOT OFFER AN ARCHIVAL BRIEF. A per-duty button promises the duty's own
    # names in it, and an archival brief is copied verbatim with nothing substituted -- pressing
    # Produce's button and getting a brief that says DEVOTION would be worse than no button.
    briefs = [p for p in prompts() if not p["archival"]]
    if not briefs:
        raise SystemExit("every brief in prompts/ is marked archival, so there is none the "
                         "board can fill a duty's names into")
    for b in briefs:
        b["text"] = b["text"].replace("{{GEOMETRY}}", geometry_text(band, 3.0))
    data["briefs"] = briefs
    data["subjects"] = subjects()
    page = TMPL.read_text(encoding="utf-8")
    for token, value in (("__DATA__", json.dumps(data)), ("__BUILD__", BUILD_VERSION)):
        if token not in page:
            raise SystemExit("the template no longer has %s in it" % token)
        page = page.replace(token, value)
    return page


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None)
    ap.add_argument("--open", action="store_true")
    a = ap.parse_args(argv)
    page = build()
    out = pathlib.Path(a.out) if a.out else OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")

    data = collect(board())
    slots = sum(d["actions"] for d in data["duties"])
    filled = sum(1 for d in data["duties"] for k in ("left", "right")
                 if d[k] and d[k]["art"])
    try:
        shown = out.relative_to(ROOT)
    except ValueError:
        shown = out
    print("wrote %s  (%d KB)" % (shown, len(page.encode("utf-8")) // 1024))
    print("  %d of %d action slots have art;  %d of %d duties have a master"
          % (filled, slots,
             sum(1 for d in data["duties"] if d["masters"]), len(data["duties"])))
    if a.open:
        webbrowser.open(out.resolve().as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
