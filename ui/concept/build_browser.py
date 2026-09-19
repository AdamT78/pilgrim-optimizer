"""The concept art for Pilgrim, in one page you can browse.

    python3 ui/concept/build_browser.py --open

Concept art arrives as loose files in a downloads folder and dies there: nobody opens a folder of
3 MB PNGs to compare four characters. This folder is where it stops being loose. Each image is
filed under the subject it belongs to and named for what it IS, and this script collects them into
one self-contained HTML page with a button per subject.

WHY THE NAMES ARE DERIVED AND NOT INVENTED

A file's path is `<subject>/<kind>.png`, and both halves come from the SUBJECTS table below --
the same table that orders the buttons and titles the cards. So a filename cannot disagree with
the page, and `duty_wheel_concept/labelled.png` says where it belongs without anybody looking it
up. `manifest.json` records what each file was called before, who made it, and its sha256, which
is what stops the rename destroying the only link back to the export it came from.

WHY IT IS DECLARED AND NOT GLOBBED

The table names every file the page expects. A glob would quietly produce a four-subject page when
a fifth exists, or a two-image subject when one file never got saved. Declared, a missing file is
reported by name on stdout and drawn as a gap, which is the difference between "there is no figure
for player 3" and "I forgot to look".

WHAT IS NOT IN THE REPOSITORY

`_reference/` is git-ignored. It holds third-party images kept for inspiration and never used in
the game -- committing one would put somebody else's work in every clone forever. An entry marked
`optional` is embedded when the file is there and drawn as a card linking to its source when it is
not, so the page is complete on this machine and honest on a fresh clone. Neither case is an
error, and the manifest keeps the URL either way.

TWO SOURCES THAT ARE NOT FILES HERE

The four portraits are production art and are read from `ui/assets-gothic/portraits/`, through the
same seat cast the board build uses (`gen_game_view.SEAT_PORTRAITS` over
`population_sets.SEAT_ORDER`), so a re-dealt cast moves this page with it. The duty wheel is
geometry, drawn as vector straight from its committed layout rather than from a saved picture.

The page embeds every image as a data: URI, downscaled to a long edge of MAX_EDGE, so it is one
portable file rather than a folder of links. The originals here are the archive; the page is not.
"""

from __future__ import annotations

import argparse
import base64
import html
import io
import json
import os
import pathlib
import sys
import urllib.parse
import webbrowser

try:
    from PIL import Image
except ModuleNotFoundError:                                          # pragma: no cover
    raise SystemExit("this needs Pillow: pip3 install --user Pillow")

HERE = pathlib.Path(__file__).resolve().parent          # ui/concept
ROOT = HERE.parents[1]                                  # the repository

MAX_EDGE = 1200                     # long edge of an embedded image, in pixels
QUALITY = 86                        # WebP quality; the sources stay untouched at full size

# The figures are drawn one at a time, so each arrives on its own plinth at its own scale. They
# are meant to be read as one set, and a set whose bases disagree reads as four unrelated
# pictures. They are levelled HERE rather than by editing the files: the sources stay as the
# generator made them, and the rule that makes them agree lives in one place where it can be
# seen and changed.
# Levelled per KIND, not across all of them: the display figures stand on stone plinths and the
# plastic sculpts on moulded pucks, so they are two sets that each need to agree internally and
# have no reason to agree with each other. A kind can only be levelled if it has alpha to measure.
LEVELLED_KINDS = ("figure", "sculpt_plastic")
FIGURE_CANVAS = (1086, 1448)        # the canvas these are drawn on
FIGURE_FLOOR = 16                   # base bottom to canvas bottom, shared within a kind

# Seat order and the seat-to-portrait cast, mirroring ui/render. Kept as literals so this script
# runs against a downloads folder with no repo present, and checked against the repo when there
# is one -- see resolve_portraits().
SEATS = ("sage", "pewter", "plum", "bone")
SEAT_PORTRAITS = {
    "sage": "leader_male_shaven",
    "pewter": "leader_female_hooded",
    "plum": "leader_male_hooded",
    "bone": "leader_female_blindfolded",
}
SEAT_INK = {"sage": "#4a7f24", "pewter": "#215482", "plum": "#7c227f", "bone": "#a59d92"}

