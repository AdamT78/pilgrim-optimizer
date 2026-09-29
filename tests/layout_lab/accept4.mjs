// V4 ACCEPTANCE. Every check is a measurement taken from the live page, not from the source.
import { chromium } from 'playwright';
import fs from 'fs';
// Paths are derived from this file so the suite runs from any checkout, and the browser can be
// pointed elsewhere with LAYOUT_LAB_CHROMIUM -- the container this was written in keeps chromium
// at a versioned path that exists nowhere else.
import path from 'path';
import { fileURLToPath, pathToFileURL } from 'url';
const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..', '..');
const OUT = process.env.LAYOUT_LAB_OUT || path.join(ROOT, 'out');
const FIXTURES = process.env.LAYOUT_LAB_ASSETS || path.join(HERE, 'fixtures');
const CHROMIUM = process.env.LAYOUT_LAB_CHROMIUM
  || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';


const A = FIXTURES + '/';
const b = await chromium.launch({executablePath: CHROMIUM});
const p = await b.newPage({viewport:{width:1900,height:1400}, deviceScaleFactor:1});

const errs = [];
p.on('pageerror', e => errs.push('pageerror: ' + e.message));
p.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text()); });

const PAGE = process.argv[2] || pathToFileURL(path.join(OUT, 'lab.html')).href;
await p.goto(PAGE);
await p.evaluate(() => localStorage.clear());
await p.reload();
await p.waitForTimeout(400);

let n = 0, fail = 0;
const R = [];
function ck(group, name, ok, detail){
  n++; if (!ok) fail++;
  R.push((ok ? 'PASS ' : 'FAIL ') + group + ' :: ' + name + (detail === undefined ? '' : '   [' + detail + ']'));
}
const near = (a, t, e = 1) => Math.abs(a - t) <= e;

const box = (sel) => p.evaluate(s => {
  const e = document.querySelector(s); if (!e) return null;
  return {x: parseFloat(e.style.left), y: parseFloat(e.style.top),
          w: parseFloat(e.style.width), h: parseFloat(e.style.height),
          z: +getComputedStyle(e).zIndex, cls: e.className, txt: e.innerText.trim()};
}, sel);
const setView = v => p.evaluate(x => { setView(x); }, v);
const clean = on => p.evaluate(o => { if ((document.body.classList.contains('clean')) !== o)
  document.getElementById('bMode').click(); }, on);

