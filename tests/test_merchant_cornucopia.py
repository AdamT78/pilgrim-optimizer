"""What happens when the Merchant stands on the cornucopia tile.

WHY THIS FILE EXISTS AS ITS OWN THING

Hiring a building crashed on a cornucopia -- `_resource_amount` raises on it -- and the whole
suite passed over that crash. It passed because the fallback tithe counters that hand-written
scenarios inherit deal 2 wheat, 3 silver and 2 stone and NO cornucopia, so no scenario in the
repository could put the Merchant on one. The generator deals a cornucopia on every seed; the
fixtures could not. That gap is not a tidiness problem, it is the reason a reachable crash was
invisible, and these tests exist to reach the state the fixtures could not.

A test used to stand here pinning that blind spot, and its own docstring said to delete it rather
than widen it once a fixture dealt a cornucopia the Merchant can reach. Tithing the counter needed
exactly such a fixture, so `scenarios/tithe_counter_choice_001.json` now deals one and starts the
Merchant on it. The pin has been deleted as instructed and the coverage taken from the fixture, in
`test_a_committed_fixture_now_puts_the_merchant_on_a_cornucopia` below.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import FullTurnAction, action_id
from pilgrim.model.enums import EventType, TurnResolutionType
from pilgrim.rules.buildings import building_ability_source
from pilgrim.rules.merchant import current_merchant_resource
from pilgrim.rules.transition import (
    TransitionValidationError,
    apply_action,
    apply_turn_step,
    legal_actions,
    turn_steps,
)

HIRE_SCENARIO = "scenarios/building_hire_opponent_owned_001.json"
DEEP_SCENARIO = "scenarios/deep_round_eighteen_seed_seven_two_player_001.json"


def _payment_for_hired_building(action) -> str | None:
    if action.hired_building_id is None:
        return None
    return dict(action.hire_payments).get(action.hired_building_id)


def _hire_event_resources(events) -> Counter[str]:
    return Counter(
        str(dict(event.details).get("resource"))
        for event in events
        if event.event_type is EventType.BUILDING_HIRED
    )


def _with_counter_under_the_merchant(scenario, value: str):
    """Put one tithe counter on the tile the Merchant occupies, leaving everything else alone."""
    position_name = scenario.config.board.positions[scenario.state.merchant_board_position]
    counters = scenario.config.tithe_counters
    moved = tuple(
        (name, value if name == position_name else resource)
        for name, resource in counters.counters_by_position
    )
    return replace(scenario.config, tithe_counters=replace(counters, counters_by_position=moved))


def _with_cornucopia_under_the_merchant(scenario):
    return scenario.state, _with_counter_under_the_merchant(scenario, "cornucopia")


def _with_stock(state, *, stone: int, silver: int, wheat: int):
    """Set the acting player's goods, so affordability is under test and not the fixture."""
    player = state.active_player
    player_state = state.player_state(player)
    resources = replace(player_state.resources, stone=stone, silver=silver, wheat=wheat)
    return state.with_player_state(player, replace(player_state, resources=resources))


def test_a_merchant_on_the_cornucopia_offers_the_wildcard_rather_than_a_resource() -> None:
    scenario = load_scenario(HIRE_SCENARIO)
    state, config = _with_cornucopia_under_the_merchant(scenario)
    assert current_merchant_resource(state, config) == "cornucopia"


def test_hiring_on_a_cornucopia_is_affordable_if_any_one_stock_can_pay() -> None:
    """The wildcard is usable on the strength of whichever stock the payer chooses.

    This asserted a refusal until the choice existed. The refusal was a placeholder standing in for
    the rule, not the rule: paying in an arbitrary resource would have spent the wrong stock, so
    hiring was blocked rather than guessed at. Now the source stays wild and stays usable, and the
    resource is settled where the variants are built.
    """
    scenario = load_scenario(HIRE_SCENARIO)
    state, config = _with_cornucopia_under_the_merchant(scenario)

    source = building_ability_source(
        state,
        config,
        acting_player=state.active_player,
        building_key="well",
    )
    assert source.usable is True
    assert source.hire_resource == "cornucopia"


def test_hiring_on_a_cornucopia_is_unavailable_when_no_stock_can_pay() -> None:
    """A wildcard the payer cannot cover in any of its three stocks buys nothing.

    Unavailable for want of resources, which is the ordinary answer, and not the separate answer
    Taxation gives -- there the Merchant offers nothing at all, whatever the payer holds.
    """
    scenario = load_scenario(HIRE_SCENARIO)
    state, config = _with_cornucopia_under_the_merchant(scenario)
    state = _with_stock(state, stone=0, silver=0, wheat=0)

    source = building_ability_source(
        state,
        config,
        acting_player=state.active_player,
        building_key="well",
    )
    assert source.usable is False
    assert source.reason == "insufficient_resource"


