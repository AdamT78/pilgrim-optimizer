"""Render the third-party notices from `attribution.json`.

    python3 gen_credits.py            # write both notices
    python3 gen_credits.py --check    # fail if either is stale

Two outputs, one source. `THIRD-PARTY-NOTICES.md` is the record kept with the assets;
`credits-third-party-icons.html` is the fragment that ships inside the game's credits screen.
Generating both means the shipped credit cannot drift from the files it credits -- which is the
failure that actually happens, because a credits screen is written once and the asset tree keeps
moving.

CC BY wants five things: the title, the creator, the source, the licence with a link, and a
statement of what was changed. A register naming only the creator and the licence -- which is what
this tree had -- satisfies neither version of the licence, so each entry carries all five.
"""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
DATA = json.loads((HERE / "attribution.json").read_text())
MD = HERE / "THIRD-PARTY-NOTICES.md"
HTML = HERE / "credits-third-party-icons.html"


def _shipped(states=("present",)):
    """Files that carry an attribution obligation into the finished game.

    Only `present` by default. Crediting an `awaited` file would put a line in the shipped credits
    for artwork the build does not contain -- a claim to have used something you have not -- and
    the moment the file lands the entry appears here on its own. `held` files can never qualify,
    and project-owned art has no third party to credit.
    """
    out = []
    for path, a in DATA["files"].items():
        lic = DATA["licences"][a["licence"]]
        if a["state"] not in states or not lic["attributionRequired"]:
            continue
        out.append((path, a, lic))
    return sorted(out, key=lambda r: (r[1]["collection"] or "", r[1]["title"] or ""))


def _mods(a):
    return a.get("modifications") or DATA["modificationsDefault"]


def markdown():
    o = ["# Third-party notices",
         "",
         "Generated from `attribution.json` by `gen_credits.py` -- edit that, not this.",
         "",
         "Every entry below is an attribution-only licence: none is ShareAlike, so including these",
         "files does not oblige the game, the renderer or any unrelated artwork to be open-sourced.",
         "The obligation is to carry the credit, and it survives resizing, recolouring, conversion",
         "to PNG and Base64 embedding.",
         ""]
    for path, a, lic in _shipped():
        o += ["## %s" % (a["title"] or path),
              "",
              "- **File** `%s`" % path,
              "- **Creator** %s%s" % (a["creator"], " (%s)" % a["collection"] if a["collection"] else ""),
              "- **Source** %s" % (a["source"] or "not recorded"),
              "- **Licence** %s%s" % (lic["name"], " -- %s" % lic["url"] if lic["url"] else ""),
              "- **Changes** %s" % _mods(a),
              ""]
        if a.get("notes"):
            o += ["- **Note** %s" % a["notes"], ""]

    awaited = [(p, a) for p, a in DATA["files"].items() if a["state"] == "awaited"]
    held = [(p, a) for p, a in DATA["files"].items() if a["state"] == "held"]
    if awaited:
        o += ["## Cleared but not yet in the tree", "",
              "Licence established; the file itself is missing, so nothing renders it yet.", ""]
        for p, a in sorted(awaited):
            o += ["- `%s` -- %s by %s. %s" % (p, a["title"], a["creator"], a["awaitedBecause"])]
        o += [""]
    if held:
        o += ["## Held", "",
              "No licence on record. These are **not committed** and must not ship.", ""]
        for p, a in sorted(held):
            o += ["- `%s` -- %s" % (p, a["awaitedBecause"])]
        o += [""]
    return "\n".join(o)


def _esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def html():
    """One paragraph per collection, which is how a reader wants to see it -- grouping by licence
    keeps the two Font Awesome icons together instead of scattering four near-identical lines."""
    groups = {}
    for path, a, lic in _shipped():
        groups.setdefault((a["collection"], a["licence"]), []).append(a)

    o = ['<!-- Generated from assets/attribution.json by assets/gen_credits.py. Do not hand-edit. -->',
         '<section id="third-party-icon-credits">',
         '  <h2>Third-party icon credits</h2>']
    for (collection, licid), items in sorted(groups.items(), key=lambda kv: kv[0][0] or ""):
        lic = DATA["licences"][licid]
        # One creator for the group reads as one clause: "X and Y icons by Z", not "X icon by Z
        # and Y icon by Z". Several creators keep their own names.
        creators = {i["creator"] for i in items}
        titles = ["&ldquo;%s&rdquo;" % _esc(i["title"]) for i in items]
        if len(creators) == 1:
            names = "%s icon%s by %s" % (" and ".join(titles), "s" if len(items) > 1 else "",
                                         _esc(items[0]["creator"]))
        else:
            names = " and ".join("%s icon by %s" % (t, _esc(i["creator"]))
                                 for t, i in zip(titles, items))
        srcs = " and ".join('<a href="%s">%s</a>' % (i["source"], _esc(i["title"]))
                            for i in items if i["source"])
        lic_html = ('<a href="%s">%s</a>' % (lic["url"], _esc(lic["name"]))
                    if lic["url"] else _esc(lic["name"]))
        o += ['  <p>',
              '    %s,' % names,
              '    from %s, licensed under' % _esc(collection or "an unnamed collection"),
              '    %s.' % lic_html,
              '    %s.' % _esc(_mods(items[0])[0].upper() + _mods(items[0])[1:])]
        # A collection's front page is not a source for a particular icon. Linking it as one
        # looks like provenance and is not.
        if srcs and not all(i["source"] == DATA["licences"][licid]["url"] for i in items):
            o += ['    Source%s: %s.' % ("s" if len(items) > 1 else "", srcs)]
        o += ['  </p>']
    o += ['</section>', '']
    return "\n".join(o)


def main(check=False):
    want = {MD: markdown(), HTML: html()}
    if check:
        stale = [p.name for p, t in want.items() if not p.exists() or p.read_text() != t]
        if stale:
            print("stale, re-run gen_credits.py: %s" % ", ".join(stale))
            return 1
        print("notices are current")
        return 0
    for p, t in want.items():
        p.write_text(t)
        print("wrote %s" % p.name)
    return 0


if __name__ == "__main__":
    sys.exit(main(check="--check" in sys.argv))
