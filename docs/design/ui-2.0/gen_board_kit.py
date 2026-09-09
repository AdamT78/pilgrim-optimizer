"""The player-card drawing kit: colours, pills, cubes, numerals, the wax seal.

Extracted from the scratch generator so that the board and the picker can be rebuilt from the
repository alone. What was left behind is deliberate: the scratch module also carried a `portrait()`
that read a Base64 bundle of the afilinkov NPC art, whose licence is personal-use only and forbids
use in any project. Nothing here touches it -- the portrait the card actually draws is a few lines
of geometry in `gen_board.py` -- so this module has no licence encumbrance and no /tmp dependency.

The pill geometry is not invented here either. It is derived from the live renderer's own constants
(`ui_debug.render_player_boards_v2`) through the scale factor K, so a change to the game's resource
chooser reaches these studies instead of silently diverging from them -- which is also why this
module must be imported with the repository root on the path.
"""
import math, pathlib, re, sys

def _repo_root():
    """Find the checkout by looking for the renderer, not by counting directories up.

    Counting is what breaks when a study file is copied somewhere to be run; searching for the
    thing actually needed does not care where this file sits.
    """
    for base in list(pathlib.Path(__file__).resolve().parents) + [pathlib.Path.cwd().resolve()]:
        if (base / "tools" / "ui_debug" / "render_player_boards_v2.py").exists():
            return base
    raise RuntimeError("cannot find the pilgrim checkout: run this from inside the repository")


