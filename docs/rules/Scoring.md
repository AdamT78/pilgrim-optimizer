# Official Score Sheet (v5.10)

## Purpose

This document defines the current **official** score sheet derived from `GameState`.

Core rule:

- score is **derived** from current state when needed
- score is **not** stored as mutable running state on `GameState`

Use:

- end-game final scoring
- in-progress scoring snapshot
- CLI score-sheet output
- tests

Important distinction:

- official score sheet is separate from sandbox/search evaluation
- this does not change solve/search objective

## API

Rules helper:

`score_breakdown(state, player, config) -> ScoreBreakdown`

All real players:

`score_all_players(state, config) -> dict[PlayerId, ScoreBreakdown]`

## Implemented categories

### Acolytes in scoring locations

`1 VP` per acolyte in:

- Abbey
- City
- Duty tiles

Current model detail:

- City + Duty tiles are represented by the player's Mancala vector
- score uses `workforce.abbey + workforce.mancala_total`

Not counted here:

- Special Activities
- Alms table
- Roads (committed)
- Shrines (committed)
- Market Ports (committed)
- Pilgrimage Sites (committed)

Alms-table rule:

- acolytes on Alms table do **not** also score 1 VP each
- they score only through Alms-table VP lookup

### Piety track VP

Score uses real player piety position and piety-track VP mapping from config.

- current track range in config: `-5 VP` to `+9 VP`
- Confession Box temporary `+2` effective piety is not persisted and is not scored

### Alms table VP

Score uses configured Alms-table VP lookup from committed Alms-table acolytes:

- `0 -> 0 VP`
- `1 -> 5 VP`
- `2 -> 11 VP`
- `3 -> 18 VP`
- `4 -> 26 VP`

### Donated buildings VP

Only donated/flipped buildings score:

- level 1: `2 VP`
- level 2: `4 VP`
- level 3: `6 VP`

Active/unflipped buildings do not score.

### Resources VP

Resources counted:

- wheat
- stone
- silver

Formula:

`resources_vp = (wheat + stone + silver) // 3`

## Implemented total

Implemented total includes only implemented categories:

`acolytes_vp + piety_vp + alms_vp + donated_buildings_vp + resources_vp`

## Deferred categories

These are explicitly excluded from current implemented total:

- Pilgrim Trails
- Pilgrimage Sites
- Cardinal Favours
- Road / Shrine / Market Port placement scoring

## CLI

Use:

```bash
python3 -m pilgrim.cli score scenarios/<scenario>.json
```

The command prints one score sheet per real player plus deferred categories.
# Scoring

Current search evaluation uses a sandbox-only `EvaluationBreakdown`:

- victory points (placeholder field on player state)
- piety track VP
- Alms-table VP
- resource total (`stone + silver + wheat`)

Current sandbox formula:

`victory_points + piety_track_vp + alms_table_vp + resource_total`

This is not final Pilgrim scoring and exists only to support deterministic search/debugging in the current milestone.

Deferred full-scoring components include:

- Pilgrim trails and pilgrimage-site systems
- Building and trade-route scoring
- Cardinal/bonus systems
- Remaining acolyte and endgame conversions
- Final tie-break rules
