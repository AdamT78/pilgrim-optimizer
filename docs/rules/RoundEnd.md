# Round End (v5.8 Sandbox Scope)

## Implemented scope

The sandbox now executes an explicit round-end phase pipeline after the last player turn in a round.

Normal-round cadence:

- each real player acts once per round
- round length equals real player count (`2..4`)
- round-end pipeline runs only after the last real player turn.
- the Ship marker is the round marker in engine terms (`SHIP_ADVANCE`).

Setup-sow exception:

- `setup_sow` actions do not run this round-end pipeline.
- setup rotation remains `next incomplete setup player` until setup completes.

Implemented now:

- Excess resource cap (`stone` and `wheat` capped at 6 for each player)
- Round increment at round end (`ROUND_ADVANCE`)
- Season-end pilgrimage check from metadata rounds with Alms leader scoring
- Abstract Ship marker movement on a 26-step path
- Game-end trigger on fourth season-end pilgrimage site
- Legacy game-end trigger when Ship returns to NW pilgrimage site after 26 completed rounds
- Merchant movement once per round (not once per turn)
- Trade-route income after round-end Merchant movement
- Confession Box temporary piety choices at start-player-selection time
- Deterministic start-player selection placeholder policy (`highest_piety_selects_self`)
  using effective piety when Confession Box bonuses are present

Deferred:

- Dummy-acolyte automatic season-end movement in transition pipeline
- Player choice for who the deciding player selects as next start player
- Spatial board geometry and map-space calculations

## Round-end event order

For non-round-ending turns, the timing tail is minimal:

1. `TURN_ADVANCE`
2. `INVARIANT_CHECK`

For round-ending turns, event order is:

1. `EXCESS_RESOURCE_CAP` (emitted per player only when stone/wheat were actually capped)
2. `SHIP_ADVANCE`
3. `GAME_END` (legacy NW full-loop fallback only when no metadata pilgrimage block is pending for the next round; if emitted, pipeline stops)
4. `ROUND_ADVANCE`
5. `ALMS_SEASON_END` (only when the new round matches optional pilgrimage-round metadata)
6. `ALMS_SEASON_REWARD` (move/forfeit outcome)
7. `ALMS_RESET` (all Alms markers to row 0)
8. `GAME_END` (fourth pilgrimage-site season end, or deferred NW full-loop fallback after the Alms block; if emitted, pipeline stops)
9. `MERCHANT_ADVANCE` (only if game not over)
10. `TRADE_ROUTE_INCOME` (one event per gaining player; emitted only when Merchant resource exists and trade route count is positive)
11. `BUILDING_HIRED` (only when Confession Box is hired during start-player phase)
12. `CONFESSION_BOX_BONUS` (one per Confession Box user/hirer in start-player turn order)
13. `START_PLAYER_TIE_BREAK` (only when highest effective-piety tie occurs)
14. `START_PLAYER_SELECTION` (only if game not over)
15. `TURN_ADVANCE` (from acting player to selected next active player; skipped when game over)
16. `INVARIANT_CHECK`

Guild interaction (v5.3):

- Guild Merchant movement is separate from round-end Merchant movement.
- When Guild is used during a turn, its `MERCHANT_ADVANCE` is emitted in the pre-sowing
  building-modifier window with `cause=guild`.
- If that same turn is also round-ending, round-end still performs its normal single
  Merchant advance later in this sequence.
- Trade-route income then uses the Merchant resource after that round-end Merchant advance.
- Result: a round-ending Guild turn can emit two Merchant advances total:
  - one pre-sowing from Guild
  - one in round-end step 9

## Excess cap

At round end, each real player is checked:

- `stone > 6` is reduced to `6`
- `wheat > 6` is reduced to `6`
- `silver` is unchanged in this milestone

Example event:

`EXCESS_RESOURCE_CAP: player_one stone 8 -> 6; wheat 9 -> 6`

Trade-route income phase interaction:

- excess cap remains the first round-end phase
- no second excess cap runs after trade-route income
- trade-route income can therefore move stone/wheat above 6 until the next round-end cap

## Start-player Confession Box

At the beginning of start-player selection:

- players are evaluated in start-player turn order from current `start_player`
- each player may decline or use/hire Confession Box if available by source priority
  (`own_active`, then `opponent_active_hire`, then `live_market_hire`)
- hired uses pay current Merchant resource (`1`) to bank/owner before bonus event
- each use grants temporary `+2` effective piety for this start-player decision only

Branch-pruning policy for legal action generation:

- no-use Confession Box variant is always retained
- Confession Box use/hire variants are generated only when the temporary `+2` bonuses
  can change the resolved next `start_player` under the current deterministic
  "deciding player selects self" policy

Temporary piety notes:

- effective piety can exceed the piety-track cap
- real piety and piety-track VP are unchanged
- no temporary piety state persists into later rounds

## Trade-route income

Round-end trade-route income resolves immediately after `MERCHANT_ADVANCE`:

- each real player gains `trade_routes_count` of the Merchant's current resource
- if Merchant resource is `none` (for example Taxation), no trade-route income is emitted
- if `trade_routes_count` is `0`, that player receives no income event
- this milestone uses scalar `trade_routes_count` on `PlayerState`; spatial route creation remains
  deferred

## Ship marker model

Ship config comes from `configs/ship.json`:

- `path_length`: abstract number of valid stopping spaces (26)
- `start_position`: initial NW position (0)
- `nw_pilgrimage_site_position`: NW site marker (0)
- `pilgrimage_site_positions`: all pilgrimage-site positions on the abstract path
- `advance_per_round`: round-end step size (1)

The abstract path already excludes non-stopping spaces (for example circular Market Ports).

## Season end and game end

Round-end season checking is metadata-driven:

- if generated/setup metadata exposes pilgrimage rounds, and the **new** round number
  (after `ROUND_ADVANCE`) matches one of those rounds, season-end Alms logic runs.
- if metadata is missing, no season-end Alms scoring/reset events run.

Alms leader selection tie-break:

1. highest Alms marker position
2. highest piety among tied players
3. earliest in current turn order using current `start_player` as first in order

Alms season-end reward:

- winning player moves 1 acolyte `abbey -> committed.alms_table` if available
- if no Abbey acolyte is available, reward is forfeited
- Alms table VP lookup:
  - `1 -> 5`
  - `2 -> 11`
  - `3 -> 18`
  - `4 -> 26`
- all players' `alms_position` reset to `0` after season-end resolution

Fourth-season game end:

- when season-end occurs on the fourth pilgrimage-site round, game ends immediately after
  `ALMS_SEASON_END`, `ALMS_SEASON_REWARD`, and `ALMS_RESET`.
- merchant/start-player continuation steps are skipped.

Legacy NW return game end remains:

- if Ship returns to NW pilgrimage site after full 26-round loop and no metadata pilgrimage
  round is pending, game ends immediately as a fallback.
- if that NW full-loop return coincides with a metadata pilgrimage round, season-end Alms
  scoring/reset resolves first, then game ends before Merchant/start-player continuation steps.

## Start player placeholder policy

At round end (if game not over):

1. resolve any selected Confession Box uses/hires in start-player turn order
2. compute effective piety = real piety + temporary Confession Box bonus (`+2` when used/hired)
3. find highest effective piety among real players
4. if unique highest effective piety: that player is deciding player
5. if tie: choose deciding player clockwise away from current `start_player`
6. placeholder policy: deciding player selects themselves as next start player
7. set both `start_player` and next `active_player` to that selected player

This is deterministic scaffolding until full player choice is modelled.
