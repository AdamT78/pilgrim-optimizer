// THE LAYOUT HELPERS ACCEPTANCE TESTS, A to J, in the brief's own order and wording.
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

// Everything the tests look at, in one read.
const geom = () => p.evaluate(() => ({
  wheel: {x: S.wheel.x, y: S.wheel.y, w: S.wheel.width, h: S.wheel.height},
  anchors: DUTY_ORDER.map(s => [S.duties[s].figures.x, S.duties[s].figures.y,
                                S.duties[s].figures.u, S.duties[s].figures.v]),
  cards: DUTY_ORDER.map(s => { const c = S.duties[s].card;
                               return [c.x, c.y, c.width, c.height]; }),
  artL: [artOf('left').x, artOf('left').y, artOf('left').width, artOf('left').height],
  artR: [artOf('right').x, artOf('right').y, artOf('right').width, artOf('right').height],
  tithe: [S.tithe.x, S.tithe.y, S.tithe.width, S.tithe.height],
  city: [S.city.x, S.city.y, S.city.width, S.city.height],
  gaps: rowGaps(),
  metrics: document.getElementById('metCtl').innerText.replace(/\s+/g, ' ').trim(),
  hist: HIST.length,
}));
// Drive a control the way a person does, so the wiring is exercised and not just the function.
const slide = async (id, value) => {
  await p.evaluate(([i, v]) => {
    const e = document.getElementById(i);
    e.value = v; e.oninput();
  }, [id, value]);
  await p.waitForTimeout(550);           // past the 400ms history debounce
};
const press = async (label) => {
  await p.evaluate(l => {
    const b = [].slice.call(document.querySelectorAll('#helpCtl button'))
                .filter(x => x.textContent.trim().toLowerCase() === l)[0];
    if (!b) throw new Error('no button: ' + l);
    b.click();
  }, label);
  await p.waitForTimeout(200);
};

// =============================================================================================
// TEST A — WHEEL SCALE + CENTER
// =============================================================================================
let before = await geom();
await slide('hpWheelR', 1200);
let g = await geom();
ck('TEST A', 'width = 1200', g.wheel.w === 1200, g.wheel.w);
ck('TEST A', 'height = round(1200 × 0.5299) = 636', g.wheel.h === Math.round(1200 * 0.5299),
   g.wheel.h);
ck('TEST A', 'x = 100', g.wheel.x === 100, g.wheel.x);
ck('TEST A', 'y unchanged', g.wheel.y === before.wheel.y, g.wheel.y);
ck('TEST A', 'the acolytes keep their wheel-relative u/v',
   JSON.stringify(g.anchors.map(a => [a[2], a[3]]))
     === JSON.stringify(before.anchors.map(a => [a[2], a[3]])));
ck('TEST A', 'and their absolute positions followed the wheel',
   JSON.stringify(g.anchors.map(a => [a[0], a[1]]))
     !== JSON.stringify(before.anchors.map(a => [a[0], a[1]])));
const aAnchor = await p.evaluate(() => {
  const w = S.wheel, f = S.duties.clerical.figures;
  return Math.abs((w.x + f.u * w.width) - f.x) <= 1 && Math.abs((w.y + f.v * w.height) - f.y) <= 1;
});
ck('TEST A', 'each anchor resolves against the new wheel', aAnchor);
// ONE USEFUL UNDO. A slider sweep must not cost a press per pixel.
const undoA = await p.evaluate(() => { stepHistory(-1);
  return {x: S.wheel.x, w: S.wheel.width, h: S.wheel.height}; });
ck('TEST A', 'one undo restores the previous wheel',
   undoA.w === before.wheel.w && undoA.x === before.wheel.x && undoA.h === before.wheel.h,
   JSON.stringify(undoA));

await reset();

