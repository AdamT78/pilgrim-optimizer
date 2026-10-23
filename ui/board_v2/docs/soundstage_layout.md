# Where each sound sits in the field

One table per duty action, recording **where every bed is placed left to right** and **how that
placement was made**. It did not exist until 2026-10-18 and the first table in it was written by
measuring a scene nobody had specified — which is the reason it exists.

**This file is updated when beds are filed, not when they are requested.** A table that says
*prescribed* after its delivery has landed is worse than no table: it reads as an open job and it
contradicts the tree. The status line below is the one place to check, and it moves at filing.

| action | beds | layout status |
|---|---:|---|
| `produce_actionB` — Produce Stone | 17 | **descriptive** — measured after the fact, never prescribed |
| `produce_actionA` — Produce Wheat | 13 | **delivered and filed**, all thirteen placements landed |
| `allocation_actionA` — Allocation | 14 | **descriptive** — measured after the rebuild by journey |
| `build_roads_actionA` — Build Roads | 11 | **delivered and filed**; re-read against v02 artwork 2026-10-23 |
| `build_roads_actionB` — Build Shrine | 7 | **delivered and filed** after two rounds |
| `clerical_actionA` — Devotion | 6 | **delivered and filed** |
| `taxation_actionA` — Taxation | 9 | **delivered and filed** 2026-10-20; every placement landed, two widths could not |
| `clerical_actionB` — Silversmith | 12 | **delivered and filed** 2026-10-23 |
| `ordination_actionB` — Send on Mission | 10 | **delivered and filed** 2026-10-23; nine re-panned, `night_city`'s fold declared out of limit |
| the other two sounded actions | 2 | no table yet |

*A hundred and one beds in eleven folders; nine of the eleven have a table here.*

## Why this file

Produce Stone turned out to have a coherent soundstage: the lamp and the stonecutter to the left,
the haul and the hoist to the right, the wind and the workers filling the centre, and the moth
circling the lamp it is named after. **Nobody designed that.** The supplier made those choices
while building the scene, and across every Produce Stone delivery document only two placements
are ever stated — the hoist "right-of-centre" and the foreground's "fixed position". The rest was
discovered here by measuring the shipped files.

That worked once and is not a process. Produce Wheat was built the same way and came out with its
foreground worker split across both sides, four of its six placed sources crowded left, and one
bird 12.4 dB right. The difference between the two scenes is luck, not method.

So placement joins the delivery contract: an action's layout is **stated before the stems are
built**, and this file is where the agreed layout and the measured result are kept side by side.

## How the numbers are taken

**Balance** is `10·log10(Eʟ / Eʀ)` over the whole bed — positive is left. It says where the
energy sits, not where a listener points: a bed at +4.0 dB reads as clearly left of centre, +7 dB
as well out to the side, and anything past about ±6 dB starts paying for it in the mono fold.

**Width** is `10·log10(E_side / E_mid)` over the whole stem: how much space the source takes
up, as distinct from where it sits. **A placed source is not a point.** Every bed in Produce
Stone, including the ones that are plainly single objects, carries width between −4.7 and
−13.6 dB — a lamp has a flame around it, a stonecutter has a room. A width near −25 dB or
beyond means a mono recording was panned and nothing else was done, which gives a direction with
no size and is almost never what a scene wants. Produce Wheat v2 delivered its four foreground
stems at exactly −26.74 dB for that reason: the table said *placed* and said nothing about size,
so they were panned and left dimensionless.

**Width is taken with the pan removed, and that changed on 2026-10-18.** Panning a source
*creates* side energy, so the figure above is partly a statement about where a source is rather
than about how big it is — and on anything placed past about 4 dB the pan dominates it. Scale one
channel so the two carry equal energy, then measure: that number belongs to the source and
cannot conflict with a balance target.

Two things forced the change, both on Build Roads. **A pan imposes a floor that no narrowing can
get under** — for balance *B* with `r = 10^(B/20)`, side/mid cannot go below
`20·log10((r−1)/(r+1))`, which at 6.5 dB is **−8.93 dB** — so a row of that table asked for a
width that does not exist at the balance beside it. And **four beds hit their stated width target
while having almost none**: they measured −10 to −12 dB and were −15 to −32 dB once de-panned.

*The two figures are both worth having and the difference between them is the pan.* **Build Roads,
Build Shrine and Devotion carry both.** Produce Stone, Produce Wheat and Allocation were written
before the change and their width columns are **as filed** — so on every placed source in those
three, most of the number is pan. Produce Wheat is the worked example: its thirteen beds hit their
as-filed widths and only the three centre fields have any real size, the ten placed sources running
**−20.7 to −34.7 dB de-panned**. Re-measured 2026-10-19.

**And the figure that governs is the one the shipped `.ogg` measures, not the master.** Vorbis q6
adds decorrelated quantisation noise straight into the side channel, so an encode is always a
little wider than the WAV it came from — 0.82 dB on Devotion's `robe_movement`, enough on its
`wood_cracks` to take a band over the fold limit the master cleared. Every width in this file is
taken on the `.ogg`.

**Construction** is the least-squares fit of side against mid, reported as the percentage of side
energy the fit cannot explain:

- **under ~35% unexplained** — the side signal is largely a scaled copy of mid, so this is one
  sound amplitude-panned to a position. Correct for a point source: a bird, a lamp, one machine,
  one tool in one place.
- **near 100% unexplained** — the channels carry genuinely different material. This is a field
  rather than a point, and it has no single position; it occupies width.

The two are not better and worse. They are answers to different questions, and the fault is
using one where the scene wants the other — a crowd of workers panned to a point, or a single
owl smeared across the horizon.

**Nothing past ±6 dB without a reason.** A hard pan costs mono fold: the owl below is panned far
enough to lose **1.28 dB** summed to mono, which is the price of having it clearly off in the dark.
*Re-measured on the shipped `.ogg` on 2026-10-19; this figure and the one below read 1.38 until
then, and the tree-wide fold sweep that day disagreed with both.*

---

## `produce_actionB` — Produce Stone

Seventeen beds, measured 2026-10-18 on the shipped `.ogg` files after v17.
**Descriptive, not prescribed** — this is what arrived, written down after the fact.

| bed | balance | width | motion | construction | what it is |
|---|---:|---:|---|---|---|
| `oil_lamp_rattle_sfx_v01` | 7.3 dB L | -7.9 dB | static | placed, 2.5% | the lamp's mechanical rattles |
| `moth_sfx_v01` | 6.9 dB L | -8.1 dB | static | placed, 5.4% | moth circling that same lamp |
| `oil_lamp_flame_sfx_v01` | 5.5 dB L | -9.7 dB | static | placed, 9.3% | the lamp at the cutting face, continuous |
| `debris_cleave_sfx_v03` | 4.0 dB L | -11.0 dB | static | placed, 32.0% | the stone splitting |
| `power_strikes_sfx_v02` | 4.0 dB L | -10.8 dB | static | placed, 34.3% | the stonecutter's heavy blows |
| `chisel_reposition_sfx_v02` | 4.0 dB L | -10.9 dB | static | placed, 33.1% | the tool reset between blows |
| `quarry_footsteps_sfx_v01` | 2.7 dB L | -10.9 dB | static | field, 68.5% | foot traffic across the workings |
| `quarry_wind_sfx_v02` | centre | -7.5 dB | static | field, 100% | the continuous bed |
| `background_worker_a_sfx_v01` | centre | -7.0 dB | static | field, 100% | nearest of five, continuous |
| `background_worker_b_sfx_v01` | centre | -8.5 dB | static | field, 100% | second |
| `background_worker_c_sfx_v01` | centre | -10.0 dB | static | field, 100% | third |
| `background_worker_d_sfx_v01` | centre | -11.5 dB | static | field, 100% | fourth |
| `background_worker_e_sfx_v01` | centre | -12.4 dB | static | field, 100% | farthest |
| `quarry_hoist_sfx_v02` | 2.9 dB R | -13.6 dB | static | placed, 33.7% | rope and pulley behind |
| `sleigh_crew_footsteps_sfx_v01` | 5.7 dB R | -9.7 dB | static | placed, 5.0% | the haul crew |
| `stone_sleigh_sfx_v01` | 5.9 dB R | -8.1 dB | static | placed, 25.0% | the loaded sleigh dragging |
| `distant_owl_sfx_v01` | 11.0 dB R | -4.7 dB | static | placed, 4.6% | one call, off in the dark |

Whole-scene balance is **+0.63 dB**, so the field is even overall.

### What this layout gets right

**The lamp cluster holds together.** Flame, rattle and moth sit at 5.5, 7.3 and 6.9 dB left — the
moth is where it is because it is circling a lamp that is there. The stem is named
`moth_near_oil_lamp` and the placement agrees with the name, which is not something that happens
by accident.

**The foreground shares one exact position.** Power strikes, debris cleave and chisel
repositioning all measure 4.0 dB left, all three at 32–34% unexplained. That is one stonecutter
standing in one place, and it survived the stem being rebuilt twice: v15 put the room there, v17
restored a different event inside it, and the position did not drift.

**The haul is a separate place.** Sleigh and crew at 5.7 and 5.9 dB right, hoist at 2.9 — work
happening somewhere other than where the player's own worker is.

**Centre is reserved for what has no position.** The wind and the five workers are the only beds
at 0.0 dB, and all six are fully decorrelated. Nothing is panned to the centre; the centre is
what is everywhere.

### Two things it gets wrong

**The five background workers are at exactly 0.00 dB — all five.** Their distance is carried by
level (−19.8 to −27.0 dBTP) and by width (−7.0 to −12.5 dB side/mid) but not by position, so five
workers at five distances are stacked in one spot. The width ladder does a lot of the work and
the result is not bad, but a quarry would fan them out. Worth fixing whenever that action is
next open; it needs no rebuild, only a re-pan.

**The owl at 11.0 dB right is still the hardest pan in the tree** — re-checked across all
eighty-five beds on 2026-10-19, with Allocation's reader next at 7.7 dB — and it loses **1.28 dB**
folded to mono, in a band carrying **99.6%** of it. It is the fifth-worst fold in the tree and the
worst whose failing band is the whole file rather than a corner of the spectrum.
Defensible for something meant to be at the edge of the scene, and it is the only bed out there,
so it does not crowd anything. It is recorded here as a deliberate outlier rather than left to
look like an error.

---

## `produce_actionA` — Produce Wheat

**PRESCRIBED, DELIVERED AND FILED.** Read off the action's own artwork,
`duty_actions/produce/gain_wheat/produce_gain_wheat_left_v01.png`, on 2026-10-18, and delivered
as **thirteen beds** where there had been eight. **Every one of the thirteen placements landed**,
within 0.03 dB on twelve of them — re-measured on the shipped `.ogg` files on 2026-10-19. What the
eight beds measured before is kept at the end of the section.

*The width half of the table did not land, and it took the de-panned convention to see that.*
See below the table.

### What the picture puts where

An old woman kneels centre-left, binding a sheaf with both hands at about **55%** across the
frame. Her sickle lies on the ground to her lower left. Three or four bent cutters work the far
left edge between **3% and 27%**. A fence crosses the right half with a hooded figure at **88%**
and **a raven perched on it at 96%**. A cathedral silhouette sits in the left background around
**18%**; the sunset glows right of centre. Stubble fills the whole frame.

Horizontal position in frame sets the pan: `balance_dB = (50 − x%) / 50 × 8`, positive left.
Apparent distance sets level and width, never pan. Anything not in the picture is free, and
centre is reserved for what is everywhere.

| stem, as filed | read at | asked | **delivered** | width asked | as filed | **de-panned** | construction |
|---|---:|---:|---:|---:|---:|---:|---|
| `wind_sfx_v02` | — | centre | **0.00** | −7.5 dB | −7.51 | **−7.51** | field, continuous |
| `field_rustle_sfx_v02` | whole frame | centre | **0.14 R** | −7.0 dB | −7.24 | **−7.24** | field |
| `stalk_brushing_sfx_v02` | whole frame | centre | **0.03 R** | −7.5 dB | −6.93 | **−6.93** | **field** — was a point at 6.9 dB L |
| `sheaf_handling_sfx_v02` | 55% | 0.8 dB R | **0.81 R** | −10 to −12 | −19.87 | −20.91 | placed, a point |
| `sheaf_settling_sfx_v01` | 55% | 0.8 dB R | **0.82 R** | −10 to −12 | −20.15 | −21.27 | placed, a point |
| `worker_repositioning_sfx_v01` | 55% | 0.8 dB R | **0.77 R** | −10 to −12 | −23.63 | −26.23 | placed, a point |
| `straw_binding_close_sfx_v01` | 55% | 0.8 dB R | **0.80 R** | −10 to −12 | −20.22 | −21.30 | placed, a point |
| `worker_a_sickle_sfx_v01` | 7% | 6.9 dB L | **6.89 L** | −8.5 dB | −8.29 | −21.97 | placed, a point |
| `worker_a_straw_sfx_v01` | 14% | 5.8 dB L | **5.81 L** | −9.8 dB | −9.49 | −20.69 | placed, a point |
| `distant_rooster_sfx_v02` | 18% | 6.0 dB L | **6.01 L** | −9.6 dB | −9.55 | −34.66 | placed, a point |
| `worker_b_sickle_sfx_v01` | 20% | 4.8 dB L | **4.77 L** | −11.4 dB | −11.08 | −22.09 | placed, a point |
| `worker_b_straw_sfx_v01` | 25% | 4.0 dB L | **4.01 L** | −12.9 dB | −12.22 | −20.68 | placed, a point |
| `nearby_raven_sfx_v02` | 96% | 7.4 dB R | **7.39 R** | −7.9 dB | −7.83 | −24.47 | placed, a point |

