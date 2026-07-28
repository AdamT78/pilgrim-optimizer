# Buildings (v1.9-v5.4 Sandbox Scope)

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
- `effect_status` (`deferred` or `implemented`)

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
- v3.1a simple bonus actions now consume this helper pattern for single-building hires

## Simple bonus hire wiring (v3.1a)

This milestone wires hire sources into four direct-output building bonuses:

- Well -> `produce_wheat` `+1 wheat`
- Quarry -> `produce_stone` `+1 stone`
- Mint -> `clerical_silversmith` `+1 silver`
- Chapel -> `clerical_devotion` `+1 piety`

These four abilities now resolve from:

- own active building (free)
- live market hire (pay Merchant resource `1` to bank)
- opponent active hire (pay Merchant resource `1` to owner)

Unavailable source cases remain enforced:

- donated building
- not-live market building
- Merchant on taxation (`resource = none`)
- insufficient Merchant resource payment

Notes:

- `BUILDING_HIRED` is emitted for hired sources (before `BUILDING_BONUS`).
- own-active use remains free and emits only `BUILDING_BONUS`.
- direct-output semantics remain unchanged (no effective duty-value inflation for these four).

Important scope boundary:

- Chapter House is still not wired to hire sources.

## Infirmary hire wiring (v3.1b)

Infirmary duty-value bonuses now also resolve through hire sources:

- own active Infirmary -> free
- live market Infirmary -> hire from bank
- opponent active Infirmary -> hire from owner

Allocation behavior:

- Infirmary adds `+1 effective Duty Value` (same cap semantics as own-active behavior)
- hired Infirmary variants are generated only when they use that extra cap
- hired source emits `BUILDING_HIRED` before `BUILDING_BONUS`

Ordination behavior:

- Infirmary adds `+1 effective Duty Value` only when the action actually takes the extra paid step
- the extra Ordination step still costs wheat; Infirmary does not make steps free
- hired extra-step variants are generated only when all costs are jointly affordable:
  - minority silver (if any)
  - Ordination wheat step costs
  - Infirmary hire payment (`1` Merchant resource)

Unavailable source rules remain enforced:

- donated Infirmary
- not-live market Infirmary
- Merchant on Taxation (`resource = none`)
- insufficient hire payment resource

## Mill wheat-cost rule (v3.2)

Mill now applies to:

- `give_alms_paid`
- `ordination`

Mill source resolution follows the existing building-hire source model:

- own active Mill -> free
- live market Mill -> hire from bank
- opponent active Mill -> hire from owner

Wheat waiver rule:

- Mill waives up to the first `2` required wheat from the action's own wheat costs
- formula:
  - `mill_waiver = min(2, required_wheat)`
  - `actual_wheat_spent = max(0, required_wheat - 2)`

Reference table:

- `required 1 -> waived 1 -> spent 0`
- `required 2 -> waived 2 -> spent 0`
- `required 3 -> waived 2 -> spent 1`
- `required 4 -> waived 2 -> spent 2`
- `required 5 -> waived 2 -> spent 3`

```text
Required wheat | Mill waiver | Actual wheat spent
1              | 1           | 0
2              | 2           | 0
3              | 2           | 1
4              | 2           | 2
5              | 2           | 3
```

Scope details:

- waived wheat includes:
  - `give_alms_paid` wheat payment
  - `give_alms_paid` Alms House extra wheat payment
  - Ordination step wheat costs
- not waived:
  - minority silver
  - any silver costs
  - Mill hire payment
  - `give_alms_donate_building`
  - tithe

Event semantics:

- hired Mill emits `BUILDING_HIRED` before `BUILDING_BONUS`
- Mill emits `BUILDING_BONUS` only when wheat is actually waived (`required_wheat > 0`)

## Grain Store wheat/silver conversion (v4.0)

Grain Store now applies as an optional economic modifier attached to a normal full-turn action.

Source resolution follows the existing building-hire source model:

- own active Grain Store -> free
- live market Grain Store -> hire from bank
- opponent active Grain Store -> hire from owner

Conversion rule:

- sell wheat: pay `X` wheat, gain `X` silver
- buy wheat: pay `X` silver, gain `X` wheat
- `X >= 1`
- conversion rate is always `1:1`

