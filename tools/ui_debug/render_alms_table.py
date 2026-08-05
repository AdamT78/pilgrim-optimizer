"""Structured renderer for the Alms Table debug view.

One grey strip split by a rule into the two things the board tracks. Left of the rule is the
race: steps `0` to `6`, a pocket for the first disc to reach the top, and the threshold rewards
printed underneath against the steps that pay them. Right of it is the record, which is what
survives the round reset: a dashed socket per round over the season-end scoring key.

Where the baseline draws a full 2x2 of discs on every step, as a diagram of where discs go, this
renderer draws player state: one disc per player, at the step that player stands on. They all
start at `0`, and `render_alms_table_svg(..., positions=...)` is what a later PR moves them with.
Nothing here reads or writes `GameState`, and no rule decides where a disc may go.

This is a debug/visual tool only. It reads `alms_table_layout.json` for geometry and
`configs/alms.json` for everything the board says about the game: how far the track runs, which
steps pay a reward, and the season-end VP per cube. Those numbers are deliberately not copied into
the layout JSON — the config is the game's source of truth for them, and it is parsed here with
the game's own `alms_from_dict`, so a change to the Alms table shows up in this view without
anyone editing the UI layer. What the layout does own is the prose beside each reward, which is
display copy the config has no opinion about.

Geometry constants mirror `prototypes/alms_table.html`, which stays the visual baseline.
`prototype_sources/alms_table.py.txt` is the reference for how that baseline was drawn; it is
read, never imported or executed. The pieces are shared rather than reinvented: the disc is the
piety-track disc at a larger radius, the star is the piety-track star, and the cube is the mancala
board's cube.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from xml.sax.saxutils import escape

from pilgrim.model.config import AlmsConfig, alms_from_dict

LAYOUT_FILENAME = "alms_table_layout.json"
ALMS_CONFIG_RELATIVE_PATH = ("configs", "alms.json")

INK_FONT = "Helvetica, Arial, sans-serif"
TITLE_FONT = "Georgia, 'Times New Roman', serif"
SOCKET_DASH = "3,2.5"

# Offsets the baseline holds as constants rather than per-anchor data.
NUMBER_FONT_SIZE = 11
BONUS_LABEL_FONT_SIZE = 8
BADGE_WIDTH = 18
BADGE_HEIGHT = 15
BADGE_LABEL_OFFSET = 3.9
REWARD_TEXT_GAP = 16
REWARD_TEXT_OFFSET = 3.8
REWARD_FONT_SIZE = 10.5
TICK_WIDTH = 6
TICK_HEIGHT = 4.5
ROUND_LABEL_FONT_SIZE = 7.5
STAR_LABEL_OFFSET = 3.0
STAR_LABEL_FONT_SIZE = 9

COMPONENT_NAME = "alms-table"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_layout_path() -> Path:
    return Path(__file__).resolve().parent / LAYOUT_FILENAME


def default_alms_config_path() -> Path:
    return repo_root().joinpath(*ALMS_CONFIG_RELATIVE_PATH)


def load_alms_table_layout(path: Path | None = None) -> dict:
    layout_path = default_layout_path() if path is None else Path(path)
    return json.loads(layout_path.read_text(encoding="utf-8"))


def load_alms_config(path: Path | None = None) -> dict:
    config_path = default_alms_config_path() if path is None else Path(path)
    return json.loads(config_path.read_text(encoding="utf-8"))


def alms_rules(config: dict) -> AlmsConfig:
    """The Alms track bounds, rewards, and scoring, read with the game's own config reader."""
    return alms_from_dict(config)


def step_centers(layout: dict) -> list[float]:
    return list(layout["track"]["step_centers"])


def position_by_index(layout: dict, index: int) -> dict:
    """The step a disc stands on, by its Alms position."""
    centers = step_centers(layout)
    if not 0 <= index < len(centers):
        raise KeyError(f"no alms position {index}")
    return {"index": index, "label": str(index), "center_x": centers[index]}


def players_of(layout: dict) -> list[dict]:
    return list(layout["players"])


def initial_positions(layout: dict) -> dict[str, int]:
    """Every player on the starting step, which is where a round leaves them."""
    start = layout["starting_position"]
    return {player["id"]: start for player in players_of(layout)}


