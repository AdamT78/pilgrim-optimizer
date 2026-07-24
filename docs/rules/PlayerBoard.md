# Player Board (v2.7 Sandbox Scope)

## Implemented now

This milestone adds the remaining player-board workforce foundations and special-activity
infrastructure for the headless sandbox:

- Village / Serf pool tracking
- Abbey / Acolyte pool tracking
- City and Duty-tile acolyte tracking via the existing mancala vector
- Allocation full-turn action (Abbey <-> Special Activities and Special -> Special)
- Six per-player Special Activity spaces and their currently supported bonuses

No road/trade-route/spatial-map placement systems are added here.
Construct building acquisition is supported for market buildings; road/spatial Construct effects
remain deferred.

## Player-board workforce areas

Per player, workforce is currently represented as:

- `workforce.village` (Village Serfs)
- `workforce.abbey` (Abbey Acolytes)
- `workforce.mancala` (City + Duty tile acolytes)
- `workforce.committed` (roads, shrines, market ports, pilgrimage sites, alms table)
- `special_activities` (occupied Special Activity spaces)

For verbose state output and conservation checks, total workforce is interpreted as:

- mancala/city/duty acolytes
- + village serfs
- + abbey acolytes
- + occupied special-activity acolytes
- + committed acolytes

### Starting setup defaults

In `configs/setups/basic_mancala_sandbox.json`, default real-table setup now includes:

- Village Serfs: 8
- Abbey Acolytes: 3

Small sandbox scenarios may still override these counts explicitly (for focused tests).

## Ordination duty workforce flow

Ordination now uses the existing player-board workforce pools directly:

- `ordain`: pay 1 wheat, move 1 worker `village -> abbey`
- `mission`: pay 1 wheat, move 1 acolyte `abbey -> city` (mancala position `city`)

One Ordination action can include multiple ordered steps up to duty value. Steps are validated
and applied sequentially, so a newly ordained acolyte can be missioned in the same action
(`ordain; mission`).

## Player-board slots and Give Alms donation

Per-player shared slot state is tracked as:

- `active_buildings`
- `donated_buildings`
- `cardinal_favor_tiles`

Donation under Give Alms moves exactly one building from active to donated:

- donated building abilities are considered unavailable for future use
- donated buildings still consume board slots
- slot usage is preserved by donation (`active -1`, `donated +1`)

## Construct building acquisition and slots

Construct now supports acquiring exactly one building from `building_market`:

- cost is stone equal to the building level
- acquired building is added to `active_buildings`
- building is removed from market immediately
- this consumes one shared player-board slot at once

Slot limit remains shared across:

- `active_buildings`
- `donated_buildings`
- `cardinal_favor_tiles`

## Allocation action

Allocation is modelled as a full-turn duty resolution (`action: allocation`) when a selected
duty tile is assigned the `allocation` category in the scenario duty layout.

Allocation move primitives:

- `abbey -> <special_activity>`
- `<special_activity> -> abbey`
- `<special_activity> -> <special_activity>`

Rules enforced now:

- Allocation does **not** move acolytes to City.
- One Allocation action contains `1..duty_value` moves.
- Each move must be legal at the moment it is taken (step-by-step state updates).
- Special Activity destination must be below its current capacity.
- Special Activity source must be occupied.
- A Special Activity cannot move to itself.
- action emits one `ALLOCATION` event per move, in move order.

Notes:

- Duty-tile recall still runs after allocation, consistent with other non-tithe duty resolutions.
- Allocation is no longer tied to a fixed physical position; duty layout controls where it appears.
- A move between two Special Activities counts as one Allocation move.

## Special Activities

Per player, each space tracks occupied acolyte count:

- `fields`
- `road_engineer`
- `stone_mason`
- `alms_house`
- `engraver`
- `vestry`

The old `grain` name has been replaced by canonical ID `fields` (player-facing: Fields).

Capacity rule by Chapter House status:

- without active Chapter House: max 1 acolyte per Special Activity space
- with active Chapter House: max 2 acolytes per Special Activity space
- second-acolyte occupancy is still placed by Allocation (Chapter House does not move acolytes)
- donated Chapter House does not apply

