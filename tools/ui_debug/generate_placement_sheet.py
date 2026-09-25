"""Every arrangement the placement rules produce, on one page, from the file that decides them.

    python3 tools/ui_debug/generate_placement_sheet.py --open

WHAT THIS IS FOR

`ui/assets-gothic/metadata/duty_placement.json` decides how acolyte sculpts stand on a duty
tile. Its numbers are small and abstract -- a spread, a set-back, a rank gap, all bare
pixels with no figure beside them -- and there is
no way to tell from reading them whether 2+1+1 will look deliberate or like a pile-up. This page
draws every case the rules will actually meet, so the file can be judged by its output rather
than by its values.

Change a number in the file, run this, look. That is the whole loop.

IT READS THE FILE, AND YOU CAN PROVE IT

The run prints the settings it used for every size. To check they came from the file rather than
from anywhere else, put an unmistakable value in it -- 999 -- and see it on the page. A tool
that claims to read a file is worth exactly as much as your ability to falsify the claim.

WHY ORDERED CASES, NOT SHAPES

Elsewhere in this toolchain the fifteen distinct SHAPES matter -- 2+1+1 counted once, whoever
owns the pair. Not here. This page is about what a seat's own sculpts look like, so `p1 p1 p2`
and `p2 p2 p1` are two different pictures and both are drawn. The seat colours are the point.

THE RULES ARE NOT COPIED HERE

`placement()` and `figures()` are imported from generate_duty_board_check.py, which owns them.
A second copy of the validator would drift from the first the day someone widens a range, and
both pages would then disagree about what a valid file is while each looked entirely correct.
"""

import argparse
import html
import importlib.util
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "generated" / "placement_sheet.html"