*The filed names are not the names this table was written with*: the cutters were asked for as
`sickle_worker_a` and came back as `worker_a_sickle`, and so on for the other three. Harmless, and
recorded because a table that names files has to name the files that exist.

### Every placement landed and not one width did

**Ten of the thirteen are panned mono.** They run **−20.7 to −34.7 dB de-panned** — a direction
with no size — while reading −8.3 to −23.6 as filed, which is how they passed. Only the three
centre fields have any real width, and they have it because a bed at centre has no pan for the
as-filed figure to borrow from.

*This is the same failure Build Roads had, found the same way and one day later.* The width column
was written before the de-panned convention existed, so it asked for as-filed numbers; the delivery
met them exactly, at every row; and the numbers were the wrong numbers. The woman's four stems were
flagged at the time for coming back at −26.74 dB, which is right, and the reason given was that
their target had been omitted — but **the nine that did have targets are in the same state**, and
nothing flagged them because they hit the figure as written.

**So Produce Wheat is the largest outstanding width job in the tree**, ten beds of it, and it is a
request rather than a defect in the delivery. Produce Stone's foreground sits at −10.8 to −11.0 dB
of real width and is the model.

### And its three centre fields are the three beds that fail the fold limit

`field_rustle` folds **−1.061 dB** at 2 kHz, `stalk_brushing` **−1.035** at 8 kHz and `wind`
**−1.014** at 250 Hz. **None of that is pan** — all three sit at centre, so there is nothing to
subtract. It is intrinsic width in one band of each: broadband they read −6.9 to −7.5, inside the
−5.87 dB no-pan ceiling, and the ceiling applies **band by band**. Three of the fourteen beds over
the 1 dB limit tree-wide are these three.

### Three things this table decides

**The woman's four stems share one position exactly.** She is one person; her binding, her
settling gesture, her repositioning and the close straw detail are all her hands at 55%. Before the
rebuild they were at 1.6 dB right, 3.8 dB left and 4.7 dB left, because three of them had been
merged into a stem with the background workers and inherited its pan. **All four now sit between
0.77 and 0.82 dB right**, which is as close to one position as four separate files get.

**The field work really is all on the left, and that is the picture's doing, not an error.** The
right half of the frame holds fence, sky, a standing figure and a bird; no labour happens there.
A review that had not opened the artwork called this crowding and was wrong. The scene is
asymmetric by design and the intermittent events follow it; whole-scene balance stays even
because the wind and the rustle dominate the energy and sit centre.

**The raven came in from 12.4 dB to 7.4 dB, and did.** The picture earns it the right-hand edge —
it is the only placed source over there — but 12.4 dB was further out than the frame justifies and
cost **1.38 dB** of mono fold as it then stood. It was delivered at **7.39 dB right**, folding
**0.66 dB**, inside the limit and still plainly the rightmost thing in the scene.

### What the eight beds measured before, which is the argument for the table

Taken on the shipped `.ogg` files on 2026-10-18, before the rebuild, including the elements buried
inside the two combined stems. **None of these files is in the tree any more.**

| element | lives in | balance | construction |
|---|---|---:|---|
| sickle worker A | `sickle_cutting_sfx_v02` | 8.0 dB L | placed, ~3% |
| straw worker A | `straw_workers_sfx_v01` | 8.0 dB L | placed, ~3% |
| stalk brushing | `stalk_brushing_sfx_v01` | 6.9 dB L | placed, 7.3% |
| worker repositioning | `sickle_cutting_sfx_v02` | 4.7 dB L | partial, 36.6% |
| sickle worker B | `sickle_cutting_sfx_v02` | 4.6 dB L | placed, ~5% |
| straw worker B | `straw_workers_sfx_v01` | 4.6 dB L | placed, ~8% |
| sheaf settling | `sickle_cutting_sfx_v02` | 3.8 dB L | partial, 52.8% |
| distant rooster | `distant_rooster_sfx_v01` | 2.8 dB L | placed, 1.2% |
| wind | `wind_sfx_v01` | centre | field, 99.7% |
| field rustle | `field_rustle_sfx_v01` | centre | field, 99.9% |
| straw binding, close | `straw_workers_sfx_v01` | centre | field, ~98% |
| sheaf handling | `sheaf_handling_sfx_v01` | 1.6 dB R | partial, 49.8% |
| nearby raven | `nearby_raven_sfx_v01` | 12.4 dB R | placed, 0.5% |

**The two merged stems reused exactly two pan slots between them** — +8.0 and +4.6 dB each appeared
twice, so four different people stood in two places. That was the clearest argument for the split
after the fader argument: a merge forces shared positions as well as a shared gain. *The split was
made and the thirteen beds above are the result* — the four people now stand at 6.89, 5.81, 4.77
and 4.01 dB left, four positions for four people.

---

## `allocation_actionA` — Allocation

Fourteen beds, measured 2026-10-18 on the shipped `.ogg` files, after the action was rebuilt
twice in one day: fifteen stems filed **by sound type**, then fourteen filed **by journey**.
This is the first action in the tree where a stem is a *person* rather than a *kind of sound*,
and the table below is the first one here with a motion column that is not all `static`.

**The scene, stated at last.** Five monks wait in a row near the camera. Each in turn takes two
steps forward, receives a key from the almoner on the left, and leaves — one right through a
door, one left through a door, one two steps back and up the wooden stairs, one right through a
third door, and one forward-right and down the stone stairs. A reader turns pages twice in the
background right and shifts once; a torch burns on the left wall; a mouse crosses at the far
left. Nothing in the first fifteen stems recorded any of this, because nobody had written it
down.

**THE ARTWORK WAS REGENERATED ON 2026-10-20 AND NOTHING IN THIS TABLE MOVES.**
`allocation_relocate_acolytes_left_v02.png` replaces v01 to fix the keys — the old ring carried
five or six tangled across two interlocking rings, several of them malformed, where the new one
carries three cleanly drawn. Measured against a grid the composition is v01's to within about a
percent, and every element a bed depends on sits where it sat. The one real move is the torch:
its flame is larger and its centre is **2.1% further left**, which is 0.34 dB through the layout
formula, against `torch_base` and `torch_gust` that already sat about 0.7 dB right of it in v01.
*This table is descriptive and that is why none of this needs acting on* — the figures were
measured off the shipped `.ogg` files after the rebuild by journey, not read off the picture, so
the artwork moving does not make any of them wrong.

**The new ring agrees with the five journeys better than the old one did, by accident.** The
scene above says five monks each receive a key, and `key_handoffs_sfx_v02` is five keys changing
hands. Count what is in the picture now: three on the ring, one in the almoner's hand mid-pass,
one already held by the monk at the right edge. Five. v01 showed seven or eight, and nobody
noticed — this file describes what the beds do rather than auditing what the picture shows, and
the two had quietly disagreed since the day the scene was written down.

| bed | balance | width | motion | construction | what it is |
|---|---:|---:|---|---|---|
| `mouse_scurry_out_sfx_v02` | 7.5 dB L | -7.2 dB | static | placed | the mouse leaving |
| `mouse_scurry_in_sfx_v02` | 7.2 dB L | -7.1 dB | static | placed | the mouse arriving |
| `mouse_squeak_sfx_v01` | 7.1 dB L | -8.1 dB | static | placed | its one vocalisation |
| `key_handoffs_sfx_v02` | 1.8 dB L | -9.8 dB | static | placed | five keys changing hands |
| `torch_base_sfx_v02` | 1.2 dB L | -7.5 dB | static | field | the wall torch, continuous |
| `torch_gust_sfx_v01` | 0.7 dB L | -7.5 dB | static | field | its flares, continuous |
| `allocation_wind_sfx_v03` | centre | -7.0 dB | static | field | the interior howl, continuous |
| `monk_02_left_door_sfx_v01` | 0.6 dB L | -11.8 dB | **4.5 R → 8.0 L** | placed, travelling | the second monk's whole journey |
| `monk_03_back_wood_stairs_sfx_v01` | 1.1 dB R | -17.3 dB | **5.5 R → 0.8 R, then -11.6 dB** | placed, receding | the third monk's, up the wooden stairs |
| `monk_05_near_stone_stairs_sfx_v01` | 2.7 dB R | -15.2 dB | **4.0 R → 0.8 R → 4.0 R, +4.4 dB** | placed, approaching | the fifth monk's, down the stone stairs |
| `monk_04_right_door_sfx_v01` | 2.9 dB R | -13.8 dB | **5.0 R → 5.5 R** | placed, travelling | the fourth monk's whole journey |
| `monk_01_right_door_sfx_v01` | 3.0 dB R | -13.7 dB | **3.5 R → 8.0 R** | placed, travelling | the first monk's whole journey |
| `page_turns_sfx_v01` | 7.3 dB R | -7.1 dB | static | placed | the reader in the alcove |
| `reader_reposition_sfx_v01` | 7.7 dB R | -7.5 dB | static | placed | the reader shifting |

**A travelling stem's balance figure is the average of a path and means very little on its own**,
which is why the motion column carries the real information for the five monks. `monk_02` reads
0.6 dB left over the whole stem and is never at 0.6 dB left at any moment in it: it starts at
4.5 right and ends at 8.0 left.

### The five journeys, event by event

Each monk is one stem that is mostly silence, beginning and ending in silence, so none of them
has a loop seam to join. Measured in runs separated by 250 ms or more:

| | waits at | steps forward to | then | arrives | lock | door or stair |
|---|---:|---:|---|---:|---:|---:|
| `monk_01` | 3.5 R | 0.8 R | five steps right | 5.5 R | **7.5 R** | **8.0 R** |
| `monk_02` | 4.5 R | 0.8 R | five steps left, across centre | 5.8 L | **8.0 L** | **8.0 L**, one run |
| `monk_03` | 5.5 R | 0.8 R | two steps back, pan held | 0.8 R | — | **centre, 3.5 s climb** |
| `monk_04` | 5.0 R | 0.8 R | five steps right | 4.3 R | **5.4 R** | **5.5 R** |
| `monk_05` | 4.0 R | 0.8 R | forward and right | 4.0 R | — | **4.0 R, 3.8 s descent** |

**The three kinds of movement are different and all three are here.** Monks 1, 2 and 4 leave
sideways: the pan carries them off while the level falls and the stem narrows. Monk 3 leaves
*backwards* — his level falls 11.6 dB across the climb and **his pan does not change at all**,
because walking away from the camera is a change of distance, not of direction. Monk 5 is the
only one who gets louder, rising 4.4 dB as he comes toward the camera before dropping out of
sight down the stone stairs.

**Neither staircase pans.** A staircase is a fixed object and the monk on it barely moves
sideways; what says *up* or *down* is the material — footfall spacing, effort, the way a descent
runs away from you and a climb labours. Monk 3's climb holds centre to within 0.4 dB over 3.5 s
and monk 5's descent holds 4.0 dB right to within 0.00 dB over eight further footfalls.

**A monk, his lock and his door now agree.** They did not in the first delivery of this
structure: monk 2 walked to 8.0 dB left, unlocked a door 3 dB away from himself and opened it
5 dB further out again, at 13.1 dB left — which would have been the hardest-panned event in the
project and cost him 1.33 dB of mono fold at 1 kHz. That was inherited from the by-type package,
where the left lock sat at +4.6 and the left door at +13.1, 8.5 dB apart, while both right pairs
agreed to within half a decibel. One stem was re-rendered to fix it, touching 49,471 samples
between 10.886 and 11.917 s and nothing else.

### Why this action was refiled by journey

**A monk's journey is one continuous gesture and it sat on four faders.** The engine applies one
gain per bed, so with the walking in one stem, the robes in another, the locks in a third and the
doors in a fourth, lowering the doors made a monk arrive silently, and no monk could take a
different path from any other. Filing by journey costs the ability to level all the footsteps
together — deliberately, because a path must not change loudness halfway along — and buys a scene
in which five different people do five different things.

**It also broke a metronome that could not be heard until it was named.** In the by-type package
the five keys landed at 2.00, 7.20, 12.40, 17.60 and 22.00 s — four gaps of exactly 5.20 s — with
all five peaks bit-identical at a raw value of 0.0621503592; the footsteps sat on the same grid.
Five monks were one monk five times. Across the five journey stems there are now **63 events with
63 distinct peak values and nothing shared between any two**, and the five journeys overlap —
monk 2 starts forward at 5.4 s while monk 1 is still walking away at 8.1 s — so the queue flows
rather than ticks.

