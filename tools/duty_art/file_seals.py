"""File a wax seal: normalise it, place it, record it.

    python tools/duty_art/file_seals.py duty  <duty> <image> [<image>]
    python tools/duty_art/file_seals.py tithe <wheat> <stone> <silver>

Two kinds of seal and two folder conventions, which is why this is one tool with two
subcommands rather than two tools: everything except WHERE THE FILES GO is shared.

    duty    the red marks in a duty's tile, one per action, under
            ui/board_v2/duty_actions/<duty>/seals/. The print carries a version and the
            board draws the newest -- so a new one supersedes by arriving.

    tithe   the grey marks in the Take Tithe column, under ui/board_v2/tokens/. The print
            has a STABLE name, because generate_action_board looks it up by name, and the
            version lives on the master. A new one supersedes by replacing the print, and
            the print's own record names the master it came from.

Either way the untouched original goes to masters/ and is never re-encoded: that is the
archive, a lossy archive is not one, and anything wanted at another size comes off it.

WHY THIS IS NOT JUST A COPY. Every set generated so far has come back filling a different
fraction of its own square -- from 0.914 to 0.998. Dropped in untouched, two seals in the
same tile at the same size differ by up to six per cent, which reads as a fault in the
layout rather than a difference in the drawings. SOLID_FRACTION in
ui/board_v2/action_board/geometry.py is what every disc on this board is held to, and
tests/action_board measures the files against it. This scales each image about its own
centre to reach it, inside the canvas it was generated at, and refuses rather than filing
something the test would catch later.

A RECORD SAYS WHERE A FILE CAME FROM, NOT WHETHER IT IS THE ONE IN USE. Entries used to
read "the untouched original of X" and "the seal for Y", which is false for every version
but the current one the moment a second arrives. Provenance is in attribution.json;
which version draws is the folder convention above, in one place each.

Needs `pillow` and `numpy`.
"""
from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
BOARD = ROOT / "ui" / "board_v2"
ATTRIB = BOARD / "attribution.json"
SIDE_OF = {"actionA": "left", "actionB": "right"}

# THE PRINT IS WEBP AND THE MASTER IS PNG. At quality 90 the shipped set is 7 MB where the
# PNGs were 40, for a worst case of 12 of 255 on one pixel -- measured on the seal composited
# over the panel it sits on, at the size the board inlines it, which is the only place it is
# ever seen.
UNRECORDED = ("unrecorded -- this one predates the folder the briefs are kept in. If the text "
              "turns up it goes in duty_art_lab/prompts/seals/ with a `produces:` header and "
              "this field names it.")
# AND THE OTHER WAY OF NOT KNOWING, which is not the same way. A file can arrive after the
# folder exists and still have no brief with it, because the text was not passed on. Saying it
# predates the folder would be a dated claim about a file that does not fit it, and the record
# would read as settled. --unbriefed is how you say so deliberately; leaving --brief off by
# accident is what the refusal below is for.
UNBRIEFED = ("not supplied -- this one postdates duty_art_lab/prompts/seals/ and belongs in it. "
             "The text was not passed on with the image. When it is, it goes in the folder with "
             "a `produces:` header and this field names it.")
BRIEFS = BOARD / "duty_art_lab" / "prompts" / "seals"

PRINT_SUFFIX = ".webp"
PRINT_OPTS = {"quality": 90, "method": 6}
MASTER_SUFFIX = ".png"

# TWO FIELDS, ONE FACT, AND THEY HAD STOPPED AGREEING. `source` said "no prompt or seed on
# record" on every file this tool wrote, which was true when it was written and became false the
# moment reproducibleBy started naming a brief in the folder next door. Twenty-four records
# asserted both at once. A record that contradicts itself is worse than one that admits it does
# not know: the reader has to pick which half to believe, and nothing tells them which.
#
# So `source` no longer speaks about the prompt at all. reproducibleBy owns that, alone, and says
# either which brief produced the file or in so many words that nobody kept it.
PROVENANCE = {
    "state": "present",
    "creator": "Generated with ChatGPT (OpenAI)",
    "source": "generated in ChatGPT sessions for this project; no upstream URL and no seed. "
              "Which prompt produced it is reproducibleBy's to say, not this field's.",
    "licence": "openai-generated",
}

