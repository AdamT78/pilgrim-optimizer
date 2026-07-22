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

## Intentionally Deferred

- Full Pilgrim rule set and board systems.
- Rich replay visualizations.
- Performance tuning and parallelized search strategies.
