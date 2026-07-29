# Player Choice Model

## Purpose

This document inventories player choices in Pilgrim and maps them to how the current engine
represents those choices.

It is intentionally a modeling and architecture reference, not a rules-change proposal.
It tracks:

- official/conceptual player choices in tabletop Pilgrim
- current engine representation shape
- deterministic/strategic simplifications
- deferred or partially implemented choice areas

## Core engine model: flattened legal actions

The current engine generally does not prompt choices step-by-step during execution.
Instead, it enumerates fully specified action variants via:

`legal_actions(state)`

For normal turns, each `FullTurnAction` is a flattened combination of choices, typically including:

- sow origin
- sow route
- optional building use/hire (including source and any mode/amount fields)
- selected Duty tile
- selected Duty action
- action parameters (for example taxation resources, ordination steps, allocation moves)

The CLI `legal-actions` output is therefore a menu of complete choices, not an interactive
multi-step prompt flow.

## Choice inventory table

Status labels used here:

- Fully modeled
- Mostly modeled
- Partially modeled
- Deterministic simplification
- Strategic simplification
- Deferred / not implemented
- Needs rules audit

| Choice area | Official / conceptual choice | Current engine behavior | Status | Future note |
| --- | --- | --- | --- | --- |
| Starting sow position | Choose legal occupied mancala position to pick up from and start sowing | Encoded as separate `FullTurnAction` variants | Fully modeled | Keep as explicit action variant dimension |
| Route choice | Choose route branch when more than one legal route exists | Encoded as separate action variants where route branching exists | Mostly modeled | Expand with spatial-road systems when implemented |
| Optional building use / hire | Choose whether to use own building, hire market building, or hire opponent building | Encoded as additional full-turn variants; hire is bundled into the selected turn action (not standalone) | Mostly modeled | Continue to use source categories: own active, market hire, opponent hire, unavailable |
| Building mode and amount | Choose building-specific mode/direction and intensity/amount | Encoded with building-specific action fields (`direction`, `amount`, fixed modifiers) | Mostly modeled | Add new parameter fields as additional buildings are implemented |
| Selected Duty tile after sowing | Choose which occupied Duty tile resolves after sowing | Encoded as separate action variants | Fully modeled | Keep tile selection explicit in action summary |
| Which Duty action to trigger | Choose among legal duty options (including `tithe` where legal) | Encoded as separate action variants per duty category | Mostly modeled | Deferred duty systems remain to be expanded |
| Duty action intensity / Duty Value used | Choose to use all or only part of available Duty Value | Engine generally resolves at full usable value when legal/affordable | Deterministic simplification | Add explicit `duty_value_used` style field if partial-use choices are implemented |
| Taxation choices | Choose step-1 resource; choose bonus resource mix from majority-controlled duty context | Step-1 and step-2 resource mix are encoded in action variants; Scriptorium can change majority checks and available bonus mixes | Mostly modeled | Consider encoding/displaying bonus source Duty tiles explicitly |
| Allocation choices | Choose relocation source, destination, and sequence/order of moves | Allocation move sequences are encoded, but strategic partial-use/ordering semantics should be audited explicitly | Partially modeled / Needs rules audit | Audit source/destination/order and optional step counts against intended rules |
| Construct / hire choices | Choose whether to construct and which construct/hire path to take | Implemented construct/building pathways exist; some broader construct/roads/spatial interactions remain deferred | Partially modeled | Expand explicit variants as deferred spatial systems arrive |
| Give Alms donate-building choice | Choose which eligible owned building to donate | Selected donated building is encoded in action field | Partially modeled / Needs rules audit | Audit multiplicity/ordering expectations when Duty Value > 1 |
| Alms threshold effects (rows 2/4/6) | Threshold rewards may create optional or strategic choices | Current rewards auto-resolve if possible; row-4 abbey->city can be strategically sensitive | Step 2/6: Deterministic simplification; Step 4: Strategic simplification | Consider explicit optionality for row-4 effect |
| Season-end Alms reward | Winner may move abbey acolyte to Alms table or decline/forfeit | Mandatory if possible: auto-move exactly 1 abbey acolyte; if none, reward forfeits | Deterministic simplification | Add explicit yes/no season-end choice if desired |
| Round-end start-player selection | Highest-piety decider chooses next start player | Highest piety determines deciding player; tie-break clockwise from current `start_player`; placeholder policy: decider selects themselves | Strategic simplification | Add explicit selected-player choice dimension |
| Round-end trade-route income | No direct player choice at resolution time; outcome depends on prior route network and Merchant marker | Deterministic phase after round-end `MERCHANT_ADVANCE`; each player gains `trade_routes_count` of the Merchant's current resource, with no income when Merchant resource is `none` | Deterministic simplification | Spatial route creation remains deferred; current milestone consumes scalar `trade_routes_count` only |
| Future building-specific choices | Future buildings may add source/target/amount/timing option sets | Tracked building-by-building as they are implemented | Deferred / not implemented | Extend this inventory per building milestone |

