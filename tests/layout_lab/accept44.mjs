// V4.4: tithe resource tokens. The brief's tests 24-31, in its own order.
import { chromium } from 'playwright';
import path from 'path';
import { fileURLToPath, pathToFileURL } from 'url';
const HERE = path.dirname(fileURLToPath(import.meta.url));
const CHROMIUM = process.env.LAYOUT_LAB_CHROMIUM
  || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
const TOK = process.env.LAYOUT_LAB_TOKENS
  || path.join(HERE, '..', '..', 'ui', 'board_v2', 'tokens', 'resources');
const F = n => path.join(TOK, n);

const b = await chromium.launch({executablePath: CHROMIUM});
const p = await b.newPage({viewport:{width:1900,height:1400}, deviceScaleFactor:1});
const errs = [];
p.on('pageerror', e => errs.push('pageerror: ' + e.message));
p.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text()); });
await p.goto(process.argv[2] || pathToFileURL(path.join(HERE, '..', '..', 'out', 'lab.html')).href);
await p.evaluate(() => localStorage.clear());
await p.reload(); await p.waitForTimeout(450);

let n = 0, fail = 0; const R = [];
function ck(test, name, ok, detail){
  n++; if (!ok) fail++;
  let d = detail === undefined ? undefined : String(detail);
  if (d !== undefined && d.length > 120) d = d.slice(0, 117) + '...';
  R.push((ok?'PASS ':'FAIL ') + test + ' :: ' + name + (d===undefined?'':'   ['+d+']'));
}
const reset = async () => { await p.evaluate(() => localStorage.clear());
                            await p.reload(); await p.waitForTimeout(400);
                            await p.evaluate(() => setView('action'));
                            await p.waitForTimeout(250); };
const loadTokens = async (which) => {
  const inputs = await p.$$('#titheCtl input[data-tok]');
  const names = ['token_wheat.png','token_stone.png','token_silver.png'];
  for (const i of (which || [0,1,2])){
    await inputs[i].setInputFiles(F(names[i]));
    await p.waitForTimeout(420);
  }
};
// geometry of the three rendered tokens, measured off the DOM
const pyramid = () => p.evaluate(() => {
  const slots = [].slice.call(document.querySelectorAll('#titheObj .slot'));
  const card = document.querySelector('[data-kind=tithe]').getBoundingClientRect();
  return slots.map(s => {
    const r = s.getBoundingClientRect();
    const kid = s.firstElementChild.getBoundingClientRect();
    return {slot: Math.round(r.width), cx: Math.round(r.x + r.width/2 - card.x),
            cy: Math.round(r.y + r.height/2 - card.y),
            img: Math.round(kid.width), tag: s.firstElementChild.tagName.toLowerCase(),
            cls: s.firstElementChild.className};
  });
});

