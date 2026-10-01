# The seal briefs

One file per seal, **word for word as it was sent**, each marked `<!-- archival: -->` — which is
the mechanism `generate_duty_art_lab.py` already has for exactly this: "somebody's text as they
wrote it, kept because it produced a particular picture… it gets a button and no substitution".

`<!-- produces: -->` names the file each one made. That is what `attribution.json`'s
`reproducibleBy` points at, and what the duty art board matches a seal to.

## There is no shared brief here, and that is a finding rather than an omission

The action-card briefs in `../` are one text with `{{LEFT_SUBJECT}}` and friends substituted in,
because they genuinely are one brief run against eight duties. The seal briefs look like they
work the same way — the same section headings, the same vocabulary — so the obvious move was to
pull the common part out into a template.

Measured, they do not. Splitting the four on their `======` rules and comparing word by word:

| section | compared | words the same |
| --- | --- | --- |
| VERY THIN OUTER EDGE | red wheat vs grey wheat | 67% |
| CAMERA / PRESENTATION | red wheat vs grey wheat | 60% |
| LIGHTING | red wheat vs grey wheat | 59% |
| REAL …CONSTRUCTION | red wheat vs red stone | 46% |
| REAL SEAL CONSTRUCTION | grey wheat vs grey stone | 41% |
| COLOR / MATERIAL | grey wheat vs grey stone | 33% |
| SURFACE / AGE | grey wheat vs grey stone | 31% |
| SMALL-SIZE READABILITY | grey stone vs red stone | 31% |
| FINAL GOAL | grey wheat vs grey stone | 24% |
| STONE MOTIF | grey stone vs red stone | 13% |

Nothing is near-verbatim. These are four separately written prompts that share a **vocabulary**,
not one brief with holes in it. A template built from them would be a document that never existed
and never produced anything, and every record pointing at it would be approximately true — which
is the one thing a provenance record must not be.

## What the vocabulary actually is

Worth knowing when writing the next one, because the phrasing is not equally good everywhere and
the later files are not the better ones. Reading the diffs rather than the similarity scores:

- The differences between the red and grey versions of EDGE, LIGHTING and CAMERA are almost all
  **drift**, not intent: `centred`/`centered`, `focal length`/`focal-length`, `No coloured
  reflections`/`No colored light`, a line moved. Nothing there distinguishes a red seal from a
  grey one.
- Two differences are not drift, and both are **losses in the grey wheat version**. It dropped
  the lip figure — "approximately 4–6% of the seal radius" became "a narrow irregular outer lip",
  so the one quantity in that section went missing — and it dropped `No black background` from
  the exclusions. The grey stone brief later restored the lip figure; the grey wheat one never
  did.
- The red wheat brief has the most specific LIGHTING of the four ("small specular highlights on
  polished wax; deep but soft shadows inside the impressed recesses"). The grey wheat one replaced
  it with a vaguer list.

So the best phrasing for a new seal is mostly the **red wheat** brief, with the grey stone brief's
COLOR / MATERIAL section when the seal is a resource.

## Two things in here are stale and stay stale

**"approximately 55–70 px wide."** True when the Tithe tokens were 64 and the duty seals 46. The
board has drawn both at 78 since the seals went diagonal, so these briefs ask for readability at a
size nothing uses. Left as written.

**The edge proportion is not the figure the repository enforces.** These ask for an impressed face
of 88–92% of the diameter plus a 4–6% lip, which is about where the wax ends on the *seal*.
`SOLID_FRACTION` in `../../action_board/geometry.py` is 0.906 and measures something else — how
much of the *square PNG* the drawing fills — and the generator does not hit any stated target
reliably: the nineteen filed so far came back between 0.914 and 0.998 of their squares. That is
why `tools/duty_art/file_seals.py` corrects every one of them about its own centre, and why the
master is kept. Do not try to fix this by rewording a brief.

## The reference chain

Three of the four were built from the one before it, which is why they are numbered in generation
order rather than by duty. `<!-- reference: -->` records it per file:

```
red PRODUCE wheat  →  grey TAKE TITHE wheat  →  grey TAKE TITHE stone  →  red PRODUCE stone
                                  └──────────────────┴──→  grey TAKE TITHE silver
```

Silver branches rather than continuing the line: it was told to match the grey wheat AND stone
together, so it is the first one written against a family rather than against a single picture.
Every brief names its own reference in its opening sentence, so the header is a reading of the
text rather than a note kept beside it.

Note that the download order of the images disagrees with this: the grey pair reached Downloads
before the red pair. The chain above is what the briefs themselves say, and the pictures agree
with the briefs — the red wheat seal has the three stalks its brief asks for and the grey one the
single stalk it was told to reduce to.

## What produced the v01 seals is not recorded

Fourteen duty seals and two resource seals were filed before any brief was kept. Their
`reproducibleBy` says so in as many words rather than guessing, and the duty art board shows them
without a brief. If the texts turn up, they go here with the same headers.
