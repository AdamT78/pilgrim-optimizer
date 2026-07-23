# Player Board (v1.7 Sandbox Scope)

## Implemented now

This milestone adds the remaining player-board workforce foundations and special-activity
infrastructure for the headless sandbox:

- Village / Serf pool tracking
- Abbey / Acolyte pool tracking
- City and Duty-tile acolyte tracking via the existing mancala vector
- Allocation full-turn action (Abbey <-> Special Activities and Special -> Special)
- Six per-player Special Activity spaces and their currently supported bonuses

No roads, construct, trade-route, or spatial-map systems are added here.
The only building action currently supported is Give Alms `donate_building`.

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
- Special Activity destination must be empty.
- Special Activity source must be occupied.
- A Special Activity cannot move to itself.
- action emits one `ALLOCATION` event per move, in move order.

Notes:

- Duty-tile recall still runs after allocation, consistent with other non-tithe duty resolutions.
- Allocation is no longer tied to a fixed physical position; duty layout controls where it appears.
- A move between two Special Activities counts as one Allocation move.

## Special Activities

Per player, each space is either occupied or empty:

- `fields`
- `road_engineer`
- `stone_mason`
- `alms_house`
- `engraver`
- `vestry`

The old `grain` name has been replaced by canonical ID `fields` (player-facing: Fields).

Capacity rule:

- max 1 acolyte per Special Activity space per player

Helpers are available for occupied/available activity queries and counts.

## Implemented Special Activity effects

### Fields

- produce has two explicit mutually exclusive actions: `produce_wheat` and `produce_stone`
- Produce duty value is applied to exactly one chosen resource and cannot be split.
- Fields is a production bonus only; it does not increase Produce duty value.
- if occupied, Fields adds `+1 wheat` to `produce_wheat` only
- Fields does not affect `produce_stone`
- emits `SPECIAL_ACTIVITY_BONUS`

### Stone Mason

- Stone Mason is a production bonus only; it does not increase Produce duty value.
- if occupied, Stone Mason adds `+1 stone` to `produce_stone` only
- Stone Mason does not affect `produce_wheat`
- emits `SPECIAL_ACTIVITY_BONUS`

### Engraver

- adds `+1 silver` to `clerical_silversmith`
- emits `SPECIAL_ACTIVITY_BONUS`

### Vestry

- adds `+1 piety` to `clerical_devotion`
- emits `SPECIAL_ACTIVITY_BONUS`

### Alms House

- optional Give Alms bonus path
- raises Give Alms duty value by `+1` when the extra payment is made
- requires extra payment of exactly `1 silver` or `1 wheat`
- extra payment is encoded in the action fields and validated
- emits `SPECIAL_ACTIVITY_BONUS`
- does not enhance `donate_building` in the current milestone

### Road Engineer

- when taking `build_roads`, Road Engineer raises effective Duty Value by `+1`
- this currently applies only to `build_roads_deferred` scaffold resolution
- no runtime road/bridge/ford/shrine placement is performed in this milestone
- construct-related Road Engineer behavior remains deferred until Construct road placement exists

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

- Special Activity removal/reallocation
- construct-related Road Engineer placement effects
- full player-board systems beyond current sandbox scope
