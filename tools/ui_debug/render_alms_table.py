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

Geometry constants mirror `prototypes/alms_table.html`, which stays the baseline for the race:
the steps, the rules between them, the ticks and the reward lines are still drawn exactly as it
draws them. What has moved away from it is the record. The board is wider than the prototype's,
because in the composed game table it stands over two seats and should be as wide as they are, and
that width was bought in its own units rather than by scaling the board up. The room it bought
went right of the zone divider, where the season-end cubes are now the cube a player board plays
with rather than a larger one of this board's own. `prototype_sources/alms_table.py.txt` is the
reference for how the baseline was drawn; it is read, never imported or executed.

The pieces are shared rather than reinvented: the disc is the piety-track disc at a larger radius,
the star is the piety-track star, and the cube is the one on Player Board v2.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from xml.sax.saxutils import escape

from pilgrim.model.config import AlmsConfig, alms_from_dict
from tools.ui_debug.render_player_boards_v2 import ROLE_FONT_SIZE as PLAYER_LABEL_FONT_SIZE
from tools.ui_debug.render_player_boards_v2 import TOKEN_GAP as PLAYER_CUBE_GAP
from tools.ui_debug.render_player_boards_v2 import TOKEN_RADIUS as PLAYER_CUBE_RADIUS

LAYOUT_FILENAME = "alms_table_layout.json"
ALMS_CONFIG_RELATIVE_PATH = ("configs", "alms.json")

INK_FONT = "Helvetica, Arial, sans-serif"
TITLE_FONT = "Georgia, 'Times New Roman', serif"
SOCKET_DASH = "3,2.5"

# What one player board unit measures here.
#
# The game table hands this board the piety track's scale rather than the seats' width, because
# the two draw the same player disc and pinning them together is what makes that disc come out the
# same size on both. The piety track's units are the smaller of the two, so a unit here renders
# 1.48688 of the pixels a player board unit does. That ratio belongs to the composed table, not to
# either board, and the game table tests check it against the real solve rather than trusting the
# number written here -- which is why it is re-solved whenever the table is recomposed. Growing the
# building slots to the size of a map hex moved it last, by a third of a percent: the slots took a
# zigzag to keep the board's width, which made a seat taller and so drawn a little smaller.
#
# So anything meant to read at the same size as its counterpart on a seat is that board's size in
# PLAYER_UNITs. It was also once why this board is 536 units wide: at the ratio that held then,
# that came out a seat's width exactly. It no longer does -- the seats are drawn at the duty
# wheel's scale now rather than stretched to its height, which made them narrower -- so this board
# renders about a seventh wider than a seat until its own width is re-fitted.
UNITS_PER_PLAYER_UNIT = 1.49227
PLAYER_UNIT = 1 / UNITS_PER_PLAYER_UNIT

# A cube is a cube wherever it is played, so the season-end cubes are a seat's cube and the air
# between them is the air between the ones in a Village grid. Both are taken from the seats rather
# than written here, and a seat takes them from the duty wheel, so the three boards draw one piece
# at one size. Rounded to the hundredth the board writes its geometry in; a thousandth of a unit is
# nothing anyone can see.
#
# A seat places a cube by its centre and so keeps a radius; this board asks for the side, which is
# the number every socket and every printed cube here is drawn from.
#
# There are no cubes above or below each other on this board, so only the side-to-side gap crosses
# over. The scoring key's rows are a star apart, not a cube apart -- `row_height` in the layout is
# the star's own diameter -- and that is the star's spacing to set, not the cube's.
PLAYER_CUBE = 2 * PLAYER_CUBE_RADIUS
CUBE_SIZE = round(PLAYER_CUBE * PLAYER_UNIT, 2)
CUBE_GAP = round(PLAYER_CUBE_GAP * PLAYER_UNIT, 2)
CUBE_PITCH = CUBE_SIZE + CUBE_GAP

# `Season end winners` and the `2`/`4`/`6` the rewards are filed under both read as the seats'
# special activity labels -- `Fields`, `Stone Mason` -- do.
SEASON_END_LABEL_FONT_SIZE = round(PLAYER_LABEL_FONT_SIZE * PLAYER_UNIT, 2)
THRESHOLD_LABEL_FONT_SIZE = SEASON_END_LABEL_FONT_SIZE

