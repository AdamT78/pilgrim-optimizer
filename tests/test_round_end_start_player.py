from __future__ import annotations

import re

import pytest

from pilgrim.io.event_text import format_event
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import StartPlayerSelectionAction, action_id
from pilgrim.model.enums import EventType, PlayerId, TurnPhase
from pilgrim.rules.transition import legal_actions
from tests.round_end_helpers import apply_declining_confession

_PLAYER_NAME = re.compile(r"player_(?:one|two|three|four)")


def _round_ended(scenario, *, start_player: PlayerId | None = None):
    """Play the turn that closes the round, and return where it stops."""
    state = scenario.state
    if start_player is not None:
        state = state.with_start_player(start_player)
    action = legal_actions(state, scenario.config)[0]
    return apply_declining_confession(state, action, scenario.config)


def _details(events, event_type):
    return dict(next(event for event in events if event.event_type is event_type).details)


def test_a_round_ends_by_stopping_on_the_marker_holder_with_nothing_else_to_do() -> None:
    """The round does not run on into the next one. It stops, holding the table on one player.

    Everything about the position says the same thing: the phase names what is being waited for,
    the active player names who is being waited on, and the only actions on offer are that player's
    answer. What is NOT set is the start player, which is still the seat the round was played from
    -- nobody has chosen yet, and writing one in advance is exactly the placeholder this replaces.
    """
    scenario = load_scenario("scenarios/round_end_excess_caps_001.json")
    result = _round_ended(scenario, start_player=PlayerId.PLAYER_TWO)

    assert result.state.phase is TurnPhase.START_PLAYER_SELECTION
    assert result.state.active_player is PlayerId.PLAYER_ONE
    assert result.state.start_player is PlayerId.PLAYER_TWO
    assert result.state.timing.turn_in_round == 0

    marker = _details(result.events, EventType.START_PLAYER_MARKER)
    assert marker["deciding_player"] == "player_one"
    assert marker["current_start_player"] == "player_two"
    assert not any(event.event_type is EventType.START_PLAYER_SELECTION for event in result.events)

    offered = legal_actions(result.state, scenario.config)
    assert {action.chosen_start_player for action in offered} == {
        PlayerId.PLAYER_ONE,
        PlayerId.PLAYER_TWO,
    }
    assert all(isinstance(action, StartPlayerSelectionAction) for action in offered)


@pytest.mark.parametrize(
    "chosen",
    [PlayerId.PLAYER_ONE, PlayerId.PLAYER_TWO],
    ids=["holder chooses themselves", "holder chooses the other player"],
)
def test_whoever_the_holder_names_is_who_begins_the_next_round(chosen: PlayerId) -> None:
    """Every option on offer really works, including the holder naming themselves.

    Both run through the same code by the same route. If choosing yourself were special-cased
    anywhere, one of these two would be taking a path the other does not, and the point of the rule
    is that it does not: the holder is simply one of the players who may be chosen.
    """
    scenario = load_scenario("scenarios/round_end_excess_caps_001.json")
    waiting = _round_ended(scenario, start_player=PlayerId.PLAYER_TWO).state
    holder = waiting.active_player
    assert holder is PlayerId.PLAYER_ONE

    action = StartPlayerSelectionAction(chosen_start_player=chosen)
    assert action in legal_actions(waiting, scenario.config)
    result = apply_declining_confession(waiting, action, scenario.config)

    assert result.state.start_player is chosen
    assert result.state.active_player is chosen
    assert result.state.phase is TurnPhase.SOW

    # Both names are carried whichever way the choice went, so a reader of the event never has to
    # work out from an absent one whether the holder kept the round or the detail was dropped.
    selection = _details(result.events, EventType.START_PLAYER_SELECTION)
    assert selection["deciding_player"] == "player_one"
    assert selection["selected_start_player"] == chosen.name.lower()


def test_a_holder_naming_someone_else_gives_up_the_next_round_to_them() -> None:
    """The whole reason the marker is worth having is that it need not be kept.

    Read off the piety rather than off the seat: the player with the most piety takes the marker
    and hands the round to the player with the least, which no policy that picks by piety could
    ever produce.
    """
    scenario = load_scenario("scenarios/round_end_excess_caps_001.json")
    waiting = _round_ended(scenario).state
    piety = {
        player: waiting.player_state(player).piety
        for player in (PlayerId.PLAYER_ONE, PlayerId.PLAYER_TWO)
    }
    holder = max(piety, key=lambda player: piety[player])
    other = min(piety, key=lambda player: piety[player])
    assert waiting.active_player is holder

    result = apply_declining_confession(
        waiting,
        StartPlayerSelectionAction(chosen_start_player=other),
        scenario.config,
    )
    assert result.state.start_player is other
    assert result.state.active_player is other


