#!/usr/bin/env python3
"""Minimal single-board production assembler for Pilgrim Gothic v2.

This version is intentionally small:
- builds one player board at a time;
- uses the recalibrated v2 template;
- keeps the frame base and gemstone overlay as separate assets;
- embeds PNG/SVG assets into <defs>;
- writes SVG/HTML and optionally PNG.

PNG output requires CairoSVG:
    python3 -m pip install cairosvg
"""

from __future__ import annotations

import argparse
import base64
import copy
import html
import json
import mimetypes
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Mapping

_HERE = Path(__file__).resolve().parent          # ui/render
_UI = _HERE.parent                              # ui

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)

def q(tag: str) -> str:
    return f"{{{SVG_NS}}}{tag}"

RESOURCE_NAMES = ("piety", "grain", "stone", "silver")
COUNT_NAMES = ("serf", "acolyte", *RESOURCE_NAMES)
GEM_BY_COLOR = {
    "red": "frames/stones_red.png",
    "black": "frames/stones_black.png",
    "sage": "frames/stones_sage.png",
    "pewter": "frames/stones_pewter.png",
    "plum": "frames/stones_plum.png",
    "bone": "frames/stones_bone.png",
}

# The seat colours, and only these. Red is the drape every other colour was derived from and is kept
# as provenance, but it is deliberately NOT a seat: lit red measures L* 20.6, which is darker than
# dimmed sage (23.8) and dimmed bone (25.2), so a red player waiting to be told it was their turn
# would be sitting behind a board dimmer than two boards that are not. See ../assets-gothic/
# frames/README.md for the lit/dim banding this protects.
SEAT_COLORS = ("sage", "pewter", "plum", "bone")

TURNS = ("lit", "dim")

# THE PORTRAIT BACKGROUND, PER SEAT AND PER TURN.
#
# The oval behind a leader's head used to be one warm grey, #b8b1a5, for all four seats. Measuring
# it was the whole answer: in CIE Lab that grey is L* 72.5, chroma 7.0, hue 87 deg, and the BONE
# drape is chroma 7.1, hue 78 deg. It was never a neutral -- it was already the bone seat's colour,
# lightened. So the other three seats are not a new idea, they are the same recipe applied:
#
#     L* 72.5 throughout        a face has to stay legible, so lightness does not carry the signal
#     hue = that seat's drape   measured off the cloth PNGs, not chosen by eye
#     chroma = the turn         28 for the seat to play, 13 for a seat waiting
#
# Chroma rather than lightness is what says whose turn it is here, and it is the second voice
# saying it -- the drape already says it much louder, in lightness. A portrait that dimmed with the
# board would put the player's own face in shadow on three boards out of four.
#
# BONE SIGNALS WITH LIGHTNESS INSTEAD, and it is forced rather than chosen. Its hue has nowhere to
# go but yellow, so at chroma 28 it stops reading as ash and starts reading as tan -- it would be
# the one seat whose identity the scheme damages. So bone is the seat that moves in L* rather than
# in chroma: 86 to play against 72.5 waiting, pale to near-white, with its chroma falling as it
# rises so it whitens rather than yellows. Its dim state is the grey the board has always had.
#
# That makes bone the exception in the mechanism as well as in the numbers, which is worth stating
# plainly rather than hiding behind a table: three seats say "my turn" by becoming more coloured,
# and ash says it by becoming brighter. Both readings are available at a glance because no two
# seats are ever being compared on the same axis -- you are comparing a board with itself.
#
# tests/test_gothic_seat_coherence.py re-derives every one of these from Lab and fails on a typo.
PORTRAIT_BG = {
    "sage":   {"lit": "#a0ba8a", "dim": "#aab69f"},   # hue 129.6, L* 72.5, chroma 28 / 13
    "pewter": {"lit": "#84b7e3", "dim": "#a0b4c9"},   # hue 258.9, L* 72.5, chroma 28 / 13
    "plum":   {"lit": "#cfa4cf", "dim": "#c0acbf"},   # hue 325.8, L* 72.5, chroma 28 / 13
    "bone":   {"lit": "#e1d5c8", "dim": "#bab0a5"},   # hue  77.9, L* 86 / 72.5, chroma 8 / 7
}
PORTRAIT_BG_HUE = {"sage": 129.6, "pewter": 258.9, "plum": 325.8, "bone": 77.9}
# seat -> ((lit L*, lit chroma), (dim L*, dim chroma)). Three seats hold L* and move chroma; bone
# moves L* and holds chroma. The test re-derives the hexes above from exactly these numbers.
PORTRAIT_BG_LC = {
    "sage":   ((72.5, 28), (72.5, 13)),
    "pewter": ((72.5, 28), (72.5, 13)),
    "plum":   ((72.5, 28), (72.5, 13)),
    "bone":   ((86.0, 8), (72.5, 7)),
}