# Each subject is one button. `kinds` is ordered, and the order is the order on the page. A kind
# is either a FILE -- {root, rel}, raster, re-encoded -- or a WHEEL -- {layout}, a committed
# geometry file drawn as vector and embedded as SVG rather than rasterised.
SUBJECTS = [
    {
        "id": "player_%d" % n,
        "label": "Player %d" % n,
        "tag": seat,
        "ink": SEAT_INK[seat],
        "kinds": [
            {"kind": "portrait", "title": "Portrait", "root": "assets",
             "rel": "ui/assets-gothic/portraits/%s.png" % SEAT_PORTRAITS[seat]},
            {"kind": "concept", "title": "Concept sheet"},
            {"kind": "figure", "title": "Figure"},
            {"kind": "sculpt_plastic", "title": "Sculpt, plastic"},
            {"kind": "mini_engraved", "title": "Mini, engraved"},
        ],
    }
    for n, seat in enumerate(SEATS, start=1)
]

# The duty wheel is not a picture anybody saved; it is geometry, and the committed layout is the
# only honest source for it. Drawn from the JSON as vector, so it is exact at any zoom and costs
# a few KB rather than a megapixel. Add a row here when there is another version to compare.
SUBJECTS.append({
    "id": "duty_wheel",
    "label": "Duty wheel",
    "tag": "geometry",
    "ink": "#e8c97a",
    "kinds": [
        {"kind": "wheel_1500", "title": "Aspect 1.500", "root": "assets",
         "layout": "tools/ui_debug/duty_wheel_v2_1500_layout.json"},
    ],
})

# The concept work the geometry came out of. Sits next to the built wheel on purpose: the whole
# point of having both on one page is being able to flip between what was drawn and what got
# built. Filenames here are whatever the generator happened to save, so the TITLE carries the
# meaning and the caption still shows the file so it can be found again on disk.
SUBJECTS.append({
    "id": "duty_wheel_concept",
    "label": "Duty wheel concept",
    "tag": "concept",
    "ink": "#a6763f",
    "kinds": [
        # Not in the repository. Present on the machine that found it, a link everywhere else.
        {"kind": "reference", "title": "Reference poster", "optional": True,
         "rel": "_reference/reference_poster.jpeg",
         "origin": {"text": "kr.pinterest.com",
                    "url": "https://kr.pinterest.com/pin/909867930987080612/"}},
        {"kind": "labelled", "title": "Nine faces, labelled"},
        {"kind": "unlabelled", "title": "Nine faces, unlabelled"},
        {"kind": "outlines", "title": "Outline study, 1.500"},
    ],
})

# Production art, borrowed and not copied: these live in ui/assets-gothic/ and the game uses them.
# `stack` because they are 2.6:1 -- three of them sharing a row would be 470 px wide each, which
# is not a size anyone can judge a background at.
SUBJECTS.append({
    "id": "panorama_backgrounds",
    "label": "Panorama backgrounds",
    "tag": "production art",
    "ink": "#6b6250",
    "stack": True,
    "kinds": [
        # The composed file is LOSSY webp -- it is the one the game ships. The halves it was
        # made from are lossless and twice the data, so they are the archival form and the card
        # links them too. Whoever wants a panorama to work from wants these, not the delivery copy.
        {"kind": "panorama_dark", "title": "Dark centre", "root": "assets",
         "rel": "ui/assets-gothic/ui/panorama.webp",
         "also": [("lossless left half", "ui/assets-gothic/ui/sources/panorama_left.webp"),
                  ("lossless right half", "ui/assets-gothic/ui/sources/panorama_right.webp")]},
        {"kind": "panorama_clearing", "title": "Clearing", "root": "assets",
         "rel": "ui/assets-gothic/ui/panorama_clearing.webp",
         "also": [("lossless left half",
                   "ui/assets-gothic/ui/sources/panorama_clearing_left.webp"),
                  ("lossless right half",
                   "ui/assets-gothic/ui/sources/panorama_clearing_right.webp")]},
        {"kind": "panorama_mist", "title": "Mist", "root": "assets",
         "rel": "ui/assets-gothic/ui/panorama_mist.webp",
         "also": [("lossless left half", "ui/assets-gothic/ui/sources/panorama_mist_left.webp"),
                  ("lossless right half",
                   "ui/assets-gothic/ui/sources/panorama_mist_right.webp")]},
    ],
})

# The nine duty actions, as SQUARES. The game view never shows them this way: gen_duty_grid cuts
# each one to its tile shape and the wheel shows a wedge of it, so a whole half of some of these
# pictures has never been on screen. That is exactly why they are here uncut -- this page is for
# looking at the art, and the tile shape is a separate decision applied later.
#
# Literals, like the seat cast above, so this runs without a renderer present; resolve_duty_tiles()
# hands authority to gen_duty_grid wherever there is one. The version matters: A was engraved and
# B grim dark, and `gen_duty_grid.VERSION` says which set the board actually draws.
DUTY_VERSION = "C"
DUTY_TILES = [("01", "allocation", "Allocation"), ("02", "clerical", "Clerical"),
              ("03", "construct", "Construct"), ("04", "build_roads", "Build Roads"),
              ("05", "city", "The City"), ("06", "ordination", "Ordination"),
              ("07", "produce", "Produce"), ("08", "taxation", "Taxation"),
              ("09", "give_alms", "Give Alms")]