try {
await p.evaluate(() => setView('action'));
await p.waitForTimeout(250);

// ============================================================ TEST 24 — NO ICONS
let g = await pyramid();
ck('TEST 24', 'three slots exist with no icons loaded', g.length === 3, g.length);
ck('TEST 24', 'each shows the letter placeholder, not an image',
   g.every(s => s.tag === 'span' && /res/.test(s.cls)), g.map(s => s.tag).join(','));
const letters = await p.evaluate(() =>
  [].slice.call(document.querySelectorAll('#titheObj .res')).map(e => e.textContent));
ck('TEST 24', 'and the letters are W / S / Ag',
   JSON.stringify(letters) === '["W","S","Ag"]', letters.join(','));
const broken = await p.evaluate(() =>
  [].slice.call(document.querySelectorAll('#titheObj img')).length);
ck('TEST 24', 'no image element at all, so nothing can be broken', broken === 0, broken);
// AND THEY ARE ACTUALLY ON SCREEN. Reading textContent proves the letters exist in the DOM,
// which a `display:none` placeholder satisfies perfectly while showing an empty card -- and the
// whole point of the fallback is that the tool stays usable with no assets loaded.
const shown24 = await p.evaluate(() =>
  [].slice.call(document.querySelectorAll('#titheObj .res')).map(e => {
    const r = e.getBoundingClientRect(), c = getComputedStyle(e);
    return {w: Math.round(r.width), h: Math.round(r.height),
            disp: c.display, vis: c.visibility, op: c.opacity};
  }));
ck('TEST 24', 'and every placeholder is really drawn, not just present in the DOM',
   shown24.length === 3 && shown24.every(s => s.w > 0 && s.h > 0 && s.disp !== 'none'
                                          && s.vis !== 'hidden' && +s.op > 0),
   JSON.stringify(shown24[0]));
ck('TEST 24', 'at the stated token size', shown24.every(s => s.w === 38 && s.h === 38),
   shown24.map(s => s.w + 'x' + s.h).join(' '));

// ============================================================ TEST 25 — THREE ICONS
await loadTokens();
g = await pyramid();
ck('TEST 25', 'all three are now images',
   g.every(s => s.tag === 'img'), g.map(s => s.tag).join(','));
const names = await p.evaluate(() => S.tithe.resources.map(r => r.iconName));
ck('TEST 25', 'wheat on top, stone bottom-left, silver bottom-right',
   JSON.stringify(names) === '["token_wheat.png","token_stone.png","token_silver.png"]',
   names.join(' / '));
// THE PNG IS THE WHOLE TOKEN. A disc behind it or a border around it would be a second rim.
const chrome = await p.evaluate(() =>
  [].slice.call(document.querySelectorAll('#titheObj .tok')).map(e => {
    const c = getComputedStyle(e);
    return {bg: c.backgroundImage, bw: c.borderTopWidth, br: c.borderTopLeftRadius,
            bgc: c.backgroundColor};
  }));
ck('TEST 25', 'no background is drawn behind a token',
   chrome.every(c => c.bg === 'none' && /rgba\(0, 0, 0, 0\)|transparent/.test(c.bgc)),
   JSON.stringify(chrome[0]));
ck('TEST 25', 'and no border is drawn around one',
   chrome.every(c => c.bw === '0px'), chrome.map(c => c.bw).join(','));
ck('TEST 25', 'the old brown disc is gone from the card',
   (await p.evaluate(() => document.querySelectorAll('#titheObj .res').length)) === 0);
// state holds keys, not bytes
const keys = await p.evaluate(() => S.tithe.resources.map(r => r.icon));
ck('TEST 25', 'the state holds pool keys', keys.every(k => /^im\d+$/.test(k)), keys.join(','));
ck('TEST 25', 'and no image bytes',
   (await p.evaluate(() => JSON.stringify(S).indexOf('data:image') < 0)));

// ============================================================ TEST 26 — MASTER SIZE
const before26 = await p.evaluate(() => {
  const t = document.querySelector('[data-kind=tithe]').getBoundingClientRect();
  const c = document.querySelector('[data-kind=city]').getBoundingClientRect();
  const a = artOf('right');
  return {tithe: [Math.round(t.width), Math.round(t.height)],
          city: [Math.round(c.x), Math.round(c.width)], art: [a.x, a.width]};
});
await p.evaluate(() => { setTokenSize(70); });
await p.waitForTimeout(300);
g = await pyramid();
const after26 = await p.evaluate(() => {
  const t = document.querySelector('[data-kind=tithe]').getBoundingClientRect();
  const c = document.querySelector('[data-kind=city]').getBoundingClientRect();
  const a = artOf('right');
  return {tithe: [Math.round(t.width), Math.round(t.height)],
          city: [Math.round(c.x), Math.round(c.width)], art: [a.x, a.width]};
});
ck('TEST 26', 'all three slots grew together',
   g.every(s => s.slot === 70), g.map(s => s.slot).join(','));
ck('TEST 26', 'the Tithe box did not resize',
   JSON.stringify(after26.tithe) === JSON.stringify(before26.tithe),
   before26.tithe + ' -> ' + after26.tithe);
ck('TEST 26', 'the City did not move',
   JSON.stringify(after26.city) === JSON.stringify(before26.city));
ck('TEST 26', 'the action row did not move',
   JSON.stringify(after26.art) === JSON.stringify(before26.art));

// ============================================================ TEST 27 — PER-TOKEN SCALE
await p.evaluate(() => { setTokenSize(60); });
await p.waitForTimeout(250);
const centresBefore = (await pyramid()).map(s => s.cx + ',' + s.cy);
await p.evaluate(() => { setTokenScale(0, 110); setTokenScale(1, 90); setTokenScale(2, 100); });
await p.waitForTimeout(300);
g = await pyramid();
ck('TEST 27', 'wheat draws at 66 px', g[0].img === 66, g[0].img);
ck('TEST 27', 'stone at 54 px', g[1].img === 54, g[1].img);
ck('TEST 27', 'silver at 60 px', g[2].img === 60, g[2].img);
ck('TEST 27', 'the slots all stay 60 px', g.every(s => s.slot === 60),
   g.map(s => s.slot).join(','));
// THE WHOLE POINT: scaling one token must not shove its neighbours.
const centresAfter = g.map(s => s.cx + ',' + s.cy);
ck('TEST 27', 'and no token moved a pixel',
   JSON.stringify(centresAfter) === JSON.stringify(centresBefore),
   centresBefore.join(' | ') + '  ->  ' + centresAfter.join(' | '));

// ============================================================ TEST 28 — TOKEN GAP
const g28a = await pyramid();
const imgsBefore = g28a.map(s => s.img).join(',');
await p.evaluate(() => { setTokenGap(24); });
await p.waitForTimeout(300);
const g28b = await pyramid();
const dxBefore = g28a[2].cx - g28a[1].cx, dxAfter = g28b[2].cx - g28b[1].cx;
const dyBefore = g28a[1].cy - g28a[0].cy, dyAfter = g28b[1].cy - g28b[0].cy;
ck('TEST 28', 'the horizontal spacing changed', dxAfter > dxBefore, dxBefore + ' -> ' + dxAfter);
ck('TEST 28', 'the vertical spacing changed too', dyAfter > dyBefore, dyBefore + ' -> ' + dyAfter);
ck('TEST 28', 'the artwork sizes are unchanged', g28b.map(s => s.img).join(',') === imgsBefore,
   imgsBefore + ' -> ' + g28b.map(s => s.img).join(','));
const tithe28 = await p.evaluate(() => [S.tithe.width, S.tithe.height]);
ck('TEST 28', 'the Tithe box is unchanged', JSON.stringify(tithe28) === '[178,184]', tithe28);

// ============================================================ TEST 29 — LAB EXPORT
await reset();
await loadTokens();
const withImg = await p.evaluate(() => JSON.stringify(labSession(true)));
ck('TEST 29', 'a session WITH images carries three token images',
   (withImg.match(/data:image/g) || []).length >= 3,
   (withImg.match(/data:image/g) || []).length + ' data URLs');
const noImg = await p.evaluate(() => JSON.stringify(labSession(false)));
ck('TEST 29', 'a geometry-only session carries none', noImg.indexOf('data:image') < 0);
ck('TEST 29', 'but remembers the filenames', noImg.indexOf('token_wheat.png') > 0);
await reset();
const back = await p.evaluate(t => { importSession(JSON.parse(t));
  return S.tithe.resources.map(r => (r.iconName||'-') + ':' + (haveImage(r.icon)?'bytes':'none'));
}, withImg);
ck('TEST 29', 'importing with images restores all three',
   back.every(x => /bytes$/.test(x)), back.join(' | '));
await reset();
const bare = await p.evaluate(t => { importSession(JSON.parse(t));
  render();
  return {names: S.tithe.resources.map(r => r.iconName),
          loaded: S.tithe.resources.map(r => haveImage(r.icon)),
          letters: [].slice.call(document.querySelectorAll('#titheObj .res')).map(e=>e.textContent)};
}, noImg);
ck('TEST 29', 'a geometry-only import does not crash and keeps the names',
   bare.names[0] === 'token_wheat.png', bare.names.join(','));
ck('TEST 29', 'reports the bytes as missing', bare.loaded.every(x => x === false));
ck('TEST 29', 'and falls back to the letters', JSON.stringify(bare.letters) === '["W","S","Ag"]',
   bare.letters.join(','));

// ============================================================ TEST 30 — OLD SESSION
await reset();
const old = await p.evaluate(() => {
  const d = labSession(false);
  // a V4.2.1 session: resources with no icon fields, and no token settings at all
  d.state.tithe.resources = [{key:'W',name:'Wheat'},{key:'S',name:'Stone'},{key:'Ag',name:'Silver'}];
  delete d.state.tithe.tokenSize;
  delete d.state.tithe.tokenGap;
  return JSON.stringify(d);
});
const migrated = await p.evaluate(t => { importSession(JSON.parse(t));
  return {res: S.tithe.resources.map(r => [r.icon, r.iconName, r.scale]),
          size: S.tithe.tokenSize, gap: S.tithe.tokenGap,
          letters: [].slice.call(document.querySelectorAll('#titheObj .res')).map(e=>e.textContent)};
}, old);
ck('TEST 30', 'an old session gains icon = null',
   migrated.res.every(r => r[0] === null), JSON.stringify(migrated.res[0]));
ck('TEST 30', 'iconName = null', migrated.res.every(r => r[1] === null));
ck('TEST 30', 'scale = 100', migrated.res.every(r => r[2] === 100));
ck('TEST 30', 'tithe gains a token size', migrated.size === 38, migrated.size);
ck('TEST 30', 'and a token gap', migrated.gap === 9, migrated.gap);
ck('TEST 30', 'the letters still show', JSON.stringify(migrated.letters) === '["W","S","Ag"]',
   migrated.letters.join(','));

// ---- §17: imported numbers are not trusted
const wild = await p.evaluate(() => {
  const d = labSession(false);
  d.state.tithe.tokenSize = 4000; d.state.tithe.tokenGap = -50;
  d.state.tithe.resources.forEach(r => { r.scale = 9000; });
  importSession(JSON.parse(JSON.stringify(d)));
  return {size: S.tithe.tokenSize, gap: S.tithe.tokenGap,
          scales: S.tithe.resources.map(r => r.scale)};
});
ck('TEST 30', 'a hand-edited size is clamped', wild.size === 100, wild.size);
ck('TEST 30', 'a negative gap is clamped to zero', wild.gap === 0, wild.gap);
ck('TEST 30', 'and a wild scale to 140', wild.scales.every(s => s === 140), wild.scales.join(','));
// a gap of zero is a real choice and must survive
const zero = await p.evaluate(() => {
  const d = labSession(false); d.state.tithe.tokenGap = 0;
  importSession(JSON.parse(JSON.stringify(d)));
  return S.tithe.tokenGap;
});
ck('TEST 30', 'but a deliberate gap of 0 survives the round trip', zero === 0, zero);

// ============================================================ §22 — PRODUCTION EXPORT
await reset();
await loadTokens();
const game = await p.evaluate(() => JSON.stringify(gameLayout()));
const gt = await p.evaluate(() => gameLayout().tithe);
ck('§22', 'the export carries tokenSize and tokenGap',
   typeof gt.tokenSize === 'number' && typeof gt.tokenGap === 'number',
   gt.tokenSize + ' / ' + gt.tokenGap);
ck('§22', 'and each resource carries iconName and scale',
   gt.resources.every(r => 'iconName' in r && 'scale' in r),
   JSON.stringify(gt.resources[0]));
ck('§22', 'the filename is there', gt.resources[0].iconName === 'token_wheat.png',
   gt.resources[0].iconName);
ck('§22', 'no image bytes', game.indexOf('data:image') < 0 && game.indexOf('blob:') < 0);
ck('§22', 'and no image-pool key', !/"icon"\s*:/.test(game));

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
