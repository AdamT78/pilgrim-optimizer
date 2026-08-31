"""Pinned player wording at the seams documented by the text inventory."""

from __future__ import annotations

import pytest

from pilgrim.io.event_text import format_event_for_players
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import StartPlayerConfessionBoxAction
from pilgrim.model.enums import EventType
from pilgrim.model.events import GameEvent, make_event_details
from tools import play_server
from tools.audits import text_inventory
from tools.ui_debug import render_play_view

_CHANGED_TEXTS: tuple[str, ...] = (
    "player_one: Choose a space to lift acolytes from.",
    "player_one: Follow an arrow.",
    "player_one: Choose a duty to take.",
    "player_one: Choose the City or Duty space on your route to leave unsown.",
    "player_one: Choose a resource.",
    "player_one: Choose a building.",
    "player_one: Choose whether to hire a building.",
    "player_one: Choose payment.",
    "player_one: Move serfs and acolytes, up to 1 in total.",
    "player_one: Move serfs and acolytes, up to 2 in total.",
    "Move a serf from the Village to the Abbey",
    "Move an Acolyte from the Abbey to the City",
    "player_one: Move one acolyte from the Abbey to Special Activity and/or between "
    "Special Activities",
    "player_one: Move two acolytes from the Abbey to Special Activity and/or between "
    "Special Activities",
    "player_one: Taxation step 2. No other Duty tile is a majority.",
    "player_one: Taxation step 2. Choose one resource.",
    "player_one: Taxation step 2. Choose two resources.",
    "player_one: Taxation step 2. The Scriptorium makes south west and west majorities. "
    "Choose two resources.",
    "player_one: Taxation step 2. The Customs House makes your occupied tiles majorities. "
    "Choose two resources.",
    "A building can be hired here.",
    "A building can be used here, free.",
    "Buildings can be used here — some free, some hired.",
    "player_one ordained a serf. It is now an acolyte in the Abbey.",
    "player_one sent an acolyte on a mission. It is now in the City.",
    "player_one hired Kogge from player_two and paid 1 silver.",
    "player_one hired Chapel from the market and paid 1 wheat to the bank.",
)


@pytest.fixture(scope="module")
def inventory_texts() -> set[str]:
    return {row.text for row in text_inventory.collect_rows()}


def _candidate_steps(scenario_path: str, kind: str) -> list[dict]:
    scenario = load_scenario(scenario_path)
    return [
        step
        for candidate in play_server.turn_candidates(
            scenario.state,
            scenario.config,
            include_preview_effects=False,
        )
        for step in candidate["steps"]
        if step["kind"] == kind
    ]


def _event(event_type: EventType, **details) -> GameEvent:
    from pilgrim.model.enums import PlayerId

    return GameEvent(
        event_type=event_type,
        actor=PlayerId.PLAYER_ONE,
        action_id="wording-test",
        details=make_event_details(**details),
    )


def test_ordination_prompt_and_buttons_name_the_duty_actions() -> None:
    steps = _candidate_steps("scenarios/ordination_ordain_then_mission_001.json", "ordination")

    assert {step["prompt"] for step in steps} == {
        "player_one: Move serfs and acolytes, up to 2 in total."
    }
    choice_sets = {
        tuple((choice["value"], choice["label"]) for choice in step["choices"])
        for step in steps
    }
    assert choice_sets == {
        (
            ("ordain", "Move a serf from the Village to the Abbey"),
            ("mission", "Move an Acolyte from the Abbey to the City"),
        )
    }
    page = render_play_view.render_turn_panel(
        {
            "turn_candidates": [
                {
                    "steps": steps,
                    "action_id": None,
                    "summary": None,
                    "unresolved": [],
                    "unresolved_text": [],
                    "variants": 1,
                }
            ]
        }
    )
    assert 'data-ordination-action="ordain"' in page
    assert ">Move a serf from the Village to the Abbey<" in page
    assert 'data-ordination-action="mission"' in page
    assert ">Move an Acolyte from the Abbey to the City<" in page