Helpers are available for occupied/available activity queries and counts.

For a central Duty-action enhancement index (Special Activities plus known building effects), see
`docs/rules/DutyEnhancements.md`.

## Implemented Special Activity effects

### Fields

- produce has two explicit mutually exclusive actions: `produce_wheat` and `produce_stone`
- Produce duty value is applied to exactly one chosen resource and cannot be split.
- Fields is a production bonus only; it does not increase Produce duty value.
- Fields adds `+1 wheat` per occupied Fields acolyte to `produce_wheat` only
- Fields does not affect `produce_stone`
- emits `SPECIAL_ACTIVITY_BONUS`

### Stone Mason

- Stone Mason is a production bonus only; it does not increase Produce duty value.
- Stone Mason adds `+1 stone` per occupied Stone Mason acolyte to `produce_stone` only
- Stone Mason does not affect `produce_wheat`
- emits `SPECIAL_ACTIVITY_BONUS`

### Engraver

- adds `+1 silver` per occupied Engraver acolyte to `clerical_silversmith`
- emits `SPECIAL_ACTIVITY_BONUS`

### Vestry

- adds `+1 piety` per occupied Vestry acolyte to `clerical_devotion`
- emits `SPECIAL_ACTIVITY_BONUS`

### Alms House

- optional Give Alms bonus path
- raises Give Alms duty value by `+N` when the extra payment is made
- `N` is capped by occupied Alms House acolytes (`N<=1` normally, `N<=2` with active Chapter House)
- each `+1` requires extra payment of `1 silver` or `1 wheat`
- extra payment is encoded in the action fields and validated
- emits `SPECIAL_ACTIVITY_BONUS`
- does not enhance `give_alms_donate_building` in the current milestone

### Road Engineer

- when taking `build_roads`, Road Engineer raises effective Duty Value by `+N`
- `N` equals occupied Road Engineer acolytes (`N<=1` normally, `N<=2` with active Chapter House)
- this currently applies only to `build_roads_deferred` scaffold resolution
- no runtime road/bridge/ford/shrine placement is performed in this milestone
- when taking `construct`, Road Engineer does **not** raise duty value
- instead, Construct may include additional deferred roads only if the plan already includes a
  road built via duty value
- extra-road count scales by occupied Road Engineer acolytes (max +2 with active Chapter House)
- this appears as a Construct scaffold plan (`... + road_engineer_extra_road`) plus
  `SPECIAL_ACTIVITY_BONUS`
- no runtime road/bridge placement is performed for Construct in this milestone

## Implemented active-building Duty bonuses

These building bonuses are now implemented in the Duty transition paths:

- Well: `produce_wheat` gains `+1 wheat`
- Quarry: `produce_stone` gains `+1 stone`
- Mint: `clerical_silversmith` gains `+1 silver`
- Chapel: `clerical_devotion` gains `+1 piety`
- Infirmary: true duty-value modifier bonuses:
  - Allocation: `+1 effective Duty Value`
  - Ordination: `+1 effective Duty Value` when the chosen sequence uses an extra paid step
- Chapter House:
  - raises Special Activity per-space capacity from 1 to 2 while active
  - enables Allocation placement of second acolytes on Special Activity spaces
  - makes Special Activity bonus output scale by occupied acolyte count (max 2)

Rules for these bonuses:

- only `active_buildings` apply
- `donated_buildings` do not apply
- bonuses stack with matching Special Activity bonuses
- Infirmary's Ordination bonus does not make any step free; wheat costs still apply per step

## Validation and invariants

Validation now additionally enforces Special Activity structure integrity.

Post-transition invariant checks continue to enforce:

- non-negative resources and workforce counts
- deterministic round/season/game-over state validity
- workforce conservation across transitions
- dummy-acolyte conservation

Verbose invariant output now explicitly reports player workforce totals and mentions
serfs/acolytes conservation scope.

## Deferred

- Mill building effects
- real spatial placement effects for Road Engineer (Build Roads / Construct)
- full player-board systems beyond current sandbox scope
