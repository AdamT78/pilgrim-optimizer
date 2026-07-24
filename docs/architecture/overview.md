# Architecture Overview

## Current Layering

- `pilgrim.model`: immutable/hashable domain models and config representations.
- `pilgrim.rules`: deterministic transition logic, legal action generation, and invariants.
- `pilgrim.io`: JSON scenario loading and event/replay serialization helpers.
- `pilgrim.search`: optimization routines that call rules APIs only.
- `pilgrim.cli`: thin command-line entrypoint over scenario loading + engine/search calls.

## Design Constraints

- Rules code must be deterministic and side-effect free.
- Search must not embed game rules; it consumes `legal_actions()` and `apply_action()`.
- Static game data should live in `configs/` JSON files.
- Every transition emits structured events to support replay and debugging.

## Search Perspective Model (v0.3)

- **Game state**: immutable snapshot with active player, resources, piety position, and mancala vectors.
- **Active player**: the player whose turn is currently being simulated.
- **Root player**: the player whose outcome the solve call optimizes.
- **Opponent model**: placeholder policy for how non-root decisions are selected during search.
- **Evaluator**: computes sandbox score breakdown for a chosen player perspective.
- **Search algorithm**: expands full-turn actions via rules APIs and chooses lines according to the configured opponent model.

Current default opponent model is `sandbox_active_player_max`: each active player picks locally favorable actions, while terminal/cutoff score reporting remains root-player-based.

## Workforce Pools (v0.4)

- `PlayerState` now contains explicit workforce pools.
- Mancala acolytes are only one workforce component.
- Additional pools are represented for future systems: village, abbey, and committed pools (roads, shrines, market ports, pilgrimage sites, alms table).
- Transition validation enforces workforce non-negativity and conservation.

## Alms Subsystem (v0.5)

- Alms adds per-player track state (`alms_position`) plus VP scoring from committed `alms_table` acolytes.
- Give Alms is the first sandbox subsystem that moves workforce across pools:
  - `village -> abbey`
  - `abbey -> city` (mancala city position)
  - `village -> city`
- Season-end Alms helper adds a deterministic tie-breaked leader reward:
  - potential `abbey -> committed.alms_table` move
  - then Alms-position reset for all players
- Search remains rules-agnostic: it still consumes `legal_actions()` and `apply_action()` only.

## Evaluation Breakdown Cleanup (v0.6)

- Evaluation is now centralized in `pilgrim.evaluation` and remains separate from rules.
- The canonical model is `EvaluationBreakdown` (player identity + scoring components + total).
- Current sandbox-only formula:
  - `victory_points + piety_track_vp + alms_table_vp + resource_total`
- Search optimizes `EvaluationBreakdown.total` for the configured root player.
- CLI `solve --verbose` and `apply --verbose` use the same evaluation breakdown formatter.
- This is still an early proxy objective, not full Pilgrim final scoring.

## Round and Season Timing (v0.7)

- `GameState` now carries explicit timing state:
  - absolute turn number
  - round number
  - season number
  - turn index within round
- Active player progression is independent from root-player optimization perspective:
  - **active player** = whose full turn is being simulated now
  - **root player** = whose `EvaluationBreakdown.total` search optimizes
- Post-turn timing advancement is centralized in `pilgrim.rules.timing`.
- After each full turn the transition pipeline now:
  - advances active player and absolute timing
  - detects whether the turn closed the round
  - runs extra round-end phases only when needed

## Merchant Context (v0.8)

- `GameState` now includes `merchant_position` as deterministic turn-to-turn context.
- Merchant path and duty-to-resource lookup are loaded from `configs/merchant.json`.
- Round-end transition flow advances Merchant position once per completed round.
- Merchant context is reusable infrastructure for future systems:
  - building-hire payment resource
  - trade-route income resource
- At `taxation`, Merchant resource context is intentionally `None` (no resource).

## Dummy Acolytes (v0.9)

- `GameState` now tracks neutral dummy acolytes as two internal groups:
  - `north_group`
  - `south_group`
- Dummy setup is table-size dependent (`player_count`):
  - 2 players: 3+3 seeded dummies
  - 3 players: 2+2 seeded dummies
  - 4 players: no dummies
- Dummy totals are included in Duty strength comparison as neutral competition.
- Season-end flow now includes deterministic dummy leap-frog movement before `SEASON_ADVANCE`.
- Search remains rules-agnostic: dummy behavior is encapsulated in rules/state transition code.

## Round-End Phase Pipeline (v1.0)

