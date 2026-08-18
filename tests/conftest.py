from __future__ import annotations

from pathlib import Path

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.rules.transition import legal_actions

REPO = Path(__file__).resolve().parents[1]
DEEP_FIXTURE_PATH = REPO / "scenarios" / "deep_round_eighteen_seed_seven_two_player_001.json"


@pytest.fixture(scope="session")
def deep_actions():
    """The deep fixture, loaded and enumerated once for the whole test session.

    Under pytest-xdist this is once per WORKER, not once per entire run; if xdist is added later,
    keep deep-fixture tests on one worker (`--dist=loadfile` or an xdist_group) or this saving is
    lost.
    """
    scenario = load_scenario(DEEP_FIXTURE_PATH)
    return scenario, tuple(legal_actions(scenario.state, scenario.config))


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
