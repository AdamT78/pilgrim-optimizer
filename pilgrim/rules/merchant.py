"""Where the Merchant stands on the board, and what it therefore provides.

The Merchant rides the eight Duty tiles. It starts on Taxation, advances one tile clockwise at
each round end for the whole game, and never enters the City. What it provides is the TITHE
COUNTER on the tile it currently occupies -- not a property of the duty, of the tile. Taxation
carries no counter and so provides nothing, and the cornucopia counter is a wildcard the paying
player chooses against.

WHAT THIS REPLACED, AND WHY IT WAS WRONG

`merchant_position` used to index a fixed six-step path in `configs/merchant.json`,
`["taxation", "produce", "clerical", "alms", "build", "clerical"]`, with a `resource_by_duty` map
beside it. That path predated tithe counters and never learned about them: it ignored the per-game
duty arrangement and the per-game counters entirely, so every seed produced the same Merchant
sequence on a board whose tiles had been shuffled. Two of its six names, `alms` and `build`, were
not duty category names at all, and `clerical` appeared twice.

THE INDEX SPACE CHANGED MEANING, WHICH IS WHY THE FIELD WAS RENAMED

`merchant_position` indexed a 6-element list where 0 meant Taxation. A board ring position is a
different thing: 0 is the CITY, which the Merchant can never occupy, and the valid range is 1..8.
The two ranges overlap, so an old value of 1 or 2 would have loaded and run under the new meaning
without complaint. The field is therefore `merchant_board_position` now, and a scenario carrying
the old name is refused rather than reinterpreted -- see `pilgrim/io/scenarios.py`.
"""

from __future__ import annotations

from pilgrim.model.config import BoardConfig, GameConfig
from pilgrim.model.duties import duty_category_at_position
from pilgrim.model.state import GameState

CITY_POSITION = 0
DUTY_TILE_COUNT = 8
TAXATION_DUTY = "taxation"
CORNUCOPIA_COUNTER = "cornucopia"
# What the wildcard stands for when someone pays a hire with it. Ordered, because the order decides
# the order the hire variants come out in, and a stable action order is worth more than the choice
# of order itself. Piety is deliberately absent: no tithe counter offers it and hires are paid in
# goods.
CORNUCOPIA_HIRE_RESOURCES: tuple[str, ...] = ("wheat", "stone", "silver")


def _require_duty_tile(position: int) -> int:
    if position == CITY_POSITION:
        raise ValueError("The Merchant is never in the City; board position 0 is not a duty tile.")
    if not 1 <= position <= DUTY_TILE_COUNT:
        raise ValueError(
            f"Merchant board position must be a duty tile, 1..{DUTY_TILE_COUNT}; got {position}."
        )
    return position


def ring_successor(position: int, board: BoardConfig) -> int:
    """The next duty tile clockwise, read off the board's own edges.

    Derived rather than written down a second time. The ring is already in `configs/board.json`:
    every duty position has exactly one outgoing edge that is not the City, and following it eight
    times walks north, north_east, east, south_east, south, south_west, west, north_west and back.
    A separate ordering here would be a copy that could disagree with the graph the sowing rules
    move over, and the disagreement would be silent.
    """
    _require_duty_tile(position)
    onward = [step for step in board.neighbors(position) if step != CITY_POSITION]
    if len(onward) != 1:
        raise ValueError(
            f"Board position {position} does not have exactly one onward ring step: {onward}."
        )
    return onward[0]


def taxation_board_position(config: GameConfig) -> int:
    """Where Taxation landed this game. A lookup, not a constant: the scenario deals the tiles."""
    return config.duty_tiles.board_index_for_category(TAXATION_DUTY)


def merchant_position_name(position: int, config: GameConfig) -> str:
    """The compass point the Merchant stands on."""
    return config.board.positions[_require_duty_tile(position)]


def advance_merchant_position(position: int, config: GameConfig) -> int:
    """Advance the Merchant one duty tile clockwise."""
    return ring_successor(_require_duty_tile(position), config.board)


def current_merchant_duty(state: GameState, config: GameConfig) -> str:
    """The duty category lying on the Merchant's tile in THIS game's arrangement."""
    return duty_category_at_position(config, _require_duty_tile(state.merchant_board_position))


def current_merchant_resource(state: GameState, config: GameConfig) -> str | None:
    """The tithe counter on the Merchant's tile, or None on Taxation.

    Read off the POSITION rather than off the duty. The setup generator deals counters onto
    positions after it has shuffled the tiles, so a counter is a fact about the space; a lookup
    keyed by duty would follow a tile around the ring and pay out the wrong resource everywhere.
    """
    return config.tithe_counters.resource_for_board_index(
        _require_duty_tile(state.merchant_board_position)
    )


def merchant_resource_is_wild(state: GameState, config: GameConfig) -> bool:
    """Whether the Merchant's tile carries the cornucopia, which the payer chooses against."""
    return current_merchant_resource(state, config) == CORNUCOPIA_COUNTER


def building_hire_payment_resource(state: GameState, config: GameConfig) -> str | None:
    """What a hire is paid in. `cornucopia` here means "the payer chooses"; see the hire rules."""
    return current_merchant_resource(state, config)


def trade_route_income_resource(state: GameState, config: GameConfig) -> str | None:
    """What trade-route income would be paid in.

    No income is ever paid today: every `trade_routes_count` is 0 until map tile placement exists,
    and round end emits TRADE_ROUTE_INCOME_SKIPPED. When trade routes do arrive, a cornucopia here
    will need a per-player choice at round end, which deliberately does not exist yet -- there is
    nothing for it to choose about.
    """
    return current_merchant_resource(state, config)
