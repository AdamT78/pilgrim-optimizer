# Round End (v4.5 Sandbox Scope)

## Implemented scope

The sandbox now executes an explicit round-end phase pipeline after the last player turn in a round.

Normal-round cadence:

- each real player acts once per round
- round length equals real player count (`2..4`)
- round-end pipeline runs only after the last real player turn.

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
- Deterministic start-player selection placeholder policy (`highest_piety_selects_self`)

Deferred:

- Dummy-acolyte automatic season-end movement in transition pipeline
- Real trade-route income
- Player choice for who the deciding player selects as next start player
- Spatial board geometry and map-space calculations

## Round-end event order

For non-round-ending turns, the timing tail is minimal:

1. `TURN_ADVANCE`
2. `INVARIANT_CHECK`

For round-ending turns, event order is:

1. `EXCESS_RESOURCE_CAP` (emitted per player only when stone/wheat were actually capped)
2. `SHIP_ADVANCE`
3. `GAME_END` (only on final NW return after 26 completed rounds; if emitted, pipeline stops)
4. `ROUND_ADVANCE`
5. `ALMS_SEASON_END` (only when the new round matches optional pilgrimage-round metadata)
6. `ALMS_SEASON_REWARD` (move/forfeit outcome)
7. `ALMS_RESET` (all Alms markers to row 0)
8. `GAME_END` (fourth pilgrimage-site season end; if emitted, pipeline stops)
9. `MERCHANT_ADVANCE` (only if game not over)
10. `START_PLAYER_TIE_BREAK` (only when highest-piety tie occurs)
11. `START_PLAYER_SELECTION` (only if game not over)
12. `TURN_ADVANCE` (from acting player to selected next active player; skipped when game over)
13. `INVARIANT_CHECK`

## Excess cap

At round end, each real player is checked:

- `stone > 6` is reduced to `6`
- `wheat > 6` is reduced to `6`
- `silver` is unchanged in this milestone

Example event:

`EXCESS_RESOURCE_CAP: player_one stone 8 -> 6; wheat 9 -> 6`

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

- if Ship returns to NW pilgrimage site after full 26-round loop, game ends before the
  round-advance/season-end tail.

## Start player placeholder policy

At round end (if game not over):

1. find highest piety among real players
2. if unique highest piety: that player is deciding player
3. if tie: choose deciding player clockwise away from current `start_player`
4. placeholder policy: deciding player selects themselves as next start player
5. set both `start_player` and next `active_player` to that selected player

This is deterministic scaffolding until full player choice is modelled.
