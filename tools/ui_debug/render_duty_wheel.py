"""Structured renderer for the duty wheel debug view.

The duty wheel holds the duty tiles away from the map so the map stays readable: eight duty
spaces ringed around a central City on a green hexagon, joined by clockwise ring arrows and four
arrows running to and from the middle. Each duty shows the cubes standing on it as one column per
seat on a shared baseline, and most of them carry a capsule with a Tithe token icon.

Two pieces of the picture are named here so a later renderer does not have to guess:

- the purple disc is the **Merchant token**, drawn on whichever duty `merchant_token.starts_on`
  names (Taxation, for the debug page);
- the resource icons in the capsules are **Tithe tokens**.

Drawn plain, this is one fixed picture. Drawn `interactive`, the board also carries every slot the
page's debug buttons can turn on — a Merchant token on each duty, every Tithe token icon on each
duty that has a capsule, and a cube tally per player count — hidden until they are wanted, so a
click flips opacity instead of redrawing the board. Those buttons cycle sample setups, walk the
Merchant around the ring, and switch between the two-, three-, and four-player views; they touch
nothing else. There is no sowing, no sow animation, no Tithe token logic, and no rule saying what
any of this means. It is a debug/visual tool that reads `duty_wheel_layout.json` and emits
SVG/HTML, connected to nothing.

Geometry mirrors `prototypes/duty_wheel.svg`, which stays the visual baseline. Every space is
placed from one anchor, the centre of its arc, and everything else on that space — the flat-top
capsule outline, the title, the cube tally, the Tithe capsule, the ornaments — is a fixed offset
from it. The layout JSON says what a space carries and where its anchor sits; this module says
how the pieces around that anchor are drawn. The three traced artwork paths (the two arrow
silhouettes and the cornucopia horn) live in the JSON too, since they are shapes nobody derives.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from xml.sax.saxutils import escape

LAYOUT_FILENAME = "duty_wheel_layout.json"

# One space: a flat top with a round bottom, the arc centre acting as its anchor.
SPACE_RADIUS = 101.5
SPACE_STROKE_WIDTH = 2.438679
LABEL_OFFSET_Y = -50.7
LABEL_FONT_SIZE = 15.5

# Cube tally: one column per seat on a shared baseline, kept even at zero so the stack tops stay
# comparable across spaces. The columns are centred on the duty, so a shorter table narrows the
# tally around the middle of the space instead of leaving a gap on the right.
CUBE_SIZE = 13.0
CUBE_CELL_HEIGHT = 18.0
CUBE_COLUMN_WIDTH = 22.0
CUBE_STACK_LIMIT = 3
TALLY_OFFSET_Y = 19.0

# Tithe capsule: a stadium under the title, its left cap holding the Tithe token icon and its
# right cap the Merchant token when the Merchant stands here.
CAPSULE_OFFSET_Y = 34.0
CAPSULE_CAP_RADIUS = 24.0
CAPSULE_WAIST = 44.0

# Ornament: the inset margin and the trefoil above each title. It is identical on all nine
# spaces on purpose — a mark that never varies cannot be read as per-space meaning.
ORNAMENT_INSET = 7.5
ORNAMENT_HEADER_OFFSET_Y = -78.0
ORNAMENT_TREFOIL_RADIUS = 4.6
ORNAMENT_RULE_GAP = 15.0

RING_ARROW_COUNT = 8

# How far the movable duty tiles are turned around the ring in each sample setup. The first is
# the board as the layout describes it; the others are just far enough apart to look different.
DUTY_SETUP_ROTATIONS = (0, 1, 3)

_WHEAT_STALKS = (
    (-8.2, -10.8, -6.8, -9.4, -22),
    (-4.6, -13.0, -3.8, -11.3, -10),
    (0.9, -13.8, 0.6, -12.1, 2),
    (5.9, -12.3, 4.7, -10.8, 14),
    (9.6, -9.1, 8.0, -7.6, 24),
)
_STONE_FACES = (
    ("M 0,-17.3 L 8.8,-12.3 L 0,-7.3 L -8.8,-12.3 Z", "0.9"),
    ("M 8.8,-12.3 L 8.8,-2.3 L 0,2.7 L 0,-7.3 Z", "0.55"),
    ("M -8.8,-12.3 L 0,-7.3 L 0,2.7 L -8.8,-2.3 Z", "0.75"),
)
_CORNUCOPIA_FRUIT = ((9.48, -7.31, 2.94), (4.98, -11.18, 2.10), (10.95, -1.69, 2.03))


def _num(value: float) -> str:
    """A layout value written out as given, so nothing is lost to formatting."""
    return str(int(value)) if float(value).is_integer() else repr(float(value))


def _class_name(duty_id: str, suffix: str) -> str:
    return f"{duty_id.replace('_', '-')}-{suffix}"


def default_layout_path() -> Path:
    return Path(__file__).resolve().parent / LAYOUT_FILENAME


def load_duty_wheel_layout(path: Path | None = None) -> dict:
    layout_path = default_layout_path() if path is None else Path(path)
    return json.loads(layout_path.read_text(encoding="utf-8"))


def duties_of(layout: dict) -> list[dict]:
    return list(layout["duties"])


def duty_position_by_id(layout: dict, duty_id: str) -> dict:
    for duty in duties_of(layout):
        if duty["id"] == duty_id:
            return duty
    raise KeyError(f"unknown duty: {duty_id!r}")


def ring_duties(layout: dict) -> list[dict]:
    """The eight duties around the City, clockwise from the top."""
    return [duty_position_by_id(layout, duty_id) for duty_id in layout["clockwise_order"]]


def default_duty_wheel_state(layout: dict) -> dict:
    """The cubes the baseline shows standing on each duty.

    This is sample debug state, not `GameState`: it is what a debug page has to draw before
    anything real is wired up.
    """
    player_ids = [player["id"] for player in layout["players"]]
    return {
        duty["id"]: {
            player_id: int(duty.get("sample_cubes", {}).get(player_id, 0))
            for player_id in player_ids
        }
        for duty in duties_of(layout)
    }


def players_for_count(layout: dict, count: int) -> list[dict]:
    """The seats in play at a two-, three-, or four-player count, in seat order."""
    players = layout["players"]
    if count not in layout["player_counts"]:
        raise ValueError(f"no {count}-player view: the layout offers {layout['player_counts']}")
    return players[:count]


def tally_columns(layout: dict, duty: dict, count: int) -> list[dict]:
    """Where each seat's cube column stands on one duty, left to right.

    The group of visible columns is centred on the duty, so dropping seats narrows the tally
    around the middle of the space rather than leaving it hanging off to one side. `x` is the
    left edge of a cube, `center_x` the middle of the column it stands in.
    """
    cx, _ = duty["center"]
    players = players_for_count(layout, count)
    left = cx - len(players) * CUBE_COLUMN_WIDTH / 2
    return [
        {
            "player": player["id"],
            "x": left + column * CUBE_COLUMN_WIDTH + (CUBE_COLUMN_WIDTH - CUBE_SIZE) / 2,
            "center_x": left + (column + 0.5) * CUBE_COLUMN_WIDTH,
        }
        for column, player in enumerate(players)
    ]


def merchant_path(layout: dict) -> list[str]:
    """The positions the Merchant can stand on: all eight duty tiles, clockwise.

    The City is not one of them — it is not a duty tile, and no ring arrow runs through it.
    """
    return list(layout["clockwise_order"])


def next_merchant_position(layout: dict, current: str) -> str:
    """The next duty tile clockwise, wrapping round the ring."""
    path = merchant_path(layout)
    return path[(path.index(current) + 1) % len(path)]


def duty_setups(layout: dict) -> list[list[dict]]:
    """Sample arrangements of the duty tiles, one entry per ring position, clockwise.

    Debug fodder, not a setup rule: the first is the board as the layout describes it, and the
    rest turn the movable tiles around the ring by a fixed number of places. A tile keeps its own
    Tithe token wherever it lands, which is why Taxation holds its position in all of them: it is
    the one duty with no Tithe token, so it is also the one position drawn without a capsule to
    put a token in. The City is not a duty tile at all and never takes part.
    """
    order = layout["clockwise_order"]
    movable = [duty["id"] for duty in ring_duties(layout) if duty["tithe_icon"]]

    setups = []
    for rotation in DUTY_SETUP_ROTATIONS:
        turned = movable[rotation:] + movable[:rotation]
        landed = dict(zip(movable, turned, strict=True))
        setups.append(
            [
                {
                    "position": position,
                    "duty": landed.get(position, position),
                    "label": duty_position_by_id(layout, landed.get(position, position))["label"],
                    "tithe_icon": duty_position_by_id(layout, landed.get(position, position))[
                        "tithe_icon"
                    ],
                }
                for position in order
            ]
        )
    return setups


def merchant_slot_center(duty: dict) -> tuple[float, float]:
    """Where the Merchant stands on a duty: the capsule's right cap, or the empty band on
    Taxation, which has no capsule to share."""
    cx, cy = duty["center"]
    _, merchant_x, cap_y = _capsule_caps(cx, cy)
    return (merchant_x if duty.get("tithe_icon") else cx), cap_y


def space_path_data(cx: float, cy: float, radius: float = SPACE_RADIUS) -> str:
    """A flat top on the arc centre's level, closed by a half circle below it."""
    top = cy - radius
    return (
        f"M {cx - radius:.1f},{top:.1f} H {cx + radius:.1f} V {cy:.1f}"
        f" A {radius:.1f},{radius:.1f} 0 0 1 {cx - radius:.1f},{cy:.1f} V {top:.1f} Z"
    )


