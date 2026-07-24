# Pilgrim Optimizer CLI: First Commands

## Purpose

This guide explains the core CLI commands in `pilgrim-optimizer` and what they currently prove in the Ruleset A mancala sandbox.

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
- Asks the current rules engine to generate legal actions for the current phase.
- In normal `sow` phase, each action is one complete simplified turn: sow + selected duty/tithe resolution.
- In `setup_sow` phase, actions are setup sow actions only (`Setup sow: ...`).
- Give Alms actions include explicit payment details (`pay silver=..., wheat=...`).
- If the acting player has active buildings, Give Alms can also show:
  - `action: give_alms_donate_building | building: <building_id>`
- Ordination actions show ordered steps:
  - `action: ordination | steps: ordain`
  - `action: ordination | steps: ordain; mission`
- Taxation actions show chosen resources:
  - `action: taxation | take: wheat`
  - `action: taxation | take: wheat; bonus: stone, silver`
- Prints a numbered list of readable legal-action summaries.
- Prints a final legal-action count.
- Action indexes are 1-based and can be passed directly to `apply --action-index`.
- If `game_over` is true, legal action list is empty by design.

Duty Tiles and Actions (canonical naming):

| Duty tile | Canonical action names |
| --- | --- |
| `produce` | `produce_wheat`, `produce_stone`, `tithe` |
| `clerical` | `clerical_devotion`, `clerical_silversmith`, `tithe` |
| `build_roads` | `build_roads_deferred`, `tithe` |
| `construct` | `construct_building`, `construct_building_and_road_deferred`, `construct_road_deferred`, `tithe` |
| `give_alms` | `give_alms_paid`, `give_alms_donate_building`, `tithe` |
| `ordination` | `ordination`, `tithe` |
| `allocation` | `allocation`, `tithe` |
| `taxation` | `taxation`, `tithe` |

Why this matters:

- It is one of the fastest ways to debug action generation.
- It should usually be checked before trusting solver output.

Example output:

```text
Legal actions for scenario 'mancala_sandbox_001':

1. Turn: sow city -> north -> north_east -> east | selected duty: north (produce) | action: produce_wheat
2. Turn: sow city -> north -> north_east -> east | selected duty: north (produce) | action: produce_stone
3. Turn: sow city -> north -> north_east -> east | selected duty: north (produce) | action: tithe
...
10. Turn: sow city -> south -> south_west -> west | selected duty: south (give_alms) | action: give_alms_paid | pay silver=1, wheat=1
11. Turn: sow city -> south -> south_west -> west | selected duty: south (give_alms) | action: give_alms_donate_building | building: confession_box
...

Total legal actions: N
```

## Command 3: Apply one legal action by index

```bash
python3 -m pilgrim.cli apply scenarios/alms_sandbox_001.json --action-index 1 --verbose
```

What it does right now:

- Loads the scenario and generates legal actions for the current phase.
- Selects one action by **1-based** index (matching `legal-actions` numbering).
- Applies exactly one transition.
- In non-verbose mode, prints selected action and next active player.
- In verbose mode, prints transition events, resulting state summary, and `Root-player evaluation after action`.
- Verbose apply may also include round-end pipeline events (`EXCESS_*`, `SHIP_ADVANCE`, `SEASON_END`, `MERCHANT_ADVANCE`, `START_PLAYER_SELECTION`, etc.) when boundaries are crossed.
- Verbose state summary always includes a `Setup` section (`required`, `complete`, `completed by`).

Why this matters:

- `solve` chooses the best action under current sandbox evaluation.
- `apply` is deterministic debugging: you choose the exact legal action to inspect.
- This is especially useful for `give_alms` debugging when solver policy picks another line.

Typical non-verbose output:

