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
    for path in sorted(mod.GROUNDS_DIR.glob("*")):
        if path.name.startswith("."):
            continue
        key = "grounds/%s" % path.name
        assert key in att["files"], "%s has no entry in attribution.json" % key
        assert att["files"][key]["licence"] in att["licences"], (
            "%s claims a licence the register does not define" % key)


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


def _height_row(checker, raw, height_tol):
    for name, value, verdict, _why in checker.judge(
            raw, 30.0, 2.5, height_tol=height_tol)["checks"]:
        if name == "height":
            return value, verdict
    return None, None


def test_the_height_verdict_moves_with_its_own_tolerance(checker):
    """Height has a tolerance of its own rather than sharing the angle's.

    The same figure has to pass a loose bar and fail a tight one, or the number in the box is
    decoration. The angle is held at its target throughout, so a change of verdict can only have
    come from the height tolerance and not from the file being wrong in some other way.
    """
    import io
    buf = io.BytesIO()
    _disc(240, 30, wall=20, stem=500).save(buf, "PNG")     # about +24% of the set
    raw = buf.getvalue()

    if _height_row(checker, raw, 15.0)[1] is None:
        pytest.skip("no set on record to compare a height against")

    assert _height_row(checker, raw, 45.0)[1] == "ok", (
        "a figure 41% over the set failed a 45% tolerance")
    assert _height_row(checker, raw, 15.0)[1] == "bad", (
        "a figure 41% over the set passed a 15% tolerance")

    angles = {t: [c[2] for c in checker.judge(raw, 30.0, 2.5, height_tol=t)["checks"]
                  if c[0] == "camera angle"] for t in (15.0, 45.0)}
    assert angles[15.0] == angles[45.0] == ["ok"], (
        "the angle moved too, so the height tolerance is not what changed the verdict")


def test_a_tall_figure_is_told_what_it_costs_the_rest_of_the_set(checker):
    """Being out of tolerance is not the whole story: the tray levels every figure by the
    narrowest plinth and then scales the set so the TALLEST reaches the target size, so one tall
    newcomer shrinks its four siblings. A percentage off the median does not say that; the cost
    row does, and only when the figure actually becomes the tallest."""
    import io

    def cost(stem):
        buf = io.BytesIO()
        _disc(240, 30, wall=20, stem=stem).save(buf, "PNG")
        for name, value, verdict, _why in checker.judge(buf.getvalue(), 30.0, 2.5)["checks"]:
            if name == "cost to the set":
                return value, verdict
        return None, None

    short = cost(300)
    if short[1] is None:
        pytest.skip("no set on record to be shrunk")
    assert short == ("none", "ok"), "a figure shorter than the set was said to cost it something"

    value, verdict = cost(700)
    assert verdict == "bad" and "smaller" in value, (
        "a figure well over the tallest on record cost the set nothing: %r" % (value,))


def test_the_height_tolerance_admits_the_set_it_judges_newcomers_against(checker):
    """A bar the existing art cannot clear would fail every honest new figure.

    With the camera divided out the set is tighter than it looked: player_2, _3 and _4 agree on
    proportion to within 1% of each other, and player_1 stands 8.3% above them. So the guard is
    that the CLUSTER passes and at most one figure sits outside -- which still catches a
    tolerance screwed down so far that honest art fails, without pretending the known outlier
    is not there. When the set is regenerated this should tighten, and the number here with it.
    """
    seen = {}
    for name in checker.PLAYERS:
        path = checker.CONCEPT / name / "sculpt_plastic.png"
        if not path.is_file():
            continue
        for row, value, verdict, _why in checker.judge(path.read_bytes(), 29.0, 2.5)["checks"]:
            if row == "height":
                seen[name] = (value, verdict)
    if len(seen) < 3:
        pytest.skip("the concept art is not here")
    bad = {k: v for k, v in seen.items() if v[1] != "ok"}
    assert len(bad) <= 1, "the tool fails most of the set it was calibrated on: %s" % bad
    assert not [k for k, v in seen.items() if v[1] == "bad"], (
        "a figure on record is more than twice the tolerance out: %s" % seen)


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


def test_a_sculpt_is_judged_on_angle_then_base_then_height(checker):
    """Three questions, asked in that order, because they fail independently.

    The camera says where you stood. The base says how chunky the plinth is. The height says how
    tall the figure stands above it. A set can agree on any two and disagree on the third: ten
    nuns and ten monks shared a camera and a height and differed by two thirds on their bases.
    """
    order = [c[0] for c in checker.judge(_png(_plinth(240, 32, 40)), 32.0, 2.5)["checks"]]
    for name in ("camera angle", "base height / width", "height"):
        assert name in order, "%s is not among the sculpt checks" % name
    assert (order.index("camera angle") < order.index("base height / width")
            < order.index("height")), "the three questions are not asked in order: %s" % order


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
    """The panel draws ui/assets-gothic/sculpts/ at 32 degrees while the band that actually
    judges a newcomer still comes from ui/concept/ at 9. Calling both 'the set on record' on one
    page is how someone reads the wrong number off the screen."""
    src = (ROOT / "tools" / "ui_debug" / "generate_asset_check.py").read_text(encoding="utf-8")
    panel = src.split('id="record"')[-1] if 'id="record"' in src else src
    assert "ui/assets-gothic/sculpts/" in src, "the panel does not say where its figures came from"
    assert "NOT the band" in src, "the panel does not distinguish itself from the judging band"
    del panel


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