# The header motif is the duty wheel's, at the size that board draws it. There a trefoil lobe is
# 4.6 units against a 13.0-unit cube, the rule holds 15.0 clear either side of the lobes before it
# starts, and each arm then runs 29.0 further -- 0.354, 1.154 and 2.231 cubes. Cubes are what the
# game table makes agree across boards drawn at different scales, so carrying the motif over in
# cubes is what puts the two ornaments at the same size on screen.
#
# The arms are the one departure. On the wheel each runs out to the end of that space's cube tally,
# which is far narrower than this header, so at that length the rule reads as two ticks beside the
# lobes rather than as a rule. Here the right arm runs out to ORNAMENT_RULE_CLEARANCE short of the
# zone divider, and the left one takes the same length back the other way rather than a reach of
# its own, so the mark stays symmetrical about the lobes. That leaves the left arm ending clear of
# the title, which is the other thing it must not touch; the tests hold it to both.
ORNAMENT_TREFOIL_RADIUS = 0.3538 * CUBE_SIZE
ORNAMENT_RULE_GAP = 1.1538 * CUBE_SIZE
ORNAMENT_RULE_CLEARANCE = 8.0
ORNAMENT_STROKE_WIDTH = 0.1 * CUBE_SIZE
ORNAMENT_STROKE_OPACITY = "0.34"
ORNAMENT_LOBE_ANGLES = (-90, 30, 150)

# The board's name, and the rules that divide one step of the track from the next. Both are style
# rather than layout -- where the title sits and where the rules fall are this board's business,
# but how they are drawn is the house's -- so they are constants the piety track can be drawn from
# too, rather than numbers buried in this board's layout JSON.
TITLE_FONT_SIZE = 15
TITLE_FONT_WEIGHT = "700"
LABEL_FONT_WEIGHT = "600"
STEP_RULE_STROKE_OPACITY = "0.22"
STEP_RULE_STROKE_WIDTH = 1

# Offsets the baseline holds as constants rather than per-anchor data.
STEP_NUMBER_FONT_SIZE = 11
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
# The star a score is printed in, and the score inside it. The VP reads as the track's own step
# numbers do, and its baseline sits a third of the size below the star's centre, which is what puts
# the middle of the digits on it -- so the offset follows the size rather than being set beside it.
# The star is drawn big enough to hold two of those digits between its inner points.
STAR_OUTER_RADIUS = 18
STAR_INNER_RATIO = 0.45
STAR_INNER_RADIUS = STAR_OUTER_RADIUS * STAR_INNER_RATIO
STAR_LABEL_FONT_SIZE = STEP_NUMBER_FONT_SIZE
STAR_LABEL_OFFSET = STAR_LABEL_FONT_SIZE / 3

# The place past the last step: the `1st` pocket on the race track, for the first disc to reach the
# top. It is a space on the track, not one of the record's cube sockets, and not a score.
RANK_FIRST = "rank_1st"

# A disc stands on a numbered step, or in the `1st` pocket past the last one.
Positions = dict[str, int | str]

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


