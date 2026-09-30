#!/usr/bin/env python3
"""Every duty's action art on one page, with the blanks showing.

    python3 ui/board_v2/duty_art_lab/generate_duty_art_board.py --open

Sixteen action images and eight masters, at the size the board draws them, in the wheel's own
order. WHAT IS NOT THERE IS THE POINT: an empty slot is a dashed frame carrying the action's
name, so the page reads as a list of what still has to be drawn rather than as a gallery of what
has been.

WHERE EACH THING COMES FROM, and none of it from here:

  the eight duties and their order   generate_layout_lab.py's DUTY_ORDER
  the card's size and the gap        its default_state(), the same band the cutter uses
  what each action is called         ui/board_v2/duty_text.json
  how many actions a duty offers     the same file -- a null actionB means one
  the art itself                     ui/board_v2/duty_actions/<duty>/<folder>/

WHICH SLOT A FILE BELONGS IN is the one thing that cannot be derived, and the page says so where
it has had to guess. The folders are named after what the action does -- `gain_piety`,
`gain_coins` -- and those names came from wording that has since changed, so they neither match
duty_text.json nor sort into slot order: Clerical's LEFT is `gain_piety` and its RIGHT is
`gain_coins`, which alphabetically is backwards. Three things are tried, in order:

  1. an explicit `slot` on the file's attribution.json entry: "left", "right" or "master"
  2. `_left` or `_right` in the filename, which is what crop_duty_master.py now writes
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
import sys
import webbrowser

from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BOARD = HERE.parent
ART = BOARD / "duty_actions"
ATTRIB = BOARD / "attribution.json"
TEXT = BOARD / "duty_text.json"
TMPL = HERE / "duty_art_board.html.tmpl"
OUT = HERE / "generated" / "duty_art_board.html"

BUILD_VERSION = "0.1"
# Thumbnails are for judging composition at board size, so they are built at twice the card and
# no larger. Sixteen full-resolution crops inlined would be 20 MB of page to show 750px pictures.
THUMB_SCALE = 2
JPEG_Q = 82


def viewfinder():
    """The viewfinder's generator, imported for the things both pages need.

    The briefs, the subject descriptions and the shape-and-zones paragraph all belong to one
    owner. A copy here is how the board comes to hand out a brief the viewfinder would not.
    """
    p = HERE / "generate_duty_art_lab.py"
    spec = importlib.util.spec_from_file_location("_board_vf", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_board_vf"] = mod
    spec.loader.exec_module(mod)
    return mod


def lab():
    p = HERE.parent / "layout_lab" / "generate_layout_lab.py"
    if not p.is_file():
        raise SystemExit("the layout lab generator is not at %s -- it owns the duty order and "
                         "the card size, and this page is a list of both" % p)
    spec = importlib.util.spec_from_file_location("_board_lab", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_board_lab"] = mod
    spec.loader.exec_module(mod)
    return mod


def slots_from_attribution(m) -> dict:
    """Which slot each recorded file sits in -- ASKED OF THE LAB, not worked out again here.

    This used to carry its own copy of the rule. The lab's generator now needs the same answer,
    to decide which artwork to build into the page, and two copies of one rule is how a board
    comes to show art that the lab does not open with. The board's job is to report what the lab
    will do, so it has to be asking the same question of the same function.
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


def collect(m) -> dict:
    S = m.default_state()
    L, R = S["display"]["artLeft"], S["display"]["artRight"]
    band = {"card_w": L["width"], "card_h": L["height"],
            "gap": R["x"] - (L["x"] + L["width"])}
    if not TEXT.is_file():
        raise SystemExit("duty_text.json is not at %s -- it owns what the actions are called"
                         % TEXT)
    TXT = json.loads(TEXT.read_text(encoding="utf-8"))["duties"]
    placed = slots_from_attribution(m)

    # WHAT THE LAB WILL OPEN WITH, from the lab itself rather than inferred. If these two ever
    # disagree the board is the thing that is wrong, so it is better to ask than to reconstruct.
    bundled = getattr(m, "ART_BY_DUTY", {}) or {}
    art_notes = list(getattr(m, "ART_NOTES", []) or [])

    duties = []
    # THE ORDER COMES OFF THE STATE, not off the DUTIES tuple. The state is what the lab
    # actually composes and its dict preserves the wheel's order; the tuple is only where it
    # starts, and a page listing duties in a different order from the board would be a quiet
    # lie about which slot is which.
    for slug in S["duties"]:
        d = S["duties"][slug]
        t = TXT.get(slug, {})
        a, b = t.get("actionA") or {}, t.get("actionB")
        folder = ART / slug
        found = {"left": [], "right": [], "master": [], "unplaced": []}
        if folder.is_dir():
            for f in sorted(folder.rglob("*.png")):
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
        inlab = bundled.get(slug, {})
        duties.append({
            "slug": slug, "name": d.get("name", slug),
            # filename the generated lab page carries for each slot, or None
            "inLab": {"left": (inlab.get(m.ACTIONS[0][0]) or [None, None])[1],
                      "right": (inlab.get(m.ACTIONS[1][0]) or [None, None])[1]},
            "actions": 1 if b is None else 2,
            "left": {"name": (a.get("name") or "").strip(),
                     "label": (a.get("shortLabel") or "").strip(),
                     "folder": None, "art": found["left"]},
            "right": None if b is None else {
                "name": (b.get("name") or "").strip(),
                "label": (b.get("shortLabel") or "").strip(),
                "folder": None, "art": found["right"]},
            "masters": found["master"], "unplaced": found["unplaced"],
            "folders": sorted(p.name for p in folder.iterdir() if p.is_dir())
            if folder.is_dir() else [],
        })
    return {"band": band, "duties": duties, "artNotes": art_notes}


def build() -> str:
    data = collect(lab())
    vf = viewfinder()
    band = dict(data["band"], span=data["band"]["card_w"] * 2 + data["band"]["gap"])
    # THE BOARD DOES NOT OFFER AN ARCHIVAL BRIEF. A per-duty button promises the duty's own
    # names in it, and an archival brief is copied verbatim with nothing substituted -- pressing
    # Produce's button and getting a brief that says DEVOTION would be worse than no button.
    # The viewfinder still offers them, where "verbatim" is the stated contract.
    briefs = [p for p in vf.prompts() if not p["archival"]]
    if not briefs:
        raise SystemExit("every brief in prompts/ is marked archival, so there is none the "
                         "board can fill a duty's names into")
    for b in briefs:
        b["text"] = b["text"].replace("{{GEOMETRY}}", vf.geometry_text(band, 3.0))
    data["briefs"] = briefs
    data["subjects"] = vf.subjects()
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

    data = collect(lab())
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
