// Runs the play view's turn script for real, against a stub board, so the narrowing under test is
// the shipped JavaScript rather than a second copy of it written in Python.
//
// Reads a JSON job on argv: { script, resolutions, combinations, seats, panels, clicks, reset,
// confirm }. A click is { kind: 'position'|'resolution'|'combination'|'resource'|'seat'|'building',
// value }; a resource click also carries { seat }, a seat click names the player whose board is
// pressed, and a building click names the building whose hex on the round track is pressed.
// Prints a JSON transcript: what was offered at each point, which seat was asked for a stock, which
// boards were offered as an answer in themselves, what was marked as chosen, which panel was
// revealed, and what was finally posted.
'use strict';

const fs = require('fs');
const job = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));

function makeElement(attrs, children) {
  return {
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
      const key = selector.replace(/[[\]]/g, '');
      return this.children.find((child) => child.getAttribute(key) !== null) || null;
    },
    querySelectorAll(selector) {
      const key = selector.replace(/[[\]]/g, '');
      return this.children.filter((child) => child.getAttribute(key) !== null);
    },
    click() {
      (this.listeners.click || []).forEach((fn) => fn());
    },
  };
}

const spaces = [];
for (let index = 0; index <= 8; index += 1) {
  spaces.push(makeElement({ 'data-board-position-index': String(index) }));
}
const board = makeElement({ 'data-component': 'duty-wheel' });
board.querySelectorAll = () => spaces;

const keys = job.resolutions.map((name) => makeElement({ 'data-resolution-key': name }));
const pairs = (job.combinations || []).map((value) =>
  makeElement({ 'data-combination-key': value })
);
// Every building the round track carries, not merely the ones a turn may construct, so a script
// that revealed the wrong ones has wrong ones available to reveal.
const buildings = (job.buildings || []).map((id) =>
  makeElement({ 'data-building-choice-key': id })
);

// One board per seat, each carrying the keys the board renderer draws hidden: three for the stocks
// on it, and one for the board itself. Every seat is given the same keys, so the script has four
// boards to choose wrongly between rather than one it cannot help but get right, and the transcript
// reports which of them ended up offered. The two sets are asked of different numbers of seats --
// a stock of the one that is acting, a board of every one that may be named -- so they are kept
// apart here as well.
const seats = (job.seats || []).map((seat) =>
  makeElement(
    {
      'data-component': 'player-board-v2',
      'data-player-seat': String(seat.seat),
      'data-player': seat.player,
      'data-seat-taken': seat.taken ? 'true' : 'false',
      'data-active-seat': seat.active ? 'true' : 'false',
    },
    ['wheat', 'stone', 'silver']
      .map((stock) => makeElement({ 'data-resource-choice-key': stock }))
      .concat([makeElement({ 'data-seat-choice-key': seat.player })])
  )
);

const panels = [];
for (let index = 0; index < job.panels.length; index += 1) {
  const actionId = job.panels[index];
  const commit = actionId ? [makeElement({ 'data-turn-confirm': actionId })] : [];
  panels.push(makeElement({ 'data-turn-panel': String(index) }, commit));
}
const reset = makeElement({ 'data-turn-reset': '', 'data-turn-started': 'false' });

const aside = makeElement({ 'data-component': 'play-turn' });
aside.querySelectorAll = (selector) => {
  if (selector === '[data-resolution-key]') return keys;
  if (selector === '[data-combination-key]') return pairs;
  if (selector === '[data-turn-panel]') return panels;
  return [];
};
aside.querySelector = (selector) => (selector === '[data-turn-reset]' ? reset : null);

const transcript = {
  offered: [],
  chosen: [],
  shownPanel: [],
  askedSeats: [],
  offeredBySeat: [],
  offeredBoards: [],
  posted: null,
  rewritten: false,
};

global.document = {
  querySelector(selector) {
    if (selector === '[data-component="duty-wheel"]') return board;
    if (selector === '[data-component="play-turn"]') return aside;
    return null;
  },
  querySelectorAll(selector) {
    if (selector === '[data-component="player-board-v2"][data-player-seat]') return seats;
    if (selector === '[data-building-choice-key]') return buildings;
    return [];
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

function snapshot() {
  const offered = [];
  const chosen = [];
  spaces.forEach((space, index) => {
    if (space.getAttribute('data-play-offered') === 'true') offered.push(index);
    if (space.getAttribute('data-play-chosen') === 'true') chosen.push(index);
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
  // A stock counts as offered once, however many boards carry a key for it, but which seats were
  // asked is recorded separately so reaching across the table is visible rather than averaged out.
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
  return { offered, chosen, shown, asked, bySeat, boards };
}

function record() {
  const snap = snapshot();
  transcript.offered.push(snap.offered);
  transcript.chosen.push(snap.chosen);
  transcript.shownPanel.push(snap.shown);
  transcript.askedSeats.push(snap.asked);
  transcript.offeredBySeat.push(snap.bySeat);
  transcript.offeredBoards.push(snap.boards);
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
  if (click.kind === 'position') spaces[click.value].click();
  else if (click.kind === 'combination') {
    pairs.find((pair) => pair.getAttribute('data-combination-key') === click.value).click();
  } else if (click.kind === 'resource') pressResource(click);
  else if (click.kind === 'seat') pressBoard(click);
  else if (click.kind === 'building') {
    buildings.find((key) => key.getAttribute('data-building-choice-key') === click.value).click();
  }
  else keys.find((key) => key.getAttribute('data-resolution-key') === click.value).click();
  record();
});

if (job.reset) {
  reset.click();
  const snap = snapshot();
  transcript.afterReset = { offered: snap.offered, chosen: snap.chosen, shown: snap.shown };
}

if (job.confirm) {
  const shown = snapshot().shown;
  const commit = shown === -1 ? null : panels[shown].querySelector('[data-turn-confirm]');
  if (commit) commit.click();
  transcript.confirmable = commit !== null;
}

transcript.resetVisible = reset.getAttribute('data-turn-started');
process.stdout.write(JSON.stringify(transcript));
