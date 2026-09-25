// The control that chooses which sculpt set a page is showing.
//
// A SELECT RATHER THAN A ROW OF BUTTONS, because there are ten sets and there will be more the
// first time another kind is rendered. Ten buttons is ten rows of a panel that has sliders to
// fit in as well -- measured on the placement sheet, the button row was taller than the whole
// "how the sculpts stand" section it existed to serve.
//
// GROUPED, NOT FILTERED. `sizes` in duty_placement.json used to decide which sets the sow page
// would show at all, and that hid real work: a set tuned in the placement sheet did not appear
// on the sow page, with nothing to say it existed. So everything the tray has rendered is
// reachable here, and `sizes` decides only which ones are grouped as the played sizes.
//
// Shared by generate_duty_sow.py and generate_placement_sheet.py. One copy, because a picker
// that grouped differently on the two pages would be two answers to "which sets are there".

// `210_painted` reads as `210 painted`. The underscore is the file's spelling, not a person's.
function dutySetName(label) {
  return String(label).replace("_", " ");
}

// What a set is, said after its name: which one owns the base, which carry numbers of their
// own. Both are worth knowing before you move a slider, because they say where a save lands.
function dutySetNote(label, baseSet, ownSets) {
  if (label === baseSet) return "base";
  return (ownSets || []).indexOf(label) >= 0 ? "own numbers" : "";
}

// Build the select. `opts` carries every label, the played subset, the base, the sets with
// their own numbers, the current value, and what to do when it changes.
function dutySetPicker(host, opts) {
  var all = opts.all || [], played = opts.played || [];
  var rest = all.filter(function(v){ return played.indexOf(v) < 0; });
  var sel = document.createElement("select");
  sel.className = "setpick";

  function option(label) {
    var o = document.createElement("option");
    var note = dutySetNote(label, opts.base, opts.own);
    o.value = label;
    o.textContent = dutySetName(label) + (note ? "  · " + note : "");
    if (label === opts.value) o.selected = true;
    return o;
  }
  // ONE GROUP OR TWO, never an empty heading: with nothing in `sizes`, or with every rendered
  // set named there, a second group would be a label with no rows under it.
  if (played.length && rest.length) {
    [["played at", played], ["also rendered", rest]].forEach(function(pair){
      var g = document.createElement("optgroup");
      g.label = pair[0];
      pair[1].forEach(function(v){ g.appendChild(option(v)); });
      sel.appendChild(g);
    });
  } else {
    all.forEach(function(v){ sel.appendChild(option(v)); });
  }
  sel.onchange = function(){ opts.choose(sel.value); };
  host.innerHTML = "";
  host.appendChild(sel);
  return sel;
}

// Move the control to a value nobody clicked -- a set loaded at open, a keyboard shortcut, a
// page driven from the console. Without this the control can sit showing one set while the
// sliders show another's numbers, which is the exact confusion the per-set split ended.
function dutySetPickerShow(host, label) {
  var sel = host && host.querySelector("select");
  if (sel) sel.value = label;
}
