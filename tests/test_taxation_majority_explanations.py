from __future__ import annotations

from collections.abc import Callable

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import FullTurnAction
from pilgrim.model.enums import TurnResolutionType
from pilgrim.rules.transition import legal_actions, taxation_majority_unlocks_for_action


def _bonus_taxation_action(
    path: str,
    predicate: Callable[[FullTurnAction], bool],
) -> tuple[object, FullTurnAction]:
    scenario = load_scenario(path)
    action = next(
        candidate
        for candidate in legal_actions(scenario.state, scenario.config)
        if isinstance(candidate, FullTurnAction)
        and candidate.resolution is TurnResolutionType.TAXATION
        and candidate.taxation_step2_resources
        and predicate(candidate)
    )
    return scenario, action


@pytest.mark.parametrize(
    ("path", "predicate", "expected"),
    (
        (
            "scenarios/taxation_three_bonus_types_001.json",
            lambda action: (
                action.effective_acolyte_building_id is None
                and action.taxation_majority_building_id is None
            ),
            (
                ("ordination", ("silver",), "real_count", 1, 1, 0),
                ("allocation", ("stone",), "real_count", 1, 1, 0),
                ("produce", ("wheat",), "real_count", 1, 1, 0),
            ),
        ),
        (
            "scenarios/scriptorium_taxation_majority_other_tiles_001.json",
            lambda action: action.effective_acolyte_building_id == "scriptorium",
            (
                ("ordination", ("silver",), "scriptorium", 1, 2, 1),
                ("allocation", ("stone",), "scriptorium", 1, 2, 1),
            ),
        ),
        (
            "scenarios/customs_house_active_taxation_majority_001.json",
            lambda action: action.taxation_majority_building_id == "customs_house",
            (
                ("ordination", ("silver",), "customs_house", 1, 1, 1),
                ("allocation", ("stone",), "customs_house", 1, 1, 1),
            ),
        ),
    ),
)
def test_taxation_majority_unlocks_expose_tile_resource_count_and_reason(
    path: str,
    predicate: Callable[[FullTurnAction], bool],
    expected: tuple[tuple[str, tuple[str, ...], str, int, int, int], ...],
) -> None:
    scenario, action = _bonus_taxation_action(path, predicate)

    unlocks = taxation_majority_unlocks_for_action(scenario.state, scenario.config, action)

    assert tuple(
        (
            unlock.duty_category,
            unlock.resources,
            unlock.majority_reason,
            unlock.player_acolytes,
            unlock.effective_player_acolytes,
            unlock.competing_acolytes,
        )
        for unlock in unlocks
    ) == expected