_ROOT = _repo_root()
for _p in (str(_ROOT / "tools"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from ui_debug.render_player_boards_v2 import (_ICON_RENDERERS, resource_icon_size,
    STOCK_CHOICE_PAINT, RESOURCE_CHOICE_RADIUS, RESOURCE_CHOICE_WIDTH, STOCK_CHOICE_STROKE_WIDTH)
PARCH="#E5D8B9"; PARCH2="#F0E7D2"; INK="#2A2320"; PALE="#A89B7E"
SEAT={"red":("#B7382E","#7A241C"),"yellow":("#D9B33B","#8A6B1E"),
      "blue":("#3B6EA5","#254A73"),"white":("#FFFFFF","#8B7B4E")}
PIETY_F,PIETY_S="#C9A0C9","#6B4A6B"; SERF_F,SERF_S="#9A958A","#4E4A43"; SEAL_GOLD="#C9A227"
RESICON={"wheat":"wheat","stone":"cube","silver":"coin"}
PLAYERS=[
 dict(seat="red",   serfs=6, acolytes=3, wheat=2, stone=1, silver=4, piety=7, seal=True, active=True),
 dict(seat="yellow",serfs=8, acolytes=2, wheat=0, stone=3, silver=1, piety=4),
 dict(seat="blue",  serfs=5, acolytes=4, wheat=3, stone=0, silver=2, piety=9),
 dict(seat="white", serfs=7, acolytes=1, wheat=1, stone=2, silver=0, piety=2),
]
def _bbox(svg):
    xs=[];ys=[]
    for m in re.finditer(r'<line[^>]*x1="(-?[\d.]+)"[^>]*y1="(-?[\d.]+)"[^>]*x2="(-?[\d.]+)"[^>]*y2="(-?[\d.]+)"',svg):
        a,b,c,d=map(float,m.groups()); xs+=[a,c]; ys+=[b,d]
    for m in re.finditer(r'<ellipse[^>]*cx="(-?[\d.]+)"[^>]*cy="(-?[\d.]+)"[^>]*rx="(-?[\d.]+)"[^>]*ry="(-?[\d.]+)"',svg):
        cx,cy,rx,ry=map(float,m.groups()); r=max(rx,ry); xs+=[cx-r,cx+r]; ys+=[cy-r,cy+r]
    for m in re.finditer(r'<circle[^>]*cx="(-?[\d.]+)"[^>]*cy="(-?[\d.]+)"[^>]*r="(-?[\d.]+)"',svg):
        cx,cy,r=map(float,m.groups()); xs+=[cx-r,cx+r]; ys+=[cy-r,cy+r]
    for m in re.finditer(r'd="([^"]+)"',svg):
        for p in re.finditer(r'(-?[\d.]+),(-?[\d.]+)',m.group(1)):
            xs.append(float(p.group(1))); ys.append(float(p.group(2)))
    return min(xs),max(xs),min(ys),max(ys)
BOX={k:_bbox(_ICON_RENDERERS[RESICON[k]](0.0,0.0,resource_icon_size(RESICON[k]),"#000")) for k in RESICON}
PILL_W,PILL_H,ICON_H,CUBE = 36.0,33.0,22.0,18.0
K=PILL_W/RESOURCE_CHOICE_WIDTH
def darken(c,f):
    b=c.lstrip("#"); return "#"+"".join(f"{round(int(b[i:i+2],16)*f):02X}" for i in (0,2,4))
W1,W2=0.045,0.026; CROWN=((-.50,.42),(-.50,-.34),(-.22,.02),(0,-.46),(.22,.02),(.50,-.34),(.50,.42))
def waxpts(cx,cy,r,seed=1.1):
    o=[]
    for i in range(26):
        a=2*math.pi*i/26
        rr=r*(1+W1*math.sin(3*a+seed)+W2*math.sin(5*a+seed*1.7))
        o.append(f"{cx+math.cos(a)*rr:.2f},{cy+math.sin(a)*rr:.2f}")
    return " ".join(o)
def seal(cx,cy,r,wax=SEAL_GOLD,tilt=-14.0):
    w=r*.90; h=w*.86
    cp=" ".join(f"{cx+fx*w:.2f},{cy+fy*h:.2f}" for fx,fy in CROWN)
    return (f'<g transform="rotate({tilt} {cx} {cy})">'
            f'<polygon points="{waxpts(cx,cy,r)}" fill="{wax}" stroke="{darken(wax,.45)}" stroke-width="{r*.10:.2f}"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r*.78:.2f}" fill="none" stroke="{darken(wax,.72)}" stroke-width="{r*.08:.2f}"/>'
            f'<polygon points="{cp}" fill="{darken(wax,.50)}"/></g>')
FACE='<circle cx="0" cy="-4" r="6.5"/><path d="M-11 14 V9 a11 11 0 0 1 22 0 V14"/>'
def cube(f,s,size=CUBE):
    return (f'<rect x="{-size/2}" y="{-size/2}" width="{size}" height="{size}" fill="{f}" '
            f'stroke="{s}" stroke-width="1.4"/>')
def pillShell(fill,stroke):
    return (f'<rect x="{-PILL_W/2:.1f}" y="{-PILL_H/2:.1f}" width="{PILL_W:g}" height="{PILL_H:g}" '
            f'rx="{RESOURCE_CHOICE_RADIUS*K:.1f}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{STOCK_CHOICE_STROKE_WIDTH*K+0.5:.2f}"/>')
def resPill(kind):
    fill,stroke=STOCK_CHOICE_PAINT[kind]; icon=RESICON[kind]; size=resource_icon_size(icon)
    x0,x1,y0,y1=BOX[kind]; s=ICON_H/(y1-y0); dx,dy=-(x0+x1)/2,-(y0+y1)/2
    return (pillShell(fill,stroke)+f'<g transform="scale({s:.3f}) translate({dx:.2f} {dy:.2f})">'
            + _ICON_RENDERERS[icon](0.0,0.0,size,INK) + '</g>')
def pietyPill(style="cross"):
    r=ICON_H/2
    g=(f'<circle r="{r:.1f}" fill="none" stroke="{INK}" stroke-width="1.6"/>'
       f'<path d="M0 {-r*0.62:.1f}V{r*0.62:.1f}M{-r*0.62:.1f} 0H{r*0.62:.1f}" stroke="{INK}" '
       f'stroke-width="2.4" stroke-linecap="round"/>') if style=="cross" else (
       f'<circle r="{r:.1f}" fill="none" stroke="{INK}" stroke-width="1.5"/>'
       f'<circle r="{r*0.52:.1f}" fill="{INK}" fill-opacity=".85"/>')
    return pillShell(PIETY_F,PIETY_S)+g
def num(x,y,v,size=14,fill=INK,anchor="start",weight=700):
    return (f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" fill="{fill}" '
            f'font-weight="{weight}" font-family="Georgia,serif">{v}</text>')
COLS=(118,192,266); NUMDX=23
def slot(cx,y,mark,val):
    return f'<g transform="translate({cx} {y})">{mark}</g>'+num(cx+NUMDX,y+5,val)
def card(w,h,p,rx=9,top=0):
    f,_=SEAT[p["seat"]]
    o=f'<rect y="{top}" width="{w}" height="{h}" rx="{rx}" fill="{PARCH}" stroke="{INK}" stroke-width="1.2"/>'
    o+=f'<path d="M9 {top} H7 a{rx} {rx} 0 0 0-{rx} {rx} V{top+h-rx} a{rx} {rx} 0 0 0 {rx} {rx} H9 Z" fill="{f}"/>'
    return o
