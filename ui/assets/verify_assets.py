"""Check every raster against the contract in ../hybrid-svg-png.md.

The contract exists because a transparent PNG's canvas bounds and its visual bounds are different
objects, and nothing in SVG or the DOM will tell you so. This makes that failure loud: it recomputes
each alpha box and compares it to the declared one, and it flags the two things that silently ruin a
set -- an untrimmed canvas, and members of one normalisation group whose ink does not agree.

    python3 verify_assets.py                        # check this tree
    python3 verify_assets.py --write                # recompute assets.json from the files
    python3 verify_assets.py --root ../assets-gothic   # check another tree's records

TWO TREES, ONE CHECK

The gothic tree keeps its own attribution.json of the same shape, and until now nothing ran against
it: the check walked the directory it happened to live in. That is the worst kind of gap, because
the file LOOKS like a record being kept. The licences in that tree are the ones that actually bite
-- portraits that may never be committed at all, a wagon icon whose attribution has to ship with the
game -- so it is the tree that most wants a guard, and it had none.

Only the attribution half travels. The rest of this file checks each raster against assets.json, the
canvas-and-ink-box contract, and the gothic tree has no assets.json because its art is not placed
that way. A root without one is checked for its records and says so, rather than inventing a
contract it was never written to.

WHICH DIRECTORIES HOLD ASSETS

From the tree's own attribution.json, under `assetDirs`, falling back to this tree's four. A second
hard-coded list here would be one more thing to update from a distance when a tree grows a folder.
"""
import argparse
import fnmatch
import json, pathlib, sys

from PIL import Image
import numpy as np

HERE = pathlib.Path(__file__).parent
DEFAULT_ASSET_DIRS = ("icons", "portraits", "frames", "ui")
ALPHA = 8
# Below this fill a "content-normalized" asset is carrying padding it should not: the renderer
# supplies padding, the file does not. 0.95 leaves room for an antialiasing bleed and no more.
TIGHT = 0.95


def ink_box(path):
    a = np.array(Image.open(path).convert("RGBA"))[:, :, 3]
    ys, xs = np.nonzero(a > ALPHA)
    if len(xs) == 0:
        return None
    return [int(xs.min()), int(ys.min()), int(xs.max()) + 1 - int(xs.min()),
            int(ys.max()) + 1 - int(ys.min())]


def attribution_problems(root):
    """Every file in the tree must be accounted for by name, not by assumption.

    This is the check that matters most, because the failure it catches is silent: a file arrives,
    gets used, ships, and nobody can say afterwards where it came from. An asset with no entry is a
    problem even when its licence would have been fine -- the record is the obligation.
    """
    att = json.loads((root / "attribution.json").read_text())
    out = []
    owned = att.get("projectOwned", [])
    # Walk the directories that hold assets, rather than the whole tree minus a list of
    # extensions. The blacklist version reported __pycache__ as an unlicensed asset the first
    # time anyone ran a script in here -- and a check that fails on a stray .pyc is a check
    # people learn to ignore. `_masters` is excluded because a master is not a shipped file;
    # its production cut carries the entry.
    for folder in att.get("assetDirs", DEFAULT_ASSET_DIRS):
        base = root / folder
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if not p.is_file() or p.name in {".gitkeep", ".gitignore"}:
                continue
            if "__pycache__" in p.parts:
                continue
            rel = p.relative_to(root).as_posix()
            if rel in att["files"]:
                state = att["files"][rel]["state"]
                if state != "present":
                    out.append("%-52s on disk but recorded as '%s'. A held file in the tree is "
                               "one wholesale `git add` away from being committed; its directory "
                               "carries a .gitignore for that reason, but move it out once you "
                               "are done." % (rel, state))
                continue
            if any(fnmatch.fnmatch(rel, pat) for pat in owned):
                continue
            out.append("%-52s no entry in attribution.json and matches no projectOwned pattern"
                       % rel)

    for rel, a in sorted(att["files"].items()):
        if a["state"] == "present" and not (root / rel).exists():
            out.append("%-52s recorded as present, but the file is missing" % rel)
        lic = att["licences"][a["licence"]]
        if a["state"] == "present" and lic["attributionRequired"]:
            for field in ("title", "creator", "licence"):
                if not a.get(field):
                    out.append("%-52s needs %s: its licence requires attribution" % (rel, field))
    return out


