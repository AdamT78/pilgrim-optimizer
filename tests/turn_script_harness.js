// Runs the play view's turn script for real, against a stub board, so the narrowing under test is
// the shipped JavaScript rather than a second copy of it written in Python.
//
// Reads a JSON job on argv: { script, prompts, resolutions, combinations, seats, panels, clicks,
// reset, confirm, spaces, arrows, counters, controls, cubes, playerCount }.
//
// A click is { kind: 'position'|'origin'|'duty'|'edge'|'resolution'|'combination'|'resource'
// |'seat'|'building'|'control', value }; a resource click also carries { seat }, a seat click
// names the player whose board is pressed, a building click names the building whose hex on the
// round track is pressed, and a control click presses one board plaque by name.
//
// Prints a JSON transcript: what was offered at each point, which seat was asked for a stock, which
// boards were offered as an answer in themselves, what was marked as chosen, which panel was shown,
// what counter/control state was visible, and what was finally posted.
'use strict';

const fs = require('fs');
const job = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));

function parsePart(part) {
  const tag = /^[A-Za-z0-9_-]+/.test(part) ? part.match(/^[A-Za-z0-9_-]+/)[0] : null;
  const attrs = Array.from(part.matchAll(/\[([A-Za-z0-9_-]+)(?:="([^"]*)")?\]/g)).map((match) => ({
    name: match[1],
    value: match[2],
  }));
  return { tag, attrs };
}

function matches(node, part) {
  const parsed = parsePart(part);
  if (parsed.tag && node.tag !== parsed.tag) return false;
  return parsed.attrs.every((requirement) => {
    const found = node.getAttribute(requirement.name);
    if (found === null) return false;
    return requirement.value === undefined ? true : found === requirement.value;
  });
}

function descendants(node) {
  const found = [];
  (node.children || []).forEach((child) => {
    found.push(child);
    descendants(child).forEach((nested) => found.push(nested));
  });
  return found;
}

function search(root, selector) {
  const parts = selector.trim().split(/\s+/).filter(Boolean);
  let current = [root];
  parts.forEach((part) => {
    const next = [];
    current.forEach((origin) => {
      descendants(origin).forEach((candidate) => {
        if (matches(candidate, part)) next.push(candidate);
      });
    });
    current = next;
  });
  return current;
}

function makeElement(tag, attrs, children) {
  return {
    tag,
    attrs: Object.assign({}, attrs),
    children: children || [],
    listeners: {},
    getAttribute(name) {
      return Object.prototype.hasOwnProperty.call(this.attrs, name) ? this.attrs[name] : null;
    },
    setAttribute(name, value) {
      this.attrs[name] = String(value);
    },
    removeAttribute(name) {
      delete this.attrs[name];
    },
    addEventListener(type, fn) {
      (this.listeners[type] = this.listeners[type] || []).push(fn);
    },
    querySelector(selector) {
      return this.querySelectorAll(selector)[0] || null;
    },
    querySelectorAll(selector) {
      return search(this, selector);
    },
    click() {
      (this.listeners.click || []).forEach((fn) => fn());
    },
  };
}

const boardPositions = job.spaces || [
  { index: 0, name: 'city' },
  { index: 1, name: 'north' },
  { index: 2, name: 'north_east' },
  { index: 3, name: 'east' },
  { index: 4, name: 'south_east' },
  { index: 5, name: 'south' },
  { index: 6, name: 'south_west' },
  { index: 7, name: 'west' },
  { index: 8, name: 'north_west' },
];
const playerCount =
  job.playerCount
  || (job.seats || []).filter((seat) => seat.taken).length
  || 4;

function cubeElement(cube, slot) {
  const attrs = { 'data-player': cube.player || 'player_one', 'data-slot': String(slot) };
  if (cube.opacity !== undefined && cube.opacity !== null) attrs.opacity = String(cube.opacity);
  return makeElement('rect', attrs, []);
}

