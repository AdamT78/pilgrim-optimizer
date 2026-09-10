"""Everything a seat decides must agree about which seat it is.

WHY THIS EXISTS

A player board carries several assets that all follow from one seat colour: the drape, its dim twin,
the gemstones, the acolyte cube. They are drawn as `<use>` elements pointing at symbols embedded in
the board, and the failure this guards against is not a broken reference -- it is a perfectly valid
reference to the wrong symbol.

That has happened. Rewriting the picker's seat handler, the acolyte cube was left pointing at the
previous seat's colour: a plum board with a sage green cube. Nothing complained. The markup was
well-formed, the `<use>` resolved, the symbol existed, the page threw no error, and a diff of the
generated SVG showed a plausible id changing to another plausible id. Only looking at the picture
gave it away.

So these tests do what looking at the picture does, but arithmetically: they follow every
`data-asset-role` through its `<use>`, through the symbol it names, to the file that symbol actually
carries -- and check that file is the one the seat asked for.
"""

from __future__ import annotations

import copy
import importlib.util
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
UI = REPO / "ui"
ASSETS = UI / "assets-gothic"
SVG_NS = "http://www.w3.org/2000/svg"

# Roles the config may name explicitly; they are cleared before each build so the seat supplies them
# and the test is measuring the seat rather than whatever the config happened to be left holding.
SEAT_ROLES = ("frame_base", "frame_ornaments", "cloth_lit", "cloth_dim", "gems", "acolyte_cube")


def q(tag: str) -> str:
    return f"{{{SVG_NS}}}{tag}"


@pytest.fixture(scope="module")
def asm():
    path = UI / "render" / "gen_board_gothic.py"
    if not path.is_file() or not ASSETS.is_dir():
        pytest.skip("the gothic tree is not in this checkout")
    spec = importlib.util.spec_from_file_location("gothic_assembler", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build(asm, seat: str, turn: str = "lit") -> ET.Element:
    """One board, exactly as the production assembler makes it."""
    config = copy.deepcopy(asm.read_json(ASSETS / "production_test_config.json"))
    for role in SEAT_ROLES:
        config.pop(role, None)
    config["seat"] = seat
    config["turn"] = turn
    asm.apply_seat(config)
    layout = asm.read_json(ASSETS / "metadata" / "layout.json")
    root = ET.parse(ASSETS / "template" / "player_board_template.svg").getroot()
    asm.apply_config(root, config, layout)
    asm.embed_assets_once(root, ASSETS)
    asm.assert_no_duplicated_payloads(root)
    return root


def drawn_sources(root: ET.Element) -> dict[str, str]:
    """role -> the asset file that role ends up actually drawing.

    This is the whole point: not what the config said, but what the finished board resolves to.
    """
    by_id = {s.get("id"): s.get("data-source") for s in root.iter(q("symbol"))}
    drawn = {}
    for use in root.iter(q("use")):
        role = use.get("data-asset-role")
        if not role:
            continue
        target = (use.get("href") or "")[1:]
        assert target in by_id, f"role {role!r} points at #{target}, which is not a symbol here"
        drawn[role] = by_id[target]
    return drawn


def test_every_seat_decided_role_draws_that_seats_file(asm):
    for seat in asm.SEAT_COLORS:
        drawn = drawn_sources(build(asm, seat))
        for role, expected in asm.seat_layers(seat).items():
            assert role in drawn, f"{seat}: the board has no <use> for role {role!r}"
            assert drawn[role] == expected, (
                f"{seat}: role {role!r} draws {drawn[role]!r}, but the seat asked for {expected!r}"
            )


def test_no_board_mentions_another_seats_colour(asm):
    """Read the filenames, not the table, so a wrong `seat_layers` cannot vouch for itself.

    The test above compares the board against `seat_layers`, which means both sides come from the
    same source of truth. This one only reads the names of the files that ended up on the board and
    asserts no rival seat is among them.
    """
    for seat in asm.SEAT_COLORS:
        others = [c for c in asm.SEAT_COLORS if c != seat]
        for role, source in drawn_sources(build(asm, seat)).items():
            stem = Path(source).stem
            intruder = [c for c in others if c in stem.split("_")]
            assert not intruder, (
                f"{seat} board: role {role!r} draws {source!r}, which belongs to {intruder[0]}"
            )


def test_the_turn_shows_exactly_one_drape(asm):
    """Both drapes ship in the board and one is hidden; neither zero nor two is a board."""
    for seat in asm.SEAT_COLORS:
        for turn in ("lit", "dim"):
            root = build(asm, seat, turn)
            holder = root.find(f".//{q('g')}[@data-turn]")
            assert holder is not None, "the template has no turn holder"
            assert holder.get("data-turn") == turn
            shown = [use.get("data-turn-layer") for use in holder.iter(q("use"))
                     if use.get("data-turn-layer") and use.get("display") != "none"]
            assert shown == [turn], (
                f"{seat}/{turn}: the drapes displayed are {shown}, expected exactly ['{turn}']"
            )


def test_the_two_drapes_are_different_pictures(asm):
    """A lit and a dim drape pointing at one symbol would toggle nothing at all."""
    for seat in asm.SEAT_COLORS:
        drawn = drawn_sources(build(asm, seat))
        assert drawn["cloth_lit"] != drawn["cloth_dim"], (
            f"{seat}: lit and dim draw the same file, so the turn indicator does nothing"
        )


def test_the_committed_config_is_coherent(asm):
    """The config as committed, not scrubbed first.

    `apply_seat` fills only roles the config has not already set, which is deliberate -- it is what
    lets the frame-layer regression check dress a board in the red source. The cost of that design
    is that a stale explicit path in the production config silently outranks the seat, and every
    other test here clears those paths before building, so none of them would see it.
    """
    config = copy.deepcopy(asm.read_json(ASSETS / "production_test_config.json"))
    seat = config.get("seat")
    assert seat, "the production config names no seat"
    asm.apply_seat(config)
    layout = asm.read_json(ASSETS / "metadata" / "layout.json")
    root = ET.parse(ASSETS / "template" / "player_board_template.svg").getroot()
    asm.apply_config(root, config, layout)
    asm.embed_assets_once(root, ASSETS)
    for role, expected in asm.seat_layers(seat).items():
        drawn = drawn_sources(root).get(role)
        assert drawn == expected, (
            f"the committed config draws {drawn!r} for {role!r} on a {seat} board; the seat asks "
            f"for {expected!r}. Something is overriding the seat -- check for a leftover "
            f"{role!r} key in production_test_config.json."
        )


def test_the_shared_frame_layers_are_shared(asm):
    """The stonework and ornaments are colour-neutral: every seat must draw the same two files."""
    seen = {}
    for seat in asm.SEAT_COLORS:
        drawn = drawn_sources(build(asm, seat))
        for role in ("frame_base", "frame_ornaments"):
            seen.setdefault(role, {})[seat] = drawn[role]
    for role, per_seat in seen.items():
        assert len(set(per_seat.values())) == 1, (
            f"{role} differs by seat ({per_seat}), so the frame would be embedded once per seat"
        )
