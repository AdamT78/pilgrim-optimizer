// THE TEN PRE-COMMIT ACCEPTANCE TESTS, in the brief's own order and wording.
//
// Separate from accept4.mjs on purpose: that suite guards the V4 design as a whole and this one
// answers a specific list, so a failure here names the numbered test that failed rather than
// something adjacent to it. Both run before the commit.
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
function ck(test, name, ok, detail){
  n++; if (!ok) fail++;
  R.push((ok ? 'PASS ' : 'FAIL ') + test + ' :: ' + name + (detail === undefined ? '' : '   [' + detail + ']'));
}
const near = (a, t, e = 1) => Math.abs(a - t) <= e;
const clean = on => p.evaluate(o => { if (document.body.classList.contains('clean') !== o)
  document.getElementById('bMode').click(); }, on);
const setView = v => p.evaluate(x => { setView(x); }, v);
const wheel = () => p.evaluate(() => ({
  x: S.wheel.x, y: S.wheel.y, w: S.wheel.width, h: S.wheel.height,
  ratio: S.wheel.naturalRatio, src: S.wheel.ratioSource,
  assetRatio: S.wheel.assetRatio, image: S.wheel.image, name: S.wheel.imageName,
  anchors: DUTY_ORDER.map(s => [S.duties[s].figures.x, S.duties[s].figures.y,
                                S.duties[s].figures.u, S.duties[s].figures.v]),
}));

// =============================================================================================
// TEST 1 — DEFAULT WHEEL
// =============================================================================================
let W = await wheel();
ck('TEST 1', 'x = 14', W.x === 14, W.x);
ck('TEST 1', 'y = 438', W.y === 438, W.y);
ck('TEST 1', 'w = 1372', W.w === 1372, W.w);
ck('TEST 1', 'h = 727', W.h === 727, W.h);
ck('TEST 1', 'ratio ~ 0.5299', near(W.ratio, 0.5299, 0.0005), W.ratio);
ck('TEST 1', 'bottom = 1165', W.y + W.h === 1165, W.y + W.h);
const oob = await p.evaluate(() => document.querySelectorAll('.obj.oob').length);
ck('TEST 1', 'no out-of-bounds warning', oob === 0, oob);

// =============================================================================================
// TEST 2 — BUILT-IN SVG
// =============================================================================================
const built = await p.evaluate(() => {
  const svg = document.querySelector('#wheelObj svg'), vb = svg && svg.viewBox.baseVal;
  const r = svg && svg.getBoundingClientRect();
  const wr = document.getElementById('wheelObj').getBoundingClientRect();
  const g = document.querySelector('#wheelObj [id="ground"]');
  return {vbw: vb && vb.width, vbh: vb && vb.height,
          drawn: r && [r.width, r.height], box: [wr.width, wr.height],
          par: svg && (svg.getAttribute('preserveAspectRatio') || 'default'),
          hasGround: !!g, groundShown: !!g && getComputedStyle(g).display !== 'none'};
});
ck('TEST 2', 'viewBox is 1000 x 529.9', built.vbw === 1000 && near(built.vbh, 529.9, 0.01),
   built.vbw + ' x ' + built.vbh);
ck('TEST 2', 'the logical ratio is 0.5299', near(built.vbh / built.vbw, 0.5299, 0.0005),
   (built.vbh / built.vbw).toFixed(4));
// NO DISTORTION means the drawing is drawn at its own proportions. The element fills the box,
// and the box is at the same ratio, so the two agree -- which is the claim worth checking.
ck('TEST 2', 'no distortion: the drawn box carries the asset ratio',
   near(built.drawn[1] / built.drawn[0], built.vbh / built.vbw, 0.002),
   built.drawn.map(Math.round).join(' x '));
ck('TEST 2', 'it fills the wheel box', near(built.drawn[0], built.box[0], 1),
   built.drawn.map(Math.round).join('x') + ' in ' + built.box.map(Math.round).join('x'));
ck('TEST 2', 'no preserveAspectRatio="none" anywhere', built.par !== 'none', built.par);
const ground = await p.evaluate(() => {
  const out = {off: getComputedStyle(document.querySelector('#wheelObj [id="ground"]')).display};
  S.wheel.ground = true; render();
  out.on = getComputedStyle(document.querySelector('#wheelObj [id="ground"]')).display;
  S.wheel.ground = false; render();
  out.back = getComputedStyle(document.querySelector('#wheelObj [id="ground"]')).display;
  return out;
});
ck('TEST 2', 'the ground rectangle still toggles',
   ground.off === 'none' && ground.on !== 'none' && ground.back === 'none',
   [ground.off, ground.on, ground.back].join(' / '));

