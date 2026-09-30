// V4.4: tithe resource tokens, arranged on an invisible equilateral triangle.
//
// The arrangement started as a flex pyramid with a gap control and a per-resource scale control,
// and both were wrong for the same reason: a gap is the space BETWEEN two boxes, so it could not
// be changed without also changing what "bigger" meant, and the three controls fought each other.
// What is tested here is the replacement -- two numbers, size and spread, that do not interact --
// and the two things that came out with the old model: the per-resource optical correction (the
// artwork was corrected instead) and the token-gap control.
import { chromium } from 'playwright';
import path from 'path';
import { fileURLToPath, pathToFileURL } from 'url';
const HERE = path.dirname(fileURLToPath(import.meta.url));
const CHROMIUM = process.env.LAYOUT_LAB_CHROMIUM
  || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
// The suite loads the REPOSITORY'S OWN token artwork, not a copy kept beside the tests: the
// three PNGs were re-exported to match each other optically, and a private copy would go on
// passing after somebody replaced them.
const TOK = process.env.LAYOUT_LAB_TOKENS
  || path.join(HERE, '..', '..', 'ui', 'board_v2', 'tokens', 'resources');
const F = n => path.join(TOK, n);

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
// GEOMETRY OF THE THREE RENDERED TOKENS, measured off the DOM and divided back out of the stage's
// scale() transform. Every rect the browser hands back is already multiplied by it, and the
// factor depends on the viewport -- so readings taken raw agree with the controls at one window
// size and quietly disagree at another. Dividing it out means these numbers can be compared with
// the state directly, whatever the window is.
const pyramid = () => p.evaluate(() => {
  const st = document.getElementById('stage');
  const k = st.getBoundingClientRect().width / st.offsetWidth;
  const slots = [].slice.call(document.querySelectorAll('#titheObj .slot'));
  const card = document.querySelector('[data-kind=tithe]').getBoundingClientRect();
  return slots.map(s => {
    const r = s.getBoundingClientRect();
    const kid = s.firstElementChild.getBoundingClientRect();
    return {slot: Math.round(r.width / k), cx: (r.x + r.width/2 - card.x) / k,
            cy: (r.y + r.height/2 - card.y) / k,
            img: Math.round(kid.width / k), tag: s.firstElementChild.tagName.toLowerCase(),
            cls: s.firstElementChild.className};
  });
});
// The three side lengths of the triangle the centres stand on.
const sidesOf = g => {
  const d = (a, c) => Math.hypot(a.cx - c.cx, a.cy - c.cy);
  return [d(g[0], g[1]), d(g[1], g[2]), d(g[2], g[0])];
};
const equilateral = g => { const s = sidesOf(g); return Math.max(...s) - Math.min(...s) < 0.75; };
const at = g => g.map(s => s.cx.toFixed(2) + ',' + s.cy.toFixed(2)).join(' | ');

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
const shown24 = await p.evaluate(() => {
  const st = document.getElementById('stage');
  const k = st.getBoundingClientRect().width / st.offsetWidth;
  return [].slice.call(document.querySelectorAll('#titheObj .res')).map(e => {
    const r = e.getBoundingClientRect(), c = getComputedStyle(e);
    return {w: Math.round(r.width / k), h: Math.round(r.height / k),
            disp: c.display, vis: c.visibility, op: c.opacity};
  });
});
ck('TEST 24', 'and every placeholder is really drawn, not just present in the DOM',
   shown24.length === 3 && shown24.every(s => s.w > 0 && s.h > 0 && s.disp !== 'none'
                                          && s.vis !== 'hidden' && +s.op > 0),
   JSON.stringify(shown24[0]));
ck('TEST 24', 'at the stated token size', shown24.every(s => s.w === 38 && s.h === 38),
   shown24.map(s => s.w + 'x' + s.h).join(' '));

// ============================================================ TEST 24b — THE TRIANGLE
// The arrangement is the claim, so it is measured rather than described: three equal sides, apex
// up, base level, apex centred over it. None of this is asserted from the markup -- it is read
// back out of where the browser actually put the three boxes.
const tri = await pyramid();
const s24 = sidesOf(tri);
ck('TEST 24b', 'the three centres stand on an equilateral triangle', equilateral(tri),
   s24.map(x => x.toFixed(2)).join(' / '));
