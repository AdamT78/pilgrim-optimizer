// V4.5: a size for the Tithe and City captions, and one line across the action band.
//
// Two changes, and the second is the reason the first needed testing in a browser at all.
//
// TAKE TITHE and THE CITY were the last text on the board whose size was fixed in the stylesheet
// and both now have a control. That much a source test can check. What it cannot check is the
// thing the controls immediately broke: the four captions on the action band print on two
// baselines -- the artwork's action NAMES and THE CITY along the top, the artwork's EFFECT lines
// and TAKE TITHE along the bottom -- and they only did so before because 9px of City padding
// happened to put 13px of type exactly where 6px of artwork padding put 17px. Nothing held it
// there. Whether it holds NOW is a question about rendered glyphs, and this is what asks it.
//
// The measurement to be careful about: a top-anchored caption is lined up on its FIRST line's
// baseline and a bottom-anchored one on its LAST, because those are the lines that sit next to
// each other. Probing the wrong end made a working version of this look badly broken.
import { chromium } from 'playwright';
import path from 'path';
import { fileURLToPath, pathToFileURL } from 'url';
const HERE = path.dirname(fileURLToPath(import.meta.url));
const CHROMIUM = process.env.LAYOUT_LAB_CHROMIUM
  || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';

const b = await chromium.launch({executablePath: CHROMIUM});
const p = await b.newPage({viewport:{width:1900,height:1400}, deviceScaleFactor:1});
const errs = [];
p.on('pageerror', e => errs.push('pageerror: ' + e.message));
p.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text()); });
await p.goto(process.argv[2] || pathToFileURL(path.join(HERE, 'lab.html')).href);
await p.evaluate(() => localStorage.clear());
await p.reload(); await p.waitForTimeout(450);

let n = 0, fail = 0; const R = [];
function ck(test, name, ok, detail){
  n++; if (!ok) fail++;
  let d = detail === undefined ? undefined : String(detail);
  if (d !== undefined && d.length > 120) d = d.slice(0, 117) + '...';
  R.push((ok?'PASS ':'FAIL ') + test + ' :: ' + name + (d===undefined?'':'   ['+d+']'));
}