**The key became the signature event it depicts.** It was the quietest thing in the action at
−24.1 dBFS, 0.7 dB right and 17.2 dB narrow; it is now five different takes at five different
levels, at 1.8 dB left where the almoner's hand meets the monk's, −9.8 dB wide, peaking at −9.0
dBFS, and the loudest thing in the folder. That breaks the 4 dB intra-stem spread rule as a
declared exception, the same way Produce Stone's cleave does.

### One thing left

**`page_turns_sfx_v01` folds −1.72 dB at 125 Hz** and −1.17 dB at 250 Hz, in bands holding 5.9%
of the stem. It is byte-identical to the v35 delivery, it was explicitly not asked for in either
rebuild, and it is the only measurement in this folder outside the contract. Noted, not queued.

---
## `build_roads_actionA` — Build Roads

**PRESCRIBED, DELIVERED AND MEASURED, all on 2026-10-18.** Read off the action's own artwork,
asked for, and checked against the delivery — the first action whose layout went round that loop
inside a day. **Nine of the eleven landed at 0.00 dB**; `rammers` at −0.11 and the two cart stems
at −0.49, declared. What the beds measured before is kept at the end of the section, because it is
the argument for having done this at all.

**RE-READ AGAINST `build_roads_build_road_left_v02.png` ON 2026-10-23, and the beds survived it.**
The artwork was remade: one ox where there were two, and the whole background right replaced —
timber viaducts, a crane and flooded ground became hills, a winding road and a distant castle.
Every bed was re-read against the new frame and **none moved more than 0.3 dB except the cart**.
The two beds that had been agreed against the old background, `bridge_work` at 4.2 dB right and
`river` at 5.6, have nothing left to answer to and are struck from the table. Neither was ever
built, so nothing is retired with them.

### What the picture puts where

A loaded ox cart fills the **left edge**: its rear wheel at 0–4.5%, the body between 0% and 11%,
a second wheel at 7.5–10.5%, and the shaft running right to the yoke. **One ox** stands in the
shafts between 11.5% and 25%, its head and horns from 18%. A hooded rider on a horse is behind at
22–29.5%, the horse's head at 26–29.5%, with a ruined castle on the skyline at 2–19%. The subject
of the picture is a monk at **45%** driving an upright timber rammer into a stone block; six more
recede behind him between 48% and 75%. The new road runs from the bottom at 62% back to a
vanishing point near 80%, fenced along 72–82%. A lantern hangs on a post at **83%** — the only
warm light in the frame — with a cross-carved milestone beside it at 86–100% and a second castle
small on the horizon at 85–92%. Broken stone fills the lower frame from the left edge to about
60%.

*v01 had two oxen between 10% and 29%, a banner over the rider, timber viaducts and a crane across
60–97% and flooded ground beneath them. The oxen became one, and the viaducts and the water are
gone.*

Horizontal position in frame sets the pan: `balance_dB = (50 − x%) / 50 × 8`, positive left.
Apparent distance sets level and width, never pan. Anything not in the picture is free, and
centre is reserved for what is everywhere.

`width` is given twice: **de-panned** is the source's own size, and **as filed** is what the
shipped file measures with the pan still in it. The two differ by the pan, and on anything placed
past about 4 dB the second figure is mostly placement — see *How the numbers are taken*.

| stem | read at | balance asked | **delivered** | width de-panned | width as filed | motion | construction |
|---|---:|---:|---:|---:|---:|---|---|
| `ox_cart_mechanics_sfx_v02` | 5.5% | 7.1 dB L | **6.00 L** | −32.21 | −9.54 | static | placed, a point |
| `ox_cart_stones_sfx_v02` | 5.5% | 7.1 dB L | **6.01 L** | −29.98 | −9.52 | static | placed, a point |
| `ox_breathing_sfx_v02` | 18.3% | 5.1 dB L | **4.80 L** | −15.69 | −10.02 | static | placed |
| `horse_snorts_sfx_v02` | 25.8% | 3.9 dB L | **3.99 L** | −19.82 | −12.13 | static | placed, a point |
| `gravel_sfx_v02` | 32% | 2.9 dB L | **2.91 L** | **−7.52** | −6.92 | static | **field**, 100% decorrelated |
| `rammers_sfx_v02` | 45% | 0.8 dB L | **0.68 L** | −12.22 | −12.11 | static | placed |
| `wind_sfx_v02` | — | centre | **0.01 R** | −6.94 | −6.94 | static | field, continuous |
| `worker_footsteps_sfx_v02` | 55% | 0.8 dB R | **0.79 R** | −11.00 | −10.89 | static | placed |
| `far_work_sfx_v02` | 65% | 2.4 dB R | **2.42 R** | −7.91 | −7.44 | static | field |
| `oil_lamp_rattle_sfx_v02` | 83% | 5.3 dB R | **5.13 R** | −18.39 | −10.15 | static | placed, a point |
| `oil_lamp_flame_sfx_v02` | 83% | 5.3 dB R | **5.09 R** | −9.17 | −6.99 | static | field, continuous |

No placement above costs more than **0.52 dB** of mono fold, and most cost under 0.3 dB. All
eleven fold within **0.90 dB**, against three that failed the 1 dB limit before — `oil_lamp_flame`
at −7.27 dB, `wind` at −3.46 and `ox_breathing` at −2.76.

### The width column is why this doc now carries two figures

**Four of the eleven hit their stated width band while having almost no width at all.**
`horse_snorts` reads −12.13 dB as filed and −19.82 de-panned; the two cart stems read −9.5 and
are **exact panned mono on the master**, −111.6 and −96.2 dB, arriving at −32 and −30 only
because Vorbis cannot encode a perfectly correlated pair. They met the number as written. The
number was the wrong number.

**And one row asked for something that does not exist.** At 6.5 dB L the narrowest possible
side/mid is **−8.93 dB**, so the cart could not be given −10 to −12 dB at that balance. The
supplier caught it, declared it, and delivered 6.01 dB L — inside the ±0.5 dB tolerance — at the
narrowest image that balance allows. Five of the eleven rows were affected and only the two carts
were wholly impossible; the other three straddled their floor and landed inside their bands, so
nothing flagged them.

**What the change bought is visible in the one bed that was really about width.** `gravel` went
from −21.55 to **−7.52 dB** de-panned: a point pretending to be the stone going down across a
whole work site, now a genuine field with 100% of its side energy unexplained by any fit to mid.

### What this table decided, and what the delivery did about it

*These four were written against the beds as they stood on the morning of 2026-10-18 and are kept
in that tense, with the delivered figure beside each.* The files they describe are gone.

**The ox cart was a left-edge object sitting almost centred.** Mechanics and stones read 2.4 and
2.3 dB left against the 6.5 the frame gives them — the single largest correction in the action.
**Delivered at 6.00 and 6.01 dB left**, which is the floor-constrained departure declared below
rather than the 6.5 asked for.

**The ox trio was inside out.** The animals measured **6.5 dB left** while their own cart measured
2.4, and in the picture the cart is at the very edge with the oxen inboard of it. The three had
been built as one group and panned by ear rather than by position, so the heaviest, nearest object
ended up nearest the middle. A cart and its load are **one object and share one position exactly**,
which is rule 2; the ox at the shaft is a second thing and gets its own. **Delivered the right way
round**: cart at 6.00, ox at 4.80, horse at 3.99 dB left.

**The right half of the frame was carried by almost nothing.** `far_work` read 0.4 dB right and the
lamp 1.3 to 2.7 dB right, so the viaducts, the water and the only light source in the picture were
all crowded into the middle. **Delivered at 2.42 dB right for `far_work` and 5.09 / 5.13 for the
two lamp stems**, which puts the only warm light in the frame where the frame has it.

*The two right-hand positions that were being held open are now closed.* `bridge_work` at 4.2 dB
right and `river` at 5.6 were agreed on 2026-10-18 against a background of viaducts and flooded
ground. v02 has neither, so both are struck rather than left standing as ground reserved for
something the picture no longer contains. The right of the stage is now `far_work` at 2.4 and the
two lamp stems at 5.1 — three beds, and the frame they answer to is emptier than the one they were
placed in.

**Ten of the eleven beds sat within 2.7 dB of centre.** Build Roads had the widest subject matter
of any action in the tree — an edge-to-edge work site with a cart at one side and a bridge at the
other — and had the narrowest stage. That was the finding this table existed to fix, and it is
fixed: the spread runs from 6.0 dB left to 5.1 dB right.

**WHAT THE v02 RE-READ FOUND, 2026-10-23.** The ox and the horse were the stated change and they
barely moved: the pair became one ox, narrowing from 10–29% to 11.5–25%, but its centre went 19.5%
to 18.3%, which is **0.19 dB**; the horse went 25% to 25.8%, **0.13 dB**. Against beds delivered at
4.80 and 3.99 dB left the new frame asks 5.07 and 3.87. Neither is worth re-panning.

**The cart is the one placement the new frame argues with.** Its body ran 5–17% and now runs 0–11%,
taking the read point from 9% to 5.5% and the ask from 6.56 to 7.12 dB left. Both cart stems were
delivered at 6.00, so a gap of 0.56 dB is now **1.12 dB**. They are panned mono points — −32.21 and
−29.98 de-panned — so moving them costs almost nothing in fold and nothing else in the action moves
with them. Recorded here and not corrected, because the beds were not re-delivered.

### What the eleven measured before, which is the argument for the table

Taken on the shipped `.ogg` files the morning of 2026-10-18, before the rebuild.

| bed | balance | width | construction | against the table |
|---|---:|---:|---|---|
| `ox_breathing` | 6.5 dB L | -1.3 dB | pan + room | 1.7 dB too far left, and far too wide |
| `gravel` | 1.0 dB L | -18.8 dB | decorrelated | 1.9 dB right of its place, almost no width |
| `rammers` | 0.7 dB L | -12.1 dB | decorrelated | **already in place**; width 0.1 dB outside the band |
| `worker_footsteps` | 0.3 dB L | -15.6 dB | decorrelated | 1.1 dB left of its place |
| `ox_cart_mechanics` | 2.4 dB L | -17.1 dB | panned point | 4.1 dB right of its place |
| `ox_cart_stones` | 2.3 dB L | -17.5 dB | panned point | 4.2 dB right of its place |
| `far_work` | 0.4 dB R | -9.2 dB | decorrelated | 2.0 dB left of its place; width is fine |
| `horse_snorts` | 0.5 dB R | -13.7 dB | decorrelated | **4.5 dB out** — the largest single error |
| `oil_lamp_flame` | 1.3 dB R | -1.6 dB | decorrelated | 3.8 dB left of its place, and far too wide |
| `wind` | 1.5 dB R | -2.7 dB | decorrelated | should be centre; too wide |
| `oil_lamp_rattle` | 2.7 dB R | -15.5 dB | pan + room | 2.4 dB left of its place |

### Three beds failed the mono-fold limit, and all three failed on width

Energy-weighted per-octave, counting only bands carrying at least 1% of the stem:

| bed | side/mid | worst fold | band | share of the stem |
|---|---:|---:|---:|---:|
| `oil_lamp_flame` | -1.58 dB | **-7.27 dB** | 125 Hz | 7% |
| `wind` | -2.69 dB | **-3.46 dB** | 1 kHz | 21% |
| `ox_breathing` | -1.28 dB | **-2.76 dB** | 125 Hz | **57%** |

`oil_lamp_flame` is the worst fold in the tree: it loses between 1.21 and 7.27 dB in *every* band
that carries it, including the 250 Hz band that holds 46% of the stem. `ox_breathing` is the most
consequential, because the band it loses 2.76 dB in is where more than half the ox lives — on a
laptop speaker the animal mostly disappears. All three are genuinely decorrelated rather than
panned mono, so the method is right and only the amount is wrong; a 1 dB fold limit caps width at
about **-5.87 dB** side/mid and these three sit well past it.

At the other end, five beds have almost no space in them at all — `gravel` at -18.8 dB,
`ox_cart_stones` at -17.5, `ox_cart_mechanics` at -17.1, `worker_footsteps` at -15.6 and
`oil_lamp_rattle` at -15.5. Nothing there folds, and nothing there has any size either.

### One repeated sample

`rammers` **had two pairs of bit-identical peaks** among its fourteen strikes — events 4 and 7 at
a raw value of 0.4013268948, events 9 and 12 at 0.3948360682 — and three of its gaps are
2.727, 2.729 and 2.729 s. It is also the loudest bed in the action at -7.93 dBFS, so the
repetition is audible rather than buried. Milder than Allocation's five-in-a-row and the same
fault: one recording retriggered. A rammer is a rhythmic tool and some regularity is right; two
strikes that are bit-identical are not regularity, they are one strike played twice. It now reads
**14 distinct peak values of 14** and a loudest-to-second-loudest gap of 0.489 dB against 0.000,
built from the same fourteen recordings — each matches the old stem at r = +0.998.