ck('TEST 24b', 'its side is the spread the state holds',
   Math.abs(s24[0] - (await p.evaluate(() => tokenSpread()))) < 0.75, s24[0].toFixed(2));
ck('TEST 24b', 'apex up: wheat sits above the other two',
   tri[0].cy < tri[1].cy - 1 && tri[0].cy < tri[2].cy - 1,
   tri.map(s => s.cy.toFixed(1)).join(' / '));
ck('TEST 24b', 'stone and silver are level with each other',
   Math.abs(tri[1].cy - tri[2].cy) < 0.5);
ck('TEST 24b', 'and the apex is centred over them',
   Math.abs(tri[0].cx - (tri[1].cx + tri[2].cx) / 2) < 0.5);
// AND THE WHOLE ARRANGEMENT IS CENTRED IN THE CARD. Everything above is relative -- equal sides,
// level base, apex over the middle -- and a triangle measured from the wrong origin satisfies
// every one of them while sitting in a corner. This is the only check here that says where it
// is, rather than what shape it is.
const card24 = await p.evaluate(() => {
  const st = document.getElementById('stage');
  const k = st.getBoundingClientRect().width / st.offsetWidth;
  const c = document.querySelector('[data-kind=tithe]').getBoundingClientRect();
  return {w: c.width / k, h: c.height / k};
});
const mid24 = {x: tri.reduce((a, s) => a + s.cx, 0) / 3, y: tri.reduce((a, s) => a + s.cy, 0) / 3};
ck('TEST 24b', 'the arrangement is horizontally centred in the card',
   Math.abs(mid24.x - card24.w / 2) < 1,
   mid24.x.toFixed(1) + ' vs ' + (card24.w / 2).toFixed(1));
// Not the card's own middle: the caption is reserved space at the bottom, so the tokens are
// centred in what is left above it.
ck('TEST 24b', 'and sits above the middle, in the space the caption leaves',
   mid24.y < card24.h / 2 && mid24.y > card24.h * 0.25,
   mid24.y.toFixed(1) + ' of ' + card24.h.toFixed(1));

// ============================================================ TEST 25 — THREE ICONS
await loadTokens();
g = await pyramid();
ck('TEST 25', 'all three are now images',
   g.every(s => s.tag === 'img'), g.map(s => s.tag).join(','));
const names = await p.evaluate(() => S.tithe.resources.map(r => r.iconName));
ck('TEST 25', 'wheat on top, stone bottom-left, silver bottom-right',
   JSON.stringify(names) === '["token_wheat.png","token_stone.png","token_silver.png"]',
   names.join(' / '));
ck('TEST 25', 'and the artwork is arranged the same way the letters were', equilateral(g),
   sidesOf(g).map(x => x.toFixed(2)).join(' / '));
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
const centres26 = await pyramid();
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
// THE POINT OF THE TRIANGLE. Under the old flex rows, growing a token also pushed its neighbours
// away, because the only spacing available was the gap between boxes. Here the centres are the
// vertices and the size has nothing to do with them.
const moved26 = centres26.map((c, i) => Math.hypot(c.cx - g[i].cx, c.cy - g[i].cy));
ck('TEST 26', 'and not one centre moved: size does not spread them',
   Math.max(...moved26) < 0.75,
   'worst ' + Math.max(...moved26).toFixed(3) + ' px · ' + at(centres26) + ' -> ' + at(g));
ck('TEST 26', 'the triangle is still equilateral at the larger size', equilateral(g),
   sidesOf(g).map(x => x.toFixed(2)).join(' / '));
ck('TEST 26', 'and at 70 px on a 47 px side they are free to overlap',
   sidesOf(g)[0] < g[0].slot, sidesOf(g)[0].toFixed(1) + ' < ' + g[0].slot);
