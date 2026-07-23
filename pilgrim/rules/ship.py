"""Abstract ship-marker helpers for round-end timing."""

from __future__ import annotations

from pilgrim.model.config import ShipConfig


def advance_ship_position(position: int, config: ShipConfig) -> int:
    """Advance ship marker once along configured abstract path."""
    return config.advance(position)


def is_pilgrimage_site(position: int, config: ShipConfig) -> bool:
    """Return True when ship marker is at any pilgrimage site."""
    return config.is_pilgrimage_site(position)


def is_nw_pilgrimage_site(position: int, config: ShipConfig) -> bool:
    """Return True when ship marker is at NW pilgrimage site."""
    return config.is_nw_site(position)
