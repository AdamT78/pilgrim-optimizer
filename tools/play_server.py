"""A thin local process holding one loaded scenario, so the play view can be looked at live.

Standard library only. The repo declares no dependencies at all -- `pyproject.toml` has
`dependencies = []` -- so bringing in a framework to serve four routes would be the first one, and
`http.server` is enough for one local page playing one game.

    GET  /              the play view, rendered from the state now held
    GET  /state.json    the payload the adapter was handed, verbatim
    GET  /actions.json  the legal actions, structured, with an id each and a token for the state
    POST /action        apply one of them, by id, quoting the token it was read from

SETUP SOW ONLY. `/action` will apply whatever `legal_actions` offers, but the page only knows how
to ask for a setup sow; a normal turn is a later PR. The distinction is the page's, not this file's.

ONE GAME, IN MEMORY, NO PERSISTENCE. Restarting the process loses the position. That is a real
limitation and is left rather than papered over: saving would mean choosing a format and a place to
put it, and a local process for looking at a board does not need to have that argued out yet.

WHY THIS FILE IS NOT UNDER tools/ui_debug

It imports the engine, and nothing under `tools/ui_debug` may. That rule is what keeps the whole UI
testable against hand-written JSON with no engine in the room, and it is enforced by a test. This
is the seam: the engine on one side, a plain dict crossing it, the renderers on the other. Living
one directory up is how the seam stays visible rather than becoming a convention people remember.

Run from the repo root:

    python3 -m pilgrim.cli generate-setup --players 4 --seed 99 --output /tmp/scenario.json
    python3 tools/play_server.py /tmp/scenario.json
"""

from __future__ import annotations

import argparse
import dataclasses
import enum
import hashlib
import json
import socketserver
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pilgrim.io.event_text import format_event  # noqa: E402
from pilgrim.io.scenarios import load_scenario  # noqa: E402
from pilgrim.io.view import view_payload  # noqa: E402
from pilgrim.model.actions import (  # noqa: E402
    SetupSowAction,
    StartPlayerConfessionBoxAction,
    StartPlayerSelectionAction,
    action_id,
    action_summary,
)
from pilgrim.rules.transition import apply_action, legal_actions  # noqa: E402
from tools.ui_debug.render_play_view import render_play_view_from_payload  # noqa: E402

DEFAULT_PORT = 8765


def _plain(value: Any) -> Any:
    """JSON-able, and structured all the way down.

    Tuples become lists and enums become their values; nothing is flattened into a sentence. The
    summary string the CLI prints is deliberately absent: a client that parsed it to decide what an
    action does would be a rules parser wearing a disguise, and the fields it would be parsing back
    out are right here already.
    """
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, tuple | list):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    return value


def state_token(payload: dict) -> str:
    """A short name for exactly this position.

    The next PR needs to reject a submission quoting a list that has since gone stale, and the only
    honest way to do that is to name the state the list came from. It is a digest of the payload,
    so it changes when anything drawn changes and cannot be guessed from a turn number.
    """
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def actions_document(state: Any, config: Any, payload: dict) -> dict:
    """The legal actions as data, each with a stable readable id.

    The id is what a client quotes back, rather than a position in this list: a menu index means
    nothing once the list is regenerated, and `setup_sow:sow:0:1->2->3->4->5` means the same thing
    for as long as the action does.
    """
    actions = legal_actions(state, config)
    return {
        "state_token": state_token(payload),
        "count": len(actions),
        "actions": [
            {
                "action_id": action_id(action),
                "action_type": type(action).__name__,
                "fields": _plain(dataclasses.asdict(action)),
            }
            for action in actions
        ],
    }


class StaleStateToken(Exception):
    """The submission quoted a list that is no longer the one on offer."""


class UnknownAction(Exception):
    """The submission named an action that is not legal in the position now held."""


DECIDED_FIELDS = ("origin", "route", "selected_duty", "resolution")

