from __future__ import annotations

from pilgrim.model.enums import TurnResolutionType


def test_turn_resolution_type_accepts_legacy_action_name_values() -> None:
    assert TurnResolutionType("give_alms") is TurnResolutionType.GIVE_ALMS_PAID
    assert (
        TurnResolutionType("donate_building")
        is TurnResolutionType.GIVE_ALMS_DONATE_BUILDING
    )
    assert (
        TurnResolutionType("construct_deferred")
        is TurnResolutionType.CONSTRUCT_ROAD_DEFERRED
    )