def _render_space(duty: dict) -> str:
    cx, cy = duty["center"]
    return (
        f'<path d="{space_path_data(cx, cy)}" class="board-circle"/>'
        f'<text x="{cx:.1f}" y="{cy + LABEL_OFFSET_Y:.1f}" class="circle-label"'
        f' data-duty-label="{duty["id"]}">{escape(duty["label"])}</text>'
    )


def render_cube_tally(
    layout: dict,
    duty: dict,
    counts: dict,
    count: int | None = None,
    visible: bool = True,
) -> str:
    """The cubes standing on one duty, one column per seat, growing up from the baseline.

    `count` picks how many seats are in play; the columns and the baseline under them are drawn
    centred on the duty either way, so the two- and three-player tallies sit in the middle of the
    space rather than off to the left.
    """
    _, cy = duty["center"]
    seats = count or layout["default_player_count"]
    players = players_for_count(layout, seats)
    columns = tally_columns(layout, duty, seats)
    baseline = cy + TALLY_OFFSET_Y
    left = columns[0]["center_x"] - CUBE_COLUMN_WIDTH / 2
    right = columns[-1]["center_x"] + CUBE_COLUMN_WIDTH / 2
    ink = layout["palette"]["ink"]

    parts = [
        f'<line x1="{left:.1f}" y1="{baseline:.1f}" x2="{right:.1f}" y2="{baseline:.1f}"'
        f' stroke="{ink}" stroke-opacity="0.55" stroke-width="1.6" stroke-linecap="round"/>'
    ]
    for player, column in zip(players, columns, strict=True):
        for index in range(min(int(counts.get(player["id"], 0)), CUBE_STACK_LIMIT)):
            y = baseline - (index + 1) * CUBE_CELL_HEIGHT + (CUBE_CELL_HEIGHT - CUBE_SIZE) / 2
            parts.append(
                f'<rect x="{column["x"]:.1f}" y="{y:.1f}" width="{CUBE_SIZE:g}"'
                f' height="{CUBE_SIZE:g}" fill="{player["fill"]}" stroke="#000000"'
                f' stroke-width="{player["cube_stroke_width"]:g}"'
                f' data-player="{player["id"]}"/>'
            )
    return (
        f'<g class="{_class_name(duty["id"], "cube-tally")}" data-cube-tally="{duty["id"]}"'
        f' data-player-count="{seats}" opacity="{1 if visible else 0}"'
        f' aria-label="cube counts">{"".join(parts)}</g>'
    )


