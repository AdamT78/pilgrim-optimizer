// V4.2.1: lock semantics, control synchronisation, and a fit that cannot keep an overlap.
// The brief's tests 16-24, in its own order.
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
const reset = async () => { await p.evaluate(() => localStorage.clear());
                            await p.reload(); await p.waitForTimeout(350); };

// A full snapshot of every object a helper can touch, plus the history depth.
const snap = () => p.evaluate(() => ({
  all: JSON.stringify({
    wheel: [S.wheel.x, S.wheel.y, S.wheel.width, S.wheel.height],
    cards: DUTY_ORDER.map(s => { const c = S.duties[s].card; return [c.x, c.y, c.width, c.height]; }),
    artL: [artOf('left').x, artOf('left').y, artOf('left').width, artOf('left').height],
    artR: [artOf('right').x, artOf('right').y, artOf('right').width, artOf('right').height],
    tithe: [S.tithe.x, S.tithe.y, S.tithe.width, S.tithe.height],
    city: [S.city.x, S.city.y, S.city.width, S.city.height],
    figs: DUTY_ORDER.map(s => [S.duties[s].figures.x, S.duties[s].figures.y]),
  }),
  hist: HIST.length,
  status: document.getElementById('status').textContent,
  controls: ['hpWheelN','hpWheelR','hpCardN','hpCardR','hpArtWN','hpArtWR',
             'hpArtHN','hpArtHR','hpGapN','hpGapR']
            .reduce((o, k) => { o[k] = document.getElementById(k).value; return o; }, {}),
}));
const slide = async (id, value) => {
  await p.evaluate(([i, v]) => { const e = document.getElementById(i); e.value = v; e.oninput(); },
                   [id, value]);
  await p.waitForTimeout(550);
};
const press = async (label) => {
  await p.evaluate(l => {
    const b = [].slice.call(document.querySelectorAll('#helpCtl button'))
                .filter(x => x.textContent.trim().toLowerCase() === l)[0];
    if (!b) throw new Error('no button: ' + l);
    b.click();
  }, label);
  await p.waitForTimeout(250);
};
const lock = (expr, on) => p.evaluate(([e, v]) => { eval(e + '.locked = ' + v);
  render(); panels(); }, [expr, on]);

// A refused helper must change nothing, add no history, and say why.
async function refuses(test, label, run, word, verb){
  const before = await snap();
  await run();
  const after = await snap();
  ck(test, label + ' changes no geometry', after.all === before.all);
  // AND SEPARATELY, OBJECT BY OBJECT. The snapshot above already covers this, but it compares
  // one long string: when it fails it says "not equal" and leaves you to find which of the
  // fourteen objects moved. The partial-group failure -- seven cards resized, the locked eighth
  // left behind -- is the one this suite most needs to name out loud.
  const moved = await p.evaluate(b => {
    const was = JSON.parse(b), now = [], p4 = o => [o.x, o.y, o.width, o.height].join(',');
    DUTY_ORDER.forEach((s, i) => {
      if (p4(S.duties[s].card) !== was.cards[i].join(',')) now.push(s + "'s card");
      const f = S.duties[s].figures;
      if ([f.x, f.y].join(',') !== was.figs[i].join(',')) now.push(s + "'s acolytes");
    });
    [['the wheel', S.wheel, 'wheel'], ['the left artwork', artOf('left'), 'artL'],
     ['the right artwork', artOf('right'), 'artR'], ['Tithe', S.tithe, 'tithe'],
     ['the City', S.city, 'city']].forEach(([name, o, key]) => {
      if (p4(o) !== was[key].join(',')) now.push(name);
    });
    return now;
  }, before.all);
  ck(test, label + ' moves no individual object', moved.length === 0,
     moved.length ? moved.join(', ') + ' moved' : 'all 14 unchanged');
  ck(test, label + ' creates no undo step', after.hist === before.hist,
     before.hist + ' -> ' + after.hist);
  // THE WHOLE SENTENCE, not just the object's name. Checking only for "lock" and the label let
  // "cannot undefined · the City is locked" pass every assertion in this file.
  const msg = after.status.trim();
  ck(test, label + ' says why', /lock/.test(msg) && new RegExp(word, 'i').test(msg), msg);
  ck(test, label + ' names the operation it refused',
     msg.indexOf('undefined') < 0 && new RegExp(verb, 'i').test(msg), msg);
}

