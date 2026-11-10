"""Guards for the duty banners on ui/board_v2/action_board's v2 board.

WHY THESE AND NOT A GENERAL v2 SUITE. v2 is a fork for answering one design question and most of
what it does is visible the moment you open it. The banners are the exception, and they are the
exception for one reason: **every way they can be wrong looks fine.**

A banner is a BLANK parchment with the duty's name set over it at render time. So the art carries
no information about which duty it belongs to, and the pairing of blank to name lives entirely in
a filename. Give Clerical the wrong blank and you get a correctly-spelled title on a
slightly-different piece of vellum -- no build error, no exception, no visibly broken layout,
nothing in the console. Nobody would find it by looking, and there is nothing else in this tree
that would catch it.

The pairing is also INHERITED rather than invented: `tools/ui_debug/generate_duty_board_check.py`
zips `DUTY_NAMES` from `ui/render/gen_duty_grid.py` against `BANNER_ORDER`, and the sow page and
the concept browser have drawn it for months. v2 COPIED the art into its own tree so the build
reads nothing from those trees -- which is right, and which means a drift between the copy and
the original now has nothing watching it. These tests are that watch: the coupling belongs in a
guard, not in the build.

THE BOARD NO LONGER DRAWS ANY OF THIS. The parchments came off on 2026-11-09 and the
rectangles carry no name at all. The files stayed, and so did these guards, because the
cheapest way to keep the option of putting them back is to keep them correct while they are
unused -- art that is deleted and re-fetched comes back as a different file. The last test
here is the one that changed: it used to hold that the generator inlines all nine, and it
now holds that the removal is complete rather than half-done.

Each test names the failure it exists to catch and how to falsify it.
"""
import hashlib
import importlib.util
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
BOARD = ROOT / "ui" / "board_v2"
TOOL = BOARD / "action_board"
BANNERS = BOARD / "duty_actions" / "banners"
FONTS = BOARD / "fonts"
ATTRIB = BOARD / "attribution.json"

# THE PAIRING, WRITTEN OUT. This is the one place in board_v2 that states it in full, and it is
# deliberately a literal rather than something derived: a derivation would be a second copy of
# the logic it is checking, and would agree with the filenames for the same reason they are
# wrong. `test_the_pairing_still_matches_the_tree_it_was_taken_from` holds this against the
# original, so the literal cannot quietly drift either.
#
#   duty slug  ->  which duty_banner_NN.png in ui/assets-gothic/banners/ it was made from
PAIRING = {
    "allocation": 1,
    "clerical": 5,
    "construct": 8,
    "build_roads": 3,
    "city": 9,
    "ordination": 4,
    "produce": 7,
    "taxation": 6,
    "give_alms": 2,
}


def _load(name: str, where: pathlib.Path = TOOL):
    spec = importlib.util.spec_from_file_location("_abv2_" + name, where / (name + ".py"))
    if spec is None or spec.loader is None:                       # pragma: no cover
        pytest.skip("cannot import %s" % name)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    sys.path.insert(0, str(where))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(where))
    return mod


@pytest.fixture(scope="module")
def record():
    return json.loads(ATTRIB.read_text(encoding="utf-8"))["files"]


@pytest.fixture(scope="module")
def geo():
    return _load("geometry")


def _key(slug):
    return "duty_actions/banners/%s_banner_v01.webp" % slug


# =================================================================================================
# THE PAIRING
# =================================================================================================

def test_every_duty_and_the_city_has_a_banner_on_disk(geo):
    """Nine rectangles, nine parchments, and the City is one of them.

    WRITTEN BECAUSE A MISSING BANNER IS A SILENT DOWNGRADE, not a failure. `banner()` in the
    template falls back to printing the duty's name as text when `BANNERS[slug]` is absent --
    which is the right behaviour on a page that must still draw with no art at all, and which
    means deleting a file costs you one parchment and no warning anywhere.

    THE CITY IS INCLUDED DELIBERATELY. It is not a duty and does not appear in `geo.DUTIES`, so
    every loop in this tree that walks the eight would skip it -- and it is exactly the one whose
    banner was added last and is least likely to be remembered.

    Falsified by deleting any of the nine .webp files.
    """
    want = set(slug for slug, _n, _d in geo.DUTIES) | {"city"}
    assert want == set(PAIRING), "PAIRING and geometry disagree about which duties exist"
    missing = sorted(s for s in want if not (BANNERS / ("%s_banner_v01.webp" % s)).is_file())
    assert not missing, "no banner art for: %s" % missing