def initial_positions(layout: dict) -> Positions:
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

    The row centres itself under the heading it sits below rather than starting at an x the layout
    names. Where it starts depends on the cube and the air around it, and both of those are the
    seats' to set, so a number here would be one that has to be recomputed by hand every time the
    cube moves — which is exactly what it was when the cube last moved.
    """
    slots = layout["record"]["placeholder_slots"]
    record = layout["record"]
    row_count = len(scoring_key_rows(layout, rules))
    first_center_x = record["x"] + record["width"] / 2 - (row_count - 1) * CUBE_PITCH / 2
    return [
        {
            "slot": row["rank"],
            "round": row["rank"],
            "center_x": first_center_x + (row["rank"] - 1) * CUBE_PITCH,
            "center_y": slots["center_y"],
            "label_y": slots["label_y"],
        }
        for row in scoring_key_rows(layout, rules)
    ]


def season_end_slot_by_index(layout: dict, rules: AlmsConfig, index: int) -> dict:
    """A season-end winner slot by its 1-based number, left to right."""
    for slot in placeholder_slots(layout, rules):
        if slot["slot"] == index:
            return slot
    raise KeyError(f"no season end winner slot {index}")


def mover_path(rules: AlmsConfig) -> list[int | str]:
    """Everywhere the moving disc can stand, in order: the steps, then the `1st` pocket."""
    return [*range(rules.max_position + 1), RANK_FIRST]


def next_mover_position(rules: AlmsConfig, position: int | str) -> int | str:
    """One step up the track, and off the end of it into the `1st` pocket."""
    path = mover_path(rules)
    return path[min(path.index(position) + 1, len(path) - 1)]


def previous_mover_position(rules: AlmsConfig, position: int | str) -> int | str:
    """One step back down, which drops out of the `1st` pocket onto the last step."""
    path = mover_path(rules)
    return path[max(path.index(position) - 1, 0)]


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


def alms_position_target(
    layout: dict, rules: AlmsConfig, player: dict, position: int | str
) -> tuple[float, float]:
    """Where a disc sits for a track step, or for the `1st` pocket past the last step.

    The pocket holds one disc, so a disc there takes the pocket's own centre rather than its seat
    corner in the 2x2 it shares with three others on a step.
    """
    if position == RANK_FIRST:
        return bonus_pocket_center_x(layout), layout["track"]["bonus_pocket"]["center_y"]
    return disc_center(layout, player, position)


def _f(value: float) -> str:
    return f"{value:.1f}"


def _n(value: float) -> str:
    """Sizes the baseline prints as written: `13`, not `13.0`."""
    return f"{value:g}"


def cube_rect(center_x: float, center_y: float) -> str:
    """The box every cube on this board is drawn in, whether it is a socket or a cube in one.

    One helper for all of them, so a placed cube covers the dashed socket it fills exactly rather
    than nearly: same centre, same size, same rounding, so there is no way for the two to drift.
    """
    return (
        f'x="{_f(center_x - CUBE_SIZE / 2)}" y="{_f(center_y - CUBE_SIZE / 2)}"'
        f' width="{_f(CUBE_SIZE)}" height="{_f(CUBE_SIZE)}"'
    )


def ornament_rule_arm(layout: dict) -> float:
    """How far each arm of the header rule runs out from the gap around the lobes.

    The right one is the one with somewhere to be: it stops just short of the zone divider, which
    is what closes the header. The left one is given the same length rather than a reach of its
    own, so the mark is symmetrical about the lobes wherever they are put.
    """
    trefoil = layout["ornament"]["trefoil"]
    reach = layout["zone_divider"]["x"] - ORNAMENT_RULE_CLEARANCE - trefoil["center_x"]
    return reach - ORNAMENT_RULE_GAP


def bonus_pocket_center_x(layout: dict) -> float:
    """The middle of the lane the `1st` pocket stands in.

    That lane is what is left of the track past the last step's rule, and it is wider than a step
    because the zone divider, not the track's pitch, is what closes it. Centring the pocket in it
    is measured rather than written down, so the air either side of the pocket stays equal.
    """
    track = layout["track"]
    centers = step_centers(layout)
    last_rule_x = centers[0] - track["step_pitch"] / 2 + len(centers) * track["step_pitch"]
    return (last_rule_x + layout["zone_divider"]["x"]) / 2


def _text(
    x: float,
    y: float,
    value: str,
    *,
    size: float,
    fill: str,
    anchor: str = "middle",
    weight: str | None = LABEL_FONT_WEIGHT,
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


def render_player_disc(layout: dict, rules: AlmsConfig, player: dict, position: int | str) -> str:
    """One player's disc, tagged with who it belongs to and where it stands."""
    disc = layout["disc"]
    center_x, center_y = alms_position_target(layout, rules, player, position)
    return (
        f'<circle cx="{_f(center_x)}" cy="{_f(center_y)}" r="{_n(disc["radius"])}"'
        f' fill="{player["fill"]}" stroke="{player["stroke"]}"'
        f' stroke-width="{_n(disc["stroke_width"])}"'
        f' data-player-disc="true" data-player="{player["id"]}"'
        f' data-player-color="{player["color"]}" data-alms-position="{position}"/>'
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
        f" L {_f(center_x + TICK_WIDTH / 2)},{_f(y)}"
        f' L {_f(center_x)},{_f(y + TICK_HEIGHT)} Z"'
        f' fill="{layout["palette"]["ink"]}" fill-opacity="0.65"/>'
    )


