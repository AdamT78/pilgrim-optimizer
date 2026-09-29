# Layout Lab test suites

The pytest guards in `tests/test_board_v2_layout_lab.py` read the generator and the template as
text: they check what the source says. These suites check what the built page *does*, by driving
it in a real browser, and then check the checks by deliberately breaking the page and confirming
something fails.

Nothing here is needed to build or run the lab. It is needed to trust it.

## Running them

```
npm install playwright                       # once; the suites import it directly
python3 ui/board_v2/layout_lab/generate_layout_lab.py --out out/lab.html
node  tests/layout_lab/accept421.mjs         # or accept4 / accept41 / accept42
python3 tests/layout_lab/mut421.py           # or mut4 / mut41 / mut42 / mut4py
pytest tests/layout_lab/                     # the primitive's own tests
```

Three environment variables move the fixed points, all optional:

| variable | default | what it is |
| --- | --- | --- |
| `LAYOUT_LAB_OUT` | `<repo>/out` | where the built `lab.html` is |
| `LAYOUT_LAB_CHROMIUM` | a Playwright path | the browser binary |
| `LAYOUT_LAB_ASSETS` | `tests/layout_lab/fixtures` | images, probe SVGs, legacy sessions |

A mutation suite takes several minutes: it rebuilds and re-runs the whole acceptance suite once
per mutation, and there are 191 of them.

## What each file is

**`accept4.mjs` · `accept41.mjs` · `accept42.mjs` · `accept421.mjs`** — the acceptance suites, one
per release, each covering what that release introduced. They are kept separate rather than merged
because each one is the record of a specific set of claims, and a merged suite would lose which
release a failure belongs to. 150 + 71 + 66 + 129 checks.

**`mut4.py` · `mut41.py` · `mut42.py` · `mut421.py`** — break the built page in one specific way
and confirm the matching acceptance suite fails. **`mut4py.py`** does the same to the generator
and the template, and confirms the pytest guards fail.

**`mutation_tools.py`** — the shared primitive, and the most important file here. See below.
Its own tests are in `test_mutation_tools.py` and run with the ordinary suite, deliberately: the
first draft was a standalone script ending in `raise SystemExit`, which pytest executes at import
while collecting `tests/`, aborting the entire run with an INTERNALERROR before anything else had
run. A checker that breaks the checker is worse than no checker.

**`fixtures/`** — a few small images, two probe SVGs (one matching the design ratio and one not),
and V2 / V3 lab sessions kept as migration fixtures.

## Why `replace_exactly_once` exists

A mutation suite's claim is negative: *these tests would have noticed if the code were wrong.*
That rests entirely on the code having actually been made wrong — and `source.replace(old, new)`
with an `old` that no longer appears returns the source unchanged, perfectly happily. The suite
then runs the tests against the real build, they pass, and the line prints as a clean result.
Nothing says the mutation never happened.

This is not hypothetical. Three markers in the V4.2 suite stopped matching the moment a lock guard
was inserted as the first line of the functions they were anchored to. The `BUILD_VERSION` mutation
sat pinned at `"4.2"` for an entire version, replacing nothing. Both were found by accident.

So every target must resolve to **exactly one** occurrence. Zero means the marker has gone stale;
more than one means the mutation is ambiguous. Either is a failure of the suite, not a skipped
line, and the summary counts *applied* separately from *caught*:

```
  mutations declared : 26
  mutations applied  : 26
  mutations caught   : 26
  mutations survived : 0
  invalid / stale    : 0
  RESULT: GREEN
```

A run with a stale target is **red even when nothing survived**, because a suite that cannot prove
it broke the code cannot prove the tests caught anything.

Two smaller distinctions the reporter makes:

*Caught by crash.* A non-zero exit is how a mutation is normally judged caught, but a harness that
*threw* never ran its assertions to a conclusion. That still shows the mutation is detectable, so
it is not a survivor — but it is weaker evidence than a named failing assertion, and a harness that
crashed for an unrelated reason would score identically. The acceptance suites now catch their own
exceptions and record them as failures, so this count should stay at zero.

*Benign no-ops.* A few mutations are expected **not** to be caught: they corrupt a stored value
that the page repairs on load, so breaking it changes nothing observable. They document the repair.
They must still resolve exactly once — a benign mutation with a stale marker is just as blind as
any other.

## A warning about `mut4py.py`

It mutates the production source **in place** and restores it after each test, so an interrupted
run can leave the working tree holding a deliberate bug. This has happened: a killed run left
`check_design_ratio` sitting at `if False:` — the 32° invariant switched off in the working tree —
and it was found only because the next run reported that target as stale.

It now restores from an `atexit` hook, turns `SIGTERM`/`SIGINT`/`SIGHUP` into ordinary exits so
that hook runs, and asserts at the end that both files came back to their original bytes. If you
ever `kill -9` it, check `git status` before doing anything else.
