"""Structured renderer for the ornamented piety track debug view.

This is v2 of the piety track: the same strip, wearing the house ornament the mancala board and
the Alms Table already wear. Two devices survived onto the board — a hairline inset just inside
the panel edge, and a trefoil between two rules beside the title — and the v1 strip has nowhere to
put either, because its boxes butt against the panel edge. So the strip becomes a panel that
*contains* the boxes, gaining side padding, a title band, and a little more room at the bottom.
That also puts the board's name in the artwork rather than leaving it to the page heading.

The page shows the panel twice: once for 3-4 players (two disc rows on the starting space) and
once for 2 players (one row). Both are the same panel, so the variants differ only in disc rows
and the height that follows from them.

This is a debug/visual tool only. It reads `piety_track_v2_layout.json` for geometry and
`configs/piety.json` for the VP values printed on the stars. It is not connected to `GameState`
and does not implement any game rules. v2 does not replace `render_piety_track.py`, which still
draws the current view.

The VP numbers are deliberately not copied into the layout JSON: `configs/piety.json` is the
game's source of truth for them, and it is parsed here with the game's own `piety_from_dict`, so
a change to the piety table shows up in this view without anyone editing the UI layer. Nor are the
viewBox and display size stored: they follow from the panel and the padding, and a stored copy
could only ever disagree with what is drawn.

`prototypes/piety_tracks_v2.html` and the two SVG baselines beside it are what was drawn first, and
the strip is still theirs: the same panel width, the same spaces on the same centres, the same
discs. What has moved away from them is how it is all set. This board and the Alms Table are the
same thing twice -- a numbered row of spaces with a player disc standing on one and a score printed
under each -- and in the composed game table they are drawn at the same scale, so this one is set
from that one's constants and each thing lands at the same size on screen. The star, the disc, the
numbers, the rules between them and the title all come from elsewhere rather than being reinvented
here. `prototype_sources/piety_tracks_v2.py.txt` is the reference for how the baseline was drawn;
it is read, never imported or executed.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from xml.sax.saxutils import escape

from pilgrim.model.config import piety_from_dict
from tools.ui_debug.render_alms_table import (
    INK_FONT,
    LABEL_FONT_WEIGHT,
    ORNAMENT_LOBE_ANGLES,
    ORNAMENT_RULE_GAP,
    ORNAMENT_STROKE_OPACITY,
    ORNAMENT_STROKE_WIDTH,
    ORNAMENT_TREFOIL_RADIUS,
    STAR_INNER_RADIUS,
    STAR_LABEL_FONT_SIZE,
    STAR_LABEL_OFFSET,
    STAR_OUTER_RADIUS,
    STEP_NUMBER_FONT_SIZE,
    STEP_RULE_STROKE_OPACITY,
    STEP_RULE_STROKE_WIDTH,
    TITLE_FONT,
    TITLE_FONT_SIZE,
    TITLE_FONT_WEIGHT,
)
from tools.ui_debug.render_donated_buildings import render_star_path, star_points

COMPONENT_NAME = "piety-track-v2"
LAYOUT_FILENAME = "piety_track_v2_layout.json"
PIETY_CONFIG_RELATIVE_PATH = ("configs", "piety.json")

# Both boards are a numbered row of spaces with a player disc standing on one, and in the game
# table they are drawn at the same scale -- that is what makes the disc they share come out the
# same size on each. So a space here is set the way a step there is: the same number at the same
# size and weight, divided from its neighbours by the same hairline, under a title of the same size
# at the same distance above it, and paying a star of the same size with the score set inside it
# the same way. Every one of those is the Alms Table's own constant rather than a copy of its
# value, so the two boards cannot be restyled apart by accident.
NUMBER_FONT = (
    f'font-family="{INK_FONT}" font-size="{STEP_NUMBER_FONT_SIZE:g}"'
    f' font-weight="{LABEL_FONT_WEIGHT}"'
)
# The score in a star is the one number on either board set plain: the star is already standing it
# out, so the digits do not have to as well.
STAR_LABEL_FONT = f'font-family="{INK_FONT}" font-size="{STAR_LABEL_FONT_SIZE:g}"'


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_layout_path() -> Path:
    return Path(__file__).resolve().parent / LAYOUT_FILENAME


def default_piety_config_path() -> Path:
    return repo_root().joinpath(*PIETY_CONFIG_RELATIVE_PATH)


def load_piety_track_v2_layout(path: Path | None = None) -> dict:
    layout_path = default_layout_path() if path is None else Path(path)
    return json.loads(layout_path.read_text(encoding="utf-8"))


def load_piety_config(path: Path | None = None) -> dict:
    config_path = default_piety_config_path() if path is None else Path(path)
    return json.loads(config_path.read_text(encoding="utf-8"))


def piety_vp_values(config: dict) -> list[int]:
    """VP per piety position, parsed with the game's own config reader."""
    return list(piety_from_dict(config).score_by_position)


