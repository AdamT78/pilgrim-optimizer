# Building Turn Modifiers (v3.4)

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

## Entries in v3.4

- `kogge`
  - category: `sow_route_modifier`
  - phase: `during_sow`
  - effect: adds city -> east and city -> west sow options
  - status: `implemented`
  - notes: implemented in transition sow-route generation and apply validation/events

The following entries remain `scaffolded`:
- `cloisters`
  - category: `sow_route_modifier`
  - phase: `during_sow`
  - effect: may skip one Duty tile or the city when moving acolytes to Duty actions
  - notes: skip-route logic deferred
- `dormitory`
  - category: `start_turn_relocation`
  - phase: `start_of_turn`
  - effect: may return 1 acolyte from any Duty action to City
  - notes: optional pre-turn action composition deferred
- `inquisition`
  - category: `start_turn_relocation`
  - phase: `start_of_turn`
  - effect: may move 1 acolyte from City to any Duty
  - notes: optional pre-turn action composition deferred
- `library`
  - category: `end_turn_relocation`
  - phase: `end_of_turn`
  - effect: may move 1 acolyte from City directly to a Duty action or back to Abbey
  - notes: optional post-turn action composition deferred

## Future action-shape examples (not implemented yet)

These examples are documentation only:

- `start: dormitory north -> city | turn: sow city -> south | action: give_alms_paid`
- `start: inquisition city -> east | turn: sow city -> north | action: produce_wheat`
- `turn: sow city -> north | action: produce_wheat | end: library city -> abbey`

No such composite action model is implemented in this milestone.
