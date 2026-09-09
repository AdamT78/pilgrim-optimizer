# UI 2.0 assets

Authored and third-party source material only. **Nothing generated belongs here** — the boards,
tiles and panels are built by the generator and rendered on demand, and a folder of exported board
images would be a second copy of the truth that starts drifting the first time a constant changes.
What lives here is what a generator cannot produce: drawings, portraits, frames, bought icons.

    assets/
      attribution.json                 licence and credit, one entry per file -- the record
      gen_credits.py                   renders the two notices below from it
      THIRD-PARTY-NOTICES.md           generated; the record kept with the assets
      credits-third-party-icons.html   generated; ships in the game's credits screen
      assets.json                      ink boxes for the rasters
      verify_assets.py                 enforces both contracts
      icons/
        population/          one directory per SLOT, not per subject
          serf/              serf_wide_hat.png
          acolyte/           acolyte_hood_cross.png, acolyte_tied_cloak.png
          other/
        resources/           one directory per slot, as population
          piety/             pilgrim_piety.svg, fa_hands_praying.svg
          wheat/             pilgrim_wheat.svg, fa_wheat_awn.svg
          stone/             pilgrim_stone.svg, gi_stone_block.svg
          silver/            pilgrim_silver.svg, gi_two_coins.svg
          cornucopia/
        actions/             <duty>_<n>.svg -- see below
      portraits/
        leaders/             leader_female_hooded_sketch.png, leader_male_hooded_sketch.png
      frames/
        player_board/        player_frame_gothic_red_01.png
      ui/
        buttons/
        markers/             merchant_wagon.svg
        miscellaneous/

The four marks the shortlist prototype opens with are Font Awesome's **Hands Praying** and **Wheat
Awn** (CC BY 4.0) and Game-icons' **Stone Block** by Lorc and **Two Coins** by Delapouite
(CC BY 3.0). All four are here. The Game-icons pair arrived as the white-on-black download — a
full-canvas black rectangle with the glyph in white on top — so the background path is stripped and
the glyph stores `fill="currentColor"`, which is what lets the renderer recolour it instead of the
file fixing today's palette.

## Why population is split by slot

The proposed tree had `population/serf_wide_hat.png` beside `population/acolyte_hood_cross.png`,
which reads fine and enumerates badly. A renderer that offers "pick a serf icon" has to answer
*which files are candidates for this slot*, and with one flat directory the only answer is a
filename prefix — a convention nothing enforces and a rename breaks. One directory per slot makes
the answer a directory listing: `assets/icons/population/serf/*` **is** the set of serf icons. Add
a file, it appears in the picker; no manifest to update, no prefix to remember.

The same logic applies to every slot that takes alternatives. Resources moved to the same shape
once a picker needed to enumerate them: `icons/resources/stone/*` is the set of candidate stone
marks, whatever their format. Filenames carry their source as a prefix — `pilgrim_`, `fa_` — so
where a mark came from is visible in a directory listing rather than only in this file. Leader
portraits are already under `portraits/leaders/` for the same reason.

A slot directory may hold **SVG and PNG side by side**; the renderer picks by extension. That is the
point of enumerating a directory rather than a hardcoded list.

## Duty action icons

Exported from the generator by `../_scratch/export_assets.py`, not traced: the file and the board come
from one drawing, so they cannot drift. Each is the **mark alone** — the pill behind it on a duty
tile is the tile's furniture, not the icon — on a `-16 -16 32 32` viewBox.

The proposed names assumed one icon per duty. The board does not work that way: five of the eight
duty tiles carry two acts and three carry one, thirteen in all. So they are named
`<duty>_<n>.svg`, numbered in the order the tile draws them:

| duty | icons |
| --- | --- |
| allocation | `allocation_1` |
| build_roads | `build_roads_1` |
| clerical | `clerical_1` (devotion), `clerical_2` (silversmith) |
| construct | `construct_1` (build), `construct_2` (road) |
| give_alms | `give_alms_1`, `give_alms_2` |
| ordination | `ordination_1` (serf → abbey), `ordination_2` (→ city) |
| produce | `produce_1` (wheat), `produce_2` (stone) |
| taxation | `taxation_1` |

Two of these are known to want replacing: `construct_2` and `build_roads_1` are the **same path**,
so changing one changes both, and `taxation_1` reads as Justice rather than a purse.

## Provenance

`attribution.json` is the record, one entry per file, and it is the only place licence facts are
written by hand. Two notices are generated from it by `gen_credits.py` and must not be edited:

    THIRD-PARTY-NOTICES.md            the record kept with the assets
    credits-third-party-icons.html    the fragment that ships in the game's credits screen

Generating the shipped credit rather than writing it is the point. A credits screen gets written
once; the asset tree keeps moving. Deriving one from the other means the game cannot end up
crediting artwork it no longer contains, or shipping artwork it never credited.

Each entry carries a **state**, and the states are what the tooling acts on:

