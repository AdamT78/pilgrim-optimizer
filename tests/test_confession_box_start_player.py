"""The Confession Box, asked of each player in turn before the marker is awarded.

What changed here is the SHAPE and not the rule. The bonus is still two piety, still temporary,
still spent only on the comparison that decides who holds the marker. What is gone is the tuple
that hung off one player's round-ending turn and carried everybody else's answer: each player is
now asked for their own, in the order the round was played, and the marker waits for the last of
them.

So the pruning tests are gone with the encoding they tested -- there is nothing left to prune
against, because a player deciding for themselves cannot be measured against an outcome that turns
on players who have not decided yet. Everything else here is the same claim as before, made about a
sequence of actions rather than one.
"""

from __future__ import annotations

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import EndTurnAction, StartPlayerConfessionBoxAction, action_summary
from pilgrim.model.enums import EventType, PlayerId, TurnPhase, TurnResolutionType
from pilgrim.rules.piety import score_piety
from pilgrim.rules.transition import (
    TransitionResult,
    TransitionValidationError,
    apply_action,
    legal_actions,
)


def _events_of_type(events, event_type: EventType):
    return [event for event in events if event.event_type is event_type]


def _round_ended(path: str):
    """Play the round-ending tithe, then make its required End of Turn pass."""
    scenario = load_scenario(path)
    action = next(
        candidate
        for candidate in legal_actions(scenario.state, scenario.config)
        if candidate.resolution is TurnResolutionType.TITHE
    )
    result = apply_action(scenario.state, action, scenario.config)
    if result.state.turn_progress.resolution_committed:
        passed = apply_action(result.state, EndTurnAction(), scenario.config)
        result = TransitionResult(
            state=passed.state,
            events=(*result.events, *passed.events),
        )
    return scenario, result


def _answer(scenario, state, events, answers: dict[PlayerId, str | None]):
    """Answer each Confession Box question in the order the engine puts them.

    `answers` maps a player to the source they use, or to None for a decline. A player the engine
    never asks simply never comes up, which is how the tests below check that it never asks them.
    """
    asked: list[PlayerId] = []
    while state.phase is TurnPhase.START_PLAYER_CONFESSION:
        player = state.active_player
        asked.append(player)
        source = answers.get(player)
        action = (
            StartPlayerConfessionBoxAction(use=False)
            if source is None
            else StartPlayerConfessionBoxAction(use=True, source=source)
        )
        result = apply_action(state, action, scenario.config)
        state, events = result.state, (*events, *result.events)
    return state, events, tuple(asked)


def _played(path: str, answers: dict[PlayerId, str | None]):
    scenario, result = _round_ended(path)
    state, events, asked = _answer(scenario, result.state, result.events, answers)
    return scenario, state, events, asked


# ---------------------------------------------------------------------------------------------
# Who is asked, and in what order
# ---------------------------------------------------------------------------------------------


def test_each_player_with_a_box_is_asked_in_the_order_the_round_was_played() -> None:
    """Turn order means clockwise from the seat the round STARTED from, not from anywhere else.

    The distinction only exists at a round end, which is the one moment it matters: the marker has
    not been awarded and no new start player has been chosen, so `start_player` still names the
    seat the finished round began at, and that is the seat the walk starts from.
    """
    scenario, result = _round_ended(
        "scenarios/confession_box_multiple_players_player_order_001.json"
    )
    start = scenario.state.start_player
    _state, _events, asked = _answer(scenario, result.state, result.events, {})

    expected = tuple(
        PlayerId((int(start) + offset) % scenario.state.player_count)
        for offset in range(scenario.state.player_count)
    )
    assert asked == tuple(player for player in expected if player in asked)
    assert asked[0] is start


def test_the_marker_is_awarded_only_after_the_last_player_has_answered() -> None:
    """Not one player early. The boxes are what the marker is being decided on."""
    scenario, result = _round_ended(
        "scenarios/confession_box_multiple_players_player_order_001.json"
    )
    state, events = result.state, result.events
    assert state.phase is TurnPhase.START_PLAYER_CONFESSION

    answered = 0
    while state.phase is TurnPhase.START_PLAYER_CONFESSION:
        still_to_answer = len(state.start_player_confession_pending)
        step = apply_action(state, StartPlayerConfessionBoxAction(use=False), scenario.config)
        answered += 1
        marker_now = _events_of_type(step.events, EventType.START_PLAYER_MARKER)
        assert bool(marker_now) == (still_to_answer == 1), (
            "the marker was awarded with players still owed a question"
        )
        state, events = step.state, (*events, *step.events)

    assert answered >= 2, "this scenario is meant to ask more than one player"
    assert state.phase is TurnPhase.START_PLAYER_SELECTION


