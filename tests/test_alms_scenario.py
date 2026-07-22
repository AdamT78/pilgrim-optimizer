from pilgrim.cli import main
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import action_summary
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules.transition import apply_action, legal_actions
from pilgrim.rules.validation import validate_state_invariants


def test_alms_sandbox_scenario_validates() -> None:
    scenario = load_scenario("scenarios/alms_sandbox_001.json")
    validate_state_invariants(scenario.state)


def test_alms_sandbox_legal_actions_include_give_alms_with_payment_text(capsys) -> None:
    exit_code = main(["legal-actions", "scenarios/alms_sandbox_001.json"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Legal actions for scenario 'alms_sandbox_001':" in output
    assert "action: give_alms" in output
    assert "pay silver=1, wheat=1" in output


def test_alms_sandbox_give_alms_transition_emits_events_and_conserves_workforce() -> None:
    scenario = load_scenario("scenarios/alms_sandbox_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    give_alms_action = next(
        action for action in actions if action.resolution is TurnResolutionType.GIVE_ALMS
    )

    summary = action_summary(give_alms_action, scenario.config)
    assert "action: give_alms" in summary
    assert "pay silver=1, wheat=1" in summary

    before = scenario.state
    before_p1_total = before.total_acolytes(PlayerId.PLAYER_ONE)
    before_p2_total = before.total_acolytes(PlayerId.PLAYER_TWO)

    result = apply_action(before, give_alms_action, scenario.config)
    after_player = result.state.player_state(PlayerId.PLAYER_ONE)

    assert after_player.alms_position == 2
    assert after_player.workforce.village == 0
    assert after_player.workforce.abbey == 2
    assert result.state.player_vector(PlayerId.PLAYER_ONE)[0] == 1

    event_types = {event.event_type for event in result.events}
    assert EventType.ALMS_PAYMENT in event_types
    assert EventType.ALMS_PROGRESS in event_types
    assert EventType.ALMS_THRESHOLD_REWARD in event_types

    threshold_event = next(
        event for event in result.events if event.event_type is EventType.ALMS_THRESHOLD_REWARD
    )
    threshold_details = dict(threshold_event.details)
    assert "row 2" in str(threshold_details["description"])

    assert result.state.total_acolytes(PlayerId.PLAYER_ONE) == before_p1_total
    assert result.state.total_acolytes(PlayerId.PLAYER_TWO) == before_p2_total


def test_alms_sandbox_solve_verbose_runs(capsys) -> None:
    exit_code = main(
        [
            "solve",
            "scenarios/alms_sandbox_001.json",
            "--depth",
            "3",
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Solve result for scenario 'alms_sandbox_001'" in output
    assert "Events for best first full turn:" in output