def variant_by_id(layout: dict, variant_id: str) -> dict:
    for variant in layout["variants"]:
        if variant["id"] == variant_id:
            return variant
    known = ", ".join(variant["id"] for variant in layout["variants"])
    raise KeyError(f"unknown piety track variant: {variant_id} (have {known})")


def player_by_id(layout: dict, player_id: str) -> dict:
    for player in layout["players"]:
        if player["id"] == player_id:
            return player
    raise KeyError(f"unknown player: {player_id}")


def _star_extent(outer_r: float, inner_r: float) -> tuple[float, float]:
    """Highest and lowest point of the star, relative to its own centre."""
    ys = [y for _, y in star_points(0.0, 0.0, outer_r, inner_r)]
    return min(ys), max(ys)


def track_geometry(layout: dict, disc_rows: int) -> dict:
    """Vertical layout of one panel: title, then the numbers, the discs and the stars beneath.

    The numbers hang `title_to_numbers` below the title's baseline, which is the drop the Alms
    Table gives its own track under `Alms Table`, and everything below is chained off them: gap,
    disc rows, gap, stars, bottom margin. So dropping a disc row still shortens the panel by
    exactly that row, and nothing else moves.

    The two gaps used to be one number. They are separate because the second one is doing a job
    the first is not: the composed game table stands this panel's top level with the Alms Table's,
    and `discs_to_stars` is what lands this row of stars on the row the `11` star sits in there,
    so a score reads across the table at one height. That holds for the variant the table stands
    on. The 2 player one is a disc row shorter and its stars come up with the rest of the strip,
    which is the same rule applied, not an exception to it.

    Every y here is already in panel coordinates. There is no separate title band to add on: what
    used to be one is now the drop itself, which is the thing worth naming.
    """
    panel = layout["panel"]
    track = layout["track"]
    label = track["position_label"]
    disc = track["disc"]

    radius = disc["radius"]
    row_step = 2 * radius + disc["gap"]

    title_baseline_y = panel["pad_top"] + layout["ornament"]["title"]["dy"]
    number_baseline_y = title_baseline_y + track["title_to_numbers"]
    number_bottom = number_baseline_y + label["descent"]
    top_row_cy = number_bottom + track["numbers_to_discs"] + radius
    discs_cy = top_row_cy + (disc_rows - 1) * row_step / 2
    discs_bottom = top_row_cy + (disc_rows - 1) * row_step + radius

    star_min_y, star_max_y = _star_extent(STAR_OUTER_RADIUS, STAR_INNER_RADIUS)
    star_cy = discs_bottom + track["discs_to_stars"] - star_min_y

    strip_width = 2 * track["outer_extra"] + track["position_count"] * track["box_width"]
    rule = track["position_rule"]

    return {
        "panel_width": 2 * panel["pad_x"] + strip_width,
        "panel_height": star_cy + star_max_y + track["bottom_margin"] + panel["pad_bottom"],
        "title_baseline_y": title_baseline_y,
        "number_baseline_y": number_baseline_y,
        "discs_cy": discs_cy,
        "discs_bottom": discs_bottom,
        "disc_offset": row_step / 2,
        "star_cy": star_cy,
        "rule_y1": number_baseline_y - rule["above_numbers"],
        "rule_y2": discs_bottom + rule["below_discs"],
    }


