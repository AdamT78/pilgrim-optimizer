# Dummy Acolytes (v0.9 Sandbox Scope)

## Implemented scope

The sandbox now supports neutral dummy acolytes for reduced player-count tables.

Implemented in this milestone:

- setup seeding for 2-player and 3-player tables
- no-dummy setup for 4-player tables
- internal split into two dummy groups:
  - `north_group`
  - `south_group`
- dummy inclusion in Duty strength comparison (majority/parity/minority)
- season-end dummy leap-frog movement per group

Dummy acolytes are neutral competition only. They do not have turns, resources, piety, Alms, or VP.

## Clockwise order

Dummy logic uses duty positions only (city is excluded):

`north -> north_east -> east -> south_east -> south -> south_west -> west -> north_west -> north`

## Setup seeding

### 2-player setup

- `north_group`: 3 seeded clockwise from North
- `south_group`: 3 seeded clockwise from South

Result:

- `north_group`: north, north_east, east
- `south_group`: south, south_west, west

### 3-player setup

- `north_group`: 2 seeded clockwise from North
- `south_group`: 2 seeded clockwise from South

Result:

- `north_group`: north, north_east
- `south_group`: south, south_west

### 4-player setup

- no dummy acolytes

## Scenario representation

Scenario state stores dummies as grouped vectors:

```json
"dummy_acolytes": {
  "north_group": [0, 1, 1, 1, 0, 0, 0, 0, 0],
  "south_group": [0, 0, 0, 0, 0, 1, 1, 1, 0]
}
```

If `dummy_acolytes` is omitted, defaults are seeded from top-level `player_count`.

## Setup assumption

Current implementation assumes:

- "clockwise from North" includes North as the first occupied tile
- "clockwise from South" includes South as the first occupied tile

This behavior is centralized in `seed_from_anchor(...)` and can be changed in one place if rule interpretation changes.

## Season-end leap-frog movement

At season end, each group moves once:

- the rearmost acolyte in the group leap-frogs clockwise over the other acolytes in that same group
- it lands on the next duty tile not occupied by that same group

Movement wraps around the duty ring.

Example (2-player default):

- `north_group`: north, north_east, east -> north_east, east, south_east
- `south_group`: south, south_west, west -> south_west, west, north_west

## Duty strength integration

Dummy totals are included as competing counts when determining Duty relation:

- majority: active player strictly greater than highest competing count
- parity: active player equals highest competing count
- minority: active player below highest competing count

Dummy and real-opponent counts are both considered; the highest competing count controls the relation.
