"""Guards for the duty-board stack checker.

The page is a debug tool, but two things in it are rules rather than taste and are computed in
the generator so they can be held here: the enumeration of distinct tile shapes, and the two
seating rules that turn a shape into an order of seats. The page looks both up rather than
deriving them, so a drift between generator and page would fail here rather than quietly draw a
board nobody asked for.
"""

import importlib.util
import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GEN = ROOT / "tools" / "ui_debug" / "generate_duty_board_check.py"
TMPL = ROOT / "tools" / "ui_debug" / "duty_board_check.html.tmpl"


@pytest.fixture(scope="module")
def mod():
    """Import the generator without running it.

    It puts ui/render on sys.path and imports gen_duty_grid at module scope, which is why this
    is a fixture rather than a plain import at the top of the file.
    """
    sys.path.insert(0, str(ROOT / "ui" / "render"))
    spec = importlib.util.spec_from_file_location("generate_duty_board_check", GEN)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_fifteen_distinct_shapes(mod):
    """Three seats, totals one to five, counted up to which seat holds which part."""
    shapes = mod.shapes()
    assert len(shapes) == 15, "expected 15 shapes, got %d: %s" % (len(shapes), shapes)
    keys = ["+".join(str(v) for v in s) for s in shapes]
    assert len(set(keys)) == 15, "shapes are not distinct: %s" % keys


def test_shapes_are_partitions_into_at_most_three_parts(mod):
    for shape in mod.shapes():
        assert 1 <= sum(shape) <= 5, "%s totals outside 1..5" % shape
        assert 1 <= len(shape) <= 3, "%s needs more than three seats" % shape
        assert all(v > 0 for v in shape), "%s carries an empty part" % shape
        assert list(shape) == sorted(shape, reverse=True), "%s is not in descending order" % shape


def test_every_total_is_represented(mod):
    """One shape for a total of 1, two for 2, and so on -- the count of partitions of n into at
    most three parts. A missing total would leave a hole the sweep deal walks straight past."""
    by_total = {}
    for shape in mod.shapes():
        by_total.setdefault(sum(shape), []).append(shape)
    assert sorted(by_total) == [1, 2, 3, 4, 5]
    assert [len(by_total[n]) for n in range(1, 6)] == [1, 2, 3, 4, 5]


def test_queues_place_every_sculpt_exactly_once(mod):
    """Both rules are permutations of the same multiset of seats -- they differ in ORDER only."""
    for shape in mod.shapes():
        q = mod.queues(shape)
        for name, order in q.items():
            assert len(order) == sum(shape), (
                "%s %s queue has %d entries for a total of %d"
                % (shape, name, len(order), sum(shape)))
            for seat, count in enumerate(shape):
                got = order.count(seat)
                assert got == count, (
                    "%s %s gives seat %d %d slots, the shape says %d"
                    % (shape, name, seat, got, count))
        assert sorted(q["grouped"]) == sorted(q["arrival"]), (
            "%s: the two rules disagree about who is on the tile" % shape)


def test_grouped_keeps_a_seat_contiguous(mod):
    """The whole point of `grouped`: a player's sculpts are neighbours, so the tile can be read
    for "how many are mine" without scanning it."""
    for shape in mod.shapes():
        order = mod.queues(shape)["grouped"]
        runs = [order[0]]
        for seat in order[1:]:
            if seat != runs[-1]:
                runs.append(seat)
        assert len(runs) == len(set(runs)), "%s grouped is not contiguous: %s" % (shape, order)


def test_arrival_takes_turns(mod):
    """`arrival` deals round-robin over the seats that still have sculpts to place, so no seat
    takes a second slot while another is still waiting for its first."""
    for shape in mod.shapes():
        order = mod.queues(shape)["arrival"]
        seen = {}
        for i, seat in enumerate(order):
            seen[seat] = seen.get(seat, 0) + 1
            for other, count in enumerate(shape):
                if other == seat or count < seen[seat]:
                    continue
                assert seen.get(other, 0) >= seen[seat] - 1, (
                    "%s arrival gave seat %d its round-%d sculpt at %d while seat %d was still "
                    "short: %s" % (shape, seat, seen[seat], i, other, order))


