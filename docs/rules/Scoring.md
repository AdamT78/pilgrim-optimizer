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
