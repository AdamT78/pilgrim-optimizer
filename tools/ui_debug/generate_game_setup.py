"""Write the generated game setup debug page.

The page composes two existing renderers — the map and the 3-4 player piety track — and adds a
ship marker on the board edge plus one piety disc per player, moved by plain buttons.

Everything here is visual only. The ship walks a path of 26 points because that is the engine's
round track length, but nothing in this page reads or writes `GameState`, picks legal actions, or
applies any rule; moving a marker changes an SVG attribute and nothing else.

Run from the repo root:

    python3 tools/ui_debug/generate_game_setup.py
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from pathlib import Path
from xml.sax.saxutils import escape

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ui_debug.render_buildings import HEX_RADIUS as TILE_HEX_RADIUS  # noqa: E402
from tools.ui_debug.render_map import (  # noqa: E402
    hex_center,
    label_to_coord,
    load_map_layout,
    render_map_svg,
)
from tools.ui_debug.render_piety_track import (  # noqa: E402
    load_piety_config,
    load_piety_track_layout,
    piety_vp_values,
    position_center_x,
    render_piety_track_variant_svg,
    track_geometry,
    variant_by_id,
)
from tools.ui_debug.render_ship_marker import (  # noqa: E402
    SHIP_ANCHOR_OFFSET_Y as TILE_SHIP_ANCHOR_OFFSET_Y,
)
from tools.ui_debug.render_ship_marker import (  # noqa: E402
    SHIP_SCALE as TILE_SHIP_SCALE,
)
from tools.ui_debug.render_ship_marker import render_ship_icon  # noqa: E402

GENERATED_DIRNAME = "generated"
OUTPUT_FILENAME = "game_setup.html"

TITLE = "PILGRIM — Game Setup Debug View"
SUBTITLE = (
    "Generated map with the 3-4 player piety track above it. The ship and piety buttons move "
    "markers only: no GameState, no rules, no actions."
)
PAGE_BACKGROUND = "#000000"

# The setup page has four players, so it uses the 3-4 player track: two token rows on the
# starting space, one disc per player, in the token order white, red, yellow, blue.
PIETY_VARIANT_ID = "three_four_player"

# The ship sails the edge hexes clockwise from J3, skipping the four special corner hexes below.
# That leaves 26 stops, which is also the engine's round track length.
SHIP_HEX_PATH = (
    "J3",
    "J2",
    "I1",
    "H1",
    "G1",
    "E1",
    "D1",
    "D2",
    "C3",
    "C4",
    "B5",
    "B7",
    "C8",
    "C9",
    "D10",
    "D11",
    "E11",
    "F11",
    "H11",
    "I11",
    "J10",
    "J9",
    "K8",
    "K7",
    "K5",
    "K4",
)
SHIP_SKIPPED_HEXES = ("F1", "B6", "G11", "L6")
SHIP_POSITION_COUNT = len(SHIP_HEX_PATH)

SHIP_COLOR = "#000000"


def default_output_path() -> Path:
    return Path(__file__).resolve().parent / GENERATED_DIRNAME / OUTPUT_FILENAME


def _tile_ratio(map_layout: dict) -> float:
    """Map hexes are smaller than building tile hexes, so ship geometry is scaled between them."""
    return map_layout["hex_size"] / TILE_HEX_RADIUS


def ship_scale(map_layout: dict) -> float:
    return TILE_SHIP_SCALE * _tile_ratio(map_layout)


def ship_anchor_offset_y(map_layout: dict) -> float:
    return TILE_SHIP_ANCHOR_OFFSET_Y * _tile_ratio(map_layout)


def ship_path_points(
    map_layout: dict, labels: Sequence[str] = SHIP_HEX_PATH
) -> list[tuple[float, float]]:
    """One stop per hex label, in the upper part of that hex.

    The stops are resolved through the map's own label table, so a stop cannot end up on a hex
    the map does not draw, or drift if the labelling ever changes.
    """
    coords = label_to_coord(map_layout)
    offset = ship_anchor_offset_y(map_layout)

    points = []
    for label in labels:
        center_x, center_y = hex_center(map_layout, *coords[label])
        points.append((center_x, center_y + offset))
    return points


def render_ship_overlay(map_layout: dict, path: list[tuple[float, float]]) -> str:
    """The ship marker alone: the other stops stay unmarked, the ship is moved onto them."""
    start_x, start_y = path[0]
    ship = render_ship_icon(0.0, 0.0, scale=ship_scale(map_layout), color=SHIP_COLOR)
    return f'<g id="ship-marker" transform="translate({start_x:.1f},{start_y:.1f})">{ship}</g>'


def player_discs(piety_layout: dict, variant: dict) -> list[dict]:
    """One disc per player, taking colour and start offset from the track's own token data."""
    geometry = track_geometry(piety_layout, variant["token_rows"])
    offset = geometry["token_offset"]
    return [
        {
            "label": f"Player {index + 1}",
            "fill": token["fill"],
            "stroke": token["stroke"],
            "cx_offset": token["col"] * offset,
            "cy": geometry["tokens_cy"] + token["row"] * offset,
        }
        for index, token in enumerate(variant["tokens"])
    ]


