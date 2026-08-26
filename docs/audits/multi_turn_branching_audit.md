# Multi-Turn Branching Audit

## Purpose

This audit is deterministic, reporting-only diagnostics for branching behavior over scripted
multi-turn traces.

It helps answer:

- how legal-action branching changes over time
- how committed turn steps expand the reachable choices at each position
- where branching spikes appear
- whether duplicate action IDs appear
- how often key branching contributors (step hires, conversions, relocations, route modifiers)
  occur
- how much branching comes from base sow/action expansion (origins/routes/duties/pickups)

This audit does **not** change rules, action generation, event wording, or search behavior.

## Run

From repository root:

```bash
python3 tools/audits/multi_turn_branching_audit.py
```

## Trace set

Current default traces:

- `basic_2p_round_flow`
- `movement_hotspot_2p`
- `grain_store_2p`
- `generated_setup_3p`
- `generated_setup_4p`

These traces are deterministic branching probes, not strategic play.

## Per-step columns

Each trace step reports:

- timing/player context (`step`, `absolute_turn`, `round`, `season`, `turn_in_round`, `active_player`)
- branching totals (`legal_action_count`, `unique_action_id_count`, `duplicate_action_id_count`)
- committed-step branching counts:
  - `turn_step_count`
  - `reachable_step_sequences` (including the empty, no-commit sequence)
  - `action_step_sequence_product` (`Act×Seq`)
  - `hired_turn_steps`
  - `conversion_turn_steps`
  - `grain_store_conversion_turn_steps`
  - `relocation_turn_steps`
- action-feature counts that still live on `FullTurnAction`:
  - `actions_with_route_modifier`
  - `actions_with_kogge`
  - `actions_with_cloisters`
  - `actions_with_kogge_cloisters_combined`
- base sow/action breakdown counts:
  - `setup_sow_actions`
  - `full_turn_actions`
  - `distinct_sow_origins`
  - `distinct_routes`
  - `distinct_actual_routes`
  - `distinct_selected_duties`
  - `distinct_duty_actions`
  - `max_picked_up_acolytes`
  - `avg_picked_up_acolytes`
  - `max_route_length`
  - `avg_route_length`
- chosen deterministic action (`selected_action_id` + `selected_action_summary`)
- every committed trace step, with the complete stable list of step IDs offered immediately before
  that commit and the selected step ID/summary

The report prints:

- a `Branching totals` table
- a `Base sow/action breakdown` table
- a `Committed turn steps` record
- a per-trace `Summary` and `Base branching summary` section

The base summary includes a deterministic likely-driver heuristic (reporting only):

- `base sow/duty expansion`
- `committed turn-step branching`
- `combined route modifiers`
- `route modifiers`
- `mixed / low`

Before each action, a trace commits all currently offered turn steps using the stable lowest
turn-step ID, except `grain_store_2p`: its first pre-action commit must be a Grain Store
conversion step and raises if none is offered. After resolution, it records and commits all
offered post-resolution steps before selecting `EndTurnAction`; it does not assume the window has
only one action.

## Determinism

- fixed trace order
- fixed per-trace selector strategy
- deterministic fallback selection by `action_id`
- stable turn-step selection and sequence traversal by `turn_step_id`
- no timestamps in output

## Limitations

- Trace selectors are intentionally simple and deterministic, not optimal strategy.
- The 10,000-prefix step-sequence walk cap prints lower bounds (`>=…`), keeps the first eight
  stable dropped prefixes, and prints the count of additional omitted prefixes. `Act×Seq`
  multiplies the current legal-action count by reachable step prefixes; it is a comparable
  branching diagnostic, not a future step-aware search-node count because step commits can alter
  the next legal-action set.
- Counts are generated-choice diagnostics, not semantic proof of play quality.
- Generated 3p/4p traces use fixed seeds and normal-play overrides to probe branching in turn flow.
- Current action model stores one route tuple on actions; there is no separate candidate-vs-actual
  route field. `distinct_actual_routes` therefore uses the same route tuple as `distinct_routes`.
