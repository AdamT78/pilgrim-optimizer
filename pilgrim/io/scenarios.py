"""JSON-driven scenario loading for deterministic engine runs."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pilgrim.model.config import GameConfig, game_config_from_dict
from pilgrim.model.enums import PlayerId, TurnPhase
from pilgrim.model.resources import Resources
from pilgrim.model.state import GameState, PlayerState


@dataclass(frozen=True, slots=True)
class LoadedScenario:
    """Loaded scenario bundle used by CLI and tests."""

    scenario_id: str
    state: GameState
    config: GameConfig


def load_scenario(path: str | Path) -> LoadedScenario:
    """Load scenario + setup + config JSON into typed models."""
    scenario_path = Path(path).resolve()
    scenario_raw = _read_json(scenario_path)
    merged = _merge_setup_into_scenario(scenario_raw, scenario_path)

    board_path = _resolve_path(str(merged["board_file"]), scenario_path)
    duties_path = _resolve_path(str(merged["duties_file"]), scenario_path)
    piety_file = str(merged.get("piety_file", "configs/piety.json"))
    piety_path = _resolve_path(piety_file, scenario_path)
    board_raw = _read_json(board_path)
    duties_raw = _read_json(duties_path)
    piety_raw = _read_json(piety_path)

    config = game_config_from_dict(
        board_raw=board_raw,
        duties_raw=duties_raw,
        piety_raw=piety_raw,
    )
    state = _game_state_from_dict(merged["initial_state"])
    scenario_id = str(merged.get("scenario_id", merged.get("name", scenario_path.stem)))
    return LoadedScenario(scenario_id=scenario_id, state=state, config=config)


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


def _game_state_from_dict(raw: Mapping[str, Any]) -> GameState:
    players_raw = raw["players"]
    acolytes_raw = raw["acolytes"]
    player_one = _player_state_from_dict(players_raw["player_one"])
    player_two = _player_state_from_dict(players_raw["player_two"])
    return GameState(
        active_player=PlayerId.from_string(str(raw["active_player"])),
        phase=TurnPhase.from_string(str(raw["phase"])),
        players=(player_one, player_two),
        acolytes=(
            tuple(int(value) for value in acolytes_raw["player_one"]),
            tuple(int(value) for value in acolytes_raw["player_two"]),
        ),
        turn=int(raw.get("turn", 0)),
    )


def _player_state_from_dict(raw: Mapping[str, Any]) -> PlayerState:
    resources_raw = raw["resources"]
    return PlayerState(
        resources=Resources(
            stone=int(resources_raw.get("stone", 0)),
            silver=int(resources_raw.get("silver", 0)),
            wheat=int(resources_raw.get("wheat", 0)),
        ),
        piety=int(raw.get("piety", 0)),
        victory_points=int(raw.get("victory_points", 0)),
    )


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
