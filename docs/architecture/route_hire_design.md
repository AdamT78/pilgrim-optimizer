# Route Hire Design

How route hiring works now that its hire has moved off the committed-step path and onto the
sow action. This is the design record for that change: each decision with the measurement that
settled it, and the implementation that carries it.

Read `design_principles.md` first. This document is that document applied to one change.

## The change

Before this change, a route hire was a committed step taken before the sow. You paid, and then the
map widened. Measured on `kogge_hire_market_city_to_east_001`, the Kogge took a position from
6 candidates to 14, and those eight extra routes are invisible until the silver is spent.
That is the shape `design_principles.md` calls buying blind, and it also let a player pay for a
route and then walk somewhere else — on `movement_2p`, all 63 pre-hire actions remained legal
after the Kogge was bought.

The hire is now on the `FullTurnAction`, where the Mill, Infirmary and Well already carry theirs.
Choosing a route that needs the Kogge buys it; choosing any other route buys nothing. Paying for
something not used has stopped being a rule to enforce and has become a state that cannot be
described.

The route-hire move was the first branch in this sequence whose capture diffs moved.
`docs/audits/route_modifier_hire_manifest.json` records the files that changed with it.

## The tile is a toggle

The building tile is no longer a control that commits a purchase; it shows what the purchase would
buy. The page carries four `data-turn-family-state` values: `off`, `on`, `owned`, and `in_effect`.
The server writes `toggle_waiting_text`, `toggle_off_text`, and `toggle_on_text`; the page chooses
among those finished sentences as the already-offered candidates are narrowed, but never composes
the wording.

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

Three states are live in `turn_styles`, painted as a fill on `.arrow-interior`, which is the
mechanism that already paints offered arrows green.

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

An arrow does not carry a price. The server accumulates the hire lines as the route is assembled,
one line per route building the route uses. It ships them as one newline-separated `hire_text`
string on the first route edge; the page has no hire-line state to append. The corpus has two
multi-line variants with the same shape: each line names the building and its price and payee; one
pays the bank and the other pays an opponent seat.

`sharedHireText` intersects the lines already present in surviving candidates. It therefore shows
the hires every remaining route still needs; it never builds a combined sentence by appending lines
in the browser.

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

The Kogge and the Cloisters are the route families. The Bank, Scriptorium and Customs House modify
a resolution rather than a movement, so their hire belongs after the resolution choice, where the
Infirmary's question already sits at index 4 of 6.

The Wagon Yard does not move. It buys a single free hire rather than a standing permission,
its effect is consumed by another committed step rather than by the sow, and "buy it where
it is consumed" therefore points somewhere else for it.

## Resolved detail

The turn box does not carry a standing price line while arrows are merely shown. The server supplies
the route's `hire_text` once a selected route contains a hire, and Reset still costs nothing.
