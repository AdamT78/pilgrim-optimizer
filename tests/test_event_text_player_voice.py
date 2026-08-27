"""Guards for the player-facing event formatter's fallback surface.

The fallback to `format_event` is intentional: dropping an event silently is worse than showing a
developer sentence. But fallback growth must be deliberate, so this list is pinned and reviewed.
"""

from __future__ import annotations

import re

import pytest

from pilgrim.io import event_text
from pilgrim.io.event_text import PLAYER_EVENT_FALLBACK_TYPES, format_event_for_players
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import EventType
from pilgrim.rules.transition import (
    apply_action,
    apply_turn_step,
    legal_actions,
    turn_step_id,
    turn_steps,
)
from tools.audits.text_inventory import scenario_paths


def test_the_event_types_still_using_developer_fallback_are_explicit() -> None:
    expected = [
        "alms_season_end",
        "alms_season_reward",
        "alms_reset",
        "dummy_acolyte_move",
        "confession_box_bonus",
        "confession_box_declined",
        "excess_resource_cap",
        "excess_check",
        "excess_discard",
        "trade_route_income",
        "game_end",
        "season_end_deferred",
        "season_end",
    ]
    assert [event.value for event in PLAYER_EVENT_FALLBACK_TYPES] == expected


_DEBUG_EVENT_PREFIX = re.compile(r"^[A-Z][A-Z0-9_]*:")
_PLAYER_BONUS_EVENT_TYPES = {EventType.BUILDING_BONUS, EventType.SPECIAL_ACTIVITY_BONUS}


def _player_events_from_the_corpus():
    for path in scenario_paths():
        scenario = load_scenario(path)
        for action in legal_actions(scenario.state, scenario.config):
            for event in apply_action(scenario.state, action, scenario.config).events:
                yield event, scenario.config
        for step in turn_steps(scenario.state, scenario.config):
            applied_step_id = turn_step_id(step)
            for event in apply_turn_step(scenario.state, scenario.config, step).events:
                if event.action_id == applied_step_id:
                    yield event, scenario.config


def _bonus_line_is_intentionally_absent(event) -> bool:
    details = dict(event.details)
    if bool(details.get("player_line_suppressed", False)):
        return True
    if event.event_type is EventType.BUILDING_BONUS and (
        "enabled_route" in details or "skipped_location" in details
    ):
        return True
    return event_text._bonus_delta_is_zero(details)


def _assert_the_corpus_has_no_accidental_debug_player_text() -> None:
    for event, config in _player_events_from_the_corpus():
        line = format_event_for_players(event, config)
        if event.event_type in PLAYER_EVENT_FALLBACK_TYPES:
            continue
        if line is None:
            if bool(dict(event.details).get("player_line_suppressed", False)):
                assert event.event_type not in PLAYER_EVENT_FALLBACK_TYPES
                continue
            if event.event_type in _PLAYER_BONUS_EVENT_TYPES:
                assert _bonus_line_is_intentionally_absent(event), (
                    f"{event.event_type.value} {dict(event.details)!r} returned no player line"
                )
            continue
        assert not _DEBUG_EVENT_PREFIX.match(line), (
            f"{event.event_type.value} leaked debug player text: {line!r}"
        )


def test_the_corpus_has_no_accidental_debug_player_text() -> None:
    _assert_the_corpus_has_no_accidental_debug_player_text()


def test_the_corpus_guard_catches_a_written_bonus_subcase_returning_none(monkeypatch) -> None:
    original = event_text._building_bonus_for_players

    def without_pulpit(actor: str, details: dict) -> str | None:
        if details.get("building") == "pulpit":
            return None
        return original(actor, details)

    monkeypatch.setattr(event_text, "_building_bonus_for_players", without_pulpit)

    with pytest.raises(AssertionError, match=r"building_bonus.*pulpit"):
        _assert_the_corpus_has_no_accidental_debug_player_text()