def _bonus_pocket(layout: dict) -> str:
    """Single-disc space for the first player to reach the top step — rounded, not square."""
    pocket = layout["track"]["bonus_pocket"]
    center_x, center_y = bonus_pocket_center_x(layout), pocket["center_y"]
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
        layout,
        center_x,
        center_y + BADGE_LABEL_OFFSET,
        str(reward["position"]),
        THRESHOLD_LABEL_FONT_SIZE,
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
    cube = layout["record"]["cube"]
    center_x, center_y = slot["center_x"], slot["center_y"]
    socket = (
        f"<rect {cube_rect(center_x, center_y)}"
        f' fill="{layout["palette"]["socket_fill"]}" stroke="{ink}"'
        f' stroke-width="{_n(cube["stroke_width"])}" stroke-dasharray="{SOCKET_DASH}"'
        f' data-placeholder-slot="{slot["slot"]}" data-round="{slot["round"]}"/>'
    )
    return socket + _label(
        layout, center_x, slot["label_y"], str(slot["round"]), ROUND_LABEL_FONT_SIZE
    )


def render_winner_cube(layout: dict, slot: dict, player: dict, visible: bool = True) -> str:
    """A round winner's cube, exactly the size of the slot it fills, so it covers it completely.

    This is the player's own cube from their board, not a new piece, so it carries the Player
    Board v2 cube colours rather than the piety-track disc colours the track uses.
    """
    cube = layout["record"]["cube"]
    center_x, center_y = slot["center_x"], slot["center_y"]
    return (
        f"<rect {cube_rect(center_x, center_y)}"
        f' fill="{player["cube_fill"]}" stroke="{player["cube_stroke"]}"'
        f' stroke-width="{_n(cube["stroke_width"])}" opacity="{1 if visible else 0:g}"'
        f' data-season-end-winner-slot="{slot["slot"]}" data-player="{player["id"]}"'
        f' data-player-color="{player["color"]}"/>'
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
    center_y = row["center_y"]

    cubes = "".join(
        f"<rect {cube_rect(key['first_cube_center_x'] + k * CUBE_PITCH, center_y)}"
        f' fill="{palette["key_cube_fill"]}" stroke="{palette["key_cube_stroke"]}"'
        f' stroke-width="{_n(cube["stroke_width"])}"/>'
        for k in range(row["cubes"])
    )
    star_x = key["star_center_x"]
    star = (
        f'<path d="{_star_path_data(star_x, center_y, STAR_OUTER_RADIUS, STAR_INNER_RADIUS)}"'
        f' fill="{palette["star_fill"]}" stroke="{palette["star_stroke"]}"'
        ' stroke-width="1.5" stroke-linejoin="round"/>'
    )
    label = _text(
        star_x,
        center_y + STAR_LABEL_OFFSET,
        str(row["vp"]),
        size=STAR_LABEL_FONT_SIZE,
        fill=palette["star_label_fill"],
        weight=None,
    )
    return (
        f'<g data-season-end-rank="{row["rank"]}" data-season-end-cubes="{row["cubes"]}"'
        f' data-season-end-vp="{row["vp"]}">{cubes}{star}{label}</g>'
    )


def _trefoil_rule(layout: dict) -> str:
    """The board's title motif: the duty wheel's trefoil, on a rule that spans this board's header.

    The lobes and the air they hold are the wheel's own, so the mark reads at the size it does over
    every duty there. The rule they sit on is this header's, since it has a header to span and the
    wheel does not; what it used to be was the wheel's lobes scaled up with it.
    """
    trefoil = layout["ornament"]["trefoil"]
    cx, y = trefoil["center_x"], trefoil["y"]
    radius = ORNAMENT_TREFOIL_RADIUS
    lobes = "".join(
        f'<circle cx="{_f(cx + radius * math.cos(math.radians(a)))}"'
        f' cy="{_f(y + radius * math.sin(math.radians(a)))}" r="{_f(radius)}" />'
        for a in ORNAMENT_LOBE_ANGLES
    )
    inner = ORNAMENT_RULE_GAP
    outer = inner + ornament_rule_arm(layout)
    return (
        f'<g fill="none" stroke="{layout["palette"]["ink"]}"'
        f' stroke-opacity="{ORNAMENT_STROKE_OPACITY}"'
        f' stroke-width="{_f(ORNAMENT_STROKE_WIDTH)}" stroke-linecap="round">{lobes}'
        f'<path d="M {_f(cx - outer)},{_f(y)} H {_f(cx - inner)}'
        f' M {_f(cx + inner)},{_f(y)} H {_f(cx + outer)}" /></g>'
    )


def _race_zone(
    layout: dict, rules: AlmsConfig, positions: Positions, interactive: bool = False
) -> str:
    track = layout["track"]
    ink = layout["palette"]["ink"]
    centers = step_centers(layout)
    rewarded = {reward["position"] for reward in threshold_rewards(layout, rules)}
    parts: list[str] = []

    for index, center_x in enumerate(centers):
        step = [
            _label(layout, center_x, track["number_label_y"], str(index), STEP_NUMBER_FONT_SIZE)
        ]
        # Player state, not the baseline's full 2x2: a disc appears only where a player stands.
        # A disc that can move lives in its own layer instead, so sliding it along the track
        # does not leave it parented to the step it started on.
        if not interactive:
            step += [
                render_player_disc(layout, rules, player, index)
                for player in players_of(layout)
                if positions.get(player["id"]) == index
            ]
        if index in rewarded:
            step.append(_effect_tick(layout, center_x))
        parts.append(f'<g data-alms-position="{index}">{"".join(step)}</g>')

    pocket = track["bonus_pocket"]
    parts.append(
        f'<g data-alms-bonus-pocket="true" data-alms-position="{RANK_FIRST}">'
        + _label(
            layout,
            bonus_pocket_center_x(layout),
            track["number_label_y"],
            pocket["label"],
            BONUS_LABEL_FONT_SIZE,
        )
        + _bonus_pocket(layout)
        + "</g>"
    )

    # After the pocket, which is painted solid: a disc that can reach it must sit on top of it.
    if interactive:
        discs = "".join(
            render_player_disc(layout, rules, player, positions.get(player["id"], 0))
            for player in players_of(layout)
        )
        parts.append(f'<g data-alms-discs="true">{discs}</g>')

    rule = track["step_rule"]
    pitch = track["step_pitch"]
    first_x = centers[0] - pitch / 2
    parts += [
        f'<line x1="{_f(first_x + i * pitch)}" y1="{_f(rule["y1"])}"'
        f' x2="{_f(first_x + i * pitch)}" y2="{_f(rule["y2"])}"'
        f' stroke="{ink}" stroke-opacity="{STEP_RULE_STROKE_OPACITY}"'
        f' stroke-width="{_n(STEP_RULE_STROKE_WIDTH)}"/>'
        for i in range(1, len(centers) + 1)
    ]
    parts += [
        render_threshold_reward(layout, reward) for reward in threshold_rewards(layout, rules)
    ]
    return "".join(parts)


def _record_zone(layout: dict, rules: AlmsConfig, interactive: bool = False) -> str:
    record = layout["record"]
    ink = layout["palette"]["ink"]
    heading = record["heading"]
    rule = record["rule"]
    slots = placeholder_slots(layout, rules)

    # Every cube that could ever be placed, drawn hidden, so a click flips opacity rather than
    # building SVG in the browser: the colours and geometry stay here.
    winner_cubes = ""
    if interactive:
        winner_cubes = "".join(
            render_winner_cube(layout, slot, player, visible=False)
            for slot in slots
            for player in players_of(layout)
        )

    return "".join(
        [
            _label(layout, heading["x"], heading["y"], heading["text"], SEASON_END_LABEL_FONT_SIZE),
            "".join(render_placeholder_slot(layout, slot) for slot in slots),
            winner_cubes,
            f'<line x1="{_f(rule["x1"])}" y1="{_f(rule["y"])}" x2="{_f(rule["x2"])}"'
            f' y2="{_f(rule["y"])}" stroke="{ink}" stroke-opacity="0.25" stroke-width="1"/>',
            "".join(_scoring_key_row(layout, row) for row in scoring_key_rows(layout, rules)),
        ]
    )


def render_alms_table_svg(
    layout: dict,
    config: dict,
    positions: Positions | None = None,
    interactive: bool = False,
) -> str:
    """The board, with each player's disc on the step `positions` puts them on.

    Defaults to the start of a round, every disc on `0`. `positions` is a picture of state, not a
    rule about which moves are legal.

    `interactive` lifts the discs into their own layer and draws every winner cube hidden, so a
    page can move a disc and fill a slot without building any SVG of its own. Left off, the board
    is the fixed picture the baseline prototype draws.
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
        size=TITLE_FONT_SIZE,
        fill=palette["ink"],
        anchor="start",
        weight=TITLE_FONT_WEIGHT,
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
            _race_zone(layout, rules, where, interactive),
            _trefoil_rule(layout),
            zone_divider,
            _record_zone(layout, rules, interactive),
        ]
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg"'
        f' viewBox="{_n(view["min_x"])} {_n(view["min_y"])} {_f(width)} {_f(height)}"'
        f' width="{_f(width)}" height="{_f(height)}"'
        f' data-component="{COMPONENT_NAME}">'
        f"\n  {background}\n  {body}\n</svg>"
    )


ALMS_TABLE_CONTROL_STYLES = """  .alms-table-controls {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
    justify-content: center;
    margin: 0 0 16px;
    max-width: 760px;
  }
  .alms-table-controls button {
    background: #1C1C1C;
    border: 1px solid #4A4A4A;
    border-radius: 6px;
    color: #F2EEDF;
    cursor: pointer;
    font: inherit;
    font-size: 13px;
    padding: 7px 12px;
  }
  .alms-table-controls button:hover:enabled { background: #2A2A2A; }
  .alms-table-controls button:disabled { cursor: default; opacity: 0.4; }
  .alms-table-readout { color: #A8A296; font-size: 13px; width: 100%; text-align: center; }
"""

# Plain inline JavaScript, no dependencies. It slides a disc the renderer already drew and flips
# opacity on cubes and slots it already drew; it decides nothing about the game.
_CONTROLS_SCRIPT = """<script>
(function initAlmsTableControls() {
  var PATH = __PATH__;
  var TARGETS = __TARGETS__;
  var SLOT_COUNT = __SLOT_COUNT__;
  var RANK_FIRST = "__RANK_FIRST__";
  var MOVER = "__MOVER__";

  var board = document.querySelector('[data-component="alms-table"]');
  if (!board) { return; }
  var disc = board.querySelector('[data-player-disc="true"][data-player="' + MOVER + '"]');
  var up = document.getElementById("alms-move-up");
  var down = document.getElementById("alms-move-down");
  var readout = document.getElementById("alms-readout");
  var winnerButtons = [].slice.call(document.querySelectorAll("[data-add-winner]"));

  // Where the one moving disc stands, as an index into PATH, and which players' cubes are down
  // in the record's sockets. Debug bookkeeping only; it ranks nobody and scores nothing.
  var almsState = {
    playerPositions: __POSITIONS__,
    seasonEndWinners: []
  };

  function moveBy(step) {
    var at = PATH.indexOf(almsState.playerPositions[MOVER]);
    var next = PATH[Math.min(Math.max(at + step, 0), PATH.length - 1)];
    almsState.playerPositions[MOVER] = next;
    var target = TARGETS[next];
    disc.setAttribute("cx", target[0]);
    disc.setAttribute("cy", target[1]);
    disc.setAttribute("data-alms-position", String(next));
    refresh();
  }

  function addWinner(playerId) {
    var index = almsState.seasonEndWinners.length;
    if (index >= SLOT_COUNT) { return; }
    var slot = index + 1;
    var cube = board.querySelector(
      '[data-season-end-winner-slot="' + slot + '"][data-player="' + playerId + '"]');
    if (cube) { cube.setAttribute("opacity", "1"); }
    // The socket goes out from under its cube, so no dashed edge is left showing around it.
    var placeholder = board.querySelector('[data-placeholder-slot="' + slot + '"]');
    if (placeholder) { placeholder.setAttribute("opacity", "0"); }
    almsState.seasonEndWinners.push(playerId);
    refresh();
  }

  function refresh() {
    var at = almsState.playerPositions[MOVER];
    var placed = almsState.seasonEndWinners.length;
    up.disabled = at === PATH[PATH.length - 1];
    down.disabled = at === PATH[0];
    winnerButtons.forEach(function (button) { button.disabled = placed >= SLOT_COUNT; });
    readout.textContent =
      "__MOVER_LABEL__ " + (at === RANK_FIRST ? "in the 1st pocket" : "on step " + at)
      + " \\u00b7 " + placed + " of " + SLOT_COUNT + " winner cubes";
  }

  up.addEventListener("click", function () { moveBy(1); });
  down.addEventListener("click", function () { moveBy(-1); });
  winnerButtons.forEach(function (button) {
    button.addEventListener("click", function () { addWinner(button.dataset.addWinner); });
  });
  refresh();
})();
</script>"""


def mover_id(layout: dict) -> str:
    """The one disc these debug controls move. The other three stay where they start."""
    return players_of(layout)[0]["id"]


def disc_targets(layout: dict, rules: AlmsConfig, player_id: str) -> dict[str, list[float]]:
    """Every place a player's disc can stand, so the page moves it without recomputing geometry."""
    player = next(p for p in players_of(layout) if p["id"] == player_id)
    return {
        str(position): list(alms_position_target(layout, rules, player, position))
        for position in mover_path(rules)
    }


def render_alms_table_controls_html(layout: dict, config: dict) -> str:
    """Buttons for the one disc that moves and for filling the winner slots."""
    rules = alms_rules(config)
    start = layout["starting_position"]
    mover = next(p for p in players_of(layout) if p["id"] == mover_id(layout))
    buttons = "".join(
        f'\n    <button type="button" data-add-winner="{player["id"]}">'
        f"Add {player['color']} cube to Season end winner</button>"
        for player in players_of(layout)
    )
    # Rendered in the state the page opens in, so it reads correctly before any script runs.
    path = mover_path(rules)
    at_bottom = " disabled" if start == path[0] else ""
    at_top = " disabled" if start == path[-1] else ""
    slots = len(placeholder_slots(layout, rules))
    label = mover["label"]
    readout = f"{label} on step {start} &middot; 0 of {slots} winner cubes"
    return f"""<div class="alms-table-controls">
    <button type="button" id="alms-move-up"{at_top}>Move {label} up</button>
    <button type="button" id="alms-move-down"{at_bottom}>Move {label} down</button>{buttons}
    <span class="alms-table-readout" id="alms-readout">{readout}</span>
  </div>"""


def render_alms_table_controls_script(layout: dict, config: dict) -> str:
    rules = alms_rules(config)
    targets = disc_targets(layout, rules, mover_id(layout))
    return (
        _CONTROLS_SCRIPT.replace("__PATH__", json.dumps(mover_path(rules)))
        .replace("__TARGETS__", json.dumps(targets))
        .replace("__SLOT_COUNT__", str(len(placeholder_slots(layout, rules))))
        .replace("__RANK_FIRST__", RANK_FIRST)
        .replace("__MOVER__", mover_id(layout))
        .replace("__MOVER_LABEL__", players_of(layout)[0]["label"])
        .replace("__POSITIONS__", json.dumps(initial_positions(layout)))
    )


def render_alms_table_html(
    layout: dict,
    config: dict,
    positions: Positions | None = None,
    interactive: bool = False,
) -> str:
    start = layout["starting_position"]
    controls = render_alms_table_controls_html(layout, config) if interactive else ""
    script = render_alms_table_controls_script(layout, config) if interactive else ""
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
{ALMS_TABLE_CONTROL_STYLES}</style>
</head>
<body>
  <h1>{escape(layout["title"])}</h1>
  <p class="subtitle">{escape(layout["subtitle"])}
  All four player discs start at step {start}. Generated from {LAYOUT_FILENAME}, with the track
  bounds, rewards, and VP values from {"/".join(ALMS_CONFIG_RELATIVE_PATH)}.</p>
  {controls}
  <div class="board-wrap">
    {render_alms_table_svg(layout, config, positions, interactive)}
  </div>
{script}
</body>
</html>
"""
