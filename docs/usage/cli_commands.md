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

## Score sheet snapshot (official scoring)

```bash
python3 -m pilgrim.cli score scenarios/scoring_basic_breakdown_001.json
```

What it does right now:

- Loads a scenario state and prints an official score sheet for each real player.
- Uses the derived scoring model from `GameState` (no mutable running score state).
- Includes implemented categories:
  - acolytes in Abbey/City/Duty tiles
  - piety track VP
  - Alms table VP
  - donated buildings VP
  - resources VP (`(wheat + stone + silver) // 3`)
- Prints deferred scoring categories separately and excludes them from implemented totals.

Important distinction:

- `score` reports official score-sheet totals.
- `solve` still reports sandbox evaluation totals for search/debugging.

## Command 2: List legal actions

```bash
python3 -m pilgrim.cli legal-actions scenarios/mancala_sandbox_001.json
```

What it does right now:

- Loads the same scenario.
- Asks the current rules engine to generate legal actions for the current phase.
- In normal `sow` phase, each action is one complete simplified turn: sow + selected duty/tithe resolution.
- In `setup_sow` phase, actions are setup sow actions only (`Setup sow: ...`).
- In normal play, round length is based on real players in scenario state (`2..4`), not a fixed 2-player cadence.
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
- Verbose apply may also include round-end pipeline events (`EXCESS_RESOURCE_CAP`, `SHIP_ADVANCE`, `ROUND_ADVANCE`, `ALMS_SEASON_END`, `ALMS_SEASON_REWARD`, `ALMS_RESET`, `MERCHANT_ADVANCE`, `TRADE_ROUTE_INCOME`, `BUILDING_HIRED`, `CONFESSION_BOX_BONUS`, `START_PLAYER_SELECTION`, etc.) when boundaries are crossed.
- Verbose state summary always includes a `Setup` section (`required`, `complete`, `completed by`).

Why this matters:

- `solve` chooses the best action under the selected search objective (`sandbox` by default).
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
- Uses selectable search objectives (`--objective`) for leaf scoring.

Objective options:

- `sandbox` (default)
- `implemented-official-score`
- `sandbox-with-official-terminal`

Examples:

```bash
python3 -m pilgrim.cli solve scenarios/mancala_sandbox_001.json --depth 3 --objective sandbox
python3 -m pilgrim.cli solve scenarios/mancala_sandbox_001.json --depth 3 --objective implemented-official-score
```

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
- `best_score` follows the selected objective:
  - `sandbox`: sandbox evaluation
  - `implemented-official-score`: implemented official score-sheet total
  - `sandbox-with-official-terminal`: sandbox, except terminal states use implemented official score
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
  - `ROUND_ADVANCE`
  - `EXCESS_RESOURCE_CAP`
  - `SHIP_ADVANCE`
  - `ALMS_SEASON_END` / `ALMS_SEASON_REWARD` / `ALMS_RESET` (metadata-driven pilgrimage rounds)
  - `MERCHANT_ADVANCE` (round end only)
  - `START_PLAYER_SELECTION` (and tie-break event when relevant)

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
- Round-end transition flow currently does not auto-emit `DUMMY_ACOLYTE_MOVE`; that behavior is
  deferred for a later milestone.

## Round-End Phase Structure (v1.0)

- Merchant no longer advances after every turn; it advances once per round end.
- Round-end verbose traces now include:
  - `EXCESS_RESOURCE_CAP` (only when one or more players were capped)
  - `SHIP_ADVANCE`
  - `ROUND_ADVANCE`
  - `ALMS_SEASON_END`
  - `ALMS_SEASON_REWARD`
  - `ALMS_RESET`
  - `TRADE_ROUTE_INCOME` (after `MERCHANT_ADVANCE`, one event per gaining player)
  - `CONFESSION_BOX_BONUS` (start-player temporary piety bonus; optional `BUILDING_HIRED` first)
  - `START_PLAYER_SELECTION` (and optional tie-break event)
  - `GAME_END` at fourth season-end pilgrimage site (and still on legacy NW full-loop return)
- `game_over: true` is shown in verbose state summaries, and legal-action generation returns no actions.

Trade-route income notes:

- each player has scalar `trade_routes_count` on state (default `0`)
- at round end, after `MERCHANT_ADVANCE`, each player gains
  `trade_routes_count * current_merchant_resource`
