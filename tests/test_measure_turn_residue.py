"""The measurement has to be readable, and it has to stay pessimistic.

This tool exists to say what the page cannot yet do, and it was believed when it said zero on the
reference board -- because nothing in its output distinguished "there is nothing left to present"
from "this walk never went anywhere that would have asked". Both come out as zero, and only one of
them is good news.

So two things are pinned here. That the output splits those apart, field by field, so a zero cannot
be read as coverage again. And a FLOOR: the numbers we already found by accident on seed 7, named
in full, which the sweep must rediscover. A measurement drifting quietly towards optimism is worse
than no measurement, because it is the one thing anyone would cite as evidence the work is done.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pilgrim.model.duties import DUTY_CATEGORIES
from pilgrim.model.enums import TurnResolutionType
from tools.measure_turn_residue import (
    ASKED,
    NEVER_A_QUESTION,
    NEVER_OFFERED,
    REFUSED,
    TURN_FIELDS,
    generated_board,
    measure,
    sweep,
)

# The conversion fields formerly refused by this measurement are now committed steps and no
# longer belong to the full-turn residue. Keep the zero explicit so a future field-removal change
# cannot silently turn this into an unmeasured claim.
SEED_SEVEN_FLOOR: dict[int, int] = {2: 0, 3: 0, 4: 0}
# Same walk policy as `swept`: reference + generated boards for seed 7 only.
SEED_SEVEN_COVERAGE_FLOOR = 76

SEED_SEVEN_FIELDS: frozenset[str] = frozenset()


@pytest.fixture(scope="module")
def swept() -> dict:
    """The default sweep, once. It is the slowest thing here and every floor test wants it."""
    return sweep(turns=40, policy="coverage", seeds=(7, 99))


def test_seed_seven_still_refuses_exactly_what_it_refused(tmp_path: Path) -> None:
    """The board is measured with the current full-turn field set.

    Exact rather than at-least on the counts. Each number is a property of one seed, one table
    size, one policy and one walk length, all named in the call, so a change in any of them is a
    change in the tool and ought to be looked at rather than absorbed by an inequality.

    Conversion steps are deliberately outside this full-turn residue measurement.
    """
    refused: set[str] = set()
    for player_count, expected in sorted(SEED_SEVEN_FLOOR.items()):
        board = generated_board(player_count, 7, tmp_path)
        result = measure(board, turns=40, policy="first")
        assert result["ambiguous"] == expected, f"{player_count}p seed 7 moved"
        refused |= {name for name, state in result["field_state"].items() if state == REFUSED}

    assert refused == set(SEED_SEVEN_FIELDS)


def test_the_sweep_finds_at_least_what_one_seed_found_by_accident(swept: dict) -> None:
    """A sweep that finds LESS than a single lucky board is broken, not reassuring."""
    refused = {name for name, state in swept["field_state"].items() if state == REFUSED}
    missing = SEED_SEVEN_FIELDS - refused
    assert not missing, f"the sweep lost sight of fields seed 7 refused: {sorted(missing)}"
    assert swept["ambiguous"] >= SEED_SEVEN_COVERAGE_FLOOR


def test_a_zero_cannot_be_read_as_coverage(swept: dict) -> None:
    """The bug this tool had: nothing in the output said what it had never been offered.

    The assertion that matters is the last one. A run reporting no refusals while a quarter of the
    action's fields were never put to it has measured its own line of play, not the game, and the
    report has to be capable of saying so.
    """
    field_state = swept["field_state"]

    assert set(field_state) == set(TURN_FIELDS), "every field on the action, not only the live ones"
    assert set(field_state.values()) <= {REFUSED, ASKED, NEVER_A_QUESTION, NEVER_OFFERED}
    assert any(state == ASKED for state in field_state.values())
    assert any(state == NEVER_OFFERED for state in field_state.values()), (
        "a sweep this short cannot have reached everything; if it claims to, the claim is the bug"
    )


def test_the_coverage_walk_goes_where_the_old_one_never_did() -> None:
    """The second axis, on one board, so the board cannot be what changed.

    The reference board reports no refusals at all under the old policy, and every duty tile it
    holds is a duty tile the coverage policy reaches. Same board, same length, different line of
    play -- which is the whole argument for the policy existing.
    """
    old = measure("scenarios/play_view_reference_4p_001.json", turns=40, policy="first")
    new = measure("scenarios/play_view_reference_4p_001.json", turns=40, policy="coverage")

    assert old["ambiguous"] == 0
    assert new["ambiguous"] == 0
    assert set(old["duties_seen"]) < set(new["duties_seen"])
    assert "allocation" in set(new["duties_seen"])
    assert set(new["duties_seen"]) <= set(DUTY_CATEGORIES)
    assert set(old["resolutions_seen"]) < set(new["resolutions_seen"])
    assert set(new["resolutions_seen"]) <= {member.value for member in TurnResolutionType}


def test_the_same_command_twice_gives_the_same_numbers() -> None:
    """No randomness anywhere in the walk, so a change in the numbers means a change in the code.

    The tie-break is the action id read lexicographically, which is stable under a reordering of
    what `legal_actions` enumerates. Position in the list would pass this test and fail the point
    of it, so the id is what is compared.
    """
    first = measure("scenarios/play_view_reference_4p_001.json", turns=25, policy="coverage")
    again = measure("scenarios/play_view_reference_4p_001.json", turns=25, policy="coverage")

    assert first["ambiguous"] == again["ambiguous"]
    assert first["groups"] == again["groups"]
    assert first["field_state"] == again["field_state"]
    assert first["fields"] == again["fields"]