def position_center_x(layout: dict, index: int) -> float:
    """Centre of the box drawn for one piety position, in panel coordinates."""
    track = layout["track"]
    count = track["position_count"]
    if not 0 <= index < count:
        raise KeyError(f"no piety position {index}")
    box_width = track["box_width"]
    return layout["panel"]["pad_x"] + track["outer_extra"] + index * box_width + box_width / 2


def position_center(layout: dict, variant_id: str, index: int) -> tuple[float, float]:
    """Where a disc on one position stands, before its seat offset in the grid."""
    variant = variant_by_id(layout, variant_id)
    geometry = track_geometry(layout, variant["disc_rows"])
    return position_center_x(layout, index), geometry["discs_cy"]


def seated_players(layout: dict, variant_id: str) -> list[dict]:
    """Each player a variant seats, with its colours and its own corner of the grid.

    The offsets are relative to a position's centre, so anything that moves a disc along the track
    only has to change the x of the position it stands on. That is the one description of where a
    disc sits: the renderer draws from it, and the setup page moves from it.
    """
    variant = variant_by_id(layout, variant_id)
    geometry = track_geometry(layout, variant["disc_rows"])
    offset = geometry["disc_offset"]
    return [
        {
            **player_by_id(layout, seat["player"]),
            "cx_offset": seat["column"] * offset,
            "cy": geometry["discs_cy"] + seat["row"] * offset,
        }
        for seat in variant["seats"]
    ]


def render_position_label(layout: dict, geometry: dict, index: int) -> str:
    fill = layout["track"]["position_label"]["fill"]
    return (
        f'<text x="{position_center_x(layout, index):.1f}"'
        f' y="{geometry["number_baseline_y"]:.1f}" text-anchor="middle" {NUMBER_FONT}'
        f' fill="{fill}">{index}</text>'
    )


def position_rule_x(layout: dict, index: int) -> float:
    """Where the hairline between position `index` and the one after it falls."""
    track = layout["track"]
    if not 0 <= index < track["position_count"] - 1:
        raise KeyError(f"no piety position rule after {index}")
    box_width = track["box_width"]
    return layout["panel"]["pad_x"] + track["outer_extra"] + (index + 1) * box_width


def render_position_rules(layout: dict, geometry: dict) -> str:
    """The hairlines that divide one position from the next, as the Alms Table divides its steps.

    Only between the numbers: the strip's own two ends are closed by the panel's padding and the
    inset hairline inside it, so a rule there would be a second edge beside an edge.
    """
    ink = layout["palette"]["ink"]
    y1, y2 = geometry["rule_y1"], geometry["rule_y2"]
    return "".join(
        f'<line x1="{position_rule_x(layout, index):.1f}" y1="{y1:.1f}"'
        f' x2="{position_rule_x(layout, index):.1f}" y2="{y2:.1f}"'
        f' stroke="{ink}" stroke-opacity="{STEP_RULE_STROKE_OPACITY}"'
        f' stroke-width="{STEP_RULE_STROKE_WIDTH:g}"/>'
        for index in range(layout["track"]["position_count"] - 1)
    )


def render_player_disc(layout: dict, index: int, player: dict) -> str:
    """One seated player's disc on a position, tagged with whose it is and where it stands."""
    disc = layout["track"]["disc"]
    return (
        f'<circle cx="{position_center_x(layout, index) + player["cx_offset"]:.1f}"'
        f' cy="{player["cy"]:.1f}" r="{disc["radius"]}"'
        f' fill="{player["fill"]}" stroke="{player["stroke"]}"'
        f' stroke-width="{disc["stroke_width"]}"'
        f' data-player-disc="true" data-player="{player["id"]}"'
        f' data-player-color="{player["color"]}" data-piety-position="{index}"/>'
    )


