"""Move the column's numbers with controls, against real boards, and save them where the build reads.

    python3 ui/render/gen_layout_tool.py --serve      # controls that can save
    python3 ui/render/gen_layout_tool.py --open       # same page, read-only, shows the JSON instead

WHAT IT IS AND IS NOT

It is a control panel over the whole table, and nothing on it is a mockup. The gothic player boards
come from the production assembler; the Special Activities panel, the alms table, the market, the
action box, the duty wheel and the log are lifted straight out of `gen_board.py`'s own output,
markup and stylesheet together. Every knob is a number the layout actually depends on, and each one
recomputes the budget live, beside the real components rather than beside a drawing of them.

Lifting rather than re-implementing is what stops this drifting: what the tool shows IS what
gen_board.py produced. If a class is renamed there, the extraction fails loudly the next time this
is built rather than quietly showing an empty box.

THE BOXES ARE MEASURED OFF THE GOLD, NOT OFF THE BOUNDING BOX

The slider is the player board's width. Every other panel -- Special Activities, the log, the alms
table, the action box -- is derived from it by where the gold actually is, both measured off
frame_base.png:

    right   x 1839 of 1905. 283 of the frame's rows end between 1830 and 1839, far more than end
            anywhere else; that is the border's own edge. The quatrefoil ornaments around the gem
            sockets push out to x 1902, so the board's bounding box is 3.5%% wider than the board
            looks. Aligning a panel to an ornament tip lines it up with nothing.

    left    x 620, exactly where the portrait oval ends, and only on the second setting of the
            "boxes measured" control.

On "from the board's left edge" the boxes run from there to the gold: 96.54%% of the board. On "from
the gold frame" they start at the gold on the left too, 63.99%% of the board, and the portraits break
out to the left of the grid. Either way the BOARD does not move, so the control shows the two
arrangements at one board size and they can be judged against each other.

At the default 339.4 the difference is stark: boxes of 327.6 against 217.2, and a duty wheel that
goes from 845 to 955.4 -- which at that point is square and filling its row exactly, for the first
time in any configuration we have tried. The cost is the action box, which at 217 px starts wrapping
its turn script badly. The current game view is not quite like that -- boards
are 339.4 while the action box is 305 and the log 304.7 -- and the ragged 19 px that leaves between
the market and the wheel is exactly what the rule removes. Under it the market and the wheel are the
same number by construction.

THE WHEEL IS THE COUPLING

The duty wheel is not sized by hand. It takes whatever width the player-board column and the action
box leave, and because it is SQUARE that width becomes its height -- which is the height the column
then has to live in. Widen the boards and the wheel shrinks; the wheel shrinking shortens the very
column that was widened. The measured game view balances exactly: a 855.3 px square wheel in a
855.3 px row. Board width looks like a free parameter and is not, which is the single most useful
thing this tool says -- and under the rule above the trade is sharper still, since every pixel added
to a board takes two from the wheel.

It is not a layout editor. Nothing drags, nothing can be repositioned, no component can be added or
removed. Where things go lives in the generators, where a coordinate can carry the paragraph that
explains it; a drag handle throws that reasoning away. None of the open questions here are "where
should this sit", they are "how big, and does it still fit".

WHY THERE IS A FILE

The settings are written to `ui/layout.json`, and `gen_board_2.py` reads it. That is the whole point
of the file: without it this would be a playground whose numbers you retype into a generator by
hand, which is two sources of truth and a drift waiting to happen -- this repository has been bitten
by that twice, once when a committed page compared identical forever and once when the duty tile
scale silently reverted. With it, moving a slider and changing the layout are the same act.

Saving is explicit and never silent, because `rebuild_ui_pages.py --check` depends on the result.
Only the player-board column's numbers are read back by `gen_board_2.py`; the other components are
still laid out by `gen_board.py` itself, so their settings here are a proposal rather than something
a build consumes.

BUILD ORDER

This reads `ui/generated/board-3-2-step1.html`, so `gen_board.py` has to have run. It is listed
before this tool in `rebuild_ui_pages.py`, and if the page is missing this says so and stops.

WHY IT DOES NOT REBUILD ANYTHING

The boards are assembled once, up front, and every control after that is a CSS or attribute change:
a board's width is an attribute, the gaps are CSS, the canvas is CSS. Nothing is re-embedded and
nothing is re-fetched, which is why a slider is smooth against 5.6 MB of Base64.

THE SCREEN SELECTOR IS THE POINT

The stage is zoom-to-fit, so how large anything appears depends on the window, not on the canvas.
The preview therefore lays the boards out at the zoom the chosen screen would actually produce, and
the readout reports the resulting sizes in true pixels -- a layout comfortable on an ultrawide and
unreadable on a laptop is exactly what this is for catching.

A SIMULATED screen is then scaled AGAIN, separately, to fit whatever window the tool is open in, and
the legend says by how much. Keeping those two shrinks apart is the point: the first is the game's
and is what the numbers describe, the second is the tool's and describes nothing. Simulating a
3440 px screen inside a window on that same screen cannot be done at true size, so the honest thing
is to scale it and say so rather than clip it and leave you wondering what you are looking at.

AND FOR THE SCREEN YOU ACTUALLY HAVE, DO NOT SIMULATE AT ALL

The first option in the list, and the default, is "this window": no simulated screen, no second
scale, the boards laid out against the real window and drawn at the size they will really be. For
the machine you are designing on that is not a model of the answer, it is the answer.

Two things steal from it, though, and full screen removes both -- the control panel, and the
browser's own tabs and address bar. In full screen the panel becomes a faint overlay at the left
edge that wakes on hover, so a slider can still be dragged while the board sits at the size it would
really be. That is the mode for deciding how big a player board should be.
"""
import argparse
import importlib.util
import json
import pathlib
import xml.etree.ElementTree as ET
from html import escape as html_escape

HERE = pathlib.Path(__file__).resolve().parent
UI = HERE.parent
LAYOUT_PATH = UI / "layout.json"

DEFAULTS = {
    "canvas_width": 1600,
    "canvas_height": 1200,
    "board_width": 339.4,
    "board_gap": 30,
    "special_height": 178.0,
    "frame_border_y": 0.10,
    "frame_border_x": 0.05,
    "seats": 4,
    # True: the board-width slider means the whole board, portrait and all, and every other panel
    # takes that same width. False: it means the width from where the gold frame starts -- measured
    # at x 620 of the 1905 canvas, which is the right edge of the portrait oval -- so the panels
    # align on the frame and the portraits hang out to the left of them.
    "width_whole_board": True,
    # The rest of the table. There is deliberately no action-box width: THE RULE is that the two
    # left columns are one width, so the player board, Special Activities, the log, the alms table
    # and the action box all move together on the board-width slider. The measured view is not quite
    # like that -- boards are 339.4 while the action box is 305 and the log 304.7 -- and the ragged
    # 19 px that leaves between the market and the wheel is exactly what the rule removes.
    #
    # THE TWO COLUMN GAPS ARE SHARED BY BOTH ROWS, and that is what keeps the grid a grid. The
    # first gap is special activities -> alms table above and player boards -> action box below;
    # the second is alms -> market above and action box -> duty wheel below. Because the first
    # cell of each row is a board wide and the second is a box wide, one pair of gaps puts all
    # four columns on the same two vertical lines without any of it being asserted twice.
    "column_gap_1": 30.0,
    "column_gap_2": 30.0,
    "row_gap": 36.8,
    # WHAT TO DO WITH THE HEIGHT THE WHEEL CANNOT REACH.
    #
    # The wheel is square, so its width decides its height, and above about a 270 px board that
    # height is less than the canvas has to give. Somebody has to take the difference and there are
    # only two answers, so this is a setting rather than a decision made on your behalf:
    #
    #   True   the action box and the board column take it. Nothing is wasted, the log keeps its
    #          room at every board width, and the bottom margin stays equal to the top -- but the
    #          wheel then ends above the other two, so the bottom edge is ragged.
    #   False  it stays as green under the row. All three columns end on one line, at the cost of
    #          a bottom margin that grows with board width, and of the log, which is squeezed out
    #          entirely somewhere around 380.
    "wheel_slack_to_boxes": True,
    # The action box's own inner rule, in px from its edge -- the hairline that runs inside its
    # border. 7 is what gen_board.py draws. This is a different thing from the frame border below
    # and both can be on at once: the frame border is empty margin RESERVED around a box for
    # artwork that does not exist yet, while this is a line the component actually DRAWS today.
    "act_rule": 7.0,
    # WHICH BOXES RESERVE A FRAME BORDER.
    #
    # Not every box wants one. The special activities board, the alms table and the market are
    # pictures and will be framed. The action box and the log are live panels that already draw
    # their own border and their own inner rule, so a reserved margin on top of that is a second
    # frame around a frame -- and on the action box it also costs 169 px of the height its prose
    # needs. The wheel is arguable either way, which is exactly why it is a toggle and not a rule.
    # Anything left out of this list is drawn edge to edge in its slot.
    "framed": ["sa", "alms", "mkt", "wheel"],
    # The green around the table, top and bottom, as separate numbers because they answer different
    # questions: the top margin is the gap above the special activities board, the bottom is the
    # gap under the action box and the log. 14 each is gen_board.py's STAGE_PAD, which is still the
    # one number for the two SIDES -- those are pinned by the column arithmetic and there is nothing
    # to tune. build() checks that 14 is still what that generator uses.
    "margin_top": 14.0,
    "margin_bottom": 14.0,
}