Timing:

- if Grain Store is hired, hire payment resolves first
- conversion resolves next
- sowing and selected Duty resolve after conversion
- conversion cannot be used to pay Grain Store's own hire cost

Legal generation behavior:

- normal full-turn actions remain legal
- Grain Store variants are added when source is usable and resources are available after hire:
  - sell variants for amounts `1..available_wheat_after_hire`
  - buy variants for amounts `1..available_silver_after_hire`
- no zero-amount conversion variants are generated

Event semantics before sowing:

- hired source: `BUILDING_HIRED` -> `BUILDING_BONUS` -> conversion `RESOURCE_DELTA` -> `SOWING`
- own active source: `BUILDING_BONUS` -> conversion `RESOURCE_DELTA` -> `SOWING`

## Indulgences piety/silver conversion (v5.0)

Indulgences now applies as an optional economic/piety modifier attached to a normal full-turn action.

Source resolution follows the existing building-hire source model:

- own active Indulgences -> free
- live market Indulgences -> hire from bank
- opponent active Indulgences -> hire from owner

Conversion rule:

- sell piety: pay `X` piety, gain `X` silver
- buy piety: pay `X` silver, gain `X` piety
- `X >= 1`
- conversion rate is always `1:1`

Timing:

- if Indulgences is hired, hire payment resolves first
- conversion resolves next
- sowing and selected Duty resolve after conversion
- conversion cannot be used to pay Indulgences' own hire cost

Piety bounds:

- sell variants: `1..current_piety_after_hire`
- buy variants: `1..min(available_silver_after_hire, piety_track_remaining_space)`
- no buy variants are generated at piety cap
- no sell variants are generated at piety position `0`

Legal generation behavior:

- normal full-turn actions remain legal
- Indulgences variants are added when source is usable and post-hire bounds allow conversion
- no zero-amount conversion variants are generated

Event semantics before sowing:

- hired source: `BUILDING_HIRED` -> `BUILDING_BONUS` -> conversion `RESOURCE_DELTA` -> `SOWING`
- own active source: `BUILDING_BONUS` -> conversion `RESOURCE_DELTA` -> `SOWING`
- conversion deltas include `piety` and `silver` changes explicitly

## Stone Yard stone/silver conversion (v5.1)

Stone Yard now applies as an optional economic/resource modifier attached to a normal full-turn action.

Source resolution follows the existing building-hire source model:

- own active Stone Yard -> free
- live market Stone Yard -> hire from bank
- opponent active Stone Yard -> hire from owner

Conversion rule:

- sell stone: pay `X` stone, gain `X` silver
- buy stone: pay `X` silver, gain `X` stone
- `X >= 1`
- conversion rate is always `1:1`

Timing:

- if Stone Yard is hired, hire payment resolves first
- conversion resolves next
- sowing and selected Duty resolve after conversion
- conversion cannot be used to pay Stone Yard's own hire cost

Resource bounds:

- sell variants: `1..available_stone_after_hire`
- buy variants: `1..available_silver_after_hire`
- stone and silver are never allowed to go below `0`
- silver is uncapped
- stone can exceed `6` during the turn; round-end excess caps still apply later

Legal generation behavior:

- normal full-turn actions remain legal
- Stone Yard variants are added when source is usable and post-hire resources allow conversion
- no zero-amount conversion variants are generated

Event semantics before sowing:

- hired source: `BUILDING_HIRED` -> `BUILDING_BONUS` -> conversion `RESOURCE_DELTA` -> `SOWING`
- own active source: `BUILDING_BONUS` -> conversion `RESOURCE_DELTA` -> `SOWING`
- conversion deltas include `stone` and `silver` changes explicitly

## Brewery wheat-to-silver conversion (v5.2)

Brewery now applies as an optional economic/resource modifier attached to a normal full-turn action.

Source resolution follows the existing building-hire source model:

- own active Brewery -> free
- live market Brewery -> hire from bank
- opponent active Brewery -> hire from owner

Conversion rule:

- sell exactly `1` wheat: gain `2` silver
- conversion is one-direction only (`sell_wheat_for_silver`)
- no buy variants and no variable-amount variants are legal

Timing:

- if Brewery is hired, hire payment resolves first
- conversion resolves next
- sowing and selected Duty resolve after conversion
- conversion cannot be used to pay Brewery's own hire cost

Resource bounds:

- conversion requires at least `1` wheat after any required hire payment
- wheat cannot go below `0`
- silver is uncapped
- round-end wheat caps remain unchanged

Legal generation behavior:

- normal full-turn actions remain legal
- Brewery variants are added when source is usable and post-hire wheat is at least `1`
- each eligible base action gets at most one Brewery variant (`amount = 1`)

Event semantics before sowing:

- hired source: `BUILDING_HIRED` -> `BUILDING_BONUS` -> conversion `RESOURCE_DELTA` -> `SOWING`
- own active source: `BUILDING_BONUS` -> conversion `RESOURCE_DELTA` -> `SOWING`
- Brewery conversion delta is always `wheat -1`, `silver +2`

## Guild merchant advance (v5.3)

Guild now applies as an optional pre-sow Merchant-position modifier attached to a normal full-turn action.

Source resolution follows the existing building-hire source model:

- own active Guild -> free
- live market Guild -> hire from bank
- opponent active Guild -> hire from owner

Merchant movement rule:

- move Merchant exactly one Duty tile clockwise
- movement is player-triggered and optional
- this is not the round-end Merchant phase

Timing:

- if Guild is hired, hire payment resolves first
- Guild Merchant movement resolves next
- sowing and selected Duty resolve after the Merchant move
- Guild movement cannot change the resource required to pay Guild's own hire

Resource and availability behavior:

- own active Guild works even when Merchant resource is `none`
- hired Guild sources are unavailable when Merchant resource is `none`
- hired Guild sources require payment affordability before movement
- donated/not-live Guild remains unavailable

Event semantics before sowing:

- hired source: `BUILDING_HIRED` -> `BUILDING_BONUS` -> `MERCHANT_ADVANCE` -> `SOWING`
- own active source: `BUILDING_BONUS` -> `MERCHANT_ADVANCE` -> `SOWING`
- Guild `MERCHANT_ADVANCE` events include `cause=guild` in event details

Conservative composition scope in this milestone:

- Guild variants are generated only for ordinary full-turn actions
- mixed Guild + other same-turn hire-dependent building modifiers are deferred
  to avoid ambiguous hire-cost ordering on post-Guild Merchant resources

## Pulpit free serf move (v5.4)

Pulpit now applies as an optional pre-sow workforce modifier attached to a normal full-turn action.

Source resolution follows the existing building-hire source model:

- own active Pulpit -> free
- live market Pulpit -> hire from bank
- opponent active Pulpit -> hire from owner

Pulpit rule:

- move exactly `1` serf from Village to Abbey
- wheat cost is always `0` for the Pulpit move itself
- no amount/direction payload is used

Timing:

- if Pulpit is hired, hire payment resolves first
- Pulpit movement resolves next
- sowing and selected Duty resolve after the movement
- Pulpit cannot be used to create a Village/Abbey workforce change before paying its own hire

Infirmary and Ordination distinction:

- Pulpit is independent from Ordination Duty value and step budgets
- Pulpit does not consume Duty Value
- Pulpit does not add Duty Value
- Infirmary cannot increase Pulpit from one free move to two free moves
- when both are present:
  - Pulpit still performs exactly one free Village -> Abbey move
  - Infirmary can still modify the separate Ordination action (extra paid step) as usual

Availability and gating:

- own active Pulpit works even when Merchant resource is `none`
- hired Pulpit sources are unavailable when Merchant resource is `none`
- hired Pulpit sources require payment affordability before movement
- donated/not-live Pulpit remains unavailable
- no Pulpit variant is generated when acting player has `Village serfs = 0` after any hire payment

Event semantics before sowing:

- hired source: `BUILDING_HIRED` -> `BUILDING_BONUS` -> `WORKFORCE_MOVE` -> `SOWING`
- own active source: `BUILDING_BONUS` -> `WORKFORCE_MOVE` -> `SOWING`
- `WORKFORCE_MOVE` reports `amount=1`, `unit=serf`, `from_pool=village`, `to_pool=abbey`, `wheat_paid=0`

## Building turn-modifier registry (v3.3-v3.9)