def threshold_rewards(layout: dict, rules: AlmsConfig) -> list[dict]:
    """One row per reward the config pays, with the prose the layout prints for it."""
    text_by_reward = layout["reward_text"]
    rows = layout["threshold_rows"]
    result = []
    for order, (position, reward) in enumerate(rules.threshold_rewards):
        if reward not in text_by_reward:
            raise ValueError(f"alms layout has no reward text for {reward!r}")
        result.append(
            {
                "position": position,
                "reward": reward,
                "text": text_by_reward[reward],
                "center_x": rows["badge_center_x"],
                "center_y": rows["first_row_center_y"] + order * rows["row_height"],
            }
        )
    return result


def scoring_key_rows(layout: dict, rules: AlmsConfig) -> list[dict]:
    """Cubes owned to VP. Row `0` scores nothing, so the board does not print it."""
    key = layout["record"]["scoring_key"]
    return [
        {
            "rank": cubes,
            "cubes": cubes,
            "vp": vp,
            "center_y": key["first_row_center_y"] + (cubes - 1) * key["row_height"],
        }
        for cubes, vp in enumerate(rules.alms_table_scoring)
        if cubes > 0
    ]


def placeholder_slots(layout: dict, rules: AlmsConfig) -> list[dict]:
    """One empty cube space per round.

    The board caps at as many cubes as the scoring key has rows, so an impossible extra one has
    nowhere to go — four rounds, four cubes, four sockets.
    """
    slots = layout["record"]["placeholder_slots"]
    cube = layout["record"]["cube"]
    pitch = cube["size"] + cube["gap"]
    return [
        {
            "slot": row["rank"],
            "round": row["rank"],
            "center_x": slots["first_center_x"] + (row["rank"] - 1) * pitch,
            "center_y": slots["center_y"],
            "label_y": slots["label_y"],
        }
        for row in scoring_key_rows(layout, rules)
    ]


def disc_center(layout: dict, player: dict, index: int) -> tuple[float, float]:
    """Where one player's disc sits on a step: its own corner of the 2x2.

    The step pitch is fixed, so a larger disc buys its size out of the gap between discs rather
    than out of the step spacing, which is what keeps four of them clear of the step rules.
    """
    disc = layout["disc"]
    offset = disc["radius"] + disc["grid_gap"] / 2
    seat = player["seat"]
    return (
        position_by_index(layout, index)["center_x"] + seat["column"] * offset,
        layout["track"]["disc_grid_center_y"] + seat["row"] * offset,
    )


def _f(value: float) -> str:
    return f"{value:.1f}"


def _n(value: float) -> str:
    """Sizes the baseline prints as written: `13`, not `13.0`."""
    return f"{value:g}"


def _text(
    x: float,
    y: float,
    value: str,
    *,
    size: float,
    fill: str,
    anchor: str = "middle",
    weight: str | None = "600",
    font: str = INK_FONT,
) -> str:
    weight_attr = f' font-weight="{weight}"' if weight is not None else ""
    return (
        f'<text x="{_f(x)}" y="{_f(y)}" text-anchor="{anchor}"'
        f' font-family="{font}" font-size="{_n(size)}"{weight_attr}'
        f' fill="{fill}">{escape(value)}</text>'
    )


def _label(layout: dict, x: float, y: float, value: str, size: float) -> str:
    return _text(x, y, value, size=size, fill=layout["palette"]["ink"])


def render_player_disc(layout: dict, player: dict, index: int) -> str:
    """One player's disc, tagged with who it belongs to and where it stands."""
    disc = layout["disc"]
    center_x, center_y = disc_center(layout, player, index)
    return (
        f'<circle cx="{_f(center_x)}" cy="{_f(center_y)}" r="{_n(disc["radius"])}"'
        f' fill="{player["fill"]}" stroke="{player["stroke"]}"'
        f' stroke-width="{_n(disc["stroke_width"])}"'
        f' data-player-disc="true" data-player="{player["id"]}"'
        f' data-player-color="{player["color"]}" data-alms-position="{index}"/>'
    )


def _disc_socket(layout: dict, center_x: float, center_y: float) -> str:
    disc = layout["disc"]
    return (
        f'<circle cx="{_f(center_x)}" cy="{_f(center_y)}" r="{_n(disc["radius"])}"'
        f' fill="{layout["palette"]["socket_fill"]}" stroke="{layout["palette"]["ink"]}"'
        f' stroke-width="{_n(disc["stroke_width"])}" stroke-dasharray="{SOCKET_DASH}"/>'
    )


