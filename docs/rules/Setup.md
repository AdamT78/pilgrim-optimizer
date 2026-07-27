# Setup and Setup Sow (v2.0)

## Scope

Controlled scenario files remain the source of truth for tests and search.

Seeded setup generation is still a convenience step that writes deterministic scenario JSON.

## Setup sow phase

When setup sow is required, the game begins in a dedicated pre-game phase:

- `phase = setup_sow`
- each real player performs exactly one setup sow from `city`
- setup sow picks up all city acolytes and sows them on a legal route

During setup sow:

- no Duty resolution is triggered
- no tithe action is legal
- no minority silver cost is applied
- no acolyte recall occurs
- Merchant and Ship do not advance
- round-end/season-end phases do not run
- normal turn timing does not advance

After all setup players complete setup sow, the game transitions to normal play at:

- `absolute_turn = 0`
- `round_number = 1`
- `season_number = 1`
- `turn_in_round = 0`
- `active_player = start_player_id`
- `phase = sow`

## Explicit setup state

Rules state now includes explicit setup tracking in `initial_state.setup`:

```json
"setup": {
  "setup_sow_required": true,
  "setup_sow_complete": false,
  "setup_sow_completed_by": []
}
```

Backward compatibility:

- old hand-authored scenarios without setup state default to normal play
- generated-like scenarios that only set `setup_metadata.setup_sow_required: true` are loaded into setup sow mode

## Generated scenario metadata

Generated setup metadata now documents setup sow as implemented:

- `setup_sow_required: true`
- `setup_sow_implemented: true`

Generated scenarios still begin with 5 city acolytes per player.

## Abstract pilgrimage + building timeline (v4.3)

Seeded setup generation now derives building live rounds from an abstract 26-round border timeline
instead of sampling independent live rounds per building.

Timeline model:

- 26 abstract border positions (one per game round)
- quadrants:
  - NW: 6
  - NE: 7
  - SE: 6
  - SW: 7
- four pilgrimage sites in fixed order:
  - site 1 in NW
  - site 2 in NE
  - site 3 in SE
  - site 4 in SW

Pilgrimage placement rolls:

- one d6 roll per quadrant (`1..6`)
- NE/SW still roll `1..6` even though those quadrants have 7 positions

Round mapping from rolls:

- offsets: `NW=0`, `NE=6`, `SE=13`, `SW=19`
- absolute positions:
  - `P1_abs = rand_nw`
  - `P2_abs = 6 + rand_ne`
  - `P3_abs = 13 + rand_se`
  - `P4_abs = 19 + rand_sw`
- rounds:
  - `P1_round = 1`
  - `P2_round = 1 + (P2_abs - P1_abs)`
  - `P3_round = 1 + (P3_abs - P1_abs)`
  - `P4_round = 1 + (P4_abs - P1_abs)`

Building placement on this abstract timeline:

- place all selected Level 1 buildings first, then Level 2, then Level 3
- preserve deterministic market order within each level
- after each pilgrimage site, the next non-site round is reserved as empty
- after finishing one level, reserve one empty round before the next level
- if a pilgrimage site interrupts a level, placement resumes after that site's required empty round

Level start gates:

- Level 1 starts after site 1 gap
- Level 2 starts after both:
  - Level 1 completion gap
  - site 2 gap
- Level 3 starts after both:
  - Level 2 completion gap
  - site 3 gap

Generated scenarios continue to emit only:

- `initial_state.building_availability` (`building_id -> live_round`)

Optional generation metadata now also includes timeline inputs/derived rounds for inspection.

## Determinism boundary

Randomization happens only when running:

`python3 -m pilgrim.cli generate-setup ...`

No setup randomization occurs inside scenario loading, `legal_actions`, `apply_action`, or `solve`.
