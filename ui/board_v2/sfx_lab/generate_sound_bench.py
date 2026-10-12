#!/usr/bin/env python3
"""Every sound the board has or wants, auditioned at the gains the board actually plays them.

    python3 ui/board_v2/sfx_lab/generate_sound_bench.py
    python3 ui/board_v2/sfx_lab/generate_sound_bench.py --open

WHY THIS IS A GENERATOR AND NOT A PAGE. The bench was a hand-built HTML file for a while and it
rotted the moment a clip was added: the audio is inlined, so the file is build output with every
sound baked into it twice over. Reading the clips off disk means the page cannot disagree with
what is actually in the tree, which is the only property worth having here.

THE COVERAGE IS THE POINT. Four categories, every slot listed whether it has a sound or not --
three tithe resources, fourteen duty actions, twenty-four buildings. A list of what exists tells
you nothing; a list of what is missing is a plan.

WHERE THE LISTS COME FROM. duty_text.json for the actions and configs/buildings.json for the
buildings, which is what the engine itself loads -- not tools/ui_debug/building_catalog.json,
which holds the same 24 but is a derived view for a debug renderer.

THE RECORD GATES EVERY CLIP, by the same rule as every picture on this board: a file with no
attribution entry is left out and NAMED rather than drawn silently. It is also where the levels
come from, so this script needs no audio tooling at all -- see probe().
"""
import argparse
import base64
import json
import pathlib
import re
import webbrowser

ROOT = pathlib.Path(__file__).resolve().parents[3]
BOARD = ROOT / "ui" / "board_v2"
SFX = BOARD / "sfx"
LAB = BOARD / "sfx_lab"
OUT = LAB / "generated" / "sound_bench.html"
MIME = {".ogg": "audio/ogg", ".mp3": "audio/mpeg", ".wav": "audio/wav", ".flac": "audio/flac"}

# THE GAINS ARE THE BOARD'S, read from the template rather than typed here -- the page is where
# they live, and a second copy would be the one that went stale.
def board_gains() -> dict:
    page = (BOARD / "action_board" / "action_board.html.tmpl").read_text(encoding="utf-8")
    m = re.search(r"var SFX_GAIN = \{([^}]*)\}", page)
    if not m:
        return {"hover": 0.12, "select": 0.5, "confirm": 0.7}
    return {k: float(v) for k, v in re.findall(r"(\w+)\s*:\s*([\d.]+)", m.group(1))}


def ogg_facts(path: pathlib.Path) -> dict:
    """Channels, sample rate and length, read straight out of the Ogg pages.

    NO ffprobe, AND THAT IS THE POINT. The first version of this shelled out to ffprobe for every
    clip, which worked here and died on the machine it was written for: ffmpeg is on the Linux VM
    behind the file bridge and is NOT on the Mac's PATH. A lab page is not worth a build
    dependency, and everything needed is in the first and last page of the file.

    The identification header gives channels and rate; the last page's granule position is the
    sample count, so duration is one division. Anything unparseable returns what it knows and the
    page simply shows less.
    """
    import struct
    out = {"ms": 0, "sr": 0, "ch": 1}
    try:
        raw = path.read_bytes()
        i = raw.find(b"\x01vorbis")
        if i >= 0:
            ch, rate = struct.unpack_from("<BI", raw, i + 11)
            out["ch"], out["sr"] = ch, rate
        j = raw.rfind(b"OggS")
        if j >= 0 and out["sr"]:
            granule = struct.unpack_from("<q", raw, j + 6)[0]
            out["ms"] = round(granule * 1000 / out["sr"])
    except Exception:
        pass
    return out


def probe(path: pathlib.Path, entry: dict) -> dict:
    """What the page shows about one clip: its shape from the file, its level from the record.

    THE LEVEL IS NOT MEASURED HERE. attribution.json already carries it -- `measured` holds the
    length and the peak, written when the clip was cut and checked -- and measuring it again would
    be a second answer to a question the record already owns. It is also the half that genuinely
    needs an audio tool, so taking it from the record is what keeps this script dependency-free.
    """
    facts = ogg_facts(path)
    m = re.search(r"(\d+)\s*ms", entry.get("measured", "") or "")
    if facts["ms"] == 0 and m:
        facts["ms"] = int(m.group(1))
    pk = re.search(r"peak\s*([-\d.]+)\s*dB", entry.get("measured", "") or "")
    facts.update(peak=pk.group(1) if pk else None, mean=None,
                 bytes=path.stat().st_size,
                 src="data:%s;base64,%s" % (MIME.get(path.suffix.lower(), "audio/ogg"),
                                            base64.b64encode(path.read_bytes()).decode("ascii")))
    return facts