| state | meaning |
| --- | --- |
| `present` | in the tree, licensed, credited |
| `awaited` | licence cleared, file not here yet — credited in the record, **not** in the shipped credits, because crediting art the build does not contain is a claim to have used something you have not |
| `held` | no licence on record. Not committed, must not ship |

CC BY wants five things — title, creator, source, licence with a link, and a statement of what was
changed. The register this file used to carry named only the creator and the licence, which
satisfies neither version of the licence, so every entry now carries all five. Resizing,
recolouring, converting to PNG and Base64 embedding all preserve the obligation; none of these
licences is ShareAlike, so none of them reaches the renderer, the game, or unrelated artwork.

Nothing is `held` at present. The precedent stands, and it is the afilinkov NPC portraits: those
are personal-use only and their terms forbid use in *any* project, so nothing derived from them is
committed, and none of it is in this tree. If something arrives without a licence, give it a `held`
entry and a `.gitignore` in its directory — a held file in the asset tree is one wholesale
`git add` away from being committed, and a note in a README does not stop that.

The leader portraits and the player-board frame are `openai-generated`, which is a rights basis
rather than a licence: rights in the output are assigned to the user under the OpenAI Europe Terms,
so they may be used, modified and shipped commercially, and no attribution is owed. Two things
follow that are easy to get wrong. They are **not** CC0, public domain, or royalty-free stock, and
should not be described that way. And the unmodified output likely carries no copyright protection
in Sweden, so it can be used but is weak to defend — substantial human-authored redesign, or the
wider player-board composition, may qualify separately. The originals must never be described as
manually illustrated by a human.

### Register: `openai-generated`

    Files:      icons/population/serf/serf_wide_hat.png
                icons/population/acolyte/acolyte_hood_cross.png
                icons/population/acolyte/acolyte_tied_cloak.png
                portraits/leaders/leader_female_hooded_sketch.png
                portraits/leaders/leader_male_hooded_sketch.png
                frames/player_board/player_frame_gothic_red_01.png

    Source:     Generated with OpenAI image generation in ChatGPT for the Pilgrim UI project.
    Rights:     Output rights assigned to the user under the OpenAI Europe Terms of Use.
    Use:        Commercial use, modification, embedding and distribution as part of the game.
    Attribution: None known or required.
    Exclusivity: Not exclusive. Similar AI output may exist or be generated for others.
    Copyright:  Likely not independently protected by copyright in Sweden while wholly
                AI-generated. Human-authored modifications, or the broader UI composition,
                may receive protection if they satisfy the originality requirement.
    Notes:      Do not describe the original images as manually illustrated.

The practical consequence of the copyright line: these three can be used and modified freely, but
they are weak to defend. A substantial manual redesign — silhouette, proportions, line work, the
face opening — could make the human-authored changes protectable; cropping, resizing, Base64
encoding or a mechanical trace to SVG almost certainly would not. Nothing here depends on that, but
it is worth knowing before these become the game's signature marks.

The frame is **coordinate-bound**, not content-normalised: it is a transparent overlay placed into
a defined rectangle, so its native aspect must be preserved and it must never be stretched with
`preserveAspectRatio="none"`. Its production cut is 1024x444 against a 1905x826 master, which holds
the aspect to 2.30631 against 2.30630. The portraits are coordinate-bound for the same reason —
they are placed into the portrait disc rather than cropped to their ink, and cropping a portrait to
its ink moves the face. Any resource symbol laid on top of the frame keeps its own separate
attribution.

## Masters and production files

`_masters/` holds the full-resolution originals; the files in the slot directories are the
production cuts the renderer reads. The leading underscore keeps `_masters/` out of any glob that
enumerates a slot.

The population icons draw about 22 px on a player card. Their masters are 1254² at ~360 KB each —
about 70x linear overkill, and **1,421 KB** of Base64 for the three. Cut to the alpha box at a
common ink height of 120, still ~5x the display size, they are ~11 KB each and **46 KB** embedded.
Thirty-one times smaller, with no visible difference at board scale.

Keep the masters: a 120 px cut cannot be re-derived into one.

## Checking

`verify_assets.py` enforces the contract in `../hybrid-svg-png.md` rather than trusting it —
declared boxes against measured ones, untrimmed canvases, and whether a normalisation group agrees
on the dimension it normalises. Run it before an asset is used, not after a layout is built on it.

    python3 verify_assets.py            # check
    python3 verify_assets.py --write    # recompute assets.json from the files
    python3 gen_credits.py              # rewrite the two notices
    python3 gen_credits.py --check      # fail if either notice is stale

`verify_assets.py` also walks the tree and fails on any file with no `attribution.json` entry that
matches no `projectOwned` pattern. That check catches the silent failure: a file arrives, gets
used, ships, and afterwards nobody can say where it came from. An asset with no entry is a problem
even when its licence would have been fine — the record is the obligation.
