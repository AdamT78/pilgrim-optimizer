# Merchant

## The rule

The Merchant rides the eight Duty tiles. It starts on Taxation, advances one tile clockwise at
each round end for the whole game, and never enters the City.

What it provides is the **tithe counter on the tile it currently occupies**. Taxation carries no
counter and so provides nothing. On the cornucopia tile the paying player chooses which resource
to pay in.

## Position

`GameState.merchant_board_position` is a board ring position, `1..8`. Position `0` is the City and
is never valid; it is asserted on the state, in `pilgrim/rules/validation.py`, and on every
Merchant helper.

The ring is derived from `configs/board.json`'s edges rather than written down a second time:
every duty position has exactly one outgoing edge that is not the City, and following it walks

`north -> north_east -> east -> south_east -> south -> south_west -> west -> north_west -> north`

A lap is therefore eight rounds.

### What the change costs

This is a balance change, not a refactor.

The retired six-step path paid, per lap: 2 wheat, 2 silver, 1 stone and 1 nothing. The eight-tile
ring pays 2 wheat, 2 silver, 2 stone, 1 cornucopia and 1 nothing. Per round, the odds move:

| | Wheat | Silver | Stone | Cornucopia | Nothing |
|---|---|---|---|---|---|
| Six-step path | 33% | 33% | 17% | — | 17% |
| Eight-tile ring | 25% | 25% | 25% | 12.5% | 12.5% |

Stone stops being the scarce one, and a wild appears.

A 26-round game also drops from about 4.33 laps to 3.25, so the Merchant now passes any given tile
roughly three times instead of four.

## Resource

The resource is read off the POSITION, not off the duty:

```python
config.tithe_counters.resource_for_board_index(state.merchant_board_position)
```

This matters because the setup generator shuffles the duty tiles and then deals counters onto
positions. A counter is a fact about a space, so a lookup keyed by duty would follow a tile around
the ring and pay out the wrong resource. The generator deals seven counters — two stone, two
wheat, two silver, one cornucopia — onto the seven non-Taxation positions.

## Advancement timing

Merchant advancement is integrated into the **round-end** transition flow:

1. Resolve the current full turn and emit `TURN_ADVANCE`
2. If the round does not end: no Merchant movement
3. If the round ends: run Excess/Ship/season-end steps
4. Advance the Merchant once (`MERCHANT_ADVANCE`) if the game has not ended
5. Run trade-route income and start-player selection
6. Finish round/season advancement and invariants

Guild and Wagon Yard can also move the Merchant during a turn; they use the same ring.

`MERCHANT_ADVANCE` details carry `from_duty`, `to_duty`, `to_position` and `current_resource`, so
the log names the tile a player would look at and what a hire will now cost.

Because the Merchant opens on Taxation and only advances at round end, **hiring is impossible for
the whole of round 1 in every game**. That was true before this rule too, but it used to be a
consequence of `path[0]` rather than of the rule.

## Cornucopia

Building hire is the live consumer of the Merchant resource. When the Merchant sits on the
cornucopia, the hiring player chooses which of wheat, stone or silver to pay in, and the choice
shows up as one hire variant per resource they can afford. The action records payments per hire in
`hire_payments`, a sorted tuple of `(building_id, resource)` pairs.

Affordability decides how wide the choice is:

- can afford all three: three variants
- can afford one: one variant, identical to what a plain counter of that resource would generate
- can afford none: hiring is unavailable, for want of resources rather than for the reason Taxation
  gives — there the Merchant offers nothing at all, whatever the player holds

Only affordable resources are offered. A variant that cannot be paid is a legal action that fails
on contact, and pruning a choice down to its one real option is the no-op pruning applied elsewhere.

Trade-route income reads the same resource and does **not** have the choice. It emits
`TRADE_ROUTE_INCOME_SKIPPED` on a cornucopia, because every `trade_routes_count` is 0 until map tile
placement exists and so there is nothing to choose about. The asymmetry is not an oversight: hiring
happens on one player's turn and that player can be asked, whereas round-end income would need every
player to answer at once. The choice will be needed when trade routes arrive.

### A coverage note worth keeping

The fallback tithe counters that hand-written scenarios inherit deal 2 wheat, 3 silver and 2 stone
and **no cornucopia**, while the generator deals 2/2/2/1 with one. No fixture in the repository can
therefore put the Merchant on a cornucopia, which is why a reachable crash in building hire sat
under a green suite. `tests/test_merchant_cornucopia.py` reaches that state deliberately, and is
the only coverage the hire choice has for as long as that stays true.

## What this replaced

`configs/merchant.json` used to define a fixed six-step path,
`["taxation", "produce", "clerical", "alms", "build", "clerical"]`, with its own `resource_by_duty`
map. It predated tithe counters and never learned about them: it ignored the per-game duty
arrangement and the per-game counters, so every seed produced the same Merchant sequence on a board
whose tiles had been shuffled. Two of its six names, `alms` and `build`, were not duty categories
at all, and `clerical` appeared twice. Both fields are removed, and a config still carrying them is
refused rather than ignored.

The index space changed meaning, which is why the state field was renamed from `merchant_position`
to `merchant_board_position`. The old field indexed a 6-element list where `0` meant Taxation; the
new one indexes the board ring where `0` is the City. The two ranges overlap, so an old value of
`1` or `2` would have loaded in silence under the new meaning. A range check cannot catch that;
only the name can, so a scenario carrying the old field is refused.

207 scenarios plus the base setup file were migrated by preserving the resource each one offered
rather than the duty.