- Round-end orchestration is now explicit in `pilgrim.rules.transition` and helper modules:
  - `pilgrim.rules.round_end` for excess caps, start-player policy, trade-route placeholder
  - `pilgrim.rules.ship` for abstract Ship marker movement and site checks
- `GameState` now tracks:
  - `start_player`
  - `ship_position`
  - `completed_rounds`
  - `game_over`
- Season-end trigger now comes from Ship pilgrimage-site positions, not only round cadence.
- Game end occurs when Ship returns to NW pilgrimage site after 26 completed rounds, after final season-end Alms resolution.
- When `game_over` becomes true, `legal_actions()` returns no actions, keeping search/CLI behavior deterministic.

## Building Catalogue and Slots (v1.1)

- `GameConfig` now includes static building metadata loaded from `configs/buildings.json`.
- Building config now captures:
  - 24-entry catalogue
  - per-level pool metadata
  - per-game draw shape (4/4/4)
  - player-board slot limit
- `GameState` now tracks:
  - `building_market` (12 stable ids for current game)
  - per-player board-slot occupancy (`active_buildings`, `donated_buildings`, `cardinal_favor_tiles`)
- Scenario loading stays deterministic:
  - explicit `building_market` is accepted
  - missing market falls back to first 4 ids per level from catalogue order
- Transition/search are still rules-agnostic with no building actions yet; this milestone adds data and validation only.

## Player Board Workforce and Special Activities (v1.2)

- `PlayerState` now carries per-player `special_activities` occupancy counts.
- Player-board workforce semantics are now explicit in CLI/docs:
  - Village workers (Serfs) via `workforce.village`
  - Abbey acolytes via `workforce.abbey`
  - City/Duty acolytes via `workforce.mancala`
- New rules helper module `pilgrim.rules.special_activities` centralizes:
  - occupancy queries and formatting
  - allocation helpers (Abbey <-> Special Activity and Special -> Special)
  - current activity bonus hooks
- Transition layer now supports:
  - `allocation` duty resolution
  - `ALLOCATION` events
  - `SPECIAL_ACTIVITY_BONUS` events for active effects
  - optional Alms House give-alms boost with explicit extra payment fields
- Search remains decoupled from these details and still consumes `legal_actions()` + `apply_action()`.

## Duty Tile Identity Framework (v1.3)

- Duty identity is now scenario-defined via a deterministic `duty_tiles` layout.
- Physical board position and duty category are explicitly separated:
  - physical: non-city mancala positions
  - identity: one of eight duty categories
- `GameConfig` now resolves duty category by selected position at runtime.
- Legal action generation and duty resolution use category-based option mapping, removing
  hardcoded position semantics like "south always means give_alms".
- Deferred categories remain valid in layout.
- `construct` currently exposes no non-tithe action.
- `build_roads` now exposes a deterministic scaffold action (`build_roads_deferred`) that
  resolves duty relation/cost/recall without spatial map effects.

## Seeded Setup Generator (v1.9)

- Setup randomization is now available as an explicit CLI file-generation step only.
- `generate-setup` uses a local seeded RNG to produce deterministic scenario JSON from:
  - player count
  - seed
  - output path
- Generated files include:
  - randomized duty layout
  - randomized Tithe counters (with Taxation tile excluded)
  - randomized 12-building market draw (4 per level)
  - explicit dummy setup by player count
  - turn-0 scaffold state plus setup metadata
- Runtime determinism boundary is unchanged:
  - no randomization inside scenario loading
  - no randomization inside transition/apply logic
  - no randomization inside search/solve

## Setup Sow Phase (v2.0)

- `GameState` now tracks explicit setup progression:
  - `setup_sow_required`
  - `setup_sow_complete`
  - `setup_sow_completed_by`
- Top-level phase now includes `setup_sow` for pre-game actions.
- Legal-action generation is phase-aware:
  - `setup_sow` phase generates setup-only sow actions
  - `sow` phase generates normal full-turn duty/tithe actions
- Setup sow transitions are isolated from normal turn advancement:
  - no duty resolution/tithe flow
  - no recall
  - no turn/round/season advancement
  - no Merchant/Ship movement
- Setup completion transition is explicit:
  - marks all players complete
  - returns to normal `sow` phase
  - resets active player to `start_player`
  - preserves turn-0 timing scaffold
- Validation includes setup-state invariants so malformed setup progression fails fast.

## Duty Enhancement Registry (v2.3)

- `pilgrim.rules.duty_enhancements` now provides a deterministic metadata registry of Duty
  enhancements by:
  - duty category + action key
  - source type/key (Special Activity or building)
  - effect text and implementation status
