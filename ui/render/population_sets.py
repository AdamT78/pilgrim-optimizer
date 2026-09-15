"""Every way this game draws people, and the numbers each surface needs to place them.

A SET is one population's artwork together with the metrics for laying it out. There are two
surfaces and they lay people out differently, so a set carries a block for each:

    tile    the duty wheel. One PILE per seat under each tile, growing upward, one figure per
            acolyte and no numeral -- see `gen_duty_grid.acolyte_row` for why a count is a heap
            rather than a number.
    board   the player card. One ROW per population along its own box, overlapped left to right
            -- the same idea turned on its side. See `gen_board_gothic.population_row`.

WHY THIS IS DATA AND NOT CODE. Both surfaces had their numbers as module constants, which is fine
for one way of drawing and useless for two: comparing a second figure meant editing the module
that draws the first, so the comparison could not be made without changing what it was being
compared against. The sets are a table; adding one is an entry, and the page that draws it takes
the name.

WHAT A SET MAY NOT DO. It carries no colours. A seat's colour is a property of the PLAYER, not of
how their people are drawn, so a set carrying its own would be a second answer to "what colour is
plum" -- and there are now two surfaces drawing seat-coloured figures that have to agree. The one
table lives below, and both of them read it.
"""

# The four seats, as the figures wear them. Here rather than in either module that draws them: the
# duty wheel duotones its photograph with these and the player card fills its hooded mark with
# them, and a wheel and a card disagreeing about plum is not a thing anyone would look for.
SEAT_SWATCH = {"sage": "#7d9b52", "pewter": "#4a6b86", "plum": "#8a5a92", "bone": "#A8A296"}
SEAT_ORDER = ("sage", "pewter", "plum", "bone")


# The hooded figure: a dome, a neck notch, shoulders, a flat base, drawn as a flat seat-coloured
# mark rather than as a duotoned photograph. Traced from Adam's mock-up: the outline is a
# parametric shape fitted to it with the three landmarks PINNED rather than fitted --
#
#     the dome's widest half-width   0.300 of the figure's width, at 0.300 down
#     the neck notch                 0.2143, at 0.686 down
#     the shoulder reaching full     width by 1.086 down
#
# -- because an area fit traded the neck away. The notch is a handful of pixels and it is the whole
# read: without it the shape is a pawn. Pinned, the fit scores 0.978 against the mock-up's own
# silhouette; free, it scored 0.964 AND lost the neck, which is the case for measuring landmarks
# rather than trusting an objective.
#
# Coordinates are fractions of the figure's WIDTH, x from its centre and y from its crown, so the
# shape scales with one number and the 1.2 below is its height in those units.
HOOD_H = 1.2                  # height, in width units -- so the aspect w/h is 1/1.2 = 0.8333
# The darker face inside the hood, same units. Not decoration: in a pile every buried figure shows
# only its top STACK_STEP of height, and the face is what makes that band read as another person
# rather than as the same silhouette continuing.
HOOD_FACE = {"cy": 0.336, "rx": 0.207, "ry": 0.2424}

