# Marking the duty wheel — what lights up, when, and why

Working notes. **Nothing here is final.** Measured facts are separated from suggestions; where
something is my opinion rather than a reading, it says so.

Written while deciding *not* to put permanent arrows on the wheel, and the commit that files this
takes them out. The short version of that decision: the arrows were drawn between adjacent grid
squares, which is correct but nearly information-free, because six of the nine shapes have exactly
one successor. Everything a player can actually decide happens at three shapes. Marking those three
at the moment they matter carries more than eight permanent arrows ever did.

---

## 1. Connectivity is a property of the shapes, not the tiles

Duty tiles shuffle at setup. The **shapes do not move**, and the route runs over shapes. So nothing
about routing, marking, or sowing needs to know which duty is sitting where.

`configs/board.json` is the single source of truth:

```
city       -> north, south
north      -> north_east
north_east -> east
east       -> south_east, city
south_east -> south
south      -> south_west
south_west -> west
west       -> north_west, city
north_west -> north
```

Twelve directed edges. Eight ring steps clockwise, four City spokes.

### Where the player actually has a choice

| | branch shapes | most options at one shape |
|---|---|---|
| normal | `city`, `east`, `west` | 2 |
| with Kogge | `city`, `east`, `north`, `south`, `west` | **4** (at `city`) |

Kogge makes the City spokes passable both ways — `_board_with_kogge_city_spokes` adds `city→east`,
`city→west`, `north→city`, `south→city`. Ring direction is unchanged. **So "the two possible next
shapes" is only true in the base game.** Under Kogge the City offers four, and any mark or prompt
built around "pick one of two" will be wrong there.

### Cloisters is a different shape of choice

`cloisters_candidate_placements` generates routes of length **N+1** and then omits one placement
(`valid_cloisters_omissions`, restricted to the City or a non-city duty tile). So under Cloisters:

- the number of steps walked is one more than the acolytes in hand;
- there is a second kind of decision — *which visited shape to skip* — that is not a branch;
- a shape can be stepped through without receiving an acolyte.

Not traced further than that. Flagged because it breaks the assumption that steps and acolytes are
the same count, which an incremental sowing UI would otherwise bake in.

### Consequence for step-by-step sowing

Do **not** offer the next step from `board.neighbors()` alone. With modifiers in play a step can be
legal by connectivity and still appear in no legal complete route. The safe construction is to keep
the prefix walked so far and offer the next elements of the routes still matching it — same engine
call (`normal_sow_routes` / `kogge_sow_routes`), no new rules code, and the player cannot be offered
a move that strands them.

---

## 2. The one thing the 3×3 renderer will need

`ui/render/` has **no representation of board position at all**, and after the arrow removal it has
no representation of the topology either. The renderer thinks in two spaces: duty identity
(`DUTY_NAMES`) and grid square (`cells[duty]`).

The deleted `RING` and `CITY_ROUTES` encoded the topology in *grid* space with no names attached.
That is why arrows worked without anyone noticing the gap — adjacency is a property of the grid, so
`(5, 8)` was a correct arrow whatever sat in those squares. A mark is different: the sow happens in
engine position space, so something has to say which square is `east`.

That something is one tuple:

```python
CELL = {"north_west": 0, "north": 1, "north_east": 2,
        "west": 3, "city": 4, "east": 5,
        "south_west": 6, "south": 7, "south_east": 8}
```

**Verified against the arrow code before it was deleted**: pushing `configs/board.json` through
`CELL` produced exactly `RING + CITY_ROUTES` — all twelve edges, no residue in either direction. So
the hand-written copy was provably correct, and this tuple is a faithful record of it. Anything
built on `CELL` should derive its edges from `board.json` rather than write them down a second time;
that duplicate is what has just been deleted and it should not come back.

The previous UI already had this: `tools/ui_debug/duty_wheel_layout.json` carries `board_position`
on every tile alongside its centre. It is nine lines being ported, not a mapping being invented.

### The duty-arrangement disagreement, and what it does *not* affect

Four places in the repo answer "which duty sits at which position" and give four different answers
(`gen_duty_grid`, `pilgrim/model/duties.py`, `duty_wheel_layout.json`, `gen_board.py`). That is
**not a bug** — tiles shuffle, so there is no canonical arrangement and all four are declared
fixtures.

It has **no bearing on states (a) and (b) below**, which are pure position. It bears only on (c) and
on the action box, where "activate this duty" has to resolve the duty whose picture is showing —
and that is a question `eligible_tiles()` already lives with.