// AND AGAIN PAST THE EDGE OF THE CARD, which is where the interesting version of this fails.
// At 70 px the arrangement still fits, so a container sized to the whole thing rather than to
// the triangle stays centred and nothing drifts; at 160 px it overflows, the flex column gives
// up on centring it and pins it to one edge, and the tokens slide while you scale them. The test
// has to reach the size where the difference shows.
await p.evaluate(() => { setTokenSize(160); });
await p.waitForTimeout(300);
const huge = await pyramid();
const over = await p.evaluate(() => tokenOverflow());
ck('TEST 26', 'at the top of the range the arrangement really does outgrow the card', over > 0,
   over + ' px over');
const movedHuge = centres26.map((c, i) => Math.hypot(c.cx - huge[i].cx, c.cy - huge[i].cy));
ck('TEST 26', 'and the centres still have not moved, overflowing or not',
   Math.max(...movedHuge) < 0.75,
   'worst ' + Math.max(...movedHuge).toFixed(3) + ' px · ' + at(centres26) + ' -> ' + at(huge));
ck('TEST 26', 'the Tithe box still did not resize to hide it',
   JSON.stringify(await p.evaluate(() => [S.tithe.width, S.tithe.height]))
     === JSON.stringify(before26.tithe));

// ============================================================ TEST 27 — ONE SIZE, NOT THREE
// There is no per-resource correction any more, and its absence is part of the design rather than
// an omission: silver read about a ninth smaller than the other two because its PNG carried more
// transparent margin, and a slider in the studio would have papered over a fault in the artwork
// that the production pipeline would then have had to reproduce. The three masters were
// re-exported to the same disc fraction instead.
await p.evaluate(() => { setTokenSize(60); });
await p.waitForTimeout(250);
g = await pyramid();
ck('TEST 27', 'all three slots are the same size',
   g.every(s => s.slot === 60), g.map(s => s.slot).join(','));
ck('TEST 27', 'and all three pictures are drawn at that size',
   g.every(s => s.img === 60), g.map(s => s.img).join(','));
const noScale = await p.evaluate(() => ({
  fn: typeof window.setTokenScale,
  ctl: document.querySelectorAll('#titheCtl [data-tsc], #titheCtl [data-tscr]').length,
  state: (S.tithe.resources || []).filter(r => 'scale' in r).length}));
ck('TEST 27', 'there is no per-resource scale control in the panel', noScale.ctl === 0,
   noScale.ctl + ' found');
ck('TEST 27', 'no per-resource scale function', noScale.fn === 'undefined', noScale.fn);
ck('TEST 27', 'and no per-resource scale left in the state', noScale.state === 0, noScale.state);

// ============================================================ TEST 28 — TOKEN SPREAD
const g28a = await pyramid();
const imgsBefore = g28a.map(s => s.img).join(',');
await p.evaluate(() => { setTokenSpread(120); });
await p.waitForTimeout(300);
const g28b = await pyramid();
const dxBefore = g28a[2].cx - g28a[1].cx, dxAfter = g28b[2].cx - g28b[1].cx;
const dyBefore = g28a[1].cy - g28a[0].cy, dyAfter = g28b[1].cy - g28b[0].cy;
ck('TEST 28', 'the horizontal spacing changed', dxAfter > dxBefore,
   dxBefore.toFixed(1) + ' -> ' + dxAfter.toFixed(1));
ck('TEST 28', 'the vertical spacing changed too', dyAfter > dyBefore,
   dyBefore.toFixed(1) + ' -> ' + dyAfter.toFixed(1));
ck('TEST 28', 'one control drives both axes, because it is the side of a triangle',
   equilateral(g28b), sidesOf(g28b).map(x => x.toFixed(2)).join(' / '));
ck('TEST 28', 'the side IS the number typed', Math.abs(sidesOf(g28b)[0] - 120) < 0.75,
   sidesOf(g28b)[0].toFixed(2));
ck('TEST 28', 'the artwork sizes are unchanged', g28b.map(s => s.img).join(',') === imgsBefore,
   imgsBefore + ' -> ' + g28b.map(s => s.img).join(','));
const tithe28 = await p.evaluate(() => [S.tithe.width, S.tithe.height]);
ck('TEST 28', 'the Tithe box is unchanged', JSON.stringify(tithe28) === '[178,184]', tithe28);
// SPREAD 0 IS A REAL ARRANGEMENT, not an error: three tokens concentric on one point. It is the
// bottom of the control's range, so it has to draw.
await p.evaluate(() => { setTokenSpread(0); });
await p.waitForTimeout(250);
const g28z = await pyramid();
ck('TEST 28', 'a spread of 0 stacks all three on one point',
   Math.max(...sidesOf(g28z)) < 0.5, sidesOf(g28z).map(x => x.toFixed(3)).join(' / '));