def seat_layers(seat: str) -> dict[str, str]:
    """Every asset a seat's colour decides, from the one colour name.

    A board's colour touches four files, and the whole point of naming them together is that they
    cannot drift apart -- a board wearing a plum drape and sage gemstones is a bug that no single
    file is wrong about. The two frame layers are colour-neutral and identical for every seat; they
    are listed here anyway so that one call returns a complete set and a caller never has to know
    which parts of the frame happen not to vary.
    """
    if seat not in SEAT_COLORS:
        raise BuildError(
            "Unknown seat %r. The seat colours are %s. (Red is the source drape, not a seat -- "
            "lit red is darker than dimmed sage, so it cannot join the lit/dim banding.)"
            % (seat, ", ".join(SEAT_COLORS)))
    return {
        "frame_base": "frames/frame_base_nocloth.png",
        "frame_ornaments": "frames/frame_ornaments.png",
        "cloth_lit": f"frames/cloth_{seat}.png",
        "cloth_dim": f"frames/cloth_{seat}_dim.png",
        "gems": f"frames/stones_{seat}.png",
        # The acolyte cube is a player's own marker, so it wears the seat's colour too. It takes the
        # gemstone treatment rather than the drape's: the drape is dyed wool and reads best
        # desaturated, while this is a 70 px painted block that has to be unmistakable next to the
        # grey serf cube a hand's width away. Bone is the one to watch there -- it is drawn warm
        # cream rather than pearl, which keeps it dE 41 from that grey instead of merging with it.
        "acolyte_cube": f"ui/cube_acolyte_{seat}.svg",
    }


def seat_fills(seat: str) -> dict[str, str]:
    """The colours a seat decides, as opposed to the files it decides.

    Kept apart from `seat_layers` because the caller does different things with them -- one names
    assets to embed, the other names fills to write -- and because a fill that arrived in the layer
    table would be looked for on disk.
    """
    if seat not in SEAT_COLORS:
        raise BuildError("Unknown seat %r. The seat colours are %s."
                         % (seat, ", ".join(SEAT_COLORS)))
    return {
        "portrait_background_lit": PORTRAIT_BG[seat]["lit"],
        "portrait_background_dim": PORTRAIT_BG[seat]["dim"],
    }


