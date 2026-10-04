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


def _sample(alt: str) -> str:
    """A path the alternative `alt` is meant to match, as the shell would see it.

    THE ALTERNATIVES ARE REGEX, NOT PATHS. They carry escapes and anchors -- `\\.github/` and
    `tests/test_ci_router\\.py$` -- and an earlier version of this built its sample by stripping a
    trailing `$` and gluing on an "x", which turned the first into `\\.github/x`: a path with a
    literal backslash in it, matching nothing, so the test reported two correctly-excused paths as
    missing. The sample has to be a path, so the escapes come out and the anchor decides whether
    the pattern names a file or a directory.
    """
    s = alt.replace("\\.", ".")
    if s.endswith("$"):
        return s[:-1]                      # anchored: the pattern names one exact file
    return s + ("x" if s.endswith("/") else "/x")


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
        if not re.match("^(%s)" % router["engine"], _sample(alt)):
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
    # AND THE ROUTER'S OWN GUARD HAS TO BE IN A LANE THAT RUNS IT. .github/ stopped waking the
    # engine on the strength of this file existing; if nothing runs it, that trade was a loss.
    assert re.match("^(%s)" % router["lab"], "tests/test_ci_router.py"), (
        "this test does not wake the lab lane, so a router change runs nothing that checks it")
    lane = WORKFLOW.read_text(encoding="utf-8")
    assert "tests/test_ci_router.py" in lane.split("run: pytest tests/action_board/")[1][:200], (
        "the lab lane does not run tests/test_ci_router.py")
    assert not unrouted, (
        "these test directories exist and no lane wakes for them: %s" % ", ".join(unrouted))


# A PATH THAT STOPS TRIGGERING SOMETHING HAS TO START TRIGGERING SOMETHING ELSE. The workflow
# states this rule in as many words and nothing enforced it, which is how .github/ could have been
# excused from the engine lane and left waking nothing at all -- a router you can edit with no
# lane running. The two recorded exceptions are below, with their reasons.
NOTHING_TO_RUN = {
    # CI checks out a clean tree, where an ignore rule has nothing to ignore.
    "\\.gitignore$": "an ignore rule cannot change what any test does",
    # Prose. No test reads it.
    "docs/": "documentation, which no test loads",
}


def _wakes_ui(path: str) -> bool:
    """The UI lane's condition is a pipeline, not one pattern: under ui/ but not under board_v2/."""
    return path.startswith("ui/") and not path.startswith("ui/board_v2/")


def test_everything_excused_from_the_engine_still_wakes_a_lane(router):
    """Falsified by excusing a path from the engine lane and not giving it one of its own.

    This is the half of the rule that was never checked. The engine condition is an EXCLUSION, so
    adding a path to it is subtraction: the lane stops running for that path and, unless some
    other condition names it, NOTHING does. A router you can edit with no lane running is worse
    than a router that runs everything, because the first failure is silent and the second is
    only slow.
    """
    orphans = []
    for alt in _alternatives(router["engine"]):
        if alt in NOTHING_TO_RUN:
            continue
        sample = _sample(alt)
        import re as _re
        if _wakes_ui(sample) or _re.match("^(%s)" % router["lab"], sample):
            continue
        orphans.append(alt)
    assert not orphans, (
        "these are excused from the engine lane and wake no other lane, so a change to them runs "
        "nothing at all: %s" % ", ".join(orphans))
