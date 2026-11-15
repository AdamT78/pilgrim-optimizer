#!/usr/bin/env python3
"""The drawn acolyte, as an alternative to the parametric hood beside this file.

WHY THERE ARE TWO. hood.py is a 96-point outline with one fill, which is why a seat's colour has
always been free: there is one shape and one `fill` to put the colour in. This one is a DRAWING,
and a drawing cannot be recoloured by setting an attribute. It arrives as three layers -- see
tools/duty_art/split_acolyte.py, which makes them from the master -- and the board stacks them:
a mask filled with the seat's colour, a second mask filled with that colour darkened, and an
overlay carrying the ink and the tan, which are the drawing's own and identical for every player.

THE SHADOW IS DERIVED AND NOT STORED, which is the whole reason this is a module rather than two
more hex values in a table. Tint only the lit robe and a plum acolyte gets green shadows. The
ratios below are measured off the master -- in HLS the dark green sits at 0.422 of the lit
green's lightness -- so one number carries to any seat colour, including ones that do not exist
yet. Re-running the splitter prints the measured ratio; if a redrawn acolyte shades differently,
this is where that moves, because nothing downstream re-measures the master.

WHAT IS SHARED WITH THE HOOD AND WHAT IS NOT. The seat colours, their order, and how a PILE is
built are facts about players and about tiles; they do not change because the figure was redrawn,
so they are read from hood.py rather than copied. The figure's own proportions do change, and
they are here.

NO PATH, NO INK, NO STROKE. Those are the hood's way of being a figure and this one has no use
for them -- its outline is painted into the overlay. A reader looking for them here should not
find them half-filled in.
"""
import colorsys

import hood

# THE INKED BOX, MEASURED OFF THE LAYERS RATHER THAN ASSUMED. The master is trimmed to its ink
# before the layers are cut, so this is the drawing's own aspect and not the canvas it arrived
# on. 1.2037 against the hood's 1.2000 -- near enough that the two figures occupy the same slot,
# far enough that using the hood's number would letterbox this one.
FRIAR_H = 1.2037

# THE THREE LAYERS, by the names the splitter writes. The board loads them; the master beside
# them is the source and is never loaded.
LAYERS = ("robe", "shade", "over")
STEM = "acolyte_friar"

# HOW MUCH LIGHT THE SHADOW HAS LOST, in HLS, measured off the master: the dark green is at 0.422
# of the lit green's lightness and 1.444 of its saturation. SATURATION GOES UP, which looks wrong
# written down and is what the drawing does -- a shadow on cloth keeps its colour and loses its
# light, so the hue reads STRONGER as it darkens. It is capped at full below, because a seat
# whose colour is already saturated has nowhere to go.
SHADE_L, SHADE_S = 0.422, 1.444

# THE PILE IS TIGHTER FOR THIS FIGURE, and that is a fact about the drawing rather than about the
# board. A hood is a solid mass that fills its box; this one tapers to a point and carries air at
# the shoulders, so at the hood's spacing it reads as four small figures with gaps rather than as
# a row of people. At a gap of 0 the boxes touch and the INK does not -- 42 pixels against the
# hood's 36, with the four seats still telling apart three deep, which was checked on the city
# tile because the city is where the piles are deepest.
#
# AND IT JOGS BY TWICE THE HOOD'S NUMBER, which is the same distance on screen. `lean` is the
# sideways nudge that breaks a pile up so it reads as separate people, and the rule it feeds was
# changed at the same time as this: it used to alternate a figure LEFT or RIGHT of the column and
# now it nudges every other one to the right of a column the rest stand on. Alternating, the two
# ends were `lean` apart and the swing between them was TWICE that; nudging, the swing is `lean`
# itself. So 0.2 here is 0.1 of a width each way, which is exactly what this figure had.
#
# WHY THE RULE CHANGED IS IN THE TEMPLATE, beside the line that does it. In short: the figure
# standing on the line was exempt from the alternation, so the first step up a pile was half the
# size of every step above it, and a stack that is supposed to zigzag evenly did not.
TILE = dict(hood.TILE, gap=0.0, lean=0.2)


def shade_of(seat_colour: str) -> str:
    """A seat's shadow: its own colour with the measured amount of light taken out."""
    r, g, b = (int(seat_colour[i:i + 2], 16) / 255 for i in (1, 3, 5))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    out = colorsys.hls_to_rgb(h, l * SHADE_L, min(1.0, s * SHADE_S))
    return "#%02x%02x%02x" % tuple(round(c * 255) for c in out)


def as_dict(over: str) -> dict:
    """Everything the page needs, in the same shape hood.as_dict() answers in.

    THE TWO MASKS ARE NOT IN HERE. They are CSS -- a mask-image on two custom properties, set
    once for the page -- because a data URI repeated per figure would be the same twenty
    kilobytes forty-two times. Only the overlay is an <img>, and it is one string the markup
    points at.
    """
    return {"kind": "friar", "h": FRIAR_H, "over": over,
            "shadeOf": {k: shade_of(v) for k, v in hood.SEAT_SWATCH.items()},
            "swatch": hood.SEAT_SWATCH, "order": list(hood.SEAT_ORDER),
            "step": TILE["step"], "lean": TILE["lean"], "gap": TILE["gap"]}
