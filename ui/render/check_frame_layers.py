"""Prove that splitting the frame into layers did not change what the board looks like.

    python3 ui/render/check_frame_layers.py

WHAT THIS IS FOR

`frame_base.png` used to be the whole frame: stonework, gold, tower, scroll and a red drape in one
image, drawn by one <image> in the template. It is now four layers, so that a seat's colour can be a
swapped drape instead of a second copy of the frame. That refactor has a failure mode that looks
fine in isolation: get the z-order wrong, or place a layer a pixel off, or drop one, and the board
still renders as a perfectly plausible gothic frame. You only see it next to the original.

So this builds both -- the layered board wearing the red source drape, and a board built from the
old single-image markup -- renders them at the frame's native 1905 px so nothing is resampled, and
requires that every pixel agrees. Native width matters: composite-then-scale and scale-then-
composite are not the same operation, so at any other size a genuine match would still show small
differences along the artwork's edges and the test would have to accept a tolerance, which is
exactly the slack a real one-pixel offset would hide in.

Being an alpha split, the layers cover disjoint pixels, so an exact match is available and anything
less than exact is a bug.
"""
import pathlib
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET

HERE = pathlib.Path(__file__).resolve().parent
UI = HERE.parent
SVG_NS = "http://www.w3.org/2000/svg"
NATIVE_W, NATIVE_H = 1905, 826


def q(tag):
    return f"{{{SVG_NS}}}{tag}"


def load_assembler():
    import importlib.util
    spec = importlib.util.spec_from_file_location("assembler", HERE / "gen_board_gothic.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def legacy_template(path, out):
    """The template as it was: one <image> for the whole frame, no drape layers, no turn."""
    root = ET.parse(path).getroot()
    parents = {c: p for p in root.iter() for c in p}
    frame = None
    for node in list(root.iter(q("image"))):
        role = node.get("data-asset-role")
        if role == "frame_base":
            frame = node
            node.set("data-asset-role", "frame")
            node.set("href", "../frames/frame_base.png")
        elif role == "frame_ornaments":
            parents[node].remove(node)
    # The turn holder is emptied rather than deleted. An empty <g> draws nothing, so the legacy
    # board is unchanged, and the assembler's guard that the template still HAS a turn holder stays
    # armed -- weakening that guard to let this test run would be trading the real check for the
    # test of it.
    holder = root.find(f".//{q('g')}[@data-turn]")
    if holder is not None:
        for child in list(holder):
            holder.remove(child)
    if frame is None:
        raise SystemExit("template has no frame_base role; nothing to compare against")
    ET.ElementTree(root).write(out, encoding="unicode")


def build(asm, assets_dir, template, config, out_svg):
    layout = asm.read_json(assets_dir / "metadata" / "layout.json")
    root = ET.parse(template).getroot()
    asm.apply_config(root, config, layout)
    asm.embed_assets_once(root, assets_dir)
    asm.assert_no_duplicated_payloads(root)
    out_svg.write_text(ET.tostring(root, encoding="unicode"), encoding="utf-8")


PAGE = """<!doctype html><meta charset="utf-8"><style>
html,body{margin:0;padding:0;background:#123d2c}
svg{display:block;width:%dpx;height:%dpx}
</style>
%s
"""


def shoot(pages, out_dir):
    """Render each page at native size. One browser, so the two renders share every setting."""
    from playwright.sync_api import sync_playwright
    shots = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--no-sandbox", "--disable-gpu",
                                           "--disable-dev-shm-usage"])
        page = browser.new_page(viewport={"width": NATIVE_W, "height": NATIVE_H},
                                device_scale_factor=1)
        for name, html_path in pages:
            page.goto(html_path.resolve().as_uri())
            page.wait_for_timeout(1200)
            shot = out_dir / f"{name}.png"
            page.query_selector("svg").screenshot(path=str(shot))
            shots.append(shot)
        browser.close()
    return shots


def main():
    try:
        import numpy as np
        from PIL import Image
        import playwright  # noqa: F401  -- imported here only so a missing browser fails early
    except ImportError as exc:
        raise SystemExit(
            "this check renders two boards and compares them, so it needs pillow, numpy and "
            "playwright (%s).\n"
            "    pip install pillow numpy playwright && python3 -m playwright install chromium"
            % exc)

    asm = load_assembler()
    assets = UI / "assets-gothic"
    template = assets / "template" / "player_board_template.svg"
    base_config = asm.read_json(assets / "production_test_config.json")

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="framecheck-"))
    try:
        # The layered board, wearing the source drape the original frame had baked in.
        # The seat is kept so that everything a seat supplies but the frame -- the acolyte cube --
        # still resolves; apply_seat fills only what is not already set, so the explicit red layers
        # below win. Both boards therefore differ in the frame and in nothing else.
        layered_cfg = dict(base_config)
        layered_cfg["turn"] = "lit"
        layered_cfg.update({
            "frame_base": "frames/frame_base_nocloth.png",
            "frame_ornaments": "frames/frame_ornaments.png",
            "cloth_lit": "frames/cloth_red.png",
            "cloth_dim": "frames/cloth_red.png",
            "gems": "frames/stones_red.png",
        })
        asm.apply_seat(layered_cfg)
        build(asm, assets, template, layered_cfg, tmp / "layered.svg")

        # The same board from the markup this replaced.
        legacy_template(template, tmp / "legacy_template.svg")
        legacy_cfg = dict(layered_cfg)
        legacy_cfg.pop("turn", None)
        for role in ("frame_base", "frame_ornaments", "cloth_lit", "cloth_dim"):
            legacy_cfg.pop(role, None)
        legacy_cfg["frame"] = "frames/frame_base.png"
        legacy_cfg["gems"] = "frames/stones_red.png"
        # apply_seat would reject a config carrying 'frame'; this path deliberately bypasses it,
        # because reproducing the old markup is the whole point.
        build(asm, assets, tmp / "legacy_template.svg", legacy_cfg, tmp / "legacy.svg")

        pages = []
        for name in ("layered", "legacy"):
            svg = (tmp / f"{name}.svg").read_text(encoding="utf-8")
            html = tmp / f"{name}.html"
            html.write_text(PAGE % (NATIVE_W, NATIVE_H, svg), encoding="utf-8")
            pages.append((name, html))

        a, b = (np.array(Image.open(p).convert("RGB")).astype(int) for p in shoot(pages, tmp))
        if a.shape != b.shape:
            print("FAIL  different sizes: layered %s, legacy %s" % (a.shape, b.shape))
            return 1
        diff = np.abs(a - b)
        differing = int((diff.max(axis=2) > 0).sum())
        print("rendered both at %d x %d" % (NATIVE_W, NATIVE_H))
        print("  differing pixels : %d of %d" % (differing, a.shape[0] * a.shape[1]))
        print("  largest channel  : %d" % diff.max())
        if differing:
            ys, xs = np.where(diff.max(axis=2) > 0)
            print("  bounding box     : x %d..%d  y %d..%d" % (xs.min(), xs.max(),
                                                               ys.min(), ys.max()))
            Image.fromarray((diff.max(axis=2) > 0).astype("uint8") * 255).save(tmp / "diff.png")
            print("\nFAIL  the layered frame does not reproduce the original board.")
            print("      diff mask kept at %s" % (tmp / "diff.png"))
            return 1
        print("\nthe layered frame reproduces the original board exactly")
        return 0
    finally:
        if "--keep" not in sys.argv:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
