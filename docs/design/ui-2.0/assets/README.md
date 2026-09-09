# UI 2.0 assets

Authored and third-party source material only. **Nothing generated belongs here** — the boards,
tiles and panels are built by the generator and rendered on demand, and a folder of exported board
images would be a second copy of the truth that starts drifting the first time a constant changes.
What lives here is what a generator cannot produce: drawings, portraits, frames, bought icons.

    assets/
      icons/
        population/          one directory per SLOT, not per subject
          serf/              serf_wide_hat.png
          acolyte/           acolyte_hood_cross.png, acolyte_tied_cloak.png
          other/
        resources/           one directory per slot, as population
          piety/             pilgrim_piety.svg, fa_hands_praying.svg
          wheat/             pilgrim_wheat.svg, fa_wheat_awn.svg
          stone/  silver/  cornucopia/
        actions/             <duty>_<n>.svg -- see below
      portraits/
        leaders/             leader_male_01.png, leader_female_01.png
      frames/
        player_board/        frame_01.png
      ui/
        buttons/
        markers/             merchant_wagon.svg
        miscellaneous/

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

Exported from the generator by `/tmp/export_assets.py`, not traced: the file and the board come
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

Every file needs a licence on record before it is committed, because some of it cannot be. The
precedent: the afilinkov NPC portraits are personal-use only and their terms forbid use in *any*
project, so nothing derived from them is committed. The merchant wagon is a Noun Project icon by
**Alzam** and its attribution travels with the file.

| path | source | licence |
| --- | --- | --- |
| `icons/actions/*.svg` | drawn for Pilgrim, exported from the generator | project |
| `icons/resources/*/pilgrim_*.svg` | drawn for Pilgrim, exported from the generator | project |
| `icons/resources/*/fa_*.svg` | Font Awesome Free 6, Fonticons Inc. | **CC BY 4.0** |
| `ui/markers/merchant_wagon.svg` | Noun Project, **Alzam** | attribution required |
| `icons/population/**` | OpenAI image generation | `openai-generated`, see below |
| `portraits/leaders/*` | uploaded 2026-09-09 | **unverified** |
| `frames/player_board/frame_01.png` | uploaded 2026-09-09 | **unverified** |

### Register: `cc-by`

    Files:      icons/resources/piety/fa_hands_praying.svg   (Font Awesome, hands-praying)
                icons/resources/wheat/fa_wheat_awn.svg       (Font Awesome, wheat-awn)

    Licence:    CC BY 4.0. Font Awesome Free 6, Fonticons, Inc.
    Attribution: REQUIRED, and must ship with the game -- a credits line, not a code comment.

Anything under CC BY carries an obligation the `openai-generated` population icons do not. Keep the
two classes visibly apart in this register, because the moment they blur, the credits line gets
forgotten.

### Register: `openai-generated`

    Files:      icons/population/serf/serf_wide_hat.png
                icons/population/acolyte/acolyte_hood_cross.png
                icons/population/acolyte/acolyte_tied_cloak.png

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

`portraits/leaders/*` and `frames/player_board/frame_01.png` are still unverified and **not
committed**. If they came from the same source, the register above applies to them too.

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