// =============================================================================================
// TEST B — MANUAL WHEEL + CENTER BUTTON
// =============================================================================================
// A NON-DEFAULT WIDTH FIRST. Pressing centre on a wheel that is already the default size
// cannot show whether the button also resets the width, because the reset would be a no-op.
await slide('hpWheelR', 980);
await p.evaluate(() => { S.wheel.x = 233; S.wheel.y = 452; syncAttached(); render(); record(); });
before = await geom();
await press('centre wheel x');
g = await geom();
ck('TEST B', 'only x changed', g.wheel.x === Math.round((1400 - g.wheel.w) / 2), g.wheel.x);
ck('TEST B', 'width untouched', g.wheel.w === before.wheel.w, g.wheel.w);
ck('TEST B', 'height untouched', g.wheel.h === before.wheel.h, g.wheel.h);
ck('TEST B', 'y untouched', g.wheel.y === before.wheel.y, g.wheel.y);
ck('TEST B', 'the acolytes are still attached and resolve',
   await p.evaluate(() => DUTY_ORDER.every(s => {
     const w = S.wheel, f = S.duties[s].figures;
     return f.attached && Math.abs((w.x + f.u * w.width) - f.x) <= 1;
   })));

await reset();

// =============================================================================================
// TEST C — DUTY CARD HEIGHT
// =============================================================================================
before = await geom();
await slide('hpCardR', 200);
g = await geom();
ck('TEST C', 'all eight cards are exactly 200 high',
   g.cards.every(c => c[3] === 200), [...new Set(g.cards.map(c => c[3]))].join(','));
ck('TEST C', 'x, y and width are unchanged',
   JSON.stringify(g.cards.map(c => [c[0], c[1], c[2]]))
     === JSON.stringify(before.cards.map(c => [c[0], c[1], c[2]])));
ck('TEST C', 'the readout reports the new size', /159 × 200 each/.test(g.metrics), g.metrics.slice(0, 40));
ck('TEST C', 'nothing below was pushed down',
   JSON.stringify([g.artL, g.artR, g.tithe, g.city, g.wheel])
     === JSON.stringify([before.artL, before.artR, before.tithe, before.city, before.wheel]));
// 78 + 200 = 278 against an action row at 240, so this must now report an overlap.
ck('TEST C', 'the overlap with the action row is reported',
   /cards → row overlap 38 px/.test(g.metrics), (g.metrics.match(/cards → row[^a-z]*/) || [''])[0]);
const badClass = await p.evaluate(() =>
  !!document.querySelector('#metCtl b.bad'));
ck('TEST C', 'and shown in the warning colour', badClass);

// =============================================================================================
// TEST D — MIXED CARD HEIGHT
// =============================================================================================
await p.evaluate(() => { S.duties.produce.card.height = 260; render(); record(); });
g = await geom();
ck('TEST D', 'the readout says the cards are mixed', /mixed/.test(g.metrics),
   (g.metrics.match(/duty cards [^a-z]*[a-z]*/) || [''])[0]);
ck('TEST D', 'and shows the range honestly', /200–260/.test(g.metrics));
await slide('hpCardR', 150);
g = await geom();
ck('TEST D', 'the group slider makes all eight equal again',
   g.cards.every(c => c[3] === 150), [...new Set(g.cards.map(c => c[3]))].join(','));
ck('TEST D', 'and the readout stops saying mixed', !/mixed/.test(g.metrics.split('action gaps')[0]));

await reset();

// =============================================================================================
// TEST E — LINKED ACTION HEIGHT
// =============================================================================================
// OFFSET FIRST, so "their y positions match" is something the control had to do rather than
// something that was already true.
await p.evaluate(() => { artOf('right').y += 17; render(); record(); });
before = await geom();
await slide('hpArtHR', 240);
g = await geom();
ck('TEST E', 'both artwork boxes are exactly 240 high',
   g.artL[3] === 240 && g.artR[3] === 240, g.artL[3] + '/' + g.artR[3]);
ck('TEST E', 'their y positions match', g.artL[1] === g.artR[1], g.artL[1] + '/' + g.artR[1]);
ck('TEST E', 'Tithe stays at 184', g.tithe[3] === 184, g.tithe[3]);
ck('TEST E', 'the City stays at 184', g.city[3] === 184, g.city[3]);
ck('TEST E', 'and the wheel did not move', JSON.stringify(g.wheel) === JSON.stringify(before.wheel));