SUBJECTS.append({
    "id": "duty_actions",
    "label": "Duty actions",
    "tag": "production art",
    "ink": "#c2a24a",
    "kinds": [{"kind": "duty_%s" % slug, "title": title, "root": "assets",
               "rel": "ui/assets-gothic/duty-tiles/%s/%s_%s_%s.webp"
                      % (DUTY_VERSION, nn, slug, DUTY_VERSION)}
              for nn, slug, title in DUTY_TILES],
})

# Components, not people: same shape of entry, a different subject. The table is a list of
# subjects rather than a list of players, which is why this costs one block and no plumbing.
SUBJECTS.append({
    "id": "tithe_resources",
    "label": "Tithe resources",
    "tag": "components",
    "ink": "#b08d57",
    "kinds": [
        {"kind": "counters", "title": "Counters"},
        {"kind": "board_frame", "title": "Board frame"},
        {"kind": "render_3d", "title": "3D render"},
    ],
})

SUBJECTS.append({
    "id": "acolytes_on_board",
    "label": "Generic acolytes on board",
    "tag": "in situ",
    "ink": "#6f8ba0",
    "kinds": [
        {"kind": "board_0", "title": "Board 0"},
        {"kind": "board_1", "title": "Board 1"},
        {"kind": "board_1_stacked", "title": "Board 1, stacked"},
    ],
})


def plinth(im: Image.Image) -> dict | None:
    """Where the miniature meets the ground: the widest row of its base.

    Off the alpha channel, not the colour: the base is the lowest thing in the picture and the
    only part guaranteed to be opaque all the way across. Measured at its WIDEST row rather than
    at the bottom edge, because the base is an ellipse seen from slightly above and its bottom
    edge is a good deal narrower than its true width.
    """
    mask = im.getchannel("A").point(lambda v: 255 if v > 200 else 0)
    box = mask.getbbox()
    if not box:
        return None
    _, top, _, below = box
    bottom = below - 1
    height = bottom - top + 1
    best = {"width": 0}
    for y in range(max(top, bottom - int(height * 0.25)), bottom + 1):
        row = mask.crop((0, y, mask.width, y + 1)).getbbox()
        if row and row[2] - row[0] > best["width"]:
            best = {"width": row[2] - row[0], "left": row[0], "right": row[2], "row": y}
    if not best["width"]:
        return None
    best["bottom"] = bottom
    return best


def level(im: Image.Image, target: float) -> Image.Image:
    """Scale a figure so its plinth is `target` wide, then stand it on the shared floor line.

    Placed by the PLINTH and not by the picture: the base is the thing being made to agree, and
    the figure above it is free to be whatever height it is. That is the trade -- one set of
    bases, four heights -- and it is the right way round, because a miniature is identified by
    the base it stands on.
    """
    here = plinth(im)
    if not here:
        return im
    k = target / here["width"]
    scaled = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)
    now = plinth(scaled) or here
    canvas = Image.new("RGBA", FIGURE_CANVAS, (0, 0, 0, 0))
    canvas.alpha_composite(scaled, (
        round(FIGURE_CANVAS[0] / 2 - (now["left"] + now["right"]) / 2),
        FIGURE_CANVAS[1] - FIGURE_FLOOR - 1 - now["bottom"]))
    return canvas


def figure_target(paths: list[pathlib.Path]) -> float | None:
    """The narrowest plinth in the set, so levelling only ever scales DOWN.

    Levelling up would mean enlarging one of the sources, which is the one operation here that
    invents detail that was never drawn.
    """
    widths = []
    for p in paths:
        if not p.is_file():
            continue
        with Image.open(p) as im:
            found = plinth(im.convert("RGBA"))
        if found:
            widths.append(found["width"])
    return min(widths) if widths else None


def encode(path: pathlib.Path,
           base: float | None = None) -> tuple[str, int, int, int, tuple[int, int]]:
    """One image as a WebP data URI, its embedded size, its cost, and the SOURCE's own size.

    The last of those is what the caption should quote. Everything on this page is downscaled to
    MAX_EDGE to keep the file portable, so the embedded dimensions describe the preview and not
    the archive -- quoting them tells a reader the file is smaller than it is.
    """
    im = Image.open(path)
    source = im.size
    keep = "RGBA" if (im.mode in ("RGBA", "LA") or "transparency" in im.info) else "RGB"
    im = im.convert(keep)
    if base:
        im = level(im, base)
    im.thumbnail((MAX_EDGE, MAX_EDGE), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=QUALITY, method=6)
    raw = buf.getvalue()
    return ("data:image/webp;base64," + base64.b64encode(raw).decode("ascii"),
            im.width, im.height, len(raw), source)