def render_vp_star(layout: dict, geometry: dict, index: int, vp: int) -> str:
    """The VP a player scores for finishing the season on this position."""
    center_x = position_center_x(layout, index)
    star_cy = geometry["star_cy"]
    return (
        render_star_path(center_x, star_cy, STAR_OUTER_RADIUS, STAR_INNER_RADIUS)
        + f'<text x="{center_x:.1f}" y="{star_cy + STAR_LABEL_OFFSET:.1f}"'
        f' text-anchor="middle" {STAR_LABEL_FONT}'
        f' fill="{layout["palette"]["star_label_fill"]}">{escape(str(vp))}</text>'
    )


def render_panel_inset(layout: dict, geometry: dict) -> str:
    """The house hairline, a fixed distance inside the panel edge and concentric with it."""
    inset = layout["ornament"]["inset"]
    offset = inset["offset"]
    width = geometry["panel_width"] - 2 * offset
    height = geometry["panel_height"] - 2 * offset
    radius = layout["panel"]["corner_radius"] - offset
    return (
        f'<rect x="{offset}" y="{offset}" width="{width:.1f}" height="{height:.1f}"'
        f' rx="{radius:.1f}" ry="{radius:.1f}" fill="none"'
        f' stroke="{layout["palette"]["ink"]}" stroke-opacity="{inset["stroke_opacity"]}"'
        f' stroke-width="{inset["stroke_width"]}"/>'
    )


def render_trefoil_rule(layout: dict, geometry: dict) -> str:
    """The house header: a rule broken by three lobes, running from the title to the far edge.

    The lobes and the air they hold are the Alms Table's, so the mark reads at the size it does
    there. The rule they sit on is this header's own: it runs from clear of the title to the far
    padding, which is wider than the Alms Table's header, and the lobes stay at its middle.
    """
    panel = layout["panel"]
    trefoil = layout["ornament"]["trefoil"]
    ink = layout["palette"]["ink"]

    x0 = panel["pad_x"] + trefoil["start_dx"]
    x1 = geometry["panel_width"] - panel["pad_x"] - trefoil["end_dx"]
    y = panel["pad_top"] + trefoil["dy"]
    center_x = (x0 + x1) / 2
    radius = ORNAMENT_TREFOIL_RADIUS
    gap = ORNAMENT_RULE_GAP

    lobes = "".join(
        f'<circle cx="{center_x + radius * math.cos(math.radians(angle)):.1f}"'
        f' cy="{y + radius * math.sin(math.radians(angle)):.1f}" r="{radius:.1f}" />'
        for angle in ORNAMENT_LOBE_ANGLES
    )
    return (
        f'<g fill="none" stroke="{ink}" stroke-opacity="{ORNAMENT_STROKE_OPACITY}"'
        f' stroke-width="{ORNAMENT_STROKE_WIDTH:.1f}" stroke-linecap="round">{lobes}'
        f'<path d="M {x0:.1f},{y:.1f} H {center_x - gap:.1f}'
        f' M {center_x + gap:.1f},{y:.1f} H {x1:.1f}" /></g>'
    )


def render_panel_title(layout: dict, geometry: dict) -> str:
    """The board's name, in the artwork rather than only in the page heading."""
    x = layout["panel"]["pad_x"] + layout["ornament"]["title"]["dx"]
    return (
        f'<text x="{x:.1f}" y="{geometry["title_baseline_y"]:.1f}" text-anchor="start"'
        f' font-family="{escape(TITLE_FONT)}"'
        f' font-size="{TITLE_FONT_SIZE:g}" font-weight="{TITLE_FONT_WEIGHT}"'
        f' fill="{layout["palette"]["ink"]}">{escape(layout["title"])}</text>'
    )


