"""What a tithe takes, and who decides it.

A tithe paid nothing at all until now: the enumerator emitted one unparameterised TITHE per
reachable duty and apply emitted an event and moved no goods. So there is no behaviour here to
preserve, only behaviour to state.

WHY THE FIXTURE

The fallback tithe counters that hand-written scenarios inherit are 2 wheat, 3 silver and 2 stone
with no cornucopia, so nothing already in the repository could reach the choice. The generated
boards can, but they start mid-setup and would need a setup played out before a duty could be
tithed at all. `scenarios/tithe_counter_choice_001.json` is a normal-play board that carries all
four kinds of counter -- wheat, stone, silver and the cornucopia -- and puts Taxation among the
tiles a player can actually sow to, so the presences and the one absence are all checkable from
one load.
"""

from __future__ import annotations

import dataclasses

import pytest

from pilgrim.io.event_text import format_event
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import FullTurnAction, action_summary
from pilgrim.model.enums import EventType, TurnResolutionType
from pilgrim.rules.transition import apply_action, legal_actions

FIXTURE = "scenarios/tithe_counter_choice_001.json"
DECIDED = {"action_type", "origin", "route", "selected_duty", "resolution", "tithe_resource"}


def _fixture():
    scenario = load_scenario(FIXTURE)
    return scenario.state, scenario.config


def _plain_tithes(state, config):
    """Tithes carrying no building hire, conversion or other rider that would move goods too.

    Anything else in the action list can spend or earn on its own account, and this file is about
    what the tithe alone does.
    """
    tithes = []
    for action in legal_actions(state, config):
        if action.resolution is not TurnResolutionType.TITHE:
            continue
        riders = [
            field.name
            for field in dataclasses.fields(action)
            if field.name not in DECIDED and getattr(action, field.name) != field.default
        ]
        if not riders:
            tithes.append(action)
    return tithes


def _position_with_counter(config, counter: str) -> int:
    for index in config.tithe_counters.board_indices_by_position:
        if config.tithe_counters.resource_for_board_index(index) == counter:
            return index
    raise AssertionError(f"the fixture carries no {counter} counter")


def _only_tithe_on(state, config, position: int, resource: str) -> FullTurnAction:
    matches = [
        action
        for action in _plain_tithes(state, config)
        if action.selected_duty == position and action.tithe_resource == resource
    ]
    assert matches, f"no plain tithe gaining {resource} at board position {position}"
    return matches[0]


def _stocks(state, player):
    resources = state.player_state(player).resources
    return {"stone": resources.stone, "silver": resources.silver, "wheat": resources.wheat}


@pytest.mark.parametrize("counter", ["wheat", "stone", "silver"])
def test_a_tithe_on_a_plain_counter_moves_that_stock_by_one_and_no_other(counter: str) -> None:
    """Parametrised over all three, because one resource proves almost nothing.

    A test that only ever tithes wheat passes just as happily against an apply that ignores the
    action and pays wheat every time -- a one-in-three chance of certifying the exact bug this
    field exists to prevent.
    """
    state, config = _fixture()
    player = state.active_player
    before = _stocks(state, player)
    position = _position_with_counter(config, counter)

    action = _only_tithe_on(state, config, position, counter)
    after = _stocks(apply_action(state, action, config).state, player)

    # The stocks that must not move are checked first, so that a tithe paying out of the wrong one
    # is reported as the stock that moved rather than as the stock that failed to.
    for untouched in sorted({"stone", "silver", "wheat"} - {counter}):
        assert after[untouched] == before[untouched], (
            f"a tithe on a {counter} counter moved {untouched}"
        )
    assert after[counter] == before[counter] + 1


def test_a_cornucopia_offers_exactly_three_tithes_one_per_resource() -> None:
    state, config = _fixture()
    position = _position_with_counter(config, "cornucopia")

    offered = [
        action for action in _plain_tithes(state, config) if action.selected_duty == position
    ]

    assert len(offered) == 3
    assert sorted(action.tithe_resource for action in offered) == ["silver", "stone", "wheat"]


