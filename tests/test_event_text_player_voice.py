"""Guards for the player-facing event formatter's fallback surface.

The fallback to `format_event` is intentional: dropping an event silently is worse than showing a
developer sentence. But fallback growth must be deliberate, so this list is pinned and reviewed.
"""

from pilgrim.io.event_text import PLAYER_EVENT_FALLBACK_TYPES


def test_the_event_types_still_using_developer_fallback_are_explicit() -> None:
    expected = [
        "start_turn_relocation",
        "end_turn_relocation",
        "workforce_move",
        "building_hired",
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