# THE TWO RESOURCE BOX LAYOUTS.
#
#   strip   what the template draws: the icon in the upper 132 px, the count on a parchment band
#           across the foot. The default, and the only thing a config without this key gets.
#   disc    the icon fills the whole box, and the count sits on a quarter disc tucked into the
#           lower right corner -- a circle centred exactly on that corner, so the box's own clip
#           leaves its upper-left quadrant and nothing else.
#
# NO PER-RESOURCE COORDINATES, and that is the point of writing it this way. Every number below is
# derived from the box the template already declares, so the four boxes need four rectangles and
# not four sets of disc-and-numeral positions -- and a fifth resource, whenever one arrives, needs
# a rectangle and nothing more. The template stays the one place a coordinate lives; this is the
# one place a RULE about coordinates lives.
RESOURCE_LAYOUTS = ("strip", "disc")
DISC_RADIUS = 100.0         # of the quarter disc, from the box's lower right corner
# Where the numeral sits along the diagonal, as a fraction of the radius. A quarter disc's centre
# of AREA is 4/3pi = 0.424 of the way out, and that is where this started -- but the area is
# bunched at the corner while the parchment you can SEE runs on up the arc, so a numeral placed
# there reads as pushed into the corner rather than sitting in the shape. 0.45 is the eye's answer
# rather than the integral's, and it buys the clearance the numeral needs below it besides.
DISC_TEXT_FRAC = 0.45
# TWO SIZES, BY HOW MANY DIGITS THERE ARE, and it is the quadrant that forces it. A quarter disc
# is widest along its diagonal, so one numeral has room to spare while two are already pressing the
# arc. Measured against the drawn ink rather than the em box -- the em box carries ascender space
# these lining figures never use, and sizing to it would leave the disc looking half empty, which
# is what it looked like. Usable radius is 88.5, the arc less its own 3 px rule:
#
#     one digit    74: reaches 89.3 of the 98.5 arc, clears the box's foot by 18
#     two digits   62: reaches 95.0 of the 98.5 arc, clears the box's foot by 23
#
# All three edges of the quadrant are measured, not just the arc, and that correction is the reason
# the radius is 100 rather than 90. The first sizing pass measured the numeral's ink inside the
# box's own crop -- so ink the box CLIPPED was invisible to it, and it could only ever report the
# arc. It said there was room. What it could not see was that the numeral had 12 units of parchment
# beneath it and 22 to its right, which at a 405 px board is under three pixels, and reads exactly
# as a number sinking out of its disc.
#
# Silver is the reason two digits have to fit at all: EXCESS_RESOURCE_CAP trims stone and wheat to
# 6 at round end, but nothing caps silver, so a double-digit purse is a normal board state.
DISC_FONT = 74.0            # one digit
DISC_FONT_WIDE = 62.0       # two or more
DISC_ICON_INSET = 10.0      # breathing room between the icon and the box edge, all four sides
# THE DISC IS A SHADOW, NOT A PATCH. It was parchment with a drawn arc, which made the corner read
# as an inlaid piece of furniture -- a second object sitting on the box. Painting black at 60%%
# instead lets each field darken in its OWN colour, so the purple stays purple and the blue stays
# blue, and the corner reads as shade the icon casts rather than as something added. The arc keeps
# no rule for the same reason: a shadow with a drawn edge is neither a shadow nor an inlay.
#
# 60%% rather than something gentler because of what the numeral has to do on top of it. The pale
# fields are the weak case -- a pale field darkened is still pale -- and at 45%% the count sits at
# 4.3:1 against grain and stone, against 6.8:1 at 60%%. That count renders near 8 px on a 14 inch
# screen, which is already at the legibility floor the layout tool warns about, so the contrast is
# not the place to economise.
DISC_FILL = "#000000"
DISC_FILL_OPACITY = 0.60


INK = "#24190f"             # the board's text colour, and the dark half of the numeral's choice


def _luminance(colour: str) -> float:
    channels = [int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a: str, b: str) -> float:
    """WCAG contrast ratio, so "is this readable" is a number rather than an opinion."""
    low, high = sorted((_luminance(a), _luminance(b)))
    return (high + 0.05) / (low + 0.05)


def darken(colour: str, opacity: float) -> str:
    """What a field becomes under the disc's black at this opacity."""
    return "#%02x%02x%02x" % tuple(
        int(round(int(colour[i:i + 2], 16) * (1 - opacity))) for i in (1, 3, 5))