- if Merchant resource is `none` (Taxation), no `TRADE_ROUTE_INCOME` event is emitted
- no extra resource-cap pass runs after this income; capped resources may exceed cap until next round-end

Confession Box start-player notes:

- a round end stops on `CONFESSION_BOX_PHASE` when any player can reach a Confession Box, naming
  the turn order and who is being waited on
- each player answers with their own action, summarised as one sentence and never as a list:
  - `Confession Box: use own active Confession Box`
  - `Confession Box: hire from market`
  - `Confession Box: hire from player_one`
  - `Confession Box: decline`
- a use prints `BUILDING_HIRED` (hires only) then `CONFESSION_BOX_BONUS`; a refusal prints
  `CONFESSION_BOX_DECLINED`, so a player who declined does not read the same as one never asked
- the last answer awards the marker, so `START_PLAYER_MARKER` appears on that action rather than
  on the round-ending turn
- legal-actions output is not pruned here: a player deciding for themselves cannot be measured
  against an outcome that turns on players who have not decided yet

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
  - `alms_house` (`give_alms` payment-ceiling boost; scales by occupancy with Chapter House)
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
- Building hiring for supported building effects is implemented; there is still no standalone
  "hire-only" command.

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
  - applies only to action wheat costs (`give_alms_paid` wheat, and
    Ordination step wheat)
  - does not waive silver costs, minority silver, tithe, or Mill hire payment
- Verbose apply output now includes Mill-specific bonus text:
  - `BUILDING_BONUS: mill waived wheat cost 2 for give_alms_paid`
  - `BUILDING_BONUS: mill waived wheat cost 2 for ordination`
- Hired Mill ordering remains:
  - `BUILDING_HIRED` before `BUILDING_BONUS`

## Grain Store Wheat/Silver Conversion (v4.0)

- Grain Store is available as an optional full-turn conversion modifier (not a standalone action):
  - `sell_wheat`: `wheat -X`, `silver +X`
  - `buy_wheat`: `silver -X`, `wheat +X`
  - `X >= 1`, fixed `1:1` rate
- Source resolution uses existing building-source priority:
  - own active Grain Store (free)
  - opponent active Grain Store (hire from owner)
  - live market Grain Store (hire from bank)
- Action summary examples:
  - `... | use building: grain_store to sell 2 wheat for 2 silver | ...`
  - `... | use building: grain_store to buy 1 wheat for 1 silver | ...`
  - hired variants append `| hire building: grain_store from <market|player_two>`
- Legal generation:
  - normal non-Grain Store actions remain legal
  - sell variants are generated for amounts `1..available_wheat_after_hire`
  - buy variants are generated for amounts `1..available_silver_after_hire`
  - no zero-amount variants
- `apply --verbose` ordering for Grain Store conversion:
  - `BUILDING_HIRED` (if hired)
  - `BUILDING_BONUS: grain_store sold/bought ...`
  - conversion `RESOURCE_DELTA`
  - `SOWING`

## Indulgences Piety/Silver Conversion (v5.0)

- Indulgences is available as an optional full-turn conversion modifier (not a standalone action):
  - `sell_piety`: `piety -X`, `silver +X`
  - `buy_piety`: `silver -X`, `piety +X`
  - `X >= 1`, fixed `1:1` rate
- Source resolution uses existing building-source priority:
  - own active Indulgences (free)
  - opponent active Indulgences (hire from owner)
  - live market Indulgences (hire from bank)
- Action summary examples:
  - `... | use building: indulgences to sell 2 piety for 2 silver | ...`
  - `... | use building: indulgences to buy 1 piety for 1 silver | ...`
  - hired variants append `| hire building: indulgences from <market|player_two>`
- Legal generation:
  - normal non-Indulgences actions remain legal
  - sell variants are generated for amounts `1..current_piety_after_hire`
  - buy variants are generated for amounts
    `1..min(available_silver_after_hire, piety_track_remaining_space)`
  - no zero-amount variants
  - no buy variants are generated at piety cap
- `apply --verbose` ordering for Indulgences conversion:
  - `BUILDING_HIRED` (if hired)
  - `BUILDING_BONUS: indulgences sold/bought ...`
  - conversion `RESOURCE_DELTA` (shows both `silver` and `piety` deltas)
  - `SOWING`

## Stone Yard Stone/Silver Conversion (v5.1)