def test_a_cornucopia_offers_one_hire_variant_per_affordable_resource() -> None:
    """The rule itself: the payer chooses, so each stock they can pay from is its own action.

    This asserted that no action could hire at all, which was the placeholder's shape. What it
    should hold is that the choice is offered exactly as wide as the payer's means.
    """
    scenario = load_scenario(HIRE_SCENARIO)
    _state, config = _with_cornucopia_under_the_merchant(scenario)

    state = _with_stock(scenario.state, stone=5, silver=5, wheat=5)
    hires = [
        action for action in legal_actions(state, config) if action.hired_building_id is not None
    ]
    assert {_payment_for_hired_building(action) for action in hires} == {
        "wheat",
        "stone",
        "silver",
    }

    state = _with_stock(scenario.state, stone=0, silver=0, wheat=5)
    hires = [
        action for action in legal_actions(state, config) if action.hired_building_id is not None
    ]
    assert {_payment_for_hired_building(action) for action in hires} == {"wheat"}

    state = _with_stock(scenario.state, stone=0, silver=0, wheat=0)
    assert not [
        action for action in legal_actions(state, config) if action.hired_building_id is not None
    ]


def test_a_single_affordable_resource_costs_nothing_in_extra_actions() -> None:
    """No-op pruning: one option is not a choice, so it should not read as one.

    A cornucopia the payer can only cover in wheat must generate exactly what a plain wheat counter
    would. With one affordable payment, there is no branch to add.

    Tithes are held out of the comparison because they are not subject to the claim. The helper
    moves the counter on the tile the MERCHANT stands on, and that tile is also a duty tile a
    player can sow to and tithe on, so a cornucopia there is two wildcards at once: what a hire is
    paid in and what a tithe gains. Only the first is prunable. The second has no affordability to
    prune against and always generates all three, which is a real difference in the action list and
    not the redundancy this test is about.
    """
    scenario = load_scenario(HIRE_SCENARIO)
    state = _with_stock(scenario.state, stone=0, silver=0, wheat=5)
    _unused, cornucopia_config = _with_cornucopia_under_the_merchant(scenario)
    wheat_config = _with_counter_under_the_merchant(scenario, "wheat")

    def hire_ids(config) -> set[str]:
        return {
            action_id(action)
            for action in legal_actions(state, config)
            if action.resolution is not TurnResolutionType.TITHE
        }

    wildcard_ids = hire_ids(cornucopia_config)
    plain_ids = hire_ids(wheat_config)
    assert wildcard_ids == plain_ids


@pytest.mark.parametrize(
    ("paid_in", "expected_stone", "expected_silver", "expected_wheat"),
    [
        ("stone", 4, 5, 7),
        ("silver", 5, 4, 7),
        ("wheat", 5, 5, 6),
    ],
)
def test_a_cornucopia_hire_is_paid_out_of_the_named_stock_and_no_other(
    paid_in: str,
    expected_stone: int,
    expected_silver: int,
    expected_wheat: int,
) -> None:
    """Guards that the resource is settled once, at enumeration, and not re-derived at apply time.

    Apply re-derives the hire source from the state, where the counter is still the wildcard. If it
    reads the resource off that source instead of off the action, it spends whichever stock the
    wildcard is compared against first, and every variant quietly pays in the same one. Nothing that
    only inspects `legal_actions` can see it: the three variants are generated correctly and tagged
    correctly, and the divergence is entirely in what the payment takes.

    So the assertion that carries the weight is the two stocks that must NOT move. That the named
    stock falls by the hire cost is true under the bug as well, for one of the three resources.

    The player holds five of each, and the resolution these hires attach to is Produce Wheat, worth
    +2 wheat whichever stock paid for the hire. Expected totals are written out in full rather than
    derived, so the test states an outcome instead of restating the arithmetic under test.
    """
    scenario = load_scenario(HIRE_SCENARIO)
    _unused, config = _with_cornucopia_under_the_merchant(scenario)
    state = _with_stock(scenario.state, stone=5, silver=5, wheat=5)

    variants = [
        action
        for action in legal_actions(state, config)
        if action.hired_building_id is not None and _payment_for_hired_building(action) == paid_in
    ]
    assert len(variants) == 1, f"expected exactly one hire variant paid in {paid_in}"

    after = apply_action(state, variants[0], config).state
    resources = after.player_state(state.active_player).resources

    # The stocks the hire must leave alone are checked first, so that a payment taken from the
    # wrong one is reported as what it is rather than as the named stock failing to fall.
    untouched = {"stone", "silver", "wheat"} - {paid_in}
    expected_untouched = {
        "stone": expected_stone,
        "silver": expected_silver,
        "wheat": expected_wheat,
    }
    for resource in sorted(untouched):
        assert getattr(resources, resource) == expected_untouched[resource], (
            f"hire paid in {paid_in} moved {resource}"
        )

    assert getattr(resources, paid_in) == expected_untouched[paid_in]


