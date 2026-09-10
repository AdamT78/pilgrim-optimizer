"""Take a gothic frame apart: stonework, colour-neutral ornaments, and the drape.

    python3 ui/render/split_frame_layers.py --preview      # look before you leap
    python3 ui/render/split_frame_layers.py --write        # write the three layers
    python3 ui/render/split_frame_layers.py --check        # compare against what is committed

WHY

A frame arrives as one image with a coloured drape painted into it. A seat's colour has to be a
swapped layer, so the drape must come out -- and the tower and scroll must come out with it, because
they sit inside the drape's bounding box without being part of it, and a recolour that took them
along would turn the tower plum.

This is that operation, written down. It exists mainly for the NEXT frame: the layers currently in
ui/assets-gothic/frames/ were split once by hand before this script existed, and `--check` will tell
you plainly that this does not reproduce them pixel for pixel (see THE HONEST BIT below).

WHAT IT GUARANTEES

Not a particular mask -- masks are a judgement call about where a shadow stops being cloth. What it
guarantees is the property the rest of the pipeline depends on:

  * every ink pixel of the original lands in exactly one layer, never two and never none;
  * each layer carries the original's RGBA verbatim, not a blend or a re-composite;
  * stacking the three layers back up reproduces the input bit for bit, which is asserted on every
    run and is the whole reason a recolour can be trusted.

Antialiasing is why that matters and why the split is by hard alpha. Almost every pixel in this
artwork is partly transparent -- 552,508 of 555,031 in frame_base.png -- so any rule that tried to
divide a boundary pixel's colour between two layers would have to invent the division, and stacking
would no longer give you back what you started with. A boundary pixel therefore goes wholly to one
layer, and the seam is invisible because the layers are drawn touching.

HOW

  1. Seed the drape by colour: ink that is red enough and saturated enough. The frame's gold sits at
     hue 14-42 and its stonework is desaturated, so both fall outside.
  2. Close small gaps, keep only components big enough to be drapery rather than a red highlight
     somewhere else on the frame, then fill enclosed holes -- the deep folds are nearly black and
     have no red left in them, but they are surrounded by drape on every side.
  3. Whatever is left is the frame. Its largest connected component is the stonework; every smaller
     piece -- the tower, the scroll, and a scatter of near-black specks off the lower left -- is an
     ornament. Ornaments are colour-neutral, so they ride above every seat colour unchanged, and
     keeping the specks with them is what stops them vanishing when a drape is swapped.

THE HONEST BIT

Step 1's thresholds are a judgement, not a measurement, and the committed layers were made before
this script by a slightly different judgement. About 8% of the drape's pixels land differently --
almost all of them deep fold shadow, near-black in both directions, which is why the two look alike.
`--check` prints the disagreement rather than hiding it. Do not run `--write` against the current
frame casually: it would change cloth_red.png, and every seat colour is derived from that file.
"""
import argparse
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
UI = HERE.parent
FRAMES = UI / "assets-gothic" / "frames"

# Step 1's judgement, in one place so it can be argued with.
CLOTH_HUE_MAX = 11      # degrees either side of pure red, on PIL's 0-255 hue scale
CLOTH_SAT_MIN = 100     # below this the pixel is stonework, not dyed wool
CLOSE_RADIUS = 3        # bridge the hairline gaps the drape's own highlights cut into the seed
MIN_COMPONENT = 400     # px: smaller red islands are highlights elsewhere on the frame


def layers(image_path):
    """Split one frame into (stonework, ornaments, drape) as full-canvas RGBA arrays."""
    import numpy as np
    from PIL import Image
    from scipy import ndimage

    src = np.array(Image.open(image_path).convert("RGBA"))
    ink = src[:, :, 3] > 0
    hsv = np.array(Image.fromarray(src[:, :, :3], "RGB").convert("HSV")).astype(int)
    hue_from_red = np.minimum(hsv[:, :, 0], 256 - hsv[:, :, 0])
    structure = np.ones((3, 3), bool)

    seed = ink & (hue_from_red <= CLOTH_HUE_MAX) & (hsv[:, :, 1] >= CLOTH_SAT_MIN)
    seed = ndimage.binary_closing(seed, np.ones((CLOSE_RADIUS, CLOSE_RADIUS), bool))
    labelled, _ = ndimage.label(seed, structure)
    sizes = np.bincount(labelled.ravel())
    sizes[0] = 0
    seed = np.isin(labelled, np.where(sizes >= MIN_COMPONENT)[0])
    cloth = ndimage.binary_fill_holes(seed) & ink

    rest = ink & ~cloth
    labelled, _ = ndimage.label(rest, structure)
    sizes = np.bincount(labelled.ravel())
    sizes[0] = 0
    stonework = labelled == sizes.argmax()
    ornaments = rest & ~stonework

    masks = {"stonework": stonework, "ornaments": ornaments, "cloth": cloth}
    assert_partition(src, masks)
    return src, masks, {name: cut(src, m) for name, m in masks.items()}