// =============================================================================================
// TEST 3 — LOAD MATCHING SVG
// =============================================================================================
const before = await wheel();
await p.evaluate(() => { sel = {kind: 'wheel', id: null}; inspector(); });
await p.setInputFiles('#fWheel', A + 'probe_wheel_match.svg');
await p.waitForTimeout(350);
let after = await wheel();
ck('TEST 3', 'the wheel geometry does not change',
   JSON.stringify([after.x, after.y, after.w, after.h])
     === JSON.stringify([before.x, before.y, before.w, before.h]),
   [after.x, after.y, after.w, after.h].join(','));
ck('TEST 3', 'the layout ratio does not change', after.ratio === before.ratio, after.ratio);
ck('TEST 3', 'the acolyte anchors do not move',
   JSON.stringify(after.anchors) === JSON.stringify(before.anchors));
ck('TEST 3', 'the asset was actually loaded', !!after.image && /match/.test(after.name), after.name);
ck('TEST 3', "the asset's own ratio is recorded", near(after.assetRatio, 0.5299, 0.0005),
   after.assetRatio);
const say3 = await p.evaluate(() => ({
  line: document.getElementById('status').textContent,
  bad: document.getElementById('status').className,
  hint: document.getElementById('insp').innerText}));
ck('TEST 3', 'the tool reports that the asset ratio matches',
   /match/i.test(say3.line) && /match/i.test(say3.hint), say3.line.trim());

// =============================================================================================
// TEST 4 — LOAD WRONG-RATIO SVG
// =============================================================================================
await p.setInputFiles('#fWheel', A + 'probe_wheel_wrong.svg');
await p.waitForTimeout(350);
after = await wheel();
ck('TEST 4', 'the wheel remains 1372 x 727', after.w === 1372 && after.h === 727,
   after.w + ' x ' + after.h);
ck('TEST 4', 'and stays at 14, 438', after.x === 14 && after.y === 438, after.x + ',' + after.y);
ck('TEST 4', 'the layout ratio is untouched', near(after.ratio, 0.5299, 0.0005), after.ratio);
ck('TEST 4', 'the acolytes do not move',
   JSON.stringify(after.anchors) === JSON.stringify(before.anchors));
const say4 = await p.evaluate(() => ({
  line: document.getElementById('status').textContent,
  warned: /warn|bad/.test(document.getElementById('status').className),
  hint: document.getElementById('insp').innerText,
  fit: (function(){ const i = document.querySelector('#wheelObj img');
    return i ? getComputedStyle(i).objectFit : null; })(),
  drawn: (function(){ const i = document.querySelector('#wheelObj img');
    return i ? [i.getBoundingClientRect().width, i.getBoundingClientRect().height] : null; })()}));
ck('TEST 4', 'the tool warns that the asset does not match',
   /differs/i.test(say4.line) && /differs/i.test(say4.hint), say4.line.trim());
ck('TEST 4', 'the asset is contained rather than stretched', say4.fit === 'contain', say4.fit);
ck('TEST 4', 'the drawn asset is an <img>, not the built-in svg',
   !!say4.drawn, say4.drawn && say4.drawn.map(Math.round).join('x'));

// =============================================================================================
// TEST 5 — RESET WHEEL WITH EXTERNAL ASSET LOADED
// =============================================================================================
await p.evaluate(() => {
  S.wheel.x = 200; S.wheel.y = 600; S.wheel.width = 800;
  S.wheel.height = Math.round(800 * S.wheel.naturalRatio);
  syncAttached(); render();
  resetOne('wheel', null);
});
await p.waitForTimeout(200);
after = await wheel();
ck('TEST 5', 'x = 14', after.x === 14, after.x);
ck('TEST 5', 'y = 438', after.y === 438, after.y);
ck('TEST 5', 'w = 1372', after.w === 1372, after.w);
ck('TEST 5', 'h = 727', after.h === 727, after.h);
ck('TEST 5', 'the external artwork is still loaded', !!after.image && /wrong/.test(after.name),
   after.name);
ck('TEST 5', 'the ratio is 0.5299', near(after.ratio, 0.5299, 0.0005), after.ratio);
ck('TEST 5', 'and it is the layout\'s, not the asset\'s',
   after.src === 'builtin' && !near(after.ratio, after.assetRatio, 0.001),
   after.src + ' · asset ' + after.assetRatio);