---
## `build_roads_actionB` — Build Shrine

**PRESCRIBED, DELIVERED AND MEASURED**, read off the action's own artwork,
`duty_actions/build_roads/build_shrine/build_roads_build_shrine_right_v01.png`, on 2026-10-19 and
filed the same day after two rounds. **Six of the seven landed at 0.00 dB**; `tinkering` at
−0.22. What the beds measured before is kept at the end of the section.

**Both rounds were spent on faults in the request rather than the delivery**, and the second one
is the reason this file now says what it says about multi-event stems — see *What the width
column cannot tell you* below.

### What the picture puts where

A stone wayside shrine stands left of centre, spanning **31% to 49%** of the frame, with a carved
figure in its niche and a cross on its roof. **A lit candle sits in the niche at 41%** and is the
brightest thing in the picture. Dressed stone blocks lie at the shrine's foot between 28% and
40%. A hooded monk in heavy wool fills the right of the foreground from **48% to 78%**, bent over
the candle with his hands cupped at 46%; his body's centre of mass is about **63%** and his rope
belt crosses at 62%. In the background right a **gallows stands between 77% and 83%**, a body
hanging at 80%, **two corvids perched on its crossbeam** at 78.5% and 81%. A dead tree fills
88–95%, a waymarker cross stands at 9% on the left, and two or three birds are in flight above
the hillside at about 9%. Stone walls close both edges; a track runs down each side.

Horizontal position in frame sets the pan: `balance_dB = (50 − x%) / 50 × 8`, positive left.
Apparent distance sets level and width, never pan.

| bed | read at | asked | **delivered** | width de-panned | as filed | motion | construction |
|---|---:|---:|---:|---:|---:|---|---|
| `tinkering_sfx_v02` | 40% | 1.6 dB L | **1.38 L** | −11.09 | −10.75 | static | placed |
| `wind_sfx_v02` | — | centre | **0.00** | −7.00 | −7.00 | static | field, continuous |
| `fabric_sfx_v02` | 63% | 2.1 dB R | **2.10 R** | −11.05 | −10.32 | static | placed |
| `monk_robe_sfx_v02` | 63% | 2.1 dB R | **2.10 R** | −11.00 | −10.28 | static | placed |
| `crows_ravens_sfx_v02` | 80% | 4.8 dB R | **4.80 R** | **−95.68** | −11.39 | static | **placed, four mono points** |
| `gallows_timber_sfx_v02` | 80% | 4.8 dB R | **4.80 R** | −13.05 | −9.15 | static | placed |
| `gallows_rope_sfx_v02` | 80% | 4.8 dB R | **4.80 R** | −13.01 | −9.13 | static | placed |

No placement above costs more than **0.30 dB** of mono fold, and all seven fold within 0.79 dB.

### What the width column cannot tell you

**`crows_ravens` reads −95.68 dB de-panned and that is the honest number.** All four of its calls
are exact panned mono, as they always were — measured individually the previous version read
−102.7, −92.5, −93.5 and −106.1 dB. The **−11.45 dB** that version showed as a whole-stem figure
was not width: it was the **13.5 dB gap between its two groups of calls** surviving the de-pan,
because de-panning by a stem's whole-stem energy ratio leaves any event at a different balance
still partly panned, and that residual is counted as side energy. Modelling the old file as four
mono events at their measured balances predicts −10.1 dB of that apparent width from the split
alone.

**So a de-panned width figure is only meaningful for a stem whose events share one position.**
For anything else, measure per event — which is what rule 6 below now requires, and what the
delivery spec requires at §10.6b.

### This is the first table written under the de-panned width rule, and it is the case that rule was made for

At 4.8 dB right the pan alone imposes a floor of **−11.39 dB** on the measured side/mid. Under the
old definition a −12 to −14 dB target at that balance would have been **impossible**, which is
the trap that cost Build Roads a declared departure a day earlier. Stated de-panned there is no
conflict: those three beds should come back reading about −9.1 dB as filed, and the gap between
the two figures is the pan, not a miss. *The "expected as filed" column exists so that nobody
reads a correct delivery as a failed one.*

### What this table decides

**The gallows frame, its rope and the birds on it are one object at one position.** The birds are
perched on the beam; the rope hangs from it. Four beds at 4.8 dB right is more than this project
has put in one place before, and it is right here because they are literally one thing in the
frame. They separate by content and level rather than by pan — a creaking frame low and broad,
hemp under load, two corvid calls high and sharp.

**The monk's two stems share one position exactly.** `fabric` is his robe working as he changes
posture twice a lap and `monk_robe` is the same man moving; they are one subject, so they take
one place, the way Produce Wheat's binder has four gestures at 0.8 dB right. *An earlier reading
of this scene called their shared position a fault*, on the belief that `fabric` was canvas on
scaffolding — the file is named `fabric_flapping` and its record says "cloth under tension, which
is what a shrine under construction has". It is the monk. A record can be wrong about its own
subject, and the picture plus the person who commissioned it settle it, not the filename.

**The candle has no sound and the picture makes it the centre of the scene.** It is at 41%,
1.4 dB left, and it is the only light source in the frame. Not in the table because it is not in
the folder; recorded here because the omission is a decision somebody should make deliberately.

### What the seven measured before, which is the argument for the table

Taken on the shipped `.ogg` files on the morning of 2026-10-19, before the rebuild.

| bed | balance | width de-panned | against the table |
|---|---:|---:|---|
| `gallows_rope` | 9.7 dB R | −28.87 | **4.9 dB too far out**, and a point |
| `gallows_timber` | 9.8 dB R | −30.19 | **5.0 dB too far out**, and a point |
| `fabric` | 2.8 dB R | −28.59 | 0.7 dB out; no width at all |
| `monk_robe` | 2.8 dB R | −23.58 | 0.7 dB out; no width at all |
| `tinkering` | 1.4 dB L | −29.21 | **placement already right**; no width at all |
| `wind` | centre | −5.12 | **placement already right**; too wide |
| `crows_ravens` | 4.1 dB **L** | −11.46 | **8.9 dB out, and on the wrong side** |

### Two faults, both placement rather than content, and both fixed

*Written against the beds as they stood on the morning of 2026-10-19 and kept in that tense. The
files they describe are gone; the delivered figure follows each.*

**`crows_ravens` was on the wrong side by 8.9 dB.** It sat 4.1 dB left; the corvids in the picture
are on the gallows at 80% across the frame, which is 4.8 dB right. There are birds in flight at
9% left as well, so the bed had a referent on both sides and matched only the fainter one. Agreed
on 2026-10-19 to move the single bed to the gallows rather than split it, and **delivered at
4.80 dB right — all four calls, individually**, which is the part that mattered.

**The gallows pair failed the mono-fold limit, and the entire fold was the pan.** Both sat at
9.7 dB right and folded −1.01 and −1.02 dB, over the 1 dB limit; at 9.72 dB *the pan alone costs
1.00 dB* before any content is considered. They were also exact panned mono, −28.9 and −30.2 dB
de-panned, sitting on the width floor their own pan imposed — **side/mid −5.87 against a floor of
−5.89**. Pulling them to **4.80 dB right** dropped the fold to 0.30 dB and fixed both failures
without touching a sample of content.

*That is the clearest case this file holds for reading the picture first.* Neither bed was wrong
about what it is; both were placed by ear, too far out, and the arithmetic bill arrived as a fold
failure that looks like a width problem and is not.

### Six of the seven had no width — and the seventh had none either

`crows_ravens` appeared to, at −11.46 dB de-panned, and that figure was its two-position split rather than width; see above. The other six run **−23.6 to −30.2** — panned
mono with a direction and no size. `wind` is the opposite case and the only continuous bed here:
at −5.12 dB it is wider than the −6 to −8 the contract asks, and it folds **−5.63 dB at 500 Hz**
and −2.40 at 250 Hz, where 18% of it lives.

### The wind's loop was a hole, and it was the first bed caught by the new continuous test

Its wrap window **was the quietest window in the loop** — 0th percentile, 2.36 dB under the
median, the loop's own minimum falling exactly on the wrap. The join step read 1.42× the file's own
median sample step, which passes; the window test is what caught it. Both ends sat 1.1 to 1.7 dB
below the body, which is a fade rather than an equal-power fold. *A shallow hole is still a hole:
on a continuous wind the quietest moment of every lap falls on the seam, which is what a listener
hears as a pulse.* **Re-folded, it sits at the 89.7th percentile, 0.68 dB above the median**, with
a join step of 1.39×.

Three of the intermittent beds sit in the listen band — `fabric`, `gallows_timber` and
`tinkering` — and `fabric` is the file the ratio rule in §13 of `ambient_loop_note.md` was
written on, at 3.589 s against a shortest interior pause of 3.648.

### Nothing here replays a sample

All seven have distinct event peaks, and the loudest-to-second-loudest gaps run 0.39 to 4.29 dB.
Worth stating because it is the one fault this folder does **not** have, and three of the last
four actions did.

---

## `ordination_actionB` — Send on Mission

**PRESCRIBED, DELIVERED AND MEASURED, all on 2026-10-23 — and the prescription came eight days
after the delivery it corrected.** Ten beds were built and filed on 2026-10-15 with nothing read
off the artwork; a descriptive table written on 2026-10-23 found that **six of the ten sat on the
opposite side of centre from the thing they answer to**, and the rebuild below was asked for the
same day. Nine beds were re-panned from the 24-bit masters. `footsteps` was left alone.

This is the first action in the tree whose table was written to describe a fault and then used to
fix it inside the hour. What the beds measured before is kept at the end, because it is the whole
argument for having measured them.

### What the picture puts where

Read off `duty_actions/ordination/send_on_mission/ordination_send_on_mission_right_v04.png`.

A lantern burns on the monastery wall at the **far left**, its housing at 3–10% and the flame at
5–8%. A second hooded figure holds the door open from inside the gateway at 12–22%. The great
studded timber door fills 20–37% and its stone jamb 36–45%. The subject is a monk at **40–62%**,
hood at 45–58%, satchel at 40–48% and a pectoral cross at 52%, stepping out onto wet cobbles with
a staff at 55–63%. The road runs from the bottom at 55% back to a lit city gate at **75–82%**.
Near houses and a market awning stand at 62–72%, more houses at 82–95%, and a cathedral skyline
fills 62–95% behind all of it. **Two rats cross the cobbles at 83–93%.** Rubble closes the right
edge from 90%.

Everything that is not the monk, the door, the porter or the lantern is on the right.

### The method, written once

The nine bed records point here rather than carrying nine copies of this.

1. **De-pan to centre.** Energy-match the channels — scale R by `sqrt(eL/eR)` — so whatever
   imbalance the source arrived with stops being read as a placement. Six of this folder's ten
   beds were off centre because a *recording's* imbalance had been left in and treated as a
   position; `distant_dogs` sat 7.03 dB left purely because its source does.
2. **Scale the side.** Take mid and side, multiply the side by a per-bed factor, re-sum. Four
   beds needed this to clear the per-band fold limit; five were left at 1.000.
3. **Pan by attenuation only.** Divide the far channel down; never raise the near one. Nothing
   can clip that did not clip before, which matters on `door_close` at −1.70 dBTP.
4. **Give the level back.** Step 3 costs total energy — 2.86 dB on the worst case here — and
   that is a side effect of the pan, not a level anyone chose. Each bed carries a scalar makeup
   gain restoring the integrated (ungated) loudness of the `.ogg` it replaces, converged **on
   the encode** rather than on the WAV, because Vorbis moves loudness a tenth of a decibel or
   two. A scalar cannot change balance, side/mid or any band's fold, so this step is provably
   free of everything the rebuild was for. Eight of nine landed inside **0.02 dB**; `door_close`
   is the exception and says why below.

No trim, no fade, no edit, no re-cut, no loop change. Granulepos stays 1728000 — 36.000 s exactly.

### What was asked and what landed

`balance_dB = (50 − x%) / 50 × 8`, positive **left**. Every bed is inside **0.07 dB** of its ask.

