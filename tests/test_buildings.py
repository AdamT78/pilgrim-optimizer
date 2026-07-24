from dataclasses import replace

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.buildings import PlayerBoardSlots
from pilgrim.model.enums import PlayerId
from pilgrim.rules.buildings import (
    available_player_board_slots,
    building_live_round,
    building_by_id,
    buildings_by_level,
    default_building_market,
    future_buildings,
    has_available_player_board_slot,
    is_building_live,
    live_buildings,
    used_player_board_slots,
    validate_building_availability,
    validate_building_catalogue,
    validate_building_market,
    validate_building_state,
    validate_player_board_slots,
)
from pilgrim.rules.validation import TransitionValidationError


def test_building_catalogue_has_expected_size_and_level_distribution() -> None:
    scenario = load_scenario("scenarios/building_market_001.json")
    config = scenario.config.buildings
    validate_building_catalogue(config)
    assert len(config.catalogue) == 24
    for level in (1, 2, 3):
        assert len(buildings_by_level(config, level)) == 8


def test_building_catalogue_contains_expected_ids() -> None:
    scenario = load_scenario("scenarios/building_market_001.json")
    expected_ids = {
        "confession_box",
        "chapel",
        "chapter_house",
        "guild",
        "infirmary",
        "mint",
        "quarry",
        "well",
        "brewery",
        "cloisters",
        "dormitory",
        "grain_store",
        "indulgences",
        "library",
        "reliquary",
        "stone_yard",
        "bank",
        "customs_house",
        "inquisition",
        "kogge",
        "mill",
        "pulpit",
        "scriptorium",
        "wagon_yard",
    }
    actual_ids = {building.id for building in scenario.config.buildings.catalogue}
    assert actual_ids == expected_ids


def test_building_catalogue_cost_vp_and_effect_metadata() -> None:
    scenario = load_scenario("scenarios/building_market_001.json")
    expected_vp = {1: 2, 2: 4, 3: 6}
    ids: list[str] = []
    names: list[str] = []
    for building in scenario.config.buildings.catalogue:
        ids.append(building.id)
        names.append(building.name)
        assert building.stone_cost == building.level
        assert building.donation_vp == expected_vp[building.level]
        assert building.effect_status == "deferred"
    assert len(set(ids)) == len(ids)
    assert len(set(names)) == len(names)


def test_building_market_is_valid_and_has_four_per_level() -> None:
    scenario = load_scenario("scenarios/building_market_001.json")
    market = scenario.state.building_market
    validate_building_market(market, scenario.config.buildings)
    assert len(market) == 12
    level_counts = {1: 0, 2: 0, 3: 0}
    for building_id in market:
        level = building_by_id(scenario.config.buildings, building_id).level
        level_counts[level] += 1
    assert level_counts == {1: 4, 2: 4, 3: 4}


def test_missing_market_uses_deterministic_fallback() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    fallback = default_building_market(scenario.config.buildings)
    assert scenario.state.building_market == fallback
    assert fallback == (
        "confession_box",
        "chapel",
        "chapter_house",
        "guild",
        "brewery",
        "cloisters",
        "dormitory",
        "grain_store",
        "bank",
        "customs_house",
        "inquisition",
        "kogge",
    )


def test_missing_availability_defaults_selected_market_to_live_round_two() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    state = scenario.state

    assert len(state.building_availability) == len(state.building_market)
    assert set(building_id for building_id, _live_round in state.building_availability) == set(
        state.building_market
    )
    assert all(live_round == 2 for _, live_round in state.building_availability)

    first_building = state.building_market[0]
    assert building_live_round(state, first_building) == 2
    assert is_building_live(state, first_building) is False
    assert is_building_live(state, first_building, round_number=2) is True


def test_live_and_future_building_helpers_reflect_current_round() -> None:
    scenario = load_scenario("scenarios/building_availability_future_001.json")
    state = scenario.state

    assert building_live_round(state, "well") == 2
    assert building_live_round(state, "chapel") == 4
    assert is_building_live(state, "well") is True
    assert is_building_live(state, "chapel") is False
    assert live_buildings(state) == ("well",)
    assert future_buildings(state)[0] == ("chapel", 4)