// Clearing goes back to the built-in drawing.
const cleared = await p.evaluate(() => {
  S.wheel.image = null; S.wheel.imageName = null;
  S.wheel.assetRatio = null; S.wheel.assetRatioSource = null;
  render();
  return {svg: !!document.querySelector('#wheelObj svg'),
          img: !!document.querySelector('#wheelObj img'),
          faces: document.querySelectorAll('#wheelObj svg #faces path').length};
});
ck('TEST 5', 'clearing the asset returns to the built-in wheel',
   cleared.svg && !cleared.img && cleared.faces === 9, JSON.stringify(cleared));

// ---- and the import normalisation the brief asks for, which is the other half of TEST 5 ----
// An older V4 session may carry a ratio taken from whatever asset happened to be loaded when it
// was written. That is a layout at somebody else's projection, so it is normalised on the way in
// rather than migrated -- the schema is unchanged and the session still opens.
const norm = await p.evaluate(() => {
  const old = JSON.parse(JSON.stringify(DEFAULT_STATE));
  old.wheel.naturalRatio = 0.5624;          // written by a build that adopted an asset's ratio
  old.wheel.ratioSource = "viewBox";
  old.wheel.width = 1372;
  old.wheel.height = 772;                   // and the height that went with it
  old.wheel.image = null;
  importSession(old);
  return {ratio: S.wheel.naturalRatio, src: S.wheel.ratioSource,
          w: S.wheel.width, h: S.wheel.height, bottom: S.wheel.y + S.wheel.height,
          oob: document.querySelectorAll('.obj.oob').length};
});
ck('TEST 5', 'an imported asset-derived ratio is normalised to the layout\'s',
   near(norm.ratio, 0.5299, 0.0005) && norm.src === 'builtin', norm.ratio + ' / ' + norm.src);
ck('TEST 5', 'and the height is re-derived from it',
   norm.h === Math.round(norm.w * norm.ratio), norm.w + ' x ' + norm.h);
ck('TEST 5', 'so the imported wheel is back inside the module',
   norm.bottom <= 1200 && norm.oob === 0, 'bottom ' + norm.bottom + ', ' + norm.oob + ' warnings');

// =============================================================================================
// TEST 6 — READY PREVIEW
// =============================================================================================
await p.evaluate(() => localStorage.clear());
await p.reload();
await p.waitForTimeout(400);
await clean(true);
await setView('ready');
await p.click('.obj[data-kind=card][data-id=clerical]');
await p.waitForTimeout(200);
let pv = await p.evaluate(() => ({
  n: document.querySelectorAll('.obj[data-kind=art]').length,
  badges: document.querySelectorAll('.obj[data-kind=art] .pv').length,
  duty: S.previewDuty,
  caps: [].slice.call(document.querySelectorAll('.obj[data-kind=art] .cap')).map(c => c.textContent.trim())}));
ck('TEST 6', "Clerical's two artworks appear with a PREVIEW badge",
   pv.n === 2 && pv.badges === 2 && pv.caps.join('|') === 'Gain X piety|Gain X silver',
   pv.caps.join(' | '));

// Each of these must LEAVE the preview open.
async function clickAndCheck(sel, label){
  await p.click(sel, {position: {x: 6, y: 6}});
  await p.waitForTimeout(150);
  const d = await p.evaluate(() => ({duty: S.previewDuty,
    n: document.querySelectorAll('.obj[data-kind=art]').length}));
  ck('TEST 6', 'clicking ' + label + ' leaves the preview open',
     d.duty === 'clerical' && d.n === 2, d.duty + '/' + d.n);
}
await clickAndCheck('.obj[data-kind=art][data-id=left]', 'the artwork itself');
await clickAndCheck('#wheelObj', 'the wheel');
await clickAndCheck('#cityObj', 'the City');
await p.evaluate(() => {
  const f = document.querySelector('.obj[data-kind=figs] .fig');
  f.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true}));
});
await p.waitForTimeout(150);
let acc = await p.evaluate(() => S.previewDuty);
ck('TEST 6', 'clicking an acolyte leaves the preview open', acc === 'clerical', acc);

// And empty stage must close it.
await p.mouse.click(700, 1330);
await p.waitForTimeout(200);
const closed = await p.evaluate(() => ({duty: S.previewDuty,
  n: document.querySelectorAll('.obj[data-kind=art]').length}));
