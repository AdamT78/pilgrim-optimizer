"""Will a replacement frame fit the template, or is it asking the template to move?

    python3 ui/render/check_frame_fit.py --candidate ~/Downloads/new_frame.png

WHY THIS IS THE FIRST THING TO RUN

The template's coordinates are calibrated to the holes in the current frame: the portrait ellipse,
the information panel, the four resource cards. A replacement frame that looks perfect but puts its
portrait opening thirty pixels to the left is not a new frame, it is a request to re-calibrate the
whole template -- and the standing rule for this project is that replacement artwork does not get to
move production coordinates, because every other asset placed against them would then be wrong.

So this compares a candidate's openings against the frame the template was built for, and says which
ones moved and by how much. It is a five-second check that decides whether the next hour is worth
spending.

WHAT AN OPENING IS

A hole: a fully transparent region that does not touch the canvas edge. The region that does touch
the edge is the outside of the frame, not an opening, and is ignored. Openings are matched between
the two frames by nearest centre rather than by index, so a candidate that happens to enumerate them
in a different order still reports sensibly.
"""
import argparse
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
UI = HERE.parent
REFERENCE = UI / "assets-gothic" / "frames" / "frame_base.png"

# How far an opening may drift before the template would have to be re-cut. Two pixels at the
# frame's native 1905 px is a quarter of a pixel once a board is drawn at 339 px in the game view,
# which is genuinely invisible; ten is not.
TOLERANCE = 2.0
MIN_OPENING = 2000      # px: smaller transparent islands are artwork, not openings


def openings(path):
    """Every enclosed transparent region, as (centre_x, centre_y, width, height, area)."""
    import numpy as np
    from PIL import Image
    from scipy import ndimage

    alpha = np.array(Image.open(path).convert("RGBA"))[:, :, 3]
    labelled, _ = ndimage.label(alpha == 0, np.ones((3, 3), bool))
    found = []
    for index in range(1, labelled.max() + 1):
        ys, xs = np.where(labelled == index)
        if len(xs) < MIN_OPENING:
            continue
        if xs.min() == 0 or ys.min() == 0 or xs.max() == alpha.shape[1] - 1 \
                or ys.max() == alpha.shape[0] - 1:
            continue                      # touches the edge: this is the outside
        found.append(((xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2,
                      xs.max() - xs.min() + 1, ys.max() - ys.min() + 1, len(xs)))
    return alpha.shape[1], alpha.shape[0], sorted(found, key=lambda o: -o[4])


def main():
    ap = argparse.ArgumentParser(description="Check a replacement frame against the template.")
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--reference", default=str(REFERENCE))
    ap.add_argument("--tolerance", type=float, default=TOLERANCE)
    args = ap.parse_args()

    try:
        import numpy  # noqa: F401
        from PIL import Image  # noqa: F401
        import scipy  # noqa: F401
    except ImportError as exc:
        raise SystemExit("this needs pillow, numpy and scipy (%s):\n"
                         "    pip install pillow numpy scipy" % exc)

    candidate = pathlib.Path(args.candidate).expanduser().resolve()
    reference = pathlib.Path(args.reference).expanduser().resolve()
    for p in (candidate, reference):
        if not p.is_file():
            raise SystemExit("no such file: %s" % p)

    rw, rh, ref = openings(reference)
    cw, ch, cand = openings(candidate)

    print("reference %s   %d x %d, %d openings" % (reference.name, rw, rh, len(ref)))
    print("candidate %s   %d x %d, %d openings\n" % (candidate.name, cw, ch, len(cand)))

    problems = 0
    if (cw, ch) != (rw, rh):
        print("CANVAS DIFFERS: %dx%d against %dx%d. Everything below is measured on a different\n"
              "grid, so treat it as advisory -- the canvas has to match first." % (cw, ch, rw, rh))
        problems += 1
    if len(cand) != len(ref):
        print("OPENING COUNT DIFFERS: %d against %d. An opening that is missing or extra is a\n"
              "different frame layout, not a restyle." % (len(cand), len(ref)))
        problems += 1

    unmatched = list(cand)
    print("%-12s %-22s %-22s %s" % ("opening", "reference centre", "candidate centre", "drift"))
    for cx, cy, w, h, _a in ref:
        if not unmatched:
            print("%-12s %-22s %-22s no candidate opening left to match"
                  % ("", "(%.1f, %.1f)" % (cx, cy), "-"))
            problems += 1
            continue
        best = min(unmatched, key=lambda o: (o[0] - cx) ** 2 + (o[1] - cy) ** 2)
        unmatched.remove(best)
        dx, dy = best[0] - cx, best[1] - cy
        dw, dh = best[2] - w, best[3] - h
        drift = max(abs(dx), abs(dy), abs(dw) / 2, abs(dh) / 2)
        bad = drift > args.tolerance
        problems += bad
        print("%-12s %-22s %-22s dx %+.1f dy %+.1f  size %+d x %+d   %s"
              % ("%dx%d" % (w, h), "(%.1f, %.1f)" % (cx, cy),
                 "(%.1f, %.1f)" % (best[0], best[1]), dx, dy, dw, dh,
                 "MOVED" if bad else "ok"))
    for extra in unmatched:
        print("%-12s %-22s %-22s extra opening in the candidate"
              % ("%dx%d" % (extra[2], extra[3]), "-", "(%.1f, %.1f)" % (extra[0], extra[1])))
        problems += 1

    if problems:
        print("\nThis frame does not drop in. Either the artwork moves to match the template, or\n"
              "somebody re-calibrates the template and every coordinate placed against it -- which\n"
              "is a deliberate project, not a side effect of accepting a nicer frame.")
        return 1
    print("\nEvery opening lands within %.1f px. This frame drops in; carry on with\n"
          "    python3 ui/render/split_frame_layers.py --frame %s --preview"
          % (args.tolerance, candidate))
    return 0


if __name__ == "__main__":
    sys.exit(main())
