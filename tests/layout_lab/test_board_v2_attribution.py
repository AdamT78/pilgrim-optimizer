"""Every asset under ui/board_v2/ must be on the provenance record, and the record must not lie.

This exists because of what happened without it. ui/board_v2/attribution.json was added for one
vendored SVG, and over the next two releases the tree gained nine images -- a duty action master,
two crops of it, three resource tokens and their three untouched originals -- none of which was
recorded. Nothing noticed, because tools/verify_assets.py walks ui/assets and ui/assets-gothic
and has never walked this tree. The gothic tree has had a guard like this for a while; board_v2
did not, and the difference showed.

The file is data, not documentation: a reader that answers "may we ship this, and who do we
credit" has to be able to trust that a missing entry is impossible rather than merely unlikely.
"""
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
TREE = ROOT / "ui" / "board_v2"
RECORD = TREE / "attribution.json"

# What counts as an asset here. Source, documentation and the empty-folder markers are not.
ASSET_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".avif"}


@pytest.fixture(scope="module")
def record():
    return json.loads(RECORD.read_text(encoding="utf-8"))


def _assets():
    return sorted(p for p in TREE.rglob("*")
                  if p.is_file() and p.suffix.lower() in ASSET_SUFFIXES)


def test_every_asset_in_the_tree_has_an_entry(record):
    """The whole point. A file with no entry is a gap, never an implicit default."""
    assert _assets(), "found no assets under ui/board_v2/ at all -- has the tree moved?"
    missing = [str(p.relative_to(TREE)) for p in _assets()
               if str(p.relative_to(TREE)) not in record["files"]]
    assert not missing, (
        "no entry in ui/board_v2/attribution.json for: %s" % ", ".join(missing))


def test_the_record_does_not_name_files_that_are_gone(record):
    """The other direction, which rots more quietly: an entry for a deleted file reads as
    coverage and is not. Entries may declare themselves absent, and those are left alone."""
    here = {str(p.relative_to(TREE)) for p in _assets()}
    stale = [k for k, v in record["files"].items()
             if v.get("state", "present") == "present" and k not in here]
    assert not stale, "attribution.json claims files that are not in the tree: %s" % stale


def test_every_entry_names_a_licence_the_file_defines(record):
    licences = record["licences"]
    for name, entry in record["files"].items():
        assert "licence" in entry, "%s has no licence" % name
        assert entry["licence"] in licences, (
            "%s names licence %r, which this file does not define" % (name, entry["licence"]))


def test_anything_requiring_attribution_says_who_to_credit(record):
    """A licence with attributionRequired is a promise the repository has to be able to keep.

    VACUOUS TODAY, and deliberately kept: nothing in this tree currently requires attribution,
    because everything here is either OpenAI-generated or produced by a script in this
    repository. It guards the day somebody drops a CC-BY icon or a Noun Project glyph in here --
    ui/assets/ already carries four such licences, so it is a matter of when.
    """
    for name, entry in record["files"].items():
        if record["licences"][entry["licence"]].get("attributionRequired"):
            assert entry.get("creator"), (
                "%s needs attribution but names no creator" % name)


def test_the_stated_default_is_written_down_and_is_the_one_actually_used(record):
    """The project's rule is that an image here is ChatGPT-generated unless its entry says
    otherwise. That is worth an assertion rather than a convention: a rule nobody can read is a
    rule that gets applied differently by whoever touches the tree next."""
    assert "openai-generated" in record["licences"], (
        "the default licence for artwork in this tree is not defined")
    assert "ChatGPT" in record.get("defaultProvenance", ""), (
        "the default is not stated in the record itself")
    # And it is not merely declared: the artwork actually carries it.
    art = [k for k in record["files"] if k.startswith(("duty_actions/", "tokens/"))]
    assert art, "no artwork entries to check the default against"
    odd = [k for k in art if record["files"][k]["licence"] != "openai-generated"]
    assert not odd, (
        "these carry a non-default licence and each needs a source saying why: %s" % odd)


def test_a_derived_file_says_what_it_came_from(record):
    """A crop or a rescale is only trustworthy while the thing it was made from is named."""
    for name, entry in record["files"].items():
        mods = entry.get("modifications", "")
        if mods and mods != "none" and not mods.startswith("none"):
            assert entry.get("source"), "%s is modified but names no source" % name