ck('TEST 6', 'clicking the empty black background closes it',
   !closed.duty && closed.n === 0, closed.duty + '/' + closed.n);

// =============================================================================================
// TEST 7 — SAME / DIFFERENT CARD
// =============================================================================================
await p.click('.obj[data-kind=card][data-id=clerical]'); await p.waitForTimeout(150);
await p.click('.obj[data-kind=card][data-id=clerical]'); await p.waitForTimeout(150);
let s7 = await p.evaluate(() => S.previewDuty);
ck('TEST 7', 'clicking the same card again closes the preview', !s7, String(s7));
await p.click('.obj[data-kind=card][data-id=clerical]'); await p.waitForTimeout(150);
await p.click('.obj[data-kind=card][data-id=produce]'); await p.waitForTimeout(150);
s7 = await p.evaluate(() => ({duty: S.previewDuty,
  caps: [].slice.call(document.querySelectorAll('.obj[data-kind=art] .cap')).map(c => c.textContent.trim())}));
ck('TEST 7', 'clicking another card switches straight to it',
   s7.duty === 'produce' && s7.caps.join('|') === 'Gain X wheat|Gain X stone', s7.caps.join(' | '));
await p.evaluate(() => { S.previewDuty = null; render(); });

// =============================================================================================
// TEST 8 — SOWING
// =============================================================================================
await setView('sow'); await p.waitForTimeout(150);
const handBefore = await p.evaluate(() => ({count: S.inHand.count,
  label: document.querySelector('#cityObj .cl').textContent.trim(),
  shown: document.querySelector('#cityObj .ct').textContent.trim(),
  line: document.querySelector('#statusObj .main').textContent.trim()}));
await p.click('.obj[data-kind=card][data-id=taxation]'); await p.waitForTimeout(200);
const s8 = await p.evaluate(() => ({n: document.querySelectorAll('.obj[data-kind=art]').length,
  badges: document.querySelectorAll('.obj[data-kind=art] .pv').length,
  duty: S.previewDuty,
  count: S.inHand.count,
  label: document.querySelector('#cityObj .cl').textContent.trim(),
  shown: document.querySelector('#cityObj .ct').textContent.trim(),
  line: document.querySelector('#statusObj .main').textContent.trim()}));
// ONE BOX: the duty clicked here is Taxation, which has one action from V4.5. The claim is
// that a preview in SOWING behaves as it does in READY, and it still does -- READY shows one box
// for Taxation too.
ck('TEST 8', 'preview behaves as in READY', s8.n === 1 && s8.badges === 1 && s8.duty === 'taxation',
   s8.n + '/' + s8.badges + '/' + s8.duty);
ck('TEST 8', 'the City region still shows Acolytes in Hand', /IN HAND/i.test(s8.label), s8.label);
ck('TEST 8', 'the preview does not disturb the in-hand count',
   s8.count === handBefore.count && s8.shown === handBefore.shown && s8.line === handBefore.line,
   s8.shown + ' · ' + s8.line);
await p.click('.obj[data-kind=art][data-id=left]', {position: {x: 6, y: 6}});
await p.waitForTimeout(150);
ck('TEST 8', 'and the artwork is still inert here too',
   await p.evaluate(() => S.previewDuty) === 'taxation');

// =============================================================================================
// TEST 9 — ACTION SELECTION
// =============================================================================================
await setView('action'); await p.waitForTimeout(200);
const s9 = await p.evaluate(() => ({
  carried: S.previewDuty,
  caps: [].slice.call(document.querySelectorAll('.obj[data-kind=art] .cap')).map(c => c.textContent.trim()),
  badges: document.querySelectorAll('.obj[data-kind=art] .pv').length,
  tithe: !!document.getElementById('titheObj'),
  reached: [].slice.call(document.querySelectorAll('.obj[data-kind=card].reached')).map(e => e.dataset.id),
  previewable: document.querySelectorAll('.obj[data-kind=card].previewable').length,
}));
ck('TEST 9', 'the reached duty\'s artwork appears automatically',
   s9.caps.join('|') === 'Gain X piety|Gain X silver' && s9.badges === 0, s9.caps.join(' | '));
ck('TEST 9', 'Tithe appears', s9.tithe);
ck('TEST 9', 'the reached card is highlighted', s9.reached.join(',') === 'clerical', s9.reached.join(','));
ck('TEST 9', 'changing state closed the previous preview', !s9.carried, String(s9.carried));
ck('TEST 9', 'no card is marked previewable here', s9.previewable === 0, s9.previewable);

