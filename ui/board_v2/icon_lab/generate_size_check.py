#!/usr/bin/env python3
"""Show every cut mark at a chosen drawn size, so the size can be decided by looking at it.

    python3 ui/board_v2/icon_lab/generate_size_check.py --open

WHAT THIS PAGE IS FOR, AND WHAT IT DELIBERATELY DOES NOT DO. Its output is a NUMBER, not a file.
You look at the marks at 80, at 110, at 130, at the scale your own window would draw them, and
you decide; that decision then goes into geometry.py's SEAL, which is the one place the board's
sizes live.

IT DOES NOT EXPORT BAKED ICONS, and that is a decision rather than an omission. Baking the drawn
size into a file takes it away from geometry.py, so changing one number would stop restyling the
marks and start needing fourteen files re-cut. Baking the ground takes it away from the record's
`ground` field and the one CSS rule that owns the colour. Baking a border makes a style into art.
And a file at exactly its drawn size is soft on a retina screen, which is why the board inlines
every mark at SEAL * 2 instead. A viewer that quietly became a source would undo all four.

The icon sizer beside this decides the CROP -- how much of a master a mark is. This decides how
big that mark is drawn. Two decisions, two pages.
"""
import argparse
import base64
import importlib.util
import json
import pathlib
import re
import sys
import webbrowser

HERE = pathlib.Path(__file__).resolve().parent
BOARD = HERE.parent
ART_DIR = BOARD / "duty_actions"
ATTRIB_FILE = BOARD / "attribution.json"
TEXT_FILE = BOARD / "duty_text.json"
TMPL = HERE / "size_check.html.tmpl"
OUT = HERE / "generated" / "size_check.html"

_spec = importlib.util.spec_from_file_location(
    "geometry", BOARD / "action_board" / "geometry.py")
G = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(G)

doc = json.loads(ATTRIB_FILE.read_text(encoding="utf-8"))
REC, FOLDERS = doc["files"], doc.get("markFolders") or ("seals",)
TEXT = json.loads(TEXT_FILE.read_text(encoding="utf-8"))["duties"]
SIDE = {"left": "actionA", "right": "actionB"}


def version_of(name):
    m = re.search(r"_v(\d+)\.", name)
    return int(m.group(1)) if m else -1


def marks() -> dict:
    """The mark the board would draw for each slot, keyed (duty, actionA|actionB).

    THE BOARD'S OWN RULE, not just the icons. This looked only in `icons/` for an hour, which is
    right while every slot has one and silently wrong the first time a slot falls back to its wax
    seal: the page would show thirteen marks and say nothing about the fourteenth, so a size
    chosen on it would have been chosen without looking at the mark it most affects.

    The rule is attribution.json's markFolders read IN ORDER -- the later folder wins -- and then
    the higher version inside it. A version counts up within one lineage and means nothing across
    two, which is the mistake the board itself made once.
    """
    order = {n: i for i, n in enumerate(FOLDERS)}
    best = {}
    for path, e in REC.items():
        if not path.startswith("duty_actions/"):
            continue
        parts = path[len("duty_actions/"):].split("/")
        if len(parts) < 3 or parts[1] not in order or "masters" in parts:
            continue
        slot = SIDE.get(e.get("slot"))
        if slot is None:
            continue
        key = (parts[0], slot)
        rank = (order[parts[1]], version_of(parts[-1]))
        if key not in best or rank > best[key][0]:
            best[key] = (rank, path)
    return best


def main():
    best = marks()

    try:
        from PIL import Image
    except ImportError:
        Image = None                       # the page still builds; the captions lose their size

    # BOARD ORDER, so the page reads the way the ribbon does rather than alphabetically.
    icons = []
    for slug, _name, _deg in G.DUTIES:
        for slot in ("actionA", "actionB"):
            got = best.get((slug, slot))
            if not got or not TEXT[slug].get(slot):
                continue
            f = BOARD / got[1]
            px = Image.open(f).width if Image else 0
            icons.append({
                "name": TEXT[slug][slot]["name"],
                "px": px,
                "src": "data:image/%s;base64,%s"
                       % ("webp" if f.suffix == ".webp" else "png",
                          base64.b64encode(f.read_bytes()).decode()),
            })

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--open", action="store_true", help="open the page when it is built")
    a = ap.parse_args()

    if not TMPL.is_file():
        raise SystemExit("the template is not at %s" % TMPL)
    page = TMPL.read_text(encoding="utf-8")
    fill = {"__ICONS__": json.dumps(icons),
            "__CANVAS__": json.dumps(G.as_dict()["canvas"])}
    for token, value in fill.items():
        if token not in page:
            raise SystemExit("the template has no %s in it, so the build would be dropped on the "
                             "floor" % token)
        page = page.replace(token, value)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding="utf-8")
    print("  wrote %s  (%d KB)" % (OUT, len(page.encode()) // 1024))
    print("  %d marks, %d to %d px square;  the board draws them at %d today"
          % (len(icons), min(i["px"] for i in icons), max(i["px"] for i in icons), G.SEAL))
    if a.open:
        webbrowser.open(OUT.as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
