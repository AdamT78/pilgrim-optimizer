# Duty Tiles (v2.7 Sandbox Scope)

## Core model

The sandbox now separates:

- physical mancala position
- duty category identity

City is **not** a duty tile.

Duty tiles are the 8 non-city positions:

- `north`
- `north_east`
- `east`
- `south_east`
- `south`
- `south_west`
- `west`
- `north_west`

## Duty categories

The category set is fixed and complete:

- `produce`
- `clerical`
- `give_alms`
- `allocation`
- `build_roads`
- `construct`
- `ordination`
- `taxation`

Each category must appear exactly once in a layout.

## Scenario-defined layout

Real Pilgrim randomizes these tiles. For deterministic engine runs, the layout is defined by
scenario JSON:

```json
"duty_tiles": {
  "north": "produce",
  "north_east": "clerical",
  "east": "build_roads",
  "south_east": "construct",
  "south": "give_alms",
  "south_west": "ordination",
  "west": "allocation",
  "north_west": "taxation"
}
```

If omitted, the same mapping above is used as deterministic fallback.

For setup-file authoring convenience, a seeded setup generator now exists:

`python3 -m pilgrim.cli generate-setup --players <2|3|4> --seed <int> --output <path>`

No randomization occurs inside scenario loading, rules transitions, or search.

## Implemented vs deferred categories

Implemented action systems:

- `produce`:
  - `produce_wheat`
  - `produce_stone`
- `clerical`:
  - `clerical_devotion`
  - `clerical_silversmith`
- `give_alms`:
  - `give_alms_paid` (pay silver/wheat)
  - `give_alms_donate_building` (donate one active building)
- `ordination`:
  - `ordination` (ordered `ordain`/`mission` steps)
- `allocation`
- `build_roads`:
  - `build_roads_deferred` (scaffold only; no spatial placement yet)
- `construct`:
  - `construct_building` (acquire 1 market building by paying stone = building level)
  - `construct_building_and_road_deferred` (real building acquisition + deferred road part)
  - `construct_road_deferred` (road-only scaffold)
- `taxation`:
  - `taxation` (step-1 chosen resource + step-2 bonus resources from other majority tiles)

Enhancement mapping reference:

- `docs/rules/DutyEnhancements.md` documents Duty-related Special Activity/building effects as
  metadata registry entries (including implemented vs deferred status).

Deferred category systems (valid in layout, no non-tithe action yet):

- none

## Canonical Action Names

Duty tile categories are not action names. Use the following concrete action names:

| Duty tile | Canonical action names |
| --- | --- |
| `produce` | `produce_wheat`, `produce_stone`, `tithe` |
| `clerical` | `clerical_devotion`, `clerical_silversmith`, `tithe` |
| `build_roads` | `build_roads_deferred`, `tithe` |
| `construct` | `construct_building`, `construct_building_and_road_deferred`, `construct_road_deferred`, `tithe` |
| `give_alms` | `give_alms_paid`, `give_alms_donate_building`, `tithe` |
| `ordination` | `ordination`, `tithe` |
| `allocation` | `allocation`, `tithe` |
| `taxation` | `taxation`, `tithe` |

## Runtime implications

- Majority/parity/minority is still computed on the selected **physical** duty position.
- Duty value is still derived from the selected position relation.
- Available non-tithe actions come from the selected position's **category**.
- For `produce`, one explicit option is chosen: `produce_wheat` or `produce_stone`.
- Produce duty value cannot be split across resources in one action.
- Produce special-activity bonuses (Fields / Stone Mason) add produced resources and do not
  change duty value.
- Produce building bonuses are now implemented:
  - Well adds `+1 wheat` to `produce_wheat`
  - Quarry adds `+1 stone` to `produce_stone`
- Produce building bonuses apply only from `active_buildings` and stack with matching
  Special Activity bonuses.
- For `give_alms`, paid actions still pay silver/wheat equal to effective duty value and move
  that many rows.
- `give_alms_donate_building` always donates exactly one active building and advances Alms by
  exactly one
  row.
- On majority `give_alms`, `give_alms_donate_building` still resolves as one deterministic
  action; it does not chain into a second paid Give Alms step.
- Alms House currently enhances only paid `give_alms_paid`, not
  `give_alms_donate_building`.
- For `ordination`, each action contains `1..duty_value` ordered steps chosen from:
  - `ordain`: pay 1 wheat, move 1 worker village -> abbey
  - `mission`: pay 1 wheat, move 1 acolyte abbey -> city
- Ordination steps are validated sequentially, so `ordain; mission` is legal at duty value 2 even
  when Abbey starts empty.
- Each ordination step must be legal when reached and costs 1 wheat.
- Active Infirmary now modifies Ordination duty value semantics:
  - legal generation may allow one additional step (`+1` cap) when Infirmary is active
  - the extra step still costs wheat (no free steps)
  - apply-time `effective duty value` and `BUILDING_BONUS` are emitted only when the chosen
    sequence actually uses that extra paid step
