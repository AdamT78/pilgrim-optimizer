"""Dump the exact turn-step list for every scenario, as a refactor tripwire.

The CLI's turn-step summary is human-readable and omits step ids, so it can agree while the ids
underneath have churned. This writes the ids themselves, in generation order, which is the thing a
saved search depends on.
"""

from __future__ import annotations

import sys
from pathlib import Path

from pilgrim.io.scenarios import load_scenario
from pilgrim.rules.transition import turn_step_id, turn_steps

REPO = Path(__file__).resolve().parents[1]


def main(argv: list[str]) -> int:
    out = Path(argv[0])
    out.mkdir(parents=True, exist_ok=True)
    paths = sorted(
        (
            *REPO.joinpath("scenarios").glob("*.json"),
            *REPO.joinpath("scenarios/playtest").glob("*.json"),
        )
    )
    for path in paths:
        try:
            scenario = load_scenario(path)
            steps = turn_steps(scenario.state, scenario.config)
            body = "\n".join(f"{index}\t{turn_step_id(step)}" for index, step in enumerate(steps))
        except Exception as exc:  # a scenario that cannot load must fail identically, not silently
            body = f"ERROR\t{type(exc).__name__}\t{exc}"
        out.joinpath(f"{path.stem}.txt").write_text(body + "\n", encoding="utf-8")
    print(f"wrote {len(list(out.glob('*.txt')))} files to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