- This registry is intentionally non-executable documentation/scaffolding:
  - gameplay transitions do not auto-consume it
  - existing duty-specific hooks remain authoritative runtime behavior
  - known unimplemented building effects are tracked without changing rules execution

## Construct Building Acquisition (v2.5)

- Construct now includes explicit acquisition actions:
  - `construct_building`
  - `construct_building_and_road_deferred`
  - `construct_road_deferred` (road-only scaffold retained)
- Building acquisition transition behavior is now stateful:
  - validates market presence, stone affordability, and free player-board slot
  - applies stone payment (plus normal minority silver cost when applicable)
  - removes the acquired building from `building_market`
  - adds the building to acting player's `active_buildings`
  - emits `BUILDING_CONSTRUCTED` explainability event
- Mixed Construct (`building + road`) is partially implemented:
  - building resolves now
  - road part stays deferred with `DUTY_DEFERRED`
  - Road Engineer still uses Construct-specific extra-road semantics only
- Runtime market validation now supports shrinking `building_market` during play while preserving
  deterministic id/level constraints.

## Infirmary Duty Bonuses (v2.6)

- Infirmary building effects are implemented in explicit duty-specific transition/generation paths
  (not via generic registry execution):
  - Allocation: active Infirmary adds `+1 effective Duty Value`
  - Ordination: active Infirmary allows one additional paid step and contributes
    `+1 effective Duty Value` only when that extra step is actually used
- Legal-action generation now incorporates Infirmary caps where relevant:
  - Allocation move-sequence generation uses `base + 1` when Infirmary is active
  - Ordination sequence generation can explore one extra step when Infirmary is active, while
    step-level wheat/workforce legality is still enforced by Ordination rules
- Event semantics stay consistent with existing duty-value policy:
  - true duty-value modifiers surface via `effective_duty_value` in `DUTY_RESOLUTION`
  - Infirmary emits `BUILDING_BONUS` duty-value events
  - direct output bonuses (Well/Quarry/Mint/Chapel and matching Special Activities) remain
    separate output bonuses and do not alter `effective_duty_value`

## Chapter House Special Activity Capacity (v2.7)

- Special Activity occupancy is now count-based (`0..2`) with immutable state semantics.
- Scenario loading now supports legacy boolean/list forms and count mappings for
  `special_activities`.
- Chapter House behavior is implemented through explicit transition/helpers (not via generic
  registry execution):
  - active Chapter House raises Special Activity capacity from `1` to `2`
  - second-acolyte placements are still ordinary Allocation moves
  - donated/inactive Chapter House does not apply
- Allocation legal generation/apply now uses capacity-aware move validation:
  - `abbey -> special_activity`
  - `special_activity -> abbey`
  - `special_activity -> special_activity`
  - source counts decrement by 1; destination counts increment by 1
- Special Activity bonuses now scale by occupancy count:
  - Fields / Stone Mason / Engraver / Vestry output bonuses
  - Alms House paid Give Alms duty-value bonus (`+1`/`+2` by paid extras)
  - Road Engineer Build Roads duty-value bonus (`+1`/`+2`)
  - Road Engineer Construct deferred extra-road scaffold count (`+1`/`+2`)

## Building Availability Timeline (v2.9)

- `GameState` now carries deterministic `building_availability` metadata:
  - tuple of `(building_id, live_round)` entries
  - live rounds constrained to `2..26`
- Scenario-loading behavior:
  - explicit `initial_state.building_availability` is parsed and validated
  - legacy scenarios without it default selected market buildings to live round `2`
- Validation now enforces:
  - all current market buildings have availability entries
  - availability keys reference selected in-game buildings
  - round bounds and uniqueness constraints
- Rules helpers now expose:
  - `building_live_round(...)`
  - `is_building_live(...)`
  - `live_buildings(...)`
  - `future_buildings(...)`
- Construct integration:
  - legal Construct purchase actions are now gated to live market buildings
  - apply-time validation rejects attempts to construct non-live market buildings
- Setup generator integration:
  - generated setups now include explicit live rounds for selected buildings using seeded local RNG
- Hiring remains deferred:
  - no bank-hire or other-player-hire runtime behavior is implemented yet

## Building Hire Infrastructure (v3.0)

- Rules now include a deterministic building-ability source resolver:
  - `own_active`
  - `live_market_hire`
  - `opponent_active_hire`
  - `unavailable`
