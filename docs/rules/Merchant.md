# Merchant (v0.8 + v1.8 Taxation Clarification)

## Implemented scope

The sandbox now tracks Merchant position and exposes reusable Merchant resource context.

Implemented items:

- Merchant path config loaded from `configs/merchant.json`
- Merchant duty lookup from current position
- Merchant resource lookup from current duty
- Merchant advancement once per round during round-end processing
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

Merchant advancement is integrated into **round-end** transition flow:

1. Resolve the current full turn and emit `TURN_ADVANCE`
2. If round does not end: no Merchant movement
3. If round ends: run Excess/Ship/season-end steps
4. Advance Merchant once (`MERCHANT_ADVANCE`) if game has not ended
5. Run trade-route placeholder and start-player selection
6. Finish round/season advancement and invariants

Merchant starts at `taxation` (`merchant_position = 0`) in default setups/scenarios.

## Future hooks

The rules layer exposes placeholders:

- `building_hire_payment_resource(...)`
- `trade_route_income_resource(...)`

Both currently return `current_merchant_resource(...)` and are intended for future systems.

## Taxation interaction

Taxation is now an implemented duty action, but Merchant resource context remains unchanged:

- Merchant can stand on the `taxation` duty tile.
- At `taxation`, current Merchant resource is still `None` (`none` in CLI output).
- Future systems should continue to treat this as:
  - no trade-route income resource when Merchant is on Taxation
  - no building-hire payment resource when Merchant is on Taxation

Trade routes and building hire are still out of scope for the current milestone; the helper
hooks preserve the `None` context for forward compatibility.