def render_piety_track_v2_svg(layout: dict, config: dict, variant_id: str) -> str:
    """One ornamented panel: the grey rounded rect, the ornament, then the track inside it."""
    variant = variant_by_id(layout, variant_id)
    vp_values = piety_vp_values(config)
    track = layout["track"]
    position_count = track["position_count"]
    if len(vp_values) != position_count:
        raise ValueError(
            f"piety config has {len(vp_values)} VP values but the layout draws {position_count} "
            "positions"
        )

    panel = layout["panel"]
    geometry = track_geometry(layout, variant["disc_rows"])
    panel_width = geometry["panel_width"]
    panel_height = geometry["panel_height"]
    corner_r = panel["corner_radius"]
    fill = layout["palette"]["panel_fill"]

    parts = [
        f'<rect x="0" y="0" width="{panel_width:.1f}" height="{panel_height:.1f}"'
        f' rx="{corner_r}" ry="{corner_r}" fill="{fill}" stroke="{fill}"'
        f' stroke-width="{panel["stroke_width"]}"/>',
        render_panel_inset(layout, geometry),
        render_panel_title(layout, geometry),
        render_trefoil_rule(layout, geometry),
        render_position_rules(layout, geometry),
    ]

    seated = seated_players(layout, variant_id)
    for index, vp in enumerate(vp_values):
        parts.append(render_position_label(layout, geometry, index))
        if index == track["disc_position"]:
            parts += [render_player_disc(layout, index, player) for player in seated]
        parts.append(render_vp_star(layout, geometry, index, vp))

    padding = layout["padding"]
    min_x, min_y = -padding["side"], -padding["top"]
    width = panel_width + 2 * padding["side"]
    height = panel_height + padding["top"] + padding["bottom"]

    # The viewBox is left alone; only the displayed size is scaled, so the track lines up with the
    # map's width when the two are viewed together.
    display_scale = layout["display_width"] / width

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg"'
        f' viewBox="{min_x} {min_y} {width:.1f} {height:.1f}"'
        f' width="{width * display_scale:.1f}" height="{height * display_scale:.1f}"'
        f' data-component="{COMPONENT_NAME}" data-piety-variant="{variant["id"]}">'
        f'\n  <rect x="{min_x}" y="{min_y}" width="{width:.1f}" height="{height:.1f}"'
        f' fill="{layout["page_background"]}"/>'
        f"\n  {''.join(parts)}\n</svg>"
    )


def render_piety_tracks_v2_html(layout: dict, config: dict) -> str:
    """The debug page: every variant the layout describes, stacked as the prototype stacks them."""
    rows = "\n".join(
        '    <div class="track-row">\n'
        f"      {render_piety_track_v2_svg(layout, config, variant['id'])}\n"
        "    </div>"
        for variant in layout["variants"]
    )
    background = layout["page_background"]
    subtitle = f"{layout['subtitle']} Generated from {LAYOUT_FILENAME}, VP values from "
    subtitle += "/".join(PIETY_CONFIG_RELATIVE_PATH) + "."
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Pilgrim — {escape(layout["page_title"])} (generated)</title>
<style>
  body {{
    margin: 0;
    background: {background};
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
    color: #F2EEDF;
    margin: 0 0 2px;
  }}
  p.subtitle {{
    color: #A8A296;
    font-size: 14px;
    margin: 0 0 18px;
    text-align: center;
    max-width: 720px;
  }}
  .board-wrap {{
    background: {background};
    border: 1px solid #333333;
    border-radius: 10px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.5);
    padding: 10px;
    display: flex;
    flex-direction: column;
    align-items: center;
  }}
  .board-wrap svg {{ display: block; max-width: 95vw; height: auto; }}
  .track-row {{ margin-bottom: 18px; }}
  .track-row:last-child {{ margin-bottom: 0; }}
</style>
</head>
<body>
  <h1>{escape(layout["page_title"])}</h1>
  <p class="subtitle">{escape(subtitle)}</p>
  <div class="board-wrap">
{rows}
  </div>
</body>
</html>
"""