def wheel_svg(path: pathlib.Path) -> tuple[str, float, float, int, str]:
    """A committed duty-wheel layout as an SVG data URI, in its own colours.

    The faces carry Beziers, so this stays vector: rasterising geometry that is exact at any size
    to compare it against hand-drawn art would be throwing away the one advantage it has.
    """
    d = json.loads(path.read_text(encoding="utf-8"))
    pal = d.get("palette", {})
    ground = pal.get("ground", "#17130d")
    body = "".join(
        '<path fill="%s" d="%s"/>'
        % (pal.get("centre", "#e8dcc0") if c["position"] == "centre"
           else pal.get("face", "#efe3c8"), c["d"])
        for c in d["cells"])
    # width/height as well as viewBox: without an intrinsic size an <img> of an SVG falls back
    # to the browser's default 300x150-ish box, which is right in ratio but lies about the source.
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="%g" height="%g" viewBox="0 0 %g %g">'
           '<rect width="%g" height="%g" fill="%s"/>%s</svg>'
           % (d["box"], d["box_h"], d["box"], d["box_h"], d["box"], d["box_h"], ground, body))
    raw = svg.encode("utf-8")
    # The title already carries the aspect. Say where the drawing came from instead: this one is
    # not generated art like the rest of the page, and the footer's default should not claim it is.
    note = "%d faces, drawn from this layout" % len(d["cells"])
    return ("data:image/svg+xml;base64," + base64.b64encode(raw).decode("ascii"),
            d["box"], d["box_h"], len(raw), note)


def where(subject: dict, spec: dict) -> pathlib.Path:
    """The file this entry means.

    `root: "assets"` is a path from the repository root -- production art this page borrows and
    does not own. Everything else is concept art living here, and its path is DERIVED:
    `<subject id>/<kind>.png`. Deriving it is the point of the folder. A name that has to be
    written down twice is a name that eventually disagrees with itself.
    """
    if spec.get("root") == "assets":
        return ROOT / (spec.get("rel") or spec["layout"])
    return HERE / (spec.get("rel") or "%s/%s.png" % (subject["id"], spec["kind"]))


def source_link(path: pathlib.Path, out_dir: pathlib.Path) -> str:
    """A path from the finished page back to the file it is showing.

    Everything on this page is downscaled to MAX_EDGE and re-encoded, so saving an image out of
    the page gets the preview -- for a panorama, 1200 x 462 of a 2860 x 1100 original. The card
    therefore carries a link to the file itself.

    Relative, not absolute: the page is rebuilt by whoever runs the script, so a path from the
    output directory works for all of them, where a baked-in /Users/... would work for one. It
    does mean the link dies if the HTML is moved or mailed on its own, which is the same trade
    the embedded images already make in the other direction.
    """
    return urllib.parse.quote(os.path.relpath(path, out_dir).replace(os.sep, "/"))


def collect(out_dir: pathlib.Path) -> tuple[list, list, list]:
    """Every declared image: found, reported missing, or absent-but-expected. Nothing is globbed."""
    # One pass over the figures before anything is encoded: the target is the narrowest plinth in
    # the set, so it cannot be known from any single image.
    bases = {}
    for kind in LEVELLED_KINDS:
        found_target = figure_target([where(s, k) for s in SUBJECTS for k in s["kinds"]
                                      if k["kind"] == kind])
        if found_target:
            bases[kind] = found_target
            print("  levelling %-14s to the narrowest base in that set: %d px" % (kind, found_target))
    found, missing, absent = [], [], []
    for ch in SUBJECTS:
        panels = []
        for spec in ch["kinds"]:
            kind, title = spec["kind"], spec["title"]
            path = where(ch, spec)
            if not path.is_file():
                # An optional entry is git-ignored on purpose. Missing it is the NORMAL state on
                # any machine but the one that found it, so it is not a gap in the record -- the
                # card becomes a link to where the image came from.
                if spec.get("optional"):
                    absent.append("%s / %s" % (ch["label"], kind))
                    panels.append({"kind": kind, "title": title, "uri": None, "w": 4.0, "h": 3.0,
                                   "src": str(path), "name": path.name, "bytes": 0,
                                   "dims": "not in this checkout", "note": "",
                                   "origin": spec.get("origin"), "source": None})
                else:
                    missing.append("%s / %s: %s" % (ch["label"], kind, path))
                continue
            if "layout" in spec:
                uri, w, h, size, note = wheel_svg(path)
                dims = "%g \u00d7 %g units" % (w, h)
            else:
                lift = bases.get(spec["kind"])
                uri, w, h, size, source = encode(path, lift)
                note = "base levelled to %d px" % lift if lift else ""
                dims = "%d \u00d7 %d" % source
            panels.append({"kind": kind, "title": title, "uri": uri, "w": w, "h": h,
                           "src": str(path), "name": path.name, "bytes": size,
                           "dims": dims, "note": note, "origin": spec.get("origin"),
                           "source": source_link(path, out_dir),
                           # further files worth reaching for this one: a higher-quality form,
                           # the parts it was composed from. Silently dropped if absent.
                           "also": [(label, source_link(ROOT / rel, out_dir))
                                    for label, rel in spec.get("also", [])
                                    if (ROOT / rel).is_file()]})
            print("  %-16s %-12s %5g x %-6g %6.0f KB embedded  <- %s"
                  % (ch["id"], kind, w, h, size / 1024, path.name))
        found.append({**{k: ch[k] for k in ("id", "label", "tag", "ink")},
                      "stack": ch.get("stack", False), "panels": panels})
    return found, missing, absent


