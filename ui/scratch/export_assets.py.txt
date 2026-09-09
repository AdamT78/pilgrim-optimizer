"""Export every glyph the board draws as a standalone SVG into the asset tree.

The board's icons are not files today -- they are built inside mkR.py and only ever exist inside a
rendered page. That is fine while the board is the only consumer, and wrong the moment a second
thing (an asset library, a player-board renderer, a rules PDF) wants the same mark. This writes
them out once, from the generator itself rather than by tracing a screenshot, so the exported file
and the board cannot drift.

Run it with OUTNAME pointed at a scratch file: importing mkR.py rebuilds a board as a side effect.
"""
import os, re, pathlib, sys

ROOT = pathlib.Path('/home/claude/ui-2.0/assets')
NS = {}
os.environ.setdefault("OUTNAME", "_export_scratch.html")
os.environ.setdefault("TILE_S", "0.80")
os.environ.setdefault("TITLE_SZ", "11.4")
exec(compile(pathlib.Path('/tmp/mkR.py').read_text(), '/tmp/mkR.py', 'exec'), NS)

INK = "#2A2320"


def write(rel, body):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body)
    return rel


def wrap(inner, box="-16 -16 32 32", size=32):
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="%s" width="%d" height="%d">'
            '%s</svg>\n' % (box, size, size, inner))


# ---- duty action icons -------------------------------------------------------------------------
# Each act group in the wheel is a pill plus a glyph. The pill is the tile's furniture, not the
# icon, so it comes off: an exported icon is the mark alone, to be framed by whatever draws it.
wheel = NS['wheel']
SLUG = {"Build Roads": "build_roads", "Give Alms": "give_alms"}
written = []
for m in re.finditer(r'<g class="act" data-duty="([^"]+)" data-i="(\d+)"[^>]*>', wheel):
    duty, i = m.group(1), int(m.group(2))
    start = m.start()
    end = NS['_gspan'](wheel, start)
    body = wheel[start:end]
    inner = body[body.index('>', body.index('data-i')) + 1:-4]
    inner = re.sub(r'<rect [^>]*rx="2\.82"[^>]*></rect>', '', inner)   # the pill
    slug = SLUG.get(duty, duty.lower())
    written.append(write('icons/actions/%s_%d.svg' % (slug, i + 1), wrap(inner)))

# ---- stock glyphs ------------------------------------------------------------------------------
# _ico() already emits a complete 16x16 svg -- the same mark the log and the action box use, so the
# asset and the running board are one drawing.
for kind, name in (("piety", "piety"), ("wheat", "wheat"),
                   ("stone", "stone"), ("silver", "silver")):
    svg = NS['_ico'](kind).replace('<svg class="ico"',
                                   '<svg xmlns="http://www.w3.org/2000/svg"')
    written.append(write('icons/resources/%s.svg' % name, svg + "\n"))

# the cornucopia is a tithe like the other three, it just has no stock behind it
written.append(write('icons/resources/cornucopia.svg',
                     wrap('<g transform="scale(%s)">%s</g>' % (NS['_CORN_S'], NS['_cornu']()))))

# ---- markers -----------------------------------------------------------------------------------
# The merchant wagon travels with its own defs so the file does not depend on the wheel's.
wgn = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">'
       '%s<use href="#wgn" color="%s"/></svg>\n' % (NS['_WAGON_DEFS'], "#5A3E8C"))
written.append(write('ui/markers/merchant_wagon.svg', wgn))

print("\n".join(sorted(written)))
print("\n%d files" % len(written))