def test_a_player_with_nothing_to_decide_is_never_asked() -> None:
    """No box within reach is not the same as a box declined, and does not cost a question."""
    scenario, result = _round_ended("scenarios/confession_box_owned_start_player_001.json")
    _state, _events, asked = _answer(scenario, result.state, result.events, {})

    reachable = {
        player
        for player in (PlayerId(index) for index in range(scenario.state.player_count))
        if player in asked
    }
    assert reachable == set(asked)
    assert len(asked) < scenario.state.player_count, (
        "every seat was asked, so this scenario cannot show a player being skipped"
    )


def test_a_table_where_nobody_can_reach_a_box_never_enters_the_phase() -> None:
    """The phase does not happen at all, rather than happening and asking nobody."""
    _scenario, result = _round_ended("scenarios/confession_box_hire_blocked_merchant_none_001.json")

    assert result.state.phase is TurnPhase.START_PLAYER_SELECTION
    assert result.state.start_player_confession_pending == ()
    event_types = {event.event_type for event in result.events}
    assert EventType.CONFESSION_BOX_PHASE not in event_types
    assert EventType.CONFESSION_BOX_BONUS not in event_types
    assert EventType.START_PLAYER_MARKER in event_types


def test_a_player_being_asked_is_offered_using_and_declining_and_nothing_else() -> None:
    _scenario2, result = _round_ended("scenarios/confession_box_owned_start_player_001.json")
    scenario = load_scenario("scenarios/confession_box_owned_start_player_001.json")
    offered = legal_actions(result.state, scenario.config)

    assert len(offered) == 2
    assert {action.use for action in offered} == {False, True}
    assert next(action.source for action in offered if action.use) is not None
    assert next(action.source for action in offered if not action.use) is None


# ---------------------------------------------------------------------------------------------
# What a use costs, and what it does not
# ---------------------------------------------------------------------------------------------


def test_a_use_leaves_real_piety_and_victory_points_exactly_where_they_were() -> None:
    """The untouched values first, because they are the ones a bug here would move.

    Two piety that were only ever borrowed. They are added to a comparison, the comparison is made,
    and nothing on any player record has changed -- not piety, not the victory points piety scores
    into, and not some temporary field quietly added to carry them.
    """
    path = "scenarios/confession_box_owned_temp_piety_above_12_001.json"
    scenario = load_scenario(path)
    before_piety = scenario.state.player_state(PlayerId.PLAYER_ONE).piety
    before_vp = score_piety(before_piety, scenario.config.piety)

    _scenario, state, events, _asked = _played(path, {PlayerId.PLAYER_ONE: "own_active"})
    after = state.player_state(PlayerId.PLAYER_ONE)

    assert after.piety == before_piety == 12
    assert score_piety(after.piety, scenario.config.piety) == before_vp
    assert after.victory_points == scenario.state.player_state(PlayerId.PLAYER_ONE).victory_points
    assert not hasattr(after, "temporary_piety")
    assert EventType.PIETY_DELTA not in {event.event_type for event in events}

    bonus = dict(_events_of_type(events, EventType.CONFESSION_BOX_BONUS)[0].details)
    marker = dict(_events_of_type(events, EventType.START_PLAYER_MARKER)[0].details)
    assert (bonus["base_piety"], bonus["temporary_bonus"], bonus["effective_piety"]) == (12, 2, 14)
    assert marker["highest_effective_piety"] == 14
    assert marker["deciding_player"] == "player_one"


def test_the_two_piety_are_not_carried_into_the_next_round() -> None:
    """Bought for one comparison. The state that follows must not still be holding them."""
    _scenario, state, _events, _asked = _played(
        "scenarios/confession_box_owned_start_player_001.json",
        {PlayerId.PLAYER_ONE: "own_active"},
    )
    assert state.start_player_confession_used == ()
    assert state.start_player_confession_pending == ()


def test_an_owned_box_costs_nothing_even_with_no_merchant_resource_to_pay_in() -> None:
    _scenario, _state, events, _asked = _played(
        "scenarios/confession_box_owned_start_player_001.json",
        {PlayerId.PLAYER_ONE: "own_active"},
    )
    event_types = {event.event_type for event in events}

    assert EventType.BUILDING_HIRED not in event_types
    assert EventType.CONFESSION_BOX_BONUS in event_types
    marker = dict(_events_of_type(events, EventType.START_PLAYER_MARKER)[0].details)
    assert marker["deciding_player"] == "player_one"


