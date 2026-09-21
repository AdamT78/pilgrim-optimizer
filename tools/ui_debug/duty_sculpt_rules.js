// HOW ACOLYTE SCULPTS ARE DRAWN ON A DUTY TILE. This file is THE copy.
//
// It is inlined verbatim into every page that draws acolytes -- the board checker and the
// placement sheet -- rather than written out in each of them. The formation was written three
// times for a while and the depth cue twice; they agreed only because someone had just copied
// them, and the first edit to any one would have made the pages disagree while each looked
// entirely correct on its own.
//
// Numbers come from ui/assets-gothic/metadata/duty_placement.json. Nothing here decides spread,
// set-back, rank gap or how strong the cue is -- this is the SHAPE, the file is the SIZE.
//
// x is measured from the tile centre, y as height above the floor the figures stand on, both in
// real device pixels. Positions come back unsorted; callers that care sort by x.

function dutyFormation(n, spread, back, rank) {
  // AN EMPTY TILE MUST RETURN NO SLOTS. Without this the chain falls through to the five-slot
  // case, the seat queue has nothing to fill them with, and the board build throws on the first
  // empty tile -- which under a typical deal is most of them.
  if (n <= 0) return [];
  if (n === 1) return [{x: 0, y: 0}];
  if (n === 2) return [{x: -spread / 2, y: 0}, {x: spread / 2, y: 0}];
  // Three abreast with the middle set BACK: a flat row of three identical silhouettes is the
  // hardest case to read, and lifting the centre one breaks the repeat.
  if (n === 3) return [{x: -spread, y: 0}, {x: 0, y: back}, {x: spread, y: 0}];
  // Four and five split into two ranks, the back one offset half a step so nobody stands
  // directly behind anybody.
  if (n === 4) return [{x: -spread * 0.75, y: rank}, {x: spread * 0.25, y: rank},
                       {x: -spread * 0.25, y: 0},    {x: spread * 0.75, y: 0}];
  return [{x: -spread / 2, y: rank}, {x: spread / 2, y: rank},
          {x: -spread, y: 0}, {x: 0, y: back}, {x: spread, y: 0}];
}

// Which seat stands in each slot, left to right.
//
//   grouped  a player's sculpts are consecutive        p1 p1 p2 p3
//   arrival  seats take turns as they place            p1 p2 p3 p1
//
// Both are truthful, and measured they move the same number of sculpts per drop (2.73), because
// the shuffle comes from the formation changing shape with the count rather than from the order.
function dutySeatOrder(counts, order) {
  var out = [], seat, k;
  if (order === "arrival") {
    var left = counts.slice(), total = 0;
    for (seat = 0; seat < counts.length; seat++) total += counts[seat];
    while (out.length < total)
      for (seat = 0; seat < left.length; seat++)
        if (left[seat] > 0) { out.push(seat); left[seat] -= 1; }
    return out;
  }
  for (seat = 0; seat < counts.length; seat++)
    for (k = 0; k < counts[seat]; k++) out.push(seat);
  return out;
}

// HOW MUCH CUE A FIGURE AT DEPTH y GETS. Absolute, never relative.
//
// This used to be `y / max(depth of everything on the tile)`, which made the cue a function of
// the company a figure keeps rather than of where it stands. Push the middle of five back past
// the back rank and the divisor grew, so the rank BEHIND it lost haze -- a figure got clearer by
// having something else move further away. Three depths could never be told apart either: once
// something reached the maximum, everything at the maximum looked identical.
//
// Extinction instead, which is what haze actually does: 1 - exp(-y/ref). Monotonic, so deeper is
// always hazier; absolute, so one figure moving changes nothing about the others; and it never
// saturates, so a third rank still reads as further back than the second. `ref` is the distance
// at which the cue reaches about 63% of full -- one e-fold -- and comes from the placement file.
function dutyDepth(y, ref) {
  if (!(y > 0)) return 0;
  var r = ref > 0 ? ref : 1;
  return 1 - Math.exp(-y / r);
}

// THE LADDER'S SHAPE, in one place. Both numbers have to agree between the filters that get
// BUILT and the filter each figure PICKS: build eight rungs and then round a depth onto twelve
// and the deepest figures silently land on rungs that were never defined, which renders as no
// haze at all rather than as an error. They were written out separately in each page.
var DUTY_HAZE = {steps: 8, max: 0.62};

