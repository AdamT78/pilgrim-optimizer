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
          stone/             pilgrim_stone.svg, [gi_stone_block.svg awaited]
          silver/            pilgrim_silver.svg, [gi_two_coins.svg awaited]
          cornucopia/
        actions/             <duty>_<n>.svg -- see below
      portraits/
        leaders/             HELD -- .gitignore, nothing committed
      frames/
        player_board/        HELD -- .gitignore, nothing committed
      ui/
        buttons/
        markers/             merchant_wagon.svg
        miscellaneous/

The four marks the shortlist prototype opens with are Font Awesome's **Hands Praying** and **Wheat
Awn** (CC BY 4.0) and Game-icons' **Stone Block** by Lorc and **Two Coins** by Delapouite
(CC BY 3.0). The first two are here. The second two are `awaited`: the prototype links them rather
than embedding them, so their geometry exists in no file we hold — their licences are cleared and
recorded, and dropping the two SVGs into the slot directories is all that remains. The picker
offers them the moment they land.

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

The precedent for `held`: the afilinkov NPC portraits are personal-use only and their terms forbid
use in *any* project, so nothing derived from them is committed. `portraits/leaders/` and
`frames/player_board/` each carry a `.gitignore`, because a held file sitting in the asset tree is
one wholesale `git add` away from being committed and a note in a README does not stop that.

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
committed**. If they came from the same source, the register above applies to them too — change
their `state` to `present` in `attribution.json` and fill in the credit fields, and the checker
will stop reporting them.

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