- For `clerical`:
  - Mint adds `+1 silver` to `clerical_silversmith`
  - Chapel adds `+1 piety` to `clerical_devotion`
  - these bonuses apply only from `active_buildings`
  - these bonuses stack with matching Special Activity bonuses (Engraver / Vestry)
- For `allocation`, duty value controls how many allocation moves can be sequenced in one
  action (1..duty value) between Abbey and Special Activities.
- Active Infirmary now adds `+1 effective Duty Value` to Allocation:
  - parity Allocation can sequence up to 2 moves
  - majority Allocation can sequence up to 3 moves
  - this is a true duty-value modifier and appears in `effective duty value` output
- Active Chapter House modifies Special Activity occupancy semantics for Allocation:
  - without active Chapter House, each Special Activity space has capacity 1
  - with active Chapter House, each Special Activity space has capacity 2
  - second-acolyte occupancy still requires legal Allocation moves
  - donated/inactive Chapter House does not apply
- For `build_roads`:
  - legal actions currently include `build_roads_deferred` plus `tithe`
  - `build_roads_deferred` applies normal duty relation, minority silver cost, and recall
  - no roads/bridges/fords/shrines are placed, upgraded, or demolished in this milestone
  - `DUTY_DEFERRED` event documents deferred option families:
    - build road/bridge/ford/shrine
    - upgrade road/bridge
    - demolish road/bridge
- For `construct`:
  - legal actions now include `construct_building`, `construct_road_deferred`, and (at duty value
    2) `construct_building_and_road_deferred`, plus `tithe`
  - market buildings now have deterministic live rounds (`2..26`)
  - a market building is live when `current round >= live round`
  - Construct purchase actions are generated only for live market buildings
  - Construct can acquire exactly one market building:
    - pay stone equal to building level (L1=1, L2=2, L3=3)
    - remove that building from `building_market`
    - add it to acting player's `active_buildings`
    - consume one shared player-board slot immediately
  - Construct still enforces "max 1 building per Construct action"
  - at duty value 2, building + road is partially implemented:
    - building resolves immediately
    - road remains deferred and logged via `DUTY_DEFERRED`
  - Road Engineer for Construct does not raise generic duty value:
    - it allows additional deferred roads when a road plan is already included
    - additional-road count scales by occupied Road Engineer acolytes (max +2 with active
      Chapter House)
  - roads/bridges/upgrades/demolition/spatial placement remain deferred
  - minority silver cost and duty recall still apply normally
- For `taxation`:
  - Step I always takes exactly one chosen resource: `stone`, `silver`, or `wheat`.
  - Step II checks other physical duty tiles (excluding the selected Taxation tile and any
    position whose category is `taxation`) where the acting player has true majority.
  - Eligible Step II resource types come from `tithe_counters` on those other majority tiles.
  - If no eligible other majorities exist, Step II is empty.
  - If eligible types exist, Step II chooses exactly `duty_value` resources with repetition
    allowed (for example `stone, stone` or `stone, silver` at duty value 2).
  - Maximum total gain is `1 + duty_value` (currently at most 3 resources).
  - Taxation recalls acolytes only from the selected Taxation tile.
  - Taxation does not change piety, does not advance Alms, and does not consume Tithe counters.
  - Special Activities and Produce/Clerical building effects do not boost Taxation resources.
- Tithe counters are modeled separately from `tithe` action mode:
  - `tithe_counters` map physical duty positions to one of
    `stone` / `silver` / `wheat` / `cornucopia` (or `null`).
  - `city` is never valid for a counter.
  - The physical position currently mapped to duty category `taxation` must have no non-null
    Tithe counter.
  - `cornucopia` is a Taxation Step-II wildcard source: it unlocks chosen resource gains from
    `stone` / `silver` / `wheat` and is not itself a gained resource.
- Verbose CLI now prints duty layout and shows category in action/event text:
  - `selected duty: north_east (clerical)`
  - `DUTY_RESOLUTION: selected east (build_roads); ...; action build_roads_deferred`
  - `DUTY_DEFERRED: build_roads requires spatial road/shrine system; ...`
  - `DUTY_RESOLUTION: selected south_east (construct); ...; action construct_building`
  - `BUILDING_CONSTRUCTED: player_one constructed Well from market; level 1; cost stone 1; ...`
  - `DUTY_DEFERRED: construct road part requires spatial road system; requested plan: ...`
  - `DUTY_RESOLUTION: selected north_west (allocation); ...; duty value 1; effective duty value 2; ...`
  - `BUILDING_BONUS: infirmary added duty value +1 to allocation`
  - `BUILDING_BONUS: infirmary added duty value +1 to ordination; extra wheat cost paid`
  - `BUILDING_BONUS: chapter_house allowed second acolyte on vestry (capacity 2)`
  - `Building availability:` summary:
    - `Live market: ...`
    - `Future market: ... (round N)`
    - `Owned/live: ...`
