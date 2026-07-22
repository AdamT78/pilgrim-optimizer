# Merchant (v0.8 Sandbox Scope)

## Implemented scope

The sandbox now tracks Merchant position and exposes reusable Merchant resource context.

Implemented items:

- Merchant path config loaded from `configs/merchant.json`
- Merchant duty lookup from current position
- Merchant resource lookup from current duty
- Merchant advancement after each full turn (configurable)
- `MERCHANT_ADVANCE` transition event

Not implemented in this milestone:

- building systems
- building hiring payments
- trade-route systems
- trade-route income resolution

## Merchant path

Merchant position is an index into config `path`.

Current sandbox path:

`taxation -> produce -> clerical -> alms -> build -> clerical -> (wrap)`

Path wrapping is deterministic:

`next_position = (position + 1) % len(path)`

## Resource lookup

Resource context is read from `resource_by_duty`.

Example mapping:

- `produce -> wheat`
- `clerical -> silver`
- `alms -> wheat`
- `build -> stone`
- `taxation -> None`

At `taxation`, Merchant resource is intentionally `None` (shown as `none` in CLI output).

## Advancement timing

Merchant advancement is integrated into full-turn transition flow:

1. Apply full-turn action
2. Recall acolytes when applicable
3. Advance active player/timing (`TURN_ADVANCE`)
4. Advance Merchant (`MERCHANT_ADVANCE`)
5. Resolve round/season boundary events
6. Validate invariants

This ordering is designed for readable debug traces and deterministic replay.

## Future hooks

The rules layer exposes placeholders:

- `building_hire_payment_resource(...)`
- `trade_route_income_resource(...)`

Both currently return `current_merchant_resource(...)` and are intended for future systems.
