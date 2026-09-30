#!/usr/bin/env python3
"""Break the band alignment on purpose and see whether accept45 notices.

The pytest guards check the SHAPE of the arithmetic; this checks the RESULT. Both are needed:
a shape guard cannot tell you that two baselines coincide, and the browser suite cannot tell you
that the max is taken over the right set -- it only sees the consequence.

Each mutation is a plausible mistake. CAUGHT means accept45 failed. SURVIVED means it did not,
and a matrix that passes whatever the code does is a matrix that proves nothing.
"""
import pathlib
import subprocess
import sys

# The repository root: this file lives in tests/layout_lab/, two levels down.
ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent
TMPL = ROOT / "ui/board_v2/layout_lab/duty_wheel_layout_lab.html.tmpl"
GEN = ROOT / "ui/board_v2/layout_lab/generate_layout_lab.py"
PAGE = HERE / "lab.html"

MUTS = [
    ("the line is taken from the artwork alone, not the tallest caption",
     "function bandTopInset(){ return CAP_PAD + maxOf(topCapSizes(), capBase); }",
     "function bandTopInset(){ return CAP_PAD + capBase(nameSizeOf(artOf('left'))); }"),
    ("the bottom line likewise",
     "function bandBottomInset(){ return CAP_PAD + maxOf(bottomCapSizes(), capDrop); }",
     "function bandBottomInset(){ return CAP_PAD + capDrop(artOf('left').labelSize); }"),
    ("a hidden right slot stops counting, so the band jumps between duties",
     'return [nameSizeOf(artOf("left")), nameSizeOf(artOf("right")), cityCapSize()];',
     'return [nameSizeOf(artOf("left"))].concat(artUsed("right") '
     '? [nameSizeOf(artOf("right"))] : []).concat([cityCapSize()]);'),
    ("the City is left off the top line",
     'return [nameSizeOf(artOf("left")), nameSizeOf(artOf("right")), cityCapSize()];',
     'return [nameSizeOf(artOf("left")), nameSizeOf(artOf("right"))];'),
    ("the Tithe is left off the bottom line",
     'return [artOf("left").labelSize, artOf("right").labelSize, titheCapSize()];',
     'return [artOf("left").labelSize, artOf("right").labelSize];'),

    ("one baseline fraction is scaled instead of measured per size",
     "  probe.style.fontSize = F + \"px\";",
     "  probe.style.fontSize = \"100px\"; F = 100;"),
    ("the baseline fraction is a constant",
     "function capBase(size){",
     "function capBase(size){ return Math.round(size) * 0.93; // eslint-disable-line\n"),
    ("the drop to the line box's bottom is measured from the top instead",
     "function capDrop(size){ return Math.round(size) * CAP_LH - capBase(size); }",
     "function capDrop(size){ return capBase(size); }"),

    ("the City's border is not accounted for",
     'city.style.paddingTop = capPadTop(cityCapSize(), BAND_BORDER) + "px";',
     'city.style.paddingTop = capPadTop(cityCapSize()) + "px";'),
    ("the Tithe's border is not accounted for",
     'tl.style.bottom = capPadBottom(titheCapSize(), BAND_BORDER) + "px";',
     'tl.style.bottom = capPadBottom(titheCapSize()) + "px";'),
    ("the artwork captions stop being dropped onto the line",
     '    if (anm) anm.style.paddingTop = capPadTop(nameSizeOf(e)) + "px";\n'
     '    if (cap) cap.style.paddingBottom = capPadBottom(e.labelSize) + "px";\n', ""),
    ("the City heading stops being dropped onto the line",
     '  if (city) city.style.paddingTop = capPadTop(cityCapSize(), BAND_BORDER) + "px";\n', ""),
    ("the Tithe caption stops being dropped onto the line",
     '  if (tl) tl.style.bottom = capPadBottom(titheCapSize(), BAND_BORDER) + "px";\n', ""),

    ("the caption's height is read before it has been moved",
     '  if (tl) tl.style.bottom = capPadBottom(titheCapSize(), BAND_BORDER) + "px";\n'
     '  // AFTER the offset is set, because the reserve is measured against where the caption '
     'ended up.\n  TITHE_CAP_H = tl ? tl.offsetHeight : null;',
     '  TITHE_CAP_H = tl ? tl.offsetHeight : null;\n'
     '  if (tl) tl.style.bottom = capPadBottom(titheCapSize(), BAND_BORDER) + "px";'),
    ("the reserve stops following the caption",
     "  return Math.round(capPadBottom(titheCapSize(), BAND_BORDER))\n"
     "       + Math.round(titheCapHeight()) + TITHE_CAP_AIR;",
     "  return 36;"),
    ("the City caption goes back to its own line-height",
     "#cityObj .cl{font:600 var(--cap,13px)/1.2 Georgia,serif",
     "#cityObj .cl{font:600 var(--cap,13px)/1.1 Georgia,serif"),
    ("the fit pass runs before the stage has the nodes",
     "  st.appendChild(frag);\n  // NOW the caption has a height, so now the card can reserve "
     "the room it needs. Before\n  // paintMetrics(), because the overflow reading it paints is "
     "measured against that reserve.\n  fitBandCaptions();",
     "  fitBandCaptions();\n  st.appendChild(frag);"),
    ("a size out of range is thrown away instead of bounded",
     "  return (v === undefined || v === null || isNaN(+v)) ? clampCap(dflt) : clampCap(v);",
     "  return clampCap(+v > CAP_MAX || +v < CAP_MIN ? dflt : v);"),
    ("the Tithe control stops reaching the caption",
     "                    + '<div class=tl style=\"--cap:' + titheCapSize() + 'px\">' "
     "+ esc(T.label)",
     "                    + '<div class=tl style=\"--cap:17px\">' + esc(T.label)"),
    ("the City control stops reaching the heading",
     "body = '<div class=cl style=\"--cap:' + cityCapSize() + 'px\">' + esc(c.label)",
     "body = '<div class=cl style=\"--cap:13px\">' + esc(c.label)"),
]


