"""The play view: one engine position drawn on the table layout, with only seam-driven choices.

Same panels as the debug table, in the same places, from the same layout module. Unlike that
sandbox, this page does not invent a move and does not carry a second rules copy: its script only
filters and reveals the candidates the server already offered, previews the route those candidates
already contain, and submits one action id back.

WHAT IS REAL AND WHAT IS STILL THE SAMPLE

A page that looks finished while half of it is baked into the layout JSON is worse than one that
obviously is not, so the split is written down rather than left to a screenshot:

  drawn from the scenario   the duty lying at each position, the tithe counter on each space, the
                            space the Merchant stands on, every seat's acolytes on the board, the
                            neutral acolytes, which seats are occupied, the buildings and
                            pilgrimage sites on the rounds they are live on, each seat's
                            wheat/stone/silver, each seat's Alms row, who holds the first player
                            seal, the acolytes inside each player board -- village, abbey and the
                            six role circles -- the buildings standing in each seat's slots and
                            which of them were donated, how far around the ring the ship has come,
                            and every line of the log
  still the layout's sample which map hex round 1 starts on for payloads without setup metadata;
                            generated setups carry the NW roll that pins the physical ring and the
                            ship is counted around it
  in the state, with        committed acolytes, which stand on roads, shrines, market ports and
  nowhere to draw it        pilgrimage sites -- none of which this page draws at all; cardinal
                            favour tiles, which have no area on the player board; victory points,
                            which have no readout anywhere; and trade routes, which come from map
                            tile placement and are deferred

The last row is the one to read carefully: those need a place on the board decided first, and no
amount of wiring will produce one.

Run from the repo root to write it out:

    python3 tools/ui_debug/render_play_view.py <scenario.json>
"""

from __future__ import annotations

