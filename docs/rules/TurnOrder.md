# Turn Order (v4.7 Sandbox Scope)

## Normal play order

- Real players act in fixed clockwise order:
  - 2p: `player_one -> player_two -> player_one`
  - 3p: `player_one -> player_two -> player_three -> player_one`
  - 4p: `player_one -> player_two -> player_three -> player_four -> player_one`
- Each real player acts exactly once per round.
- A round closes only after the last real player in that order acts.

## Round length

- Round length is derived from `GameState` real player count (`2..4`), not from a fixed timing-file constant.
- `timing.turn_in_round` advances from `0` up to `player_count - 1`.
- After the last turn in the round:
  - round-end pipeline runs
  - `timing.turn_in_round` resets to `0`
  - next `active_player` is the selected `start_player`.

## Start-player selection

At round end:

1. highest piety determines deciding player
2. if tied, tie-break walks clockwise away from current `start_player` to first tied player
3. placeholder policy remains: deciding player selects themselves

Result:

- `start_player` is updated to that selected player
- `active_player` is set to that same selected player for the next round.

## Season-end Alms tie-break order

When Alms and Piety are tied at season end, winner uses current round turn order from current
`start_player`:

- current `start_player` is first
- next clockwise real player is second
- and so on across only real players in the game.

## Setup-sow exception

- `setup_sow` is separate from normal round progression.
- Setup-sow rotates through incomplete setup players only.
- Setup-sow turns do **not** run round-end phases.
- When setup sow completes:
  - phase changes to normal `sow`
  - `active_player` resets to current `start_player`.