| bed | answers to | asked | **delivered** | gap | side × | width before → after | fold before → after |
|---|---|---:|---:|---:|---:|---:|---:|
| `night_city_sfx_v01` | the whole city, 62–95% | 4.6 R | **4.58 R** | 0.02 | 1.000 | −4.33 → −4.33 | −3.432 → **−3.359** ✗ |
| `footsteps_sfx_v01` | the monk, 51% | 0.2 R | **0.01 L** | 0.17 | — | −31.60 → −31.60 | −0.009 |
| `staff_sfx_v02` | his staff, 59% | 1.4 R | **1.40 R** | 0.00 | 0.704 | −10.68 → −13.59 | −1.487 → −0.860 ✓ |
| `distant_dogs_sfx_v01` | the town beyond the gate | 5.6 R | **5.61 R** | 0.01 | 0.754 | −8.61 → −11.07 | −1.544 → −0.866 ✓ |
| `distant_cart_sfx_v01` | the gate road, 78% | 4.6 R | **4.61 R** | 0.01 | 1.000 | −22.42 → −22.34 | −0.037 → −0.321 |
| `two_horses_sfx_v01` | the gate road, 78% | 4.6 R | **4.59 R** | 0.01 | 1.000 | −23.84 → −23.97 | −0.028 → −0.305 |
| `rats_crossing_sfx_v01` | the rats, 88% | 6.1 R | **6.09 R** | 0.01 | 1.000 | −11.77 → −11.75 | −0.457 → −0.810 |
| `rat_squeaks_sfx_v01` | the rats, 88% | 6.1 R | **6.03 R** | 0.07 | 0.738 | −14.63 → −17.03 | −0.412 → −0.863 |
| `bottle_knock_sfx_v01` | the rats, 88% | 6.1 R | **6.13 R** | 0.03 | 1.000 | −27.91 → −27.57 | −0.016 → −0.482 |
| `door_close_sfx_v01` | the door, 28.5% | 3.4 L | **3.42 L** | 0.02 | 1.000 | −50.57 → −28.31 | −0.000 → −0.191 |

**The six inversions are gone.** `distant_dogs` moved 12.64 dB across centre, `rat_squeaks` 9.97,
`rats_crossing` 9.08, `bottle_knock` 6.80, `distant_cart` 4.71 and `night_city` 5.27. The stage
now runs from `door_close` at 3.42 left to `bottle_knock` at 6.13 right — a 9.55 dB spread where
the ten beds previously occupied 7.03 left to 0.25 right with the city on the wrong side of it.

**Panning a mono point costs fold even with no width added.** `distant_cart` went −0.037 to
−0.321 dB and `two_horses` −0.028 to −0.305 without a sample of new side content, because L and R
are no longer equal and the difference signal is no longer zero. That is the floor price of
placing anything off centre, and at a third of the limit it is cheap.

### `night_city` keeps a failing fold, and that was chosen

It is the one bed in the tree outside the 1 dB per-band limit. Six of its eight qualifying octaves
are past 1 dB, worst **−3.359 dB at 8 kHz**. Clearing −0.85 would have meant this:

| side × | de-panned width | worst qualifying fold |
|---:|---:|---:|
| 1.000 | **−4.33** | **−3.359** |
| 0.500 | −10.29 | −1.564 |
| 0.350 | −13.39 | −1.063 |
| 0.279 | −15.36 | −0.849 |

Eleven decibels of width off the **only continuous bed in the action** — the one that is always
playing, and the one carrying what little width the action has. The project owner was shown that
ladder and chose to keep the width.

**The rebuild did not make it worse.** The fold was −3.432 before and is −3.359 after: the
position was fixed and the fold left exactly as failing as it already was. On a phone speaker the
city loses about three and a half decibels of its upper bands for as long as the action is
selected. That is a known, chosen cost, recorded here and in the bed's own record rather than
carried quietly.

### `bottle_knock` departs from this table, and the timing is why

The descriptive table read this bed off the picture as the market stalls at 67%, which is 2.7 dB
right. The audio disagrees: it is audible **10.800–11.608 s, entirely inside `rats_crossing` at
10.299–11.855 s** and overlapping `rat_squeaks` at 10.481–11.631 s. A bottle that sounds only
while two rats are crossing is a bottle a rat knocked over, so it is placed with them at 6.1 dB
right rather than 3.4 dB away from the animal doing it. Both readings were put to the project
owner and he chose the rats.

**That is the same class of error as the retirement note below**: a position argued from a drawing
and never checked against when the sound actually happens. Two groups in this action share a
position for the same reason and it is deliberate — `distant_cart` and `two_horses` are one event
at 14.0–30.2 s, a cart and the horses pulling it; `rats_crossing`, `rat_squeaks` and
`bottle_knock` are one event at 10.3–11.9 s.

### `door_close` is owed 1.51 dB, and its master is missing

Two things are wrong with this bed and neither was introduced by the rebuild.

**It was re-panned from the shipped `.ogg`, not from a master.** The other eight came from
`sfx/_masters/ordination_actionB/`; the stem that folder holds under this bed's name correlates
**0.0003** with the shipped file against its L, its R and its mono sum — not a weak match but no
relationship at all. Whatever is in `_masters` here is not what the game plays. The recipe in the
bed's record still reproduces the `.ogg` from the upload, so nothing about provenance turns on it,
but the gap is real and is recorded rather than resolved.

**Its makeup gain could not be taken in the audio.** The pan cost 1.41 dB; giving it back would
have put the file at about −0.19 dBTP through Vorbis, past the −1 dBTP line that this bed's own
2.0 dB of encoder headroom exists to hold. The makeup was therefore clamped by the peak ceiling at
−0.08 dB, and the bed now plays **1.51 dB under** the loudness of the file it replaced. The remedy
is one number: `gainDb` −1.5 → about 0.0. **It has deliberately not been typed**, because levels
in this tree are the project owner's by standing decision.

### Three records said the trim was zero while the field said otherwise

`rat_squeaks` carries `gainDb` −17.0, `rats_crossing` −4.0 and `door_close` −1.5, all set by ear.
All three records still read *"THE TRIM IS ZERO BECAUSE NOBODY HAS SET IT"* — a sentence that was
true when written and went stale when the levels were set. Corrected in all three as part of this
filing. **The re-pan was made level-neutral precisely so those three numbers still mean what they
meant**; `door_close` is the one that no longer does, and it is flagged above.

### The rats were the clearest case, and a record here was wrong about them

Kept because the correction is the point, not the error.

`rats_crossing` was filed **2.99 dB left** and `rat_squeaks` **3.94 dB left**. The rats are drawn
at 83–93% of the frame, which is **6.08 dB right**. The two beds were 9.07 and 10.02 dB from the
animals they are named after, on the wrong side of centre. They are now at 6.09 and 6.03 right.

**And v03's retirement note in `attribution.json` still says the opposite.** It records that v04
"adds two rats crossing at 83-93%" and that "both changes move the picture TOWARD beds that were
already filed." The rats were added to the artwork to answer beds that existed — and put on the
far side of the frame from where those beds played. That sentence was written on 2026-10-20
without measuring the beds it claimed agreement with. It is wrong, it is mine, and **it is still
in the file**: the beds have since been moved to where the picture puts them, which makes the
sentence's conclusion accidentally true and its reasoning no less false. Correcting it is open.

### What the ten measured before, which is the argument for the table

| bed | picture | **filed 2026-10-15** | gap | de-panned width | worst fold |
|---|---:|---:|---:|---:|---:|
| `night_city_sfx_v01` | 4.6 R | **0.69 L** | **5.25, opposite side** | −4.33 | **−3.432** ✗ |
| `footsteps_sfx_v01` | 0.2 R | **0.01 L** | 0.17 | −31.60 | −0.009 |
| `staff_sfx_v02` | 1.4 R | **0.08 R** | 1.36 | −10.68 | **−1.487** ✗ |
| `distant_dogs_sfx_v01` | 4.6 R | **7.03 L** | **11.59, opposite side** | −8.61 | **−1.544** ✗ |
| `distant_cart_sfx_v01` | 4.6 R | **0.10 L** | **4.66, opposite side** | −22.42 | −0.037 |
| `two_horses_sfx_v01` | 4.6 R | **0.25 R** | 4.31 | −23.84 | −0.028 |
| `rats_crossing_sfx_v01` | 6.1 R | **2.99 L** | **9.07, opposite side** | −11.77 | −0.457 |
| `rat_squeaks_sfx_v01` | 6.1 R | **3.94 L** | **10.02, opposite side** | −14.63 | −0.412 |
| `bottle_knock_sfx_v01` | 2.7 R | **0.67 L** | **3.39, opposite side** | −27.91 | −0.016 |
| `door_close_sfx_v01` | 3.4 L | **0.00** | 3.44 | **−50.57** | −0.000 |

Three beds failed the fold limit and two of the three now pass. Five of the ten had no width at
all — `door_close` at −50.57 de-panned and a correlation of 1.0000, exact dual mono for a door
filling 20–37% of the frame, plus `bottle_knock`, `two_horses`, `distant_cart` and `footsteps`
within a few decibels of the same. **That has not been fixed and was not asked for.** Four of the
five are still points; `door_close` now reads −28.31 only because Vorbis quantised its two
unequal channels independently and the noise landed in the side, which is a codec artefact and
not width. A width claim has to be made on the master, never on the shipped `.ogg`.

### The group sum is where `door_close`'s missing decibel and a half shows up

At `groupDb` −5.0 this action summed **−2.42 dBTP** before the rebuild and was the hottest in the
tree. It now sums **−2.81 dBTP at −29.86 LUFS**, which puts it second on peak behind
`taxation_actionA` at −2.64 and second on loudness behind `allocation_actionA` at −29.03.

**Nine beds are level-neutral, so that 0.39 dB is one bed.** `door_close` is the hottest single
bed in the tree at −1.70 dBTP and therefore sets the group's peak almost by itself; it is the one
bed whose makeup gain had to be clamped, and the 1.51 dB it is owed reappears here as 0.39 dB off
the action. That is the practical argument for giving it back in `gainDb`: the loss is not
confined to one door, it moves the whole action down the crossfade ladder.

It is still among the two or three actions whose faults are heard most, which is why it was worth
the rebuild.

*These beds are 36.000 s where the rest of the tree is 35 or 25. Nothing depends on it; it is
noted because the group-sum tool prints lengths and this is the only action that prints 36.*

---

## `clerical_actionB` — Silversmith

**DELIVERED AND FILED 2026-10-23**, twelve beds at 35.000 s, replacing a single 25 s fire loop.
Read off `duty_actions/clerical/gain_coins/clerical_gain_coins_right_v06.png` against a
percentage grid, balance by the project formula `(50 - x%) / 50 * 8`, positive = left.

### What the picture puts where, and what was filed

| element | spans | centre | picture says | filed at | bed |
|---|---:|---:|---:|---:|---|
| forge mouth and coals | 0–16% | 8.0% | 6.72 L | **5.000 L** | `fireplace` |
| the coals alone | 0–13% | 6.5% | 6.96 L | **6.698 L** | `forge_embers` |
| bowl of blanks | 4–23% | 13.5% | 5.84 L | **5.181 L** | `blank_handling` |
| bench and vessels | 14–33% | 23.5% | 4.24 L | **4.221 L** | `bench_response` |
| coin die | 41–50% | 45.5% | 0.72 L | **0.734 L** | `die_work` |
| the smith's torso | 30–76% | 53.0% | 0.48 R | **1.056 R** | `smith_body` |
| minted coin stacks | 55–70% | 62.5% | 2.00 R | **2.029 R** | `coin_tick` |
| coin boxes | 68–95% | 81.5% | 5.04 R | **5.00 R** (deposit) | `coin_transfer` |
| the guard | 82–97% | 89.5% | 6.32 R | **5.600 R** | `guard_leather`, `_sword`, `_helmet` |
| his sword | 90–95% | 92.5% | 6.80 R | **5.600 R** | `guard_sword` |

`smith_footsteps` is not in the table because it moves: 0.70 L for the five contacts at the
bench, then 2.0, 3.2, 4.0 and 4.0 R as he walks to the box. Its whole-stem balance of −0.607
describes nothing.

### Three placements fall short of the picture, and each for a different reason

**The forge, 5.000 against 6.72.** At its delivered width it reaches only 3.84 before its fold
crosses the −0.85 working target. 5.000 was bought with a side scale of 0.90, taking it from
−7.97 de-panned to −8.90. The rest would have cost a scale of 0.68 and a width of −11.35, at
which a room full of heat starts sounding like a fire noise over on the left. The precedent is
Build Roads' `oil_lamp_flame` at 5.09 and −9.17.

**The bowl, 5.181 against 5.84.** 5.220 is where its fold reaches the target at its delivered
width, and at −13.74 de-panned there was nothing left to narrow. It sat at 0.700 until the
second revision, on top of the die, leaving the whole stage between the fire and the die empty.

**The guard, 5.600 against 6.32.** Three beds, one body, one position, limited by the tightest
member: `guard_sword` reaches 5.641. Taking the group to 6.32 would have needed side scales on
the sword and the leather, putting them at −14.36 and −12.92 de-panned, and −14.36 is past the
point where this tree stops calling a bed placed.

### What the retired bed measured, which is the argument for the twelve

`silversmith_sfx_v01.ogg` measured **−25.91 de-panned at +0.05 balance, correlation +0.9949** —
a mono point at dead centre, under a picture with a forge at one edge and a guard at the other.
`fireplace_sfx_v01.ogg` is built from the same master and measures **−8.88 de-panned at 5.000
left**, and the other eleven put the work, the man and the guard where the card says they are.

### Three beds sit on the fold ceiling

