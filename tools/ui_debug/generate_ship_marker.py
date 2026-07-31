"""Write the generated ship marker debug page.

Run from the repo root:

    python3 tools/ui_debug/generate_ship_marker.py
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ui_debug.render_ship_marker import (  # noqa: E402
    load_ship_marker_examples,
    render_ship_marker_examples_html,
)

GENERATED_DIRNAME = "generated"
OUTPUT_FILENAME = "ship_marker.html"


def default_output_path() -> Path:
    return Path(__file__).resolve().parent / GENERATED_DIRNAME / OUTPUT_FILENAME


def generate_ship_marker_page(
    *,
    data_path: Path | None = None,
    output_path: Path | None = None,
) -> Path:
    destination = default_output_path() if output_path is None else Path(output_path)
    data = load_ship_marker_examples(data_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_ship_marker_examples_html(data), encoding="utf-8")
    return destination


def main() -> None:
    written = generate_ship_marker_page()
    print(f"wrote {written}")


if __name__ == "__main__":
    main()
