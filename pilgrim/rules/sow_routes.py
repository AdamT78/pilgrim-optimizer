"""Pure helper utilities for sow-route generation and modifier validation."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable

from pilgrim.model.config import BoardConfig
from pilgrim.rules.mancala import generate_routes


@dataclass(frozen=True, slots=True)
class SowRouteVariant:
    """One deterministic sow-route variant with optional omitted placement."""

    route: tuple[int, ...]
    omitted_location: int | None = None


def normal_sow_routes(
    *,
    origin: int,
    picked_up: int,
    board: BoardConfig,
) -> tuple[tuple[int, ...], ...]:
    """Return normal non-modified sow routes for one origin."""
    if picked_up <= 0:
        return ()
    return tuple(generate_routes(origin, picked_up, board))


@lru_cache(maxsize=32)
def _board_with_kogge_city_spokes(board: BoardConfig) -> BoardConfig:
    """Board graph with Kogge's City-spoke reversals applied.

    Kogge is a graph modifier, not a route-shape exception: while active, City spokes are passable
    both ways. Only those spokes change; ring direction stays as-is.
    """
    city = board.index_for_name("city")
    north = board.index_for_name("north")
    east = board.index_for_name("east")
    south = board.index_for_name("south")
    west = board.index_for_name("west")

    edges = [tuple(neighbors) for neighbors in board.edges]

    def add_edge(origin: int, destination: int) -> None:
        if destination in edges[origin]:
            return
        edges[origin] = (*edges[origin], destination)

    add_edge(city, east)
    add_edge(city, west)
    add_edge(north, city)
    add_edge(south, city)

    return BoardConfig(positions=board.positions, edges=tuple(edges))


def kogge_sow_routes(
    *,
    origin: int,
    picked_up: int,
    board: BoardConfig,
) -> tuple[tuple[int, ...], ...]:
    """Return Kogge-enabled routes for one origin on the Kogge-augmented graph."""
    if picked_up <= 0:
        return ()
    return tuple(generate_routes(origin, picked_up, _board_with_kogge_city_spokes(board)))


def cloisters_candidate_placements(
    *,
    origin: int,
    picked_up: int,
    board: BoardConfig,
) -> tuple[tuple[int, ...], ...]:
    """Return Cloisters candidate placement routes of length N+1."""
    if picked_up <= 0:
        return ()
    return tuple(generate_routes(origin, picked_up + 1, board))


def cloisters_candidate_omissions(
    *,
    origin: int,
    candidate_placements: tuple[int, ...],
) -> tuple[tuple[int, int], ...]:
    """Return omission candidates as (index, location)."""
    omissions: list[tuple[int, int]] = []
    for omitted_index, omitted_location in enumerate(candidate_placements):
        omissions.append((omitted_index, omitted_location))
    return tuple(omissions)


def valid_cloisters_omissions(
    *,
    origin: int,
    candidate_placements: tuple[int, ...],
    board: BoardConfig,
) -> tuple[tuple[int, int], ...]:
    """Return valid Cloisters omissions constrained to City or non-city Duty tiles."""
    allowed_locations = _allowed_cloisters_omission_locations(board)
    return tuple(
        (omitted_index, omitted_location)
        for omitted_index, omitted_location in cloisters_candidate_omissions(
            origin=origin,
            candidate_placements=candidate_placements,
        )
        if omitted_location in allowed_locations
    )


def cloisters_actual_placements_after_omission(
    candidate_placements: tuple[int, ...],
    *,
    omitted_index: int,
) -> tuple[int, ...]:
    """Return actual placements after omitting one candidate index."""
    if omitted_index < 0 or omitted_index >= len(candidate_placements):
        raise ValueError("Cloisters omitted index is out of bounds.")
    return (
        *candidate_placements[:omitted_index],
        *candidate_placements[omitted_index + 1 :],
    )


def selected_duty_is_actual_placement(
    actual_placements: tuple[int, ...],
    *,
    selected_duty: int,
) -> bool:
    """Return whether selected duty appears in actual placements."""
    return any(position == selected_duty for position in actual_placements)


def route_variant_key(variant: SowRouteVariant) -> tuple[tuple[int, ...], int | None]:
    """Return deterministic key for route-variant deduplication."""
    return (variant.route, variant.omitted_location)


def dedupe_sow_route_variants(
    variants: Iterable[SowRouteVariant],
) -> tuple[SowRouteVariant, ...]:
    """Dedupe equivalent route variants while preserving first-seen order."""
    deduped: dict[tuple[tuple[int, ...], int | None], SowRouteVariant] = {}
    for variant in variants:
        key = route_variant_key(variant)
        if key in deduped:
            continue
        deduped[key] = variant
    return tuple(deduped.values())


def cloisters_route_variants(
    *,
    origin: int,
    picked_up: int,
    board: BoardConfig,
) -> tuple[SowRouteVariant, ...]:
    """Return Cloisters actual routes with one omitted placement, deduped."""
    if picked_up <= 0:
        return ()
    variants: list[SowRouteVariant] = []
    for candidate_route in cloisters_candidate_placements(
        origin=origin,
        picked_up=picked_up,
        board=board,
    ):
        for omitted_index, omitted_location in cloisters_candidate_omissions(
            origin=origin,
            candidate_placements=candidate_route,
        ):
            variants.append(
                SowRouteVariant(
                    route=cloisters_actual_placements_after_omission(
                        candidate_route,
                        omitted_index=omitted_index,
                    ),
                    omitted_location=omitted_location,
                )
            )
    return dedupe_sow_route_variants(variants)


def kogge_cloisters_candidate_placements(
    *,
    origin: int,
    picked_up: int,
    board: BoardConfig,
) -> tuple[tuple[int, ...], ...]:
    """Return Kogge-enabled candidate placements of length N+1 for Cloisters omission."""
    if picked_up <= 0:
        return ()
    return kogge_sow_routes(
        origin=origin,
        picked_up=picked_up + 1,
        board=board,
    )


def combined_kogge_cloisters_route_variants(
    *,
    origin: int,
    picked_up: int,
    board: BoardConfig,
) -> tuple[SowRouteVariant, ...]:
    """Return combined Kogge+Cloisters actual routes with one omitted placement."""
    if picked_up <= 0:
        return ()
    allowed_locations = _allowed_cloisters_omission_locations(board)
    variants: list[SowRouteVariant] = []
    for candidate_route in kogge_cloisters_candidate_placements(
        origin=origin,
        picked_up=picked_up,
        board=board,
    ):
        for omitted_index, omitted_location in enumerate(candidate_route):
            if omitted_location not in allowed_locations:
                continue
            variants.append(
                SowRouteVariant(
                    route=cloisters_actual_placements_after_omission(
                        candidate_route,
                        omitted_index=omitted_index,
                    ),
                    omitted_location=omitted_location,
                )
            )
    return dedupe_sow_route_variants(variants)


def sow_vector_from_route(
    vector: tuple[int, ...],
    *,
    origin: int,
    route: tuple[int, ...],
) -> tuple[int, ...]:
    """Apply deterministic sowing by directly placing along one route."""
    if origin < 0 or origin >= len(vector):
        raise ValueError(f"Invalid source position: {origin}")
    picked_up = vector[origin]
    if picked_up <= 0:
        raise ValueError("Sowing source must contain at least one acolyte.")
    if len(route) != picked_up:
        raise ValueError("Route length must equal number of picked-up acolytes.")

    updated = list(vector)
    updated[origin] = 0
    for position in route:
        if position < 0 or position >= len(vector):
            raise ValueError(f"Invalid route position: {position}")
        updated[position] += 1
    return tuple(updated)


def sow_vector_with_optional_city_kogge(
    vector: tuple[int, ...],
    *,
    origin: int,
    route: tuple[int, ...],
    board: BoardConfig,
    allows_kogge_city_spokes: bool,
    cloisters_omitted_location: int | None = None,
    cloisters_with_kogge: bool = False,
) -> tuple[int, ...]:
    """Apply sowing while validating optional Kogge or Cloisters route semantics."""
    sowed_vector = sow_vector_from_route(
        vector,
        origin=origin,
        route=route,
    )
    picked_up = vector[origin]

    if cloisters_omitted_location is not None:
        if cloisters_with_kogge:
            if not is_legal_route_with_kogge_and_cloisters_skip(
                origin=origin,
                route=route,
                board=board,
                omitted_location=cloisters_omitted_location,
            ):
                raise ValueError("Route is not legal for combined Kogge+Cloisters modifier.")
        elif allows_kogge_city_spokes and route_requires_kogge(
            origin=origin,
            route=route,
            board=board,
        ):
            if not is_legal_route_with_kogge_and_cloisters_skip(
                origin=origin,
                route=route,
                board=board,
                omitted_location=cloisters_omitted_location,
            ):
                raise ValueError("Route is not legal for combined Kogge+Cloisters modifier.")
        elif not is_legal_route_with_cloisters_skip(
            origin=origin,
            route=route,
            board=board,
            omitted_location=cloisters_omitted_location,
        ):
            raise ValueError("Route is not legal for Cloisters skip-route modifier.")
        return sowed_vector

    if not is_legal_route_with_optional_city_kogge(
        origin,
        route,
        board=board,
        allows_kogge_city_spokes=allows_kogge_city_spokes,
    ):
        raise ValueError("Route is not legal for the board graph.")

    if len(route) != picked_up:
        raise ValueError("Route length must equal number of picked-up acolytes.")
    return sowed_vector


def is_legal_route_with_optional_city_kogge(
    origin: int,
    route: tuple[int, ...],
    *,
    board: BoardConfig,
    allows_kogge_city_spokes: bool,
) -> bool:
    """Validate route connectivity with optional Kogge-reversed City spokes."""
    route_board = _board_with_kogge_city_spokes(board) if allows_kogge_city_spokes else board
    current = origin
    for next_position in route:
        if next_position not in route_board.neighbors(current):
            return False
        current = next_position
    return True


def is_legal_route_with_cloisters_skip(
    *,
    origin: int,
    route: tuple[int, ...],
    board: BoardConfig,
    omitted_location: int,
) -> bool:
    """Validate that one omitted location can yield the provided actual route."""
    if omitted_location not in _allowed_cloisters_omission_locations(board):
        return False

    candidate_length = len(route) + 1
    for candidate_route in generate_routes(origin, candidate_length, board):
        for omitted_index, candidate_location in valid_cloisters_omissions(
            origin=origin,
            candidate_placements=candidate_route,
            board=board,
        ):
            if candidate_location != omitted_location:
                continue
            actual_route = cloisters_actual_placements_after_omission(
                candidate_route,
                omitted_index=omitted_index,
            )
            if actual_route == route:
                return True
    return False


def is_legal_route_with_kogge_and_cloisters_skip(
    *,
    origin: int,
    route: tuple[int, ...],
    board: BoardConfig,
    omitted_location: int,
) -> bool:
    """Validate combined Kogge+Cloisters candidate route with one Cloisters omission."""
    if omitted_location not in _allowed_cloisters_omission_locations(board):
        return False

    for candidate_route in kogge_cloisters_candidate_placements(
        origin=origin,
        picked_up=len(route),
        board=board,
    ):
        for omitted_index, candidate_location in valid_cloisters_omissions(
            origin=origin,
            candidate_placements=candidate_route,
            board=board,
        ):
            if candidate_location != omitted_location:
                continue
            actual_route = cloisters_actual_placements_after_omission(
                candidate_route,
                omitted_index=omitted_index,
            )
            if actual_route == route:
                return True
    return False


def route_requires_kogge(
    *,
    origin: int,
    route: tuple[int, ...],
    board: BoardConfig,
) -> bool:
    """Return whether route requires Kogge's reversed City spokes."""
    if not route:
        return False
    if is_legal_route_with_optional_city_kogge(
        origin,
        route,
        board=board,
        allows_kogge_city_spokes=False,
    ):
        return False
    return is_legal_route_with_optional_city_kogge(
        origin,
        route,
        board=board,
        allows_kogge_city_spokes=True,
    )


def _allowed_cloisters_omission_locations(board: BoardConfig) -> frozenset[int]:
    return frozenset(
        (
            board.index_for_name("city"),
            board.index_for_name("north"),
            board.index_for_name("north_east"),
            board.index_for_name("east"),
            board.index_for_name("south_east"),
            board.index_for_name("south"),
            board.index_for_name("south_west"),
            board.index_for_name("west"),
            board.index_for_name("north_west"),
        )
    )


__all__ = [
    "SowRouteVariant",
    "cloisters_actual_placements_after_omission",
    "cloisters_candidate_omissions",
    "cloisters_candidate_placements",
    "cloisters_route_variants",
    "combined_kogge_cloisters_route_variants",
    "dedupe_sow_route_variants",
    "is_legal_route_with_kogge_and_cloisters_skip",
    "is_legal_route_with_cloisters_skip",
    "is_legal_route_with_optional_city_kogge",
    "kogge_cloisters_candidate_placements",
    "kogge_sow_routes",
    "normal_sow_routes",
    "route_requires_kogge",
    "route_variant_key",
    "selected_duty_is_actual_placement",
    "sow_vector_from_route",
    "sow_vector_with_optional_city_kogge",
    "valid_cloisters_omissions",
]
