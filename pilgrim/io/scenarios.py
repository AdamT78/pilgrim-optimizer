"""JSON-driven scenario loading for deterministic engine runs."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pilgrim.model.dummy import DummyAcolyteGroups
from pilgrim.model.config import GameConfig, game_config_from_dict
from pilgrim.model.enums import PlayerId, TurnPhase
from pilgrim.model.resources import Resources
from pilgrim.model.state import GameState, PlayerState
from pilgrim.model.timing import TimingState
from pilgrim.model.workforce import MANCALA_POSITION_COUNT, CommittedAcolytes, Workforce
from pilgrim.opponents import OpponentModel, opponent_model_from_dict
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
    board_raw = _read_json(board_path)
    duties_raw = _read_json(duties_path)
    piety_raw = _read_json(piety_path)
    alms_raw = _read_json(alms_path)
    timing_raw = _read_json(timing_path)
    merchant_raw = _read_json(merchant_path)

    config = game_config_from_dict(
        board_raw=board_raw,
        duties_raw=duties_raw,
        piety_raw=piety_raw,
        alms_raw=alms_raw,
        timing_raw=timing_raw,
        merchant_raw=merchant_raw,
    )
    table_player_count = _player_count_from_dict(merged)
    state = _game_state_from_dict(
        merged["initial_state"],
        merchant_path_length=len(config.merchant.path),
        table_player_count=table_player_count,
    )
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
    dummy_acolytes = _dummy_acolytes_from_dict(raw, table_player_count=table_player_count)
    if merchant_position >= merchant_path_length:
        raise ValueError(
            "Scenario merchant_position must be within Merchant path bounds: "
            f"{merchant_position} not in [0, {merchant_path_length - 1}]."
        )
    return GameState(
        active_player=PlayerId.from_string(str(raw["active_player"])),
        phase=TurnPhase.from_string(str(raw["phase"])),
        players=(player_one, player_two),
        timing=timing,
        table_player_count=table_player_count,
        dummy_acolytes=dummy_acolytes,
        merchant_position=merchant_position,
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


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return data