- Stone Yard is available as an optional full-turn conversion modifier (not a standalone action):
  - `sell_stone`: `stone -X`, `silver +X`
  - `buy_stone`: `silver -X`, `stone +X`
  - `X >= 1`, fixed `1:1` rate
- Source resolution uses existing building-source priority:
  - own active Stone Yard (free)
  - opponent active Stone Yard (hire from owner)
  - live market Stone Yard (hire from bank)
- Action summary examples:
  - `... | use building: stone_yard to sell 2 stone for 2 silver | ...`
  - `... | use building: stone_yard to buy 1 stone for 1 silver | ...`
  - hired variants append `| hire building: stone_yard from <market|player_two>`
- Legal generation:
  - normal non-Stone-Yard actions remain legal
  - sell variants are generated for amounts `1..available_stone_after_hire`
  - buy variants are generated for amounts `1..available_silver_after_hire`
  - no zero-amount variants
- Resource bounds:
  - stone and silver cannot go below `0`
  - silver is uncapped
  - stone can exceed `6` during turn resolution and is capped later only by round-end excess rules
- `apply --verbose` ordering for Stone Yard conversion:
  - `BUILDING_HIRED` (if hired)
  - `BUILDING_BONUS: stone_yard sold/bought ...`
  - conversion `RESOURCE_DELTA` (shows `stone` and `silver` deltas)
  - `SOWING`

## Brewery Wheat-to-Silver Conversion (v5.2)

- Brewery is available as an optional full-turn conversion modifier (not a standalone action):
  - `sell_wheat_for_silver`: `wheat -1`, `silver +2`
  - exact-one conversion only (no amount variants)
  - one-direction only (no buy variants)
- Source resolution uses existing building-source priority:
  - own active Brewery (free)
  - opponent active Brewery (hire from owner)
  - live market Brewery (hire from bank)
- Action summary examples:
  - `... | use building: brewery to sell 1 wheat for 2 silver | ...`
  - hired variants append `| hire building: brewery from <market|player_two>`
- Legal generation:
  - normal non-Brewery actions remain legal
  - Brewery variants are generated only when at least `1` wheat remains after any hire payment
  - at most one Brewery conversion variant is generated per eligible base action
- `apply --verbose` ordering for Brewery conversion:
  - `BUILDING_HIRED` (if hired)
  - `BUILDING_BONUS: brewery sold 1 wheat for 2 silver`
  - conversion `RESOURCE_DELTA` (`silver +2; wheat -1`)
  - `SOWING`

## Guild Merchant Advance (v5.3)

- Guild is available as an optional pre-sow Merchant modifier (not a standalone action):
  - move Merchant exactly `+1` clockwise
  - no amount variants and no direction variants
- Source resolution uses existing building-source priority:
  - own active Guild (free)
  - opponent active Guild (hire from owner)
  - live market Guild (hire from bank)
- Action summary examples:
  - `... | use building: guild to move merchant +1 | ...`
  - hired variants append `| hire building: guild from <market|player_two>`
- Legal generation:
  - normal non-Guild actions remain legal
  - Guild variants are generated only when Guild source is usable and (if hired) payment is affordable
  - conservative scope: mixed Guild + other same-turn hire-dependent modifier combinations are deferred
- `apply --verbose` ordering for Guild:
  - `BUILDING_HIRED` (if hired)
  - `BUILDING_BONUS: guild moved Merchant clockwise +1`
  - `MERCHANT_ADVANCE: <from> -> <to>; current resource=<resource>; cause=guild`
  - `SOWING`
- Round-end interaction:
  - Guild Merchant movement is separate from round-end Merchant movement.
  - On a round-ending Guild turn, output may contain two `MERCHANT_ADVANCE` lines
    (one with `cause=guild`, one round-end advance without cause).

## Pulpit Free Serf Move (v5.4)

- Pulpit is available as an optional pre-sow workforce modifier (not a standalone action):
  - move exactly `1` serf `village -> abbey`
  - Pulpit movement is always free (`wheat_paid=0`)
  - no amount/direction variants are generated
- Source resolution uses existing building-source priority:
  - own active Pulpit (free)
  - opponent active Pulpit (hire from owner)
  - live market Pulpit (hire from bank)
- Action summary examples:
  - `... | use building: pulpit to move 1 serf village -> abbey for free | ...`
  - hired variants append `| hire building: pulpit from <market|player_two>`
- Legal generation:
  - normal non-Pulpit actions remain legal
  - Pulpit variants are generated only when source is usable and acting player has at least one
    Village serf after any required hire payment
  - no Pulpit variants are generated when `Village serfs = 0`
