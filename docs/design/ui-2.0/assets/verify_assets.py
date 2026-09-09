"""Check every raster against the contract in ../hybrid-svg-png.md.

The contract exists because a transparent PNG's canvas bounds and its visual bounds are different
objects, and nothing in SVG or the DOM will tell you so. This makes that failure loud: it recomputes
each alpha box and compares it to the declared one, and it flags the two things that silently ruin a
set -- an untrimmed canvas, and members of one normalisation group whose ink does not agree.

    python3 verify_assets.py            # check
    python3 verify_assets.py --write    # recompute assets.json from the files
"""
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


def main(write=False):
    meta = json.loads(META.read_text())
    problems, held, groups = [], [], {}

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