try {

// A ZERO-SIZE INLINE-BLOCK SITS ON THE BASELINE, so its bottom edge is the baseline. It is the
// only way to get at one from script, and it is exact -- no font tables, no assumptions about
// ascent, and it reports what was actually drawn.
await p.evaluate(() => {
  window.__base = function(el, which){
    if (!el) return null;
    const s = document.createElement('span');
    s.style.cssText = 'display:inline-block;width:0;height:0;vertical-align:baseline';
    which === 'last' ? el.appendChild(s) : el.insertBefore(s, el.firstChild);
    const r = s.getBoundingClientRect(); s.remove();
    // Divided back out of the stage's scale, so every number here is in module pixels.
    const k = +(document.getElementById('stage').style.transform.match(/[\d.]+/)||[1])[0];
    return +(r.bottom / k).toFixed(2);
  };
  window.__row = function(){
    const L = '.obj[data-kind="art"][data-id="left"]', R = '.obj[data-kind="art"][data-id="right"]';
    const q = s => document.querySelector(s);
    return {
      top: {artL: __base(q(L+' .anm'),'first'), artR: __base(q(R+' .anm'),'first'),
            city: __base(q('#cityObj .cl'),'first')},
      bot: {artL: __base(q(L+' .cap'),'last'),  artR: __base(q(R+' .cap'),'last'),
            tithe: __base(q('#titheObj .tl'),'last')},
    };
  };
  window.__sizes = function(nm, ef, ti, ci){
    S.view = 'action';
    for (const s of ['left','right']){ const a = artOf(s); a.nameSize = nm; a.labelSize = ef; }
    S.tithe.labelSize = ti; S.city.labelSize = ci;
    commitPanels();
    return __row();
  };
});
const spread = o => {
  const v = Object.values(o).filter(x => x != null);
  return +(Math.max(...v) - Math.min(...v)).toFixed(2);
};

// §1 THE CONTROLS EXIST AND MOVE THE TYPE ----------------------------------------------------
const sized = await p.evaluate(() => {
  S.view = 'action'; S.tithe.labelSize = 34; S.city.labelSize = 26; commit();
  const f = s => getComputedStyle(document.querySelector(s)).fontSize;
  return {tithe: f('#titheObj .tl'), city: f('#cityObj .cl')};
});
ck('§1', 'the Tithe caption takes its size from the control', sized.tithe === '34px', sized.tithe);
ck('§1', 'and so does the City heading', sized.city === '26px', sized.city);

const bounds = await p.evaluate(() => {
  S.tithe.labelSize = 900; S.city.labelSize = -5; applyState(clone(S));
  const a = {tithe: S.tithe.labelSize, city: S.city.labelSize};
  const d = clone(DEFAULT_STATE); delete d.tithe.labelSize; delete d.city.labelSize;
  applyState(d);
  return {clamped: a, missing: {tithe: S.tithe.labelSize, city: S.city.labelSize}};
});
ck('§1', 'an absurd size is pulled into range, not thrown away',
   bounds.clamped.tithe === 60 && bounds.clamped.city === 8, JSON.stringify(bounds.clamped));
ck('§1', 'a missing size opens at the design, which is a different thing',
   bounds.missing.tithe === 17 && bounds.missing.city === 13, JSON.stringify(bounds.missing));

// §2 ONE LINE, AT ANY COMBINATION OF THE FOUR SIZES -------------------------------------------
// The matrix is not decorative. Every one of these was a size at which some earlier version of
// the arithmetic was wrong: the two 'largest' rows are where lining up on the artwork alone
// became geometrically impossible and silently clamped, and the 'everything large' row is where
// a captions-scale-linearly assumption was three pixels out.
const MATRIX = [
  ['defaults',              17, 17, 17, 13],
  ['a bigger Tithe',        17, 17, 34, 13],
  ['a bigger City',         17, 17, 17, 26],
  ['a huge action name',    40, 17, 17, 13],
  ['a huge effect line',    17, 40, 17, 13],
  ['all four different',    28, 22, 11, 36],
  ['everything at the min',  8,  8,  8,  8],
  ['everything at the max', 60, 60, 60, 60],
  ['the City largest',      12, 12, 12, 60],
  ['the Tithe largest',     12, 12, 60, 12],
];
// 0.3px, and the number is load-bearing. At 0.75 this suite passed with the baseline fraction
// replaced by a constant -- which misplaces the City heading by 0.72px at the DEFAULT sizes,
// because the browser rounds a baseline to a whole pixel and a constant cannot. Correct code
// scores 0.02px here, so the headroom is still enormous; it was the slack that was wrong.
const TOL = 0.3;
for (const [why, nm, ef, ti, ci] of MATRIX){
  const r = await p.evaluate(a => __sizes(...a), [nm, ef, ti, ci]);
  ck('§2', `top line holds · ${why}`, spread(r.top) <= TOL,
     `spread ${spread(r.top)}px · ` + JSON.stringify(r.top));
  ck('§2', `bottom line holds · ${why}`, spread(r.bot) <= TOL,
     `spread ${spread(r.bot)}px · ` + JSON.stringify(r.bot));
}

// §3 THE LINE DOES NOT MOVE WHEN A ONE-ACTION DUTY HIDES THE RIGHT SLOT ------------------------
// Taxation and Allocation draw one artwork. If the hidden slot were dropped from the reckoning
// the whole band would shift as the wheel is stepped through the duties -- a layout change as a
// side effect of which duty is reached.
// THE RIGHT SLOT IS DELIBERATELY THE TALLEST CAPTION ON BOTH EDGES. With all four the same
// size it makes no difference whether the hidden slot is counted, and this section passed while
// the code dropped it -- the test was agreeing with anything.
const step = await p.evaluate(() => {
  __sizes(14, 14, 14, 14);
  const r = artOf('right'); r.nameSize = 44; r.labelSize = 44;
  S.selectedDuty = 'clerical'; commitPanels(); const two = __row();
  S.selectedDuty = 'taxation'; commitPanels(); const one = __row();
  return {two, one, rightDrawn: !!document.querySelector('.obj[data-kind="art"][data-id="right"]')};
});
ck('§3', 'a one-action duty really does hide the right slot', step.rightDrawn === false);
ck('§3', 'the top line is where it was', Math.abs(step.two.top.artL - step.one.top.artL) < 0.01
   && Math.abs(step.two.top.city - step.one.top.city) < 0.01,
   JSON.stringify({two: step.two.top, one: step.one.top}));
ck('§3', 'and so is the bottom line', Math.abs(step.two.bot.artL - step.one.bot.artL) < 0.01
   && Math.abs(step.two.bot.tithe - step.one.bot.tithe) < 0.01,
   JSON.stringify({two: step.two.bot, one: step.one.bot}));

// §4 THE CITY IS ON THE LINE IN STATES WHERE THERE IS NO ARTWORK TO SEE ------------------------
// READY and SOWING draw the City and no artwork at all. The heading still has to sit where the
// action names would have put theirs, or the band jumps as the view is stepped through.
const acrossViews = await p.evaluate(() => {
  const out = {};
  for (const v of ['action', 'ready', 'sow']){
    S.view = v; const a = artOf('left'); a.nameSize = 17; a.labelSize = 17;
    S.city.labelSize = 13; commitPanels();
    out[v] = {city: __base(document.querySelector('#cityObj .cl'), 'first'),
              artDrawn: !!document.querySelector('.obj[data-kind="art"]')};
  }
  return out;
});
ck('§4', 'no artwork is drawn in READY or SOWING',
   acrossViews.ready.artDrawn === false && acrossViews.sow.artDrawn === false);
ck('§4', 'the City heading does not move between the three states',
   Math.abs(acrossViews.ready.city - acrossViews.action.city) < 0.01
   && Math.abs(acrossViews.sow.city - acrossViews.action.city) < 0.01,
   JSON.stringify(acrossViews));

// §5 THE TITHE CARD KEEPS ROOM FOR ITS CAPTION, MEASURED ---------------------------------------
// The reserve used to be a flat 36px, right for exactly one size. Estimating it from the font
// size was tried and is wrong as soon as the caption wraps, which TAKE TITHE does at 34px in a
// 178px card -- the second line then sits on the tokens.
const reserve = await p.evaluate(() => {
  const read = () => {
    const c = document.getElementById('titheObj');
    return {pad: parseFloat(getComputedStyle(c).paddingBottom),
            capH: c.querySelector('.tl').getBoundingClientRect().height,
            capTop: c.querySelector('.tl').getBoundingClientRect().top,
            pyrBottom: c.querySelector('.pyr').getBoundingClientRect().bottom};
  };
  S.view = 'action'; __sizes(17, 17, 17, 13); const small = read();
  __sizes(17, 17, 34, 13); const big = read();
  return {small, big};
});
ck('§5', 'a 34px TAKE TITHE really does wrap in a 178px card',
   reserve.big.capH > reserve.small.capH * 1.8,
   `${reserve.small.capH.toFixed(1)} -> ${reserve.big.capH.toFixed(1)} px tall`);
ck('§5', 'the card reserves more room when it does',
   reserve.big.pad > reserve.small.pad + 10,
   `${reserve.small.pad} -> ${reserve.big.pad} px`);
ck('§5', 'so the tokens never end up on top of the caption',
   reserve.big.capTop >= reserve.big.pyrBottom - 0.5,
   `caption top ${reserve.big.capTop.toFixed(1)} · tokens end ${reserve.big.pyrBottom.toFixed(1)}`);

// §7 NO CAPTION IS PUSHED OUT OF ITS OWN CARD -------------------------------------------------
// This is what taking the TALLEST caption actually buys, and it is not obvious. Every caption on
// an edge is dropped onto that edge's line by padding, so they agree with each other whatever
// line is chosen -- the arithmetic is self-correcting and §2 stays green even when the line is
// taken from the wrong set. What changes is whether the line is reachable: measure it from the
// artwork alone and a City heading bigger than the artwork's name needs NEGATIVE padding to get
// its baseline that high. Taking the max guarantees every caption's offset is at least the
// artwork's own 6px, less its card's 1px border.
for (const [why, nm, ef, ti, ci] of [
  ['the City far larger than the artwork',  10, 10, 10, 58],
  ['the Tithe far larger than the artwork', 10, 10, 58, 10],
  ['the artwork far larger than both',      58, 58, 10, 10],
  ['all four at the maximum',               60, 60, 60, 60],
]){
  const inside = await p.evaluate(a => {
    __sizes(...a);
    const k = +(document.getElementById('stage').style.transform.match(/[\d.]+/)||[1])[0];
    const pair = (capSel, boxSel) => {
      const c = document.querySelector(capSel), b = document.querySelector(boxSel);
      if (!c || !b) return null;
      const cr = c.getBoundingClientRect(), br = b.getBoundingClientRect();
      return {over: +(Math.max(br.top - cr.top, cr.bottom - br.bottom) / k).toFixed(2)};
    };
    return {
      city: pair('#cityObj .cl', '#cityObj'),
      tithe: pair('#titheObj .tl', '#titheObj'),
      artName: pair('.obj[data-kind="art"][data-id="left"] .anm',
                    '.obj[data-kind="art"][data-id="left"]'),
      artEff: pair('.obj[data-kind="art"][data-id="left"] .cap',
                   '.obj[data-kind="art"][data-id="left"]'),
    };
  }, [nm, ef, ti, ci]);
  const worst = Math.max(...Object.values(inside).filter(v => v).map(v => v.over));
  ck('§7', `every caption stays inside its card · ${why}`, worst <= 0,
     `worst overhang ${worst}px · ` + JSON.stringify(inside));
}

// §6 THE MEASUREMENT SETTLES -------------------------------------------------------------------
// Everything above is read back off the thing being positioned. If a second pass disagreed with
// the first the band would creep, a pixel at a time, under a drag.
const settle = await p.evaluate(() => {
  __sizes(23, 19, 31, 41);
  const snap = () => JSON.stringify(__row());
  const a = snap(); render(); const b2 = snap(); render(); const c = snap();
  return {a, b: b2, c};
});
ck('§6', 'a second and third render read the same baselines back',
   settle.a === settle.b && settle.b === settle.c, settle.a);

ck('ALL', 'no page or console errors', errs.length === 0, errs.slice(0,3).join(' | '));
} catch (e) {
  ck('ALL', 'the run completed without throwing', false,
     (e && e.message ? e.message : String(e)).split('\n')[0]);
}
await b.close();
const out = R.join('\n') + `\n\n${n - fail}/${n} passed, ${fail} failed.\n`;
console.log(process.argv[2]
  ? out.split('\n').filter(l => l.startsWith('FAIL')).concat(out.trim().split('\n').pop()).join('\n')
  : out);
process.exit(fail ? 1 : 0);
