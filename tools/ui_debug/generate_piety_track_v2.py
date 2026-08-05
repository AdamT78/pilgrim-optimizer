"""Write the generated ornamented piety track debug page.

Run from the repo root:

    python3 tools/ui_debug/generate_piety_track_v2.py
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ui_debug.render_piety_track_v2 import (  # noqa: E402
    load_piety_config,
    load_piety_track_v2_layout,
    render_piety_tracks_v2_html,
)

GENERATED_DIRNAME = "generated"
OUTPUT_FILENAME = "piety_tracks_v2.html"


def default_output_path() -> Path:
    return Path(__file__).resolve().parent / GENERATED_DIRNAME / OUTPUT_FILENAME


def generate_piety_track_v2_page(
    *,
    layout_path: Path | None = None,
    piety_config_path: Path | None = None,
    output_path: Path | None = None,
) -> Path:
    destination = default_output_path() if output_path is None else Path(output_path)
    layout = load_piety_track_v2_layout(layout_path)
    piety_config = load_piety_config(piety_config_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_piety_tracks_v2_html(layout, piety_config), encoding="utf-8")
    return destination


def main() -> None:
    written = generate_piety_track_v2_page()
    print(f"wrote {written}")


if __name__ == "__main__":
    main()