`fireplace` holds 0.0007 dB of margin against −0.85, `blank_handling` 0.0024 and `guard_sword`
0.0044. All three clear the 1 dB per-band limit after Vorbis q6 — −0.8522, −0.8728 and −0.9105 —
which is exactly what the working margin exists to buy, and none of the three can absorb a
change of level, EQ, pan or cut.

---

## `clerical_actionA` — Devotion

**DELIVERED AND FILED 2026-10-19** from `Devotion_Clerical_v02`. Read off the action's own
artwork, `duty_actions/clerical/gain_piety/clerical_gain_piety_left_v04.png`, on 2026-10-19
against the six-stem delivery `Clerical_Final_Soundscape`, and delivered to within a thousandth
of a decibel the same day. The three beds that were in the tree were a different and smaller set;
all three are now retired and what they measured is at the end of the section.

### What the picture puts where

An old monk kneels face-down on a stone floor, his heavy robe filling **2% to 53%** of the frame
with its mass centred about **27%** and his rope belt coiled at 3–20%. His face is at **44%** and
his clasped hands at **46–52%**, with a rosary hanging from them, its beads running to a cross at
**49%**. A candle on a wrought-iron stand burns at **70%** — the only light source in the
picture. Behind it, stone steps rise between 53% and 68%, a carved crucifix stands at **65%**, a
carved saint in a niche at **82%**, and a censer hangs on a chain at **94%**. **A heavy wooden
bench fills 91% to 100%**, the only wood in the frame. A cross is carved into the wall at 10%.

Horizontal position in frame sets the pan: `balance_dB = (50 − x%) / 50 × 8`, positive left.
Apparent distance sets level and width, never pan.

| stem | read at | asked | delivered | de-panned | as filed, predicted → got | construction |
|---|---:|---:|---:|---:|---:|---|
| `robe_movement_sfx_v01` | 27% | 3.7 dB L | **3.70 L** | −11.32 | −9.3 → **−9.303** | placed |
| `slow_breathing_sfx_v01` | 44% | 1.0 dB L | **1.00 L** | −11.38 | −11.2 → **−11.189** | placed, continuous |
| `prayer_beads_sfx_v01` | 49% | 0.2 dB L | **0.20 L** | −11.50 | −11.5 → **−11.494** | placed |
| `background_sermon_sfx_v01` | — | centre | **0.00** | −7.65 | −7.6 → **−7.645** | field, continuous |
| `candlelight_sfx_v01` | 70% | 3.2 dB R | **3.20 R** | −7.60 | −6.9 → **−6.866** | placed, continuous |
| `wood_cracks_sfx_v01` | 95% | 7.2 dB R | **7.20 R** | −13.54 | −7.1 → **−7.061** | placed |

**Every row landed within a thousandth of a decibel of what was asked**, and every de-panned width
came back from the accepted v01 unchanged to within 0.002 dB. No placement cost more than
**0.621 dB** of mono fold, the largest being `wood_cracks` — which is the figure this table
predicted before the files existed.

*The column that matters most is the last one.* The request computed what each as-filed figure
would become once the pan was added — `ratio = (q² + p²w)/(p² + q²w)`, with `a = 10^(|B|/40)`,
`p = (a + 1/a)/2` and `q = (a − 1/a)/2` — and all six predictions landed within **0.04 dB**. That
is the de-panned convention paying for itself: it turns the as-filed number into a prediction
instead of a surprise.

### What the shipped `.ogg` measures, which is not what the master measures

Everything above is the 24-bit master. The board plays the Vorbis encode, and **q6 widens every one
of them**, because quantisation noise is uncorrelated between channels and lands in the side:

| stem | de-panned, master → encode | worst fold, master → encode |
|---|---:|---:|
| robe movement | −11.32 → **−10.50** | −0.579 → −0.602 |
| slow breathing | −11.38 → −10.99 | −0.471 → −0.503 |
| prayer beads | −11.50 → −11.36 | −0.355 → −0.350 |
| background sermon | −7.65 → −7.63 | −0.754 → −0.758 |
| candlelight | −7.60 → −7.57 | −0.977 → −0.976 |
| wood cracks | −13.54 → −13.45 | −0.952 → **−1.006** |

**`wood_cracks` crosses the 1 dB fold limit on the encode and not on the master**, by 0.006 dB. The
broadband figure hides where that happens: its 2 kHz band alone widens −11.02 → −10.21, and that
band carries 1.4% of a bed that is 81% silence — exactly where coding noise is the largest share of
what is there. It was kept at q6; `../sfx/README.md` carries the reasoning and the tree-wide sweep
behind it.

*Every width and fold number elsewhere in this file is a master measurement.* This is the first
section to state both, and the gap is small but it is not zero.

### This is the first table where nothing needs widening

Every one of the six already measures inside the band its role asks for — the two continuous beds
at −7.64 and −7.60 dB, the three foreground stems between −11.3 and −11.5, and the distant
timber at −13.5. All six read **100% of side energy unexplained** by a least-squares fit to mid,
and their per-band widths are uniform to within about a decibel across every octave that carries
energy. *That uniformity is the thing to notice*: Build Shrine's corvid bed spanned −5.2 to
−17.9 dB across its bands and failed a fold limit on a placement that looked safe. These do not.

**So the whole job here is placement, and placement is the whole of what is wrong.** All six
stems sit within **1.5 dB of centre** — balances of −0.01, −0.05, +0.10, +0.27, +0.37 and
−1.43 — in a picture that runs from a monk's robe at the left edge to a wooden bench at the
right.

### The per-band fold check was run before this table was written

This is the first table checked against the clause added to §7 of the delivery spec on
2026-10-19, which says the fold ceiling applies band by band and tightens as a stem is panned
out. At the proposed placements the ceilings are −5.87 dB at centre, −6.43 at 3.2 dB and
**−9.61 dB at 7.2 dB**; the widest carrying band in any of the six is `wood_cracks` at −11.3 dB.
Every row clears by at least 1.2 dB.

*That check exists because the previous action's corvid bed passed a fold limit at one placement
and failed it at another with no sample changed.* Running it before the request rather than after
the delivery is the point of having it.

### Three things this table decides

**The monk gets three positions, not one.** His robe at 27%, his breath at 44% and his beads at
49% span **3.5 dB**, which reads as one large figure close to the camera rather than as three
people — and it gives the left half of the picture, which is almost entirely monk, something to
carry it. *Agreed on 2026-10-19 as a departure from the one-subject-one-position rule*, on the
grounds that the rule exists to stop a single small source being smeared across the field, and a
robe filling half the frame is not that.

**`wood_cracks` goes to the bench it can be seen on.** Its own record calls it "distant
structural detail, not a foreground door or furniture cue", but the only wood in the picture is
the heavy bench at 91–100%, and the right third of the scene otherwise has nothing in it but the
candle. Agreed on 2026-10-19 to place it on the thing in frame.

**The censer has no sound.** It hangs on a chain at 94%, directly above the bench, and a slow
metallic creak there would be the natural companion to the timber. Not in the table because it
is not in the folder; recorded because the omission should be a decision.

### A length that was deliberate is being dropped, and that is the right call

The tree's `candle` is **25.5 s** against two beds of 35 s, and it was chosen that way: its own
record says *"the length was chosen for what it plays against — 25.5 s against Devotion's 35 s
realigns every 1785 s, half an hour."* A continuous bed at a different length drifts instead of
pulsing with the rest, which is what Build Roads' 31 s wind does under ten stems of 35.

**The delivery makes all six stems 35.000 s and that supersedes the reasoning.** It was written
when this action had two beds, one of them the candle; two continuous layers locking in step is
exposed. The delivery has **three** continuous beds, so moving one off 35 s would leave the other
two locked — the benefit is a third of what it appears to be.

**And there is nothing in any of them to recognise.** Across their own length in 1.5 s windows
the sermon varies by **1.10 dB**, the candle by **1.41** and the breathing by **3.51**, and the
event detector finds nothing in any of the three. The rule a loop has to meet is *no recognisable
event in a looping stem*; the `devotion` cut was taken from the cathedral master's quiet stretches
for exactly that reason, since the master "alternates full choir at −22 to −25 dB with long
stretches at −31 to −36 and only the quiet ones are a setting rather than a performance."

Uniform length also buys the stronger verification — **a reference mix that is the unity sum of
all six** rather than five with one excluded, which is the price Build Roads pays.

*A drifting length is an exception that has to earn itself per action, and here it does not.*
Recorded rather than silently dropped, because the 25.5 s was a decision and this is another one.

### What the three filed beds and the six delivered stems measure

| | balance | de-panned | length | |
|---|---:|---:|---:|---|
| `devotion_sfx_v01` *(filed)* | centre | −7.6 | 35 s | the service |
| `candle_sfx_v01` *(filed)* | centre | −7.6 | **25.5 s** | the flame |
| `rosary_sfx_v01` *(filed)* | centre | −11.5 | 35 s | the beads |
| `background_sermon` *(new)* | 0.05 R | −7.64 | 35 s | same master as `devotion`, cut 3.5 s later |
| `candlelight` *(new)* | 0.01 R | −7.60 | 35 s | same master as `candle`, **a different cut** |
| `prayer_beads` *(new)* | 0.10 L | −11.50 | 35 s | same material as `rosary`, re-roomed, timing kept |
| `robe_movement` *(new)* | 0.27 L | −11.32 | 35 s | new |
| `slow_breathing` *(new)* | 1.43 R | −11.38 | 35 s | new |
| `wood_cracks` *(new)* | 0.37 L | −13.54 | 35 s | new |

All three filed beds were retired on 2026-10-19 and the six stems filed in their place, so this
action went from three tracks to six and the tree from eighty-two beds to eighty-five. `groupDb`
went **+8.5 → +2.5** so that six beds at unity sit where three beds at their old trims did.

**Three of the six are the beds already in the tree, re-cut or re-treated.** `background_sermon`
correlates with `devotion` at **+0.9104** once a 3.5 s offset is allowed — the same cathedral
master, begun at 1:25 against the filed bed's 81.50 s. `prayer_beads` correlates with `rosary` at
**+0.9628 at zero lag**: the same bead timing with room treatment added. `candlelight` correlates
at **+0.015** and is a genuinely different cut of the same freesound candle.

---

## `taxation_actionA` — Taxation

**PRESCRIBED 2026-10-19, RE-READ 2026-10-19 AGAINST NEW ARTWORK, DELIVERED AND FILED 2026-10-20.**
The action's picture was replaced the same day: the balance scales came out of the right third and
**a second peasant setting a dressed stone block on the table** went in, so the scene now shows all
three tithe resources — grain, silver, stone — left to right. The layout below is read off the new
image.

**THE PICTURE WAS REPLACED A SECOND TIME ON 2026-10-20, AFTER THE BEDS WERE FILED**, by
`taxation_action_a_left_v02.png` — a further generation of the same scene rather than a new scene.
Everything below was written against the 19 October image and is left as written; the
re-measurement against what actually shipped is the subsection after the table, and the one note
it voids is marked where it stands.

**The lap is 25 s, not 30.** It was built at 30 and shortened without cutting an event: the
approach to the stone was compressed and the head and tail trimmed. 30 s was never a tree
standard — of 137 ambient beds, 99 are 35 s and 16 are 25 s, and the only four at 30 s were this
action's own. Everything below that says *thirty seconds* was written against the 30 s request and
is left as written.

### What the picture puts where

A hooded peasant fills the **left edge, 0–15%**, his cloak running the full height with its mass
about **7%**; his hands are on a grain sack at 12–19% and **23–37%**, his sleeve and sacking at
16–29%. Stacked sacks, a straw bundle and crates fill the background between 10% and 32%, an
unlit hanging lantern sits at **31–35%**, and the one barred window — now the only light in the
frame — at **35–39%**. **The sack spills grain across the table from 33%, its mass at 42%.** The
collector's gloved left hand holds a knife at 52–57%; **the tally stick he is notching is centred
at 55%**; his right hand grips it at 65%, his chain and cross pendant at 63.5%. **Coin stacks lie
at 52–66%, centred 57%.** The ledger runs 60–76%. **A dressed stone block stands at 76–89%**, its
lit top face centred about **83%**, with **three tally notches cut into its front face** and stone
dust scattered on the boards around its base. A second peasant's hands grip it at **82–92%** and
his cloaked body fills **90–100%**, centred **93%**.

| stem | read at | balance | width de-panned | expected as filed | from | construction |
|---|---:|---:|---:|---:|---:|---|
| `peasant_cloth_left` *(new)* | 7% | **6.9 dB L** | −11 to −13 | −6.2 to −6.9 | — | placed |
| `wheat` | 42% | **1.3 dB L** | −10 to −12 | −9.8 to −11.6 | −23.28 | placed |
| `tally_knife` *(new)* | 55% | **0.8 dB R** | −10 to −12 | −9.9 to −11.9 | — | placed |
| `tally_leather` *(new)* | 55% | **0.8 dB R** | −10 to −12 | −9.9 to −11.9 | — | placed |
| `coins` | 57% | **1.1 dB R** | −10 to −12 | −9.8 to −11.7 | −3.43 | placed |
| `stone_block` *(new)* | 83% | **5.3 dB R** | −10 to −12 | −7.3 to −8.2 | — | placed |
| `peasant_cloth_right` *(new)* | 93% | **6.9 dB R** | −11 to −13 | −6.2 to −6.9 | — | placed |
| `barn_creaks` | — | **centre** | −7 to −8 | same | −3.21 | field |
| `room` *(then ours, unchanged — it was replaced too)* | — | **centre** | −7 to −8 | same | −10.97 | field, continuous |