def caption(p: dict) -> str:
    """The caption for one card, with its source only when that source is not the page default.

    Provenance under EVERY image would be four repetitions of "ChatGPT" per row, which is noise
    that pushes the captions into a second line and unsettles a layout that currently works. The
    default is stated once in the footer and only the exceptions are marked here.
    """
    text = html.escape(" \u00b7 ".join(x for x in (p["name"], p["dims"], p["note"]) if x))
    if p.get("source"):
        # `download` is kept for the case where this is ever served over http, but on a file://
        # page Chromium ignores it and navigates instead -- so the label says open, not save.
        text += (' \u00b7 <a class="dl" href="%s" download>open the original</a>'
                 % html.escape(p["source"], quote=True))
    for label, href in p.get("also") or []:
        text += (' \u00b7 <a class="dl" href="%s" download>%s</a>'
                 % (html.escape(href, quote=True), html.escape(label)))
    src = p.get("origin")
    if src:
        text += (' \u00b7 source <a href="%s" target="_blank" rel="noopener noreferrer">%s</a>'
                 % (html.escape(src["url"], quote=True), html.escape(src["text"])))
    return text


def render(chars: list, missing: list) -> str:
    buttons, sheets = "", ""
    for i, ch in enumerate(chars):
        n = len(ch["panels"])
        buttons += (
            '<button class="tab" data-i="%d"%s><i style="background:%s"></i>%s'
            '<small>%s &#183; %d image%s</small></button>'
            % (i, " aria-current='true'" if i == 0 else "", ch["ink"],
               html.escape(ch["label"]), html.escape(ch["tag"]), n, "" if n == 1 else "s"))

        cards = ""
        for p in ch["panels"]:
            a = p["w"] / max(p["h"], 1)
            if p["uri"] is None:
                # No file, and that is the expected state off this machine. Say where it lives
                # rather than drawing an empty frame that looks like something went wrong.
                src = p.get("origin") or {}
                inner = ('<div class="shot away"><span>not in the repository'
                         '<em>%s</em></span></div>'
                         % html.escape(src.get("text", "kept out of git on purpose")))
                cards += ('<figure class="card gone" style="--a:%.4f;flex:%.4f 1 0">%s'
                          "<figcaption><b>%s</b><span>%s</span></figcaption></figure>"
                          % (a, a, inner, html.escape(p["title"]), caption(p)))
                continue
            # The overlay reads the card's own <img> rather than a data-full copy of the same
            # URI. Carrying it twice put every picture in the file twice -- 25.5 MB of a 25.3 MB
            # page was base64, 84 URIs for 43 images -- and no reader ever saw the difference.
            cards += (
                '<figure class="card" style="--a:%.4f;flex:%.4f 1 0">'
                '<div class="shot"><img src="%s" alt="%s" loading="lazy"></div>'
                "<figcaption><b>%s</b><span>%s</span></figcaption>"
                "</figure>"
            ) % (a, a, p["uri"],
                 html.escape("%s, %s" % (ch["label"], p["title"])),
                 html.escape(p["title"]), caption(p))
        if not cards:
            cards = '<p class="none">No images found for this subject.</p>'
        sheets += '<section class="sheet%s"%s>%s</section>' % (
            " stack" if ch.get("stack") else "",
            "" if len(sheets) == 0 else " hidden", cards)

    gaps = ""
    if missing:
        gaps = ('<div class="gaps"><b>%d declared file%s not found</b>%s</div>'
                % (len(missing), "" if len(missing) == 1 else "s",
                   "".join("<span>%s</span>" % html.escape(m) for m in missing)))

    # Written from the subjects that actually got built, so the key hint cannot promise 1-4 on a
    # page that now has five buttons.
    keys = "Key 1" if len(chars) == 1 else "Keys 1&#8211;%d" % min(9, len(chars))
    lede = ("Concept art and components, a button per subject. Anything already in the repository "
            "is shown from there rather than from a copy: the portraits are the production assets, "
            "and the duty wheel is drawn from its committed layout rather than from a saved "
            "picture. Click any image to see it large. %s switch subject, arrows step through "
            "them." % keys)
    if any(p["uri"] is None for c in chars for p in c["panels"]):
        lede += (" A greyed card is an image kept out of the repository on purpose; its caption "
                 "links to where it came from.")
    return (PAGE.replace("__BUTTONS__", buttons).replace("__SHEETS__", sheets)
                .replace("__GAPS__", gaps).replace("__LEDE__", lede))


