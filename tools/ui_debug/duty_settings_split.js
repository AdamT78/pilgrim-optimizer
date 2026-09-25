// How a page turns "here is what every set is tuned to" into the two documents on disk: one
// set's numbers at the top of the file, and every other set stored as what it changes.
//
// A SECOND COPY OF generate_placement_sheet.py's _split_base_and_overrides AND
// _split_grounds_overrides, on purpose, and pinned rather than trusted. The placement sheet can
// be opened as a file with no server behind it, and its save button then has to hand you a
// DOCUMENT rather than the wire payload -- it handed over the payload once, under the placement
// file's name, in a shape that file never has, and the download went into the repo. So the rule
// has to exist in the page.
//
// tests/test_ui_debug_duty_board.py runs these two functions in node against the same payload it
// gives the Python pair and compares the results key for key, so the day the copies stop
// agreeing is the day a test fails rather than the day a save quietly loses a set's tuning.

function splitBaseAndOverrides(doc, sentSets, baseLabel, keys, note){
  var out = {}, k, i, label;
  for (k in doc) out[k] = doc[k];
  var perSet = {};
  for (k in (doc.per_set || {})) perSet[k] = doc.per_set[k];
  if (sentSets[baseLabel])
    for (i = 0; i < keys.length; i++)
      if (keys[i] in sentSets[baseLabel]) out[keys[i]] = sentSets[baseLabel][keys[i]];
  for (label in sentSets){
    if (label === baseLabel){ delete perSet[label]; continue; }
    var own = {}, any = false;
    for (i = 0; i < keys.length; i++){
      k = keys[i];
      if (k in sentSets[label]
          && JSON.stringify(sentSets[label][k]) !== JSON.stringify(out[k])){
        own[k] = sentSets[label][k]; any = true;
      }
    }
    if (any) perSet[label] = own; else delete perSet[label];
  }
  if (Object.keys(perSet).length){
    out.per_set = perSet;
    if (!("per_set_note" in out)) out.per_set_note = note;
  } else { delete out.per_set; }
  return out;
}
function splitGroundOverrides(doc, sentSets, baseLabel, note){
  var out = {}, k, label, name;
  for (k in doc) out[k] = doc[k];
  var perSet = {};
  for (k in (doc.per_set || {})) perSet[k] = doc.per_set[k];
  var baseGrounds = out.grounds || {};
  for (label in sentSets){
    if (label === baseLabel){ delete perSet[label]; continue; }
    var own = {}, plates = {}, anyPlate = false;
    if ("lift" in sentSets[label] && sentSets[label].lift !== out.lift)
      own.lift = sentSets[label].lift;
    for (name in (sentSets[label].grounds || {}))
      if (JSON.stringify(sentSets[label].grounds[name])
          !== JSON.stringify(baseGrounds[name])){
        plates[name] = sentSets[label].grounds[name]; anyPlate = true;
      }
    if (anyPlate) own.grounds = plates;
    if (Object.keys(own).length) perSet[label] = own; else delete perSet[label];
  }
  if (Object.keys(perSet).length){
    out.per_set = perSet;
    if (!("per_set_note" in out)) out.per_set_note = note;
  } else { delete out.per_set; }
  return out;
}