**The two peasants bracket the scene at ±6.9 dB and the stage is now 13.8 dB wide.** This action
had the narrowest soundstage in the tree at 2.4 dB when it held five beds clustered on a table;
the new artwork fixes that by putting a person at each edge, which no amount of careful panning
could have done.

### What the shipped picture puts where, measured against a grid

The artwork changed again on 2026-10-20, after the nine beds were filed. These are the positions
in `taxation_action_a_left_v02.png`, taken off a percentage grid rather than estimated — the
layout formula turns each of them into a stereo placement, so a guess here becomes a number in a
bed's record.

| feature | read on the 19 Oct image | measured on v02 |
|---|---:|---:|
| hooded peasant, cloak mass | 7% | **~5%** |
| his upper hand on the sack | 12–19% | 10–16% |
| sacks, straw and crates | 10–32% | 9–32% |
| **unlit hanging lantern** | **31–35%** | **gone** |
| the barred window | 35–39% | 33.5–38% |
| grain spills from / mass at | 33% / 42% | 33% / 41% |
| tally stick, centred | 55% | 55% |
| chain and cross pendant | 63.5% | 63.5% |
| coin stacks, centred | 52–66%, 57% | 50–65%, 57% |
| the ledger | 60–76% | 57–78% |
| stone block, lit top face | 76–89%, 83% | 76.5–89.5%, **83%** |
| stone-bearer's hands | 82–92% | 81–93% |
| stone-bearer's body, centred | 90–100%, 93% | 90–100%, **~95%** |

**Nothing in the lap had to be re-cut.** The stone block, which carries the loudest event by
9.5 dB, is where it was to within half a percent. The largest move is the two peasants, each about
2% further out, which through the formula takes the cloth beds from 6.9 dB to about **7.2 dB** —
and both are delivered narrower than their targets already, so the change moves them further
inside rather than out. At 7.2 dB the per-band fold ceiling is about −9.4 dB de-panned, where
those beds sit at −16.40 and −15.55. Everything else moves by 0.2 dB or less.

*The check that mattered was not of the picture but of the file.* The first one offered for this
slot carried a hand-drawn red review circle at 58–61% across — 386 pixels of marker red in a
palette with nothing saturated in it — and was RGBA with Adobe XMP where every other card here is
RGB with none. An annotated copy and an export are indistinguishable by filename and obvious by
measurement.

### What was delivered, measured on the 24-bit master

| stem | asked | **delivered balance** | de-panned | **width asked** | fold | worst octave | silence |
|---|---:|---:|---:|---:|---:|---|---:|
| `peasant_cloth_left` | 6.9 dB L | **+6.38** | −16.40 | −11 to −13 | −0.593 | −0.750 @ 8 k | 97.1% |
| `wheat` | 1.3 dB L | **+1.19** | −11.08 | −10 to −12 | −0.344 | −0.416 @ 16 k | 87.3% |
| `tally_knife` | 0.8 dB R | **−0.47** | −12.21 | −10 to −12 | −0.257 | −0.393 @ 62.5 | 91.2% |
| `tally_leather` | 0.8 dB R | **−0.80** | −12.45 | −10 to −12 | −0.249 | −0.297 @ 500 | 94.6% |
| `coins` | 1.1 dB R | **−0.77** | −12.88 | −10 to −12 | −0.226 | −0.352 @ 1 k | 87.0% |
| `stone_block` | 5.3 dB R | **−5.30** | −13.97 | −10 to −12 | −0.520 | −0.816 @ 500 | 89.9% |
| `peasant_cloth_right` | 6.9 dB R | **−6.04** | −15.55 | −11 to −13 | −0.566 | −0.704 @ 8 k | 96.0% |
| `barn_creaks` | centre | **−0.25** | −11.35 | −7 to −8 | −0.308 | −0.514 @ 250 | 50.4% |
| `room` | centre | **+0.11** | −13.12 | −7 to −8 | −0.207 | −0.743 @ 2 k | 0.0% |
| **mix** | — | **−1.60** | −11.16 | — | −0.354 | −0.450 @ 500 | 0.0% |

**Every placement landed inside 0.9 dB and seven of the nine inside 0.35.** The two that did not
are `tally_knife` at −0.47 against −0.80 asked and `peasant_cloth_right` at −6.04 against −6.90;
both are narrower moves than asked rather than wider, so neither costs anything at the fold limit.

**The nine stems sum to the reference mix with 0 differing samples of 2,400,000**, maximum
absolute difference 0.000e+00. That is now a standing condition on this kind of delivery; the
archive that preceded it failed by 14.9% of samples, which is how an eighth bed nobody had
recorded was found.

### Three widths missed their band and one of them could not have met it

`coins` at −12.88 and `tally_leather` at −12.45 are 0.88 and 0.45 dB narrower than the −10 to −12
band. Reported, not corrected: narrower never threatens the fold limit.

**`barn_creaks` is 3.4 dB narrower than its field target and that one is not a choice.** The table
asks −7 to −8 and the replacement source cannot reach −8 and pass the per-band limit at the same
time: at −7.78 its 250 Hz band folds **−1.534 dB**. The widest setting that passes everywhere sits
near −10.5 with 0.13 dB of margin, so it was taken to −11.35 for half a decibel instead. *This is
the second time this file has recorded a bed whose width target was unreachable in the material
rather than unmet in the build, and both times the source had already been chosen.*

`stone_block` at −13.97 is about 2 dB narrower than asked, and that is the cost of a repair rather
than a miss — see below.

### The stone is panned by attenuation, because a symmetric pan would clip

`stone_block` peaks at **−2.59 dBFS**, 9.5 dB above anything else in the lap. Panned symmetrically
to 5.3 dB right it would reach **+0.43 dBFS**. It is panned by pulling the left channel down
instead, which leaves the peak exactly where it is.

**Its side signal had to be scaled before it could be placed at all.** The shove was cut from
12.380 s of its source, inside a region measured days earlier — for a different purpose — as
anti-phase: 12.0 to 13.8 s of that recording folds −3.4 to −5.8 dB in mono. Re-cutting does not
help; seven alternative windows were measured and 250 and 500 Hz fail across the whole file. The
repair is a side-scale, 0.22 on the shove and 0.70 on the placement, and the −13.97 de-panned
figure is what it cost.

**One window in the mix still fails and no guard measures it.** A 450 ms span around the landing
folds **−1.259 dB at 500 Hz**. Halving the side signal moves it 0.4 dB and shifting the pan 1.8 dB
moves it 0.14 dB, so neither narrowing nor repositioning reaches it — the side energy in that band
is intrinsic to the recording. *A prediction was made here that narrowing would bring it inside
1 dB, and it was wrong.* The bed, the lap and the shove all pass; only that window does not.

### What the shipped `.ogg` measures, which is not what the master measures

| file | balance | de-panned | fold | worst octave |
|---|---:|---:|---:|---|
| `wheat_sfx_v02.ogg` | +1.15 | −8.90 | −0.543 | −0.722 @ 16 k |
| `coins_sfx_v02.ogg` | −0.78 | −12.39 | −0.252 | −0.356 @ 4 k |
| `tally_knife_sfx_v01.ogg` | −0.43 | −12.26 | −0.253 | −0.384 @ 62.5 |
| `tally_leather_sfx_v01.ogg` | −0.80 | −12.31 | −0.256 | −0.299 @ 500 |
| `stone_block_sfx_v01.ogg` | −5.30 | −13.82 | −0.526 | −0.810 @ 500 |
| `barn_creaks_sfx_v02.ogg` | −0.21 | −11.20 | −0.318 | −0.555 @ 16 k |
| `room_sfx_v02.ogg` | +0.11 | −12.96 | −0.214 | −0.820 @ 2 k |
| `peasant_cloth_left_sfx_v01.ogg` | +6.40 | −14.11 | −0.653 | −0.869 @ 8 k |
| `peasant_cloth_right_sfx_v01.ogg` | −6.03 | −13.80 | −0.616 | −0.845 @ 8 k |

**Beds over the 1 dB per-band limit after encoding: 0.** Every file reports granulepos 1200000 at
48000 Hz = 25.000000 s exactly.

**Four needed correcting because of the encode and one was already over on the master.** The first
pass measured `peasant_cloth_left` −1.235 and `peasant_cloth_right` −1.068 at 16 kHz, `room` −1.010
at 2 kHz, and `tally_knife` −1.835 at 16 kHz. The three 16 kHz failures are Vorbis quantisation
noise in a band carrying 3.6 to 4.2% of the energy — **except `tally_knife`, which measured −1.860
on its own 24-bit master and was never the encoder's fault.** Fixed by summing the two channels
above 10 kHz on the three, and a small extra narrowing on `room`.

**That fix broke something a width check cannot see.** An FFT taken over the whole buffer is not
time-limited, so the 10 kHz sum leaked energy into every silent sample and `tally_knife` went from
91.7% digital silence to 0.0%. The silence mask was restored afterwards and all four re-encoded
and re-verified. *The lesson is that a repair aimed at one measurement has to be checked against
the others, and width and silence are measured by different tools here.*

### `room` is the only continuous bed, and its first loop pumped

25.000 s from 89.25 s of the master, with the following 1.5 s folded back over the head as an
equal-power crossfade. Step across the wrap **0.05 dB**, against a median adjacent-window step of
0.56 dB and a 90th percentile of 1.52. Three laps measure identical to one pass — **the seam is
smoother than a typical point inside the loop.**

**The build before it passed every check and pumped once a lap.** Its join was clean by sample
step — 1.7× the median, well inside tolerance — and its head was **3.09 dB quieter than its tail**.
The loop check had only ever compared continuity across the seam, never level, and a 3 dB step in
a continuous bed is heard as the bed breathing. *That metric is now part of the check.*

**A gain ramp was tried and discarded.** Correcting the level into the existing window is the
obvious repair and it does not work: a ramp's endpoints do not meet, and the corrected build
measured a wrap step 5.7× the median — it traded an audible level step for an audible click. The
window was reselected for level continuity instead.

### The stage finished 1.60 dB right of centre, and that is reported rather than fixed

Nothing sits further left than `wheat` at +1.19 dB, and the heaviest event in the scene is 5.30 dB
right. The two cloth beds do bracket the stage at ±6.9 dB as the table asked, but they are **22 dB
below the stone** and do not move the centre of mass.

Three readings of that, and the first is the one taken: **accept it** — the picture is asymmetric,
the grain is on the left and the clerk and the stone on the right, and 1.60 dB is not a large
offset. The alternatives are to **move `wheat` further left**, from 42% to the 20–25% region for
4–5 dB, or to **find a left-hand bed**, which is the one real hole in the arrangement.

### The cloth beds were narrowed before the request, not after the delivery

At 6.9 dB the per-band fold ceiling is **−9.18 dB**, and a bed at the −10 end of the usual
foreground band folds **−0.931 dB** — seven hundredths of a decibel of margin, on the two rows
placed furthest out. **So their target is −11 to −13 rather than −10 to −12**, which folds −0.862
to −0.76 and leaves room for a band to be wider than the broadband figure.

*That check cost one calculation and it is the whole point of having the ceiling table.* Build
Shrine lost a round to a bed that passed the fold limit at one placement and failed it at another
with no sample changed; Devotion's `candlelight` shipped with 0.024 dB of margin because nobody
looked until afterwards. Here the arithmetic ran before the number was written down.

**Delivered narrower still, at −16.40 and −15.55**, because the encode pushed both over at 16 kHz
and the repair was to sum the channels above 10 kHz. 3 to 3.5 dB inside the band rather than at
its edge, which costs stereo image on two beds that are 22 dB down and gains the margin the
ceiling table existed to protect.

#### The source was chosen on a measurement, after two cloth beds were rejected

Cloth was tried twice before this and rejected both times on the same ground: *it never gets good,
just disturbing sounds that nobody understands what it is.* The third attempt worked because the
third attempt measured the right thing first.

**A cloth recording that reads as cloth has almost nothing below 125 Hz.** Of five candidates
audited, three were exact dual mono — one with its right channel **34.1 dB** under its left — and
the fourth carried **77.9% of its energy below 125 Hz**. That is microphone handling noise, not
fabric, and an LF thump firing in time with every movement is precisely what makes a cloth bed
sound like a broken clip rather than a person. The source taken has **1.6% below 125 Hz** and is
genuinely stereo.

