# Round End (v1.0 Sandbox Scope)

## Implemented scope

The sandbox now executes an explicit round-end phase pipeline after the last player turn in a round.

Implemented now:

- Excess resource cap (`stone` and `wheat` capped at 6 for each player)
- Abstract Ship marker movement on a 26-step path
- Season-end trigger when Ship reaches a configured pilgrimage-site position
- Existing Alms season-end leader reward/reset integration
- Existing dummy-acolyte season-end movement integration
- Game-end trigger when Ship returns to NW pilgrimage site after 26 completed rounds
- Merchant movement once per round (not once per turn)
- Trade-route income placeholder hook (`TRADE_ROUTE_INCOME_SKIPPED`)
- Deterministic start-player selection placeholder policy (`highest_piety_selects_self`)

Deferred:

- Confession Box use/hire decisions
- Real trade-route income
- Player choice for who the deciding player selects as next start player
- Spatial board geometry and map-space calculations

## Round-end event order

For non-round-ending turns, the timing tail is minimal:

1. `TURN_ADVANCE`
2. `INVARIANT_CHECK`

For round-ending turns, event order is:

1. `TURN_ADVANCE`
2. `ROUND_END`
3. `EXCESS_DISCARD` (or `EXCESS_CHECK` when no discards)
4. `SHIP_ADVANCE`
5. `SEASON_END` (only if Ship reached a pilgrimage site)
6. `ALMS_SEASON_REWARD` (season end only)
7. `ALMS_RESET` (season end only)
8. `GAME_END` (only on final NW return after 26 completed rounds; if emitted, pipeline stops)
9. `DUMMY_ACOLYTE_MOVE` (season end only, per dummy group, and only when game is not over)
10. `MERCHANT_ADVANCE` (only if game not over)
11. `TRADE_ROUTE_INCOME_SKIPPED` (only if game not over)
12. `START_PLAYER_TIE_BREAK` (only when highest-piety tie occurs)
13. `START_PLAYER_SELECTION` (only if game not over)
14. `ROUND_ADVANCE` (only if game not over)
15. `SEASON_ADVANCE` (season end + game not over)
16. `INVARIANT_CHECK`

## Excess cap

At round end, each real player is checked:

- `stone > 6` is reduced to `6`
- `wheat > 6` is reduced to `6`
- `silver` is unchanged in this milestone

Example event:

`EXCESS_DISCARD: player_one wheat 9 -> 6; returned 3 to supply`

## Ship marker model

Ship config comes from `configs/ship.json`:

- `path_length`: abstract number of valid stopping spaces (26)
- `start_position`: initial NW position (0)
- `nw_pilgrimage_site_position`: NW site marker (0)
- `pilgrimage_site_positions`: all pilgrimage-site positions on the abstract path
- `advance_per_round`: round-end step size (1)

The abstract path already excludes non-stopping spaces (for example circular Market Ports).

## Season end and game end

Season end now depends on Ship position, not only round counts:

- after `SHIP_ADVANCE`, season ends when new `ship_position` is in `pilgrimage_site_positions`

Game ends when all are true:

- season ended this round
- Ship is at NW pilgrimage site
- `completed_rounds >= path_length` (26)

This prevents ending at setup and ensures the game ends on the full loop return.

Season-end behavior differs by case:

- normal season end: `ALMS_SEASON_REWARD -> ALMS_RESET -> DUMMY_ACOLYTE_MOVE -> SEASON_ADVANCE`
- final NW game-ending season end: `ALMS_SEASON_REWARD -> ALMS_RESET -> GAME_END`

Dummy acolytes do not move on the final NW game-ending round because no further turns/seasons occur.

## Start player placeholder policy

At round end (if game not over):

1. find highest piety among real players
2. if unique highest piety: that player is deciding player
3. if tie: choose deciding player clockwise away from current `start_player`
4. placeholder policy: deciding player selects themselves as next start player
5. set both `start_player` and next `active_player` to that selected player

This is deterministic scaffolding until full player choice is modelled.
