# Search and Pruning Model

## Purpose

This document explains how search interacts with the Pilgrim rules engine and catalogs the
pruning/canonicalization rules that currently control legal-action branching.

It is an implementation guide for contributors. It describes current behavior and scope
boundaries; it is not a rules proposal.

## Search contract

Current exact search is intentionally rules-agnostic.

- `pilgrim/search/exact.py` expands nodes only through:
  - `legal_actions(state, config)`
  - `apply_action(state, action, config)`
- Search does not import building-specific rule modules directly.
- Search chooses lines from returned legal actions and evaluates resulting states.

Practical implication:

- if a branch should be searchable, it must appear in `legal_actions`
- if a branch should be deterministic and replayable, it must be expressed in `apply_action`
  state transitions and events

## Search objective selection (v5.11)

Exact search now supports selectable leaf-scoring objectives via `solve_exact(..., objective=...)`.

Supported objectives:

- `sandbox` (default): uses sandbox evaluation from `evaluate_player(...).total`
- `implemented_official_score`: uses official score-sheet implemented total from
  `score_breakdown(...).implemented_total`
- `sandbox_with_official_terminal`: uses sandbox during play and switches to implemented official
  score only when `state.game_over` is true

Objective selection changes only leaf scoring. It does not change:

- legal action generation
- transition/apply behavior
- pruning rules
- round-end/start-player policy

Important distinction:

- official score sheet remains owned by rules scoring (`pilgrim/rules/scoring.py`)
- sandbox evaluation remains owned by evaluation (`pilgrim/evaluation/breakdown.py`)
- search objective chooses which scoring model to apply at leaf states

## FullTurnAction expansion model

Normal play search branches over complete `FullTurnAction` variants.

One legal action can flatten multiple conceptual subchoices into one object, including:

- sow origin
- route
- selected Duty tile
- selected Duty action
- action parameters (for example Ordination steps, Taxation resources, Allocation move sequence)
- optional building modifiers (source + mode + amount where applicable)
- round-end subchoices currently modeled in action metadata (for example Confession Box uses)

See `docs/architecture/player_choice_model.md` for the full choice-inventory view.

## Why pruning exists

Building modifiers and composed legal variants can create large action sets. Pruning is used to:

- avoid no-op variants
- avoid duplicate-equivalent variants
- limit intentionally out-of-scope composition combinations
- keep generic search/explainability smoke tests focused on contract behavior rather than
  branch-factor stress

Important distinction:

- Rules correctness: a tabletop-legal option can exist.
- Engine pruning/scope: the runtime may omit a branch when it is documented as no-op,
  outcome-irrelevant under current simplifications, state-equivalent, or intentionally deferred.

## Pruning categories

### 1) No-op pruning

Variants are not generated when they cannot affect the modeled result.

Examples:

- Scriptorium variants are skipped for actions where relation/value context is irrelevant
  (`tithe`, `give_alms_donate_building`) via `_scriptorium_can_affect_action(...)`.
- Customs House variants are Taxation-only via `_customs_house_can_affect_action(...)`.

### 2) Scope pruning

Variants are excluded when composition is intentionally outside current implementation scope.

Examples:

- mixed pre-sow modifier combinations are blocked/deferred in transition validation
  (`"Combining ... is deferred"` checks in `pilgrim/rules/transition.py`)
- Wagon Yard composition is constrained by `_wagon_yard_action_is_supported_composition(...)`

### 3) Outcome-based pruning

Variants are generated only when they can change the modeled outcome under current policy.

Example:

- Confession Box start-player variants are generated from legal source/payment combinations, then
  pruned against the no-use baseline in `_start_player_confession_box_variants_for_action(...)`
  by comparing resolved next `start_player`.

### 4) Source/availability pruning

Variants are excluded when source/payment preconditions are not met.

Examples include:

- unusable source (`source.usable == false`)
- donated/unavailable source
- not-live/future source
- hired source when Merchant resource is `none`
- hired source when payment is unaffordable
- source-priority constraints where own-active handling suppresses hired alternatives for that
  option shape

### 5) Duplicate/canonicalization pruning

Legal generation contains repeated de-dup checks (`if action not in actions`) to prevent duplicate
action objects from entering the final set.

## Current pruning rules

| Area | Pruning rule | Reason | Status / notes |
| --- | --- | --- | --- |
| Scriptorium | `_scriptorium_can_affect_action(...)` excludes no-impact resolutions | avoid no-op variants | Implemented |
| Customs House | `_customs_house_can_affect_action(...)` keeps Taxation-only | effect applies only to Taxation relation checks | Implemented |
| Wagon Yard | own-active enabler only, no self-target, target-source filtering, supported-composition filtering | avoid nested/free-hire composition explosion and unsupported chains | Implemented with explicit deferred edges |
| Confession Box | always keep no-use; keep use/hire combinations only when next `start_player` differs from no-use baseline | outcome-based pruning under deterministic self-selection policy | Implemented |
| Mixed pre-sow modifiers | explicit `"Combining ... is deferred"` validation checks | hire-order-sensitive composition intentionally deferred | Implemented as scope boundary |
| Generic exact-search smoke tests | use lightweight scenarios instead of broad sandbox market branching | keep contract tests fast and stable | Implemented in current smoke fixtures |

## Search test fixtures vs full rule scenarios

The repository now separates two test roles:

- **Search/CLI contract smoke**: small deterministic fixtures with low branch factor
  - `scenarios/mancala_sandbox_search_smoke_001.json`
  - `scenarios/player_board_slots_search_smoke_001.json`
- **Rule coverage and interaction tests**: broader scenarios that intentionally exercise
  building/round-end/action branching

This keeps generic solve/explainability tests from becoming implicit performance benchmarks for
every new branching feature.

## Guidelines for adding new pruning

- Prefer pruning no-op variants during legal-action generation.
- Do not hide meaningful strategic choices unless documented as a simplification/scope boundary.
- If pruning is outcome-based, compare against a baseline outcome using the same policy helpers
  used by runtime resolution.
- Keep action IDs stable for unaffected actions.
- Add focused tests for both:
  - variants that must remain
  - variants that must be pruned
- Keep production branch pruning separate from test-fixture simplification.

## Known deferred branching areas

Current deferred/simplified areas that can expand branching later include:

- start-player decider selecting any player (current policy self-selects)
- duty-value intensity controls (partial-use decisions)
- deeper Allocation optionality/ordering semantics
- spatial roads/bridges/trade-route creation systems
- deferred building effects (for example `bank`, `reliquary`)
- broader mixed-modifier composition/hire-order-sensitive stacks

## Related documents

- `docs/architecture/overview.md`
- `docs/architecture/player_choice_model.md`
- `docs/rules/Buildings.md`
- `docs/rules/RoundEnd.md`