// THE HOVER AFFORDANCE ITSELF, measured rather than inferred from the class: the CSS rule has to
// be the one that stops applying.
const hover = await p.evaluate(() => {
  const card = document.querySelector('.obj[data-kind=card][data-id=produce]');
  const read = () => {
    const cs = getComputedStyle(card);
    return {cursor: cs.cursor, previewable: card.classList.contains('previewable')};
  };
  const out = {action: read()};
  setView('ready');
  const c2 = document.querySelector('.obj[data-kind=card][data-id=produce]');
  out.ready = {cursor: getComputedStyle(c2).cursor,
               previewable: c2.classList.contains('previewable')};
  return out;
});
ck('TEST 9', 'cards are previewable in READY and not in ACTION',
   hover.ready.previewable && !hover.action.previewable,
   'ready ' + hover.ready.previewable + ', action ' + hover.action.previewable);
const rule = await p.evaluate(() => {
  let found = null;
  [].slice.call(document.styleSheets).forEach(sh => {
    let rules; try { rules = sh.cssRules; } catch (e){ return; }
    [].slice.call(rules || []).forEach(r => {
      if (r.selectorText && /\.card.*:hover/.test(r.selectorText)) found = r.selectorText;
    });
  });
  return found;
});
ck('TEST 9', 'the hover rule is scoped to previewable cards',
   !!rule && /previewable/.test(rule), rule);

// AND THE CLICK ITSELF DOES NOTHING. The class and the CSS are the affordance; this is the
// behaviour they are promising, and testing only the promise leaves the promise free to lie.
await setView('action'); await p.waitForTimeout(150);
const inert = await p.evaluate(() => {
  const before = {duty: S.previewDuty,
                  caps: [].slice.call(document.querySelectorAll('.obj[data-kind=art] .cap'))
                          .map(c => c.textContent.trim()).join('|')};
  document.querySelector('.obj[data-kind=card][data-id=produce]')
    .dispatchEvent(new PointerEvent('pointerdown', {bubbles: true, clientX: 0, clientY: 0}));
  return {before, after: {duty: S.previewDuty,
          caps: [].slice.call(document.querySelectorAll('.obj[data-kind=art] .cap'))
                  .map(c => c.textContent.trim()).join('|')}};
});
ck('TEST 9', 'clicking another duty card in ACTION SELECTION does nothing at all',
   !inert.after.duty && inert.after.caps === inert.before.caps,
   inert.after.duty + ' · ' + inert.after.caps);

// =============================================================================================
// TEST 10 — GAME LAYOUT EXPORT
// =============================================================================================
const G = await p.evaluate(() => ({o: gameLayout(), text: JSON.stringify(gameLayout())}));
const g = G.o, text = G.text;
const has = (o, keys) => keys.every(k => k in o);

ck('TEST 10', 'complete status presentation and byView text',
   has(g.status, ['x','y','width','height','size','align','opacity','visible','byView'])
     && ['ready','sow','action'].every(v => typeof (g.status.byView[v] || {}).main === 'string'
                                            && g.status.byView[v].main.length > 0),
   Object.keys(g.status).join(','));
ck('TEST 10', 'wheel geometry plus ratio, ground and opacity',
   has(g.wheel, ['x','y','width','height','ratio','ground','opacity'])
     && near(g.wheel.ratio, 0.5299, 0.0005),
   Object.keys(g.wheel).join(','));
ck('TEST 10', 'duty card geometry and visibility',
   Object.keys(g.duties).length === 8
     && Object.values(g.duties).every(d => has(d.card, ['x','y','width','height','visible'])),
   Object.keys(g.duties.clerical.card).join(','));