const spaces = boardPositions.map((space) => {
  const listed = (job.cubes && job.cubes[space.name]) || [];
  const cubes = listed.map((cube, index) => cubeElement(cube, index));
  const tally = makeElement(
    'g',
    { 'data-cube-tally': space.name, 'data-player-count': String(playerCount) },
    cubes
  );
  return makeElement(
    'g',
    {
      'data-board-position-index': String(space.index),
      'data-board-position': String(space.name),
    },
    [tally]
  );
});

const arrows = (job.arrows || []).map((edge) =>
  makeElement('g', { 'data-arrow': edge, 'data-turn-offered': 'false' }, [])
);
const counters = (job.counters || []).map((value) =>
  makeElement('g', { 'data-turn-counter': String(value), 'data-turn-offered': 'false' }, [])
);
const controlNames = ['sow', 'reset', 'confirm', 'action', 'tithe'];
const controls = controlNames.map((name) =>
  makeElement(
    'g',
    {
      'data-turn-control': name,
      'data-turn-control-enabled':
        job.controls && Object.prototype.hasOwnProperty.call(job.controls, name)
          ? (job.controls[name] ? 'true' : 'false')
          : (name === 'sow' ? 'true' : 'false'),
    },
    []
  )
);

const board = makeElement(
  'svg',
  { 'data-component': 'duty-wheel' },
  [].concat(spaces, arrows, counters, controls)
);

const prompts = (job.prompts || []).map((sentence) =>
  makeElement('div', { 'data-turn-prompt': sentence }, [])
);
const keys = (job.resolutions || []).map((name) =>
  makeElement('button', { 'data-resolution-key': name }, [])
);
const pairs = (job.combinations || []).map((value) =>
  makeElement('button', { 'data-combination-key': value }, [])
);
const buildings = (job.buildings || []).map((id) =>
  makeElement('g', { 'data-building-choice-key': id }, [])
);

const seats = (job.seats || []).map((seat) =>
  makeElement(
    'div',
    {
      'data-component': 'player-board-v2',
      'data-player-seat': String(seat.seat),
      'data-player': seat.player,
      'data-seat-taken': seat.taken ? 'true' : 'false',
      'data-active-seat': seat.active ? 'true' : 'false',
    },
    ['wheat', 'stone', 'silver']
      .map((stock) => makeElement('g', { 'data-resource-choice-key': stock }, []))
      .concat([makeElement('rect', { 'data-seat-choice-key': seat.player }, [])])
  )
);

const panels = [];
for (let index = 0; index < (job.panels || []).length; index += 1) {
  const actionId = job.panels[index];
  const commit = actionId ? [makeElement('button', { 'data-turn-confirm': actionId }, [])] : [];
  panels.push(makeElement('div', { 'data-turn-panel': String(index) }, commit));
}

const aside = makeElement(
  'div',
  { 'data-component': 'play-turn' },
  [].concat(prompts, keys, pairs, panels)
);

const root = makeElement('document', {}, [].concat([board, aside], buildings, seats));

const transcript = {
  offered: [],
  chosen: [],
  shownPanel: [],
  askedSeats: [],
  offeredBySeat: [],
  offeredBoards: [],
  startCandidates: [],
  dutyCandidates: [],
  asking: [],
  resetShown: [],
  counterShown: [],
  controls: [],
  cubes: [],
  overflow: [],
  posted: null,
  rewritten: false,
};

global.document = {
  querySelector(selector) {
    return search(root, selector)[0] || null;
  },
  querySelectorAll(selector) {
    return search(root, selector);
  },
  open() {},
  write() {
    transcript.rewritten = true;
  },
  close() {},
};
global.window = { alert(message) { transcript.alerted = message; } };
global.XMLHttpRequest = function XMLHttpRequestStub() {
  this.open = () => {};
  this.setRequestHeader = () => {};
  this.send = (body) => {
    transcript.posted = JSON.parse(body);
    this.status = 200;
    this.responseText = '<!DOCTYPE html><html></html>';
    if (this.onload) this.onload();
  };
};

