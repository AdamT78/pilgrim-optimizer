#!/usr/bin/env python3
"""The hooded acolyte, copied into board_v2 so this board reads nothing out of ui/render/.

WHY A COPY AND NOT AN IMPORT. The same rule the banners follow: the v2 board is not allowed to
reach into the older trees at build time, so a change over there cannot alter this board and
neither tree's guards reach the other. ui/render/population_sets.py remains the ORIGINAL and is
where any question about the shape should be settled; this is a transcript of the facts the
board needs, taken on 2026-11-09.

WHAT WAS COPIED, AND WHAT DELIBERATELY WAS NOT. The outline, the face, the ink, the seat colours
and the tile block's numbers. NOT the two surfaces, the gothic set, the card's placement table or
the duotoned photograph: this board draws one population one way, and carrying the rest would be
carrying a table to use one row of.

THERE IS NO ASSET HERE AND SO NO ATTRIBUTION ENTRY. The mark is drawn -- a 96-point path and an
ellipse -- not loaded, so nothing lands under an assetDir and nothing needs a record. Its
provenance is this docstring and the original module, which says of the outline:

   "Traced from Adam's mock-up: the outline is a parametric shape fitted to it with the three
    landmarks PINNED rather than fitted -- the dome's widest half-width 0.300 of the figure's
    width at 0.300 down, the neck notch 0.2143 at 0.686 down, the shoulder reaching full width
    by 1.086 down -- because an area fit traded the neck away. The notch is a handful of pixels
    and it is the whole read: without it the shape is a pawn."

Coordinates are fractions of the figure's WIDTH, x from its centre and y from its crown, so the
shape scales with one number.
"""

# One unit wide, crown at y = 0. 96 points, verbatim from population_sets.hood_path().
HOOD_PATH = (
    "M0.0000 0.0000L0.0413 0.0029L0.0817 0.0114L0.1206 0.0253L0.1573 0.0445L0.1909 0.0686L0.2"
    "209 0.0970L0.2467 0.1294L0.2679 0.1649L0.2839 0.2030L0.2945 0.2430L0.2996 0.2840L0.2989 "
    "0.3254L0.2927 0.3663L0.2973 0.4074L0.2975 0.4487L0.2933 0.4899L0.2850 0.5304L0.2729 0.57"
    "00L0.2573 0.6083L0.2388 0.6453L0.2176 0.6809L0.2423 0.7074L0.2745 0.7335L0.3057 0.7606L0"
    ".3358 0.7890L0.3647 0.8187L0.3920 0.8498L0.4174 0.8825L0.4404 0.9168L0.4607 0.9529L0.477"
    "5 0.9907L0.4902 1.0301L0.4983 1.0706L0.5000 1.1119L0.5000 1.1533L0.4964 1.1939L0.4569 1."
    "2000L0.4156 1.2000L0.3742 1.2000L0.3328 1.2000L0.2914 1.2000L0.2500 1.2000L0.2086 1.2000"
    "L0.1672 1.2000L0.1259 1.2000L0.0845 1.2000L0.0431 1.2000L0.0017 1.2000L-0.0397 1.2000L-0"
    ".0811 1.2000L-0.1225 1.2000L-0.1639 1.2000L-0.2052 1.2000L-0.2466 1.2000L-0.2880 1.2000L"
    "-0.3294 1.2000L-0.3708 1.2000L-0.4122 1.2000L-0.4536 1.2000L-0.4941 1.1963L-0.5000 1.156"
    "7L-0.5000 1.1153L-0.4987 1.0740L-0.4911 1.0333L-0.4787 0.9939L-0.4622 0.9559L-0.4422 0.9"
    "197L-0.4193 0.8852L-0.3941 0.8524L-0.3670 0.8212L-0.3383 0.7914L-0.3082 0.7629L-0.2771 0"
    ".7357L-0.2450 0.7095L-0.2158 0.6837L-0.2371 0.6483L-0.2559 0.6114L-0.2717 0.5732L-0.2842"
    " 0.5337L-0.2928 0.4932L-0.2973 0.4521L-0.2974 0.4107L-0.2933 0.3696L-0.2986 0.3287L-0.29"
    "97 0.2874L-0.2952 0.2463L-0.2850 0.2062L-0.2694 0.1679L-0.2486 0.1321L-0.2232 0.0995L-0."
    "1935 0.0708L-0.1601 0.0463L-0.1237 0.0267L-0.0850 0.0123L-0.0446 0.0033Z"
)

HOOD_H = 1.2              # height in width units, so the aspect w/h is 1/1.2 = 0.8333
HOOD_FACE = {'cy': 0.336, 'rx': 0.207, 'ry': 0.2424}
# NOT DECORATION. Pewter and plum fall to 1.2:1 against the brightest tile bottom and would
# vanish without something dark around them; 0.055 of a width, centred, puts 2.6% outside.
HOOD_INK = '#2b2114'
HOOD_STROKE = 0.055

# A SEAT'S COLOUR IS A PROPERTY OF THE PLAYER, not of how its people are drawn -- which is why
# the original keeps this table apart from the figure. Copied whole so the two cannot disagree
# about plum.
SEAT_SWATCH = {'sage': '#7d9b52', 'pewter': '#4a6b86', 'plum': '#8a5a92', 'bone': '#A8A296'}
SEAT_ORDER = ('sage', 'pewter', 'plum', 'bone')

# The tile block: how a PILE is built. `step` is how far each figure rises above the one under
# it, `lean` is the sideways jog that makes a pile read as separate people rather than as one
# smeared silhouette, and `gap` is the clearance between neighbouring seats' piles.
#
# A pile is 2 * lean wider than one figure against a gap of 0.24, which leaves 0.04 of a figure
# between neighbours. That is bounding boxes; the ink clears by more, because the leaning
# figures are the upper ones and a figure is 9% of its width at the crown.
TILE = {"overlap": 0.6, "gap": 0.24, "step": 0.3, "lean": 0.1}


def as_dict() -> dict:
    """Everything the page needs, in one object, so the template holds no copy of any of it."""
    return {"path": HOOD_PATH, "h": HOOD_H, "face": HOOD_FACE, "ink": HOOD_INK,
            "stroke": HOOD_STROKE, "swatch": SEAT_SWATCH, "order": list(SEAT_ORDER),
            "step": TILE["step"], "lean": TILE["lean"], "gap": TILE["gap"]}
