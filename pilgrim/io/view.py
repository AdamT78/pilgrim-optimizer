"""One plain dict carrying everything a view needs to draw a position.

This exists because a view needs two things the engine keeps apart. `state_to_record` serializes a
`GameState` and nothing else, which is right -- but the duty arrangement is not on the state. It is
on `GameConfig`, because a scenario's tiles are fixed when the scenario is written and no turn
moves them. A page that drew the wheel from the state alone would have to invent an arrangement,
and would draw the same wheel for every seed.

So the payload is the state record plus exactly the config facts a board cannot be drawn without,
and the join between them is made here, once, on the engine's side of the line. Nothing downstream
imports the engine: the UI is handed this dict and maps it.

Deliberately NOT resolved here: whose turn it is next, what is legal, what anything scores. Those
are the engine's and asking them of a serializer is how a second rules implementation starts.
"""

from __future__ import annotations

from typing import Any

from pilgrim.io.logs import state_to_record
from pilgrim.model.config import GameConfig
from pilgrim.model.duties import duty_category_at_position
from pilgrim.model.enums import CANONICAL_POSITION_NAMES
from pilgrim.model.state import GameState

CITY_POSITION = 0


def duty_tiles_record(config: GameConfig) -> list[dict[str, Any]]:
    """Which duty lies at each board position, and what it pays.

    Keyed by board position, never by duty slot. The two are different things and only agree in the
    default arrangement: a scenario shuffles the tiles, so the tile that natively belongs at a
    position is not the tile lying there. A view that cached the pairing would draw the wrong wheel
    for every seed but one, and pay out the wrong tithe on every tile.

    The tithe counter goes with the POSITION rather than with the tile: the setup generator deals
    counters onto positions after it has shuffled the tiles, so a counter is a fact about the space
    on the board. Taxation carries none, which is why the value is nullable rather than absent.
    """
    tithe_by_position = config.tithe_counters_mapping()
    tiles = []
    for index, name in enumerate(CANONICAL_POSITION_NAMES):
        if index == CITY_POSITION:
            continue
        tiles.append(
            {
                "position": index,
                "position_name": name,
                "duty": duty_category_at_position(config, index),
                "tithe": tithe_by_position.get(name),
            }
        )
    return tiles


def view_payload(state: GameState, config: GameConfig) -> dict[str, Any]:
    """The state record, plus the config facts a board cannot be drawn without."""
    return {
        "state": state_to_record(state),
        "duty_tiles": duty_tiles_record(config),
        "board_positions": list(CANONICAL_POSITION_NAMES),
    }
