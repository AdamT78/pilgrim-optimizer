# Design Principles

How Pilgrim asks a player for a decision, and what it owes them in return. These are
play-facing rules, not engineering ones, though the seam in `docs/architecture/overview.md`
is what makes them enforceable. Each principle names the guard that holds it where one
exists, and the open questions at the end are the places where the game does not yet obey
its own rules.

## Nothing is spent until the answer is complete

A player cannot pay for something and then fail to receive it. For hired conversions this
is not a rule the game enforces but a shape it has: the payment and the use are one
committed step, so no state exists in between. `_apply_building_conversion_step` charges
the hire and applies the conversion in a single transaction, which is why Reset costs
nothing at any point before Confirm — nothing has left the player's stock yet.

The design consequence is that a question sequence may be as long as it needs to be. Since
the price of abandoning halfway is zero, there is no reason to hurry a player through, and
no reason to ask them to confirm a step that has not yet cost anything.

> **Example.** Yellow clicks Stone Yard on Red's board, chooses to pay with stone, sees the
> directions narrow to Buy alone, thinks better of it and presses Reset. Their stock is
> still 1 stone, 1 silver, 1 wheat — exactly what it was before the first click. Nothing
> was posted to the engine, so there is nothing to give back.

## Say the price before the click that spends it

A cost that only becomes visible in the log after it is paid is a trap. When a building can
be hired, the turn box states what it costs and who receives it as soon as the building is
chosen, before any other question. Where the Merchant's cornucopia leaves the resource
open, that becomes a real question with the payable resources offered as answers, and the
payment is settled before the conversion, because what a player can afford afterwards
depends on what they paid with.

The order follows from the rule, not from convenience: a question whose answer changes the
options of a later question belongs first.

> **Example.** On `conversions_2p`, clicking Stone Yard used to lead straight to a direction
> and an amount, with nothing anywhere on screen saying the building cost anything or that
> Red would be paid. It now reads "Hire Stone Yard from Red for 1 resource of your choice."
> the moment the tile is clicked, and the payable resources are the first question asked.
> Answering it narrows what follows: pay stone and only Buy survives, pay silver and only
> Sell, pay wheat and both remain.

## Only a forced movement edge is skipped

A single-option frontier is not automatically a frontier worth skipping. The game skips a
click if and only if the frontier holds exactly one option *and* that option is a movement
edge — a step of a route the player has already committed to walking. Every other frontier
with one option is still asked, because being told what is about to happen is itself
information, and a board that advances on its own leaves a player wondering what they
missed.

`test_auto_advance_is_exactly_the_unambiguous_edge_at_every_corpus_frontier` holds this as
an if-and-only-if across more than 5,400 corpus frontiers.

The companion rule matters as much: a skipped step still leaves its fact on screen.
Auto-advance removes the click, never the information.

> **Example.** A Cloisters route with one edge left advances by itself; there was never a
> decision there, only a formality. But when the Merchant names silver, hiring the Kogge has
> exactly one possible payment and still shows "Hire Kogge from Yellow for 1 silver." No
> question is asked, because there is nothing to choose — and the price is stated anyway,
> because the player is spending it either way.

## A refusal says why

A control that looks available and does nothing is worse than one that is visibly closed.
Every building tile that cannot be used now says so in its own terms: a tile not yet
reached is shown by the ship token, a donated building is flipped face down, and anything
in play but unusable renders greyscale with the reason in its tooltip.

The same applies to controls. Confirm is dimmed and `aria-disabled` until the answer it
would post is complete, rather than accepting a click and discarding it.

> **Example.** Activate the Dormitory and the engine stops offering it — eleven committed
> steps become ten. Until recently the tile stayed in full colour and its tooltip still read
> "Usable: no payment.", so the only way to discover the building was spent was to click it
> and watch nothing happen. It now greys, and says "Cannot be used: already used this turn."

## Buy a thing where it is consumed

A purchase should be committed at the moment its effect lands. The Guild and the Pulpit are
consumed on the spot — activating the Guild *is* moving the Merchant — so committing them
as their own step is right. Conversions are consumed on the spot, so the atomic step is
right. A hire whose effect is exercised later belongs on the action that exercises it.

What decides the model is when the effect lands, not what kind of building it is.

> **Example.** On `allocation_hire_infirmary_market_001` there are 29 legal actions, 22 of
> which carry the Infirmary hire and 7 of which do not. The wheat leaves the player's stock
> only by choosing one of the 22 — that is, only by using the building. Paying for an
> Infirmary you then ignore is not forbidden there; it cannot be described.

## The page renders decisions, it does not make them

The engine decides what is legal, the play server puts the decision into player-facing
words, and the page draws what it is given. The order of the questions, the sentence
describing a cost, and the reason a tile is grey are all produced above the page, which
recognises none of them by name. This is what keeps the principles above from being
restated — and quietly diverging — in a second place.

> **Example.** The page once decided for itself that the Indulgences were the building whose
> hire payment needed asking, by testing `conversionChosen[0] === 'indulgences'`. Every other
> hired conversion therefore had no way to answer that question, and the Stone Yard could not
> be committed at all. The order now arrives from the server as an `answers` list, and the
> string "indulgences" no longer appears anywhere in `play_view_turn.js`.

## Open questions

Route and modifier hires do not yet obey the first and fifth principles. The Kogge is
committed as its own step and charges immediately, and after paying, every action that was
legal beforehand is still legal — measured on `movement_2p` as 63 actions before the hire
and all 63 still present among the 190 afterwards. A player can therefore buy a route and
walk somewhere else. Moving those hires onto the sow action would resolve both, at the cost
of enumerating the payment as part of the action.

The Wagon Yard resists that resolution, because what it discounts is another building's
hire, including hires taken as committed steps. Its purchase is consumed by a step rather
than by the sow, so it would have to pair with that step.
