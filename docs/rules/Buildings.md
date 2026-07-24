# Buildings (v1.9 Sandbox Scope)

## Implemented now

This milestone adds deterministic building data and board-slot state, plus the
`give_alms_donate_building` action under Give Alms.

- static 24-building catalogue in `configs/buildings.json`
- per-game 12-building market shape (4 per level)
- deterministic scenario market fallback (no random draws in engine/search)
- player-board slot occupancy state
- Give Alms `give_alms_donate_building` option (move one active building to donated, +1 Alms row)
- slot-capacity validation (shared building + Cardinal favor spaces)

## Catalogue structure

The catalogue contains 24 unique building definitions:

- 8 level-1 buildings
- 8 level-2 buildings
- 8 level-3 buildings

Each definition includes:

- stable snake_case `id`
- display `name`
- `level`
- `stone_cost`
- `donation_vp`
- `effect_status` (currently `deferred`)

### Cost and donation VP rules

- level 1: `stone_cost = 1`, `donation_vp = 2`
- level 2: `stone_cost = 2`, `donation_vp = 4`
- level 3: `stone_cost = 3`, `donation_vp = 6`

## Per-game building market

Each game uses exactly 12 buildings:

- 4 level 1
- 4 level 2
- 4 level 3

Scenario state may provide an explicit `building_market` list of 12 ids.

If `building_market` is omitted, loader applies a deterministic fallback:

- first 4 level-1 ids from catalogue order
- first 4 level-2 ids from catalogue order
- first 4 level-3 ids from catalogue order

This keeps scenario loading and search deterministic; no random market draw happens inside
the rules engine.

Seeded setup generation can now produce randomized-but-deterministic market draws at file
generation time (`generate-setup`), still preserving deterministic runtime behavior once the
scenario is written.

## Building availability timeline (v2.9)

Selected buildings now also carry deterministic live-round metadata:

- `initial_state.building_availability` maps `building_id -> live_round`
- live rounds are constrained to `2..26`
- a building is considered live when:
  - `current_round >= live_round`

Backward-compatible scenario loading behavior:

- if `building_availability` is omitted, each selected market building defaults to live round `2`

Generated setup scenarios now always include explicit `building_availability` entries using the
seeded local RNG.

Current runtime use:

- display/explainability (`apply --verbose` / `solve --verbose`)
- validation
- Construct purchase gating

Construct note:

- Construct can buy from `building_market` only when a target building is live
- future/non-live market buildings are not legal Construct purchase targets yet
- building hiring (bank or other players) remains deferred

## Building hire infrastructure (v3.0)

This milestone adds source/cost/payment infrastructure for future hired building abilities.

Potential ability sources:

- own active building (`active_buildings`) -> free use
- live market building (`building_market` + live round reached) -> hire from bank
- opponent-owned active building -> hire from that owner
- donated building -> unavailable

Hire cost rule:

- exactly `1` resource of Merchant's current resource type

Payment destination:

- live market hire -> bank
- opponent active hire -> owning player
- own active -> no payment

Merchant none rule:

- Taxation Duty tile has no Tithe resource, so Merchant resource is `none` there
- own active building remains usable for free
- hired building sources are unavailable while Merchant resource is `none`

Per-turn hire limit rule (infrastructure helper scope):

- a given building may be hired at most once during one player turn
- multiple different buildings may each be hired once during the same turn
- v3.0 provides pure helper/context support for this rule
- runtime duty actions are not yet wired to consume this helper

Important scope boundary:

- existing building bonuses (Well/Quarry/Mint/Chapel/Infirmary/Chapter House) are still wired
  from own active buildings only in current duty transitions
- this milestone does not yet auto-wire hired sources into those bonuses

## Player-board slots

Each player has shared slot occupancy state:

- `active_buildings`
- `donated_buildings`
- `cardinal_favor_tiles`

These six shared spaces are part of the broader player-board model (see
`docs/rules/PlayerBoard.md`), alongside Village/Abbey workforce and Special Activities.

Slot usage:

`used = len(active_buildings) + len(donated_buildings) + cardinal_favor_tiles`

Capacity:

- shared slot limit = `6`

Important:

- donated buildings still consume slots
- Cardinal favor tiles consume slots

## Give Alms building donation option

Give Alms now has a deterministic donation action:

- `action: give_alms_donate_building | building: <building_id>`

When resolved:

- exactly one building moves from `active_buildings` to `donated_buildings`
- Alms advances by exactly one row
- threshold rewards still apply if a row is crossed
- building donation VP is added from catalogue metadata:
  - level 1 -> 2 VP
  - level 2 -> 4 VP
  - level 3 -> 6 VP
- donated buildings remain on the player board and still consume slots

Current scope constraints:

- no chained "second Give Alms payment" after donation (majority extra step is forfeited)
- Alms House bonus applies only to paid `give_alms_paid`, not `give_alms_donate_building`
- this does **not** introduce general-purpose building buy/hire/donate systems

## Validation rules

Catalogue validation enforces:

- exactly 24 entries
- exactly 8 per level
- level set is only {1,2,3}
- stone cost equals level
- donation VP is 2/4/6 by level
- unique ids and names
- all `effect_status = "deferred"` for now

Market validation enforces:

- exactly 12 ids
- no duplicates
- all ids exist in catalogue
- level mix is exactly 4/4/4
- every building currently in `building_market` has a `building_availability` entry

Building availability validation enforces:

- every availability key is a valid building id from the catalogue
- every availability key refers to a selected building currently present in game state
  (market or already owned)
- each live round is an integer in `2..26`
- no duplicate availability keys

Player-board slot validation enforces:

- non-negative Cardinal favor tile count
- no duplicate ids within active or donated lists
- no overlap between active and donated ids for same player
- all listed ids exist in catalogue
- used slots cannot exceed 6

## Deferred in later milestones

- building purchase/hire actions
- Confession Box and all other building effects
- Cardinal favor gain logic
- trade-route/trail/building-system interactions
