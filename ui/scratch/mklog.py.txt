"""Turn the engine's real log into the design's log voice, and render it as a panel.

The lines come from an actual 4-player game (scenarios/play_view_reference_4p_001.json, random
legal actions, seed 7) -- so the SEQUENCE is real. The wording is not: the engine's transcript
names the duty ACTION ("chose Give Alms Paid at Give Alms"), prints raw deltas ("player_three
silver -1") and repeats itself ("CONFESSION_BOX_DECLINED: ..."), none of which the log rule allows.
This is where that rule gets applied: actor, took, the DUTY TILE's name, and what happened.
"""
import json, re, html, pathlib

SEATS = {"player_one": "Red", "player_two": "Yellow",
         "player_three": "Blue", "player_four": "White"}
SEAT_FILL = {"Red": "#B7382E", "Yellow": "#D9B33B", "Blue": "#3B6EA5", "White": "#F4EFE2"}
SEAT_EDGE = {"Red": "#7A241C", "Yellow": "#8A6B1E", "Blue": "#254A73", "White": "#8B7B4E"}

DROP = (re.compile(r"ended the turn"), re.compile(r"^CONFESSION_BOX_"),
        re.compile(r"^player_\w+ (silver|stone|wheat|piety) -?\d+$"),
        re.compile(r"recalled \d+ acolytes? from .+ to City"))
START = re.compile(r"^(player_\w+) (chose|took the tithe|declined|sowed)")

def seat(pid): return SEATS.get(pid, pid)

def blocks(lines):
    out, cur = [], None
    for raw in lines:
        line = raw.strip()
        if any(p.search(line) for p in DROP):
            continue
        if START.match(line) or line.startswith("Round end:") or line.startswith("Setup complete"):
            if cur: out.append(cur)
            cur = [line]
        elif cur is not None:
            cur.append(line)
    if cur: out.append(cur)
    return out

def _join(bits):
    if len(bits) == 1: return bits[0]
    return ", ".join(bits[:-1]) + " and " + bits[-1]

def result_clause(rest):
    """Gains, cost and movement, each collected before any of it is written -- otherwise the
    sentence comes out as "took Taxation and took 1 stone and 1 silver", which is the engine's
    line count showing through the prose."""
    gains, placed, moved, paid = [], [], [], []
    for line in rest:
        m = re.search(r"moved on the Alms table from row (\d+) to row (\d+)", line)
        if m: moved.append("moved %d on the Alms table" % (int(m[2]) - int(m[1]))); continue
        m = re.search(r"moved \d+ acolytes? from Abbey to (.+)\.", line)
        if m: placed.append(m[1]); continue
        m = re.search(r"took bonus (\w+) from other majority duties", line)
        if m: gains.append("1 %s in majority" % m[1]); continue
        m = re.search(r"took (\w+) from .+\.", line)
        if m: gains.append("1 %s" % m[1]); continue
        m = re.search(r"gained (\d+) piety", line)
        if m: gains.append("%s piety" % m[1]); continue
        m = re.search(r"paid (\d+) silver and (\d+) wheat", line)
        if m and int(m[1]): paid.append("paid %s silver" % m[1]); continue
    bits = []
    if gains: bits.append("gained " + _join(gains))
    if paid: bits += paid
    if moved: bits += moved
    if placed:
        bits.append(("placed an acolyte on " if len(placed) == 1 else "placed acolytes on ")
                    + _join(placed))
    return _join(bits) if bits else None

def entry(block):
    head, rest = block[0], block[1:]
    E, B = html.escape, lambda t: "<b>%s</b>" % html.escape(t)
    # No "took" before the tile: every entry in the log is a duty taken, so the verb was the
    # same word on every line and the tile is what the eye is looking for anyway.
    m = re.match(r"^(player_\w+) chose (.+) at (.+)\.$", head)
    if m and not m[3].startswith("player"):
        clause = result_clause(rest)
        return (seat(m[1]), "%s%s." % (B(m[3]), (", " + E(clause)) if clause else ""))
    # The tithe is always one of its stock, so the figure says nothing the icon does not.
    m = re.match(r"^(player_\w+) took the tithe at (.+) and gained (\w+)\.$", head)
    if m:
        return (seat(m[1]), "%s and took Tithe gaining %s." % (B(m[2]), E(m[3])))
    m = re.match(r"^(player_\w+) declined the Confession Box\.$", head)
    if m: return (seat(m[1]), "declined the %s." % B("Confession Box"))
    m = re.match(r"^(player_\w+) sowed (.+), ending at (.+)\.$", head)
    if m: return (seat(m[1]), "sowed %s, ending at %s." % (E(m[2]), B(m[3])))
    m = re.match(r"^(player_\w+) chose (player_\w+) to begin this round\.$", head)
    if m: return (seat(m[1]), "chose %s to begin the round." % seat(m[2]))
    m = re.match(r"^Setup complete\. (player_\w+) begins this round\.$", head)
    if m: return (None, "Setup complete. %s begins." % seat(m[1]))
    return (None, html.escape(head))

def _disc(who, mid=False):
    """Every gap around a disc is a MARGIN, never a space character. A literal space is ~3.4px at
    this size and a margin is 6, so mixing them gave three different gaps: 6 after the leading
    disc, 3.4 before an in-text one, and 9.4 after it."""
    return ('<span class="disc%s" style="background:%s;border-color:%s"></span>'
            % (" mid" if mid else "", SEAT_FILL[who], SEAT_EDGE[who]))

def _discify(text):
    """Every seat named inside a sentence becomes its disc, whitespace and all -- the margins
    replace the spaces, so the gap is the same one the leading disc keeps."""
    for nm in SEAT_FILL:
        text = re.sub(r"\s*\b%s\b\s*" % nm, lambda _m, n=nm: _disc(n, mid=True), text)
    return text

def render(lines, mode):
    """mode 'name' colours the seat's name; mode 'disc' puts the alms table's own player disc
    before an ink name."""
    out, round_no = [], 1
    for b in blocks(lines):
        head = b[0]
        if head.startswith("Round end:"):
            m = re.search(r"ship advanced from \d+ to (\d+)", head)
            if m:
                round_no = int(m[1]) + 1
                out.append('<div class="rule"><span>Round %d</span></div>' % round_no)
                continue
            m = re.search(r"Merchant advanced from .+ to (.+)\.", head)
            if m:
                out.append('<div class="ev merch">The Merchant moved to %s.</div>'
                           % html.escape(m[1]))
                continue
            m = re.search(r"(player_\w+) takes the First Player marker", head)
            if m:
                nm = seat(m[1])
                lead = _disc(nm) if mode == "disc" else nm + " "
                out.append('<div class="ev">%stakes the First Player marker.</div>' % lead)
                continue
            continue
        who, text = entry(b)
        if who is None:
            body = _discify(text) if mode == "disc" else text
            out.append('<div class="ev">%s</div>' % body)
            continue
        if mode == "disc":
            tag = _disc(who)
        else:
            tag = '<b class="nm" style="color:%s">%s</b> ' % (SEAT_EDGE[who], who)
        body = _discify(text) if mode == "disc" else text
        out.append('<div class="e">%s%s</div>' % (tag, body))
    return "".join(out)

LINES = json.load(open('/tmp/loglines.json'))
pathlib.Path('/tmp/log_name.html').write_text(render(LINES, "name"))
pathlib.Path('/tmp/log_disc.html').write_text(render(LINES, "disc"))
print("entries:", render(LINES, "disc").count('<div class="e"'),
      "| rules:", render(LINES, "disc").count('class="rule"'))
