"""Seeded setup-scenario generator for deterministic file creation."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from pilgrim.model.duties import DUTY_CATEGORIES, DUTY_POSITIONS
from pilgrim.rules.dummy import seed_dummy_groups
from pilgrim.setup.timeline import (
    assign_building_live_rounds,
    build_abstract_setup_timeline,
    generate_pilgrimage_rolls,
    grouped_live_rounds_by_level,
    pilgrimage_rounds_from_rolls,
)

SUPPORTED_PLAYER_COUNTS: tuple[int, ...] = (2, 3, 4)
SETUP_TITHE_COUNTER_POOL: tuple[str, ...] = (
    "stone",
    "stone",
    "wheat",
    "wheat",
    "silver",
    "silver",
    "cornucopia",
)


def generate_setup_scenario(
    player_count: int,
    seed: int,
    scenario_name: str | None = None,
) -> dict[str, Any]:
    """Return one deterministic generated setup scenario dictionary."""
    if player_count not in SUPPORTED_PLAYER_COUNTS:
        raise ValueError(
            f"Unsupported player count {player_count}. Supported: {SUPPORTED_PLAYER_COUNTS}."
        )

    rng = random.Random(seed)
    duty_tiles = _generate_duty_tiles(rng)
    tithe_counters = _generate_tithe_counters(rng, duty_tiles)
    building_ids_by_level = _building_ids_by_level_from_default_catalogue()
    building_level_lookup = _building_level_lookup_from_grouped_ids(building_ids_by_level)
    building_market = _generate_building_market(rng, by_level=building_ids_by_level)
    pilgrimage_rolls = generate_pilgrimage_rolls(rng)
    pilgrimage_rounds = pilgrimage_rounds_from_rolls(pilgrimage_rolls)
    setup_timeline = build_abstract_setup_timeline(
        pilgrimage_rounds=pilgrimage_rounds,
        building_market=building_market,
        building_levels=building_level_lookup,
    )
    building_availability = assign_building_live_rounds(
        timeline=setup_timeline,
        building_market=building_market,
    )
    grouped_live_rounds = grouped_live_rounds_by_level(
        building_market=building_market,
        building_levels=building_level_lookup,
        building_live_rounds=building_availability,
    )
    dummy_groups = seed_dummy_groups(player_count)
    player_ids = _player_ids_for_count(player_count)
    scenario_id = scenario_name or f"generated_setup_{player_count}p_seed_{seed}"

    players: dict[str, Any] = {}
    for player_id in player_ids:
        players[player_id] = _starting_player_state()

    return {
        "scenario_id": scenario_id,
        "root_player_id": "player_one",
        "opponent_model": {"type": "sandbox_active_player_max"},
        "player_count": player_count,
        "board_file": "configs/board.json",
        "duties_file": "configs/duties.json",
        "piety_file": "configs/piety.json",
        "alms_file": "configs/alms.json",
        "timing_file": "configs/timing.json",
        "merchant_file": "configs/merchant.json",
        "ship_file": "configs/ship.json",
        "buildings_file": "configs/buildings.json",
        "duty_tiles": duty_tiles,
        "tithe_counters": tithe_counters,
        "setup_metadata": {
            "generated": True,
            "seed": seed,
            "player_count": player_count,
            "setup_sow_required": True,
            "setup_sow_implemented": True,
            "setup_timeline": {
                "pilgrimage_rolls": pilgrimage_rolls,
                "pilgrimage_rounds": pilgrimage_rounds,
                "building_live_rounds": grouped_live_rounds,
            },
            "note": (
                "Generated setup is deterministic. "
                "Each real player must complete setup sow before normal play."
            ),
        },
        "initial_state": {
            # Both lines below name that seat, and they are not one line twice. The marker is who
            # HOLDS it, for the whole first round and past the choice about to be made; the active
            # player is who is being waited on, which is the holder only until they answer. A
            # generated game always writes the marker, so the seal is drawn from the first frame --
            # unlike a saved fixture, which may not know.
            "active_player": "player_one",
            "first_player_marker": "player_one",
            "phase": "start_player_selection",
            "setup": {
                "setup_sow_required": True,
                "setup_sow_complete": False,
                "setup_sow_completed_by": [],
            },
            "merchant_board_position": _taxation_board_position(duty_tiles),
            "ship_position": 0,
            "completed_rounds": 0,
            "game_over": False,
            "timing": {
                "absolute_turn": 0,
                "round_number": 1,
                "season_number": 1,
                "turn_in_round": 0,
            },
            "dummy_acolytes": {
                "north_group": list(dummy_groups.north_group),
                "south_group": list(dummy_groups.south_group),
            },
            "building_market": building_market,
            "building_availability": building_availability,
            "players": players,
        },
    }


def _generate_duty_tiles(rng: random.Random) -> dict[str, str]:
    categories = list(DUTY_CATEGORIES)
    rng.shuffle(categories)
    return dict(zip(DUTY_POSITIONS, categories, strict=True))


def _taxation_board_position(duty_tiles: dict[str, str]) -> int:
    """Where the Merchant starts: a lookup on this seed's shuffle, not a constant.

    The tiles are dealt before this is read, so Taxation lands somewhere different from seed to
    seed and the Merchant's opening position moves with it.
    """
    taxation_position = next(
        position for position, category in duty_tiles.items() if category == "taxation"
    )
    return 1 + DUTY_POSITIONS.index(taxation_position)


def _generate_tithe_counters(
    rng: random.Random,
    duty_tiles: dict[str, str],
) -> dict[str, str]:
    taxation_position = next(
        position_name for position_name, category in duty_tiles.items() if category == "taxation"
    )
    counters = list(SETUP_TITHE_COUNTER_POOL)
    rng.shuffle(counters)

    non_taxation_positions = [
        position_name for position_name in DUTY_POSITIONS if position_name != taxation_position
    ]
    return dict(zip(non_taxation_positions, counters, strict=True))


def _generate_building_market(
    rng: random.Random,
    *,
    by_level: dict[int, tuple[str, ...]],
) -> list[str]:
    market: list[str] = []
    for level in (1, 2, 3):
        pool = list(by_level[level])
        rng.shuffle(pool)
        market.extend(pool[:4])
    return market


def _building_ids_by_level_from_default_catalogue() -> dict[int, tuple[str, ...]]:
    config_path = Path(__file__).resolve().parents[2] / "configs" / "buildings.json"
    with config_path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    catalogue = raw.get("catalogue")
    if not isinstance(catalogue, list):
        raise ValueError("configs/buildings.json must contain a 'catalogue' list.")

    by_level: dict[int, list[str]] = {1: [], 2: [], 3: []}
    for entry in catalogue:
        if not isinstance(entry, dict):
            raise ValueError("Building catalogue entries must be JSON objects.")
        level = int(entry["level"])
        building_id = str(entry["id"])
        if level not in by_level:
            raise ValueError(f"Unsupported building level in catalogue: {level}.")
        by_level[level].append(building_id)

    for level in (1, 2, 3):
        if len(by_level[level]) != 8:
            raise ValueError(
                "Building catalogue must contain exactly 8 buildings per level; "
                f"found {len(by_level[level])} at level {level}."
            )
    return {level: tuple(ids) for level, ids in by_level.items()}


def _building_level_lookup_from_grouped_ids(
    grouped_ids: dict[int, tuple[str, ...]],
) -> dict[str, int]:
    lookup: dict[str, int] = {}
    for level, building_ids in grouped_ids.items():
        for building_id in building_ids:
            lookup[building_id] = level
    return lookup


def _player_ids_for_count(player_count: int) -> tuple[str, ...]:
    return {
        2: ("player_one", "player_two"),
        3: ("player_one", "player_two", "player_three"),
        4: ("player_one", "player_two", "player_three", "player_four"),
    }[player_count]


def _starting_player_state() -> dict[str, Any]:
    return {
        "victory_points": 0,
        "piety": 0,
        "alms_position": 0,
        "resources": {
            "stone": 1,
            "silver": 1,
            "wheat": 1,
        },
        "workforce": {
            "mancala": [5, 0, 0, 0, 0, 0, 0, 0, 0],
            "village": 8,
            "abbey": 3,
            "committed": {
                "roads": 0,
                "shrines": 0,
                "market_ports": 0,
                "pilgrimage_sites": 0,
                "alms_table": 0,
            },
        },
        "special_activities": {
            "fields": False,
            "road_engineer": False,
            "stone_mason": False,
            "alms_house": False,
            "engraver": False,
            "vestry": False,
        },
        "player_board_slots": {
            "active_buildings": [],
            "donated_buildings": [],
            "cardinal_favor_tiles": 0,
        },
    }
