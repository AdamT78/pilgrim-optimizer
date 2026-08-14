"""What a tithe takes off the tile it was declared on.

Choosing TITHE instead of a duty's own action gains the TITHE COUNTER sitting on the selected
position: one wheat, one stone or one silver. The cornucopia is a wildcard and the tithing player
picks. Taxation carries no counter, so there is nothing to tithe there and no tithe is offered.

THE AMOUNT IS ONE, AND IT DOES NOT SCALE

Duty value (2 for majority, 1 otherwise) scales produce output, alms rows, ordination steps,
allocation moves and Taxation step II. It does not scale this, and that is not an omission anyone
would have to take on trust: `_scriptorium_can_affect_action` already excludes TITHE from
Scriptorium variants on the grounds that relation and value cannot change a tithe's outcome. Make
a tithe scale with duty value and that pruning silently starts discarding distinct results. The
two statements cannot both be kept, and the pruning is the older one.

`tools/ui_debug`'s hand-driven table says the same thing from the other side -- "Tithe credits the
active seat one of whatever the chosen tile carries" -- though it knows no rules and only counts
as corroboration.
"""

from __future__ import annotations

from pilgrim.model.config import GameConfig

CORNUCOPIA_COUNTER = "cornucopia"
TITHE_GAIN = 1
# Everything a tithe can gain, and so also the wildcard's three answers in the order the variants
# come out in. Shares its members with `CORNUCOPIA_HIRE_RESOURCES` and nothing else: that one is
# what a building hire is PAID in, this is what a tithe GAINS. Two decisions, made by different
# players at different moments, that happen to have the same three answers. Joining them would
# make one of them impossible to change.
TITHE_RESOURCES: tuple[str, ...] = ("wheat", "stone", "silver")


def tithe_resources_for_position(config: GameConfig, duty_position: int) -> tuple[str, ...]:
    """Every resource a tithe on this position could name, one per action to be enumerated.

    Empty on Taxation, one long for a plain counter, three long for the cornucopia -- ALWAYS three,
    with no affordability filter. The usual reason a variant list gets pruned is that the player
    cannot pay for it, and the reason that reason is absent here is that a tithe gains rather than
    spends. There is no stock a cornucopia tithe could be short of, so all three are always legal
    and a reader looking for the missing `if player_resources...` should stop looking.
    """
    counter = config.tithe_counters.resource_for_board_index(duty_position)
    if counter is None:
        return ()
    if counter == CORNUCOPIA_COUNTER:
        return TITHE_RESOURCES
    return (counter,)
