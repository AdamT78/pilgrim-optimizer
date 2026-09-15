"""Rebuild every page under `ui/generated/`, and check that nothing there is a fossil.

    python3 ui/rebuild_ui_pages.py            # rebuild
    python3 ui/rebuild_ui_pages.py --check    # rebuild each page TWICE and diff the two builds

WHY THIS EXISTS

`ui/generated/` is git-ignored, which is right -- a committed output sits there looking
authoritative long after it stopped matching its generator, and this repo has been bitten by that
twice now. Once when the play view compared identical forever because nothing rebuilt it, and once
when the committed board silently reverted to the old duty tile scale.

But ignoring the directory removes the only signal git gave you. `git diff` on anything inside it
reports nothing however much changed, so a page that no longer rebuilds, or rebuilds differently,
says nothing at all. That is what this replaces.

WHAT --check ACTUALLY COMPARES, AND WHY IT CHANGED

It used to diff each rebuilt page against the copy already sitting in `ui/generated/`. That reads
as a strong check and was two weak ones. In CI it was no check at all -- the directory is ignored,
so a fresh checkout has nothing to compare against and the comparison silently did not happen,
leaving a step that only proved the generators do not crash. And locally it failed for the wrong
reason: a page differing from the copy on your disk usually means you had not rebuilt lately, which
is the normal state of an ignored directory and not a fault, so a red run here stopped meaning
anything.

So it builds each page TWICE and diffs those two builds. That tests DETERMINISM, which is the
property worth having and the one that makes every other comparison possible: a page that differs
from itself between builds can never be diffed against anything, by this script or by a person.
It found one -- the layout tool stamped its pages with the wall clock, so two builds a second apart
disagreed by two bytes. Staleness against the disk copy is still reported, as a remark rather than
as a failure.

It also CHECKS ITS OWN COVERAGE, which is the half that is easy to skip: every `.html` sitting in
the output directory that no generator here wrote is reported as a fossil and fails the run. A
rebuild sweep is worth exactly as much as the list of generators behind it is complete.
"""
import os
import pathlib
import subprocess
import sys

UI = pathlib.Path(__file__).resolve().parent
RENDER = UI / "render"
OUT = UI / "generated"

# Each entry is a generator, the arguments the sweep runs it with, and the page it must write.
# The arguments matter for the gothic board: its own default is svg,html,png, and PNG needs
# CairoSVG, which is a heavier dependency than a rebuild sweep should require.
GENERATORS = [
    ("gen_board.py", [], "board-3-2-step1.html"),
    ("gen_picker.py", [], "player-board-picker.html"),
    ("gen_board_gothic.py", ["--formats", "html", "--name", "gothic-board"], "gothic-board.html"),
    ("gen_picker_2.py", [], "gothic-board-picker.html"),
    ("gen_layout_tool.py", [], "layout-tool.html"),
    # `--tiles` is not decoration. Without it this generator runs in shapes-only mode -- it says so,
    # `version A: 0 of 9`, which is correct behaviour and not a fault -- and never reaches the
    # palette code. That palette code is the only thing here that imports from gen_duty_grid, so the
    # cheap invocation would build a page, pass, and prove nothing about the coupling that actually
    # breaks. It costs 4.6s against the sweep's 3.0s, which is the price of the check being real.
    ("gen_picker_grid.py", ["--tiles", "ui/assets-gothic/duty-tiles"], "duty-grid-picker.html"),
    # The game view borrows from gen_board.py by exec, so it breaks if a name there is renamed --
    # which is exactly the coupling a rebuild sweep is for. It also redirects that exec's own page
    # write, so watch for board-3-2-step1.html appearing twice in a run if that ever regresses.
    ("gen_game_view.py", [], "game-view.html"),
    # Named here for the reason the sweep exists. This one reads nine shapes, two colours and a
    # stroke weight out of gen_duty_grid, and every one of those is a name that can be renamed
    # somewhere else -- which is exactly how the two throwaway scripts it replaces died, silently,
    # months before anyone opened them.
    ("gen_border_studio.py", [], "duty-border-studio.html"),
]

