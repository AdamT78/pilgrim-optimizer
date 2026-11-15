"""Guards for the merchant marker the v2 board stands on every duty's icon line.

WHERE IT IS PLACED IS NOT HERE. test_action_board_v2_grid.py runs the template's own arithmetic
over every slider setting and asks what the marker clears, how big it is and which side of the
frame it stands on. This file is about the PICTURE: that the board draws the file that was filed,
at the shape it was drawn in, once rather than eight times, and only when its provenance has been
written down.

WHY ANY OF IT NEEDS A GUARD. The marker is one small ochre figure on a dark board, repeated
eight times. Inlined at the wrong aspect it is a 7% stretch -- a slightly different drawing, not
a visible fault. Inlined per duty it is the same twenty kilobytes eight times, which costs a
board nobody can see the weight of. Filed without a record it is an asset in a shipped page that
nobody can say the rights to, which is the one failure this tree has a whole file to prevent.
"""
import importlib.util
import json
import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOL = ROOT / "ui" / "board_v2" / "action_board"
MARKERS = ROOT / "ui" / "board_v2" / "tokens" / "markers"
ATTRIB = ROOT / "ui" / "board_v2" / "attribution.json"
TMPL = TOOL / "action_board_v2.html.tmpl"


def _load(name: str, where: pathlib.Path = TOOL):
    spec = importlib.util.spec_from_file_location("_abv2m_" + name, where / (name + ".py"))
    if spec is None or spec.loader is None:                       # pragma: no cover
        pytest.skip("cannot import %s" % name)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    sys.path.insert(0, str(where))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(where))
    return mod


@pytest.fixture(scope="module")
def gen():
    return _load("generate_action_board_v2")


@pytest.fixture(scope="module")
def filed():
    found = sorted(f for f in MARKERS.glob("merchant_marker_v*") if f.is_file())
    if not found:
        pytest.skip("no merchant marker is filed under %s" % MARKERS)
    return found[-1]


def test_the_page_carries_the_shape_the_file_was_drawn_at(gen, filed):
    """The aspect travels with the picture, and it has to be the picture's own.

    THE MARKER IS PLACED BY WIDTH. What the line between the frame and the resource can spare
    decides how big it is, and the height comes from this number -- so a redrawn merchant at
    another aspect, or a number left behind when the drawing changed, stretches it on all eight
    duties at once. There is no second measurement anywhere downstream to catch that.
    """
    Image = pytest.importorskip("PIL.Image", reason="Pillow is not installed")
    merchant, _notes = gen.bundled_merchant()
    with Image.open(filed) as im:
        w, h = im.size
    assert merchant["src"], (
        "the generator inlines no merchant, though %s is on disk -- a cut with no attribution "
        "entry is left out on purpose, so check the record before the code" % filed.name)
    assert abs(merchant["h"] - h / w) < 0.001, (
        "the page is told the merchant is %.4f tall for its width and %s is %d x %d, which is "
        "%.4f" % (merchant["h"], filed.name, w, h, h / w))

    # AND THE BITMAP THAT WENT IN IS THAT SHAPE TOO. The number above and the picture below it
    # are set a line apart and the inliner RESIZES to whatever box it is handed -- it does not
    # fit, it stretches -- so a box that forgot the aspect would hand the page a squashed
    # drawing and tell it the right shape to draw it at. `object-fit:contain` then preserves the
    # squashing and centres it, which looks like a smaller merchant rather than a broken one.
    import base64
    import io

    head, body = merchant["src"].split(",", 1)
    assert head.startswith("data:image/"), "the merchant is not inlined as a data URI"
    with Image.open(io.BytesIO(base64.b64decode(body))) as inl:
        iw, ih = inl.size
    assert abs((ih / iw) - (h / w)) < 0.01, (
        "the inlined merchant is %d x %d, an aspect of %.4f, against the file's %.4f -- the "
        "picture was resized into a box of the wrong shape" % (iw, ih, ih / iw, h / w))


def test_the_marker_is_inlined_once_and_pointed_at_eight_times(gen):
    """One data URI on the page, not one per duty.

    EIGHT DUTIES AND ONE PICTURE. The acolyte masks are custom properties for this reason and
    the marker is one string for the same one: written into each tile's own markup it would be
    the same twenty kilobytes eight times over, and the board would look exactly right.
    """
    page, _notes = gen.build()
    uris = re.findall(r'"data:image/[a-z]+;base64,([A-Za-z0-9+/=]{200,})"', page)
    merchant, _ = gen.bundled_merchant()
    body = merchant["src"].split(",", 1)[1][:200]
    hits = sum(1 for u in uris if u.startswith(body[:120]))
    assert hits == 1, (
        "the merchant's picture appears %d times in the built page; it belongs in MERCHANT once "
        "and every tile points at that" % hits)


def test_the_marker_is_not_drawn_until_its_provenance_is_written_down(gen, filed, monkeypatch,
                                                                     tmp_path):
    """A picture with no attribution entry is left out and SAID, not guessed into the board.

    THE RULE EVERY OTHER PICTURE HERE IS HELD TO. The acolyte layers, the duty cut-outs and the
    resource icons are all gated on the record; a marker that slipped past would be an asset in
    a shipped page whose rights nobody can state, which is the single thing attribution.json
    exists to prevent. Checked by pointing the walk at a tree with the file in it and no record
    of it -- the one arrangement that cannot be produced by deleting something.
    """
    import shutil

    # UNDER A NAME NOTHING HAS A RECORD FOR, because the lookup is by file NAME and not by
    # path: copying the filed marker into another folder would still find its own entry, and the
    # test would pass against a generator that had no gate at all. A later version is also
    # exactly what this gate is for -- replacing the drawing is adding v02, and v02 has no
    # record until someone writes one.
    where = tmp_path / "markers"
    where.mkdir()
    shutil.copy(filed, where / "merchant_marker_v99.webp")
    monkeypatch.setattr(gen, "MERCHANT_DIR", where)
    merchant, notes = gen.bundled_merchant()
    assert merchant["src"] == "", (
        "a merchant with no entry in attribution.json was inlined anyway")
    assert any("attribution" in n for n in notes), (
        "the merchant was dropped without saying why: %s" % notes)


