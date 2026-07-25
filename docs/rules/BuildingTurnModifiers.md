# Building Turn Modifiers (v3.7)

## Purpose

`pilgrim/rules/building_turn_modifiers.py` classifies buildings that modify turn phases or sow
movement layers rather than directly modifying one duty output.

This registry remains declarative metadata, but entries can now be marked `implemented`
once explicit runtime wiring exists:

- it does **not** auto-execute generic behavior
- it does **not** add a generic modifier engine
- runtime behavior is implemented explicitly in transition helpers per building

## Why a separate registry

These effects are not simple duty-output bonuses. They affect:

- sow route shape (`during_sow`)
- optional pre-turn relocation (`start_of_turn`)
- optional post-turn relocation (`end_of_turn`)

For this reason they are tracked separately from `DutyEnhancements`.

## Registry shape

Each entry contains:

- `building_key`
- `category`
- `phase`
- `effect`
- `status`
- `notes`

Current categories:

- `sow_route_modifier`
- `start_turn_relocation`
- `end_turn_relocation`

Current phases:

- `during_sow`
- `start_of_turn`
- `end_of_turn`

Current statuses:

- `scaffolded`
- `implemented`
- `deferred_spatial`

## Entries in v3.7

- `kogge`
  - category: `sow_route_modifier`
  - phase: `during_sow`
  - effect: adds city -> east and city -> west sow options
  - status: `implemented`
  - notes: implemented in transition sow-route generation and apply validation/events

- `cloisters`
  - category: `sow_route_modifier`
  - phase: `during_sow`
  - effect: may skip one Duty tile or the city when moving acolytes to Duty actions
  - status: `implemented`
  - notes: implemented as optional sow-route skip modifier using candidate N+1 placements with
    one omitted placement

- `dormitory`
  - category: `start_turn_relocation`
  - phase: `start_of_turn`
  - effect: may return 1 acolyte from any Duty action to City
  - status: `implemented`
  - notes: implemented as optional pre-sow start-turn relocation action prefix

- `inquisition`
  - category: `start_turn_relocation`
  - phase: `start_of_turn`
  - effect: may move 1 acolyte from City to any Duty
  - status: `implemented`
  - notes: implemented as optional pre-sow start-turn relocation action prefix

- `library`
  - category: `end_turn_relocation`
  - phase: `end_of_turn`
  - effect: may move 1 acolyte from City directly to a Duty action or back to Abbey
  - status: `implemented`
  - notes: implemented as optional post-turn end-turn relocation action suffix

Start-turn relocation runtime semantics:

- prefixes a normal full-turn action (not a standalone turn)
- resolves before sowing
- supports own active, live market hire, and opponent active hire sources
- hired variants emit `BUILDING_HIRED` then `BUILDING_BONUS`, then `START_TURN_RELOCATION`, then `SOWING`
- own-active variants omit `BUILDING_HIRED`
- hired variants are unavailable when source is donated, not live, merchant resource is `none`, or
  hire payment is unaffordable

Sow-route skip (Cloisters) runtime semantics:

- suffixes a normal full-turn sow route (not a standalone turn)
- pick up `N`, generate candidate placements length `N+1`, omit exactly one City/Duty placement,
  then place on the remaining `N`
- skipped location receives no acolyte
- selected Duty must still be a non-city Duty tile with at least one non-omitted placement
- supports own active, live market hire, and opponent active hire sources
- hired variants emit `BUILDING_HIRED` then `BUILDING_BONUS`, then `SOWING`
- own-active variants omit `BUILDING_HIRED`
- hired variants are unavailable when source is donated, not live, merchant resource is `none`, or
  hire payment is unaffordable
- Kogge + Cloisters in one combined sow route is intentionally deferred in this milestone

End-turn relocation (Library) runtime semantics:

- suffixes a normal full-turn action (not a standalone turn)
- source location is City; target is one non-city Duty tile or Abbey
- resolves after `ACOLYTE_RECALL` and before `TURN_ADVANCE`
- supports own active, live market hire, and opponent active hire sources
- hired variants emit `BUILDING_HIRED` then `BUILDING_BONUS`, then `END_TURN_RELOCATION`
- own-active variants omit `BUILDING_HIRED`
- hired variants are unavailable when source is donated, not live, merchant resource is `none`, or
  hire payment is unaffordable

Scaffolded entries remaining: none

## Action-shape examples

Implemented examples:

- `start: dormitory east -> city | turn: sow city -> north -> north_east | action: produce_wheat`
- `start: inquisition city -> west | hire building: inquisition from market | turn: sow city -> north | action: produce_wheat`
- `turn: sow north -> east -> south_east | skip north_east with cloisters | selected duty: east (build_roads) | action: build_roads_deferred`
- `turn: sow east -> north | skip city with cloisters | selected duty: north (produce) | action: produce_wheat | hire building: cloisters from player_two`
- `turn: sow city -> north | selected duty: north (produce) | action: produce_wheat | end: library city -> west`
- `turn: sow city -> north | selected duty: north (produce) | action: produce_wheat | end: library city -> abbey`
