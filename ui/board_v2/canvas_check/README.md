# Canvas check

How much screen is left beside the board_v2 module.

```
python3 ui/board_v2/canvas_check/generate_canvas_check.py --open
```

The module is a settled 1400 × 1200 composition. This drops it into a canvas, pushes it flush
right, and shows what is left on the left for player boards and the rest. Keys **1**, **2** and
**3** switch canvas; **h** hides the chrome.

| key | canvas | free to the left |
| --- | --- | --- |
| 1 | 1600 × 1200 | 200 × 1200 · 12.5% |
| 2 | 2039 × 1200 | 639 × 1200 · 31.3% |
| 3 | 2283 × 1200 | 883 × 1200 · 38.7% |

All three canvases are 1200 tall, which is the module's own height, so the module fills the
height exactly and the whole of the leftover is that vertical strip. If a canvas height ever
changes, the page says the module overruns it rather than cropping quietly.

## What is real here and what is a box

The duty wheel is the real drawing — the same vendored SVG the layout lab inlines, recoloured the
same way, at the size the module's geometry gives it. The status line, the eight duty cards, the
two action artworks, Tithe and the City are correctly sized labelled boxes with no art. That is
the same bargain `tools/ui_debug/generate_wheel_space_check.py` strikes, for the same reason: the
question is what is left over, and art inside the module cannot change the answer.

**The free strip is empty on purpose.** It is a dashed hole with its size called out and nothing
inside. Sketching a player board in there would answer a question that was not asked and would
make a claim about fit this file has no business making — the board geometry lives in `ui/render`,
and the moment it is drawn here the two can disagree.

## Nothing is retyped

Every number comes from whatever already owned it. The module's size and each object's position
come from the layout lab's `default_state()`, so recomposing in the lab and re-running reproduces
it here. The three canvases come from `ui/render/gen_game_view.py` through `geometry()`, heights
included — the route `generate_wheel_space_check_v3.py` takes.

There is deliberately **no fallback** if either import fails. A page that quietly drew hard-coded
canvases would be worth less than no page: it would go on agreeing with itself while the numbers
it exists to report moved underneath it.

## How this differs from the wheel space check

`tools/ui_debug/generate_wheel_space_check.py` measures what the **wheel** gets once the player
boards and everything else have taken their share, and its slider moves `board_width` to see the
wheel's room change. This asks the opposite question, with the module treated as fixed. The two
agree on the three canvases and on nothing else, because they are looking from opposite ends.

## Output

The page is written to `generated/canvas_check.html`, which is gitignored — regenerate rather
than expect to find it. It needs no server and no network.