def test_every_banner_is_recorded_and_its_sha256_is_the_file(record):
    """The record gates the art, and the hash is what makes the record worth having.

    `bundled_banners()` refuses to inline a file that attribution.json has no entry for, so an
    unrecorded banner is another silent downgrade to the text fallback. And an entry whose
    sha256 no longer matches the bytes is worse than no entry: it is a provenance claim about a
    file that has since changed.

    Falsified by adding a banner without a record, or by re-encoding one without updating its
    sha256.
    """
    bad = []
    for slug in sorted(PAIRING):
        key = _key(slug)
        if key not in record:
            bad.append("%s has no attribution entry" % key)
            continue
        e = record[key]
        if e.get("state", "present") != "present":
            bad.append("%s is recorded but not present" % key)
            continue
        got = hashlib.sha256((BOARD / key).read_bytes()).hexdigest()
        if got != e.get("sha256"):
            bad.append("%s: record says %s, file is %s" % (key, e.get("sha256"), got))
    assert not bad, "\n".join(bad)


def test_each_banner_names_the_blank_it_was_made_from(record):
    """The pairing, held against what each record SAYS it came from.

    THIS IS THE TEST THE WHOLE FILE EXISTS FOR. The blanks carry no clue to which duty they
    belong to -- the title is drawn over them at render time -- so a banner paired with the
    wrong duty produces a correctly-spelled name on the wrong vellum and NOTHING anywhere says
    so. It is not caught by the build, by a layout check, or by looking at the board.

    The record's `source` names its origin file, and this holds that against PAIRING. It is a
    weaker check than comparing pixels and a far cheaper one, and it catches the failure that
    actually happens: a file renamed or copied under the wrong name.

    Falsified by swapping any two banner files, or by editing a `source` to name a different
    duty_banner_NN.png.
    """
    wrong = []
    for slug, n in sorted(PAIRING.items()):
        src = record[_key(slug)].get("source", "")
        want = "duty_banner_%02d.png" % n
        if want not in src:
            wrong.append("%s should name %s; its source says %r"
                         % (slug, want, src[:90]))
    assert not wrong, "\n".join(wrong)


def test_the_pairing_still_matches_the_tree_it_was_taken_from():
    """And the literal above is held against the original, so the copy cannot drift.

    v2 COPIED the art so the build reads nothing from ui/render/ or ui/assets-gothic/. That is
    the right call and it has a cost: the pairing now exists in two places that no longer talk to
    each other. A guard is where that coupling belongs -- it fails on a Tuesday in CI rather than
    changing what the board draws.

    SKIPPED, NOT FAILED, IF THE ORIGINALS ARE GONE. board_v2 is meant to outlive them; the day
    ui/render/ is deleted this test should quietly stop applying rather than block a release.

    Falsified by changing BANNER_ORDER or DUTY_NAMES upstream without changing PAIRING here.
    """
    try:
        dg = _load("gen_duty_grid", ROOT / "ui" / "render")
        check = _load("generate_duty_board_check", ROOT / "tools" / "ui_debug")
    except BaseException:                                   # pragma: no cover
        pytest.skip("the upstream pairing is not importable here")
    names = list(getattr(dg, "DUTY_NAMES", []))
    order = tuple(getattr(check, "BANNER_ORDER", ()))
    if not names or not order:                              # pragma: no cover
        pytest.skip("upstream no longer publishes DUTY_NAMES / BANNER_ORDER")
    assert len(names) == len(order) == 9

    slug_of = {"The City": "city"}
    upstream = {}
    for name, n in zip(names, order):
        upstream[slug_of.get(name, name.lower().replace(" ", "_"))] = n
    assert upstream == PAIRING, (
        "the pairing has drifted from ui/render + tools/ui_debug.\n"
        "  upstream: %s\n  here:     %s" % (sorted(upstream.items()), sorted(PAIRING.items())))