ck('TEST 28', 'and they are still drawn at full size there',
   g28z.every(s => s.slot === 60), g28z.map(s => s.slot).join(','));

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

// ============================================================ TEST 30 — OLD SESSIONS
await reset();
const old = await p.evaluate(() => {
  const d = labSession(false);
  // a V4.2.1 session: resources with no icon fields, and no token settings at all
  d.state.tithe.resources = [{key:'W',name:'Wheat'},{key:'S',name:'Stone'},{key:'Ag',name:'Silver'}];
  delete d.state.tithe.tokenSize;
  delete d.state.tithe.tokenSpread;
  return JSON.stringify(d);
});
const migrated = await p.evaluate(t => { importSession(JSON.parse(t));
  return {res: S.tithe.resources.map(r => [r.icon, r.iconName, 'scale' in r]),
          size: S.tithe.tokenSize, spread: S.tithe.tokenSpread,
          letters: [].slice.call(document.querySelectorAll('#titheObj .res')).map(e=>e.textContent)};
}, old);
ck('TEST 30', 'an old session gains icon = null',
   migrated.res.every(r => r[0] === null), JSON.stringify(migrated.res[0]));
ck('TEST 30', 'iconName = null', migrated.res.every(r => r[1] === null));
ck('TEST 30', 'and no per-resource scale is invented for it',
   migrated.res.every(r => r[2] === false));
ck('TEST 30', 'tithe gains a token size', migrated.size === 38, migrated.size);
ck('TEST 30', 'and a token spread', migrated.spread === 47, migrated.spread);
ck('TEST 30', 'the letters still show', JSON.stringify(migrated.letters) === '["W","S","Ag"]',
   migrated.letters.join(','));

// ---- a session saved by the FLEX build carries tokenGap, which means something else -----------
// tokenGap was the space between two token BOXES; tokenSpread is the distance between two token
// CENTRES. They differ by exactly one token, so the arrangement a V4.4 session was saved at can
// be recovered rather than reset -- and a session that simply dropped the old field would silently
// snap back to the default the next time it was opened.
const gapped = await p.evaluate(() => {
  const d = labSession(false);
  d.state.tithe.tokenSize = 50;
  d.state.tithe.tokenGap = 16;              // boxes 50 px wide, 16 px apart -> centres 66 apart
  delete d.state.tithe.tokenSpread;
  importSession(JSON.parse(JSON.stringify(d)));
  return {size: S.tithe.tokenSize, spread: S.tithe.tokenSpread,
          gapGone: !('tokenGap' in S.tithe)};
});
ck('TEST 30', 'a pre-triangle session keeps the size it was saved at',
   gapped.size === 50, gapped.size);
ck('TEST 30', 'its gap becomes the equivalent spread, size + gap', gapped.spread === 66,
   gapped.spread + ' (wanted 50 + 16)');
ck('TEST 30', 'and the old field is not carried forward', gapped.gapGone);
// The per-resource scale goes the same way, and it has to be tested on a file that HAS one:
// every other fixture here predates it, so nothing in them could tell a build that strips it
// from one that carries it along forever in every session it writes.
const scaled = await p.evaluate(() => {
  const d = labSession(false);
  d.state.tithe.resources.forEach(function(r){ r.scale = 130; });
  importSession(JSON.parse(JSON.stringify(d)));
  return {left: S.tithe.resources.filter(r => 'scale' in r).length,
          saved: JSON.stringify(labSession(false)).indexOf('"scale"')};
});
ck('TEST 30', 'a session carrying the old per-resource scale has it stripped',
   scaled.left === 0, scaled.left + ' still there');
