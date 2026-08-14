"""The play view: one engine position drawn on the table layout, and nothing to press.

Same panels as the debug table, in the same places, from the same layout module -- and no controls,
no selects and no script. It is read-only on purpose. Where the debug table is a sandbox whose
buttons move its own SVG about, this draws a position that came from the engine and offers no way
to change it, so anything on it that looks wrong is the engine's or the mapping's and never a
button someone pressed.

WHAT IS REAL AND WHAT IS STILL THE SAMPLE

A page that looks finished while half of it is baked into the layout JSON is worse than one that
obviously is not, so the split is written down rather than left to a screenshot:

  drawn from the scenario   the duty lying at each position, the tithe counter on each space, the
                            space the Merchant stands on, every seat's acolytes on the board, the
                            neutral acolytes, which seats are occupied, the buildings and
                            pilgrimage sites on the rounds they are live on, each seat's
                            wheat/stone/silver, each seat's Alms row, who holds the first player
                            seal, and every line of the log
  still the layout's sample the piety discs, the acolytes inside each player board (village, abbey
                            and roles), and which map hex round 1 starts on
  in the state, drawn here  special activities, committed acolytes, donated buildings, cardinal
  by nothing                favour tiles, victory points, ship position, and trade routes

Run from the repo root to write it out:

    python3 tools/ui_debug/render_play_view.py <scenario.json>
"""

from __future__ import annotations

import json
import sys
from html import escape
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ui_debug.generate_game_setup import (  # noqa: E402  # noqa: E402
    DEFAULT_START_ROLL,
    render_setup_map_svg,
    rotated_edge_path,
    site_by_index,
    start_hex_for_roll,
)
from tools.ui_debug.play_view_adapter import (  # noqa: E402
    acolytes_by_position,
    dummy_acolytes_by_position,
    duty_by_position_name,
    merchant_position_name,
    resources_for,
    seated_player_ids,
    state_header,
    timeline_slots,
    tithe_by_position_name,
)
from tools.ui_debug.render_alms_table import (  # noqa: E402
    load_alms_config,
    load_alms_table_layout,
    render_alms_table_svg,
)
from tools.ui_debug.render_buildings import load_building_catalog  # noqa: E402
from tools.ui_debug.render_duty_wheel import (  # noqa: E402
    load_duty_wheel_layout,
    render_duty_wheel_svg,
)
from tools.ui_debug.render_map import load_map_layout  # noqa: E402
from tools.ui_debug.render_piety_track_v2 import (  # noqa: E402
    load_piety_config,
    load_piety_track_v2_layout,
    render_piety_track_v2_svg,
)
from tools.ui_debug.render_pilgrimage_sites import load_pilgrimage_sites  # noqa: E402
from tools.ui_debug.render_player_boards_v2 import (  # noqa: E402
    load_player_boards_v2_layout,
    player_by_id,
    render_player_board_v2_svg,
    resource_choice_styles,
)
from tools.ui_debug.render_table_layout import (  # noqa: E402
    SEATED_PLAYERS,
    board_measurements,
    crop_svg,
    duty_hexagon,
    regularise_duty_hexagon,
    render_table_stage,
    solve_table_scale,
    table_layout_styles,
    table_stacking_styles,
)

GENERATED_DIRNAME = "generated"
OUTPUT_FILENAME = "play_view.html"
PAGE_TITLE = "Pilgrim — Play View"

CITY_POSITION = 0
TWO_PLAYER_VARIANT = "2_player"
WIDE_VARIANT = "3_4_player"


def default_output_path() -> Path:
    return Path(__file__).resolve().parent / GENERATED_DIRNAME / OUTPUT_FILENAME


def piety_variant_for(seated: list[str]) -> str:
    """Which piety board is on the table. The two-player track is a different board, not a crop."""
    return TWO_PLAYER_VARIANT if len(seated) == 2 else WIDE_VARIANT


