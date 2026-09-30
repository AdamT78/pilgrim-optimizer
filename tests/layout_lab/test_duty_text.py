"""What the action boxes say lives in one file, and that file must keep meaning something.

ui/board_v2/duty_text.json owns the wording. It used to live in the generator's DUTIES tuple as
two extra columns, which was fine while it was one decision made once -- and would have stopped
being fine the first time somebody edited the wording in one place and the engine mapping in the
other. The tuple gave the columns up; this checks nobody quietly puts them back.

The join to the engine is `engineAction`, an id from docs/rules/DutyTiles.md. That is the only
thread between a card's wording and the action it describes, and it is a thread nothing else
would notice snapping: rename an action in the engine and every caption in the lab goes on
reading exactly as before, while pointing at nothing.
"""
import importlib.util
import json
import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
TEXT = ROOT / "ui" / "board_v2" / "duty_text.json"
RULES = ROOT / "docs" / "rules" / "DutyTiles.md"
GEN = ROOT / "ui" / "board_v2" / "layout_lab" / "generate_layout_lab.py"
SLOTS = ("actionA", "actionB")


@pytest.fixture(scope="module")
def text():
    return json.loads(TEXT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def lab():
    spec = importlib.util.spec_from_file_location("_dt_lab", GEN)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_dt_lab"] = mod
    spec.loader.exec_module(mod)
    return mod


def canonical_ids():
    """Every action id in DutyTiles.md's Canonical Action Names table."""
    md = RULES.read_text(encoding="utf-8")
    start = md.index("## Canonical Action Names")
    table = md[start:md.index("\n## ", start + 1)]
    ids = set()
    for line in table.splitlines():
        if not line.startswith("|") or line.startswith("| ---"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2 or cells[0].startswith("Duty tile"):
            continue
        ids.update(re.findall(r"`([a-z_]+)`", cells[1]))
    return ids


def test_the_rules_table_is_still_readable():
    """If this fails the parser below has stopped seeing the table, and every id check under it
    would pass vacuously."""
    ids = canonical_ids()
    assert len(ids) >= 8, ids
    assert "clerical_devotion" in ids and "tithe" in ids, sorted(ids)


def test_every_duty_and_slot_is_present(text, lab):
    """Both keys always exist. A duty with one action spells its second slot `null` rather than
    leaving the key out, so a typo in the key name still fails instead of quietly meaning
    'one action'."""
    slugs = [d[0] for d in lab.DUTIES]
    assert sorted(text["duties"]) == sorted(slugs), sorted(text["duties"])
    for slug, entry in text["duties"].items():
        assert sorted(k for k in entry) == list(SLOTS), (slug, sorted(entry))
        assert entry[SLOTS[0]] is not None, "%s has no first action" % slug


def test_only_taxation_and_allocation_have_one_action(text):
    """Which duties offer one action is a fact about the game, so it is named rather than
    counted. Anything else going null here is a design change and should say so out loud."""
    single = sorted(s for s, e in text["duties"].items() if e[SLOTS[1]] is None)
    assert single == ["allocation", "taxation"], single


def test_every_engine_action_named_here_exists_in_the_rules(text):
    """THE JOIN. A null is allowed -- some duties have no engine action yet -- but an id that is
    not in DutyTiles.md is a caption describing something the engine does not have."""
    ids = canonical_ids()
    for slug, entry in text["duties"].items():
        for slot in SLOTS:
            if entry[slot] is None:
                continue          # a one-action duty
            action = entry[slot].get("engineAction")
            if action is None:
                continue
            assert action in ids, (
                "%s/%s names engine action %r, which is not in DutyTiles.md's canonical table: %s"
                % (slug, slot, action, sorted(ids)))


def test_a_box_always_has_something_to_say(text):
    """shortLabel is the caption the card has always had, so it may not be missing or blank.
    `name` may be null, because the action names are still being decided -- but not blank, which
    would be indistinguishable from a mistake."""
    for slug, entry in text["duties"].items():
        for slot in SLOTS:
            if entry[slot] is None:
                continue          # a one-action duty
            label = entry[slot].get("shortLabel")
            assert isinstance(label, str) and label.strip(), (slug, slot, label)
            name = entry[slot].get("name", None)
            assert name is None or (isinstance(name, str) and name.strip()), (slug, slot, name)


def test_the_wording_is_stored_as_written_not_shouted(text):
    """The card uppercases in CSS. A value stored already uppercase cannot be reused anywhere
    quieter, and the two conventions would drift into the same file."""
    for slug, entry in text["duties"].items():
        for slot in SLOTS:
            if entry[slot] is None:
                continue          # a one-action duty
            for field in ("name", "shortLabel"):
                v = entry[slot].get(field)
                if isinstance(v, str) and len(v) > 3:
                    assert v != v.upper(), (
                        "%s/%s %s is stored shouting (%r); the card does that, see `casing`"
                        % (slug, slot, field, v))


def test_the_generator_keeps_no_second_copy(lab):
    """DUTIES is slug, name and angle. If it grows the labels back there are two owners again."""
    for row in lab.DUTIES:
        assert len(row) == 3, (
            "DUTIES rows carry %d fields; the action wording belongs in duty_text.json" % len(row))
    src = GEN.read_text(encoding="utf-8")
    assert "duty_text.json" in src, "the generator no longer reads the file that owns the wording"


def test_the_starting_layout_actually_uses_the_file(text, lab):
    """Not just that the file is read -- that what it says is what the cards get."""
    S = lab.default_state()
    for slug, entry in text["duties"].items():
        for slot in SLOTS:
            got = S["duties"][slug][slot]
            if entry[slot] is None:
                # The slot still exists so the schema stays one shape for all eight duties; it
                # simply says nothing, and nothing draws it.
                assert got["shortLabel"] == "" and got["name"] is None, (slug, slot, got)
                continue
            assert got["shortLabel"] == entry[slot]["shortLabel"], (slug, slot)
            assert got["name"] == entry[slot].get("name"), (slug, slot)


def test_the_two_fields_are_no_longer_the_same_string(lab):
    """The bug this whole change came out of: `name` and `shortLabel` held one value in every
    duty, so one caption could stand in for both and nobody noticed there were two fields."""
    S = lab.default_state()
    named = [(slug, slot) for slug in S["duties"] for slot in SLOTS
             if S["duties"][slug][slot]["name"]]
    assert named, "no duty has an action name yet, so this guard proves nothing"
    for slug, slot in named:
        a = S["duties"][slug][slot]
        assert a["name"] != a["shortLabel"], (
            "%s/%s has the same text in both fields (%r) -- the name is what the action is "
            "called, the shortLabel is what it does" % (slug, slot, a["name"]))


def test_a_missing_file_stops_the_build_rather_than_drawing_blanks(lab, monkeypatch, tmp_path):
    """No fallback: a blank caption on a finished-looking card is the failure worth avoiding."""
    monkeypatch.setattr(lab, "DUTY_TEXT_ASSET", tmp_path / "gone.json")
    with pytest.raises(SystemExit) as e:
        lab.duty_text()
    assert "duty_text.json" in str(e.value)


def test_the_effect_line_shouts_by_default_and_the_switch_can_stop_it(lab):
    """One switch, for both boxes, and it starts on.

    The card has always uppercased the effect line, so ON is the default and turning it off is
    the new thing: it shows the sentence duty_text.json actually holds -- "Gain X piety", proper
    nouns intact -- which is the form the wording is written and reused in.

    It governs the effect line ALONE. The action name is a label and stays set the way the card
    sets labels, so nothing here should touch it.
    """
    d = lab.default_state()
    assert d["display"]["effectUpper"] is True, (
        "the effect line has always shouted; off is the choice, not the default")
    # ONE switch, not one per box: a composition with one box shouting and the other not is not
    # a thing anybody wants to be able to make by accident.
    for side in ("artLeft", "artRight"):
        assert "effectUpper" not in d["display"][side], (
            "%s carries its own casing switch; it belongs to the composition, not the box" % side)

    src = (lab.HERE / "duty_wheel_layout_lab.html.tmpl").read_text(encoding="utf-8")
    # The class is what the renderer hangs it on, and the CSS is what makes the class mean
    # something. Either alone is a switch that does nothing.
    assert '.art .cap.asis{text-transform:none}' in src
    assert 'S.display.effectUpper ? "" : " asis"' in src
    # And it must not reach the name.
    assert '.art .anm.asis' not in src, (
        "the action name is a label and is set the way the card sets labels")


def test_a_session_saved_before_the_switch_keeps_shouting(lab):
    """The trap this avoids: `!!undefined` is false, so coercing an absent key would turn the
    switch OFF on load and silently restyle every caption in somebody's saved composition.
    Absent means 'saved before this existed', which is the default."""
    src = (lab.HERE / "duty_wheel_layout_lab.html.tmpl").read_text(encoding="utf-8")
    i = src.index("S.display.effectUpper = (S.display.effectUpper === undefined")
    block = src[i:i + 400]
    assert "DEFAULT_STATE.display.effectUpper" in block, (
        "an absent switch must fall back to the default, not to false")


def test_the_state_is_stamped_with_the_wording_it_was_built_from(lab):
    """The fingerprint that lets a stale autosave be told from somebody's typing.

    Without it the lab looks broken in a specific and confusing way: the generator has been run,
    the file has been edited, and the page still shows the old words -- because localStorage kept
    a whole state and deepMerge lets the saved copy win over the defaults.
    """
    d = lab.default_state()
    v = d.get("textVersion")
    assert isinstance(v, str) and len(v) == 12 and all(c in "0123456789abcdef" for c in v), v
    assert d["version"] == lab.STATE_VERSION, "the schema version is a different thing"
    assert v != str(lab.STATE_VERSION), "the wording fingerprint is not the schema version"


def test_the_fingerprint_follows_the_words_and_nothing_else(lab):
    """It must move when a card would read differently, and stay put otherwise -- a fingerprint
    that changed on every save would throw away real work, and one that never changed would
    never refresh anything."""
    said = lab.duty_text()
    base = lab.duty_text_version(said)

    import copy
    changed = copy.deepcopy(said)
    changed["clerical"]["actionA"]["shortLabel"] = "Gain Y piety"
    assert lab.duty_text_version(changed) != base, "a changed caption did not move the version"

    renamed = copy.deepcopy(said)
    renamed["clerical"]["actionA"]["name"] = "Prayer"
    assert lab.duty_text_version(renamed) != base, "a changed action name did not move it"

    # Only what reaches a card counts. Editing the explanatory prose at the top of the file --
    # `note`, `casing`, `theX` -- must not invalidate everybody's saved session.
    import json
    raw = json.loads(lab.DUTY_TEXT_ASSET.read_text(encoding="utf-8"))
    raw["note"] = "reworded entirely"
    raw["duties"]["clerical"]["actionA"]["unresolved"] = "a new note to self"
    from_raw = {s: {k: (None if v is None else {"name": v["name"],
                                                "shortLabel": v["shortLabel"]})
                    for k, v in e.items()} for s, e in raw["duties"].items()}
    assert lab.duty_text_version(from_raw) == base, (
        "editing the notes in duty_text.json invalidated every saved session")


def test_a_stale_session_is_refreshed_and_a_typed_one_is_not(lab):
    """The two halves of the rule, read off the template because the behaviour is the page's.

    Exercised for real in test_board_v2_layout_lab.py, which can run the page; this is the
    cheap check that the condition is still the fingerprint rather than something that would
    fire on every load and discard somebody's wording every time.
    """
    src = (lab.HERE / "duty_wheel_layout_lab.html.tmpl").read_text(encoding="utf-8")
    i = src.index("if (d.duties && d.textVersion !== TEXT_VERSION){")
    block = src[i:i + 600]
    assert "delete D[a.key].name" in block and "delete D[a.key].shortLabel" in block
    assert "delete D.actions" in block, (
        "a stale action count would leave a box drawn for an action that no longer exists")
    assert "d.textVersion = TEXT_VERSION;" in src
