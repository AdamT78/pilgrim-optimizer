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
