"""Check every raster against the contract in ../hybrid-svg-png.md.

The contract exists because a transparent PNG's canvas bounds and its visual bounds are different
objects, and nothing in SVG or the DOM will tell you so. This makes that failure loud: it recomputes
each alpha box and compares it to the declared one, and it flags the two things that silently ruin a
set -- an untrimmed canvas, and members of one normalisation group whose ink does not agree.

    python3 verify_assets.py            # check
    python3 verify_assets.py --write    # recompute assets.json from the files
"""
import fnmatch
import json, pathlib, sys

from PIL import Image
import numpy as np

HERE = pathlib.Path(__file__).parent
META = HERE / "assets.json"
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


def attribution_problems():
    """Every file in the tree must be accounted for by name, not by assumption.

    This is the check that matters most, because the failure it catches is silent: a file arrives,
    gets used, ships, and nobody can say afterwards where it came from. An asset with no entry is a
    problem even when its licence would have been fine -- the record is the obligation.
    """
    att = json.loads((HERE / "attribution.json").read_text())
    out = []
    owned = att.get("projectOwned", [])
    for p in sorted(HERE.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(HERE).as_posix()
        if (rel.split("/")[0] in {"_masters"} or p.name in {".gitkeep", ".gitignore"}
                or p.suffix in {".json", ".py", ".md", ".html"}):
            continue
        if rel in att["files"]:
            state = att["files"][rel]["state"]
            if state != "present":
                out.append("%-52s on disk but recorded as '%s'. A held file in the tree is one "
                           "wholesale `git add` away from being committed; its directory carries "
                           "a .gitignore for that reason, but move it out once you are done."
                           % (rel, state))
            continue
        if any(fnmatch.fnmatch(rel, pat) for pat in owned):
            continue
        out.append("%-52s no entry in attribution.json and matches no projectOwned pattern"
                   % rel)

    for rel, a in sorted(att["files"].items()):
        if a["state"] == "present" and not (HERE / rel).exists():
            out.append("%-52s recorded as present, but the file is missing" % rel)
        lic = att["licences"][a["licence"]]
        if a["state"] == "present" and lic["attributionRequired"]:
            for field in ("title", "creator", "licence"):
                if not a.get(field):
                    out.append("%-52s needs %s: its licence requires attribution" % (rel, field))
    return out


def main(write=False):
    meta = json.loads(META.read_text())
    problems, held, groups = [], [], {}
    if not write:
        problems += attribution_problems()

    for name, a in sorted(meta["assets"].items()):
        p = HERE / a["src"]
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
        META.write_text(json.dumps(meta, indent=2) + "\n")
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
    sys.exit(main(write="--write" in sys.argv))
