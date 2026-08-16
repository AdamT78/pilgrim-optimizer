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

3. Seat order is explicit, once, in `SEATED_PLAYERS`. It matches engine order today, and still
   goes through one constant so a future reseating has one source of truth instead of a spread of
   "first N players" assumptions.

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

    Filtered from `SEATED_PLAYERS` rather than derived from player count, so one constant owns seat
    order wherever this page needs it.
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


def first_player_seat(payload: dict) -> int | None:
    """Which chair the First Player seal is struck on, or None when the position does not say.

    The seal belongs to whoever HOLDS the marker, which is not whoever begins the round. They part
    company the moment a holder names somebody else, and that is the one thing about this rule a
    screenshot can show -- so reading `start_player_id` here would draw the seal on the wrong board
    exactly when it finally had something to say.

    Through the seating order, like every other per-player value on this page. The seal is a chair
    and the marker is a player, and this keeps that join in one place.

    None means the state does not know its holder, which is what a scenario written before the
    engine kept one looks like. Nothing is drawn, because a marker put on the likeliest seat is a
    guess with a seal on it.
    """
    holder = payload["state"].get("first_player_marker")
    if holder is None or holder not in seated_player_ids(payload):
        return None
    return SEATED_PLAYERS.index(holder) + 1


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


def piety_by_player(payload: dict) -> dict[str, int]:
    """Each occupied seat's piety, keyed by player id and passed through unchanged.

    This is the same seam as every other per-seat value on this page: read from the state record,
    in seating order, and hand over exactly what is there. Position 0..12 has geometry on the
    board; values beyond that are still returned as-is and are for the renderer to reject loudly.
    """
    values: dict[str, int] = {}
    for player_id in seated_player_ids(payload):
        record = player_record(payload, player_id)
        if record is None:
            continue
        values[player_id] = int(record["piety"])
    return values


def duty_by_position_name(payload: dict) -> dict[str, str]:
    """Board position name -> the duty lying there in this scenario."""
    return {tile["position_name"]: tile["duty"] for tile in payload["duty_tiles"]}


def tithe_by_position_name(payload: dict) -> dict[str, str | None]:
    """Board position name -> the counter on that space, None on Taxation.

    Read off the position rather than carried with the tile, which is how the engine deals them.
    """
    return {tile["position_name"]: tile["tithe"] for tile in payload["duty_tiles"]}


def merchant_position_name(payload: dict) -> str:
    """The board position the Merchant stands on, by name.

    Read off `merchant_board_position`, which is a ring index of 1..8 and never 0 -- 0 is the City
    and the Merchant is never there. The name is what the wheel's spaces are keyed by, so the index
    is turned into one here rather than in the renderer.

    A POSITION, deliberately, and not a duty. The Merchant opens on Taxation, which makes a lookup
    by duty look right for as long as it has not moved and for as long as the tiles are in their
    default arrangement. It is the same trap the tithe counters set: what stands on a space is a
    fact about the space, and the tile lying there is shuffled per seed and is not.
    """
    names = payload["board_positions"]
    index = payload["state"]["merchant_board_position"]
    if not 1 <= index < len(names):
        raise ValueError(
            f"Merchant board position must be a duty tile, 1..{len(names) - 1}; got {index}."
        )
    return names[index]


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
    """The one status sentence the box keeps: setup progress or round progress."""
    state = payload["state"]
    timing = state["timing"]
    setup = state.get("setup", {})
    player_count = state.get("table_player_count") or len(state.get("players") or [])
    if state.get("phase") == "setup_sow" and setup.get("setup_sow_required"):
        sown = len(setup.get("setup_sow_completed_by") or ())
        return [("Status", f"Setup - {sown} of {player_count} sown")]
    if (
        setup.get("setup_sow_required")
        and setup.get("setup_sow_complete")
        and timing.get("absolute_turn") == 0
        and timing.get("turn_in_round") == 0
    ):
        sown = len(setup.get("setup_sow_completed_by") or ())
        return [
            (
                "Status",
                "Setup - "
                f"{sown} of {player_count} sown. "
                f'Round {timing["round_number"]} - 0 of {player_count} turns played',
            )
        ]
    return [
        (
            "Status",
            f'Round {timing["round_number"]} - {timing["turn_in_round"]} of {player_count} turns played',
        )
    ]


def played_this_round(payload: dict) -> tuple[str, ...]:
    """Seats the payload explicitly says have already finished this round.

    This is pass-through only. If the payload does not carry it, this returns empty and the page
    does not infer it from other fields.
    """
    raw = payload["state"].get("played_this_round")
    if not isinstance(raw, (list, tuple)):
        return ()
    seated = set(seated_player_ids(payload))
    seen: list[str] = []
    for value in raw:
        player_id = str(value)
        if player_id in seated and player_id not in seen:
            seen.append(player_id)
    return tuple(seen)
