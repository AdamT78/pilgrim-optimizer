# Multi-Turn Branching Audit (v4.8)

## Purpose

This audit is deterministic, reporting-only diagnostics for branching behavior over scripted
multi-turn traces.

It helps answer:

- how legal-action branching changes over time
- where branching spikes appear
- whether duplicate action IDs appear
- how often key branching contributors (hiring, route modifiers, Grain Store conversion) occur

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
- action-feature counts:
  - `actions_with_hired_building`
  - `actions_with_two_or_more_hired_buildings`
  - `actions_with_route_modifier`
  - `actions_with_kogge`
  - `actions_with_cloisters`
  - `actions_with_kogge_cloisters_combined`
  - `actions_with_start_turn_modifier`
  - `actions_with_end_turn_modifier`
  - `actions_with_building_conversion`
  - `actions_with_grain_store_conversion`
- chosen deterministic action (`selected_action_id` + `selected_action_summary`)

## Determinism

- fixed trace order
- fixed per-trace selector strategy
- deterministic fallback selection by `action_id`
- no timestamps in output

## Limitations

- Trace selectors are intentionally simple and deterministic, not optimal strategy.
- Counts are field-based classification of generated actions; they are useful diagnostics, not
  semantic proof of play quality.
- Generated 3p/4p traces use fixed seeds and normal-play overrides to probe branching in turn flow.

## Scope boundary

- No pruning/search policy changes are implemented here.
- No gameplay/runtime behavior changes are required by this audit.