function control(name) {
  return controls.find((candidate) => candidate.getAttribute('data-turn-control') === name) || null;
}

function cubeSnapshot() {
  const byPosition = {};
  spaces.forEach((space) => {
    const name = space.getAttribute('data-board-position');
    const tally = space.querySelector('[data-cube-tally]');
    byPosition[name] = (tally ? tally.querySelectorAll('rect') : []).map((cube) => ({
      player: cube.getAttribute('data-player'),
      opacity: cube.getAttribute('opacity') === null ? '1' : cube.getAttribute('opacity'),
    }));
  });
  return byPosition;
}

function snapshot() {
  const offered = [];
  const chosen = [];
  const starts = [];
  const duties = [];
  spaces.forEach((space, index) => {
    const asksOrigin = space.getAttribute('data-turn-start-candidate') === 'true';
    const asksDuty = space.getAttribute('data-turn-duty-candidate') === 'true';
    if (asksOrigin || asksDuty) offered.push(index);
    if (asksOrigin) starts.push(index);
    if (asksDuty) duties.push(index);
    const pickedOrigin = space.getAttribute('data-turn-start-selected') === 'true';
    const pickedDuty = space.getAttribute('data-turn-duty-selected') === 'true';
    if (pickedOrigin || pickedDuty) chosen.push(index);
  });
  arrows.forEach((arrow) => {
    if (arrow.getAttribute('data-turn-offered') === 'true') {
      offered.push(arrow.getAttribute('data-arrow'));
    }
  });
  keys.forEach((key) => {
    if (key.getAttribute('data-turn-offered') === 'true') {
      offered.push(key.getAttribute('data-resolution-key'));
    }
  });
  pairs.forEach((pair) => {
    if (pair.getAttribute('data-turn-offered') === 'true') {
      offered.push(pair.getAttribute('data-combination-key'));
    }
  });
  buildings.forEach((key) => {
    if (key.getAttribute('data-turn-offered') === 'true') {
      offered.push(key.getAttribute('data-building-choice-key'));
    }
  });
  const asked = [];
  const bySeat = {};
  const boards = [];
  seats.forEach((seat) => {
    const name = seat.getAttribute('data-player-seat');
    if (seat.getAttribute('data-resource-choice') === 'true') asked.push(name);
    if (seat.getAttribute('data-seat-choice') === 'true') {
      boards.push(seat.getAttribute('data-player'));
    }
    const stocks = seat
      .querySelectorAll('[data-resource-choice-key]')
      .filter((key) => key.getAttribute('data-turn-offered') === 'true')
      .map((key) => key.getAttribute('data-resource-choice-key'));
    if (stocks.length) bySeat[name] = stocks;
    stocks.forEach((stock) => {
      if (offered.indexOf(stock) === -1) offered.push(stock);
    });
    seat
      .querySelectorAll('[data-seat-choice-key]')
      .filter((key) => key.getAttribute('data-turn-offered') === 'true')
      .forEach((key) => {
        const player = key.getAttribute('data-seat-choice-key');
        if (offered.indexOf(player) === -1) offered.push(player);
      });
  });
  let shown = -1;
  panels.forEach((panel, index) => {
    if (panel.getAttribute('data-turn-shown') === 'true') shown = index;
  });
  const asking = prompts
    .filter((line) => line.getAttribute('data-turn-offered') === 'true')
    .map((line) => line.getAttribute('data-turn-prompt'));
  const counter = counters
    .filter((item) => item.getAttribute('data-turn-offered') === 'true')
    .map((item) => item.getAttribute('data-turn-counter'));
  const states = {};
  const activeStates = {};
  controls.forEach((item) => {
    states[item.getAttribute('data-turn-control')] = item.getAttribute('data-turn-control-enabled');
    activeStates[item.getAttribute('data-turn-control')] = item.getAttribute('data-turn-control-active');
  });
  ['action', 'tithe'].forEach((name) => {
    if (states[name] === 'true' && offered.indexOf(name) === -1) offered.push(name);
  });
  const overflow = board.getAttribute('data-turn-preview-overflow') === 'true';
  return {
    offered,
    chosen,
    shown,
    asked,
    bySeat,
    boards,
    starts,
    duties,
    asking,
    reset: control('reset') ? control('reset').getAttribute('data-turn-control-enabled') === 'true' : false,
    counter,
    controls: states,
    controlActive: activeStates,
    cubes: cubeSnapshot(),
    overflow,
  };
}

