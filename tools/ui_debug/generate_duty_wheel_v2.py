"""Write the generated v2 duty wheel debug page.

Run from the repo root:

    python3 tools/ui_debug/generate_duty_wheel_v2.py

`--baseline` writes the committed pair in `prototypes/` instead of the git-ignored debug copy in
`generated/`. That is the right flag here and the wrong one almost everywhere else in this
folder: this prototype is the renderer's output rather than a hand-drawn baseline it is measured
against, so it is regenerated on purpose when the geometry moves. See the header of
`render_duty_wheel_v2.py`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ui_debug.render_duty_wheel_v2 import (  # noqa: E402
    load_duty_wheel_v2_layout,
    render_duty_wheel_v2_html,
    render_duty_wheel_v2_svg,
)

GENERATED_DIRNAME = "generated"
PROTOTYPES_DIRNAME = "prototypes"
OUTPUT_FILENAME = "duty_wheel_v2.html"
SVG_FILENAME = "duty_wheel_v2.svg"


def default_output_dir(*, baseline: bool = False) -> Path:
    here = Path(__file__).resolve().parent
    return here / (PROTOTYPES_DIRNAME if baseline else GENERATED_DIRNAME)


def generate_duty_wheel_v2_page(
    *,
    layout_path: Path | None = None,
    output_dir: Path | None = None,
    baseline: bool = False,
) -> list[Path]:
    destination = default_output_dir(baseline=baseline) if output_dir is None else Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    layout = load_duty_wheel_v2_layout(layout_path)

    page = destination / OUTPUT_FILENAME
    page.write_text(render_duty_wheel_v2_html(layout), encoding="utf-8")
    written = [page]

    # The SVG baseline is the wheel on its own, with no labels and no page around it -- the thing
    # to drop into a vector editor or into another view, which the HTML is not.
    svg = destination / SVG_FILENAME
    svg.write_text(render_duty_wheel_v2_svg(layout, standalone=True), encoding="utf-8")
    written.append(svg)
    return written


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--baseline", action="store_true",
                    help="write the committed pair in prototypes/ instead of generated/")
    args = ap.parse_args()
    for path in generate_duty_wheel_v2_page(baseline=args.baseline):
        print("wrote %s" % path)


if __name__ == "__main__":
    main()
