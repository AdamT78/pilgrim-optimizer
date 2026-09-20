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
    monkeypatch.setattr(sys, "argv", ["generate_duty_board_check.py", "--out", str(out)])
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
    monkeypatch.setattr(sys, "argv", ["generate_duty_board_check.py",
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
    monkeypatch.setattr(sys, "argv", ["generate_duty_board_check.py", "--out", str(out)])
    mod.main()
    page = out.read_text(encoding="utf-8")
    assert not re.search(r"FIGS\s*=\s*\{\}", page), "the sculpt table came out empty"
    for size in mod.FIGURE_SIZES:
        if (mod.FIGURE_DIR / ("figure_player_1_%d.png" % size)).is_file():
            assert '"%d"' % size in page, "size %d rendered but never reached the page" % size


def test_template_guards_the_empty_tile(mod):
    """formation(0) must return no slots. It fell through to the five-slot case once, and since
    a typical deal leaves most tiles empty, that threw before the board was ever drawn."""
    src = TMPL.read_text(encoding="utf-8")
    assert "if (n <= 0) return [];" in src, (
        "the empty-tile guard has gone from formation(); an empty tile will ask for five slots")


def test_template_pins_the_haze_filters_to_srgb(mod):
    """SVG filters default to linearRGB, which kept so much chroma that the low end of the
    amount slider did nothing visible. Losing this line would silently weaken the cue."""
    src = TMPL.read_text(encoding="utf-8")
    assert 'color-interpolation-filters="sRGB"' in src