await reset();

// =============================================================================================
// TEST F — LINKED ACTION WIDTH
// =============================================================================================
before = await geom();
const gapBefore = await p.evaluate(() => rowGapSuggested());
await slide('hpArtWR', 300);
g = await geom();
ck('TEST F', 'both artwork widths are equal', g.artL[2] === 300 && g.artR[2] === 300,
   g.artL[2] + '/' + g.artR[2]);
ck('TEST F', 'the left artwork is still the row anchor', g.artL[0] === before.artL[0], g.artL[0]);
ck('TEST F', 'the second box, Tithe and the City reposition from the shared gap',
   g.artR[0] === g.artL[0] + 300 + gapBefore
     && g.tithe[0] === g.artR[0] + 300 + gapBefore
     && g.city[0] === g.tithe[0] + g.tithe[2] + gapBefore,
   [g.artL[0], g.artR[0], g.tithe[0], g.city[0]].join(' / ') + ' at gap ' + gapBefore);
ck('TEST F', 'Tithe and the City keep their widths',
   g.tithe[2] === before.tithe[2] && g.city[2] === before.city[2]);

await reset();

// =============================================================================================
// TEST G — GAP SLIDER
// =============================================================================================
before = await geom();
await slide('hpGapR', 20);
g = await geom();
ck('TEST G', 'all three gaps are 20', JSON.stringify(g.gaps) === JSON.stringify([20, 20, 20]),
   g.gaps.join(' / '));
ck('TEST G', 'no widths changed',
   JSON.stringify([g.artL[2], g.artR[2], g.tithe[2], g.city[2]])
     === JSON.stringify([before.artL[2], before.artR[2], before.tithe[2], before.city[2]]));
ck('TEST G', 'the left anchor did not move', g.artL[0] === before.artL[0], g.artL[0]);
ck('TEST G', 'the readout says 20 px', /action gaps 20 px/.test(g.metrics),
   (g.metrics.match(/action gaps [^c]*/) || [''])[0]);
const reopened = await p.evaluate(() => { panels();
  return {slider: +document.getElementById('hpGapR').value, suggested: rowGapSuggested()}; });
ck('TEST G', 'and the control reopens at that common value',
   reopened.slider === 20 && reopened.suggested === 20, JSON.stringify(reopened));

await reset();

// =============================================================================================
// TEST H — EXISTING MIXED GAPS
// =============================================================================================
// The shipped default already has 15 / 10 / 12, which is the case this test is about.
g = await geom();
ck('TEST H', 'the default layout really does have mixed gaps',
   JSON.stringify(g.gaps) === JSON.stringify([15, 10, 12]), g.gaps.join(' / '));
ck('TEST H', 'the readout reports them individually and says mixed',
   /action gaps 15 \/ 10 \/ 12 px mixed/.test(g.metrics),
   (g.metrics.match(/action gaps [^c]*/) || [''])[0]);
const sliderAt = await p.evaluate(() => ({
  slider: +document.getElementById('hpGapR').value,
  number: +document.getElementById('hpGapN').value}));
ck('TEST H', 'the slider opens at the median of the three', sliderAt.slider === 12,
   JSON.stringify(sliderAt));
// OPENING THE PANEL IS NOT AN EDIT.
const untouched = await p.evaluate(() => {
  const snap = JSON.stringify(S);
  panels(); paintMetrics(); inspector();
  return JSON.stringify(S) === snap;
});
ck('TEST H', 'opening and repainting the panel moves nothing', untouched);
await slide('hpGapR', 12);
g = await geom();
ck('TEST H', 'touching the slider then normalises them',
   JSON.stringify(g.gaps) === JSON.stringify([12, 12, 12]), g.gaps.join(' / '));

await reset();

// =============================================================================================
// TEST I — FIT ROW
// =============================================================================================
await slide('hpArtWR', 600);
let tooWide = await geom();
ck('TEST I', 'the row can be made to overflow the module',
   tooWide.city[0] + tooWide.city[2] > 1400, tooWide.city[0] + tooWide.city[2]);