def _capsule_path_data(cx: float, cy: float) -> str:
    left = cx - CAPSULE_WAIST / 2
    right = cx + CAPSULE_WAIST / 2
    top = cy + CAPSULE_OFFSET_Y
    bottom = top + 2 * CAPSULE_CAP_RADIUS
    radius = f"{CAPSULE_CAP_RADIUS:g},{CAPSULE_CAP_RADIUS:g}"
    return (
        f"M {left:.1f},{top:.1f} H {right:.1f} A {radius} 0 0 1 {right:.1f},{bottom:.1f}"
        f" H {left:.1f} A {radius} 0 0 1 {left:.1f},{top:.1f} Z"
    )


def _capsule_caps(cx: float, cy: float) -> tuple[float, float, float]:
    """Where the two cap centres sit: the Tithe icon's, the Merchant's, and their shared level."""
    cap_y = cy + CAPSULE_OFFSET_Y + CAPSULE_CAP_RADIUS
    return cx - CAPSULE_WAIST / 2, cx + CAPSULE_WAIST / 2, cap_y


def _icon_coin(ink: str) -> str:
    return (
        f'<circle cx="0" cy="0" r="9.6" fill="none" stroke="{ink}" stroke-width="1.45"/>'
        f'<circle cx="0" cy="0" r="6.55" fill="none" stroke="{ink}" stroke-width="0.98"/>'
        f'<line x1="2.0" y1="-4.8" x2="6.2" y2="-4.8" stroke="{ink}" stroke-width="1.08"'
        ' stroke-linecap="round"/>'
        f'<line x1="4.1" y1="-6.9" x2="4.1" y2="-2.7" stroke="{ink}" stroke-width="1.08"'
        ' stroke-linecap="round"/>'
    )


def _icon_stone(ink: str) -> str:
    return "".join(
        f'<path d="{face}" fill="{ink}" fill-opacity="{opacity}" stroke="{ink}"'
        ' stroke-width="1.0" stroke-linejoin="round"/>'
        for face, opacity in _STONE_FACES
    )


def _icon_wheat(ink: str) -> str:
    parts = []
    for tip_x, tip_y, seed_x, seed_y, angle in _WHEAT_STALKS:
        parts.append(
            f'<line x1="0" y1="7.0" x2="{tip_x:.1f}" y2="{tip_y:.1f}" stroke="{ink}"'
            ' stroke-width="1.35" stroke-linecap="round"/>'
        )
        parts.append(
            f'<ellipse cx="{seed_x:.1f}" cy="{seed_y:.1f}" rx="1.95" ry="3.25" fill="{ink}"'
            f' transform="rotate({angle:g} {seed_x:.1f} {seed_y:.1f})"/>'
        )
    parts.append(f'<line x1="-5.2" y1="8.0" x2="5.2" y2="8.0" stroke="{ink}" stroke-width="1.46"/>')
    return "".join(parts)