def seat_of(player_id: str) -> int:
    """Which chair an engine player sits in. See the adapter's point 3: this is not their index."""
    return SEATED_PLAYERS.index(player_id) + 1


def duty_layout_for(payload: dict, duty_layout: dict) -> dict:
    """The wheel with this scenario's tiles on it, each one lying where the scenario put it.

    This is the position/slot distinction made concrete. A SLOT is a space on the board: it owns a
    centre, a compass point and a position index, and none of those move. A TILE is what lies on
    it: it owns a duty's name and its label, and a scenario deals them out afresh. The layout ships
    the two fused together, because in the default arrangement every tile happens to be on its own
    slot -- which is exactly why reading either one for the other looks correct until the first
    shuffled scenario, and then is wrong on seven spaces out of eight.

    The tithe counter goes with the slot rather than the tile, which is the engine's own answer:
    counters are dealt onto positions after the tiles are shuffled. So the counter drawn here is
    the one the scenario put on that space, not the one the layout drew with that tile.
    """
    duty_at = duty_by_position_name(payload)
    tithe_at = tithe_by_position_name(payload)
    label_of = {duty["id"]: duty["label"] for duty in duty_layout["duties"]}

    tiles = []
    for slot in duty_layout["duties"]:
        position = slot["board_position"]
        if position not in duty_at:
            tiles.append(dict(slot))
            continue
        tile = dict(slot)
        tile["id"] = duty_at[position]
        tile["label"] = label_of[duty_at[position]]
        # Null rather than absent: the renderer reads the key on every duty tile and a space with
        # no counter is a fact about it, not a missing field.
        tile["tithe_icon"] = tithe_at[position]
        tile.pop("sample_cubes", None)
        tiles.append(tile)

    seated = seated_player_ids(payload)
    dummy = dict(duty_layout["dummy_acolytes"])
    dummy["sample_cubes"] = {
        str(len(seated)): {
            duty_at[slot["board_position"]]: count
            for slot, count in zip(tiles, _dummy_per_slot(payload, tiles), strict=True)
            if slot["board_position"] in duty_at and count
        }
    }

    seated_layout = dict(duty_layout)
    seated_layout["duties"] = tiles
    seated_layout["dummy_acolytes"] = dummy
    seated_layout["seats_by_player_count"] = {str(len(seated)): list(seated)}
    seated_layout["player_counts"] = [len(seated)]
    seated_layout["default_player_count"] = len(seated)
    return seated_layout


def _dummy_per_slot(payload: dict, tiles: list[dict]) -> list[int]:
    by_position = dummy_acolytes_by_position(payload)
    return [_position_index(payload, tile, by_position) for tile in tiles]


def _position_index(payload: dict, tile: dict, by_position: list[int]) -> int:
    names = payload["board_positions"]
    position = tile["board_position"]
    return by_position[names.index(position)] if position in names else 0


def merchant_duty_for(payload: dict, duty_layout: dict) -> str:
    """Which tile the Merchant token is drawn on, found by the space it stands on.

    The wheel marks the Merchant by duty id, so a duty id is what comes back -- but it is looked up
    THROUGH the position, never asked for directly. `duty_wheel_layout.json` carries
    `merchant_token.starts_on = "taxation"`, which is the debug page's default and is ignored here:
    the Merchant occupies a space under the current rule, and the tile lying on that space is dealt
    afresh per seed. Asking for Taxation would give a token that follows the Taxation tile around
    the ring instead of standing where the engine put it, which is right only until it advances.
    """
    position = merchant_position_name(payload)
    for tile in duty_layout["duties"]:
        if tile["board_position"] == position:
            return tile["id"]
    raise ValueError(f"No duty tile lies on board position {position!r}.")


