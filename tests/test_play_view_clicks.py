"""Browser hit-testing guards for affordances the JS harness cannot see.

Each check uses `elementFromPoint` at the intended click centre plus a real mouse click, because
`element.click()` bypasses hit-testing and is exactly how these bugs shipped green.
"""

from __future__ import annotations

from dataclasses import replace
import threading
from pathlib import Path

import pytest

from tools.play_server import PlayServer

pytestmark = pytest.mark.slow

SCENARIOS = Path(__file__).resolve().parents[1] / "scenarios"
PLAYTEST_CLOISTERS = "cloisters_reach_2p.json"
PLAYTEST_CLOISTERS_LOOP = "cloisters_loop_2p.json"
PLAYTEST_KOGGE_AND_CLOISTERS = "kogge_and_cloisters_2p.json"


@pytest.fixture(scope="session")
def chromium_browser():
    sync_api = pytest.importorskip(
        "playwright.sync_api", reason="playwright is not installed"
    )
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as exc:
            detail = str(exc)
            if "Executable doesn't exist" in detail or "playwright install chromium" in detail:
                pytest.skip(
                    "Playwright Chromium is missing; run `python -m playwright install chromium`."
                )
            raise
        try:
            yield browser
        finally:
            browser.close()


@pytest.fixture
def page(chromium_browser):
    context = chromium_browser.new_context()
    page = context.new_page()
    try:
        yield page
    finally:
        context.close()


@pytest.fixture
def serve():
    running: list[tuple[PlayServer, threading.Thread]] = []

    def _open(scenario: Path | None = None) -> tuple[str, PlayServer]:
        server = PlayServer(("127.0.0.1", 0), scenario)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        running.append((server, thread))
        return f"http://127.0.0.1:{server.server_address[1]}", server

    try:
        yield _open
    finally:
        for server, thread in reversed(running):
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


def _candidate_with_step(server: PlayServer, kind: str, *, value: str | None = None) -> dict:
    for candidate in server.payload["turn_candidates"]:
        for step in candidate["steps"]:
            if step["kind"] != kind:
                continue
            if value is not None and step["value"] != value:
                continue
            return candidate
    raise AssertionError(f"no candidate asks kind={kind!r} value={value!r}")


def _centre(page, handle) -> tuple[float, float]:
    data = page.evaluate(
        """target => {
            const box = target.getBoundingClientRect();
            return { x: box.left + box.width / 2, y: box.top + box.height / 2,
                     width: box.width, height: box.height };
        }""",
        handle,
    )
    assert data["width"] > 0 and data["height"] > 0, "target has no clickable centre"
    return float(data["x"]), float(data["y"])


def _is_hit_target(page, handle, x: float, y: float) -> bool:
    return bool(
        page.evaluate(
            """({target, x, y}) => {
                const hit = document.elementFromPoint(x, y);
                return Boolean(target && hit && (hit === target || target.contains(hit)));
            }""",
            {"target": handle, "x": x, "y": y},
        )
    )


def _click_handle_centre(page, handle, *, require_hit: bool = True) -> None:
    x, y = _centre(page, handle)
    if require_hit:
        assert _is_hit_target(page, handle, x, y), "elementFromPoint at target centre missed target"
    page.mouse.click(x, y)


def _next_offered_from_dom(
    page,
    *,
    preferred_resolution: str | None = None,
    preferred_control: str | None = None,
):
    if preferred_resolution:
        preferred = page.query_selector(
            f'[data-resolution-key="{preferred_resolution}"][data-turn-offered="true"]'
        )
        if preferred is not None:
            return preferred
    if preferred_control:
        preferred = page.query_selector(
            f'[data-turn-control="{preferred_control}"][data-turn-control-enabled="true"]'
        )
        if preferred is not None:
            return preferred

    selectors = (
        '[data-board-position-index][data-turn-start-candidate="true"]',
        '[data-board-position-index][data-turn-skip-candidate="true"]',
        '[data-board-position-index][data-turn-duty-candidate="true"]',
        '[data-arrow][data-turn-offered="true"]',
        '[data-resolution-key][data-turn-offered="true"]',
        '[data-combination-key][data-turn-offered="true"]',
        '[data-resource-choice-key][data-turn-offered="true"]',
        '[data-seat-choice-key][data-turn-offered="true"]',
        '[data-building-choice-key][data-turn-offered="true"]',
        '[data-turn-control="action"][data-turn-control-enabled="true"]',
        '[data-turn-control="tithe"][data-turn-control-enabled="true"]',
        '[data-turn-control="confirm"][data-turn-control-enabled="true"]',
    )
    for selector in selectors:
        handle = page.query_selector(selector)
        if handle is not None:
            return handle
    return None


def _walk_live_dom_until(
    page,
    condition,
    *,
    target: str,
    preferred_resolution: str | None = None,
    preferred_control: str | None = None,
    max_clicks: int = 80,
) -> None:
    for _ in range(max_clicks):
        if condition():
            return
        offered = _next_offered_from_dom(
            page,
            preferred_resolution=preferred_resolution,
            preferred_control=preferred_control,
        )
        if offered is None:
            page.wait_for_timeout(50)
            offered = _next_offered_from_dom(
                page,
                preferred_resolution=preferred_resolution,
                preferred_control=preferred_control,
            )
        assert offered is not None, f"no live offered target while walking to {target}"
        _click_handle_centre(page, offered, require_hit=True)
        page.wait_for_timeout(20)
    raise AssertionError(f"did not reach {target} within {max_clicks} clicks")


def _walk_until_skip_step_by_preferring_edges(page, *, target: str, max_clicks: int = 80) -> None:
    """Advance toward a Cloisters skip prompt without taking duty/resolution branches first."""
    for _ in range(max_clicks):
        if page.locator('[data-board-position-index][data-turn-skip-candidate="true"]').count() > 0:
            return
        origin = page.query_selector('[data-board-position-index][data-turn-start-candidate="true"]')
        if origin is not None:
            _click_handle_centre(page, origin, require_hit=True)
            page.wait_for_timeout(20)
            continue
        edge = page.query_selector('[data-arrow][data-turn-offered="true"]')
        if edge is not None:
            _click_handle_centre(page, edge, require_hit=True)
            page.wait_for_timeout(20)
            continue
        raise AssertionError(f"no origin/edge target while walking to {target}")
    raise AssertionError(f"did not reach {target} within {max_clicks} clicks")


