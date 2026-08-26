# Building Status and Branching Audit

## Purpose

This audit is a deterministic, reporting-only snapshot for:

- current building implementation status (best-effort from available metadata + runtime registries)
- legal-action and committed-turn-step branching for representative scenarios
- buildings whose effects remain unimplemented, with the status reason already measured by the
  audit

It does **not** change gameplay behavior, legal action generation, action IDs, summaries, event
wording, or apply-time semantics.

## Run

From repository root:

```bash
python3 tools/audits/building_status_branching_audit.py
```

## Report sections

- `Building Status Audit`
  - Groups buildings by audit statuses (`implemented`, `partial`, `deferred`, and `unknown`)
  - Sorts building names alphabetically within each status group
- `Unimplemented Buildings`
  - Lists only currently deferred buildings and their measured status reason; the section is
    omitted when none remain
- `Branching Count Audit`
  - Reports each scenario's legal-action count, directly offered pre-resolution turn-step count,
    reachable optional step-sequence count, distinct reachable-state count, and both the
    `Act×Seq` and `Act×State` products.
  - `PostWindow` says whether the supplied scenario starts in a measured post-resolution window.
    `UNMEASURED` prevents a zero pre-resolution step count from being read as a zero after every
    legal action: post-resolution availability is action-dependent and not collapsed into a
    scenario-wide total.
  - `StepSeq` includes the empty sequence: choosing a full-turn action without committing a
    building is one reachable sequence.
  - `States` includes the distinct immutable engine states reached by those same prefixes. It
    leaves every commit-order sequence in `StepSeq`, while showing the resulting-state merges a
    memoising search could make.
  - Counts directly offered committed steps by the behavior now carried there: hires,
    conversions, Grain Store conversions, and relocations. Movement and combined Kogge+Cloisters
    remain action metrics because those route choices still live on `FullTurnAction`.
  - The fixed 10,000-prefix walk cap applies to `StepSeq`, `States`, and both products. Every
    bounded figure is reported as a lower bound (`>=…`); the audit keeps the first eight
    deterministic dropped prefixes and prints how many additional prefixes were not shown.

The configured corpus contains the eleven focused building fixtures, all five
`scenarios/playtest/*.json` positions, and the deep round-eighteen fixture.

## Determinism

- No timestamps are printed.
- Scenario rows follow a fixed configured scenario list order.
- Building rows are sorted alphabetically by display name within status groups.
- Turn-step sequence walks and displayed dropped prefixes are ordered by stable turn-step ID.

## Known limitations

- `configs/buildings.json` currently has coarse `effect_status` metadata.
- Classification limitation: this audit does not infer blocked-by-spatial or
  blocked-by-final-scoring per building from machine-readable metadata because those tags are not
  yet encoded in the catalogue.
- The audit therefore uses best-effort runtime signals from existing registries and reports
  unresolved cases as deferred or unknown rather than inventing unsupported metadata.
- No scenario in the configured corpus starts in a post-resolution position. `PostWindow` is
  therefore `UNMEASURED` for every row, including Library; its post-resolution relocation remains
  unmeasured by this scenario-level audit.
- When a sequence walk truncates, its `StepSeq`/`States` ratio is not meaningful: depth-first
  traversal leaves collapsing commit orders in unreached parts of the tree, so `conversions_2p`'s
  roughly 1.7× ratio at 10,000 and 4.3× at 50,000 (still unfinished) understates deduplication.
- `Act×Seq` is a reporting product of the action count at the observed position and all reachable
  committed-step prefixes. A future step-aware search would still need to regenerate legal
  actions after each prefix, so this is a comparable branching diagnostic rather than a runtime
  search-node count. `Act×State` uses the same observed action count and reports only the state
  merge potential at the measured position.