# Fields answered by picking one stock out of the three. "Which stock grows" is the same question
# whichever field is asking it, so both are the same KIND of step and the page reveals the same
# affordance for either. A `None` here means this action has no such choice to make -- the field is
# optional precisely because most resolutions never ask -- so no step is emitted for it.
RESOURCE_CHOICE_FIELDS: tuple[str, ...] = ("tithe_resource", "taxation_step1_resource")

# Fields answered by pointing at a building where it stands on the round track. Same kind of step
# whichever field asks it, as with the stocks, and a `None` means this action does not ask -- a
# Construct that only lays road carries no building at all.
BUILDING_CHOICE_FIELDS: tuple[str, ...] = ("construct_building_id",)

# Fields that are only legal in certain COMBINATIONS, offered whole rather than one at a time.
# Setting one number and then the other would walk through states the engine never offered, and
# deciding which second number goes with a given first is a rule -- the engine's rule, which the
# page would then be keeping a second copy of. So the combinations that exist are the ones offered.
#
# Keyed off the resolution rather than off the values, the way `action_id` and `action_summary`
# already are, because zero is a legal amount and so cannot stand for "this action never asks".
#
# The verb travels with the row because these are not the same event: a paid alms hands stocks over
# and a Taxation bonus collects them, and a button reading "pay stone and silver" for the one that
# gives you both would be worse than no words at all.
COMBINATION_STEPS: tuple[tuple[str, str, tuple[tuple[str, str], ...]], ...] = (
    (
        "give_alms_paid",
        "pay",
        (("alms_payment_silver", "silver"), ("alms_payment_wheat", "wheat")),
    ),
)

# Combinations the engine states as a RUN OF NAMES rather than as a set of amounts: one name per
# unit, so ("stone", "stone") is two stone. Counted into amounts here and then offered exactly like
# the alms pair, because they are the same kind of question -- several stocks that are only legal
# together -- wearing a different spelling.
#
# Offered WHOLE, and this is the part that matters. The engine writes these runs canonically, in
# the order below, so ("silver", "stone") is spelled stone-first. Filtering them name by name would
# turn that spelling into a rule the player has to obey: press silver first and stone would go out,
# though a stone-and-silver bonus is perfectly legal. The mix is one answer and is asked for once.
COUNTED_COMBINATION_STEPS: tuple[tuple[str, str, str], ...] = (
    ("taxation", "take", "taxation_step2_resources"),
)

# The order amounts are spoken and encoded in. A display order only -- what may be taken is the
# engine's business, and every mix it offers is offered whichever way round this reads.
COMBINATION_STOCKS: tuple[str, ...] = ("stone", "silver", "wheat")

# WHAT EACH QUESTION IS ASKING, IN WORDS. One per construction site below, and each is written
# beside the step it belongs to.
#
# Here rather than in the page because what a question ASKS is a fact about the action. The page
# knows a step is answered by pointing at a space; it does not know, and must not have to be told,
# that this particular space is where acolytes are lifted from. That is why three of these are the
# same KIND -- a position -- and say three different things.
#
# The panel used to fall silent exactly when the question moved onto the board. A setup sow settles
# its origin by auto-advance, leaving a board with two faintly ringed spaces and no words anywhere
# saying that pointing at one is what is wanted. A player who does not already know the rules has
# nothing to go on.
#
# Sentences, not fragments, and no sentence is composed in JavaScript. The page reveals one of
# these whole, the way it reveals a summary or a key.
ORIGIN_PROMPT = "Point at the space to lift acolytes from."
ROUTE_PROMPT = "Point at the next space on the route."
DUTY_PROMPT = "Point at the duty to select."
RESOLUTION_PROMPT = "Choose what to do with that duty."
RESOURCE_PROMPT = "Choose a resource on your own board."
BUILDING_PROMPT = "Choose a building on the round track."
COMBINATION_PROMPT = "Choose one of these."
SEAT_PROMPT = "Point at the board of the player who begins the next round."

_NUMBER_WORDS: tuple[str, ...] = ("zero", "one", "two", "three", "four", "five", "six")