def _effect_tick(layout: dict, center_x: float) -> str:
    """The mark under a step that pays a reward, pointing down at its text."""
    y = layout["track"]["effect_tick_y"]
    return (
        f'<path d="M {_f(center_x - TICK_WIDTH / 2)},{_f(y)}'
        f' L {_f(center_x + TICK_WIDTH / 2)},{_f(y)}'
        f' L {_f(center_x)},{_f(y + TICK_HEIGHT)} Z"'
        f' fill="{layout["palette"]["ink"]}" fill-opacity="0.65"/>'
    )


def _bonus_pocket(layout: dict) -> str:
    """Single-disc space for the first player to reach the top step — rounded, not square."""
    pocket = layout["track"]["bonus_pocket"]
    center_x, center_y = pocket["center_x"], pocket["center_y"]
    width, height = pocket["width"], pocket["height"]
    return (
        f'<rect x="{_f(center_x - width / 2)}" y="{_f(center_y - height / 2)}"'
        f' width="{_n(width)}" height="{_n(height)}"'
        f' rx="{_f(height / 2)}" ry="{_f(height / 2)}"'
        f' fill="{layout["board"]["fill"]}" stroke="{layout["palette"]["ink"]}"'
        ' stroke-width="1.4"/>'
    ) + _disc_socket(layout, center_x, center_y)


def render_threshold_reward(layout: dict, reward: dict) -> str:
    """A reward line: the step number in a badge, then what that step pays."""
    ink = layout["palette"]["ink"]
    center_x, center_y = reward["center_x"], reward["center_y"]
    badge = (
        f'<rect x="{_f(center_x - BADGE_WIDTH / 2)}" y="{_f(center_y - BADGE_HEIGHT / 2)}"'
        f' width="{_n(BADGE_WIDTH)}" height="{_n(BADGE_HEIGHT)}" rx="3"'
        f' fill="{layout["palette"]["socket_fill"]}" stroke="{ink}" stroke-width="1.1"/>'
    )
    number = _label(
        layout, center_x, center_y + BADGE_LABEL_OFFSET, str(reward["position"]), NUMBER_FONT_SIZE
    )
    text = _text(
        center_x + REWARD_TEXT_GAP,
        center_y + REWARD_TEXT_OFFSET,
        reward["text"],
        size=REWARD_FONT_SIZE,
        fill=ink,
        anchor="start",
        weight=None,
    )
    return (
        f'<g data-alms-threshold="{reward["position"]}"'
        f' data-alms-reward="{reward["reward"]}">{badge}{number}{text}</g>'
    )


def render_placeholder_slot(layout: dict, slot: dict) -> str:
    """An empty cube space, for the coloured player cube a later PR will cover it with."""
    ink = layout["palette"]["ink"]
    size = layout["record"]["cube"]["size"]
    center_x, center_y = slot["center_x"], slot["center_y"]
    socket = (
        f'<rect x="{_f(center_x - size / 2)}" y="{_f(center_y - size / 2)}"'
        f' width="{_n(size)}" height="{_n(size)}"'
        f' fill="{layout["palette"]["socket_fill"]}" stroke="{ink}" stroke-width="1.4"'
        f' stroke-dasharray="{SOCKET_DASH}"'
        f' data-placeholder-slot="{slot["slot"]}" data-round="{slot["round"]}"/>'
    )
    return socket + _label(
        layout, center_x, slot["label_y"], str(slot["round"]), ROUND_LABEL_FONT_SIZE
    )


def _star_path_data(cx: float, cy: float, outer_r: float, inner_r: float) -> str:
    points: list[tuple[float, float]] = []
    step = math.pi / 5
    start = math.radians(-90)
    for i in range(10):
        radius = outer_r if i % 2 == 0 else inner_r
        angle = start + i * step
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return "M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in points) + " Z"