ck('TEST 30', 'so it is not written back out again', scaled.saved < 0, scaled.saved);
const measuredMigration = await p.evaluate(() => {
  const st = document.getElementById('stage');
  const k = st.getBoundingClientRect().width / st.offsetWidth;
  const c = [].slice.call(document.querySelectorAll('#titheObj .slot')).map(s => {
    const r = s.getBoundingClientRect();
    return [(r.x + r.width/2)/k, (r.y + r.height/2)/k];
  });
  return Math.hypot(c[1][0]-c[2][0], c[1][1]-c[2][1]);
});
ck('TEST 30', 'and the migrated session really draws at that spread',
   Math.abs(measuredMigration - 66) < 0.75, measuredMigration.toFixed(2));

// ---- §17: imported numbers are not trusted
const wild = await p.evaluate(() => {
  const d = labSession(false);
  d.state.tithe.tokenSize = 4000; d.state.tithe.tokenSpread = -50;
  importSession(JSON.parse(JSON.stringify(d)));
  return {size: S.tithe.tokenSize, spread: S.tithe.tokenSpread};
});
const bounds = await p.evaluate(() => ({size: HELPERS.tokenSize, spread: HELPERS.tokenSpread}));
ck('TEST 30', 'a hand-edited size is clamped to the top of its range',
   wild.size === bounds.size[1], wild.size + ' vs ' + bounds.size[1]);
ck('TEST 30', 'a negative spread is clamped to the bottom of its range',
   wild.spread === bounds.spread[0], wild.spread + ' vs ' + bounds.spread[0]);
// a spread of zero is a real choice and must survive
const zero = await p.evaluate(() => {
  const d = labSession(false); d.state.tithe.tokenSpread = 0;
  importSession(JSON.parse(JSON.stringify(d)));
  return S.tithe.tokenSpread;
});
ck('TEST 30', 'but a deliberate spread of 0 survives the round trip', zero === 0, zero);

// ============================================================ §22 — PRODUCTION EXPORT
await reset();
await loadTokens();
const game = await p.evaluate(() => JSON.stringify(gameLayout()));
const gt = await p.evaluate(() => gameLayout().tithe);
ck('§22', 'the export carries tokenSize and tokenSpread',
   typeof gt.tokenSize === 'number' && typeof gt.tokenSpread === 'number',
   gt.tokenSize + ' / ' + gt.tokenSpread);
ck('§22', 'and not the field the flex build used', !('tokenGap' in gt));
ck('§22', 'each resource carries exactly key, name and iconName',
   gt.resources.every(r => Object.keys(r).sort().join(',') === 'iconName,key,name'),
   JSON.stringify(gt.resources[0]));
ck('§22', 'the filename is there', gt.resources[0].iconName === 'token_wheat.png',
   gt.resources[0].iconName);
ck('§22', 'no image bytes', game.indexOf('data:image') < 0 && game.indexOf('blob:') < 0);
ck('§22', 'and no image-pool key', !/"icon"\s*:/.test(game));

// ============================================================ §6 — POOL KEYS ARE NEVER REUSED
// THE BUG: the pool counter restarts at 0 on every page load, while the autosave keeps image
// KEYS and strips only the BYTES. So after a reload the state still claimed "im1" with nothing
// behind it, and the next image loaded was handed "im1" and instantly became that asset too --
// a wheat token appearing in the Gain Piety slot. One file, two owners.
await reset();
// stand in for "a previous session left these keys behind, bytes long gone"
await p.evaluate(() => {
  S.duties.clerical.actionA.scenic = "im1";
  S.duties.clerical.actionA.scenicName = "clerical_gain_piety_v01.png";
  S.duties.clerical.actionB.scenic = "im2";
  S.duties.clerical.actionB.scenicName = "clerical_gain_coins_v01.png";
  applyState(JSON.parse(JSON.stringify(S)));
  render(); panels();
});
await p.waitForTimeout(250);
const orphaned = await p.evaluate(() => ({
  aBytes: haveImage(S.duties.clerical.actionA.scenic),
  bBytes: haveImage(S.duties.clerical.actionB.scenic), seq: IMG_SEQ}));
ck('§6', 'the remembered keys have no bytes, as after a reload',
   !orphaned.aBytes && !orphaned.bBytes);
