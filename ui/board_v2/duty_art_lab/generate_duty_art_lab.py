#!/usr/bin/env python3
"""A viewfinder for cutting a wide duty master into the two action images.

    python3 duty_art_lab/generate_duty_art_lab.py --open

WHAT IT IS AND WHAT IT DELIBERATELY IS NOT. It shows you, at the size the board draws them,
exactly what the two action slots will contain for a given pair of rectangles -- and then it
hands you the rectangles. IT DOES NOT CUT THE FILES. A canvas re-encode will never match what
PIL produces byte for byte, and the moment the committed crops stop being reproducible from
their master by a recorded command, tests/layout_lab/test_duty_art_crop.py has nothing to
assert and attribution.json's `reproducibleBy` becomes a recipe nobody checked. Composing is
the part that needs an eye; cutting is the part that needs to be deterministic, and they are
better apart.

THE WINDOW'S SHAPE IS NOT TYPED HERE. It comes from the layout lab's own default_state(), the
way ui/board_v2/canvas_check does it, because the one thing this tool exists to get right is
the relationship between the crop and the box that will hold it.

That relationship was wrong, which is why this exists. The art slots are 375 x 184 -- ratio
2.03804 -- and the committed Clerical crops are 1120 x 560, ratio 2.00000. The slots draw with
`fit: cover`, so every crop is silently re-cropped by the browser: about 1.9% of its height,
some 10 source pixels off the top and 10 off the bottom, is never seen by anybody. The art was
being composed against a window that was not the window.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import re
import sys
import base64
import webbrowser

from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LAB = HERE.parent / "layout_lab" / "generate_layout_lab.py"
TMPL = HERE / "duty_art_lab.html.tmpl"
PROMPTS = HERE / "prompts"
REFERENCE = HERE / "reference" / "ground_plate_32deg.png"
SUBJECTS = HERE / "subjects.json"
OUT = HERE / "generated" / "duty_art_lab.html"

BUILD_VERSION = "0.4"


def lab():
    """The layout lab generator, imported by path the way the canvas check does it.

    LOUD ON FAILURE, and for the same reason: this page's whole claim is that the window it
    draws is the window the board draws. A fallback shape hard-coded here would keep the page
    working and make it a liar.
    """
    if not LAB.is_file():
        raise SystemExit("the layout lab generator is not at %s -- this page takes the action "
                         "slot's shape from it and has nothing to draw without it" % LAB)
    spec = importlib.util.spec_from_file_location("_duty_art_lab_lab", LAB)
    if spec is None or spec.loader is None:      # pragma: no cover - unreachable in practice
        raise SystemExit("could not load %s" % LAB)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_duty_art_lab_lab"] = mod
    spec.loader.exec_module(mod)
    return mod


def band_of(m) -> dict:
    """The two action slots, read off the state rather than off the module constants.

    The state is what the lab actually composes; the constants are only where it starts. If
    somebody moves or resizes a slot in the lab and re-runs, this follows.
    """
    S = m.default_state()
    L, R = S["display"]["artLeft"], S["display"]["artRight"]
    if (L["width"], L["height"]) != (R["width"], R["height"]):
        # Not a crash: two shapes would mean two crop ratios, and this page would have to ask
        # which slot you are cutting for. Worth knowing loudly if it ever happens.
        raise SystemExit(
            "the two action slots are no longer the same shape (%dx%d and %dx%d). This page "
            "assumes one crop shape serves both; it needs rethinking rather than patching."
            % (L["width"], L["height"], R["width"], R["height"]))
    gap = R["x"] - (L["x"] + L["width"])
    return {"card_w": L["width"], "card_h": L["height"], "gap": gap,
            "span": L["width"] * 2 + gap, "fit": L.get("fit", "cover")}


def prompts() -> list[dict]:
    """Every brief in prompts/, in filename order.

    MORE THAN ONE, AND KEPT RATHER THAN EDITED. A brief that produced a picture somebody liked
    is evidence, and evidence gets superseded rather than overwritten: the next idea goes in a
    new file beside this one so the two can be run against each other. The numeric prefix is
    ordering and is stripped from the title.

    The geometry paragraph is deliberately NOT in any of them -- it is computed in the page from
    the same band the cut uses, so a brief and the cut can never describe different pictures.
    """
    if not PROMPTS.is_dir():
        raise SystemExit("there are no briefs at %s" % PROMPTS)
    out = []
    for f in sorted(PROMPTS.glob("*.md")):
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
        raise SystemExit("prompts/ has no .md files in it")
    return out


def reference() -> dict:
    """The camera reference, and the size of the PICTURE in it rather than of the file.

    A transparent margin is still pixels, and measuring the file's full extent reports an
    elevation that is too generous -- 34.0 degrees against the 33.2 the plate actually subtends,
    because the margin is taller in proportion than the plate. The page prints an angle, so the
    number behind it has to be the picture's.
    """
    if not REFERENCE.is_file():
        raise SystemExit("the camera reference is not at %s -- the page offers it for download "
                         "and overlays it, and would be lying about both without it" % REFERENCE)
    im = Image.open(REFERENCE)
    box = im.convert("RGBA").getchannel("A").getbbox() if im.mode in ("RGBA", "LA") else None
    if box is None:
        box = (0, 0, im.width, im.height)
    return {"file": REFERENCE.name, "fileW": im.width, "fileH": im.height,
            "w": box[2] - box[0], "h": box[3] - box[1],
            "x": box[0], "y": box[1]}


def reference_src() -> str:
    """The reference as a data URI, INLINED rather than left beside the page.

    It was a sibling file, which is tidy in the repository and wrong everywhere else: the moment
    the page is copied, downloaded or opened on its own, the plate stops loading, the download
    link 404s and the overlay silently does nothing -- which is exactly how it reached somebody
    who then had no way to tell what was broken. 2.6 MB becomes 3.5 MB of base64 and the page
    works wherever it lands, which is the better trade for a tool that gets passed around.
    """
    return "data:image/png;base64," + base64.b64encode(REFERENCE.read_bytes()).decode("ascii")


# The aspects the viewfinder offers. 3:1 is ChatGPT's widest and, for this cut, the least
# wasteful ask -- the board's band is wider than anything a generator draws, so the shortfall is
# always vertical and a wider master loses less of it.
ASPECTS = (3.0, 2.8, 2.6, 2.4, 2.0)


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

    ONE OWNER. The Clerical pair was hard-coded into the viewfinder's template as a worked
    example and the art board needed the same words; a second copy is how the two pages come to
    offer different briefs for the same duty.
    """
    if not SUBJECTS.is_file():
        raise SystemExit("the subject descriptions are not at %s" % SUBJECTS)
    return json.loads(SUBJECTS.read_text(encoding="utf-8")).get("duties", {})


