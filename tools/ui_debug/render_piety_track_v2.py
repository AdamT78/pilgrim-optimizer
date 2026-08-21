"""Structured renderer for the ornamented piety track debug view.

This is v2 of the piety track: the same strip, wearing the house ornament the mancala board and
the Alms Table already wear. Two devices survived onto the board — a hairline inset just inside
the panel edge, and a trefoil between two rules beside the title — and the v1 strip has nowhere to
put either, because its boxes butt against the panel edge. So the strip becomes a panel that
*contains* the boxes, gaining side padding, a title band, and a little more room at the bottom.
That also puts the board's name in the artwork rather than leaving it to the page heading.

The page shows the panel twice: once for 3-4 players (two rows of two discs), and once for
2 players (the same two rows, with one disc above the other). Both are the same panel; the
variants differ in where each seated player's disc sits within a position.

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

from html import escape

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
from tools.ui_debug.render_player_boards_v2 import (
    _render_resource,
    _render_resource_choice_keys,
    RESOURCE_CHOICE_TOP,
    board_geometry,
    load_player_boards_v2_layout,
    resource_block,
)
from tools.ui_debug.render_seal import WOBBLE, darken, render_seal

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

# --- the first player marker ------------------------------------------------------------------
# Turn order is decided on this track -- highest piety takes the marker, and whoever holds it says
# who starts -- so the marker belongs on this panel: the thing that decides it and the thing itself
# end up in one frame. What is drawn here is only whichever seat it is told about. Who has the most
# piety, and which way a tie walks, are turn logic and are decided nowhere near this file.
#
# It sits in the top right corner, struck across the header rule rather than tucked beside it. The
# rule runs under the wax and comes out the far side, which is what makes it read as pressed on
# rather than parked in a gap.
SEAL_CX = 516.0
SEAL_CY = 27.0
SEAL_RADIUS = 22.0
SEAL_SEED = 1.1
SEAL_TILT = -14.0

# How far the rule must still run past the wax before it stops. A short enough remainder stops
# reading as a line passing underneath and starts reading as a hair poking out of the seal with
# nothing beyond it, which looks like a bug rather than a join. `check_rule_stub` holds it.
MIN_RULE_STUB = 18.0

# The seat's own colour is the wax; the rest of the seal is that colour pulled toward black. Three
# factors rather than three palettes, so a re-tuned seat colour drags its own seal along with it.
SEAL_RIM_DARKEN = 0.45
SEAL_RING_DARKEN = 0.72
SEAL_CROWN_DARKEN = 0.50

# Which player sits in which seat. Named here because nothing in this renderer resolves it: the
# discs are drawn from `variant["seats"]`, which says where in the cluster each player's disc goes
# and nothing about seat numbers, and `data-player-seat` is stamped on later by the composing page.
# Keeping seat order explicit here and there, and asserted equal in tests, keeps one source of
# truth if table seating changes again.
#
# THIS IS BOARD ORDER, NOT TURN ORDER. Where a player sits is fixed for the whole game; who plays
# first changes every round.
SEAT_ORDER = ("player_one", "player_two", "player_three", "player_four")

# The crown, as fractions of its own box about the seal's centre. It is one closed polygon and not
# a band with points standing on it: at this size two shapes leave a seam across the middle where
# they meet, which reads as a crack in the wax.
CROWN_WIDTH_R = 0.90  # of the seal's radius
CROWN_HEIGHT_W = 0.86  # of the crown's own width
CROWN_POINTS = (
    (-0.50, 0.42),
    (-0.50, -0.34),
    (-0.22, 0.02),
    (0.0, -0.46),
    (0.22, 0.02),
    (0.50, -0.34),
    (0.50, 0.42),
)


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


def track_geometry(layout: dict, disc_rows: int, *, choice_lane: bool = False) -> dict:
    """Vertical layout of one panel: title, then the numbers, the discs and the stars beneath.

    The numbers hang `title_to_numbers` below the title's baseline, which is the drop the Alms
    Table gives its own track under `Alms Table`, and everything below is chained off them: gap,
    disc rows, gap, stars, bottom margin. So dropping a disc row still shortens the panel by
    exactly that row, and nothing else moves.

    The two gaps used to be one number. They are separate because the second one is doing a job
    the first is not: the composed game table stands this panel's top level with the Alms Table's,
    and `discs_to_stars` is what lands this row of stars on the row the `11` star sits in there,
    so a score reads across the table at one height. The row count controls both where the discs
    stand and how tall the panel is; variants can therefore change the cluster without touching any
    other vertical numbers.

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

    # Destination choices use the disc band itself.  The choice group is an overlay, so it must
    # never become another vertical row or change the panel's measured height.
    choice_lane_top = top_row_cy - radius if choice_lane else discs_bottom
    choice_lane_height = 2 * radius if choice_lane else 0
    choice_lane_bottom = choice_lane_top + choice_lane_height
    star_min_y, star_max_y = _star_extent(STAR_OUTER_RADIUS, STAR_INNER_RADIUS)
    star_cy = discs_bottom + track["discs_to_stars"] - star_min_y

    strip_width = 2 * track["outer_extra"] + track["position_count"] * track["box_width"]
    rule = track["position_rule"]

    return {
        "panel_width": 2 * panel["pad_x"] + strip_width,
        "panel_height": star_cy + star_max_y + track["bottom_margin"] + panel["pad_bottom"],
        "title_baseline_y": title_baseline_y,
        "number_baseline_y": number_baseline_y,
        "choice_lane_top": choice_lane_top,
        "choice_lane_height": choice_lane_height,
        "choice_lane_bottom": choice_lane_bottom,
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


def _coerce_piety_position(value: object, player_id: str, position_count: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{player_id} piety position must be an integer, got {value!r}")
    if not 0 <= value < position_count:
        raise ValueError(
            f"{player_id} piety position {value} is outside the drawn range 0..{position_count - 1}"
        )
    return value


def disc_positions_by_player(
    layout: dict, variant_id: str, piety_positions_by_player: dict[str, int] | None
) -> dict[str, int]:
    """Where each rendered disc stands on the track.

    With no explicit positions this is the layout sample: every seated disc stands on the starting
    position. When positions are provided, only those players are drawn, and each value must be an
    in-range integer.
    """
    seated = seated_players(layout, variant_id)
    track = layout["track"]
    if piety_positions_by_player is None:
        start = int(track["disc_position"])
        return {player["id"]: start for player in seated}

    seated_ids = {player["id"] for player in seated}
    unknown = sorted(set(piety_positions_by_player) - seated_ids)
    if unknown:
        listed = ", ".join(unknown)
        raise KeyError(f"piety positions include players this variant does not seat: {listed}")

    position_count = int(track["position_count"])
    return {
        player_id: _coerce_piety_position(position, player_id, position_count)
        for player_id, position in piety_positions_by_player.items()
    }


def render_position_label(layout: dict, geometry: dict, index: int) -> str:
    fill = layout["track"]["position_label"]["fill"]
    return (
        f'<text data-piety-position-label="{index}" x="{position_center_x(layout, index):.1f}"'
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
        f'<g data-piety-score-row="true">'
        + render_star_path(center_x, star_cy, STAR_OUTER_RADIUS, STAR_INNER_RADIUS)
        + f'<text x="{center_x:.1f}" y="{star_cy + STAR_LABEL_OFFSET:.1f}"'
        f' text-anchor="middle" {STAR_LABEL_FONT}'
        f' fill="{layout["palette"]["star_label_fill"]}">{escape(str(vp))}</text>'
        + '</g>'
    )


def render_piety_choice_pills(
    layout: dict,
    geometry: dict,
    choices: list[dict],
) -> str:
    """Hidden destination pills for an active Indulgences conversion.

    The server supplies the destination and the silver delta after applying the engine step to a
    throwaway state. Steps with the same destination are grouped: a silver figure is painted only
    when every step in that group agrees. Hire payment remains a separate prompt answer.
    """
    grouped: dict[int, list[dict]] = {}
    for choice in choices:
        grouped.setdefault(int(choice["piety_destination"]), []).append(choice)

    track = layout["track"]
    left = position_center_x(layout, 0) - track["box_width"] / 2
    width = track["position_count"] * track["box_width"]
    top = geometry["choice_lane_top"]
    height = geometry["choice_lane_height"]
    board_layout = load_player_boards_v2_layout()
    board_geometry_values = board_geometry(len(board_layout["worker_roles"]))
    board_resource = resource_block(board_geometry_values["panel_width"])
    board_palette = board_layout["palette"]
    icon_offset = board_resource["icon_cy"] - board_resource["top"]
    value_offset = board_resource["value_baseline"] - board_resource["top"]
    parts = [
        f'<g data-piety-choice-lane="true" data-piety-choice-lane-top="{top:.1f}"'
        f' data-piety-choice-lane-height="{height:.1f}">'
        f'<rect x="{left:.1f}" y="{top:.1f}" width="{width:.1f}" height="{height:.1f}"'
        ' fill="none" pointer-events="none"/>'
    ]
    for destination, destination_choices in sorted(grouped.items()):
        cx = position_center_x(layout, destination)
        silver_values = {int(choice["silver_delta"]) for choice in destination_choices}
        # The static template can contain both directions, whose destinations may overlap. It is
        # hidden until the direction is answered; the page replaces this seed with the selected
        # direction's engine-provided delta before revealing the pill.
        figure = f"{next(iter(silver_values)):+d}"
        frame_markup = _render_resource_choice_keys(
            {"cell_x": [cx]}, [{"id": "silver"}],
            surface_background=layout["palette"]["panel_fill"],
        )
        frame_markup = (
            f'<g transform="translate({cx:.1f} {top:.1f}) scale(.9) '
            f'translate({-cx:.1f} {-RESOURCE_CHOICE_TOP:.1f})">'
            f'{frame_markup}</g>'
        )
        silver_markup = _render_resource(
            {"icon_cy": top + icon_offset, "value_baseline": top + value_offset},
            cx,
            {"id": "silver", "icon": "coin", "count": figure},
            board_palette,
        ).replace('<text ', '<text data-piety-choice-silver="true" ', 1)
        resource_markup = (
            f'<g transform="translate({cx:.1f} {top:.1f}) scale(.7) translate({-cx:.1f} {-top:.1f})">'
            f'<rect data-piety-choice-hit="true" x="{cx - 11.6:.1f}" y="{top + 2.4:.1f}"'
            f' width="23.2" height="45.7"'
            f' fill="transparent" pointer-events="all"/>{frame_markup}'
            f'{silver_markup}</g>'
        )
        parts.append(
            f'<g data-piety-choice-template="true" data-piety-choice-destination="{destination}"'
            ' data-piety-choice-offered="false" data-piety-choice-selected="false"'
            ' pointer-events="all">'
            f'{resource_markup}</g>'
        )
    parts.append("</g>")
    return "".join(parts)


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


def header_rule_end_x(layout: dict, geometry: dict) -> float:
    """Where the header rule stops, short of the panel's own padding.

    Read from one place because two things need it now: the rule is drawn to it, and the first
    player seal is checked against it. A seal that cleared a number written down separately would
    be cleared of the wrong line the first time the padding changed.
    """
    panel = layout["panel"]
    return geometry["panel_width"] - panel["pad_x"] - layout["ornament"]["trefoil"]["end_dx"]


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
    x1 = header_rule_end_x(layout, geometry)
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


def first_player_by_seat(layout: dict, seat: int) -> dict:
    """Whose marker it is, taken from the same `players` the discs on the track are drawn from."""
    if not 1 <= seat <= len(SEAT_ORDER):
        raise KeyError(f"no seat {seat}: this table seats {len(SEAT_ORDER)}")
    return player_by_id(layout, SEAT_ORDER[seat - 1])


def seats_that_can_hold_the_marker(layout: dict, variant_id: str) -> list[int]:
    """Seat numbers a variant puts a disc on, in seat order.

    Read off the discs the variant actually seats rather than assumed to run 1..n. A marker can
    only be held by someone at the table, so this is what a page can offer the marker to.
    """
    seated = {player["id"] for player in seated_players(layout, variant_id)}
    return [seat for seat, player_id in enumerate(SEAT_ORDER, start=1) if player_id in seated]


def render_crown(cx: float, cy: float, r: float, colour: str) -> str:
    """The die the first player seal is struck with, as one closed outline.

    Drawn square and handed to `render_seal` as its `inner`, which turns it with the wax and the
    ring. The ring and this come off one die, so they turn together or the strike is depicted as
    half a die turning.
    """
    width = r * CROWN_WIDTH_R
    height = width * CROWN_HEIGHT_W
    points = " ".join(f"{cx + fx * width:.2f},{cy + fy * height:.2f}" for fx, fy in CROWN_POINTS)
    return f'<polygon points="{points}" fill="{colour}"/>'


def check_rule_stub(layout: dict, geometry: dict) -> float:
    """What is left of the header rule to the right of the wax, and whether it is enough to read.

    The seal is struck ON the rule, so the rule goes under it and comes out the other side. That
    only reads as a line passing underneath while there is a decent run of it beyond the wax. Move
    the seal far enough right and what is left stops being a line and becomes a hair sticking out
    of the blob with nothing on the end of it, which looks like a rendering fault.

    Measured at the trough of the wobble rather than at the nominal radius, because the wax is not
    a circle: at `r` a seal can be declared clear and still show a hair where the ripple runs wide.
    The factor comes off `WOBBLE` so that re-tuning the ripple re-tunes this with it.
    """
    trough = SEAL_RADIUS * (1 - WOBBLE[0] - WOBBLE[1])
    rule_end = header_rule_end_x(layout, geometry)
    stub = rule_end - (SEAL_CX + trough)
    assert stub >= MIN_RULE_STUB, (
        f"only {stub:.1f} of header rule is left right of the seal, and {MIN_RULE_STUB:g} is the "
        f"least that still reads as a rule running underneath rather than a hair poking out of "
        f"the wax: move the seal left of x={rule_end - MIN_RULE_STUB - trough:.1f} or stop the "
        f"rule further right than x={rule_end:.1f}"
    )
    return stub


def _strike_first_player_seal(layout: dict, geometry: dict, seat: int, hooks: str) -> str:
    """One seat's seal at the approved position, with whatever hooks the caller needs on the group.

    Every seal is struck the same: same centre, same radius, same seed, same tilt, same crown. Only
    the colour differs, and it comes off the seat rather than out of a palette of its own.
    """
    check_rule_stub(layout, geometry)
    player = first_player_by_seat(layout, seat)
    wax = player["fill"]
    return (
        f'<g data-first-player-seal="true" data-player="{player["id"]}"'
        f' data-player-color="{player["color"]}"{hooks}>'
        + render_seal(
            SEAL_CX,
            SEAL_CY,
            SEAL_RADIUS,
            wax,
            darken(wax, SEAL_RIM_DARKEN),
            darken(wax, SEAL_RING_DARKEN),
            seed=SEAL_SEED,
            tilt=SEAL_TILT,
            inner=render_crown(SEAL_CX, SEAL_CY, SEAL_RADIUS, darken(wax, SEAL_CROWN_DARKEN)),
        )
        + "</g>"
    )


def render_first_player_seal(layout: dict, geometry: dict, seat: int) -> str:
    """The first player marker: a seal in the holder's own colour, pressed over the header rule.

    Only the seat it is given. Which seat that is -- highest piety, and clockwise from there on a
    tie -- is turn logic, and this draws whichever answer it is handed without checking it.
    """
    return _strike_first_player_seal(layout, geometry, seat, "")


def render_first_player_seals(
    layout: dict, geometry: dict, variant_id: str, held_by: int | None
) -> str:
    """Every seat's seal, struck in its own colour, all hidden but the one the marker sits on.

    For a page that has to move the marker after the SVG is written. The alternative is to emit the
    holder's seal alone and restrike it in JavaScript when it moves, which means writing `darken()`
    a second time in a second language and then keeping the two agreeing. Striking all four here
    leaves the page nothing to do but show one and hide the rest -- no colour crosses the line.

    Hidden with `visibility`, which is what the composed table already toggles its discs and its
    seat boards with, so a hidden seal still occupies its place and nothing reflows when it appears.
    """
    return "".join(
        _strike_first_player_seal(
            layout,
            geometry,
            seat,
            f' data-player-seat="{seat}"' + ("" if seat == held_by else ' visibility="hidden"'),
        )
        for seat in seats_that_can_hold_the_marker(layout, variant_id)
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


def render_piety_track_v2_svg(
    layout: dict,
    config: dict,
    variant_id: str,
    first_player_seat: int | None = None,
    interactive: bool = False,
    piety_positions_by_player: dict[str, int] | None = None,
    piety_choice_steps: list[dict] | None = None,
) -> str:
    """One ornamented panel: the grey rounded rect, the ornament, then the track inside it.

    `first_player_seat` strikes that seat's wax seal into the top right corner and says so on the
    root element. Left out, no seal is drawn and the panel is what it has always been -- nothing
    else on it reads the seat, and nothing else about it changes when one is given.

    `interactive` strikes every seat's seal instead of only the holder's, hidden but for the one
    named, so a page can move the marker without building any SVG of its own. Left off, the panel
    is the fixed picture every standalone page here draws. That is the same bargain the Alms Table
    makes for its own discs and winner cubes.

    `piety_positions_by_player` is the state seam for disc placement: player id -> piety position.
    Left out, the layout sample is drawn (everyone on the starting position). Given, each value
    must be an integer in the drawn range the layout defines; outside it, rendering raises loudly
    rather than pretending a value still on the board.

    No seat with `interactive` on is a legitimate state for a page mid-build: every seal is struck
    and every one is hidden. It is not a game state -- the marker always sits with someone -- but
    it is the rendering default, and it is what keeps the pages that ask for no marker unchanged.
    """
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
    geometry = track_geometry(
        layout, variant["disc_rows"], choice_lane=bool(piety_choice_steps)
    )
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
    positions = disc_positions_by_player(layout, variant_id, piety_positions_by_player)
    for index, vp in enumerate(vp_values):
        parts.append(render_position_label(layout, geometry, index))
        parts += [
            render_player_disc(layout, index, player)
            for player in seated
            if positions.get(player["id"]) == index
        ]
        parts.append(render_vp_star(layout, geometry, index, vp))

    if piety_choice_steps:
        parts.append(render_piety_choice_pills(layout, geometry, piety_choice_steps))

    # Struck last, because wax goes on top of what it is pressed onto.
    seal = "" if first_player_seat is None else f' data-first-player-seat="{first_player_seat}"'
    if interactive:
        parts.append(render_first_player_seals(layout, geometry, variant_id, first_player_seat))
    elif first_player_seat is not None:
        parts.append(render_first_player_seal(layout, geometry, first_player_seat))

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
        f' data-component="{COMPONENT_NAME}" data-piety-variant="{variant["id"]}"{seal}>'
        f'\n  <rect x="{min_x}" y="{min_y}" width="{width:.1f}" height="{height:.1f}"'
        f' fill="{layout["page_background"]}"/>'
        f"\n  {''.join(parts)}\n</svg>"
    )


def render_first_player_seal_rows(layout: dict, config: dict) -> str:
    """The marker at real scale on the real renderer: the absence case, then one panel per seat.

    Nothing in the game sets `data-first-player-seat` yet, so without these the seal renders nowhere
    and cannot be looked at. These are renders of the same panel the page already shows, asked for
    with a seat -- no separate artwork, so what is reviewed here is what would ship.
    """
    panels = [(variant["id"], None) for variant in layout["variants"][:1]]
    panels += [
        (variant["id"], seat)
        for variant in layout["variants"]
        for seat in seats_that_can_hold_the_marker(layout, variant["id"])
    ]

    rows = []
    for variant_id, seat in panels:
        label = variant_by_id(layout, variant_id)["label"]
        if seat is None:
            caption = f"{label} — no seat set, no seal struck"
        else:
            caption = f"{label} — seat {seat}, {first_player_by_seat(layout, seat)['color']}"
        rows.append(
            '    <figure class="seal-row">\n'
            f"      {render_piety_track_v2_svg(layout, config, variant_id, seat)}\n"
            f"      <figcaption>{escape(caption)}</figcaption>\n"
            "    </figure>"
        )
    return "\n".join(rows)


def render_piety_tracks_v2_html(layout: dict, config: dict) -> str:
    """The debug page: every variant the layout describes, stacked as the prototype stacks them."""
    rows = "\n".join(
        '    <figure class="track-row">\n'
        f"      {render_piety_track_v2_svg(layout, config, variant['id'])}\n"
        f"      <figcaption>{escape(variant['label'])}</figcaption>\n"
        "    </figure>"
        for variant in layout["variants"]
    )
    seal_rows = render_first_player_seal_rows(layout, config)
    seal_note = (
        "The same panels, asked for with data-first-player-seat. The seal is struck in the "
        "holder's own seat colour and pressed over the header rule; with no seat set nothing is "
        "drawn and nothing is left behind."
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
  h2 {{
    font-family: Georgia, serif;
    font-size: 18px;
    color: #F2EEDF;
    margin: 34px 0 2px;
  }}
  .track-row, .seal-row {{ margin: 0 0 18px; }}
  .track-row:last-child, .seal-row:last-child {{ margin-bottom: 0; }}
  figcaption {{
    color: #A8A296;
    font-size: 12px;
    margin-top: 7px;
    text-align: center;
  }}
</style>
</head>
<body>
  <h1>{escape(layout["page_title"])}</h1>
  <p class="subtitle">{escape(subtitle)}</p>
  <div class="board-wrap">
{rows}
  </div>
  <h2>First player marker</h2>
  <p class="subtitle">{escape(seal_note)}</p>
  <div class="board-wrap">
{seal_rows}
  </div>
</body>
</html>
"""