PAGE = """<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pilgrim concept art</title>
<style>
 :root{color-scheme:dark}
 *{box-sizing:border-box}
 html,body{margin:0;background:#0b0907;color:#8b8071;
   font:14px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace}
 .wrap{max-width:1500px;margin:0 auto;padding:26px 20px 60px}
 h1{font-size:15px;font-weight:600;color:#e8c97a;margin:0 0 3px;letter-spacing:.02em}
 .lede{margin:0 0 22px;color:#6f6556;font-size:12.5px;max-width:80ch}
 nav{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 26px}
 .tab{display:flex;align-items:center;gap:9px;flex-wrap:wrap;cursor:pointer;
   background:#100d0a;color:#9a8f7c;border:1px solid #2a241c;border-radius:4px;
   padding:9px 14px;font:inherit;font-size:13px;transition:border-color .12s,color .12s}
 .tab:hover{border-color:#4a4031;color:#cbbb98}
 .tab[aria-current]{border-color:#8a7a52;color:#e8c97a;background:#171209}
 .tab i{width:9px;height:9px;border-radius:50%;flex:0 0 auto}
 .tab small{color:#5f5749;font-size:11px}
 .tab[aria-current] small{color:#8a7a52}
 /* A class with display: beats the UA sheet's [hidden]{display:none}, so hiding a sheet from
    JS silently does nothing without this rule. Every sheet was visible at once until it existed.
    !important, not just specificity: .sheet.stack{display:block} ties with .sheet[hidden] at
    (0,2,0) and wins on order, which put the stacked panorama sheet on every tab. Any future
    variant class would do the same, so this rule has to beat all of them rather than the one. */
 .sheet[hidden]{display:none!important}
 /* Equal HEIGHT, not equal width: the three are a square portrait, a wide turnaround sheet and a
    tall figure, and only a common height lets you compare the drawing across them. */
 /* Each card grows in proportion to its own aspect ratio from a zero basis, so the widths come
    out as w:h ratios of one another and every image ends up the SAME HEIGHT -- in one row, at
    whatever height the window affords. A fixed height instead would overflow the row and wrap. */
 .sheet{display:flex;flex-wrap:wrap;gap:22px;align-items:flex-start}
 /* A lone card would grow to the whole row and come out taller than the window, so cap its
    WIDTH at aspect x a height limit -- which caps the height without letterboxing the image.
    With three cards sharing a row the cap never binds. */
 .card{margin:0;min-width:0;max-width:calc(var(--a) * min(72vh, 720px))}
 .shot{width:100%;aspect-ratio:var(--a);background:#17130d;
   border:1px solid #221d16;border-radius:4px;overflow:hidden;cursor:zoom-in}
 .sheet.stack{display:block}
 .sheet.stack .card{max-width:min(100%,calc(var(--a) * min(52vh,520px)));margin:0 0 24px}
 .sheet.stack .card:last-child{margin-bottom:0}
 @media (max-width:900px){
   /* three in a row is unreadable on a phone; stack them and let each take the full width */
   .sheet{display:block}
   .card{margin-bottom:22px}
 }
 .shot img{display:block;width:100%;height:100%;object-fit:contain}
 .shot.away{display:flex;align-items:center;justify-content:center;cursor:default;
   border-style:dashed;border-color:#332c22;text-align:center}
 .shot.away span{color:#4f483c;font-size:12px;line-height:1.7}
 .shot.away em{display:block;font-style:normal;color:#6b6250;font-size:11px}
 figcaption{display:flex;flex-wrap:wrap;align-items:baseline;gap:3px 10px;margin-top:8px}
 figcaption b{color:#cbbb98;font-weight:600;font-size:13px}
 figcaption span{color:#5f5749;font-size:11.5px}
 figcaption a{color:#8a7a52}
 figcaption a.dl{color:#9a8a5e}
 figcaption a:hover{color:#cbbb98}
 .hint a{color:#5f5749}
 .hint code{color:#6b6250;font-size:11px}
 .none{color:#6f6556}
 .gaps{margin-top:34px;padding:14px 16px;border:1px solid #4a2b22;border-radius:4px;
   background:#180f0c;font-size:12px;color:#c08878}
 .gaps b{display:block;color:#e0705f;font-weight:600;margin-bottom:6px}
 .gaps span{display:block;color:#a8796b}
 #lb{position:fixed;inset:0;background:rgba(6,5,4,.95);display:none;align-items:center;
   justify-content:center;padding:26px;cursor:zoom-out;z-index:9}
 #lb.on{display:flex}
 #lb img{max-width:100%;max-height:100%;object-fit:contain}
 .hint{margin-top:30px;color:#4f483c;font-size:11.5px;max-width:80ch}
</style>
<div class="wrap">
<h1>Pilgrim concept art</h1>
<p class="lede">__LEDE__</p>
<nav>__BUTTONS__</nav>
__SHEETS__
__GAPS__
<p class="hint">Every image here was generated with ChatGPT unless its caption names a source,
and the duty wheel is drawn from its committed layout rather than generated at all.
<code>ui/concept/manifest.json</code> records what each file was called before it was filed here,
who made it and its checksum. Images are downscaled and re-encoded for this page; the files in
<code>ui/concept/</code> are the archive and nothing here replaces them.</p>
</div>
<div id="lb"><img alt=""></div>
<script>
(function(){
  var tabs = [].slice.call(document.querySelectorAll(".tab"));
  var sheets = [].slice.call(document.querySelectorAll(".sheet"));
  var lb = document.getElementById("lb"), lbImg = lb.firstElementChild;
  var at = 0;

  function show(i){
    at = (i + tabs.length) % tabs.length;
    tabs.forEach(function(t, j){
      if (j === at) t.setAttribute("aria-current", "true");
      else t.removeAttribute("aria-current");
    });
    sheets.forEach(function(s, j){ s.hidden = j !== at; });
  }
  tabs.forEach(function(t){
    t.addEventListener("click", function(){ show(+t.dataset.i); });
  });

  document.addEventListener("click", function(e){
    if (!e.target.closest) return;
    // A secondary click is a request for the browser's own menu, not for the overlay. A real
    // right-click never reaches here -- it only raises `contextmenu` -- but CONTROL-CLICK, which
    // is how a Mac has asked for that menu since before the two-button mouse, arrives as an
    // ordinary left click with ctrlKey set. Without this line the overlay opened on top of the
    // menu and "save image as" looked like it had been replaced by a zoom. Cmd and shift are
    // here for the same reason: they mean open-in-a-tab and open-in-a-window, never zoom.
    if (e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
    // the caption's source link lives INSIDE the card, so its click bubbles here and used to
    // open the overlay on top of the download. A link is never a request to zoom.
    if (e.target.closest("a")) return;
    var card = e.target.closest(".card");
    if (!card) return;
    // The card's own image IS the full-size copy, so there is nothing to look up. A card whose
    // art is not in the repository has no <img> at all and has nothing to enlarge.
    var img = card.querySelector("img");
    if (!img) return;
    lbImg.src = img.src;
    lb.classList.add("on");
  });
  lb.addEventListener("click", function(){ lb.classList.remove("on"); lbImg.src = ""; });

  addEventListener("keydown", function(e){
    if (e.key === "Escape"){ lb.classList.remove("on"); lbImg.src = ""; return; }
    if (lb.classList.contains("on")) return;
    if (e.key >= "1" && e.key <= String(Math.min(9, tabs.length))) show(+e.key - 1);
    else if (e.key === "ArrowRight") show(at + 1);
    else if (e.key === "ArrowLeft") show(at - 1);
  });
  show(0);
})();
</script>
</html>
"""