def _topmost_descriptor_at(page, x: float, y: float) -> str | None:
    return page.evaluate(
        """({x, y}) => {
            const hit = document.elementFromPoint(x, y);
            if (!hit) { return null; }
            if (hit.matches('[data-token="role"]')) {
                return `role-token:${hit.getAttribute('data-role')}:${hit.getAttribute('data-role-slot')}`;
            }
            if (hit.matches('[data-role-circle]')) {
                return `role-circle:${hit.getAttribute('data-role-circle')}`;
            }
            if (hit.matches('[data-token="abbey"]')) {
                return 'abbey-token';
            }
            if (hit.matches('[data-token="village"]')) {
                return 'village-token';
            }
            return hit.tagName.toLowerCase();
        }""",
        {"x": x, "y": y},
    )


def _visible_role_count(page, role_id: str) -> int:
    return int(
        page.evaluate(
            """role => Array.from(document.querySelectorAll(
                `[data-active-seat="true"] [data-token="role"][data-role="${role}"]`
            )).filter(token => token.getAttribute('opacity') !== '0').length""",
            role_id,
        )
    )


def _confirm_enabled(page) -> bool:
    return (
        page.get_attribute('[data-turn-control="confirm"]', "data-turn-control-enabled")
        == "true"
    )


def _ordination_counts(value: str) -> tuple[int, int]:
    if value == "none":
        return (0, 0)
    counts = {"ordain": 0, "mission": 0}
    for part in value.split(","):
        name, amount = part.split("=", 1)
        counts[name] = int(amount)
    return (counts["ordain"], counts["mission"])


def _visible_active_token_count(page, token_name: str) -> int:
    return int(
        page.evaluate(
            """tokenName => Array.from(document.querySelectorAll(
                `[data-active-seat="true"] [data-token="${tokenName}"]`
            )).filter(token => token.getAttribute('opacity') !== '0').length""",
            token_name,
        )
    )


def _lit_city_slots_for_player(page, player_id: str) -> int:
    return page.locator(
        f'[data-city-column-player="{player_id}"][data-city-cube][opacity="1"]'
    ).count()


def _turn_state_snapshot(page) -> dict[str, object]:
    """A compact view of what the page currently offers and enables in the turn UI."""
    return {
        "origins": page.locator('[data-board-position-index][data-turn-start-candidate="true"]').count(),
        "skips": page.locator('[data-board-position-index][data-turn-skip-candidate="true"]').count(),
        "duties": page.locator('[data-board-position-index][data-turn-duty-candidate="true"]').count(),
        "arrows": page.locator('[data-arrow][data-turn-offered="true"]').count(),
        "resolution_keys": page.locator('[data-resolution-key][data-turn-offered="true"]').all_inner_texts(),
        "combination_keys": page.locator('[data-combination-key][data-turn-offered="true"]').all_inner_texts(),
        "resource_keys": page.locator('[data-resource-choice-key][data-turn-offered="true"]').count(),
        "seat_keys": page.locator('[data-seat-choice-key][data-turn-offered="true"]').all_inner_texts(),
        "building_keys": page.locator('[data-building-choice-key][data-turn-offered="true"]').all_inner_texts(),
        "action_enabled": page.get_attribute(
            '[data-turn-control="action"]', "data-turn-control-enabled"
        ),
        "tithe_enabled": page.get_attribute(
            '[data-turn-control="tithe"]', "data-turn-control-enabled"
        ),
        "confirm_enabled": page.get_attribute(
            '[data-turn-control="confirm"]', "data-turn-control-enabled"
        ),
        "prompts": page.locator('[data-turn-prompt][data-turn-offered="true"]').all_inner_texts(),
    }


def _offered_combination_values(page) -> list[str]:
    return [
        str(value)
        for value in page.eval_on_selector_all(
            '[data-combination-key][data-turn-offered="true"]',
            "nodes => nodes.map(node => node.getAttribute('data-combination-key'))",
        )
        if value is not None
    ]


def _assert_allocation_vestry_overlap_behaviour(page, base_url: str, server: PlayServer) -> None:
    _candidate_with_step(server, "arrangement", value="abbey=-1,vestry=+1")

    def arrangement_is_live() -> bool:
        return page.locator('[data-arrangement-choice="true"]').count() == 1

    page.goto(base_url, wait_until="networkidle")
    _walk_live_dom_until(
        page,
        arrangement_is_live,
        target="allocation arrangement step",
        preferred_resolution="allocation",
    )

    vestry_token = page.query_selector(
        '[data-active-seat="true"] [data-token="role"][data-role="vestry"]'
        '[data-role-slot="single"][opacity="1"]'
    )
    vestry_circle = page.query_selector('[data-active-seat="true"] [data-role-circle="vestry"]')
    abbey_token = page.query_selector('[data-active-seat="true"] [data-token="abbey"][opacity="1"]')
    assert vestry_token is not None and vestry_circle is not None and abbey_token is not None

    assert _is_hit_target(page, abbey_token, *_centre(page, abbey_token))
    assert _is_hit_target(page, vestry_token, *_centre(page, vestry_token))

    vx, vy = _centre(page, vestry_circle)
    assert _topmost_descriptor_at(page, vx, vy) == "role-token:vestry:single", (
        "topmost live at Vestry centre should be token while nothing is held"
    )

    _click_handle_centre(page, vestry_token, require_hit=True)
    assert _visible_role_count(page, "vestry") == 0, "Vestry token did not lift from the circle"

    page.goto(base_url, wait_until="networkidle")
    _walk_live_dom_until(
        page,
        arrangement_is_live,
        target="allocation arrangement step",
        preferred_resolution="allocation",
    )

    abbey_token = page.query_selector('[data-active-seat="true"] [data-token="abbey"][opacity="1"]')
    vestry_circle = page.query_selector('[data-active-seat="true"] [data-role-circle="vestry"]')
    assert abbey_token is not None and vestry_circle is not None
    _click_handle_centre(page, abbey_token, require_hit=True)

    vx, vy = _centre(page, vestry_circle)
    assert _topmost_descriptor_at(page, vx, vy) == "role-circle:vestry", (
        "topmost live at Vestry centre while holding should be the circle"
    )
    _click_handle_centre(page, vestry_circle, require_hit=True)
    assert _visible_role_count(page, "vestry") == 2
    assert _confirm_enabled(page), "confirm did not light for abbey=-1,vestry=+1"


