from __future__ import annotations

from pilgrim.io.event_text import format_event
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import BuildingActivationStep
from pilgrim.model.enums import TurnResolutionType
from pilgrim.rules.transition import apply_action, apply_turn_step, legal_actions, turn_steps


def _pulpit_event_output(
    scenario_path: str,
    *,
    resolution: TurnResolutionType,
    ordination_steps: tuple[str, ...] | None = None,
) -> str:
    """Render the same events the CLI prints after Pulpit's committed step and resolution."""
    scenario = load_scenario(scenario_path)
    step = next(
        step
        for step in turn_steps(scenario.state, scenario.config)
        if isinstance(step, BuildingActivationStep) and step.building_id == "pulpit"
    )
    stepped = apply_turn_step(scenario.state, scenario.config, step)
    action = next(
        action
        for action in legal_actions(stepped, scenario.config)
        if action.resolution is resolution
        and (ordination_steps is None or action.ordination_steps == ordination_steps)
    )
    result = apply_action(stepped, action, scenario.config)
    return "\n".join(
        text
        for event in result.events
        if (text := format_event(event, scenario.config)) is not None
    )


def test_cli_output_for_own_active_pulpit_shows_bonus_and_workforce_move_before_sowing() -> None:
    output = _pulpit_event_output(
        "scenarios/pulpit_active_move_serf_001.json",
        resolution=TurnResolutionType.TITHE,
    )

    assert "BUILDING_HIRED" not in output
    assert "BUILDING_BONUS: pulpit moved 1 serf village -> abbey for free" in output
    assert "WORKFORCE_MOVE: player_one moved 1 serf village -> abbey for free with Pulpit" in output
    assert output.index("BUILDING_BONUS: pulpit moved 1 serf village -> abbey for free") < output.index(
        "WORKFORCE_MOVE: player_one moved 1 serf village -> abbey for free with Pulpit"
    )
    assert output.index(
        "WORKFORCE_MOVE: player_one moved 1 serf village -> abbey for free with Pulpit"
    ) < output.index("SOWING: picked up 1 from north; route north -> north_east")


def test_cli_output_for_market_hired_pulpit_shows_hire_then_bonus_then_move() -> None:
    output = _pulpit_event_output(
        "scenarios/pulpit_hire_market_move_serf_001.json",
        resolution=TurnResolutionType.TITHE,
    )

    assert "BUILDING_HIRED: player_one hired Pulpit from market; paid wheat 1 to bank" in output
    assert "BUILDING_BONUS: pulpit moved 1 serf village -> abbey for free" in output
    assert "WORKFORCE_MOVE: player_one moved 1 serf village -> abbey for free with Pulpit" in output
    assert output.index(
        "BUILDING_HIRED: player_one hired Pulpit from market; paid wheat 1 to bank"
    ) < output.index("BUILDING_BONUS: pulpit moved 1 serf village -> abbey for free")
    assert output.index("BUILDING_BONUS: pulpit moved 1 serf village -> abbey for free") < output.index(
        "WORKFORCE_MOVE: player_one moved 1 serf village -> abbey for free with Pulpit"
    )


def test_cli_output_for_opponent_hired_pulpit_shows_owner_payment() -> None:
    output = _pulpit_event_output(
        "scenarios/pulpit_hire_opponent_move_serf_001.json",
        resolution=TurnResolutionType.TITHE,
    )

    assert (
        "BUILDING_HIRED: player_one hired Pulpit from player_two; paid silver 1 to player_two"
        in output
    )
    assert "BUILDING_BONUS: pulpit moved 1 serf village -> abbey for free" in output
    assert "WORKFORCE_MOVE: player_one moved 1 serf village -> abbey for free with Pulpit" in output


def test_cli_output_for_pulpit_with_infirmary_still_shows_paid_ordination_steps() -> None:
    output = _pulpit_event_output(
        "scenarios/pulpit_infirmary_does_not_double_free_move_001.json",
        resolution=TurnResolutionType.ORDINATION,
        ordination_steps=("ordain", "mission"),
    )

    assert "BUILDING_BONUS: pulpit moved 1 serf village -> abbey for free" in output
    assert "WORKFORCE_MOVE: player_one moved 1 serf village -> abbey for free with Pulpit" in output
    assert "ORDINATION: player_one ordained 1 serf village -> abbey; paid wheat=1" in output
    assert "ORDINATION: player_one sent 1 acolyte abbey -> city; paid wheat=1" in output
