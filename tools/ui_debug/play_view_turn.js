(function () {
  'use strict';
  /* CLICKING FILTERS AND REVEALS. IT DOES NOT CONSTRUCT.

     Every candidate below is an answer the engine already offered, carrying the sequence of
     decisions that reaches it. This narrows that list. It never invents a move, never asks whether
     a step is allowed, and never derives the hand count: each count is read off a step the seam
     already provided. */
  var CANDIDATES = __CANDIDATES__;
  var FAMILIES = __FAMILIES__;
  var TURN_STEPS = __TURN_STEPS__;
  var USED_BUILDINGS = __USED_BUILDINGS__;
  var RESOLUTION_COMMITTED = __RESOLUTION_COMMITTED__;
  var PHASE_COLUMN_SCOPE = __PHASE_COLUMN_SCOPE__;
  var TOKEN = __TOKEN__;
  var ALMS_POSITION_TARGETS = __ALMS_POSITION_TARGETS__;
  var BUILDING_ABILITIES = __BUILDING_ABILITIES__;
  var BUILDING_ABILITY_WINDOWS = __BUILDING_ABILITY_WINDOWS__;
  var currentTurnPhase = __BUILDING_ABILITY_WINDOW__;
  var buildingAbilityTargets = document.querySelectorAll('[data-building-id]');

  function buildingAbilityWindow() {
    return BUILDING_ABILITY_WINDOWS[currentTurnPhase] || {
      turn_steps_offered: false,
      abilities: BUILDING_ABILITIES
    };
  }

  function buildingAbilityFor(buildingId) {
    var abilities = buildingAbilityWindow().abilities || BUILDING_ABILITIES;
    for (var index = 0; index < abilities.length; index += 1) {
      if (abilities[index].building_id === buildingId) {
        return abilities[index];
      }
    }
    return null;
  }

  function renderBuildingAbilityTexts(liveSteps) {
    var inEffect = Array.isArray(chosen) ? familiesInEffect() : [];
    var familyOriginChosen = Array.isArray(chosen) && familyOriginIsChosen();
    Array.prototype.forEach.call(buildingAbilityTargets, function (target) {
      var buildingId = target.getAttribute('data-building-id');
      var ability = buildingAbilityFor(buildingId);
      if (conversionChosen && conversionChosen[0] === buildingId && liveSteps.length === 1) {
        ability = liveSteps[0].ability || ability;
      }
      var abilityText = inEffect.indexOf(buildingId) !== -1
          && ability && typeof ability.in_effect_status_text === 'string'
          ? ability.in_effect_status_text
          : !familyOriginChosen && ability && typeof ability.toggle_waiting_text === 'string'
          ? ability.toggle_waiting_text
          : ability && target.getAttribute('data-turn-family-state') === 'on'
            && typeof ability.toggle_on_text === 'string'
          ? ability.toggle_on_text
          : ability && typeof ability.toggle_off_text === 'string'
          ? ability.toggle_off_text
          : ability && typeof ability.status_text === 'string' ? ability.status_text : '';
      target.setAttribute('data-building-ability-text', abilityText);
      var visibleTooltip = document.querySelector('[data-building-tooltip="true"]');
      if (
        visibleTooltip
        && visibleTooltip.getAttribute('data-building-tooltip-for') === buildingId
      ) {
        var tooltipAbility = visibleTooltip.querySelector('[data-building-tooltip-ability="true"]');
        if (tooltipAbility) { tooltipAbility.textContent = abilityText; }
      }
      target.setAttribute(
        'data-building-ability-greyed',
        ability && ability.greyed === true ? 'true' : 'false'
      );
    });
  }

  renderBuildingAbilityTexts([]);
  if (!CANDIDATES.length && !TURN_STEPS.length) { return; }

  var board = document.querySelector('[data-component="duty-wheel"]');
  var aside = document.querySelector('[data-component="play-turn"]');
  if (!board || !aside) { return; }
  var spaces = board.querySelectorAll('[data-board-position-index]');
  var ornaments = board.querySelectorAll('.ornament-header g');
  var arrows = board.querySelectorAll('[data-arrow]');
  var counters = board.querySelectorAll('[data-turn-counter]');
  var merchantTokens = board.querySelectorAll('[data-token="merchant"]');
  var prompts = aside.querySelectorAll('[data-turn-prompt]');
  var hireFact = aside.querySelector('[data-turn-hire-fact]');
  var phaseRows = aside.querySelectorAll('[data-turn-phase]');
  var phasePrompts = aside.querySelectorAll('[data-turn-phase-prompt]');
  var keys = aside.querySelectorAll('[data-resolution-key]');
  var pairs = aside.querySelectorAll('[data-combination-key]');
  var ordinationActions = aside.querySelectorAll('[data-ordination-action]');
  var turnStepDirections = aside.querySelectorAll('[data-turn-step-direction]');
  var turnStepResourceRow = aside.querySelector('[data-turn-step-resource-row]');
  var turnStepHireRow = aside.querySelector('[data-turn-step-hire-row]');
  var turnStepHireText = aside.querySelector('[data-turn-step-hire-text]');
  var turnStepHireButtons = aside.querySelectorAll('[data-turn-step-hire-payment]');
  var turnStepDirectionRow = aside.querySelector('[data-turn-step-direction-row]');
  var turnStepDirectionLabel = aside.querySelector('[data-turn-step-direction-label]');
  var turnStepActivationPrompt = aside.querySelector('[data-turn-step-activation-prompt]');
  var turnStepResourceKeys = document.querySelectorAll('[data-resource-choice-key]');
  var pietyChoicePills = document.querySelectorAll('[data-piety-choice-template]');
  var turnStepAmountTotal = aside.querySelector('[data-turn-step-amount-total="true"]');
  var turnStepAnswerLabel = aside.querySelector('[data-turn-step-answer-label="true"]');
  var turnStepResourceHint = aside.querySelector('[data-turn-step-resource-hint="true"]');
  var panels = aside.querySelectorAll('[data-turn-panel]');
  /* Every seat's board, so the one being asked can be picked out of them and the rest left alone.
     Which seat that is is read off the page, where it is already written down, rather than worked
     out here from whose turn it might be. */
  var seats = document.querySelectorAll('[data-component="player-board-v2"][data-player-seat]');
  /* Every building the round track carries. Which hex each one stands on is the map's business and
     is not asked about here: a key names the building it belongs to, so this never learns the
     rotation the track was drawn at. */
  var buildings = document.querySelectorAll('[data-building-choice-key]');
  var chosen = [];
  var answered = [];
  var enabledFamilies = [];
  var resolutionSplit = null;
  var baseline = [];
  var resourceBaseline = [];
  var merchantBaseline = [];
  var buildingSlotBaseline = [];
  var pietyDiscBaseline = [];
  var almsDiscBaseline = null;
  var almsWorkforceBaseline = [];
  var merchantBoardBaseline = board.getAttribute('data-merchant-token');
  var activePlayer = null;
  var activeSeat = null;
  var arrangementBaseline = [];
  var arrangementStartCounts = null;
  var arrangementHeldFrom = null;
  var arrangementEnvelope = null;
  var ordinationBaseline = [];
  var ordinationStartCounts = null;
  var ordinationOffered = [];
  var conversionChosen = [];
  var resourceAllocation = {};
  var resourceAllocationTotal = null;
  var requestInFlight = false;
  var conversionBuildings = document.querySelectorAll('[data-turn-step-building-id]');
  Array.prototype.forEach.call(seats, function (seat) {
    if (seat.getAttribute('data-active-seat') === 'true') {
      activePlayer = seat.getAttribute('data-player');
      activeSeat = seat;
    }
  });

  function matchingCandidates(prefix) {
    var answers = prefix || chosen;
    return CANDIDATES.filter(function (candidate) {
      return answers.every(function (answer, index) {
        var step = candidate.steps[index];
        return step !== undefined && step.value === answer;
      });
    });
  }

  function familyBuildingIds(candidate) {
    return (candidate.family || []).map(function (index) {
      var building = FAMILIES[index];
      return building ? building.building_id : null;
    }).filter(function (buildingId) { return buildingId !== null; });
  }

  function familyForStep(step) {
    var buildingIndex = step.family;
    return buildingIndex === undefined ? null : FAMILIES[buildingIndex] || null;
  }

  function enabledFamiliesAllow(candidate) {
    return familyBuildingIds(candidate).every(function (buildingId) {
      return enabledFamilies.indexOf(buildingId) !== -1;
    });
  }

  function surviving(prefix) {
    return matchingCandidates(prefix).filter(enabledFamiliesAllow);
  }

  function familyBuildingIdsOn(candidates) {
    var ids = [];
    candidates.forEach(function (candidate) {
      familyBuildingIds(candidate).forEach(function (buildingId) {
        if (ids.indexOf(buildingId) === -1) { ids.push(buildingId); }
      });
    });
    return ids;
  }

  function familiesInEffect() {
    var effects = [];
    var prefix = [];
    chosen.forEach(function (answer) {
      var live = surviving(prefix);
      live.forEach(function (candidate) {
        var step = candidate.steps[prefix.length];
        var building = step && step.value === answer ? familyForStep(step) : null;
        if (!building) { return; }
        if (effects.indexOf(building.building_id) === -1) {
          effects.push(building.building_id);
        }
      });
      prefix.push(answer);
    });
    return effects;
  }

  function familyOriginIsChosen() {
    if (!chosen.length) { return false; }
    return matchingCandidates().some(function (candidate) {
      var firstStep = candidate.steps[0];
      return familyBuildingIds(candidate).length > 0 && firstStep && firstStep.kind === 'origin';
    });
  }

  function resetPreview() {
    restoreArrangementBaseline();
    restoreOrdinationBaseline();
    chosen = [];
    answered = [];
    resourceAllocation = {};
    resourceAllocationTotal = null;
    conversionChosen = [];
    resolutionSplit = null;
  }

  function renderFamilies() {
    var available = familyBuildingIdsOn(matchingCandidates());
    var inEffect = familiesInEffect();
    var familyOriginChosen = familyOriginIsChosen();
    Array.prototype.forEach.call(buildingAbilityTargets, function (target) {
      var buildingId = target.getAttribute('data-building-id');
      if (available.indexOf(buildingId) === -1) {
        target.removeAttribute('data-turn-family-state');
        target.removeAttribute('data-turn-family-available');
        return;
      }
      var effect = inEffect.indexOf(buildingId) !== -1;
      target.setAttribute(
        'data-turn-family-state', effect ? 'in_effect' : enabledFamilies.indexOf(buildingId) !== -1 ? 'on' : 'off'
      );
      target.setAttribute(
        'data-turn-family-available', effect || !familyOriginChosen ? 'false' : 'true'
      );
      target.setAttribute('data-building-ability-greyed', 'false');
    });
  }

  function onlyActionId(candidates) {
    if (candidates.length !== 1 || candidates[0].action_id === null) { return null; }
    return candidates[0].action_id;
  }

  function renderPhase(current) {
    if (PHASE_COLUMN_SCOPE !== 'turn') { return; }
    if (current === null) { return; }
    currentTurnPhase = current;
    Array.prototype.forEach.call(phaseRows, function (row) {
      if (row.getAttribute('data-turn-phase') === current) {
        row.setAttribute('data-phase-current', 'true');
      } else {
        row.removeAttribute('data-phase-current');
      }
    });
    Array.prototype.forEach.call(phasePrompts, function (prompt) {
      if (prompt.getAttribute('data-turn-phase-prompt') === current) {
        prompt.setAttribute('data-turn-phase-prompt-current', 'true');
      } else {
        prompt.removeAttribute('data-turn-phase-prompt-current');
      }
    });
  }

  function turnStepAnswer(step, index) {
    return step.answers && step.answers[index] ? step.answers[index] : null;
  }

  function turnStepField(step, index) {
    var answer = turnStepAnswer(step, index);
    return answer ? answer.value : null;
  }

  function turnStepAnswerIndex(live, field) {
    if (!live.length) { return -1; }
    var index = -1;
    var inconsistent = false;
    live.forEach(function (step) {
      var answers = step.answers || [];
      answers.forEach(function (answer, answerIndex) {
        if (answer.field !== field) { return; }
        if (index === -1) { index = answerIndex; }
        else if (index !== answerIndex) { inconsistent = true; }
      });
    });
    return inconsistent ? -1 : index;
  }

  function turnStepNextField(live) {
    var index = conversionChosen.length;
    var field = null;
    live.forEach(function (step) {
      var answer = turnStepAnswer(step, index);
      if (!answer) { return; }
      if (field === null) { field = answer.field; }
      else if (field !== answer.field) {
        throw new Error('turn-step answer field changed across surviving steps');
      }
    });
    return field;
  }

  function survivingTurnSteps(prefix) {
    var answers = prefix || conversionChosen;
    return TURN_STEPS.filter(function (step) {
      return answers.every(function (answer, index) {
        var field = turnStepField(step, index);
        return field !== null && String(field) === String(answer);
      });
    });
  }

  function offeredTurnStepValues(index, live) {
    var values = [];
    live.forEach(function (step) {
      var value = String(turnStepField(step, index));
      if (values.indexOf(value) === -1) { values.push(value); }
    });
    return values;
  }

  function pietySilverFor(destination, live) {
    var values = [];
    live.forEach(function (step) {
      var index = turnStepAnswerIndex([step], 'piety_destination');
      if (index === -1 || String(turnStepField(step, index)) !== String(destination)) { return; }
      var value = Number(step.silver_delta);
      if (values.indexOf(value) === -1) { values.push(value); }
    });
    if (values.length > 1) {
      throw new Error('piety destination has inconsistent conversion silver deltas');
    }
    return values.length === 1 ? values[0] : null;
  }

  function pietyAmountFor(live) {
    var values = [];
    live.forEach(function (step) {
      var value = Number(step.amount);
      if (values.indexOf(value) === -1) { values.push(value); }
    });
    if (values.length > 1) {
      throw new Error('piety conversion has inconsistent amounts');
    }
    return values.length === 1 ? values[0] : null;
  }

  function conversionReady() {
    var live = survivingTurnSteps();
    return live.length === 1 && conversionChosen.length === (live[0].answers || []).length;
  }

  function autoAdvanceHirePayment() {
    while (true) {
      var live = survivingTurnSteps();
      var field = turnStepNextField(live);
      var values = field === 'hire_payment'
        ? offeredTurnStepValues(conversionChosen.length, live)
        : [];
      if (values.length !== 1) { return; }
      conversionChosen.push(values[0]);
    }
  }

  function chooseTurnStepAnswer(field, value) {
    var live = survivingTurnSteps();
    if (turnStepNextField(live) !== field) { return false; }
    conversionChosen.push(String(value));
    autoAdvanceHirePayment();
    return true;
  }

  function conversionNeedsAmountResource() {
    var live = survivingTurnSteps();
    var amountIndex = turnStepAnswerIndex(live, 'amount');
    return amountIndex !== -1 && conversionChosen.length >= amountIndex;
  }

  function abandonConversion() {
    conversionChosen = [];
  }

  function renderTurnSteps() {
    var live = survivingTurnSteps();
    var buildingWindow = buildingAbilityWindow();
    var availableBuildings = buildingWindow.turn_steps_offered === true
      ? offeredTurnStepValues(0, TURN_STEPS)
      : [];
    var activation = live.length === 1 && live[0].kind === 'activation'
      && conversionChosen.length === (live[0].answers || []).length;
    var nextField = turnStepNextField(live);
    var buildingIndex = turnStepAnswerIndex(live, 'building');
    var directionIndex = turnStepAnswerIndex(live, 'direction');
    var hireIndex = turnStepAnswerIndex(live, 'hire_payment');
    var pietyIndex = turnStepAnswerIndex(live, 'piety_destination');
    var amountIndex = turnStepAnswerIndex(live, 'amount');
    var directions = nextField === 'direction'
      ? offeredTurnStepValues(conversionChosen.length, live)
      : directionIndex !== -1 && conversionChosen.length > directionIndex
        ? [String(conversionChosen[directionIndex])]
        : [];
    var relocation = nextField === 'selected_position';
    var relocationTargets = relocation ? offeredTurnStepValues(conversionChosen.length, live) : [];
    var piety = pietyIndex !== -1 && conversionChosen.length >= pietyIndex;
    var resource = amountIndex !== -1 && conversionChosen.length >= amountIndex;
    var pietyAmount = piety && conversionChosen.length > pietyIndex
      ? pietyAmountFor(live) : null;
    var resourceId = null;
    if (resource) {
      resourceId = String(turnStepAnswer(live[0], amountIndex).label);
    }
    if (conversionChosen.length > 0) {
      Array.prototype.forEach.call(seats, function (seat) {
        if (resource && seat.getAttribute('data-active-seat') === 'true') {
          seat.setAttribute('data-resource-choice', 'true');
        } else {
          seat.removeAttribute('data-resource-choice');
        }
      });
    }

    Array.prototype.forEach.call(conversionBuildings, function (building) {
      var buildingId = building.getAttribute('data-turn-step-building-id');
      var used = USED_BUILDINGS.indexOf(buildingId) !== -1;
      var offered = !used && availableBuildings.indexOf(buildingId) !== -1;
      building.setAttribute('data-turn-step-offered', offered ? 'true' : 'false');
      building.setAttribute(
        'data-turn-step-selected',
        conversionChosen.length > 0 && conversionChosen[0] === buildingId ? 'true' : 'false'
      );
      building.setAttribute('data-turn-step-used', used ? 'true' : 'false');
      var ability = buildingAbilityFor(buildingId);
      building.setAttribute(
        'data-building-ability-greyed',
        ability && ability.greyed === true ? 'true' : 'false'
      );
    });
    Array.prototype.forEach.call(turnStepDirections, function (button) {
      var value = button.getAttribute('data-turn-step-direction');
      button.setAttribute('data-turn-step-offered', directions.indexOf(value) === -1 ? 'false' : 'true');
      button.setAttribute(
        'data-turn-step-selected',
        directionIndex !== -1 && conversionChosen.length > directionIndex
          && conversionChosen[directionIndex] === value ? 'true' : 'false'
      );
    });
    var directionActive = directionIndex !== -1 && buildingIndex !== -1
      && conversionChosen.length > buildingIndex;
    if (turnStepDirectionRow) {
      turnStepDirectionRow.setAttribute(
        'data-turn-step-row-active',
        directionActive || activation ? 'true' : 'false'
      );
      turnStepDirectionRow.setAttribute(
        'data-turn-step-activation-companion', activation ? 'true' : 'false'
      );
    }
    if (turnStepDirectionLabel) {
      turnStepDirectionLabel.setAttribute(
        'data-turn-step-direction-label-visible', activation ? 'false' : 'true'
      );
    }
    if (turnStepActivationPrompt) {
      turnStepActivationPrompt.textContent = activation && live.length ? live[0].prompt : '';
      turnStepActivationPrompt.setAttribute(
        'data-turn-step-activation-active', activation ? 'true' : 'false'
      );
    }
    Array.prototype.forEach.call(spaces, function (space) {
      var index = String(space.getAttribute('data-board-position-index'));
      if (relocationTargets.indexOf(index) === -1) {
        space.removeAttribute('data-turn-step-relocation-candidate');
      } else {
        space.setAttribute('data-turn-step-relocation-candidate', 'true');
      }
    });
    if (activeSeat) {
      if (relocationTargets.indexOf('abbey') !== -1) {
        activeSeat.setAttribute('data-end-relocation-choice', 'true');
      } else {
        activeSeat.removeAttribute('data-end-relocation-choice');
      }
    }
    if (turnStepResourceRow) {
      turnStepResourceRow.setAttribute(
        'data-turn-step-row-active',
        piety || resource || relocation ? 'true' : 'false'
      );
    }
    var pietyTrack = document.querySelector('[data-component="piety-track-v2"]');
    var pietyPreviewed = pietyTrack
      && pietyTrack.getAttribute('data-piety-preview-position') !== null;
    var pietyHasOffer = piety && (
      conversionChosen.length > pietyIndex
      || (!pietyPreviewed && live.some(function (step) {
        return turnStepField(step, pietyIndex) !== null;
      }))
    );
    if (turnStepAnswerLabel) {
      turnStepAnswerLabel.textContent = 'Amount';
      turnStepAnswerLabel.setAttribute(
        'data-turn-step-answer-label-visible',
        piety ? (pietyHasOffer ? 'true' : 'false') : (resource ? 'true' : 'false')
      );
    }
    if (turnStepResourceHint) {
      turnStepResourceHint.textContent = relocation
        ? (live.length ? live[0].prompt : '') : '';
    }
    var hireText = conversionChosen.length && live.length ? live[0].hire_text || '' : '';
    var hirePayments = nextField === 'hire_payment'
      ? offeredTurnStepValues(conversionChosen.length, live)
      : [];
    if (turnStepHireRow) {
      turnStepHireRow.setAttribute(
        'data-turn-step-row-active',
        hireText ? 'true' : 'false'
      );
      turnStepHireRow.setAttribute(
        'data-turn-step-activation-companion', activation ? 'true' : 'false'
      );
    }
    if (turnStepHireText) { turnStepHireText.textContent = hireText; }
    Array.prototype.forEach.call(turnStepHireButtons, function (button) {
      var payment = button.getAttribute('data-turn-step-hire-payment');
      var offered = hirePayments.length > 1 && hirePayments.indexOf(payment) !== -1;
      button.setAttribute('data-turn-step-hire-offered', offered ? 'true' : 'false');
      button.setAttribute(
        'data-turn-step-hire-selected',
        hireIndex !== -1 && conversionChosen.length > hireIndex
          && conversionChosen[hireIndex] === payment ? 'true' : 'false'
      );
    });
    if (conversionChosen.length > 0) {
      Array.prototype.forEach.call(turnStepResourceKeys, function (key) {
        var amountCandidates = amountIndex === -1
          ? [] : survivingTurnSteps(conversionChosen.slice(0, amountIndex));
        var currentAmount = amountIndex !== -1 && conversionChosen.length > amountIndex
          ? Number(conversionChosen[amountIndex]) : 0;
        var offered = resource && key.getAttribute('data-resource-choice-key') === resourceId
          && amountCandidates.some(function (step) {
            return Number(turnStepField(step, amountIndex)) > currentAmount;
          });
        key.setAttribute('data-turn-offered', offered ? 'true' : 'false');
      });
    }
    Array.prototype.forEach.call(pietyChoicePills, function (choice) {
      var destination = choice.getAttribute('data-piety-choice-destination');
      var offered = piety && !pietyPreviewed && live.some(function (step) {
        return String(turnStepField(step, pietyIndex)) === String(destination);
      });
      if (offered) {
        choice.setAttribute('data-piety-choice-pill', 'true');
      } else {
        choice.removeAttribute('data-piety-choice-pill');
      }
      choice.setAttribute('data-piety-choice-offered', offered ? 'true' : 'false');
      choice.setAttribute('visibility', offered ? 'visible' : 'hidden');
      choice.setAttribute(
        'data-piety-choice-selected',
        conversionChosen.length > pietyIndex
          && String(conversionChosen[pietyIndex]) === String(destination)
          ? 'true' : 'false'
      );
      if (offered) {
        var silver = pietySilverFor(destination, live);
        if (silver === null) {
          throw new Error('offered piety destination has no conversion silver figure');
        }
        var silverText = choice.querySelector('[data-piety-choice-silver]');
        if (silverText) { silverText.textContent = silver >= 0 ? '+' + silver : String(silver); }
      }
    });
    if (turnStepAmountTotal) {
      turnStepAmountTotal.textContent = resource && conversionChosen.length > amountIndex
        ? conversionChosen[amountIndex]
        : pietyAmount === null ? '' : pietyAmount;
    }
    renderFamilies();
    renderBuildingAbilityTexts(live);
  }

  function tokenVisible(token) {
    return token.getAttribute('opacity') !== '0' && token.getAttribute('visibility') !== 'hidden';
  }

  function roleIdsOnActiveSeat() {
    var found = [];
    if (!activeSeat) { return found; }
    Array.prototype.forEach.call(activeSeat.querySelectorAll('[data-role-circle]'), function (circle) {
      var role = circle.getAttribute('data-role-circle');
      if (role && found.indexOf(role) === -1) {
        found.push(role);
      }
    });
    return found;
  }

  function abbeyTokensOnActiveSeat() {
    if (!activeSeat) { return []; }
    var tokens = Array.prototype.slice.call(activeSeat.querySelectorAll('[data-token="abbey"]'));
    tokens.sort(function (left, right) {
      return Number(left.getAttribute('data-token-index')) - Number(right.getAttribute('data-token-index'));
    });
    return tokens;
  }

  function villageTokensOnActiveSeat() {
    if (!activeSeat) { return []; }
    var tokens = Array.prototype.slice.call(activeSeat.querySelectorAll('[data-token="village"]'));
    tokens.sort(function (left, right) {
      return Number(left.getAttribute('data-token-index')) - Number(right.getAttribute('data-token-index'));
    });
    return tokens;
  }

  function citySlotsForActiveSeat() {
    if (!board || !activePlayer) { return []; }
    var slots = Array.prototype.slice.call(
      board.querySelectorAll(
        '[data-city-column-player="' + activePlayer + '"][data-city-cube]'
      )
    );
    slots.sort(function (left, right) {
      return Number(left.getAttribute('data-city-cube')) - Number(right.getAttribute('data-city-cube'));
    });
    return slots;
  }

  function roleTokensOnActiveSeat(roleId) {
    if (!activeSeat) { return []; }
    return Array.prototype.slice.call(
      activeSeat.querySelectorAll('[data-token="role"][data-role="' + roleId + '"]')
    );
  }

  function roleCircleOnActiveSeat(roleId) {
    if (!activeSeat) { return null; }
    return activeSeat.querySelector('[data-role-circle="' + roleId + '"]');
  }

  function roleCount(roleId) {
    return roleTokensOnActiveSeat(roleId).filter(tokenVisible).length;
  }

  function abbeyCount() {
    return abbeyTokensOnActiveSeat().filter(tokenVisible).length;
  }

  function villageCount() {
    return villageTokensOnActiveSeat().filter(tokenVisible).length;
  }

  function cityCount() {
    return citySlotsForActiveSeat().filter(tokenVisible).length;
  }

  function currentArrangementCounts() {
    if (!activeSeat) { return null; }
    var counts = { abbey: abbeyCount() };
    roleIdsOnActiveSeat().forEach(function (roleId) {
      counts[roleId] = roleCount(roleId);
    });
    return counts;
  }

  function setRoleCount(roleId, count) {
    if (!activeSeat) { return; }
    var capped = Math.max(0, Math.min(2, Number(count) || 0));
    var single = activeSeat.querySelector(
      '[data-token="role"][data-role="' + roleId + '"][data-role-slot="single"]'
    );
    var pair = activeSeat.querySelectorAll(
      '[data-token="role"][data-role="' + roleId + '"][data-role-slot="pair"]'
    );
    if (single) {
      single.setAttribute('opacity', capped === 1 ? '1' : '0');
    }
    Array.prototype.forEach.call(pair, function (token) {
      token.setAttribute('opacity', capped === 2 ? '1' : '0');
    });
  }

  function setAbbeyCount(count) {
    var capped = Math.max(0, Math.min(abbeyTokensOnActiveSeat().length, Number(count) || 0));
    abbeyTokensOnActiveSeat().forEach(function (token, index) {
      token.setAttribute('opacity', index < capped ? '1' : '0');
    });
  }

  function setVillageCount(count) {
    var capped = Math.max(0, Math.min(villageTokensOnActiveSeat().length, Number(count) || 0));
    villageTokensOnActiveSeat().forEach(function (token, index) {
      token.setAttribute('opacity', index < capped ? '1' : '0');
    });
  }

  function setCityCount(count) {
    var capped = Math.max(0, Math.min(citySlotsForActiveSeat().length, Number(count) || 0));
    citySlotsForActiveSeat().forEach(function (slot, index) {
      slot.setAttribute('opacity', index < capped ? '1' : '0');
    });
  }

  function setAllocationCount(slot, count) {
    if (slot === 'abbey') {
      setAbbeyCount(count);
      return;
    }
    setRoleCount(slot, count);
  }

  function parseArrangementValue(value) {
    if (value === 'none' || value === '') { return {}; }
    var parsed = {};
    String(value).split(',').forEach(function (part) {
      var split = part.split('=');
      if (split.length !== 2) { return; }
      var slot = split[0];
      var delta = Number(split[1]);
      if (!slot || Number.isNaN(delta)) { return; }
      parsed[slot] = delta;
    });
    return parsed;
  }

  function encodeArrangementDelta(start, current) {
    var slots = Object.keys(start || {}).sort();
    var parts = [];
    slots.forEach(function (slot) {
      var delta = (current[slot] || 0) - (start[slot] || 0);
      if (!delta) { return; }
      parts.push(slot + '=' + (delta > 0 ? '+' + String(delta) : String(delta)));
    });
    return parts.length ? parts.join(',') : 'none';
  }

  function arrangementEnvelopeFor(values) {
    if (!arrangementStartCounts) {
      arrangementStartCounts = currentArrangementCounts();
    }
    if (!arrangementStartCounts) {
      return { low: {}, high: {} };
    }
    var vectors = values.map(parseArrangementValue);
    var low = {};
    var high = {};
    Object.keys(arrangementStartCounts).forEach(function (slot) {
      var minDelta = 0;
      var maxDelta = 0;
      vectors.forEach(function (vector) {
        var delta = Object.prototype.hasOwnProperty.call(vector, slot) ? vector[slot] : 0;
        minDelta = Math.min(minDelta, delta);
        maxDelta = Math.max(maxDelta, delta);
      });
      low[slot] = arrangementStartCounts[slot] + minDelta;
      high[slot] = arrangementStartCounts[slot] + maxDelta;
    });
    return { low: low, high: high };
  }

  function arrangementSelection(values) {
    if (!values.length || !activeSeat) { return null; }
    if (!arrangementStartCounts) {
      arrangementStartCounts = currentArrangementCounts();
    }
    var current = currentArrangementCounts();
    if (!arrangementStartCounts || !current) { return null; }
    var encoded = encodeArrangementDelta(arrangementStartCounts, current);
    return values.indexOf(encoded) === -1 ? null : encoded;
  }

  function clearArrangementMarks() {
    if (!activeSeat) { return; }
    activeSeat.removeAttribute('data-arrangement-choice');
    Array.prototype.forEach.call(
      activeSeat.querySelectorAll(
        '[data-arrangement-can-lift],[data-arrangement-can-place],[data-arrangement-held]'
      ),
      function (node) {
        node.removeAttribute('data-arrangement-can-lift');
        node.removeAttribute('data-arrangement-can-place');
        node.removeAttribute('data-arrangement-held');
      }
    );
  }

  function markArrangementSlot(slot, counts) {
    if (!activeSeat || !arrangementEnvelope) { return; }
    var current = counts[slot] || 0;
    var low = arrangementEnvelope.low[slot];
    var high = arrangementEnvelope.high[slot];
    var canLift = current - 1 >= low;
    var canPlace = current + 1 <= high;
    var held = arrangementHeldFrom === slot;
    var waitingToPlace = arrangementHeldFrom !== null;
    var canLiftNow = !waitingToPlace && canLift;
    var canPlaceNow = waitingToPlace && canPlace;

    if (slot === 'abbey') {
      abbeyTokensOnActiveSeat().forEach(function (token) {
        token.setAttribute('data-arrangement-can-lift', canLiftNow ? 'true' : 'false');
        token.setAttribute('data-arrangement-can-place', canPlaceNow ? 'true' : 'false');
        token.setAttribute('data-arrangement-held', held ? 'true' : 'false');
      });
      return;
    }

    roleTokensOnActiveSeat(slot).forEach(function (token) {
      token.setAttribute('data-arrangement-can-lift', canLiftNow ? 'true' : 'false');
      token.setAttribute('data-arrangement-can-place', canPlaceNow ? 'true' : 'false');
      token.setAttribute('data-arrangement-held', held ? 'true' : 'false');
    });
    var circle = roleCircleOnActiveSeat(slot);
    if (!circle) { return; }
    circle.setAttribute('data-arrangement-can-lift', canLiftNow ? 'true' : 'false');
    circle.setAttribute('data-arrangement-can-place', canPlaceNow ? 'true' : 'false');
    circle.setAttribute('data-arrangement-held', held ? 'true' : 'false');
  }

  function showArrangement(values) {
    if (!activeSeat) { return; }
    if (!values.length) {
      arrangementStartCounts = null;
      arrangementEnvelope = null;
      arrangementHeldFrom = null;
      clearArrangementMarks();
      return;
    }
    activeSeat.setAttribute('data-arrangement-choice', 'true');
    arrangementEnvelope = arrangementEnvelopeFor(values);
    var counts = currentArrangementCounts() || {};
    markArrangementSlot('abbey', counts);
    roleIdsOnActiveSeat().forEach(function (roleId) {
      markArrangementSlot(roleId, counts);
    });
  }

  function captureArrangementBaseline() {
    arrangementBaseline = [];
    if (!activeSeat) { return; }
    Array.prototype.forEach.call(
      activeSeat.querySelectorAll('[data-token="abbey"],[data-token="role"]'),
      function (token) {
        arrangementBaseline.push({
          token: token,
          opacity: token.getAttribute('opacity')
        });
      }
    );
  }

  function restoreArrangementBaseline() {
    arrangementBaseline.forEach(function (entry) {
      if (entry.opacity === null) {
        entry.token.removeAttribute('opacity');
      } else {
        entry.token.setAttribute('opacity', entry.opacity);
      }
    });
    arrangementStartCounts = null;
    arrangementEnvelope = null;
    arrangementHeldFrom = null;
    clearArrangementMarks();
  }

  function arrangementCanLift(slot) {
    var counts = currentArrangementCounts() || {};
    if (!arrangementEnvelope) { return false; }
    return (counts[slot] || 0) - 1 >= arrangementEnvelope.low[slot];
  }

  function arrangementCanPlace(slot) {
    var counts = currentArrangementCounts() || {};
    if (!arrangementEnvelope) { return false; }
    return (counts[slot] || 0) + 1 <= arrangementEnvelope.high[slot];
  }

  function arrangementClick(slot, sourceKind) {
    if (requestInFlight) { return; }
    if (!activeSeat || !activeSeat.getAttribute('data-arrangement-choice')) { return; }
    var counts = currentArrangementCounts();
    if (!counts) { return; }
    if (arrangementHeldFrom === null) {
      if (sourceKind !== 'token' || !arrangementCanLift(slot)) { return; }
      setAllocationCount(slot, (counts[slot] || 0) - 1);
      arrangementHeldFrom = slot;
    } else {
      if (slot === arrangementHeldFrom) {
        setAllocationCount(slot, (counts[slot] || 0) + 1);
        arrangementHeldFrom = null;
      } else if (sourceKind === 'token' && slot !== 'abbey') {
        return;
      } else if (arrangementCanPlace(slot)) {
        setAllocationCount(slot, (counts[slot] || 0) + 1);
        arrangementHeldFrom = null;
      } else {
        return;
      }
    }
    render();
  }

  function parseOrdinationValue(value) {
    var parsed = { ordain: 0, mission: 0 };
    if (value === 'none' || value === '') { return parsed; }
    String(value).split(',').forEach(function (part) {
      var split = part.split('=');
      if (split.length !== 2) { return; }
      var key = split[0];
      var amount = Number(split[1]);
      if ((key !== 'ordain' && key !== 'mission') || Number.isNaN(amount)) { return; }
      parsed[key] = amount;
    });
    return parsed;
  }

  function encodeOrdinationValue(ordain, mission) {
    var parts = [];
    if (ordain > 0) { parts.push('ordain=' + String(ordain)); }
    if (mission > 0) { parts.push('mission=' + String(mission)); }
    return parts.length ? parts.join(',') : 'none';
  }

  function currentOrdinationCounts() {
    return {
      village: villageCount(),
      abbey: abbeyCount(),
      city: cityCount()
    };
  }

  function currentOrdinationProgress() {
    if (!ordinationStartCounts) { return null; }
    var counts = currentOrdinationCounts();
    var ordain = ordinationStartCounts.village - counts.village;
    var mission = ordinationStartCounts.abbey + ordain - counts.abbey;
    return { ordain: ordain, mission: mission, counts: counts };
  }

  function clearOrdinationMarks() {
    if (!activeSeat) { return; }
    activeSeat.removeAttribute('data-ordination-choice');
    Array.prototype.forEach.call(
      activeSeat.querySelectorAll(
        '[data-ordination-can-ordain],[data-ordination-can-mission]'
      ),
      function (node) {
        node.removeAttribute('data-ordination-can-ordain');
        node.removeAttribute('data-ordination-can-mission');
      }
    );
  }

  function ordinationCanAdvance(kind) {
    var progress = currentOrdinationProgress();
    if (!progress || !ordinationOffered.length) { return false; }
    if (kind === 'ordain') {
      if (progress.counts.village <= 0) { return false; }
      if (progress.counts.abbey >= abbeyTokensOnActiveSeat().length) { return false; }
    } else {
      if (progress.counts.abbey <= 0) { return false; }
      if (progress.counts.city >= citySlotsForActiveSeat().length) { return false; }
    }
    return ordinationOffered.some(function (encoded) {
      var target = parseOrdinationValue(encoded);
      if (target.ordain < progress.ordain || target.mission < progress.mission) {
        return false;
      }
      return kind === 'ordain'
        ? target.ordain > progress.ordain
        : target.mission > progress.mission;
    });
  }

  function ordinationSelection(values) {
    if (!values.length || !activeSeat) { return null; }
    if (!ordinationStartCounts) {
      ordinationStartCounts = currentOrdinationCounts();
    }
    var progress = currentOrdinationProgress();
    if (!progress) { return null; }
    var encoded = encodeOrdinationValue(progress.ordain, progress.mission);
    return values.indexOf(encoded) === -1 ? null : encoded;
  }

  function showOrdination(values) {
    if (!activeSeat) { return; }
    if (!values.length) {
      ordinationStartCounts = null;
      ordinationOffered = [];
      clearOrdinationMarks();
      return;
    }
    if (!ordinationStartCounts) {
      ordinationStartCounts = currentOrdinationCounts();
    }
    ordinationOffered = values.slice();
    activeSeat.setAttribute('data-ordination-choice', 'true');
    var progress = currentOrdinationProgress();
    var canOrdainNow = progress ? ordinationCanAdvance('ordain') : false;
    var canMissionNow = progress ? ordinationCanAdvance('mission') : false;
    villageTokensOnActiveSeat().forEach(function (token) {
      token.setAttribute('data-ordination-can-ordain', canOrdainNow ? 'true' : 'false');
      token.setAttribute('data-ordination-can-mission', 'false');
    });
    abbeyTokensOnActiveSeat().forEach(function (token) {
      token.setAttribute('data-ordination-can-ordain', 'false');
      token.setAttribute('data-ordination-can-mission', canMissionNow ? 'true' : 'false');
    });
    if (progress) {
      setCityCount(ordinationStartCounts.city + progress.mission);
    }
  }

  function captureOrdinationBaseline() {
    ordinationBaseline = [];
    if (!activeSeat) { return; }
    Array.prototype.forEach.call(
      activeSeat.querySelectorAll('[data-token="village"],[data-token="abbey"]'),
      function (token) {
        ordinationBaseline.push({
          token: token,
          opacity: token.getAttribute('opacity')
        });
      }
    );
    Array.prototype.forEach.call(citySlotsForActiveSeat(), function (slot) {
      ordinationBaseline.push({
        token: slot,
        opacity: slot.getAttribute('opacity')
      });
    });
  }

  function restoreOrdinationBaseline() {
    ordinationBaseline.forEach(function (entry) {
      if (entry.opacity === null) {
        entry.token.removeAttribute('opacity');
      } else {
        entry.token.setAttribute('opacity', entry.opacity);
      }
    });
    ordinationStartCounts = null;
    ordinationOffered = [];
    clearOrdinationMarks();
  }

  function ordinationClick(kind) {
    if (requestInFlight) { return; }
    if (!activeSeat || !activeSeat.getAttribute('data-ordination-choice')) { return; }
    var counts = currentOrdinationCounts();
    if (kind === 'ordain') {
      if (!ordinationCanAdvance('ordain')) { return; }
      setVillageCount(counts.village - 1);
      setAbbeyCount(counts.abbey + 1);
    } else if (kind === 'mission') {
      if (!ordinationCanAdvance('mission')) { return; }
      setAbbeyCount(counts.abbey - 1);
      setCityCount(counts.city + 1);
    } else {
      return;
    }
    render();
  }

  function stepsAt(index, live) {
    var seen = [];
    live.forEach(function (candidate) {
      var step = candidate.steps[index];
      if (!step) { return; }
      var known = seen.some(function (other) {
        return other.kind === step.kind && other.value === step.value;
      });
      if (!known) { seen.push(step); }
    });
    return seen;
  }

  function resourceCounts(value) {
    var counts = { stone: 0, silver: 0, wheat: 0 };
    String(value).split(',').forEach(function (part) {
      var pieces = part.split('=');
      if (pieces.length === 2 && counts[pieces[0]] !== undefined) {
        counts[pieces[0]] = Number(pieces[1]) || 0;
      }
    });
    return counts;
  }

  function resourceAllocationSteps(offered) {
    return offered.filter(function (step) { return step.resource_allocation === true; });
  }

  function resourceAllocationAmount(counts) {
    return ['stone', 'silver', 'wheat'].reduce(function (total, resource) {
      return total + Number(counts[resource] || 0);
    }, 0);
  }

  function allocationMatches(value, counts) {
    var option = resourceCounts(value);
    return ['stone', 'silver', 'wheat'].every(function (resource) {
      return Number(counts[resource] || 0) <= option[resource];
    });
  }

  function allocationEquals(value, counts) {
    var option = resourceCounts(value);
    return ['stone', 'silver', 'wheat'].every(function (resource) {
      return Number(counts[resource] || 0) === option[resource];
    });
  }

  function resourceAllocationAnyTotal(steps) {
    return steps.some(function (step) {
      return step.resource_allocation_any_total === true;
    });
  }

  function allocationMaximum(resource, options) {
    var maximum = 0;
    options.forEach(function (step) {
      maximum = Math.max(maximum, resourceCounts(step.value)[resource]);
    });
    return maximum;
  }

  function replacePage(request) {
    /* The server sends the whole page back, drawn from the state it now holds. Swapping it in
       is the only way anything on this board changes: nothing here draws a piece. */
    if (request.status !== 200) {
      requestInFlight = false;
      window.alert('refused: ' + request.responseText);
      return;
    }
    document.open();
    document.write(request.responseText);
    document.close();
  }

  function postPage(path, body) {
    if (requestInFlight) { return; }
    requestInFlight = true;
    var request = new XMLHttpRequest();
    request.open('POST', path, true);
    request.setRequestHeader('Content-Type', 'application/json');
    request.onload = function () { replacePage(request); };
    request.onerror = function () {
      requestInFlight = false;
      window.alert('refused: request failed');
    };
    request.send(JSON.stringify(body));
  }

  function submit(actionId) {
    postPage('/action', { action_id: actionId, state_token: TOKEN });
  }

  function submitTurnStep(stepId) {
    postPage('/turn-step', { step_id: stepId, state_token: TOKEN });
  }

  function submitReset() {
    postPage('/reset-turn', { state_token: TOKEN });
  }

  /* A step says how it is answered and this sorts them by that, so a new
     kind of question is a new bucket here and nothing else. That includes
     three kinds answered on the wheel: `origin`, `skip`, and `duty`, split so they can
     be marked differently without naming fields. No step is recognised by
     what it is ABOUT: there is no field name anywhere in this file, and a
     page that told a tithe's stock from a taxation's would be one that had
     to be taught about the next one. */
  function offeredByKind(offered, kind) {
    var values = [];
    offered.forEach(function (step) {
      if (step.kind === kind) { values.push(step.value); }
    });
    return values;
  }

  /* What the offered step is ASKING, in one line at a time. The sentence comes off the step
     whole. Nothing here composes, shortens or joins one. */
  function promptsOf(offered) {
    var prompt = null;
    offered.forEach(function (step) {
      if (prompt !== null) { return; }
      if (step.prompt) { prompt = step.prompt; }
    });
    return prompt === null ? [] : [prompt];
  }

  function mark(elements, attribute, values) {
    Array.prototype.forEach.call(elements, function (element) {
      var name = element.getAttribute(attribute);
      element.setAttribute('data-turn-offered', values.indexOf(name) === -1 ? 'false' : 'true');
    });
  }

  function controls(name) {
    return document.querySelectorAll('[data-turn-control="' + name + '"]');
  }

  function setControl(name, enabled, active) {
    Array.prototype.forEach.call(controls(name), function (item) {
      item.setAttribute('data-turn-control-enabled', enabled ? 'true' : 'false');
      item.setAttribute('data-turn-control-active', active ? 'true' : 'false');
      item.setAttribute('aria-disabled', enabled ? 'false' : 'true');
    });
  }

  function setConfirmLabel(endTurn) {
    var shown = endTurn ? 'end_turn' : 'confirm';
    Array.prototype.forEach.call(document.querySelectorAll('[data-turn-control-label]'), function (item) {
      item.setAttribute(
        'data-turn-offered',
        item.getAttribute('data-turn-control-label') === shown ? 'true' : 'false'
      );
    });
  }

  function spaceAt(name) {
    return board.querySelector('[data-board-position="' + name + '"]');
  }

  function tallyAt(name) {
    var space = spaceAt(name);
    return space ? space.querySelector('[data-cube-tally]') : null;
  }

  function positionName(index) {
    var name = null;
    Array.prototype.forEach.call(spaces, function (space) {
      if (Number(space.getAttribute('data-board-position-index')) === index) {
        name = space.getAttribute('data-board-position');
      }
    });
    return name;
  }

  function columnAt(name, player) {
    var tally = tallyAt(name);
    if (!tally || !player) { return []; }
    return Array.prototype.filter.call(tally.querySelectorAll('rect'), function (cube) {
      return cube.getAttribute('data-player') === player;
    });
  }

  function visibleColumnAt(name, player) {
    return columnAt(name, player).filter(function (cube) {
      return cube.getAttribute('opacity') !== '0';
    });
  }

  function hide(cubes) {
    cubes.forEach(function (cube) {
      cube.setAttribute('opacity', '0');
    });
  }

  function restore(cubes) {
    cubes.forEach(function (entry) {
      if (entry.opacity === null) {
        entry.cube.removeAttribute('opacity');
      } else {
        entry.cube.setAttribute('opacity', entry.opacity);
      }
    });
  }

  function firstEmptySlotAt(name, player) {
    return columnAt(name, player).filter(function (cube) {
      return cube.getAttribute('opacity') === '0';
    })[0] || null;
  }

  function placeOneCubeAt(name, player) {
    var slot = firstEmptySlotAt(name, player);
    if (!slot) { return null; }
    slot.setAttribute('opacity', '1');
    return slot;
  }

  function captureBaseline() {
    baseline = [];
    Array.prototype.forEach.call(
      board.querySelectorAll('[data-cube-tally] rect[data-player]'),
      function (cube) {
        baseline.push({ cube: cube, opacity: cube.getAttribute('opacity') });
      }
    );
    resourceBaseline = [];
    if (activeSeat) {
      Array.prototype.forEach.call(
        activeSeat.querySelectorAll('g'),
        function (group) {
          if (!group.getAttribute('data-resource')) { return; }
          var text = group.querySelector('text');
          if (text) { resourceBaseline.push({ text: text, value: text.textContent }); }
        }
      );
    }
    merchantBaseline = [];
    Array.prototype.forEach.call(merchantTokens, function (token) {
      merchantBaseline.push({ token: token, opacity: token.getAttribute('opacity') });
    });
    buildingSlotBaseline = [];
    Array.prototype.forEach.call(
      document.querySelectorAll('[data-player-board-slot]'),
      function (slot) {
        var use = slot.querySelector('use');
        var content = slot.querySelector('g[transform]');
        buildingSlotBaseline.push({
          slot: slot,
          use: use,
          attributes: {
            'data-building-slot-state': slot.getAttribute('data-building-slot-state'),
            'data-building-id': slot.getAttribute('data-building-id'),
            'data-donated': slot.getAttribute('data-donated')
          },
          content: content,
          contentHTML: content ? content.innerHTML : null,
          href: use ? use.getAttribute('href') : null,
          useOpacity: use ? use.getAttribute('opacity') : null
        });
      }
    );
    pietyDiscBaseline = [];
    Array.prototype.forEach.call(
      document.querySelectorAll(
        '[data-component="piety-track-v2"] [data-player-disc="true"]'
      ),
      function (disc) {
        pietyDiscBaseline.push({
          disc: disc,
          cx: disc.getAttribute('cx'),
          cy: disc.getAttribute('cy'),
          position: disc.getAttribute('data-piety-position')
        });
      }
    );
    almsDiscBaseline = null;
    if (activePlayer) {
      var almsDisc = document.querySelector(
        '[data-player-disc="true"][data-player="' + activePlayer + '"]'
      );
      if (almsDisc) {
        almsDiscBaseline = {
          disc: almsDisc,
          cx: almsDisc.getAttribute('cx'),
          cy: almsDisc.getAttribute('cy'),
          position: almsDisc.getAttribute('data-alms-position')
        };
      }
    }
    almsWorkforceBaseline = [];
    if (activeSeat) {
      Array.prototype.forEach.call(
        activeSeat.querySelectorAll('[data-token="village"],[data-token="abbey"]'),
        function (token) {
          almsWorkforceBaseline.push({
            token: token,
            opacity: token.getAttribute('opacity')
          });
        }
      );
    }
    if (activePlayer) {
      Array.prototype.forEach.call(
        board.querySelectorAll(
          '[data-city-column-player="' + activePlayer + '"][data-city-cube]'
        ),
        function (slot) {
          almsWorkforceBaseline.push({
            token: slot,
            opacity: slot.getAttribute('opacity')
          });
        }
      );
    }
  }

  function restoreBaseline() {
    restore(baseline);
    if (merchantBoardBaseline === null) { board.removeAttribute('data-merchant-token'); }
    else { board.setAttribute('data-merchant-token', merchantBoardBaseline); }
    resourceBaseline.forEach(function (entry) {
      entry.text.textContent = entry.value;
    });
    merchantBaseline.forEach(function (entry) {
      if (entry.opacity === null) { entry.token.removeAttribute('opacity'); }
      else { entry.token.setAttribute('opacity', entry.opacity); }
    });
    buildingSlotBaseline.forEach(function (entry) {
      var slot = entry.slot;
      var use = entry.use;
      ['data-building-slot-state', 'data-building-id', 'data-donated'].forEach(function (name) {
        var value = entry.attributes[name];
        if (value === null) { slot.removeAttribute(name); }
        else { slot.setAttribute(name, value); }
      });
      if (use) {
        if (entry.href === null) { use.removeAttribute('href'); }
        else { use.setAttribute('href', entry.href); }
        if (entry.useOpacity === null) { use.removeAttribute('opacity'); }
        else { use.setAttribute('opacity', entry.useOpacity); }
      }
      if (entry.content && entry.contentHTML !== null) {
        entry.content.innerHTML = entry.contentHTML;
      }
    });
    pietyDiscBaseline.forEach(function (entry) {
      entry.disc.setAttribute('cx', entry.cx);
      entry.disc.setAttribute('cy', entry.cy);
      entry.disc.setAttribute('data-piety-position', entry.position);
    });
    if (almsDiscBaseline) {
      almsDiscBaseline.disc.setAttribute('cx', almsDiscBaseline.cx);
      almsDiscBaseline.disc.setAttribute('cy', almsDiscBaseline.cy);
      almsDiscBaseline.disc.setAttribute('data-alms-position', almsDiscBaseline.position);
    }
    var pietyTrack = document.querySelector('[data-component="piety-track-v2"]');
    if (pietyTrack) { pietyTrack.removeAttribute('data-piety-preview-position'); }
  }

  function applyResourceDelta(delta) {
    if (!activeSeat || !delta) { return; }
    ['stone', 'silver', 'wheat'].forEach(function (resource) {
      var amount = Number(delta[resource] || 0);
      if (!amount) { return; }
      var text = null;
      Array.prototype.some.call(activeSeat.querySelectorAll('g'), function (group) {
        if (group.getAttribute('data-resource') !== resource) { return false; }
        text = group.querySelector('text');
        return true;
      });
      if (text) { text.textContent = String(Number(text.textContent || 0) + amount); }
    });
  }

  function applyMerchantAdvance(position) {
    var target = Number(position);
    if (Number.isNaN(target)) { return; }
    var targetDuty = null;
    Array.prototype.forEach.call(merchantTokens, function (token) {
      var space = token.closest('[data-board-position-index]');
      var visible = space && Number(space.getAttribute('data-board-position-index')) === target;
      token.setAttribute('opacity', visible ? '1' : '0');
      if (visible) {
        targetDuty = space ? space.getAttribute('data-duty') : null;
      }
    });
    if (targetDuty) { board.setAttribute('data-merchant-token', targetDuty); }
  }

  function applyBuildingConstructed(buildingId) {
    if (!activeSeat || !buildingId) { return; }
    var empty = Array.prototype.filter.call(
      activeSeat.querySelectorAll('[data-player-board-slot]'),
      function (slot) { return slot.getAttribute('data-building-id') === ''; }
    )[0] || null;
    if (!empty) { return; }
    var use = empty.querySelector('use');
    if (!use) { return; }
    empty.setAttribute('data-building-slot-state', 'bought');
    empty.setAttribute('data-building-id', buildingId);
    empty.setAttribute('data-donated', 'false');
    use.setAttribute('href', '#preview-building-' + buildingId);
    use.setAttribute('opacity', '1');
  }

  function applyBuildingDonation(buildingId) {
    if (!activeSeat || !buildingId) { return; }
    var slot = Array.prototype.filter.call(
      activeSeat.querySelectorAll('[data-player-board-slot]'),
      function (candidate) {
        return candidate.getAttribute('data-building-id') === buildingId;
      }
    )[0] || null;
    if (!slot) { return; }
    var content = slot.querySelector('g[transform]');
    if (!content) { return; }
    slot.setAttribute('data-building-slot-state', 'donated');
    slot.setAttribute('data-donated', 'true');
    content.innerHTML = '<use href="#preview-donated-building-' + buildingId + '"></use>';
  }

  function applyPietyDelta(delta) {
    if (!activePlayer || !delta || delta.new_piety_position === undefined) { return; }
    var track = document.querySelector('[data-component="piety-track-v2"]');
    var disc = track && track.querySelector(
      '[data-player-disc="true"][data-player="' + activePlayer + '"]'
    );
    if (!disc) { return; }
    var targetPosition = String(delta.new_piety_position);
    var targetLabel = track.querySelector(
      '[data-piety-position-label="' + targetPosition + '"]'
    );
    var currentLabel = track.querySelector(
      '[data-piety-position-label="' + disc.getAttribute('data-piety-position') + '"]'
    );
    if (!targetLabel || !currentLabel) { return; }
    var offset = Number(disc.getAttribute('cx')) - Number(currentLabel.getAttribute('x'));
    disc.setAttribute('cx', String(Number(targetLabel.getAttribute('x')) + offset));
    disc.setAttribute('data-piety-position', targetPosition);
    track.setAttribute('data-piety-preview-position', targetPosition);
  }

  function applyAlmsProgress(progress) {
    if (!activePlayer || !progress || progress.new_row === undefined) { return; }
    var alms = document.querySelector('[data-component="alms-table"]');
    var disc = alms && alms.querySelector(
      '[data-player-disc="true"][data-player="' + activePlayer + '"]'
    );
    var target = ALMS_POSITION_TARGETS[String(progress.new_row)];
    if (!disc || !target) { return; }
    disc.setAttribute('cx', target[0]);
    disc.setAttribute('cy', target[1]);
    disc.setAttribute('data-alms-position', String(progress.new_row));
  }

  function applyAlmsThresholdRewards(rewards) {
    if (!Array.isArray(rewards)) { return; }
    rewards.forEach(function (reward) {
      if (!reward || reward.moved !== true) { return; }
      var name = reward.reward;
      if (name === 'village_to_abbey') {
        setVillageCount(villageCount() - 1);
        setAbbeyCount(abbeyCount() + 1);
      } else if (name === 'abbey_to_city') {
        setAbbeyCount(abbeyCount() - 1);
        setCityCount(cityCount() + 1);
      } else if (name === 'village_to_city') {
        setVillageCount(villageCount() - 1);
        setCityCount(cityCount() + 1);
      }
    });
  }

  function applyStepEffects(step) {
    if (!step) { return; }
    if (
      step.resource_delta
      && (!step.resource_allocation || step.resource_allocation_any_total === true)
    ) {
      applyResourceDelta(step.resource_delta);
    }
    if (step.building_constructed !== undefined) {
      applyBuildingConstructed(step.building_constructed);
    }
    if (step.building_donation !== undefined) {
      applyBuildingDonation(step.building_donation);
    }
    if (step.piety_delta) {
      applyPietyDelta(step.piety_delta);
    }
    if (step.merchant_advance !== undefined) {
      applyMerchantAdvance(step.merchant_advance);
    }
    if (step.alms_progress) {
      applyAlmsProgress(step.alms_progress);
    }
    if (step.alms_threshold_reward) {
      applyAlmsThresholdRewards(step.alms_threshold_reward);
    }
  }

  function restoreAlmsWorkforceBaseline() {
    almsWorkforceBaseline.forEach(function (entry) {
      if (entry.opacity === null) { entry.token.removeAttribute('opacity'); }
      else { entry.token.setAttribute('opacity', entry.opacity); }
    });
  }

  function agreedStepEffect(live, index, answer, field) {
    var found = false;
    var value = null;
    var agreed = true;
    live.forEach(function (candidate) {
      var offered = candidate.steps[index];
      if (!offered || offered.value !== answer) { return; }
      var current = offered && offered.value === answer
        && Object.prototype.hasOwnProperty.call(offered, field)
        ? offered[field] : null;
      if (!found) {
        found = true;
        value = current;
      } else if (JSON.stringify(value) !== JSON.stringify(current)) {
        agreed = false;
      }
    });
    return found && agreed ? value : null;
  }

  function applyPartialResourceAllocation() {
    var live = surviving(chosen);
    var allocationSteps = resourceAllocationSteps(stepsAt(chosen.length, live));
    if (!allocationSteps.length) { return; }
    if (resourceAllocationAnyTotal(allocationSteps)) {
      restoreAlmsWorkforceBaseline();
      var exact = live.filter(function (candidate) {
        var step = candidate.steps[chosen.length];
        return step !== undefined
          && step.resource_allocation === true
          && allocationEquals(step.value, resourceAllocation);
      });
      if (exact.length === 1) {
        applyStepEffects(exact[0].steps[chosen.length]);
      }
      return;
    }
    var unitDeltas = allocationSteps[0].resource_unit_deltas || {};
    ['stone', 'silver', 'wheat'].forEach(function (resource) {
      var count = Number(resourceAllocation[resource] || 0);
      for (var index = 0; index < count; index += 1) {
        applyResourceDelta(unitDeltas[resource]);
      }
    });
  }

  function applyTurnStepRelocationPreview() {
    var live = survivingTurnSteps();
    var step = live.length === 1 ? live[0] : null;
    if (
      !step
      || conversionChosen.length !== step.answers.length
      || step.kind !== 'relocation'
      || !activePlayer
    ) { return; }
    if (
      step.building_id !== 'dormitory'
      && step.building_id !== 'inquisition'
      && step.building_id !== 'library'
    ) { return; }
    var source = 'city';
    var destination = null;
    if (step.building_id === 'dormitory') {
      source = positionName(Number(step.selected_position));
      destination = 'city';
    } else if (step.selected_position === 'abbey') {
      var abbeyToken = abbeyTokensOnActiveSeat().filter(function (token) {
        return !tokenVisible(token);
      })[0];
      var cityCube = visibleColumnAt(source, activePlayer)[0];
      if (!abbeyToken || !cityCube) { return; }
      cityCube.setAttribute('opacity', '0');
      abbeyToken.setAttribute('opacity', '1');
      return;
    } else {
      destination = positionName(Number(step.selected_position));
    }
    if (!source || !destination) { return; }
    var moved = visibleColumnAt(source, activePlayer)[0];
    var placed = placeOneCubeAt(destination, activePlayer);
    if (!moved || !placed) {
      if (placed) { placed.setAttribute('opacity', '0'); }
      return;
    }
    moved.setAttribute('opacity', '0');
  }

  function applyPreview() {
    var started = false;
    var overflow = false;
    var count = null;
    var origin = null;
    var skip = null;
    var duty = null;
    var resolution = null;
    var hireFactText = '';
    var placedAlongRoute = {};
    var prefix = [];
    var remaining = chosen.slice();

    function sharedHireText(candidates) {
      var sharedLines = null;
      for (var candidateIndex = 0; candidateIndex < candidates.length; candidateIndex += 1) {
        var steps = candidates[candidateIndex].steps;
        var factStep = steps.find(function (candidateStep) {
          return candidateStep.hire_text;
        });
        if (!factStep) { continue; }
        var lines = factStep.hire_text.split('\n');
        if (sharedLines === null) {
          sharedLines = lines;
          continue;
        }
        sharedLines = sharedLines.filter(function (line) {
          return lines.indexOf(line) !== -1;
        });
      }
      return sharedLines ? sharedLines.join('\n') : '';
    }

    restoreBaseline();
    while (remaining.length) {
      var answer = remaining[0];
      remaining = remaining.slice(1);
      var live = surviving(prefix);
      if (!live.length) { break; }
      var stepIndex = prefix.length;
      var step = null;
      live.forEach(function (candidate) {
        var offered = candidate.steps[stepIndex];
        if (step || !offered) { return; }
        if (offered.value === answer) {
          step = offered;
        }
      });
      prefix.push(answer);
      if (!step) { continue; }
      applyStepEffects(step);
      if (step.kind === 'origin') {
        origin = step.value;
        var start = positionName(step.value);
        if (start && activePlayer) {
          hide(visibleColumnAt(start, activePlayer));
        }
        started = true;
        if (step.counter !== undefined && step.counter !== null) {
          count = step.counter;
        } else if (live[0].counter_start !== undefined && live[0].counter_start !== null) {
          count = live[0].counter_start;
        }
        continue;
      }
      if (step.kind === 'skip') {
        skip = step.value;
        var skipped = positionName(Number(step.value));
        if (skipped && placedAlongRoute[skipped] && placedAlongRoute[skipped].length) {
          placedAlongRoute[skipped].pop().setAttribute('opacity', '0');
        }
        continue;
      }
      if (step.kind === 'duty') {
        duty = step.value;
        continue;
      }
      if (step.kind === 'resolution') {
        resolution = step.value;
        continue;
      }
      if (step.kind === 'resource' && step.resource_delta) { continue; }
      if (step.kind !== 'edge') { continue; }
      var matched = surviving(prefix);
      hireFactText = sharedHireText(matched);
      var ends = String(answer).split('->');
      var destination = ends.length === 2 ? ends[1] : null;
      if (destination && activePlayer) {
        var placed = placeOneCubeAt(destination, activePlayer);
        if (!placed) {
          overflow = true;
          if (window.console && window.console.error) {
            window.console.error('turn preview overflow: no slot at ' + destination);
          }
          break;
        }
        if (!placedAlongRoute[destination]) { placedAlongRoute[destination] = []; }
        placedAlongRoute[destination].push(placed);
      }
      if (step.counter !== undefined && step.counter !== null) {
        count = step.counter;
      }
    }
    applyPartialResourceAllocation();
    applyTurnStepRelocationPreview();
    return {
      started: started,
      resettable: started && answered.length > 0,
      overflow: overflow,
      count: count,
      origin: origin,
      skip: skip,
      duty: duty,
      resolution: resolution,
      hire_fact_text: hireFactText
    };
  }

  function familyPaint(edge, offered) {
    var paint = null;
    var priority = -1;
    offered.forEach(function (step) {
      var building = step.kind === 'edge' && step.value === edge ? familyForStep(step) : null;
      if (!building) { return; }
      var candidatePriority = Number(building.priority);
      if (candidatePriority > priority) {
        paint = building.paint;
        priority = candidatePriority;
      }
    });
    return paint;
  }

  function show(
    offered, resolutionOptions, settled, confirmActionId, preview, arrangementValues, ordinationValues,
    allocationOptions
  ) {
    var origins = offeredByKind(offered, 'origin');
    var skips = offeredByKind(offered, 'skip');
    var duties = offeredByKind(offered, 'duty');
    var edges = offeredByKind(offered, 'edge');
    var resolutions = resolutionOptions || [];
    var actionResolutions = resolutions.filter(function (value) {
      return value !== 'tithe';
    });
    var shownResolutions = resolutionSplit === 'action' ? actionResolutions : [];
    var dutyName = preview.duty === null ? null : positionName(preview.duty);
    var allocationSteps = resourceAllocationSteps(offered);
    var allocationActive = allocationSteps.length > 0;
    var allocationChoices = allocationOptions || allocationSteps;
    var allocationAnyTotal = resourceAllocationAnyTotal(allocationSteps);
    var allocationComplete = allocationActive && (
      allocationAnyTotal
        ? allocationChoices.some(function (step) {
            return allocationEquals(step.value, resourceAllocation);
          })
        : resourceAllocationAmount(resourceAllocation) === resourceAllocationTotal
    );
    var stocks = offeredByKind(offered, 'resource');
    if (allocationActive) {
      stocks = ['stone', 'silver', 'wheat'].filter(function (resource) {
        var selected = Number(resourceAllocation[resource] || 0);
        var needs_more = allocationChoices.some(function (step) {
          return resourceCounts(step.value)[resource] > selected;
        });
        var can_reset = !allocationAnyTotal && !allocationComplete
          && selected > 0
          && selected >= allocationMaximum(resource, allocationChoices);
        return needs_more || can_reset;
      });
    }
    var boards = offeredByKind(offered, 'seat');
    Array.prototype.forEach.call(spaces, function (space) {
      var index = Number(space.getAttribute('data-board-position-index'));
      if (origins.indexOf(index) === -1) {
        space.removeAttribute('data-turn-start-candidate');
      } else {
        space.setAttribute('data-turn-start-candidate', 'true');
      }
      if (skips.indexOf(index) === -1) {
        space.removeAttribute('data-turn-skip-candidate');
      } else {
        space.setAttribute('data-turn-skip-candidate', 'true');
      }
      if (duties.indexOf(index) === -1) {
        space.removeAttribute('data-turn-duty-candidate');
      } else {
        space.setAttribute('data-turn-duty-candidate', 'true');
      }
      /* Offered and taken are different marks. Once origin is taken, it is no longer offered and
         carries no ring of its own. */
      space.removeAttribute('data-turn-start-selected');
      if (preview.skip === index) {
        space.setAttribute('data-turn-skip-selected', 'true');
      } else {
        space.removeAttribute('data-turn-skip-selected');
      }
      if (preview.duty === index) {
        space.setAttribute('data-turn-duty-selected', 'true');
      } else {
        space.removeAttribute('data-turn-duty-selected');
      }
    });
    Array.prototype.forEach.call(ornaments, function (ornament) {
      if (dutyName && ornament.getAttribute('data-ornament-position') === dutyName) {
        ornament.setAttribute('data-turn-duty-selected', 'true');
      } else {
        ornament.removeAttribute('data-turn-duty-selected');
      }
    });
    mark(arrows, 'data-arrow', edges);
    Array.prototype.forEach.call(arrows, function (arrow) {
      var paint = familyPaint(arrow.getAttribute('data-arrow'), offered);
      if (paint === null) {
        arrow.removeAttribute('data-turn-family-paint');
      } else {
        arrow.setAttribute('data-turn-family-paint', paint);
      }
    });
    mark(counters, 'data-turn-counter', preview.count === null ? [] : [String(preview.count)]);
    board.setAttribute('data-turn-preview-overflow', preview.overflow ? 'true' : 'false');
    mark(prompts, 'data-turn-prompt', promptsOf(offered));
    if (hireFact) {
      hireFact.textContent = preview.hire_fact_text || '';
      hireFact.setAttribute(
        'data-turn-hire-fact-active', preview.hire_fact_text ? 'true' : 'false'
      );
    }
    mark(keys, 'data-resolution-key', shownResolutions);
    mark(
      pairs,
      'data-combination-key',
      offeredByKind(offered, 'combination')
        .filter(function (value) {
          return !offered.some(function (step) {
            return step.kind === 'combination'
              && step.value === value
              && step.resource_allocation === true;
          });
        })
        .concat(offeredByKind(offered, 'hire'))
        .concat(offeredByKind(offered, 'merchant_advance'))
    );
    mark(buildings, 'data-building-choice-key', offeredByKind(offered, 'building'));
    /* A stock is picked on the board of the seat whose stock it is, and on no other. The other
       three are not merely unlit: their keys are marked unoffered too, so a key that something
       else revealed still cannot be pressed. Nobody reaches across the table. */
    Array.prototype.forEach.call(seats, function (seat) {
      var conversionResourceChoice = conversionNeedsAmountResource();
      var asking = (stocks.length || conversionResourceChoice)
        && seat.getAttribute('data-active-seat') === 'true';
      if (asking) { seat.setAttribute('data-resource-choice', 'true'); }
      else { seat.removeAttribute('data-resource-choice'); }
      mark(seat.querySelectorAll('[data-resource-choice-key]'), 'data-resource-choice-key',
           asking ? stocks : []);
    });
    /* And the other set, which is NOT the same set and must not be folded into the one above. A
       stock is asked of the one seat that is acting; a board is asked of every seat the answer may
       name, which is most of them and usually includes seats that are not acting at all. The seat
       that IS acting is in this set like any other, and nothing here checks for it. */
    Array.prototype.forEach.call(seats, function (seat) {
      var named = seat.getAttribute('data-player');
      var offering = boards.indexOf(named) !== -1;
      if (offering) { seat.setAttribute('data-seat-choice', 'true'); }
      else { seat.removeAttribute('data-seat-choice'); }
      mark(seat.querySelectorAll('[data-seat-choice-key]'), 'data-seat-choice-key',
           offering ? boards : []);
    });
    showArrangement(arrangementValues || []);
    showOrdination(ordinationValues || []);
    Array.prototype.forEach.call(ordinationActions, function (button) {
      var action = button.getAttribute('data-ordination-action');
      var offered = ordinationValues && ordinationValues.length && ordinationCanAdvance(action);
      button.setAttribute('data-turn-offered', offered ? 'true' : 'false');
    });
    renderTurnSteps();
    Array.prototype.forEach.call(panels, function (panel) {
      var index = Number(panel.getAttribute('data-turn-panel'));
      panel.setAttribute('data-turn-shown', index === settled ? 'true' : 'false');
    });
    setControl('sow', false, preview.started && preview.duty === null);
    setControl('reset', preview.resettable, false);
    if (RESOLUTION_COMMITTED || USED_BUILDINGS.length > 0 || conversionChosen.length > 0) {
      setControl('reset', true, false);
    }
    if (resourceAllocationAmount(resourceAllocation) > 0) {
      setControl('reset', true, false);
    }
    setControl(
      'confirm',
      (conversionReady() || (conversionChosen.length === 0 && confirmActionId !== null))
        && !preview.overflow,
      false
    );
    setConfirmLabel(
      RESOLUTION_COMMITTED && conversionChosen.length === 0 && confirmActionId !== null
    );
    setControl(
      'action',
      actionResolutions.length > 0 && preview.resolution === null && resolutionSplit !== 'tithe',
      resolutionSplit === 'action'
        || (preview.resolution !== null && preview.resolution !== 'tithe')
    );
    setControl(
      'tithe',
      resolutions.indexOf('tithe') !== -1
        && preview.resolution === null
        && resolutionSplit !== 'action',
      resolutionSplit === 'tithe' || preview.resolution === 'tithe'
    );
  }

  function render() {
    if (!CANDIDATES.length) {
      renderPhase(RESOLUTION_COMMITTED ? 'end' : null);
      restoreBaseline();
      applyTurnStepRelocationPreview();
      renderTurnSteps();
      setConfirmLabel(false);
      setControl(
        'reset',
        RESOLUTION_COMMITTED || USED_BUILDINGS.length > 0 || conversionChosen.length > 0,
        false
      );
      setControl('confirm', conversionReady(), false);
      return;
    }
    var live = surviving(chosen);
    var offered = stepsAt(chosen.length, live);
    /* The server marks exceptional continuations it has already found unambiguous. */
    while (offered.length && offered[0].auto_advance === true) {
      chosen.push(offered[0].value);
      live = surviving(chosen);
      offered = stepsAt(chosen.length, live);
    }
    var phase = RESOLUTION_COMMITTED ? 'end' : null;
    if (phase === null && offered.length) {
      phase = offered[0].turn_phase;
    }
    if (phase === null && live.length) {
      phase = live[0].settled_turn_phase;
    }
    renderPhase(phase || null);
    var allocationSteps = resourceAllocationSteps(offered);
    var allocationAnyTotal = resourceAllocationAnyTotal(allocationSteps);
    if (!allocationSteps.length) {
      resourceAllocation = {};
      resourceAllocationTotal = null;
    } else if (allocationAnyTotal) {
      resourceAllocationTotal = null;
    } else if (resourceAllocationTotal === null) {
      resourceAllocationTotal = Number(allocationSteps[0].resource_total || 0);
    }
    var allocationActive = allocationSteps.length > 0;
    var allocationLive = live;
    if (allocationActive) {
      allocationLive = live.filter(function (candidate) {
        var step = candidate.steps[chosen.length];
        return step !== undefined && allocationMatches(step.value, resourceAllocation);
      });
    }
    var allocationExactLive = allocationAnyTotal
      ? allocationLive.filter(function (candidate) {
          var step = candidate.steps[chosen.length];
          return step !== undefined && allocationEquals(step.value, resourceAllocation);
        })
      : [];
    var allocationComplete = allocationActive && (
      allocationAnyTotal
        ? allocationExactLive.length > 0
        : resourceAllocationAmount(resourceAllocation) === resourceAllocationTotal
    );
    var arrangements = offeredByKind(offered, 'arrangement');
    var arrangementPicked = arrangementSelection(arrangements);
    var ordinations = offeredByKind(offered, 'ordination');
    var ordinationPicked = ordinationSelection(ordinations);
    var narrowed = live;
    if (allocationActive) {
      narrowed = allocationLive;
    }
    if (arrangements.length && arrangementPicked !== null) {
      narrowed = live.filter(function (candidate) {
        var step = candidate.steps[chosen.length];
        return step !== undefined && step.kind === 'arrangement' && step.value === arrangementPicked;
      });
    }
    if (ordinations.length && ordinationPicked !== null) {
      narrowed = narrowed.filter(function (candidate) {
        var step = candidate.steps[chosen.length];
        return step !== undefined && step.kind === 'ordination' && step.value === ordinationPicked;
      });
    }
    var directConfirm = offered.filter(function (step) {
      return step.direct_confirm === true;
    });
    var directConfirmActionId = directConfirm.length === 1 ? onlyActionId(live) : null;
    var resolutions = offeredByKind(offered, 'resolution').filter(function (value) {
      return !directConfirm.some(function (step) { return step.value === value; });
    });
    if (!resolutions.length) {
      resolutionSplit = null;
    } else if (resolutionSplit === 'tithe' && resolutions.indexOf('tithe') !== -1) {
      abandonConversion();
      chosen.push('tithe');
      answered.push('tithe');
      resolutionSplit = null;
      render();
      return;
    } else if (resolutionSplit === 'action') {
      var actionResolutions = resolutions.filter(function (value) {
        return value !== 'tithe';
      });
      if (!actionResolutions.length) {
        resolutionSplit = null;
      } else if (actionResolutions.length === 1) {
        abandonConversion();
        chosen.push(actionResolutions[0]);
        answered.push(actionResolutions[0]);
        resolutionSplit = null;
        render();
        return;
      }
    }
    var preview = applyPreview();
    /* Nothing is sent on reaching one candidate. Its panel is revealed -- either the words it
       would be committed as, or what is still undecided about
       it -- and the player says so. */
    var currentQuestionIsAnswered = !offered.length
      || (arrangements.length && arrangementPicked !== null)
      || (ordinations.length && ordinationPicked !== null);
    if (
      narrowed.length === 1
      && !allocationActive
      && (!arrangements.length || arrangementPicked !== null)
      && (!ordinations.length || ordinationPicked !== null)
      && currentQuestionIsAnswered
    ) {
      var shownOffered = (arrangements.length || ordinations.length) ? offered : [];
      show(
        shownOffered,
        [],
        CANDIDATES.indexOf(narrowed[0]),
        onlyActionId(narrowed),
        preview,
        arrangements,
        ordinations
      );
      return;
    }
    var confirmActionId = directConfirmActionId;
    if (allocationActive && allocationComplete) {
      confirmActionId = onlyActionId(allocationAnyTotal ? allocationExactLive : narrowed);
    }
    show(
      offered,
      resolutions,
      -1,
      confirmActionId,
      preview,
      arrangements,
      ordinations,
      allocationActive ? stepsAt(chosen.length, allocationLive) : []
    );
  }

  Array.prototype.forEach.call(conversionBuildings, function (building) {
    building.addEventListener('click', function (event) {
      if (requestInFlight) { return; }
      if (building.getAttribute('data-turn-step-offered') !== 'true') { return; }
      if (building.getAttribute('data-turn-step-market') === 'true') {
        event.stopImmediatePropagation();
      }
      conversionChosen = [building.getAttribute('data-turn-step-building-id')];
      autoAdvanceHirePayment();
      render();
    });
  });

  Array.prototype.forEach.call(turnStepDirections, function (button) {
    button.addEventListener('click', function () {
      if (requestInFlight) { return; }
      if (button.getAttribute('data-turn-step-offered') !== 'true') { return; }
      if (!chooseTurnStepAnswer('direction', button.getAttribute('data-turn-step-direction'))) {
        return;
      }
      render();
    });
  });

  Array.prototype.forEach.call(turnStepResourceKeys, function (key) {
    key.addEventListener('click', function () {
      if (requestInFlight) { return; }
      if (key.getAttribute('data-turn-offered') !== 'true') { return; }
      var allocationCandidates = surviving(chosen).filter(function (candidate) {
        var step = candidate.steps[chosen.length];
        return step !== undefined && allocationMatches(step.value, resourceAllocation);
      });
      var allocationOffered = resourceAllocationSteps(
        stepsAt(chosen.length, allocationCandidates)
      );
      if (allocationOffered.length > 0) {
        var resource = key.getAttribute('data-resource-choice-key');
        var selected = Number(resourceAllocation[resource] || 0);
        if (resourceAllocationAnyTotal(allocationOffered)) {
          var canAdd = allocationOffered.some(function (step) {
            return resourceCounts(step.value)[resource] > selected;
          });
          if (!canAdd) { return; }
          resourceAllocation[resource] = selected + 1;
          render();
          return;
        }
        var maximum = allocationMaximum(resource, allocationOffered);
        if (selected > 0 && selected >= maximum) {
          resourceAllocation[resource] = 0;
        } else {
          resourceAllocation[resource] = selected + 1;
        }
        render();
        return;
      }
      if (conversionChosen.length === 0) {
        var value = key.getAttribute('data-resource-choice-key');
        chosen.push(value);
        answered.push(value);
        resolutionSplit = null;
        render();
        return;
      }
      var live = survivingTurnSteps();
      var amountIndex = turnStepAnswerIndex(live, 'amount');
      if (amountIndex === -1 || conversionChosen.length < amountIndex) { return; }
      var amountCandidates = survivingTurnSteps(conversionChosen.slice(0, amountIndex));
      var current = conversionChosen.length > amountIndex
        ? Number(conversionChosen[amountIndex]) : 0;
      var next = amountCandidates
        .map(function (step) { return Number(turnStepField(step, amountIndex)); })
        .filter(function (amount) { return amount > current; })
        .sort(function (left, right) { return left - right; })[0];
      if (next === undefined) { return; }
      conversionChosen = conversionChosen.slice(0, amountIndex).concat([String(next)]);
      render();
    });
  });

  Array.prototype.forEach.call(pietyChoicePills, function (choice) {
    choice.addEventListener('click', function () {
      if (requestInFlight) { return; }
      if (choice.getAttribute('data-piety-choice-offered') !== 'true') { return; }
      if (!chooseTurnStepAnswer(
        'piety_destination', choice.getAttribute('data-piety-choice-destination')
      )) { return; }
      render();
    });
  });

  Array.prototype.forEach.call(turnStepHireButtons, function (button) {
    button.addEventListener('click', function () {
      if (requestInFlight) { return; }
      if (button.getAttribute('data-turn-step-hire-offered') !== 'true') { return; }
      if (!chooseTurnStepAnswer('hire_payment', button.getAttribute('data-turn-step-hire-payment'))) {
        return;
      }
      render();
    });
  });

  Array.prototype.forEach.call(spaces, function (space) {
    space.addEventListener('click', function () {
      if (requestInFlight) { return; }
      if (
        space.getAttribute('data-turn-start-candidate') !== 'true'
        && space.getAttribute('data-turn-step-relocation-candidate') !== 'true'
        && space.getAttribute('data-turn-skip-candidate') !== 'true'
        && space.getAttribute('data-turn-duty-candidate') !== 'true'
      ) { return; }
      var value = Number(space.getAttribute('data-board-position-index'));
      if (space.getAttribute('data-turn-step-relocation-candidate') === 'true') {
        if (!chooseTurnStepAnswer('selected_position', String(value))) { return; }
        render();
        return;
      }
      chosen.push(value);
      answered.push(value);
      resolutionSplit = null;
      render();
    });
  });

  Array.prototype.forEach.call(buildingAbilityTargets, function (target) {
    target.addEventListener('click', function (event) {
      if (requestInFlight) { return; }
      if (target.getAttribute('data-turn-family-available') !== 'true') { return; }
      if (event && event.stopImmediatePropagation) { event.stopImmediatePropagation(); }
      var buildingId = target.getAttribute('data-building-id');
      var enabled = enabledFamilies.indexOf(buildingId) !== -1;
      if (enabled) {
        enabledFamilies = enabledFamilies.filter(function (candidate) {
          return candidate !== buildingId;
        });
        if (chosen.length > 0) { resetPreview(); }
      } else {
        enabledFamilies.push(buildingId);
      }
      render();
    });
  });

  Array.prototype.forEach.call(arrows, function (arrow) {
    arrow.addEventListener('click', function () {
      if (requestInFlight) { return; }
      if (arrow.getAttribute('data-turn-offered') !== 'true') { return; }
      var edge = arrow.getAttribute('data-arrow');
      chosen.push(edge);
      answered.push(edge);
      resolutionSplit = null;
      render();
    });
  });

  /* Five key surfaces are answered the same way: press one that is offered and it becomes the next
     answer. What the key stands for is the attribute it carries, and this does not read it. */
  function answers(elements, attribute) {
    Array.prototype.forEach.call(elements, function (key) {
      key.addEventListener('click', function () {
        if (requestInFlight) { return; }
        if (key.getAttribute('data-turn-offered') !== 'true') { return; }
        var value = key.getAttribute(attribute);
        if (attribute === 'data-resolution-key') {
          abandonConversion();
        }
        chosen.push(value);
        answered.push(value);
        resolutionSplit = null;
        render();
      });
    });
  }

  answers(keys, 'data-resolution-key');
  answers(pairs, 'data-combination-key');
  answers(buildings, 'data-building-choice-key');
  Array.prototype.forEach.call(ordinationActions, function (button) {
    button.addEventListener('click', function () {
      if (requestInFlight || button.getAttribute('data-turn-offered') !== 'true') { return; }
      ordinationClick(button.getAttribute('data-ordination-action'));
    });
  });
  Array.prototype.forEach.call(seats, function (seat) {
    answers(seat.querySelectorAll('[data-seat-choice-key]'), 'data-seat-choice-key');
  });
  if (activeSeat) {
    Array.prototype.forEach.call(activeSeat.querySelectorAll('[data-token="village"]'), function (token) {
      token.addEventListener('click', function () {
        if (requestInFlight) { return; }
        ordinationClick('ordain');
      });
    });
    Array.prototype.forEach.call(activeSeat.querySelectorAll('[data-token="abbey"]'), function (token) {
      token.addEventListener('click', function () {
        if (requestInFlight) { return; }
        if (activeSeat.getAttribute('data-end-relocation-choice') === 'true') {
          if (!chooseTurnStepAnswer('selected_position', 'abbey')) { return; }
          render();
          return;
        }
        arrangementClick('abbey', 'token');
        ordinationClick('mission');
      });
    });
    Array.prototype.forEach.call(activeSeat.querySelectorAll('[data-token="role"]'), function (token) {
      token.addEventListener('click', function () {
        if (requestInFlight) { return; }
        arrangementClick(token.getAttribute('data-role'), 'token');
      });
    });
    Array.prototype.forEach.call(activeSeat.querySelectorAll('[data-role-circle]'), function (circle) {
      circle.addEventListener('click', function () {
        if (requestInFlight) { return; }
        arrangementClick(circle.getAttribute('data-role-circle'), 'circle');
      });
    });
  }

  Array.prototype.forEach.call(controls('confirm'), function (confirmControl) {
    confirmControl.addEventListener('click', function () {
      if (requestInFlight) { return; }
      if (confirmControl.getAttribute('data-turn-control-enabled') !== 'true') { return; }
      if (conversionChosen.length > 0) {
        if (!conversionReady()) {
          throw new Error('enabled Confirm has no ready committed building step');
        }
        submitTurnStep(survivingTurnSteps()[0].step_id);
        return;
      }
      var live = surviving(chosen);
      var allocationCandidates = live.filter(function (candidate) {
        var step = candidate.steps[chosen.length];
        return step !== undefined && allocationMatches(step.value, resourceAllocation);
      });
      var allocationSteps = resourceAllocationSteps(
        stepsAt(chosen.length, allocationCandidates)
      );
      if (allocationSteps.length > 0) {
        if (resourceAllocationAnyTotal(allocationSteps)) {
          var exactCandidates = allocationCandidates.filter(function (candidate) {
            var step = candidate.steps[chosen.length];
            return step !== undefined && allocationEquals(step.value, resourceAllocation);
          });
          if (exactCandidates.length !== 1 || !exactCandidates[0].action_id) { return; }
          submit(exactCandidates[0].action_id);
          return;
        }
        if (
          resourceAllocationTotal === null
          || resourceAllocationAmount(resourceAllocation) !== resourceAllocationTotal
          || allocationCandidates.length !== 1
          || !allocationCandidates[0].action_id
        ) { return; }
        submit(allocationCandidates[0].action_id);
        return;
      }
      var offered = stepsAt(chosen.length, live);
      var arrangements = offeredByKind(offered, 'arrangement');
      if (arrangements.length) {
        var picked = arrangementSelection(arrangements);
        if (picked === null) { return; }
        live = live.filter(function (candidate) {
          var step = candidate.steps[chosen.length];
          return step !== undefined && step.kind === 'arrangement' && step.value === picked;
        });
      }
      var ordinations = offeredByKind(offered, 'ordination');
      if (ordinations.length) {
        var chosenOrdination = ordinationSelection(ordinations);
        if (chosenOrdination === null) { return; }
        live = live.filter(function (candidate) {
          var step = candidate.steps[chosen.length];
          return step !== undefined && step.kind === 'ordination' && step.value === chosenOrdination;
        });
      }
      if (live.length !== 1 || !live[0].action_id) { return; }
      submit(live[0].action_id);
    });
  });

  Array.prototype.forEach.call(controls('reset'), function (resetControl) {
    resetControl.addEventListener('click', function () {
      if (requestInFlight) { return; }
      if (resetControl.getAttribute('data-turn-control-enabled') !== 'true') { return; }
      if (RESOLUTION_COMMITTED || USED_BUILDINGS.length > 0) {
        submitReset();
        return;
      }
      resetPreview();
      render();
    });
  });

  function chooseResolutionSplit(name) {
    if (requestInFlight) { return; }
    var live = surviving(chosen);
    var offered = stepsAt(chosen.length, live);
    var resolutions = offeredByKind(offered, 'resolution');
    if (!resolutions.length) { return; }
    if (name === 'tithe') {
      if (resolutions.indexOf('tithe') === -1) { return; }
      resolutionSplit = 'tithe';
    } else {
      if (!resolutions.filter(function (value) { return value !== 'tithe'; }).length) { return; }
      resolutionSplit = 'action';
    }
    render();
  }

  ['action', 'tithe'].forEach(function (name) {
    Array.prototype.forEach.call(controls(name), function (controlButton) {
      controlButton.addEventListener('click', function () {
        if (requestInFlight) { return; }
        if (controlButton.getAttribute('data-turn-control-enabled') !== 'true') { return; }
        chooseResolutionSplit(name);
      });
    });
  });

  captureBaseline();
  captureArrangementBaseline();
  captureOrdinationBaseline();
  render();
})();