def duty_board_state_for(payload: dict, duty_layout: dict) -> dict:
    """How many of each seat's acolytes stand on each space of the wheel.

    Keyed by the duty lying there, because that is what the wheel's own state is keyed by -- but
    read out of the mancala vector by POSITION, which is the index the vector is in. The City is
    index 0 and is a space like any other here.
    """
    names = payload["board_positions"]
    seated = seated_player_ids(payload)
    vectors = {player_id: acolytes_by_position(payload, player_id) for player_id in seated}
    return {
        tile["id"]: {
            player_id: vectors[player_id][names.index(tile["board_position"])]
            for player_id in seated
        }
        for tile in duty_layout["duties"]
        if tile["board_position"] in names
    }


def map_placements_for(payload: dict, catalog: dict, site_data: dict | list) -> list[dict]:
    """The border track: what is standing on each round of it in this scenario.

    Which hex round 1 lands on is still the sample. The engine's timeline is 26 abstract rounds
    and carries no start hex, so the rotation is the map's own and only the CONTENTS are real.
    """
    by_id = {building["id"]: building for building in catalog["buildings"]}
    path = rotated_edge_path(start_hex_for_roll(DEFAULT_START_ROLL))
    placements = []
    for slot in timeline_slots(payload):
        building = by_id[slot["building_id"]] if slot["building_id"] else None
        site = site_by_index(site_data, slot["site_index"] - 1) if slot["site_index"] else None
        placements.append(
            {
                "round": slot["round"],
                "label": _slot_label(slot, building),
                "kind": slot["kind"],
                "hex": path[slot["round"] - 1],
                "building": building,
                "site": site,
            }
        )
    return placements


def _slot_label(slot: dict, building: dict | None) -> str:
    if building is not None:
        return f"{building['name']} (level {building['level']})"
    if slot["site_index"] is not None:
        return f"Pilgrimage site {slot['site_index']}"
    return "Empty"


def render_log_box(payload: dict) -> str:
    """The state header, in the slack the debug table puts its controls in.

    Real content rather than a placeholder: every line is a value read off the state, and the box
    is where this PR's successor will put the event transcript underneath them.
    """
    rows = "".join(
        f'<div class="log-line"><span class="log-key">{escape(key)}</span>'
        f'<span class="log-value">{escape(value)}</span></div>'
        for key, value in state_header(payload)
    )
    # Already formatted when it got here. The sentences are the CLI's own, written by the shared
    # formatter on the engine's side of the seam, so the two accounts of a game cannot drift; an
    # event the formatter declines to describe never becomes a line and is not represented by a
    # blank one.
    entries = "".join(
        f'<div class="log-event">{escape(str(line))}</div>' for line in payload.get("log", ())
    )
    transcript = f'<div class="log-transcript">{entries}</div>' if entries else ""
    return (
        f'<div class="play-log" data-component="play-log">{rows}{transcript}</div>'
        f"{render_turn_panel(payload)}"
    )


def _resolution_keys(candidates: list[dict]) -> str:
    """One key per resolution any candidate offers, all struck here and all hidden.

    The board can be asked for a position by pointing at it. What to DO with a duty is not on the
    board at all, so it needs somewhere to be asked, and the keys are drawn for the same reason the
    seals and the stock keys are: the page reveals one, and never makes one.
    """
    seen: list[str] = []
    for candidate in candidates:
        for step in candidate["steps"]:
            if step["kind"] == "resolution" and step["value"] not in seen:
                seen.append(step["value"])
    return "".join(
        f'<button type="button" class="turn-key" data-resolution-key="{escape(name)}"'
        f' data-turn-offered="false">{escape(name.replace("_", " "))}</button>'
        for name in sorted(seen)
    )


def _combination_keys(candidates: list[dict]) -> str:
    """One key per whole combination any candidate offers, all struck here and all hidden.

    A combination is several amounts that are only legal together, so the key stands for the set of
    them and there is no key for a part of one. Offering the parts separately would let a player
    build a pairing the engine never offered, and the page would then have to know which pairings
    go together -- which is the rule it exists not to hold a copy of.

    The words are the seam's, not this file's. What a combination amounts to is a fact about the
    action, and composing a sentence for it here would be a second description to keep in step.
    """
    seen: dict[str, str] = {}
    for candidate in candidates:
        for step in candidate["steps"]:
            if step["kind"] == "combination":
                seen.setdefault(step["value"], step.get("label", step["value"]))
    return "".join(
        f'<button type="button" class="turn-key" data-combination-key="{escape(value)}"'
        f' data-turn-offered="false">{escape(label)}</button>'
        for value, label in sorted(seen.items())
    )