def _scoring_key_row(layout: dict, row: dict) -> str:
    """`n` cubes owned pays the star beside them. Solid grey: printed reference, not a space."""
    palette = layout["palette"]
    key = layout["record"]["scoring_key"]
    cube = layout["record"]["cube"]
    size, pitch = cube["size"], cube["size"] + cube["gap"]
    center_y = row["center_y"]

    cubes = "".join(
        f'<rect x="{_f(key["first_cube_center_x"] + k * pitch - size / 2)}"'
        f' y="{_f(center_y - size / 2)}" width="{_n(size)}" height="{_n(size)}"'
        f' fill="{palette["key_cube_fill"]}" stroke="{palette["key_cube_stroke"]}"'
        ' stroke-width="1.5"/>'
        for k in range(row["cubes"])
    )
    outer = key["star_outer_radius"]
    star_x = key["star_center_x"]
    star = (
        f'<path d="{_star_path_data(star_x, center_y, outer, outer * key["star_inner_ratio"])}"'
        f' fill="{palette["star_fill"]}" stroke="{palette["star_stroke"]}"'
        ' stroke-width="1.5" stroke-linejoin="round"/>'
    )
    label = _text(
        star_x,
        center_y + STAR_LABEL_OFFSET,
        str(row["vp"]),
        size=STAR_LABEL_FONT_SIZE,
        fill=palette["star_label_fill"],
    )
    return (
        f'<g data-season-end-rank="{row["rank"]}" data-season-end-cubes="{row["cubes"]}"'
        f' data-season-end-vp="{row["vp"]}">{cubes}{star}{label}</g>'
    )


def _trefoil_rule(layout: dict) -> str:
    """The board's title motif, stretched from the title across to the zone divider."""
    trefoil = layout["ornament"]["trefoil"]
    x0, x1, y = trefoil["x0"], trefoil["x1"], trefoil["y"]
    radius, gap = trefoil["lobe_radius"], trefoil["rule_gap"]
    cx = (x0 + x1) / 2
    lobes = "".join(
        f'<circle cx="{_f(cx + radius * math.cos(math.radians(a)))}"'
        f' cy="{_f(y + radius * math.sin(math.radians(a)))}" r="{_n(radius)}" />'
        for a in (-90, 30, 150)
    )
    return (
        f'<g fill="none" stroke="{layout["palette"]["ink"]}" stroke-opacity="0.34"'
        f' stroke-width="1.3" stroke-linecap="round">{lobes}'
        f'<path d="M {_f(x0)},{_f(y)} H {_f(cx - gap)}'
        f' M {_f(cx + gap)},{_f(y)} H {_f(x1)}" /></g>'
    )


def _race_zone(layout: dict, rules: AlmsConfig, positions: dict[str, int]) -> str:
    track = layout["track"]
    ink = layout["palette"]["ink"]
    centers = step_centers(layout)
    rewarded = {reward["position"] for reward in threshold_rewards(layout, rules)}
    parts: list[str] = []

    for index, center_x in enumerate(centers):
        step = [_label(layout, center_x, track["number_label_y"], str(index), NUMBER_FONT_SIZE)]
        # Player state, not the baseline's full 2x2: a disc appears only where a player stands.
        step += [
            render_player_disc(layout, player, index)
            for player in players_of(layout)
            if positions.get(player["id"]) == index
        ]
        if index in rewarded:
            step.append(_effect_tick(layout, center_x))
        parts.append(f'<g data-alms-position="{index}">{"".join(step)}</g>')

    pocket = track["bonus_pocket"]
    parts.append(
        '<g data-alms-bonus-pocket="true">'
        + _label(
            layout,
            pocket["center_x"],
            track["number_label_y"],
            pocket["label"],
            BONUS_LABEL_FONT_SIZE,
        )
        + _bonus_pocket(layout)
        + "</g>"
    )

    rule = track["step_rule"]
    pitch = track["step_pitch"]
    first_x = centers[0] - pitch / 2
    parts += [
        f'<line x1="{_f(first_x + i * pitch)}" y1="{_f(rule["y1"])}"'
        f' x2="{_f(first_x + i * pitch)}" y2="{_f(rule["y2"])}"'
        f' stroke="{ink}" stroke-opacity="0.22" stroke-width="1"/>'
        for i in range(1, len(centers) + 1)
    ]
    parts += [
        render_threshold_reward(layout, reward) for reward in threshold_rewards(layout, rules)
    ]
    return "".join(parts)


def _record_zone(layout: dict, rules: AlmsConfig) -> str:
    record = layout["record"]
    ink = layout["palette"]["ink"]
    heading = record["heading"]
    rule = record["rule"]

    return "".join(
        [
            _label(layout, heading["x"], heading["y"], heading["text"], heading["font_size"]),
            "".join(
                render_placeholder_slot(layout, slot)
                for slot in placeholder_slots(layout, rules)
            ),
            f'<line x1="{_f(rule["x1"])}" y1="{_f(rule["y"])}" x2="{_f(rule["x2"])}"'
            f' y2="{_f(rule["y"])}" stroke="{ink}" stroke-opacity="0.25" stroke-width="1"/>',
            "".join(_scoring_key_row(layout, row) for row in scoring_key_rows(layout, rules)),
        ]
    )


