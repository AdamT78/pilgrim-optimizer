"""The population rows: a count drawn as that many figures, and what stops them merging.

WHAT IS ACTUALLY AT RISK

Not that the rows appear -- that is obvious on any board. Two things are at risk and neither shows
up by looking:

    the geometry     Every number in a row is DERIVED from what the template already declares: the
                     panel from its own clip rect, the two boxes from where the divider sits inside
                     it, a figure's size from the very <image> the row replaces. Written out by hand
                     instead, it would look identical and then be wrong the first time the art moves.

    the opacity      The serf asset is semi-transparent through its whole body -- mean alpha 184 of
                     255, with 62% of pixels four pixels inside the silhouette still partial. Stacked
                     copies show through each other. The acolyte is 251 and does not. So one is
                     composited before it is drawn and the other is not, and the thing that decides
                     is the MEASUREMENT rather than the asset's name, or a redrawn acolyte starts
                     bleeding with nothing to say why.

These run in the ui lane, which installs pillow and numpy, AND in the lane that runs the whole
suite, which installs neither -- and the whole file needs both, because drawing a row decides
whether to composite the figure and deciding means measuring it. The fixture says so, so the file
skips there rather than failing there.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
UI = REPO / "ui"
ASSETS = UI / "assets-gothic"
SVG_NS = "http://www.w3.org/2000/svg"


def q(tag: str) -> str:
    return f"{{{SVG_NS}}}{tag}"


@pytest.fixture(scope="module")
def asm():
    # EVERY test here needs pixels, not just the two that measure alpha. Drawing a row decides
    # whether that figure has to be composited, and deciding means measuring, so building a board
    # at all now needs numpy and Pillow. The whole file skips where they are absent rather than
    # seven of nine failing in the lane that runs the entire suite -- which is exactly the red run
    # this repo has already paid for once.
    pytest.importorskip("numpy", reason="a population row measures the figure it draws")
    pytest.importorskip("PIL.Image", reason="a population row measures the figure it draws")
    path = UI / "render" / "gen_board_gothic.py"
    if not path.is_file() or not ASSETS.is_dir():
        pytest.skip("the gothic tree is not in this checkout")
    spec = importlib.util.spec_from_file_location("gothic_population", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build(asm, serfs, acolytes):
    config = copy.deepcopy(json.loads((ASSETS / "production_test_config.json").read_text()))
    config.setdefault("counts", {})["serf"] = serfs
    config["counts"]["acolyte"] = acolytes
    asm.apply_seat(config)
    layout = asm.read_json(ASSETS / "metadata" / "layout.json")
    root = ET.parse(ASSETS / "template" / "player_board_template.svg").getroot()
    asm.apply_config(root, config, layout, ASSETS)
    return root


def figures(root, kind):
    return [node for node in root.iter(q("use")) if node.get("data-population") == kind]


def span(asm, root, kind):
    """(left, right) of the drawn row, from the <use> boxes."""
    nodes = figures(root, kind)
    lefts = [float(n.get("x")) for n in nodes]
    width = float(nodes[0].get("width"))
    return min(lefts), max(lefts) + width


def test_a_count_is_that_many_figures(asm):
    """The picture is the count. Nothing on the board states it a second time.

    Counts run past what a game reaches on purpose: ordination can move all eight serfs into the
    abbey, so the acolyte box has to hold eleven while the serf box holds eight at the start.
    """
    for serfs, acolytes in ((8, 3), (4, 7), (0, 11), (1, 1), (8, 0)):
        root = build(asm, serfs, acolytes)
        assert len(figures(root, "serf")) == serfs
        assert len(figures(root, "acolyte")) == acolytes


def test_a_count_of_zero_draws_nothing(asm):
    root = build(asm, 0, 0)
    assert figures(root, "serf") == []
    assert figures(root, "acolyte") == []


def test_the_cube_and_the_numeral_are_gone_and_the_resources_keep_theirs(asm):
    """Both said what the row now says, and a numeral can disagree with the figures drawn."""
    root = build(asm, 8, 3)
    roles = [n.get("data-asset-role") for n in root.iter(q("image"))]
    assert "serf_cube" not in roles and "acolyte_cube" not in roles
    ids = [n.get("id") for n in root.iter(q("text"))]
    assert "count-serf" not in ids and "count-acolyte" not in ids
    for name in asm.RESOURCE_NAMES:
        assert f"count-{name}" in ids, f"the {name} numeral went with them"


def test_every_row_is_centred_in_its_own_box(asm):
    """A box that empties must not leave its figures hanging off one side."""
    for count in range(1, 12):
        root = build(asm, min(count, 8), count)
        boxes = asm.population_boxes(root)
        for kind, n in (("serf", min(count, 8)), ("acolyte", count)):
            lo, hi = boxes[kind]
            left, right = span(asm, root, kind)
            assert abs((left + right) / 2 - (lo + hi) / 2) < 0.6, (
                "%s row of %d is centred at %.2f, its box at %.2f"
                % (kind, n, (left + right) / 2, (lo + hi) / 2))


def test_a_row_never_leaves_its_box_and_never_spreads_wider_than_the_step(asm):
    """The step is capped at POPULATION_STEP and tightened only as far as the box demands.

    Both halves matter. Without the cap a nearly empty box would fling its figures apart; without
    the tightening, eleven acolytes would run off the panel and into the frame.
    """
    for count in range(1, 12):
        root = build(asm, min(count, 8), count)
        boxes = asm.population_boxes(root)
        for kind in ("serf", "acolyte"):
            nodes = figures(root, kind)
            if len(nodes) < 2:
                continue
            lo, hi = boxes[kind]
            left, right = span(asm, root, kind)
            assert left >= lo + asm.POPULATION_PAD - 0.6 and right <= hi - asm.POPULATION_PAD + 0.6, (
                "%s row of %d runs %.1f..%.1f outside its box %.1f..%.1f"
                % (kind, len(nodes), left, right, lo, hi))
            xs = sorted(float(n.get("x")) for n in nodes)
            width = float(nodes[0].get("width"))
            step = (xs[1] - xs[0]) / width
            assert step <= asm.POPULATION_STEP + 1e-6, (
                "%s row of %d steps %.4f, wider than POPULATION_STEP" % (kind, len(nodes), step))


def test_the_geometry_comes_from_the_template_not_from_constants(asm):
    """Move what the template declares and the row must move with it.

    This is the guard against the coordinates being written out by hand: a row that ignores the
    template would sit in exactly the same place after the divider moves, and look perfectly fine.
    """
    root = build(asm, 8, 3)
    before = asm.population_boxes(root)
    for image in root.iter(q("image")):
        if image.get("data-asset-role") == "population_divider":
            image.set("x", str(float(image.get("x")) + 120))
            break
    after = asm.population_boxes(root)
    assert after["serf"][1] == before["serf"][1] + 120, "the serf box ignored the divider"
    assert after["acolyte"][0] == before["acolyte"][0] + 120, "the acolyte box ignored the divider"


def test_one_symbol_per_kind_however_many_figures(asm):
    """Eleven acolytes must cost one copy of the artwork, not eleven."""
    root = build(asm, 8, 11)
    for kind in ("serf", "acolyte"):
        symbols = [s for s in root.iter(q("symbol")) if s.get("id") == f"population-{kind}"]
        assert len(symbols) == 1, f"{len(symbols)} symbols for {kind}"
    asm.assert_no_duplicated_payloads(root)


def test_which_figures_are_composited_is_decided_by_measuring_them(asm):
    """Not by name. A redrawn acolyte that arrives semi-transparent must be treated too."""
    pytest.importorskip("numpy")
    pytest.importorskip("PIL.Image")
    serf = ASSETS / "population" / "serf_gothic.png"
    acolyte = ASSETS / "population" / "acolyte_gothic.png"
    if not serf.is_file() or not acolyte.is_file():
        pytest.skip("the population assets are not in this checkout")
    low, high = asm.mean_ink_alpha(serf), asm.mean_ink_alpha(acolyte)
    assert low < asm.OPAQUE_ALPHA_FLOOR <= high, (
        "the serf measures %.1f and the acolyte %.1f against a floor of %s; the floor no longer "
        "separates a figure that needs compositing from one that does not"
        % (low, high, asm.OPAQUE_ALPHA_FLOOR))


def test_compositing_changes_how_a_figure_stacks_and_not_how_it_looks(asm):
    """On the panel, one composited figure is the figure. Stacked, it occludes instead of blending.

    Both halves are the point. Hardening the alpha WITHOUT compositing was tried and rejected: the
    mid-alpha pixels carry the drawing's lightness, so forcing them opaque turns the serf into a
    heavy dark blob. This asserts the thing that made compositing the right answer.
    """
    np = pytest.importorskip("numpy")
    Image = pytest.importorskip("PIL.Image")
    import io

    source = ASSETS / "population" / "serf_gothic.png"
    if not source.is_file():
        pytest.skip("the serf asset is not in this checkout")
    panel = "#ead8b4"
    rgb = tuple(int(panel[1:][i:i + 2], 16) for i in (0, 2, 4))
    made = Image.open(io.BytesIO(asm.opaque_figure(source, panel))).convert("RGBA")
    original = Image.open(source).convert("RGBA")

    ground = Image.new("RGBA", original.size, rgb + (255,))
    a = np.asarray(Image.alpha_composite(ground.copy(), original)).astype(int)[..., :3]
    b = np.asarray(Image.alpha_composite(ground.copy(), made)).astype(int)[..., :3]
    worst = int(np.abs(a - b).max())
    assert worst <= 16, "compositing changed how one figure looks on the panel, by %d" % worst

    alpha = np.asarray(made).astype(int)[..., 3]
    inked = alpha[alpha > 24]
    assert inked.mean() >= asm.OPAQUE_ALPHA_FLOOR, (
        "the composited figure is still only %.0f/255 opaque, so stacked copies will keep showing "
        "through each other" % inked.mean())


def _load(name):
    path = UI / "render" / f"{name}.py"
    if not path.is_file():
        pytest.skip(f"{name}.py is not in this checkout")
    spec = importlib.util.spec_from_file_location(f"_pop_{name}", path)
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.path.insert(0, str(UI / "render"))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(UI / "render"))
    return module


def test_every_assembler_of_this_template_draws_the_rows(asm):
    """Four things build this template, and the rows have to appear in all of them.

    THIS IS THE GUARD FOR THE MISTAKE THAT WAS ACTUALLY MADE. The rows were first hung off
    `build_one`, which only the production assembler calls, so gothic-board.html grew them and the
    game view's column and the layer picker quietly went on drawing the cube and the numeral. Every
    check passed. The docstring of the module that built the game view's boards still said they were
    built "exactly as the production assembler would write it", which had silently stopped being
    true, and it was found by someone opening the game view and noticing the old design.

    The structural fix is that `apply_config` takes `assets_dir` and draws the rows itself, so a
    caller cannot skip them without a TypeError. This is the guard that says so out loud, and it
    fails if a fifth assembler ever appears that goes around it.
    """
    config_path = ASSETS / "production_test_config.json"

    view = _load("gen_game_view")
    root = view.build_board(asm, ASSETS, config_path, "sage", "lit")
    assert [n for n in root.iter(q("use")) if n.get("data-population")], (
        "gen_game_view builds the game view's boards and drew no population figures")

    picker = _load("gen_picker_2")
    root, _config = picker.build_board(asm, ASSETS, config_path, "sage")
    assert [n for n in root.iter(q("use")) if n.get("data-population")], (
        "gen_picker_2 builds the layer picker and drew no population figures")


# ---------------------------------------------------------------------------------------------
# THE CARD-ROW PRESETS. Where a row sits along its box, as a table rather than as three literals,
# so the choice can be compared in the picker instead of argued about. What is at risk is the
# usual failure of a read-only dial: that the option it OPENS on is not the one the board draws,
# which makes every comparison beside it a comparison against the wrong picture.

BOARD_KEYS = {"label", "step", "pad", "align"}


def pop_sets():
    import sys
    sys.path.insert(0, str(UI / "render"))
    import population_sets
    return population_sets


def test_every_card_row_preset_names_every_metric_a_row_reads(asm):
    pop = pop_sets()
    for name, preset in pop.BOARD_SETS.items():
        assert set(preset) == BOARD_KEYS, (
            "card set %r has %s; a row reads exactly %s"
            % (name, sorted(preset), sorted(BOARD_KEYS)))
        assert preset["align"] in ("left", "centre", "right"), (
            "card set %r aligns %r, which population_row has no branch for"
            % (name, preset["align"]))


def test_the_controls_open_on_the_row_the_board_actually_drew(asm):
    """The guard the two deleted experiment scripts most needed and did not have.

    GOES THROUGH THE PICKER'S OWN ANSWER. Written the obvious way -- recompute `population_row`
    with BOARD_DEFAULT and compare -- it was DEAD: the board is built through the same default, so
    changing the default moved the board and the expectation together and the assertion held for
    every value. That is the same tautology `abs(got - ARROW_OUTSET)` was, one file over.

    It has since earned its place twice. It caught the geometry being computed for the default
    FIGURE while the board drew another one -- the spread control would have snapped the acolytes
    back to the photograph's width -- and it is why the two controls now share one table keyed by
    both, instead of two that overwrite each other.
    """
    import importlib.util as _il
    pop = pop_sets()
    spec = _il.spec_from_file_location("picker2", UI / "render" / "gen_picker_2.py")
    picker = _il.module_from_spec(spec)
    spec.loader.exec_module(picker)

    root = build(asm, 6, 3)
    template = ET.parse(ASSETS / "template" / "player_board_template.svg").getroot()
    drawn = {k: [{"x": round(float(n.get("x")), 3), "width": round(float(n.get("width")), 3)}
                 for n in figures(root, k)] for k in ("serf", "acolyte")}

    geo = picker.population_geo(asm, root, template)
    opening = geo["%s/%s" % (pop.CARD, pop.BOARD_DEFAULT)]
    assert opening == drawn, (
        "the controls open on %s/%s, which puts the figures at %s while the board draws them at %s"
        % (pop.CARD, pop.BOARD_DEFAULT, opening, drawn))

    rows = picker.population_options(asm, root, template)
    on = [e for e in rows if e["on"]]
    assert len(on) == 1 and on[0]["value"] == pop.BOARD_DEFAULT, (
        "the spread control preselects %s" % [e["value"] for e in on])


def test_the_acolyte_control_carries_a_symbol_of_its_own_for_every_option(asm):
    """Every option must point at a symbol IT put in the defs.

    `population-acolyte` is whatever the board was built with, so an option that reuses that id
    swaps the href and the width and changes nothing visible. That is exactly what the image
    option did first time out: the assertion on the href passed and the picture did not move, and
    only a screenshot said so.
    """
    import importlib.util as _il
    import copy as _copy
    import json as _json
    pop = pop_sets()
    spec = _il.spec_from_file_location("picker2b", UI / "render" / "gen_picker_2.py")
    picker = _il.module_from_spec(spec)
    spec.loader.exec_module(picker)

    config = _copy.deepcopy(_json.loads((ASSETS / "production_test_config.json").read_text()))
    config.setdefault("counts", {})["acolyte"] = 3
    asm.apply_seat(config)
    root = build(asm, 6, 3)
    template = ET.parse(ASSETS / "template" / "player_board_template.svg").getroot()
    defs = root.find(q("defs"))
    entries = picker.acolyte_options(asm, root, template, defs, config, ASSETS)
    assert entries and len(entries) == len(pop.SETS)

    ids = {e["value"]: set(e["ids"].values()) for e in entries}
    for name, got in ids.items():
        assert "population-acolyte" not in got, (
            "the %r option points at the id the board was built with, so choosing it can only "
            "look like a change on a board built the other way" % name)
        for sid in got:
            assert defs.find("*[@id='%s']" % sid) is not None, (
                "the %r option points at #%s, which nothing defines" % (name, sid))
    assert not set.intersection(*ids.values()), (
        "two figure options share a symbol: %s" % ids)


def test_the_presets_are_not_all_the_same_row(asm):
    """A dial whose settings all draw the same picture is a dial that does nothing.

    Checked at a count the box is NOT full at. At eight serfs the row fills its box, the existing
    tightening clamps every step to the same value and all three alignments coincide -- which is
    correct, documented behaviour and also exactly the count at which this guard would pass on a
    control that had been broken.
    """
    pop = pop_sets()
    template = ET.parse(ASSETS / "template" / "player_board_template.svg").getroot()
    layouts = {name: tuple(round(x, 3) for x, _y, _w, _h in
                           asm.population_row(template, "acolyte", 3, pop_set=name))
               for name in pop.BOARD_SETS}
    assert len(set(layouts.values())) == len(layouts), (
        "two card presets draw the same row: %s" % layouts)

    full = {name: tuple(round(x, 3) for x, _y, _w, _h in
                        asm.population_row(template, "serf", 8, pop_set=name))
            for name in pop.BOARD_SETS}
    assert len(set(full.values())) < len(full), (
        "a full row is supposed to clamp to the same layout under most presets; if it no longer "
        "does, the tightening in population_step has changed and the note above is stale")


def test_four_seats_keep_four_marks_when_the_game_view_merges_them(asm):
    """The one that would have shipped looking perfect.

    `gen_game_view.merge_defs` collapses symbols sharing a `data-source` and a
    `preserveAspectRatio`, which is what stops four boards carrying four copies of the same
    photograph. The drawn mark is not a file, so it has to state a `data-source` of its own -- and
    if that string did not carry the SEAT, all four would collapse into one and every board would
    wear the first seat's colour.

    ONE BOARD LOOKS RIGHT WHILE THIS IS WRONG, which is why it is worth a test rather than a look.
    """
    import importlib.util as _il
    import copy as _copy
    import json as _json
    pop = pop_sets()
    if pop.card(pop.CARD)["kind"] == "image":
        pytest.skip("the card draws a placed image, so there is no per-seat symbol to collapse")

    spec = _il.spec_from_file_location("gameview", UI / "render" / "gen_game_view.py")
    gv = _il.module_from_spec(spec)
    spec.loader.exec_module(gv)

    roots = []
    for seat in asm.SEAT_COLORS:
        config = _copy.deepcopy(_json.loads((ASSETS / "production_test_config.json").read_text()))
        config.setdefault("counts", {})["acolyte"] = 2
        config["seat"] = seat
        asm.apply_seat(config)
        root = ET.parse(ASSETS / "template" / "player_board_template.svg").getroot()
        asm.apply_config(root, config, asm.read_json(ASSETS / "metadata" / "layout.json"), ASSETS)
        asm.embed_assets_once(root, ASSETS)
        roots.append(root)

    shared, _n, _saved = gv.merge_defs(asm, roots)
    marks = [e for e in shared.iter(q("symbol"))
             if str(e.get("data-source", "")).startswith("hood:")]
    assert len(marks) == len(asm.SEAT_COLORS), (
        "four seats merged to %d hooded symbols (%s); every board after the first would wear "
        "another seat's colour"
        % (len(marks), [e.get("data-source") for e in marks]))
    fills = {m.find(q("path")).get("fill") for m in marks}
    assert len(fills) == len(asm.SEAT_COLORS), "the four marks share %d fills: %s" % (len(fills), fills)
    assert fills == {pop.SEAT_SWATCH[s] for s in asm.SEAT_COLORS}, (
        "the card's marks are not the seat colours the wheel uses: %s" % sorted(fills))


def test_a_drawn_mark_is_sized_to_its_own_shape_and_not_to_the_photographs_box(asm):
    """Checked against the TEMPLATE's numbers, which is the only independent thing here.

    Asserting that the row and the picker agree about the width cannot fail -- both go through
    `population_figure_frame`, so breaking it moves the board and the expectation together. The
    template's `<image>` is the outside fact: it is sized for the photograph, and a mark that
    simply inherited it would be fitted inside a box wider than itself, leaving the row spaced for
    a figure it is not drawing.
    """
    pop = pop_sets()
    template = ET.parse(ASSETS / "template" / "player_board_template.svg").getroot()
    image = [im for im in template.iter(q("image"))
             if im.get("data-asset-role") == "acolyte"][0]
    t_w, t_h = float(image.get("width")), float(image.get("height"))

    for name, spec in ((n, pop.card(n)) for n in pop.SETS):
        _y, w, h = asm.population_figure_frame(template, "acolyte", name)
        if spec["kind"] == "image":
            assert (w, h) == (t_w, t_h), (
                "%r is a placed image and should take the template's box whole" % name)
        else:
            inset = spec.get("inset", 0.0)
            assert abs(h - t_h * (1 - 2 * inset)) < 1e-9, (
                "%r is drawn %.3f tall; the frame less its margin is %.3f"
                % (name, h, t_h * (1 - 2 * inset)))
            assert abs(w - h * spec["aspect"]) < 1e-9, (
                "%r is drawn at %.3f wide; its own aspect over its height is %.3f"
                % (name, w, h * spec["aspect"]))
            assert abs(w - t_w) > 1.0, (
                "%r is drawn at the photograph's width (%.1f), so the shape is being fitted "
                "inside a box wider than itself" % (name, t_w))


def test_the_symbols_viewbox_holds_the_whole_mark_including_its_outline(asm):
    """A <symbol> clips to its viewport and a stroke is centred on its path.

    Set to the path's bare bounds, the viewBox cuts half the outline off on EVERY edge: the dome
    comes out flat, the shoulders square. It shipped that way and read as a figure too big for its
    box rather than as one being trimmed, which is why it was reported as a sizing problem.

    Checked as arithmetic on the shape rather than on the rendered pixels: the box must contain
    every point of the outline grown by half the stroke.
    """
    pop = pop_sets()
    x0, y0, w, h = pop.hood_box()
    half = pop.HOOD_STROKE / 2
    xs = [p[0] for p in pop.HOOD_SHAPE]
    ys = [p[1] for p in pop.HOOD_SHAPE]
    assert x0 <= min(xs) - half + 1e-12 and x0 + w >= max(xs) + half - 1e-12, (
        "the box %s clips the outline sideways (path spans %.4f..%.4f, stroke reaches %.4f)"
        % ((x0, w), min(xs), max(xs), max(xs) + half))
    assert y0 <= min(ys) - half + 1e-12 and y0 + h >= max(ys) + half - 1e-12, (
        "the box %s clips the outline vertically (path spans %.4f..%.4f, stroke reaches %.4f)"
        % ((y0, h), min(ys), max(ys), max(ys) + half))
    assert abs(pop.card("hood")["aspect"] - w / h) < 1e-12, (
        "the card set is sized to a different box than the symbol carries, so the <use> and the "
        "symbol disagree and the mark is letterboxed or cropped")


def test_the_marks_margin_is_the_one_the_photograph_leaves(asm):
    """`inset` is a MEASUREMENT of the asset it replaces, so it must still be true of it.

    The gothic PNGs are not alpha-tight: they carry transparent rows at each end, so the
    photograph never reaches the edges of the box the template gives it. A drawn mark is tight and
    does, which put it flush against a band only 174 units deep. This re-measures rather than
    trusting the number, because the asset can be recut and nothing else would say so.
    """
    numpy = pytest.importorskip("numpy")
    Image = pytest.importorskip("PIL.Image")
    pop = pop_sets()
    inset = pop.card("hood").get("inset")
    assert inset, "the drawn mark leaves no margin; see the note beside `inset`"

    alpha = numpy.asarray(Image.open(ASSETS / "population" / "acolyte_gothic.png")
                          .convert("RGBA"))[..., 3]
    rows = numpy.nonzero((alpha > 8).any(axis=1))[0]
    top = rows.min() / alpha.shape[0]
    bottom = 1 - (rows.max() + 1) / alpha.shape[0]
    assert abs(top - inset) < 0.002 and abs(bottom - inset) < 0.002, (
        "the acolyte asset now leaves %.4f above and %.4f below, but the drawn mark is inset by "
        "%.4f -- the two figures would no longer sit on the same line" % (top, bottom, inset))

    template = ET.parse(ASSETS / "template" / "player_board_template.svg").getroot()
    image = [im for im in template.iter(q("image"))
             if im.get("data-asset-role") == "acolyte"][0]
    t_y, t_h = float(image.get("y")), float(image.get("height"))
    y, _w, h = asm.population_figure_frame(template, "acolyte", "hood")
    assert abs(y - (t_y + t_h * top)) < 0.5 and abs(h - t_h * (1 - top - bottom)) < 0.5, (
        "the drawn mark sits at %.2f..%.2f while the photograph's ink sits at %.2f..%.2f"
        % (y, y + h, t_y + t_h * top, t_y + t_h * (1 - bottom)))
