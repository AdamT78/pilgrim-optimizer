"""Populate the map from the REAL random setup generator, not the setup page's example schedule.

`tools/ui_debug/generate_game_setup.py` says of its own SETUP_SLOTS that they "stand in for the
real setup generator, which this page deliberately does not call". This does call it: the four
buildings per level and the four pilgrimage sites, and the rounds they go live on, all come from
`pilgrim.setup.generator.generate_setup_scenario`. Only the round -> hex mapping is borrowed from
that page, because the edge path IS the round track and is not the generator's business.

Runs on 3.13 (the package uses `type` statements) and writes an SVG that mkR.py reads, the same
way it reads the duty wheel.
"""
import json, sys
sys.path.insert(0, '.')

from pilgrim.setup.generator import generate_setup_scenario
from tools.ui_debug.generate_game_setup import (
    DEFAULT_START_ROLL, building_by_name, load_building_catalog,
    render_setup_map_svg, rotated_edge_path, start_hex_for_roll,
)
from tools.ui_debug.render_map import load_map_layout
from tools.ui_debug.render_pilgrimage_sites import load_pilgrimage_sites, site_by_index

SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 20260730

scenario = generate_setup_scenario(4, SEED)
timeline = scenario["setup_metadata"]["setup_timeline"]

catalog = load_building_catalog()
by_name = building_by_name(catalog)
by_id = {b.get("id", b["name"].lower().replace(" ", "_")): b for b in catalog["buildings"]}

# round -> what stands on it
schedule = {}
for level, entries in timeline["building_live_rounds"].items():
    for building_id, round_number in entries.items():
        building = by_id.get(building_id)
        if building is None:                       # fall back on the display name
            building = by_name.get(building_id.replace("_", " ").title())
        assert building is not None, building_id
        schedule[round_number] = ("building", building)
for key, round_number in timeline["pilgrimage_rounds"].items():
    index = int(key.rsplit("_", 1)[1]) - 1
    assert round_number not in schedule, f"round {round_number} is double-booked"
    schedule[round_number] = ("site", site_by_index(load_pilgrimage_sites(), index))

path = rotated_edge_path(start_hex_for_roll(DEFAULT_START_ROLL))
placements = []
for round_number in range(1, len(path) + 1):
    kind, payload = schedule.get(round_number, ("empty", None))
    placements.append({
        "round": round_number,
        "label": (payload["name"] if kind == "building" else
                  f"Pilgrimage site" if kind == "site" else "Empty"),
        "kind": kind,
        "hex": path[round_number - 1],
        "building": payload if kind == "building" else None,
        "site": payload if kind == "site" else None,
    })

layout = load_map_layout()
svg = render_setup_map_svg(layout, placements)

# The 18xx-style hex coordinates are build-time furniture -- they exist so a hex can be named
# while the map is being drawn, and nothing in play refers to one. They are TAGGED here rather
# than deleted, so the page can hide them with a rule and they are still there to switch back on.
import re as _re
_LABEL = _re.compile(r'(<text x="[-\d.]+" y="[-\d.]+" font-family="Helvetica, Arial, sans-serif"'
                     r' font-size="%g")' % layout["label_font_size"])
svg, _n_hidden = _LABEL.subn(r'\1 class="hexref"', svg)
assert _n_hidden == 84, _n_hidden          # every coordinate the map draws, and only those
open('/tmp/map_populated.svg', 'w').write(svg)
print("tagged", _n_hidden, "hex coordinate labels as .hexref")

report = [(p["round"], p["hex"], p["kind"], p["label"]) for p in placements if p["kind"] != "empty"]
print("seed", SEED, "| start hex", path[0], "|", len(report), "occupied of", len(path))
for row in report:
    print("  round %2d  %-4s  %-8s %s" % row)
