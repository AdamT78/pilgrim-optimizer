// V4.3: the duty action art workflow. The brief's tests C-K, in its own order, plus the
// architectural claims the panel would otherwise be free to quietly break.
import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';
import { fileURLToPath, pathToFileURL } from 'url';
const HERE = path.dirname(fileURLToPath(import.meta.url));
const CHROMIUM = process.env.LAYOUT_LAB_CHROMIUM
  || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
const PIETY = path.join(HERE, 'clerical_gain_piety_v01.png');
const COINS = path.join(HERE, 'clerical_gain_coins_v01.png');

const b = await chromium.launch({executablePath: CHROMIUM});
const p = await b.newPage({viewport:{width:1900,height:1500}, deviceScaleFactor:1});
const errs = [];
p.on('pageerror', e => errs.push('pageerror: ' + e.message));
p.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text()); });

const PAGE = process.argv[2] || pathToFileURL(path.join(HERE, 'lab.html')).href;
await p.goto(PAGE);
await p.evaluate(() => localStorage.clear());
await p.reload();
await p.waitForTimeout(500);

let n = 0, fail = 0;
const R = [];
function ck(test, name, ok, detail){
  n++; if (!ok) fail++;
  // TRUNCATED. A failing assertion about image bytes would otherwise print the bytes -- a 3 MB
  // data URL into the report, which took the whole run down and read as a crash rather than as
  // the clean catch it was.
  let d = detail === undefined ? undefined : String(detail);
  if (d !== undefined && d.length > 120) d = d.slice(0, 117) + '...';
  R.push((ok ? 'PASS ' : 'FAIL ') + test + ' :: ' + name
         + (d === undefined ? '' : '   [' + d + ']'));
}
const reset = async () => { await p.evaluate(() => localStorage.clear());
                            await p.reload(); await p.waitForTimeout(400); };
const press = async (label) => {
  await p.evaluate(l => {
    const el = [].slice.call(document.querySelectorAll('#artCtl button'))
                 .filter(x => x.textContent.trim().toLowerCase() === l)[0];
    if (!el) throw new Error('no button: ' + l);
    el.click();
  }, label);
  await p.waitForTimeout(250);
};
const pairInput = async (slot) => (await p.$$('#artCtl input[data-pair]'))[slot === 'actionA' ? 0 : 1];
const loadPair = async (aFile, bFile) => {
  if (aFile) await (await pairInput('actionA')).setInputFiles(aFile);
  if (bFile) await (await pairInput('actionB')).setInputFiles(bFile);
  await p.waitForTimeout(200);
  await press('load pair');
  await p.waitForTimeout(700);
};
const art = () => p.evaluate(() => ({
  aName: S.duties.clerical.actionA.scenicName, aKey: S.duties.clerical.actionA.scenic,
  bName: S.duties.clerical.actionB.scenicName, bKey: S.duties.clerical.actionB.scenic,
  view: S.view, preview: S.previewDuty, selected: S.selectedDuty, hist: HIST.length,
}));

