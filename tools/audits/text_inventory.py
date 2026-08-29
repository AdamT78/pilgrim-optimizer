"""Deterministic inventory of the words the play surface gets from the engine.

The inventory deliberately calls the text-producing seams over every scenario position and every
enumerated transition.  Looking for quoted literals would include comments and miss dynamic text;
the generated table instead records only words that an actual game position can produce.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from pilgrim.io.event_text import format_event_for_players
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import action_id
from pilgrim.rules.transition import (
    apply_action,
    apply_turn_step,
    legal_actions,
    turn_step_id,
    turn_steps,
)

if __package__:
    from .audit_helpers import project_root
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from audit_helpers import project_root

from tools.play_server import (  # noqa: E402
    _turn_window_prompt,
    building_abilities_payload,
    building_ability_windows_payload,
    turn_candidates,
    turn_steps_payload,
)

OUTPUT_PATH = Path("docs/guides/what_the_game_says.md")
_POSITION_PREVIEW_COUNT = 6


@dataclass(frozen=True, slots=True)
class TextInventoryRow:
    source: str
    situation: str
    text: str
    positions: tuple[str, ...]


def scenario_paths(root: Path | None = None) -> tuple[Path, ...]:
    """Every checked-in position, in the stable order used by the inventory."""
    base = project_root() if root is None else root
    return tuple(sorted((base / "scenarios").rglob("*.json")))


def _position_name(path: Path, root: Path, suffix: str = "initial") -> str:
    """The checked-in scenario that supplied a live initial or derived position."""
    return f"{path.relative_to(root).as_posix()}: {suffix}"


def _record(
    rows: defaultdict[tuple[str, str, str], set[str]],
    *,
    source: str,
    situation: str,
    text: str,
    position: str,
) -> None:
    rows[(source, situation, text)].add(position)


def _record_turn_candidates(
    rows: defaultdict[tuple[str, str, str], set[str]],
    *,
    state: object,
    config: object,
    position: str,
) -> None:
    for candidate in turn_candidates(state, config, include_preview_effects=False):
        for field, text in zip(
            candidate["unresolved"], candidate.get("unresolved_text", ()), strict=True
        ):
            _record(
                rows,
                source="turn_candidates",
                situation=f"unresolved field: {field}",
                text=text,
                position=position,
            )
        for step in candidate["steps"]:
            prompt = step.get("prompt")
            if isinstance(prompt, str):
                _record(
                    rows,
                    source="turn_candidates",
                    situation=f"step prompt: {step['kind']}",
                    text=prompt,
                    position=position,
                )
            label = step.get("label")
            if isinstance(label, str):
                _record(
                    rows,
                    source="turn_candidates",
                    situation=f"step label: {step['kind']}",
                    text=label,
                    position=position,
                )
            hire_text = step.get("hire_text")
            if isinstance(hire_text, str) and hire_text.startswith("This action uses the Bank"):
                _record(
                    rows,
                    source="turn_candidates",
                    situation=f"step hire fact: {step['kind']}",
                    text=hire_text,
                    position=position,
                )
            for choice in step.get("choices", ()):
                _record(
                    rows,
                    source="turn_candidates",
                    situation=f"step button: {step['kind']}",
                    text=str(choice["label"]),
                    position=position,
                )


def _record_turn_window(
    rows: defaultdict[tuple[str, str, str], set[str]],
    *,
    state: object,
    config: object,
    position: str,
) -> None:
    available_turn_steps = turn_steps_payload(state, config)
    for step in available_turn_steps:
        hire_text = step.get("hire_text")
        if not isinstance(hire_text, str) or not hire_text:
            continue
        _record(
            rows,
            source="_building_hire_sentence",
            situation=f"hire source: {step['ability']['source_type']}",
            text=hire_text,
            position=position,
        )
    text = _turn_window_prompt(
        resolution_committed=state.turn_progress.resolution_committed,
        available_turn_steps=available_turn_steps,
    )
    _record(
        rows,
        source="_turn_window_prompt",
        situation="available building abilities",
        text=text,
        position=position,
    )


def _record_building_statuses(
    rows: defaultdict[tuple[str, str, str], set[str]],
    *,
    state: object,
    config: object,
    position: str,
) -> None:
    for ability in building_abilities_payload(state, config):
        building_id = str(ability["building_id"])
        _record(
            rows,
            source="_building_ability_status_text",
            situation=f"{building_id}: {ability['reason'] or 'usable'}",
            text=str(ability["status_text"]),
            position=position,
        )
    for ability in building_ability_windows_payload(state, config)["sow"]["abilities"]:
        if ability["reason"] != "mid_sow":
            continue
        _record(
            rows,
            source="_building_ability_status_text",
            situation=f"{ability['building_id']}: mid_sow",
            text=str(ability["status_text"]),
            position=position,
        )


def _record_events(
    rows: defaultdict[tuple[str, str, str], set[str]],
    *,
    events: object,
    config: object,
    position: str,
) -> None:
    for event in events:
        text = format_event_for_players(event, config)
        if text is not None:
            _record(
                rows,
                source="format_event_for_players",
                situation=event.event_type.value,
                text=text,
                position=position,
            )


def collect_rows(root: Path | None = None) -> tuple[TextInventoryRow, ...]:
    """Call the five player-text seams over the committed scenario corpus."""
    base = project_root() if root is None else root
    observed: defaultdict[tuple[str, str, str], set[str]] = defaultdict(set)

    for path in scenario_paths(base):
        scenario = load_scenario(path)
        initial_position = _position_name(path, base)
        _record_turn_candidates(
            observed,
            state=scenario.state,
            config=scenario.config,
            position=initial_position,
        )
        _record_turn_window(
            observed,
            state=scenario.state,
            config=scenario.config,
            position=initial_position,
        )
        _record_building_statuses(
            observed,
            state=scenario.state,
            config=scenario.config,
            position=initial_position,
        )

        for action in legal_actions(scenario.state, scenario.config):
            result = apply_action(scenario.state, action, scenario.config)
            action_position = _position_name(path, base, f"after {action_id(action)}")
            _record_turn_window(
                observed,
                state=result.state,
                config=scenario.config,
                position=action_position,
            )
            _record_building_statuses(
                observed,
                state=result.state,
                config=scenario.config,
                position=action_position,
            )
            _record_events(
                observed,
                events=result.events,
                config=scenario.config,
                position=action_position,
            )

        for step in turn_steps(scenario.state, scenario.config):
            after_step = apply_turn_step(scenario.state, scenario.config, step)
            applied_step_id = turn_step_id(step)
            step_position = _position_name(path, base, f"after {applied_step_id}")
            _record_turn_window(
                observed,
                state=after_step,
                config=scenario.config,
                position=step_position,
            )
            _record_building_statuses(
                observed,
                state=after_step,
                config=scenario.config,
                position=step_position,
            )
            _record_events(
                observed,
                events=(event for event in after_step.events if event.action_id == applied_step_id),
                config=scenario.config,
                position=step_position,
            )

    return tuple(
        TextInventoryRow(
            source=source,
            situation=situation,
            text=text,
            positions=tuple(sorted(positions)),
        )
        for (source, situation, text), positions in sorted(observed.items())
    )


def _markdown_cell(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")


def _position_preview(positions: tuple[str, ...]) -> str:
    if len(positions) <= _POSITION_PREVIEW_COUNT:
        return "; ".join(positions)
    shown = "; ".join(positions[:_POSITION_PREVIEW_COUNT])
    return f"{shown}; … ({len(positions)} total)"


def render_markdown(rows: tuple[TextInventoryRow, ...]) -> str:
    """Render a stable table that is useful in review rather than as source code."""
    lines = [
        "# What the Game Says",
        "",
        "Generated by `python3 tools/audits/text_inventory.py`; do not edit by hand.",
        "",
        "The audit executes the five text producers over every checked-in scenario, its legal",
        "actions, and its available committed turn steps. Positions name the scenario whose live",
        "state or transition produced the text; rows with more than six show the total as well.",
        "",
        "| Source | Situation | Text | Positions |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        positions = _position_preview(row.positions)
        lines.append(
            "| "
            + " | ".join(
                (
                    _markdown_cell(row.source),
                    _markdown_cell(row.situation),
                    _markdown_cell(row.text) or "*(nothing shown)*",
                    _markdown_cell(positions),
                )
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def generate_markdown(root: Path | None = None) -> str:
    return render_markdown(collect_rows(root=root))


def output_path(root: Path | None = None) -> Path:
    base = project_root() if root is None else root
    return base / OUTPUT_PATH


def main() -> None:
    output_path().write_text(generate_markdown(), encoding="utf-8")


if __name__ == "__main__":
    main()
