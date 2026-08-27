# Architecture Overview

This is the map of the running engine: use it to decide where a change belongs. It deliberately
describes current responsibilities, not the order in which features arrived. The versioned record
is in [Feature notes](feature_notes.md).

## Reading guarantees

A claim marked **Guard:** names the test that should fail if it stops being true. A focused guard
is evidence for the stated behavior, not proof of an unstated universal property. Claims without a
guard are collected in [Known unguarded claims](#known-unguarded-claims).

## Current layering

| Area | Responsibility | Guard |
| --- | --- | --- |
| `pilgrim.model` | Immutable state, action, event, and configuration shapes. It makes a position safe to compare, replay, and use as a search key; it does not decide rules. | `tests/test_turn_steps.py::test_apply_turn_step_is_pure_and_leaves_a_hashable_state` |
| `pilgrim.rules` | The authoritative rules boundary: enumerate legal choices, apply one choice, validate the result, and emit structured facts about what happened. New game logic belongs here, not in a caller. | `tests/test_legal_actions_apply.py::test_every_legal_action_applies` |
| `pilgrim.io` | Load a scenario into model values and serialize state/events for replay or other adapters. It translates formats, not rules. | `tests/test_turn_steps.py::test_turn_progress_is_serialised_and_end_of_turn_resets_it` |
| `pilgrim.search` | Select among engine-provided choices and evaluate the resulting states. It owns search policy and objectives, never a second game-rule implementation. | `tests/test_library_end_turn_relocation.py::test_exact_search_refuses_library_in_the_end_of_turn_window` |
| `pilgrim.cli` | A thin command-line boundary over loading, rules, and search. It should report engine results, not repair them. | `tests/test_cli_output_contracts.py::test_cli_scriptorium_legal_actions_contract_prunes_no_op_variants_output` |

The play server is an adapter alongside these layers. It turns engine decisions and events into
player-facing words and publishes them to the page; it is not a rules layer.

## The decision boundary

The central rule is: **the engine decides, the play server explains, and the page renders what it
is given.** The server may choose clear player language, but it must receive the decided candidates,
settled payments, previews, and events from the engine. The browser may filter and reveal those
published choices; it must never derive legality, routes, adjacency, or another rule locally.

**Guard:** `tests/test_play_server.py::test_what_is_offered_is_what_the_engine_says_may_come_next`
checks that offered choices are engine choices, and
`tests/test_play_server.py::test_the_script_may_filter_and_reveal_and_nothing_else` rejects
rule-looking browser code. The mutation guard
`tests/test_play_server.py::test_a_rule_computed_in_the_script_is_caught` proves the latter
guard can fail.

This boundary matters even when a recomputation would appear equivalent. At the Cornucopia, the
engine enumerates the exact resource that pays for a hire. Re-resolving the hire source later only
finds the Merchant's wildcard, not that settled payment. A page that guesses again can render a
legal-looking but different decision. **Guard:**
`tests/test_merchant_cornucopia.py::test_a_conversion_step_records_its_cornucopia_payment` and
`tests/test_play_server.py::test_cornucopia_turn_step_payload_keeps_the_enumerated_payment_resource`.

## Design constraints

- Rule transitions are deterministic and do not mutate the input position. The focused
  purity/hashability guard is
  `tests/test_turn_steps.py::test_apply_turn_step_is_pure_and_leaves_a_hashable_state`; it does
  not prove this property for every rules function.
- Search must not embed game rules. Its complete current contract is
  `legal_actions()` + `apply_action()` for full turns, plus a `turn_steps()` check that
  refuses positions it cannot yet search. A future step-aware search must consume
  `turn_steps()` + `apply_turn_step()` as well. **Guard:**
  `tests/test_library_end_turn_relocation.py::test_exact_search_refuses_library_in_the_end_of_turn_window`.
- Static game data belongs in `configs/`; this placement is a convention, not presently protected
  by an architecture-level test.
- Structured events are the engine's replay/debug facts, while the server owns their wording.
  Event ordering is covered for representative paths by
  `tests/test_library_end_turn_relocation.py::test_library_step_moves_after_recall_and_before_turn_advance`.
  No test establishes that every possible transition emits an event.

## One turn, two windows

Normal play is in `TurnPhase.SOW` throughout both optional building windows. The discriminator is
`turn_progress.resolution_committed`, not a second phase:

1. **Beginning-of-turn window** — `phase == TurnPhase.SOW` and
   `resolution_committed == False`. `turn_steps()` can offer committed starts such as
   conversions, activations, and pre-sow relocations.
2. **Sow and resolution** — choose a `FullTurnAction` through `legal_actions()`; it carries the
   sow and the selected action or tithe. `apply_action()` resolves it and commits the resolution.
3. **End-of-turn window** — still `TurnPhase.SOW`, now
   `resolution_committed == True`. Post-resolution steps such as Library may be available.
   In `legal_actions()`, `EndTurnAction` is the only legal `GameAction`; any offered
   `TurnStep` must be committed separately before it is applied.
4. **Pass** — apply `EndTurnAction` to run the end-of-turn/round work, advance the turn, and
   reset progress for the next beginning-of-turn window.

**Guard:** `tests/test_post_resolution_conversion_window.py::test_devotion_keeps_the_turn_open_for_a_conversion_then_end_turn_passes`
checks the shared phase, commit flag, post-resolution step, sole `EndTurnAction`, and reset;
`tests/test_library_end_turn_relocation.py::test_relocation_steps_are_offered_in_their_respective_windows`
checks the window split.

## Two decision-generation paths

| Path | It represents | Where a change belongs | Guard |
| --- | --- | --- | --- |
| `legal_actions()` / `apply_action()` | Whole normal-turn decisions: sow, route, selected Duty, resolution, and resolution-specific choices. It also serves setup and marker-decision phases. | Add a legal player choice that is resolved atomically with the sow/Duty action. Resolution-specific hires such as Well remain on this path. | `tests/test_legal_actions_apply.py::test_every_legal_action_applies`; `tests/test_hired_simple_building_bonuses.py::test_market_well_hire_variant_exists_for_produce_wheat` |
| `turn_steps()` / `apply_turn_step()` | A building decision committed during the current turn, so later choices are generated from the altered state. | Add an optional building effect whose timing changes later availability, payment, resources, workforce, or movement. | `tests/test_turn_steps.py::test_two_active_conversion_buildings_remain_independently_available` |

Conversions (Grain Store, Indulgences, Stone Yard, Brewery), Guild and Pulpit activations, and
Dormitory/Inquisition/Library relocations are committed steps. Paid route/modifier hires such as
Kogge, Cloisters, Scriptorium, Customs House, Bank, and Wagon Yard are also committed before they
can widen a later action set. **Guard:**
`tests/test_pulpit_free_serf_move.py::test_full_turn_actions_carry_no_pulpit_modifier_fields`,
`tests/test_start_turn_relocations.py::test_full_turn_actions_and_ids_carry_no_start_turn_relocation_fields`,
and `tests/test_hired_route_buildings_as_turn_steps.py::test_hired_kogge_routes_only_appear_after_its_committed_hire`.

`full_turn_actions()` is a lazy composition helper that walks reachable pre-resolution step
prefixes with full-turn actions; it is useful for generation/audits, not the contract exact search
currently implements. **Guard:** `tests/test_turn_steps.py::test_full_turn_actions_collapses_conversion_order_transpositions`.

## Building taxonomy

Treat a building's effect type and its source as separate questions.

- A **doer** changes state by an explicit click/step: a conversion, activation, or relocation. It
  must be represented by a `TurnStep` when its commitment changes what can happen later.
  **Guard:** `tests/test_pulpit_free_serf_move.py::test_own_active_pulpit_generates_one_free_beginning_of_turn_step`.
- A **passive** affects an applicable resolution without a separate question. It is never offered
  merely to acknowledge ownership. **Guard:**
  `tests/test_passive_buildings.py::test_simple_passive_applies_only_on_its_owned_duty_and_not_other_locations`.
- A **permitter** widens the legal action set. An owned permitter is free and invisible as a
  separate choice; the actions it permits simply appear. **Guard:**
  `tests/test_hired_route_buildings_as_turn_steps.py::test_owned_route_buildings_are_free_immediate_and_offer_no_step`.
- **Hiring is an orthogonal source axis, not a fourth effect type.** A hired building costs a
  resource and can pay another player, so its use must remain an explicit decision. Depending on
  timing it is either a settled field on the atomic full-turn resolution or a committed step that
  enables later choices. **Guard:**
  `tests/test_hired_simple_building_bonuses.py::test_opponent_well_hire_pays_owner_and_adds_bonus`
  and `tests/test_hired_modifier_buildings_as_turn_steps.py::test_hired_scriptorium_only_changes_actions_after_its_step`.

## What exact search can do today

`pilgrim/search/exact.py` searches only `legal_actions()` and applies only
`apply_action()`. Before each node, and before it passes a committed resolution window,
`_refuse_unsearched_turn_steps` asks `turn_steps()`; if any are available, exact search raises
instead of silently skipping them. It therefore does **not** search a position with available
committed steps, pre- or post-resolution. **Guard:**
`tests/test_library_end_turn_relocation.py::test_exact_search_refuses_library_in_the_end_of_turn_window`.

## Instruments

- `python tools/capture_legal_actions.py <dir>` is the full-turn refactor tripwire. It writes
  every scenario's action IDs in generation order, so a saved search cannot be silently churned.
- `python tools/capture_turn_steps.py <dir>` is the corresponding committed-step tripwire. It
  writes step IDs in generation order for top-level and playtest scenarios.
- `tools/audits/building_status_branching_audit.py` reports the current building-status
  classification and one-position action/step branching measurements. It keeps pre-resolution
  counts distinct from an unmeasured post-resolution window. **Guard:**
  `tests/test_building_status_branching_audit.py::test_branching_rows_are_deterministic_for_representative_subset`
  and `tests/test_building_status_branching_audit.py::test_library_row_marks_its_post_resolution_window_unmeasured`.
- `tools/audits/multi_turn_branching_audit.py` traces fixed multi-turn lines, recording
  generation and committed steps before actions and after resolution, so movement of an effect
  between representations remains visible. **Guard:**
  `tests/test_multi_turn_branching_audit.py::test_post_resolution_turn_steps_are_recorded_before_end_turn`
  and `tests/test_multi_turn_branching_audit.py::test_trace_rows_are_deterministic_and_have_no_duplicate_action_ids`.

The capture tools themselves do not have dedicated automated tests. Their required before/after
diff use is a repository workflow rule in `AGENTS.md`, not a test-proven runtime invariant.

## Known unguarded claims

- No test enforces the package ownership boundaries in the layering table.
- No architecture-level test enforces that all static game data lives in `configs/`.
- No exhaustive test proves all rules transitions are pure/deterministic or all transitions emit
  structured events.
- No exhaustive test proves that every engine decision has every player-facing payload field the
  page will need. The play-server guards cover the exercised controls and reject browser rule
  derivation, but they are not a complete schema proof.

## Related documents

- [Feature notes](feature_notes.md) — chronological historical record; not current architecture.
- [Search and pruning model](search_and_pruning_model.md) — exact-search scope and pruning.
- [Player choice model](player_choice_model.md) — older inventory; assess it against the committed
  step model before treating its flattened-action claims as current.
- [Official scoring](../rules/Scoring.md) — implemented score-sheet categories and deferred scope.