## Detailed notes by choice area

### 1) Starting sow position

Official choice:

- choose which legal occupied position to pick up from

Current model:

- separate full-turn action variants

### 2) Route choice

Official choice:

- choose route when branching exists

Current model:

- separate action variants for legal routes
- route modifiers (for example Kogge/Cloisters) are also represented through variants

### 3) Optional building use / hire

Official choice:

- choose whether to use building ability
- choose source where legal

Current model:

- source categories represented in action variants:
  - own active building
  - live market hire
  - opponent active hire
  - unavailable (donated/not-live/merchant-none/insufficient payment)
- hire payment is part of the selected full-turn variant, not a standalone action

### 4) Building mode and amount

Current implemented shapes include:

- Brewery: fixed one-way conversion (`1 wheat -> 2 silver`)
- Grain Store: buy/sell wheat with variable amount
- Stone Yard: buy/sell stone with variable amount
- Indulgences: buy/sell piety with variable amount
- Guild: fixed `Merchant +1` pre-sow modifier
- Pulpit: fixed `1 serf Village -> Abbey` pre-sow modifier
- Scriptorium: fixed virtual `+1 effective acolyte` relation modifier on occupied Duty tiles
- Customs House: fixed Taxation-only majority override modifier on occupied Duty tiles
- Wagon Yard: fixed free-hire enabler with explicit target building/source choice

### 5) Selected Duty tile after sowing

Official choice:

- choose selected occupied Duty tile after sowing

Current model:

- explicit action variants per selected Duty position

### 6) Which Duty action to trigger

Official choice:

- choose legal action on selected Duty tile (including `tithe` where legal)

Current model:

- explicit variants by duty category and action type, including implemented branches like:
  - produce wheat / produce stone / tithe
  - clerical devotion / clerical silversmith / tithe
  - taxation / tithe
  - give alms paid / donate building / tithe
  - allocation / tithe
  - ordination / tithe
  - construct variants / tithe (subject to current scope)

### 7) Duty action intensity / Duty Value used

Conceptual choice:

- choose whether to use full Duty Value or only part of it

Current model:

- deterministic maximal-use tendency: full available value is generally consumed when legal

Strategic impact:

- partial-use choices can matter for resources, workforce timing, and future flexibility

### 8) Taxation choices

Conceptual choices:

- select primary taxed resource
- select legal bonus resource mix from majority-controlled duty context

Current model:

- primary and bonus mix are explicit action parameters
- current CLI shape example:
  - `action: taxation | take: wheat; bonus: stone, silver`
- Scriptorium can change majority checks and therefore legal bonus mixes

Note:

- summary emphasizes resource mix; source duty tiles for each bonus unit may be less explicit

### 9) Allocation choices

Conceptual choices:

- choose source/destination and ordered move sequence
- potentially use fewer than available steps

Current model:

- allocation sequences are represented in action variants
- strategic completeness and optional step-usage semantics should be audited

### 10) Construct / hire choices

Conceptual choices:

- choose construct pathway and involved building(s)
- choose hire/use pathways where legal

Current model:

- implemented construct and building-use/hire options exist in legal action variants
- broader deferred systems (roads/bridges/spatial) still constrain the full choice space