@pytest.mark.parametrize(
    ("current_start", "expected_holder"),
    [
        (PlayerId.PLAYER_ONE, PlayerId.PLAYER_TWO),
        (PlayerId.PLAYER_TWO, PlayerId.PLAYER_ONE),
    ],
)
def test_a_tied_marker_walks_clockwise_from_whichever_seat_started_the_round(
    current_start: PlayerId,
    expected_holder: PlayerId,
) -> None:
    """The walk starts from the seat the round was played from, so moving it moves the answer.

    Run from two different start players on the same tied piety, because a tie-break tested from one
    fixed seat passes whether it walks from the start player, from the acting player, or from a
    hardcoded player_one.
    """
    scenario = load_scenario("scenarios/start_player_selection_001.json")
    result = _round_ended(scenario, start_player=current_start)

    assert result.state.active_player is expected_holder
    tie_break = _details(result.events, EventType.START_PLAYER_TIE_BREAK)
    assert tie_break["current_start_player"] == current_start.name.lower()
    assert tie_break["deciding_player"] == expected_holder.name.lower()


def test_the_marker_is_not_the_start_player_and_the_state_keeps_both() -> None:
    """The two facts are held separately and are allowed to disagree, which is the point.

    Under the placeholder they were one value wearing two names, so the marker could never mean
    anything. Here the holder is asked, says somebody else, and the state carries both answers.
    """
    scenario = load_scenario("scenarios/start_player_selection_001.json")
    waiting = _round_ended(scenario, start_player=PlayerId.PLAYER_ONE).state
    assert waiting.active_player is PlayerId.PLAYER_TWO
    assert waiting.start_player is PlayerId.PLAYER_ONE

    result = apply_declining_confession(
        waiting,
        StartPlayerSelectionAction(chosen_start_player=PlayerId.PLAYER_ONE),
        scenario.config,
    )
    assert result.state.start_player is PlayerId.PLAYER_ONE


def _selection_message(scenario, chosen: PlayerId) -> str:
    waiting = _round_ended(scenario, start_player=PlayerId.PLAYER_TWO).state
    result = apply_declining_confession(
        waiting,
        StartPlayerSelectionAction(chosen_start_player=chosen),
        scenario.config,
    )
    event = next(
        event for event in result.events if event.event_type is EventType.START_PLAYER_SELECTION
    )
    message = format_event(event, scenario.config)
    assert message is not None
    return message


def test_the_log_names_the_decider_and_the_player_they_chose_even_when_those_are_one_player() -> (
    None
):
    """One sentence for both cases, and it never has fewer than two names in it.

    This is the only line in the log where the decider and the player they chose are visibly two
    things, so it is the line that carries the whole point of separating them. Written short for the
    self-selection -- "player_one chose to begin this round" -- it reads exactly like a line
    that meant to name somebody and lost them, and a reader has to work out which from a name that
    is not there. The shape is compared with the names blanked out, so the two cases have to be the
    same sentence and not merely both mention two players.
    """
    scenario = load_scenario("scenarios/round_end_excess_caps_001.json")
    chose_self = _selection_message(scenario, PlayerId.PLAYER_ONE)
    chose_other = _selection_message(scenario, PlayerId.PLAYER_TWO)

    assert chose_self == (
        "START_PLAYER_SELECTION: player_one chose player_one to begin this round"
    )
    assert chose_other == (
        "START_PLAYER_SELECTION: player_one chose player_two to begin this round"
    )

    assert len(_PLAYER_NAME.findall(chose_self)) == 2
    assert len(_PLAYER_NAME.findall(chose_other)) == 2
    assert _PLAYER_NAME.sub("<player>", chose_self) == _PLAYER_NAME.sub("<player>", chose_other)


def test_a_selection_names_the_player_chosen_so_two_choices_are_two_actions() -> None:
    scenario = load_scenario("scenarios/round_end_excess_caps_001.json")
    waiting = _round_ended(scenario).state
    ids = [action_id(action) for action in legal_actions(waiting, scenario.config)]
    assert ids == ["start_player_selection:player_one", "start_player_selection:player_two"]
    assert len(set(ids)) == len(ids)


def test_choosing_a_start_player_is_refused_when_nobody_is_being_waited_on() -> None:
    """The action exists only inside the phase that asks for it."""
    scenario = load_scenario("scenarios/round_end_excess_caps_001.json")
    assert scenario.state.phase is not TurnPhase.START_PLAYER_SELECTION

    assert legal_actions(scenario.state, scenario.config)
    with pytest.raises(Exception, match="marker holder is being waited on"):
        apply_declining_confession(
            scenario.state,
            StartPlayerSelectionAction(chosen_start_player=PlayerId.PLAYER_ONE),
            scenario.config,
        )
