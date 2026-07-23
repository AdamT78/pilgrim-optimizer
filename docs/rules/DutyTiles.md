# Duty Tiles (v2.2 Sandbox Scope)

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
  - `give_alms` (pay silver/wheat)
  - `donate_building` (donate one active building)
- `ordination`:
  - `ordination` (ordered `ordain`/`mission` steps)
- `allocation`
- `build_roads`:
  - `build_roads_deferred` (scaffold only; no spatial placement yet)
- `construct`:
  - `construct_deferred` (scaffold only; no building/spatial placement yet)
- `taxation`:
  - `taxation` (step-1 chosen resource + step-2 bonus resources from other majority tiles)

Deferred category systems (valid in layout, no non-tithe action yet):

- none

## Runtime implications

- Majority/parity/minority is still computed on the selected **physical** duty position.
- Duty value is still derived from the selected position relation.
- Available non-tithe actions come from the selected position's **category**.
- For `produce`, one explicit option is chosen: `produce_wheat` or `produce_stone`.
- Produce duty value cannot be split across resources in one action.
- Produce special-activity bonuses (Fields / Stone Mason) add produced resources and do not
  change duty value.
- For `give_alms`, paid actions still pay silver/wheat equal to effective duty value and move
  that many rows.
- `donate_building` always donates exactly one active building and advances Alms by exactly one
  row.
- On majority `give_alms`, `donate_building` still resolves as one deterministic action; it does
  not chain into a second paid Give Alms step.
- Alms House currently enhances only paid `give_alms`, not `donate_building`.
- For `ordination`, each action contains `1..duty_value` ordered steps chosen from:
  - `ordain`: pay 1 wheat, move 1 worker village -> abbey
  - `mission`: pay 1 wheat, move 1 acolyte abbey -> city
- Ordination steps are validated sequentially, so `ordain; mission` is legal at duty value 2 even
  when Abbey starts empty.
- Each ordination step must be legal when reached and costs 1 wheat.
- For `allocation`, duty value controls how many allocation moves can be sequenced in one
  action (1..duty value) between Abbey and Special Activities.
- For `build_roads`:
  - legal actions currently include `build_roads_deferred` plus `tithe`
  - `build_roads_deferred` applies normal duty relation, minority silver cost, and recall
  - no roads/bridges/fords/shrines are placed, upgraded, or demolished in this milestone
  - `DUTY_DEFERRED` event documents deferred option families:
    - build road/bridge/ford/shrine
    - upgrade road/bridge
    - demolish road/bridge
- For `construct`:
  - legal actions currently include `construct_deferred` plus `tithe`
  - scaffold plans model intent only (`building`, `road`, `building + road`, plus Road Engineer
    extra-road variants when legal)
  - real Construct rule modelled by plan constraints:
    - at most 1 building from Construct
    - at duty value 2, `building + road` is legal
    - `building + building` is never legal
  - no buildings, roads, bridges, upgrades, demolitions, or map changes are applied in this
    milestone
  - minority silver cost and duty recall still apply normally
  - `DUTY_DEFERRED` event records the requested deferred plan
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
  - `DUTY_RESOLUTION: selected south_east (construct); ...; action construct_deferred`
  - `DUTY_DEFERRED: construct requires building/spatial road system; requested plan: ...`