def test_a_market_hire_pays_the_bank_before_the_bonus_lands() -> None:
    _scenario, state, events, _asked = _played(
        "scenarios/confession_box_hire_market_start_player_001.json",
        {PlayerId.PLAYER_TWO: "market"},
    )
    hired = _events_of_type(events, EventType.BUILDING_HIRED)[0]
    bonus = _events_of_type(events, EventType.CONFESSION_BOX_BONUS)[0]
    hired_details = dict(hired.details)

    assert hired_details["building_id"] == "confession_box"
    assert hired_details["source"] == "market"
    assert hired_details["payee"] == "bank"
    assert (hired_details["resource"], hired_details["amount"]) == ("wheat", 1)
    assert dict(bonus.details)["effective_piety"] == 11
    # The hire's wheat goes out and the tithe's wheat comes back: these round-ending turns resolve
    # as tithes, which stopped being free of resource effects when they started paying counters.
    assert state.player_state(PlayerId.PLAYER_TWO).resources.wheat == 1
    assert events.index(hired) < events.index(bonus)


def test_an_opponent_hire_pays_the_owner_before_the_bonus_lands() -> None:
    _scenario, state, events, _asked = _played(
        "scenarios/confession_box_hire_opponent_start_player_001.json",
        {PlayerId.PLAYER_TWO: "player_one"},
    )
    hired = _events_of_type(events, EventType.BUILDING_HIRED)[0]
    bonus = _events_of_type(events, EventType.CONFESSION_BOX_BONUS)[0]
    hired_details = dict(hired.details)

    assert hired_details["source"] == "player_one"
    assert hired_details["payee"] == "player_one"
    assert (hired_details["resource"], hired_details["amount"]) == ("wheat", 1)
    assert dict(bonus.details)["effective_piety"] == 11
    assert state.player_state(PlayerId.PLAYER_TWO).resources.wheat == 1
    assert state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 1
    assert events.index(hired) < events.index(bonus)


# ---------------------------------------------------------------------------------------------
# What a use buys
# ---------------------------------------------------------------------------------------------


def test_using_a_box_takes_the_marker_off_the_player_who_would_have_had_it() -> None:
    """The whole point of the thing, shown as a difference between two runs of one position.

    Declining leaves the marker where the piety already put it. Using moves it. Both are played
    from the same round end, so nothing but the answer differs.
    """
    path = "scenarios/confession_box_effective_piety_tie_break_001.json"
    _scenario, declined_state, declined_events, _asked = _played(path, {})
    _scenario2, used_state, used_events, _asked2 = _played(
        path, {PlayerId.PLAYER_ONE: "own_active"}
    )

    declined_marker = dict(
        _events_of_type(declined_events, EventType.START_PLAYER_MARKER)[0].details
    )
    used_marker = dict(_events_of_type(used_events, EventType.START_PLAYER_MARKER)[0].details)

    assert declined_marker["deciding_player"] != "player_one"
    assert used_marker["deciding_player"] == "player_one"
    assert declined_state.first_player_marker is not PlayerId.PLAYER_ONE
    assert used_state.first_player_marker is PlayerId.PLAYER_ONE

    tie_break = dict(_events_of_type(used_events, EventType.START_PLAYER_TIE_BREAK)[0].details)
    assert tie_break["current_start_player"] == "player_two"
    assert tie_break["deciding_player"] == "player_one"
    # The bonus wins player_one the marker. It does not win them the round: they hold the
    # marker and have yet to say who begins, so the start player is still player_two.
    assert used_state.active_player is PlayerId.PLAYER_ONE
    assert used_state.start_player is PlayerId.PLAYER_TWO


def test_a_game_that_ends_at_the_round_end_never_asks_about_boxes() -> None:
    """Nothing left for the marker to decide, so nothing worth paying for it."""
    _scenario, result = _round_ended(
        "scenarios/confession_box_game_end_no_start_player_phase_001.json"
    )
    event_types = {event.event_type for event in result.events}

    assert result.state.game_over is True
    assert EventType.GAME_END in event_types
    assert EventType.CONFESSION_BOX_PHASE not in event_types
    assert EventType.CONFESSION_BOX_BONUS not in event_types
    assert EventType.START_PLAYER_MARKER not in event_types
    assert EventType.START_PLAYER_SELECTION not in event_types


# ---------------------------------------------------------------------------------------------
# Answers that are not the player's to give
# ---------------------------------------------------------------------------------------------


def test_a_box_decision_is_refused_outside_the_phase_that_asks_for_one() -> None:
    scenario = load_scenario("scenarios/alms_sandbox_001.json")
    with pytest.raises(TransitionValidationError, match="only legal while a player is being"):
        apply_action(
            scenario.state,
            StartPlayerConfessionBoxAction(use=False),
            scenario.config,
        )