def apply_disc_layout(group, rects, name, parchment):
    """Rebuild one resource box as icon-fills-the-box with the count on a corner disc.

    Everything is measured off the group's own rectangles: the coloured field gives the origin and
    width, the noise overlay gives the full height -- it is the one rect that always spanned the
    whole box, which is why it is the honest source for that number rather than 179 written here.
    """
    box, strip = rects[0], rects[1]
    full = next((r for r in rects if float(r.get("height", 0)) > float(box.get("height", 0))), None)
    if full is None:
        raise BuildError(
            f"Resource group '{name}' has no rect spanning the whole box, so the disc layout "
            f"cannot tell how tall the box is. The template's third rect is the noise overlay and "
            f"is normally that rect.")
    x, y = float(box.get("x")), float(box.get("y"))
    w, h = float(box.get("width")), float(full.get("height"))

    box.set("height", str(h))                       # the colour now runs the full box
    group.remove(strip)                             # the parchment band and the rule under it go
    for child in list(group):
        if child.tag == q("line"):
            group.remove(child)

    icon = group.find(f".//*[@data-asset-role='resource:{name}']")
    if icon is None:
        raise BuildError(f"Resource group '{name}' has no icon to fill the box with")
    icon.set("x", str(x + DISC_ICON_INSET))
    icon.set("y", str(y + DISC_ICON_INSET))
    icon.set("width", str(w - 2 * DISC_ICON_INSET))
    icon.set("height", str(h - 2 * DISC_ICON_INSET))
    icon.set("preserveAspectRatio", "xMidYMid meet")

    text = group.find(q("text"))
    if text is None:
        raise BuildError(f"Resource group '{name}' has no count to place")
    group.remove(text)                              # removed and re-appended, so it draws on top

    cx, cy = x + w, y + h
    disc = ET.SubElement(group, q("circle"))
    disc.set("cx", str(cx))
    disc.set("cy", str(cy))
    disc.set("r", str(DISC_RADIUS))
    disc.set("fill", DISC_FILL)
    disc.set("fill-opacity", str(DISC_FILL_OPACITY))
    disc.set("data-resource-disc", name)

    # The numeral's colour is DERIVED from what it will actually sit on, never set beside the fill
    # and hoped to match. Someone deepening the shadow later would otherwise leave a dark numeral on
    # a dark ground, and the count is the one thing on this box that has to be readable.
    ground = darken(str(box.get("fill") or "#808080"), DISC_FILL_OPACITY) \
        if DISC_FILL == "#000000" else DISC_FILL
    text.set("fill", parchment if contrast(parchment, ground) >= contrast(INK, ground) else INK)

    # A quarter disc's centre of AREA lies 4r/3pi from the corner along each axis, not r/2. Placing
    # the numeral there is the difference between a number sitting in the shape and one that looks
    # pushed into the curve; the eye is unforgiving about this and it costs one constant.
    offset = DISC_RADIUS * DISC_TEXT_FRAC
    font = DISC_FONT if len((text.text or "").strip()) < 2 else DISC_FONT_WIDE
    text.set("x", str(cx - offset))
    text.set("y", str(cy - offset + font * 0.36))        # 0.36em lifts the baseline to the centre
    text.set("font-size", str(font))
    group.append(text)


def resource_count_fonts(config) -> tuple[float, ...]:
    """Every size a resource count can be drawn at under this config's layout.

    For the layout tool rather than for the board: it reports whether the counts are legible at a
    given board width, and the answer is decided by the SMALLEST a count can get, not by whichever
    counts the sample config happens to hold. A test config of 4, 0, 3 and 1 would otherwise have
    the readout answering for single digits and saying nothing about the double-digit purse a real
    game produces.

    The strip's size is not here because it is not here to be had: it lives in the template, where
    the tool reads it off the board it is already holding.
    """
    if str(config.get("resource_layout", "strip")) == "disc":
        return (DISC_FONT, DISC_FONT_WIDE)
    return ()


