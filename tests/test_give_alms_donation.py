from __future__ import annotations

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.buildings import PlayerBoardSlots
from pilgrim.model.enums import EventType, PlayerId, TurnPhase, TurnResolutionType
from pilgrim.model.resources import Resources
from pilgrim.model.special_activities import SpecialActivities
from pilgrim.model.state import GameState, PlayerState
from pilgrim.model.workforce import Workforce
from pilgrim.rules.buildings import used_player_board_slots
from pilgrim.rules.transition import apply_action, legal_actions


def _give_alms_state(
    *,
    player_one_resources: Resources,
    player_one_mancala: tuple[int, ...],
    player_two_mancala: tuple[int, ...] = (0, 0, 0, 0, 0, 0, 0, 0, 0),
    table_player_count: int = 2,
    alms_position: int = 0,
    active_buildings: tuple[str, ...] = ("confession_box",),
    donated_buildings: tuple[str, ...] = (),
    special_activities: SpecialActivities | None = None,
) -> GameState:
    return GameState(
        active_player=PlayerId.PLAYER_ONE,
        phase=TurnPhase.SOW,
        players=(
            PlayerState(
                resources=player_one_resources,
                alms_position=alms_position,
                workforce=Workforce(
                    mancala=player_one_mancala,
                    village=1,
                    abbey=0,
                ),
                special_activities=special_activities or SpecialActivities(),
                player_board_slots=PlayerBoardSlots(
                    active_buildings=active_buildings,
                    donated_buildings=donated_buildings,
                    cardinal_favor_tiles=0,
                ),
            ),
            PlayerState(
                resources=Resources(stone=0, silver=0, wheat=0),
                workforce=Workforce(
                    mancala=player_two_mancala,
                    village=0,
                    abbey=0,
                ),
            ),
        ),
        table_player_count=table_player_count,
        turn=0,
    )


def test_give_alms_legal_actions_include_paid_and_donate_building_options() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    state = _give_alms_state(
        player_one_resources=Resources(stone=0, silver=2, wheat=0),
        player_one_mancala=(0, 0, 0, 0, 1, 0, 0, 0, 0),
        table_player_count=4,
        active_buildings=("confession_box", "chapel"),
    )

    actions = legal_actions(state, scenario.config)
    give_alms_actions = [
        action for action in actions if action.resolution is TurnResolutionType.GIVE_ALMS_PAID
    ]
    donate_actions = [
        action for action in actions if action.resolution is TurnResolutionType.GIVE_ALMS_DONATE_BUILDING
    ]

    assert give_alms_actions
    assert any(
        action.alms_payment_silver == 2 and action.alms_payment_wheat == 0
        for action in give_alms_actions
    )
    assert all(action.donate_building_id is None for action in give_alms_actions)

    assert {action.donate_building_id for action in donate_actions} == {
        "confession_box",
        "chapel",
    }
    assert all(action.alms_payment_silver == 0 for action in donate_actions)
    assert all(action.alms_payment_wheat == 0 for action in donate_actions)
    assert all(action.alms_house_extra_silver == 0 for action in donate_actions)
    assert all(action.alms_house_extra_wheat == 0 for action in donate_actions)
    assert all(action.resolution.value != "give_alms" for action in actions)
    assert all(action.resolution.value != "donate_building" for action in actions)


def test_give_alms_legal_actions_do_not_generate_donate_without_active_buildings() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    state = _give_alms_state(
        player_one_resources=Resources(stone=0, silver=2, wheat=0),
        player_one_mancala=(0, 0, 0, 0, 1, 0, 0, 0, 0),
        table_player_count=4,
        active_buildings=(),
        donated_buildings=("confession_box",),
    )

    actions = legal_actions(state, scenario.config)
    assert not any(
        action.resolution is TurnResolutionType.GIVE_ALMS_DONATE_BUILDING for action in actions
    )


def test_give_alms_legal_actions_skip_unknown_or_already_donated_buildings() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    unknown_state = _give_alms_state(
        player_one_resources=Resources(stone=0, silver=2, wheat=0),
        player_one_mancala=(0, 0, 0, 0, 1, 0, 0, 0, 0),
        table_player_count=4,
        active_buildings=("not_a_real_building",),
    )
    already_donated_state = _give_alms_state(
        player_one_resources=Resources(stone=0, silver=2, wheat=0),
        player_one_mancala=(0, 0, 0, 0, 1, 0, 0, 0, 0),
        table_player_count=4,
        active_buildings=("confession_box",),
        donated_buildings=("confession_box",),
    )

    unknown_actions = legal_actions(unknown_state, scenario.config)
    already_donated_actions = legal_actions(already_donated_state, scenario.config)

    assert not any(
        action.resolution is TurnResolutionType.GIVE_ALMS_DONATE_BUILDING for action in unknown_actions
    )
    assert not any(
        action.resolution is TurnResolutionType.GIVE_ALMS_DONATE_BUILDING
        for action in already_donated_actions
    )