// EVERYTHING BELOW RUNS INSIDE ONE try. A thrown exception here -- a mutated page whose
// `render` is gone, an evaluate against a function that no longer exists -- used to take the
// whole process down WITHOUT the summary, and a mutation run reading only the exit code scored
// that as a catch. It is a catch of sorts, but no named assertion said so, and a harness that
// died for an unrelated reason would have scored identically. Recording the throw as a failure
// keeps the summary, names what broke, and keeps "caught" meaning "a test noticed".
try {

// =============================================================================================
// TEST 16 — LOCKED WHEEL
// =============================================================================================
await lock('S.wheel', true);
await refuses('TEST 16', 'the wheel width number',
              () => p.evaluate(() => { const e = document.getElementById('hpWheelN');
                                       e.value = 1000; e.oninput(); }), 'wheel', 'resize the wheel');
await refuses('TEST 16', 'the wheel width slider', () => slide('hpWheelR', 900),
              'wheel', 'resize the wheel');
await refuses('TEST 16', 'centre wheel x', () => press('centre wheel x'),
              'wheel', 'centre the wheel');
const shown16 = await p.evaluate(() => ({ctl: +document.getElementById('hpWheelN').value,
                                        real: S.wheel.width}));
ck('TEST 16', 'and the control settles back on the real width',
   shown16.ctl === shown16.real, JSON.stringify(shown16));
await lock('S.wheel', false);
await slide('hpWheelR', 1200);
let g = await p.evaluate(() => [S.wheel.x, S.wheel.width, S.wheel.height]);
ck('TEST 16', 'unlocked, it works normally again',
   g[1] === 1200 && g[0] === 100 && g[2] === Math.round(1200 * 0.5299), g.join(','));

await reset();

// =============================================================================================
// TEST 17 — LOCKED DUTY CARD
// =============================================================================================
await lock('S.duties.ordination.card', true);
await refuses('TEST 17', 'the group card height', () => slide('hpCardR', 220),
              'ordination', 'resize the duty cards');
await refuses('TEST 17', 'align card tops', () => press('align card tops'),
              'ordination', 'align the duty cards');
await lock('S.duties.ordination.card', false);
await slide('hpCardR', 220);
let h = await p.evaluate(() => DUTY_ORDER.map(s => S.duties[s].card.height));
ck('TEST 17', 'unlocked, all eight resize', h.every(v => v === 220),
   [...new Set(h)].join(','));
await p.evaluate(() => { S.duties.produce.card.y += 22; render(); record(); });
await press('align card tops');
let ys = await p.evaluate(() => DUTY_ORDER.map(s => S.duties[s].card.y));
ck('TEST 17', 'and align card tops works', new Set(ys).size === 1, [...new Set(ys)].join(','));

await reset();

// =============================================================================================
// TEST 18 — LOCKED ACTION ROW MEMBER
// =============================================================================================
await lock('S.city', true);
await refuses('TEST 18', 'the linked artwork width', () => slide('hpArtWR', 300),
              'city', 'resize the action artwork');
await refuses('TEST 18', 'the action row gap', () => slide('hpGapR', 20),
              'city', 're-space the action row');
await refuses('TEST 18', 'align row top', () => press('align row top'),
              'city', 'align the action row');
await refuses('TEST 18', 'fit action row', () => press('fit action row'),
              'city', 'fit the action row');

// THE HEIGHT SPECIAL CASE: it writes only the two artwork boxes, so the City's lock is
// irrelevant to it. This is what proves the rule is "what the operation writes".
const beforeH = await snap();
await slide('hpArtHR', 250);
const afterH = await p.evaluate(() => ({L: artOf('left').height, R: artOf('right').height,
                                        city: S.city.height, tithe: S.tithe.height}));
ck('TEST 18', 'the linked HEIGHT still works with the City locked',
   afterH.L === 250 && afterH.R === 250, JSON.stringify(afterH));
ck('TEST 18', 'and does not touch the locked City', afterH.city === 184, afterH.city);
ck('TEST 18', 'nor Tithe', afterH.tithe === 184, afterH.tithe);

// The left artwork may stay locked for gap and align, because neither writes it.
await lock('S.city', false);
await lock('S.display.artLeft', true);
const gapOK = await (async () => { await slide('hpGapR', 18);
  return p.evaluate(() => rowGaps()); })();
ck('TEST 18', 'the gap works with the LEFT artwork locked, which it never writes',
   JSON.stringify(gapOK) === JSON.stringify([18, 18, 18]), gapOK.join(' / '));
await p.evaluate(() => { S.city.y += 30; render(); record(); });
await press('align row top');
const alignOK = await p.evaluate(() => [artOf('left').y, artOf('right').y, S.tithe.y, S.city.y]);
ck('TEST 18', 'and so does align row top', new Set(alignOK).size === 1, alignOK.join(' / '));
// But an operation that DOES write it is refused.
await refuses('TEST 18', 'the linked width, which does write the left artwork',
              () => slide('hpArtWR', 320), 'left artwork', 'resize the action artwork');
await lock('S.display.artLeft', false);

await reset();

// =============================================================================================
// TEST 19 — HELPER INPUT SYNCHRONISATION
// =============================================================================================
const controlsAfter = async () => (await snap()).controls;
let c = await controlsAfter();
ck('TEST 19', 'the wheel control starts at 1372', c.hpWheelN === '1372' && c.hpWheelR === '1372',
   c.hpWheelN + '/' + c.hpWheelR);
// A "stage handle" resize: write the geometry and render, exactly as the drag code does.
await p.evaluate(() => { S.wheel.width = 1100;
  S.wheel.height = Math.round(1100 * S.wheel.naturalRatio);
  syncAttached(); render(); record(); });
await p.waitForTimeout(150);
c = await controlsAfter();
const met = await p.evaluate(() => document.getElementById('metCtl').innerText.replace(/\s+/g, ' '));
ck('TEST 19', 'a stage resize moves the helper control too',
   c.hpWheelN === '1100' && c.hpWheelR === '1100', c.hpWheelN + '/' + c.hpWheelR);
ck('TEST 19', 'and the metrics agree', /wheel 1100 × 583/.test(met),
   (met.match(/wheel [^a-z]*/) || [''])[0]);
// An inspector edit is the same path.
await p.evaluate(() => { S.wheel.width = 980;
  S.wheel.height = Math.round(980 * S.wheel.naturalRatio); syncAttached(); render(); });
await p.waitForTimeout(120);
c = await controlsAfter();
ck('TEST 19', 'an inspector edit does too', c.hpWheelN === '980', c.hpWheelN);

// The same for every other control.
await p.evaluate(() => {
  DUTY_ORDER.forEach(s => { S.duties[s].card.height = 176; });
  artOf('left').width = 290; artOf('right').width = 290;
  artOf('left').height = 205; artOf('right').height = 205;
  layoutActionRow(9);
  render(); record();
});
await p.waitForTimeout(150);
c = await controlsAfter();
ck('TEST 19', 'card height follows', c.hpCardN === '176' && c.hpCardR === '176', c.hpCardN);
ck('TEST 19', 'artwork width follows', c.hpArtWN === '290' && c.hpArtWR === '290', c.hpArtWN);
ck('TEST 19', 'artwork height follows', c.hpArtHN === '205' && c.hpArtHR === '205', c.hpArtHN);
ck('TEST 19', 'row gap follows', c.hpGapN === '9' && c.hpGapR === '9', c.hpGapN);

// Undo, redo and reset are the same path again.
await p.evaluate(() => stepHistory(-1)); await p.waitForTimeout(150);
c = await controlsAfter();
ck('TEST 19', 'undo brings the controls back with it', c.hpCardN !== '176', c.hpCardN);
await p.evaluate(() => stepHistory(1)); await p.waitForTimeout(150);
c = await controlsAfter();
ck('TEST 19', 'and redo takes them forward again', c.hpCardN === '176', c.hpCardN);
await p.evaluate(() => { resetOne('wheel', null); }); await p.waitForTimeout(150);
c = await controlsAfter();
ck('TEST 19', 'an individual reset updates them', c.hpWheelN === '1372', c.hpWheelN);

// AND IT DOES NOT FIGHT THE CONTROL IN YOUR HANDS.
const typing = await p.evaluate(() => {
  const e = document.getElementById('hpWheelN');
  e.focus(); e.value = '1';                 // mid-type: below the 600 minimum
  render();                                 // some other path repaints
  const kept = e.value;
  e.blur();
  return {kept: kept, focused: document.activeElement === e};
});
ck('TEST 19', 'a half-typed number is not overwritten while it has the caret',
   typing.kept === '1', JSON.stringify(typing));

// §9 CLAMPING: the control settles on what was actually applied.
await reset();
await p.evaluate(() => { const e = document.getElementById('hpWheelR'); e.value = 1500; e.oninput(); });
await p.waitForTimeout(550);
const clamped = await p.evaluate(() => ({ctl: +document.getElementById('hpWheelN').value,
                                        slider: +document.getElementById('hpWheelR').value,
                                        real: S.wheel.width}));
ck('TEST 19', 'an over-range entry settles at the applied value, not the typed one',
   clamped.real === 1400 && clamped.ctl === 1400 && clamped.slider === 1400,
   JSON.stringify(clamped));

await reset();

// =============================================================================================
// TEST 20 / 21 — MIXED CARDS AND MIXED ARTWORK
// =============================================================================================
await p.evaluate(() => { S.duties.construct.card.height = 185; render(); record(); });
let m = await p.evaluate(() => document.getElementById('metCtl').innerText.replace(/\s+/g, ' '));
ck('TEST 20', 'mixed cards are reported as a range', /duty cards 159 × 150–185 mixed/.test(m),
   (m.match(/duty cards [^a]*/) || [''])[0]);
const beforeOpen = await snap();
await p.evaluate(() => { panels(); render(); });
const afterOpen = await snap();
ck('TEST 20', 'repainting the panel alters no card', afterOpen.all === beforeOpen.all);
await slide('hpCardR', 170);
m = await p.evaluate(() => document.getElementById('metCtl').innerText.replace(/\s+/g, ' '));
h = await p.evaluate(() => DUTY_ORDER.map(s => S.duties[s].card.height));
ck('TEST 20', 'the group control makes all eight 170', h.every(v => v === 170),
   [...new Set(h)].join(','));
ck('TEST 20', 'and the readout says each, not mixed', /duty cards 159 × 170 each/.test(m),
   (m.match(/duty cards [^a]*/) || [''])[0]);

await reset();
await p.evaluate(() => { artOf('right').width = 430; render(); record(); });
m = await p.evaluate(() => document.getElementById('metCtl').innerText.replace(/\s+/g, ' '));
ck('TEST 21', 'a mismatched pair is reported separately',
   /action left 375 × 184/.test(m) && /action right 430 × 184/.test(m),
   (m.match(/action left.*?take/) || [''])[0]);
c = await controlsAfter();
ck('TEST 21', 'the linked control shows the left box, the row anchor', c.hpArtWN === '375',
   c.hpArtWN);
await slide('hpArtWR', 375);
const evened = await p.evaluate(() => [artOf('left').width, artOf('right').width]);
ck('TEST 21', 'using it makes them equal with no jump to an older value',
   JSON.stringify(evened) === JSON.stringify([375, 375]), evened.join('/'));

await reset();

// =============================================================================================
// TEST 22 — NEGATIVE GAP + FIT
// =============================================================================================
await p.evaluate(() => {
  // -20 / -10 / 12, by hand, exactly as dragging would leave it.
  const L = artOf('left'), R = artOf('right');
  R.x = L.x + L.width - 20;
  S.tithe.x = R.x + R.width - 10;
  S.city.x = S.tithe.x + S.tithe.width + 12;
  render(); record();
});
let gaps = await p.evaluate(() => rowGaps());
ck('TEST 22', 'the three gaps really are -20 / -10 / 12',
   JSON.stringify(gaps) === JSON.stringify([-20, -10, 12]), gaps.join(' / '));
m = await p.evaluate(() => document.getElementById('metCtl').innerText.replace(/\s+/g, ' '));
const warnCls = await p.evaluate(() => [].slice.call(document.querySelectorAll('#metCtl i'))
  .filter(i => i.textContent === 'action gaps')[0].nextElementSibling.className);
ck('TEST 22', 'the readout shows all three and warns', /action gaps -20 \/ -10 \/ 12 px mixed/.test(m)
   && warnCls === 'bad', (m.match(/action gaps [^c]*/) || [''])[0] + ' class=' + warnCls);
const suggested = await p.evaluate(() => rowGapSuggested());
ck('TEST 22', 'the raw suggestion really is negative here', suggested === -10, suggested);
const preFit = await p.evaluate(() => [artOf('left').x, S.tithe.width, S.city.width]);
await press('fit action row');
gaps = await p.evaluate(() => rowGaps());
const post = await p.evaluate(() => ({
  L: artOf('left'), R: artOf('right'), t: S.tithe, c: S.city,
  right: S.city.x + S.city.width, msg: document.getElementById('status').textContent}));
ck('TEST 22', 'the resulting gap is not negative', Math.min.apply(null, gaps) >= 0,
   gaps.join(' / '));
ck('TEST 22', 'all three are equal', gaps[0] === gaps[1] && gaps[1] === gaps[2], gaps.join(' / '));
ck('TEST 22', 'the two artworks are equal width', post.L.width === post.R.width,
   post.L.width + '/' + post.R.width);
ck('TEST 22', 'Tithe keeps its width', post.t.width === preFit[1], post.t.width);
ck('TEST 22', 'the City keeps its width', post.c.width === preFit[2], post.c.width);
ck('TEST 22', 'the left anchor did not move', post.L.x === preFit[0], post.L.x);
ck('TEST 22', 'the row fits the module', post.right <= 1400, post.right);
ck('TEST 22', 'nothing in the row overlaps', Math.min.apply(null, gaps) >= 0);
ck('TEST 22', 'and the message says it normalised', /normalis/.test(post.msg), post.msg.trim());

await reset();

// =============================================================================================
// TEST 23 — THE setArtWidth ORDERING SURVIVES
// =============================================================================================
// The default row is 15 / 10 / 12: known, positive and mixed, which is this test's premise.
//
// THE TWO DIRECTIONS FAIL DIFFERENTLY, and are therefore asserted separately. If the gap is
// measured AFTER the widths move rather than before, it measures the hole the change just made:
// shrinking each artwork by 75 leaves a false gap around 87, and widening by 200 leaves a false
// gap around -188. One assertion spanning both would still catch it, but would not say which
// way round the ordering had been put back.
const walk = async seq => {
  const seen = [];
  for (const w of seq){
    await slide('hpArtWR', w);
    seen.push(await p.evaluate(() => ({w: artOf('left').width, gaps: rowGaps(),
                                       anchor: artOf('left').x})));
  }
  return seen;
};
const shrink = await walk([340, 300, 250, 200]);
ck('TEST 23', 'shrinking opens no false hole',
   shrink.every(s => s.gaps[0] <= 80), shrink.map(s => s.w + '→' + s.gaps[0]).join('  '));
const widen = await walk([250, 320, 400, 375]);
ck('TEST 23', 'widening packs the row at no false negative',
   widen.every(s => s.gaps[0] >= 0), widen.map(s => s.w + '→' + s.gaps[0]).join('  '));

const seen = shrink.concat(widen);
ck('TEST 23', 'every step leaves all three gaps equal',
   seen.every(s => s.gaps[0] === s.gaps[1] && s.gaps[1] === s.gaps[2]),
   seen.map(s => s.gaps.join('/')).join('  '));
ck('TEST 23', 'and every step keeps the gap the row started with',
   seen.every(s => s.gaps[0] === 12), [...new Set(seen.map(s => s.gaps[0]))].join(','));
ck('TEST 23', 'the anchor never moves', seen.every(s => s.anchor === 28),
   [...new Set(seen.map(s => s.anchor))].join(','));
ck('TEST 23', 'and the row is deterministic: same width in, same row out',
   JSON.stringify(shrink[2].gaps) === JSON.stringify(widen[0].gaps)
   && shrink[2].w === widen[0].w,
   shrink[2].w + ':' + shrink[2].gaps.join('/') + ' vs ' + widen[0].w + ':' + widen[0].gaps.join('/'));

await reset();

// =============================================================================================
// TEST 24 — SLIDER UNDO, AS A SWEEP
// =============================================================================================
async function sweep(id, from, to, readBack){
  await reset();
  return p.evaluate(async ([i, a, z, expr]) => {
    const before = HIST.length, start = eval(expr);
    const r = document.getElementById(i);
    const step = z > a ? 1 : -1;
    for (let v = a; step > 0 ? v <= z : v >= z; v += step){ r.value = v; r.oninput(); }
    await new Promise(res => setTimeout(res, 600));
    const added = HIST.length - before;
    stepHistory(-1);
    return {added: added, back: eval(expr), start: start};
  }, [id, from, to, readBack]);
}
let s = await sweep('hpWheelR', 1372, 1000, 'S.wheel.width');
ck('TEST 24', 'a 372-step wheel sweep is one undo entry', s.added === 1, s.added);
ck('TEST 24', 'and one undo returns to the pre-sweep width', s.back === s.start,
   s.back + ' vs ' + s.start);
s = await sweep('hpCardR', 150, 200, 'S.duties.clerical.card.height');
ck('TEST 24', 'card height sweeps the same way', s.added === 1 && s.back === s.start,
   JSON.stringify(s));
s = await sweep('hpArtWR', 375, 300, 'artOf("left").width');
ck('TEST 24', 'artwork width too', s.added === 1 && s.back === s.start, JSON.stringify(s));
s = await sweep('hpArtHR', 184, 240, 'artOf("left").height');
ck('TEST 24', 'artwork height too', s.added === 1 && s.back === s.start, JSON.stringify(s));
s = await sweep('hpGapR', 12, 40, 'rowGaps()[0]');
ck('TEST 24', 'and the row gap', s.added === 1 && s.back === s.start, JSON.stringify(s));

// =============================================================================================
// TEST 25 — THE FOUR HOLES MUTATION FOUND
//
// Each of these passed a mutated build that the tests above could not tell from the real one.
// They are written here in the order mut421.py reported them.
// =============================================================================================
await reset();

// 25a. THE ANCHOR'S OWN LOCK. Clerical's y does not move when the cards are levelled -- it is
// the value everything else is levelled TO -- so a guard built out of "what actually gets
// written" would leave it out, and align would go ahead over a locked Clerical. The rule is
// "what the operation is about", not "what it assigns": a partial alignment is not an alignment.
await p.evaluate(() => { S.duties.ordination.card.y = 96; render(); record(); });
await lock('S.duties.clerical.card', true);
await refuses('TEST 25', 'align card tops with only the ANCHOR card locked',
              () => press('align card tops'), 'clerical', 'align the duty cards');
await lock('S.duties.clerical.card', false);
const levelled = await (async () => { await press('align card tops');
  return p.evaluate(() => DUTY_ORDER.map(s => S.duties[s].card.y)); })();
ck('TEST 25', 'and unlocked it levels them, so the fixture was real',
   new Set(levelled).size === 1, [...new Set(levelled)].join(','));

// 25a-ii. THE OTHER HALF OF THE PAIR. The linked width is guarded over four objects and the
// tests above lock the City and the left artwork; nothing locked the RIGHT artwork, so a guard
// that dropped it would have gone unnoticed. "Linked" is the entire feature — resizing one box
// and leaving its locked partner behind is the partial-group failure again, on the action row.
await reset();
await lock('S.display.artRight', true);
await refuses('TEST 25', 'the linked width with only the RIGHT artwork locked',
              () => slide('hpArtWR', 300), 'right artwork', 'resize the action artwork');
await refuses('TEST 25', 'and the linked height too', () => slide('hpArtHR', 220),
              'right artwork', 'resize the action artwork');
await lock('S.display.artRight', false);
const pair25 = await (async () => { await slide('hpArtWR', 300);
  return p.evaluate(() => [artOf('left').width, artOf('right').width]); })();
ck('TEST 25', 'unlocked, both boxes move together', JSON.stringify(pair25) === '[300,300]',
   pair25.join('/'));

// 25b. WHICH END OF A MIXED CARD GROUP THE CONTROL SHOWS. Both ends are honest numbers, so a
// control reading the tallest card looks right until you use it: the next touch of the slider
// would take all eight to a height only one of them has.
await reset();
await p.evaluate(() => { S.duties.construct.card.height = 185;
                         S.duties.ordination.card.height = 168; render(); record(); });
c = await controlsAfter();
ck('TEST 25', 'a mixed card group shows the GROUP value, not the tallest',
   c.hpCardN === '150' && c.hpCardR === '150', c.hpCardN + ' (heights 150/168/185)');
m = await p.evaluate(() => document.getElementById('metCtl').innerText.replace(/\s+/g, ' '));
ck('TEST 25', 'while the readout still reports the whole range',
   /duty cards 159 × 150–185 mixed/.test(m), (m.match(/duty cards [^a]*/) || [''])[0]);

// 25c. THE GAP CONTROL CANNOT SHOW WHAT IT CANNOT HOLD. The metrics tell the truth about a
// negative gap; the control is clamped into its own range, or the number box displays a value
// the slider beside it can never reach and pressing either one jumps the row.
await reset();
await p.evaluate(() => {
  const L = artOf('left'), R = artOf('right');
  R.x = L.x + L.width - 10;
  S.tithe.x = R.x + R.width - 10;
  S.city.x = S.tithe.x + S.tithe.width - 10;
  render(); record();
});
const rawNeg = await p.evaluate(() => rowGapSuggested());
c = await controlsAfter();
const gapRange = await p.evaluate(() => HELPERS.gap);
ck('TEST 25', 'the raw suggestion is negative', rawNeg === -10, rawNeg);
ck('TEST 25', 'but the control sits inside its own range',
   +c.hpGapN >= gapRange[0] && +c.hpGapN <= gapRange[1] && c.hpGapN === c.hpGapR,
   c.hpGapN + ' / ' + c.hpGapR + ' in [' + gapRange.join(',') + ']');
m = await p.evaluate(() => document.getElementById('metCtl').innerText.replace(/\s+/g, ' '));
// The three are equal here, so the readout collapses them to one figure -- which is the
// reporting rule everywhere else in the panel, not a special case for negatives.
const negCls = await p.evaluate(() => [].slice.call(document.querySelectorAll('#metCtl i'))
  .filter(i => i.textContent === 'action gaps')[0].nextElementSibling.className);
ck('TEST 25', 'and the metrics still report the overlap it hides, and warn',
   /action gaps -10 px/.test(m) && negCls === 'bad',
   (m.match(/action gaps [^c]*/) || [''])[0] + ' class=' + negCls);

// 25d. THE ORDINARY RESIZE IS NOT A REPAIR. FIT ACTION ROW normalises a negative gap because
// that is what it is for; the linked width must preserve whatever composition is in progress,
// overlap and all, or a slider nudge silently undoes a deliberate overlap.
const widened = await (async () => { await slide('hpArtWR', 340);
  return p.evaluate(() => ({gaps: rowGaps(), L: artOf('left').width,
                            R: artOf('right').width})); })();
ck('TEST 25', 'the linked width keeps the -10 gap it found',
   JSON.stringify(widened.gaps) === JSON.stringify([-10, -10, -10]), widened.gaps.join(' / '));
ck('TEST 25', 'and did resize, so the fixture was real',
   widened.L === 340 && widened.R === 340, widened.L + '/' + widened.R);
await press('fit action row');
const repaired = await p.evaluate(() => rowGaps());
ck('TEST 25', 'while FIT, on the same row, does normalise it',
   Math.min.apply(null, repaired) >= gapRange[0], repaired.join(' / '));

await reset();

ck('ALL', 'no page or console errors in the whole run', errs.length === 0, errs.slice(0, 3).join(' | '));

} catch (e) {
  ck('ALL', 'the run completed without throwing', false,
     (e && e.message ? e.message : String(e)).split('\n')[0]);
}

await b.close();
const out = R.join('\n') + `\n\n${n - fail}/${n} passed, ${fail} failed.\n`;
if (!process.argv[2]) fs.writeFileSync(path.join(OUT, 'accept421.txt'), out);
console.log(process.argv[2]
  ? out.split('\n').filter(l => l.startsWith('FAIL')).concat(out.trim().split('\n').pop()).join('\n')
  : out);
process.exit(fail ? 1 : 0);