function record() {
  const snap = snapshot();
  transcript.offered.push(snap.offered);
  transcript.chosen.push(snap.chosen);
  transcript.shownPanel.push(snap.shown);
  transcript.askedSeats.push(snap.asked);
  transcript.offeredBySeat.push(snap.bySeat);
  transcript.offeredBoards.push(snap.boards);
  transcript.startCandidates.push(snap.starts);
  transcript.dutyCandidates.push(snap.duties);
  transcript.asking.push(snap.asking);
  transcript.resetShown.push(snap.reset);
  transcript.counterShown.push(snap.counter);
  transcript.controls.push(snap.controls);
  transcript.controlActive = transcript.controlActive || [];
  transcript.controlActive.push(snap.controlActive);
  transcript.cubes.push(snap.cubes);
  transcript.overflow.push(snap.overflow);
}

// eslint-disable-next-line no-eval
eval(job.script);

record();

function pressResource(click) {
  const seat = seats.find(
    (candidate) => candidate.getAttribute('data-player-seat') === String(click.seat)
  );
  seat
    .querySelectorAll('[data-resource-choice-key]')
    .find((key) => key.getAttribute('data-resource-choice-key') === click.value)
    .click();
}

function pressBoard(click) {
  const seat = seats.find(
    (candidate) => candidate.getAttribute('data-player') === click.value
  );
  seat
    .querySelectorAll('[data-seat-choice-key]')
    .find((key) => key.getAttribute('data-seat-choice-key') === click.value)
    .click();
}

job.clicks.forEach((click) => {
  if (click.kind === 'position' || click.kind === 'origin' || click.kind === 'duty') {
    spaces.find((space) =>
      Number(space.getAttribute('data-board-position-index')) === Number(click.value)).click();
  } else if (click.kind === 'edge') {
    arrows.find((arrow) => arrow.getAttribute('data-arrow') === click.value).click();
  } else if (click.kind === 'control') {
    const button = control(click.value);
    if (button) button.click();
  } else if (click.kind === 'combination') {
    pairs.find((pair) => pair.getAttribute('data-combination-key') === click.value).click();
  } else if (click.kind === 'resource') {
    pressResource(click);
  } else if (click.kind === 'seat') {
    pressBoard(click);
  } else if (click.kind === 'building') {
    buildings.find((key) => key.getAttribute('data-building-choice-key') === click.value).click();
  } else {
    keys.find((key) => key.getAttribute('data-resolution-key') === click.value).click();
  }
  record();
});

if (job.reset) {
  const reset = control('reset');
  if (reset) reset.click();
  const snap = snapshot();
  transcript.afterReset = {
    offered: snap.offered,
    chosen: snap.chosen,
    shown: snap.shown,
    asking: snap.asking,
    startCandidates: snap.starts,
    dutyCandidates: snap.duties,
    reset: snap.reset,
    counter: snap.counter,
    controls: snap.controls,
    controlActive: snap.controlActive,
    cubes: snap.cubes,
    overflow: snap.overflow,
  };
}

if (job.confirm) {
  const confirmControl = control('confirm');
  if (confirmControl) confirmControl.click();
  transcript.confirmable =
    confirmControl && confirmControl.getAttribute('data-turn-control-enabled') === 'true';
}

transcript.resetVisible = control('reset')
  ? control('reset').getAttribute('data-turn-control-enabled')
  : null;
process.stdout.write(JSON.stringify(transcript));