def _turn_panels(candidates: list[dict]) -> str:
    """What each candidate would say if it were the one left standing, written out in advance.

    Two kinds, and which one a candidate gets is settled here rather than in the browser. A turn
    that is fully decided shows the words it would be committed as -- the CLI's own sentence for
    that action -- above the button that commits it. One that is not shows what is still open.

    Nothing is composed in the page. The script reveals a panel; it never builds a sentence, which
    is the same rule that keeps it from building a route.
    """
    panels = []
    for index, candidate in enumerate(candidates):
        if candidate["action_id"] is not None:
            body = (
                f'<div class="turn-summary">{escape(str(candidate["summary"]))}</div>'
                f'<button type="button" class="turn-commit"'
                f' data-turn-confirm="{escape(str(candidate["action_id"]))}">Confirm this turn'
                "</button>"
            )
        else:
            fields = "".join(
                f'<li class="turn-field">{escape(name)}</li>' for name in candidate["unresolved"]
            )
            body = (
                '<div class="turn-blocked">This turn is not decided yet. '
                f"{candidate['variants']} legal actions match everything asked so far and differ "
                "in fields this page cannot put to you, so it will not choose between them for "
                "you:</div>"
                f'<ul class="turn-fields">{fields}</ul>'
            )
        panels.append(f'<div class="turn-panel" data-turn-panel="{index}">{body}</div>')
    return "".join(panels)


def render_turn_panel(payload: dict) -> str:
    """Where a turn is answered and agreed to, beside the log rather than on the board."""
    candidates = payload.get("turn_candidates") or []
    if not candidates:
        return ""
    return (
        '<div class="play-turn" data-component="play-turn">'
        f'<div class="turn-keys">{_resolution_keys(candidates)}'
        f"{_combination_keys(candidates)}</div>"
        f"{_turn_panels(candidates)}"
        '<button type="button" class="turn-reset" data-turn-reset data-turn-started="false">'
        "Start this turn again</button>"
        "</div>"
    )


def log_styles() -> str:
    return """  /* The log stands in the slack under the Alms Table, the same slot the debug table
     puts its control stack in. It is the one place the two pages differ. */
  .play-log {
    width: 100%; color: #F2EEDF; font: 13px/1.5 Helvetica, Arial, sans-serif;
    background: #101010; border: 1px solid #333333; border-radius: 10px;
    padding: 10px 12px;
  }
  .log-line { display: flex; justify-content: space-between; gap: 12px; }
  .log-key { color: #9A9A9A; }
  .log-value { color: #F2EEDF; text-align: right; }
  .log-transcript {
    margin-top: 8px; padding-top: 8px; border-top: 1px solid #333333;
    max-height: 220px; overflow-y: auto;
  }
  .log-event { color: #C9C4B4; font-size: 12px; margin-bottom: 3px; }

  /* Visibility, not display: an empty chair keeps its width so the seated ones stay where the
     table would put them. At two players those are the two ends of the row, not the first two. */
  .p-player[data-seat-taken="false"] { visibility: hidden; }"""


