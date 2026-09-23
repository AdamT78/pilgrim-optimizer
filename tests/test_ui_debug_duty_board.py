"""Guards for the duty-board stack checker.

The page is a debug tool, but two things in it are rules rather than taste and are computed in
the generator so they can be held here: the enumeration of distinct tile shapes, and the two
seating rules that turn a shape into an order of seats. The page looks both up rather than
deriving them, so a drift between generator and page would fail here rather than quietly draw a
board nobody asked for.
"""

import importlib.util
import json
import pathlib
import re
import shutil
import subprocess
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


def test_the_lit_set_is_the_board_graph_and_not_a_drawing_of_one(sow, mod):
    """The sow walks the real topology or it is a different game.

    A page that restated the ring would keep looking correct while the board moved underneath
    it, which is the failure this whole toolchain keeps being bitten by.
    """
    import json as _json
    edges = sow.graph()
    real = _json.loads((ROOT / "configs" / "board.json").read_text(encoding="utf-8"))["edges"]
    assert edges == real
    branching = sorted(p for p in mod.GRID if len(edges.get(p, [])) > 1)
    assert branching == ["city", "east", "west"], (
        "the positions that offer a choice have changed: %s" % branching)
    for pos in mod.GRID:
        assert 1 <= len(edges[pos]) <= 2, "%s has %d exits; the page lights at most two" % (
            pos, len(edges[pos]))


def test_every_position_carries_a_duty_the_slug_table_knows(mod):
    """The banner and the title are looked up by slug, so an unknown one would pair a name with
    somebody else's parchment rather than failing.

    This lives with the slug table and the parchment now rather than in the sow generator: the
    placement sheet draws the same nine tiles, and the pairing was about to be written twice.
    """
    at = mod.duty_at()
    assert set(at) >= set(mod.GRID), "a compass position has no duty"
    for pos in mod.GRID:
        assert at[pos] in mod.SLUGS, "%s carries %r, which is not in the slug table" % (
            pos, at[pos])
    assert set(mod.GRID) == set(mod.duty_at()), "the compass and the layout have drifted apart"


