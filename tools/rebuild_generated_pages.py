"""Rebuild every generated debug page, in one command, and say what it wrote.

WHY THIS EXISTS

Rebuilding used to be two commands, because `generate_debug_overview.py` cannot reach the play
view: that page needs the engine to turn a scenario into a payload, and nothing under
`tools/ui_debug` may import the engine. The README said to run both. But a rebuild step that has
to be remembered is the same failure the play view already had once -- the page silently not
rebuilt while the sweep it was checked by reported nothing but greens. Documenting the second
command makes it skippable; this makes it structural.

The rebuild is only half of it. `generated/` is git-ignored, so the only way to show a page did not
move is to copy it, rebuild, and diff. That check is worth exactly as much as the rebuild behind it
is complete: a page nothing rebuilds compares identical forever, through any change to anything it
is drawn from. So this also CHECKS ITS OWN COVERAGE. Every `.html` sitting in the output directory
that no generator wrote is reported as a fossil and fails the run, which is the state the play view
was in before it was pointed at a committed scenario.

WHAT IT RUNS

The existing generators, called rather than copied. `generate_debug_views()` already builds the
fifteen pages on the drawing side, each by calling that page's own `generate_*_page()`, and
`tools/generate_play_view.py` builds the sixteenth. There is nothing here to keep in step with
them beyond those two calls.

The individual commands are untouched and still work. This adds a way to run them all at once.

WHY THIS FILE IS NOT UNDER tools/ui_debug

It calls `tools/generate_play_view.py`, which imports the engine, and a test forbids that anywhere
under `tools/ui_debug`. Same reason `play_server.py` and `generate_play_view.py` live here.

    python3 tools/rebuild_generated_pages.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.generate_play_view import generate_play_view_from_scenario  # noqa: E402
from tools.ui_debug.generate_debug_overview import (  # noqa: E402
    default_output_dir,
    generate_debug_views,
)
from tools.ui_debug.render_play_view import OUTPUT_FILENAME as PLAY_VIEW_FILENAME  # noqa: E402


class UnrebuiltPage(Exception):
    """A page is sitting in the output directory that nothing in this rebuild wrote."""


def rebuild_generated_pages(output_dir: Path | None = None) -> list[Path]:
    """Rebuild every page and return them, newest write last.

    Both sides in one call, so the ordering is not something anyone has to get right. The play
    view goes last only because it is the one that has to be asked for separately; nothing depends
    on the order.
    """
    destination = default_output_dir() if output_dir is None else Path(output_dir)
    views = generate_debug_views(output_dir=destination)
    play_view = generate_play_view_from_scenario(output_path=destination / PLAY_VIEW_FILENAME)
    return [*views.as_tuple(), play_view]


def unrebuilt_pages(written: list[Path], output_dir: Path) -> list[Path]:
    """Pages in the directory that this rebuild did not write.

    The check the rebuild exists to make possible. A page nothing rebuilds still answers a
    copy-and-diff comparison, and answers it identically forever, so finding one is finding a
    result that has stopped meaning anything rather than merely an untidy directory.
    """
    rebuilt = {path.resolve() for path in written}
    return sorted(p for p in output_dir.glob("*.html") if p.resolve() not in rebuilt)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-dir", type=Path, default=None, help="Defaults to generated/.")
    args = parser.parse_args(argv)

    destination = default_output_dir() if args.output_dir is None else args.output_dir
    written = rebuild_generated_pages(args.output_dir)

    # Named one per line rather than counted, so a page that quietly stopped being built is
    # something you can see is missing instead of having to work out from a total.
    for path in sorted(written):
        print(f"wrote {path.relative_to(Path.cwd()) if path.is_relative_to(Path.cwd()) else path}")
    print(f"{len(written)} pages")

    stale = unrebuilt_pages(written, destination)
    if stale:
        for path in stale:
            print(f"NOT REBUILT: {path.name}", file=sys.stderr)
        print(
            f"{len(stale)} page(s) in {destination} are built by nothing. Until something builds "
            "them, comparing them against a before-copy proves only that nobody touched the file.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
