# Duty Enhancements (v2.7)

## Purpose

`pilgrim/rules/duty_enhancements.py` is a metadata-only registry that records which Special
Activities and buildings are expected to affect Duty actions.

Important scope boundaries:

- It does **not** auto-apply effects during transitions.
- It does **not** replace duty-specific hooks in the rules engine.
- It does **not** implement building effects.
- Gameplay behavior continues to come from existing action generation and transition logic.

Runtime policy for currently implemented building bonuses:

- Buildings in `donated_buildings` do not apply.
- Well/Quarry/Mint/Chapel now apply from either:
  - own active building (free), or
  - a usable hired source (live market or opponent active).
- Hired source payment is one Merchant resource:
  - live market -> bank
  - opponent active -> owner
- Merchant on Taxation has resource `none`, so hired sources are unavailable there.
- These bonuses stack with matching Special Activity bonuses.
- Infirmary is now implemented as a true duty-value modifier:
  - Allocation: `+1 effective Duty Value` from own-active or usable hired source
  - Ordination: `+1 effective Duty Value` only when the extra paid Ordination step is used,
    from own-active or usable hired source
- Mill is now implemented as a wheat-cost modifier:
  - `give_alms_paid`: waive up to first `2` required wheat
  - `ordination`: waive up to first `2` required wheat
  - formula: `actual_wheat_spent = max(0, required_wheat - 2)`
- Well / Quarry / Mint / Chapel remain direct output bonuses (resource/piety), not duty-value
  modifiers.

Construct note for this milestone:

- Construct can now acquire one building from market (stone cost by level), but that acquisition is
  core Construct behavior, not a Duty enhancement entry.
- Registry entries still focus on modifiers/bonuses (for Construct: Road Engineer deferred-road
  extension logic).

Building hire infrastructure note (v3.1a):

- Rules helpers now model source/cost/payment for potential hired building use:
  - own active
  - live market hire
  - opponent active hire
  - unavailable
- Hire cost is one Merchant resource to bank/opponent depending on source.
- Merchant resource `none` (taxation) blocks hiring.
- Donated buildings remain unavailable.
- Current hire-source wiring is intentionally limited to direct-output bonuses:
  - Well (`produce_wheat`)
  - Quarry (`produce_stone`)
  - Mint (`clerical_silversmith`)
  - Chapel (`clerical_devotion`)
- Infirmary is now also wired:
  - Allocation effective-duty cap bonus (`+1`)
  - Ordination extra-step effective-duty cap bonus (`+1` when extra step is used)
- Mill is now also wired:
  - own active, live market hire, opponent active hire
  - hire payment is separate and not waived by Mill
- Chapter House remains own-active-only / deferred for hire wiring.

## Registry fields

Each entry records:

- `duty`
- `action_key`
- `source_type`
- `source_key`
- `effect`
- `status`
- `notes`

Status values currently used:

- `implemented`
- `implemented_scaffolded`
- `known_unimplemented`

## Registry entries

Format:

`duty | action_key | source_type | source_key | effect | status | notes`

### Produce

- `produce | produce_wheat | special_activity | fields | +1 wheat | implemented | Applied by produce_wheat_fields_bonus() hook.`
- `produce | produce_stone | special_activity | stone_mason | +1 stone | implemented | Applied by produce_stone_mason_bonus() hook.`
- `produce | produce_wheat | building | well | +1 wheat | implemented | Applied in transition from own-active or usable hired Well source.`
- `produce | produce_stone | building | quarry | +1 stone | implemented | Applied in transition from own-active or usable hired Quarry source.`

### Clerical

- `clerical | clerical_devotion | special_activity | vestry | +1 piety | implemented | Applied by clerical_devotion_bonus() hook.`
- `clerical | clerical_silversmith | special_activity | engraver | +1 silver | implemented | Applied by clerical_silversmith_bonus() hook.`
- `clerical | clerical_silversmith | building | mint | +1 silver | implemented | Applied in transition from own-active or usable hired Mint source.`
- `clerical | clerical_devotion | building | chapel | +1 piety | implemented | Applied in transition from own-active or usable hired Chapel source.`

### Give Alms

- `give_alms | give_alms_paid | special_activity | alms_house | optional +1 effective Duty Value with extra payment | implemented | Bonus scales by occupied Alms House acolytes (max +2 with active Chapter House); each +1 still requires one extra paid silver/wheat.`
- `give_alms | give_alms_paid | building | mill | waive up to first 2 wheat costs | implemented | Applied in transition from own-active or usable hired Mill source; does not waive silver or hire payment.`

### Build Roads

- `build_roads | build_roads_deferred | special_activity | road_engineer | +1 effective Duty Value | implemented_scaffolded | Bonus scales by occupied Road Engineer acolytes (max +2 with active Chapter House). Build Roads runtime remains deferred/scaffolded.`

### Construct

- `construct | construct_road_deferred | special_activity | road_engineer | extra deferred road only if road already included | implemented_scaffolded | Applies to Construct road plans (road-only and building+road deferred); scales by occupied Road Engineer acolytes (max +2 with active Chapter House); Construct does not use generic duty-value +1 from Road Engineer.`

### Allocation

- `allocation | allocation | building | infirmary | +1 effective Duty Value | implemented | Applied in transition from own-active or usable hired Infirmary source.`
- `allocation | all_special_activity_spaces | building | chapter_house | allows a second acolyte on each Special Activity via Allocation; bonuses scale by acolyte count, max 2 | implemented | Active Chapter House increases per-space Special Activity capacity from 1 to 2; donated Chapter House does not apply.`

### Ordination

- `ordination | ordination | building | mill | waive up to first 2 wheat costs | implemented | Applied in transition from own-active or usable hired Mill source; does not waive silver or hire payment.`
- `ordination | ordination | building | infirmary | +1 effective Duty Value if wheat cost is paid | implemented | Applied when own-active or usable hired Infirmary is used for an extra paid ordination step.`