def _board_module():
    """generate_duty_board_check.py, imported for the two functions it owns.

    Loaded by path rather than by name because it is a script rather than a package module, and
    because importing it must not depend on the caller's working directory.
    """
    sys.path.insert(0, str(ROOT / "ui" / "render"))
    spec = importlib.util.spec_from_file_location(
        "generate_duty_board_check", HERE / "generate_duty_board_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# The cases, as counts per seat. Ordered rather than collapsed: whose sculpts they are changes
# the picture, because `grouped` sorts by seat and the colours sit where the sort puts them.
CASES = [
    ("one acolyte, p1",        (1, 0, 0)),
    ("one acolyte, p2",        (0, 1, 0)),
    ("one acolyte, p3",        (0, 0, 1)),
    ("one each, two seats",    (1, 1, 0)),
    ("one each, three seats",  (1, 1, 1)),
    ("a pair, one seat",       (2, 0, 0)),
    ("2 + 1",                  (2, 1, 0)),
    ("1 + 2",                  (1, 2, 0)),
    ("2 + 1 + 1",              (2, 1, 1)),
    ("1 + 2 + 1",              (1, 2, 1)),
    ("1 + 1 + 2",              (1, 1, 2)),
    ("2 + 2",                  (2, 2, 0)),
    ("three, one seat",        (3, 0, 0)),
    ("3 + 1",                  (3, 1, 0)),
    ("3 + 1 + 1",              (3, 1, 1)),
    ("2 + 2 + 1",              (2, 2, 1)),
    ("3 + 2",                  (3, 2, 0)),
    ("four, one seat",         (4, 0, 0)),
    ("4 + 1",                  (4, 1, 0)),
    ("five, one seat",         (5, 0, 0)),
]

GROUND = "#17130d"

# THE DRAWING RULES LIVE IN ONE FILE -- formation, seat order and the depth cue -- inlined
# into every page that draws acolytes. The formation was written out three times and the depth
# cue twice; they agreed only because they had been copied from each other.
RULES_JS = HERE / "duty_sculpt_rules.js"

# WHICH KEYS THE BUTTON WRITES, AND INTO WHICH FILE. Handed to the page as well as used here,
# because the button has two paths -- POST to this generator when served, download when the page
# was opened as a file -- and they must merge the same keys into the same documents. They did
# not: the offline path wrote the wire payload under the name of the placement file, a shape
# that file never has, carrying the ground assignments in a key nothing reads them from.
PLACEMENT_KEYS = ("spread", "back", "rank", "order", "depth", "frame")
GROUND_KEYS = ("by_duty", "grounds", "lift")


def save_settings(board, sent):
    """Write the tuned numbers back into the placement file.

    MERGED, NOT OVERWRITTEN. The file carries more prose than numbers -- why the set is one set,
    what each control costs, what was measured -- and a save that replaced the document would
    throw all of it away the first time someone nudged a slider.

    Validated before it touches the disk, with the same rules the generator reads by, so the
    button cannot write a file the tool would then refuse to load.
    """
    current = json.loads(board.PLACEMENT.read_text(encoding="utf-8"))
    merged = dict(current)
    clean = {}
    for key in ("spread", "back", "rank"):
        if key not in sent:
            raise ValueError("no %s in what the page sent" % key)
        value = sent[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("%s is %r, want a non-negative whole number" % (key, value))
        clean[key] = value
    if sent.get("order") not in ("grouped", "arrival"):
        raise ValueError("order is %r, want grouped or arrival" % sent.get("order"))
    clean["order"] = sent["order"]
    depth = sent.get("depth") or {}
    if depth.get("mode") not in ("haze", "dark", "off"):
        raise ValueError("depth.mode is %r, want haze, dark or off" % depth.get("mode"))
    if isinstance(depth.get("amount"), bool) or not isinstance(depth.get("amount"), int) \
            or not 0 <= depth["amount"] <= 100:
        raise ValueError("depth.amount is %r, want a whole number 0-100" % depth.get("amount"))
    if isinstance(depth.get("full_at"), bool) or not isinstance(depth.get("full_at"), int) \
            or depth["full_at"] <= 0:
        raise ValueError("depth.full_at is %r, want a positive whole number" % depth.get("full_at"))
    clean["depth"] = {"mode": depth["mode"], "amount": depth["amount"],
                      "full_at": depth["full_at"]}
    # The frame, when the page is showing the wheel. Same rules the generator reads by, so the
    # button cannot write a file the tool would then refuse to load.
    frame = sent.get("frame")
    if frame is not None:
        for key in ("w", "h"):
            value = frame.get(key)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError("frame.%s is %r, want a positive whole number" % (key, value))
        drop = frame.get("drop", 0)
        if isinstance(drop, bool) or not isinstance(drop, int):
            raise ValueError("frame.drop is %r, want a whole number" % drop)
        clean["frame"] = {"w": frame["w"], "h": frame["h"], "drop": drop}

    # MERGED THROUGH THE ONE LIST the page is also given, so a key this function learns to
    # validate but nobody adds to PLACEMENT_KEYS is dropped here loudly rather than written by
    # one save path and not the other.
    if set(clean) - set(PLACEMENT_KEYS):
        raise ValueError("validated %s, which PLACEMENT_KEYS does not name"
                         % ", ".join(sorted(set(clean) - set(PLACEMENT_KEYS))))
    for key in PLACEMENT_KEYS:
        if key in clean:
            merged[key] = clean[key]

    # ---- and the grounds, which live in their own file ---------------------------------------
    # Two files, one button. They are separate files because they are separate decisions with
    # separate lifetimes -- how sculpts stand outlives which picture they stand on -- but they
    # are tuned in the same sitting, and a second button would mean a half-saved board.
    grounds = sent.get("grounds")
    if grounds is not None:
        save_grounds(board, grounds)

    # Written via a neighbour and renamed into place: a crash halfway through a direct write
    # leaves the file truncated, and this one is read by every page in the toolchain.
    tmp = board.PLACEMENT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    tmp.replace(board.PLACEMENT)
    return merged


def save_grounds(board, sent):
    """Write the ground assignments and their tuning back, merged like the placement file.

    Validated with the same rules the generator reads by, so the button cannot write a file the
    tool would then refuse to load.
    """
    current = {}
    if board.GROUND_PLAN.is_file():
        current = json.loads(board.GROUND_PLAN.read_text(encoding="utf-8"))
    merged = dict(current)
    assert set(GROUND_KEYS) == {"by_duty", "grounds", "lift"}, (
        "GROUND_KEYS names something this function does not write")

    by_duty = sent.get("by_duty")
    if by_duty is not None:
        if not isinstance(by_duty, dict):
            raise ValueError("by_duty is %r, want an object keyed by duty slug" % by_duty)
        for slug in by_duty:
            if slug not in board.SLUGS:
                raise ValueError("by_duty has %r, which is not a duty slug" % slug)
        merged["by_duty"] = dict(by_duty)

    grounds = sent.get("grounds")
    if grounds is not None:
        if not isinstance(grounds, dict):
            raise ValueError("grounds is %r, want an object keyed by plate name" % grounds)
        # MERGED INTO THE STORED ROW, NOT BUILT FRESH, and merged plate by plate rather than
        # replacing the map. This function writes five sliders; the file holds more than five
        # things, and what it does not understand is not its to throw away.
        #
        # It did throw it away until 2026-09-24. `planks_rough` carries a `camera` block
        # recording 31.14 degrees read off the measuring ring drawn on its source image, with
        # the method, the source file, and a note that the ring was STRIPPED when the art was
        # filed -- so the number cannot be re-derived from the committed PNG, and it is one of
        # the six the locked plate window was derived from. Sending the file's own contents
        # straight back, which is what pressing Save with nothing changed does, returned six
        # plates with every slider and all the top-level prose intact and that block gone.
        #
        # The second half matters as much. Assigning a freshly built map also DELETED any
        # plate the page did not send. That was caught only when the dropped plate happened to
        # carry a duty, by the by_duty consistency check at the foot of this function, and
        # then with a message about the duty rather than about the deletion. flagstones_slab
        # carries no duty, so dropping it was silent.
        #
        # The cost of merging is that a plate can no longer be retired through the page: doing
        # that is now a hand edit of the file. That is the right way round for a tool whose job
        # is to tune sliders, and it is a deliberate trade rather than an oversight.
        clean = dict(merged.get("grounds") or {})
        for name, g in grounds.items():
            stored = clean.get(name)
            row = dict(stored) if isinstance(stored, dict) else {}
            for key, lo, hi in (("anchor", 0, 100), ("scale", 1, 300), ("dim", 0, 100),
                                ("saturate", 0, 100), ("opacity", 0, 100)):
                value = (g or {}).get(key)
                if isinstance(value, bool) or not isinstance(value, int) \
                        or not lo <= value <= hi:
                    raise ValueError("grounds.%s.%s is %r, want a whole number %d-%d"
                                     % (name, key, value, lo, hi))
                row[key] = value
            clean[name] = row
        merged["grounds"] = clean

    # ONE LIFT FOR ALL NINE TILES. Same range the generator reads by.
    lift = sent.get("lift")
    if lift is not None:
        if isinstance(lift, bool) or not isinstance(lift, int) or not -300 <= lift <= 600:
            raise ValueError("lift is %r, want a whole number -300-600" % lift)
        merged["lift"] = lift

    # A plate the plan names but the folder no longer holds would draw nothing and say nothing.
    for slug, name in (merged.get("by_duty") or {}).items():
        if name and name not in (merged.get("grounds") or {}):
            raise ValueError("%s is assigned %r, which has no entry under grounds" % (slug, name))

    tmp = board.GROUND_PLAN.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    tmp.replace(board.GROUND_PLAN)
    return merged


def serve(page, board, port, open_it):
    """Serve the page on localhost and accept its saves.

    Bound to 127.0.0.1 and nothing else. This writes a file in the repository when asked, which
    is fine for a tool you started yourself on your own machine and would not be fine on any
    interface a neighbour can reach.
    """
    import http.server

    class Handler(http.server.BaseHTTPRequestHandler):
        def _send(self, code, body, kind="application/json"):
            raw = body if isinstance(body, bytes) else body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):                                           # noqa: N802
            if self.path in ("/", "/index.html"):
                self._send(200, page.read_bytes(), "text/html; charset=utf-8")
            else:
                self._send(404, json.dumps({"error": "not found"}))

        def do_POST(self):                                          # noqa: N802
            if self.path != "/save":
                return self._send(404, json.dumps({"error": "not found"}))
            try:
                n = int(self.headers.get("Content-Length") or 0)
                sent = json.loads(self.rfile.read(n).decode("utf-8"))
                saved = save_settings(board, sent)
            except Exception as exc:                                # noqa: BLE001
                print("  refused a save: %s" % exc)
                return self._send(400, json.dumps({"error": str(exc)}))
            frame = saved.get("frame") or {}
            print("  saved  spread %d  set-back %d  rank %d  order %s  depth %s %d%%"
                  % (saved["spread"], saved["back"], saved["rank"], saved["order"],
                     saved["depth"]["mode"], saved["depth"]["amount"]))
            if frame:
                print("         frame %d x %d, base %d below the floor"
                      % (frame["w"], frame["h"], frame.get("drop", 0)))
            if sent.get("grounds"):
                print("         grounds written to %s"
                      % board._short(board.GROUND_PLAN))
            written = [str(board._short(board.PLACEMENT))]
            if sent.get("grounds"):
                written.append(str(board._short(board.GROUND_PLAN)))
            return self._send(200, json.dumps({"ok": True, "file": ", ".join(written),
                                               "files": written}))

        def log_message(self, *a):                                  # quiet; we print what matters
            return

    srv = http.server.HTTPServer(("127.0.0.1", port), Handler)
    url = "http://127.0.0.1:%d/" % srv.server_address[1]
    print("  serving %s -- the save button writes %s"
          % (url, board._short(board.PLACEMENT)))
    print("  ctrl-c to stop")
    board.show(url, open_it)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  stopped")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None,
                    help="where to write the page (default: %s)" % OUT.relative_to(ROOT))
    ap.add_argument("--figures", default=None, help="folder holding the rendered sculpts")
    ap.add_argument("--open", action="store_true", default=True, help=argparse.SUPPRESS)
    ap.add_argument("--no-open", dest="open", action="store_false",
                    help="write the page without opening it")
    ap.add_argument("--serve", nargs="?", type=int, const=8765, default=None, metavar="PORT",
                    help="serve the page on localhost so its save button can write the file "
                         "(default port %(const)s); without this the button can only download")
    args = ap.parse_args()

    board = _board_module()
    out = pathlib.Path(args.out).expanduser() if args.out else OUT
    fig_dir = (pathlib.Path(args.figures).expanduser() if args.figures else board.FIGURE_DIR)

    notes = []
    place = board.placement(notes)
    figs = board.figures(fig_dir, notes)
    # The nine tiles come from the board checker, which owns the compass order, the slug table
    # and the parchment. The wheel view would otherwise be a third copy of that pairing.
    cells, font = board.tiles(notes)
    # The plates are discovered from the folder; the plan says which duty stands on which.
    plan = board.ground_plan(notes)
    plates = board.ground_art(notes)
    if not figs:
        raise SystemExit("no sculpt art -- run tools/ui_debug/make_tray_figures.py first; "
                         "this page is nothing but arrangements of it")

    # A SET LABEL, not a pixel height: `210_plastic` and `210_painted` are both 210 tall, so
    # int() stopped being able to name one. Sorted by height then by name, so the buttons keep a
    # settled order as sets are added.
    sizes = sorted(figs, key=board.set_sort)
    orders = ["grouped", "arrival"]

    # The CASES and the art are data; the arrangement is computed in the page, because the
    # sliders change it while you watch. The rule doing that computing is the shared file.
    cases = [{"label": label, "counts": list(counts),
              "tag": "+".join(str(c) for c in counts if c) or "0"}
             for label, counts in CASES]
    if not RULES_JS.is_file():
        raise SystemExit("%s is missing -- it is where the drawing rules live"
                         % board._short(RULES_JS))

    # A seat is a LIST OF POSES -- one for the plastic set, three for the painted one -- and
    # the page picks with dutyPose(), so the two are interchangeable with no branch on which is
    # loaded.
    art_uris = {label: [[{"uri": f["uri"], "w": f["w"], "h": f["h"]} for f in row]
                        for row in figs[label]] for label in sizes}
    page = TEMPLATE
    for key, val in (("__FONT__", font), ("__GROUND__", GROUND),
                     ("__FORMATION__", RULES_JS.read_text(encoding="utf-8")),
                     ("__CASES__", json.dumps(cases)),
                     ("__RULE__", json.dumps({k: place[k] for k in ("spread", "back", "rank")})),
                     ("__ART__", json.dumps(art_uris)),
                     ("__SIZES__", json.dumps(sizes)), ("__ORDERS__", json.dumps(orders)),
                     # WHICH SET OPENS. The file's own `tuned_at`, so the sheet opens on what
                     # the numbers below it were tuned against. It is checked against SIZES in
                     # the page rather than here, because a set the tray has not rendered is a
                     # thing the page can fall back from and this script cannot.
                     ("__OPENSET__", json.dumps(place.get("tuned_at", "210_plastic"))),
                     ("__CELLS__", json.dumps(cells)),
                     ("__PLATES__", json.dumps(plates)),
                     ("__GROUNDPLAN__", json.dumps(plan)),
                     # The WHOLE placement document, not just the three numbers the sliders
                     # move, so a page with no server behind it can still hand you the real
                     # file -- prose and all -- rather than the wire payload under its name.
                     ("__PLACEMENTDOC__", json.dumps(place)),
                     ("__SAVEKEYS__", json.dumps({
                         "placement": list(PLACEMENT_KEYS),
                         "grounds": list(GROUND_KEYS),
                         "placement_file": board.PLACEMENT.name,
                         "grounds_file": board.GROUND_PLAN.name,
                         "where": str(board._short(board.PLACEMENT.parent))})),
                     ("__FRAME__", json.dumps(place.get(
                         "frame", {"w": 320, "h": 390, "drop": 40}))),
                     ("__BANNERTOP__", json.dumps(board.BANNER_TOP)),
                     ("__BANNERFS__", json.dumps(board.BANNER_FS)),
                     ("__BANNERTRACK__", json.dumps(board.BANNER_TRACK)),
                     ("__BANNERINK__", json.dumps(board.BANNER_INK)),
                     ("__OPENORDER__", json.dumps(place.get("order", "grouped"))),
                     ("__DEPTH__", json.dumps(place.get("depth", {"mode": "haze", "amount": 60}))),
                     # _short, not relative_to: the latter RAISES for a path outside the repo, so a
                     # file pointed elsewhere would crash the page header rather than name itself.
                     ("__FILE__", html.escape(str(board._short(board.PLACEMENT))))):
        page = page.replace(key, val)
    assert "__" not in page.split("<script>")[0].replace("__FONT__", ""), "placeholder left behind"

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print("wrote %s  (%.0f KB)" % (out, len(page) / 1024))
    frame = place.get("frame") or {}
    print("  %d cases, %d set(s) (%s), both orders -- arranged live in the page"
          % (len(CASES), len(sizes),
             ", ".join("%s [%d pose%s]"
                       % (s, len(figs[s][0]), "" if len(figs[s][0]) == 1 else "s")
                       for s in sizes)))
    if frame:
        print("  frame %d x %d real px (%.2f:1), base %d below the floor"
              % (frame["w"], frame["h"], frame["w"] / frame["h"], frame.get("drop", 0)))
    in_use = board.ground_check(plan, plates, notes)
    print("  %d ground plate(s) from %s, %d duties assigned, standing on: %s"
          % (len(plates), board.GROUNDS_DIR.name, len(plan.get("by_duty") or {}),
             ", ".join(in_use) or "bare floor only"))
    print("  ground lifted %d px above the floor line on every tile" % plan.get("lift", 0))
    if args.serve is None:
        print("  NOT SERVED -- the save button can only download. Add --serve to write "
              "%s and %s in place."
              % (board.PLACEMENT.name, board.GROUND_PLAN.name))
    tuned = place.get("tuned_at")
    print("  spread %d, set-back %d, rank gap %d  (from %s, tuned against %s at %s px and used "
          "by every set)" % (place["spread"], place["back"], place["rank"],
                             board.PLACEMENT.name, tuned or "?",
                             board.set_px(tuned) if tuned else "?"))
    for note in notes:
        print("  %s" % note)
    if args.serve is not None:
        serve(out, board, args.serve, args.open)   # prints the http URL; the file one is moot
    else:
        board.show(out, args.open)


