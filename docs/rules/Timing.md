# Timing (v0.7 Sandbox Scope)

## Implemented scope

The sandbox now tracks turn/round/season timing explicitly in state.

`TimingState` fields:

- `absolute_turn`: completed full player turns
- `round_number`: current round (starts at 1)
- `season_number`: current season (starts at 1)
- `turn_in_round`: 0-based turn index within the current round

Current sandbox timing config is loaded from `configs/timing.json`.

## Round and season definitions

- One full turn = one applied `FullTurnAction`.
- One round = each player acts once (`players_per_round = 2`).
- One season = configured number of rounds (`rounds_per_season = 3`).

## Event order after a full turn

After a full-turn action resolves, the engine runs timing progression and emits timing events:

1. `TURN_ADVANCE` (always)
2. `ROUND_END` and `ROUND_ADVANCE` (if round boundary reached)
3. `SEASON_END` (if season boundary reached)
4. Season-end Alms events:
   - `ALMS_SEASON_REWARD`
   - `ALMS_RESET`
5. `SEASON_ADVANCE`

Only boundary events that actually apply are emitted.

## Alms season-end integration

When a season boundary is reached through normal turn progression:

- the existing Alms leader helper resolves winner/reward
- winner may move 1 acolyte `abbey -> committed.alms_table` if available
- all players reset Alms position to 0
- season number then advances

## Deferred

- Piety-based start-player selection between rounds/seasons.
- Full game-end timing and termination logic beyond current sandbox placeholders.