def _amounts_in_words(verb: str, amounts: list[tuple[str, int]]) -> str:
    """A combination said in words, because a row of numbers is not a thing to read off a button.

    One of something is said without the number: "take stone and silver" rather than "take 1 stone
    and 1 silver", which is how anyone would say it out loud and is the whole reason for spelling
    these out at all. Beyond the small words it falls back to digits rather than growing a table of
    English numerals no mix on this board reaches.
    """
    spoken = []
    for noun, amount in amounts:
        if not amount:
            continue
        if amount == 1:
            spoken.append(noun)
        elif amount < len(_NUMBER_WORDS):
            spoken.append(f"{_NUMBER_WORDS[amount]} {noun}")
        else:
            spoken.append(f"{amount} {noun}")
    return f"{verb} {' and '.join(spoken)}" if spoken else f"{verb} nothing"


def _combination_step(verb: str, amounts: list[tuple[str, int]]) -> dict:
    """One whole combination as a step: a scalar to match it by and a sentence to read."""
    return {
        "kind": "combination",
        # A step value is matched with `===` in the page, so it has to be one scalar. Spelled out
        # rather than hashed, so a transcript of a turn stays readable. Every noun is written even
        # at zero, so two mixes cannot collide by one of them leaving a stock out.
        "value": ",".join(f"{noun}={amount}" for noun, amount in amounts),
        "label": _amounts_in_words(verb, amounts),
        # The label already says what each option does, so the prompt only has to say that one of
        # them is what is wanted. Naming the resolution here would be a second description of the
        # thing the labels are describing, kept in step by hand.
        "prompt": COMBINATION_PROMPT,
    }


def _confession_in_words(action: Any) -> str:
    """The one sentence a player reads to make this choice, source and all.

    The source is spelled out rather than left to be inferred from the board, because the three of
    them cost different things and are owed to different people: your own is free, the market's is
    paid to the bank, and another player's is paid to that player.
    """
    if not action.use:
        return "decline the Confession Box"
    if action.source == "own_active":
        return "use your own Confession Box"
    if action.source == "market":
        return "hire the Confession Box from the market"
    return f"hire the Confession Box from {_SEAT_WORDS.get(action.source, action.source)}"


_SEAT_WORDS = {
    "player_one": "player one",
    "player_two": "player two",
    "player_three": "player three",
    "player_four": "player four",
}


def _presented(action: Any) -> list[tuple[dict, tuple[str, ...]]]:
    """Each further question this page can put about one action, with the fields it answers.

    Emitted after the resolution because they are answers to it: which stock a tithe takes is only
    a question once tithe is what is happening. Whether a step appears at all is therefore settled
    by the resolution, which is an earlier step, so every action in a group carries the same ones.

    The fields are kept BESIDE the step rather than inside it. They are this side's business -- how
    the refusal knows what has been asked -- and a page holding the name of a field would be a page
    that could come to depend on it, which is how the next one ends up being a special case.
    """
    if isinstance(action, StartPlayerConfessionBoxAction):
        # A `combination` and not a kind of its own, because the shape is the one the alms pair and
        # the taxation mix already have: several fields that only go together one way, offered whole
        # as a labelled option. Splitting `use` from `source` would put a question to a player who
        # declined about where they were not going to hire it from.
        #
        # The turn panel, deliberately. The three places a box can be reached from -- your own
        # board, the market on the map, another player's board -- are three different surfaces, so
        # no one of them can hold the choice; putting it on the map would light the market copy and
        # quietly hide that using your own is even an option.
        return [
            (
                {
                    "kind": "combination",
                    "value": "decline" if not action.use else f"use:{action.source}",
                    "label": _confession_in_words(action),
                    "prompt": COMBINATION_PROMPT,
                },
                ("use", "source"),
            )
        ]
    if isinstance(action, StartPlayerSelectionAction):
        # Answered by pointing at a player's board, so it is a `seat` the way a duty is a
        # `position` -- the kind says where the answer is given and nothing about what it means.
        # The value is the player, because that is what the engine is asking for and what the
        # boards are already stamped with; which chair that player sits in is the page's business
        # and is settled by the seating order there, not translated into a number here.
        return [
            (
                {
                    "kind": "seat",
                    "value": action.chosen_start_player.name.lower(),
                    "prompt": SEAT_PROMPT,
                },
                ("chosen_start_player",),
            )
        ]
    presented: list[tuple[dict, tuple[str, ...]]] = []
    for name in RESOURCE_CHOICE_FIELDS:
        value = getattr(action, name, None)
        if value is not None:
            presented.append(
                ({"kind": "resource", "value": value, "prompt": RESOURCE_PROMPT}, (name,))
            )
    for name in BUILDING_CHOICE_FIELDS:
        value = getattr(action, name, None)
        if value is not None:
            presented.append(
                ({"kind": "building", "value": value, "prompt": BUILDING_PROMPT}, (name,))
            )
    for resolution, verb, fields in COMBINATION_STEPS:
        if action.resolution.value != resolution:
            continue
        amounts = [(noun, getattr(action, name)) for name, noun in fields]
        presented.append((_combination_step(verb, amounts), tuple(name for name, _noun in fields)))
    for resolution, verb, name in COUNTED_COMBINATION_STEPS:
        if action.resolution.value != resolution:
            continue
        taken = tuple(getattr(action, name, ()) or ())
        amounts = [(noun, taken.count(noun)) for noun in COMBINATION_STOCKS]
        presented.append((_combination_step(verb, amounts), (name,)))
    return presented