before = await geom();
await press('fit action row');
g = await geom();
ck('TEST I', 'the two artwork boxes come out equal', g.artL[2] === g.artR[2],
   g.artL[2] + '/' + g.artR[2]);
ck('TEST I', 'Tithe and the City retain their widths',
   g.tithe[2] === before.tithe[2] && g.city[2] === before.city[2],
   g.tithe[2] + '/' + g.city[2]);
ck('TEST I', 'all three gaps are the chosen row gap',
   g.gaps[0] === g.gaps[1] && g.gaps[1] === g.gaps[2], g.gaps.join(' / '));
ck('TEST I', 'the whole row fits inside the 1400 px module',
   g.city[0] + g.city[2] <= 1400, g.artL[0] + ' … ' + (g.city[0] + g.city[2]));
// AND FILLS IT. "Fits" alone passes for a row that stops 200px short, which is not a fit --
// the right edge has to land on the band's own right margin, give or take the odd pixel of
// integer division.
const fitRight = await p.evaluate(() => HELPERS.rowRight);
ck('TEST I', 'and ends on the band\'s right margin rather than merely somewhere inside',
   near(1400 - (g.city[0] + g.city[2]), fitRight, 2),
   'right margin ' + (1400 - (g.city[0] + g.city[2])) + ', wanted ' + fitRight);
ck('TEST I', 'the left anchor did not move', g.artL[0] === before.artL[0], g.artL[0]);
ck('TEST I', 'heights are unchanged',
   g.artL[3] === before.artL[3] && g.artR[3] === before.artR[3]);
ck('TEST I', 'it is one undo step', await p.evaluate(() => {
  const w = artOf('left').width;
  stepHistory(-1);
  return artOf('left').width !== w && artOf('left').width === artOf('right').width;
}));

await reset();

// =============================================================================================
// TEST J — ALIGN ROW TOP
// =============================================================================================
before = await geom();
await p.evaluate(() => { S.city.y += 40; S.tithe.y -= 25; S.display.artRight.y += 12;
                         render(); record(); });
await press('align row top');
g = await geom();
const anchorY = g.artL[1];
ck('TEST J', 'all four share the left artwork\'s y',
   g.artR[1] === anchorY && g.tithe[1] === anchorY && g.city[1] === anchorY,
   [g.artL[1], g.artR[1], g.tithe[1], g.city[1]].join(' / '));
ck('TEST J', 'the anchor itself did not move', anchorY === before.artL[1], anchorY);
ck('TEST J', 'no heights changed',
   JSON.stringify([g.artL[3], g.artR[3], g.tithe[3], g.city[3]])
     === JSON.stringify([before.artL[3], before.artR[3], before.tithe[3], before.city[3]]));

// =============================================================================================
// ALIGN CARD TOPS, the small helper, and the individual-editing guarantee
// =============================================================================================
await reset();
// Heights varied too, so "leaves heights alone" is a claim with something to be wrong about.
await p.evaluate(() => { S.duties.produce.card.y += 30; S.duties.give_alms.card.y -= 14;
                         S.duties.produce.card.height = 210; S.duties.taxation.card.height = 176;
                         render(); record(); });
let pre = await geom();
await press('align card tops');
g = await geom();
ck('EXTRA', 'align card tops levels all eight to the first card\'s y',
   new Set(g.cards.map(c => c[1])).size === 1 && g.cards[0][1] === pre.cards[0][1],
   [...new Set(g.cards.map(c => c[1]))].join(','));
ck('EXTRA', 'and leaves widths, heights and x alone',
   JSON.stringify(g.cards.map(c => [c[0], c[2], c[3]]))
     === JSON.stringify(pre.cards.map(c => [c[0], c[2], c[3]])));

// NO HIDDEN LINKING: the brief's worked example, step by step.
await reset();
await slide('hpArtWR', 400);
await slide('hpArtHR', 230);
await p.evaluate(() => { artOf('right').width = 420; render(); record(); });
g = await geom();
ck('EXTRA', 'a box can still be edited alone after a group set',
   g.artL[2] === 400 && g.artR[2] === 420, g.artL[2] + '/' + g.artR[2]);