ck('§6', 'and the pool counter has been moved past them', orphaned.seq >= 2, orphaned.seq);
await loadTokens([0]);
const collide = await p.evaluate(() => {
  const k = S.tithe.resources[0].icon;
  return {tokenKey: k,
          stolenBy: [['actionA', S.duties.clerical.actionA.scenic],
                     ['actionB', S.duties.clerical.actionB.scenic]]
                    .filter(x => x[1] === k).map(x => x[0]),
          aStillEmpty: !haveImage(S.duties.clerical.actionA.scenic),
          tokenDrawn: haveImage(k)};
});
ck('§6', 'a newly loaded token gets a fresh key, not a remembered one',
   collide.stolenBy.length === 0, collide.tokenKey + ' stolen by ' + collide.stolenBy);
ck('§6', 'the action artwork still reports itself as not loaded', collide.aStillEmpty);
ck('§6', 'and the token itself is drawn', collide.tokenDrawn);

// ============================================================ §7 — A DRAG MUST SURVIVE ITSELF
// THE BUG: the token setters called panels(), which replaces titheCtl.innerHTML and throws away
// the very slider the mouse is holding. The element leaves the document, the browser loses the
// drag target, and the gesture ends after one step. It reads as a slider that will not move.
//
// Asserting the VALUE alone would not have caught it: synthetic events keep working, because the
// test holds its own reference to a control the page has already discarded. What has to be
// asserted is that the control is still IN THE DOCUMENT after the event it just handled.
await reset();
await loadTokens([0]);
const drag = await p.evaluate(() => {
  const out = {};
  function sweep(sel, from, to, read){
    const el = document.querySelector(sel);
    if (!el) return {error: 'missing ' + sel};
    let detached = 0;
    for (let v = from; v <= to; v++){
      el.value = v;
      el.dispatchEvent(new Event('input', {bubbles: true}));
      if (!document.contains(el)) detached += 1;
    }
    return {detached: detached, steps: to - from + 1, ended: read(), live: document.contains(el)};
  }
  out.size   = sweep('#tkSizeR', 39, 70, () => S.tithe.tokenSize);
  out.spread = sweep('#tkSpreadR', 48, 96, () => S.tithe.tokenSpread);
  return out;
});
['size','spread'].forEach(k => {
  ck('§7', 'dragging the ' + k + ' control never detaches it',
     drag[k].detached === 0 && drag[k].live,
     drag[k].detached + ' of ' + drag[k].steps + ' events hit a discarded element');
});
ck('§7', 'and the whole sweep lands, not just its first step',
   drag.size.ended === 70 && drag.spread.ended === 96,
   [drag.size.ended, drag.spread.ended].join(' / '));
// the readout and the number boxes follow without a rebuild
const mirrored = await p.evaluate(() => ({
  sizeNum: document.getElementById('tkSizeN').value,
  spreadNum: document.getElementById('tkSpreadN').value,
  read: document.querySelector('#titheCtl [data-tread]').textContent}));
ck('§7', 'the size box mirrors its slider', mirrored.sizeNum === '70', mirrored.sizeNum);
ck('§7', 'the spread box mirrors its slider', mirrored.spreadNum === '96', mirrored.spreadNum);
ck('§7', 'and the derived readout is rewritten in place',
   /side\s*96/.test(mirrored.read.replace(/\s+/g, ' '))
   && /token\s*70/.test(mirrored.read.replace(/\s+/g, ' ')), mirrored.read);
// TYPING IS A GESTURE TOO. The sync must skip whichever box has the caret, or a typed "120"
// never survives its own first digit: "1" applies, clamps to the floor, and the box is rewritten
// to the floor before the "2" arrives.
//
// IT HAS TO BE THE SIZE BOX. The spread's range starts at 0, so typing "1" into it clamps to
// nothing and a sync with no caret guard writes back the same "1" the person typed -- the test
// passes either way and proves nothing. Size starts at 28, so the unguarded version visibly
// stamps "28" over the first keystroke. A mutation run found this by removing the guard and
// watching the suite stay green.
const floor = await p.evaluate(() => HELPERS.tokenSize[0]);
const typed = await p.evaluate(() => {
  const n = document.getElementById('tkSizeN');
  n.focus();
  n.value = '1';                       // the first keystroke of "120"
  n.dispatchEvent(new Event('input', {bubbles: true}));
  const afterFirst = n.value;
  n.value = '12';
  n.dispatchEvent(new Event('input', {bubbles: true}));
  return {afterFirst: afterFirst, afterSecond: n.value,
          focused: document.activeElement === n};
});
ck('§7', 'the half-typed value would be visibly clamped if it were written back', floor > 12,
   'floor ' + floor);
