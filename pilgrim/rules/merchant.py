"""Merchant position and resource-context helpers."""

from __future__ import annotations

from pilgrim.model.config import MerchantConfig
from pilgrim.model.state import GameState


def merchant_position_name(position: int, config: MerchantConfig) -> str:
    """Return the duty name at a Merchant path position."""
    if position < 0:
        raise ValueError("Merchant position cannot be negative.")
    return config.duty_at(position)


def advance_merchant_position(position: int, config: MerchantConfig) -> int:
    """Advance Merchant one step forward on the circular path."""
    if position < 0:
        raise ValueError("Merchant position cannot be negative.")
    return (position + 1) % len(config.path)


def current_merchant_duty(state: GameState, config: MerchantConfig) -> str:
    """Return the current Merchant duty name from game state."""
    return merchant_position_name(state.merchant_position, config)


def current_merchant_resource(state: GameState, config: MerchantConfig) -> str | None:
    """Return current Merchant resource context, or None at taxation."""
    duty = current_merchant_duty(state, config)
    return config.resource_for_duty(duty)


def building_hire_payment_resource(state: GameState, config: MerchantConfig) -> str | None:
    """Future hook: building hire payment resource depends on Merchant context."""
    return current_merchant_resource(state, config)


def trade_route_income_resource(state: GameState, config: MerchantConfig) -> str | None:
    """Future hook: trade-route income resource depends on Merchant context."""
    return current_merchant_resource(state, config)