def test_what_is_filed_is_what_the_record_says_is_filed(filed):
    """The sha256 in the record is the file on disk, for both the marker and its master.

    A RECORD THAT HAS DRIFTED IS WORSE THAN NO RECORD. It answers the rights question with
    confidence about a file that is no longer there -- and the marker is one of two files that
    arrived from outside this tree, so it is exactly the kind that gets replaced in place.
    """
    import hashlib

    rec = json.loads(ATTRIB.read_text(encoding="utf-8"))["files"]
    want = {"tokens/markers/%s" % filed.name: filed,
            "tokens/markers/masters/merchant_marker_master_v01.png":
                MARKERS / "masters" / "merchant_marker_master_v01.png"}
    for rel, path in want.items():
        assert rel in rec, "%s is on disk with no record" % rel
        assert path.is_file(), "%s is recorded and is not on disk" % rel
        got = hashlib.sha256(path.read_bytes()).hexdigest()
        assert got == rec[rel]["sha256"], (
            "%s is recorded as %s and is %s" % (rel, rec[rel]["sha256"][:16], got[:16]))
        assert rec[rel]["licence"] != "provenance-pending", (
            "%s carries provenance-pending, which may not be inlined into the board" % rel)


def test_the_duty_line_s_icons_are_trimmed_to_what_is_drawn_in_them(gen):
    """Every icon on the line arrives as its own ink, with no canvas around it.

    THE DRAWINGS ARE NOT THE SIZE THEY LOOK. Each icon is generated on a square and the drawing
    inside it is whatever it is -- 28 x 97 for the wheat stalk, 100 x 77 for the stone block --
    and it is not centred in that square either: one carries 3% of empty canvas above it and 12%
    below. The board draws them in identical 50-pixel slots, so what the eye compares is the
    canvas, not the drawing: two marks the same size sit at different heights and look like two
    different sizes.

    SO THE CANVAS COMES OFF AT BUILD TIME and the files on disk are untouched. That keeps a
    layout decision out of fourteen assets and their records -- and it is checked here, on the
    pictures the page actually carries, rather than on the function that makes them.

    Falsify: inline the icons as they come, or crop them with getbbox(), which counts the halo
    of almost-nothing pixels a generated drawing carries and leaves the canvas back on.
    """
    Image = pytest.importorskip("PIL.Image", reason="Pillow is not installed")
    np = pytest.importorskip("numpy", reason="numpy is not installed")
    import base64
    import io

    page, _notes = gen.build()
    images = json.loads(re.search(r"^var IMAGES = (\{.*?\});\s*$", page, re.M).group(1))
    line = {k: v for k, v in images.items()
            if (k.startswith("seal:") or k.startswith("tithe:")) and isinstance(v, str)}
    assert len(line) > 10, "the page carries only %d icons on the duty line" % len(line)
    for key, uri in sorted(line.items()):
        im = Image.open(io.BytesIO(base64.b64decode(uri.split(",", 1)[1]))).convert("RGBA")
        a = np.asarray(im)[:, :, 3]
        ys, xs = np.where(a > 8)
        assert len(xs), "%s has nothing drawn in it" % key
        pad = (int(xs.min()), int(ys.min()),
               im.width - 1 - int(xs.max()), im.height - 1 - int(ys.max()))
        assert max(pad) <= 1, (
            "%s is %d x %d with %s pixels of empty canvas around its drawing (left, top, right, "
            "bottom). The board centres it in a 50-pixel slot, so that canvas becomes a margin "
            "nobody chose and every icon gets a different one." % ((key, im.width, im.height) + (pad,)))


def test_a_mark_cannot_grow_out_of_its_box(gen):
    """The drawing is bounded by the slot, and `height:100%` is not what bounds it.

    A MARK IS A GRID, and a grid item's percentage height against a row sized from that same
    item is cyclic: the browser drops it and uses `auto`. `height:100%` therefore meant "as tall
    as this drawing wants to be", and so did `max-height:100%` -- which is why swapping one for
    the other changed nothing. It never showed while every icon was a square, because 50 wide
    and auto-tall IS 50 tall. The moment the icons were trimmed to their own ink, a tall one
    grew out of its slot and over the frame's edge, on the two tiles that have the tallest
    drawings.

    SO THE PICTURE IS POSITIONED RATHER THAN SIZED: `position:absolute` with `inset:0` fills the
    mark's own padding box, which is a box that exists before the picture is measured.

    Falsify: put the image back in the grid's flow, or bound it with a percentage of any kind.
    """
    style = TMPL.read_text(encoding="utf-8")
    rule = re.search(r"\.seal\.filled img\{([^}]*)\}", style)
    assert rule, "there is no `.seal.filled img` rule left to bound the drawing"
    body = rule.group(1).replace("\n", " ")
    assert "position:absolute" in body and "inset:0" in body, (
        "the mark's drawing is sized inside the grid again, where a percentage height resolves "
        "to auto and a tall icon grows out of its slot: %s" % body)
    assert "object-fit:contain" in body, (
        "the drawing is no longer fitted inside its box: %s" % body)