def build():
    r = subprocess.run([sys.executable, "ui/board_v2/layout_lab/generate_layout_lab.py",
                        "--out", str(PAGE)], cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0, (r.stdout or "") + (r.stderr or "")


def accept():
    """The browser suite AND the source guards, because they catch different things.

    A mutation that reorders two statements with no visual consequence is invisible to a suite
    that only looks at pixels, and a misplaced baseline is invisible to one that only reads the
    file. Running one of them and reporting "nothing noticed" would be a claim about the other.
    """
    r = subprocess.run(["node", "tests/layout_lab/accept45.mjs"],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        return r.returncode, (r.stdout or "")
    g = subprocess.run([sys.executable, "-m", "pytest", "tests/layout_lab/",
                        "--noconftest", "-q", "-x", "--no-header"],
                       cwd=ROOT, capture_output=True, text=True)
    if g.returncode:
        line = next((l for l in (g.stdout or "").splitlines() if l.startswith("FAILED")), "")
        return g.returncode, "FAIL pytest :: " + line.split("::")[-1]
    return 0, (r.stdout or "")


def main():
    ok, out = build()
    if not ok:
        print("the page does not build before we start:\n" + out[-800:])
        return 1
    rc, out = accept()
    if rc:
        print("accept45 is not green before we start:\n"
              + "\n".join(l for l in out.splitlines() if l.startswith("FAIL"))[:1200])
        return 1
    print("baseline green: " + out.strip().splitlines()[-1] + "\n")

    stash = HERE / ".mut45b_stash"
    stash.mkdir(exist_ok=True)
    for path in (TMPL, GEN):
        keep = stash / path.name
        if keep.exists():
            path.write_text(keep.read_text(encoding="utf-8"), encoding="utf-8")
            print("restored %s from an interrupted run" % path.name)
        else:
            keep.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    original = TMPL.read_text(encoding="utf-8")

    caught = survived = invalid = 0
    losers = []
    try:
        for why, old, new in MUTS:
            n = original.count(old)
            if n != 1:
                print("INVALID   %-58s (%d matches)" % (why, n))
                invalid += 1
                continue
            TMPL.write_text(original.replace(old, new, 1), encoding="utf-8")
            built, berr = build()
            if not built:
                print("CAUGHT    %-58s (the page refused to build)" % why)
                caught += 1
                continue
            rc, out = accept()
            if rc:
                first = next((l for l in out.splitlines() if l.startswith("FAIL")), "")
                print("CAUGHT    %-58s %s" % (why, first[5:60].strip()))
                caught += 1
            else:
                print("SURVIVED  %s" % why)
                survived += 1
                losers.append(why)
    finally:
        TMPL.write_text(original, encoding="utf-8")
        for f in stash.iterdir():
            f.unlink()
        stash.rmdir()
        build()

    print("\nCAUGHT %d  SURVIVED %d  INVALID %d" % (caught, survived, invalid))
    if losers:
        print("\nnothing noticed these:")
        for s in losers:
            print("  - %s" % s)
    return 1 if losers or invalid else 0


if __name__ == "__main__":
    sys.exit(main())
