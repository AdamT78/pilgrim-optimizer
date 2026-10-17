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
OUT_AMBIENT = LAB / "generated" / "ambient_bench.html"
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
    out = {"ms": 0, "sr": 0, "ch": 1, "samples": 0}
    try:
        raw = path.read_bytes()
        i = raw.find(b"\x01vorbis")
        if i >= 0:
            ch, rate = struct.unpack_from("<BI", raw, i + 11)
            out["ch"], out["sr"] = ch, rate
        j = raw.rfind(b"OggS")
        if j >= 0 and out["sr"]:
            granule = struct.unpack_from("<q", raw, j + 6)[0]
            out["samples"] = granule
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
    # THE PLAYBACK TRIM COMES FROM THE RECORD, NOT FROM THE AUDIO. sfx_levels.py measures
    # loudness and writes `gainDb`; this script still touches no decoder. A clip without the
    # field is drawn at 0 dB rather than guessed at, which is how a newly filed clip announces
    # that nobody has measured it yet.
    facts.update(peak=pk.group(1) if pk else None, mean=None,
                 gainDb=entry.get("gainDb"),
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


# THE BED'S DUTY ACTION IS RESOLVED, NOT DECLARED. A bed is named for the action it plays
# under -- `silversmith_sfx_v01.ogg` -- and duty_text.json already owns the mapping from that
# name to `clerical_actionB`. A `duty` field on the record would be a second copy of a fact the
# game already states, and the second copy is the one that goes stale.
def duty_action_folders() -> dict:
    """{"taxation_actionA": ("taxation", "actionA", "Taxation")} -- the folder a bed lives in.

    THIS REPLACED A PREFIX MATCH ON THE FILENAME. A flat `sfx/ambient/` resolved a bed to its
    action by dropping trailing words off the stem until one matched a duty action's name, so
    `allocation_wind` found Allocation and `donate_building` had to be matched longest-first so
    it was not read as a layer of some `donate`. That carried two facts in one string and held
    up for two tracks per action.

    IT STOPS WORKING AT FOUR. A stem wants a name that says what it is -- wheat, coins, barn
    creaks -- and those collide across actions as soon as two duties both involve wheat, which
    Produce and Taxation already do. So the folder owns which action and the filename owns
    which track, and neither repeats the other.

    The folder name is the duty key and the slot joined by an underscore, which is the same
    string the action's own cue is named with: `sfx/ambient/taxation_actionA/` beside
    `sfx/duty_actions/taxation_actionA_sfx_v01.ogg`. Derived here rather than written down,
    unlike `slotFolders` in attribution.json, because unlike that one it can be.
    """
    out = {}
    for d in duty_actions():
        for slot, name in d["actions"]:
            out["%s_%s" % (d["key"], slot)] = (d["key"], slot, name)
    return out


def ambient(rec: dict, notes: list) -> tuple:
    """Every bed in sfx/ambient/<duty>_<slot>/, with the cue of the action it belongs to.

    DISCOVERED LIKE misc/, COUNTED LIKE THE DUTY ACTIONS. The folders are the list -- nothing
    declares which actions get a bed -- but the denominator is the duty-action list, because
    "2 of 14 have a bed" is a plan and "2 beds exist" is not.

    A FOLDER THAT NAMES NO DUTY ACTION IS AN ERROR, NOT A BED WITHOUT A HOME. Under the old
    prefix match an unrecognised name quietly produced a bed with `duty: null` that played and
    belonged to nothing. A folder is deliberate enough that a typo in one should be reported.
    """
    root = SFX / "ambient"
    folders = duty_action_folders()
    beds, used = [], set()
    if not root.is_dir():
        return beds, used
    stray = sorted(p.name for p in root.iterdir() if p.is_file())
    if stray:
        notes.append("sfx/ambient/ holds %d loose file(s) -- a bed belongs in a duty-action "
                     "folder: %s" % (len(stray), ", ".join(stray)))
    for sub in sorted(p for p in root.iterdir() if p.is_dir()):
        hit = folders.get(sub.name)
        if hit is None:
            notes.append("sfx/ambient/%s/ names no duty action, so its beds are left out"
                         % sub.name)
            continue
        for stem in sorted({re.sub(r"_sfx_v\d+$", "", p.stem) for p in sub.glob("*.ogg")}):
            p = newest_version(sub, stem)
            if p is None:
                continue
            rel = "%s/%s" % (sub.name, p.name)
            key = "sfx/ambient/" + rel
            if key not in rec:
                notes.append("%s has no attribution entry, left out" % key)
                continue
            e = rec[key]
            facts = ogg_facts(p)
            m = e.get("measured", "") or ""
            num = lambda pat: (float(re.search(pat, m).group(1))
                               if re.search(pat, m) else None)
            used.add((hit[0], hit[1]))
            beds.append({
                # A DOM-SAFE ID, and it has to carry the folder now: two actions may both hold
                # a track called wheat, and the checkbox is addressed by element id.
                "id": re.sub(r"[^a-z0-9]+", "_", ("%s_%s" % (sub.name, p.stem)).lower()),
                "file": rel, "name": (e.get("title") or stem).split(" -- ")[0],
                # `action` IS THE FOLDER AND ALWAYS EXISTS; `cue` IS A CLIP AND OFTEN DOES NOT.
                # Four duty actions have beds and no cue filed, so `cue` is null for them --
                # which made it the wrong thing to group by, and did exactly that once.
                "duty": hit[2], "action": sub.name, "cue": "%s_%s" % (hit[0], hit[1]),
                "ms": facts["ms"], "sr": facts["sr"], "ch": facts["ch"],
                "seconds": round(facts["samples"] / facts["sr"], 6) if facts["sr"] else 0,
                "bytes": p.stat().st_size,
                "integrated": num(r"integrated\s*(-?[\d.]+)\s*LUFS"),
                "tp": num(r"true peak\s*(-?[\d.]+)\s*dBTP"),
                "gainDb": e.get("gainDb"),
                # ABSENT MEANS LOOPING, which is what every bed filed so far does. A record
                # only has to say `loop: false`, and then the bench comes up with that box
                # unticked instead of needing it re-ticked after every rebuild.
                "loop": e.get("loop", True),
                "src": base64.b64encode(p.read_bytes()).decode("ascii"),
            })
            if facts["samples"] == 0:
                notes.append("%s: no granule position, so its loop cannot be pinned" % key)
    return beds, used


def ambient_groups(doc: dict, beds: list, notes: list) -> dict:
    """The per-action second level, read out of attribution.json's `ambientGroups`.

    TWO LEVELS, AND THE SPLIT IS THE POINT. A bed's own `gainDb` is its balance against the
    other beds of its action; an action's `groupDb` is where that whole action sits against the
    other actions. Folding the second into the first gives the same sound once and then throws
    the structure away -- there is no action level left to revisit, only N numbers that happened
    to move together. Kept apart, the two jobs stay separate.

    THIS SCRIPT STILL TOUCHES NO DECODER, which is why `summedTruePeakDbtp` is read rather than
    rendered here: sfx_lab/sfx_levels.py owns the decoding and writes that figure, and
    `summedAtTrims` fingerprints the trims it was taken at so a stale pair can be caught.

    A folder with beds and no group entry gets a zero and a note rather than being left out --
    the beds are real and must still play.
    """
    # THE WHOLE DOCUMENT, NOT ITS `files` BLOCK. Everything else here works off the per-file
    # records and `rec` is that dict; a group level is not a property of a file and lives at
    # the top of attribution.json beside the other notes. Passing `rec` in by habit silently
    # gave every action a null measurement and a zero, which is why this takes `doc`.
    said = doc.get("ambientGroups") or {}
    out = {}
    for b in beds:
        act = b["action"]
        if act in out:
            continue
        g = said.get(act)
        if g is None:
            notes.append("%s has beds and no ambientGroups entry, so its group level is 0.0"
                         % act)
            g = {}
        out[act] = {"groupDb": float(g.get("groupDb") or 0.0),
                    "duty": b["duty"],
                    "tracks": sum(1 for x in beds if x["action"] == act),
                    "summedTruePeakDbtp": g.get("summedTruePeakDbtp"),
                    # THE OTHER MEASUREMENT OF THE SAME RENDER, and the one a transition is
                    # heard by. Peak answers whether an action can clip; loudness answers
                    # whether crossfading into it will step. They rank this tree differently.
                    # Same fingerprint, because it is the same render at the same trims.
                    "summedLoudnessLufs": g.get("summedLoudnessLufs"),
                    "summedAtTrims": g.get("summedAtTrims")}
        if g and g.get("tracks") not in (None, out[act]["tracks"]):
            notes.append("%s: ambientGroups says %s tracks, the folder holds %d -- rerun "
                         "sfx_levels.py --groups --write" % (act, g.get("tracks"),
                                                             out[act]["tracks"]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--open", action="store_true", help="open the page when it is built")
    args = ap.parse_args()

    doc = json.loads((BOARD / "attribution.json").read_text(encoding="utf-8"))
    rec = doc.get("files", {})
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
    # THE GENERAL CUES ARE A SET AND NOT THREE FILES, which is why this is a list of sets rather
    # than a flat list of slots. A set is a complete answer to "what does the interface sound
    # like" and the slots inside one were levelled against each other; comparing set 1's confirm
    # with set 2's select is not a comparison anyone wants to make.
    #
    # SET 2 HAS NO HOVER AND THAT IS SHOWN, not hidden. It is drawn as a gap, the same as a duty
    # action with no clip, because a set missing a slot is an incomplete answer and the page
    # should say so -- the alternative is a set that looks finished and goes quiet on hover.
    sets = [
        {"id": "v1", "name": "Kenney interface sounds", "chosen": True,
         "note": "cut from one CC0 montage, levelled against each other, never normalised",
         "slots": [("hover", clip("tile.ogg", "tile.ogg"), gains.get("hover", .12)),
                   ("select", clip("tile.ogg", "tile.ogg -- the same clip, louder"), gains.get("select", .5)),
                   ("confirm", clip("confirm.ogg", "confirm.ogg"), gains.get("confirm", .7))]},
        {"id": "v2", "name": "ElevenLabs set", "chosen": False,
         "note": "generated, not cut; no hover, and both cues run 2 s against the Kenney set's "
                 "70 ms -- a different idea of an interface, not a longer version of this one",
         # RESOLVED, NOT SPELLED OUT. Writing "general/set2_select_sfx_v01.ogg" here was the
         # first version of this and the version guard refused it -- correctly, because a set's
         # slot is a slot like any other: file a v02 of this cue and a literal would go on
         # drawing v01 with nothing to show for it. Set 1 above names `tile.ogg` and
         # `confirm.ogg` directly because those predate the convention and carry no version at
         # all, which is a different thing from naming one and freezing it.
         "slots": [("hover", None, gains.get("hover", .12)),
                   ("select", newest("general", "set2_select"), gains.get("select", .5)),
                   ("confirm", newest("general", "set2_confirm"), gains.get("confirm", .7))]},
        {"id": "v3", "name": "Drum figure", "chosen": False,
         # THE SELECT IS THE CONFIRM'S OWN TAIL, which no other set does and which is the whole
         # idea rather than an economy. Both are cut to the same sample at 17.800 s of one
         # recording, so the select is literally the confirm's last 742 ms and the confirm adds
         # 477 ms of run-up in front of it. Selecting asks and confirming answers with the same
         # landing. It is also the risk: play them 1.6 s apart, as the board does, and a listener
         # hears the identical 742 ms twice.
         "note": "cut from one Pixabay drum track on its own beat grid; the select is the "
                 "confirm's last 742 ms, so the pair resolves onto the same landing. THE ONLY "
                 "COMPLETE SET BESIDES THE ONE IN USE -- its hover is a filtered tick, because "
                 "no window of this track is a hover until the kick is taken out of it",
         "slots": [("hover", newest("general", "set3_hover"), gains.get("hover", .12)),
                   ("select", newest("general", "set3_select"), gains.get("select", .5)),
                   ("confirm", newest("general", "set3_confirm"), gains.get("confirm", .7))]},
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

    # MISC IS DISCOVERED, NOT DECLARED, which is what separates it from every other section. The
    # tithe resources, the duty actions and the buildings all come from a list the game owns, so
    # the bench can say "2 of 3" and mean it. Nothing owns the misc list: a clip is here because
    # somebody kept it, and the only way to know what is here is to look.
    misc = []
    for stem in sorted({re.sub(r"_sfx_v\d+$", "", p.stem) for p in (SFX / "misc").glob("*.ogg")}):
        c = newest("misc", stem)
        if c:
            misc.append(c)

    # THE AMBIENT PAGE IS A SECOND OUTPUT, NOT A SECTION. A bed loops and a cue does not, so
    # the two need different players; and a bed is 500-750 KB against a cue's 10, so folding
    # them in would take the page everyone opens from 0.8 MB to several. One generator, because
    # the record gate, the version resolver and the Ogg reader are worth having once.
    beds, used = ambient(rec, notes)
    cues = {}
    for b in beds:
        if not b["cue"] or b["cue"] in cues:
            continue
        cp = newest_version(SFX / "duty_actions", b["cue"])
        ck = None if cp is None else "sfx/duty_actions/" + cp.name
        if cp is None or ck not in rec:
            notes.append("%s has a bed but its own cue is not filed, so the bed has nothing "
                         "to be set against" % b["cue"])
            b["cue"] = None
            continue
        cues[b["cue"]] = {
            "name": b["duty"] or b["cue"],
            "gainDb": rec[ck].get("gainDb") or 0.0,
            # THE SELECT GAIN, because that is the slot a duty-action cue plays in on the
            # board, and it is read from the page rather than typed here for the same reason
            # the bench's other gains are.
            "role": gains.get("select", 0.5),
            "src": base64.b64encode((BOARD / ck).read_bytes()).decode("ascii"),
        }
    slots = sum(len(d["actions"]) for d in duty_actions())
    missing = ["%s (%s)" % (name, d["name"]) for d in duty_actions()
               for slot, name in d["actions"]
               if (d["key"], slot) not in used]
    groups = ambient_groups(doc, beds, notes)
    atmpl = (LAB / "ambient_bench.html.tmpl").read_text(encoding="utf-8")
    OUT_AMBIENT.parent.mkdir(parents=True, exist_ok=True)
    OUT_AMBIENT.write_text(atmpl.replace("__DATA__", json.dumps(
        {"beds": beds, "cues": cues, "have": len(used), "slots": slots,
         "layers": len(beds), "missing": missing, "groups": groups})), encoding="utf-8")

    tmpl = (LAB / "sound_bench.html.tmpl").read_text(encoding="utf-8")
    page = tmpl.replace("__DATA__", json.dumps(
        {"sets": sets, "tithe": tithe, "duties": duties, "buildings": builds,
         "misc": misc, "targetLufs": -24.0}))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding="utf-8")

    have = lambda xs: sum(1 for x in xs if x.get("clip"))
    print("  wrote %s  (%d KB)" % (OUT, len(page.encode()) // 1024))
    print("  tithe     %d of %d" % (have(tithe), len(tithe)))
    print("  actions   %d of %d" % (sum(1 for d in duties for a in d["actions"] if a["clip"]),
                                    sum(len(d["actions"]) for d in duties)))
    print("  buildings %d of %d" % (have(builds), len(builds)))
    # NO "n of m" HERE: misc has no denominator, so a count is the only honest line.
    print("  misc      %d kept, unassigned" % len(misc))
    print("  wrote %s  (%d KB)" % (OUT_AMBIENT, OUT_AMBIENT.stat().st_size // 1024))
    print("  ambient   %d of %d duty actions have a bed, in %d file%s"
          % (len(used), slots, len(beds), "" if len(beds) == 1 else "s"))
    drawn = [c for c in ([s for st in sets for _, s, _ in st["slots"]]
                         + [t["clip"] for t in tithe]
                         + [a["clip"] for d in duties for a in d["actions"]]
                         + [b["clip"] for b in builds] + misc) if c]
    unmeasured = [c["file"] for c in drawn if c.get("gainDb") is None]
    print("  levelled  %d of %d drawn clips carry a gainDb" % (len(drawn) - len(unmeasured),
                                                               len(drawn)))
    for f in unmeasured:
        print("  NOTE: %s has no gainDb -- run sfx_lab/sfx_levels.py" % f)
    for n in notes:
        print("  NOTE:", n)
    if args.open:
        webbrowser.open(OUT.as_uri())
        webbrowser.open(OUT_AMBIENT.as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
