"""Guards on the generated third-party credits.

`ui/assets/gen_credits.py` renders the game's credits screen from `attribution.json`, so the
shipped credit cannot drift from the files it credits. It had no tests until 2026-09-24, which is
how the `source` guard below shipped a hole: it checked that a source BEGAN with a scheme rather
than that it was a URL, and a URL with a note appended sailed through into an href.
"""
import copy
import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def credits():
    spec = importlib.util.spec_from_file_location(
        "gen_credits", ROOT / "ui" / "assets" / "gen_credits.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_the_committed_notices_are_current(credits):
    """The same check CI runs, so a stale credit fails here rather than after a push."""
    assert credits.main(check=True) == 0, (
        "the notices no longer match attribution.json -- re-run ui/assets/gen_credits.py")


@pytest.mark.parametrize("source, ok", [
    ("https://thenounproject.com/icon/7392556/", True),
    ("http://example.com/a", True),
    # THE CASE THAT GOT THROUGH. It begins with a scheme and is not a URL.
    ("https://thenounproject.com/ -- icon 7392556, downloaded 2026-09-07", False),
    ("https://example.com/a and a note", False),
    ("https://example.com/a\n", False),
    ("downloaded from the artist", False),
])
def test_a_credited_source_has_to_be_a_whole_url(credits, source, ok, monkeypatch):
    """`source` is written straight into an href, so anything else ships a broken link.

    Checked through _check_sources rather than through _is_url alone, because the guard is only
    worth anything if it is actually reached for a file that carries an attribution obligation.
    """
    data = copy.deepcopy(credits.DATA)
    victim = next(path for path, a in data["files"].items()
                  if a["state"] == "present"
                  and data["licences"][a["licence"]]["attributionRequired"])
    data["files"][victim]["source"] = source
    monkeypatch.setattr(credits, "DATA", data)
    if ok:
        credits._check_sources()
    else:
        with pytest.raises(SystemExit) as exc:
            credits._check_sources()
        assert victim in str(exc.value), "the complaint does not name the file at fault"
