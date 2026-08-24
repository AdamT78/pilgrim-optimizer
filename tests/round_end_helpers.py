"""Driving a round end past the Confession Box questions, for tests that are about something else.

A round end now stops and asks each player who can reach a Confession Box whether they will spend
on it, and only awards the First Player marker once the last of them has answered. Every test that
cares about excess caps, ship advance, season scoring, trade-route income or the marker itself was
written against a round end that ran through in one action, and none of them are about the boxes.

So this walks the questions with the answer that changes nothing -- decline, every time -- and
hands back one result carrying every event from the whole run. What those tests assert stays true
and stays theirs; the boxes get their own tests, where declining is one of the answers under test
rather than the way of getting past it.
"""

from __future__ import annotations

from pilgrim.model.actions import EndTurnAction, GameAction, StartPlayerConfessionBoxAction
from pilgrim.model.config import GameConfig
from pilgrim.model.enums import TurnPhase
from pilgrim.model.state import GameState
from pilgrim.rules.transition import TransitionResult, apply_action


def apply_declining_confession(
    state: GameState,
    action: GameAction,
    config: GameConfig,
) -> TransitionResult:
    """Apply one full turn, pass its End Turn window, then decline Confession Box questions."""
    result = apply_action(state, action, config)
    events = list(result.events)
    next_state = result.state
    while next_state.turn_progress.resolution_committed:
        passed = apply_action(next_state, EndTurnAction(), config)
        events.extend(passed.events)
        next_state = passed.state
    while next_state.phase is TurnPhase.START_PLAYER_CONFESSION:
        declined = apply_action(next_state, StartPlayerConfessionBoxAction(use=False), config)
        events.extend(declined.events)
        next_state = declined.state
    return TransitionResult(state=next_state, events=tuple(events))