def build() -> str:
    m = lab()
    page = TMPL.read_text(encoding="utf-8")
    for token, value in (("__BAND__", json.dumps(band_of(m))),
                         ("__PROMPTS__", json.dumps(prompts())),
                         ("__GEOMETRY__", json.dumps(
                             {("%.1f" % a): geometry_text(band_of(m), a) for a in ASPECTS})),
                         ("__ASPECTS__", json.dumps([("%.1f" % a) for a in ASPECTS])),
                         ("__SUBJECTS__", json.dumps(subjects())),
                         ("__REF__", reference_src()),
                         ("__REFBOX__", json.dumps(reference())),
                         ("__BUILD__", BUILD_VERSION)):
        if token not in page:
            raise SystemExit("the template no longer has %s in it" % token)
        page = page.replace(token, value)
    left = [t for t in ("__BAND__", "__PROMPTS__", "__GEOMETRY__", "__ASPECTS__", "__SUBJECTS__", "__REF__", "__REFBOX__", "__BUILD__") if t in page]
    if left:
        raise SystemExit("tokens left unfilled: %s" % left)
    return page


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None, help="where to write the page (default: %s)" % OUT)
    ap.add_argument("--open", action="store_true", help="open the page when it is written")
    args = ap.parse_args(argv)

    page = build()
    out = pathlib.Path(args.out) if args.out else OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    # COPIED BESIDE THE PAGE, not inlined. It is 2.6 MB; as base64 that is 3.5 MB in every
    # build, to show one picture and offer it for download. generated/ is gitignored, so the
    # copy costs nothing and the page stays a few KB.
    (out.parent / REFERENCE.name).write_bytes(REFERENCE.read_bytes())

    s = band_of(lab())
    try:
        shown = out.relative_to(ROOT)
    except ValueError:
        shown = out
    print("wrote %s  (%d KB)" % (shown, len(page.encode("utf-8")) // 1024))
    print("  card %d x %d   gap %d   span %d x %d  (%.4f:1)   fit:%s"
          % (s["card_w"], s["card_h"], s["gap"], s["span"], s["card_h"],
             s["span"] / s["card_h"], s["fit"]))
    if args.open:
        webbrowser.open(out.resolve().as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
