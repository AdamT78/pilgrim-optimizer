"""The picker's controls, driven in a real browser.

WHY A BROWSER

Seat, stones and turn are three controls writing into one board, and two of them write the same
`<use>`. That interaction lives entirely in the page's JavaScript, so nothing that reads the
generated file can see it: the markup is identical whichever way the controls have been clicked.

The regression that prompted these tests is the shape to keep in mind. Rewriting the seat handler
to make room for the stones control, the acolyte cube stopped being repainted -- so a plum board
carried a sage green cube. The page threw no error, the `<use>` resolved, the symbol existed. What
was wrong was only ever *which* symbol, and only after a particular sequence of clicks.

So these follow each slot through to the file it actually draws, after clicking, and check the board
still agrees with itself.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.slow

REPO = Path(__file__).resolve().parents[1]
PICKER = REPO / "ui" / "render" / "gen_picker_2.py"

# Reads every slot on the board through to the asset file behind it, which is the question these
# tests actually ask. `data-source` is put on each symbol by the assembler and by the picker alike.
READ_SLOTS = """() => {
  const board = document.querySelector('.stage svg');
  const out = {};
  board.querySelectorAll('[data-asset-role]').forEach(el => {
    const id = (el.getAttribute('href') || '').slice(1);
    const symbol = id ? document.getElementById(id) : null;
    out[el.getAttribute('data-asset-role')] = symbol ? symbol.getAttribute('data-source') : null;
  });
  return out;
}"""

# `acolyte_cube` was here until the population count became a row of figures and both
# cubes left the template. It was the only seat-coloured thing in that band, which is
# why it belonged in this list -- and why its removal is worth a line rather than a
# silent deletion. test_gothic_population_rows asserts no cube role is drawn at all.
SEAT_DECIDED = ("cloth_lit", "cloth_dim", "gems")


@pytest.fixture(scope="module")
def picker_page(tmp_path_factory):
    """Build the picker once. It is an 11 MB page; building it per test would dominate the run."""
    if not PICKER.is_file():
        pytest.skip("the gothic picker is not in this checkout")
    # The picker builds a gothic board in a subprocess, and building one measures its population
    # art to decide whether it has to be composited -- so numpy and Pillow are needed HERE even
    # though nothing in this file is about population rows. The ui lane installs both; the lane
    # that runs the whole suite does not, and this is where that escaped to.
    pytest.importorskip("numpy", reason="building a gothic board measures its population art")
    pytest.importorskip("PIL.Image", reason="building a gothic board measures its population art")
    out = tmp_path_factory.mktemp("picker") / "picker.html"
    result = subprocess.run([sys.executable, str(PICKER), "--output", str(out)],
                            capture_output=True, text=True, cwd=str(REPO))
    if result.returncode != 0:
        pytest.fail("the picker failed to build:\n%s" % result.stderr.strip()[-2000:])
    return out


@pytest.fixture(scope="module")
def page(picker_page):
    sync_api = pytest.importorskip("playwright.sync_api", reason="playwright is not installed")
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as exc:                      # noqa: BLE001 - no browser, not a failure
            pytest.skip("chromium is not available to playwright: %s" % exc)
        page = browser.new_page(viewport={"width": 1180, "height": 980})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(picker_page.resolve().as_uri())
        page.wait_for_selector(".stage svg")
        page.errors = errors                          # checked by its own test at the end
        yield page
        browser.close()


def press(page, role, index):
    page.locator('button.opt[data-role="%s"]' % role).nth(index).click()
    page.wait_for_timeout(120)


def options(page, role):
    return page.locator('button.opt[data-role="%s"]' % role).count()


def seat_of(source):
    """The seat a filename belongs to: cloth_plum_dim.png -> plum."""
    return set(Path(source).stem.split("_")) if source else set()


def test_each_seat_button_repaints_every_seat_decided_slot(page):
    seats = page.evaluate("() => OPTS.seat.map(o => o.value)")
    press(page, "stones", 0)                          # coloured stones, so gems follows the seat too
    for i, seat in enumerate(seats):
        press(page, "seat", i)
        slots = page.evaluate(READ_SLOTS)
        for role in SEAT_DECIDED:
            assert role in slots, "the board has no slot for %r" % role
            assert seat in seat_of(slots[role]), (
                "seat %s: %s draws %r, which is not this seat's file"
                % (seat, role, slots[role]))


def test_black_stones_survive_a_change_of_seat(page):
    """The bug this is really about: two controls over one <use>.

    If the seat handler wrote the gemstone slot directly, choosing black and then changing seat
    would silently put you back on coloured stones -- with no error and a board that looks fine.
    """
    seats = page.evaluate("() => OPTS.seat.map(o => o.value)")
    press(page, "seat", 0)
    press(page, "stones", 1)
    assert "black" in seat_of(page.evaluate(READ_SLOTS)["gems"])
    for i, seat in enumerate(seats):
        press(page, "seat", i)
        slots = page.evaluate(READ_SLOTS)
        assert "black" in seat_of(slots["gems"]), (
            "changing seat to %s dropped the black stones (now %r)" % (seat, slots["gems"]))
        # ...and the rest of the seat still follows the seat. Two layers, not one: a single
        # assertion here would pass on a handler that repainted only the layer it names, which is
        # the class of bug the whole test is about.
        assert seat in seat_of(slots["cloth_lit"])
        assert seat in seat_of(slots["cloth_dim"])


def test_returning_to_coloured_stones_gives_this_seats_own(page):
    seats = page.evaluate("() => OPTS.seat.map(o => o.value)")
    for i, seat in enumerate(seats):
        press(page, "seat", i)
        press(page, "stones", 1)
        press(page, "stones", 0)
        slots = page.evaluate(READ_SLOTS)
        assert seat in seat_of(slots["gems"]), (
            "seat %s: coming back from black gave %r" % (seat, slots["gems"]))


def test_the_turn_control_shows_exactly_one_layer_per_holder(page):
    """Computed style, not the attribute: the attribute is overridden by the board's stylesheet.

    Per HOLDER, not per board. There are two now -- the drape, and the ground behind the portrait,
    which the seat colours and the turn dims with it -- so a board legitimately displays one layer
    from each, and the older form of this test (every `data-turn-layer` in the board, expecting
    exactly one) started failing the moment the second holder arrived. What it was really asking
    was never "how many layers are visible" but "does any holder show none, or more than one", and
    that question survives a third holder being added without anybody editing this file.
    """
    for index, expected in ((0, "lit"), (1, "dim")):
        press(page, "turn", index)
        per_holder = page.evaluate("""() => {
          const b = document.querySelector('.stage svg');
          return [...b.querySelectorAll('[data-turn]')].map(h =>
            [...h.children]
              .filter(el => el.hasAttribute('data-turn-layer')
                         && getComputedStyle(el).display !== 'none')
              .map(el => el.getAttribute('data-turn-layer')));
        }""")
        assert len(per_holder) >= 2, (
            "the board should have a turn holder for the drape and one for the portrait ground; "
            "found %d" % len(per_holder))
        assert all(shown == [expected] for shown in per_holder), (
            "turn %r displays %r" % (expected, per_holder))


def test_every_portrait_option_repoints_the_portrait(page):
    seen = set()
    for i in range(options(page, "portrait")):
        press(page, "portrait", i)
        source = page.evaluate(READ_SLOTS)["portrait"]
        assert source, "portrait option %d left the slot empty" % i
        seen.add(source)
    assert len(seen) == options(page, "portrait"), (
        "two portrait buttons draw the same file: %s" % sorted(seen))


# ---------------------------------------------------------------------------------------------
# THE TWO CONTROLS THAT ARE NOT ASSET SWAPS.
#
# Everything above repoints a <use> at a symbol, and the failure mode is the wrong symbol. These
# two write ATTRIBUTES, and their failure mode is different and quieter: the board still looks like
# a board, and what it shows is a setting the assembler is not on.
#
# They replaced two throwaway scripts that had exactly that fault. One kept captioning its baseline
# panel "parchment, as it is now" for weeks after the parchment strip was replaced by the disc; the
# other read a box height from a rect the template had stopped emitting and fell back to a
# hard-coded 179.0 that happened to still be correct. Both rendered. Neither was checked.


def assembler():
    import importlib.util
    path = REPO / "ui" / "render" / "gen_board_gothic.py"
    if not path.is_file():
        pytest.skip("the assembler is not in this checkout")
    spec = importlib.util.spec_from_file_location("_pick_asm", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pressed_label(page, role):
    got = page.evaluate(
        """r => {const b = [...document.querySelectorAll('button.opt[data-role="'+r+'"]')]
                   .find(b => b.getAttribute('aria-pressed') === 'true');
                 return b ? b.textContent.trim() : null;}""", role)
    return got


def test_both_controls_open_on_what_the_assembler_is_actually_set_to(page):
    """The preselected button must be the board's real setting, not the middle of the range.

    This is the guard that the old scripts most needed and did not have. A comparison whose
    baseline is mislabelled is worse than no comparison: it reads as "here is what you have" while
    showing something else, and every judgement made from it is made against the wrong thing.

    Read from the assembler's constants, so changing DISC_FILL_OPACITY moves what this expects.
    """
    asm = assembler()
    if not options(page, "shadow"):
        pytest.skip("this board has no discs -- resource_layout is not 'disc'")
    assert pressed_label(page, "shadow") == "%d%%" % round(float(asm.DISC_FILL_OPACITY) * 100), (
        "the shadow control opens on %s while gen_board_gothic.DISC_FILL_OPACITY is %s."
        % (pressed_label(page, "shadow"), asm.DISC_FILL_OPACITY))
    assert pressed_label(page, "icon") == "%g px" % float(asm.DISC_ICON_INSET), (
        "the icon control opens on %s while gen_board_gothic.DISC_ICON_INSET is %s."
        % (pressed_label(page, "icon"), asm.DISC_ICON_INSET))


def test_the_shadow_control_moves_the_numeral_with_the_disc(page):
    """The numeral's colour is derived from the disc, so the control has to move both.

    The assembler darkens the box's own fill by the disc's opacity and then picks parchment or ink
    by contrast against that. A control that wrote only `fill-opacity` would be showing a numeral
    the board would never draw -- and it would be wrong in precisely the case the derivation exists
    for, a dark numeral on a dark ground.

    That case is reachable from the buttons rather than hypothetical: at 20% the grain box is still
    pale enough that the derivation chooses INK, while every other box keeps parchment. So this
    asserts that some option produces more than one numeral colour across the four boxes -- which a
    hard-coded parchment cannot do.
    """
    asm = assembler()
    n = options(page, "shadow")
    if not n:
        pytest.skip("this board has no discs -- resource_layout is not 'disc'")
    seen = []
    for i in range(n):
        press(page, "shadow", i)
        seen.append(page.evaluate(
            """() => {const d = [...document.querySelectorAll('[data-resource-disc]')];
                      return {op: d.map(x => x.getAttribute('fill-opacity')),
                              ink: d.map(x => x.parentNode.querySelector('text')
                                                 .getAttribute('fill'))};}"""))
    assert len({tuple(s["op"]) for s in seen}) == n, (
        "the %d shadow options produced %d distinct opacities; some button does not move the disc."
        % (n, len({tuple(s["op"]) for s in seen})))
    for s in seen:
        assert len(set(s["op"])) == 1, (
            "the four discs are at different opacities (%s). One control, one value." % s["op"])
    mixed = [s for s in seen if len(set(s["ink"])) > 1]
    assert mixed, (
        "no shadow option gave the four numerals different colours, so the derived colour is not "
        "being carried -- a hard-coded parchment would pass every other assertion here. The "
        "assembler picks between %r and parchment by contrast against the darkened box fill."
        % asm.INK)


def test_the_icon_control_moves_every_icon_by_the_boxs_own_geometry(page):
    """Four icons, one inset, and the numbers come from the template rather than from arithmetic.

    The inset is checked against the box the picker itself read out of the board, so this fails if
    the control ever starts computing geometry in the page instead of being handed it -- which is
    how the script this replaced ended up running on a hard-coded height.
    """
    asm = assembler()
    n = options(page, "icon")
    if not n:
        pytest.skip("this board has no resource boxes")
    boxes = page.evaluate(
        """names => Object.fromEntries(names.map(nm => {
             const g = document.querySelector('g[id="resource-' + nm + '"]');
             const r = g && [...g.children].find(c => c.tagName === 'rect');
             return [nm, r ? {x:+r.getAttribute('x'), y:+r.getAttribute('y'),
                              w:+r.getAttribute('width'), h:+r.getAttribute('height')} : null];
           }))""", list(asm.RESOURCE_NAMES))
    for i in range(n):
        press(page, "icon", i)
        label = pressed_label(page, "icon")
        inset = float(label.split()[0])
        got = page.evaluate(
            """names => Object.fromEntries(names.map(nm => {
                 const e = document.querySelector('[data-asset-role="resource:' + nm + '"]');
                 return [nm, e ? {x:+e.getAttribute('x'), y:+e.getAttribute('y'),
                                  w:+e.getAttribute('width'), h:+e.getAttribute('height')} : null];
               }))""", list(asm.RESOURCE_NAMES))
        for name, box in boxes.items():
            if box is None or got.get(name) is None:
                continue
            want = {"x": box["x"] + inset, "y": box["y"] + inset,
                    "w": box["w"] - 2 * inset, "h": box["h"] - 2 * inset}
            assert got[name] == pytest.approx(want), (
                "at %s the %s icon is %r, but its box is %r so it should be %r."
                % (label, name, got[name], box, want))


def test_the_page_raised_no_errors(page):
    """Runs last, so it covers every interaction the tests above performed."""
    assert page.errors == [], "the picker raised: %s" % page.errors
