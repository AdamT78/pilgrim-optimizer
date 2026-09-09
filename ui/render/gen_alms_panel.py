"""The alms table as a parchment panel at ACTION BOX width.

316.4 x 132, drawn in the player board's own coordinate frame -- which renders at 0.9642, so
316.4 units come out as the action box's own 305 px and the two share a left and a right edge.
Keeping the frame rather than scaling the whole svg is what keeps the numerals at 13.5 px, the
size of the action box's body text, which is the rule the layout is built on. Seven columns for the 0-6 track plus a first-player column; the reward rows
(2, 4 and 6 in configs/alms.json) are shaded for the height of the dividers; four win
places sit in the title row over columns 4, 5, 6 and 1st.
"""

W = 316.4                     # 305 px at the panel's own 0.9642
# The panel stands as tall as the Buildings table: 136 px of INK. The Buildings frame is drawn
# inset by half its stroke so its stroke lands inside the 136; this rect is not, so its own 1.4
# comes off the height first. The extra all goes to the column band, since BOTY is measured up
# from the bottom.
# 143.68 px of ink now, not 136: the three panels at the head of the board grow UPWARDS until
# their top margin equals the 14 the action box leaves at the foot. The panel's own 1.4 stroke
# comes off first, since this rect sits on its edge rather than inside it.
AH = round((143.68 - 1.4 * 339.4 / 352.0) / (339.4 / 352.0), 1)   # 147.6
PAD = 12
CUBE = 11.96                  # the cube size the player boards already use
CUBE_CY = 21.0                # the win places keep their centre as the cube shrinks
SHADE = "#DCCFA8"
SLOT = "#D6C9A6"
DISC_R = 8.0                  # a player disc; the dashed slot is drawn at the same radius

# The two Ordination glyphs, kept HERE so the wheel and this table cannot drift apart -- mkR.py
# builds the duty tile's own icons from these same strings. A person moves one step along the
# chain and the icons differ only in which way the arrow points: out of the village toward the
# abbey, then into the city. Which is what the alms track pays at 2 and at 4 (configs/alms.json),
# so the reward spaces carry the picture of the thing they hand you.
ORD_SERF = ('<path d="M-8.5 7 V0 L-4.5-5 L-0.5 0 V7 Z"></path>'
            '<path d="M3 1 H8.5 M8.5 1 L6-1.5 M8.5 1 L6 3.5"></path>')
ORD_ACOLYTE = ('<path d="M2 7 V-1 L6-7 L10-1 V7 Z"></path><path d="M6-7 V-10"></path>'
               '<path d="M-9 1.5 H-2.5 M-2.5 1.5 L-5-1 M-2.5 1.5 L-5 4"></path>')
# measured, not converted: a duty tile draws these glyphs 1.338 px per drawing unit, and a unit
# of this frame draws 0.9642, so 1.388 here is the same picture at the same size
ORD_K, ORD_SW = 1.388, 1.2

X0 = PAD + 2
X1 = W - PAD - 2
NCOL = 8
CWID = (X1 - X0) / NCOL
TOPY = 50.0                   # was 42: +8 for the height the panel gained above it
BOTY = AH - PAD - 4
BANDY = TOPY + 20             # the column band: dividers, shading and discs all live here
SPECIAL = (2, 4, 6)


def _txt(x, y, s, size, anchor="start", fill="#2A2320", weight="700"):
    return ('<text x="%s" y="%s" font-size="%s" text-anchor="%s" fill="%s" font-weight="%s" '
            'font-family="Georgia,serif">%s</text>' % (x, y, size, anchor, fill, weight, s))


def _colx(i):
    return X0 + i * CWID