TEMPLATE = r"""<!doctype html><html lang=en><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Placement sheet</title>
<style>
@font-face{font-family:"PB";src:url(__FONT__) format("truetype");font-display:block}
html,body{margin:0;min-height:100%;background:#0d0b08;color:#8b8071;
  font:11px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace}
body{padding-left:243px}
#head{padding:14px 18px 6px;color:#5f574a}
#head b{color:#c9b27a;font-weight:400}
#grid{display:flex;flex-wrap:wrap;gap:10px;padding:8px 18px 28px;align-items:flex-start}
.case{background:#17130d;border:1px solid #221c14;border-radius:3px;position:relative;
  min-width:148px;display:flex;flex-direction:column}
.field{position:relative;align-self:center;flex:none}
.fig{position:absolute}
.fig img{display:block;width:100%;height:100%}
.floor{position:absolute;left:8%;right:8%;height:1px;background:#2a2318}
.cap{padding:5px 8px 7px;color:#5f574a;font-size:10px;text-align:center}
.cap em{font-style:normal;color:#8b8071}
.cap i{font-style:normal;color:#4f483d}
/* ---- the wheel view ---------------------------------------------------------------------
   The same nine tiles the board draws, at true size, so the frame can be judged against the
   thing that stands in it rather than against a number. */
#stage{position:relative;margin:6px auto 24px;background:#17130d;flex:none}
#stage .cell{position:absolute}
#stage .frame{position:absolute;z-index:1;border:1px solid rgba(201,178,122,.55);
  border-radius:2px;background:rgba(201,178,122,.045)}
#stage .frame.tight{border-color:#e0705f;background:rgba(224,112,95,.07)}
#stage .ground{position:absolute;z-index:2;pointer-events:none}
#stage .ground img{display:block;width:100%;height:100%}
#stage .cap{position:absolute;z-index:5;border:1px dashed rgba(201,178,122,.45);padding:0}
#stage .cell{cursor:pointer}
#stage .cell.picked .frame{border-color:#f0dcaa;box-shadow:0 0 0 1px rgba(240,220,170,.35)}
/* The picker: the plates on offer, shown where you are about to put one. */
#picker{display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end;padding:4px 18px 10px}
#picker .opt{border:1px solid #221c14;border-radius:3px;padding:4px;cursor:pointer;
  background:#17130d;text-align:center;color:#5f574a}
#picker .opt:hover{border-color:#5a4c36}
#picker .opt[aria-pressed=true]{border-color:#c9b27a;background:#1e1810}
#picker .opt img{display:block;height:54px;width:auto}
#picker .opt span{display:block;margin-top:3px;font-size:10px}
#picker .who{color:#c9b27a;align-self:center;margin-right:4px}
#stage .figs{position:absolute;z-index:3}
#stage .fig{position:absolute}
#stage .ban{position:absolute;left:50%;transform:translateX(-50%);z-index:4}
#stage .ban img{display:block;width:100%;height:100%}
#stage .ban b{position:absolute;left:50%;transform:translate(-50%,-50%);font-family:"PB",serif;
  text-transform:uppercase;white-space:nowrap;line-height:1}
/* ---- the panel ---------------------------------------------------------------------------
   A column down the left rather than a strip across the top. The strip wrapped as soon as the
   frame controls arrived, which put a slider on a line of its own with its name left behind on
   the line above -- an unlabelled slider is a control nobody can use without guessing.

   Three columns: name, control, value. Everything lines up because the grid makes it, not
   because each row was spaced by hand. */
#ui{position:fixed;left:0;top:0;bottom:0;width:206px;overflow:auto;z-index:5;
  background:#100d09;border-right:1px solid #1e1811;padding:12px 10px 18px;
  display:grid;grid-template-columns:58px 1fr 32px;gap:7px 7px;align-content:start;
  align-items:center}
#ui .lab{color:#4f483d;text-align:right;white-space:nowrap}
#ui .wide{grid-column:2 / span 2;display:flex;gap:4px;flex-wrap:wrap}
#ui .full{grid-column:1 / -1;display:flex;gap:6px;flex-wrap:wrap;align-items:center}
#ui .sep{grid-column:1 / -1;height:1px;background:#1e1811;margin:3px 0 1px}
#ui .ttl{grid-column:1 / -1;color:#3f3930;letter-spacing:.08em;text-transform:uppercase;
  font-size:9px;margin-top:2px}
#ui button{font:inherit;color:#8b8071;background:#1c1811;border:1px solid #332c20;
  border-radius:3px;padding:3px 7px;cursor:pointer}
#ui button:hover{border-color:#5a4c36}
#ui button[aria-pressed=true]{background:#c9b27a;border-color:#c9b27a;color:#1a1610}
#ui input[type=range]{width:100%;accent-color:#c9b27a;background:transparent;margin:0}
#ui .val{color:#c9b27a;text-align:right}
/* The lift's readout: what the number MEANS on the tile -- all nine, and whether the plate is
   still lying across the banner -- rather than the number again. */
#ui .note{grid-column:1 / -1;color:#5f574a;line-height:1.4;margin:-1px 0 2px 2px}
#ui .note b{color:#e0705f;font-weight:400}
#save{border-color:#4a5a3a}
/* The offline warning is two or three lines long in a narrow column, and it has to be read
   rather than glanced at -- that is the whole point of it. */
#saymsg{margin-left:4px;display:block;line-height:1.45}
#saymsg.ok{color:#8fae6a} #saymsg.bad{color:#e0705f} #saymsg.busy{color:#5f574a}
#save.offline{border-color:#7a4a3a;color:#e0a08f}
</style>
<svg width=0 height=0 style="position:absolute" aria-hidden=true><defs id=hazedefs></defs></svg>
<div id=ui>
  <div class=ttl>what you are looking at</div>
  <span class=lab>view</span><span id=viewb class=wide></span>
  <span class=lab>sculpt</span><span id=szb class=wide></span>
  <span class=lab>order</span><span id=ordb class=wide></span>
  <span class=lab>pose</span><span id=posb class=wide></span>

  <div class=ttl>how the sculpts stand</div>
  <span class=lab>spread</span>
  <input id=sprd type=range min=0 max=200 step=1><span class=val id=sprdv></span>
  <span class=lab>set-back</span>
  <input id=back type=range min=0 max=120 step=1><span class=val id=backv></span>
  <span class=lab>rank gap</span>
  <input id=rank type=range min=0 max=160 step=1><span class=val id=rankv></span>

  <div class=ttl>depth</div>
  <span class=lab>mode</span><span id=dmb class=wide></span>
  <span class=lab>amount</span>
  <input id=haze type=range min=0 max=100 step=1><span class=val id=hazev></span>
  <span class=lab>full at</span>
  <input id=full type=range min=4 max=200 step=1><span class=val id=fullv></span>

  <div class=ttl>the frame the art fills</div>
  <span class=lab>width</span>
  <input id=frw type=range min=120 max=900 step=1><span class=val id=frwv></span>
  <span class=lab>height</span>
  <input id=frh type=range min=120 max=900 step=1><span class=val id=frhv></span>
  <span class=lab>drop</span>
  <input id=frd type=range min=-150 max=300 step=1><span class=val id=frdv></span>
  <span class=lab>ratio</span><span class=wide id=ratio></span>

  <div class=ttl>the ground it stands on</div>
  <!-- LIFT IS THE ONE GLOBAL CONTROL IN THIS BLOCK and is marked as such, because everything
       under it acts on the plate beneath the tile you clicked. A slider that silently moved
       nine tiles while sitting among five that move one is a control you learn twice. -->
  <span class=lab>lift</span>
  <input id=glift type=range min=-150 max=400 step=1><span class=val id=gliftv></span>
  <span class=note id=gliftn></span>
  <div class=sep></div>
  <span class=lab>plate</span><span class=wide id=gwho></span>
  <span class=lab>anchor</span>
  <input id=ganc type=range min=0 max=100 step=1><span class=val id=gancv></span>
  <span class=lab>scale</span>
  <input id=gsca type=range min=20 max=200 step=1><span class=val id=gscav></span>
  <span class=lab>dim</span>
  <input id=gdim type=range min=0 max=100 step=1><span class=val id=gdimv></span>
  <span class=lab>saturate</span>
  <input id=gsat type=range min=0 max=100 step=1><span class=val id=gsatv></span>
  <span class=lab>opacity</span>
  <input id=gopa type=range min=0 max=100 step=1><span class=val id=gopav></span>

  <div class=sep></div>
  <div class=full><button id=bshadow aria-pressed=true>shadow</button>
    <button id=save>save to json</button></div>
  <div class=full><span id=saymsg></span></div>
</div>
<div id=head></div>
<div id=picker hidden></div>
<div id=stage hidden></div>
<div id=grid></div>
<script>
// ---- the drawing rules, inlined from tools/ui_debug/duty_sculpt_rules.js ----------------
__FORMATION__
// -------------------------------------------------------------------------------------------
var CASES = __CASES__, RULE = __RULE__, ART = __ART__, SIZES = __SIZES__, ORDERS = __ORDERS__;
var DEPTH = __DEPTH__, MODE = DEPTH.mode, SHADE = DEPTH.amount;
var FULL_AT = DEPTH.full_at || 52;
// A set LABEL -- `210_painted` -- not a pixel height. The opening pick is the file's own
// `tuned_at` when the tray has rendered it, and otherwise the last set on offer.
var SIZE = SIZES.indexOf(__OPENSET__) >= 0 ? __OPENSET__ : SIZES[SIZES.length - 1];
// ONLY THE ARRANGEMENTS VIEW HAS A POSE CONTROL, and the split is the point. The wheel draws
// nine grid positions and takes its pose from the column, exactly as the board and the sow do
// -- a control there would let this page show an arrangement the game cannot produce. The
// arrangements view has no grid at all: it is a table of formations, so there is no column to
// read and the pose has to be asked for. It is also where comparing the three paintings side
// by side is actually useful, which is why the control lives on the tuning page and nowhere
// else. A one-pose set ignores it, because dutyPose folds it away.
var POSE = 0, ORDER = __OPENORDER__;
var SPREAD = RULE.spread, BACK = RULE.back, RANK = RULE.rank;
var CELLS = __CELLS__, FRAME = __FRAME__, VIEW = "arrangements";
var PLATES = __PLATES__, PLAN = __GROUNDPLAN__;
var DOC_PLACEMENT = __PLACEMENTDOC__, SAVE_KEYS = __SAVEKEYS__;
// Which tile the picker is aimed at. Null until you click one, because a picker with no target
// would have to guess, and the guess it would make is "all of them".
var PICKED = null, RESIZING = false;
var GROUND_DEFAULTS = DUTY_GROUND_DEFAULTS;
// One lift for all nine tiles, real pixels, positive upward. Read from the plan like everything
// else here, so the page opens where the file left off.
var LIFT = PLAN.lift || 0;

// Resolved by the shared rule, so this page and the sow agree about what a duty stands on.
function groundFor(slug){ return dutyGroundFor(PLAN, slug); }
// The same rule, plus one thing only this page needs: a plate that arrives on its defaults is
// REMEMBERED in the plan, because a setting the page invented and did not store would not be in
// what the save button sends, and the plate would come back untuned every time.
function settingsFor(name){
  var g = (PLAN.grounds || {})[name];
  if (!g){
    g = dutyGroundSettings(PLAN, PLATES, name);
    (PLAN.grounds = PLAN.grounds || {})[name] = g;
  }
  return g;
}
var BANNER_TOP = __BANNERTOP__, BANNER_FS = __BANNERFS__,
    BANNER_TRACK = __BANNERTRACK__, BANNER_INK = __BANNERINK__;
// One illustrative deal for the wheel: nine tiles carrying nought to five, with the seats mixed
// so a frame is judged against colours next to each other rather than against one player's row.
// Every arrangement in detail is what the other view is for.
var WHEEL_DEAL = [[0,0,0],[1,0,0],[1,1,0],[2,1,0],[2,1,1],
                  [2,2,1],[1,1,1],[2,0,0],[0,1,0]];
var DPR = devicePixelRatio || 1;
function px(v){ return (v / DPR) + "px"; }

var HAZE_STEPS = DUTY_HAZE.steps, HAZE_MAX = DUTY_HAZE.max;
document.getElementById("hazedefs").innerHTML =
  dutyHazeDefs("__GROUND__", HAZE_STEPS, HAZE_MAX);
function figFilter(y, shadowOn){
  return dutyFilter(y, {ref: FULL_AT, amount: SHADE, mode: MODE, shadow: shadowOn,
                        steps: HAZE_STEPS});
}

function draw(){
  showRatio();
  var wheel = VIEW === "wheel";
  document.getElementById("stage").hidden = !wheel;
  document.getElementById("grid").hidden = wheel;
  document.getElementById("picker").hidden = !wheel || !PICKED;
  return wheel ? drawWheel() : drawCases();
}

// ---- the wheel ---------------------------------------------------------------------------------
// The frame is INDEPENDENT of the formation on purpose -- art is drawn to a fixed rectangle, and
// a frame that moved every time a spread slider did would be art you have to redraw. So the page
// draws the formation's own envelope inside it and turns the frame red when the sculpts no longer
// fit. The file decides; the page measures and says when the decision has been outgrown.
function drawWheel(){
  var art = ART[SIZE] || [], shadowOn = document.body.classList.contains("shadow");
  // Over every seat AND every pose: the field and the capacity box both have to hold the worst
  // case the set can produce, not the case pose 1 happens to be.
  var figH = dutySetHeight(art), widest = dutySetWidth(art);
  // The panel is a fixed column down the left now, so it takes width rather than height.
  var panel = document.getElementById("ui").getBoundingClientRect().width;
  var headH = document.getElementById("head").getBoundingClientRect().height;
  var pick = document.getElementById("picker");
  var pickH = pick.hidden ? 0 : pick.getBoundingClientRect().height;
  var side = Math.max(300,
                      Math.min(innerWidth - panel - 48, innerHeight - headH - pickH - 34));
  var BUD = Math.floor(side * DPR), CELL = BUD / 3;
  var L = dutyTileLayout(CELL, figH, RANK, BACK, {icons: false});
  var floor = L.top + L.field;
  var CAP = dutyCapacityBox(5, SPREAD, BACK, RANK, widest, figH);
  // Room above the floor line is the frame's height less however far its base sits below it.
  var room = FRAME.h - FRAME.drop;
  var tight = CAP.w > FRAME.w || CAP.h > room;
  // AND WHETHER THE FRAME ITSELF FITS THE TILE. Two different questions that look like one:
  // the sculpts can sit happily inside a frame that is itself taller than the tile's share of
  // the wheel, and then the top row's pictures run off the board with nothing to say so.
  var frameTop = floor + FRAME.drop - FRAME.h;
  var over = Math.max(0, -frameTop) + Math.max(0, floor + FRAME.drop - CELL);
  var wide = Math.max(0, FRAME.w - CELL);

  var h = "";
  for (var i = 0; i < 9; i++){
    var r = (i / 3) | 0, c = i % 3, C = CELLS[i] || {title: "", ban: ""};
    h += '<div class="cell' + (PICKED === C.slug ? " picked" : "") + '" data-slug="'
       + C.slug + '" style="left:' + px(c * CELL) + ';top:' + px(r * CELL) + ';width:'
       + px(CELL) + ';height:' + px(CELL) + '">';
    h += '<div class="frame' + (tight || over || wide ? " tight" : "") + '" style="left:'
       + px(CELL / 2 - FRAME.w / 2) + ';top:' + px(floor + FRAME.drop - FRAME.h) + ';width:'
       + px(FRAME.w) + ';height:' + px(FRAME.h) + '">'
       + '</div>';
    // THE GROUND, between the frame and the figures. Its standing line -- the row of the plate
    // the feet belong on -- is put ON the floor line, which is why the anchor is a property of
    // each picture rather than a number shared by all of them.
    //
    // LIFT then moves the whole thing off that line, the same distance on every tile. Two
    // separate ideas kept separate: anchor is where the standing line is IN THE PICTURE, lift is
    // how far the picture sits above the floor line ON THE TILE. Tuned against the banner, so it
    // belongs to the board rather than to any one plate.
    var gname = groundFor(C.slug), plate = PLATES[gname];
    if (plate){
      var gs = settingsFor(gname);
      var gw = FRAME.w * gs.scale / 100, gh = gw * plate.h / plate.w;
      h += '<div class=ground style="left:' + px(CELL / 2 - gw / 2) + ';top:'
         + px(floor - LIFT - gh * gs.anchor / 100) + ';width:' + px(gw) + ';height:' + px(gh)
         + ';opacity:' + (gs.opacity / 100) + ';filter:brightness(' + (gs.dim / 100)
         + ') saturate(' + (gs.saturate / 100) + ')"><img src="' + plate.uri + '"></div>';
    }
    h += '<div class=cap style="left:' + px(CELL / 2 + CAP.left) + ';top:'
       + px(floor - CAP.top) + ';width:' + px(CAP.w) + ';height:' + px(CAP.h) + '"></div>';

    var counts = WHEEL_DEAL[i], n = counts.reduce(function(a, b){ return a + b; }, 0);
    var who = dutySeatOrder(counts, ORDER);
    h += '<div class=figs style="top:' + px(L.top) + ';left:0;width:' + px(CELL) + ';height:'
       + px(L.field) + '">';
    dutyFormation(n, SPREAD, BACK, RANK)
      .sort(function(a, b){ return a.x - b.x; })
      .map(function(p, j){ return {x: p.x, y: p.y, seat: who[j]}; })
      .sort(function(a, b){ return b.y - a.y || a.x - b.x; })
      .forEach(function(p){
        var f = dutyPose(art[p.seat], dutyPoseForColumn(i));
        if (!f) return;                 // no art for this seat in this set: draws empty
        h += '<div class=fig style="left:' + px(CELL / 2 + p.x - f.w / 2) + ';top:'
           + px(L.field - f.h - p.y) + ';width:' + px(f.w) + ';height:' + px(f.h)
           + ';filter:' + figFilter(p.y, shadowOn) + '"><img src="' + f.uri + '"></div>';
      });
    h += '</div>';
    h += '<div class=ban style="top:' + px(floor + L.gapA) + ';width:' + px(L.banW)
       + ';height:' + px(L.banH) + '">' + (C.ban ? '<img src="' + C.ban + '">' : "")
       + '<b style="top:' + (BANNER_TOP * 100).toFixed(2) + '%;color:' + BANNER_INK
       + ';font-size:' + px(L.banH * BANNER_FS) + ';letter-spacing:'
       + px(L.banH * BANNER_FS * BANNER_TRACK) + '">' + (C.title || "").toUpperCase()
       + '</b></div>';
    h += '</div>';
  }
  var S = document.getElementById("stage");
  S.style.width = px(BUD); S.style.height = px(BUD);
  S.innerHTML = h;
  S.querySelectorAll(".cell").forEach(function(el){
    el.onclick = function(){
      PICKED = PICKED === el.dataset.slug ? null : el.dataset.slug;
      draw();
    };
  });
  drawPicker();
  syncGroundSliders();
  sayLift(L, floor);
  // The strip's height is only knowable once it is in the document, and it changes the board's
  // budget. One re-measure, guarded, rather than a layout loop.
  var after = pick.hidden ? 0 : pick.getBoundingClientRect().height;
  if (Math.abs(after - pickH) > 1 && !RESIZING){ RESIZING = true; drawWheel(); RESIZING = false; }

  document.getElementById("head").innerHTML =
      "The wheel at true size, from <b>__FILE__</b>.  frame <b>" + FRAME.w + "&#215;"
    + FRAME.h + "</b> real px, ratio <b>" + (FRAME.w / FRAME.h).toFixed(2) + ":1</b>, base <b>"
    + FRAME.drop + "</b> below the floor.  A full tile needs <b>" + Math.round(CAP.w)
    + "&#215;" + Math.round(CAP.h) + "</b> and has <b>" + Math.round(room)
    + "</b> above the floor to stand in."
    + (tight ? "  <b style='color:#e0705f'>The sculpts do not fit the frame.</b>" : "")
    + "  Tile is <b>" + Math.round(CELL) + "</b> real px"
    + (over || wide
        ? ", and the frame runs past it by <b style='color:#e0705f'>"
          + Math.round(Math.max(over, wide)) + "</b> real px."
        : ", which the frame fits inside.");
}

// The plates on offer, shown only once a tile is chosen -- the strip has to know what it is
// assigning to, and "all of them" is not an answer anybody wants by accident.
function drawPicker(){
  var strip = document.getElementById("picker");
  strip.hidden = VIEW !== "wheel" || !PICKED;
  if (strip.hidden) return;
  var title = "";
  CELLS.forEach(function(c){ if (c.slug === PICKED) title = c.title; });
  var here = groundFor(PICKED);
  var h = '<span class=who>' + title + ' stands on</span>';
  h += '<button class=opt data-g="" aria-pressed="' + (here ? "false" : "true")
     + '"><span>bare floor</span></button>';
  Object.keys(PLATES).sort().forEach(function(name){
    h += '<button class=opt data-g="' + name + '" aria-pressed="'
       + (name === here ? "true" : "false") + '"><img src="' + PLATES[name].uri
       + '"><span>' + name + '</span></button>';
  });
  strip.innerHTML = h;
  strip.querySelectorAll(".opt").forEach(function(b){
    b.onclick = function(){
      PLAN.by_duty = PLAN.by_duty || {};
      PLAN.by_duty[PICKED] = b.dataset.g;
      if (b.dataset.g) settingsFor(b.dataset.g);
      draw();                      // which re-syncs the sliders onto whatever is now assigned
    };
  });
}

// WHAT THE LIFT IS ACTUALLY FOR, said as a number. The lift exists to get the plate off the
// banner, so the useful readout is not the lift again but how much plate is still lying across
// the parchment -- which is what changes when the banner changes, and the reason this had to be
// a slider rather than a constant.
//
// Measured on the WORST plate in use, not on the picked one: lifting until the tile in front of
// you is clear, while another duty's taller plate still overlaps, is the whole failure mode.
function bannerClear(L, floor){
  var worst = null, seen = {};
  for (var i = 0; i < 9; i++){
    var C = CELLS[i] || {}, name = groundFor(C.slug), plate = PLATES[name];
    if (!plate || seen[name]) continue;
    seen[name] = 1;
    var gs = settingsFor(name);
    var gw = FRAME.w * gs.scale / 100, gh = gw * plate.h / plate.w;
    // the plate's own bottom edge, against the top of the parchment below the floor line
    var gap = (floor + L.gapA) - (floor - LIFT + gh * (1 - gs.anchor / 100));
    if (worst === null || gap < worst.gap) worst = {gap: gap, name: name};
  }
  return worst;
}
function sayLift(L, floor){
  var e = document.getElementById("gliftn");
  if (!e) return;
  var w = bannerClear(L, floor);
  if (!w){ e.innerHTML = "all nine tiles &#183; no plate assigned to measure"; return; }
  // ROUNDED FIRST, THEN BRANCHED. Branching on the raw gap and printing the rounded one says
  // "0 px still lies over the banner" for any overlap under half a pixel -- a number that reads
  // as a contradiction at exactly the setting you are hunting for.
  var n = Math.round(w.gap / DPR);
  e.innerHTML = "all nine tiles &#183; "
    + (n > 0
        ? "clears the banner by <b style='color:#8fae6a'>" + n + "</b> px on " + w.name
        : n < 0
          ? "<b>" + (-n) + "</b> px of " + w.name + " still lies over the banner"
          : "<b style='color:#8fae6a'>just clear</b> of the banner on " + w.name);
}

// The ground sliders act on the plate under the CHOSEN tile, or on the default when no tile is
// chosen, so moving one always has something visible to move.
function currentGround(){
  return groundFor(PICKED || (CELLS[0] || {}).slug);
}
function syncGroundSliders(){
  var name = currentGround();
  var g = name ? settingsFor(name) : GROUND_DEFAULTS;
  [["ganc", "anchor"], ["gsca", "scale"], ["gdim", "dim"],
   ["gsat", "saturate"], ["gopa", "opacity"]].forEach(function(pair){
    var e = document.getElementById(pair[0]);
    if (!e) return;
    e.value = g[pair[1]];
    e.disabled = !name;
    document.getElementById(pair[0] + "v").textContent = name ? g[pair[1]] : "-";
  });
  var who = document.getElementById("gwho");
  if (who) who.textContent = name || "none";
}
function setGround(key, value){
  var name = currentGround();
  if (!name) return;
  settingsFor(name)[key] = value;
  draw();
}

function drawCases(){
  var art = ART[SIZE] || [], shadowOn = document.body.classList.contains("shadow");
  // Measured across every case at the CURRENT settings, so a cell is never sized to a formation
  // it is not drawing -- the sliders can outgrow any constant put here.
  var widest = 0, tallest = 0, cells = [];
  CASES.forEach(function(c){
    var n = c.counts.reduce(function(a, b){ return a + b; }, 0);
    var slots = dutyFormation(n, SPREAD, BACK, RANK)
                  .sort(function(a, b){ return a.x - b.x; });
    var who = dutySeatOrder(c.counts, ORDER);
    var figs = slots.map(function(p, i){
      var a = dutyPose(art[who[i]], POSE) || {w: 0, h: 0};
      return {x: p.x, y: p.y, seat: who[i], w: a.w, h: a.h};
    });
    figs.forEach(function(f){
      widest = Math.max(widest, Math.abs(f.x) * 2 + f.w);
      tallest = Math.max(tallest, f.h + f.y);
    });
    cells.push({c: c, figs: figs, who: who});
  });
  var W = widest + 30, H = tallest + 22;

  document.getElementById("head").innerHTML =
      "Every arrangement the rules produce, read from <b>__FILE__</b>.  spread <b>" + SPREAD
    + "</b>, set-back <b>" + BACK + "</b>, rank gap <b>" + RANK + "</b>, order <b>" + ORDER
    + "</b> -- one set, used at every size.  Showing <b>" + SIZE.replace("_", " ")
    + "</b> pose <b>v" + (POSE + 1) + "</b>"
    + ((ART[SIZE] || [[]])[0].length > 1 ? "" : " (this set has one)")
    + ", depth <b>"
    + (SHADE ? MODE + " " + SHADE + "% , full at " + FULL_AT : "off")
    + "</b>.  Drawn at true size, so a sculpt here is the size it is on the board.";

  var h = "";
  cells.forEach(function(cell){
    h += '<div class=case style="width:' + px(W) + '">';
    h += '<div class=field style="width:' + px(W) + ';height:' + px(H) + '">';
    // Painter's order by foot, so a sculpt standing further back never covers a nearer one.
    cell.figs.slice().sort(function(a, b){ return (a.y === b.y) ? a.x - b.x : b.y - a.y; })
      .forEach(function(f){
        h += '<div class=fig style="left:' + px(W/2 + f.x - f.w/2) + ';top:'
           + px(H - 10 - f.h - f.y) + ';width:' + px(f.w) + ';height:' + px(f.h)
           + ';filter:' + figFilter(f.y, shadowOn)
           + '"><img src="' + dutyPose(art[f.seat], POSE).uri + '"></div>';
      });
    h += '<div class=floor style="top:' + px(H - 10) + '"></div>';
    h += '</div>';
    h += '<div class=cap><em>' + cell.c.tag + '</em> &#183; ' + cell.c.label
       + '<br><i>' + cell.who.map(function(s){ return "p" + (s + 1); }).join(" ") + '</i></div>';
    h += '</div>';
  });
  document.getElementById("grid").innerHTML = h;
}

// `label` is optional and only changes what a button SAYS: a set is stored as `210_painted`
// and reads better as `210 painted`. The value on the button is untouched, so the round trip
// through dataset.v still hands back the label the art is keyed by.
function buttons(host, list, get, set, label){
  var h = "";
  list.forEach(function(v){
    h += '<button data-v="' + v + '" aria-pressed="' + (v === get() ? "true" : "false")
       + '">' + (label ? label(v) : v) + '</button>';
  });
  host.innerHTML = h;
  [].forEach.call(host.querySelectorAll("button"), function(b){
    b.onclick = function(){
      var v = b.dataset.v;
      set(isNaN(+v) ? v : +v);
      [].forEach.call(host.querySelectorAll("button"), function(x){
        x.setAttribute("aria-pressed", x.dataset.v === b.dataset.v ? "true" : "false"); });
      draw();
    };
  });
}
function slider(id, value, set){
  var e = document.getElementById(id), v = document.getElementById(id + "v");
  e.value = value; v.textContent = value;
  e.oninput = function(){ set(+e.value); v.textContent = e.value; draw(); };
}
buttons(document.getElementById("viewb"), ["arrangements", "wheel"],
        function(){ return VIEW; }, function(v){ VIEW = v; });
buttons(document.getElementById("szb"), SIZES, function(){ return SIZE; },
        function(v){ SIZE = v; }, function(v){ return String(v).replace("_", " "); });
buttons(document.getElementById("ordb"), ORDERS, function(){ return ORDER; },
        function(v){ ORDER = v; });
// Three buttons whatever the set holds, so the row does not change shape when the set does.
// A set with fewer poses answers them all with what it has rather than losing a button --
// which keeps the row a statement about the CONVENTION (first column v1, and so on) rather
// than an inventory of the art currently loaded.
buttons(document.getElementById("posb"), [0, 1, 2], function(){ return POSE; },
        function(v){ POSE = v; }, function(v){ return "v" + (v + 1); });
buttons(document.getElementById("dmb"), ["haze", "dark", "off"], function(){ return MODE; },
        function(v){ MODE = v;
                     if (v === "off") SHADE = 0;
                     else if (SHADE === 0) SHADE = DEPTH.amount || 60;
                     document.getElementById("haze").value = SHADE;
                     document.getElementById("hazev").textContent = SHADE; });
slider("sprd", SPREAD, function(v){ SPREAD = v; });
slider("back", BACK,   function(v){ BACK = v; });
slider("rank", RANK,   function(v){ RANK = v; });
slider("haze", SHADE,  function(v){ SHADE = v; });
slider("full", FULL_AT, function(v){ FULL_AT = v; });
slider("frw", FRAME.w, function(v){ FRAME.w = v; });
slider("frh", FRAME.h, function(v){ FRAME.h = v; });
slider("frd", FRAME.drop, function(v){ FRAME.drop = v; });
[["ganc", "anchor"], ["gsca", "scale"], ["gdim", "dim"],
 ["gsat", "saturate"], ["gopa", "opacity"]].forEach(function(pair){
  slider(pair[0], 0, function(v){ setGround(pair[1], v); });
});
// The lift is not in that list because it is not a per-plate setting: it takes its opening value
// from the plan rather than from whichever plate happens to be picked, and it is never disabled,
// because it still means something on a tile standing on bare floor.
slider("glift", LIFT, function(v){ LIFT = v; });
syncGroundSliders();
function showRatio(){
  document.getElementById("ratio").textContent =
    (FRAME.w / FRAME.h).toFixed(2) + " : 1";
}
showRatio();
document.getElementById("bshadow").onclick = function(){
  var on = document.body.classList.toggle("shadow");
  this.setAttribute("aria-pressed", on ? "true" : "false");
  draw();                      // the shadow is part of the filter chain now, not a CSS class
};

// ---- saving --------------------------------------------------------------------------------
// Served by `--serve` the button POSTs and the generator writes both files, merging into what is
// already there so the prose notes survive.
//
// A page opened as a file: URL cannot write to disk. It used to hand you ONE download called
// duty_placement.json whose contents were the wire payload -- a shape that file never has, with
// every ground assignment buried in a `grounds` key nothing reads out of it. Dropping it into
// the repo would have destroyed the placement file and still lost the grounds. Now the offline
// path builds the two real documents, merging the same keys into the same files the server
// would, and says plainly that nothing was written.
function settings(){
  return {spread: SPREAD, back: BACK, rank: RANK, order: ORDER,
          depth: {mode: MODE, amount: SHADE, full_at: FULL_AT},
          frame: {w: FRAME.w, h: FRAME.h, drop: FRAME.drop},
          grounds: {by_duty: PLAN.by_duty || {}, grounds: PLAN.grounds || {}, lift: LIFT}};
}
function say(msg, cls){
  var e = document.getElementById("saymsg");
  e.textContent = msg; e.className = cls || "";
}
function connected(){
  return location.protocol === "http:" || location.protocol === "https:";
}
// The two files as the generator would write them: the tuned keys merged INTO the documents that
// are on disk, so every line of prose explaining those numbers survives. The key lists come from
// the generator, so this cannot merge a different set than the server does.
// WHAT THE TWO FILES LOOKED LIKE WHEN THE PAGE OPENED, frozen. PLAN is mutated as you work --
// settingsFor() writes a new plate's defaults into it -- so it cannot be its own before-picture.
var OPENED = {place: JSON.parse(JSON.stringify(DOC_PLACEMENT)),
              plan: JSON.parse(JSON.stringify(PLAN))};

function documents(){
  var sent = settings(), k, i, out = [];
  var place = {};
  for (k in DOC_PLACEMENT) place[k] = DOC_PLACEMENT[k];
  for (i = 0; i < SAVE_KEYS.placement.length; i++)
    place[SAVE_KEYS.placement[i]] = sent[SAVE_KEYS.placement[i]];
  out.push({name: SAVE_KEYS.placement_file, doc: place,
            changed: JSON.stringify(place) !== JSON.stringify(OPENED.place)});
  var plan = {};
  for (k in PLAN) plan[k] = PLAN[k];
  for (i = 0; i < SAVE_KEYS.grounds.length; i++)
    plan[SAVE_KEYS.grounds[i]] = sent.grounds[SAVE_KEYS.grounds[i]];
  out.push({name: SAVE_KEYS.grounds_file, doc: plan,
            changed: JSON.stringify(plan) !== JSON.stringify(OPENED.plan)});
  return out;
}
addEventListener("resize", function(){ if (VIEW === "wheel") draw(); });
document.getElementById("save").onclick = function(){
  var body = JSON.stringify(settings(), null, 2);
  if (!connected()){
    // ONLY WHAT ACTUALLY MOVED. Handing over both files every time meant a browser prompt to
    // allow multiple downloads, a folder with two copies of a document you never touched, and
    // -- because the browser will not overwrite -- names like "duty_placement (1).json", where
    // the useful file is the one with the suffix and the stale one keeps the clean name.
    // Nudging the lift changes one file; the button should hand you one file.
    var docs = documents().filter(function(d){ return d.changed; });
    var kept = documents().filter(function(d){ return !d.changed; })
                          .map(function(d){ return d.name; });
    if (!docs.length){
      say("nothing to save -- both files already match what is on disk.", "busy");
      return;
    }
    var names = [];
    docs.forEach(function(d){
      var a = document.createElement("a");
      a.href = "data:application/json;charset=utf-8,"
             + encodeURIComponent(JSON.stringify(d.doc, null, 2) + "\n");
      a.download = d.name;
      a.click();
      names.push(d.name);
    });
    say("NOT saved -- a file:// page cannot write to the repository. Downloaded "
        + names.join(" and ") + " instead; "
        + (names.length > 1 ? "they are" : "it is") + " the finished "
        + (names.length > 1 ? "files" : "file") + ", so copy "
        + (names.length > 1 ? "them" : "it") + " into " + SAVE_KEYS.where + " to keep this."
        + (kept.length ? "  " + kept.join(" and ") + " is unchanged, so it was left alone." : "")
        + "  Re-run with --serve to have the button do it.", "bad");
    return;
  }
  say("saving...", "busy");
  fetch("/save", {method: "POST", headers: {"Content-Type": "application/json"}, body: body})
    .then(function(r){ return r.json().then(function(j){ return {ok: r.ok, j: j}; }); })
    .then(function(res){
      if (!res.ok) throw new Error(res.j.error || "refused");
      say("saved to " + res.j.file + " at " + new Date().toLocaleTimeString(), "ok");
    })
    .catch(function(e){ say("not saved: " + e.message, "bad"); });
};

// SAID BEFORE THE TUNING, NOT AFTER IT. The page used to mention that a file: URL cannot write
// to the repository only once the button had been pressed -- at the end of a sitting, in the
// same small line a success message uses. An hour of assignments went into a download nobody
// knew was a download. The button now says what it is from the moment the page opens.
if (!connected()){
  document.getElementById("save").textContent = "download json";
  document.getElementById("save").className = "offline";
  say("not connected to the generator: this page can only DOWNLOAD the two files, not write "
      + "them. Re-run with --serve to save in place.", "bad");
}

document.body.classList.add("shadow");
draw();
addEventListener("resize", draw);
(function(){ if (!document.fonts) return;
  document.fonts.load('400 20px "PB"').then(function(){ return document.fonts.ready; })
    .then(draw).catch(function(){}); })();
</script>
"""


if __name__ == "__main__":
    main()