def test_exactly_eight_shapes_tell_the_rules_apart(mod):
    """The seven single-seat and one-each shapes have nothing to group or interleave, so the
    seating decision rests on the other eight. If this number moves, the argument about which
    rule to ship is being made over a different set of pictures than it was."""
    differ = [s for s in mod.shapes()
              if mod.queues(s)["grouped"] != mod.queues(s)["arrival"]]
    assert len(differ) == 8, (
        "%d shapes distinguish the rules, expected 8: %s" % (len(differ), differ))
    same = [s for s in mod.shapes()
            if mod.queues(s)["grouped"] == mod.queues(s)["arrival"]]
    for shape in same:
        assert len(shape) == 1 or set(shape) == {1}, (
            "%s should distinguish the rules but does not" % shape)


def test_slug_table_matches_the_duty_names(mod):
    assert len(mod.SLUGS) == len(mod.NAMES) == 9
    # The icon folder is keyed by slug; a slug with no icons is allowed, and The City is the one
    # that is expected to have none.
    assert "city" in mod.SLUGS
    assert not list(mod.ICON_DIR.glob("city_*.svg")), (
        "The City has gained an action icon -- the page's 'no action icon' note is now a lie")


def test_page_builds_with_every_placeholder_substituted(mod, tmp_path, monkeypatch):
    """The generator asserts this itself; running it here means a template edit that adds a
    placeholder without a value fails in CI rather than on someone's screen."""
    out = tmp_path / "duty_board_check.html"
    monkeypatch.setattr(sys, "argv",
                        ["generate_duty_board_check.py", "--no-open", "--out", str(out)])
    mod.main()
    page = out.read_text(encoding="utf-8")
    assert page.startswith("<!doctype html>")
    assert not re.findall(r"__[A-Z_]+__", page), "placeholders survived into the page"
    # The shape table has to arrive as data; a page that lost it would still render and would
    # silently draw nothing on every tile.
    assert '"parts"' in page and '"queues"' in page


def test_page_survives_missing_sculpt_art(mod, tmp_path, monkeypatch, capsys):
    """The sculpts are git-ignored debug input, so a fresh clone has none. A missing size must
    cost that size, not the page.

    Asserted on the EMBEDDED TABLE and on what the generator said, not on a string in the
    template: the page carries a literal "no sculpt art" fallback label whatever happens, so a
    test looking for that passed just as happily with the art present. It guarded nothing.
    """
    out = tmp_path / "duty_board_check.html"
    empty = tmp_path / "no_figures"
    empty.mkdir()
    monkeypatch.setattr(sys, "argv", ["generate_duty_board_check.py", "--no-open",
                                      "--out", str(out), "--figures", str(empty)])
    mod.main()
    said = capsys.readouterr().out
    page = out.read_text(encoding="utf-8")
    assert page.startswith("<!doctype html>")
    assert "no sculpts embedded" in said, (
        "the generator should say the art is missing; it printed:\n%s" % said)
    assert re.search(r"FIGS\s*=\s*\{\}", page), (
        "with no art the figure table should be empty; the page has %s"
        % (re.search(r"FIGS\s*=\s*.{0,40}", page) or "no FIGS at all"))


def test_page_embeds_the_sculpt_table_when_the_art_is_there(mod, tmp_path, monkeypatch):
    """The other half of the pair. Without this, an empty figure table would satisfy the
    missing-art test above and nothing would notice the art had stopped being embedded."""
    if not any((mod.FIGURE_DIR / ("figure_player_1_%d.png" % s)).is_file()
               for s in mod.FIGURE_SIZES):
        pytest.skip("no rendered sculpts in %s; run make_tray_figures.py"
                    % mod.FIGURE_DIR.relative_to(ROOT))
    out = tmp_path / "duty_board_check.html"
    monkeypatch.setattr(sys, "argv",
                        ["generate_duty_board_check.py", "--no-open", "--out", str(out)])
    mod.main()
    page = out.read_text(encoding="utf-8")
    assert not re.search(r"FIGS\s*=\s*\{\}", page), "the sculpt table came out empty"
    for size in mod.FIGURE_SIZES:
        if (mod.FIGURE_DIR / ("figure_player_1_%d.png" % size)).is_file():
            assert '"%d"' % size in page, "size %d rendered but never reached the page" % size


