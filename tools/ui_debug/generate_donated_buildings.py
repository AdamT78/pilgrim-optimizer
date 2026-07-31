"""Write the generated donated/flipped building tiles debug page.

Run from the repo root:

    python3 tools/ui_debug/generate_donated_buildings.py
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ui_debug.render_donated_buildings import (  # noqa: E402
    load_donated_building_tiles,
    render_donated_building_tiles_html,
)

GENERATED_DIRNAME = "generated"
OUTPUT_FILENAME = "donated_building_tiles.html"


def default_output_path() -> Path:
    return Path(__file__).resolve().parent / GENERATED_DIRNAME / OUTPUT_FILENAME


def generate_donated_building_tiles_page(
    *,
    data_path: Path | None = None,
    output_path: Path | None = None,
) -> Path:
    destination = default_output_path() if output_path is None else Path(output_path)
    data = load_donated_building_tiles(data_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_donated_building_tiles_html(data), encoding="utf-8")
    return destination


def main() -> None:
    written = generate_donated_building_tiles_page()
    print(f"wrote {written}")


if __name__ == "__main__":
    main()
