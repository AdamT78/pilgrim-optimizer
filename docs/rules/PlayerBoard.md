# Player Board (v1.2 Sandbox Scope)

## Implemented now

This milestone adds the remaining player-board workforce foundations and special-activity
infrastructure for the headless sandbox:

- Village / Serf pool tracking
- Abbey / Acolyte pool tracking
- City and Duty-tile acolyte tracking via the existing mancala vector
- Allocation full-turn action (Abbey -> City or Abbey -> Special Activity)
- Six per-player Special Activity spaces and their currently supported bonuses

No roads, construct, trade-route, spatial-map, or building action systems are added here.

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

## Allocation action

Allocation is modelled as a full-turn duty resolution (`action: allocation`) when a selected
duty tile uses the `allocation` effect.

Current allocation targets:

- `city`
- `special_activity:<id>`

Rules enforced now:

- requires at least 1 abbey acolyte
- exactly 1 acolyte is moved from abbey
- Special Activity target must be empty for that player
- action emits `ALLOCATION` event

Notes:

- Duty-tile recall still runs after allocation, consistent with other non-tithe duty resolutions.

## Special Activities

Per player, each space is either occupied or empty:

- `grain`
- `road_engineer`
- `stone_mason`
- `alms_house`
- `engraver`
- `vestry`

Capacity rule:

- max 1 acolyte per Special Activity space per player

Helpers are available for occupied/available activity queries and counts.

## Implemented Special Activity effects

### Grain

- current produce model is generic `produce` (wheat-focused in sandbox)
- if occupied, Grain adds `+1 wheat` to `produce`
- emits `SPECIAL_ACTIVITY_BONUS`

### Stone Mason

- placeholder hook exists
- no runtime bonus yet because explicit `produce_stone` option is not modelled

### Engraver

- adds `+1 silver` to `clerical_silversmith`
- emits `SPECIAL_ACTIVITY_BONUS`

### Vestry

- adds `+1 piety` to `clerical_devotion`
- emits `SPECIAL_ACTIVITY_BONUS`

### Alms House

- optional Give Alms bonus path
- raises duty value by `+1`
- requires extra payment of exactly `1 silver` or `1 wheat`
- extra payment is encoded in the action fields and validated
- emits `SPECIAL_ACTIVITY_BONUS`

### Road Engineer

- placeholder hook exists only
- no runtime road-related effect in this milestone

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
- explicit produce option split (`produce_grain` vs `produce_stone`)
- road/construct effects for Road Engineer
- full player-board systems beyond current sandbox scope