def _presented_steps(action: Any) -> list[dict]:
    return [step for step, _fields in _presented(action)]


def _covered_fields(action: Any) -> set[str]:
    """Which residue fields this action's steps actually answer.

    Read off the steps that were really emitted, so a field the page can ask about in principle but
    did not ask about here still belongs in the refusal.
    """
    return {name for _step, fields in _presented(action) for name in fields}


def _residue_fields(action: Any) -> tuple[str, ...]:
    """Everything an action carries that the page does not ask about by name.

    Read off the action in hand rather than off one type, because there is more than one kind of
    action now: a start-player selection carries one field and a full turn some forty, and the page
    presents a handful of the second and none of the first.
    """
    return tuple(
        field.name
        for field in dataclasses.fields(action)
        if field.name not in DECIDED_FIELDS and field.name != "action_type"
    )


def decision_steps(action: Any) -> list[dict]:
    """The questions this action is an answer to, in the order the page asks them.

    Origin, then the route one space at a time, then which duty was selected, then what to do with
    it, then whatever that resolution goes on to ask. A setup sow stops after the route because
    that is all it has.

    Each step says what KIND of thing it is, because they are not answered in the same place: a
    position is a space on the board, a resolution is beside the board, a stock is on the asking
    seat's own board, a seat is a whole board, a building is a hex on the round track, and a
    combination is a set of amounts that only go together one way. The page routes on the kind and
    never on what any particular step means.

    Route length is not fixed. It is however many acolytes were lifted, so it varies by origin and
    by turn, and nothing here or on the page may assume a number.
    """
    # A start-player selection is one question and nothing before it. There is no origin to lift
    # from and no duty to resolve: whoever holds the marker names a player, and that is the whole
    # of the action.
    if isinstance(action, (StartPlayerConfessionBoxAction, StartPlayerSelectionAction)):
        return _presented_steps(action)
    # Three positions and three questions. They are the same kind because they are answered the
    # same way -- by pointing at a space -- and they say different things because they are asking
    # about different things. The kind is for the page; the words are for the player.
    steps = [{"kind": "position", "value": action.origin, "prompt": ORIGIN_PROMPT}]
    steps += [
        {"kind": "position", "value": position, "prompt": ROUTE_PROMPT} for position in action.route
    ]
    if isinstance(action, SetupSowAction):
        return steps
    steps.append({"kind": "position", "value": action.selected_duty, "prompt": DUTY_PROMPT})
    steps.append(
        {"kind": "resolution", "value": action.resolution.value, "prompt": RESOLUTION_PROMPT}
    )
    steps += _presented_steps(action)
    return steps


