# Duty Tiles (v1.6 Sandbox Scope)

## Core model

The sandbox now separates:

- physical mancala position
- duty category identity

City is **not** a duty tile.

Duty tiles are the 8 non-city positions:

- `north`
- `north_east`
- `east`
- `south_east`
- `south`
- `south_west`
- `west`
- `north_west`

## Duty categories

The category set is fixed and complete:

- `produce`
- `clerical`
- `give_alms`
- `allocation`
- `build_roads`
- `construct`
- `ordination`
- `taxation`

Each category must appear exactly once in a layout.

## Scenario-defined layout

Real Pilgrim randomizes these tiles. For deterministic engine runs, the layout is defined by
scenario JSON:

```json
"duty_tiles": {
  "north": "produce",
  "north_east": "clerical",
  "east": "build_roads",
  "south_east": "construct",
  "south": "give_alms",
  "south_west": "ordination",
  "west": "allocation",
  "north_west": "taxation"
}
```

If omitted, the same mapping above is used as deterministic fallback.

No randomization occurs inside scenario loading, rules transitions, or search.

## Implemented vs deferred categories

Implemented action systems:

- `produce`:
  - `produce_wheat`
  - `produce_stone`
- `clerical`:
  - `clerical_devotion`
  - `clerical_silversmith`
- `give_alms`:
  - `give_alms` (pay silver/wheat)
  - `donate_building` (donate one active building)
- `allocation`

Deferred category systems (valid in layout, no non-tithe action yet):

- `build_roads`
- `construct`
- `ordination`
- `taxation`

## Runtime implications

- Majority/parity/minority is still computed on the selected **physical** duty position.
- Duty value is still derived from the selected position relation.
- Available non-tithe actions come from the selected position's **category**.
- For `produce`, one explicit option is chosen: `produce_wheat` or `produce_stone`.
- Produce duty value cannot be split across resources in one action.
- Produce special-activity bonuses (Fields / Stone Mason) add produced resources and do not
  change duty value.
- For `give_alms`, paid actions still pay silver/wheat equal to effective duty value and move
  that many rows.
- `donate_building` always donates exactly one active building and advances Alms by exactly one
  row.
- On majority `give_alms`, `donate_building` still resolves as one deterministic action; it does
  not chain into a second paid Give Alms step.
- Alms House currently enhances only paid `give_alms`, not `donate_building`.
- For `allocation`, duty value controls how many allocation moves can be sequenced in one
  action (1..duty value) between Abbey and Special Activities.
- Verbose CLI now prints duty layout and shows category in action/event text:
  - `selected duty: north_east (clerical)`
  - `DUTY_RESOLUTION: selected east (build_roads); mode tithe`
