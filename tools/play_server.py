"""A thin local process holding one loaded scenario, so the play view can be looked at live.

Standard library only. The repo declares no dependencies at all -- `pyproject.toml` has
`dependencies = []` -- so bringing in a framework to serve three read-only routes would be the
first one, and `http.server` is enough for a page nobody can press anything on.

    GET /              the play view, rendered from the state now held
    GET /state.json    the payload the adapter was handed, verbatim
    GET /actions.json  the legal actions, structured, with an id each and a token for the state

NOTHING IS APPLIED. This PR is a walking skeleton: the engine is live, the page is drawn from it,
and no route changes anything. `/actions.json` exists to prove the engine really is answering and
to settle the shape before the next PR filters over it.

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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pilgrim.io.scenarios import load_scenario  # noqa: E402
from pilgrim.io.view import view_payload  # noqa: E402
from pilgrim.model.actions import action_id  # noqa: E402
from pilgrim.rules.transition import legal_actions  # noqa: E402
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


class PlayServer(ThreadingHTTPServer):
    """Holds the one loaded position every route answers from."""

    daemon_threads = True

    def __init__(self, address: tuple[str, int], scenario_path: Path) -> None:
        super().__init__(address, PlayHandler)
        scenario = load_scenario(str(scenario_path))
        self.state = scenario.state
        self.config = scenario.config
        self.payload = view_payload(self.state, self.config)

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
            self._send(200, "application/json", json.dumps(self.server.payload, indent=1))
        elif route == "/actions.json":
            document = actions_document(self.server.state, self.server.config, self.server.payload)
            self._send(200, "application/json", json.dumps(document, indent=1))
        else:
            self._send(404, "text/plain; charset=utf-8", f"no route {route}\n")

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
    document = actions_document(server.state, server.config, server.payload)
    print(f"serving {args.scenario} on http://{args.host}:{args.port}/")
    print(f"state token {document['state_token']}; {document['count']} legal actions")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