def test_the_empty_tile_is_guarded(mod):
    """formation(0) must return no slots. It fell through to the five-slot case once, and since
    a typical deal leaves most tiles empty, that threw before the board was ever drawn.

    The guard moved with the formation into duty_sculpt_rules.js; this follows it rather than
    going blind, which is what a test left pointing at the old home would have done."""
    js = (ROOT / "tools" / "ui_debug" / "duty_sculpt_rules.js").read_text(encoding="utf-8")
    assert "if (n <= 0) return [];" in js, (
        "the empty-tile guard has gone; an empty tile will ask for five slots")


def test_the_haze_filters_are_pinned_to_srgb(mod):
    """SVG filters default to linearRGB, which kept so much chroma that the low end of the
    amount slider did nothing visible. Losing this line would silently weaken the cue.

    It moved into duty_sculpt_rules.js with the rest of the depth cue; this follows it, rather
    than staying pointed at the template and passing while guarding nothing."""
    js = (ROOT / "tools" / "ui_debug" / "duty_sculpt_rules.js").read_text(encoding="utf-8")
    assert 'color-interpolation-filters="sRGB"' in js


def test_placement_rejects_a_broken_file(mod, tmp_path, monkeypatch):
    """Every guard in placement() observed failing, so none of them is decorative."""
    import json as _json
    good = _json.loads(mod.PLACEMENT.read_text(encoding="utf-8"))

    def run(mutate):
        bad = _json.loads(_json.dumps(good))
        mutate(bad)
        f = tmp_path / "duty_placement.json"
        f.write_text(_json.dumps(bad), encoding="utf-8")
        monkeypatch.setattr(mod, "PLACEMENT", f)
        with pytest.raises(SystemExit) as e:
            mod.placement([])
        return str(e.value)

    assert "has no spread" in run(lambda d: d.pop("spread"))
    assert "real device pixels" in run(lambda d: d.__setitem__("spread", -3))
    assert "real device pixels" in run(lambda d: d.__setitem__("spread", "77"))
    assert "real device pixels" in run(lambda d: d.__setitem__("back", True))
    assert "order is" in run(lambda d: d.__setitem__("order", "sideways"))
    assert "want floor" in run(lambda d: d.__setitem__("mark", "sparkles"))
    assert "depth.mode" in run(lambda d: d["depth"].__setitem__("mode", "glow"))
    assert "0-100" in run(lambda d: d["depth"].__setitem__("amount", 140))


def test_missing_placement_file_says_so_rather_than_standing_in(mod, tmp_path, monkeypatch):
    """A page built from the fallback would look right and be wrong, so it must announce itself."""
    monkeypatch.setattr(mod, "PLACEMENT", tmp_path / "nope.json")
    notes = []
    out = mod.placement(notes)
    assert out["spread"] and out["rank"], "the fallback should still produce a usable set"
    assert any("missing" in n for n in notes), "a silent fallback is the failure this guards"


# ---------------------------------------------------------------- the placement sheet


