# pilgrim-optimizer

`pilgrim-optimizer` is a Python-first research and optimization project for building a deterministic, headless rules engine for **Pilgrim** (Nick Case), with search and benchmarking layers on top.

## Project Purpose

- Implement clean, testable game rules with immutable/hashable state models.
- Support deterministic transitions and replayable event logs.
- Drive scenarios through JSON files and static config data.
- Build optimization/search workflows only after rules correctness.

## Current Scope (Ruleset A)

- Mancala sandbox with 9 positions (city + 8 duties).
- Directed movement graph and legal route generation.
- Sowing, duty resolution, and tithe placeholder action.
- Duty strength (majority/parity/minority), value, and minority silver cost.
- Deterministic transition pipeline with invariant validation and game events.
- Depth-limited exact search placeholder built on `legal_actions()` + `apply_action()`.

## Not Implemented Yet

- Full Pilgrim board systems (roads, shrines, trade routes, pilgrimage sites).
- Full Duties/Alms/Piety rules, hiring/donations/building stack.
- Endgame scoring completeness.
- Beam search, MCTS, strategy benchmarking at scale.
- UI/visualization.

## Install

Python 3.12+ is required.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Run Tests

```bash
pytest
```

## CLI Usage

Validate a scenario:

```bash
python -m pilgrim.cli validate scenarios/mancala_sandbox_001.json
```

List legal actions:

```bash
python -m pilgrim.cli legal-actions scenarios/mancala_sandbox_001.json
```

Solve with temporary exact search:

```bash
python -m pilgrim.cli solve scenarios/mancala_sandbox_001.json --depth 3
```

## Documentation

- First CLI walkthrough: `docs/usage/cli_commands.md`
- The guide explains the first three CLI commands (`validate`, `legal-actions`, and `solve`).

## Development Principles

- Python first; no UI in early phases.
- Rules engine before optimizer.
- Immutable/hashable states where practical.
- Deterministic transitions and stable action IDs.
- Static game data in config files, not buried in rules code.
- Unit tests from the beginning.
- Small, understandable modules before abstraction.

## Planned Milestones

Milestones and phase details are tracked in `ROADMAP.md`.