// EVERYTHING BELOW RUNS INSIDE ONE try -- see accept421.mjs for why: a throw used to kill the
// process before its summary, and a mutation run reading only the exit code scored that as a
// catch even though no assertion had judged anything.
try {

// ---------------------------------------------------------------------------------------------
// 1. THE MODULE
// ---------------------------------------------------------------------------------------------
const meta = await p.evaluate(() => ({
  ver: STATE_VERSION, build: BUILD_VERSION, cw: CANVAS_W, ch: CANVAS_H,
  order: DUTY_ORDER.slice(), views: VIEW_STATES.map(v => v.key),
  stage: {w: parseFloat(document.getElementById('stage').style.width || getComputedStyle(document.getElementById('stage')).width),
          h: parseFloat(getComputedStyle(document.getElementById('stage')).height)},
}));
ck('1 module', 'state version is 4', meta.ver === 4, meta.ver);
// THE BUILD LABEL MOVES AND THE SCHEMA DOES NOT, which is the claim worth holding rather than
// any particular number -- pinning the number here would mean editing this file for every
// corrective release, which is how a check stops meaning anything.
ck('1 module', 'the build label is a 4.x corrective release',
   /^4\.[1-9]\d*(\.\d+)?$/.test(meta.build), meta.build);
ck('1 module', 'and the schema version did not move with it', meta.ver === 4, meta.ver);
ck('1 module', 'canvas is 1400 x 1200', meta.cw === 1400 && meta.ch === 1200, meta.cw + 'x' + meta.ch);
ck('1 module', 'stage is the canvas', near(meta.stage.w, 1400, 2) && near(meta.stage.h, 1200, 2),
   meta.stage.w + 'x' + meta.stage.h);
ck('1 module', 'eight duties in wheel order', meta.order.length === 8, meta.order.join(','));
ck('1 module', 'three view states', meta.views.join(',') === 'ready,sow,action', meta.views.join(','));

// ---------------------------------------------------------------------------------------------
// 2. THE WHEEL DOMINATES AND IS IDENTICAL IN ALL THREE STATES
// ---------------------------------------------------------------------------------------------
await clean(true);
const wheels = {}, cities = {}, cards = {}, figs = {};
for (const v of ['ready','sow','action']){
  await setView(v); await p.waitForTimeout(120);
  wheels[v] = await box('#wheelObj');
  cities[v] = await box('#cityObj');
  cards[v]  = await box('.obj[data-kind=card][data-id=clerical]');
  figs[v]   = await p.evaluate(() => [].slice.call(document.querySelectorAll('.obj[data-kind=figs]'))
                .map(e => e.style.left + ',' + e.style.top).join('|'));
}
const W = wheels.ready;
// THE SHAPE IS THE ASSET'S, so the page is asked what its own built-in wheel says rather than
// being checked against a ratio this file chose.
const asset = await p.evaluate(() => {
  const svg = document.querySelector('#wheelObj svg');
  const vb = svg && svg.viewBox.baseVal;
  return {ratio: WHEEL_RATIO, vbw: vb && vb.width, vbh: vb && vb.height,
          faces: document.querySelectorAll('#wheelObj svg #faces path').length,
          text: document.querySelectorAll('#wheelObj svg text, #wheelObj svg tspan').length,
          stored: S.wheel.naturalRatio,
          colours: [].slice.call(document.querySelectorAll('#wheelObj svg *'))
                      .map(e => e.getAttribute('fill')).filter(Boolean),
          ground: !!document.querySelector('#wheelObj [id="ground"]'),
          groundShown: (function(){ const g = document.querySelector('#wheelObj [id="ground"]');
            return !!g && getComputedStyle(g).display !== 'none'; })(),
          src: S.wheel.ratioSource};
});
ck('2 wheel', 'the wheel is the built-in duty wheel v2', asset.faces === 9, asset.faces);
ck('2 wheel', 'its viewBox is 1000 x 529.9, an aspect of 1.887',
   asset.vbw === 1000 && near(asset.vbh, 529.9, 0.01)
     && near(asset.vbw / asset.vbh, 1.887, 0.001),
   asset.vbw + 'x' + asset.vbh + ' = ' + (asset.vbw / asset.vbh).toFixed(4));
ck('2 wheel', 'the page takes its ratio from that viewBox',
   // 1e-6, not 1e-9: the SVG DOM hands back single-precision floats for viewBox numbers.
   near(asset.ratio, asset.vbh / asset.vbw, 1e-6) && asset.src === 'builtin',
   asset.ratio.toFixed(5) + ' / ' + asset.src);
// AND THE SAVED STATE CARRIES IT, not just the constant. The state is what a rescale reads and
// what an export hands on, so a default whose ratio disagreed with the drawing would re-project
// the wheel the first time anybody dragged a corner.
ck('2 wheel', "the saved state's ratio is the drawing's too",
   near(asset.stored, asset.vbh / asset.vbw, 1e-6), asset.stored);
ck('2 wheel', 'nothing in the drawing is text', asset.text === 0, asset.text);
// THE RECOLOUR REACHED THE PAGE. The drawing is built in parchment and the lab wears slate, and
// a palette that silently stopped matching would leave a cream wheel on a black field.
ck('2 wheel', 'the parchment palette is gone from the drawn wheel',
   !asset.colours.some(c => /#(efe3c8|e8dcc0|17130d)/i.test(c)),
   asset.colours.filter(c => /#(efe3c8|e8dcc0|17130d)/i.test(c)).join(',') || 'none left');
ck('2 wheel', "the faces wear the placeholder's slate",
   asset.colours.filter(c => c.toLowerCase() === '#3a3d45').length === 8,
   asset.colours.filter(c => c.toLowerCase() === '#3a3d45').length);
ck('2 wheel', 'the hub is darker than the faces',
   asset.colours.some(c => c.toLowerCase() === '#23262b'),
   asset.colours.join(' '));
ck('2 wheel', "the asset's own ground rectangle is there but not shown",
   asset.ground && !asset.groundShown, asset.ground + '/' + asset.groundShown);
ck('2 wheel', 'wheel x/y is centred at 438', W.x === (1400 - W.w) / 2 && W.y === 438,
   W.x + ',' + W.y);
ck('2 wheel', 'the box keeps the asset ratio', near(W.h, Math.round(W.w * asset.ratio), 1),
   W.w + 'x' + W.h);
ck('2 wheel', 'wheel bottom sits inside the module', W.y + W.h <= 1200, W.y + W.h);
// WHICHEVER BOUND BINDS: growing the wheel by one even step must break one ceiling or the
// other, whether that is the module's floor or its side margin. At 1.887 it is the margin.
ck('2 wheel', 'no larger wheel would fit the module',
   W.y + Math.round((W.w + 2) * asset.ratio) > 1200 || (1400 - (W.w + 2)) / 2 < 14,
   'bottom ' + (W.y + Math.round((W.w + 2) * asset.ratio))
     + ', margin ' + ((1400 - (W.w + 2)) / 2));
ck('2 wheel', 'and it keeps a margin either side', W.x >= 14, W.x);
ck('2 wheel', 'wheel fills >55% of the module area', (W.w*W.h)/(1400*1200) > 0.55,
   ((W.w*W.h)/(1400*1200)*100).toFixed(1) + '%');
ck('2 wheel', 'wheel IDENTICAL in ready/sow/action',
   JSON.stringify([W.x,W.y,W.w,W.h]) === JSON.stringify([wheels.sow.x,wheels.sow.y,wheels.sow.w,wheels.sow.h]) &&
   JSON.stringify([W.x,W.y,W.w,W.h]) === JSON.stringify([wheels.action.x,wheels.action.y,wheels.action.w,wheels.action.h]),
   [wheels.ready,wheels.sow,wheels.action].map(o=>`${o.x},${o.y},${o.w},${o.h}`).join(' / '));
ck('2 wheel', 'City region IDENTICAL in all three',
   [cities.sow, cities.action].every(c => c.x === cities.ready.x && c.y === cities.ready.y
     && c.w === cities.ready.w && c.h === cities.ready.h),
   [cities.ready,cities.sow,cities.action].map(o=>`${o.x},${o.y}`).join(' / '));
ck('2 wheel', 'duty cards IDENTICAL in all three',
   [cards.sow, cards.action].every(c => c.x === cards.ready.x && c.y === cards.ready.y),
   [cards.ready,cards.sow,cards.action].map(o=>`${o.x},${o.y}`).join(' / '));
ck('2 wheel', 'acolyte anchors IDENTICAL in all three',
   figs.ready === figs.sow && figs.ready === figs.action);

// ---------------------------------------------------------------------------------------------
// 3. NOTHING IDENTIFIES A DUTY SPACE ON THE WHEEL
// ---------------------------------------------------------------------------------------------
const onWheel = await p.evaluate(() => {
  const w = document.getElementById('wheelObj').getBoundingClientRect();
  const bad = [];
  document.querySelectorAll('#stage .obj').forEach(e => {
    if (e === document.getElementById('wheelObj')) return;
    const k = e.dataset.kind;
    if (k === 'figs') return;                       // acolytes are pieces, not identification
    const r = e.getBoundingClientRect();
    const over = !(r.right < w.left || r.left > w.right || r.bottom < w.top || r.top > w.bottom);
    if (over) bad.push(k + (e.dataset.id ? ':' + e.dataset.id : ''));
  });
  // Anything inside the wheel that is not editing chrome (its own name tag, its resize handles)
  // and not the wheel art itself would be identification of a duty space.
  const wob = document.getElementById('wheelObj');
  const content = [].slice.call(wob.children).filter(c =>
    !c.classList.contains('nm') && !c.classList.contains('h'));
  const names = Object.keys(S.duties).map(s => S.duties[s].name.toUpperCase());
  const wheelText = wob.innerText.toUpperCase();
  return {bad, keys: Object.keys(S.duties.clerical), hasLabel: 'label' in S.duties.clerical,
          wheelContent: content.map(c => c.tagName).join(','),
          namesOnWheel: names.filter(nm => wheelText.includes(nm))};
});
ck('3 wheel is bare', 'no label object survives on a duty', !onWheel.hasLabel, onWheel.keys.join(','));
ck('3 wheel is bare', 'duty keys are name/clock/actions/card/figures',
   onWheel.keys.join(',') === 'name,clock,actionA,actionB,card,figures', onWheel.keys.join(','));
ck('3 wheel is bare', 'nothing but acolytes overlaps the wheel in ACTION',
   onWheel.bad.filter(x => x !== 'city').length === 0, onWheel.bad.join(',') || 'none');
// An inline SVG's tagName is lowercase in an HTML document, an <img>'s is upper.
ck('3 wheel is bare', 'the wheel holds nothing but its own art',
   ['svg', 'IMG'].indexOf(onWheel.wheelContent) >= 0, onWheel.wheelContent);
ck('3 wheel is bare', 'no duty is named on the wheel', onWheel.namesOnWheel.length === 0,
   onWheel.namesOnWheel.join(',') || 'none');

// ---------------------------------------------------------------------------------------------
// 4. THE TOP RIBBON: EIGHT REFERENCE CARDS IN WHEEL ORDER
// ---------------------------------------------------------------------------------------------
const ribbon = await p.evaluate(() => {
  const cs = [].slice.call(document.querySelectorAll('.obj[data-kind=card]'));
  return cs.map(e => ({id: e.dataset.id, x: parseFloat(e.style.left), y: parseFloat(e.style.top),
                       w: parseFloat(e.style.width), h: parseFloat(e.style.height),
                       acts: [].slice.call(e.querySelectorAll('.act')).map(a => a.innerText.trim()),
                       seals: e.querySelectorAll('.act .seal').length}));
});
ck('4 ribbon', 'eight cards on screen', ribbon.length === 8, ribbon.length);
ck('4 ribbon', 'cards are in DUTY_ORDER', ribbon.map(c => c.id).join(',') === meta.order.join(','),
   ribbon.map(c => c.id).join(','));
ck('4 ribbon', 'cards are one row (same y)', new Set(ribbon.map(c => c.y)).size === 1,
   [...new Set(ribbon.map(c => c.y))].join(','));
ck('4 ribbon', 'cards are evenly pitched', new Set(ribbon.slice(1).map((c,i) => c.x - ribbon[i].x)).size === 1,
   [...new Set(ribbon.slice(1).map((c,i) => c.x - ribbon[i].x))].join(','));
ck('4 ribbon', 'the row fits the module', ribbon[0].x >= 0 && ribbon[7].x + ribbon[7].w <= 1400,
   ribbon[0].x + '..' + (ribbon[7].x + ribbon[7].w));
ck('4 ribbon', 'the row sits above the wheel', Math.max(...ribbon.map(c => c.y + c.h)) <= W.y,
   Math.max(...ribbon.map(c => c.y + c.h)) + ' vs ' + W.y);
ck('4 ribbon', 'every card shows two actions', ribbon.every(c => c.acts.length === 2),
   ribbon.map(c => c.acts.length).join(','));
ck('4 ribbon', 'every action carries a seal', ribbon.every(c => c.seals === 2),
   ribbon.map(c => c.seals).join(','));
ck('4 ribbon', 'no "OR" anywhere on a card',
   !ribbon.some(c => c.acts.join(' ').split(/\s+/).includes('OR')));

// ---------------------------------------------------------------------------------------------
// 5. THE STATUS LINE: ONE MESSAGE PER STATE
// ---------------------------------------------------------------------------------------------
const msgs = {};
for (const v of ['ready','sow','action']){
  await setView(v); await p.waitForTimeout(100);
  msgs[v] = await p.evaluate(() => document.querySelector('#statusObj .main').textContent.trim());
}
ck('5 status', 'READY message', msgs.ready === 'Pick up Acolytes or Hire Buildings', msgs.ready);
ck('5 status', 'SOW message counts down from in-hand', /^Choose the next Duty — \d+ Acolytes remaining$/.test(msgs.sow), msgs.sow);
ck('5 status', 'ACTION message', msgs.action === 'Select a Duty Action or take Tithe', msgs.action);
ck('5 status', 'three distinct messages', new Set(Object.values(msgs)).size === 3);
const sowN = await p.evaluate(() => { setView('sow'); S.inHand.count = 2; render();
  return document.querySelector('#statusObj .main').textContent.trim(); });
ck('5 status', '{n} is substituted, not typed', sowN.includes(' 2 Acolytes'), sowN);
await p.evaluate(() => { S.inHand.count = 4; render(); });
const sBox = await box('#statusObj');
ck('5 status', 'status band is above the ribbon', sBox.y + sBox.h <= ribbon[0].y, sBox.y + sBox.h + ' vs ' + ribbon[0].y);

// ---------------------------------------------------------------------------------------------
// 6. THE ACTION BAND: TWO ARTWORKS, TITHE, CITY
// ---------------------------------------------------------------------------------------------
await setView('action'); await p.waitForTimeout(120);
const band = await p.evaluate(() => {
  const g = s => { const e = document.querySelector(s); return e ? {
    x: parseFloat(e.style.left), y: parseFloat(e.style.top),
    w: parseFloat(e.style.width), h: parseFloat(e.style.height)} : null; };
  return {L: g('.obj[data-kind=art][data-id=left]'), Rt: g('.obj[data-kind=art][data-id=right]'),
          T: g('#titheObj'), C: g('#cityObj')};
});
ck('6 band', 'two artworks present in ACTION', !!band.L && !!band.Rt);
ck('6 band', 'artworks share a y and a height',
   band.L.y === band.Rt.y && band.L.h === band.Rt.h, band.L.y + '/' + band.Rt.y);
ck('6 band', 'artworks, Tithe and City share the band row',
   [band.Rt, band.T, band.C].every(o => o.y === band.L.y && o.h === band.L.h),
   [band.L,band.Rt,band.T,band.C].map(o => o.y + '+' + o.h).join(' '));
ck('6 band', 'the four do not overlap',
   band.L.x + band.L.w <= band.Rt.x && band.Rt.x + band.Rt.w <= band.T.x
     && band.T.x + band.T.w <= band.C.x,
   [band.L,band.Rt,band.T,band.C].map(o => o.x + '..' + (o.x+o.w)).join(' '));
ck('6 band', 'the band ends inside the module', band.C.x + band.C.w <= 1400, band.C.x + band.C.w);
ck('6 band', 'the band sits between ribbon and wheel',
   band.L.y >= ribbon[0].y + ribbon[0].h && band.L.y + band.L.h <= W.y,
   band.L.y + '..' + (band.L.y + band.L.h) + ' vs wheel ' + W.y);

// ---------------------------------------------------------------------------------------------
// 7. TITHE: ACTION ONLY, NEVER IN A PREVIEW
// ---------------------------------------------------------------------------------------------
const tithePresent = {};
for (const v of ['ready','sow','action']){
  await setView(v); await p.waitForTimeout(100);
  tithePresent[v] = await p.evaluate(() => !!document.getElementById('titheObj'));
}
ck('7 tithe', 'absent in READY', !tithePresent.ready);
ck('7 tithe', 'absent in SOWING', !tithePresent.sow);
ck('7 tithe', 'present in ACTION', tithePresent.action);
const titheBody = await p.evaluate(() => { setView('action'); render();
  const e = document.getElementById('titheObj');
  return {label: e.querySelector('.tl').textContent.trim(),
          rows: [].slice.call(e.querySelectorAll('.pr')).map(r =>
            [].slice.call(r.querySelectorAll('.res')).map(x => x.textContent.trim()))}; });
ck('7 tithe', 'label reads TAKE TITHE', /TAKE TITHE/i.test(titheBody.label), titheBody.label);
ck('7 tithe', 'resources make a 1-over-2 pyramid',
   titheBody.rows.length === 2 && titheBody.rows[0].length === 1 && titheBody.rows[1].length === 2,
   JSON.stringify(titheBody.rows));

// ---------------------------------------------------------------------------------------------
// 8. PREVIEW: OPEN, SWITCH, CLOSE -- AND NEVER A CHOICE
// ---------------------------------------------------------------------------------------------
await setView('ready'); await p.waitForTimeout(120);
const before = await p.evaluate(() => document.querySelectorAll('.obj[data-kind=art]').length);
ck('8 preview', 'no artwork before a card is clicked', before === 0, before);

await p.click('.obj[data-kind=card][data-id=clerical]'); await p.waitForTimeout(200);
let pv = await p.evaluate(() => ({
  n: document.querySelectorAll('.obj[data-kind=art]').length,
  badges: document.querySelectorAll('.obj[data-kind=art] .pv').length,
  choice: document.querySelectorAll('.obj[data-kind=art].choice').length,
  caps: [].slice.call(document.querySelectorAll('.obj[data-kind=art] .cap')).map(c => c.textContent.trim()),
  tithe: !!document.getElementById('titheObj'),
  marked: document.querySelectorAll('.obj[data-kind=card].previewing').length,
  duty: S.previewDuty, view: S.view}));
ck('8 preview', 'clicking a card opens both artworks', pv.n === 2, pv.n);
ck('8 preview', 'both are badged PREVIEW', pv.badges === 2, pv.badges);
ck('8 preview', 'a preview is NOT a choice', pv.choice === 0, pv.choice);
ck('8 preview', 'captions are that duty\'s two action names',
   pv.caps.join(' | ') === 'Gain Piety | Gain Coins', pv.caps.join(' | '));
ck('8 preview', 'TITHE NEVER APPEARS IN A PREVIEW', !pv.tithe);
ck('8 preview', 'the previewed card is marked', pv.marked === 1, pv.marked);
ck('8 preview', 'the view did not change', pv.view === 'ready', pv.view);

await p.click('.obj[data-kind=card][data-id=produce]'); await p.waitForTimeout(200);
pv = await p.evaluate(() => ({duty: S.previewDuty,
  caps: [].slice.call(document.querySelectorAll('.obj[data-kind=art] .cap')).map(c => c.textContent.trim()),
  marked: [].slice.call(document.querySelectorAll('.obj[data-kind=card].previewing')).map(e => e.dataset.id)}));
ck('8 preview', 'clicking another card switches the preview', pv.duty === 'produce', pv.duty);
ck('8 preview', 'captions follow the switch', pv.caps.join(' | ') === 'Gain Wheat | Gain Stone', pv.caps.join(' | '));
ck('8 preview', 'only one card is marked', pv.marked.join(',') === 'produce', pv.marked.join(','));

await p.click('.obj[data-kind=card][data-id=produce]'); await p.waitForTimeout(200);
let off = await p.evaluate(() => ({d: S.previewDuty, n: document.querySelectorAll('.obj[data-kind=art]').length}));
ck('8 preview', 'clicking the same card again closes it', !off.d && off.n === 0, off.d + '/' + off.n);

await p.click('.obj[data-kind=card][data-id=produce]'); await p.waitForTimeout(150);
// EMPTY MEANS EMPTY. A click on the wheel, the City or the artwork deliberately does not close a
// preview now, so the point is chosen and then checked to have nothing on it: in READY the strip
// between the right artwork and the City is clear, since Tithe is not on screen yet.
const emptyHit = await p.evaluate(() => {
  const st = document.getElementById('stage').getBoundingClientRect();
  const sc = st.width / 1400;
  const x = st.left + 890 * sc, y = st.top + 330 * sc;
  const el = document.elementFromPoint(x, y);
  return {x, y, onObject: !!(el && el.closest && el.closest('.obj')),
          hit: el ? (el.id || el.className || el.tagName) : null};
});
ck('8 preview', 'the point chosen for an empty click really is empty', !emptyHit.onObject,
   String(emptyHit.hit));
await p.mouse.click(emptyHit.x, emptyHit.y); await p.waitForTimeout(200);
off = await p.evaluate(() => ({d: S.previewDuty, n: document.querySelectorAll('.obj[data-kind=art]').length}));
ck('8 preview', 'clicking empty stage closes it', !off.d && off.n === 0, off.d + '/' + off.n);

// preview works while sowing too, and switching to ACTION drops it
await setView('sow'); await p.waitForTimeout(100);
await p.click('.obj[data-kind=card][data-id=taxation]'); await p.waitForTimeout(200);
const sowPv = await p.evaluate(() => ({n: document.querySelectorAll('.obj[data-kind=art]').length,
  badges: document.querySelectorAll('.obj[data-kind=art] .pv').length,
  tithe: !!document.getElementById('titheObj')}));
ck('8 preview', 'preview works while SOWING', sowPv.n === 2 && sowPv.badges === 2, sowPv.n + '/' + sowPv.badges);
ck('8 preview', 'still no Tithe while previewing in SOWING', !sowPv.tithe);

await setView('action'); await p.waitForTimeout(150);
const inAct = await p.evaluate(() => ({
  badges: document.querySelectorAll('.obj[data-kind=art] .pv').length,
  choice: document.querySelectorAll('.obj[data-kind=art].choice').length,
  caps: [].slice.call(document.querySelectorAll('.obj[data-kind=art] .cap')).map(c => c.textContent.trim()),
  reached: [].slice.call(document.querySelectorAll('.obj[data-kind=card].reached')).map(e => e.dataset.id),
  tithe: !!document.getElementById('titheObj')}));
ck('8 preview', 'ACTION shows no PREVIEW badge', inAct.badges === 0, inAct.badges);
ck('8 preview', 'ACTION artworks read as choices', inAct.choice === 2, inAct.choice);
ck('8 preview', 'ACTION shows the reached duty, not the previewed one',
   inAct.caps.join(' | ') === 'Gain Piety | Gain Coins', inAct.caps.join(' | '));
ck('8 preview', 'the reached card is marked reached', inAct.reached.join(',') === 'clerical', inAct.reached.join(','));
ck('8 preview', 'Tithe is back in ACTION', inAct.tithe);
const clickAct = await p.evaluate(() => { const c = document.querySelector('.obj[data-kind=card][data-id=produce]');
  c.dispatchEvent(new PointerEvent('pointerdown', {bubbles:true, clientX:0, clientY:0}));
  return S.previewDuty; });
ck('8 preview', 'cards do not preview in ACTION', !clickAct, String(clickAct));
// Leaving a state drops what was open in it, and ACTION ignores a preview set any other way --
// two independent guards, so both are pinned rather than one standing in for the other.
const carried = await p.evaluate(() => {
  setView('ready'); togglePreview('give_alms'); const opened = S.previewDuty;
  setView('sow');   const afterSwitch = S.previewDuty;
  setView('action'); S.previewDuty = 'give_alms'; render();
  return {opened, afterSwitch,
          caps: [].slice.call(document.querySelectorAll('.obj[data-kind=art] .cap'))
                  .map(c => c.textContent.trim())};
});
ck('8 preview', 'changing the view drops an open preview',
   carried.opened === 'give_alms' && carried.afterSwitch === null,
   carried.opened + ' -> ' + carried.afterSwitch);
ck('8 preview', 'ACTION ignores a preview set behind its back',
   carried.caps.join(' | ') === 'Gain Piety | Gain Coins', carried.caps.join(' | '));
await p.evaluate(() => { S.previewDuty = null; setView('action'); });

// ---------------------------------------------------------------------------------------------
// 9. THE REACHED-DUTY HIGHLIGHT
// ---------------------------------------------------------------------------------------------
const hl = await p.evaluate(() => {
  const h = document.querySelector('.hl');
  if (!h) return null;
  const w = document.getElementById('wheelObj'), f = document.querySelector('.obj[data-kind=figs][data-id=clerical]');
  return {z: +getComputedStyle(h).zIndex, wz: +getComputedStyle(w).zIndex, fz: +getComputedStyle(f).zIndex,
          x: parseFloat(h.style.left), y: parseFloat(h.style.top),
          fx: parseFloat(f.style.left), fy: parseFloat(f.style.top),
          wd: parseFloat(h.style.width), ht: parseFloat(h.style.height)};
});
ck('9 highlight', 'a highlight exists in ACTION', !!hl);
ck('9 highlight', 'it is drawn ABOVE the wheel', hl && hl.z > hl.wz, hl && (hl.z + ' vs ' + hl.wz));
ck('9 highlight', 'it is drawn BELOW the acolytes', hl && hl.z < hl.fz, hl && (hl.z + ' vs ' + hl.fz));
ck('9 highlight', 'it is centred on the reached duty\'s anchor',
   hl && near(hl.x + hl.wd/2, hl.fx + 8, 2), hl && ((hl.x + hl.wd/2) + ' vs ' + (hl.fx + 8)));
const hlOthers = await p.evaluate(() => document.querySelectorAll('.hl').length);
ck('9 highlight', 'exactly one highlight', hlOthers === 1, hlOthers);

// CAN IT ACTUALLY BE SEEN? This has now been got wrong twice in opposite directions -- pale gold
// on the drawing's cream parchment, then deep oxblood once the lab's palette turned the faces
// slate -- and both times the highlight was correctly sized, correctly placed and invisible.
// So the contrast is computed from what is drawn rather than judged: the highlight colour
// composited over the face's own fill at the highlight's own opacity.
const seen = await p.evaluate(() => {
  const H = S.display.highlight;
  const face = getComputedStyle(document.querySelector('#wheelObj svg #faces path')).fill;
  const rgb = s => s.trim().startsWith('#')
    ? [1, 3, 5].map(i => parseInt(s.slice(i, i + 2), 16))
    : s.match(/\d+/g).slice(0, 3).map(Number);
  const f = rgb(face), h = rgb(H.colour), a = H.opacity;
  const over = f.map((c, i) => a * h[i] + (1 - a) * c);
  const lum = c => { const [r, g, b] = c.map(v => v / 255); 
    return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  const lo = Math.min(lum(over), lum(f)), hi = Math.max(lum(over), lum(f));
  return {face, colour: H.colour, opacity: a, ratio: (hi + 0.05) / (lo + 0.05)};
});
ck('9 highlight', 'it can be told apart from the face it sits on',
   seen.ratio >= 1.5,
   seen.colour + ' at ' + seen.opacity + ' over ' + seen.face + ' = ' + seen.ratio.toFixed(2));
for (const v of ['ready','sow']){
  await setView(v); await p.waitForTimeout(100);
  const k = await p.evaluate(() => document.querySelectorAll('.hl').length);
  ck('9 highlight', 'no highlight in ' + v.toUpperCase(), k === 0, k);
}

// ---------------------------------------------------------------------------------------------
// 10. THE CITY IS TWO JOBS IN ONE REGION
// ---------------------------------------------------------------------------------------------
const cityStates = {};
for (const v of ['ready','sow','action']){
  await setView(v); await p.waitForTimeout(100);
  cityStates[v] = await p.evaluate(() => {
    const e = document.getElementById('cityObj');
    return {label: e.querySelector('.cl').textContent.trim(),
            figs: e.querySelectorAll('.fig').length,
            counts: [].slice.call(e.querySelectorAll('.ct')).map(c => c.textContent.trim()),
            hand: e.classList.contains('hand')};
  });
}
ck('10 city', 'READY shows THE CITY', /CITY/i.test(cityStates.ready.label), cityStates.ready.label);
ck('10 city', 'READY shows one acolyte per seat', cityStates.ready.figs === 4, cityStates.ready.figs);
ck('10 city', 'counts are inside the figures', cityStates.ready.counts.length === 4, cityStates.ready.counts.join(','));
ck('10 city', 'SOWING shows ACOLYTES IN HAND', /IN HAND/i.test(cityStates.sow.label), cityStates.sow.label);
ck('10 city', 'SOWING shows one figure', cityStates.sow.figs === 1, cityStates.sow.figs);
ck('10 city', 'the in-hand figure carries the count',
   cityStates.sow.counts.join(',') === String(4), cityStates.sow.counts.join(','));
ck('10 city', 'ACTION is back to the City', /CITY/i.test(cityStates.action.label), cityStates.action.label);

// ---------------------------------------------------------------------------------------------
// 11. ACOLYTES ON THE WHEEL STAY ON THE WHEEL
// ---------------------------------------------------------------------------------------------
const fig = await p.evaluate(() => {
  const w = document.getElementById('wheelObj').getBoundingClientRect();
  const band = document.querySelector('#cityObj').getBoundingClientRect();
  let worst = -1e9, name = '';
  document.querySelectorAll('.obj[data-kind=figs] .fig').forEach(a => {
    const r = a.getBoundingClientRect();
    if (w.top - r.top > worst){ worst = w.top - r.top; name = a.className; }
  });
  return {over: Math.round(worst), bandBottom: Math.round(band.bottom), wheelTop: Math.round(w.top),
          n: document.querySelectorAll('.obj[data-kind=figs] .fig').length,
          anchors: document.querySelectorAll('.obj[data-kind=figs]').length};
});
ck('11 acolytes', 'eight anchors, one per duty', fig.anchors === 8, fig.anchors);
ck('11 acolytes', 'acolytes are on the wheel', fig.n > 0, fig.n);
// THE RING, MEASURED AGAINST THE REAL FACES. Until the wheel was a drawing this could only be
// eyeballed; now every anchor can be mapped into the asset's own user space and handed to
// isPointInFill, so "is this row standing on its own duty's face" has an answer. Both ends of
// the row are asked, not just the anchor, because a four-figure row is 222px wide.
const ring = await p.evaluate(() => {
  const svg = document.querySelector('#wheelObj svg'), vb = svg.viewBox.baseVal, w = S.wheel;
  const faces = [].slice.call(svg.querySelectorAll('#faces path'));
  const at = (x, y) => { const q = svg.createSVGPoint();
    q.x = (x - w.x) / w.width * vb.width; q.y = (y - w.y) / w.height * vb.height;
    return faces.filter(el => el.isPointInFill(q)).map(el => el.id); };
  return DUTY_ORDER.map(slug => {
    const f = S.duties[slug].figures, half = (f.count - 1) / 2 * f.spacing;
    return {slug, on: at(f.x, f.y), left: at(f.x - half, f.y), right: at(f.x + half, f.y)};
  });
});
ck('11 acolytes', 'every anchor stands on exactly one face',
   ring.every(r => r.on.length === 1),
   ring.filter(r => r.on.length !== 1).map(r => r.slug + ':' + r.on.join('+')).join(' ') || 'all');
ck('11 acolytes', 'no two duties share a face',
   new Set(ring.map(r => r.on[0])).size === 8, ring.map(r => r.on[0]).join(','));
ck('11 acolytes', 'the whole row stays on that face, not just the anchor',
   ring.every(r => r.on.length === 1 && r.left[0] === r.on[0] && r.right[0] === r.on[0]),
   ring.filter(r => r.left[0] !== r.on[0] || r.right[0] !== r.on[0])
       .map(r => r.slug).join(',') || 'all eight');
ck('11 acolytes', 'the faces are named by position, never by duty',
   ring.every(r => /^(north|south|east|west|north_east|north_west|south_east|south_west)$/
                     .test(r.on[0])),
   ring.map(r => r.on[0]).join(','));

ck('11 acolytes', 'the tallest overhang clears the action band',
   fig.wheelTop - fig.over >= fig.bandBottom,
   'top ' + (fig.wheelTop - fig.over) + ' vs band bottom ' + fig.bandBottom);

// ---------------------------------------------------------------------------------------------
// 12. EDIT MODE STILL COMPOSES
// ---------------------------------------------------------------------------------------------
await clean(false); await setView('ready'); await p.waitForTimeout(150);
const edit = await p.evaluate(() => ({
  ghosts: document.querySelectorAll('.obj.ghost').length,
  handles: document.querySelectorAll('.obj .h').length,
  names: document.querySelectorAll('.obj .nm').length}));
ck('12 edit', 'edit mode shows handles', edit.handles > 0, edit.handles);
ck('12 edit', 'edit mode names the objects', edit.names > 0, edit.names);
const ghostAct = await p.evaluate(() => { setView('ready'); S.showGhosts = true; render();
  return {tithe: document.querySelectorAll('.obj[data-kind=tithe].ghost').length}; });
ck('12 edit', 'an out-of-state object can be composed as a ghost', ghostAct.tithe === 1, ghostAct.tithe);
const cleanGhost = await p.evaluate(() => { document.getElementById('bMode').click();
  return document.querySelectorAll('.obj.ghost').length; });
ck('12 edit', 'Clean Preview never contains a ghost', cleanGhost === 0, cleanGhost);
await clean(false);
// drag the wheel and confirm the acolytes follow it
const follow = await p.evaluate(() => {
  const b4 = JSON.parse(JSON.stringify(S.duties.clerical.figures));   // a COPY, not the object
  S.wheel.x += 30; S.wheel.y += 20; syncAttached(); relayout(); render();
  const af = S.duties.clerical.figures;
  return {uvKept: Math.abs(af.u - b4.u) < 1e-9 && Math.abs(af.v - b4.v) < 1e-9,
          moved: af.x - b4.x === 30 && af.y - b4.y === 20,
          got: (af.x - b4.x) + ',' + (af.y - b4.y)};
});
ck('12 edit', 'acolytes are wheel-relative: u/v held', follow.uvKept);
ck('12 edit', 'acolytes are wheel-relative: x/y re-derived', follow.moved, follow.got);
await p.evaluate(() => { S.wheel.x -= 30; S.wheel.y -= 20; syncAttached(); relayout(); render(); });

// ---------------------------------------------------------------------------------------------
// 13. THE TWO EXPORTS
// ---------------------------------------------------------------------------------------------
const gl = await p.evaluate(() => { try { return gameLayout(); }
                                    catch (e){ return {threw: e.message}; } });
ck('13 export', 'gameLayout() does not throw', !gl.threw, gl.threw || 'ok');
ck('13 export', 'game layout is version 4', gl.version === 4, gl.version);
if (gl.threw) { R.push('     (remaining export checks skipped: gameLayout threw)'); }
else {
ck('13 export', 'game layout carries the canvas', gl.canvas.width === 1400 && gl.canvas.height === 1200);
ck('13 export', 'game layout has eight duties', Object.keys(gl.duties).length === 8);
ck('13 export', 'an action exports wording, not a box',
   Object.keys(gl.duties.clerical.actionA).join(',') === 'name,shortLabel',
   Object.keys(gl.duties.clerical.actionA).join(','));
ck('13 export', 'two artwork slots own the geometry',
   Object.keys(gl.artwork).join(',') === 'left,right'
     && ['x','y','width','height','slot'].every(k => k in gl.artwork.left),
   Object.keys(gl.artwork.left).join(','));
ck('13 export', 'no editor settings leak into the game layout',
   !('mode' in gl) && !('guides' in gl) && !('zoom' in gl) && !('view' in gl)
     && !('previewDuty' in gl) && !('display' in gl),
   Object.keys(gl).join(','));
ck('13 export', 'no image bytes in the game layout', !JSON.stringify(gl).includes('data:'));
// THE PRESENTATION COMES TOO, and the phase does not. `visible` is the designer's switch for
// whether the object is part of the layout at all; WHEN Tithe is on screen is a phase the game
// already knows and nothing here says.
ck('13 export', 'Tithe carries its label and resources', 
   gl.tithe.label === 'TAKE TITHE' && gl.tithe.resources.length === 3
     && !('view' in gl.tithe) && !('byView' in gl.tithe) && !('states' in gl.tithe),
   Object.keys(gl.tithe).join(','));
ck('13 export', 'the City carries its label', typeof gl.city.label === 'string',
   Object.keys(gl.city).join(','));
ck('13 export', 'neither carries this session\'s counts',
   !('counts' in gl.city) && !('shown' in gl.city) && !('image' in gl.tithe),
   Object.keys(gl.city).join(','));
}
const ls = await p.evaluate(() => ({no: labSession(false), yes: labSession(true)}));
ck('13 export', 'lab session is version 4', ls.no.version === 4, ls.no.version);
ck('13 export', 'lab session without images carries none', Object.keys(ls.no.images).length === 0);
ck('13 export', 'lab session round-trips through validate',
   await p.evaluate(() => { try { return validate(gameLayout()); } catch(e){ return e.message; } }) === true);

// ---------------------------------------------------------------------------------------------
// 14. MIGRATION FROM V3.1
// ---------------------------------------------------------------------------------------------
// Through importSession, which is the path a real file takes: migrate strips the geometry that
// has no V4 equivalent and deepMerge supplies the V4 defaults, so only the live state tells the
// truth about what an imported session becomes.
const fresh = await p.evaluate(() => Object.keys(DEFAULT_STATE.duties.clerical).sort().join(','));
const ringOf = () => p.evaluate(() => {
  const xs = DUTY_ORDER.map(s => S.duties[s].figures.x), ys = DUTY_ORDER.map(s => S.duties[s].figures.y);
  return {w: Math.max(...xs) - Math.min(...xs), h: Math.max(...ys) - Math.min(...ys)};
});
const freshRing = await ringOf();
const v3 = JSON.parse(fs.readFileSync(path.join(FIXTURES, 'v3_session.json'), 'utf8'));
const mig = await p.evaluate(d => {
  importSession(d);
  const m = S;
  return {ver: m.version, duty: Object.keys(m.duties.clerical).sort(),
          name: m.duties.clerical.actionA.name,
          wheel: [m.wheel.x, m.wheel.y, m.wheel.width, m.wheel.height],
          card: [m.duties.clerical.card.x, m.duties.clerical.card.y],
          hasSummary: 'summary' in m.duties.clerical, hasLabel: 'label' in m.duties.clerical,
          hasTitheLabelObj: 'titheLabel' in m.duties.clerical,
          seats: m.duties.clerical.figures.seats, count: m.duties.clerical.figures.count,
          cards: document.querySelectorAll('.obj[data-kind=card]').length,
          oob: document.querySelectorAll('.obj.oob').length,
          ringW: Math.max.apply(null, DUTY_ORDER.map(s => m.duties[s].figures.x))
               - Math.min.apply(null, DUTY_ORDER.map(s => m.duties[s].figures.x)),
          ringH: Math.max.apply(null, DUTY_ORDER.map(s => m.duties[s].figures.y))
               - Math.min.apply(null, DUTY_ORDER.map(s => m.duties[s].figures.y)),
          inHand: Object.keys(m.inHand).sort().join(',')};
}, v3);
ck('14 migrate', 'a V3.1 session comes out as V4', mig.ver === 4, mig.ver);
ck('14 migrate', 'wheel geometry is this build\'s wheel, not the V3 one',
   JSON.stringify(mig.wheel) === JSON.stringify([W.x, W.y, W.w, W.h]), mig.wheel.join(','));
ck('14 migrate', 'cards land in the ribbon, not where summaries were',
   mig.card[1] === ribbon[0].y, mig.card.join(','));
ck('14 migrate', 'the retired objects are gone',
   !mig.hasSummary && !mig.hasLabel && !mig.hasTitheLabelObj,
   [mig.hasSummary, mig.hasLabel, mig.hasTitheLabelObj].join(','));
ck('14 migrate', 'duty keys match a fresh V4 duty', mig.duty.join(',') === fresh,
   mig.duty.join(',') + ' vs ' + fresh);
ck('14 migrate', 'the imported session renders eight cards', mig.cards === 8, mig.cards);
ck('14 migrate', 'nothing imported lands outside the module', mig.oob === 0, mig.oob);
// The V3 ring was a fraction of a 950px wheel. Kept as u/v it would redraw at 1372px as a ring
// of the wrong size, so the test is the span, not the presence of the anchors.
ck('14 migrate', 'the acolyte ring is re-derived at the V4 wheel\'s scale',
   Math.abs(mig.ringW - freshRing.w) <= 2 && Math.abs(mig.ringH - freshRing.h) <= 2,
   mig.ringW + 'x' + mig.ringH + ' vs fresh ' + freshRing.w + 'x' + freshRing.h);
// With the anchors attached, the default u/v re-derives the ring whatever x/y said. With them
// FREE, x/y is all there is -- so that is the case that proves migration rewrote them, and the
// case a designer who turned the switch off would actually hit.
const freeRing = await p.evaluate(d => {
  const raw = JSON.parse(JSON.stringify(d.state || d));
  raw.attachToWheel = false;
  importSession(raw);
  const xs = DUTY_ORDER.map(s => S.duties[s].figures.x), ys = DUTY_ORDER.map(s => S.duties[s].figures.y);
  return {w: Math.max(...xs) - Math.min(...xs), h: Math.max(...ys) - Math.min(...ys),
          attach: S.attachToWheel};
}, v3);
ck('14 migrate', 'and re-derived even with the anchors free',
   freeRing.attach === false && Math.abs(freeRing.w - freshRing.w) <= 2
     && Math.abs(freeRing.h - freshRing.h) <= 2,
   freeRing.w + 'x' + freeRing.h + ' vs fresh ' + freshRing.w + 'x' + freshRing.h);
ck('14 migrate', 'the WORDING survives', typeof mig.name === 'string' && mig.name.length > 0, mig.name);
ck('14 migrate', 'the seats and counts survive', Array.isArray(mig.seats) && mig.count > 0,
   mig.count + ' ' + JSON.stringify(mig.seats));
ck('14 migrate', 'in-hand collapses to count/seat/label', mig.inHand === 'count,label,seat', mig.inHand);
const v2 = JSON.parse(fs.readFileSync(path.join(FIXTURES, 'v2_session.json'), 'utf8'));
const mig2 = await p.evaluate(d => { importSession(d);
  return {ver: S.version, w: S.wheel.width, keys: Object.keys(S.duties.clerical).sort().join(','),
          cards: document.querySelectorAll('.obj[data-kind=card]').length,
          oob: document.querySelectorAll('.obj.oob').length}; }, v2);
ck('14 migrate', 'a V2 session also arrives at V4',
   mig2.ver === 4 && mig2.keys === fresh && mig2.w === W.w, mig2.ver + ' ' + mig2.w + ' ' + mig2.keys);
ck('14 migrate', 'and lands inside the module too', mig2.cards === 8 && mig2.oob === 0,
   mig2.cards + '/' + mig2.oob);
await p.evaluate(() => { localStorage.clear(); });
await p.reload(); await p.waitForTimeout(400);

// ---------------------------------------------------------------------------------------------
// 15. GEOMETRY-ONLY PERSISTENCE, UNDO, VIEW IS NOT UNDONE
// ---------------------------------------------------------------------------------------------
// A state with NO images cannot prove anything about stripping them, so one goes in first.
const store = await p.evaluate(() => {
  const px = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==';
  S.duties.clerical.actionA.scenic = putImage(px);
  S.duties.clerical.actionA.scenicName = 'probe.png';
  save();
  const t = localStorage.getItem(STORE_KEY) || '';
  return {len: t.length, data: t.includes('data:'), has: !!t,
          live: JSON.stringify(S).includes('data:'),
          drawn: (function(){ setView('action'); render();
            return document.querySelectorAll('.obj[data-kind=art] img').length; })()};
});
ck('15 persist', 'something is saved', store.has);
ck('15 persist', 'the probe image really is in the page', store.drawn > 0, store.drawn);
ck('15 persist', 'the pool keeps bytes out of the state itself', !store.live);
ck('15 persist', 'no image bytes reach localStorage', !store.data, store.len + ' chars');
const undo = await p.evaluate(() => {
  setView('ready'); record();
  const x0 = S.wheel.x;
  S.wheel.x = x0 + 77; record();
  setView('action');
  stepHistory(-1);
  return {x: S.wheel.x, x0: x0, view: S.view};
});
ck('15 persist', 'undo restores geometry', undo.x === undo.x0, undo.x + ' vs ' + undo.x0);
ck('15 persist', 'undo does NOT restore the view state', undo.view === 'action', undo.view);
await p.evaluate(() => { stepHistory(1); setView('ready'); });

// ---------------------------------------------------------------------------------------------
// 16. NO ERRORS, AND THE F KEY STILL GOES FULL SCREEN
// ---------------------------------------------------------------------------------------------
// THE CLASS FOLLOWS THE BROWSER, so the assertion is on setFull, and separately on F reaching it.
const full = await p.evaluate(() => {
  const a = document.body.classList.contains('full');
  setFull(true);  const b = document.body.classList.contains('full');
  setFull(false); const c = document.body.classList.contains('full');
  return {a, b, c};
});
ck('16 chrome', 'full screen hides the chrome', full.a === false && full.b === true,
   full.a + '/' + full.b);
ck('16 chrome', 'and gives it back', full.c === false, full.c);
const fKey = await p.evaluate(() => {
  let called = 0;
  const real = window.toggleFull;
  window.toggleFull = function(){ called++; };
  document.body.dispatchEvent(new KeyboardEvent('keydown', {key:'f', bubbles:true}));
  document.body.dispatchEvent(new KeyboardEvent('keydown', {key:'F', bubbles:true}));
  window.toggleFull = real;
  return called;
});
ck('16 chrome', 'the F key reaches it, upper and lower case', fKey === 2, fKey);
const zoom = await p.evaluate(() => {
  const out = {};
  ['fit',50,75,100,125,150].forEach(z => {
    setZoom(z);
    const m = getComputedStyle(document.getElementById('stage')).transform;
    out[z] = m === 'none' ? 1 : +(new DOMMatrix(m).a).toFixed(3);
  });
  setZoom(100);
  return out;
});
ck('16 chrome', 'each zoom step scales the stage by its own factor',
   zoom['50'] === 0.5 && zoom['75'] === 0.75 && zoom['100'] === 1
     && zoom['125'] === 1.25 && zoom['150'] === 1.5,
   JSON.stringify(zoom));
ck('16 chrome', 'FIT scales to something that fits', zoom.fit > 0 && zoom.fit <= 1, zoom.fit);
const zoomGeom = await p.evaluate(() => {
  setZoom(150); const a = JSON.stringify(gameLayout());
  setZoom('fit'); const b = JSON.stringify(gameLayout());
  setZoom(100); return a === b;
});
ck('16 chrome', 'zoom is display only: the export is identical at any zoom', zoomGeom);
ck('16 chrome', 'no page or console errors in the whole run', errs.length === 0, errs.slice(0,3).join(' | '));

} catch (e) {
  ck('16 chrome', 'the run completed without throwing', false,
     (e && e.message ? e.message : String(e)).split('\n')[0]);
}

// ---------------------------------------------------------------------------------------------
await b.close();
const out = R.join('\n') + `\n\n${n - fail}/${n} passed, ${fail} failed.\n`;
if (!process.argv[2]) fs.writeFileSync(path.join(OUT, 'accept4.txt'), out);
console.log(process.argv[2] ? out.split('\n').filter(l => l.startsWith('FAIL')).concat(out.trim().split('\n').pop()).join('\n') : out);
process.exit(fail ? 1 : 0);