def _icon_cornucopia(ink: str, horn_path: str) -> str:
    fruit = "".join(
        f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="none" stroke="{ink}"'
        ' stroke-width="1.4"/>'
        for cx, cy, r in _CORNUCOPIA_FRUIT
    )
    return (
        f'<path d="{horn_path}" fill="none" stroke="{ink}" stroke-width="1.7"'
        ' stroke-linecap="round" stroke-linejoin="round"/>'
        '<ellipse cx="2.21" cy="-3.11" rx="7.0" ry="3.15"'
        f' transform="rotate(-120.0 2.21 -3.11)" fill="none" stroke="{ink}" stroke-width="1.6"/>'
        + fruit
    )


_ICON_BODIES = {"coin": _icon_coin, "stone": _icon_stone, "wheat": _icon_wheat}


def render_tithe_icon(
    layout: dict,
    icon_id: str,
    cx: float,
    cy: float,
    position: str = "",
    visible: bool = True,
) -> str:
    """One Tithe token icon, drawn at its own scale in the left cap of a duty's capsule.

    An icon tagged with the ring `position` it belongs to is one the controls can turn on; it is
    drawn hidden unless it is the one that position currently shows.
    """
    spec = layout["tithe_icons"][icon_id]
    ink = layout["palette"]["ink"]
    if icon_id == "cornucopia":
        body = _icon_cornucopia(ink, layout["artwork"]["cornucopia_horn_path"])
    elif icon_id in _ICON_BODIES:
        body = _ICON_BODIES[icon_id](ink)
    else:
        raise KeyError(f"unknown tithe icon: {icon_id!r}")
    tags = f' data-duty-position="{position}" opacity="{1 if visible else 0:g}"' if position else ""
    return (
        f'<g class="{icon_id}-icon" data-tithe-token="{icon_id}"{tags}'
        f' transform="translate({cx:.1f} {cy + spec["offset_y"]:.1f}) scale({spec["scale"]:g})"'
        f' aria-label="{escape(spec["label"])}">{body}</g>'
    )


def render_merchant_token(
    layout: dict, cx: float, cy: float, position: str = "", visible: bool = True
) -> str:
    """The purple disc.

    Tagged with the ring `position` it stands on, it becomes one of the slots the Move Merchant
    button turns on and off; the disc itself carries no rules and moves nothing but itself.
    """
    merchant = layout["merchant_token"]
    tags = f' data-duty-position="{position}" opacity="{1 if visible else 0:g}"' if position else ""
    return (
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{CAPSULE_CAP_RADIUS:g}"'
        f' fill="{merchant["color"]}" stroke="{merchant["edge"]}" stroke-width="2"'
        f' data-token="merchant"{tags} aria-label="{escape(merchant["label"])}"/>'
    )


def _capsule_fill(layout: dict, duty: dict) -> str:
    palette = layout["palette"]
    return (
        f'<path d="{_capsule_path_data(*duty["center"])}" fill="{palette["capsule_fill"]}"'
        f' stroke="{palette["capsule_edge"]}" stroke-width="2" stroke-linecap="round"'
        ' stroke-linejoin="round"/>'
    )


def _capsule_outline(layout: dict, duty: dict) -> str:
    """The capsule border on its own, redrawn over the discs so they stay inside one outline."""
    palette = layout["palette"]
    return (
        f'<path d="{_capsule_path_data(*duty["center"])}" fill="none"'
        f' stroke="{palette["capsule_edge"]}" stroke-width="2" stroke-linecap="round"'
        ' stroke-linejoin="round"/>'
    )


def _render_tithe_capsule(layout: dict, duty: dict, icon_id: str, merchant: bool) -> str:
    """The capsule under a duty's title: its Tithe token, and the Merchant when he stands here.

    With the Merchant present the two discs are drawn clipped to the capsule, so the pair reads
    as one joined shape with a single outline rather than two circles that happen to touch.
    """
    palette = layout["palette"]
    tithe_x, merchant_x, cap_y = _capsule_caps(*duty["center"])

    if merchant:
        shape = (
            f'<g clip-path="url(#{duty["id"]}-capsule-clip)">'
            f'<circle cx="{tithe_x:.1f}" cy="{cap_y:.1f}" r="{CAPSULE_CAP_RADIUS:g}"'
            f' fill="{palette["capsule_fill"]}"/>'
            f"{render_merchant_token(layout, merchant_x, cap_y)}</g>"
            f"{_capsule_outline(layout, duty)}"
        )
    else:
        shape = _capsule_fill(layout, duty)
    icon = render_tithe_icon(layout, icon_id, tithe_x, cap_y)
    return f'<g class="{_class_name(duty["id"], "tithe-shape")}">{shape}{icon}</g>'


def _render_interactive_capsule(layout: dict, duty: dict, merchant: bool) -> str:
    """The capsule with every slot the controls can turn on: the Merchant, and each Tithe token.

    The Merchant is drawn between the capsule's fill and its border, clipped to the capsule, so
    turning him on joins the two discs into one shape exactly as the static board draws it.
    """
    tithe_x, merchant_x, cap_y = _capsule_caps(*duty["center"])
    icons = "".join(
        render_tithe_icon(
            layout, icon_id, tithe_x, cap_y, duty["id"], icon_id == duty["tithe_icon"]
        )
        for icon_id in layout["tithe_icons"]
    )
    return (
        f'<g class="{_class_name(duty["id"], "tithe-shape")}">'
        f"{_capsule_fill(layout, duty)}"
        f'<g clip-path="url(#{duty["id"]}-capsule-clip)">'
        f"{render_merchant_token(layout, merchant_x, cap_y, duty['id'], merchant)}</g>"
        f"{_capsule_outline(layout, duty)}{icons}</g>"
    )