Separately: `configs/duties.json` — the one the rules load — has eight entries over a *different
vocabulary* (`produce` ×4, `clerical_devotion`, `clerical_silversmith` ×2, `give_alms`), not the
nine of `DUTY_NAMES`. Possibly a sandbox config. Unresolved, and I don't know which way it cuts.

---

## 3. The three states that need a border

| | (a) lift from | (b) sow onward | (c) activate |
|---|---|---|---|
| **question** | which shape do I pick up from? | which way does the sow continue? | which duty do I resolve? |
| **when** | start of the sow, at rest | mid-sow, interrupting an animation | after the sow, at rest |
| **which shapes** | active seat has ≥1 acolyte | legal next steps from the current shape | active seat has ≥1 acolyte |
| **how many** | up to 8 | 2 normally, up to 4 under Kogge | up to 8 (≈6 typical) |
| **where computed** | `eligible_tiles()` — exists | route prefixes — engine has it, not wired | `eligible_tiles()` — exists |
| **direction** | this shape is the **source** | this shape is the **destination** | this shape is the **object** |

(c) also carries a sub-choice inside the tile — one of the duty's actions, or the Tithe indicated by
the Tithe counter. Not specified here.

### The collision to design around

**(a) and (c) are computed by the same rule.** Both are "shapes where the active seat has at least
one acolyte" — literally the same function, seconds apart in one turn, asking opposite questions.
If they share a mark, the board alone cannot tell the player which question is being asked. Either
the marks differ, or a prompt line always states the question, or both.

### Suggested mark ladder — opinion, not a finding

Order the marks by **how much they need to interrupt**, not by which phase they belong to:

| state | mark | why |
|---|---|---|
| (b) sow onward | full animated portal ring | stops an animation; only 2–4 options; rarest event |
| (a) lift from | quieter animated mark — slow pulse or ants | a decision made at rest, already expected |
| (c) activate | solid | up to six at once; six portal rings is a lot of motion |

This is the a/b/c scheme with (a) and (b) pulled apart into a ladder of three rather than sharing
one effect.

### Green is a seat colour

Seats are green, blue, purple and grey. `MARK_FILL` is currently `#4BA672`. If the active player is
purple, a green border says "green" — and (a) and (c) are about *your own* acolytes, which is
exactly when the confusion costs something. Two ways out:

- the mark wears the **active seat's own colour**, so it always means *you* — elegant, but four
  palettes to tune against nine artworks, and the grey seat's mark may be invisible;
- a colour no seat owns — but gold is already `EDGE_HOVER` (`#d8b23a`).

Undecided.

---

## 4. Path previews on hover

A thin curved line from the current shape to a hovered destination, shown only while hovering.

Two notes. **Hover does not exist on touch**, so this cannot be the only thing carrying the
information. And the problem it solves — "where is the sow right now?" — has a cheaper answer that
works everywhere: mark the shape the sow is *currently on* with a distinct, non-clickable mark, for
the whole sow. Then two lit destinations read as "from here, to one of these" with no connecting
geometry at all.

If the line is still wanted after that, it can be crude. Transient geometry nobody studies does not
need the fitting a permanent arrow did, and it can cross tile outlines freely.

---

## 5. What exists, and what does not

**Exists.** The border effects and the studio to compare them (`gen_border_studio`, `MARK_CSS`,
`MARK_JS`, `mark_defs`, `mark_vars`, `mark_paths`, `MARK_EFFECTS`). `eligible_tiles()`, deriving the
(a)/(c) set from the counts already drawn. `cells=`, for drawing a real game's arrangement. The
route generator, Kogge and Cloisters variants included.

**Does not exist.** `CELL`, or any position→square mapping in the render layer. Any page passing
`cells=` — today only the guards do, so every page draws the identity arrangement. The sow state
machine. Any wiring between a marked tile and a click.

**Gone, deliberately.** `arrow`, `arrows_svg`, `_channel`, `_ray_hit`, `_inset`, every `ARROW_*`
constant, `RING`, `CITY_ROUTES`, and the `arrows=` parameter, along with their five guards. The
topology now lives only in `configs/board.json`, which is where it belongs.

---

## 6. Open questions

1. Mark colour versus seat colour — active seat's colour, or a fifth colour?
2. Does the (b) mark need to say *which* of the options is "onward" and which is "into the City",
   or is two lit shapes enough?
3. Under Kogge the City offers four onward shapes. Does that want a different treatment from a
   two-way branch?
4. Cloisters: how is "skip this one" chosen, and does the skipped shape need a mark of its own?
5. With no permanent arrows, the route is invisible on a still board. Does that want a help overlay,
   a first-play walkthrough, or nothing?
6. `configs/duties.json`'s eight entries over a different effect vocabulary.