# =================================================================================================
# WHAT THE LAYOUT ASSUMES ABOUT THE ART
# =================================================================================================

def test_every_banner_is_three_to_one():
    """The template divides by a literal 3.0, so a banner that is not 3:1 is drawn distorted.

    `BANRATIO = 3.0` turns a wanted HEIGHT into a width, and the <img> is then stretched to that
    box -- so an off-ratio parchment is squashed or stretched rather than letterboxed, with no
    edge to notice. It is the duty-card squash fault again on a different picture.

    THE TOLERANCE IS ONE PIXEL OF WIDTH, not a ratio threshold somebody has to justify: the
    source art measures 2172 x 724 and two of the ten came back at 2171, so exact equality would
    fail on art that is correct. One pixel at 512 wide is 0.2%, far below anything visible.

    Falsified by filing a banner at any other shape.
    """
    from PIL import Image
    wrong = []
    for slug in sorted(PAIRING):
        p = BANNERS / ("%s_banner_v01.webp" % slug)
        w, h = Image.open(p).size
        if abs(w - 3 * h) > 1:
            wrong.append("%s is %d x %d, ratio %.4f" % (p.name, w, h, w / h))
    assert not wrong, "\n".join(wrong)


def test_the_art_is_at_least_twice_what_the_board_ever_draws(geo):
    """Big enough for a retina screen, and the ceiling is derived rather than assumed.

    A banner is drawn at the ICON's height, and the icon is capped at `GEO.ribbon.seal` whatever
    the sliders say -- so the widest a banner is ever drawn is 3 * seal, and nothing the page can
    be dragged to changes that. This holds the shipped raster against twice that.

    IT IS A FLOOR, NOT AN EQUALITY. Filing larger art is wasteful but harmless; filing smaller is
    a soft picture on exactly the screens people look closely at.

    Falsified by re-rastering the banners below 2x, or by raising GEO.ribbon.seal past half the
    shipped width without re-rastering.
    """
    from PIL import Image
    widest_drawn = 3.0 * geo.SEAL
    thin = []
    for slug in sorted(PAIRING):
        p = BANNERS / ("%s_banner_v01.webp" % slug)
        w = Image.open(p).size[0]
        if w < 2 * widest_drawn:
            thin.append("%s is %d wide; the board can draw %.0f, so it wants %.0f"
                        % (p.name, w, widest_drawn, 2 * widest_drawn))
    assert not thin, "\n".join(thin)


# =================================================================================================
# THE FACE
# =================================================================================================

def test_the_banner_face_is_present_and_is_the_upstream_file():
    """Pirata One, byte for byte, with its licence beside it.

    THE TITLES ARE SET LIVE, so the font is load-bearing in a way the art is not: without it
    every banner falls back to a serif at once -- the board still draws, which is the behaviour
    the sow page chose and this one keeps, and which is exactly why nothing would complain.

    BYTE FOR BYTE MATTERS HERE BECAUSE OF THE LICENCE, not because of the glyphs. `Pirata` is a
    Reserved Font Name under the OFL: modifying the file obliges a rename. Holding this copy
    against ui/assets/fonts/ is how we keep saying truthfully that nothing was modified.

    AND OFL.txt HAS TO TRAVEL WITH IT. Copying the font out of ui/assets/ left its licence text
    behind, which the OFL does not allow.

    Falsified by subsetting or re-saving the font, or by deleting OFL.txt.
    """
    here = FONTS / "PirataOne-Regular.ttf"
    assert here.is_file(), "the banner face is missing from ui/board_v2/fonts/"
    assert (FONTS / "OFL.txt").is_file(), (
        "OFL.txt must sit beside the font: the licence requires it to travel with the file")
    upstream = ROOT / "ui" / "assets" / "fonts" / "PirataOne-Regular.ttf"
    if not upstream.is_file():                              # pragma: no cover
        pytest.skip("the upstream font is gone, so there is nothing to compare against")
    assert here.read_bytes() == upstream.read_bytes(), (
        "the copy differs from ui/assets/fonts/. `Pirata` is a Reserved Font Name, so a modified "
        "file must be renamed -- and this tree claims in attribution that it is unmodified.")