def test_setup_rows_three_and_four_compute_display_none_at_two_players(page, serve) -> None:
    """Catches the `[hidden]` row bug where author display kept seats 3/4 visible."""
    base_url, _server = serve(None)
    page.goto(base_url, wait_until="networkidle")
    page.select_option("#player_count", "2")

    assert page.eval_on_selector(
        '[data-seat-row="3"]', "row => getComputedStyle(row).display"
    ) == "none"
    assert page.eval_on_selector(
        '[data-seat-row="4"]', "row => getComputedStyle(row).display"
    ) == "none"


def test_setup_test_position_dropdown_selects_and_starts_that_game(page, serve) -> None:
    base_url, _server = serve(None)
    page.goto(base_url, wait_until="networkidle")

    dropdown = page.locator("#test_position")
    assert dropdown.count() == 1, "setup page did not render test position dropdown"
    option_values = page.eval_on_selector_all(
        "#test_position option",
        "nodes => nodes.map(node => ({ value: node.value, text: node.textContent || '' }))",
    )
    assert any(option["value"] == "" for option in option_values), "fresh-game blank option is missing"
    assert any(option["value"] == PLAYTEST_CLOISTERS for option in option_values), (
        "playtest scenario is missing from dropdown"
    )
    assert any(option["value"] == PLAYTEST_CLOISTERS_LOOP for option in option_values), (
        "loop playtest scenario is missing from dropdown"
    )
    assert any(option["value"] == PLAYTEST_KOGGE_AND_CLOISTERS for option in option_values), (
        "kogge+cloisters playtest scenario is missing from dropdown"
    )

    page.select_option("#test_position", PLAYTEST_CLOISTERS)
    assert page.get_attribute("#player_count", "disabled") is not None
    assert page.get_attribute("#seed", "disabled") is not None
    assert page.eval_on_selector(
        '[data-seat-row="3"]', "row => getComputedStyle(row).display"
    ) == "none"

    submit = page.query_selector('button[type="submit"]')
    assert submit is not None, "setup form submit button missing"
    _click_handle_centre(page, submit, require_hit=True)
    page.wait_for_load_state("networkidle")
    page.wait_for_selector('[data-component="play-log"]')
    assert page.locator('[data-component="play-log"]').count() == 1, (
        "submitting selected test position did not open the game board"
    )
    state = page.request.get(f"{base_url}/state.json").json()
    assert len(state["state"]["players"]) == 2
    assert state["state"]["players"][0]["piety"] == 4
    assert state["state"]["players"][0]["resources"] == {"stone": 9, "silver": 9, "wheat": 9}
    _walk_until_skip_step_by_preferring_edges(
        page,
        target="cloisters skip step from selected test position",
    )
    skip_target = page.query_selector('[data-board-position-index][data-turn-skip-candidate="true"]')
    assert skip_target is not None, "loaded test position never offered a Cloisters skip target"
    _click_handle_centre(page, skip_target, require_hit=True)
    page.wait_for_timeout(20)
    assert page.locator('[data-board-position-index][data-turn-skip-candidate="true"]').count() == 0


@pytest.mark.parametrize(
    "position_name",
    [PLAYTEST_CLOISTERS, PLAYTEST_CLOISTERS_LOOP, PLAYTEST_KOGGE_AND_CLOISTERS],
)
def test_setup_test_position_dropdown_each_playtest_position_starts(page, serve, position_name: str) -> None:
    base_url, _server = serve(None)
    page.goto(base_url, wait_until="networkidle")
    page.select_option("#test_position", position_name)
    submit = page.query_selector('button[type="submit"]')
    assert submit is not None, "setup form submit button missing"
    _click_handle_centre(page, submit, require_hit=True)
    page.wait_for_load_state("networkidle")
    page.wait_for_selector('[data-component="play-log"]')
    assert page.locator('[data-component="play-log"]').count() == 1, (
        f"test position {position_name} did not open the game board"
    )


def test_cloisters_loop_opens_on_lift_question_and_city_click_enables_reset_with_five_in_hand(
    page,
    serve,
) -> None:
    base_url, _server = serve(SCENARIOS / "playtest" / PLAYTEST_CLOISTERS_LOOP)
    page.goto(base_url, wait_until="networkidle")

    opening = _turn_state_snapshot(page)
    assert opening["origins"] == 2, opening
    prompts = [str(prompt).lower() for prompt in opening["prompts"]]
    assert any("choose a space to lift acolytes from." in prompt for prompt in prompts), prompts
    assert all("follow an arrow." not in prompt for prompt in prompts), prompts

    city_origin = page.query_selector('[data-board-position-index="0"][data-turn-start-candidate="true"]')
    assert city_origin is not None, "city should be offered as a start-candidate origin"
    _click_handle_centre(page, city_origin, require_hit=True)
    page.wait_for_timeout(20)

    counters = [
        str(value)
        for value in page.eval_on_selector_all(
            '[data-turn-counter][data-turn-offered="true"]',
            "nodes => nodes.map(node => node.getAttribute('data-turn-counter'))",
        )
        if value is not None
    ]
    assert "5" in counters, counters
    assert (
        page.get_attribute('[data-turn-control="reset"]', "data-turn-control-enabled") == "true"
    ), "reset should enable once city is clicked"


