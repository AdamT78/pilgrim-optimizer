"""Write the generated Alms Table debug page.

Run from the repo root:

    python3 tools/ui_debug/generate_alms_table.py
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ui_debug.render_alms_table import (  # noqa: E402
    load_alms_config,
    load_alms_table_layout,
    render_alms_table_html,
)

GENERATED_DIRNAME = "generated"
OUTPUT_FILENAME = "alms_table.html"


def default_output_path() -> Path:
    return Path(__file__).resolve().parent / GENERATED_DIRNAME / OUTPUT_FILENAME


def generate_alms_table_page(
    *,
    layout_path: Path | None = None,
    alms_config_path: Path | None = None,
    output_path: Path | None = None,
) -> Path:
    destination = default_output_path() if output_path is None else Path(output_path)
    layout = load_alms_table_layout(layout_path)
    config = load_alms_config(alms_config_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        render_alms_table_html(layout, config, interactive=True), encoding="utf-8"
    )
    return destination


def main() -> None:
    written = generate_alms_table_page()
    print(f"wrote {written}")


if __name__ == "__main__":
    main()
