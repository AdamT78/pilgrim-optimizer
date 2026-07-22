# Mancala (Ruleset A Sandbox)

This repository currently implements a deterministic mancala-like subsystem:

- 9 positions: city + 8 duties.
- Directed graph movement from `configs/board.json`.
- Sowing picks up all acolytes at source and follows a legal route exactly equal to picked count.
- Sowing is followed by a duty or tithe decision.

This is a sandbox for validating engine architecture before broader Pilgrim mechanics.