# slot -> the name on its toggle. Order is the order they appear in the panel.
FRAMEABLE = [("sa", "special"), ("alms", "alms"), ("mkt", "market"),
             ("wheel", "wheel"), ("act", "action"), ("log", "log")]

# name, usable width, usable height, logical ppi.
#
# The ppi is what makes "how would it look on a 14 inch MacBook" answerable rather than approximate.
# CSS pixels are not a physical unit: 1512 of them span 11.9 inches on that MacBook and 13.8 inches
# on a 34 inch ultrawide, so drawing the MacBook's screen 1:1 on the ultrawide shows it 14% too
# large. Computed from each panel's real geometry, at its default scaling.
SCREENS = [
    # 0 x 0 means "do not simulate": measure the window this is running in. On the machine you are
    # designing for, that is not an approximation of the real thing, it IS the real thing.
    ("this window, true size", 0, 0, 0),
    ("ultrawide 3440x1440", 3440, 1300, 109.7),
    ("1440p 2560x1440", 2560, 1300, 108.8),
    ("1080p laptop 15.6in", 1920, 940, 141.2),
    ('14" MacBook', 1512, 860, 127.0),
]


BOARD_PAGE = UI / "generated" / "board-3-2-step1.html"

# The other components already exist -- gen_board.py draws every one of them. Rather than
# re-implement any of it, this lifts them out of that generator's own output, which means the tool
# cannot drift from the real thing: what it shows IS what gen_board.py produced, markup and
# stylesheet together. If a class is renamed there, the extraction fails loudly here rather than
# quietly showing an empty box.
COMPONENTS = [("sa", "svg", "sa"), ("alms", "svg", "alms"), ("mkt", "div", "mkt"),
              ("act", "div", "turn"), ("wheel", "svg", "wheel"), ("log", "div", "log")]

# Every control the page's script addresses by id, checked against the built page. See build().
# The sliders here are the same list the script calls KEYS; the rest are the controls around them.
CONTROL_IDS = ["seats", "board_width", "board_gap", "special_height", "frame_border_y",
               "frame_border_x", "column_gap_1", "column_gap_2", "row_gap", "canvas_height",
               "act_rule",
               "margin_top", "margin_bottom",
               "width_basis", "slack_use", "act-rule-css", "framed", "v-framed",
               "screen-pick", "showmode", "diag", "reset", "full", "save",
               "json", "read", "stamp", "v-basis", "v-slack", "showbox", "livehint",
               "fname", "fpick", "load", "saved"]


def extract(html, tag, cls):
    """One element and its subtree, by class, matched on tag depth.

    The markup is machine-generated and well formed, so counting opening and closing tags of the one
    name is enough; there is no need for a parser and no risk of the ragged HTML a parser exists to
    survive.
    """
    import re
    m = re.search(r'<%s[^>]*class="%s(?:[ "])' % (tag, cls), html)
    if not m:
        raise SystemExit(
            "could not find <%s class=\"%s\"> in %s.\n"
            "That page is gen_board.py's output and this tool lifts its components from it; if the "
            "class was renamed there, update COMPONENTS here to match." % (tag, cls, BOARD_PAGE))
    i, depth = m.start(), 0
    for token in re.finditer(r"<(/?)%s\b|/>" % tag, html[i:]):
        if token.group(0) == "/>":
            continue
        depth += -1 if token.group(1) else 1
        if depth == 0:
            end = html.index(">", i + token.end()) + 1
            return html[i:end]
    raise SystemExit("unbalanced <%s> while extracting .%s" % (tag, cls))


def lift_components():
    """The real components, and the stylesheet that makes them look like themselves."""
    import re
    if not BOARD_PAGE.is_file():
        raise SystemExit("%s is missing -- run `python3 ui/render/gen_board.py` first, or "
                         "`python3 ui/rebuild_ui_pages.py`." % BOARD_PAGE)
    html = BOARD_PAGE.read_text(encoding="utf-8")
    css = re.search(r"<style>(.*?)</style>", html, re.S).group(1)
    # Everything in that stylesheet is scoped to its own classes except one rule -- `html,body` --
    # and that one rule is where the board's TYPOGRAPHY lives: the serif face, the 14px size, the
    # ink colour. Applied here it would repaint the tool's own chrome, so it used to be deleted.
    # That was wrong in a way the picture showed and the markup did not: with it gone the lifted
    # components inherited the tool's placeholder look instead -- 11 px, centred, monospace -- so
    # the action box was the real component wearing the wrong clothes, and its last two sections
    # were too faint to find. Re-pointed at `.nat` it dresses the components and nothing else.
    #
    # Only the inherited properties are carried over. `height`, `margin`, `overflow` and
    # `background` describe a page, not a component, and `.nat` sets its own.
    base = re.search(r"html,body\{([^}]*)\}", css)
    if not base:
        raise SystemExit("%s has no `html,body` rule; that is where the board's font comes from, "
                         "so lifting its components would render them in the wrong face. Check "
                         "what gen_board.py now emits." % BOARD_PAGE)
    wanted = ("font", "font-family", "font-size", "line-height", "color", "letter-spacing")
    keep = [d.strip() for d in base.group(1).split(";")
            if d.strip() and d.split(":", 1)[0].strip() in wanted]
    css = css.replace(base.group(0), "")
    # `text-align` is not in that rule -- the board simply never overrides the initial value. The
    # tool's own `.ph-in` does, and it inherits, so the initial value has to be restored by hand.
    css = ".nat{%s;text-align:start}\n" % ";".join(keep) + css
    return css, {slot: extract(html, tag, cls) for slot, tag, cls in COMPONENTS}


def migrate(saved):
    """Settings that have been renamed, so a file written by an older build still opens.

    Dropping an unrecognised key is silent by design -- it is how a file from a newer build stays
    readable -- but that same silence turns a RENAME into a setting that quietly reverts to its
    default, which looks exactly like the tool having ignored the file.
    """
    if "special_border" in saved and "frame_border_y" not in saved:
        saved["frame_border_y"] = saved.pop("special_border")
    if "column_gap" in saved:                       # one gap became two, both taking its value
        for key in ("column_gap_1", "column_gap_2"):
            saved.setdefault(key, saved["column_gap"])
        saved.pop("column_gap")
    return saved


def load_layout(path=None):
    path = path or LAYOUT_PATH
    if path.is_file():
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SystemExit("%s is not valid JSON: %s" % (path, exc))
        saved = migrate(saved)
        return {**DEFAULTS, **{k: v for k, v in saved.items() if k in DEFAULTS}}
    return dict(DEFAULTS)


# A layout file is a bare name in ui/, nothing else: no directory part, no traversal, and a .json
# suffix. The page can name the file it writes, so this is the whole of the trust boundary.
LAYOUT_NAME = __import__("re").compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\.json")


def layout_path(name):
    if not LAYOUT_NAME.fullmatch(name or ""):
        return None
    path = (UI / name).resolve()
    return path if path.parent == UI.resolve() else None


def layout_files():
    return sorted(p.name for p in UI.glob("*.json") if LAYOUT_NAME.fullmatch(p.name))