def render_piety_disc_overlay(piety_layout: dict, discs: list[dict], start_position: int) -> str:
    token = piety_layout["track"]["token"]
    start_x = position_center_x(piety_layout, start_position)
    return "".join(
        f'<circle id="piety-disc-{index}" cx="{start_x + disc["cx_offset"]:.1f}"'
        f' cy="{disc["cy"]:.1f}" r="{token["radius"]}" fill="{disc["fill"]}"'
        f' stroke="{disc["stroke"]}" stroke-width="{token["stroke_width"]}"/>'
        for index, disc in enumerate(discs)
    )


def _with_overlay(svg: str, overlay: str) -> str:
    """Drop an extra fragment into a rendered SVG, drawn on top of what is already there."""
    closing = svg.rindex("</svg>")
    return f"{svg[:closing]}  {overlay}\n{svg[closing:]}"


def render_player_controls(discs: list[dict]) -> str:
    rows = []
    for index, disc in enumerate(discs):
        rows.append(
            '      <div class="player-row">\n'
            f'        <span class="swatch" style="background: {disc["fill"]};'
            f' border-color: {disc["stroke"]};"></span>\n'
            f'        <span class="player-name">{escape(disc["label"])}</span>\n'
            f'        <span class="readout">piety <strong id="piety-value-{index}">0</strong>'
            "</span>\n"
            f'        <button type="button" data-player="{index}" data-piety-delta="1">+1 piety'
            "</button>\n"
            f'        <button type="button" data-player="{index}" data-piety-delta="-1">-1 piety'
            "</button>\n"
            "      </div>"
        )
    return "\n".join(rows)


SETUP_SCRIPT = """
(function () {
  const data = JSON.parse(document.getElementById("setup-data").textContent);
  const shipPath = data.shipPath;
  const shipHexPath = data.shipHexPath;
  const pietyPositions = data.pietyPositions;
  const players = data.players;

  let shipPosition = 0;
  const pietyValues = players.map(function () { return 0; });

  const shipMarker = document.getElementById("ship-marker");
  const shipReadout = document.getElementById("ship-position");

  function renderShip() {
    const point = shipPath[shipPosition];
    shipMarker.setAttribute("transform", "translate(" + point[0] + "," + point[1] + ")");
    shipReadout.textContent = shipPosition + " / " + shipHexPath[shipPosition];
  }

  function renderPiety(index) {
    const value = pietyValues[index];
    const disc = document.getElementById("piety-disc-" + index);
    disc.setAttribute("cx", (pietyPositions[value] + players[index].cxOffset).toFixed(1));
    document.getElementById("piety-value-" + index).textContent = value;
  }

  document.getElementById("advance-ship").addEventListener("click", function () {
    shipPosition = (shipPosition + 1) % shipPath.length;
    renderShip();
  });

  document.getElementById("reset-ship").addEventListener("click", function () {
    shipPosition = 0;
    renderShip();
  });

  const pietyButtons = document.querySelectorAll("button[data-piety-delta]");
  Array.prototype.forEach.call(pietyButtons, function (button) {
    button.addEventListener("click", function () {
      const index = Number(button.getAttribute("data-player"));
      const delta = Number(button.getAttribute("data-piety-delta"));
      const bounded = Math.max(0, Math.min(pietyPositions.length - 1, pietyValues[index] + delta));
      pietyValues[index] = bounded;
      renderPiety(index);
    });
  });

  renderShip();
  players.forEach(function (_, index) { renderPiety(index); });
})();
"""


