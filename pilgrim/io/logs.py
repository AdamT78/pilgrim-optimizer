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
    """Serialize a full state snapshot for replay trails."""
    return {
        "active_player": state.active_player.name.lower(),
        "start_player_id": state.start_player.name.lower(),
        "phase": state.phase.value,
        "turn": state.turn,
        "game_over": state.game_over,
        "table_player_count": state.table_player_count,
        "ship_position": state.ship_position,
        "completed_rounds": state.completed_rounds,
        "merchant_position": state.merchant_position,
        "building_market": list(state.building_market),
        "dummy_acolytes": {
            "north_group": list(state.dummy_acolytes.north_group),
            "south_group": list(state.dummy_acolytes.south_group),
            "total": list(state.dummy_acolytes.total_vector),
        },
        "players": [
            {
                "victory_points": player.victory_points,
                "piety": player.piety,
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
