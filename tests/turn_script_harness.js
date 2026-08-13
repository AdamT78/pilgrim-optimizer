// Runs the play view's turn script for real, against a stub board, so the narrowing under test is
// the shipped JavaScript rather than a second copy of it written in Python.
//
// Reads a JSON job on argv: { script, resolutions, panels, clicks, reset, confirm }. A click is
// { kind: 'position'|'resolution', value }. Prints a JSON transcript: what was offered at each
// point, what was marked as chosen, which panel was revealed, and what was finally posted.
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
    addEventListener(type, fn) {
      (this.listeners[type] = this.listeners[type] || []).push(fn);
    },
    querySelector(selector) {
      const key = selector.replace(/[[\]]/g, '');
      return this.children.find((child) => child.getAttribute(key) !== null) || null;
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
  if (selector === '[data-turn-panel]') return panels;
  return [];
};
aside.querySelector = (selector) => (selector === '[data-turn-reset]' ? reset : null);

const transcript = { offered: [], chosen: [], shownPanel: [], posted: null, rewritten: false };

global.document = {
  querySelector(selector) {
    if (selector === '[data-component="duty-wheel"]') return board;
    if (selector === '[data-component="play-turn"]') return aside;
    return null;
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
  let shown = -1;
  panels.forEach((panel, index) => {
    if (panel.getAttribute('data-turn-shown') === 'true') shown = index;
  });
  return { offered, chosen, shown };
}

function record() {
  const snap = snapshot();
  transcript.offered.push(snap.offered);
  transcript.chosen.push(snap.chosen);
  transcript.shownPanel.push(snap.shown);
}

// eslint-disable-next-line no-eval
eval(job.script);

record();

job.clicks.forEach((click) => {
  if (click.kind === 'position') spaces[click.value].click();
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
