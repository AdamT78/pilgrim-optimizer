"""Browser hit-testing guards for affordances the JS harness cannot see.

Each check uses `elementFromPoint` at the intended click centre plus a real mouse click, because
`element.click()` bypasses hit-testing and is exactly how these bugs shipped green.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from tools.play_server import PlayServer

pytestmark = pytest.mark.slow

SCENARIOS = Path(__file__).resolve().parents[1] / "scenarios"


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


def _turn_state_snapshot(page) -> dict[str, object]:
    """A compact view of what the page currently offers and enables in the turn UI."""
    return {
        "origins": page.locator('[data-board-position-index][data-turn-start-candidate="true"]').count(),
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