def newest_version(folder: pathlib.Path, stem: str):
    """The clip a slot resolves to: `<stem>_sfx_vNN.ogg`, highest NN wins, None if there is none.

    THIS CODE USED TO BE THE STRING `_sfx_v01.ogg`, written out in three places. The tree's rule
    everywhere else is that versions count up and nothing is overwritten -- a file whose sha256
    is on the provenance record cannot be replaced in place without the record describing bytes
    that are gone -- and `bundled_controls()` picks a control by highest version for exactly that
    reason. Sound was the one corner that had never caught up, so filing `ordination_actionA_sfx
    _v02.ogg` produced a file nobody read and a slot that still drew the old take. Found by
    filing one, which is the only way it could have been found.

    A LONE MODULE-LEVEL FUNCTION BECAUSE A CLOSURE CANNOT BE TESTED. The first version of this
    sat inside main() where it could see `rec`, which made it unreachable from a test and so
    unguarded against going back to a literal. Resolving a name and reading a record are two
    jobs; this is the one worth asserting about.
    """
    best = (0, None)
    for p in folder.glob("%s_sfx_v*.ogg" % stem):
        m = re.match(re.escape(stem) + r"_sfx_v(\d+)$", p.stem)
        if m and int(m.group(1)) > best[0]:
            best = (int(m.group(1)), p)
    return best[1]


def duty_actions() -> list:
    d = json.loads((BOARD / "duty_text.json").read_text(encoding="utf-8"))["duties"]
    out = []
    for duty, v in d.items():
        acts = [(slot, v[slot]["name"]) for slot in ("actionA", "actionB")
                if isinstance(v.get(slot), dict)]
        out.append({"key": duty, "name": duty.replace("_", " ").title(), "actions": acts})
    return out


def buildings() -> list:
    # THE ENGINE'S OWN CONFIG, not tools/ui_debug/building_catalog.json. That file holds the same
    # 24 and agrees exactly, but it is a derived view for a debug renderer; this is what
    # pilgrim.model.config actually loads, so it cannot fall behind the game.
    cfg = ROOT / "configs" / "buildings.json"
    if not cfg.is_file():
        raise SystemExit("no %s -- the bench reads the engine's building list from there" % cfg)
    cat = json.loads(cfg.read_text(encoding="utf-8"))["catalogue"]
    return [{"key": e["id"], "name": e["name"], "level": int(e["level"])} for e in cat]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--open", action="store_true", help="open the page when it is built")
    args = ap.parse_args()

    rec = json.loads((BOARD / "attribution.json").read_text(encoding="utf-8")).get("files", {})
    notes: list = []

    def clip(rel: str, label: str):
        p = SFX / rel
        if not p.is_file():
            return None
        key = "sfx/" + rel
        if key not in rec:
            notes.append("%s has no attribution entry, left out" % key)
            return None
        e = rec[key]
        c = probe(p, e)
        c.update(label=label, file=rel,
                 note=(e.get("role") or "")[:170],
                 licence=e.get("licence", "?"))
        return c

    def newest(folder: str, stem: str):
        p = newest_version(SFX / folder, stem)
        return None if p is None else clip("%s/%s" % (folder, p.name), p.stem)

    gains = board_gains()
    sets = [
        {"id": "v1", "name": "Kenney interface sounds", "chosen": True,
         "note": "cut from one CC0 montage, levelled against each other, never normalised",
         "slots": [("hover", clip("tile.ogg", "tile.ogg"), gains.get("hover", .12)),
                   ("select", clip("tile.ogg", "tile.ogg -- the same clip, louder"), gains.get("select", .5)),
                   ("confirm", clip("confirm.ogg", "confirm.ogg"), gains.get("confirm", .7))]},
    ]
    tithe = [{"name": n, "clip": newest("tithe", k)}
             for k, n in (("wheat", "Wheat"), ("stone", "Stone"), ("silver", "Silver"))]
    duties = []
    for d in duty_actions():
        acts = []
        for slot, name in d["actions"]:
            acts.append({"name": name,
                         "clip": newest("duty_actions", "%s_%s" % (d["key"], slot))})
        duties.append({"name": d["name"], "actions": acts})
    builds = [dict(b, clip=newest("buildings", b["key"])) for b in buildings()]

    tmpl = (LAB / "sound_bench.html.tmpl").read_text(encoding="utf-8")
    page = tmpl.replace("__DATA__", json.dumps(
        {"sets": sets, "tithe": tithe, "duties": duties, "buildings": builds}))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding="utf-8")

    have = lambda xs: sum(1 for x in xs if x.get("clip"))
    print("  wrote %s  (%d KB)" % (OUT, len(page.encode()) // 1024))
    print("  tithe     %d of %d" % (have(tithe), len(tithe)))
    print("  actions   %d of %d" % (sum(1 for d in duties for a in d["actions"] if a["clip"]),
                                    sum(len(d["actions"]) for d in duties)))
    print("  buildings %d of %d" % (have(builds), len(builds)))
    for n in notes:
        print("  NOTE:", n)
    if args.open:
        webbrowser.open(OUT.as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