def test_cloisters_loop_city_revisit_can_be_clicked_as_skip_target(page, serve) -> None:
    base_url, server = serve(SCENARIOS / "playtest" / PLAYTEST_CLOISTERS_LOOP)
    candidate = next(
        (
            offered
            for offered in server.payload["turn_candidates"]
            if offered.get("action_id") is not None
            and any(step["kind"] == "origin" and int(step["value"]) == 0 for step in offered["steps"])
            and any(step["kind"] == "skip" and int(step["value"]) == 0 for step in offered["steps"])
        ),
        None,
    )
    assert candidate is not None, "loop playtest offered no city-origin candidate skipping city"

    edge_values = [str(step["value"]) for step in candidate["steps"] if step["kind"] == "edge"]
    assert any(value.endswith("->city") for value in edge_values), (
        "chosen city-origin candidate route never returns to city"
    )

    page.goto(base_url, wait_until="networkidle")
    city_origin = page.query_selector('[data-board-position-index="0"][data-turn-start-candidate="true"]')
    assert city_origin is not None, "city should be offered as a start origin"
    _click_handle_centre(page, city_origin, require_hit=True)
    page.wait_for_timeout(20)

    for edge_value in edge_values:
        edge = page.query_selector(f'[data-arrow="{edge_value}"][data-turn-offered="true"]')
        if edge is not None:
            _click_handle_centre(page, edge, require_hit=True)
            page.wait_for_timeout(20)

    city_skip = page.query_selector('[data-board-position-index="0"][data-turn-skip-candidate="true"]')
    assert city_skip is not None, "city revisit was not offered as a skip target"
    _click_handle_centre(page, city_skip, require_hit=True)
    page.wait_for_timeout(20)

    assert page.locator('[data-board-position-index][data-turn-skip-candidate="true"]').count() == 0, (
        "city skip click did not settle the skip question"
    )
    assert page.locator('[data-board-position-index][data-turn-duty-candidate="true"]').count() > 0, (
        "duty question did not follow city skip selection"
    )


def test_cloisters_reach_play_view_does_not_draw_city_east_reversal_arrow(page, serve) -> None:
    base_url, _server = serve(SCENARIOS / "playtest" / PLAYTEST_CLOISTERS)
    page.goto(base_url, wait_until="networkidle")

    assert page.locator('[data-arrow="city->east"]').count() == 0


def test_kogge_and_cloisters_play_view_city_east_reversal_is_present_hit_testable_and_clickable(
    page,
    serve,
) -> None:
    base_url, _server = serve(SCENARIOS / "playtest" / PLAYTEST_KOGGE_AND_CLOISTERS)
    page.goto(base_url, wait_until="networkidle")

    city_east = page.query_selector('[data-arrow="city->east"]')
    assert city_east is not None, "city->east reversal arrow was not drawn"
    x, y = _centre(page, city_east)
    assert _is_hit_target(page, city_east, x, y), "city->east centre did not hit-test to itself"

    city_origin = page.query_selector('[data-board-position-index="0"][data-turn-start-candidate="true"]')
    assert city_origin is not None, "city origin was not offered"
    _click_handle_centre(page, city_origin, require_hit=True)
    page.wait_for_timeout(20)

    offered_city_east = page.query_selector('[data-arrow="city->east"][data-turn-offered="true"]')
    assert offered_city_east is not None, "city->east was not offered after lifting from city"
    before = _turn_state_snapshot(page)
    _click_handle_centre(page, offered_city_east, require_hit=True)
    page.wait_for_timeout(20)

    after = _turn_state_snapshot(page)
    assert after != before, "city->east click did not change the turn state"


def test_kogge_and_cloisters_playtest_city_route_can_enter_city_against_arrows_then_skip_and_pick_duty(
    page,
    serve,
) -> None:
    base_url, server = serve(SCENARIOS / "playtest" / PLAYTEST_KOGGE_AND_CLOISTERS)
    against_flow_edges = {"north->city", "south->city"}
    candidate = next(
        (
            offered
            for offered in server.payload["turn_candidates"]
            if offered.get("action_id") is not None
            and any(step["kind"] == "origin" and int(step["value"]) == 0 for step in offered["steps"])
            and any(step["kind"] == "skip" for step in offered["steps"])
            and any(
                step["kind"] == "edge"
                and str(step["value"]) in against_flow_edges
                for step in offered["steps"]
            )
        ),
        None,
    )
    assert candidate is not None, "playtest offered no settled city-origin candidate using north/south->city"
    edge_values = [str(step["value"]) for step in candidate["steps"] if step["kind"] == "edge"]
    against_indexes = [index for index, value in enumerate(edge_values) if value in against_flow_edges]
    assert against_indexes, "chosen candidate did not include an against-flow City-entry edge"
    assert min(against_indexes) > 0, "against-flow City-entry edge was not reached from the City route"
    assert max(against_indexes) < len(edge_values) - 1, "route did not continue after entering City"
    skip_value = next(
        int(step["value"]) for step in candidate["steps"] if step["kind"] == "skip"
    )
    duty_value = next(
        int(step["value"]) for step in candidate["steps"] if step["kind"] == "duty"
    )

    page.goto(base_url, wait_until="networkidle")
    city_origin = page.query_selector('[data-board-position-index="0"][data-turn-start-candidate="true"]')
    assert city_origin is not None, "city origin was not offered"
    _click_handle_centre(page, city_origin, require_hit=True)
    page.wait_for_timeout(20)

    for edge_value in edge_values:
        edge = page.query_selector(f'[data-arrow="{edge_value}"][data-turn-offered="true"]')
        assert edge is not None, f"edge {edge_value} was not offered while replaying settled route"
        _click_handle_centre(page, edge, require_hit=True)
        page.wait_for_timeout(20)

    skip_target = page.query_selector(
        f'[data-board-position-index="{skip_value}"][data-turn-skip-candidate="true"]'
    )
    assert skip_target is not None, "skip target from settled candidate was not offered"
    _click_handle_centre(page, skip_target, require_hit=True)
    page.wait_for_timeout(20)

    duty_target = page.query_selector(
        f'[data-board-position-index="{duty_value}"][data-turn-duty-candidate="true"]'
    )
    assert duty_target is not None, "duty target from settled candidate was not offered"
    _click_handle_centre(page, duty_target, require_hit=True)
    page.wait_for_timeout(20)

    assert page.locator('[data-board-position-index][data-turn-duty-candidate="true"]').count() == 0, (
        "duty choice did not settle after clicking the duty target"
    )
    after = _turn_state_snapshot(page)
    assert (
        after["action_enabled"] == "true"
        or after["tithe_enabled"] == "true"
        or len(after["resolution_keys"]) > 0
        or _confirm_enabled(page)
    ), "turn did not advance beyond the duty choice after route and skip"