def _render_tallies(layout: dict, duty: dict, counts: dict, interactive: bool) -> str:
    """The cube tally, or — interactive — one tally per player count with the default showing.

    Each count gets its own group because the columns move when seats drop out: the visible ones
    stay centred on the duty. Switching views is then a matter of flipping which group is drawn.
    """
    if not interactive:
        return render_cube_tally(layout, duty, counts)
    default = layout["default_player_count"]
    return "".join(
        render_cube_tally(layout, duty, counts, count, visible=count == default)
        for count in layout["player_counts"]
    )


def render_duty_space(
    layout: dict,
    duty: dict,
    counts: dict,
    merchant: bool = False,
    interactive: bool = False,
    ring_index: int | None = None,
) -> str:
    """One duty: its space, title, cube tally, and the capsule holding its Tithe token."""
    parts = [_render_space(duty)]
    if duty["id"] != layout["city_id"]:
        parts.append(_render_tallies(layout, duty, counts, interactive))

    icon_id = duty["tithe_icon"]
    if icon_id and interactive:
        parts.append(_render_interactive_capsule(layout, duty, merchant))
    elif icon_id:
        parts.append(_render_tithe_capsule(layout, duty, icon_id, merchant))
    elif interactive or merchant:
        # Taxation has no capsule for the Merchant to share, so he stands in the empty band.
        slot_x, slot_y = merchant_slot_center(duty)
        position = duty["id"] if interactive else ""
        parts.append(render_merchant_token(layout, slot_x, slot_y, position, merchant))

    index = "" if ring_index is None else f' data-duty-ring-index="{ring_index}"'
    return f'<g data-duty="{duty["id"]}"{index}>{"".join(parts)}</g>'


def _render_ornaments(layout: dict) -> str:
    """The inset margin and the trefoil rule above each title, identical on all nine spaces."""
    ink = layout["palette"]["ink"]
    insets, headers = [], []
    for duty in duties_of(layout):
        cx, cy = duty["center"]
        radius = SPACE_RADIUS - ORNAMENT_INSET
        insets.append(
            f'<path d="{space_path_data(cx, cy, radius)}" fill="none" stroke="{ink}"'
            ' stroke-opacity="0.28" stroke-width="1.2"/>'
        )
        y = cy + ORNAMENT_HEADER_OFFSET_Y
        lobes = "".join(
            f'<circle cx="{cx + ORNAMENT_TREFOIL_RADIUS * math.cos(math.radians(angle)):.1f}"'
            f' cy="{y + ORNAMENT_TREFOIL_RADIUS * math.sin(math.radians(angle)):.1f}"'
            f' r="{ORNAMENT_TREFOIL_RADIUS:g}"/>'
            for angle in (-90, 30, 150)
        )
        half = len(layout["players"]) * CUBE_COLUMN_WIDTH / 2
        headers.append(
            f'<g fill="none" stroke="{ink}" stroke-opacity="0.34" stroke-width="1.3"'
            f' stroke-linecap="round">{lobes}'
            f'<path d="M {cx - half:.1f},{y:.1f} H {cx - ORNAMENT_RULE_GAP:.1f}'
            f' M {cx + ORNAMENT_RULE_GAP:.1f},{y:.1f} H {cx + half:.1f}"/></g>'
        )
    return (
        f'<g class="ornament-inset" aria-hidden="true">{"".join(insets)}</g>'
        f'<g class="ornament-header" aria-hidden="true">{"".join(headers)}</g>'
    )


def _render_ring_arrows(layout: dict) -> str:
    cx, cy = layout["board"]["center"]
    path = layout["artwork"]["ring_arrow_path"]
    step = 360 // RING_ARROW_COUNT
    return (
        '<g aria-label="Clockwise outer arrows">'
        + "".join(
            f'<g transform="rotate({index * step:g} {_num(cx)} {_num(cy)})"'
            f' data-ring-arrow="{index}">'
            f'<path d="{path}" class="arrow-border"/><path d="{path}" class="arrow-interior"/></g>'
            for index in range(RING_ARROW_COUNT)
        )
        + "</g>"
    )


def _render_middle_arrows(layout: dict) -> str:
    path = layout["artwork"]["middle_arrow_path"]
    arrows = []
    for arrow in layout["middle_arrows"]:
        x, y = arrow["at"]
        transform = f"translate({_num(x)} {_num(y)})"
        if arrow["rotate"]:
            transform += f" rotate({arrow['rotate']:g})"
        arrows.append(
            f'<g transform="{transform}" data-middle-arrow="{arrow["id"]}"'
            f' data-toward="{arrow["toward"]}">'
            f'<path d="{path}" class="arrow-border"/><path d="{path}" class="arrow-interior"/></g>'
        )
    return '<g aria-label="Middle directional arrows">' + "".join(arrows) + "</g>"


