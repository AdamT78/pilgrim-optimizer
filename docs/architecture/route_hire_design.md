# Route Hire Design

How hiring a route building will work once its hire moves off the committed-step path and
onto the sow action. This is the design record for that change: each decision with the
measurement that settled it, and the two questions still open. It describes intent, not
current behaviour — nothing here is implemented yet.

Read `design_principles.md` first. This document is that document applied to one change.

## The change

Today a route hire is a committed step taken before the sow. You pay, and then the map
widens. Measured on `kogge_hire_market_city_to_east_001`, the Kogge takes a position from
6 candidates to 14, and those eight extra routes are invisible until the silver is spent.
That is the shape `design_principles.md` calls buying blind, and it is also how a player
can pay for a route and then walk somewhere else — on `movement_2p`, all 63 pre-hire
actions remain legal after the Kogge is bought.

The hire moves onto the `FullTurnAction`, where the Mill, Infirmary and Well already carry
theirs. Choosing a route that needs the Kogge is what buys it; choosing any other route
buys nothing. Paying for something you do not use stops being a rule to enforce and
becomes a state that cannot be described.

This is the first branch in this sequence whose capture diffs are expected to move.
`docs/audits/route_modifier_hire_manifest.json` exists to say which files may change.

## The tile is a toggle

The building tile stops being a control that commits a purchase and becomes one that shows
what the purchase would buy. Three states.

Off. The tile is in play, its arrows are not drawn, and nothing has been spent.

On. Its arrows are drawn on the duty wheel and nothing has been spent. Toggling back off
hides them again, free, as many times as a player likes.

In effect. One of its arrows has been used, so the purchase is committed for this turn.
The tile is not greyscale — grey means there is nothing further to do with a tile, and a
hired route building is working — and it carries the sentence merged in #239: *"Hired or
activated this turn: acolytes may move against the river to enter or leave the City."*

The toggle is the reason no fourth visual state is needed. An earlier draft had the tile
inert and full-colour during Beginning of Turn, which is a coloured control that does
nothing when clicked, and that is the defect this project keeps finding.

## Taking the arrow is the hire

There is no confirmation dialog. Nothing has left the player's stock when they take a
marked arrow, and Reset undoes it for nothing, so a yes/no at that moment asks permission
for something that has not happened. Instead the turn box states it as a fact, and Confirm
is where the resources actually move — the same shape as the hired conversions in #236.

Toggling a building off part-way through a route that depends on it resets that route
rather than silently re-filtering the arrows. That is not an edge case: with both route
buildings hired, 18 of 28 routes need both.

## What the arrows say

Three states, painted as a fill on `.arrow-interior`, which is the mechanism that already
paints offered arrows green.

    ordinary move           rgb(30, 122, 52)   unchanged
    Kogge-opened edge       #7A4FB5            violet
    Cloisters extra step    #0E9BA6            teal, and overrides the violet

The teal also takes a heavier `.arrow-border`, so the override survives for a player who
cannot separate the two hues. It is deliberately not a dashed border: dashing an arrow that
small breaks its outline into fragments and it reads as a torn smear rather than a dashed
arrow.

None of the three borrows a seat colour. The seats are Red `#B7382E`, Yellow `#D9B33B`,
Blue `#3B6EA5` and White, and the duty wheel already uses seat colour to mean *whose* —
origin, skip, duty and relocation candidates share the active seat's ring. Blue and yellow
were the first proposal and had to be dropped for that reason. River blue was never a
conflict: the rivers are drawn on the hex map, the arrows on the duty wheel.

The override is right because the Cloisters does not open its own edges. It buys one more
movement, and that movement can land on an edge the Kogge opened. At that moment what
matters is that this is the bought extra step, so the teal wins.

## The price is per route, not per arrow

An arrow does not carry a price. The turn box accumulates as the route is assembled, one
line per purchase:

    This route uses the Kogge — 1 silver to Red
    and the Cloisters — 1 wheat to bank

A single arrow cannot state its cost, because the cost depends on the route so far rather
than on the arrow. It also cannot be attributed to one building by asking: where both are
involved, one provides the edge and the other provides the step, so the player owes both
and has nothing to choose between. An earlier draft offered a "use the Kogge or the
Cloisters?" question, which would have been a decision the player does not have.

## Auto-advance is unchanged

A frontier still advances without a click if and only if it holds exactly one option and
that option is a movement edge. Showing the route arrows turns forced frontiers into
choices, so the sow stops there of its own accord — the rule already produces the behaviour
this change needs.

The case worth guarding is the opposite one: a frontier whose only continuation is a paid
edge would commit a payment with no click at all, and the existing invariant would not
notice, because it counts options rather than costs. Measured across every scenario where
the Kogge is hireable, after hiring it there are 2 single-option edge frontiers and neither
is a Kogge edge, so there is nothing to fix — only something to hold. Assert that the sole
option at such a frontier never carries a hire. It passes today and fails loudly if a
future position or a new route building creates one.

## Scope

The Kogge and the Cloisters move first. The Bank, Scriptorium and Customs House follow in
a separate branch; their effects modify a resolution rather than a movement, so their hire
attaches after the resolution is chosen, where the Infirmary's question already sits at
index 4 of 6.

The Wagon Yard does not move. It buys a single free hire rather than a standing permission,
its effect is consumed by another committed step rather than by the sow, and "buy it where
it is consumed" therefore points somewhere else for it.

## Open questions

Whether the turn box carries a standing line naming the price while the arrows are showing,
or says nothing until an arrow is taken. Dropping the per-arrow price leaves a window in
which a player can click a paid arrow without having seen a number. The price does appear
the moment the arrow is taken and Reset costs nothing, so the current intention is to ship
without the line and add it if play proves it ambiguous.

Where exactly the modifier hires attach, which belongs to the second branch and is written
above as an expectation rather than a decision.