PAGE = """<!doctype html>
<meta charset="utf-8"><title>Pilgrim gothic &mdash; column layout</title>
<style>%(board_css)s</style>
<style>
*{box-sizing:border-box}
body{margin:0;background:#12140f;color:#E8E2D3;font:13px/1.5 "Iowan Old Style",Georgia,serif;
  display:flex;height:100vh;overflow:hidden}
#panel{flex:0 0 306px;padding:16px 18px;overflow:auto;background:#1b1e18;
  border-right:1px solid #2f3529}
/* Every rule for the tool's own chrome is scoped to #panel, and it has to be. A bare `button{}`
   here is not just this tool's button: the lifted components are real markup on the same page, and
   the action box has four buttons of its own. Unscoped, `width:100%%` made each of them the width
   of the column, so the pair that belongs side by side stacked, the box grew by 50 px, and the
   DUTY and LAST sections fell off the bottom. The picture was wrong for a reason no amount of
   staring at the layout arithmetic would have found. */
#panel h1{font-size:16px;margin:0 0 2px}
#panel .sub{color:#8fa286;font-size:11.5px;margin:0 0 14px}
#stamp{color:#5f7159;font-family:ui-monospace,Menlo,monospace;font-size:10.5px}
#panel label{display:block;margin:11px 0 2px;font-size:11.5px;color:#c3cdb8;
  display:flex;justify-content:space-between}
#panel label b{font-weight:600;color:#EFE8D6;font-family:ui-monospace,Menlo,monospace}
#panel input[type=range]{width:100%%;margin:0}
#panel select{width:100%%;background:#252a20;color:#E8E2D3;border:1px solid #3c4434;
  border-radius:5px;padding:5px 6px;font:12px Georgia,serif}
#panel input[type=text]{width:100%%;background:#252a20;color:#E8E2D3;border:1px solid #3c4434;
  border-radius:5px;padding:5px 6px;font:12px ui-monospace,Menlo,monospace}
#panel #load{margin-top:7px;background:#252a20;border-color:#3c4434}
#panel #load:hover{background:#2e3528}
#read{margin:16px 0 0;padding:11px 12px;border-radius:7px;background:#20261c;
  font:11.5px/1.7 ui-monospace,Menlo,monospace;color:#cddac2;white-space:pre-wrap}
#read .bad{color:#ff9b8a}
#read .good{color:#a9d78f}
#panel button{margin-top:13px;width:100%%;padding:8px;border-radius:6px;cursor:pointer;
  background:#3a4a33;color:#EFE8D6;border:1px solid #55684b;font:13px Georgia,serif}
#panel button:hover{background:#46583d}
#panel button:disabled{opacity:.45;cursor:default}
#saved{margin-top:7px;font-size:11px;color:#9fc49a;min-height:15px}
#json{width:100%%;height:140px;margin-top:8px;background:#151812;color:#c6d2ba;
  border:1px solid #333a2c;border-radius:5px;font:11px ui-monospace,Menlo,monospace;padding:7px;
  display:none}
#view{flex:1;overflow:auto;background:#0b0d09;padding:12px}
#fitwrap{position:relative}
#screen{position:relative;background:#000;transform-origin:top left;outline:1px solid #2c3327}
#legend{margin-top:10px;font:11.5px/1.7 ui-monospace,Menlo,monospace;color:#8fa286}
#legend i{display:inline-block;width:11px;height:11px;border-radius:2px;vertical-align:-1px;
  margin-right:5px}
#legend .g{background:#2F5237}
#legend .k{background:#000;outline:1px solid #2c3327}
#full{margin-top:8px}
body.live #view{padding:0}
body.live #legend{display:none}
body.live #screen{outline:none}
body.live #panel{position:fixed;left:0;top:0;bottom:0;z-index:9;opacity:.12;
  transition:opacity .18s;box-shadow:0 0 40px #000a}
body.live #panel:hover,body.live #panel:focus-within{opacity:1}
#livehint{display:none;position:fixed;right:12px;bottom:10px;z-index:9;color:#7d8f80;
  font:11px ui-monospace,Menlo,monospace;pointer-events:none}
body.live #livehint{display:block}
.t-stage{position:absolute;top:0;left:0;transform-origin:top left;background:#2F5237;
  display:flex;flex-direction:column}
.t-toprow,.t-mainrow{display:flex;align-items:flex-start}
.t-left{display:flex;flex-direction:column}
.t-boards{display:flex;flex-direction:column}
.t-boards svg,.sa-ph{display:block}
.ph{border-radius:8px;background:#2a2c26;border:1px solid #6b6250;flex:0 0 auto}
.ph-in{width:100%%;height:100%%;border:1px dashed #c9a227;background:#1d2a22;color:#93a58a;
  font-size:11px;display:grid;place-items:center;font-family:ui-monospace,Menlo,monospace;
  text-align:center}
.wheel-in{border-radius:50%%}
.ph-in{overflow:hidden;position:relative}
.nat{position:absolute;left:0;top:0;overflow:hidden}
/* A slot whose component draws its own border does not need the placeholder's two. */
.ph.t-bare{background:none;border:0;border-radius:0}
.ph.t-bare>.ph-in{border:0;background:none}
/* WHERE THE ACTION BOX PUTS HEIGHT IT DOES NOT NEED.
   In gen_board.py the DUTY panel is a fixed 196 px pushed to the bottom by `margin-top:auto`, so a
   taller box opens a gap ABOVE it -- a band of blank parchment between the hire panel and the rule,
   with DUTY and LAST crowded at the foot. Here the box has to work at any height the sliders ask
   for, so DUTY is the part that stretches instead: it is the reading area, the one section whose
   content arrives at hover time and wants the room. LAST stays pinned at the bottom either way. */
#act .turn>.inspect{margin-top:0;height:auto;flex:1 1 auto;min-height:0}
/* The log is the same kind of thing as the action box and gets the same treatment: its own border,
   its own inner rule, and a slot that does not add a second one. `.log` carries margins meant for
   its place in gen_board.py's column, and `place()` clears them. */
#framed{display:flex;flex-wrap:wrap;gap:5px;margin:4px 0 2px}
#panel #framed button{margin:0;width:auto;flex:1 1 auto;padding:5px 3px;border-radius:5px;
  font:11px Georgia,serif;background:#20261c;border:1px solid #333a2c;color:#7d8f80}
#panel #framed button.on{background:#3a4a33;border-color:#55684b;color:#EFE8D6}
#wheel{border-radius:50%%}
</style>
<style id="act-rule-css"></style>
<div id="panel">
  <h1>Column layout</h1>
  <p class="sub">Real boards. Every control is a number the build reads from
  <code>ui/layout.json</code>.<br><span id="stamp">built %(stamp)s</span></p>

  <label>screen <b id="v-screen"></b></label>
  <select id="screen-pick"></select>

  <label>seats <b id="v-seats"></b></label>
  <input type="range" id="seats" min="2" max="4" step="1">

  <label>board width <b id="v-board_width"></b></label>
  <input type="range" id="board_width" min="170" max="460" step="0.2">
  <label>boxes measured <b id="v-basis"></b></label>
  <select id="width_basis">
    <option value="board">from the board&rsquo;s left edge</option>
    <option value="gold">from the gold frame, portraits outside</option>
  </select>

  <label>gap between boards <b id="v-board_gap"></b></label>
  <input type="range" id="board_gap" min="0" max="60" step="1">

  <label>special activities height <b id="v-special_height"></b></label>
  <input type="range" id="special_height" min="120" max="320" step="1">

  <label style="margin-top:14px;color:#EFE8D6;font-weight:600">frame borders
    <b id="v-framed"></b></label>
  <div id="framed">%(framed_buttons)s</div>
  <label>top &amp; bottom <b id="v-frame_border_y"></b></label>
  <input type="range" id="frame_border_y" min="0" max="0.35" step="0.005">
  <label>left &amp; right <b id="v-frame_border_x"></b></label>
  <input type="range" id="frame_border_x" min="0" max="0.25" step="0.005">

  <label>first gap <b id="v-column_gap_1"></b></label>
  <input type="range" id="column_gap_1" min="0" max="80" step="1">
  <label>second gap <b id="v-column_gap_2"></b></label>
  <input type="range" id="column_gap_2" min="0" max="80" step="1">

  <label>gap under the top row <b id="v-row_gap"></b></label>
  <input type="range" id="row_gap" min="0" max="90" step="0.1">

  <label>height the wheel can&rsquo;t use <b id="v-slack"></b></label>
  <select id="slack_use">
    <option value="boxes">goes to the action box and the log</option>
    <option value="green">stays green, all columns end level</option>
  </select>

  <label>action box inner rule <b id="v-act_rule"></b></label>
  <input type="range" id="act_rule" min="0" max="40" step="0.5">

  <label>canvas height <b id="v-canvas_height"></b></label>
  <input type="range" id="canvas_height" min="900" max="1500" step="1">
  <label>top margin <b id="v-margin_top"></b></label>
  <input type="range" id="margin_top" min="0" max="120" step="1">
  <label>bottom margin <b id="v-margin_bottom"></b></label>
  <input type="range" id="margin_bottom" min="0" max="120" step="1">

  <div id="showbox">
    <label style="margin-top:14px" id="fitwin-row"><span id="fitwin-lab">preview shown</span></label>
    <select id="showmode">
      <option value="physical">at its real physical size</option>
      <option value="css">1:1 in CSS pixels</option>
      <option value="fit">fitted to this window</option>
    </select>
    <label>this monitor's diagonal <b id="v-diag"></b></label>
    <input type="range" id="diag" min="11" max="49" step="0.1" value="34">
  </div>
  <button id="reset" title="back to ui/layout.json, or the built-in defaults if there is no file">
    Reset</button>

  <button id="full">Full screen, true size</button>
  <div id="read"></div>
  <label style="margin-top:14px">layout file <b>ui/</b></label>
  <select id="fpick"><option value="">&mdash; open a saved file &mdash;</option>
%(fname_options)s</select>
  <input type="text" id="fname" spellcheck="false" value="layout.json">
  <button id="save">Save</button>
  <button id="load">Load layout settings</button>
  <div id="saved"></div>
  <textarea id="json" readonly></textarea>
</div>
<div id="view"><div id="fitwrap"><div id="screen"><div class="t-stage" id="stage">
  <div class="t-toprow" id="toprow">
    <div class="ph" id="sa"><div class="ph-in"><div class="nat">%(c_sa)s</div></div></div>
    <div class="ph" id="alms"><div class="ph-in"><div class="nat">%(c_alms)s</div></div></div>
    <div class="ph" id="mkt"><div class="ph-in"><div class="nat">%(c_mkt)s</div></div></div>
  </div>
  <div class="t-mainrow" id="mainrow">
    <div class="t-left" id="left">
      <div class="t-boards" id="boards">%(boards)s</div>
      <div class="ph" id="log"><div class="ph-in"><div class="nat">%(c_log)s</div></div></div>
    </div>
    <div class="ph" id="act"><div class="ph-in"><div class="nat">%(c_act)s</div></div></div>
    <div class="ph" id="wheel"><div class="ph-in wheel-in"><div class="nat">%(c_wheel)s</div></div>
    </div>
  </div>
</div></div></div>
<div id="legend"></div></div>
<div id="livehint">true size &middot; panel is at the left edge &middot; Esc to leave</div>
<svg width="0" height="0" style="position:absolute" aria-hidden="true">%(defs)s</svg>
<script>
const L = %(layout)s, SCREENS = %(screens)s, CAN_W = %(canvas_width)s;
const SA = %(sa)s, VB = {w: %(vb_w)s, h: %(vb_h)s}, FRAMEABLE = %(frameable)s;
// The built-in defaults, so Load can start a file from them rather than from whatever is on screen.
const DEFAULTS = %(defaults)s;
// The resource count's font size, in the board's own viewBox units, READ OFF THE BOARDS THIS PAGE
// IS SHOWING rather than remembered here. It used to be a hand-copied 8.9 px "at the design board
// width", which was correct for exactly as long as nobody changed the assembler -- and the first
// time anybody did, the readout went on reporting the old number with complete confidence. A
// figure this page quotes about a board it is holding should be measured from that board.
const COUNT_FONT = %(count_font)s;
// The two SIDES only. Top and bottom are sliders; see DEFAULTS.margin_top.
const PAD = %(pad)s;
// Both edges of the gold, measured off frame_base.png.
//
// LEFT: the vertical gold band between the portrait and the information panel runs x 620..703, and
// 620 is exactly where the portrait oval ends.
//
// RIGHT: 283 of the frame's rows end between x 1830 and 1839, far more than end anywhere else --
// that is the gold border's own edge. The quatrefoil ornaments around the gem sockets push out
// past it to x 1902, which is why the board's bounding box is not the board's visual edge.
const FRAME_START = 620 / 1905, FRAME_END = 1839 / 1905;
const CAN_SAVE = %(can_save)s;
const KEYS = ['seats','board_width','board_gap','special_height','frame_border_y',
              'frame_border_x','column_gap_1','column_gap_2','row_gap','canvas_height','act_rule',
              'margin_top','margin_bottom'];
let screenIndex = 0;

const el = id => document.getElementById(id);
// Snapshot before anything is applied: L is mutated by every slider move, so a reset target has to
// be taken now. These are ui/layout.json's values when there is one, and the built-in defaults when
// there is not -- which is what "reset" should mean either way.
// A shallow copy would hand Reset the same `framed` array the page then mutates, so Reset would
// restore whatever you had last, which is not a reset at all.
const START = Object.assign({}, L, {framed: (L.framed || []).slice()}), START_DIAG = '34';
const fmt = (n, d = 1) => (Math.round(n * 10**d) / 10**d).toString();

// Only arithmetic now: the panel drawn in that frame is gen_board.py's real one. What this still
// answers is the question the picture cannot -- whether the six-by-four table would still fit once
// a gothic frame takes its border out of the box.
function drawSpecial(w, h, by, bx){
  const scale = w / SA.vb_w, tw = SA.w * scale, th = SA.h * scale;
  const ix = w*bx, iw = w*(1-2*bx), iy = h*by, ih = h*(1-2*by);
  const fits = tw <= iw + 0.05 && th <= ih + 0.05;
  return {fits, needed: th / (1 - 2*by), needWide: tw / (1 - 2*bx),
          interior: [iw, ih], table: [tw, th], cube: SA.cube*scale};
}

function apply(){
  for (const k of KEYS) L[k] = parseFloat(el(k).value);
  L.width_whole_board = el('width_basis').value === 'board';
  L.wheel_slack_to_boxes = el('slack_use').value === 'boxes';
  L.framed = [...document.querySelectorAll('#framed button.on')].map(b => b.dataset.slot);
  const framed = new Set(L.framed);

  // The slider is always the board's width. The panels are derived from it by the gold's two
  // edges, so switching the basis changes the boxes and never the boards -- which is what makes
  // the two arrangements comparable at a glance.
  //
  // The right edge is the gold border in both modes: the ornaments around the gem sockets stick out
  // past it, and aligning a panel to an ornament tip lines it up with nothing.
  const bw = L.board_width;
  const leftFrac = L.width_whole_board ? 0 : FRAME_START;
  const panelW = bw * (FRAME_END - leftFrac);
  const overhang = bw * leftFrac;
  const bh = bw * VB.h / VB.w;
  const seats = Math.round(L.seats);

  // The boards themselves: an attribute, so nothing is rebuilt.
  const svgs = [...document.querySelectorAll('#boards > svg')];
  svgs.forEach((s, i) => {
    s.style.display = i < seats ? '' : 'none';
    s.setAttribute('width', fmt(bw)); s.setAttribute('height', fmt(bh));
  });
  el('boards').style.gap = L.board_gap + 'px';
  el('left').style.gap = L.board_gap + 'px';
  el('left').style.width = bw + 'px';
  // The panels sit at the frame's left edge; only the boards start at the column's.
  for (const id of ['sa', 'log']) el(id).style.marginLeft = overhang.toFixed(1) + 'px';
  // ...and the first cell of the top row still has to be a BOARD wide, or everything after it in
  // that row walks left. Narrowing the boxes to the gold frame shortened this cell by the sliver
  // of board that lies outside the gold -- 11.8 px at the default width -- so the alms table no
  // longer started where the action box starts, and the market no longer started where the wheel
  // starts. Two columns out of true by a hair, which is worse than out by a lot: it reads as
  // sloppiness rather than as a decision. The margin puts the cell back to a board's width and
  // leaves the box inside it where it belongs.
  el('sa').style.marginRight = Math.max(0, bw - overhang - panelW).toFixed(1) + 'px';
  const sa = drawSpecial(panelW, L.special_height, L.frame_border_y, L.frame_border_x);

  // THE WHOLE TABLE, and the coupling that makes it interesting.
  //
  // Across the main row sit the player-board column, the action box, and the duty wheel. The wheel
  // is not sized by hand: it takes whatever width the other two leave, and because it is SQUARE
  // that width becomes its height -- which is the height the player-board column then has to live
  // in. So widening the boards shrinks the wheel, and shrinking the wheel shortens the column that
  // was widened. The measured view balances at 339.4 + 305 + a 855.3 wheel, exactly as tall as the
  // row. Nothing in the tool enforced that before, so board width looked free and was not.
  const inner = [CAN_W - 2*PAD, L.canvas_height - L.margin_top - L.margin_bottom];
  const topH = L.special_height;
  const roomH = inner[1] - topH - L.row_gap;          // what the canvas has left under the top row
  // THE RULE: both left columns are one width, so the market above and the wheel below are handed
  // the same remainder. Widening a player board narrows both of them by exactly twice as much.
  const wheelRoom = inner[0] - bw - panelW - L.column_gap_1 - L.column_gap_2;
  const wheel = Math.max(0, Math.min(wheelRoom, roomH));
  const wheelBoundBy = wheelRoom <= roomH ? 'width' : 'height';

  // THE ROW IS AS TALL AS THE WHEEL, and that is the coupling made visible.
  //
  // The wheel is square, so once the boards have taken their width the wheel's HEIGHT is decided
  // too -- and it is usually less than the canvas has room for. Letting the row keep the canvas's
  // full height did not give that height to the wheel (it cannot grow); it gave it to the action
  // box and the log alone, which then ran 126 px below the wheel and made the bottom edge ragged
  // against a top edge that is a clean line. So the row ends where the wheel ends, every column
  // lands on one line, and the height the board width has cost you shows up where it belongs: as
  // green at the bottom, measured in the readout. The wheel itself is untouched, in size and in
  // place.
  // Whoever takes the height the wheel cannot reach, it is the same number either way, and the
  // control says where it goes. On "green" the boards still cannot be cut off, so the row keeps
  // the height they need even if that means the wheel no longer marks the bottom -- past about 380
  // that is what squeezes the log out, and the readout says so rather than leaving you to notice a
  // box has silently gone.
  const boards = seats*bh + (seats-1)*L.board_gap;
  const rowH = L.wheel_slack_to_boxes ? roomH : Math.min(roomH, Math.max(wheel, boards));
  const slack = Math.max(0, roomH - rowH);          // green under the row; 0 when the wheel fills it
  // The canvas height at which that green disappears and the bottom margin equals the top again.
  const levelHeight = L.canvas_height - slack;

  // The log has no height of its own any more: it takes whatever the boards leave. That is what a
  // scrolling panel should do, and it removes a setting that could only ever be set wrong -- the
  // old slider let you ask for a log the column had no room for, and then reported your own
  // request back to you as an overflow.
  const logH = Math.max(0, rowH - boards - L.board_gap);

  el('toprow').style.height = topH + 'px';
  el('mainrow').style.height = rowH + 'px';
  el('stage').style.gap = L.row_gap + 'px';
  el('left').style.height = rowH + 'px';
  // Flex `gap` is one number for every gap in the row, and there are now two different ones -- so
  // the gaps are margins on the cells that follow them instead. Both rows take the same pair,
  // which is what keeps the four columns on two vertical lines: the same gap after a cell of the
  // same width lands the next cell in the same place, in both rows, without either row being told
  // where the other one put anything.
  el('toprow').style.gap = el('mainrow').style.gap = '0px';
  el('alms').style.marginLeft = el('act').style.marginLeft = fmt(L.column_gap_1) + 'px';
  el('mkt').style.marginLeft = el('wheel').style.marginLeft = fmt(L.column_gap_2) + 'px';

  // Every placeholder wears the same two borders, because they will wear the same frame.
  //
  // Except the action box, and the exception is not a fudge. The frame border reserves room for
  // gothic ARTWORK around a picture -- the special activities board, the alms table, the market,
  // the wheel. The action box is not a picture: it is a live panel that already draws its own
  // parchment, its own border and its own inner rule, and it is the one component whose content
  // is fixed prose that either fits or is cut off. Insetting it by a tenth top and bottom took
  // 169 px out of 845 and cut the DUTY and LAST sections off the end -- so it was showing three
  // quarters of the picture inside a frame reserved for a frame it will never wear. It now runs
  // from the row's top margin to the bottom one, which is where the real board puts it.
  const frame = (id, w, h, bare) => {
    const e = el(id);
    e.style.width = w + 'px'; e.style.height = h + 'px';
    e.style.padding = bare ? '0' : (h*L.frame_border_y).toFixed(1) + 'px '
                                 + (w*L.frame_border_x).toFixed(1) + 'px';
    e.classList.toggle('t-bare', !!bare);
    e.style.display = (w > 0 && h > 0) ? '' : 'none';
  };
  // These components have no natural size worth measuring. In the real view none of them is laid
  // out intrinsically -- the market is stretched by its row, the action box and the log are
  // stretched by the column, the wheel takes its side from what is left. Measuring them in
  // isolation gave 300x49 for a market that is really 874x144, and 1x1 for the wheel. So they are
  // given the room their frame leaves and their own stylesheet lays them out, which is exactly what
  // happens in the game view.
  const place = (id) => {
    const n = el(id).querySelector('.nat');
    n.style.width = '100%%'; n.style.height = '100%%';
    const svg = n.querySelector(':scope > svg');
    if (svg){ svg.setAttribute('width', '100%%'); svg.setAttribute('height', '100%%'); }
    // The div components were written to be flex ITEMS of the real page's rows: the action box
    // asks for `flex:0 0 305px` and the log carries the margins that separate it from the boards
    // above. Lifted out of those rows nothing honours either, so the box was drawn at some width
    // of its own choosing inside a slot sized for it. Here the slot is the authority -- that is
    // the whole point of the tool -- so the root is told to fill it and to drop the margins it
    // brought with it. Top, not centre: when the content is taller than the slot the part you
    // want to see is the top, and a centred overflow hides both ends.
    const root = n.firstElementChild;
    if (root && !svg){
      root.style.width = '100%%'; root.style.height = '100%%';
      root.style.margin = '0'; root.style.flex = '1 1 auto'; root.style.alignSelf = 'stretch';
    }
  };

  // The market is the wheel's column, so it is the wheel's width -- `wheelRoom`, the same
  // remainder, and not a second formula that happens to agree. It used to be computed from the two
  // board widths instead, which was the same number only while the boxes were a whole board wide.
  const mktW = Math.max(0, wheelRoom);
  // The action box's frame is DRAWN, not reserved: `.turn` has a border and `::after` a hairline
  // rule inset inside it. So it cannot be moved by padding a slot -- it has to be restyled, which
  // is what this rule does. The padding follows the rule so the text never sits on top of it; at
  // 7 the two together reproduce gen_board.py's own 13/14 exactly, which is why that is the
  // default and why moving the slider back to 7 gives you the component unchanged.
  el('act-rule-css').textContent =
      '#act .turn::after{inset:' + fmt(L.act_rule) + 'px}'
    + '#act .turn{padding:' + fmt(L.act_rule + 6) + 'px ' + fmt(L.act_rule + 7) + 'px}';

  const bare = id => !framed.has(id);
  frame('sa', panelW, topH, bare('sa'));
  frame('alms', panelW, topH, bare('alms'));
  frame('mkt', mktW, topH, bare('mkt'));
  frame('log', panelW, logH, bare('log'));
  frame('act', panelW, rowH, bare('act'));
  frame('wheel', wheel, wheel, bare('wheel'));
  ['sa', 'alms', 'mkt', 'log', 'act', 'wheel'].forEach(place);

  const stage = el('stage');
  stage.style.width = CAN_W + 'px';
  stage.style.height = L.canvas_height + 'px';
  stage.style.padding = fmt(L.margin_top) + 'px ' + PAD + 'px ' + fmt(L.margin_bottom) + 'px';

  // The zoom the chosen screen would give, so apparent size is honest. A simulated screen has its
  // size in the table; the live option measures the window instead, which on the machine you are
  // designing for is the real answer rather than a model of it.
  let [name, vw, vh, ppi] = SCREENS[screenIndex];
  const live = vw === 0;
  if (live){
    const view = el('view');
    vw = Math.round(view.clientWidth);
    vh = Math.round(view.clientHeight);
    name = 'this window, ' + vw + 'x' + vh;
  }
  const zoom = Math.min(vw/CAN_W, vh/L.canvas_height);
  stage.style.transform = 'translate(' + ((vw - CAN_W*zoom)/2).toFixed(1) + 'px,'
    + ((vh - L.canvas_height*zoom)/2).toFixed(1) + 'px) scale(' + zoom.toFixed(4) + ')';
  el('screen').style.width = vw + 'px';
  el('screen').style.height = vh + 'px';

  // Two different shrinks, kept apart on purpose. `zoom` above is the GAME's fit -- what the chosen
  // screen would really do, and what every px figure in the readout describes. `show` below is only
  // this preview being made to fit the window the tool happens to be open in; it describes nothing
  // about the game. Conflating them is what made the picture confusing.
  // How big to draw the simulated screen. Three answers, because there are three questions.
  //   physical  match the real size of that panel, so a millimetre here is a millimetre there.
  //             This is "how would it look" in the everyday sense, and it needs this monitor's
  //             own ppi, which the browser cannot know -- hence the diagonal slider.
  //   css       1:1 in CSS pixels. Legibility depends on CSS pixels, not inches, so this is the
  //             right unit for "is that text big enough", and it is what the readout reports.
  //   fit       shrink it to fit the window. Answers neither, but shows the whole thing.
  const room = el('view');
  const diag = parseFloat(el('diag').value);
  const myPPI = Math.hypot(screen.width, screen.height) / diag;
  const mode = el('showmode').value;
  let show = 1;
  if (!live){
    if (mode === 'fit') show = Math.min(1, (room.clientWidth-24)/vw, (room.clientHeight-56)/vh);
    else if (mode === 'physical') show = myPPI / ppi;
  }

  // In live mode none of this applies -- the window IS the screen being previewed -- so the whole
  // group goes away rather than sitting there greyed out. A disabled control still reads as a
  // control you have broken; an absent one reads as a question that is not being asked.
  el('showbox').style.display = live ? 'none' : '';
  el('v-diag').textContent = fmt(diag) + '"  (' + Math.round(myPPI) + ' ppi)';
  el('screen').style.transform = 'scale(' + show.toFixed(4) + ')';
  el('fitwrap').style.width = (vw*show) + 'px';
  el('fitwrap').style.height = (vh*show) + 'px';

  const countPx = COUNT_FONT * (bw / VB.w) * zoom;

  for (const k of KEYS) el('v-'+k).textContent =
    k.startsWith('frame_border') ? Math.round(L[k]*1000)/10 + '%%'
                                 : fmt(L[k], k === 'seats' ? 0 : 1);
  el('v-screen').textContent = name;
  el('v-basis').textContent = fmt(panelW) + ' wide';
  el('v-slack').textContent = fmt(Math.max(0, roomH - wheel)) + ' px';
  el('v-framed').textContent = L.framed.length + ' of ' + FRAMEABLE.length;

  const bad = s => '<span class="bad">' + s + '</span>';
  const good = s => '<span class="good">' + s + '</span>';
  const wheelSlack = Math.abs(wheelRoom - roomH);
  const wheelShort = Math.max(0, rowH - wheel);
  el('read').innerHTML =
      'main row ' + fmt(rowH) + ' tall   ('
    + (!L.wheel_slack_to_boxes && rowH > wheel + 0.5
         ? bad('the boards need it; the wheel is only ' + fmt(wheel))
       : L.wheel_slack_to_boxes ? 'all the canvas had'
       : 'the wheel') + '; canvas had ' + fmt(roomH) + ')\\n'
    // The bottom margin is the slider PLUS whatever the row did not use, so the number here is the
    // green you can actually see -- which is the only one worth comparing with the top.
    + 'margins  top ' + fmt(L.margin_top) + '   bottom ' + fmt(L.margin_bottom + slack)
    + (slack >= 1 ? '  (' + fmt(L.margin_bottom) + ' + ' + fmt(slack) + ' the row left over)' : '')
    + (Math.abs(L.margin_top - L.margin_bottom - slack) < 1 ? good('   equal') : '')
    + (slack < 1 ? ''
       : '\\n  the ' + fmt(slack) + ' px is there because the wheel is narrower than the canvas\\n'
         + '  is tall. Canvas height ' + fmt(levelHeight) + ' would take it back.') + '\\n'
    + (wheelShort > 1
       ? '  the wheel ends ' + fmt(wheelShort) + ' px above the action box and the log\\n' : '')
    + 'column   boards ' + fmt(boards) + ' + gap ' + fmt(L.board_gap) + '\\n'
    + '  the log gets ' + (logH >= 90 ? good(fmt(logH) + ' px')
       : logH > 0 ? bad(fmt(logH) + ' px \\u2014 too little to read')
       : bad('nothing; the boards alone overflow the row by '
             + fmt(boards - rowH))) + '\\n\\n'
    + 'duty wheel ' + fmt(wheel) + ' square\\n'
    + '  width leaves ' + fmt(wheelRoom) + ', the canvas had ' + fmt(roomH) + ' of height\\n  '
    + (wheelSlack < 6 ? good('square and filling both')
       : wheelBoundBy === 'width'
       ? fmt(wheelSlack) + ' px of canvas height it cannot reach without more width,\\n  '
         + (L.wheel_slack_to_boxes ? 'given to the action box and the log'
                                   : 'left as green so the bottom edge stays level')
       : good(fmt(wheelSlack) + ' px of width to spare \\u2014 spend it on the gaps or the action '
              + 'box'))
    + '\\n  its frame leaves ' + fmt(wheel*(1-2*L.frame_border_x)) + ' x '
    + fmt(wheel*(1-2*L.frame_border_y))
    + (Math.abs(L.frame_border_x - L.frame_border_y) < 0.002 ? '' :
       bad('\\n  unequal borders, so a square box gives the wheel a rectangle'))
    + '\\n\\ncolumns  ' + fmt(bw) + ' |' + fmt(L.column_gap_1) + '| ' + fmt(panelW)
    + ' |' + fmt(L.column_gap_2) + '| ' + fmt(mktW) + '\\n'
    + '  boxes ' + fmt(panelW) + ' wide, ending on the gold at '
    + fmt(bw*FRAME_END) + ' of the board\\u2019s ' + fmt(bw) + '\\n'
    + (L.width_whole_board
        ? '  left edges all line up\\n'
        : '  portraits overhang ' + fmt(overhang) + ' px to the left of the boxes\\n')
    // The gaps are between COLUMNS, and the first column is a board while the box inside it stops
    // at the gold. So the white space you can see after the special activities box is wider than
    // the number on the slider, by exactly the sliver of board that lies outside the gold. Saying
    // so here costs a line and saves measuring the screenshot to find out why 30 looks like 42.
    + (bw - overhang - panelW > 0.5
        ? '  first gap looks like ' + fmt(L.column_gap_1 + bw - overhang - panelW)
          + ' above: the box stops ' + fmt(bw - overhang - panelW) + ' short of its column\\n'
        : '')
    + '\\n'
    + 'components are gen_board.py\\u2019s own, sized by their frames\\n\\n'
    + 'on ' + name + '\\n'
    + '  board renders  ' + fmt(bw*zoom) + ' px\\n'
    + '  resource count ' + (countPx >= 8 ? good(fmt(countPx) + ' px')
                                          : bad(fmt(countPx) + ' px  (under 8)')) + '\\n\\n'
    + 'special activities\\n'
    + '  interior ' + fmt(sa.interior[0]) + ' x ' + fmt(sa.interior[1])
    + ', table needs ' + fmt(sa.table[0]) + ' x ' + fmt(sa.table[1]) + '\\n  '
    + (sa.fits ? good('the table fits')
               : bad('needs ' + fmt(sa.needed) + ' px tall, or ' + fmt(sa.needWide)
                     + ' px wide, at these borders'))
    + '\\n\\nartwork canvas ' + VB.w + ' x ' + Math.round(L.special_height * VB.w / panelW)
    + '\\n  clear opening  x ' + Math.round(VB.w*L.frame_border_x)
    + ' y ' + Math.round(L.special_height * VB.w / panelW * L.frame_border_y)
    + ' w ' + Math.round(VB.w*(1-2*L.frame_border_x))
    + ' h ' + Math.round(L.special_height * VB.w / panelW * (1-2*L.frame_border_y));

  el('legend').innerHTML =
      '<i class="g"></i>the game canvas, ' + CAN_W + ' x ' + fmt(L.canvas_height)
    + ', laid out at the ' + zoom.toFixed(3) + 'x fit this screen would give'
    + '&nbsp; &middot; &nbsp;<i class="k"></i>the rest of ' + name + '<br>'
    + (live
        ? 'true size on this window &mdash; full screen removes the panel and the browser chrome '
          + 'for the real thing'
        : mode === 'physical'
        ? 'drawn at ' + Math.round(show*100) + '%% so it is the same PHYSICAL size as a ' + ppi
          + ' ppi panel &mdash; hold a ruler to it and the boards match'
        : mode === 'css'
        ? '1:1 in CSS pixels &mdash; legibility is exact, but a ' + ppi + ' ppi panel is physically '
          + Math.abs(Math.round((1 - myPPI/ppi)*100)) + '%% '
          + (ppi > myPPI ? 'smaller' : 'larger') + ' than this shows'
        : show > 0.999
        ? 'the whole screen already fits this window, so this is 1:1 in CSS pixels'
        : 'shrunk to ' + Math.round(show*100) + '%% to fit this window &mdash; the px figures on '
          + 'the left are true, this picture is not');

  // Everything the tool owns, not a chosen subset: a setting left out of this cannot be saved, and
  // a setting that cannot be saved is one you will move, like, and lose on the next reload.
  el('json').value = JSON.stringify(
    {canvas_width: CAN_W, canvas_height: L.canvas_height, board_width: +fmt(bw),
     board_gap: L.board_gap, special_height: L.special_height,
     frame_border_y: +fmt(L.frame_border_y, 3), frame_border_x: +fmt(L.frame_border_x, 3),
     seats: seats, width_whole_board: L.width_whole_board,
     column_gap_1: L.column_gap_1, column_gap_2: L.column_gap_2, row_gap: L.row_gap,
     wheel_slack_to_boxes: L.wheel_slack_to_boxes, act_rule: +fmt(L.act_rule),
     framed: L.framed,
     margin_top: +fmt(L.margin_top), margin_bottom: +fmt(L.margin_bottom)}, null, 2);
}

const setFramed = list => {
  const on = new Set(list || []);
  for (const btn of document.querySelectorAll('#framed button'))
    btn.classList.toggle('on', on.has(btn.dataset.slot));
};
// One place that writes a whole settings object into the controls, used by startup, by Reset and
// by Load alike. When they each did it themselves, adding a setting meant remembering three
// places, and the one that got forgotten failed silently -- the control simply kept its old value.
function pushControls(src){
  for (const k of KEYS) if (k in src) el(k).value = src[k];
  el('width_basis').value = src.width_whole_board === false ? 'gold' : 'board';
  el('slack_use').value = src.wheel_slack_to_boxes === false ? 'green' : 'boxes';
  setFramed(src.framed);
}
pushControls(L);
for (const k of KEYS) el(k).addEventListener('input', apply);
for (const btn of document.querySelectorAll('#framed button'))
  btn.addEventListener('click', () => { btn.classList.toggle('on'); apply(); });
el('reset').addEventListener('click', () => {
  for (const k of KEYS) L[k] = START[k];
  pushControls(START);
  el('diag').value = START_DIAG;
  el('showmode').value = 'physical';
  apply();
});
el('width_basis').addEventListener('change', apply);
el('slack_use').addEventListener('change', apply);
el('showmode').addEventListener('change', apply);
el('diag').addEventListener('input', apply);
addEventListener('resize', apply);

// Full screen is the only way to be honest about apparent size: the control panel and the browser's
// own chrome are both stealing from the window otherwise. In here the panel becomes a faint overlay
// at the left edge that wakes on hover, so a slider can still be dragged while the board is at the
// size it would really be.
el('full').addEventListener('click', async () => {
  if (document.fullscreenElement){ await document.exitFullscreen(); return; }
  try { await document.documentElement.requestFullscreen(); }
  catch (e) { document.body.classList.toggle('live'); apply(); return; }
});
document.addEventListener('fullscreenchange', () => {
  const on = !!document.fullscreenElement;
  document.body.classList.toggle('live', on);
  el('full').textContent = on ? 'Leave full screen' : 'Full screen, true size';
  if (on && SCREENS[screenIndex][1] !== 0){
    screenIndex = 0;                       // a simulated screen inside a real one is meaningless
    el('screen-pick').value = '0';
  }
  requestAnimationFrame(apply);
});
SCREENS.forEach((s, i) => el('screen-pick').add(new Option(s[0], i)));
el('screen-pick').addEventListener('change', e => { screenIndex = +e.target.value; apply(); });

// THE FILE NAME. `ui/layout.json` is the one gen_board_2.py reads; every other name is a variant
// you are keeping to compare against, and saying so on the button is the difference between a
// deliberate experiment and a save that seems to have had no effect on the build.
function fileName(){
  let n = el('fname').value.trim().replace(/[^A-Za-z0-9._-]/g, '-').replace(/^[^A-Za-z0-9]+/, '');
  if (!n) n = 'layout.json';
  if (!/\\.json$/.test(n)) n += '.json';
  el('fname').value = n;
  return n;
}
function noteFile(){
  const n = fileName();
  el('save').textContent = 'Save to ui/' + n
    + (n === 'layout.json' ? '' : '   (a variant; the build reads layout.json)');
}
el('fname').addEventListener('change', noteFile);
el('fname').addEventListener('input', noteFile);

el('save').addEventListener('click', async () => {
  const name = fileName();
  if (!CAN_SAVE){
    el('json').style.display = 'block';
    el('saved').textContent = 'Not served, so nothing can be written. Copy this into ui/' + name + '.';
    el('json').select();
    return;
  }
  const r = await fetch('/layout?name=' + encodeURIComponent(name),
                        {method: 'PUT', body: el('json').value});
  el('saved').textContent = r.ok ? 'saved to ui/' + name
                                 : 'could not save: ' + (await r.text() || r.status);
  if (r.ok) rememberFile(name);
});

// A saved file has to appear in the list without a reload, and in the right place -- the list is
// sorted, and a name appended to the end of a sorted list reads as a bug in the sort.
function rememberFile(name){
  const pick = el('fpick');
  if ([...pick.options].some(o => o.value === name)) return;
  const at = [...pick.options].findIndex((o, i) => i > 0 && o.value > name);
  pick.add(new Option(name, name), at === -1 ? null : pick.options[at]);
}

// Loading REPLACES the whole state rather than patching the current one, and it starts from the
// defaults rather than from what is on screen. A file written by an older build is missing keys
// that exist now; patching would leave those keys holding whatever you happened to be looking at,
// so the same file would load differently depending on what you had done first.
async function loadFile(name){
  if (!CAN_SAVE){
    el('saved').textContent = 'Not served, so no file can be read. Run with --serve.';
    return;
  }
  const r = await fetch('/layout?name=' + encodeURIComponent(name));
  if (!r.ok){
    el('saved').textContent = 'could not load: ' + (await r.text() || r.status);
    return;
  }
  const data = await r.json();
  const merged = Object.assign({}, DEFAULTS, data);
  for (const k of KEYS) if (k in merged) L[k] = merged[k];
  pushControls(merged);
  apply();
  const dropped = Object.keys(data).filter(k => !(k in DEFAULTS));
  el('saved').textContent = 'loaded ui/' + name
    + (dropped.length ? '  (ignored: ' + dropped.join(', ') + ')' : '');
}
el('load').addEventListener('click', () => loadFile(fileName()));

// THE DROPDOWN IS A SEPARATE CONTROL FROM THE NAME BOX, and it has to be.
//
// It was a <datalist> on the name box, which looks like the same thing and is not: a datalist
// FILTERS its options by whatever is already typed in the field. Type a new name, save it, and
// opening the list then shows only the files matching that name -- so layout.json, the one file
// you always want, is the first thing to disappear. A <select> always offers everything it has.
el('fpick').addEventListener('change', e => {
  const name = e.target.value;
  e.target.value = '';                     // it is an action, not a state; nothing to leave selected
  if (!name) return;
  el('fname').value = name;
  noteFile();
  loadFile(name);
});
if (!CAN_SAVE){
  el('save').textContent = 'Show JSON to copy';
  el('load').disabled = el('fpick').disabled = true;
} else noteFile();
apply();
</script>
"""