_STYLE_TEMPLATE = (
    ".board-circle {{ fill: url(#parchment-gradient); stroke: {space_edge};"
    " stroke-width: {space_stroke_width}; }}"
    '.circle-label {{ fill: {ink}; font-family: Georgia, "Times New Roman", serif;'
    " font-size: {label_font_size:g}px; font-weight: 700; text-anchor: middle;"
    " dominant-baseline: middle; }}"
    ".arrow-border {{ fill: none; stroke: {arrow_border}; stroke-width: 6;"
    " stroke-linecap: round; stroke-linejoin: round; }}"
    ".arrow-interior {{ fill: {arrow_interior}; stroke: none; }}"
)


def _render_defs(layout: dict, merchant_duty_id: str, interactive: bool = False) -> str:
    """The gradients, the capsule clips, and the board's own stylesheet.

    A static board only needs the clip belonging to the duty the Merchant stands on; an
    interactive one needs every capsule's, since he can be turned on at any of them.
    """
    palette = layout["palette"]
    parchment_from, parchment_to = palette["parchment"]
    ground_from, ground_to = palette["ground"]
    if interactive:
        clipped = [duty for duty in ring_duties(layout) if duty["tithe_icon"]]
    else:
        clipped = [duty_position_by_id(layout, merchant_duty_id)] if merchant_duty_id else []
    clip = "".join(
        f'<clipPath id="{duty["id"]}-capsule-clip">'
        f'<path d="{_capsule_path_data(*duty["center"])}"/></clipPath>'
        for duty in clipped
        if duty["tithe_icon"]
    )
    style = _STYLE_TEMPLATE.format(
        space_edge=palette["space_edge"],
        space_stroke_width=_num(SPACE_STROKE_WIDTH),
        ink=palette["ink"],
        label_font_size=LABEL_FONT_SIZE,
        arrow_border=palette["arrow_border"],
        arrow_interior=palette["arrow_interior"],
    )
    return (
        "<defs>"
        '<radialGradient id="parchment-gradient" cx="42%" cy="35%" r="72%">'
        f'<stop offset="0%" stop-color="{parchment_from}"/>'
        f'<stop offset="100%" stop-color="{parchment_to}"/></radialGradient>'
        '<radialGradient id="hex-gradient" cx="50%" cy="44%" r="70%">'
        f'<stop offset="0%" stop-color="{ground_from}"/>'
        f'<stop offset="100%" stop-color="{ground_to}"/></radialGradient>'
        f"{clip}<style>{style}</style></defs>"
    )


def render_duty_wheel_svg(
    layout: dict,
    board_state: dict | None = None,
    merchant_on: str | None = None,
    interactive: bool = False,
) -> str:
    """The whole board: title, ground, arrows, and the nine spaces with their contents.

    `merchant_on` overrides where the Merchant stands, which the baseline parity check uses to
    ask for the board the prototype drew. `interactive` adds the hidden slots the page's debug
    controls switch between; left off, the board is the fixed picture the prototype shows.
    """
    board = layout["board"]
    palette = layout["palette"]
    page = layout["page"]
    state = default_duty_wheel_state(layout) if board_state is None else board_state
    merchant_duty_id = merchant_on or layout["merchant_token"]["starts_on"]
    cx, cy = board["center"]
    frame = board["frame"]

    subtitle = "".join(
        f'<tspan x="{board["width"] / 2:g}" dy="{0 if index == 0 else 17:g}">{escape(line)}</tspan>'
        for index, line in enumerate(page["subtitle"])
    )

    spaces = [_render_space(duty_position_by_id(layout, layout["city_id"]))]
    for index, duty in enumerate(ring_duties(layout)):
        spaces.append(
            render_duty_space(
                layout,
                duty,
                state.get(duty["id"], {}),
                merchant=duty["id"] == merchant_duty_id,
                interactive=interactive,
                ring_index=index if interactive else None,
            )
        )
    spaces.append(_render_ornaments(layout))

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{board["width"]:g}"'
        f' height="{board["height"]:g}" viewBox="{board["view_box"]}" role="img"'
        ' aria-labelledby="svg-title svg-description" data-component="duty-wheel"'
        f' data-merchant-token="{merchant_duty_id}">'
        f'<title id="svg-title">{escape(page["board_title"])}</title>'
        f'<desc id="svg-description">{escape(page["description"])}</desc>'
        f"{_render_defs(layout, merchant_duty_id, interactive)}"
        f'<rect width="{board["width"]:g}" height="{board["height"]:g}"'
        f' fill="{palette["page_background"]}"/>'
        f'<rect x="{frame["x"]:g}" y="{frame["y"]:g}" width="{frame["width"]:g}"'
        f' height="{frame["height"]:g}" rx="{frame["corner_radius"]:g}" fill="none"'
        f' stroke="{palette["frame_stroke"]}" stroke-width="1.5"/>'
        f'<text x="{board["width"] / 2:g}" y="{board["title_baseline"]:g}"'
        f' fill="{palette["title"]}" font-family="Georgia, \'Times New Roman\', serif"'
        f' font-size="30" font-weight="700" text-anchor="middle">'
        f'{escape(page["board_title"])}</text>'
        f'<text x="{board["width"] / 2:g}" y="{board["subtitle_baseline"]:g}"'
        f' fill="{palette["subtitle"]}" font-family="Helvetica, Arial, sans-serif"'
        f' font-size="13.5" text-anchor="middle">{subtitle}</text>'
        f'<g transform="translate({_num(cx)} {_num(cy)})'
        f' scale({_num(board["scale"])}) translate({_num(-cx)} {_num(-cy)})">'
        f'<path d="{board["ground_path"]}" fill="url(#hex-gradient)"'
        f' stroke="{palette["ground_edge"]}" stroke-width="4" stroke-linejoin="round"/>'
        f"{_render_ring_arrows(layout)}{_render_middle_arrows(layout)}"
        f'<g aria-label="Board spaces">{"".join(spaces)}</g>'
        "</g></svg>"
    )


