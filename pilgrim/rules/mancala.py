"""Mancala movement and sowing helpers for Ruleset A."""

from __future__ import annotations

from pilgrim.model.config import BoardConfig


def generate_routes(
    start: int,
    route_length: int,
    board: BoardConfig,
) -> tuple[tuple[int, ...], ...]:
    """Generate all legal directed routes with an exact number of steps."""
    if route_length < 0:
        raise ValueError("Route length cannot be negative.")
    if route_length == 0:
        return ((),)

    routes: list[tuple[int, ...]] = []

    def dfs(position: int, remaining: int, path: tuple[int, ...]) -> None:
        if remaining == 0:
            routes.append(path)
            return
        for neighbor in board.neighbors(position):
            dfs(neighbor, remaining - 1, path + (neighbor,))

    dfs(start, route_length, ())
    return tuple(routes)


def is_legal_route(start: int, route: tuple[int, ...], board: BoardConfig) -> bool:
    """Check route connectivity against the directed board graph."""
    current = start
    for next_position in route:
        if next_position not in board.neighbors(current):
            return False
        current = next_position
    return True


def sow_vector(
    vector: tuple[int, ...],
    source: int,
    route: tuple[int, ...],
    board: BoardConfig,
) -> tuple[int, ...]:
    """Apply deterministic sowing to one player's acolyte vector."""
    if source < 0 or source >= len(vector):
        raise ValueError(f"Invalid source position: {source}")
    picked_up = vector[source]
    if picked_up <= 0:
        raise ValueError("Sowing source must contain at least one acolyte.")
    if len(route) != picked_up:
        raise ValueError("Route length must equal number of picked-up acolytes.")
    if not is_legal_route(source, route, board):
        raise ValueError("Route is not legal for the board graph.")

    updated = list(vector)
    updated[source] = 0
    for position in route:
        updated[position] += 1
    return tuple(updated)


def occupied_positions(vector: tuple[int, ...]) -> tuple[int, ...]:
    """Return all occupied positions in ascending index order."""
    return tuple(index for index, count in enumerate(vector) if count > 0)