_TURN_SCRIPT = """<script>
(function () {
  'use strict';
  /* CLICKING FILTERS. IT DOES NOT CONSTRUCT.

     Every candidate below is an answer the engine already offered, carrying the sequence of
     decisions that reaches it: where to pick up from, each step of the route, which duty was
     selected, and what to do with it. This narrows that list. It never builds a route, never asks
     whether a step is allowed, never decides what lies next to what, and never counts how long a
     route should be -- routes are as long as they are. An illegal turn cannot be expressed here
     because it was never in the list to begin with. */
  var CANDIDATES = __CANDIDATES__;
  var TOKEN = __TOKEN__;
  if (!CANDIDATES.length) { return; }

  var board = document.querySelector('[data-component="duty-wheel"]');
  var aside = document.querySelector('[data-component="play-turn"]');
  if (!board || !aside) { return; }
  var spaces = board.querySelectorAll('[data-board-position-index]');
  var keys = aside.querySelectorAll('[data-resolution-key]');
  var pairs = aside.querySelectorAll('[data-combination-key]');
  var panels = aside.querySelectorAll('[data-turn-panel]');
  var reset = aside.querySelector('[data-turn-reset]');
  /* Every seat's board, so the one being asked can be picked out of them and the rest left alone.
     Which seat that is is read off the page, where it is already written down, rather than worked
     out here from whose turn it might be. */
  var seats = document.querySelectorAll('[data-component="player-board-v2"][data-player-seat]');
  var chosen = [];

  function surviving() {
    return CANDIDATES.filter(function (candidate) {
      return chosen.every(function (answer, index) {
        var step = candidate.steps[index];
        return step !== undefined && step.value === answer;
      });
    });
  }

  function stepsAt(index, live) {
    var seen = [];
    live.forEach(function (candidate) {
      var step = candidate.steps[index];
      if (!step) { return; }
      var known = seen.some(function (other) {
        return other.kind === step.kind && other.value === step.value;
      });
      if (!known) { seen.push(step); }
    });
    return seen;
  }

  function submit(actionId) {
    var request = new XMLHttpRequest();
    request.open('POST', '/action', true);
    request.setRequestHeader('Content-Type', 'application/json');
    request.onload = function () {
      /* The server sends the whole page back, drawn from the state it now holds. Swapping it in
         is the only way anything on this board changes: nothing here draws a piece. */
      if (request.status !== 200) { window.alert('refused: ' + request.responseText); return; }
      document.open();
      document.write(request.responseText);
      document.close();
    };
    request.send(JSON.stringify({ action_id: actionId, state_token: TOKEN }));
  }

  /* A step says how it is answered and this sorts them by that, so a new kind of question is a new
     bucket here and nothing else. No step is recognised by what it is ABOUT: there is no field
     name anywhere in this file, and a page that told a tithe's stock from a taxation's would be
     one that had to be taught about the next one. */
  function offeredByKind(offered, kind) {
    var values = [];
    offered.forEach(function (step) {
      if (step.kind === kind) { values.push(step.value); }
    });
    return values;
  }

  function mark(elements, attribute, values) {
    Array.prototype.forEach.call(elements, function (element) {
      var name = element.getAttribute(attribute);
      element.setAttribute('data-turn-offered', values.indexOf(name) === -1 ? 'false' : 'true');
    });
  }

  function show(offered, settled) {
    var positions = offeredByKind(offered, 'position');
    var stocks = offeredByKind(offered, 'resource');
    Array.prototype.forEach.call(spaces, function (space) {
      var index = Number(space.getAttribute('data-board-position-index'));
      space.setAttribute('data-play-offered', positions.indexOf(index) === -1 ? 'false' : 'true');
      space.setAttribute('data-play-chosen', chosen.indexOf(index) === -1 ? 'false' : 'true');
    });
    mark(keys, 'data-resolution-key', offeredByKind(offered, 'resolution'));
    mark(pairs, 'data-combination-key', offeredByKind(offered, 'combination'));
    /* A stock is picked on the board of the seat whose stock it is, and on no other. The other
       three are not merely unlit: their keys are marked unoffered too, so a key that something
       else revealed still cannot be pressed. Nobody reaches across the table. */
    Array.prototype.forEach.call(seats, function (seat) {
      var asking = stocks.length && seat.getAttribute('data-active-seat') === 'true';
      if (asking) { seat.setAttribute('data-resource-choice', 'true'); }
      else { seat.removeAttribute('data-resource-choice'); }
      mark(seat.querySelectorAll('[data-resource-choice-key]'), 'data-resource-choice-key',
           asking ? stocks : []);
    });
    Array.prototype.forEach.call(panels, function (panel) {
      var index = Number(panel.getAttribute('data-turn-panel'));
      panel.setAttribute('data-turn-shown', index === settled ? 'true' : 'false');
    });
    if (reset) { reset.setAttribute('data-turn-started', chosen.length ? 'true' : 'false'); }
  }

  function render() {
    var live = surviving();
    /* A step every survivor agrees on is not a choice, so it is taken rather than asked about.
       Which steps those are is not written down anywhere; it falls out of the candidates. */
    while (live.length > 1 && stepsAt(chosen.length, live).length === 1) {
      chosen.push(stepsAt(chosen.length, live)[0].value);
      live = surviving();
    }
    /* Nothing is sent on reaching one candidate. Its panel is revealed -- either the words it
       would be committed as, over the button that commits it, or what is still undecided about
       it -- and the player says so. */
    if (live.length === 1) { show([], CANDIDATES.indexOf(live[0])); return; }
    show(stepsAt(chosen.length, live), -1);
  }

  Array.prototype.forEach.call(spaces, function (space) {
    space.addEventListener('click', function () {
      if (space.getAttribute('data-play-offered') !== 'true') { return; }
      chosen.push(Number(space.getAttribute('data-board-position-index')));
      render();
    });
  });

  /* Three kinds of key, answered the same way: press one that is offered and it becomes the next
     answer. What the key stands for is the attribute it carries, and this does not read it. */
  function answers(elements, attribute) {
    Array.prototype.forEach.call(elements, function (key) {
      key.addEventListener('click', function () {
        if (key.getAttribute('data-turn-offered') !== 'true') { return; }
        chosen.push(key.getAttribute(attribute));
        render();
      });
    });
  }

  answers(keys, 'data-resolution-key');
  answers(pairs, 'data-combination-key');
  Array.prototype.forEach.call(seats, function (seat) {
    answers(seat.querySelectorAll('[data-resource-choice-key]'), 'data-resource-choice-key');
  });

  Array.prototype.forEach.call(panels, function (panel) {
    var commit = panel.querySelector('[data-turn-confirm]');
    if (commit) {
      commit.addEventListener('click', function () {
        submit(commit.getAttribute('data-turn-confirm'));
      });
    }
  });

  if (reset) {
    /* Purely local. Nothing has been sent, because nothing is sent until the player presses
       confirm, so giving up is forgetting the clicks rather than undoing anything. */
    reset.addEventListener('click', function () { chosen = []; render(); });
  }

  render();
})();
</script>"""