```text
Apply result for scenario 'alms_sandbox_001'
Selected action 1:
Turn: sow south_east -> south | selected duty: south | action: give_alms_paid | pay silver=1, wheat=1

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
- timing state (`Absolute turn`, `Round`, `Season`, `Turn in round`, `Start player`, `Game over`)
- Ship state (`Position`, `At pilgrimage site`, `At NW pilgrimage site`)
- Merchant state (`Position`, `Resource`)
- duty-tile layout (`Duty tiles:` with position -> category mapping)
- building market summary (`Level 1`, `Level 2`, `Level 3`)
- dummy acolyte state (`north_group`, `south_group`, `total`)
- `Acted player` (the player who executed that recommended turn)
- `Next active player` (the player whose turn is next)
- the acted player state so resource gains and acolyte recall are directly visible
- `Piety position` and `Piety track VP` for direct track-value inspection
- `Alms position`, `Alms table acolytes`, and `Alms table VP`
- a `Best-line final evaluation` section (state after the full principal variation)
- a `Root-player evaluation after best first full turn` section (state after only the recommended first full turn)
- workforce totals (`Mancala total`, `Village`, `Abbey`, `Special Activities`, committed pools, and overall `Total`)
- player-board workforce labels (`Village: Serfs`, `Abbey: Acolytes`)
- Special Activity occupancy summary (`Special Activities: ...`)
- selected-duty output now includes category identity, e.g.:
  - `selected duty: north_east (clerical)`
  - `DUTY_RESOLUTION: selected south (give_alms); ...`

`Workforce: Total` includes all currently tracked pools:

- Mancala/City/Duty acolytes
- Village serfs
- Abbey acolytes
- occupied Special Activity acolytes
- committed acolytes
- player board slot summary (`Active buildings`, `Donated buildings`, `Cardinal favor tiles`, `Used slots`, `Available slots`)

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
  - `Start player`
  - `Game over`
  - `Ship` status
- `apply --verbose` is especially useful for inspecting automatic boundary events:
  - `TURN_ADVANCE`
  - `ROUND_END` / `ROUND_ADVANCE`
  - `EXCESS_CHECK` / `EXCESS_DISCARD`
  - `SHIP_ADVANCE`
  - `SEASON_END` / `SEASON_ADVANCE`
  - `DUMMY_ACOLYTE_MOVE` (on season boundaries)
  - `MERCHANT_ADVANCE` (round end only)
  - `START_PLAYER_SELECTION` (and tie-break event when relevant)
  - season-end Alms events when a season closes

## Merchant Context (v0.8)

- Merchant position is now part of scenario state and advances at round end.
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

## Round-End Phase Structure (v1.0)

- Merchant no longer advances after every turn; it advances once per round end.
- Round-end verbose traces now include:
  - `EXCESS_CHECK` / `EXCESS_DISCARD`
  - `SHIP_ADVANCE`
  - `TRADE_ROUTE_INCOME_SKIPPED` (placeholder)
  - `START_PLAYER_SELECTION` (and optional tie-break event)
  - `GAME_END` when Ship returns to NW after the full 26-round loop
- `game_over: true` is shown in verbose state summaries, and legal-action generation returns no actions.

## Building Catalogue and Slots (v1.1)

- Building catalogue data is now loaded from `configs/buildings.json`.
- Scenario state includes a 12-building `building_market` with 4 buildings per level.
- If `building_market` is omitted, deterministic fallback is used (first 4 by level from catalogue order).
- Scenario state now also supports `building_availability` (`building_id -> live_round`).
  - live rounds are `2..26`
  - a building is live when `current round >= live_round`
  - if `building_availability` is omitted, selected market buildings default to live round `2`
- Verbose `solve` and `apply` output now include:
  - `Building market`
  - `Building availability` (`Live market`, `Future market`, `Owned/live`)
  - per-player `Player board slots`
  - slot usage lines (`Used slots`, `Available slots`)
- Construct building acquisition now appears in verbose output via `BUILDING_CONSTRUCTED`,
  updated market rows, and updated active-building slot usage.

## Player Board Workforce and Special Activities (v1.2)

- `apply --verbose` and `solve --verbose` now show explicit player-board workforce sections:
  - `Village` / `Serfs`
  - `Abbey` / `Acolytes`
  - `Special Activities`
- Allocation transitions emit readable `ALLOCATION` events.
- Active bonuses emit `SPECIAL_ACTIVITY_BONUS` events for:
  - `fields` (`produce_wheat`)
  - `stone_mason` (`produce_stone`)
  - `engraver` (`clerical_silversmith`)
  - `vestry` (`clerical_devotion`)
  - `alms_house` (`give_alms` duty-value boost + extra payment; scales by occupancy with Chapter House)
- `road_engineer` now boosts `build_roads_deferred` effective duty value by occupied acolyte count
  (up to `+2` with active Chapter House).

## Duty Tile Layout and Identity (v1.3)

- Duty tiles are now scenario-defined (or deterministic fallback) via `duty_tiles`.
- City is not a duty tile.
- The 8 non-city positions map to 8 duty categories exactly once each.
- Legal actions are now generated from duty category at selected position, not fixed position hardcoding.
- `construct` now exposes:
  - `construct_building`
  - `construct_building_and_road_deferred`
  - `construct_road_deferred` (road-only scaffold)
  - `tithe`
- Construct purchase actions are generated only for live market buildings.
- `build_roads` now exposes `build_roads_deferred` scaffold plus `tithe`.
- Build Roads remains fully non-spatial scaffolded.
- Construct road effects remain non-spatial scaffolded; only building acquisition is implemented.
- Building hiring (bank or other player) remains deferred.

## Building Hire Infrastructure (v3.0)

- The rules layer now has source/cost/payment helpers for building-ability access:
  - own active (`free`)
  - live market hire (`pay Merchant resource to bank`)
  - opponent active hire (`pay Merchant resource to owner`)
  - unavailable (`donated`, `not_live`, `merchant_resource_none`, `insufficient_resource`,
    `not_selected`)
- Taxation has no Tithe resource, so Merchant resource is `none` there; hired sources are
  unavailable there.
- A given building can be hired at most once in one player turn (pure helper/context scaffold).
- Different live buildings can each be hired once in the same turn if each cost is payable.
- No standalone hire command exists; hiring is attached to actions that consume the building
  ability.

## Hire Sources for Simple Building Bonuses (v3.1a)

- Action generation/apply now wire hire sources for:
  - `produce_wheat` (Well)
  - `produce_stone` (Quarry)
  - `clerical_silversmith` (Mint)
  - `clerical_devotion` (Chapel)
- When a hired source is used, action summaries include hire context:
  - `... | hire building: well from market`
  - `... | hire building: well from player_two`
- Verbose apply output now includes:
  - `BUILDING_HIRED` (for hired sources only)
  - `BUILDING_BONUS` (own or hired source)
- Taxation/merchant-none behavior for these actions:
  - hired variants are not generated
  - own-active bonus variants remain available
- Scope boundary remains:
  - Chapter House is not wired to hire sources yet.

## Hire Sources for Infirmary Duty Bonuses (v3.1b)

- `allocation` and `ordination` now also use Infirmary hire sources:
  - own active Infirmary (free)
  - live market Infirmary (pay Merchant resource `1` to bank)
  - opponent active Infirmary (pay Merchant resource `1` to owner)
- `legal-actions` output now includes hired Infirmary context when used, for example:
  - `... | action: allocation | ... | hire building: infirmary from market`
  - `... | action: ordination | steps: ordain; mission | hire building: infirmary from player_two`
- Allocation semantics:
  - Infirmary adds `+1 effective Duty Value`
- Ordination semantics:
  - Infirmary adds `+1 effective Duty Value` only for extra-step actions
  - extra Ordination steps still cost wheat
  - hired extra-step variants are emitted only when hire + step + minority costs are affordable
- `apply --verbose` event ordering for hired Infirmary actions:
  - `DUTY_RESOLUTION`
  - `BUILDING_HIRED`
  - `BUILDING_BONUS`
  - `ALLOCATION`/`ORDINATION` step events
- Merchant at Taxation still has resource `none`, so hired Infirmary variants are not generated.

## Mill Wheat-Cost Rule (v3.2)

- `give_alms_paid` and `ordination` now consume Mill from:
  - own active (free)
  - live market hire (`pay Merchant resource 1 to bank`)
  - opponent active hire (`pay Merchant resource 1 to owner`)
- Action summaries for hired Mill variants include both hire context and Mill spend context, for
  example:
  - `... | action: give_alms_paid | ... | hire building: mill from market | mill wheat spent=1`
  - `... | action: ordination | ... | hire building: mill from player_two | mill wheat spent=1`
- Mill wheat transform:
  - `mill_waiver = min(2, required_wheat)`
  - `actual_wheat_spent = max(0, required_wheat - 2)`
  - applies only to action wheat costs (`give_alms_paid` wheat + Alms House extra wheat, and
    Ordination step wheat)
  - does not waive silver costs, minority silver, tithe, or Mill hire payment
- Verbose apply output now includes Mill-specific bonus text:
  - `BUILDING_BONUS: mill waived wheat cost 2 for give_alms_paid`
  - `BUILDING_BONUS: mill waived wheat cost 2 for ordination`
- Hired Mill ordering remains:
  - `BUILDING_HIRED` before `BUILDING_BONUS`

## Building Turn-Modifier Scaffold (v3.3)

- A metadata-only registry now tracks deferred movement/turn-phase building modifiers:
  - `kogge`, `cloisters`, `dormitory`, `inquisition`, `library`
- Registry location:
  - `pilgrim/rules/building_turn_modifiers.py`
- Rule documentation:
  - `docs/rules/BuildingTurnModifiers.md`
- Scope boundary:
  - no runtime behavior is wired yet
  - no legal-action output changes are expected from these entries in this milestone
  - no dedicated CLI command is added yet; this is scaffolding only

## Produce Options and Fields Rename (v1.4)

- Produce duty now exposes exactly two explicit actions:
  - `produce_wheat`
  - `produce_stone`
- Produce duty value cannot be split across wheat and stone in one action.
- `fields` is now the canonical special-activity ID (replacing `grain`).
- `fields` adds `+1 wheat` to `produce_wheat` only.
- `stone_mason` adds `+1 stone` to `produce_stone` only.

## Allocation Duty Move Sequences (v1.5)

- Allocation action summaries now show explicit move sequences:
  - `action: allocation | moves: abbey -> fields`
  - `action: allocation | moves: abbey -> fields; abbey -> engraver`
- Allocation no longer uses `target: city` output.
- Verbose apply emits one `ALLOCATION` event per move in sequence order.
- Allocation moves are between Abbey and Special Activities only.

## Give Alms Building Donation Option (v1.6)

- Give Alms now has two explicit options:
  - `give_alms_paid` (pay silver/wheat)
  - `give_alms_donate_building` (donate one active building)
- Donation transitions now emit `BUILDING_DONATION` and `ALMS_PROGRESS`.
- Donation always advances Alms by exactly one row.
- On majority Give Alms, donation does not chain into a second paid Give Alms step.
- Alms House still enhances paid `give_alms_paid` only; it does not modify
  `give_alms_donate_building`.

## Ordination Duty Steps (v1.7)

- Ordination now has a dedicated `ordination` action with ordered steps.
- Step primitives are:
  - `ordain` (pay 1 wheat; village -> abbey)
  - `mission` (pay 1 wheat; abbey -> city)
- One action can include `1..duty_value` steps, validated sequentially.
- Verbose apply now emits one `ORDINATION` event per step.

## Taxation Duty Rules (v1.8)

- Taxation now has a dedicated `taxation` action in legal-action generation.
- Step I always takes one chosen resource (`stone`, `silver`, or `wheat`).
- Step II uses Tithe-counter resource types from other majority duty tiles only.
- The selected Taxation duty tile is excluded from Step II and has no non-null Tithe counter.
- At duty value 2, Step II can choose repeated/mixed resources (for example `stone, stone` or `stone, silver`).
- Verbose apply emits `TAXATION` events for step 1 and step 2 plus a single combined `RESOURCE_DELTA`.
- Merchant at Taxation still shows `Resource: none`.

## Seeded Setup Generation and Setup Sow (v2.0)

Generate deterministic setup scenarios from `(players, seed)`:

```bash
python3 -m pilgrim.cli generate-setup --players 2 --seed 123 --output scenarios/generated/setup_2p_seed_123.json
```

Current behavior:

- setup randomness is used only at generation time (local seeded RNG)
- generated scenario files are plain JSON and can be committed/validated
- same seed + same player count produces identical output
- generated file includes:
  - randomized duty layout
  - randomized Tithe counters (Taxation tile excluded)
  - randomized 12-building market (4 per level)
  - explicit dummy acolyte setup for `player_count`
  - explicit setup state (`initial_state.setup`)
  - setup metadata marking setup sow as required and implemented

Setup sow behavior:

- `solve` on setup-required scenarios lists setup sow actions, not duty/tithe full turns
- `apply --verbose` emits setup-specific events:
  - `SETUP_SOWING`
  - `SETUP_SOW_COMPLETE`
  - `SETUP_PLAYER_ADVANCE`
  - `SETUP_COMPLETE` (final setup sow)
- setup sow does not emit duty/timing/round-end events
- after final setup sow, normal play starts at turn 0 timing scaffold

Determinism boundary remains unchanged:

- no randomization occurs inside `validate`, `legal-actions`, `apply`, or `solve`

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