def panel(players, seat_colours, ink="#2A2320", parch="#E5D8B9",
          positions=None, wins=0, bold_special=False, win_seats=None):
    """Inner SVG markup. `players` is a list of dicts with a 'seat' key.

    `win_seats` names the seats holding the win places, filling from the LEFT (fourth from the
    right first); `wins` is the older count and still works, taking red.
    """
    positions = positions or {}
    won = list(win_seats) if win_seats else ["red"] * wins
    first_x = (_colx(7) + (W - 6)) / 2      # the first-player column is open on its right
    o = []
    o.append('<rect x="0" y="0" width="%s" height="%s" rx="12" fill="%s" stroke="%s" '
             'stroke-width="1.4"/>' % (W, AH, parch, ink))
    o.append('<rect x="6" y="6" width="%s" height="%s" rx="7" fill="none" stroke="%s" '
             'stroke-opacity=".30" stroke-width="1.1"/>' % (W - 12, AH - 12, ink))
    o.append(_txt(PAD + 4, 26, "Alms Table", 15, fill=ink))

    # The four win places are pinned at BOTH ends: the rightmost over the first-player column,
    # the third from the right over the 6 on the track. The pitch is then whatever halves the
    # span between those two, so the remaining pair lands on it without a figure of its own --
    # which is why this is a division and not a chosen number.
    anchor = _colx(6) + CWID / 2
    WIN_PITCH = (first_x - anchor) / 2.0
    centres = [anchor + (i - 1) * WIN_PITCH for i in range(4)]
    for i, cx in enumerate(centres):
        x, y = cx - CUBE / 2, CUBE_CY - CUBE / 2
        if i < len(won):
            fill, stroke = seat_colours[won[i]]
            o.append('<rect x="%.1f" y="%.1f" width="%s" height="%s" fill="%s" '
                     'stroke="%s" stroke-width="1.4"/>' % (x, y, CUBE, CUBE, fill, stroke))
        else:
            o.append('<rect x="%.1f" y="%.1f" width="%s" height="%s" fill="none" stroke="%s" '
                     'stroke-opacity=".55" stroke-width="1.1" stroke-dasharray="2.4 2.2"/>'
                     % (x, y, CUBE, CUBE, ink))

    # the reward rows are floored differently, behind everything else
    for i in SPECIAL:
        o.append('<rect x="%.1f" y="%s" width="%.1f" height="%.1f" fill="%s"/>'
                 % (_colx(i) + 1.5, BANDY, CWID - 3, BOTY - BANDY, SHADE))

    for i in range(1, NCOL):
        o.append('<path d="M%.1f %s V%s" stroke="%s" stroke-opacity=".22" stroke-width="1"/>'
                 % (_colx(i), BANDY, BOTY, ink))
    for i in range(7):
        cx = _colx(i) + CWID / 2
        big = bold_special and i in SPECIAL
        o.append(_txt(cx, TOPY + 10, str(i), 15 if big else 14, anchor="middle", fill=ink))
    o.append(_txt(first_x, TOPY + 10, "1st", 12.5, anchor="middle", fill=ink))

    # two rows in the band now: the discs ride high, the reward icons sit under them
    cy = BANDY + 18.6
    icon_cy = BOTY - 13.0
    o.append('<circle cx="%.1f" cy="%.1f" r="15" fill="none" stroke="%s" stroke-width="1.6"/>'
             % (first_x, cy, ink))
    o.append('<circle cx="%.1f" cy="%.1f" r="%s" fill="%s" stroke="%s" stroke-width="1.1" '
             'stroke-dasharray="3 2.6" opacity=".8"/>' % (first_x, cy, DISC_R, SLOT, ink))

    # what the track hands you at 2 and at 4, drawn as the duty tile draws it
    for col, glyph in ((2, ORD_SERF), (4, ORD_ACOLYTE)):
        o.append('<g transform="translate(%.1f %.1f) scale(%s)" fill="none" stroke="%s" '
                 'stroke-width="%s" stroke-linejoin="round" stroke-linecap="round">%s</g>'
                 % (_colx(col) + CWID / 2, icon_cy, ORD_K, ink, ORD_SW, glyph))

    by_col = {}
    for p in players:
        by_col.setdefault(positions.get(p["seat"], 0), []).append(p["seat"])
    for ci, seats in by_col.items():
        cx = _colx(ci) + CWID / 2
        for j, seat in enumerate(seats):
            fill, stroke = seat_colours[seat]
            dx = (-1 if j % 2 == 0 else 1) * 8.6
            dy = (-1 if j < 2 else 1) * 8.6
            if len(seats) == 1:
                dx = dy = 0
            o.append('<circle cx="%.1f" cy="%.1f" r="%s" fill="%s" stroke="%s" '
                     'stroke-width="1.3"/>' % (cx + dx, cy + dy, DISC_R, fill, stroke))
    return "".join(o)


def panel_svg(players, seat_colours, ink="#2A2320", parch="#E5D8B9", positions=None,
              wins=0, cls="alms", width=352, win_seats=None):
    """A standalone SVG in the player board's frame: viewBox -30 -8 352 x AH+12."""
    return ('<svg class="%s" viewBox="-30 -8 352 %s" width="%s" height="%s">%s</svg>'
            % (cls, AH + 12, width, (AH + 12) * width / 352.0,
               panel(players, seat_colours, ink, parch, positions, wins,
                     win_seats=win_seats)))