def resolve_portraits() -> None:
    """Take the seat cast from the board build rather than from the copy above.

    The literals are a fallback for a checkout without the renderer. Where there IS one it is the
    authority, and a page disagreeing with the board build about who player 3 is would be worse
    than no page at all.
    """
    render_dir = ROOT / "ui" / "render"
    if not (render_dir / "gen_game_view.py").is_file():
        print("  (no ui/render in this checkout; keeping the built-in cast)")
        return
    sys.path.insert(0, str(render_dir))
    try:
        import gen_game_view as gv
        import population_sets as pop
    except Exception as exc:                                        # noqa: BLE001
        print("  (could not read the seat cast from ui/render: %s)" % exc)
        return

    # getattr and not attribute access: an OLDER copy of gen_game_view has SEAT_INK but no
    # SEAT_PORTRAITS, and a stale checkout should leave this page on its own literals with a
    # word about it -- not crash, and not silently claim repo authority it did not get.
    cast = getattr(gv, "SEAT_PORTRAITS", None)
    order = getattr(pop, "SEAT_ORDER", None)
    if not cast:
        print("  (this gen_game_view has no SEAT_PORTRAITS; keeping the built-in cast)")
        return
    if order and tuple(order) != SEATS:
        print("  (repo seat order is %s, this page assumes %s)" % (tuple(order), SEATS))

    ink = getattr(gv, "SEAT_INK", None)
    if isinstance(ink, dict):
        for seat, colour in ink.items():
            if isinstance(colour, str) and colour.startswith("#"):
                SEAT_INK[seat] = colour

    for seat, rel in cast.items():
        stem = pathlib.Path(rel).stem
        if SEAT_PORTRAITS.get(seat) != stem:
            print("  (repo casts %s as %s, not %s -- following the repo)"
                  % (seat, stem, SEAT_PORTRAITS.get(seat)))
            SEAT_PORTRAITS[seat] = stem
    for n, seat in enumerate(SEATS, start=1):
        SUBJECTS[n - 1]["kinds"][0] = {
            "kind": "portrait", "title": "Portrait", "root": "assets",
            "rel": "ui/assets-gothic/portraits/%s.png" % SEAT_PORTRAITS[seat]}