# The files that decide what this page contains. Deliberately the SOURCES and not the board page
# the components are lifted from: that one is generated too, so its mtime moves on every sweep, and
# a stamp that moved during a sweep would be the very thing this is here to avoid.
SOURCES = ("gen_layout_tool.py", "gen_board_2.py", "gen_board_gothic.py")


def build_stamp(served):
    """What the panel shows as "built ...", and it is two different questions.

    SERVED, the stamp answers "is this page the one the file on disk would produce right now" --
    the clock is exactly right for that, and it is what tells you a stale server is lying to you.

    WRITTEN TO A FILE, the clock is not just useless but harmful: it makes the page differ from
    itself on every build, so nothing can ever compare two builds and say whether a change to a
    generator changed its output. A file's stamp should describe its CONTENT, so it comes from the
    newest of the sources that decide the content. Two builds a second apart then agree, which is
    what `rebuild_ui_pages.py --check` needs in order to mean anything.

    And in UTC, which is the same argument one step further out. That check builds the two copies in
    timezones fourteen hours apart precisely so that anything depending on WHERE it was built shows
    up, and a source mtime rendered in local time is exactly that: the same file, the same content,
    a different page on a laptop that has flown somewhere. The served stamp stays local, because
    there it is answering "how long ago" for the person looking at it.
    """
    import datetime

    if served:
        return datetime.datetime.now().strftime("%H:%M:%S")
    newest = max((HERE / name).stat().st_mtime for name in SOURCES if (HERE / name).is_file())
    if LAYOUT_PATH.is_file():
        newest = max(newest, LAYOUT_PATH.stat().st_mtime)
    return datetime.datetime.fromtimestamp(newest, datetime.timezone.utc) \
        .strftime("%Y-%m-%d %H:%M UTC") + " source"