try {

// =============================================================================================
// TEST C — IMPORT THE CLERICAL PAIR
// =============================================================================================
await loadPair(PIETY, COINS);
let a = await art();
ck('TEST C', 'Action A is Gain Piety', a.aName === 'clerical_gain_piety_v01.png', a.aName);
ck('TEST C', 'Action B is Gain Coins', a.bName === 'clerical_gain_coins_v01.png', a.bName);
ck('TEST C', 'and they are not reversed',
   a.aName.indexOf('piety') > 0 && a.bName.indexOf('coins') > 0);
// THE POOL, NOT THE STATE. A data URL in here would bloat every undo snapshot and every save.
ck('TEST C', 'the state holds pool keys, not image bytes',
   /^im\d+$/.test(a.aKey) && /^im\d+$/.test(a.bKey), a.aKey + ' / ' + a.bKey);
const bytesInState = await p.evaluate(() => JSON.stringify(S).indexOf('data:image') < 0);
ck('TEST C', 'no data: URL anywhere in the state', bytesInState);
const shown = await p.evaluate(() => [].slice.call(document.querySelectorAll('#stage img'))
  .filter(i => i.src.indexOf('data:image') === 0).length);
ck('TEST C', 'both pictures actually render on the stage', shown >= 2, shown + ' images');
// AND NOT BY POSITION. The brief forbids duty.leftImage; assert the shape, not just behaviour.
const noSideFields = await p.evaluate(() => {
  const d = S.duties.clerical;
  return !('leftImage' in d) && !('rightImage' in d)
      && 'scenic' in d.actionA && 'scenic' in d.actionB;
});
ck('TEST C', 'artwork belongs to the action, not to a side', noSideFields);

// =============================================================================================
// TEST I — DIMENSION READOUT (checked here while the pair is loaded)
// =============================================================================================
const readout = await p.evaluate(() => document.getElementById('artCtl').innerText.replace(/\s+/g,' '));
ck('TEST I', 'the image size is reported', /image 1120 × 560/.test(readout),
   (readout.match(/image [^·]*· ratio [\d.]+/) || [''])[0]);
ck('TEST I', 'with its ratio to three places', /ratio 2\.000/.test(readout));
ck('TEST I', 'the slot ratio is reported too', /slot 375 × 184 · ratio 2\.038/.test(readout),
   (readout.match(/slot [^·]*· ratio [\d.]+/) || [''])[0]);
// 2.000 against 2.038 is under 2% -- it must NOT read as a problem.
ck('TEST I', 'a 2% difference reads as minimal, not a warning',
   /cover crop minimal/.test(readout) && !/substantial/.test(readout),
   (readout.match(/cover crop \w+/) || [''])[0]);
const warnColoured = await p.evaluate(() =>
  [].slice.call(document.querySelectorAll('#artCtl .hint'))
    .filter(e => /cover crop/.test(e.textContent) && /warn/.test(e.getAttribute('style') || '')).length);
ck('TEST I', 'and nothing is coloured as a warning', warnColoured === 0, warnColoured);

// A SLOT THE ART DOES NOT FIT. 2.000 art in a 2.16 slot loses 7.4% of its width -- "slight",
// and not a warning. Measuring the ratio DIFFERENCE instead gives 0.16 and calls the same
// picture substantial, which is why the two readings are distinguished here rather than only at
// the default slot, where they happen to agree.
await p.evaluate(() => { const e = artOf('left'); e.width = 432; e.height = 200;
                         render(); panels(); });
await p.waitForTimeout(200);
const odd = await p.evaluate(() => document.getElementById('artCtl').innerText.replace(/\s+/g,' '));
ck('TEST I', 'a 2.00 image in a 2.16 slot reads as slight',
   /slot 432 × 200 · ratio 2\.160 · cover crop slight/.test(odd),
   (odd.match(/slot 432[^·]*· ratio [\d.]+ · cover crop \w+/) || [''])[0]);
const oddWarn = await p.evaluate(() =>
  [].slice.call(document.querySelectorAll('#artCtl .hint'))
    .filter(e => /cover crop/.test(e.textContent) && /warn/.test(e.getAttribute('style') || '')).length);
ck('TEST I', 'and is still not coloured as a warning', oddWarn === 0, oddWarn);

// =============================================================================================
// TEST D — READY PREVIEW
// =============================================================================================
await reset();
await p.evaluate(() => setView('ready'));
await loadPair(PIETY, COINS);
a = await art();
ck('TEST D', 'READY: the imported duty opens as a preview', a.preview === 'clerical', a.preview);
const readyTithe = await p.evaluate(() => !!document.querySelector('[data-kind=tithe]'));
ck('TEST D', 'and Tithe does not appear merely because art was imported', !readyTithe);
const readyArt = await p.evaluate(() => [].slice.call(document.querySelectorAll('#stage img'))
  .filter(i => i.src.indexOf('data:image') === 0).length);
ck('TEST D', 'both scenic images show', readyArt >= 2, readyArt);

// =============================================================================================
// TEST E — SOWING PREVIEW
// =============================================================================================
await reset();
const sowBefore = await p.evaluate(() => { setView('sow'); return S.inHand.count; });
await loadPair(PIETY, null);
a = await art();
ck('TEST E', 'SOWING: the duty previews', a.preview === 'clerical', a.preview);
const sowAfter = await p.evaluate(() => S.inHand.count);
ck('TEST E', 'acolytes in hand are untouched', sowAfter === sowBefore,
   sowBefore + ' -> ' + sowAfter);
const sowTithe = await p.evaluate(() => !!document.querySelector('[data-kind=tithe]'));
ck('TEST E', 'Tithe stays hidden', !sowTithe);

// =============================================================================================
// TEST F — ACTION SELECTION
// =============================================================================================
await reset();
// START SOMEWHERE ELSE. selectedDuty defaults to Clerical, so importing Clerical and then
// asserting the selection is Clerical would pass without the import having done anything.
await p.evaluate(() => { setView('action'); S.selectedDuty = 'produce'; S.previewDuty = null;
                         render(); panels(); });
const titheBefore = await p.evaluate(() => {
  const t = document.querySelector('[data-kind=tithe]');
  return t ? t.style.left + ',' + t.style.top + ',' + t.style.width : null;
});
await loadPair(PIETY, COINS);
a = await art();
ck('TEST F', 'ACTION: the imported duty becomes the selection, from another duty',
   a.selected === 'clerical', 'produce -> ' + a.selected);
// A SELECTION, NOT A PREVIEW. In ACTION SELECTION the duty's two actions are the live choice on
// screen, so opening a preview here would be the wrong gesture entirely.
ck('TEST F', 'and it is a selection rather than a preview', !a.preview, a.preview);
const slots = await p.evaluate(() => {
  const out = {};
  ['left', 'right'].forEach(side => {
    const e = artOf(side), act = S.duties[S.selectedDuty][e.slot];
    out[side] = {slot: e.slot, name: act.scenicName};
  });
  return out;
});
ck('TEST F', 'the LEFT slot shows Action A, Gain Piety',
   slots.left.slot === 'actionA' && /piety/.test(slots.left.name || ''),
   slots.left.slot + ' / ' + slots.left.name);
ck('TEST F', 'the RIGHT slot shows Action B, Gain Coins',
   slots.right.slot === 'actionB' && /coins/.test(slots.right.name || ''),
   slots.right.slot + ' / ' + slots.right.name);
const titheAfter = await p.evaluate(() => {
  const t = document.querySelector('[data-kind=tithe]');
  return t ? t.style.left + ',' + t.style.top + ',' + t.style.width : null;
});
ck('TEST F', 'Tithe behaves exactly as before', titheAfter === titheBefore && titheAfter !== null,
   titheBefore + ' -> ' + titheAfter);

// =============================================================================================
// TEST G — PARTIAL UPDATE
// =============================================================================================
await reset();
await loadPair(PIETY, COINS);
const before = await art();
// replace ONLY Action A; Action B's field is left empty and must be left alone
await loadPair(COINS, null);
const after = await art();
ck('TEST G', 'Action A changed', after.aName === 'clerical_gain_coins_v01.png'
   && after.aKey !== before.aKey, before.aKey + ' -> ' + after.aKey);
ck('TEST G', 'Action B is untouched, key for key',
   after.bKey === before.bKey && after.bName === before.bName,
   before.bKey + ' -> ' + after.bKey);
ck('TEST G', 'an empty file field is never read as "clear"', after.bName !== null, after.bName);

// =============================================================================================
// TEST H — CLEAR, AND UNDO
// =============================================================================================
await reset();
await loadPair(PIETY, COINS);
const preClear = await art();
await press('clear action b');
const cleared = await art();
ck('TEST H', 'Action B is cleared', cleared.bKey === null && cleared.bName === null,
   cleared.bKey + ' / ' + cleared.bName);
ck('TEST H', 'Action A is intact',
   cleared.aKey === preClear.aKey && cleared.aName === preClear.aName, cleared.aName);
await p.evaluate(() => stepHistory(-1));
await p.waitForTimeout(250);
const undone = await art();
ck('TEST H', 'undo restores Action B',
   undone.bKey === preClear.bKey && undone.bName === preClear.bName,
   undone.bName);
ck('TEST H', 'and leaves Action A where it was', undone.aKey === preClear.aKey);

// ONE UNDO FOR A PAIR, not two.
await reset();
const histBefore = (await art()).hist;
await loadPair(PIETY, COINS);
const histAfter = (await art()).hist;
ck('TEST H', 'loading both files is ONE undo entry', histAfter - histBefore === 1,
   histBefore + ' -> ' + histAfter);
await p.evaluate(() => stepHistory(-1));
await p.waitForTimeout(250);
const back = await art();
ck('TEST H', 'and one undo takes both back', back.aName === null && back.bName === null,
   back.aName + ' / ' + back.bName);

// =============================================================================================
// TEST J — LAB SESSION ROUND TRIP
// =============================================================================================
await reset();
await loadPair(PIETY, COINS);
const withImages = await p.evaluate(() => JSON.stringify(labSession(true)));
ck('TEST J', 'a session WITH images carries the bytes', withImages.indexOf('data:image') > 0,
   withImages.length + ' chars');
const withoutImages = await p.evaluate(() => JSON.stringify(labSession(false)));
ck('TEST J', 'a session WITHOUT images carries none', withoutImages.indexOf('data:image') < 0,
   withoutImages.length + ' chars');
ck('TEST J', 'but still remembers the filenames',
   withoutImages.indexOf('clerical_gain_piety_v01.png') > 0);
// wipe everything, then import
await reset();
const restored = await p.evaluate(txt => {
  importSession(JSON.parse(txt));
  return {a: S.duties.clerical.actionA.scenicName, b: S.duties.clerical.actionB.scenicName,
          aLoaded: haveImage(S.duties.clerical.actionA.scenic),
          bLoaded: haveImage(S.duties.clerical.actionB.scenic)};
}, withImages);
ck('TEST J', 'importing restores both names',
   restored.a === 'clerical_gain_piety_v01.png' && restored.b === 'clerical_gain_coins_v01.png',
   restored.a + ' / ' + restored.b);
ck('TEST J', 'and both pictures, with no re-selection',
   restored.aLoaded && restored.bLoaded, restored.aLoaded + ' / ' + restored.bLoaded);
await p.waitForTimeout(300);
const drawn = await p.evaluate(() => { render(); return [].slice.call(
  document.querySelectorAll('#stage img')).filter(i => i.src.indexOf('data:image') === 0).length; });
ck('TEST J', 'and they draw', drawn >= 2, drawn);

// =============================================================================================
// TEST K — NO IMAGE BYTES IN THE PRODUCTION EXPORT
// =============================================================================================
await reset();
await loadPair(PIETY, COINS);
const game = await p.evaluate(() => JSON.stringify(gameLayout()));
ck('TEST K', 'no data: URL in the game layout', game.indexOf('data:image') < 0);
ck('TEST K', 'no blob: URL either', game.indexOf('blob:') < 0);
ck('TEST K', 'the IMAGES pool is not exported', game.indexOf('"IMAGES"') < 0
   && !/"im\d+"\s*:/.test(game));
ck('TEST K', 'and it stays small', game.length < 20000, game.length + ' chars');
// THE FILENAME IS DELIBERATELY NOT THERE. The brief says production metadata MAY identify the
// artwork by scenicName; an existing guard says it must not, pinning each exported action to
// exactly {name, shortLabel} and banning the string "scenic" outright. "May" does not override a
// decision already made and tested, so the export keeps naming the ACTION and leaves the file to
// the repository. What production needs to resolve art is the action identity, and that is here.
ck('TEST K', 'the action is still identifiable by name',
   game.indexOf('Devotion') > 0 && game.indexOf('Silversmith') > 0
     && game.indexOf('Gain X piety') > 0 && game.indexOf('Gain X silver') > 0,
   'names and effects both present');
const exported = await p.evaluate(() => Object.keys(gameLayout().duties.clerical.actionA).sort());
ck('TEST K', 'and each action exports exactly name and shortLabel',
   JSON.stringify(exported) === '["name","shortLabel"]', exported.join(','));
ck('TEST K', 'no artwork filename leaks into production',
   game.indexOf('clerical_gain_piety_v01.png') < 0 && game.indexOf('scenic') < 0);

ck('ALL', 'no page or console errors in the whole run', errs.length === 0, errs.slice(0,3).join(' | '));

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