def resolve_duty_tiles() -> None:
    """Take the duty tile set from gen_duty_grid rather than from the copy above.

    Same bargain as resolve_portraits: the literals let this run against a bare downloads folder,
    and where there IS a renderer it is the authority. It matters more here than for the cast,
    because WHICH VERSION is drawn is a live decision -- the folder holds three complete sets and
    `gen_duty_grid.VERSION` is the only thing that says which one the board uses. A page showing
    version C while the game had moved to D would be quietly, confidently wrong.

    find_tiles() is asked for the paths rather than the names being rebuilt here, so a tile that
    has not been drawn yet is simply absent from the page instead of appearing as a broken card.
    """
    render_dir = ROOT / "ui" / "render"
    if not (render_dir / "gen_duty_grid.py").is_file():
        print("  (no ui/render in this checkout; keeping the built-in duty tiles)")
        return
    sys.path.insert(0, str(render_dir))
    try:
        import gen_duty_grid as dg
    except Exception as exc:                                        # noqa: BLE001
        print("  (could not read the duty tiles from ui/render: %s)" % exc)
        return

    version = getattr(dg, "VERSION", None) or DUTY_VERSION
    if version != DUTY_VERSION:
        print("  (gen_duty_grid draws version %s, this page assumed %s -- following the repo)"
              % (version, DUTY_VERSION))
    try:
        tiles = dg.find_tiles(version=version)
    except Exception as exc:                                        # noqa: BLE001
        print("  (gen_duty_grid could not list its tiles: %s)" % exc)
        return
    if not tiles:
        print("  (no version %s tiles on disk; keeping the built-in list)" % version)
        return

    names = getattr(dg, "DUTY_NAMES", None) or []
    subject = next(s for s in SUBJECTS if s["id"] == "duty_actions")
    subject["kinds"] = [
        {"kind": "duty_%02d" % (i + 1),
         "title": names[i] if i < len(names) else "Tile %02d" % (i + 1),
         "root": "assets",
         "rel": os.path.relpath(tiles[i], ROOT).replace(os.sep, "/")}
        for i in sorted(tiles)]
    missing = len(names) - len(tiles) if names else 0
    print("  duty tiles: version %s, %d from gen_duty_grid%s"
          % (version, len(tiles), ", %d not drawn yet" % missing if missing > 0 else ""))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None,
                    help="page to write (default: generated/concept_browser.html beside this file)")
    ap.add_argument("--open", action="store_true", help="open the page when it is written")
    args = ap.parse_args()

    out = (pathlib.Path(args.out).expanduser() if args.out
           else HERE / "generated" / "concept_browser.html")

    resolve_portraits()
    resolve_duty_tiles()
    subjects, missing, absent = collect(out.parent)
    page = render(subjects, missing)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")

    shown = sum(1 for c in subjects for p in c["panels"] if p["uri"] is not None)
    print("wrote %s  (%.1f MB, %d images across %d subjects)"
          % (out, len(page) / 1e6, shown, len(subjects)))
    for a in absent:
        print("  not in this checkout, drawn as a link:  %s" % a)
    for m in missing:
        print("  MISSING  %s" % m)
    if args.open:
        webbrowser.open(out.resolve().as_uri())
    # An optional file being absent is not a failure; a declared one going missing is.
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
