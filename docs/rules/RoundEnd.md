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
- First Player marker awarded on highest effective piety, ties walking clockwise from the
  current `start_player`
- Start-player selection as a real decision by the marker holder, in its own phase

Deferred:

- Dummy-acolyte automatic season-end movement in transition pipeline
- Spatial board geometry and map-space calculations
- Confession Box directives are still an ordered tuple carried on the round-ending action, so
  one player's action encodes other players' decisions. Known modelling problem, unchanged here.

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
14. `START_PLAYER_MARKER` (only if game not over)
15. `TURN_ADVANCE` (from acting player to the marker holder, who acts next; skipped when game over)
16. `INVARIANT_CHECK`

The round-ending turn stops here, in phase `start_player_selection`, with `active_player` set to
the marker holder. `START_PLAYER_SELECTION` is emitted separately, by that player's own action.

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
  change **who receives the First Player marker**

A Confession Box cannot change who is chosen as next `start_player`: the marker holder chooses
freely and may name anyone, so every variant leads to the same set of possible start players and
differs only in who picks between them. Comparing the chosen start player would therefore find
every variant identical and prune all of them.

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

## First Player marker and start-player selection

Two values, not one. The marker holder and the start player are separate pieces of state and are
allowed to disagree.

At round end (if game not over):

1. resolve any selected Confession Box uses/hires in start-player turn order
2. compute effective piety = real piety + temporary Confession Box bonus (`+2` when used/hired)
3. find highest effective piety among real players
4. if unique highest effective piety: that player receives the First Player marker
5. if tie: the marker walks clockwise from the current `start_player`
6. emit `START_PLAYER_MARKER`, set `phase` to `start_player_selection` and `active_player` to the
   marker holder, and **stop**. `start_player` is not touched: it still names the seat this round
   was played from, which is what the next tie-break walks from.

The round-end pipeline pauses here. Nothing is skipped by pausing, because awarding the marker is
the last of the round-end steps.

Then, as a separate action by that player:

7. `legal_actions` offers one `StartPlayerSelectionAction` per real player, including the holder
8. applying it sets `start_player` and `active_player` to the chosen player, emits
   `START_PLAYER_SELECTION`, and moves to `sow`

The holder choosing themselves is one of the ordinary options and is not special-cased.

### What the two events read

```
START_PLAYER_MARKER: player_one takes the First Player marker on effective piety 4 and must
choose who begins the next round
START_PLAYER_SELECTION: player_one chose player_two to begin the next round
START_PLAYER_SELECTION: player_one chose player_one to begin the next round
```

`START_PLAYER_SELECTION` names **both** players every time, including when they are the same
player twice. It is the only line where the decider and the player they chose are visibly two
things, so it is the line that must never drop one. Shortened for the self-selection -- "player_one
chose to begin the next round" -- it reads exactly like a line that meant to name somebody and lost
them, and a reader would have to infer from an absent name which had happened. The event details
carry the two names and no `chose_self` flag: the flag said the same thing a third time, and its
only reader was the shorter wording.

### Opening a game

The same decision opens a game. Nobody has any piety yet, so no seat has earned the marker: it
starts on the **first player board, which is red**, and red is `player_two`. Generated scenarios
open in phase `start_player_selection` with `active_player` set to that seat, and it says who
begins. Because setup sow is sown in start-player order, this must be answered before any sowing:
applying the selection there moves to `setup_sow` rather than to `sow`.

The opening seat is **stated, not walked**. A tie-break walks clockwise from the current
`start_player`, and at game open there is no current start player -- the `start_player_id` a
generated file carries is a seed that the opening choice overwrites before any round ends, so
walking from it would derive who chooses from a value nobody chose. The two answers do agree today,
and `tests/test_opening_marker_seat.py` holds them to it.

Seat order is not player-id order, and this is a place it has bitten. `SEATED_PLAYERS` is
`(player_two, player_three, player_four, player_one)`: `player_one` is WHITE, at the far end of the
row. Reading "the first player board" as "the first player id" puts the marker on white, which is
what the code did until it was checked by colour. Assertions about this seat go through the board
colour, because a by-id assertion passes under both readings.

### Saved scenarios

No saved scenario can be mid-round-end under the old model, because that state was not
representable: the whole round end ran inside one `apply_action` and returned a position ready for
the next round. So there is nothing to migrate. Existing scenario files load unchanged, including
files that open in `setup_sow` with a `start_player_id` already set -- that is a legitimate saved
position in which the opening decision has already been made. A file naming a phase the code does
not know is rejected by `TurnPhase.from_string`, as before.

## Official score sheet

Round-end events update `GameState`, and official scoring is derived from that state when needed.

- There is no mutable running "current score" field in `GameState`.
- Use `python3 -m pilgrim.cli score <scenario>` for current/end-game score snapshots.
- Confession Box temporary start-player piety bonus is not persisted and is not counted in score.

See `docs/rules/Scoring.md` for implemented and deferred scoring categories.