### 11) Give Alms / donate building choice

Conceptual choice:

- choose which eligible owned building to donate

Current model:

- donated building is encoded in action parameter

Audit note:

- duty-value multiplicity and ordering expectations should be explicitly reviewed

### 12) Alms threshold effects at 2, 4, 6

Current simplification:

- row 2 (`village -> abbey`): deterministic auto-apply when possible
- row 4 (`abbey -> city`): deterministic auto-apply when possible, but strategically sensitive
- row 6 effects (where configured similarly): treated with deterministic auto-apply style

Potential future explicit choice for row 4:

- perform effect (`abbey -> city`)
- decline/skip effect

### 13) Season-end Alms reward

Conceptual choice:

- winner may move 1 abbey acolyte to alms table or decline/forfeit

Current model:

- mandatory if possible
- if winner has abbey acolyte: auto-move exactly 1
- else: reward forfeits

### 14) Round-end start-player selection

Conceptual choice:

- highest-piety deciding player chooses next start player

Current model:

- highest piety picks deciding player
- ties break clockwise from current `start_player`
- placeholder policy: deciding player selects themselves

### 15) Future/not-yet-implemented building-specific choices

Some deferred buildings may introduce additional:

- source choices
- target choices
- amount/intensity choices
- timing and optional-effect decisions

These should be added to this document as each building is implemented/audited.

## Current implemented-building choice shapes

| Building | Optional? | Source choices | Mode choices | Amount choices | Notes |
| --- | --- | --- | --- | --- | --- |
| Brewery | yes | own / market / opponent | sell wheat | fixed `1 wheat -> 2 silver` | one-way conversion |
| Grain Store | yes | own / market / opponent | buy/sell wheat | variable | conversion building |
| Stone Yard | yes | own / market / opponent | buy/sell stone | variable | conversion building |
| Indulgences | yes | own / market / opponent | buy/sell piety | variable | conversion building |
| Guild | yes | own / market / opponent | move Merchant +1 | fixed | pre-sow modifier; can combine with normal duty flow |
| Pulpit | yes | own / market / opponent | move serf Village -> Abbey | fixed `1` | free workforce move; independent modifier |
| Scriptorium | yes | own / market / opponent | `+1` effective acolyte on occupied Duty tiles | fixed | virtual relation modifier; affects selected duty and Taxation majority checks |
| Customs House | yes | own / market / opponent | Taxation majority override on occupied Duty tiles | fixed | virtual Taxation-only majority control; selected Taxation + Taxation bonus checks |
| Wagon Yard | yes | own active only (enabler); target source: market/opponent | free-hire one eligible live target building | fixed one target | no hire payment; ignores Merchant resource/position; nested hire chains deferred |
| Kogge | yes | own / market / opponent | route enablement | fixed effect | route modifier shape |
| Cloisters | yes | own / market / opponent | route skip location | selected location | route modifier shape |
| Infirmary | yes | own / market / opponent | duty-value bonus contexts | fixed bonus shape | affects Allocation/Ordination contexts |

Other implemented building behaviors may exist but are omitted from this compact table when
choice shape is not yet fully audited in this document.

## Known simplifications and deferred choices

- Season-end Alms reward is currently mandatory if possible.
- Round-end start-player selection currently self-selects the deciding player.
- Round-end trade-route income currently depends on scalar `trade_routes_count`; map-based
  trade-route creation is still deferred.
- Duty Value intensity is generally maximal-use when legal.
- Allocation move-space semantics (especially partial-use strategic options) should be audited.
- Alms row-4 effect may warrant explicit optionality.
- Taxation models resource mix explicitly; source Duty tile labeling could be clearer.
- Deferred spatial systems still limit full construct/build-roads choice modeling.

## Future implementation notes

Potential next modeling steps:

- add explicit `duty_value_used` / repetition controls where partial use is legal
- add explicit season-end Alms yes/no reward decision
- add explicit deciding-player target selection for next `start_player`
- improve Taxation action/event representation to include bonus source Duty tiles
- extend this document building-by-building as deferred effects are implemented

