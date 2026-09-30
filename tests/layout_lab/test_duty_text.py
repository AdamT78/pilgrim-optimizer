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
    slugs = [d[0] for d in lab.DUTIES]
    assert sorted(text["duties"]) == sorted(slugs), sorted(text["duties"])
    for slug, entry in text["duties"].items():
        assert sorted(k for k in entry) == list(SLOTS), (slug, sorted(entry))


def test_every_engine_action_named_here_exists_in_the_rules(text):
    """THE JOIN. A null is allowed -- some duties have no engine action yet -- but an id that is
    not in DutyTiles.md is a caption describing something the engine does not have."""
    ids = canonical_ids()
    for slug, entry in text["duties"].items():
        for slot in SLOTS:
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
            label = entry[slot].get("shortLabel")
            assert isinstance(label, str) and label.strip(), (slug, slot, label)
            name = entry[slot].get("name", None)
            assert name is None or (isinstance(name, str) and name.strip()), (slug, slot, name)


def test_the_wording_is_stored_as_written_not_shouted(text):
    """The card uppercases in CSS. A value stored already uppercase cannot be reused anywhere
    quieter, and the two conventions would drift into the same file."""
    for slug, entry in text["duties"].items():
        for slot in SLOTS:
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