_CONTROLS_HTML = """  <div class="duty-wheel-controls">
    <button type="button" id="duty-wheel-randomize">Randomize Duty tiles</button>
    <button type="button" id="duty-wheel-move-merchant">Move Merchant</button>
    <span class="duty-wheel-counts" role="group" aria-label="Player count">{player_counts}</span>
    <span class="duty-wheel-readout" id="duty-wheel-readout">{readout}</span>
  </div>
"""

_PLAYER_COUNT_BUTTON = (
    '<button type="button" data-player-count="{count}" aria-pressed="{pressed}">{count}p</button>'
)

# Every hook the controls own is prefixed, because the generated setup view drops this panel into
# a page that already has its own `.controls` row and `.readout` spans.
DUTY_WHEEL_CONTROL_STYLES = """  .duty-wheel-controls {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
  }
  .duty-wheel-controls button {
    background: #1C1C1C;
    border: 1px solid #4A4A4A;
    border-radius: 6px;
    color: #F2EEDF;
    cursor: pointer;
    font: inherit;
    font-size: 13px;
    padding: 7px 12px;
  }
  .duty-wheel-controls button:hover { background: #2A2A2A; }
  .duty-wheel-counts { display: flex; gap: 4px; }
  .duty-wheel-counts button[aria-pressed="true"] {
    background: #F2EEDF;
    border-color: #F2EEDF;
    color: #1C1C1C;
  }
  .duty-wheel-readout { color: #A8A296; font-size: 13px; }
"""

# Plain inline JavaScript, no dependencies. It flips opacity on slots the renderer already drew
# and rewrites the eight duty titles; it decides nothing about the game.
_CONTROLS_SCRIPT = """<script>
(function () {
  var SETUPS = __SETUPS__;
  var MERCHANT_PATH = __MERCHANT_PATH__;
  var board = document.querySelector('[data-component="duty-wheel"]');
  var readout = document.getElementById('duty-wheel-readout');
  var countButtons = document.querySelectorAll('.duty-wheel-counts button');
  var setupIndex = 0;
  var merchant = __START__;
  var playerCount = __PLAYER_COUNT__;

  function currentSetup() {
    return SETUPS[setupIndex];
  }

  function entryFor(position) {
    return currentSetup().filter(function (entry) { return entry.position === position; })[0];
  }

  function applySetup() {
    currentSetup().forEach(function (entry) {
      var label = board.querySelector('[data-duty-label="' + entry.position + '"]');
      if (label) { label.textContent = entry.label; }
      var icons = board.querySelectorAll(
        '[data-duty-position="' + entry.position + '"][data-tithe-token]'
      );
      Array.prototype.forEach.call(icons, function (icon) {
        var shown = icon.getAttribute('data-tithe-token') === entry.tithe_icon;
        icon.setAttribute('opacity', shown ? '1' : '0');
      });
    });
  }

  function applyMerchant() {
    var tokens = board.querySelectorAll('[data-token="merchant"]');
    Array.prototype.forEach.call(tokens, function (token) {
      var here = token.getAttribute('data-duty-position') === merchant;
      token.setAttribute('opacity', here ? '1' : '0');
    });
    board.setAttribute('data-merchant-token', merchant);
  }

  // The next duty tile clockwise, wrapping round the ring. The City is not on the path.
  function nextMerchantPosition(current) {
    return MERCHANT_PATH[(MERCHANT_PATH.indexOf(current) + 1) % MERCHANT_PATH.length];
  }

  // Each player count has its own tally drawn on every duty, already centred for that many
  // seats, so switching views only decides which of them shows.
  function applyPlayerCount() {
    var tallies = board.querySelectorAll('[data-cube-tally]');
    Array.prototype.forEach.call(tallies, function (tally) {
      var shown = tally.getAttribute('data-player-count') === String(playerCount);
      tally.setAttribute('opacity', shown ? '1' : '0');
    });
    Array.prototype.forEach.call(countButtons, function (button) {
      var active = button.getAttribute('data-player-count') === String(playerCount);
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
  }

  function updateReadout() {
    readout.textContent =
      'Setup ' + (setupIndex + 1) + ' of ' + SETUPS.length +
      ' \\u2014 Merchant on ' + entryFor(merchant).label +
      ' \\u2014 ' + playerCount + ' players';
  }

  document.getElementById('duty-wheel-randomize').addEventListener('click', function () {
    setupIndex = (setupIndex + 1) % SETUPS.length;
    applySetup();
    updateReadout();
  });

  document.getElementById('duty-wheel-move-merchant').addEventListener('click', function () {
    merchant = nextMerchantPosition(merchant);
    applyMerchant();
    updateReadout();
  });

  Array.prototype.forEach.call(countButtons, function (button) {
    button.addEventListener('click', function () {
      playerCount = Number(button.getAttribute('data-player-count'));
      applyPlayerCount();
      updateReadout();
    });
  });

  updateReadout();
})();
</script>
"""