@pytest.mark.parametrize("chosen", ["wheat", "stone", "silver"])
def test_a_cornucopia_tithe_pays_the_resource_it_named_and_no_other(chosen: str) -> None:
    """The guard on settling the resource at enumeration rather than re-deriving it at apply.

    The tile still says `cornucopia` when apply runs. An apply that looks the counter up again
    meets the wildcard a second time and has to pick, and whatever it picks it picks for all three
    variants, so they all pay out of one stock. Nothing that only reads `legal_actions` can see
    that: the three variants are generated correctly and labelled correctly, and the whole
    divergence is in what the payment moves.

    Which is why the assertion carrying the weight is the two stocks that must NOT move. That the
    named stock rises by one stays true under the bug for one resource in three.
    """
    state, config = _fixture()
    player = state.active_player
    before = _stocks(state, player)
    position = _position_with_counter(config, "cornucopia")

    action = _only_tithe_on(state, config, position, chosen)
    after = _stocks(apply_action(state, action, config).state, player)

    for untouched in sorted({"stone", "silver", "wheat"} - {chosen}):
        assert after[untouched] == before[untouched], (
            f"a cornucopia tithe naming {chosen} moved {untouched}"
        )
    assert after[chosen] == before[chosen] + 1


def test_apply_pays_what_the_action_says_even_when_the_tile_says_otherwise() -> None:
    """States the rule directly rather than through the wildcard: the action is the authority.

    A tithe naming wheat on a stone tile is not a position any enumeration reaches, and that is the
    point. If apply consults the counter at all this fails, and it fails on a board where the
    counter is a plain resource and re-deriving would look perfectly reasonable.
    """
    state, config = _fixture()
    player = state.active_player
    before = _stocks(state, player)
    stone_tile = _position_with_counter(config, "stone")
    reached_by = _only_tithe_on(state, config, stone_tile, "stone")

    contradicting = dataclasses.replace(reached_by, tithe_resource="wheat")
    after = _stocks(apply_action(state, contradicting, config).state, player)

    assert after["stone"] == before["stone"], "apply read the tile instead of the action"
    assert after["wheat"] == before["wheat"] + 1


def test_taxation_offers_no_tithe_though_the_player_can_sow_to_it() -> None:
    """Absence worth asserting only because the tile is reachable; an unreachable tile proves it."""
    state, config = _fixture()
    taxation = config.duty_tiles.board_index_for_category("taxation")
    actions = legal_actions(state, config)

    assert taxation in {action.selected_duty for action in actions}
    assert config.tithe_counters.resource_for_board_index(taxation) is None
    assert not [
        action
        for action in actions
        if action.resolution is TurnResolutionType.TITHE and action.selected_duty == taxation
    ]


def test_every_tithe_names_a_resource_its_own_tile_could_pay() -> None:
    """Sweeps the whole list rather than the tiles this file picked out by hand."""
    state, config = _fixture()

    for action in legal_actions(state, config):
        if action.resolution is not TurnResolutionType.TITHE:
            continue
        counter = config.tithe_counters.resource_for_board_index(action.selected_duty)
        allowed = {"wheat", "stone", "silver"} if counter == "cornucopia" else {counter}
        assert action.tithe_resource in allowed, (
            f"tithe on a {counter} counter claims to gain {action.tithe_resource}"
        )


def test_the_log_names_what_the_tithe_took() -> None:
    """A log that says only "mode tithe" leaves the reader to work out what arrived."""
    state, config = _fixture()
    position = _position_with_counter(config, "cornucopia")
    action = _only_tithe_on(state, config, position, "stone")

    result = apply_action(state, action, config)
    resolutions = [
        event for event in result.events if event.event_type is EventType.DUTY_RESOLUTION
    ]
    deltas = [event for event in result.events if event.event_type is EventType.RESOURCE_DELTA]

    assert len(resolutions) == 1
    assert dict(resolutions[0].details)["tithe_resource"] == "stone"
    assert "gained stone" in format_event(resolutions[0], config)

    assert len(deltas) == 1
    delta = dict(deltas[0].details)
    assert (delta["stone"], delta["silver"], delta["wheat"]) == (1, 0, 0)


def test_the_summary_says_which_resource_before_the_turn_is_committed() -> None:
    """Three cornucopia tithes are identical in every other word the summary prints."""
    state, config = _fixture()
    position = _position_with_counter(config, "cornucopia")

    summaries = {
        action_summary(_only_tithe_on(state, config, position, resource), config)
        for resource in ("wheat", "stone", "silver")
    }

    assert len(summaries) == 3
    assert all("action: tithe | gain " in summary for summary in summaries)
