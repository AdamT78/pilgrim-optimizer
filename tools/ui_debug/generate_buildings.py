"""Write the generated building tiles debug page from the structured catalog.

Run from the repo root:

    python3 tools/ui_debug/generate_buildings.py
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ui_debug.render_buildings import (  # noqa: E402
    load_building_catalog,
    render_building_catalog_html,
)

GENERATED_DIRNAME = "generated"
OUTPUT_FILENAME = "building_tiles.html"


def default_output_path() -> Path:
    return Path(__file__).resolve().parent / GENERATED_DIRNAME / OUTPUT_FILENAME


def generate_building_tiles_page(
    *,
    catalog_path: Path | None = None,
    output_path: Path | None = None,
) -> Path:
    destination = default_output_path() if output_path is None else Path(output_path)
    catalog = load_building_catalog(catalog_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_building_catalog_html(catalog), encoding="utf-8")
    return destination


def main() -> None:
    written = generate_building_tiles_page()
    print(f"wrote {written}")


if __name__ == "__main__":
    main()
