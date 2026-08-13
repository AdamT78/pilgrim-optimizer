"""Write the wax seal debug page.

Run from the repo root:

    python3 tools/ui_debug/generate_seal_prototypes.py

This is the one generator here whose default destination is `prototypes/` rather than the
git-ignored `generated/`. The seal page was never hand-drawn: it came off this script, so there is
no baseline for a renderer to be judged against and nothing would be gained by keeping a second
copy of it. The committed page is this generator's output, and the tests hold it to that, so
running this must leave the working tree clean. The overview still asks for its own copy under
`generated/` like it does for every other view.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ui_debug.render_seal_prototypes import (  # noqa: E402
    check_clearance,
    render_seal_prototypes_html,
)

PROTOTYPES_DIRNAME = "prototypes"
OUTPUT_FILENAME = "seal_prototypes.html"


def default_output_path() -> Path:
    return Path(__file__).resolve().parent / PROTOTYPES_DIRNAME / OUTPUT_FILENAME


def generate_seal_prototypes_page(*, output_path: Path | None = None) -> Path:
    destination = default_output_path() if output_path is None else Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_seal_prototypes_html(), encoding="utf-8")
    return destination


def main() -> None:
    corner, ring, clear = check_clearance()
    written = generate_seal_prototypes_page()
    print(f"glyph corners {corner:.2f} vs ring {ring:.2f} -> {clear:.2f} clear")
    print(f"wrote {written}")


if __name__ == "__main__":
    main()