- `apply --verbose` ordering for Pulpit:
  - `BUILDING_HIRED` (if hired)
  - `BUILDING_BONUS: pulpit moved 1 serf village -> abbey for free`
  - `WORKFORCE_MOVE: player_one moved 1 serf village -> abbey; for free`
  - `SOWING`
- Infirmary interaction:
  - Pulpit is independent from Ordination Duty Value.
  - Pulpit remains exactly one free move even if Infirmary is active/hired.
  - Infirmary can still affect separate Ordination extra-step actions normally (extra step remains
    paid wheat).

## Scriptorium Effective Acolyte Modifier (v5.5)

- Scriptorium is available as an optional pre-sow duty-relation modifier (not a standalone action):
  - add `+1` effective acolyte on each occupied Duty tile for the acting player
  - applies only where the acting player already has at least one real acolyte
  - virtual-count effect only (no physical acolyte placement)
- Source resolution uses existing building-source priority:
  - own active Scriptorium (free)
  - opponent active Scriptorium (hire from owner)
  - live market Scriptorium (hire from bank)
- Action summary examples:
  - `... | use building: scriptorium for +1 effective acolyte on occupied Duty tiles | ...`
  - hired variants append `| hire building: scriptorium from <market|player_two>`
- Legal generation:
  - normal non-Scriptorium actions remain legal
  - Scriptorium variants are generated when source is usable and post-hire costs are affordable
  - selected Duty and Taxation majority checks for those variants use effective counts
- `apply --verbose` ordering for Scriptorium:
  - `BUILDING_HIRED` (if hired)
  - `BUILDING_BONUS: scriptorium added +1 effective acolyte on occupied Duty tiles this turn`
  - `SOWING`
  - `DUTY_RESOLUTION` (relation can differ from the non-Scriptorium variant)
- Taxation interaction:
  - Scriptorium affects both selected Taxation relation and other Duty-tile majority checks used by
    Taxation step 2.
  - No extra real acolytes are created; recall and workforce totals still reflect real board counts.

## Customs House Taxation Majority Override (v5.6)

- Customs House is available as an optional pre-sow Taxation-only relation modifier
  (not a standalone action):
  - occupied Duty tiles for the acting player are treated as majority-controlled for Taxation
  - applies to selected Taxation relation/value and Taxation step-2 bonus eligibility checks
  - virtual effect only (no physical acolyte placement)
- Source resolution uses existing building-source priority:
  - own active Customs House (free)
  - opponent active Customs House (hire from owner)
  - live market Customs House (hire from bank)
- Action summary examples:
  - `... | use building: customs_house for Taxation majority on occupied Duty tiles | ...`
  - hired variants append `| hire building: customs_house from <market|player_two>`
- Legal generation:
  - normal non-Customs-House actions remain legal
  - Customs House variants are generated for Taxation actions only
  - no Customs House + tithe/non-Taxation variants are generated
- `apply --verbose` ordering for Customs House:
  - `BUILDING_HIRED` (if hired)
  - `BUILDING_BONUS: customs_house claimed Taxation majority on occupied Duty tiles this turn`
  - `SOWING`
  - `DUTY_RESOLUTION` (Taxation relation can differ from non-Customs-House variant)
  - `TAXATION`

## Wagon Yard Free Hire (v5.7)

- Wagon Yard is available as an optional pre-sow free-hire enabler (not a standalone action):
  - own active Wagon Yard can hire one eligible live target building for free
  - target source may be `market` or `player_two`/other opponent id
  - Wagon Yard itself is not hireable for its own effect in this scope
- Action summary examples:
  - `... | use building: wagon_yard to hire brewery from market for free | use building: brewery to sell 1 wheat for 2 silver | ...`
  - `... | use building: wagon_yard to hire brewery from player_two for free | use building: brewery to sell 1 wheat for 2 silver | ...`
- Verbose apply output now uses explicit free-hire wording:
  - `BUILDING_HIRED: player_one hired Brewery from market for free with Wagon Yard`
  - `BUILDING_HIRED: player_one hired Brewery from player_two for free with Wagon Yard`
- No hire payment line appears for Wagon Yard free hire:
  - no bank payment
  - no opponent-owner payment