def test_using_a_box_by_a_source_the_player_cannot_reach_is_refused() -> None:
    scenario, result = _round_ended("scenarios/confession_box_owned_start_player_001.json")
    with pytest.raises(TransitionValidationError, match="source selection is invalid"):
        apply_action(
            result.state,
            StartPlayerConfessionBoxAction(use=True, source="market"),
            scenario.config,
        )


def test_declining_cannot_smuggle_a_source_in_beside_the_refusal() -> None:
    scenario, result = _round_ended("scenarios/confession_box_owned_start_player_001.json")
    with pytest.raises(TransitionValidationError, match="cannot name a source"):
        apply_action(
            result.state,
            StartPlayerConfessionBoxAction(use=False, source="own_active"),
            scenario.config,
        )


def test_a_decision_reads_as_a_sentence_and_names_no_other_player() -> None:
    """One player, one answer. The old summary listed everybody's, which is what it should not."""
    scenario = load_scenario("scenarios/confession_box_owned_start_player_001.json")
    summaries = {
        action_summary(StartPlayerConfessionBoxAction(use=False), scenario.config),
        action_summary(
            StartPlayerConfessionBoxAction(use=True, source="own_active"), scenario.config
        ),
        action_summary(StartPlayerConfessionBoxAction(use=True, source="market"), scenario.config),
        action_summary(
            StartPlayerConfessionBoxAction(use=True, source="player_one"), scenario.config
        ),
    }
    assert summaries == {
        "Confession Box: decline",
        "Confession Box: use own active Confession Box",
        "Confession Box: hire from market",
        "Confession Box: hire from player_one",
    }
    for summary in summaries:
        assert ";" not in summary, "a decision that lists more than one thing is carrying somebody"


# ---------------------------------------------------------------------------------------------
# Two bugs made to happen on purpose, so that the tests above are known to catch them
# ---------------------------------------------------------------------------------------------


def test_asking_in_seat_order_instead_of_turn_order_is_caught(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MUTATION. Walk the seats from player_one rather than from the start player.

    The two readings agree whenever player_one happens to have started the round, which is most
    fresh boards and is why this is worth pinning: a scenario chosen without care would pass under
    either. The one below starts elsewhere, so the orders genuinely differ, and the seat-order
    reading asks the wrong player first.
    """
    from pilgrim.rules import round_end as round_end_rules

    path = "scenarios/confession_box_multiple_players_player_order_001.json"
    scenario, result = _round_ended(path)
    _state, _events, asked = _answer(scenario, result.state, result.events, {})
    assert scenario.state.start_player is not PlayerId.PLAYER_ONE, (
        "this scenario starts at player_one, so seat order and turn order cannot be told apart"
    )

    monkeypatch.setattr(
        round_end_rules,
        "start_player_confession_order",
        lambda state: tuple(PlayerId(index) for index in range(state.player_count)),
    )
    _scenario2, mutant = _round_ended(path)
    _state2, _events2, asked_by_seat = _answer(scenario, mutant.state, mutant.events, {})

    assert asked_by_seat != asked, "seat order and turn order produced the same sequence"
    assert asked_by_seat[0] is PlayerId.PLAYER_ONE
    assert asked[0] is scenario.state.start_player


def test_awarding_the_marker_before_the_boxes_resolve_is_caught(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MUTATION. Skip the phase and hand out the marker straight away.

    The failure is total but silent: every game still finishes, and the only symptom is that a
    building nobody can now use stops mattering. What catches it is that the position a player is
    handed has no question in it -- so there is no answer to give, and the piety that decided the
    marker is the piety nobody was allowed to add to.
    """
    from pilgrim.rules import transition as transition_rules

    path = "scenarios/confession_box_effective_piety_tie_break_001.json"
    _scenario, honest_state, honest_events, asked = _played(
        path, {PlayerId.PLAYER_ONE: "own_active"}
    )
    assert asked, "nobody was asked, so this scenario cannot show the phase being skipped"

    monkeypatch.setattr(
        transition_rules, "begin_start_player_confession", lambda state, *, config: None
    )
    _scenario2, mutant = _round_ended(path)

    assert mutant.state.phase is TurnPhase.START_PLAYER_SELECTION, (
        "the mutant is meant to skip straight past the questions"
    )
    assert _events_of_type(mutant.events, EventType.START_PLAYER_MARKER), (
        "the mutant is meant to award the marker in the round-ending action"
    )
    mutant_marker = dict(_events_of_type(mutant.events, EventType.START_PLAYER_MARKER)[0].details)
    honest_marker = dict(_events_of_type(honest_events, EventType.START_PLAYER_MARKER)[0].details)
    assert mutant_marker["deciding_player"] != honest_marker["deciding_player"], (
        "the box changed nothing here, so awarding early would not have been visible"
    )
    assert honest_state.first_player_marker is PlayerId.PLAYER_ONE