def test_plain_route_prefix_keeps_extending_cloisters_routes_live_and_clickable(page, serve) -> None:
    """A plain route completion must not eliminate Cloisters routes that extend the same prefix."""
    base_url, server = serve(SCENARIOS / "playtest" / PLAYTEST_CLOISTERS)
    candidates = server.payload["turn_candidates"]

    def origin_of(candidate: dict) -> int | None:
        for step in candidate["steps"]:
            if step["kind"] == "origin":
                return int(step["value"])
        return None

    def edges_of(candidate: dict) -> list[str]:
        return [str(step["value"]) for step in candidate["steps"] if step["kind"] == "edge"]

    chosen: tuple[int, list[str], list[str]] | None = None
    for plain in candidates:
        plain_edges = edges_of(plain)
        if not plain_edges or any(step["kind"] == "skip" for step in plain["steps"]):
            continue
        plain_origin = origin_of(plain)
        if plain_origin is None:
            continue
        for cloisters in candidates:
            if not any(step["kind"] == "skip" for step in cloisters["steps"]):
                continue
            cloisters_origin = origin_of(cloisters)
            cloisters_edges = edges_of(cloisters)
            if cloisters_origin != plain_origin:
                continue
            if (
                len(cloisters_edges) == len(plain_edges) + 1
                and cloisters_edges[: len(plain_edges)] == plain_edges
            ):
                chosen = (plain_origin, plain_edges, cloisters_edges)
                break
        if chosen is not None:
            break
    assert chosen is not None, "fixture offered no plain/Cloisters prefix pair to exercise"
    origin, plain_edges, cloisters_edges = chosen

    page.goto(base_url, wait_until="networkidle")
    origin_target = page.query_selector(
        f'[data-board-position-index="{origin}"][data-turn-start-candidate="true"]'
    )
    assert origin_target is not None, f"origin {origin} is not offered"
    _click_handle_centre(page, origin_target, require_hit=True)

    for edge in plain_edges:
        edge_target = page.query_selector(f'[data-arrow="{edge}"][data-turn-offered="true"]')
        if edge_target is not None:
            _click_handle_centre(page, edge_target, require_hit=True)
            page.wait_for_timeout(20)

    assert page.locator('[data-board-position-index][data-turn-duty-candidate="true"]').count() > 0, (
        "plain route completion did not make any duty selectable"
    )
    extending_edge = cloisters_edges[-1]
    extending_target = page.query_selector(
        f'[data-arrow="{extending_edge}"][data-turn-offered="true"]'
    )
    assert extending_target is not None, (
        "Cloisters extension edge disappeared when the plain route finished"
    )
    _click_handle_centre(page, extending_target, require_hit=True)
    page.wait_for_timeout(20)
    assert page.locator('[data-board-position-index][data-turn-skip-candidate="true"]').count() > 0, (
        "continuing the Cloisters extension edge did not reach the skip question"
    )


def test_a_wheel_origin_space_and_then_route_arrow_really_receive_clicks(page, serve) -> None:
    """Catches wheel hit-testing regressions where origin/edge affordances look live but are dead."""
    base_url, _server = serve(SCENARIOS / "tithe_counter_choice_001.json")
    page.goto(base_url, wait_until="networkidle")

    offered_origins = page.locator('[data-board-position-index][data-turn-start-candidate="true"]')
    assert offered_origins.count() >= 2, "turn did not open unresolved on origin"
    origin = offered_origins.first.element_handle()
    assert origin is not None
    _click_handle_centre(page, origin, require_hit=True)

    offered_edges = page.locator('[data-arrow][data-turn-offered="true"]')
    before_edge_count = offered_edges.count()
    assert before_edge_count >= 1, "origin click did not reveal offered route arrows"
    counter_before = page.locator('[data-turn-counter][data-turn-offered="true"]').all_inner_texts()

    edge = offered_edges.first.element_handle()
    assert edge is not None
    _click_handle_centre(page, edge, require_hit=True)

    after_edge_count = page.locator('[data-arrow][data-turn-offered="true"]').count()
    counter_after = page.locator('[data-turn-counter][data-turn-offered="true"]').all_inner_texts()
    assert counter_after != counter_before or after_edge_count != before_edge_count, (
        "route-arrow click did not change the turn preview state"
    )


