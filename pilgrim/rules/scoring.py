"""Official score-sheet helpers derived from current GameState."""

from __future__ import annotations

from dataclasses import dataclass

from pilgrim.model.config import GameConfig
from pilgrim.model.enums import PlayerId
from pilgrim.model.state import GameState
from pilgrim.rules.alms import score_alms_table
from pilgrim.rules.piety import score_piety

DEFERRED_SCORING_CATEGORIES: tuple[str, ...] = (
    "Pilgrim Trails",
    "Pilgrimage Sites",
    "Cardinal Favours",
    "Road / Shrine / Market Port placement scoring",
)


@dataclass(frozen=True, slots=True)
class ScoreBreakdown:
    """Official implemented scoring categories for one player."""

    player: PlayerId
    acolytes_vp: int
    piety_vp: int
    alms_vp: int
    donated_buildings_vp: int
    resources_vp: int
    implemented_total: int
    deferred_categories: tuple[str, ...] = DEFERRED_SCORING_CATEGORIES


def score_breakdown(state: GameState, player: PlayerId, config: GameConfig) -> ScoreBreakdown:
    """Return the current official scoring snapshot for one player."""
    player_state = state.player_state(player)
    workforce = player_state.workforce
    acolytes_vp = workforce.mancala_total + workforce.abbey
    piety_vp = score_piety(player_state.piety, config.piety)
    alms_vp = score_alms_table(workforce.committed.alms_table, config.alms)
    donated_buildings_vp = _score_donated_buildings(
        player_state.player_board_slots.donated_buildings,
        config,
    )
    resource_total = (
        player_state.resources.wheat
        + player_state.resources.stone
        + player_state.resources.silver
    )
    resources_vp = resource_total // 3
    implemented_total = (
        acolytes_vp
        + piety_vp
        + alms_vp
        + donated_buildings_vp
        + resources_vp
    )
    return ScoreBreakdown(
        player=player,
        acolytes_vp=acolytes_vp,
        piety_vp=piety_vp,
        alms_vp=alms_vp,
        donated_buildings_vp=donated_buildings_vp,
        resources_vp=resources_vp,
        implemented_total=implemented_total,
    )


def score_all_players(state: GameState, config: GameConfig) -> dict[PlayerId, ScoreBreakdown]:
    """Return score snapshots for all real players in fixed player-id order."""
    return {
        player: score_breakdown(state, player, config)
        for player in (PlayerId(index) for index in range(state.player_count))
    }


def _score_donated_buildings(
    donated_buildings: tuple[str, ...],
    config: GameConfig,
) -> int:
    return sum(
        config.buildings.definition_by_id(building_id).donation_vp
        for building_id in donated_buildings
    )