ck('§7', 'a half-typed size is not overwritten while it has the caret',
   typed.afterFirst === '1' && typed.afterSecond === '12' && typed.focused,
   JSON.stringify(typed));

// ============================================================ §10 — THE CAPTION
// TAKE TITHE and GAIN COINS are the same kind of thing said about the same kind of choice, so
// they are set identically. Comparing them to the OTHER CAPTION rather than to a literal 17px
// is what keeps them matched: restyle the artwork caption and this fails, which is the point.
//
// THE CENTRING IS MEASURED ON THE GLYPHS, NOT ON THE BOX. `.tl` is stretched left:0;right:0
// across the whole card, so its own rect is centred no matter what `text-align` says -- an
// earlier version of this check compared box centres and sat there perfectly green with the
// caption jammed against the left edge. A Range over the text node measures the ink instead.
await reset();
const caps = await p.evaluate(() => {
  const tl = document.querySelector('#titheObj .tl');
  const cap = document.querySelector('.art .cap');
  if (!tl || !cap) return {error: !tl ? 'no tithe caption' : 'no artwork caption'};
  const a = getComputedStyle(tl), b = getComputedStyle(cap);
  const pick = s => [s.fontFamily.split(',')[0].replace(/["']/g, ''), s.fontWeight, s.fontSize,
                     s.letterSpacing, s.textTransform, s.color];
  const card = document.querySelector('[data-kind=tithe]').getBoundingClientRect();
  const box = tl.getBoundingClientRect();
  const rng = document.createRange(); rng.selectNodeContents(tl);
  const ink = rng.getBoundingClientRect();
  const pyr = document.querySelector('#titheObj .pyr').getBoundingClientRect();
  return {tithe: pick(a), art: pick(b), text: tl.textContent, align: a.textAlign,
          boxDx: Math.round((box.x + box.width / 2) - (card.x + card.width / 2)),
          inkDx: Math.round((ink.x + ink.width / 2) - (card.x + card.width / 2)),
          inkWidth: Math.round(ink.width), cardWidth: Math.round(card.width),
          fromBottom: Math.round(card.bottom - box.bottom),
          inkTop: ink.top, pyrBottom: pyr.bottom, cardTop: card.top, cardBottom: card.bottom};
});
ck('§10', 'the Tithe caption is set exactly like the action-artwork caption',
   JSON.stringify(caps.tithe) === JSON.stringify(caps.art),
   JSON.stringify(caps.tithe) + ' vs ' + JSON.stringify(caps.art));
ck('§10', 'it reads TAKE TITHE', caps.text === 'TAKE TITHE', JSON.stringify(caps.text));
ck('§10', 'the text itself is horizontally centred, not merely its box',
   Math.abs(caps.inkDx) <= 1, caps.inkDx + ' px off (box ' + caps.boxDx + ')');
ck('§10', 'and the check could tell the difference: the text is narrower than the card',
   caps.inkWidth < caps.cardWidth - 12, caps.inkWidth + ' of ' + caps.cardWidth);
ck('§10', 'text-align says centre too', caps.align === 'center', caps.align);
ck('§10', 'it sits at the bottom', caps.fromBottom >= 0 && caps.fromBottom <= 20,
   caps.fromBottom + ' px from the bottom edge');
ck('§10', 'and below the tokens, not above them', caps.inkTop >= caps.pyrBottom - 0.5,
   'caption ' + caps.inkTop.toFixed(1) + ' · tokens end ' + caps.pyrBottom.toFixed(1));
ck('§10', 'in the lower half of the card, wherever the tokens happen to be',
   caps.inkTop > (caps.cardTop + caps.cardBottom) / 2,
   caps.inkTop.toFixed(1) + ' vs mid ' + ((caps.cardTop + caps.cardBottom) / 2).toFixed(1));

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