def _unresolved_fields(members: list[Any]) -> list[str]:
    """Which fields the actions in one group still disagree about.

    `FullTurnAction` carries some forty optional fields and this page presents a handful of them,
    so answering everything asked can still leave several actions standing, alike in everything
    asked and different in something never asked. This names those differences rather than guessing
    between them: the list IS the backlog, worked out from the position in front of the player
    instead of from anyone's memory of what is unbuilt, and it shrinks as each field gets a way to
    be chosen.

    Presented fields are excluded because a step for them is part of the group key, so they cannot
    differ within a group. Excluded one group at a time, from the steps actually emitted, so a
    field goes unmentioned only where it was really asked.
    """
    covered = _covered_fields(members[0])
    return [
        name
        for name in _residue_fields(members[0])
        if name not in covered and len({getattr(member, name) for member in members}) > 1
    ]


def turn_candidates(state: Any, config: Any) -> list[dict]:
    """The moves on offer, grouped by the decisions the page can actually put to a player.

    One candidate per distinct answer to the four questions above, which is not one per legal
    action: several actions can share all four and differ only further down. Those arrive here as
    one candidate carrying the count and the disagreement, so the page can refuse it honestly
    instead of picking one of them on the player's behalf.

    The summary is the CLI's own, so the words somebody confirms are the words the tool would
    print for the same action, and there is no second description to keep in step with the first.
    """
    grouped: dict[tuple, list[Any]] = {}
    for action in legal_actions(state, config):
        # THE KEY IS THE STEP VALUES AND STAYS THE STEP VALUES. A step carries words to read as
        # well as a value to match, and the words must not get in here: two spellings of one
        # question would then be two candidates, and a player would be shown the same choice twice
        # because the sentence above it differed.
        key = tuple(
            tuple(step["value"]) if isinstance(step["value"], tuple) else step["value"]
            for step in decision_steps(action)
        )
        grouped.setdefault(key, []).append(action)

    candidates = []
    for members in grouped.values():
        unresolved = _unresolved_fields(members) if len(members) > 1 else []
        settled = not unresolved
        candidates.append(
            {
                "steps": decision_steps(members[0]),
                # Nothing to submit while the choice is incomplete, so there is no id to quote and
                # no summary to agree to. The page has to say so rather than send something.
                "action_id": action_id(members[0]) if settled else None,
                "summary": action_summary(members[0], config) if settled else None,
                "unresolved": unresolved,
                "variants": len(members),
            }
        )
    return candidates


class PlayServer(ThreadingHTTPServer):
    """Holds the one loaded position every route answers from, and the log of how it got there."""

    daemon_threads = True

    def __init__(self, address: tuple[str, int], scenario_path: Path) -> None:
        super().__init__(address, PlayHandler)
        scenario = load_scenario(str(scenario_path))
        self.state = scenario.state
        self.config = scenario.config
        self.log_lines: list[str] = []
        # Threaded, so two submissions can arrive at once even from one browser. Reading the legal
        # set and replacing the state have to be one step, or the loser of the race applies a move
        # chosen against a board the winner has already moved.
        self._applying = threading.Lock()
        self._refresh()

    def _refresh(self) -> None:
        """Re-read everything the page is drawn from, after the position has changed."""
        self.state_payload = view_payload(self.state, self.config)
        self.token = state_token(self.state_payload)
        self.payload = dict(
            self.state_payload,
            state_token=self.token,
            turn_candidates=turn_candidates(self.state, self.config),
            log=list(self.log_lines),
        )

    def apply(self, submitted_id: str, submitted_token: str) -> None:
        """Apply one action, named by id and vouched for by the token it was read from.

        The token is checked first and refused rather than worked around. A submission quoting a
        stale list was decided against a board that has since moved, and re-deriving what its author
        "must have meant" would be this process inventing a move on their behalf.

        The action is then LOOKED UP in the current legal set, never rebuilt from what was sent.
        Reconstructing one from client fields would make the client the author of moves, and the
        first illegal one would arrive as a crash somewhere far from here instead of a refusal.
        """
        with self._applying:
            self._apply_locked(submitted_id, submitted_token)

    def _apply_locked(self, submitted_id: str, submitted_token: str) -> None:
        if submitted_token != self.token:
            raise StaleStateToken(
                f"state token {submitted_token!r} is not the current {self.token!r}; "
                "the position moved after that list was read"
            )
        chosen = next(
            (
                action
                for action in legal_actions(self.state, self.config)
                if action_id(action) == submitted_id
            ),
            None,
        )
        if chosen is None:
            raise UnknownAction(f"no legal action with id {submitted_id!r} in this position")

        result = apply_action(self.state, chosen, self.config)
        self.state = result.state
        # None means the event is meant not to print, so it is dropped rather than shown blank.
        self.log_lines.extend(
            line
            for line in (format_event(event, self.config) for event in result.events)
            if line is not None
        )
        self._refresh()

    def server_bind(self) -> None:
        """Bind without asking the network what this machine is called.

        `HTTPServer.server_bind` resolves the bound host to a fully qualified name, and on a
        machine whose resolver will not answer for 127.0.0.1 that reverse lookup sits there until
        it times out -- thirty-five seconds here, before the first request is even possible. The
        name is only ever used to fill in a default Host header, so the literal we were given is
        both faster and more accurate than whatever the resolver would eventually have said.
        """
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]


