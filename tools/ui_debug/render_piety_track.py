"""Structured renderer for the piety track debug view.

The page shows the piety track twice: once for 3-4 players (two token rows on the starting space)
and once for 2 players (one token row). Both are the same strip, so the two variants differ only
in token rows and the strip height that follows from them.

This is a debug/visual tool only. It reads `piety_track_layout.json` for geometry and
`configs/piety.json` for the VP values printed on the stars. It is not connected to `GameState`
and does not implement any game rules.

The VP numbers are deliberately not copied into the layout JSON: `configs/piety.json` is the
game's source of truth for them, and it is parsed here with the game's own `piety_from_dict`, so
a change to the piety table shows up in this view without anyone editing the UI layer.

Geometry constants mirror `prototypes/piety_tracks.html`, which stays the visual baseline.
`prototype_sources/piety_tracks.py.txt` is the reference for how that baseline was drawn; it is
read, never imported or executed.
"""

from __future__ import annotations

import json
from pathlib import Path
from xml.sax.saxutils import escape

from pilgrim.model.config import piety_from_dict
from tools.ui_debug.render_donated_buildings import render_star_path, star_points

LAYOUT_FILENAME = "piety_track_layout.json"
PIETY_CONFIG_RELATIVE_PATH = ("configs", "piety.json")

LABEL_FONT = 'font-family="Helvetica, Arial, sans-serif" font-size="9" font-weight="600"'


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_layout_path() -> Path:
    return Path(__file__).resolve().parent / LAYOUT_FILENAME


def default_piety_config_path() -> Path:
    return repo_root().joinpath(*PIETY_CONFIG_RELATIVE_PATH)


def load_piety_track_layout(path: Path | None = None) -> dict:
    layout_path = default_layout_path() if path is None else Path(path)
    return json.loads(layout_path.read_text(encoding="utf-8"))


def load_piety_config(path: Path | None = None) -> dict:
    config_path = default_piety_config_path() if path is None else Path(path)
    return json.loads(config_path.read_text(encoding="utf-8"))


def piety_vp_values(config: dict) -> list[int]:
    """VP per piety position, parsed with the game's own config reader."""
    return list(piety_from_dict(config).score_by_position)


def _star_extent(outer_r: float, inner_r: float) -> tuple[float, float]:
    """Highest and lowest point of the star, relative to its own centre."""
    ys = [y for _, y in star_points(0.0, 0.0, outer_r, inner_r)]
    return min(ys), max(ys)


def track_geometry(layout: dict, token_rows: int) -> dict:
    """Vertical layout of one track strip, stacked top margin, number, tokens, star.

    The top margin (strip top to the top of the number glyph) equals the bottom margin (star tip
    to strip bottom), and the number-to-tokens gap equals the tokens-to-star gap, so dropping a
    token row shortens the strip by exactly that row.
    """
    track = layout["track"]
    label = track["position_label"]
    token = track["token"]
    star = track["star"]

    top_margin = track["top_margin"]
    row_gap = track["row_gap"]
    radius = token["radius"]
    row_step = 2 * radius + token["gap"]

    number_baseline_y = top_margin + label["cap_height"]
    number_bottom = number_baseline_y + label["descent"]
    top_row_cy = number_bottom + row_gap + radius
    tokens_cy = top_row_cy + (token_rows - 1) * row_step / 2
    tokens_bottom = top_row_cy + (token_rows - 1) * row_step + radius

    outer_r = star["outer_radius"]
    star_min_y, star_max_y = _star_extent(outer_r, outer_r * star["inner_ratio"])
    star_cy = tokens_bottom + row_gap - star_min_y

    return {
        "total_width": 2 * track["outer_extra"] + track["position_count"] * track["box_width"],
        "strip_height": star_cy + star_max_y + top_margin,
        "number_baseline_y": number_baseline_y,
        "tokens_cy": tokens_cy,
        "token_offset": row_step / 2,
        "star_cy": star_cy,
    }


def variant_by_id(layout: dict, variant_id: str) -> dict:
    for variant in layout["variants"]:
        if variant["id"] == variant_id:
            return variant
    known = ", ".join(variant["id"] for variant in layout["variants"])
    raise KeyError(f"unknown piety track variant: {variant_id} (have {known})")


def position_center_x(layout: dict, index: int) -> float:
    """Centre of the box drawn for one piety position, in track coordinates."""
    track = layout["track"]
    return track["outer_extra"] + index * track["box_width"] + track["box_width"] / 2