def count_font(roots, asm, config):
    """The smallest font a resource count can be drawn at, in viewBox units.

    Two sources, and both are needed. The boards give the size the template draws -- the strip's,
    which lives nowhere else. The assembler gives the sizes its layout can CHOOSE between, which
    the boards cannot show: the disc shrinks a two-digit count to fit the quadrant, and a sample
    config holding 4, 0, 3 and 1 never produces one. Reporting the size the sample happens to use
    would tell you the counts are legible and stay silent about the double-digit purse a real game
    hands a player.
    """
    sizes = [float(f) for f in asm.resource_count_fonts(config)]
    for root in roots:
        for group in root.iter("{http://www.w3.org/2000/svg}g"):
            if not (group.get("id") or "").startswith("resource-"):
                continue
            text = group.find("{http://www.w3.org/2000/svg}text")
            if text is not None and text.get("font-size"):
                sizes.append(float(text.get("font-size")))
    if not sizes:
        raise SystemExit("no resource counts found on the boards, so the readout cannot say how "
                         "large they render. Has the resource group's <text> been renamed?")
    return min(sizes)


def build(layout, can_save):
    """Assemble the boards once, then hand the page everything it needs to re-lay them out."""
    spec = importlib.util.spec_from_file_location("gen_board_2", HERE / "gen_board_2.py")
    g = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g)

    assets = UI / "assets-gothic"
    config = assets / "production_test_config.json"
    asm = g.load_assembler(HERE / "gen_board_gothic.py")
    seats = list(asm.SEAT_COLORS)
    roots = [g.build_board(asm, assets, config, s, "lit" if i == 0 else "dim")
             for i, s in enumerate(seats)]
    defs, _unique, _saved = g.merge_defs(asm, roots)

    markup = []
    for root in roots:
        root.set("width", str(layout["board_width"]))
        root.set("height", str(round(layout["board_width"] * g.VB_H / g.VB_W, 1)))
        markup.append(ET.tostring(root, encoding="unicode"))

    # The side padding is gen_board.py's and is not tunable here; the top and bottom margins are
    # sliders whose DEFAULTS were copied from it. If that generator moves, the copy is stale and the
    # tool would open on a canvas the build does not use -- so say so rather than drift quietly.
    if abs(g.STAGE_PAD - DEFAULTS["margin_top"]) > 0.01:
        raise SystemExit("gen_board_2.STAGE_PAD is now %s, but DEFAULTS['margin_top'] and "
                         "['margin_bottom'] here are still %s. Update them to match."
                         % (g.STAGE_PAD, DEFAULTS["margin_top"]))

    board_css, parts = lift_components()
    sa = {"vb_w": g.SA_VB_W, "w": g.SA_W, "h": g.SA_H, "row1": g.SA_ROW1, "pitch": g.SA_PITCH,
          "cube": g.SA_CUBE, "acts": g.SA_ACTIVITIES, "seats": g.SA_SEATS,
          "swatch": list(g.SA_SWATCH)}
    page = PAGE % {
        "boards": "\n    ".join(markup),
        "board_css": board_css,
        "c_sa": parts["sa"], "c_alms": parts["alms"], "c_mkt": parts["mkt"], "c_act": parts["act"],
        "c_wheel": parts["wheel"], "c_log": parts["log"],
        "defs": ET.tostring(defs, encoding="unicode"),
        "layout": json.dumps(layout),
        "screens": json.dumps(SCREENS),
        "screens_": "",
        "canvas_width": layout["canvas_width"],
        "sa": json.dumps(sa),
        "frameable": json.dumps(FRAMEABLE),
        "defaults": json.dumps(DEFAULTS),
        "fname_options": "".join('<option value="%s">%s</option>' % (n, n)
                                 for n in layout_files()),
        "framed_buttons": "".join(
            '<button type="button" data-slot="%s">%s</button>' % (slot, name)
            for slot, name in FRAMEABLE),
        "count_font": count_font(roots, asm, asm.read_json(config)),
        "vb_w": g.VB_W, "vb_h": g.VB_H,
        "pad": g.STAGE_PAD,
        "can_save": "true" if can_save else "false",
        "stamp": build_stamp(can_save),
    }
    # Every control the script reaches for has to be in the page it just built. `el('width_basis')`
    # on a page with no such element throws once, inside `apply`, and the tool then looks like it
    # is missing a control rather than like it is broken -- which is a much harder thing to report
    # and a much harder thing to hear reported.
    missing = [i for i in CONTROL_IDS if ('id="%s"' % i) not in page]
    if missing:
        raise SystemExit("the built page has no %s. A control was removed from the markup but not "
                         "from the script." % ", ".join("#" + i for i in missing))
    return page


