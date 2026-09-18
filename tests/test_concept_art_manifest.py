"""ui/concept/ keeps its files under derived names. These check the derivation still holds.

Renaming a file is what makes the folder readable and is also what destroys the link back to the
export it came from. `manifest.json` is the replacement for that link, so it is only worth having
if it cannot quietly fall out of step with what is on disk -- which is what these test.

The licence check is the one that matters most. `_reference/` holds third-party images kept for
inspiration and never used in the game, and the whole point of the folder is that its contents do
not enter git history. That is a rule a person can forget; it is not a rule a test forgets.
"""

import hashlib
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CONCEPT = REPO_ROOT / "ui" / "concept"
MANIFEST = CONCEPT / "manifest.json"
BUILDER = CONCEPT / "build_browser.py"
GITIGNORE = REPO_ROOT / ".gitignore"

# Not concept art: generated output, and the git-ignored reference shelf.
SKIP_DIRS = {"generated", "_reference"}


def manifest() -> dict:
    if not MANIFEST.is_file():
        pytest.skip("ui/concept/manifest.json is not in this checkout")
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def declared() -> list:
    """What build_browser.py says the page is made of, as (subject id, kind, relative path)."""
    if not BUILDER.is_file():
        pytest.skip("ui/concept/build_browser.py is not in this checkout")
    # build_browser imports Pillow at module scope and exits if it is absent. Importing it here
    # without this would turn a missing optional dependency into a collection error for the whole
    # file, which is the other gothic asset guards' reason for the same line.
    pytest.importorskip("PIL", reason="build_browser imports Pillow to embed the images")
    sys.path.insert(0, str(CONCEPT))
    try:
        import build_browser
    except ModuleNotFoundError as exc:                               # pragma: no cover
        pytest.skip("build_browser needs %s" % exc.name)
    out = []
    for subject in build_browser.SUBJECTS:
        for spec in subject["kinds"]:
            if spec.get("root") == "assets":
                continue                     # borrowed production art, filed elsewhere
            rel = spec.get("rel") or "%s/%s.png" % (subject["id"], spec["kind"])
            out.append((subject["id"], spec["kind"], rel))
    return out


def test_every_committed_file_is_still_what_the_manifest_says() -> None:
    """A file edited or replaced in place keeps its name and stops being what was recorded."""
    for row in manifest()["images"]:
        if not row["committed"]:
            continue
        path = CONCEPT / row["path"]
        assert path.is_file(), "%s is in the manifest and not on disk" % row["path"]
        raw = path.read_bytes()
        assert len(raw) == row["bytes"], "%s changed size since it was filed" % row["path"]
        assert hashlib.sha256(raw).hexdigest() == row["sha256"], (
            "%s no longer hashes to what manifest.json records. Either it was edited in place, or "
            "a different image was copied over it. Rebuild the manifest rather than editing the "
            "hash." % row["path"])


def test_nothing_on_disk_is_missing_from_the_manifest() -> None:
    """The other direction: a file dropped into the folder by hand has no provenance at all."""
    rows = {row["path"] for row in manifest()["images"]}
    for path in sorted(CONCEPT.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
            continue
        rel = path.relative_to(CONCEPT)
        if rel.parts[0] in SKIP_DIRS:
            continue
        assert rel.as_posix() in rows, (
            "%s is in ui/concept/ with no manifest entry, so nothing records where it came from "
            "or what it was called before." % rel.as_posix())


def test_the_page_and_the_manifest_describe_the_same_files() -> None:
    """Two tables, two jobs -- the page's shape and the files' provenance. They must still meet."""
    rows = {row["path"] for row in manifest()["images"]}
    for subject_id, kind, rel in declared():
        assert rel in rows, (
            "build_browser.py shows %s/%s from %s, which has no manifest entry."
            % (subject_id, kind, rel))
    shown = {rel for _, _, rel in declared()}
    for row in manifest()["images"]:
        assert row["path"] in shown, (
            "%s is in the manifest but no subject in build_browser.py claims it, so it appears on "
            "no page and nothing would notice it going stale." % row["path"])


def test_uncommitted_reference_art_is_actually_ignored_by_git() -> None:
    """The licence rule, enforced rather than trusted.

    An image we do not have the right to redistribute must sit somewhere `.gitignore` covers. A
    rule that lives only in a README is a rule that survives until the first hurried `git add`.
    """
    ignored = GITIGNORE.read_text(encoding="utf-8")
    for row in manifest()["images"]:
        if row["committed"]:
            continue
        prefix = row["path"].split("/")[0]
        assert "ui/concept/%s/" % prefix in ignored, (
            "manifest.json marks %s as not committed, but .gitignore has no rule covering "
            "ui/concept/%s/. Either add the rule or stop claiming the file is kept out."
            % (row["path"], prefix))
        assert row["origin"], "%s is third-party and records no source" % row["path"]