def test_donate_building_action_moves_building_advances_alms_and_keeps_slot_usage() -> None:
    scenario = load_scenario("scenarios/give_alms_donate_building_001.json")
    before_player = scenario.state.player_state(PlayerId.PLAYER_ONE)
    before_used_slots = used_player_board_slots(before_player)
    action = legal_actions(scenario.state, scenario.config)[0]

    assert action.resolution is TurnResolutionType.GIVE_ALMS_DONATE_BUILDING
    assert action.donate_building_id == "confession_box"
    assert action.alms_payment_silver == 0
    assert action.alms_payment_wheat == 0

    result = apply_action(scenario.state, action, scenario.config)
    after_player = result.state.player_state(PlayerId.PLAYER_ONE)

    assert after_player.player_board_slots.active_buildings == ()
    assert after_player.player_board_slots.donated_buildings == ("confession_box",)
    assert used_player_board_slots(after_player) == before_used_slots
    assert after_player.alms_position == before_player.alms_position + 1
    assert after_player.victory_points == before_player.victory_points + 2
    assert result.state.player_vector(PlayerId.PLAYER_ONE)[0] == 1
    assert result.state.player_vector(PlayerId.PLAYER_ONE)[5] == 0

    event_types = {event.event_type for event in result.events}
    assert EventType.BUILDING_DONATION in event_types
    assert EventType.ALMS_PROGRESS in event_types
    assert EventType.ACOLYTE_RECALL in event_types
    assert EventType.ALMS_PAYMENT not in event_types

    donation_event = next(
        event for event in result.events if event.event_type is EventType.BUILDING_DONATION
    )
    donation_details = dict(donation_event.details)
    assert donation_details["building_id"] == "confession_box"
    assert donation_details["donation_vp"] == 2


def test_donate_building_majority_still_advances_alms_by_exactly_one_and_no_payment_event() -> None:
    scenario = load_scenario("scenarios/give_alms_donate_building_majority_001.json")
    action = legal_actions(scenario.state, scenario.config)[0]
    result = apply_action(scenario.state, action, scenario.config)
    after_player = result.state.player_state(PlayerId.PLAYER_ONE)

    duty_event = next(
        event for event in result.events if event.event_type is EventType.DUTY_RESOLUTION
    )
    duty_details = dict(duty_event.details)
    alms_progress_event = next(
        event for event in result.events if event.event_type is EventType.ALMS_PROGRESS
    )
    alms_progress_details = dict(alms_progress_event.details)

    assert action.resolution is TurnResolutionType.GIVE_ALMS_DONATE_BUILDING
    assert action.donate_building_id == "bank"
    assert duty_details["duty_value"] == 2
    assert duty_details["effect"] == "give_alms_donate_building"
    assert alms_progress_details["old_row"] == 0
    assert alms_progress_details["new_row"] == 1
    assert after_player.alms_position == 1
    assert after_player.victory_points == 6
    assert not any(event.event_type is EventType.ALMS_PAYMENT for event in result.events)


def test_donate_building_crossing_threshold_applies_threshold_reward() -> None:
    scenario = load_scenario("scenarios/give_alms_donate_building_threshold_001.json")
    action = legal_actions(scenario.state, scenario.config)[0]
    result = apply_action(scenario.state, action, scenario.config)
    after_player = result.state.player_state(PlayerId.PLAYER_ONE)

    assert after_player.alms_position == 2
    assert after_player.workforce.village == 0
    assert after_player.workforce.abbey == 1

    threshold_event = next(
        event for event in result.events if event.event_type is EventType.ALMS_THRESHOLD_REWARD
    )
    threshold_details = dict(threshold_event.details)
    assert threshold_details["threshold"] == 2
    assert threshold_details["moved"] is True


def test_donate_building_applies_minority_silver_cost() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    state = _give_alms_state(
        player_one_resources=Resources(stone=0, silver=1, wheat=0),
        player_one_mancala=(0, 0, 0, 0, 1, 0, 0, 0, 0),
        player_two_mancala=(0, 0, 0, 0, 0, 2, 0, 0, 0),
        table_player_count=4,
        active_buildings=("confession_box",),
    )
    action = next(
        candidate
        for candidate in legal_actions(state, scenario.config)
        if candidate.resolution is TurnResolutionType.GIVE_ALMS_DONATE_BUILDING
    )

    result = apply_action(state, action, scenario.config)
    after_player = result.state.player_state(PlayerId.PLAYER_ONE)
    resource_event = next(
        event for event in result.events if event.event_type is EventType.RESOURCE_DELTA
    )
    resource_details = dict(resource_event.details)

    assert after_player.resources.silver == 0
    assert resource_details["silver"] == -1
    assert not any(event.event_type is EventType.ALMS_PAYMENT for event in result.events)


def test_alms_house_bonus_does_not_apply_to_donate_building() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    state = _give_alms_state(
        player_one_resources=Resources(stone=0, silver=3, wheat=1),
        player_one_mancala=(0, 0, 0, 0, 1, 0, 0, 0, 0),
        table_player_count=4,
        active_buildings=("confession_box",),
        special_activities=SpecialActivities(alms_house=True),
    )
    actions = legal_actions(state, scenario.config)
    give_alms_actions = [
        action for action in actions if action.resolution is TurnResolutionType.GIVE_ALMS_PAID
    ]
    donate_action = next(
        action for action in actions if action.resolution is TurnResolutionType.GIVE_ALMS_DONATE_BUILDING
    )
    result = apply_action(state, donate_action, scenario.config)
    alms_progress_event = next(
        event for event in result.events if event.event_type is EventType.ALMS_PROGRESS
    )
    alms_progress_details = dict(alms_progress_event.details)

    assert any(
        action.alms_house_extra_silver == 1 or action.alms_house_extra_wheat == 1
        for action in give_alms_actions
    )
    assert alms_progress_details["old_row"] == 0
    assert alms_progress_details["new_row"] == 1
    assert not any(
        event.event_type is EventType.SPECIAL_ACTIVITY_BONUS
        and dict(event.details).get("activity") == "alms_house"
        for event in result.events
    )


def test_paid_give_alms_behavior_remains_available_without_active_buildings() -> None:
    scenario = load_scenario("scenarios/special_activity_alms_house_001.json")
    actions = legal_actions(scenario.state, scenario.config)

    assert any(action.resolution is TurnResolutionType.GIVE_ALMS_PAID for action in actions)
    assert not any(action.resolution is TurnResolutionType.GIVE_ALMS_DONATE_BUILDING for action in actions)
