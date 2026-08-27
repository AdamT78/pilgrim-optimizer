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
        "_building_ability_status_text",
        "format_event_for_players",
    }
    assert all(row.positions for row in rows)