// WHERE THE PARTS OF A TILE SIT. One copy, like the formation.
//
// This was written out in each page that draws the wheel, and the copies had already drifted:
// the gap between the floor and the banner was 0.046 of the cell in one and 0.050 in the other,
// so the two pages disagreed about where a banner sat -- by about two and a half real pixels,
// which is exactly the size of difference nobody notices and nobody can then explain. 0.046 is
// kept, because it is the value the banner and icon stack was actually tuned against.
//
// Everything is a fraction of the cell except the field, which is the figures' own height plus
// the deepest slot they can stand in -- those are real pixels and do not scale with the tile.
//
//   banW/banH  the parchment
//   gapA       floor line to the top of the parchment
//   gapB       parchment to the action icons, and `icon` their size (icons are the board
//              checker's; the sow page passes icons: false and gets the same numbers otherwise)
//   field      floor to the tallest head
//   total      the whole stack, which is what has to fit inside the cell
//   top        where the stack starts, centring it in the cell
//   mark       the width a tile claims on the floor -- the banner's, with a little over
function dutyTileLayout(cell, figH, rank, back, opts) {
  var o = opts || {};
  var banW = cell * 0.55, banH = banW / 3;
  var gapA = cell * 0.046, gapB = cell * 0.010;
  var icon = Math.round(cell * 0.168);
  // THE FIELD HAS TO CLEAR THE DEEPEST SLOT, and the deepest slot is the rank gap at four and
  // five but the SET-BACK at three. One copy took only the rank gap, which clips the middle
  // figure's head the moment a set-back larger than the rank gap is tried -- latent rather than
  // broken at 21 against 52, which is how every other copy in this toolchain has behaved too.
  var field = figH + Math.max(rank, back, 0);
  var total = field + gapA + banH + (o.icons ? gapB + icon : 0);
  return {banW: banW, banH: banH, gapA: gapA, gapB: gapB, icon: icon,
          field: field, total: total, top: (cell - total) / 2, mark: banW * 1.06};
}

// THE ROOM A GROUP TAKES UP, as a box around it.
//
// Measured rather than assumed: the sculpts are not one width -- three of the four are 91 px
// across at 210 and the fourth is 108 -- so the extent of a formation depends on who is standing
// in it, and the envelope has to be computed from the figures rather than from the spread.
//
// Coordinates are the formation's own: x from the tile's centre, y as height above the floor.
// `bottom` is always 0 because the figures stand ON the floor; `top` is the tallest head.
function dutyGroupBox(figs) {
  if (!figs || !figs.length) return null;
  var left = Infinity, right = -Infinity, top = 0, k, f;
  for (k = 0; k < figs.length; k++) {
    f = figs[k];
    left = Math.min(left, f.x - f.w / 2);
    right = Math.max(right, f.x + f.w / 2);
    top = Math.max(top, f.y + f.h);
  }
  return {left: left, right: right, top: top, bottom: 0,
          w: right - left, h: top};
}

// The WORST CASE a tile has to hold, which is what a tile must be sized for -- not what it
// happens to hold right now. Every slot is given the widest and tallest sculpt in the set,
// because a tile does not get to choose who stands on it.
function dutyCapacityBox(n, spread, back, rank, widest, tallest) {
  var slots = dutyFormation(n, spread, back, rank);
  return dutyGroupBox(slots.map(function (p) {
    return {x: p.x, y: p.y, w: widest, h: tallest};
  }));
}

// The haze ladder. flood-opacity cannot be driven per element from CSS, so a small ladder of
// filters stands in for a continuous one, and a figure picks the step nearest its depth.
//
// color-interpolation-filters is pinned to sRGB and that is load-bearing: the SVG default is
// linearRGB, and measured against it a full-strength haze landed under half as dark as its
// flood-opacity asked for while the bottom third of the amount slider did nothing visible.
function dutyHazeDefs(ground, steps, maxOpacity) {
  var n = steps || 8, top = maxOpacity || 0.62, out = "", k;
  for (k = 1; k <= n; k++)
    out += '<filter id="hz' + k + '" x="-30%" y="-30%" width="160%" height="160%" '
         + 'color-interpolation-filters="sRGB">'
         + '<feFlood flood-color="' + ground + '" flood-opacity="'
         + (top * k / n).toFixed(3) + '" result="f"/>'
         + '<feComposite in="f" in2="SourceGraphic" operator="in" result="t"/>'
         + '<feMerge><feMergeNode in="SourceGraphic"/><feMergeNode in="t"/></feMerge></filter>';
  return out;
}

// One filter chain per figure: the depth cue first and the shadow after it, so a receded figure
// still casts a shadow rather than having the cue applied to the shadow as well.
//
//   haze    blends toward the tile colour, which is what distance does -- a far object loses
//           contrast against its background rather than simply going dark. Ground-dependent.
//   dark    toward black with some desaturation, because brightness alone leaves the seat colour
//           at full chroma and reads as different plastic rather than as distance. Ground-free.
function dutyFilter(y, opts) {
  var steps = opts.steps || 8;
  var k = (opts.amount || 0) / 100 * dutyDepth(y, opts.ref);
  var f = "";
  if (k > 0.001)
    f = opts.mode === "haze"
      ? "url(#hz" + Math.max(1, Math.min(steps, Math.round(k * steps))) + ") "
      : "brightness(" + (1 - 0.50 * k).toFixed(3) + ") saturate("
        + (1 - 0.40 * k).toFixed(3) + ") ";
  return f + (opts.shadow ? "drop-shadow(3px 5px 4px rgba(0,0,0,.55))" : "none");
}