- Resolver semantics include unavailable reasons (`donated`, `not_live`,
  `merchant_resource_none`, `insufficient_resource`, `not_selected`).
- Merchant-based hire-cost infrastructure is now explicit:
  - cost is `1` Merchant resource
  - Taxation has no Tithe resource, so Merchant resource is `none` there
  - live market hire pays bank
  - opponent active hire pays owner
  - own active use pays nothing
- Turn-hire tracking infrastructure is now explicit:
  - same building cannot be hired twice in one player turn
  - different buildings can each be hired once in same turn
  - implemented as pure immutable helper/context scaffolding (not persisted in `GameState`)
- Payment routing helpers now support pure description + state application for transfers.
- Transition wiring now consumes this infrastructure for:
  - Well/Quarry/Mint/Chapel (direct-output bonuses)
  - Infirmary (`allocation` + `ordination` duty-value cap effects)
  - Mill (`give_alms_paid` + `ordination` wheat-cost waiver)

## Hire Sources for Simple Building Bonuses (v3.1a)

- Transition/runtime wiring now consumes hire sources for four direct-output bonuses:
  - Well -> `produce_wheat`
  - Quarry -> `produce_stone`
  - Mint -> `clerical_silversmith`
  - Chapel -> `clerical_devotion`
- Source resolution remains deterministic:
  - own active (free)
  - live market hire (pay bank)
  - opponent active hire (pay owner)
  - unavailable
- Taxation clarification is now fully enforced in these wired actions:
  - Taxation has no Tithe resource
  - Merchant resource is `none`
  - hired variants are unavailable while own-active variants still work
- Event ordering for hired sources is explicit:
  - `BUILDING_HIRED` then `BUILDING_BONUS`
- Chapter House remains outside hire-source wiring in this milestone.

## Hire Sources for Infirmary Duty Bonuses (v3.1b)

- Transition/runtime wiring now consumes hire sources for Infirmary in:
  - `allocation` (`+1 effective Duty Value`)
  - `ordination` (`+1 effective Duty Value` only when the extra paid step is used)
- Source resolution remains deterministic:
  - own active (free)
  - live market hire (pay bank)
  - opponent active hire (pay owner)
  - unavailable
- Legal-action generation now:
  - preserves base Allocation/Ordination actions without forced hire
  - emits hired Infirmary variants only when the extra cap is actually used
  - enforces joint affordability (minority silver + step wheat + hire payment)
- Apply-time ordering for hired Infirmary paths:
  - `DUTY_RESOLUTION`
  - `BUILDING_HIRED`
  - `BUILDING_BONUS`
  - `ALLOCATION` / `ORDINATION` step events
- Scope boundary remains:
  - Chapter House hire wiring is still deferred
  - no standalone "hire action" exists; hiring is attached to consuming actions

## Mill Wheat-Cost Rule (v3.2)

- Transition/runtime wiring now consumes hire sources for Mill in:
  - `give_alms_paid`
  - `ordination`
- Source resolution remains deterministic:
  - own active (free)
  - live market hire (pay bank)
  - opponent active hire (pay owner)
  - unavailable
- Wheat-cost transform:
  - `mill_waiver = min(2, required_wheat)`
  - `actual_wheat_spent = max(0, required_wheat - 2)`
- Scope behavior:
  - waives only action wheat costs (`give_alms_paid` wheat + Alms House extra wheat, Ordination step
    wheat)
  - does not waive silver costs, minority silver, tithe, or Mill hire payment
- Apply-time ordering for hired Mill paths:
  - `DUTY_RESOLUTION`
  - `BUILDING_HIRED`
  - `BUILDING_BONUS`
  - action-specific events (`ORDINATION` steps / Alms events)

## Building Turn-Modifier Scaffold (v3.3)

- Added a dedicated metadata registry in `pilgrim/rules/building_turn_modifiers.py` for
  non-duty-output building effects that target movement/turn phases.
- Registry entries (all scaffolded in this milestone):
  - during sow route modifiers: `kogge`, `cloisters`
  - start-of-turn relocations: `dormitory`, `inquisition`
  - end-of-turn relocation: `library`
- This registry is intentionally non-executable scaffolding:
  - no route graph changes yet
  - no start/end-turn relocation pipeline yet
  - no legal/apply behavior changes yet
- Separation of concerns:
  - Duty-output modifiers stay in `duty_enhancements`
  - turn-phase movement modifiers live in `building_turn_modifiers`

## Intentionally Deferred

- Full Pilgrim rule set and board systems.
- Rich replay visualizations.
- Performance tuning and parallelized search strategies.