Five movement/turn-phase buildings are classified in a dedicated metadata registry:

- `kogge`
- `cloisters`
- `dormitory`
- `inquisition`
- `library`

These are tracked in `pilgrim/rules/building_turn_modifiers.py` and documented in
`docs/rules/BuildingTurnModifiers.md`.

Scope in this milestone:

- classification and lookup registry
- runtime wiring now implemented for Kogge sow-route expansion
- runtime wiring now implemented for Cloisters sow-route skip modifier
- runtime wiring now implemented for Dormitory and Inquisition start-turn relocations
- runtime wiring now implemented for Library end-turn relocations
- no generic runtime modifier engine

Category mapping:

- `sow_route_modifier`: Kogge, Cloisters
- `start_turn_relocation`: Dormitory, Inquisition
- `end_turn_relocation`: Library

Status:

- `kogge`, `cloisters`, `dormitory`, `inquisition`, and `library` are now `implemented`

Kogge runtime behavior:

- Kogge adds sow starts `city -> east` and `city -> west` only
- source resolution follows normal building source priority:
  - own active Kogge (free)
  - opponent active hire (pay owner)
  - live market hire (pay bank)
- hired Kogge is unavailable when Merchant resource is `none` (Taxation), insufficient, donated,
  or not live

Cloisters runtime behavior:

- optional sow-route modifier on a normal full-turn action
- pick up `N`, generate candidate placements length `N+1`, omit exactly one City/Duty placement,
  and place on the remaining `N` placements
- skipped location receives no acolyte; selected Duty must be a non-city Duty tile that still
  receives an acolyte after omission
- source resolution follows normal building source priority:
  - own active Cloisters (free)
  - opponent active hire (pay owner)
  - live market hire (pay bank)
- hired Cloisters is unavailable when Merchant resource is `none` (Taxation), insufficient,
  donated, or not live
- event ordering: `BUILDING_HIRED` (if hired) -> `BUILDING_BONUS` -> `SOWING`
- Kogge + Cloisters can combine in one sow action:
  - Kogge enables City-start candidate routes (`city -> east` / `city -> west`)
  - Cloisters applies the `N+1` candidate placement omission model on that Kogge-enabled route
  - both building sources resolve independently
  - if both are hired, total hire payment is two Merchant resources
  - selected Duty must still be an actual non-omitted non-city Duty placement

Dormitory runtime behavior:

- optional start-turn relocation prefix on a normal full-turn action
- moves exactly one acting-player acolyte from a non-city Duty tile to City
- source resolution follows normal building source priority:
  - own active Dormitory (free)
  - opponent active hire (pay owner)
  - live market hire (pay bank)
- hired Dormitory is unavailable when Merchant resource is `none` (Taxation), insufficient,
  donated, or not live
- event ordering: `BUILDING_HIRED` (if hired) -> `BUILDING_BONUS` -> `START_TURN_RELOCATION` ->
  `SOWING`

Inquisition runtime behavior:

- optional start-turn relocation prefix on a normal full-turn action
- moves exactly one acting-player acolyte from City to a non-city Duty tile
- source resolution follows normal building source priority:
  - own active Inquisition (free)
  - opponent active hire (pay owner)
  - live market hire (pay bank)
- hired Inquisition is unavailable when Merchant resource is `none` (Taxation), insufficient,
  donated, or not live
- event ordering: `BUILDING_HIRED` (if hired) -> `BUILDING_BONUS` -> `START_TURN_RELOCATION` ->
  `SOWING`

Library runtime behavior:

- optional end-turn relocation suffix on a normal full-turn action
- moves exactly one acting-player acolyte from City to a non-city Duty tile or Abbey
- source resolution follows normal building source priority:
  - own active Library (free)
  - opponent active hire (pay owner)
  - live market hire (pay bank)
- hired Library is unavailable when Merchant resource is `none` (Taxation), insufficient,
  donated, or not live
- timing: resolves after `ACOLYTE_RECALL` and before `TURN_ADVANCE`
- event ordering: `ACOLYTE_RECALL` -> `BUILDING_HIRED` (if hired) -> `BUILDING_BONUS` ->
  `END_TURN_RELOCATION` -> `TURN_ADVANCE`

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
- `effect_status` must be `deferred` or `implemented`

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
