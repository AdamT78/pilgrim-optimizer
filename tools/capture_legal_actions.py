"""Dump the exact legal-action list for every committed and playtest scenario.

The CLI's `legal-actions` summary is human-readable and omits action ids, so it can agree while
the ids underneath have churned. This writes the ids themselves, in generation order, which is the
thing a saved search depends on.
"""

from __future__ import annotations

import sys
from pathlib import Path

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import action_id
from pilgrim.rules.transition import legal_actions

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
            actions = legal_actions(scenario.state, scenario.config)
            body = "\n".join(f"{index}\t{action_id(a)}" for index, a in enumerate(actions))
        except Exception as exc:  # a scenario that cannot load must fail identically, not silently
            body = f"ERROR\t{type(exc).__name__}\t{exc}"
        out.joinpath(f"{path.stem}.txt").write_text(body + "\n", encoding="utf-8")
    print(f"wrote {len(list(out.glob('*.txt')))} files to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