def main(write=False, root=HERE):
    meta_path = root / "assets.json"
    problems, held, groups = [], [], {}
    if not write:
        problems += attribution_problems(root)

    if not meta_path.is_file():
        # A tree with records but no raster contract. Saying so is the point: a silent zero here
        # would read as "every asset checked out" when nothing was measured at all.
        if write:
            raise SystemExit("%s has no assets.json to rewrite." % root)
        for line in problems:
            print(line)
        print("\n%s has no assets.json, so only its records were checked: %d file(s) on record, "
              "%d problem(s)" % (root, len(json.loads((root / "attribution.json").read_text())
                                            .get("files", {})), len(problems)))
        return 1 if problems else 0

    meta = json.loads(meta_path.read_text())
    for name, a in sorted(meta["assets"].items()):
        p = root / a["src"]
        if not p.exists():
            # An asset whose licence is not on record is deliberately absent, not broken. Reporting
            # it as a failure would make the check cry wolf, and a check that cries wolf is ignored.
            if a.get("licence") == "unverified":
                held.append("%-26s held: licence unverified, file not committed" % name)
            else:
                problems.append("%-26s missing: %s" % (name, a["src"]))
            continue
        box = ink_box(p)
        w, h = Image.open(p).size
        if write:
            a["canvasPx"] = [w, h]
            a["inkBoxPx"] = box
            a["inkFill"] = [round(box[2] / w, 3), round(box[3] / h, 3)]
            a["inkAspect"] = round(box[2] / box[3], 4)
            continue

        if a["canvasPx"] != [w, h]:
            problems.append("%-26s canvas declared %s, actually %s"
                            % (name, a["canvasPx"], [w, h]))
        if a["inkBoxPx"] != box:
            problems.append("%-26s inkBox declared %s, measured %s"
                            % (name, a["inkBoxPx"], box))
        fill = (box[2] / w, box[3] / h)
        if a["class"] == "content-normalized" and min(fill) < TIGHT:
            problems.append("%-26s untrimmed: ink fills %.3f x %.3f of its canvas. Crop to the "
                            "alpha box, or the renderer must place from inkBoxPx."
                            % (name, fill[0], fill[1]))
        if a.get("normalization") == "ink-height":
            groups.setdefault(str(p.parent.parent), []).append((name, box[3], box[2] / box[3]))

    # A group must agree on the dimension it normalises -- and only on that one. Differing widths
    # are not a fault here, they are the point: figures line up by how tall they stand, and each
    # one's width follows from its own ink aspect. An earlier version of this check complained
    # about the aspect spread, which had it exactly backwards.
    for grp, members in sorted(groups.items()):
        if len(members) < 2:
            continue
        heights = [m[1] for m in members]
        if max(heights) - min(heights) > 1:
            problems.append("group %s: ink heights disagree (%s). A set normalised on ink-height "
                            "must share it; the widths may differ freely."
                            % (grp, ", ".join("%s %d" % (n, h) for n, h, _r in members)))

    if write:
        meta_path.write_text(json.dumps(meta, indent=2) + "\n")
        print("assets.json rewritten from the files")
        return 0

    for line in held:
        print(line)
    for line in problems:
        print(line)
    print("\n%d asset(s) checked, %d problem(s), %d held"
          % (len(meta["assets"]), len(problems), len(held)))
    return 1 if problems else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--write", action="store_true",
                    help="recompute assets.json from the files, rather than checking")
    ap.add_argument("--root", default=str(HERE),
                    help="the asset tree to check; defaults to the one this script lives in")
    args = ap.parse_args()
    sys.exit(main(write=args.write, root=pathlib.Path(args.root).resolve()))
