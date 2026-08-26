# Working in this repository

Pilgrim is a deterministic rules engine with a play view on top. The engine decides; the
page displays. **The page must never re-implement a rule.** If the browser has to know
something to draw itself, the server payload should say it — a client that derives a rule
locally is a bug even when it renders correctly.

## Before you change anything

- Work in the existing checkout. Do not create branches, worktrees, or stashes; the branch
  you are on is the branch that was intended.
- Read the surrounding code before editing it. This codebase carries long comments that
  explain *why* a shape is what it is, and most of them were written after something broke.
- If an instruction you were given looks wrong once you have read the code, say so before
  implementing it. A prompt is a hypothesis, not a specification.

## Running the tests

Python 3.13, `pip install -e ".[dev]"`. Three PR-gated lanes, matching
`.github/workflows/tests.yml`:

```
pytest -m "not slow"                                    # the PR gate
pytest -m slow -p no:cacheprovider \
  --ignore=tests/test_play_view_clicks.py                 # deep guards
pytest -q -p no:cacheprovider tests/test_play_view_clicks.py   # browser click guards, also the PR gate
pytest                                                  # all three lanes in one invocation
```

`slow` is set two ways: `tests/test_play_view_clicks.py` marks its whole module, and
`tests/conftest.py` marks anything using the `deep_actions` fixture. The click suite is slow but
still gates pull requests, because the PR job runs that file explicitly. The deep-fixture tests
have their own PR step, excluding the click module so they run once — so if you touch anything the
deep fixture reaches, run `pytest -m slow` yourself.

Use `-x -p no:cacheprovider` while iterating. **Never pipe pytest to `tail` or `head`** — the
truncated output hides which test failed and why.

### When the sandbox blocks a lane

`tests/test_play_server.py` and `tests/test_play_view_clicks.py` bind a real server on
`127.0.0.1:0`, and the click suite launches Chromium through Playwright. If the environment
denies the bind or refuses to start the browser:

- **Stop and say so.** Report which lane could not run and why.
- Do not skip those tests, mock the server, or reduce the suite to the parts that happen to run.
- Do not report a lane as passing when part of it never executed.

A truthful "I could not run this" is worth more than a green summary that means nothing.

## Tests are load-bearing

- **Do not delete a test to make a change pass.** If a test genuinely no longer applies, say
  which property it guarded and where that property is asserted now. If the answer is
  "nowhere", the property needs a new home before the test goes.
- **Break every new or changed assertion once**, confirm it fails for the reason you expect,
  then restore it. Report what you saw. An assertion never observed failing is not known to work.
- **A test that runs over a population must keep running over a population.** Narrowing a
  corpus walk to one scenario silently destroys its value; if a filter is needed, add a floor
  under how many cases survive it.
- Prefer waiting on a condition to sleeping. In the browser suite, `page.wait_for_selector`
  on a marker that actually changes across the transition; a longer `wait_for_timeout` only
  moves a race somewhere less visible.

## Corpus floors shrink on purpose

Building effects are being moved out of `FullTurnAction` into committed turn steps, so action
counts at fixed positions fall branch by branch. Assertions like `len(actions) > 700` are
floors under a population, not measurements.

When one fails, do not simply lower the number. Ask first whether the property it guards still
exists somewhere: usually it has moved to `turn_steps` rather than disappeared, and the fix is
to assert it there. Only then re-floor, with a comment saying why the number moved.

## Refactors must prove themselves

Two tripwires dump generation output in order, which is what a saved search depends on:

```
python tools/capture_legal_actions.py <dir>
python tools/capture_turn_steps.py <dir>
```

For any change that claims to preserve behaviour: capture before, capture after, `diff -r` both
directories, and show that both diffs are empty. If a diff is non-empty, report it — do not
adjust the tripwire to agree with the new output.

## Style and scope

- ruff, `line-length = 100`. It is not wired into CI, so run `ruff check` yourself.
- Comments say *why*, not what. Match the register of what is already there.
- Stay inside the change you were asked for. Do not rename unrelated symbols, rewrite nearby
  docstrings, or reformat untouched code.
- **Never satisfy an acceptance criterion literally at the cost of unrelated code.** If a
  prompt says a string must not appear and the only way to achieve that is editing code the
  task has nothing to do with, the criterion is wrong. Say so instead of complying.
- Do not add speculative work — precomputing a result "in case it is needed" has cost real
  wall-clock time here more than once.
- Screenshots belong in `screenshots/` inside the repo, never `/tmp`.

## The play view

`tools/ui_debug/play_view_turn.js` holds the turn script. `render_play_view.py` reads it at
call time into the module-level `_TURN_SCRIPT`; keep that indirection, a test monkeypatches it.

`tests/turn_script_harness.js` runs the shipped script against a stub board under node. CI declares
Node with `actions/setup-node` and checks it before pytest, so its harness tests run in the fast
lane. Locally they remain gated on node being present and skip when it is absent; do not count a
locally skipped harness test as coverage.

## Reporting back

State what you ran and what it printed. If something did not run, say which and why. If you
believe part of the request was mistaken, say that too — being told the plan was wrong is
cheaper than discovering it after merge.
