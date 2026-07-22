# Piety

## Implemented in v0.2

- Piety is treated as a **track position** (not direct VP).
- Current track bounds are loaded from `configs/piety.json`.
- `clerical_devotion` moves piety by Duty Value, capped at position `12`.
- Piety track VP is resolved by lookup table and used in sandbox evaluation.

## Current Piety Scoring Table

| Position | Track VP |
|---|---|
| 0 | -5 |
| 1 | -4 |
| 2 | -3 |
| 3 | -2 |
| 4 | -1 |
| 5 | 0 |
| 6 | 1 |
| 7 | 2 |
| 8 | 3 |
| 9 | 4 |
| 10 | 5 |
| 11 | 7 |
| 12 | 9 |

## Capped Movement Rule

- If piety gain would move past `12`, position remains at `12`.
- Example: `10 + 2 => 12`, `11 + 2 => 12`, `12 + 1 => 12`.

## Deferred for Later

- Start-player comparison logic tied to piety.
- Alms tie-break interactions.
- Shrine-related piety costs.
- Pilgrimage Site piety costs.
- Full final Pilgrim scoring integration beyond sandbox approximation.
