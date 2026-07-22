# Alms (v0.5 Sandbox Scope)

## Implemented scope

This milestone adds a conservative Alms subsystem for the headless sandbox:

- Per-player Alms track position (`alms_position`) with capped movement.
- Give Alms full-turn action resolution with explicit payment.
- Threshold-based workforce movement rewards.
- Season-end Alms reward helper with deterministic tie-breaks.
- Alms-table VP scoring from committed workforce (`workforce.committed.alms_table`).

This is intentionally scoped and does **not** represent full Pilgrim Alms rules.

## Track and movement

- Alms track rows: `0..6`.
- Movement is capped at row `6`.
- Give Alms advances by the current Duty Value.

## Payment assumption (current milestone)

- Payment amount must equal Duty Value.
- Payment can use **silver and/or wheat** only.
- Stone is not valid Alms payment in this milestone.
- If the duty is minority strength, minority silver cost still applies.

## Threshold rewards

Configured in `configs/alms.json`:

- Row `2`: `village_to_abbey`
  - Move 1 acolyte `village -> abbey` if village has an available acolyte.
- Row `4`: `abbey_to_city`
  - Move 1 acolyte `abbey -> city` (mancala city position) if abbey has an available acolyte.
- Row `6`: `village_to_city`
  - Move 1 acolyte `village -> city` if village has an available acolyte.

If the source pool is empty, no movement happens and the event explicitly reports that the reward was unavailable.

## Season-end helper

`resolve_alms_season_end(state, config)` is implemented as a standalone helper.

Tie-break model for this milestone:

1. Highest Alms position.
2. If tied, highest piety position.
3. If still tied, earliest in current turn order (active player first).

At season end:

- Winner moves 1 acolyte `abbey -> committed.alms_table`, if available.
- If winner has no abbey acolyte, no Alms-table acolyte is added.
- All players reset Alms position to row `0`.

## Alms-table scoring

Current lookup:

- `0` acolytes = `0` VP
- `1` acolyte = `5` VP
- `2` acolytes = `11` VP
- `3` acolytes = `18` VP
- `4+` acolytes = `26` VP (capped to highest configured table row)

## Debugging with CLI apply

When solver output does not choose a Give Alms line, use:

`python3 -m pilgrim.cli apply scenarios/alms_sandbox_001.json --action-index N --verbose`

Workflow:

1. Run `legal-actions` to list numbered full-turn actions.
2. Pick the 1-based index for a `give_alms` action.
3. Run `apply --action-index N --verbose` to inspect `ALMS_PAYMENT`, `ALMS_PROGRESS`, threshold rewards, recall, and invariant checks for that exact action.

## Deferred

- Full season/round timing integration.
- Any non-sandbox Alms rules or interactions with future building/trail/trade systems.
- Final game scoring beyond current sandbox evaluation approximation.