def render_position_label(layout: dict, geometry: dict, index: int, text: str) -> str:
    fill = layout["track"]["position_label"]["fill"]
    return (
        f'<text x="{position_center_x(layout, index):.1f}"'
        f' y="{geometry["number_baseline_y"]:.1f}" text-anchor="middle" {LABEL_FONT}'
        f' fill="{fill}">{escape(text)}</text>'
    )


def render_tokens(layout: dict, geometry: dict, index: int, tokens: list[dict]) -> str:
    token = layout["track"]["token"]
    center_x = position_center_x(layout, index)
    offset = geometry["token_offset"]
    return "".join(
        f'<circle cx="{center_x + entry["col"] * offset:.1f}"'
        f' cy="{geometry["tokens_cy"] + entry["row"] * offset:.1f}" r="{token["radius"]}"'
        f' fill="{entry["fill"]}" stroke="{entry["stroke"]}"'
        f' stroke-width="{token["stroke_width"]}"/>'
        for entry in tokens
    )


def render_star(layout: dict, geometry: dict, index: int, vp: int) -> str:
    star = layout["track"]["star"]
    center_x = position_center_x(layout, index)
    star_cy = geometry["star_cy"]
    outer_r = star["outer_radius"]
    label_y = star_cy + star["label_offset"]
    return (
        render_star_path(center_x, star_cy, outer_r, outer_r * star["inner_ratio"])
        + f'<text x="{center_x:.1f}" y="{label_y:.1f}" text-anchor="middle" {LABEL_FONT}'
        f' fill="{star["label_fill"]}">{escape(str(vp))}</text>'
    )


def render_piety_track_variant_svg(layout: dict, vp_values: list[int], variant: dict) -> str:
    """Render one track strip: the fused grey rect, then per position label, tokens, and star."""
    track = layout["track"]
    position_count = track["position_count"]
    if len(vp_values) != position_count:
        raise ValueError(
            f"piety config has {len(vp_values)} VP values but the layout draws {position_count} "
            "positions"
        )

    geometry = track_geometry(layout, variant["token_rows"])
    total_width = geometry["total_width"]
    strip_height = geometry["strip_height"]
    corner_r = track["corner_radius"]

    parts = [
        f'<rect x="0" y="0" width="{total_width}" height="{strip_height:.1f}"'
        f' rx="{corner_r}" ry="{corner_r}" fill="{track["fill"]}" stroke="{track["stroke"]}"'
        f' stroke-width="{track["stroke_width"]}"/>'
    ]
    for index, vp in enumerate(vp_values):
        parts.append(render_position_label(layout, geometry, index, str(index)))
        if index == track["token_position"]:
            parts.append(render_tokens(layout, geometry, index, variant["tokens"]))
        parts.append(render_star(layout, geometry, index, vp))

    padding = layout["padding"]
    min_x, min_y = -padding["side"], -padding["top"]
    width = total_width + 2 * padding["side"]
    height = strip_height + padding["top"] + padding["bottom"]

    # The viewBox is left alone; only the displayed size is scaled, so the track lines up with the
    # map's width when the two are viewed together.
    display_scale = layout["display_width"] / width

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{min_x} {min_y} {width} {height}"'
        f' width="{width * display_scale:.1f}" height="{height * display_scale:.1f}">'
        f'\n  <rect x="{min_x}" y="{min_y}" width="{width}" height="{height}"'
        f' fill="{layout["page_background"]}"/>'
        f"\n  {''.join(parts)}\n</svg>"
    )


def render_piety_track_svg(layout: dict, piety_config: dict) -> str:
    vp_values = piety_vp_values(piety_config)
    return "\n".join(
        render_piety_track_variant_svg(layout, vp_values, variant) for variant in layout["variants"]
    )


def render_piety_track_html(layout: dict, piety_config: dict) -> str:
    vp_values = piety_vp_values(piety_config)
    rows = "\n".join(
        '    <div class="track-row">\n'
        f"      {render_piety_track_variant_svg(layout, vp_values, variant)}\n"
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
<title>Pilgrim — Piety Tracks (generated)</title>
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
    max-width: 640px;
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
  <h1>{escape(layout["title"])}</h1>
  <p class="subtitle">{escape(subtitle)}</p>
  <div class="board-wrap">
{rows}
  </div>
</body>
</html>
"""
