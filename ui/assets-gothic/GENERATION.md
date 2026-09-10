# Generating more of this artwork

## The short answer about seeds

Don't bother chasing them. OpenAI's image endpoints expose **no seed parameter at all** — the seed exists inside the model but is never handed to you, and ChatGPT deliberately hides it. The `gen_id` trick that worked with DALL·E 3 in 2023 does not apply to the current generation.

More to the point, a seed would not save you even if you had one. Every vendor that *does* expose seeds says the same thing: a seed reproduces an image only while the model version, the exact prompt, and every sampling parameter stay identical. Midjourney — the most transparent about this — puts its own seeds at "99% identical" within a version and warns against relying on them across sessions. Model updates are fatal to reproducibility, which is why Black Forest Labs sells *pinned* endpoints as a separate product.

So a saved seed is not a backup. **The PNG is the master, and the only master.** That is why the whole tree is committed: this repository is the backup. Losing `frame_base.png` means the frame is gone; asking again produces different artwork, not the same artwork.

## What is actually worth saving

Not the recipe for reproducing an asset. The recipe for producing the **next** one that matches.

That is a real need here and it will recur: a fifth seat colour, a third and fourth leader portrait, a new frame, another resource. Style continuity is the problem, and the two halves of it are the visual style and the technical fit. The second half is the one that quietly breaks things, because artwork that looks perfect can still be unusable.

## The technical spec any new asset must meet

Measured from the current assets, not aspirational.

| Class | Canvas | Notes |
| --- | --- | --- |
| Frame | 1905 × 826 | openings must land where the template expects — see below |
| Portrait, board | 640 × 640 | square; the template fits it into a 448 box |
| Portrait, reveal | 1254 × 1254 | same artwork, larger cut |
| Population mark | ~210–230 wide × 210 | serf and acolyte are near-square |
| Resource icon | ~220–300 × 230–270 | each differs; the template fits by aspect |

Every asset is **RGBA with a real alpha channel and no background**. The frame is essentially all soft edge — only 0.2% of its pixels are fully opaque — which is why the layer split is by hard alpha and why nothing downstream may assume crisp edges. No baked drop shadows: the board draws its own.

**The frame's openings are the hard constraint.** The template's coordinates are calibrated to the holes in `frame_base.png`, and the standing rule is that replacement artwork does not get to move them:

| Opening | Measured in frame_base.png |
| --- | --- |
| Portrait | 423 × 390, centre (409.0, 359.5) |
| Upper panel | x 669–1781, y 215–384 |
| Resource 1–4 | ~210 × 175 at y 435–608, centres x 811.5 / 1078.5 / 1355 / 1628 |

A new frame whose portrait opening sits 30 px left is not a new frame; it is a request to re-calibrate the template, and the answer to that request is no. Check a candidate before doing anything else:

```
python3 ui/render/check_frame_fit.py --candidate path/to/new_frame.png
```

## The visual style, by class

The classes do **not** share one style, and matching the wrong one is the usual mistake. Say which class you are making.

- **Population marks** (serf, acolyte): sepia and bistre engraving, visible cross-hatching, warm brown ink on nothing. Bust-length, slightly turned, no ground shadow.
- **Resource icons**: mixed on purpose. Piety and grain are the same engraving hand as the population marks; stone and silver are painterly and rendered with real form and highlights. Match the neighbour, not the average.
- **Portraits**: greyscale graphite and charcoal, hooded, head-and-shoulders, three-quarter to near-frontal, no background at all.
- **Frame**: gilt gothic architecture, gold banding in a narrow hue band around 25–44°, grey stonework, with a coloured drape at the left.

## A prompt scaffold

Paste the closest existing asset alongside this and say "match this". A reference image does far
more than adjectives.

Attach the **file from this repository**, at full resolution, with its alpha intact -- one sibling,
occasionally two. Not a contact sheet and not a screenshot: a downscaled thumbnail composited onto a
background teaches the model exactly the two things you do not want, low resolution and an opaque
ground. And because the classes are three different hands, attaching all of them invites an average
that matches none of them. Say in words that the reference is transparent and the output must be
too, since chat interfaces composite alpha onto white before showing it and the model can learn
"white background" from your own reference.

> A single [CLASS] for a 14th-century English board game, in the same hand as the attached reference: [STYLE LINE FROM THE TABLE ABOVE].
> Subject: [what it is].
> Transparent background, no scene, no ground, no cast shadow, no border, no text.
> Square framing with the subject centred and a small even margin.
> Output at [CANVAS] pixels, PNG with alpha.

Then, because the model will usually ignore at least one of those:

> Re-render with a genuinely transparent background and nothing behind the subject.

## Accepting a new asset

Nothing here is judgement; it is four commands.

1. `python3 ui/render/check_frame_fit.py --candidate <new frame>` — frames only, and first, because a misaligned opening ends the conversation.
2. `python3 ui/render/split_frame_layers.py --frame <new frame> --preview` — look at the false-colour map before trusting the split.
3. `python3 ui/render/recolor_seat_layers.py` then `--check` — rebuilds every derived colour and asserts the lit and dim bands still clear each other.
4. `python3 ui/render/check_frame_layers.py` — the layered board must still reproduce the single-image board pixel for pixel.

## If you want a record of where these came from

Save the ChatGPT conversations themselves, or paste the prompts that worked into this file under a heading per class. That is worth doing for continuity, not for reproduction — and it is the honest version of what you were reaching for when you asked about seeds. `attribution.json` already records that the originals came from ChatGPT across several sessions with no prompt or seed on record, and which 13 files that makes irreplaceable.