def turn_styles(route_color: str) -> str:
    """What the attributes the script sets do, and the only place any of it is a colour.

    Every affordance is drawn by the renderer and hidden here; the script flips an attribute
    between true and false and does nothing else. No position and no colour crosses into
    JavaScript -- the colour of the route is the active seat\'s own, written in by the page that
    knows which seat that is.

    The whole space is the target rather than the artwork on it: `.board-circle` is the space\'s
    filled shape, so a click anywhere on the parchment counts and nobody has to hit a label.
    """
    return f"""  /* Hidden by default: a space is offered only while it is one of the moves left. */
  [data-play-offered="true"] {{ cursor: pointer; }}
  [data-play-offered="true"] .board-circle {{ stroke: #F2EEDF; stroke-width: 4; }}
  [data-play-chosen="true"] .board-circle {{ stroke: {route_color}; stroke-width: 5.5; }}

  .play-turn {{
    width: 100%; margin-top: 10px; color: #F2EEDF; font: 13px/1.5 Helvetica, Arial, sans-serif;
    background: #101010; border: 1px solid #333333; border-radius: 10px; padding: 10px 12px;
  }}
  .turn-keys {{ display: flex; flex-wrap: wrap; gap: 6px; }}
  .turn-key, .turn-commit, .turn-reset {{
    color: #F2EEDF; background: #1C1C1C; border: 1px solid #3A3A3A; border-radius: 8px;
    padding: 6px 10px; cursor: pointer; font: 13px/1.4 Helvetica, Arial, sans-serif;
  }}
  /* A key is only pressable while it is one of the answers still standing. Resolutions and whole
     combinations are both keys and both hide the same way. */
  .turn-key {{ display: none; }}
  .turn-key[data-turn-offered="true"] {{ display: inline-block; }}

{resource_choice_styles()}
  /* The board renderer draws all three stock keys and the rule above shows them together. A stock
     the surviving turns do not offer is taken back out again here, so the seat is never shown a
     key it cannot press. Visibility only: the pill, the keyline and where it sits are the
     renderer's, as they are for the seals. */
  [data-resource-choice-key][data-turn-offered="false"] {{ visibility: hidden; }}

  /* One panel per candidate, all drawn, all hidden until its candidate is the one left. */
  .turn-panel {{ display: none; }}
  .turn-panel[data-turn-shown="true"] {{ display: block; }}
  .turn-summary {{ margin: 8px 0; color: #F2EEDF; }}
  .turn-commit {{ width: 100%; border-color: {route_color}; }}
  .turn-blocked {{ margin: 8px 0; color: #E0C36A; }}
  .turn-fields {{ margin: 0 0 4px 0; padding-left: 18px; color: #C9C4B4; }}
  .turn-field {{ font-family: Menlo, monospace; font-size: 12px; }}

  .turn-reset {{ display: none; margin-top: 8px; width: 100%; }}
  .turn-reset[data-turn-started="true"] {{ display: block; }}"""