def test_paying_a_cornucopia_hire_spends_the_resource_the_action_named() -> None:
    """Resolution must honour the choice, not re-guess it from a source that is still wild."""
    scenario = load_scenario(HIRE_SCENARIO)
    _state, config = _with_cornucopia_under_the_merchant(scenario)
    state = _with_stock(scenario.state, stone=5, silver=5, wheat=5)

    # Net stock is the wrong lens: a Produce Wheat action paid for in wheat earns more than the
    # hire costs, so nothing looks spent. The variants are compared against each other instead,
    # where the only difference is which stock the hire came out of.
    variants = [
        action for action in legal_actions(state, config) if action.hired_building_id is not None
    ]
    grouped: dict[str, list] = {}
    for action in variants:
        key = action_id(replace(action, hire_payments=()))
        grouped.setdefault(key, []).append(action)

    compared = 0
    for group in grouped.values():
        for paid_here in group:
            for paid_elsewhere in group:
                if paid_here is paid_elsewhere:
                    continue
                here = apply_action(state, paid_here, config).state
                elsewhere = apply_action(state, paid_elsewhere, config).state
                spent = _payment_for_hired_building(paid_here)
                assert spent is not None
                assert getattr(here.player_state(state.active_player).resources, spent) < getattr(
                    elsewhere.player_state(state.active_player).resources, spent
                )
                compared += 1
    assert compared, "no cornucopia hire offered more than one resource to compare"


def test_a_committed_fixture_now_puts_the_merchant_on_a_cornucopia() -> None:
    """What the deleted blind-spot pin was standing in for, taken from the fixture instead.

    The fixture exists for tithing a cornucopia counter, and the Merchant happens to start on that
    same tile, so the state the hand-written fixtures could not reach is now one `load_scenario`
    away rather than something this file has to synthesise.
    """
    scenario = load_scenario("scenarios/tithe_counter_choice_001.json")
    assert current_merchant_resource(scenario.state, scenario.config) == "cornucopia"


def test_a_generated_scenario_deals_a_cornucopia_the_merchant_will_reach() -> None:
    """The counterpart to the blind spot: real games do reach this, every seed.

    The Merchant laps all eight tiles, so a cornucopia dealt anywhere is a tile it stands on
    within eight rounds.
    """
    from pilgrim.setup.generator import generate_setup_scenario

    for seed in (1, 2, 3):
        generated = generate_setup_scenario(player_count=2, seed=seed)
        counters = generated["tithe_counters"]
        assert "cornucopia" in set(counters.values()), seed


@pytest.mark.parametrize("resource", ["wheat", "stone", "silver"])
def test_the_ordinary_counters_are_unaffected_by_the_wildcard_branch(resource: str) -> None:
    """The choice must belong to the wildcard alone and must not spread to real resources."""
    scenario = load_scenario(HIRE_SCENARIO)
    config = _with_counter_under_the_merchant(scenario, resource)
    state = _with_stock(scenario.state, stone=5, silver=5, wheat=5)
    assert current_merchant_resource(state, config) == resource

    source = building_ability_source(
        state,
        config,
        acting_player=state.active_player,
        building_key="well",
    )
    assert source.hire_resource == resource
    hires = [action for action in legal_actions(state, config) if action.hired_building_id is not None]
    assert {_payment_for_hired_building(action) for action in hires} <= {resource}


def test_a_conversion_step_records_its_cornucopia_payment(deep_actions) -> None:
    scenario, _actions = deep_actions
    assert current_merchant_resource(scenario.state, scenario.config) == "cornucopia"
    step = next(
        step for step in turn_steps(scenario.state, scenario.config)
        if step.building_id == "grain_store"
    )
    assert step.hire_payment == "stone"
    state = apply_turn_step(scenario.state, scenario.config, step)
    assert _hire_event_resources(state.events) == Counter({"stone": 1})


