# Timing (v1.0 Sandbox Scope)

## Implemented scope

The sandbox tracks timing explicitly and now includes a round-end phase pipeline.

`TimingState` fields:

- `absolute_turn`: completed full player turns
- `round_number`: current round (starts at 1)
- `season_number`: current season (starts at 1)
- `turn_in_round`: 0-based turn index within the current round

`GameState` adds round-end context fields:

- `start_player`: current holder of the start-player marker
- `ship_position`: abstract Ship marker position
- `completed_rounds`: count of completed rounds
- `game_over`: blocks future legal actions when true

## Round and season definitions

- One full turn = one applied `FullTurnAction`.
- One round = each real player acts once (`players_per_round = 2` in current sandbox).
- Season end is no longer based only on a round-number boundary.
- Season end is now triggered by Ship reaching a pilgrimage-site position after round-end Ship advance.
- `configs/timing.json` still carries round/turn limits, while pilgrimage-site season boundaries come from `configs/ship.json`.

## Timing progression

After every full turn:

1. `TURN_ADVANCE` is emitted.
2. If this turn does **not** end the round, processing goes directly to `INVARIANT_CHECK`.
3. If this turn ends the round, run the full round-end pipeline (see `docs/rules/RoundEnd.md`).

Key correction in v1.0:

- Merchant does **not** advance on ordinary turns.
- Merchant advances once during round-end processing.

## Interaction with duty layout (v1.3)

- Timing flow is unchanged by duty-tile layout customization.
- Duty category identity is now scenario-defined and independent from physical position, but
  turn/round/season advancement still keys off applied full turns exactly as before.

## Season-end integrations

At Ship-triggered season end:

- existing Alms helper resolves leader reward (`ALMS_SEASON_REWARD`)
- Alms positions reset (`ALMS_RESET`)
- dummy acolytes move (`DUMMY_ACOLYTE_MOVE`) only on non-final season ends
- season increments (`SEASON_ADVANCE`) only if game is not over

## Game-end integration

Game end can occur during round-end processing:

- condition: Ship returns to NW pilgrimage site after at least 26 completed rounds
- event: `GAME_END`
- after this point, legal action generation returns no actions
- on this final NW season end, Alms still resolves/resets first, then game ends immediately
- dummy acolytes do not move on the final game-ending NW round

## Deferred

- Confession Box round-end behavior and temporary piety bonuses.
- Start-player free choice by the deciding player (placeholder policy currently auto-selects self).
- Spatial/hex movement details for Ship and map geometry.