// THE EXPORT CARRIES BOTH FIELDS, AND AN UNNAMED ACTION EXPORTS AS "". They held the same
// string until V4.5, when they became two different things: `name` is the action's own name and
// `shortLabel` is what it does. Most duties have no name written yet.
//
// The null in ui/board_v2/duty_text.json does NOT survive to here, and that is applyState's
// doing rather than an oversight: it coerces both fields to strings on load, so the panel, the
// renderer and this export never have to handle a null. Null is how the source file says "not
// decided"; "" is how the state says "no name to draw". The distinction is kept where it is
// useful -- in the file somebody edits -- and flattened where it would only mean two code paths.
//
// What must NOT happen is the empty name falling back to the label. That is the shadowing this
// change existed to undo, and it is why clerical is checked for both values rather than one.
ck('TEST 10', 'the action wording: both fields, an unnamed action exporting empty',
   Object.values(g.duties).every(d => ['actionA','actionB'].every((k, i) =>
     typeof d[k].shortLabel === 'string' && typeof d[k].name === 'string'
       // A slot the duty HAS must say something; a slot beyond its action count must not.
       && (i < d.actions ? d[k].shortLabel.length > 0 : d[k].shortLabel === '')))
     && g.duties.clerical.actionA.name === 'Devotion'
     && g.duties.clerical.actionA.shortLabel === 'Gain X piety'
     && g.duties.produce.actionA.name === 'Produce Wheat'
     && g.duties.produce.actionA.shortLabel === 'Gain X wheat'
     // The one-action duties still export a second slot so the schema is one shape for all
     // eight; it simply carries nothing, and `actions` is what says so.
     && g.duties.taxation.actions === 1
     && g.duties.taxation.actionB.shortLabel === ''
     && g.duties.clerical.actions === 2,
   'clerical ' + JSON.stringify(g.duties.clerical.actionA.name)
     + ' · produce ' + JSON.stringify(g.duties.produce.actionA.name));
ck('TEST 10', 'artwork fit, opacity and captions',
   ['left','right'].every(s => has(g.artwork[s],
     ['x','y','width','height','slot','fit','opacity','visible','labelVisible','labelSize'])),
   Object.keys(g.artwork.left).join(','));
ck('TEST 10', 'the selected-duty highlight settings',
   !!g.highlight && has(g.highlight, ['width','height','dy','style','visible','opacity','colour']),
   g.highlight && Object.keys(g.highlight).join(','));
ck('TEST 10', "Tithe's label and resource definitions",
   has(g.tithe, ['x','y','width','height','visible','label'])
     && Array.isArray(g.tithe.resources) && g.tithe.resources.length === 3
     && g.tithe.resources.every(r => r.key && r.name),
   g.tithe.label + ' · ' + (Array.isArray(g.tithe.resources)
     ? g.tithe.resources.map(r => r.key).join('/') : 'no resources array'));
ck('TEST 10', "the City's label and geometry",
   has(g.city, ['x','y','width','height','visible','label']), Object.keys(g.city).join(','));
ck('TEST 10', 'acolyte sizing and anchors',
   has(g.acolytes, ['height','ratios'])
     && Object.values(g.duties).every(d =>
          has(d.figures, ['x','y','u','v','spacing','arrangement','attached'])),
   Object.keys(g.duties.clerical.figures).join(','));

// ---- and what it must not carry
const banned = ['guides','mode','zoom','view','selectedDuty','previewDuty','showGhosts',
                'attachToWheel','background','players','display','sel'];
ck('TEST 10', 'no editor selection, guides, ghosts, zoom or previewDuty',
   banned.every(k => !(k in g)), banned.filter(k => k in g).join(',') || 'none');
const bannedText = ['"locked"','"image"','"imageName"','"naturalRatio"','"ratioSource"',
                    '"assetRatio"','"seal"','"scenic"','"seats"','"count"','"clock"','data:'];
ck('TEST 10', 'no lock flags, image pool or session counts',
   bannedText.every(s => !text.includes(s)),
   bannedText.filter(s => text.includes(s)).join(' ') || 'none');
ck('TEST 10', 'no undo history and no lab image bytes',
   !('HIST' in g) && !text.includes('base64'));
ck('TEST 10', 'the export is stable across view state and zoom',
   await p.evaluate(() => {
     setView('ready'); setZoom(150); S.previewDuty = 'produce';
     const a = JSON.stringify(gameLayout());
     setView('action'); setZoom('fit'); S.previewDuty = null;
     const b = JSON.stringify(gameLayout());
     setZoom(100);
     return a === b;
   }));

// =============================================================================================
ck('ALL', 'no page or console errors in the whole run', errs.length === 0, errs.slice(0, 3).join(' | '));

await b.close();
const out = R.join('\n') + `\n\n${n - fail}/${n} passed, ${fail} failed.\n`;
if (!process.argv[2]) fs.writeFileSync(path.join(OUT, 'accept41.txt'), out);
console.log(process.argv[2]
  ? out.split('\n').filter(l => l.startsWith('FAIL')).concat(out.trim().split('\n').pop()).join('\n')
  : out);
process.exit(fail ? 1 : 0);