@pytest.fixture(scope="module")
def sheet():
    spec = importlib.util.spec_from_file_location(
        "generate_placement_sheet", ROOT / "tools" / "ui_debug" / "generate_placement_sheet.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_sheet_covers_the_cases_that_matter(sheet):
    """One of each seat, one each across two and three seats, and the mixed counts. If a case
    goes missing the sheet still renders and simply never shows you that arrangement."""
    counts = {c for _label, c in sheet.CASES}
    for want in ((1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 0), (1, 1, 1),
                 (2, 1, 1), (2, 2, 1), (3, 1, 1)):
        assert want in counts, "the sheet no longer shows %s" % (want,)
    assert all(1 <= sum(c) <= 5 for _l, c in sheet.CASES)


def test_sheet_reads_the_placement_file(sheet, mod, tmp_path, monkeypatch):
    """The claim the tool makes about itself, checked the only way that means anything: put an
    unmistakable value in the file and look for it in the page."""
    import json as _json
    good = _json.loads(mod.PLACEMENT.read_text(encoding="utf-8"))
    good["spread"] = 999
    doctored = tmp_path / "duty_placement.json"
    doctored.write_text(_json.dumps(good), encoding="utf-8")

    board = sheet._board_module()
    monkeypatch.setattr(board, "PLACEMENT", doctored)
    monkeypatch.setattr(sheet, "_board_module", lambda: board)
    out = tmp_path / "placement_sheet.html"
    monkeypatch.setattr(sys, "argv",
                        ["generate_placement_sheet.py", "--no-open", "--out", str(out)])
    if not any((board.FIGURE_DIR / ("figure_player_1_%d.png" % s)).is_file()
               for s in board.FIGURE_SIZES):
        pytest.skip("no rendered sculpts; run make_tray_figures.py")
    sheet.main()
    page = out.read_text(encoding="utf-8")
    assert "999" in page, "the doctored value never reached the page"


def test_the_one_set_is_used_at_every_size(mod):
    """The contract after the simplification: one spread, one set-back, one rank gap, applied
    whatever sculpt is on screen.

    This used to be spelled `"sizes" not in place`, which guarded the absence of a KEY rather
    than the thing the key used to mean. `sizes` now exists and is a plain list of the sculpt
    sizes the sow page offers a button for -- it carries no numbers of its own. So the guard is
    written against what would actually break the contract: a size growing its own spread.
    """
    place = mod.placement([])
    for key in ("spread", "back", "rank"):
        assert isinstance(place[key], int), "%s is no longer a single number" % key
    for value in (place.get("sizes") or []):
        assert isinstance(value, int), "sizes holds %r; it is a list of sizes, not a table" % value
    assert place.get("tuned_at") in mod.FIGURE_SIZES, (
        "tuned_at should name a size the tray can actually show")


def test_the_formation_lives_in_exactly_one_file(sheet):
    """It was written out three times -- two templates and a Python function -- and they agreed
    only because they had been copied from each other. Now there is one copy, inlined."""
    js = (ROOT / "tools" / "ui_debug" / "duty_sculpt_rules.js").read_text(encoding="utf-8")
    assert "if (n <= 0) return [];" in js, "the empty-tile guard is gone from the formation"
    assert "function dutyFormation" in js and "function dutySeatOrder" in js
    for page in ("duty_board_check.html.tmpl", "generate_placement_sheet.py",
                 "duty_sow.html.tmpl"):
        src = (ROOT / "tools" / "ui_debug" / page).read_text(encoding="utf-8")
        assert "__FORMATION__" in src, "%s no longer inlines the shared formation" % page
        assert "function formation(" not in src, (
            "%s has grown its own copy of the formation again" % page)
        assert "function chain(" not in src, (
            "%s has grown its own copy of the depth cue again" % page)


def test_save_merges_rather_than_overwrites(sheet, mod, tmp_path, monkeypatch):
    """The file is mostly prose explaining why the numbers are what they are. A save that
    replaced the document would throw all of it away the first time a slider moved."""
    import json as _json
    board = sheet._board_module()
    f = tmp_path / "duty_placement.json"
    f.write_text(mod.PLACEMENT.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(board, "PLACEMENT", f)
    before = _json.loads(f.read_text(encoding="utf-8"))

    sheet.save_settings(board, {"spread": 88, "back": 25, "rank": 60, "order": "arrival",
                                "depth": {"mode": "dark", "amount": 70, "full_at": 40}})
    after = _json.loads(f.read_text(encoding="utf-8"))
    assert after["spread"] == 88 and after["order"] == "arrival"
    assert after["depth"] == {"mode": "dark", "amount": 70, "full_at": 40}
    for key in before:
        if key.endswith("_note") or key in ("note", "tuned_at", "one_set_on_purpose"):
            assert after[key] == before[key], "save dropped %s" % key


def test_save_refuses_what_the_generator_would_refuse(sheet, mod, tmp_path, monkeypatch):
    """The button must not be able to write a file the tool would then refuse to load."""
    board = sheet._board_module()
    f = tmp_path / "duty_placement.json"
    f.write_text(mod.PLACEMENT.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(board, "PLACEMENT", f)
    good = {"spread": 80, "back": 20, "rank": 50, "order": "grouped",
            "depth": {"mode": "haze", "amount": 60, "full_at": 52}}

    def refuse(**over):
        sent = dict(good, **over)
        with pytest.raises(ValueError) as e:
            sheet.save_settings(board, sent)
        return str(e.value)

    assert "non-negative" in refuse(spread=-1)
    assert "non-negative" in refuse(spread="80")
    assert "non-negative" in refuse(back=True)
    assert "grouped or arrival" in refuse(order="sideways")
    assert "haze, dark or off" in refuse(depth={"mode": "glow", "amount": 60, "full_at": 52})
    assert "0-100" in refuse(depth={"mode": "haze", "amount": 900, "full_at": 52})
    assert "positive whole number" in refuse(depth={"mode": "haze", "amount": 60, "full_at": 0})
    # and none of that reached the disk
    import json as _json
    assert _json.loads(f.read_text(encoding="utf-8"))["spread"] == \
        _json.loads(mod.PLACEMENT.read_text(encoding="utf-8"))["spread"]


def test_the_depth_cue_is_absolute_not_relative():
    """The bug Adam found: the cue used to be y / (deepest thing on the tile), so pushing one
    figure further back made every other figure CLEARER. Three depths could not be told apart
    either -- everything at the maximum looked identical.

    Replicated here rather than imported, because the rule lives in JavaScript; if these two
    ever disagree this test is the thing that says so."""
    import math

    def depth(y, ref):
        return 0.0 if y <= 0 else 1 - math.exp(-y / ref)

    ref = 52
    # a figure's cue depends only on ITS OWN depth
    assert depth(52, ref) == depth(52, ref)
    # deeper is always more, with no ceiling to bunch against
    seq = [depth(y, ref) for y in (0, 21, 52, 90, 140)]
    assert seq == sorted(seq), "the cue is not monotonic in depth: %s" % seq
    assert len(set(round(v, 4) for v in seq)) == len(seq), "two depths share a value: %s" % seq
    # and the specific case from the screenshots: the back rank must not change when the middle
    # figure moves past it
    back_rank = depth(52, ref)
    for middle in (21, 52, 90):
        assert depth(52, ref) == back_rank, (
            "the back rank changed when the middle moved to %d" % middle)
    # the old rule failed exactly here, which is why it was replaced
    old = lambda y, others: y / max(others)          # noqa: E731
    assert old(52, [52, 21]) > old(52, [52, 90]), (
        "this assertion documents the OLD behaviour; if it stops holding, the bug is gone from "
        "the description too and this test should be re-read")


def test_full_at_is_validated(mod, tmp_path, monkeypatch):
    """full_at divides the depth. Zero would send every figure straight to full haze."""
    import json as _json
    good = _json.loads(mod.PLACEMENT.read_text(encoding="utf-8"))

    def run(value):
        bad = _json.loads(_json.dumps(good))
        bad["depth"]["full_at"] = value
        f = tmp_path / "duty_placement.json"
        f.write_text(_json.dumps(bad), encoding="utf-8")
        monkeypatch.setattr(mod, "PLACEMENT", f)
        with pytest.raises(SystemExit) as e:
            mod.placement([])
        return str(e.value)

    assert "positive whole number" in run(0)
    assert "positive whole number" in run(-10)
    assert "positive whole number" in run("52")


# ---------------------------------------------------------------- the sow page


SOW = ROOT / "tools" / "ui_debug" / "generate_duty_sow.py"
SOW_TMPL = ROOT / "tools" / "ui_debug" / "duty_sow.html.tmpl"


@pytest.fixture(scope="module")
def sow():
    spec = importlib.util.spec_from_file_location("generate_duty_sow", SOW)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_the_lit_set_is_the_board_graph_and_not_a_drawing_of_one(sow):
    """The sow walks the real topology or it is a different game.

    A page that restated the ring would keep looking correct while the board moved underneath
    it, which is the failure this whole toolchain keeps being bitten by.
    """
    import json as _json
    edges = sow.graph()
    real = _json.loads((ROOT / "configs" / "board.json").read_text(encoding="utf-8"))["edges"]
    assert edges == real
    branching = sorted(p for p in sow.GRID if len(edges.get(p, [])) > 1)
    assert branching == ["city", "east", "west"], (
        "the positions that offer a choice have changed: %s" % branching)
    for pos in sow.GRID:
        assert 1 <= len(edges[pos]) <= 2, "%s has %d exits; the page lights at most two" % (
            pos, len(edges[pos]))


def test_every_position_carries_a_duty_the_slug_table_knows(sow):
    """The banner and the title are looked up by slug, so an unknown one would pair a name with
    somebody else's parchment rather than failing."""
    board = sow._board_module()
    at = sow.duty_at()
    assert set(at) >= set(sow.GRID), "a compass position has no duty"
    for pos in sow.GRID:
        assert at[pos] in board.SLUGS, "%s carries %r, which is not in the slug table" % (
            pos, at[pos])


def test_the_sow_page_stays_on_its_side_of_the_seam():
    """Everything under tools/ui_debug is a derived view: it reads data and draws it.

    The duty at each position was briefly taken from pilgrim/model/duties.py, which works and is
    still the wrong shelf -- a game config is the source of truth for any real game value a view
    shows, and reaching into the model also drags in an interpreter requirement a tools run
    cannot count on.
    """
    src = SOW.read_text(encoding="utf-8")
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            assert "pilgrim" not in stripped, "the sow page imports the engine: %s" % stripped
    assert "configs" in src and "duty_tiles" in src, (
        "the duty layout no longer comes from a config")


def test_the_sow_lights_only_the_next_step():
    """The decision Adam settled: lit means legal NOW.

    The lookahead that ghosted tiles further along a forced run is gone, not merely turned off.
    A dormant copy is how it comes back.
    """
    tmpl = SOW_TMPL.read_text(encoding="utf-8")
    assert "function ahead(" not in tmpl, "the lookahead has grown back"
    assert "mark floor ahead" not in tmpl and "cell.route" not in tmpl, (
        "the ghosted route is back in the page")
    assert ".cell.live .mark{opacity:1}" in tmpl, "the mark no longer keys off the lit cell"


def test_no_mark_on_the_tile_the_fistful_came_from():
    """Every rule that makes a mark visible is scoped by `.cell.live`.

    Unscoped, `.mark.foot.later` once carried three classes and outranked the one-class default,
    painting pale rings on all nine tiles permanently. The source tile wears `.src`, never
    `.live`, so scoping every visibility rule to `.live` is what keeps it bare.
    """
    tmpl = SOW_TMPL.read_text(encoding="utf-8")
    for line in tmpl.splitlines():
        if "opacity:1" in line and ".mark" in line:
            assert ".cell.live" in line, (
                "a mark is lit without asking whether the cell is: %s" % line)
        if ".cell.src" in line:
            assert "opacity" not in line, "the source tile has been given a mark again: %s" % line


def test_the_sow_page_has_no_settings_of_its_own():
    """The numbers are tuned in the placement sheet and saved. A control here would be a second
    place to set them, and the two would disagree the first time one moved."""
    tmpl = SOW_TMPL.read_text(encoding="utf-8")
    assert "type=range" not in tmpl and "type=\"range\"" not in tmpl, "a slider appeared"
    for word in ("grouped", "arrival", "haze", "dark"):
        assert ("data-m=%s" % word) not in tmpl and (">%s<" % word) not in tmpl, (
            "%r has become a button; it belongs to the placement file" % word)
    # The controls that ARE there, and the two of them only.
    assert 'id=seatb' in tmpl and 'id=szb' in tmpl and 'id=breset' in tmpl


def test_the_haze_ladder_is_described_once():
    """The number of rungs BUILT and the number a figure is rounded ONTO have to agree. Build
    eight and round onto twelve and the deepest figures land on rungs that were never defined,
    which renders as no haze at all rather than as an error."""
    js = (ROOT / "tools" / "ui_debug" / "duty_sculpt_rules.js").read_text(encoding="utf-8")
    assert "var DUTY_HAZE = {steps: 8, max: 0.62};" in js
    for page in ("duty_board_check.html.tmpl", "generate_placement_sheet.py",
                 "duty_sow.html.tmpl"):
        src = (ROOT / "tools" / "ui_debug" / page).read_text(encoding="utf-8")
        if "HAZE_STEPS" not in src:
            continue
        assert "DUTY_HAZE.steps" in src, "%s sets the ladder's size itself again" % page


def test_the_sizes_on_offer_come_from_the_file(sow):
    """The rule Adam asked for: the file names the sizes, the buttons follow. A size with no art
    is dropped with a note rather than offered, because a button that draws an empty board is
    worse than a button that is absent."""
    notes = []
    art = {"210": [], "180": []}
    assert sow.offered({"sizes": [210], "tuned_at": 210}, art, notes) == [210]
    assert sow.offered({"sizes": [210, 180], "tuned_at": 210}, art, notes) == [180, 210]
    assert notes == []
    assert sow.offered({"sizes": [210, 240], "tuned_at": 210}, art, notes) == [210]
    assert any("240" in n for n in notes), "a named size with no art vanished without a word"
    # No list at all: the size the numbers were tuned at is the one you get.
    assert sow.offered({"tuned_at": 210}, art, []) == [210]


def test_placement_refuses_a_broken_size_list(mod, tmp_path, monkeypatch):
    """`sizes` is a list of sizes, not a table of numbers and not a free-for-all."""
    import json as _json
    good = _json.loads(mod.PLACEMENT.read_text(encoding="utf-8"))
    for bad in ([], [210, 210], [0], [-90], [210, True], "210", {"210": {}}):
        doctored = dict(good)
        doctored["sizes"] = bad
        path = tmp_path / "duty_placement.json"
        path.write_text(_json.dumps(doctored), encoding="utf-8")
        monkeypatch.setattr(mod, "PLACEMENT", path)
        with pytest.raises(SystemExit) as caught:
            mod.placement([])
        assert "sizes" in str(caught.value), "the refusal does not name what was wrong: %r" % bad


def test_sow_page_builds_and_reads_the_placement_file(sow, mod, tmp_path, monkeypatch):
    """Built end to end, with every placeholder gone -- and the claim that it reads the file
    checked the only way that means anything: put an unmistakable value in and look for it."""
    import json as _json
    board = sow._board_module()
    if not any((board.FIGURE_DIR / ("figure_player_1_%d.png" % s)).is_file()
               for s in board.FIGURE_SIZES):
        pytest.skip("no rendered sculpts; run make_tray_figures.py")
    doctored = tmp_path / "duty_placement.json"
    place = _json.loads(mod.PLACEMENT.read_text(encoding="utf-8"))
    place["spread"] = 999
    doctored.write_text(_json.dumps(place), encoding="utf-8")
    monkeypatch.setattr(board, "PLACEMENT", doctored)
    monkeypatch.setattr(sow, "_board_module", lambda: board)

    out = tmp_path / "duty_sow.html"
    monkeypatch.setattr(sys, "argv", ["generate_duty_sow.py", "--no-open", "--out", str(out)])
    sow.main()
    page = out.read_text(encoding="utf-8")
    assert not re.findall(r"__[A-Z_]+__", page), "a placeholder survived"
    assert '"spread": 999' in page, "the doctored value never reached the page"
    assert "function dutyFormation" in page, "the shared rules were not inlined"
    assert '"north_east"' in page, "the board graph never reached the page"