- Merchant interaction:
  - Wagon Yard free-hire variants remain legal when Merchant is on Taxation (`resource = none`)
  - Wagon Yard free-hire does not require Merchant affordability/resource checks
- Current supported free-hire targets in engine scope:
  - Grain Store, Indulgences, Stone Yard, Brewery, Guild, Pulpit, Scriptorium, Customs House
- Event ordering for free-hire target effects remains pre-sow:
  - `BUILDING_HIRED` (free via Wagon Yard)
  - target `BUILDING_BONUS` (and conversion `RESOURCE_DELTA` where applicable)
  - `SOWING`

## Building Turn-Modifier Registry (v3.3-v3.9)

- A dedicated registry tracks movement/turn-phase building modifiers:
  - `kogge`, `cloisters`, `dormitory`, `inquisition`, `library`
- Registry location:
  - `pilgrim/rules/building_turn_modifiers.py`
- Rule documentation:
  - `docs/rules/BuildingTurnModifiers.md`
- Runtime status:
  - `kogge` is implemented and can add `city -> east` / `city -> west` sow starts
  - action summaries show route usage:
    - `| use building: kogge` (own active)
    - `| hire building: kogge from market` or `| hire building: kogge from player_two`
  - verbose apply output includes:
    - `BUILDING_HIRED` before sowing for hired Kogge routes
    - `BUILDING_BONUS: kogge enabled city -> east|west sow route`
  - `cloisters` is implemented as a skip-route sow modifier:
    - action summary includes `| skip <location> with cloisters`
    - hired summaries include `| hire building: cloisters from <market|player_two>`
  - verbose apply output includes:
    - `BUILDING_HIRED` before sowing for hired Cloisters routes
    - `BUILDING_BONUS: cloisters skipped <location> during sow route`
    - `SOWING: ...; skipped <location> with Cloisters`
  - Kogge + Cloisters can combine in one action:
    - Kogge contributes City-start candidate route edges
    - Cloisters omits one City/Duty placement from that Kogge-enabled candidate route
    - summaries include both modifiers (Kogge source and Cloisters skip)
  - verbose apply output for combined routes includes deterministic ordering:
    - `BUILDING_HIRED` Kogge (if hired)
    - `BUILDING_HIRED` Cloisters (if hired)
    - `BUILDING_BONUS` Kogge
    - `BUILDING_BONUS` Cloisters
    - `SOWING`
  - `dormitory` and `inquisition` are implemented as start-turn relocation prefixes:
    - `start: dormitory east -> city | turn: sow city -> north | action: produce_wheat`
    - `start: inquisition city -> west | hire building: inquisition from market | turn: sow city -> north | action: produce_wheat`
  - verbose apply output includes:
    - `BUILDING_HIRED` (if hired) -> `BUILDING_BONUS` -> `START_TURN_RELOCATION` -> `SOWING`
    - `START_TURN_RELOCATION: player_one moved 1 acolyte east -> city using Dormitory`
    - `START_TURN_RELOCATION: player_one moved 1 acolyte city -> west using Inquisition`
  - `library` is implemented as an end-turn relocation suffix:
    - `Turn: sow city -> north | selected duty: north (produce) | action: produce_wheat | end: library city -> west`
    - `Turn: sow city -> north | selected duty: north (produce) | action: produce_wheat | end: library city -> abbey | hire building: library from market`
  - verbose apply output includes:
    - `BUILDING_HIRED` (if hired) -> `BUILDING_BONUS` -> `END_TURN_RELOCATION`
    - `END_TURN_RELOCATION: player_one moved 1 acolyte city -> west using Library`
    - `END_TURN_RELOCATION: player_one moved 1 acolyte city -> abbey using Library`
- Remaining scaffold:
  - all five turn-modifier buildings are now implemented
  - no dedicated CLI command is added for turn-modifier registry inspection

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
  - pilgrimage d6 rolls (`NW/NE/SE/SW`)
  - pilgrimage rounds derived from the abstract 26-round border timeline
  - `building_availability` derived from that timeline (not independent per-building sampling)
  - explicit dummy acolyte setup for `player_count`
  - explicit setup state (`initial_state.setup`)
  - setup metadata marking setup sow as required and implemented, including timeline details

`generate-setup` summary output now also shows:

- pilgrimage d6 rolls (`NW`, `NE`, `SE`, `SW`)
- pilgrimage rounds (`Site 1..4`)
- building live rounds grouped by level (`Level 1`, `Level 2`, `Level 3`)

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