HOOD_SHAPE = tuple(
    tuple(float(v) for v in pair.split(","))
    for pair in (
        "0.0000,0.0000 0.0413,0.0029 0.0817,0.0114 0.1206,0.0253 0.1573,0.0445 0.1909,0.0686 "
        "0.2209,0.0970 0.2467,0.1294 0.2679,0.1649 0.2839,0.2030 0.2945,0.2430 0.2996,0.2840 "
        "0.2989,0.3254 0.2927,0.3663 0.2973,0.4074 0.2975,0.4487 0.2933,0.4899 0.2850,0.5304 "
        "0.2729,0.5700 0.2573,0.6083 0.2388,0.6453 0.2176,0.6809 0.2423,0.7074 0.2745,0.7335 "
        "0.3057,0.7606 0.3358,0.7890 0.3647,0.8187 0.3920,0.8498 0.4174,0.8825 0.4404,0.9168 "
        "0.4607,0.9529 0.4775,0.9907 0.4902,1.0301 0.4983,1.0706 0.5000,1.1119 0.5000,1.1533 "
        "0.4964,1.1939 0.4569,1.2000 0.4156,1.2000 0.3742,1.2000 0.3328,1.2000 0.2914,1.2000 "
        "0.2500,1.2000 0.2086,1.2000 0.1672,1.2000 0.1259,1.2000 0.0845,1.2000 0.0431,1.2000 "
        "0.0017,1.2000 -0.0397,1.2000 -0.0811,1.2000 -0.1225,1.2000 -0.1639,1.2000 -0.2052,1.2000 "
        "-0.2466,1.2000 -0.2880,1.2000 -0.3294,1.2000 -0.3708,1.2000 -0.4122,1.2000 -0.4536,1.2000 "
        "-0.4941,1.1963 -0.5000,1.1567 -0.5000,1.1153 -0.4987,1.0740 -0.4911,1.0333 -0.4787,0.9939 "
        "-0.4622,0.9559 -0.4422,0.9197 -0.4193,0.8852 -0.3941,0.8524 -0.3670,0.8212 -0.3383,0.7914 "
        "-0.3082,0.7629 -0.2771,0.7357 -0.2450,0.7095 -0.2158,0.6837 -0.2371,0.6483 -0.2559,0.6114 "
        "-0.2717,0.5732 -0.2842,0.5337 -0.2928,0.4932 -0.2973,0.4521 -0.2974,0.4107 -0.2933,0.3696 "
        "-0.2986,0.3287 -0.2997,0.2874 -0.2952,0.2463 -0.2850,0.2062 -0.2694,0.1679 -0.2486,0.1321 "
        "-0.2232,0.0995 -0.1935,0.0708 -0.1601,0.0463 -0.1237,0.0267 -0.0850,0.0123 -0.0446,0.0033"
    ).split()
)


# -- the sets ------------------------------------------------------------------------------------
#
# `tile` metrics, all fractions:
#
#   aspect    the figure's own width / height
#   frac      figure width as a fraction of the TILE's width
#   overlap   how much of the figure sits above the tile's bottom edge
#   gap       between one seat's pile and the next, as a fraction of a figure's width
#   step      between one acolyte and the one resting on it, as a fraction of a figure's HEIGHT
#   lean      alternating side to side, as a fraction of a figure's width
#
# `board` metrics:
#
#   step      overlap between consecutive figures, as a fraction of a figure's width
#   pad       clear ground kept at each end of a box, in card units
#   align     where a short row sits in its box
#
# The board block does NOT name artwork. Both sets draw the card's own serf and acolyte, and the
# template owns their size -- `population_figure_frame` reads it off the very <image> the row
# replaces, so a constant here would be a second statement of it. A set that wanted different
# artwork on the card would add a key; nothing today does.

_GOTHIC_ASPECT = 228 / 210.0          # the asset is 228 x 210 -- WIDER than tall
_GOTHIC_FRAC = 0.205
# The hood is sized to the same drawn HEIGHT as the figure it replaces, and derived rather than
# typed so the two cannot drift. THIS IS THE WHOLE SIZING ARGUMENT: the channel between two rows
# of tiles constrains height, not width, and every number in `gen_duty_grid`'s clipping table --
# where a pile starts costing tile art, where it clips the box at 16 -- is a statement about
# height. Matching the height keeps that table true for both sets. The cost is that the hood comes
# out NARROWER than the figure, because it is the taller shape: 0.8333 against 1.0857.
_HOOD_FRAC = (_GOTHIC_FRAC / _GOTHIC_ASPECT) / HOOD_H

