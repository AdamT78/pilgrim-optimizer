# Building Status and Branching Audit (v4.2)

## Purpose

This audit is a deterministic, reporting-only snapshot for:

- current building implementation status (best-effort from available metadata + runtime registries)
- legal-action branching counts for representative scenarios
- short guidance for lower-risk next building candidates

It does **not** change gameplay behavior, legal action generation, action IDs, summaries, event
wording, or apply-time semantics.

## Run

From repository root:

```bash
python3 tools/audits/building_status_branching_audit.py
```

## Report sections

- `Building Status Audit`
  - Groups buildings by audit statuses (`implemented`, `partial`, `deferred`, etc.)
  - Sorts building names alphabetically within each status group
- `Safe Next Candidates`
  - Lightweight guidance for sequencing future building work
- `Branching Count Audit`
  - Legal-action totals and simple flags for representative scenarios
  - Includes a small optional breakdown (normal, movement-modifier, Grain Store conversion, hired,
    combined route modifier)

## Determinism

- No timestamps are printed.
- Scenario rows follow a fixed configured scenario list order.
- Building rows are sorted alphabetically by display name within status groups.

## Known limitations

- `configs/buildings.json` currently has coarse `effect_status` metadata.
- Per-building tags such as `blocked_by_roads_spatial` / `blocked_by_final_scoring` are not yet
  machine-encoded in the catalogue.
- The audit therefore uses best-effort runtime signals from existing registries and reports
  unresolved cases as deferred/needs confirmation rather than inventing unsupported metadata.
