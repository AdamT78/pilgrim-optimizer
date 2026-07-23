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

## Determinism boundary

Randomization happens only when running:

`python3 -m pilgrim.cli generate-setup ...`

No setup randomization occurs inside scenario loading, `legal_actions`, `apply_action`, or `solve`.
