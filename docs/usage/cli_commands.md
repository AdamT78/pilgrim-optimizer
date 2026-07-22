# Pilgrim Optimizer CLI: First Commands

## Purpose

This guide explains the first four CLI commands in `pilgrim-optimizer` and what they currently prove in the Ruleset A mancala sandbox.

The goal is to make the early loop explicit:

`scenario -> validate -> legal actions -> apply -> search -> recommendation`

## Prerequisites

- Python 3.12+ installed (`python3 --version`)
- Project dependencies installed from repository root:

```bash
python3 -m pip install -e ".[dev]"
```

- You are in the repository root:

```bash
cd /path/to/pilgrim-optimizer
```

## Command 1: Validate a scenario

```bash
python3 -m pilgrim.cli validate scenarios/mancala_sandbox_001.json
```

What it does right now:

- Loads the scenario JSON file.
- Parses it and loads the linked setup/config JSON files.
- Checks simplified mancala-sandbox invariants.
- Confirms the scenario is a valid starting state for the current engine.

What it does **not** do:

- It does not solve the game.
- It does not prove full Pilgrim rules are implemented.

Typical output:

```text
Scenario 'mancala_sandbox_001' is valid.
```

## Command 2: List legal actions

```bash
python3 -m pilgrim.cli legal-actions scenarios/mancala_sandbox_001.json
```

What it does right now:

- Loads the same scenario.
- Asks the current rules engine to generate legal **full-turn** actions.
- Each listed action is one complete simplified turn: sow + selected duty/tithe resolution.
- Give Alms actions include explicit payment details (`pay silver=..., wheat=...`).
- Prints a numbered list of readable full-turn summaries.
- Prints a final legal-action count.
- Action indexes are 1-based and can be passed directly to `apply --action-index`.

Why this matters:

- It is one of the fastest ways to debug action generation.
- It should usually be checked before trusting solver output.

Example output:

```text
Legal actions for scenario 'mancala_sandbox_001':

1. Turn: sow city -> north -> north_east -> east | selected duty: north | action: produce
2. Turn: sow city -> north -> north_east -> east | selected duty: north | action: tithe
...
9. Turn: sow city -> south -> south_west -> west | selected duty: south | action: give_alms | pay silver=1, wheat=1
...

Total legal actions: N
```

## Command 3: Apply one legal action by index

```bash
python3 -m pilgrim.cli apply scenarios/alms_sandbox_001.json --action-index 1 --verbose
```

What it does right now:

- Loads the scenario and generates legal full-turn actions.
- Selects one action by **1-based** index (matching `legal-actions` numbering).
- Applies exactly one transition.
- In non-verbose mode, prints selected action and next active player.
- In verbose mode, prints transition events, resulting state summary, and `Root-player evaluation after action`.
- Verbose apply may also include automatic timing/season events (`TURN_ADVANCE`, `ROUND_END`, `SEASON_END`, `ALMS_RESET`, etc.) when boundaries are crossed.

Why this matters:

- `solve` chooses the best action under current sandbox evaluation.
- `apply` is deterministic debugging: you choose the exact legal action to inspect.
- This is especially useful for `give_alms` debugging when solver policy picks another line.

Typical non-verbose output:

```text
Apply result for scenario 'alms_sandbox_001'
Selected action 1:
Turn: sow south_east -> south | selected duty: south | action: give_alms | pay silver=1, wheat=1

State updated successfully.
Next active player: player_two
```

## Command 4: Run the simple solver

```bash
python3 -m pilgrim.cli solve scenarios/mancala_sandbox_001.json --depth 3
```

What it does right now:

- Runs the current exact-search prototype.
- Searches to the specified depth in **full turns** (`--depth 3` means 3 complete turns).
- Uses a temporary placeholder evaluation function.

Example output:

```text
Solve result for scenario 'mancala_sandbox_001'
Root player: player_one
Objective: maximize root player sandbox evaluation
Opponent model: sandbox_active_player_max
Depth: 3
Best score: 3
Nodes expanded: 27

Best first full turn:
Turn: sow city -> north -> north_east -> east | selected duty: east | action: clerical_silversmith

Best line:
1. player_one: Turn: sow city -> north -> north_east -> east | selected duty: east | action: clerical_silversmith
2. player_two: Turn: sow north -> north_east | selected duty: north_east | action: clerical_devotion
3. player_one: Turn: sow city -> south | selected duty: south | action: tithe
```

## How to interpret the current output

- The old machine-oriented token `best_action=sow:0:1->2->3` is now shown in readable form.
- `city -> north -> north_east -> east` corresponds to position IDs `0 -> 1 -> 2 -> 3`.
- `nodes_expanded` means the number of search nodes explored.
- `best_score` is still a value under a **temporary placeholder sandbox evaluation**, not true final Pilgrim VP.
- `best line` is now a sequence of full turns, not alternating sow/resolve sub-actions.
- `root player` is whose outcome is being optimized.
- `active player` is whose turn is currently applied in a simulated state.
- A single search line may alternate active players while still optimizing root-player outcome.
- Together, this confirms the current development loop works end-to-end:
  `scenario -> validate -> legal actions -> search -> recommendation`.

Using `--verbose` with `solve` prints:

- all transition events for the recommended first full turn (sowing + duty/tithe + invariants)
- a compact state summary after applying that first full turn
- timing state (`Absolute turn`, `Round`, `Season`, `Turn in round`)
- Merchant state (`Position`, `Resource`)
- dummy acolyte state (`north_group`, `south_group`, `total`)
- `Acted player` (the player who executed that recommended turn)
- `Next active player` (the player whose turn is next)
- the acted player state so resource gains and acolyte recall are directly visible
- `Piety position` and `Piety track VP` for direct track-value inspection
- `Alms position`, `Alms table acolytes`, and `Alms table VP`
- a `Best-line final evaluation` section (state after the full principal variation)
- a `Root-player evaluation after best first full turn` section (state after only the recommended first full turn)
- workforce totals (`Mancala total`, `Village`, `Abbey`, committed pools, and overall `Total`)

Position mapping used by the current sandbox:

- `0 = city`
- `1 = north`
- `2 = north_east`
- `3 = east`
- `4 = south_east`
- `5 = south`
- `6 = south_west`
- `7 = west`
- `8 = north_west`

## What this does not mean yet

- The engine is not complete for full Pilgrim gameplay.
- The solver score is not final-game scoring quality.
- This is not strategic proof or balance validation.
- Only the current deterministic mancala-sandbox slice is covered.

## Piety Track Scoring (v0.2)

- Piety is now treated as a capped track position (`max_position = 12`).
- Piety position and piety VP are different values.
- The VP lookup table is loaded from `configs/piety.json`.
- Sandbox solver evaluation is still temporary, but now uses **piety track VP** instead of raw piety position.

## Root Player and Opponent Model (v0.3)

- Scenarios can set `root_player_id` explicitly (preferred).
- If `root_player_id` is omitted, the loader defaults to the initial active player.
- Current opponent model placeholder is `sandbox_active_player_max`.
- This means each active player locally selects actions, while cutoff/terminal scoring is still read from the root player perspective.

## Alms Track and Season Reward (v0.5)

- Alms positions are tracked per player (`0..6`, capped).
- Give Alms actions now appear in legal-action output when payment is affordable.
- Verbose solve output now includes Alms-specific events (`ALMS_PAYMENT`, `ALMS_PROGRESS`, threshold rewards).
- Verbose evaluation sections now include Alms-table scoring.
- Use `apply --action-index` to force a specific Give Alms transition for debugging.

## Evaluation Breakdown Cleanup (v0.6)

- `solve --verbose` and `apply --verbose` now use a shared evaluation breakdown formatter.
- Search and CLI both use the same canonical evaluation calculation via `EvaluationBreakdown`.
- `Total sandbox evaluation` is still a sandbox proxy, **not** true final Pilgrim VP.
- In solve verbose output:
  - `Best-line final evaluation` = after the full best line
  - `Root-player evaluation after best first full turn` = after one applied recommended turn
- Current formula:
  - `victory_points + piety_track_vp + alms_table_vp + resource_total`

## Round and Season Timing (v0.7)

- Timing progression is now explicit and automatic after each full turn.
- Verbose state summaries include:
  - `Absolute turn`
  - `Round`
  - `Season`
  - `Turn in round`
- `apply --verbose` is especially useful for inspecting automatic boundary events:
  - `TURN_ADVANCE`
  - `MERCHANT_ADVANCE`
  - `ROUND_END` / `ROUND_ADVANCE`
  - `SEASON_END` / `SEASON_ADVANCE`
  - `DUMMY_ACOLYTE_MOVE` (on season boundaries)
  - season-end Alms events when a season closes

## Merchant Context (v0.8)

- Merchant position is now part of scenario state and advances after full turns.
- Verbose `solve` and `apply` state summaries now include:
  - `Merchant`
  - `Position`
  - `Resource`
- At taxation, verbose output shows `Resource: none`.

## Dummy Acolytes (v0.9)

- 2-player and 3-player scenarios now include neutral dummy acolytes.
- If `dummy_acolytes` are not explicitly provided, setup defaults are seeded from `player_count`.
- Verbose `solve` and `apply` state summaries include:
  - `Dummy acolytes`
  - `north_group`
  - `south_group`
  - `total`
- On season-end turns, verbose event output includes `DUMMY_ACOLYTE_MOVE`.

## Typical development workflow

1. Edit rules/config/scenario files.
2. Run `validate` to ensure scenario integrity.
3. Run `legal-actions` to inspect generated action space.
4. Run `apply` on a chosen action index when you need deterministic transition debugging.
5. Run `solve` with a small depth to sanity-check transitions/search loop.
6. Run `pytest` to protect behavior with tests.

## Troubleshooting

- `zsh: command not found: python`
  - Use `python3` instead of `python`.
  - Optional alias:
    `echo 'alias python=python3' >> ~/.zshrc && source ~/.zshrc`
- Scenario path errors
  - Confirm file exists: `scenarios/mancala_sandbox_001.json`.
  - Run commands from repository root.
- Validation fails
  - Check JSON syntax and current invariants (acolyte conservation, non-negative resources, legal route lengths).
- Solver output seems surprising
  - Inspect `legal-actions` first.
  - Remember the current scoring function is a temporary placeholder.
  - Use `apply --action-index N --verbose` to inspect a specific action.
  - Re-run with verbose mode for transition details:
    `python3 -m pilgrim.cli solve scenarios/mancala_sandbox_001.json --depth 3 --verbose`

## Next planned CLI improvements

- Clearer validation diagnostics (which invariant failed and why).
- Optional JSON output mode for tools/integration.
- Scenario diff helpers for fast debugging.
- Replay/event export commands for transition traces.
- Additional solver options beyond exact depth-limited search.