def render_play_view_html(
    payload: dict,
    map_layout: dict,
    piety_layout: dict,
    piety_config: dict,
    catalog: dict,
    site_data: dict | list,
    board_layout: dict,
    duty_wheel_layout: dict,
    alms_layout: dict,
    alms_config: dict,
) -> str:
    seated = seated_player_ids(payload)
    scenario_duty = duty_layout_for(payload, duty_wheel_layout)
    piety_variant = piety_variant_for(seated)

    content, hexes, cubes = board_measurements(
        alms_layout, piety_layout, board_layout, duty_wheel_layout, map_layout, piety_variant
    )
    scale = solve_table_scale(content, hexes, cubes)
    hexagon = duty_hexagon(duty_wheel_layout)

    alms_svg = crop_svg(
        render_alms_table_svg(
            alms_layout,
            alms_config,
            {player_id: _alms_row(payload, player_id) for player_id in seated},
        ),
        scale.crop["alms"],
    )
    piety_svg = crop_svg(
        render_piety_track_v2_svg(
            piety_layout,
            piety_config,
            piety_variant,
            seat_of(payload["state"]["start_player_id"]),
        ),
        scale.crop["piety"],
    )
    duty_svg = crop_svg(
        regularise_duty_hexagon(
            render_duty_wheel_svg(
                scenario_duty,
                duty_board_state_for(payload, scenario_duty),
                merchant_on=merchant_duty_for(payload, scenario_duty),
            ),
            hexagon,
        ),
        scale.crop["action"],
    )
    map_svg = crop_svg(
        render_setup_map_svg(map_layout, map_placements_for(payload, catalog, site_data)),
        scale.crop["map"],
    )

    candidates = payload.get("turn_candidates") or []
    panels = []
    for seat, player_id in enumerate(SEATED_PLAYERS, start=1):
        # An empty chair is still drawn and then hidden, exactly as the debug table hides one: a
        # chair removed from the row would let the occupied ones slide along it, and at two players
        # the two who are seated are the two ENDS of the row rather than the first two of it.
        taken = player_id in seated
        player = player_by_id(board_layout, player_id)
        # The three stock keys, drawn hidden on every seat's board because which seat will be asked
        # is not known until a turn is part-built. Only the asking seat's are ever revealed, and
        # `resource_choice_styles` is what reveals them.
        board = render_player_board_v2_svg(
            _board_layout_for(payload, board_layout, player_id),
            player,
            choice_keys=bool(candidates),
        )
        active = taken and player_id == payload["state"]["active_player"]
        panels.append(
            f'<div class="panel p-player" data-component="player-board-v2"'
            f' data-player-seat="{seat}" data-player="{player_id}"'
            f' data-player-color="{player["color"]}"'
            f' data-seat-taken="{str(taken).lower()}"'
            f' data-active-seat="{str(active).lower()}">'
            f"{crop_svg(board, scale.crop['player'])}</div>"
        )

    active_seat = seat_of(payload["state"]["active_player"])
    active_color = player_by_id(board_layout, payload["state"]["active_player"])["fill"]
    # Both are opt-in, the way the choice keys and the extra seals are: a position with nothing to
    # decide is a page with nothing to press, and it should not be carrying the styles for
    # affordances that can never appear on it.
    script = (
        _TURN_SCRIPT.replace("__CANDIDATES__", json.dumps(candidates)).replace(
            "__TOKEN__", json.dumps(payload.get("state_token", ""))
        )
        if candidates
        else ""
    )
    turn_css = turn_styles(active_color) if candidates else ""
    stage = render_table_stage(
        alms_svg=alms_svg,
        piety_svg=piety_svg,
        duty_svg=duty_svg,
        map_svg=map_svg,
        seats="\n      ".join(panels),
        stage_attributes=f'data-active-player-seat="{active_seat}"',
        under_alms=render_log_box(payload),
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{PAGE_TITLE}</title>
<style>
{table_layout_styles(scale)}

{log_styles()}
  /* Whose turn it is, said the same way the debug table says it: the seat's own board carries
     the wash, and this only stops hiding it. Nothing is restyled and nothing moves. */
  .p-player[data-active-seat="true"] [data-active-player-glow="true"] {{ opacity: 1; }}

{turn_css}

{table_stacking_styles(scale)}
</style>
</head>
<body>
{stage}
{script}</body>
</html>
"""


def _alms_row(payload: dict, player_id: str) -> int:
    from tools.ui_debug.play_view_adapter import player_record

    record = player_record(payload, player_id)
    return int(record["alms_position"]) if record else 0


def _board_layout_for(payload: dict, board_layout: dict, player_id: str) -> dict:
    """This seat's board layout, with its own three stocks written into it.

    The renderer reads the amounts off the layout, so a seat with different stocks needs its own
    copy of it. Only the counts change; every piece of geometry is the shared one.
    """
    stocks = resources_for(payload, player_id)
    seat_layout = dict(board_layout)
    seat_layout["resources"] = [
        dict(resource, count=stocks.get(resource["id"], resource["count"]))
        for resource in board_layout["resources"]
    ]
    return seat_layout


def render_play_view_from_payload(payload: dict) -> str:
    """The page, from the payload alone, with every layout loaded from its own file."""
    return render_play_view_html(
        payload,
        load_map_layout(),
        load_piety_track_v2_layout(),
        load_piety_config(),
        load_building_catalog(),
        load_pilgrimage_sites(),
        load_player_boards_v2_layout(),
        load_duty_wheel_layout(),
        load_alms_table_layout(),
        load_alms_config(),
    )


def generate_play_view_page(payload: dict, output_path: Path | None = None) -> Path:
    destination = default_output_path() if output_path is None else Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_play_view_from_payload(payload), encoding="utf-8")
    return destination


def main(argv: list[str] | None = None) -> int:
    """Write the page from a payload file, so it can be reviewed and diffed like any other page.

    The payload is what `pilgrim.io.view.view_payload` produces. Taking it from a file rather than
    from a scenario is what keeps this side of the line free of the engine: `tools/play_server.py`
    knows how to make one, and so does any hand-written fixture.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("usage: render_play_view.py <payload.json> [output.html]", file=sys.stderr)
        return 2
    payload = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    output = Path(args[1]) if len(args) > 1 else None
    print(f"wrote {generate_play_view_page(payload, output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
