"""Catalogue and token invariants for building tooltips."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pilgrim.rules.building_turn_modifiers import all_building_turn_modifiers
from tools.ui_debug.render_buildings import load_building_catalog
from tools.ui_debug.render_play_view import (
    _catalog_with_engine_metadata,
    _description_html,
)


CATALOG_PATH = Path(__file__).resolve().parents[1] / "configs" / "buildings.json"
CATEGORIES = {"Conversion", "Duty Bonus", "Movement", "Utility"}


def _catalogue() -> list[dict]:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))["catalogue"]


def test_every_building_has_the_requested_category_and_description() -> None:
    entries = _catalogue()
    assert len(entries) == 24
    assert all(entry["description"].strip() for entry in entries)
    assert all(entry["category"] in CATEGORIES for entry in entries)
    assert {entry["category"] for entry in entries} == CATEGORIES
    assert {category: sum(entry["category"] == category for entry in entries) for category in CATEGORIES} == {
        "Conversion": 4,
        "Duty Bonus": 9,
        "Movement": 5,
        "Utility": 6,
    }


def test_movement_category_is_derived_from_the_turn_modifier_registry() -> None:
    catalogue_movement = {entry["id"] for entry in _catalogue() if entry["category"] == "Movement"}
    registry_movement = {entry.building_key for entry in all_building_turn_modifiers()}
    assert len(registry_movement) == 5
    assert catalogue_movement == registry_movement


def test_play_catalogue_joins_visual_buildings_to_engine_metadata() -> None:
    catalog = _catalog_with_engine_metadata(load_building_catalog())
    assert len(catalog["buildings"]) == 24
    assert all(building["description"] and building["category"] for building in catalog["buildings"])


def test_resource_tokens_are_explicit_and_unknown_tokens_fail() -> None:
    rendered = _description_html("Stone Yard sells {stone} for {silver}; Stone stays text.")
    assert "{stone}" not in rendered and "{silver}" not in rendered
    assert rendered.count('data-tooltip-resource="stone"') == 1
    assert rendered.count('data-tooltip-resource="silver"') == 1
    assert 'data-tooltip-resource="wheat"' not in _description_html("Stone Yard and Grain Store")
    with pytest.raises(ValueError, match="unknown resource token"):
        _description_html("Unknown {piety_token}")