def test_the_font_is_not_recorded_as_an_asset(record):
    """And it is deliberately NOT in attribution.json, which is worth a guard of its own.

    This was tried the other way first and five tests failed. A .ttf is not in `imageSuffixes`,
    so the asset walk cannot see it -- a record for it reads as a record naming a file that is
    not in the tree. And `test_the_stated_default_is_written_down` holds that every recorded
    entry under duty_actions/ carries `openai-generated`, which an OFL face does not.

    So the font lives OUTSIDE duty_actions/ and carries no entry, and this test exists so that
    the next person to notice an unrecorded file in a tree that records everything finds the
    reason here rather than re-deriving it through five red tests.

    Falsified by adding an attribution entry for the font, or by moving it under duty_actions/.
    """
    named = [k for k in record if k.lower().endswith(".ttf")]
    assert not named, (
        "the font must not be recorded -- a .ttf is not an asset by imageSuffixes, so the walk "
        "cannot see it and the entry reads as naming a missing file: %s" % named)
    assert not (BOARD / "duty_actions" / "banners" / "PirataOne-Regular.ttf").is_file(), (
        "the font must not live under duty_actions/: every recorded entry there has to carry "
        "`openai-generated`, and an OFL face from Google Fonts cannot")


# =================================================================================================
# WHAT THE GENERATOR DOES WITH THEM
# =================================================================================================

def test_the_resources_are_kept_although_nothing_draws_them_any_more():
    """THE BANNERS CAME OFF THE BOARD ON 2026-11-09 AND THE FILES DELIBERATELY STAYED.

    Everything above checks files on disk, and all of it still earns its keep: a resource that is
    deleted and later re-fetched comes back as a DIFFERENT file with a different provenance, so
    the cheapest way to keep the option of putting the parchments back is to leave them where they
    are, recorded, paired and measured. That is what this file now guards.

    What it stops guarding is the one thing that is no longer true: the generator used to inline
    all nine and the face, and it no longer has a `bundled_banners()` at all. So the end-to-end
    test is inverted -- it holds that the removal is COMPLETE rather than half-done. A half-done
    removal is the real risk here: delete the images and keep the code and every rectangle grows
    a serif caption from `banner()`'s own fallback; keep the code and the token and the page
    carries 287 KB of data URI for an element nobody draws.

    Falsified by putting `bundled_banners()` back without putting the drawing back, or the other
    way round.
    """
    gen = (TOOL / "generate_action_board_v2.py").read_text(encoding="utf-8")
    tmpl = (TOOL / "action_board_v2.html.tmpl").read_text(encoding="utf-8")

    assert "def bundled_banners" not in gen, (
        "the generator bundles the banners again; if that is wanted, the page has to draw them "
        "too, and this test and the one in test_action_board_v2_grid.py both have to change")
    assert "base64" not in gen, (
        "the generator inlines something as base64 again -- v2 bundles art through v1's helpers, "
        "so a base64 call here is the banner path coming back")
    for token in ("__BANNERS__", "__BANNERMETA__", "__BANNERFONT__"):
        assert token not in gen and token not in tmpl, (
            "%s is back in the build, so the page carries banner data again" % token)

    # And the files are still here, which is the whole point of the rest of this file.
    assert BANNERS.is_dir(), "duty_actions/banners/ has been deleted"
    assert len(list(BANNERS.glob("*.webp"))) == len(PAIRING), (
        "duty_actions/banners/ holds %d files and the pairing names %d"
        % (len(list(BANNERS.glob("*.webp"))), len(PAIRING)))
    assert (FONTS / "PirataOne-Regular.ttf").is_file(), "the face has been deleted"
    assert (FONTS / "OFL.txt").is_file(), (
        "the licence text has been deleted, and the OFL requires it to travel with the font")