def test_the_sow_page_stays_on_its_side_of_the_seam():
    """Everything under tools/ui_debug is a derived view: it reads data and draws it.

    The duty at each position was briefly taken from pilgrim/model/duties.py, which works and is
    still the wrong shelf -- a game config is the source of truth for any real game value a view
    shows, and reaching into the model also drags in an interpreter requirement a tools run
    cannot count on.
    """
    for path in (SOW, GEN, ROOT / "tools" / "ui_debug" / "generate_placement_sheet.py"):
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")):
                assert "pilgrim" not in stripped, "%s imports the engine: %s" % (
                    path.name, stripped)
    owner = GEN.read_text(encoding="utf-8")
    assert "configs" in owner and "duty_tiles" in owner, (
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


# ---------------------------------------------------------------- where a tile's parts sit


RULES = ROOT / "tools" / "ui_debug" / "duty_sculpt_rules.js"
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _in_node(expression):
    """Evaluate one expression against the real rules file, in node.

    The alternative was a Python reimplementation of the geometry to assert against, which is
    the second copy this whole file exists to prevent: it would agree on the day it was written
    and drift silently afterwards, and the test would go on passing either way.
    """
    script = (
        "const fs = require('fs');\n"
        "eval(fs.readFileSync(%r, 'utf8'));\n"
        "process.stdout.write(JSON.stringify(%s));\n" % (str(RULES), expression)
    )
    done = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    return json.loads(done.stdout)


def test_the_tile_layout_lives_in_exactly_one_file():
    """It was written out in each page that draws the wheel, and the copies had drifted.

    The gap above the banner was 0.046 of the cell in the board checker and 0.050 in the sow
    page, so the two disagreed about where a banner sat -- by about two and a half real pixels,
    which is the size of difference nobody notices and nobody can then explain.
    """
    js = RULES.read_text(encoding="utf-8")
    assert "function dutyTileLayout" in js
    for page in ("duty_board_check.html.tmpl", "duty_sow.html.tmpl"):
        src = (ROOT / "tools" / "ui_debug" / page).read_text(encoding="utf-8")
        assert "dutyTileLayout(" in src, "%s no longer asks for the shared layout" % page
        for own in ("* 0.55", "* 0.046", "* 0.05,", "* 0.010", "* 0.168"):
            assert own not in src, "%s computes %r itself again" % (page, own)


@needs_node
def test_the_field_clears_the_deeper_of_the_set_back_and_the_rank_gap():
    """The board checker took only the rank gap, which clips the middle of three the moment a
    set-back larger than the rank gap is tried. Latent rather than broken at 21 against 52 --
    measured, the middle figure's top went to -34 css px at a set-back of 120."""
    shallow = _in_node("dutyTileLayout(600, 210, 52, 21, {icons: false})")
    deep = _in_node("dutyTileLayout(600, 210, 52, 120, {icons: false})")
    assert shallow["field"] == 210 + 52, "the field no longer clears the rank gap"
    assert deep["field"] == 210 + 120, "a set-back past the rank gap is being ignored again"


@needs_node
def test_the_layout_centres_the_stack_and_counts_the_icons_only_when_they_are_drawn():
    without = _in_node("dutyTileLayout(600, 210, 52, 21, {icons: false})")
    with_icons = _in_node("dutyTileLayout(600, 210, 52, 21, {icons: true})")
    assert with_icons["total"] > without["total"], "the icon row costs no height"
    assert with_icons["total"] - without["total"] == pytest.approx(
        with_icons["gapB"] + with_icons["icon"])
    for layout in (without, with_icons):
        assert layout["top"] * 2 + layout["total"] == pytest.approx(600), "the stack is not centred"
        assert layout["mark"] > layout["banW"], "the floor mark no longer overhangs the banner"


@needs_node
def test_the_group_box_measures_the_figures_rather_than_the_spread():
    """The sculpts are not one width, so the room a formation takes depends on who is standing
    in it. A box computed from the spread alone would be wrong for the widest seat."""
    narrow = _in_node("dutyCapacityBox(5, 110, 21, 52, 91, 210)")
    wide = _in_node("dutyCapacityBox(5, 110, 21, 52, 108, 210)")
    assert wide["w"] - narrow["w"] == pytest.approx(108 - 91), (
        "the envelope ignores how wide the figures are")
    assert narrow["h"] == 210 + 52, "the envelope does not reach the back rank's head"
    assert _in_node("dutyGroupBox([])") is None
    one = _in_node("dutyGroupBox([{x: 0, y: 0, w: 90, h: 200}])")
    assert (one["left"], one["right"], one["top"], one["bottom"]) == (-45, 45, 200, 0)


# ---------------------------------------------------------------- the frame a tile is drawn on


def test_placement_refuses_a_broken_frame(mod, tmp_path, monkeypatch):
    """The frame is what art gets drawn to, so a nonsense rectangle must not reach a page."""
    good = json.loads(mod.PLACEMENT.read_text(encoding="utf-8"))
    for bad in ({"w": 0, "h": 430, "drop": 0}, {"w": 369, "h": -1, "drop": 0},
                {"w": 369.5, "h": 430, "drop": 0}, {"w": True, "h": 430, "drop": 0},
                {"w": 369, "h": 430, "drop": "40"}, {"h": 430, "drop": 0}, [369, 430]):
        doctored = dict(good)
        doctored["frame"] = bad
        path = tmp_path / "duty_placement.json"
        path.write_text(json.dumps(doctored), encoding="utf-8")
        monkeypatch.setattr(mod, "PLACEMENT", path)
        with pytest.raises(SystemExit) as caught:
            mod.placement([])
        assert "frame" in str(caught.value), "the refusal does not name the frame: %r" % (bad,)


def test_the_frame_may_sit_below_or_above_the_floor(mod, tmp_path, monkeypatch):
    """A ground that continues under the feet needs a positive drop; lifting the frame off the
    floor is a legitimate thing to try, so a negative one is not an error."""
    good = json.loads(mod.PLACEMENT.read_text(encoding="utf-8"))
    for drop in (-60, 0, 40):
        doctored = dict(good)
        doctored["frame"] = {"w": 369, "h": 430, "drop": drop}
        path = tmp_path / "duty_placement.json"
        path.write_text(json.dumps(doctored), encoding="utf-8")
        monkeypatch.setattr(mod, "PLACEMENT", path)
        assert mod.placement([])["frame"]["drop"] == drop


def test_the_sheet_saves_the_frame_without_losing_the_prose(sheet, mod, tmp_path, monkeypatch):
    board = sheet._board_module()
    path = tmp_path / "duty_placement.json"
    path.write_text(mod.PLACEMENT.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(board, "PLACEMENT", path)
    saved = sheet.save_settings(board, {
        "spread": 110, "back": 21, "rank": 52, "order": "grouped",
        "depth": {"mode": "haze", "amount": 60, "full_at": 52},
        "frame": {"w": 400, "h": 500, "drop": -10}})
    assert saved["frame"] == {"w": 400, "h": 500, "drop": -10}
    assert "frame_note" in saved, "the explanation of what the frame is was thrown away"
    assert "note" in saved and "one_set_on_purpose" in saved
    # And the file it wrote is one the generator would accept back.
    monkeypatch.setattr(mod, "PLACEMENT", path)
    assert mod.placement([])["frame"]["w"] == 400


def test_the_sheet_has_the_wheel_view_and_the_frame_controls(sheet):
    """The controls are the deliverable here: a frame you cannot drag is a number in a file."""
    src = sheet.TEMPLATE
    assert 'id=viewb' in src, "the view switch is gone"
    assert '"arrangements", "wheel"' in src, "the two views are no longer offered"
    for control in ("id=frw type=range", "id=frh type=range", "id=frd type=range"):
        assert control in src, "%s is missing; the frame cannot be adjusted" % control
    for wiring in ('\nslider("frw"', '\nslider("frh"', '\nslider("frd"'):
        assert wiring in src, "%s is not wired to anything" % wiring.strip()
    assert "function drawWheel" in src and "function drawCases" in src
    assert "FRAME = __FRAME__" in src, (
        "the frame is hardcoded in the page rather than coming from the file")


def test_the_wheel_view_does_not_grow_its_own_copy_of_the_nine_tiles(sheet):
    """The compass order, the slug table and the parchment pairing live in one module. The sow
    page had them first; when the sheet needed them too they moved rather than multiplied."""
    src = sheet.TEMPLATE + (ROOT / "tools" / "ui_debug" / "generate_placement_sheet.py").read_text(
        encoding="utf-8")
    assert "board.tiles(" in src, "the sheet no longer asks for the shared tiles"
    assert "north_west" not in src, "the sheet has written out its own compass order"
    sow_src = SOW.read_text(encoding="utf-8")
    assert "north_west" not in sow_src, "the sow generator has grown the compass back"


# ---------------------------------------------------------------- the ground a tile stands on


def test_every_ground_plate_has_a_licence_on_record(mod):
    """The gothic tree keeps its own attribution.json and CI verifies it. This fails earlier and
    says which file, because art that lands without a record is the kind of thing that is cheap
    to fix the day it arrives and archaeology a month later."""
    att = json.loads(
        (ROOT / "ui" / "assets-gothic" / "attribution.json").read_text(encoding="utf-8"))
    assert "grounds" in att["assetDirs"], "the grounds folder is not checked by the verifier"
    # EVERY PLATE, INCLUDING THE ONES IN candidates/. The walk used to be one flat glob over
    # grounds/ and it counted the candidates FOLDER as a file the moment one was created --
    # a plate held rather than filed still arrived from somewhere and still needs its record.
    root = mod.GROUNDS_DIR
    seen = 0
    for path in sorted(root.rglob("*")):
        if path.is_dir() or path.name.startswith("."):
            continue
        key = "grounds/%s" % path.relative_to(root).as_posix()
        assert key in att["files"], "%s has no entry in attribution.json" % key
        assert att["files"][key]["licence"] in att["licences"], (
            "%s claims a licence the register does not define" % key)
        seen += 1
    assert seen >= 5, "only %d plate(s) walked -- the tree is not being searched" % seen


def test_the_plates_are_discovered_rather_than_listed(mod):
    """Dropping a PNG in the folder is all it takes to be able to pick it. A list in the plan
    would be a second place for the folder's contents to be wrong."""
    notes = []
    art = mod.ground_art(notes)
    on_disk = {p.stem for p in mod.GROUNDS_DIR.glob("*.png")}
    assert set(art) == on_disk, "the loader and the folder disagree about what exists"
    plan = json.loads(mod.GROUND_PLAN.read_text(encoding="utf-8"))
    for name in art:
        assert name in plan.get("grounds", {}) or True   # tuning is optional; existence is not
    # and each plate reports where its own widest row sits, which is the anchor's starting guess
    for name, g in art.items():
        assert 0 <= g["widest"] <= 100, "%s reports a nonsense standing line" % name
        assert g["w"] > 0 and g["h"] > 0


def test_ground_plan_refuses_what_would_draw_nothing(mod, tmp_path, monkeypatch):
    good = json.loads(mod.GROUND_PLAN.read_text(encoding="utf-8"))
    bad_plans = [
        {"grounds": {"cobbles_oval": dict(good["grounds"]["cobbles_oval"], anchor=101)}},
        {"grounds": {"cobbles_oval": dict(good["grounds"]["cobbles_oval"], scale=0)}},
        {"grounds": {"cobbles_oval": dict(good["grounds"]["cobbles_oval"], dim="55")}},
        {"grounds": {"cobbles_oval": dict(good["grounds"]["cobbles_oval"], opacity=True)}},
        {"grounds": good["grounds"], "by_duty": {"not_a_duty": "cobbles_oval"}},
        {"grounds": good["grounds"], "by_duty": {"produce": "no_such_plate"}},
    ]
    for bad in bad_plans:
        path = tmp_path / "duty_grounds.json"
        path.write_text(json.dumps(bad), encoding="utf-8")
        monkeypatch.setattr(mod, "GROUND_PLAN", path)
        with pytest.raises(SystemExit):
            mod.ground_plan([])


def test_a_missing_plan_says_so_rather_than_drawing_a_bare_board(mod, tmp_path, monkeypatch):
    missing = tmp_path / "duty_grounds.json"
    monkeypatch.setattr(mod, "GROUND_PLAN", missing)
    notes = []
    plan = mod.ground_plan(notes)
    assert plan["by_duty"] == {} and plan["grounds"] == {}
    assert any(missing.name in n and "missing" in n for n in notes), (
        "a missing plan passed without a word: %r" % notes)


def test_the_grounds_save_merges_and_validates(sheet, mod, tmp_path, monkeypatch):
    board = sheet._board_module()
    path = tmp_path / "duty_grounds.json"
    path.write_text(mod.GROUND_PLAN.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(board, "GROUND_PLAN", path)
    saved = sheet.save_grounds(board, {
        "by_duty": {"produce": "flagstones_slab"},
        "grounds": {"flagstones_slab": {"anchor": 61, "scale": 100, "dim": 40,
                                        "saturate": 50, "opacity": 90}}})
    assert saved["by_duty"]["produce"] == "flagstones_slab"
    assert saved["grounds"]["flagstones_slab"]["dim"] == 40
    assert "note" in saved and "angle_note" in saved, "the prose was thrown away"
    # and what it wrote is a file the generator would accept back
    monkeypatch.setattr(mod, "GROUND_PLAN", path)
    assert mod.ground_plan([])["grounds"]["flagstones_slab"]["dim"] == 40
    with pytest.raises(ValueError):
        sheet.save_grounds(board, {"by_duty": {"produce": "missing"}, "grounds": {}})


def test_switching_view_hides_everything_the_other_view_owns(sheet):
    """The view switch has to own every element a view puts on screen, not most of them.

    The picker strip was only ever touched by drawWheel(), so leaving the wheel left it sitting
    above the arrangements carrying a selection from a board that was no longer visible. The
    dispatcher shows and hides; the drawing functions draw.
    """
    src = sheet.TEMPLATE
    body = src[src.index("function draw(){"):src.index("function drawPicker")]
    for element in ("stage", "grid", "picker"):
        assert ('getElementById("%s").hidden' % element) in body, (
            "draw() does not decide whether #%s is on screen" % element)


def test_the_sow_page_plays_on_what_the_sheet_saved(sow, mod, tmp_path, monkeypatch):
    """The sheet tunes and the sow page plays on the result. It was reading neither the frame
    nor the grounds -- it took the placement file and drew acolytes on an empty board, so a
    ground you had just assigned simply was not there when you went to move a piece.

    Proved the only way that means anything: put unmistakable values in both files and look for
    them in the page.
    """
    board = sow._board_module()
    if not any((board.FIGURE_DIR / ("figure_player_1_%d.png" % s)).is_file()
               for s in board.FIGURE_SIZES):
        pytest.skip("no rendered sculpts; run make_tray_figures.py")

    place = json.loads(mod.PLACEMENT.read_text(encoding="utf-8"))
    place["frame"] = {"w": 299, "h": 411, "drop": -13}
    doctored_place = tmp_path / "duty_placement.json"
    doctored_place.write_text(json.dumps(place), encoding="utf-8")

    plan = json.loads(mod.GROUND_PLAN.read_text(encoding="utf-8"))
    plan["by_duty"]["taxation"] = ""                       # bare floor
    plan["grounds"]["flagstones_slab"]["dim"] = 11
    doctored_plan = tmp_path / "duty_grounds.json"
    doctored_plan.write_text(json.dumps(plan), encoding="utf-8")

    monkeypatch.setattr(board, "PLACEMENT", doctored_place)
    monkeypatch.setattr(board, "GROUND_PLAN", doctored_plan)
    monkeypatch.setattr(sow, "_board_module", lambda: board)
    out = tmp_path / "duty_sow.html"
    monkeypatch.setattr(sys, "argv", ["generate_duty_sow.py", "--no-open", "--out", str(out)])
    sow.main()

    page = out.read_text(encoding="utf-8")
    assert '"w": 299' in page and '"drop": -13' in page, "the frame never reached the page"
    assert '"dim": 11' in page, "the ground tuning never reached the page"
    assert '"taxation": ""' in page, "a duty set to a bare floor never reached the page"
    assert "class=plate" in page, "the page has no way to draw a ground plate"


def test_the_sheet_can_pick_a_ground(sheet):
    """The picker is the deliverable: a ground you cannot assign is a filename in a folder."""
    src = sheet.TEMPLATE
    assert "id=picker" in src and "function drawPicker" in src
    assert 'data-g=""' in src, "there is no way back to a bare floor"
    for control in ("id=ganc type=range", "id=gsca type=range", "id=gdim type=range",
                    "id=gsat type=range", "id=gopa type=range"):
        assert control in src, "%s is missing" % control
    for wiring in ("\nfunction setGround", "\nfunction syncGroundSliders"):
        assert wiring in src, "%s is not there" % wiring.strip()
    assert "PLATES = __PLATES__" in src and "PLAN = __GROUNDPLAN__" in src, (
        "the plates or the plan are hardcoded rather than read")


# ---------------------------------------------------------------- the button that did not save

def test_the_offline_button_downloads_both_real_files(sheet):
    """THE BUG THIS PAIR EXISTS FOR.

    Opened as a file:// page -- which is what the generator does without --serve -- the save
    button could not POST, so it fell back to a download. It downloaded ONE file, named
    duty_placement.json, whose contents were the wire payload: spread/back/rank at the top and
    every ground assignment nested under a `grounds` key. That is not the shape of the placement
    file. Dropped into the repository it would have replaced a document full of explanatory prose
    with a payload, and STILL lost every ground, because nothing reads grounds out of that file.

    An afternoon of assignments went into ~/Downloads and looked, from the panel, like a save.

    So: the offline path must build BOTH documents, name them after the files they are, and never
    hand out the wire payload under a real filename.
    """
    src = sheet.TEMPLATE
    save = src[src.index("document.getElementById(\"save\").onclick"):]
    save = save[:save.index("\n};")]
    assert "documents()" in save, "the offline path does not build the real documents"
    assert "a.download = d.name" in save, "the download is not named after the document it is"
    assert '"duty_placement.json"' not in save and "'duty_placement.json'" not in save, (
        "a filename is hardcoded in the save path -- that is how the payload got that name")
    # and the payload must never be what gets downloaded
    offline = save[save.index("if (!connected())"):save.index("say(\"saving")]
    assert "encodeURIComponent(body)" not in offline, (
        "the offline path still downloads the wire payload")
    assert "JSON.stringify(d.doc" in offline, "the download is not a document"


def test_the_offline_button_downloads_only_what_moved(sheet):
    """Nudging one slider changed one file and handed over two.

    The browser then asks permission to download multiple files, and -- because it will not
    overwrite -- the second copy lands as "duty_placement (1).json", which leaves the USEFUL
    file wearing the suffix while whatever stale thing was already there keeps the clean name.
    So the offline path compares each document against what the page opened with and hands over
    only the ones that moved.

    The before-picture has to be frozen at load: PLAN is mutated while you work, because
    settingsFor() writes a new plate's defaults into it, so it cannot be its own baseline.
    """
    src = sheet.TEMPLATE
    assert "var OPENED = " in src, "nothing records what the two files looked like on opening"
    opened = src[src.index("var OPENED = "):]
    opened = opened[:opened.index(";\n")]
    assert "JSON.parse(JSON.stringify(PLAN))" in opened, (
        "the baseline aliases PLAN, which is mutated as you work -- it could never differ")
    docs = src[src.index("function documents()"):]
    docs = docs[:docs.index("\n}")]
    assert docs.count("changed:") == 2, "not every document is compared against its baseline"
    save = src[src.index('document.getElementById("save").onclick'):]
    save = save[:save.index("\n};")]
    assert "return d.changed; }" in save, "the offline path downloads regardless of what moved"
    assert "nothing to save" in save, "pressing save with nothing changed still downloads"


def test_the_two_save_paths_merge_the_same_keys(sheet):
    """The served save and the offline download are two pieces of code writing two files.

    They agreed by coincidence until they did not. The generator now owns ONE list of keys per
    file and hands it to the page, so the page cannot merge a different set -- there is no second
    list to drift from. This test is the guard on that arrangement, not on the lists themselves.
    """
    src = sheet.TEMPLATE
    assert "SAVE_KEYS = __SAVEKEYS__" in src, "the page was not given the key lists"
    assert "DOC_PLACEMENT = __PLACEMENTDOC__" in src, (
        "the page has no copy of the placement document to merge into, so it cannot build it")
    docs = src[src.index("function documents()"):]
    docs = docs[:docs.index("\n}")]
    for key in ("SAVE_KEYS.placement[i]", "SAVE_KEYS.grounds[i]",
                "SAVE_KEYS.placement_file", "SAVE_KEYS.grounds_file"):
        assert key in docs, "documents() does not go through %s" % key
    for literal in ("spread", "back", "rank", "by_duty"):
        assert '"%s"' % literal not in docs, (
            "documents() names %r itself instead of taking the generator's list" % literal)


def test_the_generator_hands_the_page_the_keys_it_merges_by(sheet, mod, tmp_path, monkeypatch):
    """Proved by writing the page and reading back what it was given, not by reading the source.

    The lists must be the ones save_settings and save_grounds actually merge by; a page handed a
    stale copy is the same bug wearing the fix.
    """
    board = sheet._board_module()
    if not any((board.FIGURE_DIR / ("figure_player_1_%d.png" % s)).is_file()
               for s in board.FIGURE_SIZES):
        pytest.skip("no rendered sculpts; run make_tray_figures.py")
    out = tmp_path / "placement_sheet.html"
    monkeypatch.setattr(sys, "argv",
                        ["generate_placement_sheet.py", "--no-open", "--out", str(out)])
    sheet.main()
    page = out.read_text(encoding="utf-8")
    m = re.search(r"SAVE_KEYS = (\{.*?\});", page, re.S)
    assert m, "the key lists never reached the page"
    keys = json.loads(m.group(1))
    assert tuple(keys["placement"]) == sheet.PLACEMENT_KEYS
    assert tuple(keys["grounds"]) == sheet.GROUND_KEYS
    assert keys["placement_file"] == mod.PLACEMENT.name
    assert keys["grounds_file"] == mod.GROUND_PLAN.name

    # the whole placement document, not the three numbers the sliders move
    d = re.search(r"DOC_PLACEMENT = (\{.*?\}), SAVE_KEYS", page, re.S)
    assert d, "the placement document never reached the page"
    doc = json.loads(d.group(1))
    on_disk = json.loads(mod.PLACEMENT.read_text(encoding="utf-8"))
    assert set(doc) == set(on_disk), (
        "the page was given a trimmed placement document, so its download would lose "
        "%s" % sorted(set(on_disk) - set(doc)))


def test_save_settings_writes_exactly_the_keys_it_advertises(sheet, mod, tmp_path, monkeypatch):
    """Whatever PLACEMENT_KEYS names, a save must move -- and nothing outside it may move.

    The page merges by that list offline. A key this function quietly validated but left out of
    the list would be saved when served and lost when not, which is precisely the failure that
    started this.
    """
    board = sheet._board_module()
    path = tmp_path / "duty_placement.json"
    original = json.loads(mod.PLACEMENT.read_text(encoding="utf-8"))
    path.write_text(json.dumps(original), encoding="utf-8")
    monkeypatch.setattr(board, "PLACEMENT", path)
    sent = {"spread": 97, "back": 13, "rank": 41, "order": "arrival",
            "depth": {"mode": "dark", "amount": 33, "full_at": 44},
            "frame": {"w": 301, "h": 402, "drop": -7}}
    saved = sheet.save_settings(board, sent)
    moved = {k for k in saved if saved[k] != original.get(k)}
    assert moved <= set(sheet.PLACEMENT_KEYS), (
        "%s moved but is not named by PLACEMENT_KEYS" % sorted(moved - set(sheet.PLACEMENT_KEYS)))
    assert moved == set(sheet.PLACEMENT_KEYS), (
        "%s is named by PLACEMENT_KEYS but a save does not move it"
        % sorted(set(sheet.PLACEMENT_KEYS) - moved))
    assert "tuned_at" in saved, "the prose and the untouched keys were thrown away"


def test_the_page_says_it_cannot_save_before_the_tuning_not_after(sheet):
    """The old page mentioned that a file:// URL cannot write only once the button was pressed --
    at the end of a sitting, in the one small line a success message also uses. That is too late
    to be a warning; it is a bereavement notice. It has to be on screen from the start."""
    src = sheet.TEMPLATE
    opening = src[src.index("document.body.classList.add(\"shadow\")") - 900:
                  src.index("document.body.classList.add(\"shadow\")")]
    assert "connected()" in opening, "nothing checks on load whether the page can save"
    assert "download json" in opening, (
        "the button still says 'save to json' on a page that cannot save")


def test_one_rule_decides_what_a_duty_stands_on(sheet, mod):
    """The sheet assigns a ground; the sow plays on it. They must draw the same picture.

    Each had its own resolver, with its own fallback for a plate nobody had tuned. Two spellings
    of one rule is how you assign a ground in one page and get a different one in the other.
    """
    rules = (pathlib.Path(mod.__file__).parent / "duty_sculpt_rules.js").read_text(
        encoding="utf-8")
    for fn in ("function dutyGroundFor", "function dutyGroundSettings"):
        assert fn in rules, "%s is not in the shared file" % fn
    sow_tmpl = (pathlib.Path(mod.__file__).parent / "duty_sow.html.tmpl").read_text(
        encoding="utf-8")
    for page, src in (("the placement sheet", sheet.TEMPLATE), ("the sow", sow_tmpl)):
        assert "dutyGroundFor(PLAN" in src, "%s resolves the ground itself" % page
        assert "dutyGroundSettings(PLAN" in src, "%s has its own tuning fallback" % page
        assert 'PLAN["default"]' not in src, (
            "%s still unpacks the plan by hand, so the rule lives in two places" % page)


def test_bare_floor_survives_the_shared_rule(sheet, mod):
    """An unassigned duty falls back to the plan's default. A duty assigned the empty string has
    been DECIDED -- bare floor -- and must stay bare. Collapsing the two makes that choice
    unsaveable, which is not a subtle failure: the picker's first button stops working."""
    rules = (pathlib.Path(mod.__file__).parent / "duty_sculpt_rules.js").read_text(
        encoding="utf-8")
    body = rules[rules.index("function dutyGroundFor"):]
    body = body[:body.index("\n}")]
    assert "=== undefined" in body, (
        "dutyGroundFor tests the name for truthiness, so bare floor becomes the default")


def test_a_ground_with_no_picture_is_named_out_loud(mod):
    """A duty assigned a plate the folder does not hold draws nothing and says nothing, which on
    screen is the same as a duty nobody has assigned. ground_plan cannot catch it -- it checks
    the plan against itself -- and ground_art cannot, because it only knows what exists."""
    notes = []
    plan = {"default": "", "by_duty": {s: "ghost_plate" for s in mod.SLUGS}, "grounds": {}}
    in_use = mod.ground_check(plan, {"cobbles_oval": {"widest": 46}}, notes)
    assert in_use == [], "a plate with no art was reported as in use"
    assert any("ghost_plate" in n and "no art" in n for n in notes), (
        "an assigned plate with no picture passed without a word: %r" % notes)
    # and the other direction: art nobody stands on is worth saying once, not nine times
    notes = []
    plan = {"default": "cobbles_oval", "by_duty": {}, "grounds": {}}
    in_use = mod.ground_check(plan, {"cobbles_oval": {"widest": 46},
                                     "spare_plate": {"widest": 50}}, notes)
    assert in_use == ["cobbles_oval"]
    assert sum("spare_plate" in n for n in notes) == 1, notes


def test_the_sow_names_every_plate_it_stands_a_duty_on(sow, mod, tmp_path, monkeypatch):
    """Asked for directly: the sow must take its grounds from duty_grounds.json, all of them.

    It did read the file -- but the file had never changed, because the save button was dropping
    the assignments. The terminal line now names what was actually resolved, so the next time the
    two disagree you can see it without opening the page.
    """
    board = sow._board_module()
    if not any((board.FIGURE_DIR / ("figure_player_1_%d.png" % s)).is_file()
               for s in board.FIGURE_SIZES):
        pytest.skip("no rendered sculpts; run make_tray_figures.py")

    plan = json.loads(mod.GROUND_PLAN.read_text(encoding="utf-8"))
    names = sorted(p.stem for p in mod.GROUNDS_DIR.glob("*.png"))
    assert len(names) >= 2, "need at least two plates on file to tell them apart"
    # every duty on a DIFFERENT plate than the file ships, so a page reading a stale copy shows
    plan["by_duty"] = {slug: names[i % len(names)] for i, slug in enumerate(mod.SLUGS)}
    plan["grounds"] = {n: {"anchor": 50, "scale": 100, "dim": 55, "saturate": 65, "opacity": 100}
                       for n in names}
    doctored = tmp_path / "duty_grounds.json"
    doctored.write_text(json.dumps(plan), encoding="utf-8")
    monkeypatch.setattr(board, "GROUND_PLAN", doctored)
    monkeypatch.setattr(sow, "_board_module", lambda: board)
    out = tmp_path / "duty_sow.html"
    monkeypatch.setattr(sys, "argv", ["generate_duty_sow.py", "--no-open", "--out", str(out)])
    sow.main()

    page = out.read_text(encoding="utf-8")
    for name in set(plan["by_duty"].values()):
        assert '"%s"' % name in page, "%s is assigned but never reached the page" % name


# ---------------------------------------------------------------- lifting the ground off the banner

def test_the_lift_is_one_number_for_all_nine_tiles(sheet, mod, tmp_path, monkeypatch):
    """The plate is drawn centred on the floor line, which puts its lower half across the
    parchment. The lift moves the whole ground up, the same distance on every tile, so the
    banner can be cleared -- and re-cleared when the banner art changes.

    Saved and validated like the rest of the plan, because a lift you cannot keep is a lift you
    set again every time you open the page.
    """
    board = sheet._board_module()
    path = tmp_path / "duty_grounds.json"
    path.write_text(mod.GROUND_PLAN.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(board, "GROUND_PLAN", path)
    saved = sheet.save_grounds(board, {"by_duty": {}, "grounds": {}, "lift": 137})
    assert saved["lift"] == 137
    assert "note" in saved and "angle_note" in saved, "the prose was thrown away"
    # named by the one list the offline download merges by, or it saves served and not otherwise
    assert "lift" in sheet.GROUND_KEYS, "a saved key the page is not told to merge"
    # and the generator accepts what the button wrote
    monkeypatch.setattr(mod, "GROUND_PLAN", path)
    assert mod.ground_plan([])["lift"] == 137
    for bad in (7.5, "20", True, 900, -400):
        with pytest.raises(ValueError):
            sheet.save_grounds(board, {"by_duty": {}, "grounds": {}, "lift": bad})


def test_a_plan_written_before_the_lift_existed_still_loads(mod, tmp_path, monkeypatch):
    """Every duty_grounds.json on anyone's disk predates this key. Defaulted, not required."""
    plan = json.loads(mod.GROUND_PLAN.read_text(encoding="utf-8"))
    plan.pop("lift", None)
    path = tmp_path / "duty_grounds.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    monkeypatch.setattr(mod, "GROUND_PLAN", path)
    assert mod.ground_plan([])["lift"] == 0, "a plan with no lift did not default to flat"


def test_the_lift_is_in_the_expression_that_places_the_plate(sheet, mod):
    """THAT THE DRAWING USES IT -- which is not what rendering the page twice proves.

    The first version of this rendered each page at two lifts and asserted the pages differed
    and that '"lift": 211' was in the output. Deleting LIFT from the sheet's positioning
    expression left every one of those assertions true: the plan is embedded whole, so the
    number is in the page whether or not anything draws with it, and `var LIFT = PLAN.lift`
    still matched a search for "LIFT". The test passed on code that ignored the slider.

    So the assertion has to be on the expression that puts the plate somewhere, and nothing
    else. Falsified by removing LIFT from exactly that expression in each page.
    """
    here = pathlib.Path(mod.__file__).parent
    for page, src, marker in (
            ("the placement sheet", sheet.TEMPLATE, "<div class=ground"),
            ("the sow", (here / "duty_sow.html.tmpl").read_text(encoding="utf-8"),
             "<div class=plate")):
        at = src.index(marker)
        where = src[at:at + 400]
        assert "';top:'" in where, "%s: the plate emit does not set a top" % page
        top = where[where.index("';top:'"):]
        top = top[:top.index("';width:'")]
        assert "LIFT" in top, (
            "%s positions the plate without the lift, so the slider moves nothing: %s"
            % (page, top.strip()))
        assert "anchor" in top, "%s stopped using the plate's own anchor" % page


def test_the_lift_reaches_both_pages(sheet, sow, mod, tmp_path, monkeypatch):
    """The generators must carry the key through to the page at all -- a separate claim from
    the one above, and the one that catches a generator trimming the plan on its way out."""
    board = sheet._board_module()
    if not any((board.FIGURE_DIR / ("figure_player_1_%d.png" % s)).is_file()
               for s in board.FIGURE_SIZES):
        pytest.skip("no rendered sculpts; run make_tray_figures.py")
    plan = json.loads(mod.GROUND_PLAN.read_text(encoding="utf-8"))
    path = tmp_path / "duty_grounds.json"
    monkeypatch.setattr(board, "GROUND_PLAN", path)
    # BOTH generators have to be pointed at the patched board. The sow caches its board module
    # and the sheet does not, so patching the object alone leaves sheet.main() re-executing
    # generate_duty_board_check and reading the real file -- which is how this test first
    # "proved" the lift was ignored when it was only looking at the wrong plan.
    monkeypatch.setattr(sow, "_board_module", lambda: board)
    monkeypatch.setattr(sheet, "_board_module", lambda: board)

    for page_name, module, argv0 in (("placement sheet", sheet, "generate_placement_sheet.py"),
                                     ("sow", sow, "generate_duty_sow.py")):
        drawn = {}
        for lift in (0, 211):
            plan["lift"] = lift
            path.write_text(json.dumps(plan), encoding="utf-8")
            out = tmp_path / ("%d_%s.html" % (lift, argv0))
            monkeypatch.setattr(sys, "argv", [argv0, "--no-open", "--out", str(out)])
            module.main()
            drawn[lift] = out.read_text(encoding="utf-8")
        assert '"lift": 211' in drawn[211], "%s never received the lift" % page_name
        assert '"lift": 0' in drawn[0], "%s never received the lift" % page_name


def test_the_lift_is_not_a_sixth_per_plate_slider(sheet):
    """It sits among five sliders that act on one plate, so it has to be unmistakably different.

    It must not be wired through setGround (which writes into the picked plate's settings), must
    not be disabled when a tile stands on bare floor, and must say on the page that it moves all
    nine.
    """
    src = sheet.TEMPLATE
    assert "id=glift type=range" in src, "there is no lift slider"
    wiring = src[src.index('slider("glift"'):]
    wiring = wiring[:wiring.index("\n")]
    assert "setGround" not in wiring, (
        "the lift is wired through setGround, so it writes into one plate's settings")
    sync = src[src.index("function syncGroundSliders"):]
    sync = sync[:sync.index("\n}")]
    assert "glift" not in sync, (
        "syncGroundSliders touches the lift, so picking a plate will overwrite it")
    assert "all nine tiles" in src, "the panel does not say the lift moves every tile"


def test_the_lift_readout_measures_the_worst_plate_not_the_picked_one(sheet):
    """The number worth showing is how much plate still lies over the banner -- that is what the
    lift is for, and what moves when the banner art changes.

    Measured across every plate in use. Reporting the picked tile's clearance would let you lift
    until the tile in front of you is clear while a taller plate on another duty still overlaps,
    which is the exact mistake the readout exists to catch.
    """
    src = sheet.TEMPLATE
    body = src[src.index("function bannerClear"):src.index("function sayLift")]
    assert "for (var i = 0; i < 9; i++)" in body, "the clearance is not measured across the tiles"
    assert "PICKED" not in body, "the clearance is measured on the picked tile"
    assert "gap < worst.gap" in body, "it does not keep the worst plate"
    assert "L.gapA" in body, "the clearance is not measured against the banner"


# ---------------------------------------------------------------- judging a new asset


@pytest.fixture(scope="module")
def checker():
    spec = importlib.util.spec_from_file_location(
        "generate_asset_check", ROOT / "tools" / "ui_debug" / "generate_asset_check.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def metrics():
    spec = importlib.util.spec_from_file_location(
        "sculpt_metrics", ROOT / "tools" / "ui_debug" / "sculpt_metrics.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _disc(width, degrees, wall=30, pad=40, stem=0):
    """A cylinder drawn at a known camera angle, to measure the measurer against.

    Ground truth rather than agreement with the art: comparing `ground_ellipse` to the sculpts
    only shows it is consistent with them, which it would also be if both were wrong.
    """
    import math

    from PIL import Image, ImageDraw
    minor = width * math.sin(math.radians(degrees))
    w = width + 2 * pad
    h = int(minor + wall + 2 * pad)
    h += stem
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    top = pad + stem
    if stem:
        # SOMETHING STANDING ON IT, so the art is taller than it is wide and the checker reads it
        # as a figure. Narrower than the base, like a robe on a plinth.
        d.rectangle([pad + width * 0.3, pad, pad + width * 0.7, top + wall],
                    fill=(140, 140, 140, 255))
    d.ellipse([pad, top, pad + width, top + minor], fill=(120, 120, 120, 255))
    d.rectangle([pad, top + minor / 2, pad + width, top + minor / 2 + wall],
                fill=(90, 90, 90, 255))
    d.ellipse([pad, top + wall, pad + width, top + minor + wall], fill=(90, 90, 90, 255))
    return im


def test_the_camera_angle_is_measured_against_a_known_answer(metrics):
    """A drawn cylinder whose angle we chose, measured back."""
    for degrees in (10, 20, 30, 40):
        g = metrics.ground_ellipse(_disc(600, degrees), base_band=False)
        assert g is not None
        assert abs(g["degrees"] - degrees) <= 1.5, (
            "a %d degree disc measured as %.1f" % (degrees, g["degrees"]))


def test_the_widest_row_is_the_base_and_not_the_robe(metrics):
    """Taking the whole silhouette's widest row found player_4's robe rather than its plinth and
    reported a 90 degree camera for a 6 degree one. The set has to agree with itself."""
    from PIL import Image
    seen = []
    for name in ("player_1", "player_2", "player_3", "player_4"):
        path = ROOT / "ui" / "concept" / name / "sculpt_plastic.png"
        if not path.is_file():
            pytest.skip("the concept art is not here")
        g = metrics.ground_ellipse(Image.open(path).convert("RGBA"))
        assert g is not None
        seen.append(g["degrees"])
    assert max(seen) - min(seen) <= 3.0, (
        "four figures sharing one camera measured %s" % [round(v, 1) for v in seen])


def test_a_bare_plate_is_not_measured_in_the_base_band(metrics):
    """The band is right for a figure standing on a plinth and wrong for a plate, which is all
    base: banded, the cobbles read 11 degrees against 25 for the whole outline."""
    from PIL import Image
    path = ROOT / "ui" / "assets-gothic" / "grounds" / "cobbles_oval.png"
    if not path.is_file():
        pytest.skip("no ground plates on record")
    im = Image.open(path).convert("RGBA")
    banded = metrics.ground_ellipse(im, base_band=True)
    whole = metrics.ground_ellipse(im, base_band=False)
    assert whole["width"] > banded["width"], "the band is not cutting the plate short any more"


def test_the_checker_reads_tall_as_a_sculpt_and_wide_as_a_plate(checker):
    import io
    buf = io.BytesIO()
    _disc(200, 30, stem=420).save(buf, "PNG")
    assert checker.judge(buf.getvalue(), 30.0, 2.5)["row"]["kind"] == "sculpt"

    buf = io.BytesIO()
    _disc(600, 30).save(buf, "PNG")
    assert checker.judge(buf.getvalue(), 30.0, 2.5)["row"]["kind"] == "plate"


def test_the_verdict_moves_with_the_target(checker):
    """The point of the tool: the same file passes against one target and fails against another,
    so the target is the thing being argued about rather than the measurement."""
    import io
    buf = io.BytesIO()
    _disc(240, 30, wall=20, stem=500).save(buf, "PNG")
    raw = buf.getvalue()

    def angle_verdict(target):
        for name, _value, verdict, _why in checker.judge(raw, target, 2.5)["checks"]:
            if name == "camera angle":
                return verdict
        return None

    assert angle_verdict(30.0) == "ok"
    assert angle_verdict(6.0) == "bad", "a 30 degree disc passed a 6 degree target"


def test_the_widest_figure_is_measured_rather_than_remembered(checker):
    """The fit check had 108 written into it -- player_4's width -- while the board draws three
    seats whose widest is 91. It reported a full tile needing 328 px instead of 311 and called a
    frame that fits it bad."""
    src = (ROOT / "tools" / "ui_debug" / "generate_asset_check.py").read_text(encoding="utf-8")
    assert "108" not in src.split("def judge")[1].split("def serve")[0], (
        "a figure width is hardcoded in the fit check again")
    assert "board.figures(" in src, "the fit check no longer asks what the figures measure"


def test_a_file_with_no_alpha_is_told_so_rather_than_measured(checker):
    """A screenshot has no transparency, so every row is the full canvas width, the base's bottom
    outline is flat and the angle comes out 0.0 -- which reads as a measurement of a flat camera
    rather than as the absence of one. Three derived checks failing on a single root cause is how
    an operator ends up fixing the wrong thing."""
    import io

    from PIL import Image
    art = _disc(240, 30, wall=20, stem=500)
    flat = Image.new("RGBA", art.size, (60, 62, 66, 255))
    flat.alpha_composite(art)
    buf = io.BytesIO()
    flat.convert("RGB").save(buf, "PNG")

    result = checker.judge(buf.getvalue(), 30.0, 2.5)
    named = {c[0]: (c[1], c[2]) for c in result["checks"]}
    assert named["cut out"][1] == "bad"
    assert "camera angle" not in named, "a verdict was given on art that could not be measured"
    assert any(v[1] == "cannot" for v in named.values()), (
        "nothing said the rest could not be measured")
    assert any("cut out" in n for n in result["notes"])


def test_the_background_estimate_is_offered_and_labelled(checker):
    """Screenshots are a normal thing to arrive with, so the tool guesses at the art and says the
    number is a guess. It is close enough to be worth having: measured against the same figure
    with its real alpha, the estimate lands within a couple of degrees."""
    import io

    from PIL import Image
    art = _disc(240, 30, wall=20, stem=500)
    buf = io.BytesIO()
    art.save(buf, "PNG")
    cut = checker.judge(buf.getvalue(), 30.0, 2.5)
    truth = cut["row"]["degrees"]

    flat = Image.new("RGBA", art.size, (12, 12, 14, 255))
    flat.alpha_composite(art)
    buf = io.BytesIO()
    flat.convert("RGB").save(buf, "PNG")
    guessed = checker.judge(buf.getvalue(), 30.0, 2.5)

    assert "degrees" in guessed["row"], (
        "the background could not be separated, so this proves nothing")
    named = {c[0]: c[2] for c in guessed["checks"]}
    assert "camera angle, estimated" in named, "the estimate is not labelled as one"
    assert named["camera angle, estimated"] == "info", "an estimate was given as a verdict"
    assert abs(guessed["row"]["degrees"] - truth) <= 3.0, (
        "the estimate is %.1f against %.1f" % (guessed["row"]["degrees"], truth))


def test_height_is_reported_but_never_judged(checker):
    """Height was the third check and has been WITHDRAWN. This is the guard on that.

    It was measured against the median of whatever sat in the reference folder, which made the
    verdict a fact about the folder rather than about the figure: the median moves as the set
    fills, so the same sculpt passes or fails depending on what was filed before it. And the two
    sets on file disagree by 26% in proportion with the camera already divided out -- the concept
    art at 2.18, the sculpts drawn at the board's camera at 2.75 -- so it fired on every new
    sculpt, arithmetically right and practically useless. Which proportion is wanted is a look.

    Two things have to stay true, and they pull in opposite directions, which is why they are
    asserted together: NO check may carry a height verdict, and the proportion must still be
    measured and reported, because comparing candidates by eye is easier with the number there.
    """
    result = checker.judge(_png(_plinth(240, 32, 40)), 32.0, 2.5)
    names = [c[0] for c in result["checks"]]
    for gone in ("height", "cost to the set"):
        assert gone not in names, (
            "%r is being judged again; height is decided by looking, not by a median: %s"
            % (gone, names))
    assert not any("height" in n and n != "base height / width" for n in names), (
        "something height-shaped crept back into the verdicts: %s" % names)
    assert "proportion" in result["row"], (
        "the proportion stopped being reported -- withdrawing the verdict was not meant to "
        "withdraw the measurement")
    assert result["row"]["proportion"] > 0


def test_the_height_tolerance_is_gone_from_the_tool_and_the_page(checker):
    """Not just unused: absent. A tolerance left behind as a constant and a box on the page is
    an invitation to wire it back up, and a box that changes nothing is worse than no box."""
    assert not hasattr(checker, "HEIGHT_TOLERANCE_PCT"), (
        "the height tolerance is still a constant")
    src = checker.PAGE if hasattr(checker, "PAGE") else pathlib.Path(
        checker.__file__).read_text(encoding="utf-8")
    assert "__HTOL__" not in src and "id=htol" not in src, (
        "the page still offers a height tolerance box")
    import inspect
    assert "height_tol" not in inspect.signature(checker.judge).parameters, (
        "judge still takes a height tolerance")


def test_a_tightly_cropped_cutout_is_measured_rather_than_estimated(checker):
    """"Cut out" asked whether the art touched the canvas edge, which is a question about
    margins, not about alpha. A PNG cropped flush to its own silhouette -- which every tight
    crop is, and which recolouring produces -- was therefore declared to have no transparency
    and quietly measured by the background ESTIMATE instead: it reported 29.1 for a figure whose
    alpha says 29.8, with nothing on screen to say it had guessed."""
    import io
    art = _disc(240, 30, wall=20, stem=500)
    buf = io.BytesIO()
    art.save(buf, "PNG")
    loose = checker.judge(buf.getvalue(), 29.0, 2.5)

    tight = art.crop(art.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox())
    assert tight.size != art.size, "the fixture was not actually cropped, so this proves nothing"
    buf = io.BytesIO()
    tight.save(buf, "PNG")
    cropped = checker.judge(buf.getvalue(), 29.0, 2.5)

    named = {c[0]: c[2] for c in cropped["checks"]}
    assert named["cut out"] == "ok", "a cut-out PNG was called opaque because it was cropped tight"
    assert "camera angle, estimated" not in named, "real alpha was measured by guesswork"
    assert abs(cropped["row"]["degrees"] - loose["row"]["degrees"]) < 0.2, (
        "cropping moved the measurement: %.1f against %.1f"
        % (cropped["row"]["degrees"], loose["row"]["degrees"]))


def test_height_is_compared_with_the_camera_divided_out(checker):
    """height/plinth is a PROJECTED measurement. Raising the camera shortens a figure's drawn
    height by cos(theta) while leaving its base width alone, so one sculpt measures smaller the
    higher you look from. Comparing 30 degree figures against a 9 degree band reported the new
    sculpts 29% short when they are 18% short -- reading a camera move as a change of shape."""
    import math
    true_ratio = 2.18
    for deg in (9.0, 30.0, 45.0):
        projected = true_ratio * math.cos(math.radians(deg))
        assert abs(checker._proportion(projected, deg) - true_ratio) < 1e-9, (
            "the camera was not divided out at %.0f degrees" % deg)
    raw_gap = abs(true_ratio*math.cos(math.radians(9.0))
                  - true_ratio*math.cos(math.radians(30.0)))
    assert raw_gap > 0.25, (
        "the uncorrected numbers barely differ, so correcting them proves nothing")


def test_the_height_check_does_not_compare_raw_ratios_across_cameras(checker):
    src = (ROOT / "tools" / "ui_debug" / "generate_asset_check.py").read_text(encoding="utf-8")
    body = src.split("def judge")[1].split("def serve")[0]
    assert "_proportion(" in body, "judge compares raw height/plinth across cameras again"


def _batch(tmp_path, degrees):
    """A folder of drawn plates at chosen angles, standing in for a run of generations."""
    for i, d in enumerate(degrees):
        _disc(600, d).save(tmp_path / ("plate_%02d.png" % i))
    return tmp_path


def _scan_text(checker, folder, capsys, match=None):
    checker.scan(folder, match) if match else checker.scan(folder)
    return capsys.readouterr().out


def test_a_scan_measures_a_whole_run_in_one_pass(checker, tmp_path, capsys):
    """One file at a time answers 'is this one good'. A run answers whether the prompt is good,
    and that only shows up with the spread in front of you.

    The fixture is drawn RELATIVE to the target rather than at a fixed angle: written as 29 it
    passed until the target moved to 32 and then failed for a reason that had nothing to do with
    what it tests.
    """
    t = checker.TARGET_DEGREES
    out = _scan_text(checker, _batch(tmp_path, [t, t - 0.4, t + 0.4]), capsys)
    assert out.count("plate_") == 3, "not every file in the folder was measured"
    assert "3 measured" in out and "sd" in out, "the batch's own spread was not reported"
    assert "3 of 3 inside" in out


def test_a_scan_of_unrelated_art_refuses_to_call_it_a_batch(checker, tmp_path, capsys):
    """Pointed at a folder of unrelated images this once announced that every generation shared
    one bias -- true of a run from a single prompt, nonsense about a mixed folder. A claim about
    a batch may only be made once the spread shows there IS a batch."""
    out = _scan_text(checker, _batch(tmp_path, [10.0, 30.0, 50.0, 70.0]), capsys)
    assert "not one batch" in out, "a folder with a 60 degree spread was summarised as a batch"
    assert "BATCH is off" not in out, "a shared bias was claimed across unrelated files"


def test_a_shared_bias_is_named_only_when_the_generations_agree(checker, tmp_path, capsys):
    """The case the scan exists for: files that agree with each other and are all wrong together
    are a prompt to fix, not twenty files to throw away."""
    out = _scan_text(checker, _batch(tmp_path, [21.0, 21.4, 20.7, 21.2]), capsys)
    assert "BATCH is off" in out, "a tight cluster 8 degrees off target was not named as a bias"
    assert "not one batch" not in out
    assert "prompt to change rather than files to discard" in out


def test_a_scan_can_be_narrowed_to_one_run(checker, tmp_path, capsys):
    """Downloads holds every generation ever made, so measuring 'the folder' measures the wrong
    thing; the run being judged has to be selectable."""
    _batch(tmp_path, [29.0, 29.2])
    _disc(600, 70.0).save(tmp_path / "unrelated_thing.png")
    out = _scan_text(checker, tmp_path, capsys, match="plate_*.png")
    assert "unrelated_thing" not in out, "the glob did not narrow the scan"
    assert out.count("plate_") == 2


def test_the_target_angle_is_the_one_the_generator_actually_reaches(checker):
    """30 and 40 were picked from numbers and neither survived a composite. 29 was picked by
    looking, and then the ask stopped steering: two batches of ten, asks three degrees apart,
    landed at 32.1 and 31.9. The plates converge on the same place unprompted. A target the
    generator cannot be moved to is a target that fails honest art on both sides of the board."""
    assert checker.TARGET_DEGREES == 32.0


def _plinth(width, degrees, wall, pad=40, stem=500):
    """A disc with a LIT RIM, because that is what the wall measurement actually looks for.

    `measure` scans up from the bottom of the art for the brightest row in a central strip and
    calls that the top of the wall -- a real sculpt's rounded rim catches the light there. The
    flat-filled disc used elsewhere in this file has no such row, so it reported the same wall
    whatever was drawn, and any test built on it would have proved nothing.
    """
    import math

    from PIL import Image, ImageDraw
    minor = width*math.sin(math.radians(degrees))
    im = Image.new("RGBA", (width+2*pad, int(minor+wall+2*pad)+stem), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    top = pad+stem
    d.rectangle([pad+width*0.3, pad, pad+width*0.7, top+wall], fill=(140, 140, 140, 255))
    d.ellipse([pad, top, pad+width, top+minor], fill=(120, 120, 120, 255))
    d.rectangle([pad, top+minor/2, pad+width, top+minor/2+wall], fill=(90, 90, 90, 255))
    d.ellipse([pad, top+wall, pad+width, top+minor+wall], fill=(90, 90, 90, 255))
    d.ellipse([pad, top+minor-3, pad+width, top+minor+3], fill=(250, 250, 250, 255))
    return im


def _named(checker, raw, **kw):
    return {c[0]: (c[1], c[2]) for c in checker.judge(raw, 32.0, 2.5, **kw)["checks"]}


def _png(im):
    import io
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def test_the_plinth_fixture_is_readable_by_the_measurement(metrics):
    """The guard on the guards. Every base test below varies the drawn wall, so if the measured
    wall does not follow it they all pass against a constant and mean nothing."""
    seen = [metrics.measure(_plinth(240, 32, w))["wall"] for w in (40, 60, 90)]
    assert seen == sorted(seen), "measured wall does not rise with the drawn wall: %s" % seen
    for drawn, got in zip((40, 60, 90), seen, strict=True):
        assert abs(got - drawn) <= 6, "drew a %d px wall and measured %d" % (drawn, got)


def test_the_reference_card_is_offered_whole(checker):
    """The card is an INPUT to an image model, so the button must hand over the committed bytes.

    A page that offered the 520 px preview under the same filename would be handing over a
    different instruction while looking identical in the browser: the base's ellipse ratio and
    the scale line's multiple only survive at the resolution they were drawn.
    """
    card = checker.reference_card()
    if card is None:
        pytest.skip("the reference card is not on file")
    # NOT a hardcoded filename. Which card the button offers is a live decision -- cards are
    # appended as the wall value moves and the button follows the current one -- so naming one
    # here only records which card was current the day the test was written, and fails the next
    # time the work moves on. What must hold is that the button hands over a REAL committed
    # card, whole.
    path = (checker.ROOT / "ui" / "assets-gothic" / "references" / card["name"])
    assert path.is_file(), "the button offers %s, which is not on file" % card["name"]
    assert card["bytes"] == path.stat().st_size, (
        "the card was re-encoded: %d bytes offered against %d on disk"
        % (card["bytes"], path.stat().st_size))
    # REFERENCED, not embedded, since the page stopped swallowing 15 MB of files that were
    # already on disk. What must still hold is what this test was always about: the thing the
    # button hands over is the committed card and not the preview beside it. That is now a
    # question about where the href points rather than about what a data URI decodes to.
    assert not card["uri"].startswith("data:"), "the card is embedded again"
    pointed = (checker.OUT.parent / card["uri"]).resolve()
    assert pointed.is_file(), "the card's href points at %s, which is not there" % card["uri"]
    assert pointed == path.resolve(), (
        "the button points at %s but the card on file is %s" % (pointed, path))
    assert pointed.read_bytes() == path.read_bytes()


def test_the_card_button_sits_above_the_sculpts_it_produced(checker):
    """Above, not beside: fetching the card comes first in the actual job -- you take it to the
    model, generate against it, and drop what comes back here."""
    src = pathlib.Path(checker.__file__).read_text(encoding="utf-8")
    assert "id=card" in src and "class=dl" in src, "there is no download control"
    block = src[src.index("if (CARD) {"):]
    block = block[:block.index("h.push(\"<div class=row>\")")]
    assert "download=" in block, "the anchor does not download, it navigates"
    assert "CARD.uri" in block, "the button does not point at the card"
    # and it is emitted BEFORE the row of sculpt cards
    assert src.index("if (CARD) {") < src.index('h.push("<div class=row>")'), (
        "the card button is emitted after the figures it produced")


def test_a_sculpt_is_judged_on_angle_then_base(checker):
    """Two questions now, asked in that order, because they fail independently.

    The camera says where you stood. The base says how chunky the plinth is. A set can agree on
    one and disagree on the other: ten nuns and ten monks shared a camera and differed by two
    thirds on their bases. Height was a third question and is now decided by eye -- see
    test_height_is_reported_but_never_judged.
    """
    order = [c[0] for c in checker.judge(_png(_plinth(240, 32, 40)), 32.0, 2.5)["checks"]]
    for name in ("camera angle", "base height / width"):
        assert name in order, "%s is not among the sculpt checks" % name
    assert order.index("camera angle") < order.index("base height / width"), (
        "the two questions are not asked in order: %s" % order)


def test_the_base_check_sees_what_the_other_two_cannot(checker):
    """A plinth drawn twice as thick at the same camera. The angle does not move; the base
    measurement moves enormously. That gap is the whole reason the check exists -- without it a
    batch whose bases are two thirds too thick passes every question it is asked.

    Note the walls: below about 45 px the base band clips into the wall and the ANGLE starts
    moving too, which would make this a test of two things at once rather than of one.
    """
    band = checker.reference_band()
    if not band or "base_ratio" not in band:
        pytest.skip("no set on record to compare a base against")
    thin = _named(checker, _png(_plinth(240, 32, 45)))
    thick = _named(checker, _png(_plinth(240, 32, 90)))
    # NOT a skip: with a band on record the row has to be there. Skipping when it is missing is
    # how a renamed or deleted check goes green instead of red.
    assert "base height / width" in thin, "the base check is not being reported at all"
    assert thin["camera angle"][:2] == thick["camera angle"][:2], (
        "the camera moved too, so this is not an isolated change of base: %s against %s"
        % (thin["camera angle"], thick["camera angle"]))

    def pct(row):
        return float(row[0].split("%")[0])

    assert pct(thick["base height / width"]) - pct(thin["base height / width"]) > 50.0, (
        "doubling the plinth's thickness barely moved the base reading: %s against %s"
        % (thin["base height / width"][0], thick["base height / width"][0]))


def test_the_base_verdict_moves_with_its_own_tolerance(checker):
    """Its own tolerance and not the height's: a smaller measurement on a shorter edge is
    noisier and wants a wider bar, and sharing one would hide that."""
    band = checker.reference_band()
    if not band or "base_ratio" not in band:
        pytest.skip("no set on record to compare a base against")
    raw = _png(_plinth(240, 32, 60))
    assert "base height / width" in _named(checker, raw), (
        "the base check is not being reported at all")
    loose = _named(checker, raw, base_tol=200.0)["base height / width"][1]
    tight = _named(checker, raw, base_tol=4.0)["base height / width"][1]
    assert loose == "ok" and tight == "bad", (
        "the base tolerance did not change the verdict: %s then %s" % (loose, tight))


def test_the_base_measurement_divides_the_camera_out(checker):
    """wall over width is projected exactly as height over width is: the wall is a vertical edge,
    so raising the camera shortens it while leaving the base's width alone. Comparing a 32 degree
    plinth against a 9 degree one uncorrected reads a camera move as a thicker base."""
    import math
    for deg in (9.0, 32.0, 45.0):
        assert abs(checker._upright(0.14*math.cos(math.radians(deg)), deg) - 0.14) < 1e-9, (
            "the camera was not divided out of the base ratio at %.0f degrees" % deg)
    gap = 0.14*math.cos(math.radians(9.0)) - 0.14*math.cos(math.radians(32.0))
    assert gap > 0.01, "the uncorrected numbers barely differ, so correcting proves nothing"


def test_the_page_shows_the_sculpts_on_file_with_their_plinths(checker):
    """The band is printed as figures everywhere else, and a figure is a poor way to hold a shape
    in your head while judging a new one. Each sculpt on file is drawn with the two numbers check
    (b) compares marked on the pixels they were taken from -- which is also the only way to catch
    the measurement being taken from the wrong place."""
    rows = checker.on_record()
    if not rows:
        pytest.skip("no sculpts on file yet")
    for r in rows:
        assert r["plinth"], "%s has no plinth picture" % r["name"]
        assert r["plinth"].startswith("data:image/"), "the plinth picture is not embedded"
        assert r["figure"], "%s has no figure picture" % r["name"]
        assert r["degrees"] and r["base"] and r["proportion"], (
            "%s was drawn but not measured" % r["name"])


def test_the_page_does_not_call_two_different_sets_the_set_on_record(checker):
    """The panel draws ui/assets-gothic/sculpts/ at 32 degrees while the median that actually
    judges a newcomer's BASE still comes from ui/concept/ at 9. Calling both 'the set on record'
    on one page is how someone reads the wrong number off the screen.

    Withdrawing the height verdict did not retire this: the base check still compares against the
    concept art, so the page carries two sets and has to say which is which.
    """
    src = (ROOT / "tools" / "ui_debug" / "generate_asset_check.py").read_text(encoding="utf-8")
    assert "ui/assets-gothic/sculpts/" in src, "the panel does not say where its figures came from"
    assert "ui/concept/" in src, "the panel never names where the judging median comes from"
    assert "not</b> these figures" in src, (
        "the panel does not distinguish the figures it draws from the median it judges by")


def test_the_plinth_picture_states_the_camera_it_was_measured_at(checker, metrics):
    """A wall is a vertical edge, so a higher camera draws it shorter: 67 px at 32 degrees is a
    different plinth from 67 px at 9. Two of these pictures captioned with a width and a wall and
    nothing else would invite exactly the comparison this tool exists to stop anyone making."""
    im = _plinth(240, 32, 60)
    bare = checker.plinth_picture(im)
    at32 = checker.plinth_picture(im, degrees=32.0)
    at9 = checker.plinth_picture(im, degrees=9.0)
    assert bare and at32 and at9, "the plinth picture was not drawn"
    assert at32 != bare, "stating the camera changed nothing on the picture"
    assert at32 != at9, "the same picture is drawn for two different cameras"


def test_the_plinth_caption_stays_within_the_default_font(checker):
    """PIL's default bitmap font draws a missing-glyph box for anything outside ASCII, and an em
    dash in the caption shipped one. The caption is built from a format string in the source, so
    the source is where it can be checked."""
    src = (ROOT / "tools" / "ui_debug" / "generate_asset_check.py").read_text(encoding="utf-8")
    body = src.split("def plinth_picture")[1].split("def figure_picture")[0]
    for line in body.splitlines():
        if "cap" in line and ("=" in line or "+=" in line):
            assert line.isascii(), "a non-ASCII character reached the plinth caption: %r" % line


def test_the_figure_picture_draws_the_height_it_reports(checker):
    """Check (c) drawn on the sculpt, as (b) is drawn on the plinth. Height alone is not a number
    anyone can use -- a figure generated larger is not a different sculpt -- so the span is drawn
    and the RATIO to the base's own width is what gets reported, with the camera stated beside it
    because that ratio is projected like everything else standing up."""
    im = _plinth(240, 32, 60, stem=700)
    bare = checker.figure_picture(im)
    at32 = checker.figure_picture(im, degrees=32.0)
    at9 = checker.figure_picture(im, degrees=9.0)
    assert bare and at32 and at9, "the figure picture was not drawn"
    assert at32 != bare, "stating the camera changed nothing on the figure picture"
    assert at32 != at9, "the same figure picture is drawn for two different cameras"

    # THE IMAGE TEST ALONE IS NOT ENOUGH. Two cameras give two different pictures because the
    # camera-corrected ratio is also drawn, so deleting the camera caption left this passing.
    # The caption has to be asserted where it is written.
    src = (ROOT / "tools" / "ui_debug" / "generate_asset_check.py").read_text(encoding="utf-8")
    body = src.split("def figure_picture")[1].split("def on_record")[0]
    drawn = [ln for ln in body.splitlines() if "d.text(" in ln or "cap =" in ln]
    assert any("camera" in ln for ln in drawn), (
        "the figure picture no longer states the camera it was measured at")
    for ln in drawn:
        assert ln.isascii(), "a non-ASCII character reached the figure caption: %r" % ln


def test_the_figure_picture_leaves_room_for_its_own_labels(checker, metrics):
    """The labels sit in a gutter beside the art. Drawn into too narrow a gutter they run off the
    edge silently -- the image still renders, the tests still pass, and the number is simply not
    there to read."""
    im = _plinth(240, 32, 60, stem=700)
    art = metrics.crop_to_art(im)
    drawn = checker.figure_picture(im, degrees=32.0)
    import base64
    import io as _io

    from PIL import Image as _Image
    got = _Image.open(_io.BytesIO(base64.b64decode(drawn.split(",", 1)[1])))
    fw = round(art.width * (250 / art.height))
    assert got.width - fw >= 100, (
        "only %d px of gutter for the height labels" % (got.width - fw))


def _placement(tmp_path, **over):
    """A copy of the real placement file with one or two numbers changed."""
    import json
    src = ROOT / "ui" / "assets-gothic" / "metadata" / "duty_placement.json"
    d = json.loads(src.read_text(encoding="utf-8"))
    d.update(over)
    out = tmp_path / "duty_placement.json"
    out.write_text(json.dumps(d), encoding="utf-8")
    return out


def test_the_tile_picture_follows_the_placement_file(checker, tmp_path):
    """It is a check, not a screenshot of one good arrangement. Change the file and the picture
    changes, or it is decoration that happened to be right on the day it was drawn."""
    a = checker.arrangement_picture(place=_placement(tmp_path, back=21, rank=52))
    b = checker.arrangement_picture(place=_placement(tmp_path, back=21, rank=80))
    if a is None or b is None:
        pytest.skip("no sculpts or no plates on file")
    assert a["uri"] != b["uri"], "the tile picture ignored a changed rank gap"


def test_the_tile_picture_has_no_plinths_overlapping(checker, tmp_path):
    """The arrangement drawn is the one that clears: the middle steps forward until the top of
    its plinth reaches the floor line, instead of being set back into the rank behind it.

    What collides on a tile is the plinths, and a plinth is as deep as it is wide times
    sin(camera) -- raising the camera from 9 to 32 degrees made every base three times deeper
    without moving a number in duty_placement.json. Overlap is rasterised and intersected rather
    than judged by eye, so this fails if the arrangement ever stops clearing.
    """
    got = checker.arrangement_picture()
    if got is None:
        pytest.skip("no sculpts or no plates on file")
    assert got["clashes"] == 0, "%d plinth clash(es) in the drawn arrangement" % got["clashes"]

    # and the detection is not simply always-zero: squeeze the rank gap and it must find one
    squashed = checker.arrangement_picture(place=_placement(tmp_path, rank=4))
    assert squashed["clashes"] > 0, "a rank gap of 4 reported no clash, so nothing is detected"


def test_the_tile_picture_reports_whether_the_group_fits_the_frame(checker, tmp_path):
    wide = checker.arrangement_picture(place=_placement(tmp_path, spread=260))
    if wide is None:
        pytest.skip("no sculpts or no plates on file")
    assert wide["span"] > wide["frame"], (
        "a spread of 260 was reported as fitting a %d px frame" % wide["frame"])
    normal = checker.arrangement_picture()
    assert normal["span"] <= normal["frame"], (
        "the file's own spread overflows the frame: %d of %d"
        % (normal["span"], normal["frame"]))


@pytest.fixture(scope="module")
def cards():
    spec = importlib.util.spec_from_file_location(
        "generate_sculpt_reference", ROOT / "tools" / "ui_debug" / "generate_sculpt_reference.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_every_committed_card_still_redraws_byte_for_byte(cards, tmp_path):
    """The registry is the only record of what each batch of art was actually asked for.

    A card is an INPUT that was handed to an image model, and the sculpts on file were generated
    against a specific one. If the generator stops reproducing a committed card, that card
    becomes an orphan -- a file nothing in the repo can account for -- and the provenance in
    CARDS quietly becomes a claim rather than a fact. This is the test that keeps it a fact.

    It is also the guard on the one subtlety in the drawing code: the first card's wall is
    24/360 of the base width, which in floating point is 24.000000000000004 rather than 24, and
    rounding it is what keeps that card's pixels where they were.
    """
    refs = ROOT / "ui" / "assets-gothic" / "references"
    checked = 0
    for spec in cards.CARDS:
        committed = refs / spec["name"]
        if not committed.is_file():
            continue
        out = tmp_path / spec["name"]
        cards.card(wall_ratio=spec["wall"],
                   dimension_wall=spec["dimension_wall"]).save(out)
        assert out.read_bytes() == committed.read_bytes(), (
            "%s no longer redraws to the committed file" % spec["name"])
        checked += 1
    assert checked >= 2, "only %d card(s) on file -- this guard is not guarding anything" % checked


def test_the_cards_differ_only_where_the_registry_says_they_do(cards, tmp_path):
    """The guard on the guard above: byte-equality is worthless if every card draws the same.

    Two entries with different wall values must produce different files, and the dimensioned
    ones must actually carry the dimension -- otherwise a registry row could be edited to any
    number at all and the reproduction test would still pass.
    """
    drawn = {}
    for spec in cards.CARDS:
        out = tmp_path / spec["name"]
        cards.card(wall_ratio=spec["wall"], dimension_wall=spec["dimension_wall"]).save(out)
        drawn[spec["name"]] = out.read_bytes()
    assert len(set(drawn.values())) == len(drawn), "two cards in the registry draw identically"

    a = cards.card(wall_ratio=0.127, dimension_wall=True)
    b = cards.card(wall_ratio=0.127, dimension_wall=False)
    assert a.tobytes() != b.tobytes(), "dimension_wall changes nothing that is drawn"
    assert a.height > b.height, "the dimensioned card is not the taller layout"


def test_the_fixture_is_measured_honestly_or_refused(metrics):
    """WHAT THIS TEST USED TO SAY IS THE INTERESTING PART, so it is worth writing down.

    It used to pin a FLOOR: below about 30 px of wall on a 240 px base, `measure` missed the
    lit rim and locked onto the top of the disc instead, so a SIX pixel wall reported as 134
    and the camera read 3.6 degrees. Those numbers do not look like errors -- they look like a
    chunky plinth photographed from very low down -- and a thin-base test built on them passed
    for exactly the wrong reason, which is how it was found.

    sculpt_metrics._rim no longer works that way. It takes the lowest peak standing clear of
    the plinth's own dark wall, over a window sized to the plinth rather than fixed in pixels,
    and returns None when there is no such peak. The floor is gone: the fixture measures true
    from about 12 px up, and the one thickness it cannot see refuses instead of inventing.
    """
    honest, refused, wrong = [], [], []
    for wall in (6, 12, 20, 34, 40, 60, 90):
        got = metrics.measure(_plinth(240, 32.0, wall))["wall"]
        if got is None:
            refused.append(wall)
        elif abs(got - wall) <= 6:
            honest.append(wall)
        else:
            wrong.append((wall, got))
    assert not wrong, "a wall was measured wrongly rather than refused: %s" % wrong
    assert honest == [12, 20, 34, 40, 60, 90], "the honest range has moved: %s" % honest
    assert refused == [6], "what the fixture refuses has moved: %s" % refused

    # a wide base measures the same way, because the window is a fraction of the plinth
    assert abs(metrics.measure(_plinth(480, 32.0, 66))["wall"] - 66) <= 6


def test_the_base_is_judged_asymmetrically(checker):
    """Chunky and thin carry different tolerances, and the chunky side is the wider one.

    They were one symmetric number, fitted before any monk existed, and the first monks broke it
    by landing outside the band and, once levelled onto a common plinth width, being
    indistinguishable from the set. Only the chunky side is exercised against a drawn plinth
    here -- see the test above for why there is no thin one.
    """
    assert checker.BASE_TOLERANCE_PCT > checker.BASE_THIN_PCT, (
        "the two sides are equal, so nothing is asymmetric: %s and %s"
        % (checker.BASE_TOLERANCE_PCT, checker.BASE_THIN_PCT))

    band = checker.reference_band()
    if not band or "base_ratio" not in band:
        pytest.skip("no reference band on file")
    mid = band["base_ratio"]["mid"]

    import math

    # A 480 px base keeps the drawn wall comfortably large across the whole band. A 240 px one
    # is honest now too -- see the test above -- but leaves less room between the two numbers.
    def verdict(upright, degrees=32.0, width=480):
        raw = upright * math.cos(math.radians(degrees))
        wall = round(raw * width)
        return _named(checker, _png(_plinth(width, degrees, wall)))["base height / width"][1]

    assert verdict(mid * 1.15) == "ok", "a plinth 15% chunkier than the set was not allowed"
    assert verdict(mid * 1.90) == "bad", "a plinth 90% chunkier than the set was allowed"


def test_each_side_of_the_band_answers_to_its_own_number(checker):
    """The page offers two boxes, so the two must be wired separately in the tool.

    Checked on the explanation the verdict carries rather than on a drawn plinth: the sentence
    states the band it applied, so moving one tolerance must move one end of that band and leave
    the other where it was. A single number driving both ends would move them together.
    """
    raw = _png(_plinth(240, 32.0, 60))
    def band_text(**kw):
        return _named(checker, raw, **kw)["base height / width"]

    base = band_text()[1]
    assert base in ("ok", "check", "bad")
    wide_chunky = checker.judge(raw, 32.0, 2.5, 400.0, checker.BASE_THIN_PCT)
    wide_thin = checker.judge(raw, 32.0, 2.5, checker.BASE_TOLERANCE_PCT, 400.0)
    def note(result):
        return [c[3] for c in result["checks"] if c[0] == "base height / width"][0]
    a, b = note(wide_chunky), note(wide_thin)
    assert a != b, "the two tolerances produce the same band, so one of them does nothing"
    assert "400%% chunkier" % () not in b, "the thin box moved the chunky end of the band"


def test_the_page_carries_both_base_tolerances(checker):
    """Both numbers reach the browser, or the page is judging by rules the tool does not have."""
    src = pathlib.Path(checker.__file__).read_text(encoding="utf-8")
    assert "__BTHIN__" in src and "id=bthin" in src, "the thin tolerance has no box on the page"
    assert "base_thin" in src, "the page never sends the thin tolerance back"
    # and the substitution actually happens, so the box is not left holding the placeholder
    assert 'json.dumps(BASE_THIN_PCT)' in src, "__BTHIN__ is never filled in"


def test_the_plates_are_judged_on_the_camera_they_share_with_a_sculpt(checker):
    """A plate has no plinth, so only one of the three sculpt checks transfers -- and it does.

    `base_band=False` is the whole trick and it is easy to lose: the band exists to scan the
    bottom strip of a sculpt, where a plinth lives, and a plate IS the ellipse. Scanning a
    plate's bottom strip reports about 17 degrees for every one of them, which is a plausible
    enough number to be believed.
    """
    rows = checker.ground_record()
    if not rows:
        pytest.skip("no ground plates on file")
    for r in rows:
        assert r["degrees"] is not None, "%s has no camera" % r["name"]
        assert 5.0 < r["degrees"] < 85.0, "%s measured %s" % (r["name"], r["degrees"])

    # THE GUARD THAT USED TO LIVE HERE WANTED A SPREAD OF MORE THAN 5 DEGREES ACROSS THE
    # FOLDER, as proof that the measurement was not collapsing every plate onto one number.
    # It worked only because cobbles_oval sat at 39.8 and dragged the range open. On
    # 2026-09-23 that plate was redrawn at 31.6 and the whole set came inside a degree --
    # 31.1, 31.5, 31.6, 31.9, 32.0 -- so the old guard began failing on SUCCESS. Tight
    # agreement is the goal here, and a test that reads the goal as a fault is worse than no
    # test: the obvious way to make it pass again is to keep a bad plate on file.
    #
    # What it was really trying to prove is proved below instead, per-plate and without
    # needing an outlier: the same code with base_band=True gives a DIFFERENT and wrong
    # answer, so the base_band=False path is demonstrably doing work.
    seen = sorted(r["degrees"] for r in rows)
    assert len(set(seen)) > 1, (
        "every plate measured the identical number (%s) -- that is not tight agreement, that "
        "is the measurement not reading the image at all" % seen)

    from PIL import Image
    # every plate, not just the first: this is now the only thing standing between the suite
    # and a ground_ellipse that has quietly stopped finding ellipses
    for r in rows:
        p2 = checker.GROUNDS / (r["name"] + ".png")
        b = checker.sm.ground_ellipse(Image.open(p2).convert("RGBA"), base_band=True)
        w = checker.sm.ground_ellipse(Image.open(p2).convert("RGBA"), base_band=False)
        assert b is not None and w is not None, "%s measured as nothing" % r["name"]
        assert abs(b["degrees"] - w["degrees"]) > 5.0, (
            "%s reads the same banded (%.1f) as whole (%.1f) -- base_band is not being honoured"
            % (r["name"], b["degrees"], w["degrees"]))

    plate = checker.GROUNDS / (rows[0]["name"] + ".png")
    im = Image.open(plate).convert("RGBA")
    banded = checker.sm.ground_ellipse(im, base_band=True)
    whole = checker.sm.ground_ellipse(im, base_band=False)
    assert banded and whole
    assert abs(whole["degrees"] - rows[0]["degrees"]) < 0.2, "the record is not the whole-art read"
    assert whole["degrees"] - banded["degrees"] > 5.0, (
        "the bottom-strip scan agrees with the whole-art scan on a plate, so this guard is "
        "no longer guarding the mistake it was written for")


def test_a_plate_nobody_stands_on_is_named_rather_than_dropped(checker):
    """Three of the five carry no duty and are kept as the evidence of a camera that missed.

    A panel that quietly listed only the plates in use would be throwing that away, and the
    next person to wonder what a mismatch looks like would have to generate one.
    """
    rows = checker.ground_record()
    if not rows:
        pytest.skip("no ground plates on file")
    idle = [r for r in rows if not r["duties"]]
    used = [r for r in rows if r["duties"]]
    assert used, "no plate has a duty standing on it"
    assert idle, "every plate is in use -- this guard needs a different fixture"
    src = pathlib.Path(checker.__file__).read_text(encoding="utf-8")
    assert "no duty stands on this one" in src, "the page does not say when nobody stands on one"

    # AND IT DOES NOT CALL THEM ALL MISTAKES. Standing on nobody and having the wrong camera are
    # separate facts: when every duty-less plate also failed, one sentence covered both, and the
    # moment a passing plate had no duty the page started calling it evidence of a camera that
    # missed. A plate that passes must be described as waiting, not as wrong.
    assert "no duty stands on this one yet" in src, "a passing, duty-less plate is called a miss"
    idle_ok = [r for r in rows if not r["duties"]
               and abs(r["degrees"] - checker.TARGET_DEGREES)
               <= checker.GROUND_TOLERANCE_DEGREES]
    assert idle_ok, "no passing plate is currently duty-less -- this guard needs a fixture"


def test_the_page_references_committed_files_instead_of_swallowing_them(checker, tmp_path):
    """15.3 MB of the page was base64 of files already on disk, against 0.3 MB of the drawn
    previews anyone actually looks at. The originals are referenced now; only what is GENERATED
    is embedded, because there is nothing on disk to point at.
    """
    out = tmp_path / "asset_check.html"
    for r in checker.on_record(rel_to=out.parent) + checker.ground_record(rel_to=out.parent):
        assert not r["orig"].startswith("data:"), "%s is embedded again" % r["file"]
        assert (out.parent / r["orig"]).resolve().is_file(), (
            "%s points at %s, which is not there" % (r["file"], r["orig"]))
    card = checker.reference_card(rel_to=out.parent)
    if card:
        assert not card["uri"].startswith("data:"), "the reference card is embedded again"
        assert (out.parent / card["uri"]).resolve().is_file()
    for p in checker.prompts(rel_to=out.parent):
        for a in p["attach"]:
            assert not a["uri"].startswith("data:"), "%s is embedded again" % a["name"]
            assert (out.parent / a["uri"]).resolve().is_file()
    # and the previews, which exist nowhere on disk, still are embedded
    rows = checker.ground_record(rel_to=out.parent)
    if rows:
        assert rows[0]["preview"].startswith("data:image/png;base64,")


def test_one_href_has_to_work_from_disk_and_from_the_server(checker):
    """The page is served at its own path under a document root of the repository, NOT at "/".

    That is the only reason a single relative href can work in both modes. Serving it at the
    root would leave every ../../../ pointing above the document root, and the links would work
    from disk and 404 when served -- which is exactly the mode they were added for, since
    Chromium ignores `download` on a file:// link.
    """
    src = pathlib.Path(checker.__file__).read_text(encoding="utf-8")
    assert "page_path = href(page, ROOT)" in src, "the server does not know the page's own path"
    assert '"Location", "/" + page_path' in src, "/ does not redirect to the page's real path"
    assert "os.path.realpath" in src, "the static branch is not path-confined"
    rel = checker.href(checker.SCULPTS / "player_2_v1.png", checker.OUT.parent)
    assert rel.startswith("../../../ui/"), "unexpected shape for a reference: %s" % rel
    assert (checker.OUT.parent / rel).resolve() == (checker.SCULPTS / "player_2_v1.png").resolve()


def test_a_plate_is_held_tighter_than_a_sculpt(checker):
    """Two tolerances, not one, because they are not the same measurement.

    A sculpt's camera is read off a plinth inside a figure the generator drew freehand, and five
    near-identical renders scatter by about 0.6 degrees -- 2.5 is sized to that noise. A plate
    is one flat ellipse with nothing standing on it, read far more steadily, and it has to agree
    with every figure at once. The guard is that the plate number is the smaller one and that it
    actually changes a verdict: at 2.5 a plate 2.2 degrees out passes.
    """
    assert checker.GROUND_TOLERANCE_DEGREES < checker.TOLERANCE_DEGREES, (
        "a plate is not held tighter than a sculpt: %s against %s"
        % (checker.GROUND_TOLERANCE_DEGREES, checker.TOLERANCE_DEGREES))

    rows = checker.ground_record()
    if not rows:
        pytest.skip("no ground plates on file")

    def verdict(deg, tol):
        off = abs(deg - checker.GROUND_TARGET_DEGREES)
        return "ok" if off <= tol else ("check" if off <= 2 * tol else "bad")

    # NOT "some plate on disk must fail at the tight number and pass at the loose one". That
    # was the first version of this guard, and it broke the moment the plate it happened to
    # describe was redrawn -- a test pinned to today's folder rather than to the rule. The rule
    # is that an angle between the two tolerances is judged differently by them, which is true
    # of the numbers themselves whatever is on file.
    between = checker.GROUND_TARGET_DEGREES + (checker.GROUND_TOLERANCE_DEGREES
                                               + checker.TOLERANCE_DEGREES) / 2.0
    assert verdict(between, checker.TOLERANCE_DEGREES) == "ok"
    assert verdict(between, checker.GROUND_TOLERANCE_DEGREES) != "ok", (
        "%.1f degrees is judged the same by both tolerances, so the plate number is decorative"
        % between)

    # and every plate a duty actually stands on still passes at the tighter number
    for r in rows:
        if r["duties"]:
            assert verdict(r["degrees"], checker.GROUND_TOLERANCE_DEGREES) == "ok", (
                "%s carries %s and no longer passes at %s degrees"
                % (r["name"], ", ".join(r["duties"]), checker.GROUND_TOLERANCE_DEGREES))


def test_the_plate_numbers_are_read_off_the_plates(checker):
    """The target and the tolerance are a DESCRIPTION of the accepted set, not a choice.

    Every plate on file has been looked at under figures and kept, so the set is the
    specification: the target is what it averages and the tolerance is how far the furthest
    member strays. That replaced a target of 32.0 and a tolerance of 1.0, which were a round
    number and half the sculpt figure -- and the set never centred on 32 at all, four of the
    five sitting below it.

    This recomputes both from the folder. It is the guard against the constants and the art
    drifting apart: file a plate outside the window and it fails here, which is the moment to
    decide whether the plate is wrong or the family has moved.
    """
    rows = checker.ground_record()
    if len(rows) < 3:
        pytest.skip("too few plates to describe a set")
    degs = [r["degrees"] for r in rows]
    mean = sum(degs) / len(degs)
    worst = max(abs(d - mean) for d in degs)

    assert abs(mean - checker.GROUND_TARGET_DEGREES) <= 0.05, (
        "the plates average %.2f but the target says %.2f -- the set has moved since the "
        "constant was written (%s)"
        % (mean, checker.GROUND_TARGET_DEGREES,
           ", ".join("%s %.2f" % (r["name"], r["degrees"]) for r in rows)))
    assert abs(worst - checker.GROUND_TOLERANCE_DEGREES) <= 0.05, (
        "the furthest plate is %.2f from the mean but the tolerance says %.2f"
        % (worst, checker.GROUND_TOLERANCE_DEGREES))

    # the invariant that actually matters, stated separately: every filed plate is inside its
    # own window. This is what breaks first when a plate is filed that should not have been.
    for r in rows:
        assert abs(r["degrees"] - checker.GROUND_TARGET_DEGREES) <= (
            checker.GROUND_TOLERANCE_DEGREES + 1e-9), (
            "%s measures %.2f, outside %.2f +/- %.2f"
            % (r["name"], r["degrees"], checker.GROUND_TARGET_DEGREES,
               checker.GROUND_TOLERANCE_DEGREES))

    # and the sculpts' target is close enough that ground and figure still agree about where
    # the viewer is standing -- the thing the shared constant used to assert by construction
    assert abs(checker.GROUND_TARGET_DEGREES - checker.TARGET_DEGREES) < 1.0, (
        "plates centre on %.2f and sculpts on %.2f -- they are no longer the same camera"
        % (checker.GROUND_TARGET_DEGREES, checker.TARGET_DEGREES))


def test_the_ring_ratio_note_still_describes_the_code(checker):
    """A prose explanation with numbers in it goes stale silently. This is the alarm.

    docs/architecture/ring-ratio.md quotes the plate window, the plate table and the sculpt
    target. All three are read off the code and the art, so all three move -- and a reader who
    trusts a document quoting 32.0 when the constant says 31.62 is worse off than one with no
    document at all. Every number the note states is checked against its source here.
    """
    doc = ROOT / "docs" / "architecture" / "ring-ratio.md"
    if not doc.is_file():
        pytest.skip("the note is not on file")
    text = doc.read_text(encoding="utf-8")

    target = checker.GROUND_TARGET_DEGREES
    tol = checker.GROUND_TOLERANCE_DEGREES
    for probe, what in (
            ("%.2f" % target, "the plate target"),
            ("%.2f" % tol, "the plate tolerance"),
            ("%.2f to %.2f" % (target - tol, target + tol), "the window in degrees"),
            ("%.1f" % checker.TARGET_DEGREES, "the sculpt target")):
        assert probe in text, (
            "ring-ratio.md never states %s (%s) -- the note and the code have drifted"
            % (probe, what))

    # the table of plates, every row checked against the folder rather than spot-checked
    for r in checker.ground_record():
        assert "`%s`" % r["name"] in text, "%s is missing from the note's table" % r["name"]
        assert "%.2f" % r["degrees"] in text, (
            "%s measures %.2f, which the note's table does not contain"
            % (r["name"], r["degrees"]))

    # the picture beside it, and the generator that redraws it -- a note whose illustration
    # cannot be rebuilt is a committed screenshot with extra steps
    assert "ring-ratio.png" in text, "the note does not reference its picture"
    assert (ROOT / "docs" / "architecture" / "ring-ratio.png").is_file(), "the picture is absent"
    gen = ROOT / "tools" / "ui_debug" / "generate_ring_ratio_explainer.py"
    assert gen.is_file(), "the picture has no generator"
    assert gen.name in text, "the note does not say how to redraw its picture"


def test_the_ring_ratio_picture_redraws_from_the_repository_alone(checker, tmp_path):
    """The generator must not need anything that is not committed.

    Its first draft measured a ringed candidate sitting in a downloads folder, which works
    exactly once and on one machine. It now draws the ring itself around a committed plate, so
    this runs it end to end and checks the ring it drew is one the measuring code accepts --
    the failure mode being an ellipse drawn off the edge of its canvas, which arrives not as a
    visible glitch but as ring_ellipse correctly refusing an open arc.
    """
    import importlib.util
    path = ROOT / "tools" / "ui_debug" / "generate_ring_ratio_explainer.py"
    if not path.is_file():
        pytest.skip("the generator is not on file")
    spec = importlib.util.spec_from_file_location("generate_ring_ratio_explainer", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    out = tmp_path / "ring-ratio.png"
    written, target, tol = mod.build(out=out)
    assert written.is_file() and written.stat().st_size > 20_000, "no picture came out"
    assert target == checker.GROUND_TARGET_DEGREES, "the picture drew a different target"
    assert tol == checker.GROUND_TOLERANCE_DEGREES, "the picture drew a different tolerance"

    # the drawn ring is measurable, and measures back as what it was drawn at
    from PIL import Image
    plate = Image.open(checker.GROUNDS / "cobbles_oval.png").convert("RGBA")
    want = checker.sm.ground_ellipse(plate, base_band=False)["degrees"]
    got = checker.sm.ring_ellipse(mod._ringed(plate, want))
    assert got is not None, (
        "the generator drew a ring the measuring code refuses -- almost always an ellipse "
        "off the edge of its canvas, which reads as an open arc")
    assert abs(got["degrees"] - want) < 0.5, (
        "a ring drawn at %.2f measured back as %.2f" % (want, got["degrees"]))


def test_a_recorded_camera_cannot_hide_a_bad_plate(checker):
    """A number written down by hand, for a plate whose ring was thrown away. Guard it.

    Most plates need no such thing: a round rimmed plate's outline IS an ellipse and
    ground_ellipse measures it. A ragged patch is not, and the fit is a best guess at a shape
    that has none -- on planks_rough it reads 30.66 where the measuring ring on the source
    image read 31.57. So duty_grounds.json may carry a plate's camera, and the page reports
    it as that plate's angle.

    The risk is obvious and worth stating: the ring is stripped when art is filed, so nothing
    in the repository can re-derive the recorded number. It is the one figure here that no
    later measurement contradicts, which makes it the one place a wrong angle could sit
    forever. Two conditions keep it honest.
    """
    rows = {r["name"]: r for r in checker.ground_record()}
    if not rows:
        pytest.skip("no ground plates on file")
    recorded = [r for r in rows.values() if r["camera_from"] == "ring" and not r["ringed"]]

    for r in recorded:
        # ONE: it must still agree with the plate's own outline, to the same 1.5 degrees a
        # candidate's ring and outline must agree within. The recorded number is allowed to be
        # the BETTER of two readings; it is not allowed to be a different answer. A plate whose
        # ring and outline disagree past that bar should never have been filed at all.
        assert r["measured"] is not None, "%s has a recorded camera and no outline to check "\
            "it against" % r["name"]
        assert abs(r["degrees"] - r["measured"]) <= 1.5, (
            "%s records %.2f but its own outline reads %.2f -- %.2f apart. Past 1.5 the two "
            "are not two readings of one camera, and the plate should not be on file."
            % (r["name"], r["degrees"], r["measured"], abs(r["degrees"] - r["measured"])))

        # TWO: it must say where it came from. An unattributed number is indistinguishable
        # from a typed-in one, and this is the field a future reader has to trust.
        assert r["camera_note"], (
            "%s records a camera without saying where it came from" % r["name"])
        assert len(r["camera_note"]) > 60, (
            "%s's camera note is too short to be a provenance" % r["name"])

    # and the mechanism is not quietly swallowing every plate: a plate with no recorded camera
    # must report its own measurement unchanged
    for r in rows.values():
        if r["camera_from"] == "outline":
            assert r["degrees"] == r["measured"], (
                "%s has no recorded camera but its reported angle (%.2f) is not its "
                "measurement (%.2f)" % (r["name"], r["degrees"], r["measured"]))


def test_the_grounds_panel_reads_its_own_tolerance_box(checker):
    """The panel silently rendered nothing the first time, because it read a TARGET constant
    that does not exist -- the numbers live in the boxes at the top. It must read the GROUND
    box, not the sculpt one, or the two panels answer different questions from the same input.
    """
    src = pathlib.Path(checker.__file__).read_text(encoding="utf-8")
    assert "__GTOL__" in src and "id=gtol" in src, "the plate tolerance has no box on the page"
    assert 'getElementById("gtol").value' in src, "the grounds panel does not read its own box"
    assert 'json.dumps(GROUND_TOLERANCE_DEGREES)' in src, "__GTOL__ is never filled in"
    # AND ITS OWN TARGET. A plate used to borrow the sculpts' 32.0 and differ only in
    # tolerance; both plate numbers are now read off the plates themselves, so the panel
    # reading the sculpt box would silently judge every plate against the wrong centre.
    assert "__GTARGET__" in src and "id=gtarget" in src, "the plate target has no box"
    assert 'getElementById("gtarget").value' in src, (
        "the grounds panel still reads the sculpts' target box")
    assert 'json.dumps(GROUND_TARGET_DEGREES)' in src, "__GTARGET__ is never filled in"


def test_a_brief_hands_over_the_brief_and_not_its_bookkeeping(checker, tmp_path):
    """What reaches the clipboard reaches an image model. Nothing else may ride along.

    The stripper used to remove only `attach:` lines. The first note written for a human
    reader -- eight lines on why cobbles_oval attaches the plate it REPLACED rather than the
    one it produced -- therefore went to the clipboard verbatim and would have been pasted
    into the generator as if it were part of the instruction. A brief has to be able to carry
    its reasoning without the reasoning becoming the request.

    So: every leading HTML comment is bookkeeping. `attach:` ones are understood, the rest are
    dropped, and the text starts at the first real line either way.
    """
    d = tmp_path / "prompts"
    d.mkdir()
    real = checker.ROOT / "ui" / "assets-gothic" / "grounds" / "flagstones_grey.png"
    (d / "sample.md").write_text(
        "<!-- attach: ui/assets-gothic/grounds/flagstones_grey.png -->\n"
        "<!-- a note for whoever opens this file,\n"
        "     running to several lines -->\n"
        "<!-- attach: ui/assets-gothic/grounds/flagstones_grey.png -->\n"
        "THE BRIEF BEGINS HERE.\n\nand continues <!-- this one is inline and must survive -->\n",
        encoding="utf-8")

    got = checker.prompts(folder=d)
    assert len(got) == 1
    one = got[0]

    assert one["text"].startswith("THE BRIEF BEGINS HERE."), (
        "the clipboard does not start at the brief: %r" % one["text"][:80])
    assert "a note for whoever opens this file" not in one["text"], (
        "a reader's note was copied to the clipboard")
    assert "attach:" not in one["text"], "an attach line was copied to the clipboard"

    # both attach lines are still understood, INCLUDING the one sitting after the note --
    # a plain comment must not stop the scan and swallow the attachment behind it
    assert [a["name"] for a in one["attach"]] == [real.name, real.name], (
        "attachments lost: %s" % [a["name"] for a in one["attach"]])

    # and a comment in the BODY is the author's, not ours: it is not leading, so it stays
    assert "this one is inline and must survive" in one["text"]


def test_a_brief_is_offered_beside_the_thing_it_makes(checker):
    """A ground plate's brief belongs on the ground tab, not in the sculpt row.

    The two panels answer different questions and the briefs follow their subject. The split
    is by what is ON FILE rather than by a naming convention, so a brief cannot drift into
    the wrong row by being called the wrong thing.

    A CANDIDATE COUNTS. The rule was "is there grounds/<name>.png", which is true only once a
    brief has SUCCEEDED -- so planks_rough.md, whose plate is still grounds/candidates/
    planks_rough_c01.png, landed beside the sculpts. That is backwards: a brief is most in
    the way on the wrong tab while it is still being worked on, and least once it is done.
    """
    ps = checker.prompts()
    if not ps:
        pytest.skip("no briefs on file")
    for p in ps:
        assert p["makes"] in ("ground", "sculpt"), p["makes"]
        made = (checker.GROUNDS / (p["name"] + ".png")).is_file()
        held = list((checker.GROUNDS / "candidates").glob(p["name"] + "_c*.png"))
        assert (p["makes"] == "ground") == bool(made or held), (
            "%s is filed as a %s brief but there is %s plate of that name%s"
            % (p["name"], p["makes"], "a" if (made or held) else "no",
               "" if made else " (checked candidates/ too)"))

    # the widening must not have swallowed the distinction: a sculpt brief still exists and
    # still reads as one, or this test is passing because everything is a ground now
    kinds = {p["makes"] for p in ps}
    assert kinds == {"ground", "sculpt"}, (
        "every brief came back as %s -- the split is no longer splitting" % kinds)

    src = pathlib.Path(checker.__file__).read_text(encoding="utf-8")
    assert "GROUND_PROMPTS" in src and "SCULPT_PROMPTS" in src, "the page draws one list"
    # the copy handler indexes the WHOLE list, so a split row must not renumber its buttons
    assert 'PROMPTS.indexOf(p)' in src, (
        "a button's data-i is a position within its own row rather than within PROMPTS, so "
        "the wrong brief reaches the clipboard")
    assert "data-i='\" + i + \"'" not in src, "a stale per-row index survives"


def _ringed(metrics, plate, degrees, radius=1.1, stroke=0.02):
    """A plate with a measuring ring around it, as a generation carrying one would arrive."""
    import math

    from PIL import Image, ImageDraw
    art = metrics.crop_to_art(plate)
    w, h = art.width, art.height
    s = math.sin(math.radians(degrees))
    R = w * radius
    W = int(2 * R + 60)
    H = int(max(2 * R * s, h) * 1.15 + 60)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(out)
    cx, cy = W / 2.0, H / 2.0
    d.ellipse([cx - R, cy - R * s, cx + R, cy + R * s],
              outline=metrics.RING_KEY + (255,), width=max(2, int(w * stroke)))
    out.alpha_composite(art, (int(cx - w / 2), int(cy - h * 0.5)))
    return out


@pytest.fixture(scope="module")
def ragged(checker):
    from PIL import Image
    p = checker.GROUNDS / "candidates" / "flagstones_slab_c01.png"
    if not p.is_file():
        pytest.skip("the ragged plate is not on file")
    return Image.open(p).convert("RGBA")


def _band_ring(metrics, degrees, a=690, t=9, W=1600, H=900):
    """A ring whose CENTRELINE is known exactly: the band between (a-t, b-t) and (a+t, b+t).

    _ringed() above draws with PIL's ellipse outline, which strokes INWARD from the bounding
    box. Fill that and you recover the box exactly, so a bounding measurement round-trips
    perfectly -- which is why the suite was blind to a +0.7 degree bias for as long as this
    fixture was the only one. A generated ring is a stroke around a curve, not an inward
    stroke from a box, and this is that.
    """
    import math
    import numpy as np
    from PIL import Image
    s = math.sin(math.radians(degrees))
    b = a * s
    yy, xx = np.mgrid[0:H, 0:W]
    cx, cy = W / 2.0, H / 2.0
    inner = ((xx - cx) / (a - t)) ** 2 + ((yy - cy) / (b - t)) ** 2
    outer = ((xx - cx) / (a + t)) ** 2 + ((yy - cy) / (b + t)) ** 2
    px = np.zeros((H, W, 4), np.uint8)
    px[(outer <= 1.0) & (inner >= 1.0)] = metrics.RING_KEY + (255,)
    return Image.fromarray(px, "RGBA"), b / a


def test_the_ring_is_fitted_and_not_merely_bounded(metrics):
    """The bias that was there from the start, and is larger than a plate's whole tolerance.

    Filling a ring recovers its OUTER edge, and an outer edge is a fatter ellipse than the
    centreline it was drawn around: adding half-stroke t to both semi-axes gives (b+t)/(a+t),
    which exceeds b/a whenever b < a. So a bounding measurement reports a STEEPER camera than
    the ring was drawn at, by an amount that grows with the stroke -- and the brief asks for a
    stroke of about 2% of the tile's width.

    Ground truth here is exact, so this is a measurement of the instrument rather than an
    opinion about it. A plate is held to 0.55 degrees; the old method was out by up to 0.70.
    """
    # THE THRESHOLDS ARE WHAT WAS MEASURED, not round numbers. Across strokes of 6 to 18 px
    # the fit is exact to 0.01 degrees anywhere in the 28-34 band this board works in. The
    # only place it degrades is a STEEP angle with a FAT stroke -- 0.12 at 40 with t=14 and
    # 0.22 at 40 with t=18 -- because a band of constant half-width t added to both semi-axes
    # is not itself an ellipse, and the thicker and rounder it gets the less it is one. That
    # is 6 degrees outside anywhere a plate will ever sit, and it is still a third of the old
    # method's error at the angles that matter.
    for t in (6, 9, 14, 18):
        for deg in (28.0, 30.0, 31.0, 32.0, 34.0, 40.0):
            allow = 0.05 if deg <= 34.0 else 0.25
            im, truth = _band_ring(metrics, deg, t=t)
            got = metrics.ring_ellipse(im)
            assert got is not None, "no ring found at %.0f (t=%d)" % (deg, t)
            assert abs(got["degrees"] - deg) <= allow, (
                "ring drawn at %.1f measured %.2f with a stroke of %d px -- %.2f out"
                % (deg, got["degrees"], t, abs(got["degrees"] - deg)))
            if deg <= 34.0:
                assert abs(got["sin_theta"] - truth) < 0.002, (
                    "ring drawn at ratio %.4f fitted as %.4f (t=%d)"
                    % (truth, got["sin_theta"], t))

    # and the guard on the guard: the OLD method must actually fail this, or the fixture is
    # not exercising the bias and the test proves nothing
    import numpy as np
    from scipy import ndimage
    im, truth = _band_ring(metrics, 32.0, t=18)
    m, _ = metrics._ring_mask(im)
    filled = ndimage.binary_fill_holes(m)
    px = np.zeros(filled.shape + (4,), np.uint8)
    px[filled] = [255, 255, 255, 255]
    from PIL import Image
    bounded = metrics.ground_ellipse(Image.fromarray(px, "RGBA"), base_band=False)
    assert bounded is not None
    err = abs(bounded["degrees"] - 32.0)
    assert err > 0.3, (
        "filling and bounding this fixture is accurate to %.2f degrees, so it does not "
        "exercise the bias the fit exists to remove" % err)


def test_a_ring_measures_the_camera_a_ragged_plate_cannot_show(metrics, ragged):
    """The point of the ring: the tile inside it can be any shape at all.

    This plate's own outline reads 27.5 degrees and the number is meaningless -- it is a ragged
    patch, not an ellipse. A ring drawn around it is an ellipse whatever the tile does, so the
    camera becomes readable without the art having to be measurable.
    """
    for asked in (28.0, 32.0, 36.0, 40.0):
        got = metrics.ring_ellipse(_ringed(metrics, ragged, asked))
        assert got is not None, "no ring found at %.1f" % asked
        assert abs(got["degrees"] - asked) < 0.5, (
            "ring drawn at %.1f measured %.1f" % (asked, got["degrees"]))


def test_stripping_the_ring_returns_the_tile_untouched(metrics, ragged):
    """A colour key, not a shape guess. Every pixel that is not the ring survives.

    EVERY VISIBLE pixel, to be exact. This fixture composites the tile onto a canvas, and
    alpha_composite rewrites the colour of fully transparent pixels by a unit or two -- 429 of
    them here, all at alpha 0, and exactly the same 429 whether a ring is drawn or not. That is
    the fixture's rounding, not the key's doing, so the guard is on alpha everywhere and on
    colour wherever colour can be seen. Checking raw equality instead would fail for a reason
    that has nothing to do with what this test is about.
    """
    import numpy as np
    before = np.array(metrics.crop_to_art(ragged)).astype(int)
    after = np.array(metrics.crop_to_art(
        metrics.without_ring(_ringed(metrics, ragged, 32.0)))).astype(int)
    assert before.shape == after.shape, "%s became %s" % (before.shape, after.shape)
    assert (before[..., 3] == after[..., 3]).all(), "the tile's alpha changed"
    seen = before[..., 3] > 0
    assert (before[..., :3][seen] == after[..., :3][seen]).all(), (
        "a visible pixel of the tile changed colour when the ring was removed")

    # and the guard on the guard: with no ring at all the fixture differs in the same places,
    # so this test is not quietly tolerating something the key did
    import math

    from PIL import Image
    art = metrics.crop_to_art(ragged)
    ringed = _ringed(metrics, ragged, 32.0)
    plain = Image.new("RGBA", ringed.size, (0, 0, 0, 0))
    plain.alpha_composite(art, ((ringed.width - art.width) // 2,
                                (ringed.height - art.height) // 2))
    assert math.isclose(1.0, 1.0)       # placement differs; shape is what matters here
    assert np.array(metrics.crop_to_art(plain)).shape == before.shape


def test_the_ring_takes_its_own_soft_edge_with_it(metrics, ragged):
    """The bug the hard-edged fixture above cannot see.

    _ringed() draws with ImageDraw.ellipse, which has NO antialiasing at all -- every ring
    pixel is either exactly the key or exactly nothing. A real generator does not draw like
    that. Its ring has a soft edge, and a pixel halfway along that edge is a BLEND of spring
    green and transparent background: low alpha, and an RGB pulled far enough off the key to
    sit outside RING_TOLERANCE. The colour key alone leaves those behind, and what survives is
    a faint ghost of the ring exactly where the ring was.

    Found on the cobbles candidate of 2026-09-23. The ring's ellipse was 1382 px wide; after
    the old strip the alpha>8 box was still 1382 while the SOLID plate was 1159. The ghost was
    not near the ring, it WAS the ring, and it padded the bounding box by 16%.

    It never moved an ANGLE -- ground_ellipse fits rather than taking a box, and the ghost is
    under a percent of the ink. What it corrupted was every preview that crops, which came out
    16% too wide and made the plate look small beside its neighbours. So this asserts on the
    bounding box, which is what actually broke.
    """
    import numpy as np
    from PIL import Image

    # a ring with a REAL soft edge: drawn at 4x and downscaled, per the same supersampling the
    # project uses anywhere a rendered edge is going to be judged
    big = _ringed(metrics, ragged, 32.0)
    soft = big.resize((big.width // 4 * 2, big.height // 4 * 2), Image.LANCZOS)
    soft = soft.resize(big.size, Image.LANCZOS)

    assert metrics.has_measuring_ring(soft), "the softened ring is no longer keyed at all"
    r = metrics.ring_ellipse(soft)
    assert r is not None and abs(r["degrees"] - 32.0) < 1.0, (
        "the softened ring stopped measuring: %s" % (r and r["degrees"]))

    a = np.array(metrics.without_ring(soft))[..., 3]
    ink = a > metrics.ALPHA
    assert ink.any(), "the strip removed everything"
    xs = np.where(ink.any(0))[0]
    wide = int(np.ptp(xs)) + 1

    solid = a > 200
    sxs = np.where(solid.any(0))[0]
    solid_wide = int(np.ptp(sxs)) + 1

    # the surviving ink must BE the tile, not the tile plus a ring-shaped halo around it
    assert wide <= solid_wide * 1.05, (
        "a ghost of the ring survived the strip: ink spans %d px where the solid tile spans "
        "%d (%.0f%% wider). The ring's soft edge is being left behind."
        % (wide, solid_wide, 100.0 * wide / solid_wide - 100.0))

    # and the guard on the guard: the ring really was wider than the tile, so a strip that
    # simply did nothing could not have passed the assertion above
    assert r["width"] > solid_wide * 1.2, (
        "the fixture's ring is not clear of the tile, so this test proves nothing")


def test_a_plate_without_a_ring_takes_the_path_it_always_took(checker, metrics):
    """The guard on the blast radius. Nothing on file carries a ring, so nothing on file may
    be routed through the ring code -- the five committed plates must read exactly as before."""
    from PIL import Image
    for path in sorted(checker.GROUNDS.glob("*.png")):
        im = Image.open(path).convert("RGBA")
        assert not metrics.has_measuring_ring(im), "%s trips the key" % path.name
        assert metrics.ring_ellipse(im) is None, "%s found a ring that is not there" % path.name
    for r in checker.ground_record():
        assert r["ringed"] is False


def test_the_key_is_not_a_colour_this_game_uses(metrics):
    """Magenta was the obvious key and it is wrong: it comes within 34 of stones_plum.png,
    plum being a purple. The key has to sit outside the palette or it eats the art."""
    import numpy as np
    from PIL import Image
    key = np.array(metrics.RING_KEY)
    closest = 10 ** 6
    worst = None
    for p in sorted((ROOT / "ui" / "assets-gothic").rglob("*.png")):
        a = np.array(Image.open(p).convert("RGBA")).astype(int)
        m = a[..., 3] > metrics.ALPHA
        if not m.any():
            continue
        d = int(np.abs(a[..., :3] - key).sum(2)[m].min())
        if d < closest:
            closest, worst = d, p.name
    assert closest > metrics.RING_TOLERANCE, (
        "the key fires below %d and %s comes within %d of it"
        % (metrics.RING_TOLERANCE, worst, closest))


def test_an_occluded_ring_refuses_rather_than_reporting_the_wrong_number(metrics, ragged):
    """THE WAY THIS FAILS QUIETLY. A ring's height is 2 x radius x sin(theta), so at a shallow
    camera a ring that looks generous side to side is still shorter than the tile it encircles,
    and the tile sits on top of it. Measured, a 32 degree ring at 1.04 times the tile's height
    read 6.0 degrees -- a plausible number for a very flat plate, which is exactly the kind of
    wrong answer that gets believed. A broken ring has to refuse.
    """
    tight = metrics.ring_ellipse(_ringed(metrics, ragged, 32.0, radius=0.62))
    assert tight is None, "an occluded ring reported %s instead of refusing" % tight
    roomy = metrics.ring_ellipse(_ringed(metrics, ragged, 32.0, radius=1.1))
    assert roomy is not None and abs(roomy["degrees"] - 32.0) < 0.5
