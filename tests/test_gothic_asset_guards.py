"""The gothic tree's own checks, run by CI rather than by remembering to run them.

WHY THESE ARE HERE AND NOT ONLY IN ui/render/

Both of these already existed as scripts, and both proved something worth keeping true. Neither was
run by anything. A guard nobody runs is not a guard, it is a note -- and the failures they catch are
the quiet sort that no diff shows, so a note is exactly what will not save you:

    the seat palette      the committed drapes, gemstones and cubes are DERIVED files. Someone who
                          edits a colour by hand, or regenerates one of the sixteen and not the
                          other fifteen, leaves a tree that looks fine, renders fine, and no longer
                          matches the table that is supposed to define it. The check also holds the
                          rule the whole lit/dim system rests on: the brightest dimmed seat must
                          stay darker than the darkest lit one, or the column can show a board that
                          reads as "to play" while a darker seat is actually to play.

    the layered frame     the frame was split into stonework, ornaments and a swappable drape, and
                          the claim made at the time was that the layered board reproduces the
                          original pixel for pixel at native width. That claim is only worth
                          anything if something keeps re-testing it.

They are invoked as subprocesses on purpose. These are the scripts a person runs by hand when
working on the assets, and running exactly what a person runs -- rather than importing their
internals and calling a function -- is what stops the test and the tool drifting apart.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
RENDER = REPO / "ui" / "render"


def run(script: str, *args: str) -> subprocess.CompletedProcess:
    path = RENDER / script
    if not path.is_file():
        pytest.skip("%s is not in this checkout" % script)
    return subprocess.run([sys.executable, str(path), *args],
                          capture_output=True, text=True, cwd=str(REPO))


def report(result: subprocess.CompletedProcess) -> str:
    """The script's own words. It already explains itself better than an assert message can."""
    return "\n".join(x for x in (result.stdout.strip(), result.stderr.strip()) if x)[-3000:]


def test_the_committed_seat_layers_still_match_the_palette():
    """recolor_seat_layers.py --check: sixteen derived files against the table that defines them."""
    pytest.importorskip("numpy", reason="the palette check measures pixels")
    pytest.importorskip("PIL", reason="the palette check measures pixels")
    result = run("recolor_seat_layers.py", "--check")
    assert result.returncode == 0, (
        "the committed seat layers no longer match the palette in recolor_seat_layers.py.\n"
        "Either the table changed and the files were not regenerated, or a file was edited by "
        "hand. Regenerate with `python3 ui/render/recolor_seat_layers.py`.\n\n%s" % report(result))


@pytest.mark.slow
def test_the_layered_frame_still_reproduces_the_original_board():
    """check_frame_layers.py: the split into stonework, ornaments and drape changed no pixel.

    Native width matters and is why this is slow: compositing then scaling is not the same as
    scaling then compositing, so a comparison at display size would pass on a board that is wrong.
    """
    sync_api = pytest.importorskip("playwright.sync_api",
                                   reason="this check renders two boards in a browser")
    with sync_api.sync_playwright() as playwright:
        try:
            playwright.chromium.launch(headless=True).close()
        except Exception as exc:                      # noqa: BLE001 - no browser, not a failure
            pytest.skip("chromium is not available to playwright: %s" % exc)

    result = run("check_frame_layers.py")
    assert result.returncode == 0, (
        "the layered frame no longer reproduces the original board.\n"
        "Run `python3 ui/render/check_frame_layers.py --keep` to keep the diff mask it writes.\n"
        "\n%s" % report(result))


def test_the_gothic_tree_has_a_record_for_every_asset():
    """verify_assets.py --root ui/assets-gothic.

    The licences in this tree are the ones that actually bite -- portraits that may never be
    committed, an icon whose attribution has to ship with the game -- so it is the tree that most
    wants this, and until the verifier learned `--root` it was the tree that had it least.
    """
    pytest.importorskip("numpy")
    pytest.importorskip("PIL")
    verifier = REPO / "ui" / "assets" / "verify_assets.py"
    tree = REPO / "ui" / "assets-gothic"
    if not verifier.is_file() or not tree.is_dir():
        pytest.skip("the asset trees are not in this checkout")
    result = subprocess.run([sys.executable, str(verifier), "--root", str(tree)],
                            capture_output=True, text=True, cwd=str(REPO))
    assert result.returncode == 0, (
        "a file in ui/assets-gothic/ has no entry in its attribution.json, or an entry has no "
        "file. The record is the obligation, so this fails even when the licence would have been "
        "fine.\n\n%s" % report(result))
