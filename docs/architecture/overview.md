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
  - emits turn/round/season timing events when boundaries are crossed
  - resolves season-end Alms effects automatically when season boundaries are reached
- Deferred timing item:
  - piety-based start-player selection for new seasons (not implemented yet)

## Intentionally Deferred

- Full Pilgrim rule set and board systems.
- Rich replay visualizations.
- Performance tuning and parallelized search strategies.
