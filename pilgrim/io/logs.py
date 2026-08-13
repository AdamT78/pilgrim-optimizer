"""Structured logging and replay serialization foundations."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pilgrim.model.events import GameEvent
from pilgrim.model.state import GameState


def events_to_json_records(events: Iterable[GameEvent]) -> list[dict[str, Any]]:
    """Convert immutable event tuples into JSON-serializable records."""
    return [
        {
            "event_type": event.event_type.value,
            "actor": event.actor.name.lower(),
            "action_id": event.action_id,
            "details": {key: value for key, value in event.details},
        }
        for event in events
    ]


def state_to_record(state: GameState) -> dict[str, Any]:
    """Serialize a full state snapshot for replay trails.

    The timing block, each seat's Alms position and the setup-sow flags were missing rather than
    withheld: `alms_position` sits between `piety` and `victory_points` on `PlayerState` and both
    of its neighbours were already here. Adding them is safe to do in passing because nothing reads
    the format -- `write_replay_log` has no callers and this has only that one -- so there is no
    reader to break, and a state serializer that omits state is a trap for the first one written.

    What is NOT here is anything from the config. The duty arrangement in particular lives on
    `GameConfig` and not on `GameState`, so a caller that needs to know which duty lies where has
    to be handed both; see `pilgrim.io.view`.
    """
    return {
        "active_player": state.active_player.name.lower(),
        "start_player_id": state.start_player.name.lower(),
        "phase": state.phase.value,
        "turn": state.turn,
        "timing": {
            "absolute_turn": state.timing.absolute_turn,
            "round_number": state.timing.round_number,
            "season_number": state.timing.season_number,
            "turn_in_round": state.timing.turn_in_round,
        },
        "setup": {
            "setup_sow_required": state.setup_sow_required,
            "setup_sow_complete": state.setup_sow_complete,
            "setup_sow_completed_by": [
                player_id.name.lower() for player_id in state.setup_sow_completed_by
            ],
        },
        "game_over": state.game_over,
        "table_player_count": state.table_player_count,
        "ship_position": state.ship_position,
        "completed_rounds": state.completed_rounds,
        "merchant_position": state.merchant_position,
        "building_market": list(state.building_market),
        "building_availability": {
            building_id: live_round for building_id, live_round in state.building_availability
        },
        "pilgrimage_rounds": list(state.pilgrimage_rounds),
        "dummy_acolytes": {
            "north_group": list(state.dummy_acolytes.north_group),
            "south_group": list(state.dummy_acolytes.south_group),
            "total": list(state.dummy_acolytes.total_vector),
        },
        "players": [
            {
                "victory_points": player.victory_points,
                "piety": player.piety,
                "alms_position": player.alms_position,
                # Carried but drawn nowhere yet: trade routes come from map tile placement, which
                # is not built. Serializing it is not the same as drawing it, and a state snapshot
                # that quietly drops a field is worse than one that carries an unused one.
                "trade_routes_count": player.trade_routes_count,
                "resources": {
                    "stone": player.resources.stone,
                    "silver": player.resources.silver,
                    "wheat": player.resources.wheat,
                },
                "workforce": {
                    "mancala": list(player.workforce.mancala),
                    "village": player.workforce.village,
                    "abbey": player.workforce.abbey,
                    "committed": {
                        "roads": player.workforce.committed.roads,
                        "shrines": player.workforce.committed.shrines,
                        "market_ports": player.workforce.committed.market_ports,
                        "pilgrimage_sites": player.workforce.committed.pilgrimage_sites,
                        "alms_table": player.workforce.committed.alms_table,
                    },
                },
                "special_activities": {
                    "fields": player.special_activities.count_for("fields"),
                    "road_engineer": player.special_activities.count_for("road_engineer"),
                    "stone_mason": player.special_activities.count_for("stone_mason"),
                    "alms_house": player.special_activities.count_for("alms_house"),
                    "engraver": player.special_activities.count_for("engraver"),
                    "vestry": player.special_activities.count_for("vestry"),
                },
                "player_board_slots": {
                    "active_buildings": list(player.player_board_slots.active_buildings),
                    "donated_buildings": list(player.player_board_slots.donated_buildings),
                    "cardinal_favor_tiles": player.player_board_slots.cardinal_favor_tiles,
                },
            }
            for player in state.players
        ],
        "acolytes": [list(vector) for vector in state.acolytes],
    }


def write_replay_log(path: str | Path, *, state: GameState, events: Iterable[GameEvent]) -> None:
    """
    Write one replay JSON document.

    This intentionally small foundation can be expanded into per-transition JSONL later.
    """
    replay_path = Path(path)
    replay_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "state": state_to_record(state),
        "events": events_to_json_records(events),
    }
    with replay_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
