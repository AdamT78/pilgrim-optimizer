# Round End (v4.4 Sandbox Scope)

## Implemented scope

The sandbox now executes an explicit round-end phase pipeline after the last player turn in a round.

Setup-sow exception:

- `setup_sow` actions do not run this round-end pipeline.
- setup rotation remains `next incomplete setup player` until setup completes.

Implemented now:

- Excess resource cap (`stone` and `wheat` capped at 6 for each player)
- Round increment at round end (`ROUND_ADVANCE`)
- Season-end pilgrimage check as deferred metadata-driven event
  (`SEASON_END_DEFERRED`)
- Abstract Ship marker movement on a 26-step path
- Game-end trigger when Ship returns to NW pilgrimage site after 26 completed rounds
- Merchant movement once per round (not once per turn)
- Deterministic start-player selection placeholder policy (`highest_piety_selects_self`)

Deferred:

- Alms season-end leader reward/reset integration at round end
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
5. `SEASON_END_DEFERRED` (only when the new round matches optional pilgrimage-round metadata)
6. `MERCHANT_ADVANCE` (only if game not over)
7. `START_PLAYER_TIE_BREAK` (only when highest-piety tie occurs)
8. `START_PLAYER_SELECTION` (only if game not over)
9. `TURN_ADVANCE` (from acting player to selected next active player)
10. `INVARIANT_CHECK`

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

Round-end season checking is currently metadata-driven and deferred:

- if generated/setup metadata exposes pilgrimage rounds, and the **new** round number
  (after `ROUND_ADVANCE`) matches one of those rounds, emit:
  - `SEASON_END_DEFERRED`
- deferred mode does not apply Alms season-end rewards/resets and does not change VP/resources.

Game ends when all are true:

- Ship is at NW pilgrimage site
- `completed_rounds >= path_length` (26)

When this game-end condition is reached, merchant/start-player/round-advance tail steps are skipped.

## Start player placeholder policy

At round end (if game not over):

1. find highest piety among real players
2. if unique highest piety: that player is deciding player
3. if tie: choose deciding player clockwise away from current `start_player`
4. placeholder policy: deciding player selects themselves as next start player
5. set both `start_player` and next `active_player` to that selected player

This is deterministic scaffolding until full player choice is modelled.