SETS = {
    "gothic": {
        "label": "gothic figure",
        "tile": {"kind": "image", "aspect": _GOTHIC_ASPECT, "frac": _GOTHIC_FRAC,
                 "overlap": 0.60, "gap": 0.24, "step": 0.30, "lean": 0.10},
        # The card draws the config's own PNG, which is the same file the wheel duotones.
        "card": {"kind": "image"},
    },
    "hood": {
        "label": "hooded mark",
        "tile": {"kind": "hood", "aspect": 1.0 / HOOD_H, "frac": _HOOD_FRAC,
                 "overlap": 0.60, "gap": 0.24, "step": 0.30, "lean": 0.10},
        # On the card the mark is drawn rather than placed, so it brings its own aspect: the row's
        # figure WIDTH is derived from it and the template's height, instead of both coming from
        # the <image> the row replaces. Keeping the height is what keeps the band's vertical
        # arrangement -- which the template owns and this does not touch.
        "card": {"kind": "hood", "aspect": 1.0 / HOOD_H},
    },
}
# TWO NAMES, AND THEY ARE NOT THE SAME QUESTION.
#
#   DEFAULT   what `duty_grid_svg` draws when a caller asks for nothing. It stays on the
#             gothic figure so every page that never passed a set -- the pickers, the
#             layout tool, every guard written before sets existed -- draws exactly what
#             it drew before, byte for byte. Changing this changes pages nobody asked to
#             change.
#   WHEEL     what the duty wheel SHOWS in the game. The decision, in one place, read by
#             `gen_game_view` (which draws it) and by `gen_tile_offsets` (which opens on
#             it, because a tool judging offsets against a row the board no longer draws
#             is judging against the wrong thing).
DEFAULT = "gothic"
WHEEL = "hood"
# What the PLAYER CARD draws. Separate from WHEEL because they are separate decisions -- the card
# pairs its acolyte row with a serf row and the wheel does not -- even while both say "hood".
CARD = "hood"

# -- the card's rows -----------------------------------------------------------------------------
#
# A SEPARATE TABLE, and the separation is the point. The two surfaces do not vary along the same
# axis: the duty tile varies by ARTWORK -- which figure is drawn -- while the card varies by
# PLACEMENT, because both populations there are drawn from the template's own <image> and the
# template owns their size. Folding them into one table would mean every card preset carrying a
# tile block it does not use, and every figure set carrying a placement it has no opinion about.
#
#   step    overlap between consecutive figures, as a fraction of a figure's width
#   pad     clear ground kept at each end of a box, in card units
#   align   where a SHORT row sits in its box. A row that fills its box lands in the same place
#           under all three, so this is only ever visible at low counts -- which is most of them.
#
# The card's serf and acolyte keep the gothic artwork whichever of these is chosen. The hooded
# mark is not offered here: the band pairs a serf row with an acolyte row, the mock-up has no
# serf, and a flat mark beside a photograph is not one design. When a serf hood exists it becomes
# a figure set like the two above and this table does not change.
BOARD_SETS = {
    "centred": {"label": "centred, 0.30", "step": 0.30, "pad": 20.0, "align": "centre"},
    "tight":   {"label": "tight, 0.22",   "step": 0.22, "pad": 20.0, "align": "centre"},
    "loose":   {"label": "loose, 0.42",   "step": 0.42, "pad": 20.0, "align": "centre"},
    "left":    {"label": "left, 0.30",    "step": 0.30, "pad": 20.0, "align": "left"},
    "right":   {"label": "right, 0.30",   "step": 0.30, "pad": 20.0, "align": "right"},
}
BOARD_DEFAULT = "centred"


def get(name: str | None = None) -> dict:
    """One set, by name, or the default. Raises rather than falling back.

    A silent fallback is the failure this whole table exists to make impossible: a page asking for
    a set that does not exist would draw the other one and look entirely correct.
    """
    name = DEFAULT if name is None else name
    if name not in SETS:
        raise ValueError(
            "no population set %r; there are %s. A set is a table entry in population_sets.py, "
            "not a string the caller invents." % (name, ", ".join(sorted(SETS))))
    return SETS[name]


def tile(name: str | None = None) -> dict:
    """The duty-wheel metrics of one set."""
    return get(name)["tile"]


def card(name: str | None = None) -> dict:
    """How one set draws a figure on the player card."""
    return get(name)["card"]


def board(name: str | None = None) -> dict:
    """One card-row preset, by name, or the default. Raises rather than falling back."""
    name = BOARD_DEFAULT if name is None else name
    if name not in BOARD_SETS:
        raise ValueError(
            "no card row set %r; there are %s. These are placement presets, not figure sets -- "
            "see the note above BOARD_SETS." % (name, ", ".join(sorted(BOARD_SETS))))
    return BOARD_SETS[name]


def hood_path(nd: int = 4) -> str:
    """The hood outline as an SVG `d`, one unit wide, crown at y=0."""
    f = "%%.%df" % nd
    pts = HOOD_SHAPE
    return ("M" + "L".join((f + " " + f) % p for p in pts) + "Z")