def test_two_hires_on_the_cornucopia_can_pay_different_resources(deep_actions) -> None:
    scenario, _actions = deep_actions
    assert current_merchant_resource(scenario.state, scenario.config) == "cornucopia"
    conversion = next(
        step for step in turn_steps(scenario.state, scenario.config)
        if step.building_id == "grain_store"
    )
    state = apply_turn_step(scenario.state, scenario.config, conversion)
    action = next(
        action
        for action in legal_actions(state, scenario.config)
        if isinstance(action, FullTurnAction)
        and action.hire_payments == (("infirmary", "wheat"),)
    )

    result = apply_action(state, action, scenario.config)
    assert _hire_event_resources(result.events) == Counter({"wheat": 1, "stone": 1})


@pytest.mark.slow
def test_plain_merchant_resource_records_and_spends_route_hire_resource() -> None:
    scenario = load_scenario(DEEP_SCENARIO)
    config = _with_counter_under_the_merchant(scenario, "stone")
    action = next(
        action
        for action in legal_actions(scenario.state, config)
        if isinstance(action, FullTurnAction)
        and action.hire_payments == (("cloisters", "stone"),)
    )

    result = apply_action(scenario.state, action, config)
    assert _hire_event_resources(result.events) == Counter({"stone": 1})


def test_a_late_library_hire_can_pay_from_turn_earnings() -> None:
    """A hire late in the turn may be paid out of what the turn earned, not only what it opened with."""
    scenario = load_scenario("scenarios/library_hire_market_city_to_abbey_001.json")
    city = scenario.config.board.index_for_name("city")
    action = next(
        action
        for action in legal_actions(scenario.state, scenario.config)
        if isinstance(action, FullTurnAction)
        and action.origin == city
        and action.resolution is TurnResolutionType.PRODUCE_WHEAT
    )
    resolved = apply_action(scenario.state, action, scenario.config)
    step = next(
        step
        for step in turn_steps(resolved.state, scenario.config)
        if step.building_id == "library" and step.selected_position == "abbey"
    )
    after_step = apply_turn_step(resolved.state, scenario.config, step)
    assert _hire_event_resources(after_step.turn_progress.events) == Counter({"wheat": 1})


def test_hire_payments_must_match_hired_sources_exactly(deep_actions) -> None:
    scenario, actions = deep_actions
    base = next(
        action
        for action in actions
        if isinstance(action, FullTurnAction) and action.hire_payments
    )

    with_extra = replace(
        base,
        hire_payments=tuple(sorted((*base.hire_payments, ("mint", "stone")))),
    )
    with pytest.raises(TransitionValidationError, match="non-hired buildings"):
        apply_action(scenario.state, with_extra, scenario.config)

    with_missing = replace(base, hire_payments=())
    with pytest.raises(TransitionValidationError, match="missing payments"):
        apply_action(scenario.state, with_missing, scenario.config)


def test_a_building_named_in_two_route_slots_is_rejected() -> None:
    scenario = load_scenario("scenarios/cloisters_hire_market_skip_duty_tile_001.json")
    base = next(
        action
        for action in legal_actions(scenario.state, scenario.config)
        if isinstance(action, FullTurnAction)
        and action.sow_route_building_id == "cloisters"
        and action.sow_route_secondary_building_id is None
    )
    duplicated = replace(
        base,
        sow_route_secondary_building_id="cloisters",
        sow_route_secondary_building_source=base.sow_route_building_source,
    )
    with pytest.raises(TransitionValidationError, match="cannot be the same"):
        apply_action(scenario.state, duplicated, scenario.config)


def test_action_id_differs_when_hire_payments_differ() -> None:
    scenario = load_scenario(HIRE_SCENARIO)
    _state, config = _with_cornucopia_under_the_merchant(scenario)
    state = _with_stock(scenario.state, stone=5, silver=5, wheat=5)
    hires = [action for action in legal_actions(state, config) if action.hired_building_id is not None]

    grouped: dict[str, list[FullTurnAction]] = {}
    for action in hires:
        if not isinstance(action, FullTurnAction):
            continue
        grouped.setdefault(action_id(replace(action, hire_payments=())), []).append(action)
    group = next(group for group in grouped.values() if len(group) >= 2)
    first, second = group[0], group[1]
    assert first.hire_payments != second.hire_payments
    assert action_id(first) != action_id(second)