*It is face-mask fabric, not a smock*, and it is **the only bed in this action that is not CC0** —
Sonniss GameAudioGDC 2024, bundle 1 of 9. It was chosen on the measurement and not on what it is a
recording of, which is the whole of why it works.

**The right-hand gesture was in the wrong place first.** It was built well after the landing with
silence between, which answers no question a listener is asking: a man takes hold of a thing and
then sets it down, not the other way round. It starts at 16.420, **1.130 s before the block lands**
and finishing 0.370 s clear of it.

### What the stone's notches decide about the lap

**The block already carries three tally notches, the same marks as the stick.** It has been
assessed. That makes the thirty seconds a sequence rather than four unrelated noises — grain
poured, coins counted, tally notched, stone set down and accepted — and the request asks for that
ordering explicitly. A lap that tells the shape of one transaction is more interesting than
irregular spacing, and it costs nothing to specify.

**Delivered at 6.509, 13.758 and 21.821 s: grain assessed, coin assessed, stone accepted.** The
glove leads each bite by 0.43 to 0.46 s and finishes before the cut begins, which is the clearance
that makes the pair read as two actions rather than one.

**The third notch did not exist and this file said it did.** What had been filed as notch 3 came
out of the stone package and was labelled from a filename, `longer_stone_notch`. Measured, it is a
1.34 s low drag carrying **0.7% of its energy above 4 kHz**, where a real knife cut in this bed
carries **12.6 to 14.5%**. It is the block being shoved square — a good sound under the wrong
name, now recorded as that in `stone_block` — and a real `tally_knife` cut was placed at 21.821 to
be the acceptance the picture shows. *A label taken from a filename survived three rounds of
measurement because nothing measured was the thing the label claimed.*

### One bed causing another, which this project has never asked for

The stone landing on the board should make the coins and the loose grain jump. **The difficulty is
that the reaction belongs at the reacting object's position, not the stone's** — a rattle built
into `stone_block` would sound at 5.3 dB right while the coins sit at 1.1 dB right.

**The answer is the clock.** The request states absolute times: the block lands at a stated second,
and `coins` and `wheat` each carry their own sympathetic event a few tens of milliseconds later,
placed against the timeline rather than against each other's files. Every stem stays independently
buildable and re-cuttable, and the alignment survives any one of them being rebuilt. *It is the
cross-stem overlap ask from the previous round turned the other way round: there we asked two
stems not to collide, here we ask three to coincide.*

**A few tens of milliseconds was the wrong number and the reaction was inaudible.** Built at 30 ms
after the landing, the grain sat **31.2 dB** under the stone below 125 Hz and the coins **60.7 dB**
under it. Forward masking after a loud transient covers **100–200 ms**, so neither could be heard
at all. They are delivered at **210 ms** (grain, 17.675 s) and **250 ms** (coins, 17.800 s), which
clears the mask and still reads as caused by the landing at 17.550.

*This was found three times before it was understood.* Each time the check applied was
peak-of-the-new-thing against peak-of-everything-else, a margin of a few decibels was called
clear, and the result was reported as audible when it was not. **A peak-vs-peak margin is not a
measure of audibility**, and on this kind of event — something small arriving just after something
loud — it is not even weak evidence. The useful question is where the event sits relative to the
masker in time and in band, which is what the numbers above answer.

### Three things with no sound, recorded as decisions

> **The lantern is gone too, as of the 2026-10-20 artwork.** The note below is void on the same
> terms as the candle note under it. **Two of the three survive** — the ledger is still there at
> 57–78% and still has no page turns, and nobody still breathes.

**The lantern at 31–35%** is unlit and silent. **The ledger at 60–76%** has no page turns, left out
because another action already has a page-turn bed and two actions sharing a sound is worse than a
silent book. **And nobody breathes** — three men at a table in total silence, where Devotion's own
record calls its breathing bed the thing that keeps a body in a picture that would otherwise be a
room. *The count was wrong here until 2026-10-20: this file said four.* The picture has the
collector and two peasants, one bearing grain and one bearing the stone. The fourth was a
blurred, frame-cropped shape at the left edge that reads just as well as the grain-bearer's own
shoulder, and it was never counted against the picture before being written down.

*The candle is gone.* The previous artwork had one at 78.5% and this file recorded its silence as
a decision; the new picture has no candle and the note is void. Light now comes from the window.

*And so is the lantern, one artwork later.* **Two of the three light sources this file has filed
as deliberate silences have now been painted out from under it**, each time by a regeneration
nobody expected to move them. The window has been left as the only light in the frame twice
running, which is the one thing about this scene that has held. A silence recorded against a
thing in the picture is only as durable as the picture, and this section now carries two dead
notes out of five — which is an argument for writing them against the *scene* rather than against
a percentage, not an argument for stopping.

### Not one sample of the previous version survives, and the audit is why

Every bed here was rebuilt from a different recording at v03. Four of them had to be.

| bed | what the filed record said | what was actually in the stem |
|---|---|---|
| `wheat` | 556974 lucasfuchs, *Pouring grain or seeds* | 199930 thedapperdan, *Rice Pour* |
| `barn_creaks` | 433999 snake16547, *Old wood door creak* | `moniker_subriquet-…-171122.mp3` — no URL, no licence, lossy |
| `tally_leather` | a Sonniss gloves recording, under bundle terms | 388307 isbeorn, *creaky-leather* — **CC0** |
| grain scatter | *(nothing — it was new)* | 68343 Robinhood76 — **CC BY-NC 4.0** |

**Every one of those filed records carried a sha256 that still matched its own `.ogg`**, so the
integrity tests passed throughout and would never have caught any of it. A hash proves the file
has not changed; it says nothing about whether the `source` field describes it. *Any filing pass
has to re-derive provenance from the stem in hand rather than from the record.*

**The stone and the leather were proved by cross-correlation rather than by asking.** The stone's
three elements read r = +1.0000, +1.0000 and +0.9999 against named in-points in two CC0 uploads.
The leather's four gestures read +0.8663, +0.9064, +0.8617 and +0.8773 against isbeorn and +0.1398
to −0.1772 against the Sonniss file the record named — 0.86 rather than 0.99 being what a
44.1 → 48 kHz resample costs, and against 0.13 it is not ambiguous. *That one was the good kind of
surprise: the bed is CC0 and needs no bundle-terms tag.*

### Two NonCommercial sources got this far on measurement alone

`325529` (a wooden chair, considered as the stone nudge) was measured in full, ranked against four
alternatives and written into a build prompt before its licence page was opened. **It is CC BY-NC
3.0.** `68343` (the grain scatter) went further still: it was built into a bed, mixed, delivered
and auditioned, and was caught only by the provenance audit. **It is CC BY-NC 4.0.**

Both are gone and the rule is now explicit: **check the licence before measuring anything, not
after.** All nine sources behind this lap were verified against their own pages on 2026-10-20
before a stem was encoded. Eight are CC0; the ninth is the cloth, under Sonniss bundle terms.

---

## Convention for the actions still to come

State the layout **in the request**, as a table of this shape, before the stems are built. Then
measure the delivery against it and record the result here. Three rules that came out of the
Produce Stone and Produce Wheat comparison:

1. **Centre is for what is genuinely everywhere** — the continuous base, and anything built as a
   field rather than a point. Do not pan something to the centre; leave it there.
2. **The player's own worker gets one position, and every stem of it shares that position
   exactly.** Produce Stone has it at 4.0 dB left, Produce Wheat's binder at 0.8 dB right across
   all four of her gestures, and Devotion's monk is the agreed exception — three positions over
   3.5 dB, because a robe filling half the frame is not a point source. *The rule was written on
   Produce Wheat breaking it*: its binder's handling sat at 1.6 dB right and her settling and
   repositioning at 6.1 dB left, because those gestures had been merged into a stem with the
   background workers. Fixed in the rebuild.
3. **Separate people get separate positions**, so distance shows in placement as well as in
   level. Five sources at one spot is the Produce Stone fault above, and two pan slots shared by
   four people was the Produce Wheat one — four cutters now stand at 6.89, 5.81, 4.77 and
   4.01 dB left.
4. **Movement is recorded as a path, and five beds in the tree move.** All five are Allocation's
   monks and they are the exception, not the rule — everything else here is static, and that was
   measured rather than assumed. The by-type Allocation package showed why the question has to be
   asked: its doors, locks and stairs *looked* like movement across a stem and were not, being
   separate events standing still at separate positions, each sweeping under 0.4 dB while it
   sounded, and its footsteps snapped between pan values that repeated exactly, which is a gait
   rather than a journey.

   **So the first question about a moving sound is whether it needs to move.** Most apparent
   motion in a scene is several sources standing in different places, and that is cheaper to
   build, cheaper to balance and does not have the problems below. Allocation's monks pass that
   question because each really is one person crossing the frame, and filing them by journey is
   what made the movement expressible at all.

   When something genuinely should traverse, record it as `6.2 dB L -> 5.8 dB R over 4.1 s` in
   the motion column, and verify it by measuring balance in windows *inside* the run, with a
   straightness figure so a real sweep can be told from a jump between two fixed positions. Three
   constraints come with it. The board has **no runtime panner for beds** — one gain node each —
   so motion is baked into the stem and cannot be automated afterwards. A traversing source that
   loops **teleports back to its start every 35 s** — but only if it is still audible when it
   gets there. Allocation's five monks travel and loop safely because each stem begins and ends
   in silence, so the jump happens where there is nothing to hear; a source that is *continuously*
   audible while it travels either makes a round trip inside the loop or is filed `loop: false`,
   the same trade as the owl. And a sweep that reaches the
   edges pays the mono-fold cost there, so keep it inside ±6 dB unless the edge is the point.

   *One number per stem is wrong for any stem holding more than one placed event*, which is the
   other thing the doors measurement showed: that bed read −0.23 dB overall, which would have
   filed it as centre, while containing three doors at +13.1, −5.5 and −8.0 and nothing at centre
   at all. **That is now settled by the structure rather than by the notation**: filing by journey
   gives each stem one subject, so its events agree with each other by construction, and the
   Allocation table above breaks the five monks out event by event instead of quoting one average
   per stem. Where a stem still holds several placed events, break them out that way.

5. **The action's own artwork decides the layout, and it decides it per action.** The picture is
   on screen while the sound plays, it already settles where everything is, and following it
   costs nothing. Horizontal position in frame sets the pan; apparent distance sets level and
   width, never pan; anything not in the picture is free.

   *Agreed 2026-10-18: the picture wins over consistency between actions.* The player's own
   worker therefore has no fixed place across the game — Produce Stone's stonecutter is 4.0 dB
   left because the lamp and the cutting face are on that side, and Produce Wheat's binder is
   0.8 dB right because her hands are at 55% of her frame. Rule 2 binds inside one action, not
   across them.

6. **A stem holding more than one placed event gets a number per event, not per stem.** Both
   balance and de-panned width. This was written after Allocation's doors, where a bed reading
   −0.23 dB overall held three doors at +13.1, −5.5 and −8.0 and nothing at centre — and then
   had to be written again after Build Shrine's corvids, where the same mistake was made *by this
   file*: a single prescribed balance for a bed holding four calls in two places put two of them
   at **16.1 dB right** while the whole-stem figure read exactly on target.

   **The width figure has the same hole.** De-panning by a stem's whole-stem energy ratio leaves
   an event at a different balance still partly panned, and that residual is counted as side
   energy — so a bed of four mono points 13.5 dB apart reported **−11.45 dB of width it did not
   have**. A de-panned width means something only for a stem whose events share one position.

7. **The reading is done against the artwork before the stems are built, not inferred from the
   delivery afterwards.** It produces a table of dB figures that the delivery is then measured
   against. Asking the supplier to read the picture and build to its own reading would put the
   layout and its verification in the same hands, which is the arrangement every round of review
   so far has had to correct.

8. **This file is updated at filing, in the same change as the beds.** Not when the request goes
   out, not when the delivery is reviewed — when the `.ogg` files land in `sfx/ambient/`. The
   section's status line moves from *prescribed* to *delivered and filed*, the table gains its
   delivered column, and **every sentence written in the present tense about the beds that were
   replaced is put into the past**, with the delivered figure beside it.

   *That last clause is the one this rule exists for.* On 2026-10-19 three of the six tables here
   carried headings saying "now fixed" and "what the beds measured before" over bodies still
   reading "it sits at 4.1 dB left" and "the ox cart is currently almost centred" — about files
   that had been retired days earlier. Produce Wheat's whole section still said *not yet
   delivered* with thirteen beds in the tree. None of it was wrong when written; all of it was
   wrong by the time anybody read it, and nothing in the repository disagreed out loud. A stale
   layout table is the same disease as a stale bed count, with none of the guard that catches
   one: `test_the_prose_count_of_beds_is_the_number_of_beds` can check an integer and cannot
   check a tense.

   **So the check is the status table at the top of this file.** It is the one place where
   *prescribed* and *delivered* are written as a fact per action rather than buried in prose, and
   it is the first thing to move.

Anything past ±6 dB is a decision, and the reason goes in the table.
