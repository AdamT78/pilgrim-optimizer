from __future__ import annotations

import pytest

from pilgrim.cli import main


@pytest.mark.parametrize(
    "scenario_path",
    (
        "scenarios/guild_active_move_merchant_001.json",
        "scenarios/guild_hire_market_move_merchant_001.json",
        "scenarios/guild_round_end_moves_merchant_twice_001.json",
    ),
)
def test_cli_legal_actions_does_not_offer_guild_as_a_full_turn_modifier(
    capsys, scenario_path: str
) -> None:
    """The CLI applies only full-turn actions; committed turn steps remain unreachable here."""
    exit_code = main(["legal-actions", scenario_path])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "use building: guild to move merchant +1" not in output
