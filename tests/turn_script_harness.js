// Runs the play view's turn script for real, against a stub board, so the narrowing under test is
// the shipped JavaScript rather than a second copy of it written in Python.
//
// Reads a JSON job on argv: { script, prompts, resolutions, combinations, seats, panels, clicks,
// reset, confirm, spaces, arrows, counters, controls, cubes, playerCount,
// arrangementPointerRules, buildingAbilityTargets, turnStepBuildings, phaseColumn, phaseOnly,
// phaseCandidateRuns }.
//
// A click is { kind: 'position'|'origin'|'skip'|'duty'|'edge'|'resolution'
// |'combination'|'resource'|'seat'|'building'
// |'control'|'village'|'abbey'|'role', value }; a resource click also carries { seat }, a seat
// click names the player whose board is pressed, a building click names the building whose hex on
// the round track is pressed, and a control click presses one board plaque by name. `village` clicks
// one Village token on the active seat's board, `abbey` clicks one Abbey token there, and `role`
// clicks either a role token or the role circle
// (when click.target === 'circle').
//
// Prints a JSON transcript: what was offered at each point, which seat was asked for a stock, which
// boards were offered as an answer in themselves, what was marked as chosen, which panel was shown,
// what counter/control state was visible, and what was finally posted.
'use strict';

const fs = require('fs');
const input = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const phaseCandidateTemplate = input.script.replace(
  /var CANDIDATES = [\s\S]*?;\n  var TURN_STEPS/,
  'var CANDIDATES = __HARNESS_PHASE_CANDIDATES__;\n  var TURN_STEPS'
);