def render_game_setup_html(map_layout: dict, piety_layout: dict, piety_config: dict) -> str:
    variant = variant_by_id(piety_layout, PIETY_VARIANT_ID)
    vp_values = piety_vp_values(piety_config)
    start_position = piety_layout["track"]["token_position"]
    discs = player_discs(piety_layout, variant)

    # The discs are the movable copy of the starting tokens, so the track is drawn without its
    # static ones instead of stacking two sets of circles on the starting space.
    track_svg = render_piety_track_variant_svg(piety_layout, vp_values, {**variant, "tokens": []})
    track_svg = _with_overlay(
        track_svg, render_piety_disc_overlay(piety_layout, discs, start_position)
    )

    path = ship_path_points(map_layout)
    map_svg = _with_overlay(render_map_svg(map_layout), render_ship_overlay(map_layout, path))

    setup_data = json.dumps(
        {
            "shipPath": [[round(x, 1), round(y, 1)] for x, y in path],
            "shipHexPath": list(SHIP_HEX_PATH),
            "pietyPositions": [
                round(position_center_x(piety_layout, index), 1) for index in range(len(vp_values))
            ],
            "players": [{"cxOffset": disc["cx_offset"]} for disc in discs],
        }
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Pilgrim — Game Setup (generated)</title>
<style>
  body {{
    margin: 0;
    background: {PAGE_BACKGROUND};
    color: #F2EEDF;
    font-family: Helvetica, Arial, sans-serif;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 24px 12px 40px;
    box-sizing: border-box;
  }}
  h1 {{
    font-family: Georgia, serif;
    font-size: 26px;
    margin: 0 0 2px;
  }}
  h2 {{
    font-size: 13px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #A8A296;
    font-weight: 600;
    margin: 0 0 8px;
  }}
  p.subtitle {{
    color: #A8A296;
    font-size: 14px;
    margin: 0 0 18px;
    text-align: center;
    max-width: 720px;
  }}
  .board-column, .controls {{
    width: min(1014px, 92vw);
  }}
  .panel {{
    background: {PAGE_BACKGROUND};
    border: 1px solid #333333;
    border-radius: 10px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.5);
    padding: 10px;
    margin-bottom: 14px;
  }}
  .panel svg {{ display: block; width: 100%; height: auto; }}
  .controls {{
    display: flex;
    flex-wrap: wrap;
    gap: 14px;
  }}
  .controls .panel {{ flex: 1 1 320px; margin-bottom: 0; }}
  .player-row {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 6px 0;
  }}
  .swatch {{
    width: 14px;
    height: 14px;
    border-radius: 50%;
    border: 1px solid;
    box-sizing: border-box;
  }}
  .player-name {{ width: 70px; font-size: 14px; }}
  .readout {{ width: 78px; color: #A8A296; font-size: 13px; }}
  button {{
    background: #1A1A1A;
    color: #F2EEDF;
    border: 1px solid #555555;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 13px;
    font-family: inherit;
    cursor: pointer;
  }}
  button:hover {{ background: #2A2A2A; }}
</style>
</head>
<body>
  <h1>{TITLE}</h1>
  <p class="subtitle">{escape(SUBTITLE)}</p>
  <div class="board-column">
    <div class="panel" data-piety-variant="{PIETY_VARIANT_ID}">
      <h2>{escape(variant["label"])}</h2>
      {track_svg}
    </div>
    <div class="panel">
      <h2>Map with ship marker</h2>
      {map_svg}
    </div>
  </div>
  <div class="controls">
    <div class="panel">
      <h2>Ship controls</h2>
      <p class="readout" style="width: auto;">Ship position
        <strong id="ship-position">0 / {SHIP_HEX_PATH[0]}</strong></p>
      <p class="readout" style="width: auto;">{len(SHIP_HEX_PATH)} edge hexes, skipping
        {", ".join(SHIP_SKIPPED_HEXES)}</p>
      <button type="button" id="advance-ship">Advance ship</button>
      <button type="button" id="reset-ship">Reset ship</button>
    </div>
    <div class="panel">
      <h2>Player piety controls</h2>
{render_player_controls(discs)}
    </div>
  </div>
  <script id="setup-data" type="application/json">{setup_data}</script>
  <script>{SETUP_SCRIPT}</script>
</body>
</html>
"""


def write_game_setup_page(
    output_path: Path | None = None,
    *,
    map_layout_path: Path | None = None,
    piety_layout_path: Path | None = None,
    piety_config_path: Path | None = None,
) -> Path:
    destination = default_output_path() if output_path is None else Path(output_path)
    html = render_game_setup_html(
        load_map_layout(map_layout_path),
        load_piety_track_layout(piety_layout_path),
        load_piety_config(piety_config_path),
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(html, encoding="utf-8")
    return destination


def main() -> None:
    written = write_game_setup_page()
    print(f"wrote {written}")


if __name__ == "__main__":
    main()
