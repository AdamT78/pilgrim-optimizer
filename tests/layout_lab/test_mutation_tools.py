"""The mutation primitive is load-bearing, so it gets the same treatment it enforces.

These are ordinary pytest tests and run with the rest of the suite. That matters more than it
looks: the first draft of this file was a standalone script that ended in `raise SystemExit`,
which pytest executes at import time while collecting `tests/`, aborting the whole run with an
INTERNALERROR before a single test had run. A checker that breaks the checker is worse than no
checker, so it lives here in the form the repository already runs.
"""
import pytest

from mutation_tools import (MutationRun, MutationTargetError, replace_exactly_once,
                            replace_regex_exactly_once)

SRC = "alpha\nbeta = 1\ngamma\nbeta = 1\n"


# ---------------------------------------------------------------------------------------------
# replace_exactly_once
# ---------------------------------------------------------------------------------------------
def test_a_unique_target_is_applied():
    assert (replace_exactly_once(SRC, "alpha", "ALPHA", "x")
            == "ALPHA\nbeta = 1\ngamma\nbeta = 1\n")


def test_a_missing_target_raises_and_says_which_and_how_many():
    """The whole point of the primitive: a marker that no longer matches is not a skip.

    `source.replace()` would return the source unchanged here, the tests would run against the
    real build, and the mutation would print as a clean result having tested nothing.
    """
    with pytest.raises(MutationTargetError) as e:
        replace_exactly_once(SRC, "delta", "D", "missing target")
    assert "missing target" in str(e.value)
    assert "found 0" in str(e.value)


def test_an_ambiguous_target_raises():
    """Several matches would change several places at once, and a failing test afterwards would
    not say which of them mattered."""
    with pytest.raises(MutationTargetError) as e:
        replace_exactly_once(SRC, "beta = 1", "beta = 2", "ambiguous")
    assert "found 2" in str(e.value)


def test_a_replacement_identical_to_the_target_raises():
    """Otherwise the mutation is a no-op that reports a clean pass having changed nothing."""
    with pytest.raises(MutationTargetError):
        replace_exactly_once(SRC, "alpha", "alpha", "no-op")


def test_a_stale_target_reports_where_its_first_line_got_to():
    """The context line is what makes a stale marker quick to repair rather than merely red.

    This is the exact shape of the failure that actually happened: a guard inserted as the new
    first line of a function, leaving every marker anchored to the old opening unmatched.
    """
    with pytest.raises(MutationTargetError) as e:
        replace_exactly_once("def f():\n    guard()\n    body()\n",
                             "def f():\n    body()\n", "N", "moved body")
    assert "line 1" in str(e.value)


# ---------------------------------------------------------------------------------------------
# replace_regex_exactly_once
# ---------------------------------------------------------------------------------------------
def test_a_regex_target_is_applied():
    assert (replace_regex_exactly_once('V = "4.2.1"', r'V = "[\d.]+"', 'V = "0.0"', "ver")
            == 'V = "0.0"')


def test_an_ambiguous_regex_raises():
    with pytest.raises(MutationTargetError) as e:
        replace_regex_exactly_once("a=1\nb=1\n", r"=1", "=2", "two")
    assert "found 2" in str(e.value)


# ---------------------------------------------------------------------------------------------
# MutationRun — what counts as green
# ---------------------------------------------------------------------------------------------
def test_everything_applied_and_caught_is_green():
    r = MutationRun("t", total=2)
    r.record("one", True)
    r.record("two", True)
    assert r.report() == 0


def test_a_survivor_is_red():
    r = MutationRun("t", total=2)
    r.record("one", True)
    r.record("two", False)
    assert r.report() == 1


def test_a_stale_target_is_red_even_though_nothing_survived():
    """The distinction the summary exists to make.

    A mutation that was applied and survived is a hole in the tests. One that was never applied
    says nothing about the tests at all -- and a suite that cannot prove it broke the code cannot
    prove the tests caught anything. Both are red; only the first is interesting.
    """
    r = MutationRun("t", total=2)
    r.record("one", True)
    r.record_invalid("two", "stale")
    assert r.report() == 1


def test_declaring_more_than_were_applied_is_red():
    """With no survivor and nothing marked invalid: the loop skipped one silently."""
    r = MutationRun("t", total=3)
    r.record("one", True)
    r.record("two", True)
    assert r.report() == 1


def test_a_benign_no_op_is_green_but_still_counted():
    """A few mutations corrupt a value the page repairs on load, so nothing should fail. They
    document the repair -- and they must still resolve exactly once."""
    r = MutationRun("t", total=1)
    r.record("repaired on load", False, benign=True)
    assert r.report() == 0
    assert r.benign_noop == ["repaired on load"]
    assert r.survived == []


def test_a_crash_counts_as_caught_but_is_reported_separately():
    """A non-zero exit is how a mutation is normally judged caught, but a harness that threw
    never ran its assertions to a conclusion -- and one that crashed for an unrelated reason
    would score identically."""
    r = MutationRun("t", total=1)
    r.record("killed the page", True, crashed=True)
    assert r.report() == 0
    assert r.crash_only == ["killed the page"]
    assert r.caught == 1
