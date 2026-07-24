# Duty Enhancements (v2.6)

## Purpose

`pilgrim/rules/duty_enhancements.py` is a metadata-only registry that records which Special
Activities and buildings are expected to affect Duty actions.

Important scope boundaries:

- It does **not** auto-apply effects during transitions.
- It does **not** replace duty-specific hooks in the rules engine.
- It does **not** implement building effects.
- Gameplay behavior continues to come from existing action generation and transition logic.

Runtime policy for currently implemented building bonuses:

- Only buildings in a player's `active_buildings` apply.
- Buildings in `donated_buildings` do not apply.
- These bonuses stack with matching Special Activity bonuses.
- Infirmary is now implemented as a true duty-value modifier:
  - Allocation: `+1 effective Duty Value`
  - Ordination: `+1 effective Duty Value` only when the extra paid Ordination step is used
- Well / Quarry / Mint / Chapel remain direct output bonuses (resource/piety), not duty-value
  modifiers.

Construct note for this milestone:

- Construct can now acquire one building from market (stone cost by level), but that acquisition is
  core Construct behavior, not a Duty enhancement entry.
- Registry entries still focus on modifiers/bonuses (for Construct: Road Engineer deferred-road
  extension logic).

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
- `deferred_special_activity_system`

## Registry entries

Format:

`duty | action_key | source_type | source_key | effect | status | notes`

### Produce

- `produce | produce_wheat | special_activity | fields | +1 wheat | implemented | Applied by produce_wheat_fields_bonus() hook.`
- `produce | produce_stone | special_activity | stone_mason | +1 stone | implemented | Applied by produce_stone_mason_bonus() hook.`
- `produce | produce_wheat | building | well | +1 wheat | implemented | Applied in transition when Well is active.`
- `produce | produce_stone | building | quarry | +1 stone | implemented | Applied in transition when Quarry is active.`

### Clerical

- `clerical | clerical_devotion | special_activity | vestry | +1 piety | implemented | Applied by clerical_devotion_bonus() hook.`
- `clerical | clerical_silversmith | special_activity | engraver | +1 silver | implemented | Applied by clerical_silversmith_bonus() hook.`
- `clerical | clerical_silversmith | building | mint | +1 silver | implemented | Applied in transition when Mint is active.`
- `clerical | clerical_devotion | building | chapel | +1 piety | implemented | Applied in transition when Chapel is active.`

### Give Alms

- `give_alms | give_alms | special_activity | alms_house | optional +1 effective Duty Value with extra payment | implemented | Bonus requires paying exactly 1 extra silver or wheat.`
- `give_alms | give_alms | building | mill | deferred | known_unimplemented | Give Alms building interaction is not implemented yet.`

### Build Roads

- `build_roads | build_roads_deferred | special_activity | road_engineer | +1 effective Duty Value | implemented_scaffolded | Current Build Roads runtime is deferred/scaffolded.`

### Construct

- `construct | construct_deferred | special_activity | road_engineer | extra deferred road only if road already included | implemented_scaffolded | Applies to Construct road plans (road-only and building+road deferred); Construct does not use generic duty-value +1 from Road Engineer.`

### Allocation

- `allocation | allocation | building | infirmary | +1 effective Duty Value | implemented | Applied in transition when Infirmary is active.`
- `allocation | all_special_activity_spaces | building | chapter_house | affects all Special Activity spaces | deferred_special_activity_system | Deferred until broader special-activity building system is implemented.`

### Ordination

- `ordination | ordination | building | mill | deferred | known_unimplemented | Ordination building interaction is not implemented yet.`
- `ordination | ordination | building | infirmary | +1 effective Duty Value if wheat cost is paid | implemented | Applied when active Infirmary is used for an extra paid ordination step.`
