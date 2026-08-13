"""Write `generated/play_view.html` from a scenario that lives in the repository.

WHY THIS EXISTS

Every other page under `tools/ui_debug/generated/` is rebuilt by a `generate_*.py` that reads
committed data -- a layout JSON, a config, a catalog. The play view was not: it was written once
from a payload handed to `render_play_view.py` on the command line, and that payload was not kept.

Nothing reproduced it, so rebuilding the pages and comparing them against copies -- the one honest
way to show a generated page did not move, since `generated/` is git-ignored and `git diff` there
reports nothing -- silently skipped this one. It compared identical because nothing had regenerated
it, not because it still rendered the same, and it would have gone on comparing identical through
any change to the adapter, the renderers or the view payload. This makes it a page like the others.

WHICH SCENARIO, AND WHY

`scenarios/play_view_reference_4p_001.json`, which is `generate-setup --players 4 --seed 99` with
nothing done to it since.

  - Four players, so every seat is drawn. The three- and four-player piety variant and a full row
    of player boards only appear at four; a two-player page leaves half the renderers unexercised,
    and the setup sow fixtures already in `scenarios/` are all two- or three-handed.
  - Freshly dealt and still in SETUP_SOW, which is the position this page is now for. The eighty-odd
    four-player scenarios are rule fixtures, each built around one rule and most of them without a
    dealt board at all -- no duty tiles laid, no tithe counters, no pilgrimage rolls.
  - Seed 99 is the one `tools/play_server.py` names in its own instructions and the tests use, so
    the committed page is the position somebody following those instructions actually sees.

WHY THIS FILE IS NOT UNDER tools/ui_debug

It imports the engine to turn a scenario into a payload, and nothing under `tools/ui_debug` may --
the seam is what keeps the whole UI testable against hand-written JSON with no engine in the room,
and a test enforces it. This is the same reason `tools/play_server.py` lives here.

The cost is that `generate_debug_overview.py` cannot call this, because it is on the other side of
that line. So rebuilding every page means running this one too:

    python3 tools/ui_debug/generate_debug_overview.py
    python3 tools/generate_play_view.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pilgrim.io.scenarios import load_scenario  # noqa: E402
from pilgrim.io.view import view_payload  # noqa: E402
from tools.ui_debug.render_play_view import generate_play_view_page  # noqa: E402

REFERENCE_SCENARIO = (
    Path(__file__).resolve().parents[1] / "scenarios" / "play_view_reference_4p_001.json"
)


def default_scenario_path() -> Path:
    return REFERENCE_SCENARIO


def generate_play_view_from_scenario(
    scenario_path: Path | None = None, output_path: Path | None = None
) -> Path:
    """Load the scenario, ask the engine what the position looks like, and draw it.

    The payload is derived every time rather than stored, so there is one thing to keep -- the
    scenario -- and no second artefact that can drift out of step with what `view_payload` now
    produces. Nothing is added to it here: the page comes out static, with no candidates and so no
    script and no affordances, which is what a file with no server behind it should be.
    """
    scenario = load_scenario(
        str(default_scenario_path() if scenario_path is None else scenario_path)
    )
    return generate_play_view_page(view_payload(scenario.state, scenario.config), output_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--scenario", type=Path, default=None, help="Defaults to the reference one."
    )
    parser.add_argument("--output", type=Path, default=None, help="Defaults to generated/.")
    args = parser.parse_args(argv)
    print(f"wrote {generate_play_view_from_scenario(args.scenario, args.output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