def cut(src, mask):
    """The original's own pixels where the mask says so, fully transparent everywhere else."""
    import numpy as np
    out = np.zeros_like(src)
    out[mask] = src[mask]
    return out


def assert_partition(src, masks):
    """Every ink pixel in exactly one layer, and the stack reproduces the input exactly.

    This runs on every split rather than living in a test, because it is the property the recolour
    depends on and a violation is invisible: the layers would each look perfectly reasonable and the
    board would be subtly wrong in a way no one would think to look for.
    """
    import numpy as np
    ink = src[:, :, 3] > 0
    stack = list(masks.values())
    union = np.zeros_like(ink)
    for m in stack:
        if (union & m).any():
            raise SystemExit("BUG: layers overlap; the split is not a partition")
        union |= m
    if not (union == ink).all():
        raise SystemExit("BUG: %d ink pixels landed in no layer" % int((ink & ~union).sum()))
    rebuilt = np.zeros_like(src)
    for m in stack:
        rebuilt[m] = src[m]
    if not (rebuilt == src).all():
        raise SystemExit("BUG: the layers do not stack back into the original")


DESTINATIONS = {"stonework": "frame_base_nocloth.png",
                "ornaments": "frame_ornaments.png",
                "cloth": "cloth_red.png"}


def preview(src, masks, path):
    """The three layers in flat false colour, so a new frame's split can be judged by eye."""
    import numpy as np
    from PIL import Image
    tint = {"stonework": (90, 105, 125), "ornaments": (240, 200, 90), "cloth": (215, 70, 90)}
    out = np.zeros(src.shape[:2] + (3,), np.uint8)
    out[:] = (18, 20, 18)
    for name, mask in masks.items():
        out[mask] = tint[name]
    Image.fromarray(out).save(path)


def main():
    ap = argparse.ArgumentParser(description="Separate the drape and the ornaments from a frame.")
    ap.add_argument("--frame", default=str(FRAMES / "frame_base.png"))
    ap.add_argument("--out-dir", default=None, help="defaults to the frame's own directory")
    ap.add_argument("--write", action="store_true", help="write the three layers")
    ap.add_argument("--check", action="store_true",
                    help="compare against the layers already there, change nothing")
    ap.add_argument("--preview", action="store_true", help="write a false-colour map of the split")
    args = ap.parse_args()

    try:
        import numpy as np
        from PIL import Image
        import scipy  # noqa: F401
    except ImportError as exc:
        raise SystemExit("this needs pillow, numpy and scipy (%s):\n"
                         "    pip install pillow numpy scipy" % exc)

    frame = pathlib.Path(args.frame).expanduser().resolve()
    if not frame.is_file():
        raise SystemExit("no such frame: %s" % frame)
    out_dir = pathlib.Path(args.out_dir).expanduser().resolve() if args.out_dir else frame.parent

    src, masks, cuts = layers(frame)
    ink = int((src[:, :, 3] > 0).sum())
    print("%s: %d ink pixels" % (frame.name, ink))
    for name in ("stonework", "ornaments", "cloth"):
        print("  %-10s %7d px  (%4.1f%%)  -> %s"
              % (name, int(masks[name].sum()), 100 * masks[name].sum() / ink,
                 DESTINATIONS[name]))
    print("  the three layers stack back into the original exactly")

    if args.preview:
        path = out_dir / "_split_preview.png"
        preview(src, masks, path)
        print("\npreview written to %s" % path)

    problems = 0
    if args.check:
        print("\nagainst the layers already in %s:" % out_dir)
        for name, filename in DESTINATIONS.items():
            existing = out_dir / filename
            if not existing.is_file():
                print("  %-24s missing" % filename)
                problems += 1
                continue
            have = np.array(Image.open(existing).convert("RGBA"))[:, :, 3] > 0
            if have.shape != masks[name].shape:
                print("  %-24s different canvas" % filename)
                problems += 1
                continue
            differing = int((have ^ masks[name]).sum())
            share = 100 * differing / max(int(have.sum()), 1)
            print("  %-24s %s" % (filename, "identical" if not differing
                                  else "%d pixels differ (%.1f%% of that layer)"
                                       % (differing, share)))
            problems += differing > 0
        if problems:
            print("\nThis script does not reproduce the committed layers, and is not expected to:\n"
                  "they were split by hand before it existed. The committed files remain the\n"
                  "authority for this frame -- every seat colour is derived from cloth_red.png.\n"
                  "Use this on a NEW frame, or adopt it deliberately with --write and then re-run\n"
                  "ui/render/recolor_seat_layers.py to rebuild every derived colour.")

    if args.write:
        for name, filename in DESTINATIONS.items():
            Image.fromarray(cuts[name], "RGBA").save(out_dir / filename, "PNG", optimize=True)
            print("  wrote %s" % (out_dir / filename))
        print("\nEvery colour in ui/render/recolor_seat_layers.py is derived from cloth_red.png.\n"
              "Re-run it now, or the drapes on the boards will not match the frame you just split.")

    return 1 if problems and args.check else 0


if __name__ == "__main__":
    sys.exit(main())