class BuildError(RuntimeError):
    """Raised for user-facing build errors."""


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BuildError(f"File not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise BuildError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise BuildError(f"Expected a JSON object in {path}")
    return data


def parse_number(value: str | None) -> float | None:
    if not value:
        return None
    match = re.match(r"\s*(-?\d+(?:\.\d+)?)", value)
    return float(match.group(1)) if match else None


def fmt(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.4f}".rstrip("0").rstrip(".")


def href(node: ET.Element) -> str:
    return node.get("href") or node.get(f"{{{XLINK_NS}}}href") or ""


def set_href(node: ET.Element, value: str) -> None:
    """Set the modern `href`, and the legacy `xlink:href` only where it is worth having.

    Mirroring the two is free for a path or a `#id`, and it buys compatibility with renderers
    predating SVG2. Mirroring a data URI is not free: it writes the whole Base64 payload a second
    time, which doubled every embedded asset and took one board's self-contained SVG from about
    6 MB to 12.6 MB. Nothing that can open a 6 MB inline data URI needs the xlink fallback.
    """
    node.set("href", value)
    if not value.startswith("data:"):
        node.set(f"{{{XLINK_NS}}}href", value)


def assert_no_duplicated_payloads(root: ET.Element) -> None:
    """No element may carry a `data:` href and an `xlink:href` at the same time.

    This is the regression guard for the doubling above. It is an assertion inside the build
    rather than a note in the README, because the failure is invisible: the board renders
    correctly at twice the weight, so nothing complains and nobody looks.
    """
    for node in root.iter():
        modern = node.get("href", "")
        legacy = node.get(f"{{{XLINK_NS}}}href")
        if modern.startswith("data:") and legacy is not None:
            raise BuildError(
                "%s carries a data: href and an xlink:href, so its payload is embedded twice. "
                "See set_href()." % node.tag)


def resolve_asset(assets_dir: Path, relative_path: str) -> Path:
    path = (assets_dir / relative_path).resolve()
    try:
        path.relative_to(assets_dir.resolve())
    except ValueError as exc:
        raise BuildError(f"Asset path escapes --assets-dir: {relative_path}") from exc
    if not path.is_file():
        raise BuildError(f"Missing asset: {path}")
    return path


def asset_path_for_role(config: Mapping[str, Any], role: str) -> str:
    if role.startswith("resource:"):
        resource = role.split(":", 1)[1]
        value = config.get("resources", {}).get(resource)
    else:
        value = config.get(role)
    if not isinstance(value, str) or not value:
        raise BuildError(f"Missing asset path for role '{role}'")
    return value


def png_size(path: Path) -> tuple[float, float]:
    header = path.read_bytes()[:24]
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise BuildError(f"Invalid PNG: {path}")
    return float(int.from_bytes(header[16:20], "big")), float(int.from_bytes(header[20:24], "big"))


def svg_size(path: Path) -> tuple[float, float]:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise BuildError(f"Invalid SVG asset {path}: {exc}") from exc
    view_box = root.get("viewBox") or root.get("viewbox")
    if view_box:
        parts = re.split(r"[ ,]+", view_box.strip())
        if len(parts) == 4:
            return float(parts[2]), float(parts[3])
    width = parse_number(root.get("width"))
    height = parse_number(root.get("height"))
    if width and height:
        return width, height
    raise BuildError(f"SVG has no usable viewBox or dimensions: {path}")


def intrinsic_size(path: Path) -> tuple[float, float]:
    """The asset's own canvas: its viewBox for SVG, its IHDR for PNG.

    This deliberately does not consult a metrics file. The production template places every asset
    into a calibrated box with preserveAspectRatio="xMidYMid meet", so what the assembler needs is
    the canvas and nothing else. Metadata describing visible ink belongs to the picker, which
    normalizes replacement artwork; adding it here would be a second source of truth for a
    measurement this program never makes.
    """
    return svg_size(path) if path.suffix.lower() == ".svg" else png_size(path)


def data_uri(path: Path) -> str:
    suffix = path.suffix.lower()
    mime = "image/svg+xml" if suffix == ".svg" else "image/png" if suffix == ".png" else None
    if mime is None:
        mime = mimetypes.guess_type(path.name)[0]
    if mime is None:
        raise BuildError(f"Unsupported asset type: {path}")
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{payload}"


def nearest_text(root: ET.Element, x: float, y: float) -> ET.Element:
    matches: list[tuple[float, ET.Element]] = []
    for node in root.iter(q("text")):
        nx = parse_number(node.get("x"))
        ny = parse_number(node.get("y"))
        if nx is None or ny is None:
            continue
        distance = abs(nx - x) + abs(ny - y)
        if distance <= 35:
            matches.append((distance, node))
    if not matches:
        raise BuildError(f"No count text found near ({x}, {y})")
    return min(matches, key=lambda pair: pair[0])[1]


def apply_config(root: ET.Element, config: Mapping[str, Any], layout: Mapping[str, Any]) -> None:
    # Replace every image with a declared data-asset-role.
    for image in root.iter(q("image")):
        role = image.get("data-asset-role")
        if role:
            set_href(image, asset_path_for_role(config, role))

    # Counts.
    count_points = {
        "serf": layout["population"]["serf"]["count"],
        "acolyte": layout["population"]["acolyte"]["count"],
        **{name: layout["resources"][name]["count"] for name in RESOURCE_NAMES},
    }
    counts = config.get("counts", {})
    for name in COUNT_NAMES:
        x, y = count_points[name]
        node = nearest_text(root, float(x), float(y))
        node.text = str(counts.get(name, 0))
        node.set("id", f"count-{name}")
        node.set("fill", str(config.get("text_fill", "#24190f")))
        node.set("font-family", str(config.get("font_family", "Georgia, serif")))

    # Resource card colours, and which of the two box layouts they wear.
    resource_fills = config.get("resource_fills", {})
    layout_name = str(config.get("resource_layout", "strip"))
    if layout_name not in RESOURCE_LAYOUTS:
        raise BuildError("resource_layout must be one of %s, not %r"
                         % (", ".join(RESOURCE_LAYOUTS), layout_name))
    for name in RESOURCE_NAMES:
        group = root.find(f".//{q('g')}[@id='resource-{name}']")
        if group is None:
            raise BuildError(f"Template is missing resource group '{name}'")
        rects = [child for child in list(group) if child.tag == q("rect")]
        if len(rects) < 2:
            raise BuildError(f"Resource group '{name}' needs at least two rects")
        rects[0].set("fill", str(resource_fills.get(name, rects[0].get("fill", "#ffffff"))))
        rects[1].set("fill", str(config.get("resource_value_fill", "#ead8b4")))
        if layout_name == "disc":
            apply_disc_layout(group, rects, name,
                              str(config.get("resource_value_fill", "#ead8b4")))

    # Board underlay colours.
    underlay = {
        "underlay-portrait-lit": config.get("portrait_background_lit", "#b8b1a5"),
        "underlay-portrait-dim": config.get("portrait_background_dim", "#b8b1a5"),
        "underlay-panel": config.get("information_panel_fill", "#ead8b4"),
        "underlay-upper": config.get("information_panel_fill", "#ead8b4"),
        "underlay-resource-row": config.get("resource_row_fill", "#39352f"),
    }
    for element_id, fill in underlay.items():
        node = root.find(f".//*[@id='{element_id}']")
        if node is not None:
            node.set("fill", str(fill))

    # Whose turn it is. Both drapes stay in the board and one is hidden, so the play view changes
    # turn by writing one attribute rather than asking for a new 3 MB board.
    turn = str(config.get("turn", "lit"))
    if turn not in TURNS:
        raise BuildError(f"turn must be one of {TURNS}, not {turn!r}")
    # EVERY holder, not the first one. There are two now -- the drape and the portrait background --
    # and `find` would have set the drape and left the oval on whichever state the template was
    # saved in. That failure is invisible in the markup, which is well formed either way, and shows
    # up only as a dim board wearing a lit seat's portrait.
    holders = root.findall(f".//{q('g')}[@data-turn]")
    if not holders:
        raise BuildError("Template has no <g data-turn>; the turn toggle cannot be set. "
                         "See the frame layer comment in player_board_template.svg.")
    for holder in holders:
        holder.set("data-turn", turn)
        for layer in list(holder):
            state = layer.get("data-turn-layer")
            if state is None:
                continue
            # Written statically as well as in CSS, for renderers that do not apply the stylesheet.
            if state == turn:
                layer.attrib.pop("display", None)
            else:
                layer.set("display", "none")

    root.set("role", "img")
    root.set("aria-label", str(config.get("aria_label", "Pilgrim Gothic v2 player board")))
    root.set("data-board-id", slug(str(config.get("id", "pilgrim_player_board_v2"))))
    if config.get("seat"):
        root.set("data-seat", str(config["seat"]))


def embed_assets_once(root: ET.Element, assets_dir: Path) -> None:
    defs = root.find(q("defs"))
    if defs is None:
        defs = ET.Element(q("defs"))
        root.insert(0, defs)

    template_images = [node for node in root.iter(q("image")) if node not in list(defs)]
    parents = {child: parent for parent in root.iter() for child in parent}
    symbol_by_key: dict[tuple[str, str], str] = {}

    for index, image in enumerate(template_images, start=1):
        image_href = href(image)
        if not image_href or image_href.startswith(("data:", "#")):
            continue

        asset = resolve_asset(assets_dir, image_href)
        rel = asset.relative_to(assets_dir).as_posix()
        preserve = image.get("preserveAspectRatio", "xMidYMid meet")
        key = (rel, preserve)

        symbol_id = symbol_by_key.get(key)
        if symbol_id is None:
            symbol_id = f"asset-{index}"
            symbol_by_key[key] = symbol_id

            width, height = intrinsic_size(asset)
            symbol = ET.SubElement(
                defs,
                q("symbol"),
                {
                    "id": symbol_id,
                    "viewBox": f"0 0 {fmt(width)} {fmt(height)}",
                    "preserveAspectRatio": preserve,
                    "data-source": rel,
                },
            )
            embedded = ET.SubElement(
                symbol,
                q("image"),
                {
                    "x": "0",
                    "y": "0",
                    "width": fmt(width),
                    "height": fmt(height),
                    "preserveAspectRatio": "none",
                },
            )
            set_href(embedded, data_uri(asset))

        use_attrs = {
            key_: value
            for key_, value in image.attrib.items()
            if key_ not in {"href", f"{{{XLINK_NS}}}href", "preserveAspectRatio"}
        }
        replacement = ET.Element(q("use"), use_attrs)
        set_href(replacement, f"#{symbol_id}")

        parent = parents[image]
        pos = list(parent).index(image)
        parent.remove(image)
        parent.insert(pos, replacement)


def svg_viewbox(svg_text: str) -> tuple[float, float]:
    root = ET.fromstring(svg_text)
    view_box = root.get("viewBox") or root.get("viewbox")
    if not view_box:
        raise BuildError("Generated SVG has no viewBox")
    parts = [float(part) for part in re.split(r"[ ,]+", view_box.strip())]
    if len(parts) != 4 or parts[2] <= 0 or parts[3] <= 0:
        raise BuildError(f"Invalid generated SVG viewBox: {view_box}")
    return parts[2], parts[3]


def svg_to_html(svg_text: str, title: str) -> str:
    svg_markup = re.sub(r"^<\?xml[^>]+>\s*", "", svg_text)
    logical_width, _ = svg_viewbox(svg_text)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{html.escape(title)}</title>
<style>
html,body{{margin:0;min-height:100%;background:#123d2c}}
body{{display:grid;place-items:center;padding:2.5vw;box-sizing:border-box}}
svg{{display:block;width:min(100%,{round(logical_width)}px);height:auto;overflow:visible;
    filter:drop-shadow(0 18px 24px rgba(0,0,0,.32))}}
</style>
</head>
<body>
{svg_markup}
</body>
</html>
"""


def render_png(svg_text: str, output_path: Path, output_width: int) -> None:
    try:
        import cairosvg  # type: ignore
    except ImportError as exc:
        raise BuildError("PNG output requires CairoSVG: python3 -m pip install cairosvg") from exc

    if output_width <= 0:
        raise BuildError("--output-width must be greater than zero")

    logical_width, logical_height = svg_viewbox(svg_text)
    output_height = max(1, round(output_width * logical_height / logical_width))
    cairosvg.svg2png(
        bytestring=svg_text.encode("utf-8"),
        write_to=str(output_path),
        output_width=output_width,
        output_height=output_height,
    )


def slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
    return cleaned or "pilgrim_player_board"


def parse_formats(raw: str) -> set[str]:
    formats = {part.strip().lower() for part in raw.split(",") if part.strip()}
    invalid = formats - {"svg", "html", "png"}
    if invalid or not formats:
        raise BuildError(f"Invalid --formats value: {raw}")
    return formats


def apply_seat(config: dict[str, Any], seat: str | None = None) -> dict[str, Any]:
    """Expand `seat` into the five layer paths, without overwriting anything set by hand.

    Explicit paths win over the seat, which is what makes the regression test possible: the check
    that the layered frame still draws the original board sets frame_base, frame_ornaments and
    cloth_lit to the red source directly, and no seat name can express that.
    """
    if seat:
        config["seat"] = seat
    if "frame" in config:
        raise BuildError(
            "This config sets 'frame', which no longer exists: the frame is now frame_base + "
            "frame_ornaments + cloth_lit/cloth_dim. Replace it with \"seat\": \"%s\"."
            % SEAT_COLORS[0])
    if config.get("seat"):
        for role, path in seat_layers(str(config["seat"])).items():
            config.setdefault(role, path)
        for role, fill in seat_fills(str(config["seat"])).items():
            config.setdefault(role, fill)
    # `portrait_background` was one colour for every seat and both turns. A config still setting it
    # means what it always meant, and it outranks the seat like any other explicit value -- but it
    # now has to reach both states, or the turn toggle would show a seat-coloured oval one moment
    # and that config's colour the next.
    if config.get("portrait_background"):
        config.setdefault("portrait_background_lit", config["portrait_background"])
        config.setdefault("portrait_background_dim", config["portrait_background"])
    missing = [r for r in ("frame_base", "frame_ornaments", "cloth_lit", "cloth_dim", "gems")
               if not config.get(r)]
    if missing:
        raise BuildError(
            "Config gives no %s, and no 'seat' to derive them from. Add \"seat\": \"%s\", or set "
            "each path explicitly." % (" or ".join(missing), SEAT_COLORS[0]))
    return config


def build_one(args: argparse.Namespace) -> Path:
    assets_dir = Path(args.assets_dir).expanduser().resolve()
    config_path = Path(args.config).expanduser().resolve() if args.config else assets_dir / "production_test_config.json"
    template_path = assets_dir / "template" / "player_board_template.svg"
    layout_path = assets_dir / "metadata" / "layout.json"

    for required in (config_path, template_path, layout_path):
        if not required.is_file():
            raise BuildError(f"Required file not found: {required}")

    config = copy.deepcopy(read_json(config_path))
    layout = read_json(layout_path)

    if args.name:
        config["id"] = args.name
    if args.portrait:
        config["portrait"] = args.portrait

    apply_seat(config, args.seat)

    if args.turn:
        config["turn"] = args.turn
    if args.gems:
        config["gems"] = args.gems
    elif args.gem_color:
        config["gems"] = GEM_BY_COLOR[args.gem_color]

    for key, value in {
        "serf": args.serfs,
        "acolyte": args.acolytes,
        "piety": args.piety,
        "grain": args.grain,
        "stone": args.stone,
        "silver": args.silver,
    }.items():
        if value is not None:
            if value < 0:
                raise BuildError(f"{key} count cannot be negative")
            config.setdefault("counts", {})[key] = value

    root = ET.parse(template_path).getroot()
    apply_config(root, config, layout)
    embed_assets_once(root, assets_dir)
    assert_no_duplicated_payloads(root)

    svg_text = '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n"

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    board_id = slug(str(config.get("id", "pilgrim_player_board_v2")))
    formats = parse_formats(args.formats)

    if "svg" in formats:
        (output_dir / f"{board_id}.svg").write_text(svg_text, encoding="utf-8")
    if "html" in formats:
        (output_dir / f"{board_id}.html").write_text(svg_to_html(svg_text, board_id), encoding="utf-8")
    if "png" in formats:
        render_png(svg_text, output_dir / f"{board_id}.png", args.output_width)

    return output_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Build one Pilgrim Gothic v2 player board.")
    parser.add_argument("--assets-dir", default=str(_UI / "assets-gothic"))
    parser.add_argument("--config", help="Defaults to <assets-dir>/production_test_config.json")
    parser.add_argument("--output-dir", default=str(_UI / "generated"))
    parser.add_argument("--formats", default="svg,html,png", help="Comma-separated: svg,html,png")
    parser.add_argument("--output-width", type=int, default=1400)
    parser.add_argument("--name")
    parser.add_argument("--portrait", help="Path relative to --assets-dir")
    parser.add_argument("--seat", choices=SEAT_COLORS,
                        help="Seat colour: sets the drape, its dim twin and the gemstones together")
    parser.add_argument("--turn", choices=TURNS,
                        help="Which drape is showing: lit for the seat to play, dim for the rest")
    parser.add_argument("--gem-color", choices=sorted(GEM_BY_COLOR), help="Override just the gemstone overlay")
    parser.add_argument("--gems", help="Explicit gemstone overlay path relative to --assets-dir")
    parser.add_argument("--serfs", type=int)
    parser.add_argument("--acolytes", type=int)
    parser.add_argument("--piety", type=int)
    parser.add_argument("--grain", type=int)
    parser.add_argument("--stone", type=int)
    parser.add_argument("--silver", type=int)

    args = parser.parse_args()
    try:
        out = build_one(args)
    except (BuildError, ET.ParseError, OSError) as exc:
        parser.error(str(exc))
        return 2

    print(f"Built one v2 player board in {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
