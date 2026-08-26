"""Small shared helpers for deterministic audit output."""

from __future__ import annotations

from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _format_bounded_count(value: int, *, truncated: bool) -> str:
    return f">={value}" if truncated else str(value)
