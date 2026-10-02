"""Guards for ui/board_v2/duty_art_lab.

THIS PAGE HAD NO TESTS, which is how it lost every master without a word. The walk it shares with
the other two generators was taught to step over the folders that are not a duty's actions, and
`masters` is one of them -- but this is the page whose whole top row IS the masters. It went from
1984 KB to 557 and from "8 of 8 duties have a master" to "0 of 8", kept building, kept reporting
what it had found, and the only thing that noticed was somebody opening it.

So these are not a suite. They are the two sentences the page exists for, asserted against its own
walk rather than against a copy of it.
"""
import importlib.util
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
LAB = ROOT / "ui" / "board_v2" / "duty_art_lab" / "generate_duty_art_board.py"
BOARD = ROOT / "ui" / "board_v2"


@pytest.fixture(scope="module")
def lab():
    if not LAB.is_file():                                         # pragma: no cover
        pytest.skip("the duty art lab is not in this tree")
    spec = importlib.util.spec_from_file_location("_duty_art_lab", LAB)
    if spec is None or spec.loader is None:                       # pragma: no cover
        pytest.skip("cannot import the duty art lab")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def collected(lab):
    """What the page's own walk found. Anything else would be testing a copy of it."""
    try:
        return lab.collect(lab.board())
    except SystemExit as e:                                       # pragma: no cover
        pytest.skip("the lab will not collect here: %s" % e)


def test_the_page_finds_every_master_on_disk(collected, lab):
    """The top of every duty, and what its headline counts.

    Falsified by skipping `masters` along with the other non-slot folders -- which is exactly what
    happened, and the page said nothing because "0 of 8" is a sentence it is perfectly willing to
    print.
    """
    want = set(lab.image_suffixes(lab.ATTRIB))
    on_disk = {p.name for p in BOARD.glob("duty_actions/*/masters/*") if p.suffix.lower() in want}
    if not on_disk:
        pytest.skip("this tree has no masters to show")
    shown = {a["file"] for d in collected["duties"] for a in d["masters"]}
    assert on_disk <= shown, "on disk but not on the page: %s" % ", ".join(sorted(on_disk - shown))


def test_no_seal_is_shown_as_a_duty_action_image(collected, lab):
    """A seal is recorded in the same vocabulary as a picture -- `left`, `right` -- under the same
    duty, so nothing but the folder keeps it out of an action slot. Falsified by dropping `seals`
    from what this page skips: Clerical's LEFT would show a wax seal blown up to card size."""
    # rglob, not glob: the fault this catches put the seals' MASTERS in the duty masters row --
    # fourteen wax seals shown at master size, and a headline reporting "8 of 8 duties have a
    # master" when two of them do. A test that only looked at seals/*.webp would have agreed.
    seals = {p.name for p in BOARD.glob("duty_actions/*/seals/**/*") if p.is_file()}
    if not seals:
        pytest.skip("this tree has no seals yet")
    for d in collected["duties"]:
        for bucket in ("left", "right", "masters", "unplaced"):
            got = d[bucket] if bucket in ("masters", "unplaced") else (d[bucket] or {}).get("art")
            names = {a["file"] for a in (got or [])}
            assert not (names & seals), "%s's %s shows %s" % (
                d["slug"], bucket, ", ".join(sorted(names & seals)))


def test_what_this_page_skips_comes_from_the_one_place_that_says_so(lab):
    """Four places have to agree about which folders are not a duty's actions, and each used to
    carry its own copy. This page skips all of them BUT the ones it has a bucket for, and that
    exception is the whole bug above -- so it is asserted rather than remembered.

    Falsified by hard-coding the list back into this file, or by bucketing something the walk no
    longer collects.
    """
    listed = set(json.loads(lab.ATTRIB.read_text(encoding="utf-8"))["nonSlotFolders"])
    assert set(lab.SKIP) | set(lab.BUCKETED) == listed, (
        "this page skips %s and buckets %s, and attribution.json names %s"
        % (lab.SKIP, lab.BUCKETED, sorted(listed)))
    assert "masters" in lab.BUCKETED and "masters" not in lab.SKIP
    assert "seals" in lab.SKIP