def render_alms_table_svg(
    layout: dict,
    config: dict,
    positions: dict[str, int] | None = None,
) -> str:
    """The board, with each player's disc on the step `positions` puts them on.

    Defaults to the start of a round, every disc on `0`. Passing `positions` is how a later PR
    will move them; it is a picture of state, not a rule about which moves are legal.
    """
    rules = alms_rules(config)
    centers = step_centers(layout)
    if len(centers) != rules.max_position + 1:
        raise ValueError(
            f"alms config runs 0..{rules.max_position} but the layout draws {len(centers)} steps"
        )

    where = initial_positions(layout) if positions is None else dict(positions)
    board = layout["board"]
    palette = layout["palette"]
    view = board["view_box"]
    width, height = view["width"], view["height"]
    panel_w, panel_h = board["panel_width"], board["panel_height"]
    inset = board["inset"]
    divider = layout["zone_divider"]

    background = (
        f'<rect x="{_n(view["min_x"])}" y="{_n(view["min_y"])}"'
        f' width="{_f(width)}" height="{_f(height)}" fill="{layout["page_background"]}"/>'
    )
    panel = (
        f'<rect x="0" y="0" width="{_f(panel_w)}" height="{_f(panel_h)}"'
        f' rx="{_n(board["corner_radius"])}" ry="{_n(board["corner_radius"])}"'
        f' fill="{board["fill"]}" stroke="{board["stroke"]}"'
        f' stroke-width="{_n(board["stroke_width"])}"/>'
    )
    title_anchor = board["title_anchor"]
    title = _text(
        title_anchor["x"],
        title_anchor["y"],
        layout["title"],
        size=board["title_font_size"],
        fill=palette["ink"],
        anchor="start",
        weight="700",
        font=TITLE_FONT,
    )
    # Hairline inside the panel edge; the radius shrinks with the inset to stay concentric.
    panel_inset = (
        f'<rect x="{_n(inset)}" y="{_n(inset)}" width="{_f(panel_w - 2 * inset)}"'
        f' height="{_f(panel_h - 2 * inset)}"'
        f' rx="{_f(board["corner_radius"] - inset)}" ry="{_f(board["corner_radius"] - inset)}"'
        f' fill="none" stroke="{palette["ink"]}" stroke-opacity="0.28" stroke-width="1.2"/>'
    )
    # Everything left of this line is wiped between rounds; everything right of it accumulates.
    zone_divider = (
        f'<line x1="{_f(divider["x"])}" y1="{_f(divider["y1"])}" x2="{_f(divider["x"])}"'
        f' y2="{_f(divider["y2"])}" stroke="{palette["ink"]}" stroke-opacity="0.45"'
        ' stroke-width="1.4"/>'
    )

    body = "".join(
        [
            panel,
            title,
            panel_inset,
            _race_zone(layout, rules, where),
            _trefoil_rule(layout),
            zone_divider,
            _record_zone(layout, rules),
        ]
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg"'
        f' viewBox="{_n(view["min_x"])} {_n(view["min_y"])} {_f(width)} {_f(height)}"'
        f' width="{_f(width)}" height="{_f(height)}"'
        f' data-component="{COMPONENT_NAME}">'
        f"\n  {background}\n  {body}\n</svg>"
    )


def render_alms_table_html(
    layout: dict,
    config: dict,
    positions: dict[str, int] | None = None,
) -> str:
    start = layout["starting_position"]
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Pilgrim — {escape(layout["title"])} (generated)</title>
<style>
  body {{
    margin: 0;
    background: {layout["page_background"]};
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
    max-width: 760px;
  }}
  .board-wrap {{
    background: {layout["page_background"]};
    border: 1px solid #333333;
    border-radius: 10px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.5);
    padding: 10px;
  }}
  .board-wrap svg {{ display: block; max-width: 95vw; height: auto; }}
</style>
</head>
<body>
  <h1>{escape(layout["title"])}</h1>
  <p class="subtitle">{escape(layout["subtitle"])}
  All four player discs start at step {start}. Generated from {LAYOUT_FILENAME}, with the track
  bounds, rewards, and VP values from {"/".join(ALMS_CONFIG_RELATIVE_PATH)}.</p>
  <div class="board-wrap">
    {render_alms_table_svg(layout, config, positions)}
  </div>
</body>
</html>
"""