function runJob(job) {

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
  const element = {
    tag,
    attrs: Object.assign({}, attrs),
    children: children || [],
    parent: null,
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
  element.children.forEach((child) => {
    child.parent = element;
  });
  return element;
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
const ROLE_IDS = ['fields', 'road_engineer', 'stone_mason', 'alms_house', 'engraver', 'vestry'];

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

const cityVisibleByPlayer = {};
(((job.cubes || {}).city) || []).forEach((cube) => {
  const player = cube.player || 'player_one';
  if (!Object.prototype.hasOwnProperty.call(cityVisibleByPlayer, player)) {
    cityVisibleByPlayer[player] = 0;
  }
  if ((cube.opacity === undefined || cube.opacity === null ? '1' : String(cube.opacity)) !== '0') {
    cityVisibleByPlayer[player] += 1;
  }
});
const cityColumns = (job.seats || []).map((seat) => {
  const visible = Math.max(0, Math.min(6, Number(cityVisibleByPlayer[seat.player]) || 0));
  const slots = Array.from({ length: 6 }, (_, index) =>
    makeElement(
      'rect',
      {
        'data-city-column-player': seat.player,
        'data-city-cube': String(index),
        opacity: index < visible ? '1' : '0',
      },
      []
    )
  );
  return makeElement('g', { 'data-city-column-player': seat.player }, slots);
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
  [].concat(spaces, cityColumns, arrows, counters, controls)
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
const confirmLabels = ['confirm', 'end_turn'].map((label) =>
  makeElement('span', { 'data-turn-control-label': label, 'data-turn-offered': 'false' }, [])
);
const phaseRows = ((job.phaseColumn && job.phaseColumn.rows) || []).map((row) => {
  const attrs = { 'data-turn-phase': row.key };
  if (row.current) attrs['data-phase-current'] = 'true';
  return makeElement('div', attrs, []);
});
const phasePrompts = Object.keys((job.phaseColumn && job.phaseColumn.prompts) || {}).map((key) =>
  makeElement('div', { 'data-turn-phase-prompt': key }, [])
);
const buildings = (job.buildings || []).map((id) =>
  makeElement('g', { 'data-building-choice-key': id }, [])
);
const buildingAbilityTargets = (job.buildingAbilityTargets || []).map((ability) =>
  makeElement('g', { 'data-building-id': ability.building_id }, [])
);
const turnStepBuildings = (job.turnStepBuildings || []).map((id) =>
  makeElement(
    'g',
    {
      'data-turn-step-building-id': id,
      'data-turn-step-offered': 'false',
    },
    []
  )
);

function abbeyTokensFor(count) {
  const visible = Math.max(0, Math.min(8, Number(count) || 0));
  return Array.from({ length: 8 }, (_, index) =>
    makeElement(
      'rect',
      {
        'data-token': 'abbey',
        'data-token-index': String(index),
        opacity: index < visible ? '1' : '0',
      },
      []
    )
  );
}

function villageTokensFor(count) {
  const visible = Math.max(0, Math.min(8, Number(count) || 0));
  return Array.from({ length: 8 }, (_, index) =>
    makeElement(
      'rect',
      {
        'data-token': 'village',
        'data-token-index': String(index),
        opacity: index < visible ? '1' : '0',
      },
      []
    )
  );
}

function roleTokensFor(roleId, count) {
  const capped = Math.max(0, Math.min(2, Number(count) || 0));
  return [
    makeElement(
      'rect',
      {
        'data-token': 'role',
        'data-role': roleId,
        'data-role-slot': 'single',
        opacity: capped === 1 ? '1' : '0',
      },
      []
    ),
    makeElement(
      'rect',
      {
        'data-token': 'role',
        'data-role': roleId,
        'data-role-slot': 'pair',
        opacity: capped === 2 ? '1' : '0',
      },
      []
    ),
    makeElement(
      'rect',
      {
        'data-token': 'role',
        'data-role': roleId,
        'data-role-slot': 'pair',
        opacity: capped === 2 ? '1' : '0',
      },
      []
    ),
  ];
}

function roleElementsFor(roles) {
  const entries = [];
  const byRole = roles || {};
  ROLE_IDS.forEach((roleId) => {
    entries.push(makeElement('circle', { 'data-role-circle': roleId }, []));
    roleTokensFor(roleId, byRole[roleId]).forEach((token) => entries.push(token));
  });
  return entries;
}

const seats = (job.seats || []).map((seat) => {
  const staticKeys = ['wheat', 'stone', 'silver']
    .map((stock) => makeElement('g', { 'data-resource-choice-key': stock }, []))
    .concat([makeElement('rect', { 'data-seat-choice-key': seat.player }, [])]);
  const tokens = []
    .concat(villageTokensFor(seat.village))
    .concat(abbeyTokensFor(seat.abbey))
    .concat(roleElementsFor(seat.roles));
  return makeElement(
    'div',
    {
      'data-component': 'player-board-v2',
      'data-player-seat': String(seat.seat),
      'data-player': seat.player,
      'data-seat-taken': seat.taken ? 'true' : 'false',
      'data-active-seat': seat.active ? 'true' : 'false',
    },
    staticKeys.concat(tokens)
  );
});

const panels = [];
for (let index = 0; index < (job.panels || []).length; index += 1) {
  const actionId = job.panels[index];
  const commit = actionId ? [makeElement('button', { 'data-turn-confirm': actionId }, [])] : [];
  panels.push(makeElement('div', { 'data-turn-panel': String(index) }, commit));
}

const aside = makeElement(
  'div',
  { 'data-component': 'play-turn' },
  [].concat(phaseRows, phasePrompts, prompts, keys, pairs, confirmLabels, panels)
);

const root = makeElement(
  'document',
  {},
  [].concat([board, aside], buildings, buildingAbilityTargets, turnStepBuildings, seats)
);

const transcript = {
  offered: [],
  chosen: [],
  shownPanel: [],
  askedSeats: [],
  offeredBySeat: [],
  offeredBoards: [],
  startCandidates: [],
  startRelocationCandidates: [],
  skipCandidates: [],
  dutyCandidates: [],
  asking: [],
  resetShown: [],
  counterShown: [],
  controls: [],
  cubes: [],
  arrangements: [],
  confirmLabels: [],
  buildingAbilityTexts: [],
  buildingAbilityGreyscale: [],
  turnStepOffers: [],
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

const ARRANGEMENT_POINTER_RULES = {
  blanket: {
    abbeyToken: true,
    roleToken: true,
    roleCircle: true,
  },
  live: {
    abbeyLiftVisible: true,
    abbeyCanPlace: true,
    abbeyHeld: true,
    roleLiftVisible: true,
    roleHeld: true,
    roleCircleCanPlace: true,
    roleCircleHeld: true,
  },
};
const pointerRules = Object.assign({}, ARRANGEMENT_POINTER_RULES, job.arrangementPointerRules || {});
pointerRules.blanket = Object.assign({}, ARRANGEMENT_POINTER_RULES.blanket, pointerRules.blanket || {});
pointerRules.live = Object.assign({}, ARRANGEMENT_POINTER_RULES.live, pointerRules.live || {});

function boardOf(element) {
  let node = element;
  while (node) {
    if (
      typeof node.getAttribute === 'function'
      && node.getAttribute('data-component') === 'player-board-v2'
    ) {
      return node;
    }
    node = node.parent;
  }
  return null;
}

function arrangementKind(element) {
  const token = element.getAttribute('data-token');
  if (token === 'abbey') return 'abbey-token';
  if (token === 'role') return 'role-token';
  if (element.getAttribute('data-role-circle') !== null) return 'role-circle';
  return null;
}

function arrangementPointKey(element) {
  if (!element) return null;
  const role = element.getAttribute('data-role');
  if (
    element.getAttribute('data-token') === 'role'
    && role
    && element.getAttribute('data-role-slot') === 'single'
  ) {
    return 'role-center:' + role;
  }
  const circleRole = element.getAttribute('data-role-circle');
  if (circleRole) {
    return 'role-center:' + circleRole;
  }
  return null;
}

function arrangementElementsAtPoint(seat, pointKey) {
  if (!seat || !pointKey) return [];
  const circles = seat.querySelectorAll('[data-role-circle]');
  const singles = seat.querySelectorAll('[data-token="role"][data-role-slot="single"]');
  return circles.concat(singles).filter((element) => arrangementPointKey(element) === pointKey);
}

function arrangementElementLabel(element) {
  if (!element) return null;
  if (element.getAttribute('data-role-circle') !== null) {
    return 'role-circle:' + element.getAttribute('data-role-circle');
  }
  if (element.getAttribute('data-token') === 'role') {
    return (
      'role-token:'
      + element.getAttribute('data-role')
      + ':'
      + element.getAttribute('data-role-slot')
    );
  }
  return element.tag;
}

function tokenIsVisible(element) {
  return element.getAttribute('opacity') !== '0' && element.getAttribute('visibility') !== 'hidden';
}

function arrangementPointerEvents(element) {
  const kind = arrangementKind(element);
  if (!kind) return null;
  const kindKey = kind === 'abbey-token' ? 'abbeyToken' : kind === 'role-token' ? 'roleToken' : 'roleCircle';
  const baselineNone = pointerRules.blanket[kindKey] === true;
  let pointer = baselineNone ? 'none' : 'all';
  const seat = boardOf(element);
  if (!seat || seat.getAttribute('data-arrangement-choice') !== 'true') {
    return pointer;
  }
  const canLift = element.getAttribute('data-arrangement-can-lift') === 'true';
  const canPlace = element.getAttribute('data-arrangement-can-place') === 'true';
  const held = element.getAttribute('data-arrangement-held') === 'true';
  const visible = tokenIsVisible(element);
  if (kind === 'abbey-token') {
    if (pointerRules.live.abbeyLiftVisible && canLift && visible) return 'all';
    if (pointerRules.live.abbeyCanPlace && canPlace) return 'all';
    if (pointerRules.live.abbeyHeld && held) return 'all';
    return pointer;
  }
  if (kind === 'role-token') {
    if (pointerRules.live.roleLiftVisible && canLift && visible) return 'all';
    if (pointerRules.live.roleHeld && held) return 'all';
    return pointer;
  }
  if (pointerRules.live.roleCircleCanPlace && canPlace) return 'all';
  if (pointerRules.live.roleCircleHeld && held) return 'all';
  return pointer;
}

function ordinationPointerEvents(element) {
  const token = element.getAttribute('data-token');
  if (token !== 'village' && token !== 'abbey') return null;
  const seat = boardOf(element);
  if (!seat || seat.getAttribute('data-ordination-choice') !== 'true') {
    return token === 'village' ? 'none' : null;
  }
  const visible = tokenIsVisible(element);
  if (token === 'village') {
    const canOrdain = element.getAttribute('data-ordination-can-ordain') === 'true';
    return canOrdain && visible ? 'all' : 'none';
  }
  const canMission = element.getAttribute('data-ordination-can-mission') === 'true';
  return canMission && visible ? 'all' : 'none';
}

function endRelocationPointerEvents(element) {
  if (element.getAttribute('data-token') !== 'abbey') return null;
  const seat = boardOf(element);
  if (!seat || seat.getAttribute('data-end-relocation-choice') !== 'true') {
    return null;
  }
  return tokenIsVisible(element) ? 'all' : 'none';
}

function computedPointerEvents(element) {
  const ordination = ordinationPointerEvents(element);
  if (ordination !== null) return ordination;
  const endRelocation = endRelocationPointerEvents(element);
  if (endRelocation !== null) return endRelocation;
  const arrangement = arrangementPointerEvents(element);
  if (arrangement !== null) return arrangement;
  const attr = element.getAttribute('pointer-events');
  return attr === null ? 'all' : attr;
}

function isReachable(element) {
  if (!element) return false;
  if (element.getAttribute('visibility') === 'hidden') return false;
  return computedPointerEvents(element) !== 'none';
}

function topmostLiveAtPoint(element) {
  const pointKey = arrangementPointKey(element);
  const seat = boardOf(element);
  if (!pointKey || !seat) {
    return isReachable(element) ? element : null;
  }
  const layers = arrangementElementsAtPoint(seat, pointKey);
  for (let index = layers.length - 1; index >= 0; index -= 1) {
    if (isReachable(layers[index])) return layers[index];
  }
  return null;
}

function clickReachable(element, note) {
  if (!element) throw new Error('missing click target: ' + note);
  const resolved = topmostLiveAtPoint(element);
  if (!resolved) {
    const seat = boardOf(element);
    const pointKey = arrangementPointKey(element);
    const layers = pointKey && seat
      ? arrangementElementsAtPoint(seat, pointKey).map((layer) => (
        arrangementElementLabel(layer) + ':' + computedPointerEvents(layer)
      ))
      : [];
    throw new Error(
      'unreachable click target: '
      + note
      + (pointKey ? ' point=' + pointKey + ' layers=' + layers.join('|') : '')
    );
  }
  resolved.click();
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

function occupiedRoleTokenFor(seat, roleCounts) {
  for (const roleId of ROLE_IDS) {
    if ((roleCounts[roleId] || 0) <= 0) continue;
    const tokens = seat
      .querySelectorAll('[data-token="role"][data-role="' + roleId + '"]')
      .filter((token) => tokenIsVisible(token));
    if (tokens.length) {
      return { roleId, token: tokens[0] };
    }
  }
  return null;
}

function emptyRoleCircleFor(seat, roleCounts) {
  for (const roleId of ROLE_IDS) {
    if ((roleCounts[roleId] || 0) !== 0) continue;
    const circle = seat.querySelector('[data-role-circle="' + roleId + '"]');
    if (circle) return { roleId, circle };
  }
  return null;
}

function roleCenterLayerState(seat, roleId) {
  const pointKey = 'role-center:' + roleId;
  const layers = arrangementElementsAtPoint(seat, pointKey);
  let topmost = null;
  for (let index = layers.length - 1; index >= 0; index -= 1) {
    if (isReachable(layers[index])) {
      topmost = layers[index];
      break;
    }
  }
  return {
    drawOrder: layers.map((layer) => arrangementElementLabel(layer)),
    topmostLive: arrangementElementLabel(topmost),
  };
}

function arrangementSnapshot() {
  const bySeat = {};
  seats.forEach((seat) => {
    const seatId = seat.getAttribute('data-player-seat');
    const village = seat
      .querySelectorAll('[data-token="village"]')
      .filter((token) => token.getAttribute('opacity') !== '0').length;
    const abbey = seat
      .querySelectorAll('[data-token="abbey"]')
      .filter((token) => token.getAttribute('opacity') !== '0').length;
    const roles = {};
    ROLE_IDS.forEach((roleId) => {
      roles[roleId] = seat
        .querySelectorAll('[data-token="role"][data-role="' + roleId + '"]')
        .filter((token) => token.getAttribute('opacity') !== '0').length;
    });
    const abbeyTokens = seat.querySelectorAll('[data-token="abbey"]');
    const firstAbbeyToken = abbeyTokens[0] || null;
    const visibleAbbeyToken = abbeyTokens.find((token) => tokenIsVisible(token)) || null;
    const villageTokens = seat.querySelectorAll('[data-token="village"]');
    const firstVillageToken = villageTokens[0] || null;
    const visibleVillageToken = villageTokens.find((token) => tokenIsVisible(token)) || null;
    const firstRoleToken = seat.querySelectorAll('[data-token="role"]')[0] || null;
    const occupiedRole = occupiedRoleTokenFor(seat, roles);
    const emptyRole = emptyRoleCircleFor(seat, roles);
    const roleCenterLayers = {};
    ROLE_IDS.forEach((roleId) => {
      roleCenterLayers[roleId] = roleCenterLayerState(seat, roleId);
    });
    bySeat[seatId] = {
      player: seat.getAttribute('data-player'),
      village,
      abbey,
      roles,
      arrangementChoice: seat.getAttribute('data-arrangement-choice') === 'true',
      ordinationChoice: seat.getAttribute('data-ordination-choice') === 'true',
      occupiedRoleId: occupiedRole ? occupiedRole.roleId : null,
      emptyRoleId: emptyRole ? emptyRole.roleId : null,
      roleCenterLayers,
      pointerEvents: {
        firstVillageToken: firstVillageToken ? computedPointerEvents(firstVillageToken) : null,
        visibleVillageToken: visibleVillageToken ? computedPointerEvents(visibleVillageToken) : null,
        firstAbbeyToken: firstAbbeyToken ? computedPointerEvents(firstAbbeyToken) : null,
        visibleAbbeyToken: visibleAbbeyToken ? computedPointerEvents(visibleAbbeyToken) : null,
        firstRoleToken: firstRoleToken ? computedPointerEvents(firstRoleToken) : null,
        occupiedRoleToken: occupiedRole ? computedPointerEvents(occupiedRole.token) : null,
        emptyRoleCircle: emptyRole ? computedPointerEvents(emptyRole.circle) : null,
      },
    };
  });
  return bySeat;
}

function snapshot() {
  const offered = [];
  const chosen = [];
  const starts = [];
  const startRelocations = [];
  const skips = [];
  const duties = [];
  spaces.forEach((space, index) => {
    const asksOrigin = space.getAttribute('data-turn-start-candidate') === 'true';
    const asksStartRelocation =
      space.getAttribute('data-turn-start-relocation-candidate') === 'true';
    const asksSkip = space.getAttribute('data-turn-skip-candidate') === 'true';
    const asksDuty = space.getAttribute('data-turn-duty-candidate') === 'true';
    if (asksOrigin || asksStartRelocation || asksSkip || asksDuty) {
      offered.push(index);
    }
    if (asksOrigin) starts.push(index);
    if (asksStartRelocation) startRelocations.push(index);
    if (asksSkip) skips.push(index);
    if (asksDuty) duties.push(index);
    const pickedOrigin = space.getAttribute('data-turn-start-selected') === 'true';
    const pickedSkip = space.getAttribute('data-turn-skip-selected') === 'true';
    const pickedDuty = space.getAttribute('data-turn-duty-selected') === 'true';
    if (pickedOrigin || pickedSkip || pickedDuty) chosen.push(index);
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
    if (seat.getAttribute('data-end-relocation-choice') === 'true' && offered.indexOf('abbey') === -1) {
      offered.push('abbey');
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
  const buildingAbilityTexts = {};
  const buildingAbilityGreyscale = {};
  buildingAbilityTargets.forEach((target) => {
    const buildingId = target.getAttribute('data-building-id');
    buildingAbilityTexts[buildingId] =
      target.getAttribute('data-building-ability-text') || '';
    buildingAbilityGreyscale[buildingId] =
      target.getAttribute('data-building-ability-greyed') === 'true';
  });
  return {
    offered,
    chosen,
    shown,
    asked,
    bySeat,
    boards,
    starts,
    startRelocations,
    skips,
    duties,
    asking,
    reset: control('reset') ? control('reset').getAttribute('data-turn-control-enabled') === 'true' : false,
    counter,
    controls: states,
    controlActive: activeStates,
    cubes: cubeSnapshot(),
    arrangements: arrangementSnapshot(),
    buildingAbilityTexts,
    buildingAbilityGreyscale,
    turnStepOffers: turnStepBuildings
      .filter((building) => building.getAttribute('data-turn-step-offered') === 'true')
      .map((building) => building.getAttribute('data-turn-step-building-id')),
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
  transcript.startRelocationCandidates.push(snap.startRelocations);
  transcript.skipCandidates.push(snap.skips);
  transcript.dutyCandidates.push(snap.duties);
  transcript.asking.push(snap.asking);
  transcript.resetShown.push(snap.reset);
  transcript.counterShown.push(snap.counter);
  transcript.controls.push(snap.controls);
  transcript.controlActive = transcript.controlActive || [];
  transcript.controlActive.push(snap.controlActive);
  transcript.cubes.push(snap.cubes);
  transcript.arrangements.push(snap.arrangements);
  const confirmLabel = Array.from(document.querySelectorAll('[data-turn-control-label]')).find(
    (label) => label.getAttribute('data-turn-offered') === 'true'
  );
  transcript.confirmLabels.push(
    confirmLabel ? confirmLabel.getAttribute('data-turn-control-label') : null
  );
  transcript.buildingAbilityTexts.push(snap.buildingAbilityTexts);
  transcript.buildingAbilityGreyscale.push(snap.buildingAbilityGreyscale);
  transcript.turnStepOffers.push(snap.turnStepOffers);
  transcript.overflow.push(snap.overflow);
}

let source = job.phaseCandidateRuns
  ? phaseCandidateTemplate.replace(
    '__HARNESS_PHASE_CANDIDATES__',
    JSON.stringify(job.phaseCandidateRuns[0])
  )
  : job.script;
if (job.phaseCandidateRuns) {
  const beforePhaseHook = source;
  source = source.replace(
    '  captureBaseline();\n  captureArrangementBaseline();\n  captureOrdinationBaseline();\n  render();',
    '  window.__phaseHarnessRender = function (candidates) {\n'
      + '    CANDIDATES = candidates;\n'
      + '    chosen = [];\n'
      + '    render();\n'
      + '  };\n\n'
      + '  captureBaseline();\n  captureArrangementBaseline();\n  captureOrdinationBaseline();\n  render();'
  );
  if (source === beforePhaseHook) throw new Error('phase harness did not expose render');
}

// eslint-disable-next-line no-eval
eval(source);

if (job.phaseOnly) {
  const phaseSnapshot = () => ({
    phaseRows: phaseRows
      .filter((row) => row.getAttribute('data-phase-current') === 'true')
      .map((row) => row.getAttribute('data-turn-phase')),
  });
  if (job.phaseCandidateRuns) {
    return job.phaseCandidateRuns.map((candidates) => {
      window.__phaseHarnessRender(candidates);
      return phaseSnapshot();
    });
  }
  return phaseSnapshot();
}

record();

function pressResource(click) {
  const seat = seats.find(
    (candidate) => candidate.getAttribute('data-player-seat') === String(click.seat)
  );
  const key = seat
    .querySelectorAll('[data-resource-choice-key]')
    .find((candidate) => candidate.getAttribute('data-resource-choice-key') === click.value);
  clickReachable(key, 'resource ' + click.value + ' on seat ' + String(click.seat));
}

function pressBoard(click) {
  const seat = seats.find(
    (candidate) => candidate.getAttribute('data-player') === click.value
  );
  const key = seat
    .querySelectorAll('[data-seat-choice-key]')
    .find((candidate) => candidate.getAttribute('data-seat-choice-key') === click.value);
  clickReachable(key, 'seat ' + click.value);
}

function activeSeat() {
  return seats.find((seat) => seat.getAttribute('data-active-seat') === 'true') || null;
}

function pressVillage() {
  const seat = activeSeat();
  if (!seat) throw new Error('no active seat for village click');
  const tokens = seat.querySelectorAll('[data-token="village"]');
  const target = tokens.find((token) => isReachable(token)) || null;
  clickReachable(target, 'village token');
}

function pressAbbey() {
  const seat = activeSeat();
  if (!seat) throw new Error('no active seat for abbey click');
  const tokens = seat.querySelectorAll('[data-token="abbey"]');
  const target = tokens.find((token) => isReachable(token)) || null;
  clickReachable(target, 'abbey token');
}

function pressRole(click) {
  const seat = activeSeat();
  if (!seat) throw new Error('no active seat for role click');
  if (click.target === 'circle') {
    const circle = seat.querySelector('[data-role-circle="' + click.value + '"]');
    clickReachable(circle, 'role circle ' + click.value);
    return;
  }
  const tokens = seat.querySelectorAll('[data-token="role"][data-role="' + click.value + '"]');
  const target = tokens.find((token) => isReachable(token)) || null;
  clickReachable(target, 'role token ' + click.value);
}

job.clicks.forEach((click) => {
  if (
    click.kind === 'position'
    || click.kind === 'origin'
    || click.kind === 'skip'
    || click.kind === 'duty'
  ) {
    const target = spaces.find((space) =>
      Number(space.getAttribute('data-board-position-index')) === Number(click.value));
    clickReachable(target, click.kind + ' ' + String(click.value));
  } else if (click.kind === 'edge') {
    const target = arrows.find((arrow) => arrow.getAttribute('data-arrow') === click.value);
    clickReachable(target, 'edge ' + click.value);
  } else if (click.kind === 'control') {
    const button = control(click.value);
    clickReachable(button, 'control ' + click.value);
  } else if (click.kind === 'combination') {
    const target = pairs.find((pair) => pair.getAttribute('data-combination-key') === click.value);
    clickReachable(target, 'combination ' + click.value);
  } else if (click.kind === 'resource') {
    pressResource(click);
  } else if (click.kind === 'seat') {
    pressBoard(click);
  } else if (click.kind === 'building') {
    const target = buildings.find((key) => key.getAttribute('data-building-choice-key') === click.value);
    clickReachable(target, 'building ' + click.value);
  } else if (click.kind === 'village') {
    pressVillage();
  } else if (click.kind === 'abbey') {
    pressAbbey();
  } else if (click.kind === 'role') {
    pressRole(click);
  } else {
    const target = keys.find((key) => key.getAttribute('data-resolution-key') === click.value);
    clickReachable(target, 'resolution ' + click.value);
  }
  record();
});

if (job.reset) {
  const reset = control('reset');
  clickReachable(reset, 'control reset');
  const snap = snapshot();
  transcript.afterReset = {
    offered: snap.offered,
    chosen: snap.chosen,
    shown: snap.shown,
    asking: snap.asking,
    startCandidates: snap.starts,
    startRelocationCandidates: snap.startRelocations,
    skipCandidates: snap.skips,
    dutyCandidates: snap.duties,
    reset: snap.reset,
    counter: snap.counter,
    controls: snap.controls,
    controlActive: snap.controlActive,
    cubes: snap.cubes,
    arrangements: snap.arrangements,
    overflow: snap.overflow,
  };
}

if (job.confirm) {
  const confirmControl = control('confirm');
  clickReachable(confirmControl, 'control confirm');
  transcript.confirmable =
    confirmControl && confirmControl.getAttribute('data-turn-control-enabled') === 'true';
}

transcript.resetVisible = control('reset')
  ? control('reset').getAttribute('data-turn-control-enabled')
  : null;
return transcript;
}

const output = Array.isArray(input.runs)
  ? input.runs.map((run) => runJob(Object.assign({}, input, run)))
  : runJob(input);
process.stdout.write(JSON.stringify(output));
