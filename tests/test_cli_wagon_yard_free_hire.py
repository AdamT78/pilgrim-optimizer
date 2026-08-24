from pilgrim.cli import main
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import FullTurnAction
from pilgrim.rules.transition import legal_actions


def _wagon_action_index(path: str, *, target: str, source: str) -> int:
    scenario = load_scenario(path)
    for index, action in enumerate(legal_actions(scenario.state, scenario.config), start=1):
        if not isinstance(action, FullTurnAction):
            continue
        if (
            action.free_hire_enabler_building_id == "wagon_yard"
            and action.free_hire_target_building_id == target
            and action.free_hire_target_building_source == source
        ):
            return index
    raise AssertionError(f"No Wagon Yard action for {target} from {source} in {path}.")


def test_cli_wagon_yard_no_longer_prints_retired_conversion_effects(capsys) -> None:
    for path in (
        "scenarios/wagon_yard_active_free_hire_market_brewery_001.json",
        "scenarios/wagon_yard_active_free_hire_opponent_brewery_001.json",
    ):
        assert main(["legal-actions", path]) == 0
        output = capsys.readouterr().out
        assert "to sell 1 wheat for 2 silver" not in output


def test_cli_blocked_wagon_sources_do_not_print_wagon_modifier_lines(capsys) -> None:
    for path in (
        "scenarios/wagon_yard_market_not_hireable_001.json",
        "scenarios/wagon_yard_opponent_not_hireable_001.json",
        "scenarios/wagon_yard_donated_no_modifier_001.json",
        "scenarios/wagon_yard_not_live_no_modifier_001.json",
        "scenarios/wagon_yard_no_live_target_no_modifier_001.json",
        "scenarios/wagon_yard_cannot_target_self_001.json",
    ):
        assert main(["legal-actions", path]) == 0
        output = capsys.readouterr().out
        assert "use building: wagon_yard to hire" not in output


def test_cli_legal_actions_show_wagon_yard_without_precommitting_guild(capsys) -> None:
    market_path = "scenarios/wagon_yard_active_free_hire_market_guild_001.json"
    assert main(["legal-actions", market_path]) == 0
    market_output = capsys.readouterr().out
    assert "use building: wagon_yard to hire guild from market for free" in market_output
    assert "use building: guild to move merchant +1" not in market_output

    opponent_path = "scenarios/wagon_yard_active_free_hire_opponent_customs_house_001.json"
    assert main(["legal-actions", opponent_path]) == 0
    opponent_output = capsys.readouterr().out
    assert "use building: wagon_yard to hire customs_house from player_two for free" in opponent_output
    assert "use building: customs_house" in opponent_output


def test_cli_apply_market_free_hire_shows_free_event_and_order(capsys) -> None:
    path = "scenarios/wagon_yard_active_free_hire_market_guild_001.json"
    index = _wagon_action_index(path, target="guild", source="market")
    assert main(["apply", path, "--action-index", str(index), "--verbose"]) == 0
    output = capsys.readouterr().out
    assert "BUILDING_HIRED: player_one hired Guild from market for free with Wagon Yard" in output
    assert "BUILDING_BONUS: guild moved Merchant clockwise +1" not in output
    assert "paid wheat 1 to bank" not in output


def test_cli_apply_opponent_free_hire_shows_no_owner_payment(capsys) -> None:
    path = "scenarios/wagon_yard_active_free_hire_opponent_customs_house_001.json"
    index = _wagon_action_index(path, target="customs_house", source="player_two")
    assert main(["apply", path, "--action-index", str(index), "--verbose"]) == 0
    output = capsys.readouterr().out
    assert "BUILDING_HIRED: player_one hired Customs House from player_two for free with Wagon Yard" in output
    assert "to player_two" not in output


def test_cli_wagon_yard_merchant_taxation_override_shows_legal_actions_and_apply(capsys) -> None:
    path = "scenarios/wagon_yard_active_free_hire_market_customs_house_001.json"
    assert main(["legal-actions", path]) == 0
    legal_output = capsys.readouterr().out
    assert "use building: wagon_yard to hire customs_house from market for free" in legal_output
    index = _wagon_action_index(path, target="customs_house", source="market")
    assert main(["apply", path, "--action-index", str(index), "--verbose"]) == 0
    apply_output = capsys.readouterr().out
    assert "BUILDING_HIRED: player_one hired Customs House from market for free with Wagon Yard" in apply_output
    assert "BUILDING_BONUS: customs_house" in apply_output