def test_building_market_duplicate_invalid() -> None:
    scenario = load_scenario("scenarios/building_market_001.json")
    invalid_market = scenario.state.building_market[:-1] + (scenario.state.building_market[0],)
    with pytest.raises(TransitionValidationError, match="duplicate"):
        validate_building_market(invalid_market, scenario.config.buildings)


def test_building_market_unknown_id_invalid() -> None:
    scenario = load_scenario("scenarios/building_market_001.json")
    invalid_market = scenario.state.building_market[:-1] + ("not_a_real_building",)
    with pytest.raises(ValueError, match="Unknown building id"):
        validate_building_market(invalid_market, scenario.config.buildings)


def test_building_market_wrong_level_mix_invalid() -> None:
    scenario = load_scenario("scenarios/building_market_001.json")
    invalid_market = (
        "confession_box",
        "chapel",
        "chapter_house",
        "guild",
        "infirmary",
        "brewery",
        "cloisters",
        "dormitory",
        "bank",
        "customs_house",
        "inquisition",
        "kogge",
    )
    with pytest.raises(TransitionValidationError, match="level-1"):
        validate_building_market(invalid_market, scenario.config.buildings)


def test_player_board_slots_empty_board_uses_zero_of_six() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    player_state = scenario.state.player_state(PlayerId.PLAYER_ONE)
    assert used_player_board_slots(player_state) == 0
    assert available_player_board_slots(player_state, scenario.config) == 6
    assert has_available_player_board_slot(player_state, scenario.config) is True


def test_player_board_slots_mixed_occupancy_counts_correctly() -> None:
    scenario = load_scenario("scenarios/player_board_slots_001.json")
    player_state = scenario.state.player_state(PlayerId.PLAYER_ONE)
    assert used_player_board_slots(player_state) == 4
    assert available_player_board_slots(player_state, scenario.config) == 2
    assert has_available_player_board_slot(player_state, scenario.config) is True


def test_player_board_slots_full_board_has_no_available_slots() -> None:
    scenario = load_scenario("scenarios/building_market_001.json")
    full_slots = PlayerBoardSlots(
        active_buildings=("confession_box", "chapel", "chapter_house", "guild"),
        donated_buildings=("brewery",),
        cardinal_favor_tiles=1,
    )
    validate_player_board_slots(full_slots, scenario.config.buildings)
    player_state = scenario.state.player_state(PlayerId.PLAYER_ONE)
    full_player_state = replace(player_state, player_board_slots=full_slots)
    assert used_player_board_slots(full_player_state) == 6
    assert available_player_board_slots(full_player_state, scenario.config) == 0
    assert has_available_player_board_slot(full_player_state, scenario.config) is False


def test_player_board_slots_more_than_six_invalid() -> None:
    scenario = load_scenario("scenarios/building_market_001.json")
    invalid_slots = PlayerBoardSlots(
        active_buildings=("confession_box", "chapel", "chapter_house", "guild"),
        donated_buildings=("brewery", "cloisters"),
        cardinal_favor_tiles=1,
    )
    with pytest.raises(TransitionValidationError, match="exceed limit"):
        validate_player_board_slots(invalid_slots, scenario.config.buildings)


def test_player_board_slots_active_and_donated_overlap_invalid() -> None:
    scenario = load_scenario("scenarios/building_market_001.json")
    invalid_slots = PlayerBoardSlots(
        active_buildings=("chapel",),
        donated_buildings=("chapel",),
        cardinal_favor_tiles=0,
    )
    with pytest.raises(TransitionValidationError, match="both active and donated"):
        validate_player_board_slots(invalid_slots, scenario.config.buildings)


