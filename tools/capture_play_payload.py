"""Dump the route-family-facing play payload for every scenario, as a refactor tripwire.

The legal-action and turn-step captures stop at the engine boundary.  The play server reshapes
those results into candidate families, automatic-route masks, and building interaction state, so
an empty diff from either engine capture cannot prove the page payload was preserved.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pilgrim.io.scenarios import load_scenario
from tools import play_server

REPO = Path(__file__).resolve().parents[1]
WINDOWS = ("beginning", "sow", "end")
STEP_FIELDS = ("kind", "value", "family", "auto", "hire_text")


def _capture_value(value: Any) -> Any:
    """Keep the tripwire JSON-only, so its diff has no incidental runtime spellings."""
    if isinstance(value, float):
        raise TypeError("play payload capture cannot contain floats")
    if isinstance(value, (set, frozenset)):
        raise TypeError("play payload capture cannot contain sets")
    if isinstance(value, dict):
        return {str(key): _capture_value(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_capture_value(item) for item in value]
    if value is None or isinstance(value, (bool, int, str)):
        return value
    raise TypeError(f"play payload capture cannot contain {type(value).__name__}")


def _candidate_record(candidate: dict[str, Any]) -> dict[str, Any]:
    """Project candidates onto the route-family fields the page uses to narrow a turn."""
    return {
        "action_id": _capture_value(candidate["action_id"]),
        **(
            {"family": _capture_value(sorted(candidate["family"]))}
            if "family" in candidate
            else {}
        ),
        "steps": [
            {
                field: (
                    sorted(_capture_value(step[field]))
                    if field == "auto"
                    else _capture_value(step[field])
                )
                for field in STEP_FIELDS
                if field in step
            }
            for step in candidate["steps"]
        ],
    }


def _payload_record(scenario: Any) -> dict[str, Any]:
    """Build the portion of the server payload the route-family refactor will rewrite."""
    route_payload = play_server.route_family_payload(scenario.state, scenario.config)
    candidates = route_payload["turn_candidates"]
    building_abilities = route_payload["building_abilities"]
    building_ability_windows = route_payload["building_ability_windows"]
    candidate_records = [_candidate_record(candidate) for candidate in candidates]
    return {
        "auto_family_indexes": _capture_value(
            sorted(route_payload["auto_family_indexes"])
        ),
        "building_abilities": sorted(
            (_capture_value(ability) for ability in building_abilities),
            key=lambda ability: ability["building_id"],
        ),
        "building_ability_windows": {
            window: {
                "abilities": sorted(
                    (
                        _capture_value(ability)
                        for ability in building_ability_windows[window]["abilities"]
                    ),
                    key=lambda ability: ability["building_id"],
                ),
                "turn_steps_offered": _capture_value(
                    building_ability_windows[window]["turn_steps_offered"]
                ),
            }
            for window in WINDOWS
        },
        "families": _capture_value(route_payload["families"]),
        "turn_candidates": sorted(
            candidate_records,
            key=lambda candidate: json.dumps(candidate, sort_keys=True, separators=(",", ":")),
        ),
    }


def main(argv: list[str]) -> int:
    out = Path(argv[0])
    out.mkdir(parents=True, exist_ok=True)
    paths = sorted(
        (
            *REPO.joinpath("scenarios").glob("*.json"),
            *REPO.joinpath("scenarios/playtest").glob("*.json"),
        )
    )
    for path in paths:
        try:
            body = json.dumps(_payload_record(load_scenario(path)), indent=2, sort_keys=True)
        except Exception as exc:  # a scenario that cannot load must fail identically, not silently
            body = f"ERROR\t{type(exc).__name__}\t{exc}"
        out.joinpath(f"{path.stem}.txt").write_text(body + "\n", encoding="utf-8")
    print(f"wrote {len(list(out.glob('*.txt')))} files to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
