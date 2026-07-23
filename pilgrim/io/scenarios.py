"""JSON-driven scenario loading for deterministic engine runs."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pilgrim.model.buildings import BuildingsConfig, PlayerBoardSlots
from pilgrim.model.config import GameConfig, game_config_from_dict
from pilgrim.model.dummy import DummyAcolyteGroups
from pilgrim.model.enums import PlayerId, TurnPhase
from pilgrim.model.resources import Resources
from pilgrim.model.special_activities import SPECIAL_ACTIVITY_IDS, SpecialActivities
from pilgrim.model.state import GameState, PlayerState
from pilgrim.model.timing import TimingState
from pilgrim.model.workforce import MANCALA_POSITION_COUNT, CommittedAcolytes, Workforce
from pilgrim.opponents import OpponentModel, opponent_model_from_dict
from pilgrim.rules.buildings import default_building_market, validate_building_state
from pilgrim.rules.dummy import seed_dummy_groups


@dataclass(frozen=True, slots=True)
class LoadedScenario:
    """Loaded scenario bundle used by CLI and tests."""

    scenario_id: str
    state: GameState
    config: GameConfig
    root_player_id: PlayerId
    opponent_model: OpponentModel


def load_scenario(path: str | Path) -> LoadedScenario:
    """Load scenario + setup + config JSON into typed models."""
    scenario_path = Path(path).resolve()
    scenario_raw = _read_json(scenario_path)
    merged = _merge_setup_into_scenario(scenario_raw, scenario_path)

    board_path = _resolve_path(str(merged["board_file"]), scenario_path)
    duties_path = _resolve_path(str(merged["duties_file"]), scenario_path)
    piety_file = str(merged.get("piety_file", "configs/piety.json"))
    piety_path = _resolve_path(piety_file, scenario_path)
    alms_file = str(merged.get("alms_file", "configs/alms.json"))
    alms_path = _resolve_path(alms_file, scenario_path)
    timing_file = str(merged.get("timing_file", "configs/timing.json"))
    timing_path = _resolve_path(timing_file, scenario_path)
    merchant_file = str(merged.get("merchant_file", "configs/merchant.json"))
    merchant_path = _resolve_path(merchant_file, scenario_path)
    ship_file = str(merged.get("ship_file", "configs/ship.json"))
    ship_path = _resolve_path(ship_file, scenario_path)
    buildings_file = merged.get("buildings_file")
    buildings_path = (
        _resolve_path(str(buildings_file), scenario_path)
        if buildings_file is not None
        else _default_buildings_path()
    )
    board_raw = _read_json(board_path)
    duties_raw = _read_json(duties_path)
    piety_raw = _read_json(piety_path)
    alms_raw = _read_json(alms_path)
    timing_raw = _read_json(timing_path)
    merchant_raw = _read_json(merchant_path)
    ship_raw = _read_json(ship_path)
    buildings_raw = _read_json(buildings_path)

    config = game_config_from_dict(
        board_raw=board_raw,
        duties_raw=duties_raw,
        piety_raw=piety_raw,
        alms_raw=alms_raw,
        timing_raw=timing_raw,
        merchant_raw=merchant_raw,
        ship_raw=ship_raw,
        buildings_raw=buildings_raw,
        duty_tiles_raw=_duty_tiles_from_dict(merged.get("duty_tiles")),
        tithe_counters_raw=_tithe_counters_from_dict(merged.get("tithe_counters")),
    )
    table_player_count = _player_count_from_dict(merged)
    state = _game_state_from_dict(
        merged["initial_state"],
        merchant_path_length=len(config.merchant.path),
        ship_start_position=config.ship.start_position,
        ship_path_length=config.ship.path_length,
        buildings_config=config.buildings,
        table_player_count=table_player_count,
    )
    validate_building_state(state, config)
    scenario_id = str(merged.get("scenario_id", merged.get("name", scenario_path.stem)))
    root_player_id = _root_player_from_dict(merged, default_player=state.active_player)
    opponent_model = _opponent_model_from_dict(merged)
    return LoadedScenario(
        scenario_id=scenario_id,
        state=state,
        config=config,
        root_player_id=root_player_id,
        opponent_model=opponent_model,
    )


def _merge_setup_into_scenario(
    scenario_raw: Mapping[str, Any],
    scenario_path: Path,
) -> dict[str, Any]:
    if "setup_file" not in scenario_raw:
        return dict(scenario_raw)
    setup_path = _resolve_path(str(scenario_raw["setup_file"]), scenario_path)
    setup_raw = _read_json(setup_path)
    merged = _deep_merge(dict(setup_raw), dict(scenario_raw))
    return merged


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(dict(merged[key]), dict(value))
        else:
            merged[key] = value
    return merged


def _game_state_from_dict(
    raw: Mapping[str, Any],
    *,
    merchant_path_length: int,
    ship_start_position: int,
    ship_path_length: int,
    buildings_config: BuildingsConfig,
    table_player_count: int,
) -> GameState:
    players_raw = raw["players"]
    acolytes_raw = raw.get("acolytes")
    player_one = _player_state_from_dict(
        players_raw["player_one"],
        legacy_mancala=_legacy_mancala_for_player(acolytes_raw, "player_one"),
    )
    player_two = _player_state_from_dict(
        players_raw["player_two"],
        legacy_mancala=_legacy_mancala_for_player(acolytes_raw, "player_two"),
    )
    timing = _timing_state_from_dict(raw)
    merchant_position = _merchant_position_from_dict(raw)
    ship_position = int(raw.get("ship_position", ship_start_position))
    completed_rounds = int(raw.get("completed_rounds", max(0, timing.round_number - 1)))
    start_player = _start_player_from_dict(raw)
    if start_player is None:
        start_player = PlayerId.from_string(str(raw["active_player"]))
    game_over = bool(raw.get("game_over", False))
    dummy_acolytes = _dummy_acolytes_from_dict(raw, table_player_count=table_player_count)
    building_market = _building_market_from_dict(raw, buildings_config)
    if merchant_position >= merchant_path_length:
        raise ValueError(
            "Scenario merchant_position must be within Merchant path bounds: "
            f"{merchant_position} not in [0, {merchant_path_length - 1}]."
        )
    if ship_position < 0 or ship_position >= ship_path_length:
        raise ValueError(
            "Scenario ship_position must be within Ship path bounds: "
            f"{ship_position} not in [0, {ship_path_length - 1}]."
        )
    return GameState(
        active_player=PlayerId.from_string(str(raw["active_player"])),
        start_player=start_player,
        phase=TurnPhase.from_string(str(raw["phase"])),
        players=(player_one, player_two),
        timing=timing,
        table_player_count=table_player_count,
        dummy_acolytes=dummy_acolytes,
        merchant_position=merchant_position,
        ship_position=ship_position,
        completed_rounds=completed_rounds,
        game_over=game_over,
        building_market=building_market,
    )


def _player_state_from_dict(
    raw: Mapping[str, Any],
    *,
    legacy_mancala: tuple[int, ...] | None,
) -> PlayerState:
    resources_raw = raw["resources"]
    if "workforce" in raw:
        workforce = _workforce_from_dict(raw["workforce"])
    elif legacy_mancala is not None:
        workforce = Workforce(mancala=legacy_mancala)
    else:
        workforce = Workforce(mancala=(0,) * MANCALA_POSITION_COUNT)
    return PlayerState(
        resources=Resources(
            stone=int(resources_raw.get("stone", 0)),
            silver=int(resources_raw.get("silver", 0)),
            wheat=int(resources_raw.get("wheat", 0)),
        ),
        workforce=workforce,
        piety=int(raw.get("piety", 0)),
        alms_position=int(raw.get("alms_position", 0)),
        victory_points=int(raw.get("victory_points", 0)),
        special_activities=_special_activities_from_dict(raw.get("special_activities")),
        player_board_slots=_player_board_slots_from_dict(raw.get("player_board_slots")),
    )


def _workforce_from_dict(raw: Mapping[str, Any]) -> Workforce:
    committed_raw = raw.get("committed", {})
    if not isinstance(committed_raw, Mapping):
        raise ValueError("workforce.committed must be an object.")
    mancala_raw = raw.get("mancala", [0] * MANCALA_POSITION_COUNT)
    if not isinstance(mancala_raw, list):
        raise ValueError("workforce.mancala must be a list.")
    return Workforce(
        mancala=tuple(int(value) for value in mancala_raw),
        village=int(raw.get("village", 0)),
        abbey=int(raw.get("abbey", 0)),
        committed=CommittedAcolytes(
            roads=int(committed_raw.get("roads", 0)),
            shrines=int(committed_raw.get("shrines", 0)),
            market_ports=int(committed_raw.get("market_ports", 0)),
            pilgrimage_sites=int(committed_raw.get("pilgrimage_sites", 0)),
            alms_table=int(committed_raw.get("alms_table", 0)),
        ),
    )


def _legacy_mancala_for_player(
    acolytes_raw: Any,
    player_key: str,
) -> tuple[int, ...] | None:
    if not isinstance(acolytes_raw, Mapping):
        return None
    vector = acolytes_raw.get(player_key)
    if not isinstance(vector, list):
        return None
    return tuple(int(value) for value in vector)


def _root_player_from_dict(raw: Mapping[str, Any], *, default_player: PlayerId) -> PlayerId:
    """Parse explicit root player; fallback to initial active player."""
    root_player_raw = raw.get("root_player_id")
    if root_player_raw is None:
        return default_player
    if isinstance(root_player_raw, str):
        text = root_player_raw.strip()
        try:
            return PlayerId.from_string(text)
        except ValueError:
            try:
                return PlayerId(int(text))
            except ValueError as exc:
                raise ValueError(f"Unknown root_player_id: {root_player_raw}") from exc
    return PlayerId(int(root_player_raw))


def _timing_state_from_dict(raw: Mapping[str, Any]) -> TimingState:
    timing_raw = raw.get("timing")
    if isinstance(timing_raw, Mapping):
        return TimingState(
            absolute_turn=int(timing_raw.get("absolute_turn", raw.get("turn", 0))),
            round_number=int(timing_raw.get("round_number", 1)),
            season_number=int(timing_raw.get("season_number", 1)),
            turn_in_round=int(timing_raw.get("turn_in_round", 0)),
        )
    return TimingState(
        absolute_turn=int(raw.get("turn", 0)),
        round_number=1,
        season_number=1,
        turn_in_round=0,
    )


def _merchant_position_from_dict(raw: Mapping[str, Any]) -> int:
    merchant_raw = raw.get("merchant")
    if isinstance(merchant_raw, Mapping):
        return int(merchant_raw.get("position", 0))
    return int(raw.get("merchant_position", 0))


def _start_player_from_dict(raw: Mapping[str, Any]) -> PlayerId | None:
    start_player_raw = raw.get("start_player_id")
    if start_player_raw is None:
        return None
    if isinstance(start_player_raw, int):
        return PlayerId(start_player_raw)
    return PlayerId.from_string(str(start_player_raw))


def _dummy_acolytes_from_dict(
    raw: Mapping[str, Any],
    *,
    table_player_count: int,
) -> DummyAcolyteGroups:
    dummy_raw = raw.get("dummy_acolytes")
    if dummy_raw is None:
        return seed_dummy_groups(table_player_count)
    if not isinstance(dummy_raw, Mapping):
        raise ValueError("dummy_acolytes must be an object with north_group/south_group.")

    north_group_raw = dummy_raw.get("north_group")
    south_group_raw = dummy_raw.get("south_group")
    if not isinstance(north_group_raw, list) or not isinstance(south_group_raw, list):
        raise ValueError("dummy_acolytes.north_group and south_group must be lists.")
    return DummyAcolyteGroups(
        north_group=tuple(int(value) for value in north_group_raw),
        south_group=tuple(int(value) for value in south_group_raw),
    )


def _building_market_from_dict(
    raw: Mapping[str, Any],
    buildings_config: BuildingsConfig,
) -> tuple[str, ...]:
    market_raw = raw.get("building_market")
    if market_raw is None:
        return default_building_market(buildings_config)
    if not isinstance(market_raw, list):
        raise ValueError("building_market must be a list of building ids.")
    return tuple(str(value) for value in market_raw)


def _player_board_slots_from_dict(raw: Any) -> PlayerBoardSlots:
    if raw is None:
        return PlayerBoardSlots()
    if not isinstance(raw, Mapping):
        raise ValueError("player_board_slots must be an object.")
    active_raw = raw.get("active_buildings", [])
    donated_raw = raw.get("donated_buildings", [])
    if not isinstance(active_raw, list) or not isinstance(donated_raw, list):
        raise ValueError("active_buildings and donated_buildings must be lists.")
    return PlayerBoardSlots(
        active_buildings=tuple(str(value) for value in active_raw),
        donated_buildings=tuple(str(value) for value in donated_raw),
        cardinal_favor_tiles=int(raw.get("cardinal_favor_tiles", 0)),
    )


def _special_activities_from_dict(raw: Any) -> SpecialActivities:
    if raw is None:
        return SpecialActivities()
    if isinstance(raw, list):
        flags = {str(item): True for item in raw}
    elif isinstance(raw, Mapping):
        flags: dict[str, bool] = {}
        for key, value in raw.items():
            if not isinstance(value, bool):
                raise ValueError(
                    f"special_activities.{key} must be true/false, got {type(value).__name__}."
                )
            flags[str(key)] = value
    else:
        raise ValueError("special_activities must be an object or list.")
    if "grain" in flags and "fields" not in flags:
        flags["fields"] = bool(flags["grain"])
    elif "grain" in flags and "fields" in flags:
        if bool(flags["grain"]) != bool(flags["fields"]):
            raise ValueError(
                "special_activities.grain alias conflicts with special_activities.fields."
            )
    flags.pop("grain", None)
    unknown_ids = set(flags) - set(SPECIAL_ACTIVITY_IDS)
    if unknown_ids:
        raise ValueError(
            "Unknown special activity id(s): " + ", ".join(sorted(unknown_ids)) + "."
        )
    return SpecialActivities(
        fields=bool(flags.get("fields", False)),
        road_engineer=bool(flags.get("road_engineer", False)),
        stone_mason=bool(flags.get("stone_mason", False)),
        alms_house=bool(flags.get("alms_house", False)),
        engraver=bool(flags.get("engraver", False)),
        vestry=bool(flags.get("vestry", False)),
    )


def _duty_tiles_from_dict(raw: Any) -> Mapping[str, str] | None:
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise ValueError("duty_tiles must be an object mapping positions to categories.")
    return {str(position): str(category) for position, category in raw.items()}


def _tithe_counters_from_dict(raw: Any) -> Mapping[str, Any] | None:
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise ValueError("tithe_counters must be an object mapping positions to resources/null.")
    return {str(position): resource for position, resource in raw.items()}


def _player_count_from_dict(raw: Mapping[str, Any]) -> int:
    player_count_raw = raw.get("player_count")
    if player_count_raw is None:
        return 2
    return int(player_count_raw)


def _opponent_model_from_dict(raw: Mapping[str, Any]) -> OpponentModel:
    opponent_raw = raw.get("opponent_model")
    if opponent_raw is None:
        return opponent_model_from_dict(None)
    if not isinstance(opponent_raw, Mapping):
        raise ValueError("Scenario 'opponent_model' must be an object.")
    return opponent_model_from_dict(opponent_raw)


def _resolve_path(path_value: str, scenario_path: Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    local_candidate = (scenario_path.parent / path).resolve()
    if local_candidate.exists():
        return local_candidate
    return (scenario_path.parent.parent / path).resolve()


def _default_buildings_path() -> Path:
    return (Path(__file__).resolve().parents[2] / "configs" / "buildings.json").resolve()


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return data