def serve(rebuild, port):
    """A localhost page that can write the one file it owns, and nothing else.

    THE PAGE IS BUILT PER REQUEST, not once at startup, and that is the whole difference between a
    tool you can iterate on and one that lies to you. Built once, a server left running from an
    earlier edit keeps serving that edit: the file on disk is right, the browser is wrong, and the
    only symptom is a control that is not there. That has now cost two rounds of "I don't see it",
    which is two more than a two-second rebuild is worth. Reload the browser and you have the file
    as it is on disk; the stamp in the panel says when it was built, so you can tell at a glance.
    """
    import http.server

    class Handler(http.server.BaseHTTPRequestHandler):
        # ui/<name>.json and nothing else. The page names the file it reads and writes, so this one
        # function is the entire trust boundary: no directory part, no traversal, no other suffix.
        def wanted(self):
            from urllib.parse import urlparse, parse_qs
            query = parse_qs(urlparse(self.path).query)
            name = (query.get("name") or ["layout.json"])[0]
            path = layout_path(name)
            if path is None:
                self.fail(400, "not a layout file name: %s" % name)
            return path

        # send_error writes a full HTML error page, which the fetch in the panel then shows as
        # markup in a one-line status field. These answers are read by a script, so they are plain
        # text and one sentence long.
        def fail(self, code, message):
            body = message.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def send_json(self, payload, code=200):
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path.startswith("/layout"):
                path = self.wanted()
                if path is None:
                    return
                if not path.is_file():
                    self.fail(404, "ui/%s does not exist" % path.name)
                    return
                try:
                    self.send_json(migrate(json.loads(path.read_text(encoding="utf-8"))))
                except json.JSONDecodeError as exc:
                    self.fail(400, "ui/%s is not valid JSON: %s" % (path.name, exc))
                return
            try:
                body = rebuild().encode("utf-8")
            except SystemExit as exc:               # a broken edit: say so in the page, keep serving
                body = ("<!doctype html><meta charset=utf-8>"
                        "<body style='background:#12140f;color:#ff9b8a;font:14px ui-monospace,Menlo,"
                        "monospace;padding:28px;white-space:pre-wrap'>"
                        "gen_layout_tool.py did not build:\n\n%s\n\nFix it and reload."
                        % html_escape(str(exc))).encode("utf-8")
                self.send_response(500)
            else:
                self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            # Belt as well as braces: the page is rebuilt per request, but a browser that cached the
            # last one would never ask, so it would still show you yesterday's tool.
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.end_headers()
            self.wfile.write(body)

        def do_PUT(self):
            if not self.path.startswith("/layout"):
                self.send_error(404)
                return
            path = self.wanted()
            if path is None:
                return
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            try:
                data = json.loads(body)
            except json.JSONDecodeError as exc:
                self.fail(400, str(exc))
                return
            unknown = set(data) - set(DEFAULTS)
            if unknown:
                self.fail(400, "unknown keys: %s" % ", ".join(sorted(unknown)))
                return
            path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            print("saved %s" % path)
            self.send_response(204)
            self.end_headers()

        def log_message(self, *_args):
            pass

    # An older copy still holding the port is now much less dangerous -- it rebuilds too -- but it
    # is still a second process writing the same file, so say so and step aside.
    try:
        server = http.server.HTTPServer(("127.0.0.1", port), Handler)
    except OSError as exc:
        if exc.errno not in (48, 98):                      # EADDRINUSE on macOS and on Linux
            raise
        print("port %d is already taken, almost certainly by a copy of this tool left running.\n"
              "  stop it with:  lsof -ti tcp:%d | xargs kill\n"
              "Starting on a free port instead." % (port, port))
        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    url = "http://127.0.0.1:%d/" % server.server_port
    print("serving %s\n  Save and Load use ui/<name>.json; the build reads %s\n"
          "  Ctrl-C to stop" % (url, LAYOUT_PATH.name))
    return server, url


def main():
    ap = argparse.ArgumentParser(description="Move the column's numbers against real boards.")
    ap.add_argument("--serve", action="store_true", help="run a local server so Save can write")
    ap.add_argument("--port", type=int, default=8778)
    ap.add_argument("--output", default=None, help="write the page to a file instead")
    ap.add_argument("--open", action="store_true")
    args = ap.parse_args()

    print("layout from %s" % (LAYOUT_PATH if LAYOUT_PATH.is_file() else "built-in defaults"))

    if args.serve:
        # Re-read the layout as well as re-render: Save writes ui/layout.json, so a reload after a
        # Save should come back with what was saved, not with what the process started life holding.
        server, url = serve(lambda: build(load_layout(), can_save=True), args.port)
        print("  the page rebuilds on every reload, so an edit to this file needs no restart")
        if args.open:
            import webbrowser
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")
        return

    page = build(load_layout(), can_save=False)
    out = pathlib.Path(args.output) if args.output else UI / "generated" / "layout-tool.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print("written %s  (%.1f MB)" % (out, out.stat().st_size / 1024 / 1024))
    url = out.resolve().as_uri()
    print("\n%s" % url)
    if args.open:
        import webbrowser
        webbrowser.open(url)


if __name__ == "__main__":
    main()
