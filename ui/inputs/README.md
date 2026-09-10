# Pipeline inputs

Pre-rendered stages that `gen_board.py` reads. They are generated artifacts, which the asset
library deliberately excludes — the rule there is that a generator's output must not be committed
beside its source, because the copy starts drifting the moment a constant changes. These are the
exception, and the reason is worth stating: each is produced by a *different* generator, and
`gen_board.py` composes them. Without the files, rebuilding one page means re-running four
pipelines; with them, it means running one.

| file | produced by | what it is |
| --- | --- | --- |
| `duty-wheel.svg` | `scratch/` (duty wheel builder) | the eight duty tiles, the city, the ring |
| `map-populated.svg` | `scratch/mkmap.py.txt` | the hex map, populated from the real setup generator |
| `market-hex.svg` | `scratch/mkmarketsvg.py.txt` | the market hex row, built to the panel's content box |
| `market-panel.html` | `scratch/mkmarket.py.txt` | the market panel's own markup |
| `log-body.html` | `scratch/mklog.py.txt` | the event-log body |
| `wagon-path.txt` | traced from the Noun Project wagon (Alzam) | the merchant wagon outline, spokes removed |

The generators in `scratch/` are the versions rescued from a session's temp directory. They run,
but they still carry absolute paths of their own and have not been made portable the way
`gen_board.py` and `gen_picker.py` have. Treat them as the record of how each file was made, not
yet as a build step you can rely on.

The long-standing intent is that the log's text belongs in `pilgrim/io/event_text.py` rather than
in a scratch script, at which point `log-body.html` stops being an input at all.
