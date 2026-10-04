"""Guards on the CI router: the lane conditions in .github/workflows/tests.yml.

THE ROUTER IS CODE, AND IT WAS THE ONLY CODE HERE WITHOUT A TEST. It decides which lanes a change
wakes, and it does it with three shell pipelines whose path lists have to agree with each other.
They stopped agreeing the day tests/icon_lab/ arrived: the directory was added to the lab lane's
trigger and not to the engine lane's exclusion, so every icon-lab change -- the most frequent kind
this tree gets -- ran the full engine suite to prove nothing about a tree the engine cannot
import. Nothing failed, which is why it survived. A router that routes everything to everything is
correct and useless, so the cost of its bugs is minutes rather than red, and minutes do not show
up in a test report unless something looks for them.
"""

from __future__ import annotations

import pathlib
import re

import pytest

WORKFLOW = pathlib.Path(__file__).resolve().parents[1] / ".github" / "workflows" / "tests.yml"


def _pattern_for(output: str) -> str:
    """The grep alternation whose match sets `output`, pulled out of the shell block."""
    text = WORKFLOW.read_text(encoding="utf-8")
    # The condition sits on the `if` line directly above the `echo "<output>=true"` it guards.
    m = re.search(r"grep -q(v?)E '\^\((?P<alts>[^']+)\)'[^\n]*\n\s*echo \"%s=true\"" % output,
                  text)
    assert m, "no condition in the workflow sets %s=true" % output
    return m.group("alts")


def _alternatives(pattern: str) -> list[str]:
    return [a for a in pattern.split("|") if a]


@pytest.fixture(scope="module")
def router() -> dict:
    assert WORKFLOW.is_file(), "the workflow is not at %s" % WORKFLOW
    return {"engine": _pattern_for("engine"), "lab": _pattern_for("lab")}


def test_a_path_that_wakes_the_lab_lane_does_not_also_wake_the_engine(router):
    """Falsified by adding a design-only directory to one list and not the other.

    This is the bug the router shipped with. The engine condition is an EXCLUSION -- the engine
    runs unless every changed path matches it -- so a design directory missing from it wakes the
    full suite, silently and for ever, and the only symptom is the clock.
    """
    missed = []
    for alt in _alternatives(router["lab"]):
        sample = alt.rstrip("$") + ("" if alt.endswith("/") else "/x")
        sample = sample if sample.endswith("/x") else sample + "x"
        if not re.match("^(%s)" % router["engine"], sample):
            missed.append(alt)
    assert not missed, (
        "these wake the lab lane and are not excused from the engine lane, so every change to "
        "them runs the whole engine suite for nothing: %s" % ", ".join(missed))


def test_every_lab_directory_under_tests_is_known_to_the_router(router):
    """Falsified by creating tests/<something>_lab/ and not telling the workflow about it.

    A new lab directory that nobody routes is worse than one routed wrongly: its guards do not run
    at all on a change that only touches them, because the lab lane never wakes. The directories
    are on disk, so the test can look rather than be told.
    """
    here = pathlib.Path(__file__).resolve().parent
    labs = sorted(d.name for d in here.iterdir()
                  if d.is_dir() and not d.name.startswith(("_", ".")))
    unrouted = [d for d in labs
                if not re.match("^(%s)" % router["lab"], "tests/%s/x" % d)]
    assert not unrouted, (
        "these test directories exist and no lane wakes for them: %s" % ", ".join(unrouted))