ck('EXTRA', 'and the readout reports the mismatch',
   /action left 400 × 230/.test(g.metrics) && /action right 420 × 230/.test(g.metrics),
   (g.metrics.match(/action left [^t]*/) || [''])[0]);
await slide('hpArtWR', 400);
g = await geom();
ck('EXTRA', 'using the linked control again makes them equal',
   g.artL[2] === 400 && g.artR[2] === 400, g.artL[2] + '/' + g.artR[2]);

// THE HELPERS ARE STUDIO STATE AND MUST NOT REACH THE GAME LAYOUT.
const exported = await p.evaluate(() => JSON.stringify(gameLayout()));
ck('EXTRA', 'no helper setting is exported',
   !/groupHeight|rowGap|helpers|linked/i.test(exported),
   (exported.match(/groupHeight|rowGap|helpers|linked/i) || ['none'])[0]);

// AND THE READOUT IS LIVE after a plain drag, not only after a helper.
const live = await p.evaluate(() => {
  S.city.width += 37; render();
  return document.getElementById('metCtl').innerText.replace(/\s+/g, ' ');
});
ck('EXTRA', 'the readout follows an edit made outside the panel',
   live.indexOf('city ' + (await p.evaluate(() => S.city.width))) >= 0,
   (live.match(/city [^a-z]*/) || [''])[0]);

// ONE UNDO PER ADJUSTMENT, tested as a SWEEP. A single input event collapses to one entry
// whether or not the debounce works, so the only way to see the debounce is to move the control
// the way a thumb does: many events, then a pause.
await reset();
const sweep = await p.evaluate(async () => {
  const before = HIST.length;
  const r = document.getElementById('hpCardR');
  for (let v = 150; v <= 190; v++){ r.value = v; r.oninput(); }
  await new Promise(res => setTimeout(res, 600));
  return {added: HIST.length - before, height: S.duties.clerical.card.height};
});
ck('EXTRA', 'a forty-step slider sweep is one undo entry, not forty',
   sweep.added === 1 && sweep.height === 190, JSON.stringify(sweep));
const backOut = await p.evaluate(() => { stepHistory(-1);
  return S.duties.clerical.card.height; });
ck('EXTRA', 'and one undo returns to where the sweep started', backOut === 150, backOut);

// A NEGATIVE GAP IS AN OVERLAP and reads as bad news, not as merely uneven.
await reset();
const neg = await p.evaluate(() => {
  artOf('right').width = 402; render();          // now overlaps Tithe by 17
  const cell = [].slice.call(document.querySelectorAll('#metCtl i'))
                 .filter(i => i.textContent === 'action gaps')[0].nextElementSibling;
  return {text: cell.textContent, cls: cell.className, gaps: rowGaps()};
});
ck('EXTRA', 'a negative action gap is shown in the warning colour',
   neg.cls === 'bad' && neg.gaps[1] < 0, neg.text + ' · class=' + neg.cls);
const pos = await p.evaluate(() => {
  artOf('right').width = 375; render();
  const cell = [].slice.call(document.querySelectorAll('#metCtl i'))
                 .filter(i => i.textContent === 'action gaps')[0].nextElementSibling;
  return cell.className;
});
ck('EXTRA', 'and merely uneven gaps are not', pos === 'mix', pos);

ck('ALL', 'no page or console errors in the whole run', errs.length === 0, errs.slice(0, 3).join(' | '));

await b.close();
const out = R.join('\n') + `\n\n${n - fail}/${n} passed, ${fail} failed.\n`;
if (!process.argv[2]) fs.writeFileSync(path.join(OUT, 'accept42.txt'), out);
console.log(process.argv[2]
  ? out.split('\n').filter(l => l.startsWith('FAIL')).concat(out.trim().split('\n').pop()).join('\n')
  : out);
process.exit(fail ? 1 : 0);