def test_player_board_slots_unknown_building_id_invalid() -> None:
    scenario = load_scenario("scenarios/building_market_001.json")
    invalid_slots = PlayerBoardSlots(
        active_buildings=("unknown_building",),
        donated_buildings=(),
        cardinal_favor_tiles=0,
    )
    with pytest.raises(ValueError, match="Unknown building id"):
        validate_player_board_slots(invalid_slots, scenario.config.buildings)


def test_building_state_rejects_building_in_market_and_active() -> None:
    scenario = load_scenario("scenarios/building_market_001.json")
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    invalid_state = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(
            player_one,
            player_board_slots=replace(
                player_one.player_board_slots,
                active_buildings=("kogge",),
            ),
        ),
    )

    with pytest.raises(TransitionValidationError, match="multiple locations simultaneously"):
        validate_building_state(invalid_state, scenario.config)


def test_building_state_rejects_building_in_market_and_donated() -> None:
    scenario = load_scenario("scenarios/building_market_001.json")
    player_two = scenario.state.player_state(PlayerId.PLAYER_TWO)
    invalid_state = scenario.state.with_player_state(
        PlayerId.PLAYER_TWO,
        replace(
            player_two,
            player_board_slots=replace(
                player_two.player_board_slots,
                donated_buildings=("kogge",),
            ),
        ),
    )

    with pytest.raises(TransitionValidationError, match="multiple locations simultaneously"):
        validate_building_state(invalid_state, scenario.config)


def test_building_state_rejects_active_and_donated_across_players() -> None:
    scenario = load_scenario("scenarios/building_market_001.json")
    market_without_kogge = tuple(
        building_id for building_id in scenario.state.building_market if building_id != "kogge"
    )
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    player_two = scenario.state.player_state(PlayerId.PLAYER_TWO)
    invalid_state = (
        scenario.state.with_building_market(market_without_kogge)
        .with_player_state(
            PlayerId.PLAYER_ONE,
            replace(
                player_one,
                player_board_slots=replace(
                    player_one.player_board_slots,
                    active_buildings=("kogge",),
                ),
            ),
        )
        .with_player_state(
            PlayerId.PLAYER_TWO,
            replace(
                player_two,
                player_board_slots=replace(
                    player_two.player_board_slots,
                    donated_buildings=("kogge",),
                ),
            ),
        )
    )

    with pytest.raises(TransitionValidationError, match="multiple locations simultaneously"):
        validate_building_state(invalid_state, scenario.config)


def test_building_availability_rejects_live_round_below_two() -> None:
    scenario = load_scenario("scenarios/building_availability_round2_001.json")
    availability = dict(scenario.state.building_availability)
    availability["well"] = 1
    invalid_state = scenario.state.with_building_availability(tuple(sorted(availability.items())))

    with pytest.raises(TransitionValidationError, match="between 2 and 26"):
        validate_building_availability(invalid_state, scenario.config)


def test_building_availability_rejects_live_round_above_twenty_six() -> None:
    scenario = load_scenario("scenarios/building_availability_round2_001.json")
    availability = dict(scenario.state.building_availability)
    availability["well"] = 27
    invalid_state = scenario.state.with_building_availability(tuple(sorted(availability.items())))

    with pytest.raises(TransitionValidationError, match="between 2 and 26"):
        validate_building_availability(invalid_state, scenario.config)


def test_building_availability_rejects_key_not_in_selected_buildings() -> None:
    scenario = load_scenario("scenarios/building_availability_round2_001.json")
    availability = dict(scenario.state.building_availability)
    availability["mill"] = 12
    invalid_state = scenario.state.with_building_availability(tuple(sorted(availability.items())))

    with pytest.raises(TransitionValidationError, match="selected building in game state"):
        validate_building_availability(invalid_state, scenario.config)


def test_building_availability_rejects_missing_market_entry_when_explicit() -> None:
    scenario = load_scenario("scenarios/building_availability_round2_001.json")
    availability = dict(scenario.state.building_availability)
    availability.pop("well")
    invalid_state = scenario.state.with_building_availability(tuple(sorted(availability.items())))

    with pytest.raises(TransitionValidationError, match="missing building_availability round"):
        validate_building_availability(invalid_state, scenario.config)