import json
import re
import sys
from html import escape
from pathlib import Path
from string import Template

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ui_debug.generate_game_setup import (  # noqa: E402  # noqa: E402
    DEFAULT_START_ROLL,
    START_HEX_BY_ROLL,
    building_choice_styles,
    render_board_slot_building,
    render_board_slot_donated,
    render_setup_map_svg,
    rotated_edge_path,
    site_by_index,
    start_hex_for_roll,
)
from tools.ui_debug.play_view_adapter import (  # noqa: E402
    acolytes_by_position,
    dummy_acolytes_by_position,
    duty_by_position_name,
    first_player_seat,
    merchant_position_name,
    piety_by_player,
    played_this_round,
    player_record,
    resources_for,
    seated_player_ids,
    state_header,
    timeline_slots,
    tithe_by_position_name,
)
from tools.ui_debug.render_alms_table import (  # noqa: E402
    alms_rules,
    disc_targets,
    load_alms_config,
    load_alms_table_layout,
    render_alms_table_svg,
)
from tools.ui_debug.render_buildings import load_building_catalog  # noqa: E402
from tools.ui_debug.render_donated_buildings import (  # noqa: E402
    load_donated_building_tiles,
    tiles_of,
)
from tools.ui_debug.render_duty_wheel import (  # noqa: E402
    CITY_SPOKE_REVERSAL_ARROWS,
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
    BUILDING_SLOT_HEX_SIZE,
    _ICON_RENDERERS,
    default_player_board_v2_state,
    load_player_boards_v2_layout,
    player_by_id,
    resource_icon_size,
    render_player_board_v2_svg,
    resource_choice_styles,
    seat_choice_styles,
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

ENGINE_BUILDINGS_PATH = Path(__file__).resolve().parents[2] / "configs" / "buildings.json"
RESOURCE_TOKEN_ICONS = {"wheat": "wheat", "stone": "cube", "silver": "coin"}
TOOLTIP_DECKLE_POINTS = (
    (0, 13),
    (6, 7),
    (16, 11),
    (30, 6),
    (46, 11),
    (62, 6),
    (78, 11),
    (91, 7),
    (100, 13),
    (98, 38),
    (100, 78),
    (96, 100),
    (84, 96),
    (70, 100),
    (55, 96),
    (39, 100),
    (25, 96),
    (9, 100),
    (1, 94),
    (3, 55),
)
TOOLTIP_CLIP_PATH = "polygon(" + ", ".join(f"{x}% {y}%" for x, y in TOOLTIP_DECKLE_POINTS) + ")"
TOOLTIP_DECKLE_SVG_POINTS = " ".join(f"{x},{y}" for x, y in TOOLTIP_DECKLE_POINTS)

CITY_POSITION = 0
TWO_PLAYER_VARIANT = "2_player"
WIDE_VARIANT = "3_4_player"
TURN_PHASE_DIM_COLOR = "#6B675E"
TURN_PHASE_CURRENT_COLOR = "#5FBF6E"


def default_output_path() -> Path:
    return Path(__file__).resolve().parent / GENERATED_DIRNAME / OUTPUT_FILENAME


def piety_variant_for(seated: list[str]) -> str:
    """Which piety board is on the table. The two-player track is a different board, not a crop."""
    return TWO_PLAYER_VARIANT if len(seated) == 2 else WIDE_VARIANT


def seat_of(player_id: str) -> int:
    """Which chair an engine player sits in."""
    return SEATED_PLAYERS.index(player_id) + 1


def _seat_colours() -> dict[str, str]:
    """What each engine player is called at the table, from the layout that already says so."""
    return {
        player["id"]: player["color"].capitalize()
        for player in load_player_boards_v2_layout()["players"]
    }


SEAT_COLOURS = _seat_colours()
_SEAT_NAMED = re.compile(r"\b(" + "|".join(sorted(SEAT_COLOURS)) + r")\b")


def say(value: object) -> str:
    """Put a string on the page, saying seats by the colour a player can see.

    THE ONE DOOR. Everything that becomes readable text goes through here, and everything that
    becomes an attribute goes through `escape` instead. That split is the whole rule: `data-player`
    and its kin stay in the engine's names because the script routes on them and the seam is
    defined in those names, while what the page says out loud is the page's own business.

    It has to be one door rather than one call per producer, because there are three producers --
    the state header, the transcript, the turn summaries -- and they are the engine's sentences
    arriving whole. Rewriting them at the source would be the page editing the engine's account of
    itself, and would leave the fourth producer to be found by whoever notices.

    Why it is needed at all: the engine ids and the words players use at the table are different
    vocabularies. Attributes keep the ids because that is what the seam routes on; visible text says
    the seat colours because that is what the rulebook names and what a player can point at.
    """
    return escape(_SEAT_NAMED.sub(lambda found: SEAT_COLOURS[found.group(1)], str(value)))


def _catalog_with_engine_metadata(catalog: dict) -> dict:
    """Add tooltip metadata from the engine catalogue to the visual building catalogue.

    The visual catalogue owns palette and tile geometry. The engine catalogue owns the words that
    explain a building, so the page joins the two by id instead of copying rule text into a
    renderer.
    """
    engine_catalogue = json.loads(ENGINE_BUILDINGS_PATH.read_text(encoding="utf-8"))["catalogue"]
    metadata = {entry["id"]: entry for entry in engine_catalogue}
    visual_ids = {building["id"] for building in catalog["buildings"]}
    if visual_ids != set(metadata):
        raise ValueError("Building visual and engine catalogues do not contain the same ids.")
    return {
        **catalog,
        "buildings": [
            {
                **building,
                "category": metadata[building["id"]]["category"],
                "description": metadata[building["id"]]["description"],
            }
            for building in catalog["buildings"]
        ],
    }


def _resource_glyph_for_tooltip(resource: str) -> str:
    """Render one inline glyph with the player-board resource renderer."""
    icon = RESOURCE_TOKEN_ICONS.get(resource)
    if icon is None or icon not in _ICON_RENDERERS:
        raise KeyError(f"unknown tooltip resource token: {resource}")
    size = resource_icon_size(icon) * 0.72
    return (
        f'<svg class="building-tooltip-resource" data-tooltip-resource="{resource}"'
        ' viewBox="0 0 20 30" aria-label="'
        f'{resource} resource" role="img"><g data-resource="{resource}" pointer-events="none">'
        f"{_ICON_RENDERERS[icon](10, 17, size, '#3A2F1E')}</g></svg>"
    )


def _description_html(description: str) -> str:
    """Replace only explicit resource tokens, rejecting unknown or malformed braces."""
    pieces: list[str] = []
    cursor = 0
    while cursor < len(description):
        opening = description.find("{", cursor)
        closing = description.find("}", cursor)
        if closing != -1 and (opening == -1 or closing < opening):
            raise ValueError(f"malformed resource token in description: {description!r}")
        if opening == -1:
            pieces.append(escape(description[cursor:]))
            break
        pieces.append(escape(description[cursor:opening]))
        ending = description.find("}", opening + 1)
        if ending == -1:
            raise ValueError(f"unterminated resource token in description: {description!r}")
        token = description[opening + 1 : ending]
        if token not in RESOURCE_TOKEN_ICONS:
            raise ValueError(f"unknown resource token {{{token}}} in description")
        pieces.append(_resource_glyph_for_tooltip(token))
        cursor = ending + 1
    return "".join(pieces)


def _tooltip_deckle_layer(class_name: str) -> str:
    """One dark layer behind the parchment, cut to the outline the parchment itself is cut to."""
    return (
        f'<svg class="{class_name}" aria-hidden="true" viewBox="0 0 100 100" '
        f'preserveAspectRatio="none"><polygon points="{TOOLTIP_DECKLE_SVG_POINTS}"/></svg>'
    )


def _building_tooltip_templates(catalog: dict) -> str:
    """One hidden template per building, plus the empty tooltip the script fills and moves.

    Each template is three layers of one outline: the parchment clipped to `TOOLTIP_DECKLE_POINTS`,
    a tight shadow under it so it lies on the board rather than floats, and the wide soft halo that
    lifts it off whatever is behind. All three are cut from the same points, so the pool can never
    be a rectangle under a torn shape.

    The two dark layers are separate elements rather than `drop-shadow()` on the parchment because
    `clip-path` clips what a filter produced: a shadow cast by the card is cut away at the very
    outline it was meant to follow, and nothing is painted outside. This is also why removing the
    card's border appeared to flatten the silhouette -- the border was never what made the shape.

    Their blur is a CSS `blur()` on the `<svg>` rather than an `feGaussianBlur` inside it, for two
    reasons that both come from the tooltip being content-sized. A deviation given in user units is
    scaled by the viewBox, and `preserveAspectRatio="none"` on a wide, short tooltip scales x and y
    by different amounts -- an 11 unit blur became roughly 43px sideways and 11px down, a smear
    rather than a pool. And an SVG filter paints only inside its filter region, so the tail of the
    blur was cut off square where the region ended. A CSS filter works in painted pixels, is the
    same in both directions whatever the tooltip's proportions, and has no region to fall out of.
    """
    templates = []
    for building in catalog["buildings"]:
        description = _description_html(str(building["description"]))
        templates.append(
            f'<template data-building-tooltip-template="{escape(str(building["id"]))}">'
            '<div class="building-tooltip-frame">'
            '<div class="building-tooltip-card">'
            '<div class="building-tooltip-heading">'
            f'<span class="building-tooltip-name">{escape(str(building["name"]))}</span>'
            f'<span class="building-tooltip-category">{escape(str(building["category"]))}</span>'
            "</div>"
            f'<div class="building-tooltip-description">{description}</div>'
            "</div>"
            + _tooltip_deckle_layer("building-tooltip-shadow")
            + _tooltip_deckle_layer("building-tooltip-halo")
            + "</div></template>"
        )
    return (
        '<svg class="building-tooltip-filters" aria-hidden="true" width="0" height="0">'
        '<defs><filter id="building-tooltip-aged" x="-10%" y="-20%" width="120%" height="150%">'
        '<feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="3" result="noise"/>'
        '<feColorMatrix in="noise" type="saturate" values="0" result="gray-noise"/>'
        '<feComponentTransfer in="gray-noise" result="aged-noise">'
        '<feFuncA type="linear" slope="0.10"/></feComponentTransfer>'
        '<feComposite in="aged-noise" in2="SourceGraphic" operator="atop"/>'
        "</filter></defs></svg>"
        '<div data-building-tooltip-templates="true">'
        + "".join(templates)
        + '</div><div class="building-tooltip" data-building-tooltip="true"'
        ' aria-hidden="true"></div>'
    )


def building_tooltip_styles() -> str:
    """The tooltip's own styles, with the deckled outline substituted in by name.

    CSS is nothing but braces, so this block cannot be an f-string and cannot be `.format`-ed: the
    one time the outline needs to be interpolated would cost every rule in the sheet a doubled
    brace. `Template` takes `$deckle` instead, which CSS never uses, and `substitute` raises if the
    name is ever misspelled -- the failure that produced a rectangular tooltip was a `{...}`
    placeholder reaching the browser as literal text, where an invalid declaration is dropped in
    silence and the silhouette simply goes away.
    """
    return Template("""  [data-building-tooltip-templates="true"], .building-tooltip-filters {
    display: none;
  }
  .building-tooltip {
    position: fixed; z-index: 1000; display: none; pointer-events: none;
    color: #3A2F1E; font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
  }
  .building-tooltip[data-building-tooltip-visible="true"] { display: block; }
  .building-tooltip-frame {
    position: relative; width: max-content; max-width: min(380px, calc(100vw - 24px));
  }
  .building-tooltip-halo, .building-tooltip-shadow {
    position: absolute; overflow: visible; pointer-events: none; z-index: 0;
  }
  .building-tooltip-halo {
    inset: -6px; width: calc(100% + 12px); height: calc(100% + 12px); filter: blur(11px);
  }
  .building-tooltip-halo polygon { fill: #000000; opacity: .38; }
  .building-tooltip-shadow {
    left: 0; top: 2px; width: 100%; height: 100%; filter: blur(2.5px);
  }
  .building-tooltip-shadow polygon { fill: #000000; opacity: .22; }
  .building-tooltip-card {
    box-sizing: border-box; width: max-content; max-width: min(380px, calc(100vw - 24px));
    padding: 15px 20px 16px; background-color: #E6D7B8;
    background-image: linear-gradient(#F1E7CD, #DBCAA4);
    border: 1px solid transparent;
    clip-path: $deckle;
    filter: url(#building-tooltip-aged);
    position: relative; z-index: 1;
  }
  .building-tooltip-heading {
    display: flex; align-items: baseline; gap: 12px; min-width: 220px; margin: 0 0 5px;
  }
  .building-tooltip-name {
    color: #8F2222; font-size: 14px; line-height: 1.15; font-weight: 700; white-space: nowrap;
  }
  .building-tooltip-category {
    margin-left: auto; color: #8A7550; font-size: 9px; line-height: 1.15;
    font-weight: 700; letter-spacing: .13em; text-transform: uppercase; white-space: nowrap;
  }
  .building-tooltip-description {
    max-width: 340px; font-size: 11px; line-height: 1.38; overflow-wrap: break-word;
  }
  .building-tooltip-resource {
    display: inline-block; width: 1.15em; height: 1.15em; margin: 0 .04em;
    vertical-align: -.22em; overflow: visible;
  }
""").substitute(deckle=TOOLTIP_CLIP_PATH)


def building_tooltip_script() -> str:
    return """<script>
  (function () {
    'use strict';
    var tooltip = document.querySelector('[data-building-tooltip="true"]');
    var templates = document.querySelectorAll('[data-building-tooltip-template]');
    var targets = document.querySelectorAll('[data-building-id]');
    if (!tooltip || !targets.length) { return; }

    function templateFor(id) {
      for (var index = 0; index < templates.length; index += 1) {
        if (templates[index].getAttribute('data-building-tooltip-template') === id) {
          return templates[index];
        }
      }
      return null;
    }

    function hide() {
      tooltip.removeAttribute('data-building-tooltip-visible');
      tooltip.setAttribute('aria-hidden', 'true');
      tooltip.innerHTML = '';
    }

    function findBuilding(container, selector, id) {
      var matches = (container || document).querySelectorAll(selector);
      for (var index = 0; index < matches.length; index += 1) {
        if (matches[index].getAttribute('data-building-id') === id) {
          return matches[index];
        }
      }
      return null;
    }

    function canonicalAnchor(target, id) {
      var board = target.closest('[data-component="player-board-v2"]');
      if (board) {
        return findBuilding(board, '[data-player-board-slot][data-building-id]', id) || target;
      }
      var map = target.closest(
        '#setup-fills, #setup-labels, #setup-choice-keys, #conversion-choice-keys'
      );
      if (map) {
        return findBuilding(document, '#setup-fills g[data-building-id]', id) || target;
      }
      return target;
    }

    function show(target) {
      var id = target.getAttribute('data-building-id');
      var template = templateFor(id);
      if (!template) { return; }
      tooltip.innerHTML = template.innerHTML;
      tooltip.setAttribute('data-building-tooltip-visible', 'true');
      tooltip.setAttribute('aria-hidden', 'false');
      var targetBox = canonicalAnchor(target, id).getBoundingClientRect();
      var tooltipBox = tooltip.getBoundingClientRect();
      var left = targetBox.left + (targetBox.width - tooltipBox.width) / 2;
      var top = targetBox.top - tooltipBox.height - 10;
      left = Math.max(8, Math.min(left, window.innerWidth - tooltipBox.width - 8));
      if (top < 8) { top = targetBox.bottom + 10; }
      top = Math.max(8, Math.min(top, window.innerHeight - tooltipBox.height - 8));
      tooltip.style.left = left + 'px';
      tooltip.style.top = top + 'px';
    }

    Array.prototype.forEach.call(targets, function (target) {
      target.addEventListener('mouseenter', function () { show(target); });
      target.addEventListener('mouseleave', hide);
      target.addEventListener('focus', function () { show(target); });
      target.addEventListener('blur', hide);
    });
  }());
</script>"""


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


def start_roll_for(payload: dict) -> int:
    """The physical ring rotation carried by generated setup metadata, if present.

    The engine's pilgrimage rounds are normalized by the NW roll, so round 1 is the NW roll's
    physical hex. Hand-written and older payloads have no setup metadata; they retain the debug
    view's original E1/default rotation.
    """
    metadata = payload.get("setup_metadata")
    if not isinstance(metadata, dict):
        return DEFAULT_START_ROLL
    timeline = metadata.get("setup_timeline")
    if not isinstance(timeline, dict):
        return DEFAULT_START_ROLL
    rolls = timeline.get("pilgrimage_rolls")
    if not isinstance(rolls, dict):
        return DEFAULT_START_ROLL
    try:
        roll = int(rolls["nw"])
    except (KeyError, TypeError, ValueError):
        return DEFAULT_START_ROLL
    return roll if roll in START_HEX_BY_ROLL else DEFAULT_START_ROLL


def map_placements_for(payload: dict, catalog: dict, site_data: dict | list) -> list[dict]:
    """The border track: what is standing on each round of it in this scenario.

    Generated setup metadata carries the NW roll that normalized the engine's abstract rounds. It
    is also the physical roll that pins round 1 to the NW quadrant, so the same rotation must be
    used for sites, buildings, and the ship.
    """
    by_id = {building["id"]: building for building in catalog["buildings"]}
    path = rotated_edge_path(start_hex_for_roll(start_roll_for(payload)))
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


def ship_hex_for(payload: dict) -> str:
    """The hex the ship stands on, from the position the state keeps rather than from the round 1.

    `ship_position` is an index into the same ring the track is laid along, counted from the slot
    round 1 sits on, so it needs no arithmetic beyond looking it up: the engine's path and the
    map's are both twenty-six steps and step 0 is the same step.

    The NW setup roll supplies the physical pin for both this path and the timeline placements.
    Payloads without that metadata retain the default debug rotation.
    """
    path = rotated_edge_path(start_hex_for_roll(start_roll_for(payload)))
    return path[int(payload["state"]["ship_position"]) % len(path)]


def _slot_label(slot: dict, building: dict | None) -> str:
    if building is not None:
        return f"{building['name']} (level {building['level']})"
    if slot["site_index"] is not None:
        return f"Pilgrimage site {slot['site_index']}"
    return "Empty"


def _played_round_pips(payload: dict) -> str:
    """Four seat-coloured pips, filled only for seats state explicitly marks as already played."""
    done = set(played_this_round(payload))
    if not done:
        return ""
    return (
        '<span class="round-pips" aria-label="Seats played this round">'
        + "".join(
            f'<span class="round-pip" data-player="{escape(player_id)}"'
            f' data-player-color="{SEAT_COLOURS[player_id].lower()}"'
            f' data-played="{"true" if player_id in done else "false"}"></span>'
            for player_id in SEATED_PLAYERS
        )
        + "</span>"
    )


def _log_blocks(payload: dict) -> list[dict]:
    """Action-sized transcript blocks, or one line per block when only flat lines are available."""
    raw = payload.get("log_blocks")
    blocks: list[dict] = []
    if isinstance(raw, list):
        for block in raw:
            if not isinstance(block, dict):
                continue
            lines = [str(line) for line in block.get("lines", ()) if str(line).strip()]
            if not lines:
                continue
            blocks.append({"lines": lines, "round_end": bool(block.get("round_end"))})
    if blocks:
        return blocks
    return [
        {"lines": [str(line)], "round_end": False}
        for line in payload.get("log", ())
        if str(line).strip()
    ]


def render_log_box(payload: dict) -> str:
    """Status, question, controls and transcript in one readable box under the Alms panel."""
    _key, sentence = state_header(payload)[0]
    rows = (
        f'<div class="log-status-line" data-status-line="{escape(sentence)}">'
        f"{say(sentence)}{_played_round_pips(payload)}</div>"
    )
    # Already formatted when it got here. Newest block first, then put back into reading order by
    # `column-reverse`, so the box opens on what just happened without any scrolling script.
    entries_parts = []
    for block in reversed(_log_blocks(payload)):
        marker = '<div class="log-block-mark">Round end</div>' if block["round_end"] else ""
        lines = "".join(f'<div class="log-event">{say(line)}</div>' for line in block["lines"])
        entries_parts.append(
            f'<div class="log-block" data-round-end="{str(block["round_end"]).lower()}">'
            f"{marker}{lines}</div>"
        )
    entries = "".join(entries_parts)
    transcript = f'<div class="log-transcript">{entries}</div>' if entries else ""
    return (
        f'<div class="play-log" data-component="play-log">'
        f"{rows}{render_turn_panel(payload)}{transcript}</div>"
    )


def _prompt_lines(candidates: list[dict]) -> str:
    """One line per question any candidate asks, all struck here and all hidden.

    Same shape as the keys below, and for the same reason: the page reveals a sentence and never
    writes one. The words are the seam's -- what a question asks is a fact about the action -- so
    this does not know that a position on the board means acolytes, or that some of these lines are
    answered nowhere near the panel they appear in.

    This includes board-answered steps too. The board marks where to point; this says what the
    question is, in one seam sentence the script only reveals.
    """
    seen: list[str] = []
    for candidate in candidates:
        for step in candidate["steps"]:
            prompt = step.get("prompt")
            if prompt and prompt not in seen:
                seen.append(prompt)
    return "".join(
        f'<div class="turn-prompt" data-turn-prompt="{escape(prompt)}"'
        f' data-turn-offered="false">{say(prompt)}</div>'
        for prompt in sorted(seen)
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
        f' data-turn-offered="false">{say(name.replace("_", " "))}</button>'
        for name in sorted(seen)
    )


def _combination_keys(candidates: list[dict]) -> str:
    """One key per whole combination any candidate offers, all struck here and all hidden.

    A combination is several amounts that are only legal together, so the key stands for the set of
    them and there is no key for a part of one. Offering the parts separately would let a player
    build a pairing the engine never offered, and the page would then have to know which pairings
    go together -- which is the rule it exists not to hold a copy of.

    Hire and relocation choices use the same key shape: one scalar answer and one sentence, offered
    whole. A hire is not "partly accepted", so splitting source from payment stock would ask two
    questions where there is only one legal move.

    The words are the seam's, not this file's. What a combination amounts to is a fact about the
    action, and composing a sentence for it here would be a second description to keep in step.
    """
    seen: dict[str, str] = {}
    for candidate in candidates:
        for step in candidate["steps"]:
            if step["kind"] in {
                "combination",
                "hire",
            }:
                seen.setdefault(step["value"], step.get("label", step["value"]))
    return "".join(
        f'<button type="button" class="turn-key" data-combination-key="{escape(value)}"'
        f' data-turn-offered="false">{say(label)}</button>'
        for value, label in sorted(seen.items())
    )


def _turn_step_direction_label(direction: str) -> str:
    return direction.replace("_", " ").capitalize()


def _turn_step_controls(steps: list[dict]) -> str:
    """The client-side controls for the engine's committed building steps."""
    directions = []
    for step in steps:
        if step["kind"] != "conversion":
            continue
        direction = str(step["direction"])
        if direction not in directions:
            directions.append(direction)
    direction_buttons = "".join(
        f'<button type="button" class="turn-step-direction"'
        f' data-turn-step-direction="{escape(direction)}" data-turn-step-offered="false"'
        f' data-turn-step-selected="false">{say(_turn_step_direction_label(direction))}</button>'
        for direction in directions
    )
    hire_payments = []
    for step in steps:
        payment = step.get("hire_payment")
        if payment is not None and payment not in hire_payments:
            hire_payments.append(payment)
    hire_buttons = "".join(
        f'<button type="button" class="turn-step-hire"'
        f' data-turn-step-hire-payment="{escape(str(payment))}"'
        ' data-turn-step-hire-offered="false" data-turn-step-hire-selected="false">'
        f"{say(str(payment))}</button>"
        for payment in hire_payments
    )
    return (
        '<div class="turn-step-controls" data-component="turn-step-controls">'
        '<div class="turn-step-direction-row" data-turn-step-direction-row="true"'
        ' data-turn-step-row-active="false">'
        '<span class="turn-step-label">Conversion</span>'
        f"{direction_buttons}</div>"
        '<span class="turn-step-activation-prompt" data-turn-step-activation-prompt="true"'
        ' data-turn-step-activation-active="false"></span>'
        '<div class="turn-step-resource-row" data-turn-step-resource-row="true"'
        ' data-turn-step-row-active="false">'
        '<span class="turn-step-label" data-turn-step-answer-label="true">Amount</span>'
        '<span class="turn-step-amount-total" data-turn-step-amount-total="true"></span>'
        '<span class="turn-step-resource-hint" data-turn-step-resource-hint="true"></span></div>'
        '<div class="turn-step-hire-row" data-turn-step-hire-row="true"'
        ' data-turn-step-row-active="false">'
        '<span class="turn-step-label">Hire payment</span>'
        f"{hire_buttons}</div>"
        "</div>"
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
            body = f'<div class="turn-summary">{say(candidate["summary"])}</div>'
        else:
            fields = "".join(
                f'<li class="turn-field">{say(name)}</li>' for name in candidate["unresolved"]
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


def _box_turn_controls() -> str:
    """The box controls. Same `data-turn-control` handles, new location."""

    def button(label: str, key: str) -> str:
        return (
            f'<button type="button" class="turn-control" data-turn-control="{key}"'
            ' data-turn-control-enabled="false" data-turn-control-active="false"'
            f' aria-label="{label}" aria-disabled="true">{label}</button>'
        )

    return (
        '<div class="turn-controls" data-component="turn-controls">'
        '<div class="turn-control-row turn-control-row-top">'
        f"{button('Action', 'action')}{button('Tithe', 'tithe')}"
        "</div>"
        '<div class="turn-control-row turn-control-row-bottom">'
        f"{button('Reset', 'reset')}{button('Confirm', 'confirm')}"
        "</div>"
        "</div>"
    )


def _turn_phase_column(payload: dict) -> str:
    """Draw the server-described turn, round-end, or inactive phase column."""
    column = payload.get("phase_column") or {}
    scope = str(column.get("scope", "inactive"))
    rows = column.get("rows") or (
        {"key": "beginning", "label": "Beginning of Turn", "current": False},
        {"key": "sow", "label": "Sow", "current": False},
        {"key": "end", "label": "End of Turn", "current": False},
    )
    attribute = "data-round-end-phase" if scope == "round_end" else "data-turn-phase"
    return (
        f'<div class="phase-column" data-phase-column="{escape(scope)}">'
        + "".join(
            f'<div class="phase-row" {attribute}="{escape(str(row["key"]))}"'
            + (' data-phase-current="true"' if row.get("current") else "")
            + f">{escape(str(row['label']))}</div>"
            for row in rows
        )
        + "</div>"
    )


def render_turn_panel(payload: dict) -> str:
    """Where a turn is answered and agreed to, beside the log rather than on the board."""
    candidates = payload.get("turn_candidates") or []
    turn_steps = payload.get("turn_steps") or []
    if not candidates and not turn_steps:
        return (
            f'<div class="play-turn" data-component="play-turn">{_turn_phase_column(payload)}</div>'
        )
    return (
        '<div class="play-turn" data-component="play-turn">'
        f"{_turn_phase_column(payload)}"
        f"{_prompt_lines(candidates)}"
        f'<div class="turn-keys">{_resolution_keys(candidates)}'
        f"{_combination_keys(candidates)}</div>"
        f"{_turn_step_controls(turn_steps)}"
        f"{_turn_panels(candidates)}"
        f"{_box_turn_controls()}"
        "</div>"
    )


def _turn_counter_values(candidates: list[dict]) -> tuple[int, ...]:
    """Distinct counter readouts the candidates can reach, pre-drawn for reveal-only updates."""
    seen: set[int] = set()
    for candidate in candidates:
        start = candidate.get("counter_start")
        if isinstance(start, int):
            seen.add(start)
        for step in candidate.get("steps", ()):
            count = step.get("counter")
            if isinstance(count, int):
                seen.add(count)
    return tuple(sorted(seen, reverse=True))


def _city_spoke_reversals_used(candidates: list[dict]) -> tuple[str, ...]:
    """The Kogge reversals any candidate uses, from the full turn-candidate set.

    Computed once at render time from the whole payload so arrows stay stable while the browser
    narrows the same candidate set to one action.
    """
    used = {
        str(step["value"])
        for candidate in candidates
        for step in candidate.get("steps", ())
        if step.get("kind") == "edge" and str(step.get("value")) in CITY_SPOKE_REVERSAL_ARROWS
    }
    return tuple(sorted(used))


def log_styles() -> str:
    return """  /* The play box stands in the slack under the Alms Table. */
  .play-log {
    width: 100%; color: #F2EEDF; font: 13px/1.5 Helvetica, Arial, sans-serif;
    background: #101010; border: 1px solid #333333; border-radius: 10px;
    padding: 10px 12px;
    align-self: stretch;
    display: flex; flex-direction: column; min-height: 0; flex: 1 1 auto;
  }
  .log-status-line { margin-bottom: 8px; color: #F2EEDF; text-align: left; }
  .round-pips { display: inline-flex; gap: 6px; margin-left: 8px; vertical-align: middle; }
  .round-pip {
    width: 9px; height: 9px; border-radius: 50%; opacity: 0.30;
    border: 1px solid rgba(255,255,255,0.35);
  }
  .round-pip[data-player-color="red"] { background: #B7382E; }
  .round-pip[data-player-color="yellow"] { background: #B9923A; }
  .round-pip[data-player-color="blue"] { background: #335C8F; }
  .round-pip[data-player-color="white"] { background: #DFD5BD; }
  .round-pip[data-played="true"] { opacity: 1; }

  .log-transcript {
    margin-top: 8px; padding-top: 8px; border-top: 1px solid #333333;
    display: flex; flex-direction: column-reverse;
    min-height: 0; overflow-y: auto; flex: 1 1 auto;
  }
  .log-block {
    margin-bottom: 8px; padding: 6px 8px;
    background: #151515; border: 1px solid #262626; border-radius: 8px;
  }
  .log-block[data-round-end="true"] { border-color: #6A5A32; }
  .log-block-mark {
    color: #E0C36A; font-size: 11px; text-transform: uppercase; letter-spacing: 0.04em;
    margin-bottom: 4px;
  }
  .log-event { color: #C9C4B4; font-size: 12px; margin-bottom: 3px; }
  .log-event:last-child { margin-bottom: 0; }

  /* Seats now centre by count, so chairs not at the table are removed from flow. */
  .p-player[data-seat-taken="false"] { display: none; }"""


_TURN_SCRIPT = (
    "<script>\n"
    + Path(__file__).with_name("play_view_turn.js").read_text(encoding="utf-8")
    + "</script>"
)


def turn_styles(route_color: str) -> str:
    """What the attributes the script sets do, and the only place any of it is a colour.

    Every affordance is drawn by the renderer and hidden here; the script flips an attribute
    between true and false and does nothing else. No position and no colour crosses into
    JavaScript -- the colour of the route is the active seat\'s own, written in by the page that
    knows which seat that is. So any highlight on THAT seat's own pieces cannot use `route_color`
    to stand out: it paints their existing colour back onto them.

    The whole space and arrow are the targets rather than just their outlines, so a click in the
    painted area counts.
    """
    return f"""  /* One offered-ring language: dashed means "offered now", solid means "taken".
     Origin, skip, duty and relocation candidates intentionally use the same seat-colour ring
     family. That is safe because only one of those questions is live at a time, and the prompt
     says which; the play-server sweep holds that invariant across corpus and playtests. */
  [data-turn-start-candidate="true"] {{ cursor: pointer; }}
  [data-turn-start-candidate="true"] .board-circle {{
    stroke: {route_color}; stroke-width: 4.4; stroke-dasharray: 8 4;
  }}
  [data-turn-step-relocation-candidate="true"] {{ cursor: pointer; }}
  [data-turn-step-relocation-candidate="true"] .board-circle {{
    stroke: {route_color}; stroke-width: 4.4; stroke-dasharray: 6 3;
  }}
  [data-turn-skip-candidate="true"] {{ cursor: pointer; }}
  [data-turn-skip-candidate="true"] .board-circle {{
    stroke: {route_color}; stroke-width: 4.4; stroke-dasharray: 5 3;
  }}
  [data-turn-duty-candidate="true"] {{ cursor: pointer; }}
  [data-turn-duty-candidate="true"] .board-circle {{
    stroke: {route_color}; stroke-width: 4.4; stroke-dasharray: 8 4;
  }}
  [data-turn-skip-selected="true"] .board-circle {{
    stroke: {route_color}; stroke-width: 3.5; stroke-dasharray: 3 2;
  }}
  [data-turn-duty-selected="true"] .board-circle {{ stroke: {route_color}; stroke-width: 3.5; }}
  [data-ornament-position][data-turn-duty-selected="true"] circle {{
    fill: {route_color}; stroke-opacity: 0.7;
  }}
  [data-arrow][data-turn-offered="true"] {{ cursor: pointer; }}
  [data-arrow][data-turn-offered="true"] .arrow-interior {{ fill: rgb(30, 122, 52); }}

  .play-turn {{
    position: relative; z-index: 20;
    width: 100%; margin-top: 10px; color: #F2EEDF; font: 13px/1.5 Helvetica, Arial, sans-serif;
    background: #101010; border: 1px solid #333333; border-radius: 10px; padding: 10px 12px;
  }}
  .phase-column {{ display: flex; flex-direction: column; gap: 2px;
    margin: -1px 0 9px; padding-bottom: 9px; border-bottom: 1px solid #333333; }}
  .phase-row {{ color: {TURN_PHASE_DIM_COLOR}; font-size: 12px; letter-spacing: 0.02em; }}
  .phase-row[data-phase-current="true"] {{ color: {TURN_PHASE_CURRENT_COLOR}; font-weight: 700; }}
  /* One line per question, all drawn, all hidden until the script says theirs is the one being
     asked. Above the keys because several of these are answered nowhere near them -- on the board,
     on a seat's own stock, on a hex of the round track -- and a line that only appeared when the
     answer was in the panel would go quiet in exactly the cases it is there for. */
  .turn-prompt {{ display: none; margin-bottom: 8px; color: {route_color}; font-weight: 700; }}
  .turn-prompt[data-turn-offered="true"] {{ display: block; }}

  .turn-keys {{ display: flex; flex-wrap: wrap; gap: 6px; }}
  .turn-key {{
    color: #F2EEDF; background: #1C1C1C; border: 1px solid #3A3A3A; border-radius: 8px;
    padding: 6px 10px; cursor: pointer; font: 13px/1.4 Helvetica, Arial, sans-serif;
  }}
  /* A key is only pressable while it is one of the answers still standing. Resolutions and whole
     combinations are both keys and both hide the same way. */
  .turn-key {{ display: none; }}
  .turn-key[data-turn-offered="true"] {{ display: inline-block; }}

  .turn-controls {{ margin-top: 10px; display: flex; flex-direction: column; gap: 6px; }}
  .turn-control-row {{ display: flex; gap: 6px; }}
  .turn-control {{
    flex: 1;
    color: #F2EEDF; background: #1C1C1C; border: 1px solid #3A3A3A; border-radius: 8px;
    padding: 6px 10px; font: 13px/1.4 Helvetica, Arial, sans-serif;
  }}
  .turn-control-row-bottom [data-turn-control="reset"],
  .turn-control-row-bottom [data-turn-control="confirm"] {{
    min-width: 0;
  }}
  .turn-step-controls {{ position: relative; z-index: 2; margin: 8px 0; color: #C9C4B4; }}
  .turn-step-direction-row, .turn-step-resource-row, .turn-step-hire-row {{
    display: flex; align-items: center; gap: 6px; margin-top: 5px; height: 24px;
    box-sizing: border-box; overflow: visible;
  }}
  [data-turn-step-row-active="false"] {{ visibility: hidden; }}
  [data-turn-step-answer-label-visible="false"] {{ visibility: hidden; }}
  .turn-step-label {{ min-width: 72px; color: #E0C36A; }}
  .turn-step-activation-prompt {{
    display: none; position: absolute; top: 5px; left: 0; right: 0; line-height: 24px;
    color: #C9C4B4;
  }}
  .turn-step-activation-prompt[data-turn-step-activation-active="true"] {{ display: block; }}
  .turn-step-direction {{
    color: #F2F0E6; background: #262626; border: 1px solid #555; border-radius: 999px;
    padding: 4px 9px; font: 12px/1.2 Helvetica, Arial, sans-serif; cursor: pointer;
    position: relative; z-index: 3; pointer-events: auto;
  }}
  .turn-step-amount-total {{
    min-width: 24px; color: #F2F0E6; font-weight: 700; text-align: center;
  }}
  .turn-step-hire {{
    color: #F2F0E6; background: #262626; border: 1px solid #555; border-radius: 999px;
    padding: 4px 9px; font: 12px/1.2 Helvetica, Arial, sans-serif; cursor: pointer;
  }}
  [data-turn-step-hire-offered="false"] {{ display: none; }}
  [data-turn-step-hire-selected="true"] {{
    background: #F2EEDF; border-color: #F2EEDF; color: #1C1C1C;
  }}
  [data-turn-step-direction][data-turn-step-offered="false"] {{
    display: none;
  }}
  [data-turn-step-direction][data-turn-step-selected="true"] {{
    background: #F2EEDF; border-color: #F2EEDF; color: #1C1C1C;
  }}
  /* A player-board slot remains the tooltip target. Its transparent conversion hit target carries
     data-turn-step-click-target, so this gate can stop a non-offered conversion without removing
     the slot itself from hover hit testing. Map choice keys keep the same rule below. */
  [data-turn-step-building-id][data-turn-step-offered="true"] {{ cursor: pointer; }}
  [data-turn-step-building-id][data-turn-step-offered="false"] {{ pointer-events: none; }}
  [data-turn-step-building-id][data-turn-step-market="true"] {{ visibility: hidden; }}
  [data-turn-step-building-id][data-turn-step-market="true"][data-turn-step-offered="true"] {{
    visibility: visible !important; pointer-events: all; cursor: pointer;
  }}
  [data-turn-step-building-id][data-turn-step-used="true"] {{ opacity: 0.42; }}

  svg :focus:not(:focus-visible) {{ outline: none; }}

{resource_choice_styles()}
  /* The board renderer draws all three stock keys and the rule above shows them together. A stock
     the surviving turns do not offer is taken back out again here, so the seat is never shown a
     key it cannot press. Visibility only: the pill, the keyline and where it sits are the
     renderer's, as they are for the seals. */
  [data-resource-choice-key][data-turn-offered="false"] {{ visibility: hidden; }}
  [data-piety-choice-pill] {{ visibility: hidden; }}
  [data-piety-choice-pill][data-piety-choice-offered="true"] {{
    visibility: visible !important; pointer-events: all; cursor: pointer;
  }}
  [data-piety-choice-pill][data-piety-choice-offered="false"] {{
    pointer-events: none;
  }}
  [data-piety-choice-pill][data-piety-choice-offered="true"] [data-resource-choice-key] {{
    visibility: visible !important; pointer-events: all; cursor: pointer;
  }}
  [data-piety-choice-pill][data-piety-choice-offered="false"] [data-resource-choice-key] {{
    visibility: hidden !important; pointer-events: none;
  }}
  [data-piety-choice-pill] [data-piety-choice-hit="true"] {{
    fill: transparent; stroke: none;
  }}
  [data-piety-choice-pill] text {{
    font: 8px Helvetica, Arial, sans-serif; fill: #F2F0E6; pointer-events: none;
  }}
  /* The resource renderer supplies the number, but this surface rule must not wash it out. Keep
     its computed typography identical to the player-board resource readout. */
  [data-piety-choice-pill] [data-piety-choice-silver="true"] {{
    font-family: Helvetica, Arial, sans-serif; font-size: 16px; font-weight: 700;
    fill: #3A2F1E;
  }}

  /* Every building on the round track carries a key, and the rule below shows the offered ones --
     so the map says which buildings may be constructed by ringing the ones that may, in the same
     parchment an offered space on the wheel is ringed in. Visibility only: the hex, its outline and
     which round it stands on are the map's, as they are for the seals and the stock keys. */
{building_choice_styles()}
{seat_choice_styles()}
  /* Both seat keys and building keys are outlines struck with pointer-events="all", so hiding one
     by visibility alone does not remove it from hit testing. An unoffered key must be both hidden
     and non-interactive or it can sit above another live target and swallow the click. */
  [data-building-choice-key][data-turn-offered="false"] {{
    visibility: hidden; pointer-events: none;
  }}
  /* Same shape of rule for the board-sized key, and the same reason: every chair carries one and
     a chair the choice does not include has its taken back out. Unlike the stock keys, several are
     shown at once -- the question names a player and most of the players it may name are not the
     one acting, so the mark has to say "one of these" and not "these are all active". It is the
     outline an offered space on the wheel wears, which is already what this page's "you may point
     at this" looks like, and it is nothing like the wash that means whose turn it is. */
  [data-seat-choice-key][data-turn-offered="false"] {{
    visibility: hidden; pointer-events: none;
  }}

  /* Allocation and Ordination are answered on the acting board itself. The renderer draws tags on
     every board, but only the acting one is made live while this question is being asked. */
  [data-component="player-board-v2"] [data-token="village"],
  [data-component="player-board-v2"] [data-token="abbey"],
  [data-component="player-board-v2"] [data-token="role"],
  [data-component="player-board-v2"] [data-role-circle] {{
    pointer-events: none;
  }}
  [data-end-relocation-choice="true"] [data-token="abbey"][opacity="1"] {{
    pointer-events: all; cursor: pointer;
  }}
  /* `pointer-events` on an SVG element is a presentation attribute and loses to author CSS.
     Liveness is stated once in this stylesheet, keyed by data-arrangement-* attributes. */
  [data-arrangement-choice="true"] [data-token="abbey"][data-arrangement-can-lift="true"][opacity="1"],
  [data-arrangement-choice="true"] [data-token="abbey"][data-arrangement-can-place="true"],
  [data-arrangement-choice="true"] [data-token="abbey"][data-arrangement-held="true"],
  [data-arrangement-choice="true"] [data-token="role"][data-arrangement-can-lift="true"][opacity="1"],
  [data-arrangement-choice="true"] [data-token="role"][data-arrangement-held="true"],
  [data-arrangement-choice="true"] [data-role-circle][data-arrangement-can-place="true"],
  [data-arrangement-choice="true"] [data-role-circle][data-arrangement-held="true"] {{
    pointer-events: all; cursor: pointer;
  }}
  [data-arrangement-choice="true"] [data-role-circle][data-arrangement-can-place="true"] {{
    stroke: {route_color}; stroke-width: 4; stroke-dasharray: 8 4;
  }}
  [data-arrangement-choice="true"] [data-role-circle][data-arrangement-held="true"] {{
    stroke: {route_color}; stroke-width: 4;
  }}
  /* No route-colour stroke on seat-owned cubes yet (allocation Abbey + ordination tokens):
     `route_color` is the active seat's own colour, so stroking those cubes with it erases the
     darker edge instead of standing out. */
  [data-ordination-choice="true"] [data-token="village"][data-ordination-can-ordain="true"][opacity="1"],
  [data-ordination-choice="true"] [data-token="abbey"][data-ordination-can-mission="true"][opacity="1"] {{
    pointer-events: all; cursor: pointer;
  }}

  /* One panel per candidate, all drawn, all hidden until its candidate is the one left. */
  .turn-panel {{ display: none; }}
  .turn-panel[data-turn-shown="true"] {{ display: block; }}
  .turn-summary {{ margin: 8px 0; color: #F2EEDF; }}
  .turn-blocked {{ margin: 8px 0; color: #E0C36A; }}
  .turn-fields {{ margin: 0 0 4px 0; padding-left: 18px; color: #C9C4B4; }}
  .turn-field {{ font-family: Menlo, monospace; font-size: 12px; }}
  [data-turn-control][data-turn-control-enabled="true"] {{ opacity: 1; cursor: pointer; }}
  [data-turn-control][data-turn-control-enabled="false"] {{ opacity: 0.34; cursor: default; }}
  [data-turn-control][data-turn-control-active="true"] {{ opacity: 1; }}
  [data-turn-control][data-turn-control-active="true"] {{
    background: #F2EEDF; border-color: #F2EEDF; color: #1C1C1C;
  }}
  [data-turn-counter][data-turn-offered="false"] {{ visibility: hidden; }}
  [data-turn-counter][data-turn-offered="true"] {{ visibility: visible; }}"""


def render_play_view_html(
    payload: dict,
    map_layout: dict,
    piety_layout: dict,
    piety_config: dict,
    catalog: dict,
    site_data: dict | list,
    donated_data: dict | list,
    board_layout: dict,
    duty_wheel_layout: dict,
    alms_layout: dict,
    alms_config: dict,
) -> str:
    catalog = _catalog_with_engine_metadata(catalog)
    seated = seated_player_ids(payload)
    candidates = payload.get("turn_candidates") or []
    turn_steps = payload.get("turn_steps") or []
    turn_surface = bool(candidates or turn_steps)
    # The phase column remains in place even when no turn surface is active.
    turn_panel_visible = True
    # One-time draw choice from the full candidate set; do not recalculate as the turn narrows.
    city_spoke_reversals = _city_spoke_reversals_used(candidates)
    scenario_duty = duty_layout_for(payload, duty_wheel_layout)
    piety_variant = piety_variant_for(seated)

    content, hexes, cubes = board_measurements(
        alms_layout,
        piety_layout,
        board_layout,
        duty_wheel_layout,
        map_layout,
        piety_variant,
        piety_choice_lane=any(step.get("building_id") == "indulgences" for step in turn_steps),
    )
    scale = solve_table_scale(content, hexes, cubes)
    hexagon = duty_hexagon(duty_wheel_layout)

    alms_svg = crop_svg(
        render_alms_table_svg(
            alms_layout,
            alms_config,
            {player_id: _alms_row(payload, player_id) for player_id in seated},
            interactive=turn_surface,
        ),
        scale.crop["alms"],
    )
    piety_svg = crop_svg(
        render_piety_track_v2_svg(
            piety_layout,
            piety_config,
            piety_variant,
            first_player_seat(payload),
            piety_positions_by_player=piety_by_player(payload),
            piety_choice_steps=[
                dict(step, choice_index=index)
                for index, step in enumerate(turn_steps)
                if step.get("building_id") == "indulgences"
            ],
        ),
        scale.crop["piety"],
    )
    duty_svg = crop_svg(
        regularise_duty_hexagon(
            render_duty_wheel_svg(
                scenario_duty,
                duty_board_state_for(payload, scenario_duty),
                merchant_on=merchant_duty_for(payload, scenario_duty),
                interactive=bool(candidates),
                turn_controls=bool(candidates),
                turn_counter_values=_turn_counter_values(candidates) if candidates else None,
                turn_control_names=(),
                city_spoke_reversals=city_spoke_reversals,
            ),
            hexagon,
        ),
        scale.crop["action"],
    )
    # A key on every building the track carries, drawn hidden, because which of them a turn will
    # come to ask about is not known until that turn is part-built. Only the offered ones are ever
    # revealed, and `building_choice_styles` is what reveals them.
    map_svg = crop_svg(
        render_setup_map_svg(
            map_layout,
            map_placements_for(payload, catalog, site_data),
            choice_keys=bool(candidates),
            ship_hex=ship_hex_for(payload),
            conversion_building_ids={
                step["building_id"] for step in turn_steps if step.get("building_id")
            },
        ),
        scale.crop["map"],
    )

    panels = []
    for seat, player_id in enumerate(SEATED_PLAYERS, start=1):
        # An empty chair is still drawn and then hidden, exactly as the debug table hides one: a
        # chair removed from the row would let the occupied ones slide along it.
        taken = player_id in seated
        player = player_by_id(board_layout, player_id)
        # The three stock keys, drawn hidden on every seat's board because which seat will be asked
        # is not known until a turn is part-built. Only the asking seat's are ever revealed, and
        # `resource_choice_styles` is what reveals them.
        #
        # And the one key that is the board itself, for the question that names a player. Both are
        # drawn on every chair and neither decides anything by being there.
        board = render_player_board_v2_svg(
            _board_layout_for(payload, board_layout, player_id),
            player,
            board_state=_board_state_for(
                payload,
                board_layout,
                player_id,
                catalog,
                donated_data,
            ),
            interactive=turn_surface,
            choice_keys=bool(candidates),
            seat_key=bool(candidates),
            turn_step_hit=turn_surface,
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
        _TURN_SCRIPT.replace("__CANDIDATES__", json.dumps(candidates))
        .replace("__TURN_STEPS__", json.dumps(turn_steps))
        .replace(
            "__USED_BUILDINGS__",
            json.dumps(payload.get("state", {}).get("turn_progress", {}).get("used_buildings", [])),
        )
        .replace(
            "__RESOLUTION_COMMITTED__",
            json.dumps(
                payload.get("state", {}).get("turn_progress", {}).get("resolution_committed", False)
            ),
        )
        .replace(
            "__PHASE_COLUMN_SCOPE__",
            json.dumps(payload.get("phase_column", {}).get("scope", "inactive")),
        )
        .replace("__TOKEN__", json.dumps(payload.get("state_token", "")))
        .replace(
            "__ALMS_POSITION_TARGETS__",
            json.dumps(
                disc_targets(
                    alms_layout,
                    alms_rules(alms_config),
                    payload["state"]["active_player"],
                )
            ),
        )
        if turn_surface
        else ""
    )
    turn_css = turn_styles(active_color) if turn_panel_visible else ""
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

{building_tooltip_styles()}

{table_stacking_styles(scale)}
</style>
</head>
<body>
{stage}
{_building_preview_content_defs(catalog, candidates)}
{_building_donation_preview_content_defs(catalog, donated_data, candidates)}
{_building_tooltip_templates(catalog)}
{script}
{building_tooltip_script()}</body>
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


def _board_state_for(
    payload: dict,
    board_layout: dict,
    player_id: str,
    catalog: dict,
    donated_data: dict | list,
) -> dict:
    """What is actually on this seat's board, rather than what the layout's sample has on it.

    The sample is eight serfs in the Village, three acolytes in the Abbey and cubes standing on the
    Stone Mason and the Vestry. At the opening the first two of those happen to be right and the
    third is already wrong -- nobody holds a role on turn one -- and every one of them is wrong the
    moment anybody plays. Drawing it anyway is not a gap in the page, it is the page saying
    something untrue about a seat, which is harder to notice and worse to trust.

    An empty seat still gets a board and gets the sample, because the sample is what its geometry
    is drawn from; the panel around it is hidden, so nothing untrue is on screen.
    """
    record = player_record(payload, player_id)
    if record is None:
        return default_player_board_v2_state(board_layout)
    return {
        "village_serfs": int(record["workforce"]["village"]),
        "abbey_acolytes": int(record["workforce"]["abbey"]),
        # Every role the board draws, so a role at zero is written down as zero rather than left
        # out and defaulted. `special_activities` and `worker_roles` are the same six by the same
        # names, and a role the engine stopped reporting should empty its circle, not keep it.
        "roles": {
            role["id"]: int(record["special_activities"].get(role["id"], 0))
            for role in board_layout["worker_roles"]
        },
        "slots": _slot_contents(
            record,
            catalog,
            donated_data,
        ),
    }


def _slot_contents(
    record: dict,
    catalog: dict,
    donated_data: dict | list,
) -> tuple[dict, ...]:
    """This seat's buildings, drawn ready to be dropped into the slots that hold them.

    Bought first and then donated, which is the order the engine keeps them in and the only order
    available: the state records two lists and not which of the six slots anything went into, so
    a building's slot is where this page put it rather than something being read back. Nothing
    here depends on which slot that is. Hired abilities are deliberately absent: hiring gives a
    seat temporary use of a building, not ownership of a slot on its board.

    The drawing is `generate_game_setup`'s, unchanged -- the same content the composed table points
    its slots at, called directly instead of through a `defs` and a script, because this page knows
    at render time what a seat has built and has no script to point anything anywhere.
    """
    by_id = {building["id"]: building for building in catalog["buildings"]}
    by_level = {int(tile["level"]): tile for tile in tiles_of(donated_data)}
    slots: list[dict] = []
    for building_id in record["player_board_slots"]["active_buildings"]:
        building = by_id.get(building_id)
        if building is not None:
            slots.append(
                {
                    "id": building_id,
                    "state": "bought",
                    "content": render_board_slot_building(building, BUILDING_SLOT_HEX_SIZE),
                }
            )
    for building_id in record["player_board_slots"]["donated_buildings"]:
        building = by_id.get(building_id)
        tile = by_level.get(int(building["level"])) if building is not None else None
        if tile is not None:
            slots.append(
                {
                    "id": building_id,
                    "state": "donated",
                    "content": render_board_slot_donated(tile, BUILDING_SLOT_HEX_SIZE),
                }
            )
    return tuple(slots)


def _building_preview_content_defs(catalog: dict, candidates: list[dict]) -> str:
    """Reusable bought-building drawings for construction previews."""
    ids = {
        str(step["building_constructed"])
        for candidate in candidates
        for step in candidate.get("steps", ())
        if step.get("building_constructed") is not None
    }
    if not ids:
        return ""
    by_id = {str(building["id"]): building for building in catalog["buildings"]}
    fragments = "".join(
        f'<g id="preview-building-{escape(building_id)}">'
        f"{render_board_slot_building(by_id[building_id], BUILDING_SLOT_HEX_SIZE)}</g>"
        for building_id in sorted(ids)
        if building_id in by_id
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" class="content-defs" width="0" height="0"'
        f' aria-hidden="true"><defs>{fragments}</defs></svg>'
    )


def _building_donation_preview_content_defs(
    catalog: dict, donated_data: dict | list, candidates: list[dict]
) -> str:
    """Reusable donated-side drawings for building donation previews."""
    ids = {
        str(step["building_donation"])
        for candidate in candidates
        for step in candidate.get("steps", ())
        if step.get("building_donation") is not None
    }
    by_id = {str(building["id"]): building for building in catalog["buildings"]}
    by_level = {int(tile["level"]): tile for tile in tiles_of(donated_data)}
    fragments = []
    for building_id in sorted(ids):
        building = by_id.get(building_id)
        tile = by_level.get(int(building["level"])) if building is not None else None
        if tile is None:
            continue
        fragments.append(
            f'<g id="preview-donated-building-{escape(building_id)}">'
            f"{render_board_slot_donated(tile, BUILDING_SLOT_HEX_SIZE)}</g>"
        )
    if not fragments:
        return ""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" class="content-defs" width="0" height="0"'
        f' aria-hidden="true"><defs>{"".join(fragments)}</defs></svg>'
    )


def render_play_view_from_payload(payload: dict) -> str:
    """The page, from the payload alone, with every layout loaded from its own file."""
    return render_play_view_html(
        payload,
        load_map_layout(),
        load_piety_track_v2_layout(),
        load_piety_config(),
        load_building_catalog(),
        load_pilgrimage_sites(),
        load_donated_building_tiles(),
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