def test_kogge_axis_arrows_have_distinct_hit_targets_and_support_both_directions(page, serve) -> None:
    """Catches spoke-lane regressions: no overlap, keep-left signs, and still-clickable centres."""
    base_url, server = serve(SCENARIOS / "kogge_cloisters_own_own_skip_duty_001.json")
    candidate = next(
        (
            offered
            for offered in server.payload["turn_candidates"]
            if any(step["kind"] == "edge" and step["value"] == "city->east" for step in offered["steps"])
            and any(step["kind"] == "edge" and step["value"] == "east->city" for step in offered["steps"])
        ),
        None,
    )
    assert candidate is not None, "fixture offered no route using city->east and east->city"

    page.goto(base_url, wait_until="networkidle")
    city = page.query_selector('[data-board-position="city"]')
    assert city is not None
    city_box = city.bounding_box()
    assert city_box is not None
    city_center_y = float(city_box["y"] + city_box["height"] / 2.0)

    def arrow_box(name: str) -> dict:
        handle = page.query_selector(f'[data-arrow="{name}"]')
        assert handle is not None, f"missing rendered arrow {name}"
        box = handle.bounding_box()
        assert box is not None, f"missing bounding box for {name}"
        cx, cy = _centre(page, handle)
        return {
            "name": name,
            "handle": handle,
            "x": float(box["x"]),
            "y": float(box["y"]),
            "w": float(box["width"]),
            "h": float(box["height"]),
            "cx": float(cx),
            "cy": float(cy),
        }

    def assert_pair_geometry(lower_name: str, upper_name: str) -> tuple[dict, dict]:
        a = arrow_box(lower_name)
        b = arrow_box(upper_name)
        for arrow in (a, b):
            assert _is_hit_target(page, arrow["handle"], arrow["cx"], arrow["cy"]), (
                f"elementFromPoint missed {arrow['name']} at its own centre"
            )

        ax2, ay2 = a["x"] + a["w"], a["y"] + a["h"]
        bx2, by2 = b["x"] + b["w"], b["y"] + b["h"]
        overlap_x = min(ax2, bx2) - max(a["x"], b["x"])
        overlap_y = min(ay2, by2) - max(a["y"], b["y"])
        assert overlap_x <= 0 or overlap_y <= 0, (
            f"{a['name']} and {b['name']} bounding boxes overlapped"
        )

        upper, lower = (a, b) if a["cy"] <= b["cy"] else (b, a)
        clear = lower["y"] - (upper["y"] + upper["h"])
        assert clear >= 4.0, (
            f"{a['name']} and {b['name']} had only {clear:.2f}px vertical clearance"
        )
        midpoint_y = (a["cy"] + b["cy"]) / 2.0
        assert abs(midpoint_y - city_center_y) <= 1.0, (
            f"{a['name']} and {b['name']} were not symmetric about the spoke axis"
        )
        return a, b

    east_out, east_in = assert_pair_geometry("city->east", "east->city")
    west_out, west_in = assert_pair_geometry("city->west", "west->city")

    # Keep-left on horizontal spokes: eastbound arrows sit above axis, westbound below.
    assert east_out["cy"] < city_center_y, "city->east must sit above the east spoke axis"
    assert east_in["cy"] > city_center_y, "east->city must sit below the east spoke axis"
    assert west_out["cy"] > city_center_y, "city->west must sit below the west spoke axis"
    assert west_in["cy"] < city_center_y, "west->city must sit above the west spoke axis"

    first = page.query_selector('[data-arrow="city->east"][data-turn-offered="true"]')
    assert first is not None, "city->east was not offered on the opening Kogge step"
    _click_handle_centre(page, first, require_hit=True)
    page.wait_for_timeout(20)

    second = page.query_selector('[data-arrow="east->city"][data-turn-offered="true"]')
    assert second is not None, "route did not continue with east->city after city->east"
    _click_handle_centre(page, second, require_hit=True)
    page.wait_for_timeout(20)
    assert page.locator('[data-board-position-index][data-turn-duty-candidate="true"]').count() > 0, (
        "route using both east-axis directions did not advance to a duty choice"
    )


def test_kogge_city_start_outbound_arrow_click_advances_the_turn(page, serve) -> None:
    """Catches Kogge city-start regressions where city->east looked offered but stayed dead."""
    base_url, _server = serve(SCENARIOS / "kogge_hire_opponent_city_to_west_001.json")
    page.goto(base_url, wait_until="networkidle")

    city = page.query_selector('[data-board-position-index="0"][data-turn-start-candidate="true"]')
    assert city is not None, "city origin was not offered"
    _click_handle_centre(page, city, require_hit=True)
    page.wait_for_timeout(20)

    city_east = page.query_selector('[data-arrow="city->east"][data-turn-offered="true"]')
    assert city_east is not None, "city->east was not offered after lifting from city"
    before = _turn_state_snapshot(page)
    _click_handle_centre(page, city_east, require_hit=True)
    page.wait_for_timeout(20)

    after = _turn_state_snapshot(page)
    assert after != before, "clicking city->east did not change the turn state"
    assert (
        after["duties"] > 0
        or after["arrows"] > 0
        or after["action_enabled"] == "true"
        or after["tithe_enabled"] == "true"
    ), "clicking city->east did not advance to a later turn question"


def test_kogge_route_can_enter_city_against_arrows_from_ring_and_continue(page, serve) -> None:
    """Catches regressions where north->city looked offered but could not be walked onward."""
    base_url, server = serve(SCENARIOS / "kogge_active_city_to_east_001.json")
    board = server.config.board
    north_west = board.index_for_name("north_west")
    player = server.state.active_player
    player_state = server.state.player_state(player)
    server.state = server.state.with_player_state(
        player,
        replace(
            player_state,
            workforce=replace(
                player_state.workforce,
                mancala=(1, 0, 0, 0, 0, 0, 0, 0, 3),
            ),
        ),
    )
    server._refresh()

    page.goto(base_url, wait_until="networkidle")
    origin = page.query_selector(
        f'[data-board-position-index="{north_west}"][data-turn-start-candidate="true"]'
    )
    assert origin is not None, "north-west origin was not offered for the ring-start Kogge route"
    _click_handle_centre(page, origin, require_hit=True)
    page.wait_for_timeout(20)

    north_to_city = page.query_selector('[data-arrow="north->city"][data-turn-offered="true"]')
    assert north_to_city is not None, "north->city was not offered after reaching North"
    _click_handle_centre(page, north_to_city, require_hit=True)
    page.wait_for_timeout(20)

    city_to_east = page.query_selector('[data-arrow="city->east"][data-turn-offered="true"]')
    assert city_to_east is not None, "city->east was not offered after entering City from North"
    _click_handle_centre(page, city_to_east, require_hit=True)
    page.wait_for_timeout(20)

    assert page.locator('[data-board-position-index][data-turn-duty-candidate="true"]').count() > 0, (
        "route did not advance to duty selection after entering City against arrows"
    )