def duty_wheel_readout(
    layout: dict,
    setup_index: int = 0,
    merchant: str | None = None,
    player_count: int | None = None,
) -> str:
    """What the controls report: the sample setup, where the Merchant stands, and the seat count."""
    position = merchant or layout["merchant_token"]["starts_on"]
    seats = player_count or layout["default_player_count"]
    setups = duty_setups(layout)
    label = next(entry["label"] for entry in setups[setup_index] if entry["position"] == position)
    return f"Setup {setup_index + 1} of {len(setups)} — Merchant on {label} — {seats} players"


def render_duty_wheel_controls_script(layout: dict) -> str:
    """The page's debug buttons, wired to the slots the interactive board draws.

    The whole thing is one IIFE reaching for prefixed hooks only, so a host page can drop it in
    beside its own scripts without sharing a name with them.
    """
    return (
        _CONTROLS_SCRIPT.replace("__SETUPS__", json.dumps(duty_setups(layout)))
        .replace("__MERCHANT_PATH__", json.dumps(merchant_path(layout)))
        .replace("__START__", json.dumps(layout["merchant_token"]["starts_on"]))
        .replace("__PLAYER_COUNT__", json.dumps(layout["default_player_count"]))
    )


def render_duty_wheel_controls_html(layout: dict) -> str:
    """The debug buttons and their readout, with the default player count already pressed."""
    buttons = "".join(
        _PLAYER_COUNT_BUTTON.format(
            count=count, pressed=str(count == layout["default_player_count"]).lower()
        )
        for count in layout["player_counts"]
    )
    return _CONTROLS_HTML.format(
        player_counts=buttons, readout=escape(duty_wheel_readout(layout))
    )


def render_duty_wheel_panel(
    layout: dict, board_state: dict | None = None, include_controls: bool = True
) -> str:
    """The controls and the board as one fragment a host page can drop into its own layout.

    This is what the generated setup view shows: it brings its own wrapper, heading, and width,
    and pairs this with `DUTY_WHEEL_CONTROL_STYLES` and `render_duty_wheel_controls_script()`.
    Without controls the board is the fixed picture, so no hidden slots are drawn either.
    """
    controls = render_duty_wheel_controls_html(layout) if include_controls else ""
    board = render_duty_wheel_svg(layout, board_state, interactive=include_controls)
    return f"{controls}{board}"


def render_duty_wheel_html(
    layout: dict, board_state: dict | None = None, interactive: bool = False
) -> str:
    """The board on its own page, the way the baseline prototype presents it.

    `interactive` is what the generated page uses: it adds the two debug buttons, which cycle
    sample duty setups and walk the Merchant token around the ring.
    """
    palette = layout["palette"]
    merchant = layout["merchant_token"]
    panel = render_duty_wheel_panel(layout, board_state, include_controls=interactive)
    script = render_duty_wheel_controls_script(layout) if interactive else ""
    moves = (
        "The buttons above cycle sample Duty tile setups, walk the Merchant clockwise around the "
        "eight duty tiles — the City is not on his path — and switch the cube tallies between "
        "the two-, three-, and four-player views."
        if interactive
        else "Neither moves."
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Pilgrim — Duty Wheel (generated)</title>
<style>
  * {{ box-sizing: border-box; }}
  html, body {{ min-height: 100%; margin: 0; background: {palette["page_background"]}; }}
  body {{
    display: flex;
    flex-direction: column;
    align-items: center;
    font-family: Helvetica, Arial, sans-serif;
  }}
  svg {{ display: block; width: min(100vw, {layout["board"]["width"]:g}px); height: auto; }}
{DUTY_WHEEL_CONTROL_STYLES}  .duty-wheel-controls {{ padding: 16px 12px 4px; }}
  p.note {{
    color: #A8A296;
    font-size: 13px;
    margin: 0 0 32px;
    padding: 0 16px;
    text-align: center;
    max-width: 720px;
  }}
</style>
</head>
<body>
{panel}
  <p class="note">
    Generated from {LAYOUT_FILENAME}. The purple disc is the {escape(merchant["label"])} and the
    resource icons are Tithe tokens. {moves} Visual/debug only — no GameState integration, no
    gameplay rules, and no sow animation.
  </p>
{script}</body>
</html>
"""
