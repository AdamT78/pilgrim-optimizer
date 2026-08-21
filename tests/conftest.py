from __future__ import annotations

from pathlib import Path

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.rules.transition import legal_actions

REPO = Path(__file__).resolve().parents[1]
DEEP_FIXTURE_PATH = REPO / "scenarios" / "deep_round_eighteen_seed_seven_two_player_001.json"
SCENARIO_PATHS = tuple(sorted((REPO / "scenarios").glob("*.json")))
PLAYTEST_PATHS = tuple(sorted((REPO / "scenarios" / "playtest").glob("*.json")))


@pytest.fixture(scope="session")
def corpus_actions():
    """The committed corpus, loaded and enumerated once for the whole test session.

    Under pytest-xdist this is once per WORKER, not once per entire run; workers do not share
    session fixtures. That trades repeated setup for parallel wall-clock time when xdist is used.
    """
    return tuple(
        (path, scenario, tuple(legal_actions(scenario.state, scenario.config)))
        for path in SCENARIO_PATHS
        for scenario in (load_scenario(path),)
    )


@pytest.fixture(scope="session")
def playtest_actions():
    """The small playtest corpus, loaded and enumerated once for the whole test session."""
    return tuple(
        (path, scenario, tuple(legal_actions(scenario.state, scenario.config)))
        for path in PLAYTEST_PATHS
        for scenario in (load_scenario(path),)
    )


@pytest.fixture(scope="session")
def deep_actions(corpus_actions):
    """The deep fixture, loaded and enumerated once for the whole test session.

    The corpus_actions fixture owns the load and enumeration, so the deep position is not
    generated a second time. Under pytest-xdist the parent fixture is once per worker, not once
    per entire run.
    """
    for path, scenario, actions in corpus_actions:
        if path == DEEP_FIXTURE_PATH:
            return scenario, actions
    raise AssertionError(f"missing deep fixture: {DEEP_FIXTURE_PATH}")


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark tests that use the shared deep_actions fixture as slow."""
    here = Path(__file__).resolve()
    for item in items:
        fixture_info = getattr(item, "_fixtureinfo", None)
        if fixture_info is None:
            continue
        fixture_defs = fixture_info.name2fixturedefs.get("deep_actions", ())
        uses_shared_fixture = any(
            Path(fixture_def.func.__code__.co_filename).resolve() == here
            for fixture_def in fixture_defs
        )
        if uses_shared_fixture:
            item.add_marker(pytest.mark.slow)
