from __future__ import annotations

from dataclasses import replace

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import FullTurnAction
from pilgrim.model.enums import PlayerId
from pilgrim.rules.buildings import (
    building_ability_source,
    current_merchant_resource,
    is_building_live,
)
from pilgrim.rules.transition import apply_turn_step, legal_actions, turn_steps


MOVEMENT_PLAYTEST = "scenarios/playtest/movement_2p.json"


def _without_active_building(state, *, player: PlayerId, building_id: str):
    player_state = state.player_state(player)
    slots = replace(
        player_state.player_board_slots,
        active_buildings=tuple(
            building for building in player_state.player_board_slots.active_buildings
            if building != building_id
        ),
    )
    return replace(
        state.with_player_state(player, replace(player_state, player_board_slots=slots)),
        building_availability=tuple(
            (building, live_round)
            for building, live_round in state.building_availability
            if building != building_id
        ),
    )


def _route_set(state, config) -> set[tuple[int, tuple[int, ...]]]:
    return {
        (action.origin, action.route)
        for action in legal_actions(state, config)
        if isinstance(action, FullTurnAction)
    }


def test_movement_playtest_opens_with_every_promised_building_live_and_usable() -> None:
    """Keep the hand-play position honest as building effects migrate into committed steps."""
    scenario = load_scenario(MOVEMENT_PLAYTEST)
    state = scenario.state
    config = scenario.config
    player = state.active_player

    cloisters = building_ability_source(state, config, acting_player=player, building_key="cloisters")
    dormitory = building_ability_source(state, config, acting_player=player, building_key="dormitory")
    library = building_ability_source(state, config, acting_player=player, building_key="library")
    inquisition = building_ability_source(state, config, acting_player=player, building_key="inquisition")
    kogge = building_ability_source(state, config, acting_player=player, building_key="kogge")
    guild = building_ability_source(state, config, acting_player=player, building_key="guild")

    assert is_building_live(state, "cloisters") and cloisters.usable, (
        "Cloisters must be live and usable at the movement playtest opening"
    )
    assert is_building_live(state, "dormitory") and dormitory.usable, (
        "Dormitory must be live and usable at the movement playtest opening"
    )
    assert is_building_live(state, "library") and library.usable, (
        "Library must be live and usable at the movement playtest opening"
    )
    assert is_building_live(state, "inquisition") and inquisition.usable, (
        "Inquisition must be live and usable at the movement playtest opening"
    )
    assert is_building_live(state, "kogge") and kogge.usable, (
        "Kogge must be live and usable at the movement playtest opening"
    )
    assert is_building_live(state, "guild") and guild.usable, (
        "Guild must be live and usable at the movement playtest opening"
    )

    assert cloisters.source_type == "own_active", "Cloisters must be the free own-board path"
    assert dormitory.source_type == "own_active", "Dormitory must be the free own-board path"
    assert library.source_type == "live_market_hire", "Library must be a live market hire"
    assert inquisition.source_type == "live_market_hire", "Inquisition must be a live market hire"
    assert kogge.source_type == "opponent_active_hire", "Kogge must be an opponent hire"
    assert guild.source_type == "opponent_active_hire", "Guild must be an opponent hire"

    assert current_merchant_resource(state, config) == "silver", (
        "Movement playtest Merchant must stand on a counter, not Taxation"
    )
    for building_id, source in (
        ("Library", library),
        ("Inquisition", inquisition),
        ("Kogge", kogge),
        ("Guild", guild),
    ):
        assert (
            source.hire_resource == "silver"
            and source.hire_cost == 1
            and state.player_state(player).resources.silver >= source.hire_cost
        ), f"{building_id} must be payable with the Merchant's silver counter"

    steps = turn_steps(state, config)
    assert any(step.building_id == "dormitory" for step in steps), (
        "Dormitory must offer a committed step at the movement playtest opening"
    )
    assert any(step.building_id == "inquisition" for step in steps), (
        "Inquisition must offer a committed step at the movement playtest opening"
    )
    assert any(step.building_id == "guild" for step in steps), (
        "Guild must offer a committed step at the movement playtest opening"
    )
    kogge_step = next(
        (step for step in steps if step.building_id == "kogge"),
        None,
    )
    assert kogge_step is not None, "Kogge must offer a committed opponent-hire step"

    assert not any(
        step.building_id == "library" for step in turn_steps(state, config)
    ), "Library must wait for the End of Turn window before offering a committed step"

    routes = _route_set(state, config)
    routes_without_cloisters = _route_set(
        _without_active_building(state, player=PlayerId.PLAYER_ONE, building_id="cloisters"),
        config,
    )
    routes_after_hiring_kogge = _route_set(apply_turn_step(state, config, kogge_step), config)
    assert routes_without_cloisters < routes, (
        "Cloisters must widen the opening legal route set, not merely be displayed"
    )
    assert routes < routes_after_hiring_kogge, (
        "Hiring Kogge must widen the legal route set after its committed step"
    )
    assert state.round_number + 3 <= config.timing.max_rounds, (
        "Movement playtest must retain several turns after its opening turn"
    )