TITHE_ROLE = (
    "a %s seal for the Take Tithe column. A SEAL on this board is a thing you can take and its "
    "colour says which kind -- red for a duty action, grey for a resource -- so the Tithe column, "
    "which is the third choice beside the two actions, speaks the same language they do. The "
    "artwork is the COMPLETE mark: rim, disc and motif are painted in, so the layout draws the "
    "image and nothing behind or around it.")


def geometry():
    """The board's own module, loaded by path -- it owns SOLID_FRACTION and nothing restates it."""
    path = BOARD / "action_board" / "geometry.py"
    spec = importlib.util.spec_from_file_location("_seal_geometry", path)
    if spec is None or spec.loader is None:                       # pragma: no cover
        raise SystemExit("cannot load %s" % path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def solid_fraction(im) -> float:
    """How much of its own square the drawing actually fills, by its alpha."""
    import numpy as np
    a = np.array(im.convert("RGBA"))[:, :, 3]
    rows = np.where(a.max(axis=1) > 8)[0]
    cols = np.where(a.max(axis=0) > 8)[0]
    if not len(rows) or not len(cols):
        raise SystemExit("that image is entirely transparent")
    return max(rows[-1] - rows[0] + 1, cols[-1] - cols[0] + 1) / im.size[0]


def normalised(im, target: float):
    """Scaled about its own centre to fill `target` of its square, on the canvas it came with."""
    from PIL import Image
    w, h = im.size
    k = target / solid_fraction(im)
    n = (max(1, round(w * k)), max(1, round(h * k)))
    scaled = im.resize(n, Image.LANCZOS)
    if k <= 1:
        out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        out.paste(scaled, ((w - n[0]) // 2, (h - n[1]) // 2), scaled)
        return out, k
    left, top = (n[0] - w) // 2, (n[1] - h) // 2
    return scaled.crop((left, top, left + w, top + h)), k


def next_version(folder: pathlib.Path, stem: str) -> int:
    """The next free _vNN beside what is already there, counted across every extension.

    NOTHING IS EVER OVERWRITTEN in a versioned folder. A drawing that was replaced stays on
    disk, superseded -- and since there is no undo here, not overwriting IS the undo.
    """
    n = 0
    for f in folder.glob("%s_v*" % stem):
        tail = f.stem[len(stem) + 2:]
        if f.stem.startswith(stem + "_v") and tail.isdigit():
            n = max(n, int(tail))
    return n + 1


def prepare(src: pathlib.Path, G):
    """Open, measure, normalise and check one image. Nothing is written."""
    from PIL import Image
    if not src.is_file():
        raise SystemExit("no such image: %s" % src)
    im = Image.open(src).convert("RGBA")
    before = solid_fraction(im)
    out, k = normalised(im, G.SOLID_FRACTION)
    after = solid_fraction(out)
    if abs(after - G.SOLID_FRACTION) > G.SOLID_TOLERANCE:
        raise SystemExit("%s comes out at %.3f and this board's discs are %.3f +/- %.3f"
                         % (src.name, after, G.SOLID_FRACTION, G.SOLID_TOLERANCE))
    print("  %-44s %.3f -> x%.4f -> %.3f" % (src.name, before, k, after))
    return im, out, before, k


def briefs_of(a, n: int) -> list:
    """Which brief produced each image, checked against the folder rather than taken on trust.

    ONE PER IMAGE, because a duty's two seals are not always one brief: Give Alms' building and
    its alms came from two, the second written against the first. One name given for several
    images applies to all of them, which is the common case.

    A reproducibleBy naming a file that is not there is worse than one admitting it does not
    know, because the first looks answered.
    """
    given = list(a.brief or [])
    if not given:
        # NOT KNOWING HAS TO BE SAID OUT LOUD. Defaulting to UNRECORDED meant a forgotten
        # --brief filed a dated claim -- "predates the folder" -- about a file that does not
        # predate it, and the record then reads as answered. Say which kind of not-knowing it is.
        if getattr(a, "unbriefed", False):
            return [UNBRIEFED] * n
        raise SystemExit(
            "no --brief given. Name the brief in %s that produced each image, or pass "
            "--unbriefed to record that the text was not supplied with it."
            % BRIEFS.relative_to(ROOT))
    if len(given) == 1:
        given = given * n
    if len(given) != n:
        raise SystemExit("%d brief(s) given for %d image(s) -- pass one, or one each"
                         % (len(given), n))
    out = []
    for g in given:
        name = pathlib.Path(g).name
        if not (BRIEFS / name).is_file():
            raise SystemExit("no brief called %s in %s -- it has %s"
                             % (name, BRIEFS.relative_to(ROOT),
                                ", ".join(sorted(f.name for f in BRIEFS.glob("*.md")
                                                 if f.name.lower() != "readme.md")) or "nothing"))
        out.append((BRIEFS / name).relative_to(BOARD).as_posix())
    return out


def corrected(k: float, before: float, target: float) -> str:
    return ("scaled x%.4f about its own centre, from %.3f of its square to the board's %.3f"
            % (k, before, target))


def load_doc():
    return json.loads(ATTRIB.read_text(encoding="utf-8"),
                      object_pairs_hook=collections.OrderedDict)


def save_doc(doc) -> None:
    ATTRIB.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print("  recorded in %s (%d entries)" % (ATTRIB.relative_to(ROOT), len(doc["files"])))


# =================================================================================================
def do_duty(a, G) -> None:
    doc = load_doc()
    folders = doc["slotFolders"].get(a.duty)
    if folders is None:
        raise SystemExit("attribution.json has no slotFolders for %r -- known duties are %s"
                         % (a.duty, ", ".join(sorted(doc["slotFolders"]))))
    slots = sorted(folders)
    if a.slot:
        # ONE SLOT AT A TIME, for a version that supersedes only half a pair.
        if a.slot not in slots:
            raise SystemExit("%s has no %s -- it has %s"
                             % (a.duty, a.slot, ", ".join(slots)))
        slots = [a.slot]
    if len(a.images) != len(slots):
        raise SystemExit("%s has %d action(s) -- %s -- and %d image(s) were given. Use --slot to "
                         "file one of them on its own."
                         % (a.duty, len(slots),
                            ", ".join("%s: %s" % (s, folders[s]) for s in slots), len(a.images)))

    dest = BOARD / "duty_actions" / a.duty / "seals"
    briefs = briefs_of(a, len(a.images))   # before anything is written, not during
    pending = [(src, slot) + prepare(src, G) for src, slot in zip(a.images, slots)]
    if a.dry_run:
        print("  dry run: nothing written")
        return

    (dest / "masters").mkdir(parents=True, exist_ok=True)
    files = doc["files"]
    pretty = a.duty.replace("_", " ").title()
    for i, (src, slot, original, out, before, k) in enumerate(pending):
        stem = "%s_%s_seal" % (a.duty, slot)
        n = next_version(dest, stem)
        shipped = dest / ("%s_v%02d%s" % (stem, n, PRINT_SUFFIX))
        master = dest / "masters" / ("%s_master_v%02d%s" % (stem, n, MASTER_SUFFIX))
        original.save(master)
        out.save(shipped, "WEBP", **PRINT_OPTS)
        what = folders[slot].replace("_", " ")
        files[master.relative_to(BOARD).as_posix()] = dict(
            PROVENANCE, collection="Pilgrim board_v2 duty action seals",
            title="%s %s seal v%02d, as generated" % (pretty, what, n), slot="master",
            role="the drawing as it came out of the generator, before the optical correction",
            notes="master, not shipped; the original of %s" % shipped.name)
        files[shipped.relative_to(BOARD).as_posix()] = dict(
            PROVENANCE, collection="Pilgrim board_v2 duty action seals",
            title="%s %s seal v%02d" % (pretty, what, n), slot=SIDE_OF[slot],
            role="a red wax seal for %s's %s action, drawn in the duty tile"
                 % (pretty, SIDE_OF[slot].upper()),
            reproducibleBy=briefs[i],
            notes="%s; re-encoded as WebP at quality %d from %s, the drawing unchanged"
                  % (corrected(k, before, G.SOLID_FRACTION), PRINT_OPTS["quality"], master.name))
        print("  wrote %s" % shipped.relative_to(ROOT))
    save_doc(doc)


# =================================================================================================
def do_tithe(a, G) -> None:
    """The three resources, whose PRINT NAME IS STABLE and whose version lives on the master.

    generate_action_board looks these up by name -- seal_wheat, seal_stone, seal_silver -- so
    there is no newest-wins here and nothing to choose at draw time. Replacing the print IS the
    change, and the print's record names the master it was exported from, which is the only
    place that says which version the board is showing.
    """
    order = list(G.TOKEN_ORDER)
    if len(a.images) != len(order):
        raise SystemExit("the Tithe column has %d resources -- %s -- and %d image(s) were given"
                         % (len(order), ", ".join(order), len(a.images)))

    masters = BOARD / "tokens" / "masters"
    prints = BOARD / "tokens" / "resources"
    briefs = briefs_of(a, len(a.images))   # before anything is written, not during
    pending = [(src, name) + prepare(src, G) for src, name in zip(a.images, order)]
    if a.dry_run:
        print("  dry run: nothing written")
        return

    masters.mkdir(parents=True, exist_ok=True)
    prints.mkdir(parents=True, exist_ok=True)
    doc = load_doc()
    files = doc["files"]
    for i, (src, name, original, out, before, k) in enumerate(pending):
        stem = "seal_%s" % name
        n = next_version(masters, stem)
        master = masters / ("%s_v%02d%s" % (stem, n, MASTER_SUFFIX))
        shipped = prints / (stem + PRINT_SUFFIX)
        original.save(master)
        # Anything the superseded print left behind in another format would still be found by
        # the walks, so it goes rather than lingering as a second answer to one name.
        for stale in prints.glob(stem + ".*"):
            if stale != shipped:
                stale.unlink()
                print("  removed %s" % stale.relative_to(ROOT))
        out.save(shipped, "WEBP", **PRINT_OPTS)
        files[master.relative_to(BOARD).as_posix()] = dict(
            PROVENANCE, collection="Pilgrim board_v2 resource seals",
            title="%s resource seal v%02d, as generated" % (name.title(), n), slot="master",
            role="the drawing as it came out of the generator, before the optical correction",
            notes="master, not shipped")
        files[shipped.relative_to(BOARD).as_posix()] = dict(
            PROVENANCE, collection="Pilgrim board_v2 resource seals",
            title="%s resource seal" % name.title(), slot="resource",
            role=TITHE_ROLE % name,
            reproducibleBy=briefs[i],
            notes="exported from %s; %s; re-encoded as WebP at quality %d, the drawing unchanged"
                  % (master.relative_to(BOARD).as_posix(),
                     corrected(k, before, G.SOLID_FRACTION), PRINT_OPTS["quality"]))
        print("  wrote %s  (from %s)" % (shipped.relative_to(ROOT), master.name))
    save_doc(doc)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="measure and report, write nothing")
    ap.add_argument("--brief", nargs="+", default=None, metavar="FILE",
                    help="the brief(s) in ui/board_v2/duty_art_lab/prompts/seals/ that "
                         "produced these -- one, or one per image in the same order. Without "
                         "it the record says so rather than leaving the field out.")
    ap.add_argument("--unbriefed", action="store_true",
                    help="file an image whose brief was not supplied, recording that in so many "
                         "words. For a file that postdates the briefs folder and belongs in it.")
    sub = ap.add_subparsers(dest="kind", required=True)

    d = sub.add_parser("duty", help="the red seals in a duty's tile")
    d.add_argument("duty", help="the duty slug, as duty_text.json spells it")
    d.add_argument("images", nargs="+", type=pathlib.Path,
                   help="one image per action, in slot order (actionA first)")
    d.add_argument("--dry-run", action="store_true", help=argparse.SUPPRESS)
    d.add_argument("--brief", nargs="+", default=None, help=argparse.SUPPRESS)
    d.add_argument("--unbriefed", action="store_true", default=argparse.SUPPRESS,
                   help=argparse.SUPPRESS)
    d.add_argument("--slot", default=None, metavar="actionA|actionB",
                   help="file just this one of the duty's slots, for a version that supersedes "
                        "only half a pair")

    t = sub.add_parser("tithe", help="the grey seals in the Take Tithe column")
    t.add_argument("images", nargs="+", type=pathlib.Path,
                   help="one image per resource, in the board's own order")
    t.add_argument("--dry-run", action="store_true", help=argparse.SUPPRESS)
    t.add_argument("--brief", nargs="+", default=None, help=argparse.SUPPRESS)
    t.add_argument("--unbriefed", action="store_true", default=argparse.SUPPRESS,
                   help=argparse.SUPPRESS)

    a = ap.parse_args(argv)
    if not hasattr(a, "slot"):
        a.slot = None
    G = geometry()
    (do_duty if a.kind == "duty" else do_tithe)(a, G)


if __name__ == "__main__":
    main(sys.argv[1:])