# Written as a side effect of a run rather than as a page in its own right.
BYPRODUCTS = {"_picker_scratch.html", "_log_final.html",
              # gen_game_view.py execs gen_board.py to borrow its components, and that file
              # writes its page at module level rather than under a __main__ guard. OUTNAME
              # sends the write here instead of over board-3-2-step1.html, which is the
              # point -- but it does mean every run leaves this behind.
              "_gen_game_view_scratch.html"}


# The two builds are run in timezones fourteen hours apart, and that is not a flourish.
#
# Diffing two builds catches a page that differs from itself -- but a page stamped with the wall
# clock only differs if the two builds straddle a second boundary, and a sweep is fast enough that
# usually they do not. The first version of this check was written, a clock was deliberately put
# back into the layout tool to prove the check worked, and the check said "deterministic": both
# builds had landed inside the same second. A guard that catches a fault four times in ten is worse
# than none, because it is believed.
#
# Changing the timezone between them makes any dependence on local time show up every run rather
# than sometimes -- and it tests the stronger property that is actually wanted: a generated page
# must not depend on WHEN or WHERE it was built. A stamp that describes content survives this; a
# stamp that describes the moment does not, which is the distinction worth enforcing.
TZ_A, TZ_B = "UTC", "Pacific/Kiritimati"          # +00:00 and +14:00


def run(name, argv, tz=None):
    env = None
    if tz:
        env = dict(os.environ, TZ=tz)
    r = subprocess.run([sys.executable, str(RENDER / name), *argv],
                       capture_output=True, text=True, cwd=str(UI.parent), env=env)
    if r.returncode != 0:
        print("FAILED %s\n%s" % (name, r.stderr.strip()[-2000:]))
    return r.returncode == 0


def main(check=False):
    ok = True
    for gen, argv, page in GENERATORS:
        p = OUT / page
        stale = p.read_bytes() if (check and p.exists()) else None

        if not run(gen, argv, tz=TZ_A if check else None):
            ok = False
            continue
        if not p.exists():
            print("FAILED %s did not write %s" % (gen, page))
            ok = False
            continue
        if not check:
            print("%-28s %d KB" % (page, p.stat().st_size // 1024))
            continue

        first = p.read_bytes()
        if not run(gen, argv, tz=TZ_B):            # the second build, and the whole point of --check
            ok = False
            continue
        second = p.read_bytes()

        if first != second:
            print("%-28s NOT DETERMINISTIC -- two builds differ by %d byte(s). Something in "
                  "this page\n%-28s depends on when or where it was built; a clock or a local "
                  "timezone is the usual cause."
                  % (page, sum(a != b for a, b in zip(first, second))
                     + abs(len(first) - len(second)), ""))
            ok = False
        elif stale is not None and stale != first:
            # Informational, and deliberately not a failure. It says the copy you had was older
            # than its generator, which is the normal state of an ignored directory after someone
            # edits a generator -- not a fault, and reporting it as one taught people that a red
            # run here means nothing.
            print("%-28s deterministic; the copy on disk was out of date and has been rebuilt"
                  % page)
        else:
            print("%-28s deterministic" % page)

    written = {page for _g, _a, page in GENERATORS} | BYPRODUCTS
    fossils = sorted(p.name for p in OUT.glob("*.html") if p.name not in written)
    if fossils:
        print("\nfossils in ui/generated/ that no generator writes: %s" % ", ".join(fossils))
        print("Either add its generator above, or delete it -- a page nothing rebuilds compares "
              "identical forever, through any change to anything it is drawn from.")
        ok = False

    for junk in BYPRODUCTS:
        # Tidy-up must never decide the result of the sweep. On a filesystem that refuses the
        # unlink -- a read-only mount, or a sandbox that forbids deletes -- the byproduct simply
        # stays, and it is inside an ignored directory, so nothing downstream cares.
        try:
            (OUT / junk).unlink(missing_ok=True)
        except OSError:
            pass

    print("\n%s" % ("all pages rebuilt" if ok else "PROBLEMS -- see above"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(check="--check" in sys.argv))
