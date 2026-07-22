# Workforce

## Implemented Scope (v0.4)

The sandbox now tracks each player's workforce across explicit pools:

- `mancala` (9-position vector)
- `village`
- `abbey`
- `committed.roads`
- `committed.shrines`
- `committed.market_ports`
- `committed.pilgrimage_sites`
- `committed.alms_table`

## Conservation Principle

- Full-turn transitions must conserve total acolytes per player.
- Current sandbox actions (sow, duty, tithe) only move acolytes within `mancala`.
- `duty` recall moves acolytes from selected duty position back to `city` (still within `mancala`).
- `tithe` does not recall acolytes.

## Deferred Systems

- Alms-table activity rules.
- Trail and road assignment rules.
- Shrine commitment rules and costs.
- Market port commitment and trade interactions.
- Pilgrimage Site commitment and costs.
- Special activities that move acolytes between village/abbey/committed pools.
