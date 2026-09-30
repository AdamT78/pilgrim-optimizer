#!/usr/bin/env python3
"""Break each new caption-size behaviour on purpose and see whether anything notices.

A guard nobody has broken is a guard nobody has tested. Each mutation below is a plausible
mistake -- a number changed, a call moved, a fallback written the lazy way -- and each must come
back CAUGHT. SURVIVED means the test alongside it is decorative.

EXACTLY-ONCE TARGETING: a marker that matches zero or many places is INVALID and reported as
such, because a mutation that did not apply proves nothing and quietly reads as a pass.
"""
import pathlib
import subprocess
import sys

# The repository root: this file lives in tests/layout_lab/, two levels down.
ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent
TMPL = ROOT / "ui/board_v2/layout_lab/duty_wheel_layout_lab.html.tmpl"
GEN = ROOT / "ui/board_v2/layout_lab/generate_layout_lab.py"

MUTS = [
    (GEN, "the default size drifts from the stylesheet fallback",
     "TITHE_LABEL_SIZE = 17", "TITHE_LABEL_SIZE = 19"),
    (GEN, "the city default drifts",
     "CITY_LABEL_SIZE = 13", "CITY_LABEL_SIZE = 15"),
    (GEN, "the two captions collapse to one size",
     "CITY_LABEL_SIZE = 13", "CITY_LABEL_SIZE = TITHE_LABEL_SIZE"),
    (GEN, "the tithe default stops reaching the state",
     '"tithe": dict(TITHE, label="TAKE TITHE", labelSize=TITHE_LABEL_SIZE,',
     '"tithe": dict(TITHE, label="TAKE TITHE", labelSize=20,'),
    (GEN, "the city default stops reaching the state",
     'label="THE CITY", labelSize=CITY_LABEL_SIZE,',
     'label="THE CITY", labelSize=11,'),

    (TMPL, "the stylesheet fallback drifts from the default",
     "font:600 var(--cap,17px)/1.2 Georgia,serif", "font:600 var(--cap,15px)/1.2 Georgia,serif"),
    (TMPL, "the city stylesheet fallback drifts",
     "#cityObj .cl{font:600 var(--cap,13px)/1.2", "#cityObj .cl{font:600 var(--cap,11px)/1.2"),

    # The fit pass's ORDERING mutations moved to mut45b.py with the band rewrite, which is
    # where the code they break now lives. Splitting them from the size mutations keeps each
    # suite's failures pointing at the change that owns them.
    (TMPL, "the reserve stops being measured and is guessed again",
     "TITHE_CAP_H = tl ? tl.offsetHeight : null;",
     "TITHE_CAP_H = tl ? Math.round(1.2 * titheCapSize()) : null;"),
    (TMPL, "a stale measurement survives the card being absent",
     "  TITHE_CAP_H = null;\n  if (titheMode", "  if (titheMode"),
    (TMPL, "the old fixed chrome comes back",
     "function titheChrome(){ return 10 + titheReserve() + 4; }",
     "var TITHE_CHROME = 50;\nfunction titheChrome(){ return TITHE_CHROME; }"),

    (TMPL, "the City's two phases get different sizes",
     "body = '<div class=cl style=\"--cap:' + cityCapSize() + 'px\">' + esc(ih.label)",
     "body = '<div class=cl style=\"--cap:' + clampCap(13) + 'px\">' + esc(ih.label)"),

    (TMPL, "the shared bound is written out longhand again",
     "function clampCap(v){ return clamp(Math.round(+v), CAP_MIN, CAP_MAX); }",
     "function clampCap(v){ return clamp(Math.round(+v), 8, 60); }"),
    (TMPL, "the artwork stops sharing the bound",
     "e.labelSize = clampCap(e.labelSize);",
     "e.labelSize = clamp(Math.round(e.labelSize), 6, 72);"),

    (TMPL, "a missing size and a zero one stop being different problems",
     "  return (v === undefined || v === null || isNaN(+v)) ? clampCap(dflt) : clampCap(v);",
     "  return clampCap(+v || dflt);"),
    (TMPL, "the tithe size stops being normalised on load",
     "  S.tithe.labelSize = capFor(S.tithe.labelSize, DEFAULT_STATE.tithe.labelSize);\n", ""),
    (TMPL, "the city size stops being normalised on load",
     "  S.city.labelSize = capFor(S.city.labelSize, DEFAULT_STATE.city.labelSize);\n", ""),

    (TMPL, "the tithe size stops travelling into production",
     "            labelSize: titheCapSize(),\n", ""),
    (TMPL, "the city size stops travelling into production",
     ", labelSize: cityCapSize()}", "}"),
]


def run():
    r = subprocess.run([sys.executable, "-m", "pytest", "tests/layout_lab/",
                        "--noconftest", "-q", "-x", "--no-header"],
                       cwd=ROOT, capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main():
    base_rc, base_out = run()
    if base_rc:
        print("the suite is not green before we start -- nothing to learn from mutating it")
        print(base_out[-1500:])
        return 1
    print("baseline green\n")

    # CRASH-SAFE. A previous run of this was killed by a timeout mid-mutation, and because the
    # restore lived only in a finally block the mutated file was left on disk -- the next run
    # then reported the suite red and blamed the code. The originals go to disk BEFORE anything
    # is touched, and any run finding them there puts them back first.
    stash = HERE / ".mut45_stash"
    stash.mkdir(exist_ok=True)
    for path in {m[0] for m in MUTS}:
        keep = stash / path.name
        if keep.exists():
            path.write_text(keep.read_text(encoding="utf-8"), encoding="utf-8")
            print("restored %s from a previous interrupted run" % path.name)
        else:
            keep.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    originals = {p: p.read_text(encoding="utf-8") for p in {m[0] for m in MUTS}}
    tally = {"CAUGHT": 0, "SURVIVED": 0, "INVALID": 0, "NO-OP": 0}
    survivors = []
    try:
        for path, why, old, new in MUTS:
            src = originals[path]
            n = src.count(old)
            if n != 1:
                print("INVALID   %-58s (%d matches)" % (why, n))
                tally["INVALID"] += 1
                continue
            if old == new:
                tally["NO-OP"] += 1
                continue
            path.write_text(src.replace(old, new, 1), encoding="utf-8")
            rc, out = run()
            path.write_text(src, encoding="utf-8")
            if rc:
                first = ""
                for line in out.splitlines():
                    if line.startswith("FAILED") or "::" in line and "Error" in line:
                        first = line.split("::")[-1].split(" ")[0][:52]
                        break
                print("CAUGHT    %-58s %s" % (why, first))
                tally["CAUGHT"] += 1
            else:
                print("SURVIVED  %s" % why)
                tally["SURVIVED"] += 1
                survivors.append(why)
    finally:
        for p, s in originals.items():
            p.write_text(s, encoding="utf-8")
        for f in stash.iterdir():
            f.unlink()
        stash.rmdir()

    print("\n%s" % "  ".join("%s %d" % (k, v) for k, v in tally.items()))
    if survivors:
        print("\nnothing noticed these:")
        for s in survivors:
            print("  - %s" % s)
    return 1 if survivors or tally["INVALID"] else 0


if __name__ == "__main__":
    sys.exit(main())
