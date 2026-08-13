"""Turn one engine view payload into the shapes the renderers already take.

This file MAPS. It does not decide. Whose turn it is, what is legal, what anything scores and where
a cube may walk are all the engine's, and every one of them arrives here already answered. If a
function in here ever needs to work out a rule to fill a field in, the field is in the wrong place
and the answer belongs upstream -- a second rules implementation does not announce itself, it
accumulates one convenience at a time.

It takes a plain dict, never a `GameState`, and nothing under `tools/ui_debug` imports `pilgrim`.
That is what lets the whole UI be tested against hand-written JSON with no engine in the room, and
it is asserted by a test rather than left to discipline.

THE FOUR THINGS THIS DELIBERATELY DOES NOT REDISCOVER

1. Board position indices already agree. The engine's canonical names are city, north, north_east,
   east, south_east, south, south_west, west, north_west at 0-8, and the duty wheel emits exactly
   those names at exactly those `data-board-position-index` values. A player's mancala vector is
   therefore already indexed by UI board position. There is no translation table here and there
   must not be one: a table would be a second copy of an agreement that already holds, and would
   go stale silently the day either side added a position.

2. The duty arrangement is config, not state, so it arrives in the payload. The wheel cannot be
   drawn without it.

3. Engine player id order is NOT seat order. `player_one` is white and the table seats red first,
   so `player_one` is seat 4. Everything per-player goes through `SEATED_PLAYERS`. Indexing the
   players array by seat happens to look right at four seats and is wrong at two, where the engine
   seats `player_one` and `player_two` -- white and red, seats 4 and 1, not the first two chairs.

4. `players[].workforce.mancala` is authoritative. The payload also carries a top-level `acolytes`
   array, but it is a derived backward-compatible view of exactly the same tuples; reading both
   would be two names for one fact, and the day they disagreed only one would be right.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ui_debug.render_table_layout import SEATED_PLAYERS  # noqa: E402

CITY_POSITION = 0
RESOURCE_IDS = ("wheat", "stone", "silver")


def seated_player_ids(payload: dict) -> list[str]:
    """The engine's player ids that have a seat, in seat order, with gaps left out.

    Not the first N seats. At two players the engine seats `player_one` and `player_two`, which are
    white and red -- seats 4 and 1 -- so the occupied chairs are the two ends of the row and not
    the two nearest ends of it. Filtering the seating order by who exists is what gets that right
    without anywhere having to know the answer for each count.
    """
    present = set(player_ids_in_engine_order(payload))
    return [player_id for player_id in SEATED_PLAYERS if player_id in present]


def player_ids_in_engine_order(payload: dict) -> list[str]:
    """`player_one`, `player_two`, ... for as many as the payload carries.

    The players array has no ids in it -- position in the array IS the id, because `PlayerId` is an
    IntEnum the engine indexes state tuples with. So the names are reconstructed from the length,
    which is the one place this file is allowed to know that ordering at all.
    """
    return [f"player_{word}" for word in ("one", "two", "three", "four")][
        : len(payload["state"]["players"])
    ]


def player_record(payload: dict, player_id: str) -> dict | None:
    """One seat's engine record, or None when that seat is empty at this player count."""
    order = player_ids_in_engine_order(payload)
    if player_id not in order:
        return None
    return payload["state"]["players"][order.index(player_id)]


def acolytes_by_position(payload: dict, player_id: str) -> list[int]:
    """How many of this seat's acolytes stand on each board position, indexed by position.

    Straight off `workforce.mancala`. See point 1 and point 4 in the module docstring: the index is
    already the UI's, and this is the authoritative copy of it.
    """
    record = player_record(payload, player_id)
    return list(record["workforce"]["mancala"]) if record else []


def resources_for(payload: dict, player_id: str) -> dict[str, int]:
    record = player_record(payload, player_id)
    if record is None:
        return dict.fromkeys(RESOURCE_IDS, 0)
    return {resource: int(record["resources"][resource]) for resource in RESOURCE_IDS}


def duty_by_position_name(payload: dict) -> dict[str, str]:
    """Board position name -> the duty lying there in this scenario."""
    return {tile["position_name"]: tile["duty"] for tile in payload["duty_tiles"]}


def tithe_by_position_name(payload: dict) -> dict[str, str | None]:
    """Board position name -> the counter on that space, None on Taxation.

    Read off the position rather than carried with the tile, which is how the engine deals them.
    """
    return {tile["position_name"]: tile["tithe"] for tile in payload["duty_tiles"]}


def dummy_acolytes_by_position(payload: dict) -> list[int]:
    """The neutral acolytes on each board position, both groups added together.

    Two groups is how the engine tracks them -- they move independently at season end -- but a
    space simply has some standing on it, so a board that drew the groups apart would be drawing
    bookkeeping. Three per group at 2P, two at 3P and none at 4P, which the engine has already
    decided; nothing here counts players to work it out.
    """
    dummy = payload["state"]["dummy_acolytes"]
    return list(dummy["total"])


def timeline_slots(payload: dict) -> list[dict]:
    """What stands on each round of the border track: a pilgrimage site, a building, or nothing.

    The map's own slot list is a fixed sample -- one hardcoded arrangement of the twelve buildings
    and the four sites. This is the same shape read off the scenario instead, so the buildings that
    are actually in play stand on the rounds they actually become live on.
    """
    state = payload["state"]
    site_rounds = list(state["pilgrimage_rounds"])
    building_round = dict(state["building_availability"].items())
    by_round: dict[int, dict] = {}
    for index, round_number in enumerate(sorted(site_rounds), start=1):
        by_round[round_number] = {"kind": "site", "site_index": index, "building_id": None}
    for building_id in state["building_market"]:
        round_number = building_round.get(building_id)
        if round_number is None or round_number in by_round:
            continue
        by_round[round_number] = {
            "kind": "building",
            "site_index": None,
            "building_id": building_id,
        }
    return [
        dict(
            by_round.get(round_number, {"kind": "empty", "site_index": None, "building_id": None}),
            round=round_number,
        )
        for round_number in range(1, max([*by_round, 1]) + 1)
    ]


def state_header(payload: dict) -> list[tuple[str, str]]:
    """The position in words: who is on, where the clock stands, and whether setup is done.

    Every line is read from the payload. None of it is worked out here -- `turn_in_round` in
    particular is the engine's counter and not a count of anything this file can see.
    """
    state = payload["state"]
    timing, setup = state["timing"], state["setup"]
    if not setup["setup_sow_required"]:
        setup_text = "not required"
    elif setup["setup_sow_complete"]:
        setup_text = "complete"
    else:
        done = setup["setup_sow_completed_by"]
        setup_text = f"sown by {', '.join(done)}" if done else "no seat has sown yet"
    return [
        ("Active player", state["active_player"]),
        ("Start player", state["start_player_id"]),
        ("Phase", state["phase"]),
        ("Round", str(timing["round_number"])),
        ("Season", str(timing["season_number"])),
        ("Turn in round", str(timing["turn_in_round"])),
        ("Setup sow", setup_text),
    ]
