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

SEAT_DECIDED = ("cloth_lit", "cloth_dim", "gems", "acolyte_cube")


@pytest.fixture(scope="module")
def picker_page(tmp_path_factory):
    """Build the picker once. It is an 11 MB page; building it per test would dominate the run."""
    if not PICKER.is_file():
        pytest.skip("the gothic picker is not in this checkout")
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
        # ...and the rest of the seat still follows the seat.
        assert seat in seat_of(slots["cloth_lit"])
        assert seat in seat_of(slots["acolyte_cube"])


def test_returning_to_coloured_stones_gives_this_seats_own(page):
    seats = page.evaluate("() => OPTS.seat.map(o => o.value)")
    for i, seat in enumerate(seats):
        press(page, "seat", i)
        press(page, "stones", 1)
        press(page, "stones", 0)
        slots = page.evaluate(READ_SLOTS)
        assert seat in seat_of(slots["gems"]), (
            "seat %s: coming back from black gave %r" % (seat, slots["gems"]))


def test_the_turn_control_shows_exactly_one_drape(page):
    """Computed style, not the attribute: the attribute is overridden by the board's stylesheet."""
    for index, expected in ((0, "lit"), (1, "dim")):
        press(page, "turn", index)
        shown = page.evaluate("""() => {
          const b = document.querySelector('.stage svg');
          return [...b.querySelectorAll('[data-turn-layer]')]
            .filter(el => getComputedStyle(el).display !== 'none')
            .map(el => el.getAttribute('data-turn-layer'));
        }""")
        assert shown == [expected], "turn %r displays %r" % (expected, shown)


def test_every_portrait_option_repoints_the_portrait(page):
    seen = set()
    for i in range(options(page, "portrait")):
        press(page, "portrait", i)
        source = page.evaluate(READ_SLOTS)["portrait"]
        assert source, "portrait option %d left the slot empty" % i
        seen.add(source)
    assert len(seen) == options(page, "portrait"), (
        "two portrait buttons draw the same file: %s" % sorted(seen))


def test_the_page_raised_no_errors(page):
    """Runs last, so it covers every interaction the tests above performed."""
    assert page.errors == [], "the picker raised: %s" % page.errors