class PlayHandler(BaseHTTPRequestHandler):
    server: PlayServer

    def do_GET(self) -> None:  # noqa: N802 -- BaseHTTPRequestHandler's own spelling
        route = self.path.split("?", 1)[0]
        if route == "/":
            page = render_play_view_from_payload(self.server.payload)
            self._send(200, "text/html; charset=utf-8", page)
        elif route == "/state.json":
            # The state as the engine describes it, without the token, the candidates or the log:
            # those are this process's bookkeeping, and a test comparing two positions should not
            # have to look past them to see whether anything moved.
            self._send(200, "application/json", json.dumps(self.server.state_payload, indent=1))
        elif route == "/actions.json":
            document = actions_document(
                self.server.state, self.server.config, self.server.state_payload
            )
            self._send(200, "application/json", json.dumps(document, indent=1))
        else:
            self._send(404, "text/plain; charset=utf-8", f"no route {route}\n")

    def do_POST(self) -> None:  # noqa: N802 -- BaseHTTPRequestHandler's own spelling
        route = self.path.split("?", 1)[0]
        if route != "/action":
            self._send(404, "text/plain; charset=utf-8", f"no route {route}\n")
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, TypeError):
            self._reject(400, "body must be JSON")
            return
        if not isinstance(body, dict):
            self._reject(400, "body must be a JSON object")
            return

        try:
            self.server.apply(str(body.get("action_id", "")), str(body.get("state_token", "")))
        except StaleStateToken as stale:
            # 409, not 400: the request was well formed and would have been fine a moment ago.
            self._reject(409, str(stale))
            return
        except UnknownAction as unknown:
            self._reject(422, str(unknown))
            return

        # The whole page, redrawn from the new state. The client swaps it in rather than patching
        # the board, so nothing it does can put a piece somewhere the engine did not.
        self._send(
            200,
            "text/html; charset=utf-8",
            render_play_view_from_payload(self.server.payload),
        )

    def _reject(self, status: int, reason: str) -> None:
        """Say what was wrong. A refusal that changed nothing should read like one."""
        self._send(status, "application/json", json.dumps({"error": reason, "applied": False}))

    def _send(self, status: int, content_type: str, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 -- the base class's name
        sys.stderr.write(f"{self.address_string()} {format % args}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "scenario", type=Path, help="Scenario JSON, from `pilgrim.cli generate-setup`."
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args(argv)

    server = PlayServer((args.host, args.port), args.scenario)
    document = actions_document(server.state, server.config, server.state_payload)
    print(f"serving {args.scenario} on http://{args.host}:{args.port}/")
    print(f"state token {document['state_token']}; {document['count']} legal actions")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
