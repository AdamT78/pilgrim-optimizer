"""Write the generated player board debug page from the structured layout.

Run from the repo root:

    python3 tools/ui_debug/generate_player_board.py
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ui_debug.render_player_board import (  # noqa: E402
    default_player_state,
    load_player_board_layout,
    render_player_board_html,
)

GENERATED_DIRNAME = "generated"
OUTPUT_FILENAME = "player_board.html"


def default_output_path() -> Path:
    return Path(__file__).resolve().parent / GENERATED_DIRNAME / OUTPUT_FILENAME


def generate_player_board_page(
    *,
    layout_path: Path | None = None,
    output_path: Path | None = None,
    player_state: dict | None = None,
) -> Path:
    destination = default_output_path() if output_path is None else Path(output_path)
    layout = load_player_board_layout(layout_path)
    state = default_player_state() if player_state is None else player_state
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_player_board_html(layout, state), encoding="utf-8")
    return destination


def main() -> None:
    written = generate_player_board_page()
    print(f"wrote {written}")


if __name__ == "__main__":
    main()