def test_a_cloisters_skip_target_receives_a_real_centre_click(page, serve) -> None:
    """Catches wheel skip-step regressions where the marked unsown-space target is not clickable."""
    base_url, _server = serve(SCENARIOS / "kogge_cloisters_own_own_skip_duty_001.json")
    page.goto(base_url, wait_until="networkidle")

    _walk_until_skip_step_by_preferring_edges(page, target="cloisters skip step")

    skip_target = page.query_selector('[data-board-position-index][data-turn-skip-candidate="true"]')
    assert skip_target is not None, "no offered skip target on wheel"
    x, y = _centre(page, skip_target)
    assert page.evaluate(
        """({target, x, y}) => {
            const hit = document.elementFromPoint(x, y);
            return hit === target || (hit && target.contains(hit));
        }""",
        {"target": skip_target, "x": x, "y": y},
    ), "skip target is not the top hit at its centre"
    _click_handle_centre(page, skip_target, require_hit=True)
    page.wait_for_timeout(20)
    assert page.locator('[data-board-position-index][data-turn-skip-candidate="true"]').count() == 0, (
        "skip click did not advance beyond the skip question"
    )


def test_an_offered_stock_pill_receives_the_click_on_the_asking_seat(page, serve) -> None:
    """Catches the stock-pill overlay bug where the glyph could swallow centre clicks."""
    base_url, _server = serve(SCENARIOS / "ordination_hire_infirmary_insufficient_wheat_001.json")
    page.goto(base_url, wait_until="networkidle")

    def resource_choice_is_live() -> bool:
        return (
            page.locator('[data-player-seat][data-resource-choice="true"]').count() == 1
            and page.locator('[data-resource-choice-key][data-turn-offered="true"]').count() > 0
        )

    _walk_live_dom_until(
        page,
        resource_choice_is_live,
        target="resource choice on asking seat",
    )

    asking_seat = page.query_selector('[data-player-seat][data-resource-choice="true"]')
    assert asking_seat is not None
    seat_number = asking_seat.get_attribute("data-player-seat")
    assert seat_number is not None

    stock_key = page.query_selector(
        f'[data-player-seat="{seat_number}"] [data-resource-choice-key][data-turn-offered="true"]'
    )
    assert stock_key is not None
    _click_handle_centre(page, stock_key, require_hit=True)
    assert page.locator(f'[data-player-seat="{seat_number}"][data-resource-choice="true"]').count() == 0


def test_ordination_tokens_are_mouse_reachable_and_light_city_then_confirm(page, serve) -> None:
    """Catches ordination regressions where Village/Abbey looked live but a real click missed them."""
    base_url, server = serve(SCENARIOS / "ordination_mill_active_three_steps_one_wheat_001.json")
    candidate = next(
        (
            c
            for c in server.payload["turn_candidates"]
            if any(step["kind"] == "ordination" for step in c["steps"])
            and (counts := _ordination_counts(
                next(step["value"] for step in c["steps"] if step["kind"] == "ordination")
            ))[0] >= 1
            and counts[1] >= 1
        ),
        None,
    )
    assert candidate is not None, "fixture had no ordination outcome with both ordain and mission"
    ordination_value = next(
        step["value"] for step in candidate["steps"] if step["kind"] == "ordination"
    )
    ordain_total, mission_total = _ordination_counts(ordination_value)

    def ordination_is_live() -> bool:
        return page.locator('[data-ordination-choice="true"]').count() == 1

    page.goto(base_url, wait_until="networkidle")
    _walk_live_dom_until(
        page,
        ordination_is_live,
        target="ordination step",
        preferred_resolution="ordination",
    )

    active_board = page.query_selector('[data-active-seat="true"]')
    assert active_board is not None
    active_player = active_board.get_attribute("data-player")
    assert active_player is not None

    village_before = _visible_active_token_count(page, "village")
    abbey_before = _visible_active_token_count(page, "abbey")
    city_before = _lit_city_slots_for_player(page, active_player)

    village_token = page.query_selector(
        '[data-active-seat="true"] [data-token="village"]'
        '[opacity="1"][data-ordination-can-ordain="true"]'
    )
    assert village_token is not None
    visibility = page.evaluate("node => getComputedStyle(node).visibility", village_token)
    pointer_events = page.evaluate("node => getComputedStyle(node).pointerEvents", village_token)
    assert visibility == "visible"
    assert pointer_events == "all"
    assert _is_hit_target(page, village_token, *_centre(page, village_token))

    _click_handle_centre(page, village_token, require_hit=True)
    page.wait_for_timeout(20)
    assert _visible_active_token_count(page, "village") == village_before - 1
    assert _visible_active_token_count(page, "abbey") == abbey_before + 1

    abbey_token = page.query_selector(
        '[data-active-seat="true"] [data-token="abbey"]'
        '[opacity="1"][data-ordination-can-mission="true"]'
    )
    assert abbey_token is not None
    visibility = page.evaluate("node => getComputedStyle(node).visibility", abbey_token)
    pointer_events = page.evaluate("node => getComputedStyle(node).pointerEvents", abbey_token)
    assert visibility == "visible"
    assert pointer_events == "all"
    assert _is_hit_target(page, abbey_token, *_centre(page, abbey_token))
    _click_handle_centre(page, abbey_token, require_hit=True)
    page.wait_for_timeout(20)
    assert _lit_city_slots_for_player(page, active_player) == city_before + 1

    for _ in range(max(0, ordain_total - 1)):
        next_village = page.query_selector(
            '[data-active-seat="true"] [data-token="village"]'
            '[opacity="1"][data-ordination-can-ordain="true"]'
        )
        assert next_village is not None, "expected another live village token for ordain count"
        _click_handle_centre(page, next_village, require_hit=True)
        page.wait_for_timeout(20)

    for _ in range(max(0, mission_total - 1)):
        next_abbey = page.query_selector(
            '[data-active-seat="true"] [data-token="abbey"]'
            '[opacity="1"][data-ordination-can-mission="true"]'
        )
        assert next_abbey is not None, "expected another live abbey token for mission count"
        _click_handle_centre(page, next_abbey, require_hit=True)
        page.wait_for_timeout(20)

    assert _confirm_enabled(page), f"confirm did not light for ordination outcome {ordination_value}"


