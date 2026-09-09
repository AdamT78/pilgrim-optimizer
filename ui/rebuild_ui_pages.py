"""Rebuild every page under `ui/generated/`, and check that nothing there is a fossil.

    python3 ui/rebuild_ui_pages.py            # rebuild
    python3 ui/rebuild_ui_pages.py --check    # rebuild into a temp dir and diff

WHY THIS EXISTS

`ui/generated/` is git-ignored, which is right -- a committed output sits there looking
authoritative long after it stopped matching its generator, and this repo has been bitten by that
twice now. Once when the play view compared identical forever because nothing rebuilt it, and once
when the committed board silently reverted to the old duty tile scale.

But ignoring the directory removes the only signal git gave you. `git diff` on anything inside it
reports nothing however much changed, so a page that no longer rebuilds, or rebuilds differently,
says nothing at all. That is what this replaces.

It also CHECKS ITS OWN COVERAGE, which is the half that is easy to skip: every `.html` sitting in
the output directory that no generator here wrote is reported as a fossil and fails the run. A
rebuild sweep is worth exactly as much as the list of generators behind it is complete.
"""
import pathlib
import shutil
import subprocess
import sys
import tempfile

UI = pathlib.Path(__file__).resolve().parent
RENDER = UI / "render"
OUT = UI / "generated"

# Each entry is a generator and the page it is expected to write.
GENERATORS = [
    ("gen_board.py", "board-3-2-step1.html"),
    ("gen_picker.py", "player-board-picker.html"),
]

# Written as a side effect of a run rather than as a page in its own right.
BYPRODUCTS = {"_picker_scratch.html", "_log_final.html"}


def run(name):
    r = subprocess.run([sys.executable, str(RENDER / name)],
                       capture_output=True, text=True, cwd=str(UI.parent))
    if r.returncode != 0:
        print("FAILED %s\n%s" % (name, r.stderr.strip()[-2000:]))
    return r.returncode == 0


def main(check=False):
    before = {}
    if check:
        for _g, page in GENERATORS:
            p = OUT / page
            if p.exists():
                before[page] = p.read_bytes()

    ok = True
    for gen, page in GENERATORS:
        if not run(gen):
            ok = False
            continue
        p = OUT / page
        if not p.exists():
            print("FAILED %s did not write %s" % (gen, page))
            ok = False
            continue
        if check and page in before:
            moved = before[page] != p.read_bytes()
            print("%-28s %s" % (page, "CHANGED" if moved else "unchanged"))
            if moved:
                ok = False
        elif not check:
            print("%-28s %d KB" % (page, p.stat().st_size // 1024))

    written = {page for _g, page in GENERATORS} | BYPRODUCTS
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
