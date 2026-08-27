from __future__ import annotations

from tools.audits import text_inventory


def test_text_inventory_matches_the_committed_review_table() -> None:
    committed = text_inventory.output_path().read_text(encoding="utf-8")
    assert committed == text_inventory.generate_markdown()


def test_text_inventory_covers_each_player_text_seam() -> None:
    rows = text_inventory.collect_rows()

    assert {row.source for row in rows} == {
        "turn_candidates",
        "_turn_window_prompt",
        "_building_hire_sentence",
        "_building_ability_status_text",
        "format_event_for_players",
    }
    assert all(row.positions for row in rows)


def test_text_inventory_includes_each_hire_source_sentence() -> None:
    rows = text_inventory.collect_rows()
    hire_rows = {
        (row.situation, row.text) for row in rows if row.source == "_building_hire_sentence"
    }

    assert {
        situation for situation, _text in hire_rows
    } == {
        "hire source: live_market_hire",
        "hire source: opponent_active_hire",
    }
    assert (
        "hire source: live_market_hire",
        "Hire Library from market for 1 silver.",
    ) in hire_rows
    assert (
        "hire source: opponent_active_hire",
        "Hire Stone Yard from Yellow for 1 silver.",
    ) in hire_rows