def test_taxation_and_special_activity_prompts_name_the_engine_count() -> None:
    one_resource = _candidate_steps("scenarios/playtest/movement_2p.json", "combination")
    two_resources = _candidate_steps("scenarios/taxation_majority_bonus_001.json", "combination")
    no_majority = _candidate_steps("scenarios/taxation_no_other_majority_001.json", "combination")
    arrangements = _candidate_steps("scenarios/allocation_infirmary_001.json", "arrangement")

    assert {
        step["prompt"]
        for step in one_resource
        if step.get("resource_total") == 1
    } == {
        "player_one: Taxation step 2. Choose one resource."
    }
    assert {
        step["prompt"]
        for step in two_resources
        if step.get("resource_total") == 2
    } == {
        "player_one: Taxation step 2. Choose two resources."
    }
    assert {
        step["prompt"] for step in no_majority if step.get("resource_total") == 0
    } == {"player_one: Taxation step 2. No other Duty tile is a majority."}
    assert {step["prompt"] for step in arrangements} == {
        "player_one: Move one acolyte from the Abbey to Special Activity and/or between "
        "Special Activities",
        "player_one: Move two acolytes from the Abbey to Special Activity and/or between "
        "Special Activities",
    }


def test_combination_questions_name_the_choice_instead_of_saying_choose_one() -> None:
    hire_steps = _candidate_steps("scenarios/building_hire_live_market_001.json", "hire")
    confession_scenario = load_scenario("scenarios/confession_box_owned_start_player_001.json")
    confession_steps = play_server.decision_steps(
        StartPlayerConfessionBoxAction(use=False),
        "player_one",
        state=confession_scenario.state,
        config=confession_scenario.config,
    )
    payment_steps = _candidate_steps("scenarios/give_alms_paid_001.json", "combination")

    assert {step["prompt"] for step in hire_steps} == {
        "player_one: Choose whether to hire a building."
    }
    assert {step["prompt"] for step in confession_steps} == {
        "player_one: Choose whether to use the Confession Box."
    }
    assert {step["prompt"] for step in payment_steps} == {"player_one: Choose payment."}


@pytest.mark.parametrize(
    ("prompt", "expected"),
    (
        (play_server.ORIGIN_PROMPT, "Choose a space to lift acolytes from."),
        (play_server.ROUTE_PROMPT, "Follow an arrow."),
        (play_server.DUTY_PROMPT, "Choose a duty to take."),
        (
            play_server.SKIP_PROMPT,
            "Choose the City or Duty space on your route to leave unsown.",
        ),
        (play_server.RESOURCE_PROMPT, "Choose a resource."),
        (play_server.BUILDING_PROMPT, "Choose a building."),
        (play_server.HIRE_PROMPT, "Choose whether to hire a building."),
        (play_server.CONFESSION_BOX_PROMPT, "Choose whether to use the Confession Box."),
        (play_server.ALMS_PAYMENT_PROMPT, "Choose payment."),
        (play_server.SEAT_PROMPT, "Choose first player for this round."),
        (play_server.ORDINATION_PROMPT, "Move serfs and acolytes, up to {n} in total."),
    ),
)
def test_changed_prompts_are_capitalised_and_exact(prompt: str, expected: str) -> None:
    assert prompt == expected
    assert prompt[0].isupper()


def test_ordination_and_hire_log_lines_read_as_player_sentences() -> None:
    config = load_scenario("scenarios/play_view_reference_4p_001.json").config

    assert format_event_for_players(
        _event(EventType.ORDINATION, step="ordain", amount=1), config
    ) == "player_one ordained a serf. It is now an acolyte in the Abbey."
    assert format_event_for_players(
        _event(EventType.ORDINATION, step="mission", amount=1), config
    ) == "player_one sent an acolyte on a mission. It is now in the City."
    assert format_event_for_players(
        _event(
            EventType.BUILDING_HIRED,
            building_name="Kogge",
            source="player_two",
            payee="player_two",
            amount=1,
            resource="silver",
        ),
        config,
    ) == "player_one hired Kogge from player_two and paid 1 silver."
    assert format_event_for_players(
        _event(
            EventType.BUILDING_HIRED,
            building_name="Chapel",
            source="market",
            payee="bank",
            amount=1,
            resource="wheat",
        ),
        config,
    ) == "player_one hired Chapel from the market and paid 1 wheat to the bank."


def test_player_facing_inventory_never_names_a_cornucopia(inventory_texts: set[str]) -> None:
    assert not {text for text in inventory_texts if "cornucopia" in text}


@pytest.mark.parametrize("expected", _CHANGED_TEXTS)
def test_changed_player_text_is_covered_by_the_generated_inventory(
    expected: str, inventory_texts: set[str]
) -> None:
    assert expected in inventory_texts
