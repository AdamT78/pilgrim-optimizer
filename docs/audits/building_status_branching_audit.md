# Building Status and Branching Audit

## Purpose

This audit is a deterministic, reporting-only snapshot for:

- current building implementation status (best-effort from available metadata + runtime registries)
- legal-action and committed-turn-step branching for representative scenarios
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
  - Reports each scenario's legal-action count, directly offered pre-resolution turn-step count,
    reachable optional step-sequence count, and `Act×Seq` product.
  - `PostWindow` says whether the supplied scenario starts in a measured post-resolution window.
    `UNMEASURED` prevents a zero pre-resolution step count from being read as a zero after every
    legal action: post-resolution availability is action-dependent and not collapsed into a
    scenario-wide total.
  - `StepSeq` includes the empty sequence: choosing a full-turn action without committing a
    building is one reachable sequence.
  - Counts directly offered committed steps by the behavior now carried there: hires,
    conversions, Grain Store conversions, and relocations. Movement and combined Kogge+Cloisters
    remain action metrics because those route choices still live on `FullTurnAction`.
  - The fixed 10,000-prefix sequence walk cap is reported as a lower bound (`>=…`), keeps the
    first eight deterministic dropped prefixes, and prints how many additional prefixes were not
    shown; it never silently reports a partial walk as complete.

## Determinism

- No timestamps are printed.
- Scenario rows follow a fixed configured scenario list order.
- Building rows are sorted alphabetically by display name within status groups.
- Turn-step sequence walks and displayed dropped prefixes are ordered by stable turn-step ID.

## Known limitations

- `configs/buildings.json` currently has coarse `effect_status` metadata.
- Per-building tags such as `blocked_by_roads_spatial` / `blocked_by_final_scoring` are not yet
  machine-encoded in the catalogue.
- The audit therefore uses best-effort runtime signals from existing registries and reports
  unresolved cases as deferred/needs confirmation rather than inventing unsupported metadata.
- `Act×Seq` is a reporting product of the action count at the observed position and all reachable
  committed-step prefixes. A future step-aware search would still need to regenerate legal
  actions after each prefix, so this is a comparable branching diagnostic rather than a runtime
  search-node count.
