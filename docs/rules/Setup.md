# Setup Generation (v1.9)

## Scope

Controlled scenario files remain the source of truth for tests and search.

This milestone adds a seeded setup generator that writes deterministic scenario JSON files.
Generation is a convenience tool only; it does not introduce runtime randomization.

## Determinism boundary

Randomization happens only when explicitly running:

`python3 -m pilgrim.cli generate-setup ...`

No setup randomization is performed inside:

- scenario loading
- `legal_actions`
- `apply_action`
- `solve`

Generated files are stable for the same `(player_count, seed)` and can be committed.

## Generated components

For one seed, the generator deterministically creates:

- duty-tile layout permutation across the 8 non-city positions
- tithe-counter placement for 7 non-Taxation duty positions
- 12-building market draw (4 per level)
- dummy acolyte setup by player count
- turn-0 initial state scaffold and setup metadata

## Duty tiles

The 8 duty categories are assigned exactly once each to:

- `north`
- `north_east`
- `east`
- `south_east`
- `south`
- `south_west`
- `west`
- `north_west`

`city` is never a duty tile.

## Tithe counters

Counter pool:

- `stone` x2
- `wheat` x2
- `silver` x2
- `cornucopia` x1

Taxation rule:

- the duty position mapped to category `taxation` has no Tithe counter key in generated output

Cornucopia rule:

- `cornucopia` is a Tithe counter type
- under Taxation Step II it acts as wildcard access to `stone` / `wheat` / `silver`
- `cornucopia` is never gained as a resource itself

Counters are not consumed by Taxation in the current implementation.

## Building market draw

Generator draws from the 24-building catalogue:

- 4 of 8 level-1 buildings
- 4 of 8 level-2 buildings
- 4 of 8 level-3 buildings

Resulting `building_market` always has 12 unique IDs and passes existing validation.

## Dummy acolytes

Generated scenario includes explicit dummy groups:

- 2 players: 3 per group
- 3 players: 2 per group
- 4 players: 0 per group

## Initial state and setup sow

Generated state is turn 0 scaffolding and includes:

- timing at `absolute_turn = 0`, round 1, season 1
- Ship at start position (0 / NW site)
- Merchant at Taxation path position (resource `none`)

Generated metadata marks setup sow as deferred:

- `setup_sow_required: true`
- `setup_sow_implemented: false`

Setup sow is intentionally not implemented in this milestone.

## CLI usage

```bash
python3 -m pilgrim.cli generate-setup --players 2 --seed 123 --output scenarios/generated/setup_2p_seed_123.json
```
