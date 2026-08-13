// Runs the play view's sow script for real, against a stub board, so the narrowing under test is
// the shipped JavaScript rather than a second copy of it written in Python.
//
// Reads a JSON job on argv: { script, clicks, abandonAt }. Prints a JSON transcript: what was
// offered at each step, what was marked as being on the route, and what was finally posted.
'use strict';

const fs = require('fs');
const job = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));

function makeElement(attrs) {
  return {
    attrs: Object.assign({}, attrs),
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
const abandon = makeElement({ 'data-sow-abandon': '', 'data-sow-started': 'false' });

const transcript = { offered: [], onRoute: [], posted: null, rewritten: false };

global.document = {
  querySelector(selector) {
    if (selector === '[data-component="duty-wheel"]') return board;
    if (selector === '[data-sow-abandon]') return abandon;
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
  const onRoute = [];
  spaces.forEach((space, index) => {
    if (space.getAttribute('data-sow-candidate') === 'true') offered.push(index);
    if (space.getAttribute('data-sow-on-route') === 'true') onRoute.push(index);
  });
  return { offered, onRoute };
}

// eslint-disable-next-line no-eval
eval(job.script);

let snap = snapshot();
transcript.offered.push(snap.offered);
transcript.onRoute.push(snap.onRoute);

job.clicks.forEach((index) => {
  spaces[index].click();
  snap = snapshot();
  transcript.offered.push(snap.offered);
  transcript.onRoute.push(snap.onRoute);
});

// `abandonAt` is a count of clicks to make before giving up, so the route under test is genuinely
// half built when the button is pressed.
if (job.abandonAt !== null && job.abandonAt !== undefined) {
  abandon.click();
  snap = snapshot();
  transcript.abandonedTo = { offered: snap.offered, onRoute: snap.onRoute };
}

transcript.abandonVisible = abandon.getAttribute('data-sow-started');
process.stdout.write(JSON.stringify(transcript));