@pytest.mark.parametrize(
    ("scenario_name", "resolution", "hire_key"),
    [
        ("allocation_hire_infirmary_market_001.json", "allocation", "infirmary:market:wheat"),
        ("ordination_hire_mill_market_three_steps_001.json", "ordination", "mill:market:wheat"),
    ],
)
def test_bonus_building_hire_options_are_mouse_reachable(
    page,
    serve,
    scenario_name: str,
    resolution: str,
    hire_key: str,
) -> None:
    base_url, _server = serve(SCENARIOS / scenario_name)

    def hire_step_is_live() -> bool:
        offered = set(_offered_combination_values(page))
        return "none" in offered and hire_key in offered

    for choice in ("none", hire_key):
        page.goto(base_url, wait_until="networkidle")
        _walk_live_dom_until(
            page,
            hire_step_is_live,
            target=f"hire step for {resolution}",
            preferred_resolution=resolution,
        )
        button = page.query_selector(
            f'[data-combination-key="{choice}"][data-turn-offered="true"]'
        )
        assert button is not None, f"expected offered hire option {choice!r}"
        _click_handle_centre(page, button, require_hit=True)
        page.wait_for_timeout(30)
        assert choice not in set(_offered_combination_values(page)), (
            "clicking a hire option did not advance past the hire step"
        )


def test_seat_choice_keys_are_reachable_for_all_four_seats_and_light_confirm(page, serve) -> None:
    """Catches seat-key regressions: fill-none edge hits and hidden keys swallowing clicks."""
    base_url, _server = serve(SCENARIOS / "play_view_reference_4p_001.json")
    offered_selector = '[data-seat-choice-key][data-turn-offered="true"]'

    def offered_seat_keys_are_present() -> bool:
        return page.locator(offered_selector).count() > 0

    for seat_index in range(4):
        page.goto(base_url, wait_until="networkidle")
        _walk_live_dom_until(
            page,
            offered_seat_keys_are_present,
            target="offered seat keys",
        )
        keys = page.query_selector_all(offered_selector)
        assert len(keys) == 4

        for key in keys:
            visibility = page.evaluate("node => getComputedStyle(node).visibility", key)
            pointer_events = page.evaluate("node => getComputedStyle(node).pointerEvents", key)
            assert visibility == "visible"
            assert pointer_events == "all"
            x, y = _centre(page, key)
            assert page.evaluate(
                """({target, x, y}) => {
                    const hit = document.elementFromPoint(x, y);
                    return hit === target;
                }""",
                {"target": key, "x": x, "y": y},
            ), "seat key is not the top hit at its own centre"

        target = page.query_selector_all(offered_selector)[seat_index]
        _click_handle_centre(page, target, require_hit=True)
        assert _confirm_enabled(page), "confirm did not light after clicking a seat key"


#
# No offered-key assertion here: in committed scenarios where only one building is legal, the
# building step is forced and the page answers it without asking. That auto-advance is by design.
#
def test_hidden_building_keys_keep_no_hit_area(page, serve) -> None:
    """Catches hidden-key regressions: in SVG, `pointer-events: all` still applies while hidden."""
    base_url, _server = serve(SCENARIOS / "construct_building_live_only_001.json")
    page.goto(base_url, wait_until="networkidle")

    assert page.locator('[data-building-choice-key]').count() == 4
    assert page.locator('[data-building-choice-key][data-turn-offered="true"]').count() == 0

    hidden_keys = page.query_selector_all('[data-building-choice-key][data-turn-offered="false"]')
    assert len(hidden_keys) == 4
    for hidden_key in hidden_keys:
        visibility = page.evaluate("key => getComputedStyle(key).visibility", hidden_key)
        pointer_events = page.evaluate("key => getComputedStyle(key).pointerEvents", hidden_key)
        assert visibility == "hidden"
        assert pointer_events == "none"

        x, y = _centre(page, hidden_key)
        assert not _is_hit_target(page, hidden_key, x, y)
        before = _turn_state_snapshot(page)
        page.mouse.click(x, y)
        page.wait_for_timeout(20)
        after = _turn_state_snapshot(page)
        assert after == before


def test_allocation_vestry_circle_switches_topmost_live_target_when_holding(page, serve) -> None:
    """Catches the Vestry overlap bug where a live token occluded the circle-place target."""
    base_url, server = serve(SCENARIOS / "allocation_chapter_house_second_acolyte_001.json")
    _assert_allocation_vestry_overlap_behaviour(page, base_url, server)


def test_allocation_overlap_guard_is_load_bearing(page, serve, monkeypatch) -> None:
    """Proves the overlap guard fails when lift/place flags regress to both-live-at-once."""
    from tools.ui_debug import render_play_view

    broken = (
        render_play_view._TURN_SCRIPT.replace(
            "var canLiftNow = !waitingToPlace && canLift;",
            "var canLiftNow = canLift;",
        ).replace(
            "var canPlaceNow = waitingToPlace && canPlace;",
            "var canPlaceNow = canPlace;",
        )
    )
    assert broken != render_play_view._TURN_SCRIPT
    monkeypatch.setattr(render_play_view, "_TURN_SCRIPT", broken)

    base_url, server = serve(SCENARIOS / "allocation_chapter_house_second_acolyte_001.json")
    with pytest.raises(
        AssertionError, match="topmost live at Vestry centre while holding should be the circle"
    ):
        _assert_allocation_vestry_overlap_behaviour(page, base_url, server)
