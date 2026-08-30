"""Browser hit-testing guards for affordances the JS harness cannot see.

Each check uses `elementFromPoint` at the intended click centre plus a real mouse click, because
`element.click()` bypasses hit-testing and is exactly how these bugs shipped green.
"""

from __future__ import annotations

import json
from dataclasses import replace
from io import BytesIO
import threading
from pathlib import Path

import pytest
from PIL import Image

from pilgrim.model.actions import EndTurnAction, action_id
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules.transition import apply_action, apply_turn_step, legal_actions, turn_steps
from tools import play_server
from tools.play_server import PlayServer

pytestmark = pytest.mark.slow

SCENARIOS = Path(__file__).resolve().parents[1] / "scenarios"
SCREENSHOTS = Path(__file__).resolve().parents[1] / "screenshots"
PLAYTEST_CLOISTERS = "cloisters_reach_2p.json"
PLAYTEST_CLOISTERS_LOOP = "cloisters_loop_2p.json"
PLAYTEST_KOGGE_AND_CLOISTERS = "kogge_and_cloisters_2p.json"
PLAYTEST_CONVERSIONS = "conversions_2p.json"
PLAYTEST_PULPIT = "pulpit_2p.json"
# 1280px is the narrowest width the page supports, so geometry guards must not inherit a
# Playwright default that can hide a wrap which appears in CI.
LAYOUT_VIEWPORT = {"width": 1280, "height": 720}


@pytest.fixture(scope="session")
def chromium_browser():
    sync_api = pytest.importorskip("playwright.sync_api", reason="playwright is not installed")
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
    context = chromium_browser.new_context(viewport=LAYOUT_VIEWPORT)
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


def _rendered_route_family_data(page) -> dict:
    """Read the server-written route-family data embedded in the served turn script."""
    return page.evaluate(
        r"""() => {
            const source = Array.from(document.scripts, script => script.textContent).find(
                script => script.includes('var CANDIDATES = ')
                    && script.includes('var FAMILIES = ')
            );
            if (!source) { throw new Error('rendered turn script was missing'); }
            const match = source.match(/var FAMILIES = ([\s\S]*?);\n  var AUTO_FAMILY_INDEXES/);
            if (!match) { throw new Error('rendered turn script payload was unreadable'); }
            return {families: JSON.parse(match[1])};
        }"""
    )


def test_rendered_route_family_mapping_agrees_with_server_and_candidates(page, serve) -> None:
    """The compact indexes the browser receives must retain the server's building mapping."""
    base_url, server = serve(SCENARIOS / "playtest" / PLAYTEST_KOGGE_AND_CLOISTERS)
    page.goto(base_url, wait_until="networkidle")

    rendered = _rendered_route_family_data(page)
    page_by_index = {
        family["i"]: family["building_id"] for family in rendered["families"]
    }
    declared_by_index = {
        family.i: family.building_id for family in play_server._ROUTE_FAMILIES
    }
    candidate_indexes = {
        index
        for candidate in server.payload["turn_candidates"]
        for index in (
            *candidate.get("family", ()),
            *(step["family"] for step in candidate["steps"] if "family" in step),
        )
    }
    disagreements = []
    if len(page_by_index) != len(rendered["families"]):
        disagreements.append("rendered families repeated an index")
    if page_by_index != declared_by_index:
        disagreements.append(
            {"server_declaration": declared_by_index, "rendered_page": page_by_index}
        )
    if candidate_indexes != set(page_by_index):
        disagreements.append(
            {"candidate_indexes": candidate_indexes, "rendered_indexes": set(page_by_index)}
        )

    assert not disagreements, f"route-family mapping disagreement: {disagreements!r}"


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
    # Asking every sow act grows the under-Alms transcript; the shared layout intentionally makes
    # that column scroll rather than resize the board, so centre-click guards first expose it.
    handle.scroll_into_view_if_needed()
    x, y = _centre(page, handle)
    if require_hit:
        assert _is_hit_target(page, handle, x, y), "elementFromPoint at target centre missed target"
    page.mouse.click(x, y)


def _click_handle_point(page, handle, x_fraction: float, y_fraction: float) -> None:
    handle.scroll_into_view_if_needed()
    point = page.evaluate(
        """({target, xFraction, yFraction}) => {
            const box = target.getBoundingClientRect();
            return {
                x: box.left + box.width * xFraction,
                y: box.top + box.height * yFraction,
            };
        }""",
        {"target": handle, "xFraction": x_fraction, "yFraction": y_fraction},
    )
    assert _is_hit_target(page, handle, point["x"], point["y"]), (
        "elementFromPoint at target point missed target"
    )
    page.mouse.click(point["x"], point["y"])


def _toggle_route_building(page, building_id: str) -> None:
    targets = page.locator(
        f'[data-building-id="{building_id}"][data-turn-family-available="true"]'
    )
    for index in range(targets.count()):
        target = targets.nth(index).element_handle()
        assert target is not None
        x, y = _centre(page, target)
        if not _is_hit_target(page, target, x, y):
            continue
        page.mouse.click(x, y)
        return
    raise AssertionError(f"{building_id} route toggle was not available to click")


def _show_hired_route_building_if_available(page, building_id: str) -> None:
    """Turn on a route family only when the server described it as a hire toggle."""
    if page.locator(
        f'[data-building-id="{building_id}"][data-turn-family-available="true"]'
    ).count():
        _toggle_route_building(page, building_id)


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
        '[data-board-position-index][data-turn-start-relocation-candidate="true"]',
        '[data-board-position-index][data-turn-skip-candidate="true"]',
        '[data-board-position-index][data-turn-duty-candidate="true"]',
        '[data-active-seat="true"][data-end-relocation-choice="true"] [data-token="abbey"][opacity="1"]',
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
        if offered.get_attribute("data-turn-control") == "confirm":
            # The walker passes the deterministic End Turn window to reach a later prompt. Its
            # target is the requested question, not the Confirm control's hit area.
            offered.click()
        else:
            _click_handle_centre(page, offered, require_hit=True)
        page.wait_for_timeout(20)
    raise AssertionError(f"did not reach {target} within {max_clicks} clicks")


def _click_candidate_step(page, step: dict) -> None:
    """Press the current DOM affordance for one engine-described turn step."""
    kind = step["kind"]
    value = step["value"]
    if kind == "origin":
        selector = f'[data-board-position-index="{value}"][data-turn-start-candidate="true"]'
    elif kind == "edge":
        selector = f'[data-arrow="{value}"][data-turn-offered="true"]'
    elif kind == "skip":
        selector = f'[data-board-position-index="{value}"][data-turn-skip-candidate="true"]'
    elif kind == "duty":
        selector = f'[data-board-position-index="{value}"][data-turn-duty-candidate="true"]'
    elif kind == "resource":
        selector = f'[data-active-seat="true"] [data-resource-choice-key="{value}"]'
        selector += '[data-turn-offered="true"]'
    elif kind == "building":
        selector = f'[data-building-choice-key="{value}"][data-turn-offered="true"]'
    elif kind in {"combination", "hire", "merchant_advance"}:
        selector = f'[data-combination-key="{value}"][data-turn-offered="true"]'
    elif kind == "seat":
        selector = f'[data-seat-choice-key="{value}"][data-turn-offered="true"]'
    elif kind == "resolution":
        if value == "tithe":
            selector = '[data-turn-control="tithe"][data-turn-control-enabled="true"]'
        else:
            action = page.query_selector('[data-turn-control="action"][data-turn-control-enabled="true"]')
            assert action is not None, f"Action was not offered for {value}"
            _click_handle_centre(page, action, require_hit=True)
            page.wait_for_timeout(40)
            selector = f'[data-resolution-key="{value}"][data-turn-offered="true"]'
            choice = page.query_selector(selector)
            if choice is None:
                return
    else:
        raise AssertionError(f"no browser click mapping for engine step kind {kind!r}")
    target = page.query_selector(selector)
    assert target is not None, f"engine step {kind}={value!r} was not offered by {selector}"
    _click_handle_centre(page, target, require_hit=True)
    page.wait_for_timeout(40)


def _click_candidate_prefix(
    page, candidate: dict, *, before_kind: str, route_toggles: tuple[str, ...] = ()
) -> None:
    """Walk every player question before `before_kind`.

    The server may mark a sole continuation arrow automatic; it remains in the candidate path
    even though the page has already followed it while rendering the next question.
    """
    for step in candidate["steps"]:
        if step["kind"] == before_kind:
            return
        if _page_matches_auto_advance_family_selection(page, step):
            continue
        _click_candidate_step(page, step)
        if step["kind"] == "origin":
            for building_id in route_toggles:
                _show_hired_route_building_if_available(page, building_id)
    raise AssertionError(f"candidate has no {before_kind!r} step")


def _page_matches_auto_advance_family_selection(page, step: dict) -> bool:
    """Read the page's visible family state against the server's automatic selections."""
    selected = 0
    for family in _rendered_route_family_data(page)["families"]:
        building_id = family["building_id"]
        index = family["i"]
        target = page.locator(f'[data-building-id="{building_id}"]').first
        if target.count() and target.get_attribute("data-turn-family-state") in {
            "owned",
            "on",
            "in_effect",
        }:
            selected |= 1 << index
    return selected in step.get("auto", [])


def _narrow_movement_library_turn_to_confirm(page) -> None:
    """Use movement_2p's ordinary action prefix to leave one full turn candidate."""
    # This ordinary four-question action leaves an acolyte in City and is intentionally free of
    # another building step. The Action control exposes its final resolution question.
    for selector in (
        '[data-board-position-index="0"][data-turn-start-candidate="true"]',
        '[data-arrow="city->north"][data-turn-offered="true"]',
        '[data-board-position-index="4"][data-turn-duty-candidate="true"]',
        '[data-turn-control="action"][data-turn-control-enabled="true"]',
        '[data-resolution-key="construct_road_deferred"][data-turn-offered="true"]',
    ):
        handle = page.query_selector(selector)
        assert handle is not None, f"missing movement_2p Library prefix target {selector}"
        _click_handle_centre(page, handle, require_hit=True)
        page.wait_for_timeout(20)
    assert _confirm_enabled(page), "Library prefix did not narrow to one turn action"


def _reach_movement_library_window(page) -> None:
    """Commit the ordinary movement_2p action and reach its Library end-of-turn window."""
    _narrow_movement_library_turn_to_confirm(page)
    _click_handle_point(
        page,
        page.locator('[data-turn-control="confirm"]').element_handle(),
        0.5,
        0.2,
    )
    page.wait_for_function(
        """() => {
          const library = document.querySelector('[data-turn-step-building-id="library"]');
          return library && library.getAttribute('data-turn-step-offered') === 'true';
        }"""
    )


def _pass_movement_red_turn_to_yellow(page) -> None:
    """Commit the ordinary Red turn, then pass its End of Turn window to Yellow's opening."""
    _reach_movement_library_window(page)
    confirm = page.query_selector('[data-turn-control="confirm"][data-turn-control-enabled="true"]')
    assert confirm is not None, "Red's End of Turn pass was not enabled"
    _click_handle_point(page, confirm, 0.5, 0.2)
    page.wait_for_function(
        """() => {
          const active = document.querySelector('[data-active-seat="true"]');
          return active && active.getAttribute('data-player') === 'player_two';
        }"""
    )


def _walk_until_skip_step_by_preferring_edges(
    page, *, target: str, route_toggle: str | None = None, max_clicks: int = 80
) -> None:
    """Advance toward a Cloisters skip prompt without taking duty/resolution branches first."""
    for _ in range(max_clicks):
        if page.locator('[data-board-position-index][data-turn-skip-candidate="true"]').count() > 0:
            return
        origin = page.query_selector(
            '[data-board-position-index][data-turn-start-candidate="true"]'
        )
        if origin is not None:
            _click_handle_centre(page, origin, require_hit=True)
            page.wait_for_timeout(20)
            if route_toggle is not None:
                _show_hired_route_building_if_available(page, route_toggle)
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


def _confirm_enabled_attribute(page) -> str | None:
    return page.get_attribute(
        '[data-turn-control="confirm"]', "data-turn-control-enabled"
    )


def _confirm_enabled(page) -> bool:
    return _confirm_enabled_attribute(page) == "true"


def _painted_confirm_label(page) -> str:
    """The visible server-drawn caption, rather than a script-owned control attribute."""
    label = page.locator(
        '[data-turn-control="confirm"] [data-turn-control-label][data-turn-offered="true"]'
    )
    assert label.count() == 1, "Confirm did not paint exactly one current caption"
    text = label.text_content()
    assert text is not None, "Confirm's painted caption had no text"
    return text


def _reach_taxation_step_two(page, *, step_one: str = "stone") -> None:
    """Walk the direct Taxation fixture to its separate Step II pill question."""
    for selector in (
        '[data-board-position-index="0"][data-turn-start-candidate="true"]',
        '[data-arrow="city->north"][data-turn-offered="true"]',
        '[data-board-position-index="1"][data-turn-duty-candidate="true"]',
        '[data-turn-control="action"][data-turn-control-enabled="true"]',
        f'[data-active-seat="true"] [data-resource-choice-key="{step_one}"]'
        '[data-turn-offered="true"]',
    ):
        handle = page.query_selector(selector)
        assert handle is not None, f"missing Taxation target {selector}"
        _click_handle_centre(page, handle, require_hit=True)
        page.wait_for_timeout(40)


def _click_taxation_resource(page, resource: str) -> None:
    handle = page.query_selector(
        f'[data-active-seat="true"] [data-resource-choice-key="{resource}"]'
        '[data-turn-offered="true"]'
    )
    assert handle is not None, f"resource {resource} was not offered"
    _click_handle_centre(page, handle, require_hit=True)
    page.wait_for_timeout(40)


def _screenshot_taxation_pills(page, path: Path) -> None:
    keys = page.locator('[data-active-seat="true"] [data-resource-choice-key]')
    boxes = [keys.nth(index).bounding_box() for index in range(keys.count())]
    assert boxes and all(box is not None for box in boxes)
    left = min(box["x"] for box in boxes if box is not None)
    top = min(box["y"] for box in boxes if box is not None)
    right = max(box["x"] + box["width"] for box in boxes if box is not None)
    bottom = max(box["y"] + box["height"] for box in boxes if box is not None)
    page.screenshot(
        path=str(path),
        clip={
            "x": left - 10,
            "y": top - 10,
            "width": right - left + 20,
            "height": bottom - top + 20,
        },
    )


def _player_holdings(page, selector: str = '[data-active-seat="true"]') -> dict[str, int]:
    return {
        resource: int(page.locator(f'{selector} [data-resource="{resource}"] text').text_content())
        for resource in ("stone", "silver", "wheat")
    }


def _all_player_holdings(page) -> dict[str, dict[str, int]]:
    return page.evaluate(
        """() => Object.fromEntries(Array.from(
          document.querySelectorAll('[data-component="player-board-v2"][data-player-seat]')
        ).map(board => [
          board.getAttribute('data-player'),
          Object.fromEntries(['stone', 'silver', 'wheat'].map(resource => [
            resource,
            Number(board.querySelector(`[data-resource="${resource}"] text`).textContent)
          ]))
        ]))"""
    )


def _all_player_slots(page) -> dict[str, list[tuple[str, str, str]]]:
    return page.evaluate(
        """() => Object.fromEntries(Array.from(
          document.querySelectorAll('[data-component="player-board-v2"][data-player-seat]')
        ).map(board => [
          board.getAttribute('data-player'),
          Array.from(board.querySelectorAll('[data-player-board-slot]')).map(slot => [
            slot.getAttribute('data-building-slot-state'),
            slot.getAttribute('data-building-id'),
            slot.getAttribute('data-donated')
          ])
        ]))"""
    )


def _all_piety_positions(page) -> dict[str, int]:
    return page.evaluate(
        """() => Object.fromEntries(Array.from(
          document.querySelectorAll(
            '[data-component="piety-track-v2"] [data-player-disc="true"]'
          )
        ).map(disc => [disc.getAttribute('data-player'), Number(
          disc.getAttribute('data-piety-position')
        )]))"""
    )


def _screenshot_piety_track(page, path: Path) -> None:
    box = page.locator('[data-component="piety-track-v2"]').bounding_box()
    assert box is not None
    page.screenshot(
        path=str(path),
        clip={
            "x": box["x"] - 8,
            "y": box["y"] - 8,
            "width": box["width"] + 16,
            "height": box["height"] + 16,
        },
    )


def _screenshot_turn_prompt(page, path: Path) -> None:
    page.locator('[data-component="play-turn"]').screenshot(path=str(path))


def _assert_painted_turn_phase(page, current: str) -> None:
    """The column has one visible green row and the other two remain visibly dim."""
    expected_colors = {
        True: "rgb(95, 191, 110)",
        False: "rgb(107, 103, 94)",
    }
    for phase in ("beginning", "sow", "end"):
        row = page.locator(f'[data-turn-phase="{phase}"]')
        assert row.count() == 1, f"{phase} phase row was not drawn exactly once"
        assert row.is_visible(), f"{phase} phase row was hidden"
        is_current = phase == current
        assert (row.get_attribute("data-phase-current") == "true") is is_current
        assert row.evaluate("node => getComputedStyle(node).color") == expected_colors[is_current]


def _assert_all_turn_phases_dim(page) -> None:
    """An inactive phase column remains visibly present but has no current row."""
    for phase in ("beginning", "sow", "end"):
        row = page.locator(f'[data-turn-phase="{phase}"]')
        assert row.count() == 1, f"{phase} phase row was not drawn exactly once"
        assert row.is_visible(), f"{phase} phase row was hidden"
        assert row.get_attribute("data-phase-current") is None
        assert row.evaluate("node => getComputedStyle(node).color") == "rgb(107, 103, 94)"
    assert page.locator('[data-turn-phase][data-phase-current="true"]').count() == 0


def _assert_painted_round_end_phases(page, keys: list[str], current: str) -> None:
    """The completed round-end steps are dim and exactly one live question is green."""
    assert page.locator("[data-round-end-phase]").count() == len(keys)
    for key in keys:
        row = page.locator(f'[data-round-end-phase="{key}"]')
        assert row.count() == 1, f"{key} round-end row was not drawn exactly once"
        assert row.is_visible(), f"{key} round-end row was hidden"
        is_current = key == current
        assert (row.get_attribute("data-phase-current") == "true") is is_current
        expected_color = "rgb(95, 191, 110)" if is_current else "rgb(107, 103, 94)"
        assert row.evaluate("node => getComputedStyle(node).color") == expected_color
    assert page.locator('[data-round-end-phase][data-phase-current="true"]').count() == 1


def _screenshot_active_board(page, path: Path) -> None:
    original_viewport = page.viewport_size
    assert original_viewport is not None
    original_zoom = page.evaluate("document.body.style.zoom")
    page.set_viewport_size(
        {
            "width": original_viewport["width"] * 2,
            "height": original_viewport["height"] * 2,
        }
    )
    page.evaluate("document.body.style.zoom = '2'")
    try:
        box = page.locator('[data-active-seat="true"]').bounding_box()
        assert box is not None
        image = Image.open(BytesIO(page.screenshot(full_page=True))).convert("RGB")
        crop = image.crop(
            (
                round(box["x"]),
                round(box["y"]),
                round(box["x"] + box["width"]),
                round(box["y"] + box["height"]),
            )
        )
        crop.save(path)
    finally:
        page.evaluate("zoom => { document.body.style.zoom = zoom; }", original_zoom)
        page.set_viewport_size(original_viewport)


def _click_if_offered(page, selector: str) -> None:
    handle = page.query_selector(selector)
    if handle is not None:
        _click_handle_centre(page, handle, require_hit=True)
        page.wait_for_timeout(40)


def test_taxation_step_two_pills_filter_survivors_and_reach_all_six_multisets(page, serve) -> None:
    """The six engine combinations remain reachable through the resource pills."""
    outcomes = {}
    for combination in (
        ("stone", "stone"),
        ("stone", "silver"),
        ("stone", "wheat"),
        ("silver", "silver"),
        ("silver", "wheat"),
        ("wheat", "wheat"),
    ):
        base_url, server = serve(SCENARIOS / "taxation_three_bonus_types_001.json")
        page.goto(base_url, wait_until="networkidle")
        _reach_taxation_step_two(page)

        assert (
            page.locator(
                '[data-turn-prompt*="Taxation step 2."][data-turn-offered="true"]'
            ).count()
            == 1
        )
        assert (
            page.locator(
                '[data-active-seat="true"] [data-resource-choice-key][data-turn-offered="true"]'
            ).count()
            == 3
        )
        if combination == ("stone", "stone"):
            page.screenshot(
                path=str(SCREENSHOTS / "taxation-six-option-position.png"), full_page=True
            )

        before_step_two = _player_holdings(page)
        other_players_before = _all_player_holdings(page)
        active_player_id = page.get_attribute('[data-active-seat="true"]', "data-player")
        if combination == ("stone", "stone"):
            _screenshot_taxation_pills(page, SCREENSHOTS / "taxation-step2-before.png")
        _click_taxation_resource(page, combination[0])
        after_one = _player_holdings(page)
        assert after_one[combination[0]] == before_step_two[combination[0]] + 1
        assert all(
            after_one[resource] == before_step_two[resource]
            for resource in before_step_two
            if resource != combination[0]
        )
        assert (
            page.locator(
                '[data-active-seat="true"] [data-resource-choice-key][data-turn-offered="true"]'
            ).count()
            > 0
        )
        assert {
            player: holdings
            for player, holdings in _all_player_holdings(page).items()
            if player != active_player_id
        } == {
            player: holdings
            for player, holdings in other_players_before.items()
            if player != active_player_id
        }
        if combination == ("stone", "stone"):
            _screenshot_taxation_pills(page, SCREENSHOTS / "taxation-step2-after-one.png")
        _click_taxation_resource(page, combination[1])

        preview = _player_holdings(page)
        expected = dict(before_step_two)
        for resource in combination:
            expected[resource] += 1
        assert preview == expected
        assert (
            page.locator(
                '[data-active-seat="true"] [data-resource-choice-key][data-turn-offered="true"]'
            ).count()
            == 0
        )
        assert {
            player: holdings
            for player, holdings in _all_player_holdings(page).items()
            if player != active_player_id
        } == {
            player: holdings
            for player, holdings in other_players_before.items()
            if player != active_player_id
        }
        if combination == ("stone", "stone"):
            _screenshot_taxation_pills(page, SCREENSHOTS / "taxation-step2-after-two.png")
        assert _confirm_enabled(page)
        acting_engine_player = server.state.active_player
        page.locator('[data-turn-control="confirm"]').click()
        page.wait_for_timeout(120)
        acting_board = f'[data-player="{active_player_id}"]'
        assert _player_holdings(page, acting_board) == preview
        actual = server.state.player_state(acting_engine_player).resources
        assert preview == {
            "stone": actual.stone,
            "silver": actual.silver,
            "wheat": actual.wheat,
        }
        outcomes[combination] = tuple(
            preview[resource] for resource in ("stone", "silver", "wheat")
        )

    assert len(outcomes) == 6
    assert len(set(outcomes.values())) == 6


def test_taxation_step_two_darkens_step_one_only_resources(page, serve) -> None:
    base_url, _server = serve(SCENARIOS / "taxation_majority_bonus_001.json")
    page.goto(base_url, wait_until="networkidle")
    _reach_taxation_step_two(page, step_one="wheat")

    assert (
        page.locator(
            '[data-active-seat="true"] [data-resource-choice-key="wheat"][data-turn-offered="true"]'
        ).count()
        == 0
    )
    assert (
        page.locator(
            '[data-active-seat="true"] [data-resource-choice-key="stone"][data-turn-offered="true"]'
        ).count()
        == 1
    )
    assert (
        page.locator(
            '[data-active-seat="true"] [data-resource-choice-key="silver"]'
            '[data-turn-offered="true"]'
        ).count()
        == 1
    )
    assert not _confirm_enabled(page)


def test_taxation_step_two_renders_the_server_scriptorium_explanation(page, serve) -> None:
    base_url, _server = serve(SCENARIOS / "scriptorium_taxation_majority_other_tiles_001.json")
    page.goto(base_url, wait_until="networkidle")
    _reach_taxation_step_two(page)

    prompt = page.locator('[data-turn-prompt][data-turn-offered="true"]')
    assert prompt.count() == 1
    assert prompt.text_content() == (
        "Red: Taxation step 2. The Scriptorium makes south west and west majorities. "
        "Choose two resources."
    )


def test_tithe_cornucopia_previews_the_picked_holding_and_confirm_changes_nothing(
    page, serve
) -> None:
    base_url, server = serve(SCENARIOS / "tithe_counter_choice_001.json")
    page.goto(base_url, wait_until="networkidle")
    for selector in (
        '[data-board-position-index="7"][data-turn-start-candidate="true"]',
        '[data-arrow="west->north_west"][data-turn-offered="true"]',
        '[data-board-position-index="8"][data-turn-duty-candidate="true"]',
        '[data-turn-control="tithe"][data-turn-control-enabled="true"]',
    ):
        handle = page.query_selector(selector)
        assert handle is not None, f"missing Cornucopia tithe target {selector}"
        _click_handle_centre(page, handle, require_hit=True)
        page.wait_for_timeout(40)
    assert (
        page.locator(
            '[data-active-seat="true"] [data-resource-choice-key][data-turn-offered="true"]'
        ).count()
        == 3
    )

    before = _player_holdings(page)
    others_before = _all_player_holdings(page)
    active_player_id = page.get_attribute('[data-active-seat="true"]', "data-player")
    _click_taxation_resource(page, "stone")
    after_click = _player_holdings(page)
    assert after_click["stone"] == before["stone"] + 1
    assert after_click["silver"] == before["silver"]
    assert after_click["wheat"] == before["wheat"]
    assert {
        player: holdings
        for player, holdings in _all_player_holdings(page).items()
        if player != active_player_id
    } == {
        player: holdings for player, holdings in others_before.items() if player != active_player_id
    }

    assert _confirm_enabled(page)
    acting_engine_player = server.state.active_player
    page.locator('[data-turn-control="confirm"]').click()
    page.wait_for_timeout(120)
    assert _player_holdings(page, f'[data-player="{active_player_id}"]') == after_click
    actual = server.state.player_state(acting_engine_player).resources
    assert after_click == {
        "stone": actual.stone,
        "silver": actual.silver,
        "wheat": actual.wheat,
    }


def test_resource_preview_reset_restores_pre_click_holdings(page, serve) -> None:
    base_url, _server = serve(SCENARIOS / "tithe_counter_choice_001.json")
    page.goto(base_url, wait_until="networkidle")
    for selector in (
        '[data-board-position-index="7"][data-turn-start-candidate="true"]',
        '[data-arrow="west->north_west"][data-turn-offered="true"]',
        '[data-board-position-index="8"][data-turn-duty-candidate="true"]',
        '[data-turn-control="tithe"][data-turn-control-enabled="true"]',
    ):
        handle = page.query_selector(selector)
        assert handle is not None, f"missing Cornucopia tithe target {selector}"
        _click_handle_centre(page, handle, require_hit=True)
        page.wait_for_timeout(40)
    before = _player_holdings(page)
    _click_taxation_resource(page, "stone")
    assert _player_holdings(page)["stone"] == before["stone"] + 1
    page.locator('[data-turn-control="reset"]').click()
    page.wait_for_timeout(80)
    assert _player_holdings(page) == before


def test_produce_resource_preview_matches_confirm_and_reset(page, serve) -> None:
    base_url, server = serve(SCENARIOS / "produce_wheat_001.json")
    page.goto(base_url, wait_until="networkidle")
    before = _player_holdings(page)
    other_players_before = _all_player_holdings(page)
    active_player_id = page.get_attribute('[data-active-seat="true"]', "data-player")
    acting_player = server.state.active_player
    candidate = next(
        candidate
        for candidate in server.payload["turn_candidates"]
        if any(
            step["kind"] == "resolution" and step["value"] == "produce_wheat"
            for step in candidate["steps"]
        )
    )
    action = next(
        action
        for action in legal_actions(server.state, server.config)
        if action_id(action) == candidate["action_id"]
    )
    expected_state = apply_action(server.state, action, server.config).state
    expected = expected_state.player_state(acting_player).resources

    _click_candidate_prefix(page, candidate, before_kind="resolution")
    action_control = page.query_selector(
        '[data-turn-control="action"][data-turn-control-enabled="true"]'
    )
    assert action_control is not None
    _click_handle_centre(page, action_control, require_hit=True)
    page.wait_for_timeout(40)

    _screenshot_active_board(page, SCREENSHOTS / "produce-preview-before.png")
    resolution = page.query_selector(
        '[data-resolution-key="produce_wheat"][data-turn-offered="true"]'
    )
    assert resolution is not None
    _click_handle_centre(page, resolution, require_hit=True)
    page.wait_for_timeout(60)
    _screenshot_active_board(page, SCREENSHOTS / "produce-preview-after.png")

    preview = _player_holdings(page)
    assert preview == {
        "stone": expected.stone,
        "silver": expected.silver,
        "wheat": expected.wheat,
    }
    assert {
        player: holdings
        for player, holdings in _all_player_holdings(page).items()
        if player != active_player_id
    } == {
        player: holdings
        for player, holdings in other_players_before.items()
        if player != active_player_id
    }
    assert _confirm_enabled(page)

    page.locator('[data-turn-control="reset"]').click()
    page.wait_for_timeout(100)
    assert _player_holdings(page) == before

    _click_candidate_prefix(page, candidate, before_kind="resolution")
    action_control = page.query_selector(
        '[data-turn-control="action"][data-turn-control-enabled="true"]'
    )
    assert action_control is not None
    _click_handle_centre(page, action_control, require_hit=True)
    page.wait_for_timeout(40)
    resolution = page.query_selector(
        '[data-resolution-key="produce_wheat"][data-turn-offered="true"]'
    )
    assert resolution is not None
    _click_handle_centre(page, resolution, require_hit=True)
    page.wait_for_timeout(60)
    page.locator('[data-turn-control="confirm"]').click()
    page.wait_for_timeout(120)
    assert _player_holdings(page, f'[data-player="{active_player_id}"]') == preview
    assert server.state.player_state(acting_player).resources == expected


def test_devotion_previews_piety_cap_and_confirm_matches_reset(page, serve) -> None:
    base_url, server = serve(SCENARIOS / "clerical_devotion_chapel_001.json")
    page.goto(base_url, wait_until="networkidle")
    acting_player = server.state.active_player
    active_player_id = page.get_attribute('[data-active-seat="true"]', "data-player")
    before_positions = _all_piety_positions(page)
    other_positions = {
        player: position
        for player, position in before_positions.items()
        if player != active_player_id
    }
    candidate = next(
        candidate
        for candidate in server.payload["turn_candidates"]
        if any(step.get("piety_delta") is not None for step in candidate["steps"])
    )
    action = next(
        action
        for action in legal_actions(server.state, server.config)
        if action_id(action) == candidate["action_id"]
    )
    expected_player = apply_action(server.state, action, server.config).state.player_state(
        acting_player
    )

    _click_candidate_prefix(page, candidate, before_kind="resolution")
    action_control = page.query_selector('[data-turn-control="action"][data-turn-control-enabled="true"]')
    assert action_control is not None, "Action was not offered for devotion"
    _click_handle_centre(page, action_control, require_hit=True)
    page.wait_for_timeout(40)

    _screenshot_piety_track(page, SCREENSHOTS / "devotion-piety-before.png")
    resolution = page.query_selector(
        '[data-resolution-key="clerical_devotion"][data-turn-offered="true"]'
    )
    assert resolution is not None
    _click_handle_centre(page, resolution, require_hit=True)
    page.wait_for_timeout(60)
    _screenshot_piety_track(page, SCREENSHOTS / "devotion-piety-after.png")

    preview_positions = _all_piety_positions(page)
    assert preview_positions[active_player_id] == expected_player.piety
    assert {
        player: position
        for player, position in preview_positions.items()
        if player != active_player_id
    } == other_positions
    assert _confirm_enabled(page)

    page.locator('[data-turn-control="reset"]').click()
    page.wait_for_timeout(100)
    assert _all_piety_positions(page) == before_positions

    _click_candidate_prefix(page, candidate, before_kind="resolution")
    _click_candidate_step(
        page, next(step for step in candidate["steps"] if step["kind"] == "resolution")
    )
    page.locator('[data-turn-control="confirm"]').click()
    page.wait_for_timeout(120)
    assert server.state.player_state(acting_player).piety == expected_player.piety
    assert _all_piety_positions(page)[active_player_id] == expected_player.piety
    assert {
        player: position
        for player, position in _all_piety_positions(page).items()
        if player != active_player_id
    } == other_positions


def test_piety_preview_does_not_leave_indulgence_pills_anchored_to_old_disc(page, serve) -> None:
    base_url, server = serve(SCENARIOS / "indulgences_active_sell_piety_001.json")
    page.goto(base_url, wait_until="networkidle")

    building = page.query_selector(
        '[data-active-seat="true"] [data-turn-step-building-id="indulgences"]'
        '[data-turn-step-offered="true"]'
    )
    assert building is not None
    _click_handle_centre(page, building, require_hit=True)
    direction = page.query_selector(
        '[data-turn-step-direction="sell_piety"][data-turn-step-offered="true"]'
    )
    assert direction is not None
    _click_handle_centre(page, direction, require_hit=True)
    assert page.locator('[data-piety-choice-pill][data-piety-choice-offered="true"]').count() > 0

    devotion = next(
        candidate
        for candidate in server.payload["turn_candidates"]
        if any(step["kind"] == "resolution" and step["value"] == "clerical_devotion"
               for step in candidate["steps"])
    )
    _click_candidate_prefix(page, devotion, before_kind="resolution")
    _click_candidate_step(
        page, next(step for step in devotion["steps"] if step["kind"] == "resolution")
    )

    assert page.locator('[data-piety-choice-pill][data-piety-choice-offered="true"]').count() == 0
    assert (
        page.get_attribute('[data-component="piety-track-v2"]', "data-piety-preview-position")
        is not None
    )


def test_devotion_can_sell_gained_piety_before_end_turn(page, serve) -> None:
    base_url, server = serve(SCENARIOS / "indulgences_active_sell_piety_001.json")
    page.goto(base_url, wait_until="networkidle")
    before_state = server.state
    initial_candidate_ids = tuple(
        candidate["action_id"] for candidate in server.payload["turn_candidates"]
    )
    acting_player = before_state.active_player
    devotion_candidate = next(
        candidate
        for candidate in server.payload["turn_candidates"]
        if any(step["kind"] == "resolution" and step["value"] == "clerical_devotion"
               for step in candidate["steps"])
    )
    devotion = next(
        action
        for action in legal_actions(before_state, server.config)
        if action.resolution is TurnResolutionType.CLERICAL_DEVOTION
    )
    committed = apply_action(before_state, devotion, server.config)
    sell_gained_piety = next(
        step
        for step in turn_steps(committed.state, server.config)
        if step.direction == "sell_piety" and step.amount == 1
    )
    after_conversion = apply_turn_step(
        committed.state,
        server.config,
        sell_gained_piety,
    )
    expected = apply_action(after_conversion, EndTurnAction(), server.config).state

    def click_devotion(*, choose_action: bool = True) -> None:
        if choose_action:
            _click_candidate_prefix(page, devotion_candidate, before_kind="resolution")
        selectors = []
        if choose_action:
            selectors.append('[data-turn-control="action"][data-turn-control-enabled="true"]')
        selectors.append('[data-resolution-key="clerical_devotion"][data-turn-offered="true"]')
        for selector in selectors:
            handle = page.query_selector(selector)
            assert handle is not None, f"missing devotion target {selector}"
            _click_handle_centre(page, handle, require_hit=True)
            page.wait_for_timeout(40)
        assert _confirm_enabled(page)
        page.locator('[data-turn-control="confirm"]').click()
        page.wait_for_timeout(120)

    def click_sell_and_confirm() -> None:
        building = page.query_selector(
            '[data-active-seat="true"] [data-turn-step-building-id="indulgences"]'
            '[data-turn-step-offered="true"]'
        )
        assert building is not None
        _click_handle_centre(page, building, require_hit=True)
        direction = page.query_selector(
            '[data-turn-step-direction="sell_piety"][data-turn-step-offered="true"]'
        )
        assert direction is not None
        _click_handle_centre(page, direction, require_hit=True)
        destination = page.query_selector(
            f'[data-piety-choice-pill][data-piety-choice-destination="{before_state.player_state(acting_player).piety}"]'
            '[data-piety-choice-offered="true"]'
        )
        assert destination is not None
        _click_handle_centre(page, destination, require_hit=True)
        assert _confirm_enabled(page)
        page.locator('[data-turn-control="confirm"]').click()
        page.wait_for_timeout(120)

    click_devotion()
    assert server.state == committed.state
    assert server.state.active_player is acting_player
    assert server.state.turn_progress.resolution_committed is True
    reset = page.locator('[data-turn-control="reset"]')
    assert reset.is_visible()
    assert reset.get_attribute("data-turn-control-enabled") == "true"
    _screenshot_turn_prompt(page, SCREENSHOTS / "post-resolution-conversion-window.png")

    reset_handle = reset.element_handle()
    assert reset_handle is not None
    _click_handle_centre(page, reset_handle, require_hit=True)
    page.wait_for_timeout(100)
    assert server.state == before_state
    assert (
        tuple(candidate["action_id"] for candidate in server.payload["turn_candidates"])
        == initial_candidate_ids
    )
    initial_resolution_keys = {
        step["value"]
        for candidate in server.payload["turn_candidates"]
        for step in candidate["steps"]
        if step["kind"] == "resolution"
    }
    assert len(initial_resolution_keys) > 1
    # Reset restores the first unanswered sow act.  Reach the action split again before checking
    # its offered resolutions rather than relying on the old forced-prefix shortcut.
    _click_candidate_prefix(page, devotion_candidate, before_kind="resolution")
    action_control = page.locator('[data-turn-control="action"]')
    assert action_control.is_visible()
    assert action_control.get_attribute("data-turn-control-enabled") == "true"
    tithe_control = page.locator('[data-turn-control="tithe"]')
    assert tithe_control.is_visible()
    assert tithe_control.get_attribute("data-turn-control-enabled") == "true"
    action_handle = action_control.element_handle()
    assert action_handle is not None
    _click_handle_centre(page, action_handle, require_hit=True)
    page.wait_for_timeout(40)
    for resolution_key in initial_resolution_keys - {"tithe"}:
        assert (
            page.locator(
                f'[data-resolution-key="{resolution_key}"][data-turn-offered="true"]'
            ).count()
            == 1
        )

    click_devotion(choose_action=False)
    click_sell_and_confirm()
    assert server.state == after_conversion
    _assert_painted_turn_phase(page, "end")
    assert page.locator('[data-turn-phase-prompt="end"]').count() == 0
    assert _confirm_enabled(page)
    page.locator('[data-turn-control="confirm"]').click()
    page.wait_for_timeout(120)

    assert server.state == expected
    assert (
        server.state.player_state(acting_player).piety == expected.player_state(acting_player).piety
    )
    assert (
        server.state.player_state(acting_player).resources.silver
        == expected.player_state(acting_player).resources.silver
    )


def test_resolution_abandons_piety_conversion_and_allows_a_new_commit(page, serve) -> None:
    base_url, server = serve(SCENARIOS / "indulgences_active_sell_piety_001.json")
    page.goto(base_url, wait_until="networkidle")
    before_state = server.state
    prompt = page.locator('[data-component="play-turn"]')
    height_before = prompt.bounding_box()["height"]

    building = page.query_selector(
        '[data-active-seat="true"] [data-turn-step-building-id="indulgences"]'
        '[data-turn-step-offered="true"]'
    )
    assert building is not None
    _click_handle_centre(page, building, require_hit=True)
    direction = page.query_selector(
        '[data-turn-step-direction="sell_piety"][data-turn-step-offered="true"]'
    )
    assert direction is not None
    _click_handle_centre(page, direction, require_hit=True)
    assert page.locator('[data-piety-choice-pill][data-piety-choice-offered="true"]').count() > 0
    label = page.locator('[data-turn-step-answer-label="true"]')
    slot = page.locator('[data-turn-step-amount-total="true"]')
    hint = page.locator('[data-turn-step-resource-hint="true"]')
    answer_row = page.locator('[data-turn-step-resource-row="true"]')
    assert label.is_visible()
    assert not hint.is_visible()
    assert hint.inner_text() == ""
    assert slot.inner_text() == ""
    assert prompt.bounding_box()["height"] == pytest.approx(height_before, abs=0.1)
    _screenshot_turn_prompt(page, SCREENSHOTS / "conversion-piety-answer-pending.png")

    destination = page.locator(
        '[data-piety-choice-pill][data-piety-choice-offered="true"]'
        '[data-piety-choice-destination="1"]'
    )
    assert destination.count() == 1
    target = int(destination.get_attribute("data-piety-choice-destination"))
    expected_amount_by_destination = {2: 1, 1: 2, 0: 3}
    _click_handle_centre(page, destination.element_handle(), require_hit=True)
    assert label.is_visible()
    assert slot.is_visible()
    assert slot.inner_text() == str(expected_amount_by_destination[target])
    assert not hint.is_visible()
    assert prompt.bounding_box()["height"] == pytest.approx(height_before, abs=0.1)
    _screenshot_turn_prompt(page, SCREENSHOTS / "conversion-piety-answer-chosen.png")

    devotion = next(
        candidate
        for candidate in server.payload["turn_candidates"]
        if any(step["kind"] == "resolution" and step["value"] == "clerical_devotion"
               for step in candidate["steps"])
    )
    _click_candidate_prefix(page, devotion, before_kind="resolution")
    page.locator('[data-turn-control="action"][data-turn-control-enabled="true"]').click()
    page.wait_for_timeout(40)
    resolution = page.query_selector(
        '[data-resolution-key="clerical_devotion"][data-turn-offered="true"]'
    )
    assert resolution is not None
    _click_handle_centre(page, resolution, require_hit=True)

    direction_row = page.locator('[data-turn-step-direction-row="true"]')
    assert direction_row.get_attribute("data-turn-step-row-active") == "false"
    assert not direction_row.is_visible()
    assert not answer_row.is_visible()
    _screenshot_turn_prompt(page, SCREENSHOTS / "conversion-prompt-after-resolution.png")
    assert page.locator('[data-turn-step-direction][data-turn-step-selected="true"]').count() == 0
    assert not label.is_visible()
    assert slot.inner_text() == ""
    assert not hint.is_visible()
    assert hint.inner_text() == ""
    assert page.locator('[data-piety-choice-pill][data-piety-choice-offered="true"]').count() == 0
    _assert_painted_turn_phase(page, "sow")
    assert server.state == before_state

    page.locator('[data-turn-control="reset"]').click()
    page.wait_for_timeout(80)
    assert server.state == before_state
    assert prompt.bounding_box()["height"] == pytest.approx(height_before, abs=0.1)

    building = page.query_selector(
        '[data-active-seat="true"] [data-turn-step-building-id="indulgences"]'
        '[data-turn-step-offered="true"]'
    )
    assert building is not None
    _click_handle_centre(page, building, require_hit=True)
    direction = page.query_selector(
        '[data-turn-step-direction="sell_piety"][data-turn-step-offered="true"]'
    )
    assert direction is not None
    _click_handle_centre(page, direction, require_hit=True)
    destination = page.locator(
        '[data-piety-choice-pill][data-piety-choice-offered="true"]'
        '[data-piety-choice-destination="0"]'
    )
    assert destination.count() == 1
    target = int(destination.get_attribute("data-piety-choice-destination"))
    _click_handle_centre(page, destination.element_handle(), require_hit=True)
    assert page.locator('[data-turn-step-amount-total="true"]').inner_text() == str(
        expected_amount_by_destination[target]
    )
    assert _confirm_enabled(page)
    page.locator('[data-turn-control="confirm"]').click()
    page.wait_for_timeout(120)
    assert (
        server.state.player_state(server.state.active_player).piety
        != before_state.player_state(before_state.active_player).piety
    )
    assert server.state.player_state(server.state.active_player).piety == target


@pytest.mark.parametrize(
    "scenario_path",
    [
        SCENARIOS / "playtest" / PLAYTEST_CONVERSIONS,
        SCENARIOS / "indulgences_active_sell_piety_001.json",
    ],
    ids=lambda path: path.name,
)
def test_every_conversion_pair_has_a_painted_answer_or_no_answer_row(
    page, serve, scenario_path
) -> None:
    base_url, _server = serve(scenario_path)
    page.goto(base_url, wait_until="networkidle")
    pairs = sorted(
        {(step["building_id"], step["direction"]) for step in _server.payload["turn_steps"]}
    )
    assert pairs

    prompt = page.locator('[data-component="play-turn"]')
    initial_height = prompt.bounding_box()["height"]
    for building_id, direction in pairs:
        building = page.query_selector(
            f'[data-active-seat="true"] [data-turn-step-building-id="{building_id}"]'
            '[data-turn-step-offered="true"]'
        )
        if building is None:
            building = page.query_selector(
                f'[data-turn-step-building-id="{building_id}"][data-turn-step-offered="true"]'
            )
        assert building is not None, f"missing conversion pair {building_id}/{direction}"
        _click_handle_centre(page, building, require_hit=True)
        hire_payment = page.query_selector(
            '[data-turn-step-hire-payment][data-turn-step-hire-offered="true"]'
        )
        if hire_payment is not None:
            _click_handle_centre(page, hire_payment, require_hit=True)
        direction_key = page.query_selector(
            f'[data-turn-step-direction="{direction}"][data-turn-step-offered="true"]'
        )
        assert direction_key is not None, f"missing conversion pair {building_id}/{direction}"
        _click_handle_centre(page, direction_key, require_hit=True)

        row = page.locator('[data-turn-step-resource-row="true"]')
        label = page.locator('[data-turn-step-answer-label="true"]')
        slot = page.locator('[data-turn-step-amount-total="true"]')
        assert row.is_visible(), f"answer row disappeared for {building_id}/{direction}"
        assert label.is_visible(), f"answer label disappeared for {building_id}/{direction}"
        assert (
            page.locator('[data-resource-choice-key][data-turn-offered="true"]').count()
            or page.locator('[data-piety-choice-pill][data-piety-choice-offered="true"]').count()
        ), f"no live answer control for {building_id}/{direction}"
        assert prompt.bounding_box()["height"] == pytest.approx(initial_height, abs=0.1)

        answer = page.query_selector('[data-resource-choice-key][data-turn-offered="true"]')
        if answer is None:
            answer = page.query_selector(
                '[data-piety-choice-pill][data-piety-choice-offered="true"]'
            )
        assert answer is not None, f"no live answer control for {building_id}/{direction}"
        _click_handle_centre(page, answer, require_hit=True)
        page.wait_for_timeout(40)
        assert slot.inner_text().strip(), f"empty answered slot for {building_id}/{direction}"
        assert prompt.bounding_box()["height"] == pytest.approx(initial_height, abs=0.1)

        page.locator('[data-turn-control="reset"]').click()
        page.wait_for_timeout(80)
        assert not row.is_visible(), (
            f"answer row remained after reset for {building_id}/{direction}"
        )
        assert prompt.bounding_box()["height"] == pytest.approx(initial_height, abs=0.1)


def test_resolution_abandons_partial_resource_conversion_and_reset_is_safe(page, serve) -> None:
    base_url, server = serve(SCENARIOS / "playtest" / PLAYTEST_CONVERSIONS)
    page.goto(base_url, wait_until="networkidle")
    before_state = server.state
    prompt = page.locator('[data-component="play-turn"]')
    height_before = prompt.bounding_box()["height"]

    building = page.query_selector(
        '[data-turn-step-building-id="stone_yard"][data-turn-step-offered="true"]'
    )
    assert building is not None
    _click_handle_centre(page, building, require_hit=True)
    direction = page.query_selector(
        '[data-turn-step-direction="sell_stone"][data-turn-step-offered="true"]'
    )
    assert direction is not None
    _click_handle_centre(page, direction, require_hit=True)
    stone = page.query_selector(
        '[data-active-seat="true"] [data-resource-choice-key="stone"][data-turn-offered="true"]'
    )
    assert stone is not None
    _click_handle_centre(page, stone, require_hit=True)
    assert page.locator('[data-turn-step-amount-total="true"]').inner_text() == "1"
    assert prompt.bounding_box()["height"] == pytest.approx(height_before, abs=0.1)

    devotion = next(
        candidate
        for candidate in server.payload["turn_candidates"]
        if any(step["kind"] == "resolution" and step["value"] == "clerical_devotion"
               for step in candidate["steps"])
    )
    _click_candidate_prefix(page, devotion, before_kind="resolution")
    page.locator('[data-turn-control="action"][data-turn-control-enabled="true"]').click()
    page.wait_for_timeout(40)
    resolution = page.query_selector(
        '[data-resolution-key="clerical_devotion"][data-turn-offered="true"]'
    )
    assert resolution is not None
    _click_handle_centre(page, resolution, require_hit=True)
    assert (
        page.locator('[data-turn-step-direction-row="true"]').get_attribute(
            "data-turn-step-row-active"
        )
        == "false"
    )
    assert page.locator('[data-turn-step-amount-total="true"]').inner_text() == ""
    assert not page.locator('[data-turn-step-answer-label="true"]').is_visible()
    assert server.state == before_state

    page.locator('[data-turn-control="reset"]').click()
    page.wait_for_timeout(80)
    assert server.state == before_state
    assert prompt.bounding_box()["height"] == pytest.approx(height_before, abs=0.1)

    building = page.query_selector(
        '[data-turn-step-building-id="stone_yard"][data-turn-step-offered="true"]'
    )
    assert building is not None
    _click_handle_centre(page, building, require_hit=True)
    direction = page.query_selector(
        '[data-turn-step-direction="sell_stone"][data-turn-step-offered="true"]'
    )
    assert direction is not None
    _click_handle_centre(page, direction, require_hit=True)
    stone = page.query_selector(
        '[data-active-seat="true"] [data-resource-choice-key="stone"][data-turn-offered="true"]'
    )
    assert stone is not None
    _click_handle_centre(page, stone, require_hit=True)
    assert _confirm_enabled(page)
    page.locator('[data-turn-control="confirm"]').click()
    page.wait_for_timeout(120)
    assert server.state != before_state


def test_building_donation_previews_donated_slot_and_confirm_matches_reset(page, serve) -> None:
    base_url, server = serve(SCENARIOS / "give_alms_donate_building_001.json")
    page.goto(base_url, wait_until="networkidle")
    acting_player = server.state.active_player
    active_player_id = page.get_attribute('[data-active-seat="true"]', "data-player")
    before_slots = _all_player_slots(page)
    candidate = next(
        candidate
        for candidate in server.payload["turn_candidates"]
        if any(step.get("building_donation") is not None for step in candidate["steps"])
    )
    action = next(
        action
        for action in legal_actions(server.state, server.config)
        if action_id(action) == candidate["action_id"]
    )
    expected_player = apply_action(server.state, action, server.config).state.player_state(
        acting_player
    )

    _screenshot_active_board(page, SCREENSHOTS / "donation-board-before.png")
    _click_candidate_prefix(page, candidate, before_kind="resolution")
    _click_candidate_step(
        page, next(step for step in candidate["steps"] if step["kind"] == "resolution")
    )
    _screenshot_active_board(page, SCREENSHOTS / "donation-board-after.png")

    preview_slots = _all_player_slots(page)
    expected_slots = [
        ["bought", building_id, "false"]
        for building_id in expected_player.player_board_slots.active_buildings
    ] + [
        ["donated", building_id, "true"]
        for building_id in expected_player.player_board_slots.donated_buildings
    ]
    assert preview_slots[active_player_id] == expected_slots + [
        ["empty", "", "false"]
    ] * (len(preview_slots[active_player_id]) - len(expected_slots))
    assert {
        player: slots for player, slots in preview_slots.items() if player != active_player_id
    } == {player: slots for player, slots in before_slots.items() if player != active_player_id}
    assert _confirm_enabled(page)

    page.locator('[data-turn-control="reset"]').click()
    page.wait_for_timeout(100)
    assert _all_player_slots(page) == before_slots

    _click_candidate_prefix(page, candidate, before_kind="resolution")
    _click_candidate_step(
        page, next(step for step in candidate["steps"] if step["kind"] == "resolution")
    )
    page.locator('[data-turn-control="confirm"]').click()
    page.wait_for_timeout(120)
    assert (
        action.donate_building_id
        in server.state.player_state(acting_player).player_board_slots.donated_buildings
    )
    assert _all_player_slots(page)[active_player_id][0] == [
        "donated",
        action.donate_building_id,
        "true",
    ]


def test_construction_preview_matches_confirm_and_reset(page, serve) -> None:
    base_url, server = serve(SCENARIOS / "construct_building_level1_001.json")
    page.goto(base_url, wait_until="networkidle")
    before = _player_holdings(page)
    other_players_before = _all_player_holdings(page)
    active_player_id = page.get_attribute('[data-active-seat="true"]', "data-player")
    acting_player = server.state.active_player
    candidate = next(
        candidate
        for candidate in server.payload["turn_candidates"]
        if any(step.get("building_constructed") == "well" for step in candidate["steps"])
    )
    action = next(
        action
        for action in legal_actions(server.state, server.config)
        if action_id(action) == candidate["action_id"]
    )
    expected_state = apply_action(server.state, action, server.config).state
    expected_player = expected_state.player_state(acting_player)

    _click_candidate_prefix(page, candidate, before_kind="resolution")
    _click_candidate_step(
        page, next(step for step in candidate["steps"] if step["kind"] == "resolution")
    )

    _screenshot_active_board(page, SCREENSHOTS / "construction-preview-before.png")
    building = page.query_selector('[data-building-choice-key="well"][data-turn-offered="true"]')
    assert building is not None
    building.hover()
    assert "Construct for 1 stone." in page.locator(
        '[data-building-tooltip-ability="true"]'
    ).inner_text()
    _click_handle_centre(page, building, require_hit=True)
    page.wait_for_timeout(60)
    _screenshot_active_board(page, SCREENSHOTS / "construction-preview-after.png")

    preview = _player_holdings(page)
    assert preview == {
        "stone": expected_player.resources.stone,
        "silver": expected_player.resources.silver,
        "wheat": expected_player.resources.wheat,
    }
    assert (
        page.locator(
            f'[data-player="{active_player_id}"] [data-player-board-slot][data-building-id="well"]'
        ).count()
        == 1
    )
    assert {
        player: holdings
        for player, holdings in _all_player_holdings(page).items()
        if player != active_player_id
    } == {
        player: holdings
        for player, holdings in other_players_before.items()
        if player != active_player_id
    }
    assert _confirm_enabled(page)

    page.locator('[data-turn-control="reset"]').click()
    page.wait_for_timeout(100)
    assert _player_holdings(page) == before
    assert (
        page.locator(
            f'[data-player="{active_player_id}"] [data-player-board-slot][data-building-id="well"]'
        ).count()
        == 0
    )

    # The first pass already proves reset restored the preview; Confirm must commit exactly that
    # same state, with no arithmetic in the browser to reconstruct it.
    _click_candidate_prefix(page, candidate, before_kind="resolution")
    _click_candidate_step(
        page, next(step for step in candidate["steps"] if step["kind"] == "resolution")
    )
    building = page.query_selector('[data-building-choice-key="well"][data-turn-offered="true"]')
    assert building is not None
    _click_handle_centre(page, building, require_hit=True)
    page.wait_for_timeout(60)
    page.locator('[data-turn-control="confirm"]').click()
    page.wait_for_timeout(120)
    assert _player_holdings(page, f'[data-player="{active_player_id}"]') == preview
    assert (
        page.locator(
            f'[data-player="{active_player_id}"] [data-player-board-slot][data-building-id="well"]'
        ).count()
        == 1
    )
    assert "well" in server.state.player_state(acting_player).player_board_slots.active_buildings
    page.locator(
        f'[data-player="{active_player_id}"] [data-player-board-slot][data-building-id="well"]'
    ).hover()
    assert "Construct for 1 stone." not in page.locator(
        '[data-building-tooltip-ability="true"]'
    ).inner_text()


def _merchant_visible_at(page, position: int) -> bool:
    return bool(
        page.evaluate(
            """
        position => Array.from(document.querySelectorAll(
          '[data-component="duty-wheel"] [data-token="merchant"]'
        )).some(token => {
          const space = token.closest('[data-board-position-index]');
          return space && Number(space.getAttribute('data-board-position-index')) === position
            && token.getAttribute('opacity') !== '0';
        })
        """,
            position,
        )
    )


def _stage_guild(page):
    guild = page.query_selector(
        '[data-turn-step-building-id="guild"][data-turn-step-offered="true"]'
    )
    assert guild is not None, "Guild was not offered as a committed building step"
    _click_handle_centre(page, guild, require_hit=True)
    page.wait_for_timeout(60)
    return guild


def _visible_turn_text_boxes(page) -> list[dict[str, float | str]]:
    """Every directly written, visible line in the turn box, with its actual painted bounds."""
    return page.locator('[data-component="play-turn"]').evaluate(
        """turn => Array.from(turn.querySelectorAll('*')).filter(node => {
            const directText = Array.from(node.childNodes).some(child =>
              child.nodeType === Node.TEXT_NODE && child.textContent.trim());
            const style = getComputedStyle(node);
            const box = node.getBoundingClientRect();
            return directText && style.display !== 'none' && style.visibility !== 'hidden'
              && box.width > 0 && box.height > 0;
          }).map(node => {
            const box = node.getBoundingClientRect();
            const row = node.closest(
              '[data-turn-step-hire-row], [data-turn-step-direction-row], '
              + '[data-turn-step-resource-row]'
            );
            const rowBox = row && row.getBoundingClientRect();
            return {
              text: node.textContent.trim().replace(/\\s+/g, ' '),
              left: box.left, right: box.right, top: box.top, bottom: box.bottom,
              row: row ? row.getAttribute('data-turn-step-row-active') : null,
              rowTop: rowBox ? rowBox.top : null, rowBottom: rowBox ? rowBox.bottom : null,
            };
          })"""
    )


def _assert_visible_turn_text_lines_do_not_overlap(page) -> None:
    boxes = _visible_turn_text_boxes(page)
    collisions = [
        (left, right)
        for index, left in enumerate(boxes)
        for right in boxes[index + 1 :]
        if left["left"] < right["right"]
        and right["left"] < left["right"]
        and left["top"] < right["bottom"]
        and right["top"] < left["bottom"]
    ]
    assert not collisions, f"visible turn-box text overlaps: {collisions!r}"
    orphaned = [
        box
        for box in boxes
        if box["row"] is not None
        and (
            box["row"] != "true"
            or box["top"] < box["rowTop"]
            or box["bottom"] > box["rowBottom"]
        )
    ]
    assert not orphaned, f"visible turn-box text escaped its active row: {orphaned!r}"


def _commit_guild(page, server) -> int:
    step = next(
        step for step in turn_steps(server.state, server.config) if step.building_id == "guild"
    )
    expected_position = apply_turn_step(server.state, server.config, step).merchant_board_position
    assert _confirm_enabled(page)
    page.locator('[data-turn-control="confirm"]').click()
    page.wait_for_timeout(120)
    assert server.state.merchant_board_position == expected_position
    assert _merchant_visible_at(page, expected_position)
    return expected_position


def test_turn_box_visible_text_lines_do_not_overlap(page, serve) -> None:
    base_url, _server = serve(SCENARIOS / "playtest" / "movement_2p.json")
    page.goto(base_url, wait_until="networkidle")

    _stage_guild(page)
    assert page.locator('[data-turn-step-hire-row="true"]').get_attribute(
        "data-turn-step-row-active"
    ) == "true"
    assert page.locator('[data-turn-step-activation-prompt="true"]').get_attribute(
        "data-turn-step-activation-active"
    ) == "true"
    _assert_visible_turn_text_lines_do_not_overlap(page)


def test_dormitory_prompt_stays_inside_its_active_turn_step_row(page, serve) -> None:
    base_url, _server = serve(SCENARIOS / "playtest" / "movement_2p.json")
    page.goto(base_url, wait_until="networkidle")

    dormitory = page.locator(
        '[data-turn-step-building-id="dormitory"][data-turn-step-offered="true"]'
    ).first
    _click_handle_centre(page, dormitory.element_handle(), require_hit=True)
    page.wait_for_timeout(20)

    _assert_visible_turn_text_lines_do_not_overlap(page)


def test_guild_click_commits_in_the_beginning_window_and_reset_restores_the_turn(
    page, serve
) -> None:
    base_url, server = serve(SCENARIOS / "guild_active_move_merchant_001.json")
    page.goto(base_url, wait_until="networkidle")
    before_position = server.state.merchant_board_position
    _assert_painted_turn_phase(page, "beginning")
    before_box = page.locator('[data-component="play-turn"]').bounding_box()
    assert before_box is not None

    _stage_guild(page)
    _assert_painted_turn_phase(page, "beginning")
    assert page.locator("[data-turn-step-direction-row]").get_attribute(
        "data-turn-step-row-active"
    ) == "true"
    assert page.locator('[data-turn-step-direction][data-turn-step-offered="true"]').count() == 0
    assert (
        page.locator("[data-turn-step-resource-row]").get_attribute("data-turn-step-row-active")
        == "false"
    )
    assert not page.locator("[data-turn-step-resource-row]").is_visible()
    activation_prompt = page.locator("[data-turn-step-activation-prompt]")
    assert activation_prompt.is_visible()
    assert (
        "Activate Guild: move the Merchant clockwise +1 Duty tile."
        in activation_prompt.inner_text()
    )
    staged_box = page.locator('[data-component="play-turn"]').bounding_box()
    assert staged_box is not None
    # The two independent sentences now reserve their wrapped line height instead of occupying
    # one 24px slot. Keeping the old fixed height would restore their overlap.
    assert staged_box["height"] >= before_box["height"]
    _screenshot_turn_prompt(page, SCREENSHOTS / "guild-prompt-staged.png")

    _commit_guild(page, server)
    _assert_painted_turn_phase(page, "beginning")
    _screenshot_turn_prompt(page, SCREENSHOTS / "guild-prompt-committed.png")

    page.locator('[data-turn-control="reset"]').click()
    page.wait_for_timeout(120)
    assert server.state.merchant_board_position == before_position
    assert _merchant_visible_at(page, before_position)
    _assert_painted_turn_phase(page, "beginning")


def test_guild_click_commits_in_the_end_of_turn_window_and_never_asks_about_using_guild(
    page, serve
) -> None:
    base_url, server = serve(SCENARIOS / "guild_active_move_merchant_001.json")
    page.goto(base_url, wait_until="networkidle")
    before_position = server.state.merchant_board_position
    assert "choose whether to use Guild" not in page.content()

    devotion = next(
        candidate
        for candidate in server.payload["turn_candidates"]
        if any(step["kind"] == "resolution" and step["value"] == "clerical_devotion"
               for step in candidate["steps"])
    )
    _click_candidate_prefix(page, devotion, before_kind="resolution")
    _click_candidate_step(
        page, next(step for step in devotion["steps"] if step["kind"] == "resolution")
    )
    page.locator('[data-turn-control="confirm"]').click()
    page.wait_for_timeout(120)

    assert server.state.turn_progress.resolution_committed is True
    _assert_painted_turn_phase(page, "end")
    assert "choose whether to use Guild" not in page.content()
    _stage_guild(page)
    assert "choose whether to use Guild" not in page.content()
    _commit_guild(page, server)
    _assert_painted_turn_phase(page, "end")

    page.locator('[data-turn-control="reset"]').click()
    page.wait_for_timeout(120)
    assert server.state.merchant_board_position == before_position
    assert _merchant_visible_at(page, before_position)
    _assert_painted_turn_phase(page, "beginning")


def _choose_conversion(page, building_id: str, direction: str, amount: int) -> None:
    selector = (
        f'[data-active-seat="true"] [data-turn-step-building-id="{building_id}"]'
        '[data-turn-step-offered="true"]'
    )
    building = page.query_selector(selector)
    if building is None:
        building = page.query_selector(
            f'[data-turn-step-building-id="{building_id}"][data-turn-step-offered="true"]'
        )
    assert building is not None, f"{building_id} conversion building was not offered"
    _click_handle_centre(page, building, require_hit=True)

    hire_payment = page.query_selector(
        '[data-turn-step-hire-payment][data-turn-step-hire-offered="true"]'
    )
    if hire_payment is not None:
        _click_handle_centre(page, hire_payment, require_hit=True)

    direction_key = page.query_selector(
        f'[data-turn-step-direction="{direction}"][data-turn-step-offered="true"]'
    )
    assert direction_key is not None, f"{direction} was not offered for {building_id}"
    _click_handle_centre(page, direction_key, require_hit=True)

    if building_id == "indulgences":
        destination = page.query_selector(
            '[data-piety-choice-pill][data-piety-choice-offered="true"]'
        )
        assert destination is not None, f"no piety destination was offered for {direction}"
        _click_handle_centre(page, destination, require_hit=True)
        return
    resource = "stone" if building_id == "stone_yard" else "wheat"
    for _ in range(amount):
        resource_key = page.query_selector(
            f'[data-resource-choice-key="{resource}"][data-turn-offered="true"]'
        )
        assert resource_key is not None, f"{resource} pill was not offered for {direction}"
        _click_handle_centre(page, resource_key, require_hit=True)


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


def _lit_acolytes_at(page, player_id: str, position: int) -> int:
    return page.locator(
        f'[data-board-position-index="{position}"] '
        f'[data-cube-tally] rect[data-player="{player_id}"][opacity="1"]'
    ).count()


def _turn_state_snapshot(page) -> dict[str, object]:
    """A compact view of what the page currently offers and enables in the turn UI."""
    return {
        "origins": page.locator(
            '[data-board-position-index][data-turn-start-candidate="true"]'
        ).count(),
        "relocation_targets": page.locator(
            '[data-board-position-index][data-turn-step-relocation-candidate="true"]'
        ).count(),
        "skips": page.locator(
            '[data-board-position-index][data-turn-skip-candidate="true"]'
        ).count(),
        "duties": page.locator(
            '[data-board-position-index][data-turn-duty-candidate="true"]'
        ).count(),
        "arrows": page.locator('[data-arrow][data-turn-offered="true"]').count(),
        "resolution_keys": page.locator(
            '[data-resolution-key][data-turn-offered="true"]'
        ).all_inner_texts(),
        "combination_keys": page.locator(
            '[data-combination-key][data-turn-offered="true"]'
        ).all_inner_texts(),
        "resource_keys": page.locator(
            '[data-resource-choice-key][data-turn-offered="true"]'
        ).count(),
        "seat_keys": page.locator(
            '[data-seat-choice-key][data-turn-offered="true"]'
        ).all_inner_texts(),
        "building_keys": page.locator(
            '[data-building-choice-key][data-turn-offered="true"]'
        ).all_inner_texts(),
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

    assert (
        page.eval_on_selector('[data-seat-row="3"]', "row => getComputedStyle(row).display")
        == "none"
    )
    assert (
        page.eval_on_selector('[data-seat-row="4"]', "row => getComputedStyle(row).display")
        == "none"
    )


def test_setup_test_position_dropdown_selects_and_starts_that_game(page, serve) -> None:
    base_url, _server = serve(None)
    page.goto(base_url, wait_until="networkidle")

    dropdown = page.locator("#test_position")
    assert dropdown.count() == 1, "setup page did not render test position dropdown"
    option_values = page.eval_on_selector_all(
        "#test_position option",
        "nodes => nodes.map(node => ({ value: node.value, text: node.textContent || '' }))",
    )
    assert any(option["value"] == "" for option in option_values), (
        "fresh-game blank option is missing"
    )
    assert any(option["value"] == PLAYTEST_CLOISTERS for option in option_values), (
        "playtest scenario is missing from dropdown"
    )
    assert any(option["value"] == PLAYTEST_CLOISTERS_LOOP for option in option_values), (
        "loop playtest scenario is missing from dropdown"
    )
    assert any(option["value"] == PLAYTEST_KOGGE_AND_CLOISTERS for option in option_values), (
        "kogge+cloisters playtest scenario is missing from dropdown"
    )
    assert any(option["value"] == PLAYTEST_CONVERSIONS for option in option_values), (
        "conversion playtest scenario is missing from dropdown"
    )

    page.select_option("#test_position", PLAYTEST_CLOISTERS)
    assert page.get_attribute("#player_count", "disabled") is not None
    assert page.get_attribute("#seed", "disabled") is not None
    assert (
        page.eval_on_selector('[data-seat-row="3"]', "row => getComputedStyle(row).display")
        == "none"
    )

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
        route_toggle="cloisters",
    )
    skip_target = page.query_selector(
        '[data-board-position-index][data-turn-skip-candidate="true"]'
    )
    assert skip_target is not None, "loaded test position never offered a Cloisters skip target"
    _click_handle_centre(page, skip_target, require_hit=True)
    page.wait_for_timeout(20)
    assert page.locator('[data-board-position-index][data-turn-skip-candidate="true"]').count() == 0


@pytest.mark.parametrize(
    "position_name",
    [PLAYTEST_CLOISTERS, PLAYTEST_CLOISTERS_LOOP, PLAYTEST_KOGGE_AND_CLOISTERS],
)
def test_setup_test_position_dropdown_each_playtest_position_starts(
    page, serve, position_name: str
) -> None:
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

    city_origin = page.query_selector(
        '[data-board-position-index="0"][data-turn-start-candidate="true"]'
    )
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
            and any(
                step["kind"] == "origin" and int(step["value"]) == 0 for step in offered["steps"]
            )
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
    city_origin = page.query_selector(
        '[data-board-position-index="0"][data-turn-start-candidate="true"]'
    )
    assert city_origin is not None, "city should be offered as a start origin"
    cloisters = page.locator('[data-building-id="cloisters"]').first
    assert cloisters.get_attribute("data-turn-family-state") == "owned"
    assert cloisters.get_attribute("data-turn-family-available") == "false"
    _click_handle_centre(page, city_origin, require_hit=True)
    page.wait_for_timeout(20)

    for edge_value in edge_values:
        edge = page.query_selector(f'[data-arrow="{edge_value}"][data-turn-offered="true"]')
        if edge is not None:
            _click_handle_centre(page, edge, require_hit=True)
            page.wait_for_timeout(20)

    city_skip = page.query_selector(
        '[data-board-position-index="0"][data-turn-skip-candidate="true"]'
    )
    assert city_skip is not None, "city revisit was not offered as a skip target"
    _click_handle_centre(page, city_skip, require_hit=True)
    page.wait_for_timeout(20)

    assert (
        page.locator('[data-board-position-index][data-turn-skip-candidate="true"]').count() == 0
    ), "city skip click did not settle the skip question"
    assert (
        page.locator('[data-board-position-index][data-turn-duty-candidate="true"]').count() > 0
    ), "duty question did not follow city skip selection"


def test_dormitory_step_stages_a_target_confirms_and_reset_restores_it(page, serve) -> None:
    base_url, server = serve(SCENARIOS / "playtest" / "movement_2p.json")
    page.goto(base_url, wait_until="networkidle")
    turn_start = server.state
    prompt = page.locator('[data-component="play-turn"]')
    height_before = prompt.bounding_box()["height"]

    opening = _turn_state_snapshot(page)
    assert opening["relocation_targets"] == 0, opening
    dormitory = page.locator(
        '[data-turn-step-building-id="dormitory"][data-turn-step-offered="true"]'
    ).first
    assert dormitory.count() == 1, "Dormitory was not offered as a committed building step"
    _click_handle_centre(page, dormitory.element_handle(), require_hit=True)
    page.wait_for_timeout(20)

    relocation_targets = page.locator(
        '[data-board-position-index][data-turn-step-relocation-candidate="true"]'
    )
    assert relocation_targets.count() == 1, "Dormitory did not offer its occupied Duty target"
    # The prompt now grows its own row rather than escaping the fixed-height answer row below it.
    assert prompt.bounding_box()["height"] >= height_before
    _screenshot_turn_prompt(page, SCREENSHOTS / "dormitory-prompt-staged.png")
    _click_handle_centre(
        page,
        page.locator('[data-turn-control="reset"]').element_handle(),
        require_hit=True,
    )
    page.wait_for_timeout(20)
    assert server.state == turn_start
    assert _turn_state_snapshot(page)["relocation_targets"] == 0

    dormitory = page.locator(
        '[data-turn-step-building-id="dormitory"][data-turn-step-offered="true"]'
    ).first
    _click_handle_centre(page, dormitory.element_handle(), require_hit=True)
    page.wait_for_timeout(20)
    relocation_targets = page.locator(
        '[data-board-position-index][data-turn-step-relocation-candidate="true"]'
    )
    relocation_target = relocation_targets.first.element_handle()
    assert relocation_target is not None
    chosen_target = int(relocation_target.get_attribute("data-board-position-index"))
    active_player_id = page.get_attribute('[data-active-seat="true"]', "data-player")
    assert active_player_id is not None
    target_before = _lit_acolytes_at(page, active_player_id, chosen_target)
    city = server.config.board.index_for_name("city")
    city_before = _lit_city_slots_for_player(page, active_player_id)
    _click_handle_centre(page, relocation_target, require_hit=True)
    page.wait_for_timeout(20)

    assert _confirm_enabled(page)
    assert _lit_acolytes_at(page, active_player_id, chosen_target) == target_before - 1
    assert _lit_city_slots_for_player(page, active_player_id) == city_before + 1
    _click_handle_centre(
        page,
        page.locator('[data-turn-control="reset"]').element_handle(),
        require_hit=True,
    )
    page.wait_for_timeout(20)
    assert server.state == turn_start
    assert _lit_acolytes_at(page, active_player_id, chosen_target) == target_before
    assert _lit_city_slots_for_player(page, active_player_id) == city_before

    dormitory = page.locator(
        '[data-turn-step-building-id="dormitory"][data-turn-step-offered="true"]'
    ).first
    _click_handle_centre(page, dormitory.element_handle(), require_hit=True)
    page.wait_for_timeout(20)
    relocation_target = page.locator(
        '[data-board-position-index][data-turn-step-relocation-candidate="true"]'
    ).first.element_handle()
    assert relocation_target is not None
    _click_handle_centre(page, relocation_target, require_hit=True)
    page.wait_for_timeout(20)

    turn_step_requests = []

    def record_turn_step_request(request) -> None:
        if request.method == "POST" and request.url.endswith("/turn-step"):
            turn_step_requests.append(request)

    page.on("request", record_turn_step_request)
    assert _confirm_enabled(page)
    _click_handle_point(
        page,
        page.locator('[data-turn-control="confirm"]').element_handle(),
        0.5,
        0.2,
    )
    page.wait_for_function(
        """() => document.querySelector('[data-turn-step-building-id="dormitory"]')
          .getAttribute('data-turn-step-used') === 'true'"""
    )
    assert len(turn_step_requests) == 1, "an enabled Confirm must issue its /turn-step request"
    assert server.state != turn_start
    assert server.state.player_vector(server.state.active_player)[chosen_target] == (
        turn_start.player_vector(turn_start.active_player)[chosen_target] - 1
    )
    assert server.state.player_vector(server.state.active_player)[city] == (
        turn_start.player_vector(turn_start.active_player)[city] + 1
    )
    assert "dormitory" in server.state.turn_progress.used_buildings
    assert _lit_acolytes_at(page, active_player_id, chosen_target) == target_before - 1
    _screenshot_turn_prompt(page, SCREENSHOTS / "dormitory-prompt-committed.png")


def test_dormitory_preview_removes_the_top_acolyte_from_a_multi_cube_source(page, serve) -> None:
    """The preview removes from the same stack end that its destination placement fills."""
    base_url, server = serve(SCENARIOS / "playtest" / "movement_2p.json")
    dormitory_step = next(
        step for step in server.payload["turn_steps"] if step["building_id"] == "dormitory"
    )
    source = int(dormitory_step["selected_position"])
    active_player = server.state.active_player
    vector = list(server.state.player_vector(active_player))
    vector[source] += 1
    server.state = server.state.with_player_vector(active_player, tuple(vector))
    server._refresh()

    page.goto(base_url, wait_until="networkidle")
    player_id = page.get_attribute('[data-active-seat="true"]', "data-player")
    assert player_id is not None

    def source_cubes() -> list[dict[str, object]]:
        return page.locator(
            f'[data-board-position-index="{source}"] '
            f'[data-cube-tally] rect[data-player="{player_id}"]'
        ).evaluate_all(
            """cubes => cubes.map((cube, index) => ({
              index,
              y: Number(cube.getAttribute('y')),
              opacity: cube.getAttribute('opacity'),
            }))"""
        )

    before = source_cubes()
    visible_before = [cube for cube in before if cube["opacity"] != "0"]
    assert len(visible_before) >= 2, "fixture did not stage a multi-acolyte Dormitory source"

    dormitory = page.locator(
        '[data-turn-step-building-id="dormitory"][data-turn-step-offered="true"]'
    ).first
    _click_handle_centre(page, dormitory.element_handle(), require_hit=True)
    relocation_target = page.locator(
        f'[data-board-position-index="{source}"][data-turn-step-relocation-candidate="true"]'
    ).first
    _click_handle_centre(page, relocation_target.element_handle(), require_hit=True)
    page.wait_for_timeout(20)

    after = source_cubes()
    hidden = [
        before_cube
        for before_cube, after_cube in zip(before, after, strict=True)
        if before_cube["opacity"] != "0" and after_cube["opacity"] == "0"
    ]
    assert hidden == [min(visible_before, key=lambda cube: cube["y"])], (
        "Dormitory preview hid a bottom cube instead of the stack's top visible cube"
    )


@pytest.mark.parametrize(
    ("building_id", "answer_count", "target_delta", "city_delta"),
    (
        ("dormitory", 2, -1, 1),
        ("inquisition", 3, 1, -1),
    ),
)
def test_relocation_preview_waits_for_every_server_answer(
    page, serve, building_id, answer_count, target_delta, city_delta
) -> None:
    """A preview follows the server's answer list, not the old two-answer relocation shape."""
    base_url, server = serve(SCENARIOS / "playtest" / "movement_2p.json")
    relocation_steps = [
        step for step in server.payload["turn_steps"] if step["building_id"] == building_id
    ]
    assert {len(step["answers"]) for step in relocation_steps} == {answer_count}

    page.goto(base_url, wait_until="networkidle")
    building = page.locator(
        f'[data-turn-step-building-id="{building_id}"][data-turn-step-offered="true"]'
    ).first
    assert building.count() == 1
    _click_handle_centre(page, building.element_handle(), require_hit=True)
    page.wait_for_timeout(20)

    target = page.locator(
        '[data-board-position-index][data-turn-step-relocation-candidate="true"]'
    ).first
    assert target.count() == 1
    position = int(target.get_attribute("data-board-position-index"))
    player_id = page.get_attribute('[data-active-seat="true"]', "data-player")
    assert player_id is not None
    target_before = _lit_acolytes_at(page, player_id, position)
    city_before = _lit_city_slots_for_player(page, player_id)

    _click_handle_centre(page, target.element_handle(), require_hit=True)
    page.wait_for_timeout(20)

    assert _confirm_enabled(page)
    assert _lit_acolytes_at(page, player_id, position) == target_before + target_delta
    assert _lit_city_slots_for_player(page, player_id) == city_before + city_delta


def test_library_step_stages_and_confirms_duty_with_preview_and_reset(page, serve) -> None:
    base_url, server = serve(SCENARIOS / "playtest" / "movement_2p.json")
    page.goto(base_url, wait_until="networkidle")
    turn_step_requests = []

    def record_turn_step_request(request) -> None:
        if request.method == "POST" and request.url.endswith("/turn-step"):
            turn_step_requests.append(request)

    page.on("request", record_turn_step_request)

    def stage_library():
        active_player = page.get_attribute('[data-active-seat="true"]', "data-player")
        assert active_player is not None
        city_before = _lit_city_slots_for_player(page, active_player)
        library = page.locator(
            '[data-turn-step-building-id="library"][data-turn-step-offered="true"]'
        ).first
        _click_handle_centre(page, library.element_handle(), require_hit=True)
        page.wait_for_timeout(20)
        return active_player, city_before

    def reset_to_turn_start() -> None:
        turn_start = server._turn_start_state
        assert turn_start is not None
        _click_handle_centre(
            page,
            page.locator('[data-turn-control="reset"]').element_handle(),
            require_hit=True,
        )
        page.wait_for_function(
            """() => {
              const city = document.querySelector('[data-board-position-index="0"]');
              return city && city.getAttribute('data-turn-start-candidate') === 'true';
            }"""
        )
        assert server.state == turn_start

    _reach_movement_library_window(page)

    expected_prompt = next(
        step["prompt"] for step in server.payload["turn_steps"] if step["building_id"] == "library"
    )
    active_player, city_before = stage_library()
    assert page.locator('[data-turn-step-activation-prompt="true"]').inner_text() == expected_prompt
    assert page.locator('[data-turn-step-resource-row="true"]').get_attribute(
        "data-turn-step-row-active"
    ) == "false"
    assert not page.locator('[data-turn-step-answer-label="true"]').is_visible()
    duty_targets = page.locator(
        '[data-board-position-index][data-turn-step-relocation-candidate="true"]'
    )
    assert duty_targets.count() == len(server.config.duty_positions()), (
        "Library did not light every non-City Duty target"
    )
    duty_target = duty_targets.first
    duty_position = int(duty_target.get_attribute("data-board-position-index"))
    duty_before = _lit_acolytes_at(page, active_player, duty_position)
    _click_handle_centre(page, duty_target.element_handle(), require_hit=True)
    page.wait_for_timeout(20)
    assert _confirm_enabled(page), "a complete Library Duty relocation did not enable Confirm"
    assert _lit_acolytes_at(page, active_player, duty_position) == duty_before + 1
    assert _lit_city_slots_for_player(page, active_player) == city_before - 1
    _screenshot_turn_prompt(page, SCREENSHOTS / "library-prompt-staged-duty.png")
    reset_to_turn_start()

    _reach_movement_library_window(page)
    active_player, city_before = stage_library()
    duty_target = page.locator(
        '[data-board-position-index][data-turn-step-relocation-candidate="true"]'
    ).first
    duty_position = int(duty_target.get_attribute("data-board-position-index"))
    duty_before = _lit_acolytes_at(page, active_player, duty_position)
    step_start = server.state
    state_token = server.payload["state_token"]
    requests_before = len(turn_step_requests)
    _click_handle_centre(page, duty_target.element_handle(), require_hit=True)
    page.wait_for_timeout(20)
    _click_handle_point(
        page,
        page.locator('[data-turn-control="confirm"]').element_handle(),
        0.5,
        0.2,
    )
    page.wait_for_function(
        "token => !document.documentElement.innerHTML.includes(token)", arg=state_token
    )
    assert len(turn_step_requests) == requests_before + 1
    assert server.state != step_start
    assert server.state.player_vector(server.state.active_player)[duty_position] == (
        step_start.player_vector(step_start.active_player)[duty_position] + 1
    )
    assert server.state.player_vector(server.state.active_player)[
        server.config.board.index_for_name("city")
    ] == step_start.player_vector(step_start.active_player)[server.config.board.index_for_name("city")] - 1
    assert _lit_acolytes_at(page, active_player, duty_position) == duty_before + 1
    assert _lit_city_slots_for_player(page, active_player) == city_before - 1
    reset_to_turn_start()


def test_library_step_stages_and_confirms_abbey_with_preview_and_reset(page, serve) -> None:
    base_url, server = serve(SCENARIOS / "playtest" / "movement_2p.json")
    page.goto(base_url, wait_until="networkidle")
    turn_step_requests = []

    def record_turn_step_request(request) -> None:
        if request.method == "POST" and request.url.endswith("/turn-step"):
            turn_step_requests.append(request)

    page.on("request", record_turn_step_request)

    def stage_library():
        active_player = page.get_attribute('[data-active-seat="true"]', "data-player")
        assert active_player is not None
        city_before = _lit_city_slots_for_player(page, active_player)
        library = page.locator(
            '[data-turn-step-building-id="library"][data-turn-step-offered="true"]'
        ).first
        _click_handle_centre(page, library.element_handle(), require_hit=True)
        page.wait_for_timeout(20)
        return active_player, city_before

    def reset_to_turn_start() -> None:
        turn_start = server._turn_start_state
        assert turn_start is not None
        _click_handle_centre(
            page,
            page.locator('[data-turn-control="reset"]').element_handle(),
            require_hit=True,
        )
        page.wait_for_function(
            """() => {
              const city = document.querySelector('[data-board-position-index="0"]');
              return city && city.getAttribute('data-turn-start-candidate') === 'true';
            }"""
        )
        assert server.state == turn_start

    _reach_movement_library_window(page)
    active_player, city_before = stage_library()
    expected_prompt = next(
        step["prompt"] for step in server.payload["turn_steps"] if step["building_id"] == "library"
    )
    assert page.locator('[data-turn-step-activation-prompt="true"]').inner_text() == expected_prompt
    assert page.locator('[data-turn-step-resource-row="true"]').get_attribute(
        "data-turn-step-row-active"
    ) == "false"
    abbey_before = _visible_active_token_count(page, "abbey")
    abbey = page.locator(
        '[data-active-seat="true"][data-end-relocation-choice="true"] '
        '[data-token="abbey"][opacity="1"]'
    ).first
    assert abbey.count() == 1, "Library did not light Abbey as a relocation target"
    _click_handle_centre(page, abbey.element_handle(), require_hit=True)
    page.wait_for_timeout(20)
    assert _confirm_enabled(page), "a complete Library Abbey relocation did not enable Confirm"
    assert _visible_active_token_count(page, "abbey") == abbey_before + 1
    assert _lit_city_slots_for_player(page, active_player) == city_before - 1
    _screenshot_turn_prompt(page, SCREENSHOTS / "library-prompt-staged-abbey.png")
    reset_to_turn_start()

    _reach_movement_library_window(page)
    active_player, city_before = stage_library()
    abbey_before = _visible_active_token_count(page, "abbey")
    abbey = page.locator(
        '[data-active-seat="true"][data-end-relocation-choice="true"] '
        '[data-token="abbey"][opacity="1"]'
    ).first
    step_start = server.state
    state_token = server.payload["state_token"]
    requests_before = len(turn_step_requests)
    _click_handle_centre(page, abbey.element_handle(), require_hit=True)
    page.wait_for_timeout(20)
    _click_handle_point(
        page,
        page.locator('[data-turn-control="confirm"]').element_handle(),
        0.5,
        0.2,
    )
    page.wait_for_function(
        "token => !document.documentElement.innerHTML.includes(token)", arg=state_token
    )
    assert len(turn_step_requests) == requests_before + 1
    assert server.state != step_start
    assert server.state.player_state(server.state.active_player).workforce.abbey == (
        step_start.player_state(step_start.active_player).workforce.abbey + 1
    )
    city = server.config.board.index_for_name("city")
    assert server.state.player_vector(server.state.active_player)[city] == (
        step_start.player_vector(step_start.active_player)[city] - 1
    )
    assert _visible_active_token_count(page, "abbey") == abbey_before + 1
    assert _lit_city_slots_for_player(page, active_player) == city_before - 1


def test_confirm_needs_one_turn_action_or_a_complete_committed_step(page, serve) -> None:
    """A real disabled click does nothing; an enabled Confirm always sends its matching request."""
    base_url, server = serve(SCENARIOS / "playtest" / "movement_2p.json")
    page.goto(base_url, wait_until="networkidle")
    opening_state = server.state
    requests: list[str] = []

    def record_request(request) -> None:
        if request.method == "POST" and request.url.rsplit("/", 1)[-1] in {"action", "turn-step"}:
            requests.append(request.url)

    page.on("request", record_request)

    confirm = page.query_selector('[data-turn-control="confirm"]')
    assert confirm is not None
    assert not _confirm_enabled(page)
    _click_handle_point(page, confirm, 0.5, 0.2)
    page.wait_for_timeout(50)
    assert requests == [], "a disabled opening Confirm sent a request"
    assert server.state == opening_state

    dormitory = page.query_selector(
        '[data-turn-step-building-id="dormitory"][data-turn-step-offered="true"]'
    )
    assert dormitory is not None
    _click_handle_centre(page, dormitory, require_hit=True)
    page.wait_for_timeout(20)
    assert not _confirm_enabled(page), (
        "staging Dormitory enabled Confirm before a target was chosen"
    )
    confirm = page.query_selector('[data-turn-control="confirm"]')
    assert confirm is not None
    _click_handle_point(page, confirm, 0.5, 0.2)
    page.wait_for_timeout(50)
    assert requests == [], "an incomplete Dormitory relocation sent a request"
    assert server.state == opening_state

    target = page.query_selector(
        '[data-board-position-index][data-turn-step-relocation-candidate="true"]'
    )
    assert target is not None
    _click_handle_centre(page, target, require_hit=True)
    page.wait_for_timeout(20)
    assert _confirm_enabled(page), "a complete Dormitory relocation did not enable Confirm"
    confirm = page.query_selector('[data-turn-control="confirm"]')
    assert confirm is not None
    _click_handle_point(page, confirm, 0.5, 0.2)
    page.wait_for_function(
        """() => document.querySelector('[data-turn-step-building-id="dormitory"]')
          .getAttribute('data-turn-step-used') === 'true'"""
    )
    assert len(requests) == 1 and requests[0].endswith("/turn-step"), (
        "an enabled Dormitory Confirm did not send its /turn-step request"
    )
    assert server.state != opening_state

    after_dormitory = server.state
    assert not _confirm_enabled(page), "Confirm stayed enabled after committing Dormitory"
    confirm = page.query_selector('[data-turn-control="confirm"]')
    assert confirm is not None
    _click_handle_point(page, confirm, 0.5, 0.2)
    page.wait_for_timeout(50)
    assert len(requests) == 1, "a disabled post-Dormitory Confirm sent a request"
    assert server.state == after_dormitory

    for _ in range(80):
        if _confirm_enabled(page):
            break
        offered = _next_offered_from_dom(page)
        assert offered is not None, "no offered choice remained while narrowing a turn action"
        assert offered.get_attribute("data-turn-control") != "confirm"
        _click_handle_centre(page, offered, require_hit=True)
        page.wait_for_timeout(20)
    else:
        raise AssertionError("the normal turn action did not narrow to an enabled Confirm")

    # A taxation step requiring zero resources has no control to press, but it remains visible as
    # the current engine question and Confirm still has exactly the action it will submit.
    assert page.locator('[data-turn-panel][data-turn-shown="true"]').count() == 0
    assert page.locator('[data-turn-prompt][data-turn-offered="true"]').inner_text() == (
        "Red: Taxation step 2. No other Duty tile is a majority."
    )
    before_action_token = server.payload["state_token"]
    confirm = page.query_selector('[data-turn-control="confirm"]')
    assert confirm is not None
    _click_handle_point(page, confirm, 0.5, 0.2)
    page.wait_for_function(
        "token => !document.documentElement.innerHTML.includes(token)", arg=before_action_token
    )
    assert len(requests) == 2 and requests[-1].endswith("/action"), (
        "an enabled normal-turn Confirm did not send its /action request"
    )
    assert server.state != after_dormitory


def test_confirm_paints_the_action_that_its_next_press_will_take(page, serve) -> None:
    base_url, _server = serve(SCENARIOS / "playtest" / "movement_2p.json")
    page.goto(base_url, wait_until="networkidle")

    origin = page.query_selector(
        '[data-board-position-index="0"][data-turn-start-candidate="true"]'
    )
    assert origin is not None, "movement_2p did not offer its opening sow origin"
    _click_handle_centre(page, origin, require_hit=True)
    page.wait_for_timeout(20)
    assert _painted_confirm_label(page) == "Confirm", "Sow painted a label that would pass the turn"

    page.reload(wait_until="networkidle")
    _reach_movement_library_window(page)
    _assert_painted_turn_phase(page, "end")
    assert _painted_confirm_label(page) == "End turn", (
        "the End-of-Turn Confirm did not say what its next press would do"
    )
    assert _confirm_enabled(page), "the direct End-of-Turn Confirm was not enabled"
    full_page = page.evaluate(
        """() => ({
            width: document.documentElement.scrollWidth,
            height: document.documentElement.scrollHeight,
        })"""
    )
    assert full_page == page.viewport_size, (
        "the End of Turn screenshot no longer covers the entire play page"
    )
    page.screenshot(path=str(SCREENSHOTS / "end-turn-confirm-label.png"))

    library = page.query_selector(
        '[data-turn-step-building-id="library"][data-turn-step-offered="true"]'
    )
    assert library is not None, "Library was not offered in its End of Turn window"
    _click_handle_centre(page, library, require_hit=True)
    page.wait_for_timeout(20)
    assert _painted_confirm_label(page) == "Confirm", (
        "a staged End of Turn step still painted the pass label"
    )
    turn_box = page.locator('[data-component="play-turn"]').bounding_box()
    activation_prompt = page.locator('[data-turn-step-activation-prompt="true"]').bounding_box()
    assert turn_box is not None and activation_prompt is not None
    for index in range(page.locator('[data-turn-control]').count()):
        control = page.locator('[data-turn-control]').nth(index).bounding_box()
        assert control is not None
        assert (
            turn_box["x"] <= control["x"]
            and turn_box["y"] <= control["y"]
            and control["x"] + control["width"] <= turn_box["x"] + turn_box["width"]
            and control["y"] + control["height"] <= turn_box["y"] + turn_box["height"]
        ), "a turn control escaped the turn box after the Library prompt wrapped"
        assert (
            activation_prompt["x"] + activation_prompt["width"] <= control["x"]
            or control["x"] + control["width"] <= activation_prompt["x"]
            or activation_prompt["y"] + activation_prompt["height"] <= control["y"]
            or control["y"] + control["height"] <= activation_prompt["y"]
        ), "the Library activation prompt overlapped a turn control"


def test_two_rapid_real_confirm_clicks_send_one_request(page, serve) -> None:
    """The second pointer event must not pass the freshly replaced End of Turn window."""
    base_url, _server = serve(SCENARIOS / "playtest" / "movement_2p.json")
    page.goto(base_url, wait_until="networkidle")
    _narrow_movement_library_turn_to_confirm(page)
    requests: list[str] = []

    def record_request(request) -> None:
        if request.method == "POST" and request.url.rsplit("/", 1)[-1] == "action":
            requests.append(request.url)

    page.on("request", record_request)
    confirm = page.query_selector('[data-turn-control="confirm"][data-turn-control-enabled="true"]')
    assert confirm is not None, "the narrowed action did not enable Confirm"
    x, y = _centre(page, confirm)
    y -= confirm.bounding_box()["height"] * 0.4
    assert _is_hit_target(page, confirm, x, y), "Confirm's visible upper edge was not its click target"
    page.mouse.click(x, y)
    page.mouse.click(x, y)
    page.wait_for_timeout(100)

    assert len(requests) == 1, "two rapid enabled Confirm clicks sent more than one request"


def test_a_refused_submission_releases_the_in_flight_guard(page, serve) -> None:
    base_url, server = serve(SCENARIOS / "playtest" / "movement_2p.json")
    page.goto(base_url, wait_until="networkidle")
    _reach_movement_library_window(page)
    stale_token = server.payload["state_token"]
    server.apply(action_id(EndTurnAction()), stale_token)
    requests: list[str] = []
    dialogs: list[str] = []

    def record_request(request) -> None:
        if request.method == "POST" and request.url.rsplit("/", 1)[-1] == "action":
            requests.append(request.url)

    def dismiss_refusal(dialog) -> None:
        dialogs.append(dialog.message)
        dialog.dismiss()

    page.on("request", record_request)
    page.on("dialog", dismiss_refusal)
    confirm = page.query_selector('[data-turn-control="confirm"][data-turn-control-enabled="true"]')
    assert confirm is not None, "the stale page did not retain its enabled End turn control"
    _click_handle_centre(page, confirm, require_hit=True)
    page.wait_for_timeout(100)
    assert dialogs and dialogs[-1].startswith("refused:"), "the stale submission was not refused"
    assert _confirm_enabled(page), "a refused submission left the still-painted control disabled"
    _click_handle_centre(page, confirm, require_hit=True)
    page.wait_for_timeout(100)
    assert len(requests) == 2, "the control stayed dead after its refusal alert was dismissed"


def test_pointer_focused_svg_buildings_have_no_mouse_focus_outline(page, serve) -> None:
    base_url, _server = serve(SCENARIOS / "playtest" / "movement_2p.json")
    page.goto(base_url, wait_until="networkidle")

    map_building = page.query_selector('#setup-fills g[data-building-id]')
    assert map_building is not None
    map_fill = map_building.query_selector("polygon")
    assert map_fill is not None
    _click_handle_point(page, map_fill, 0.1, 0.5)
    map_focus = page.evaluate(
        """target => ({
            withinBuilding: target.contains(document.activeElement),
            outline: getComputedStyle(document.activeElement).outlineStyle,
        })""",
        map_building,
    )
    assert map_focus["withinBuilding"], "the map-building click did not focus its SVG building"
    assert map_focus["outline"] == "none", "a mouse-focused map building retained its focus outline"

    board_building = page.query_selector(
        '[data-component="player-board-v2"] g[data-player-board-slot][data-building-id="cloisters"]'
    )
    assert board_building is not None
    _click_handle_centre(page, board_building, require_hit=True)
    board_focus = page.evaluate(
        """target => ({
            withinBuilding: target.contains(document.activeElement),
            outline: getComputedStyle(document.activeElement).outlineStyle,
        })""",
        board_building,
    )
    assert board_focus["withinBuilding"], "the player-board click did not focus its SVG building"
    assert board_focus["outline"] == "none", (
        "a mouse-focused player-board building retained its focus outline"
    )


def test_relocation_prompt_grows_its_own_step_row(page, serve) -> None:
    base_url, server = serve(SCENARIOS / "playtest" / "movement_2p.json")
    page.goto(base_url, wait_until="networkidle")
    prompt = page.locator('[data-component="play-turn"]')
    height_before = prompt.bounding_box()["height"]
    expected = next(
        step["prompt"]
        for step in server.payload["turn_steps"]
        if step["building_id"] == "dormitory"
    )

    dormitory = page.locator(
        '[data-turn-step-building-id="dormitory"][data-turn-step-offered="true"]'
    ).first
    _click_handle_centre(page, dormitory.element_handle(), require_hit=True)
    page.wait_for_timeout(20)

    answer_row = page.locator('[data-turn-step-resource-row="true"]')
    step_prompt = page.locator('[data-turn-step-activation-prompt]')
    assert not answer_row.is_visible()
    assert step_prompt.inner_text() == expected
    assert step_prompt.is_visible()
    assert prompt.bounding_box()["height"] >= height_before


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

    city_origin = page.query_selector(
        '[data-board-position-index="0"][data-turn-start-candidate="true"]'
    )
    assert city_origin is not None, "city origin was not offered"
    _click_handle_centre(page, city_origin, require_hit=True)
    page.wait_for_timeout(20)
    _show_hired_route_building_if_available(page, "kogge")

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
            and any(
                step["kind"] == "origin" and int(step["value"]) == 0 for step in offered["steps"]
            )
            and any(step["kind"] == "skip" for step in offered["steps"])
            and any(
                step["kind"] == "edge" and str(step["value"]) in against_flow_edges
                for step in offered["steps"]
            )
        ),
        None,
    )
    assert candidate is not None, (
        "playtest offered no settled city-origin candidate using north/south->city"
    )
    edge_values = [str(step["value"]) for step in candidate["steps"] if step["kind"] == "edge"]
    against_indexes = [
        index for index, value in enumerate(edge_values) if value in against_flow_edges
    ]
    assert against_indexes, "chosen candidate did not include an against-flow City-entry edge"
    assert min(against_indexes) > 0, (
        "against-flow City-entry edge was not reached from the City route"
    )
    assert max(against_indexes) < len(edge_values) - 1, "route did not continue after entering City"
    skip_value = next(int(step["value"]) for step in candidate["steps"] if step["kind"] == "skip")
    duty_value = next(int(step["value"]) for step in candidate["steps"] if step["kind"] == "duty")

    page.goto(base_url, wait_until="networkidle")
    city_origin = page.query_selector(
        '[data-board-position-index="0"][data-turn-start-candidate="true"]'
    )
    assert city_origin is not None, "city origin was not offered"
    _click_handle_centre(page, city_origin, require_hit=True)
    page.wait_for_timeout(20)
    _show_hired_route_building_if_available(page, "kogge")
    _show_hired_route_building_if_available(page, "cloisters")

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

    assert (
        page.locator('[data-board-position-index][data-turn-duty-candidate="true"]').count() == 0
    ), "duty choice did not settle after clicking the duty target"
    after = _turn_state_snapshot(page)
    assert (
        after["action_enabled"] == "true"
        or after["tithe_enabled"] == "true"
        or len(after["resolution_keys"]) > 0
        or _confirm_enabled(page)
    ), "turn did not advance beyond the duty choice after route and skip"


def test_plain_route_prefix_keeps_extending_cloisters_routes_live_and_clickable(
    page, serve
) -> None:
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
    cloisters = page.locator('[data-building-id="cloisters"]').first
    assert cloisters.get_attribute("data-turn-family-state") == "owned"
    assert cloisters.get_attribute("data-turn-family-available") == "false"
    _click_handle_centre(page, origin_target, require_hit=True)

    for edge in plain_edges:
        edge_target = page.query_selector(f'[data-arrow="{edge}"][data-turn-offered="true"]')
        if edge_target is not None:
            _click_handle_centre(page, edge_target, require_hit=True)
            page.wait_for_timeout(20)

    assert (
        page.locator('[data-board-position-index][data-turn-duty-candidate="true"]').count() > 0
    ), "plain route completion did not make any duty selectable"
    extending_edge = cloisters_edges[-1]
    extending_target = page.query_selector(
        f'[data-arrow="{extending_edge}"][data-turn-offered="true"]'
    )
    assert extending_target is not None, (
        "Cloisters extension edge disappeared when the plain route finished"
    )
    _click_handle_centre(page, extending_target, require_hit=True)
    page.wait_for_timeout(20)
    assert (
        page.locator('[data-board-position-index][data-turn-skip-candidate="true"]').count() > 0
    ), "continuing the Cloisters extension edge did not reach the skip question"


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


def test_kogge_axis_arrows_have_distinct_hit_targets_and_support_both_directions(
    page, serve
) -> None:
    """Catches spoke-lane regressions: no overlap, keep-left signs, and still-clickable centres."""
    base_url, server = serve(SCENARIOS / "kogge_cloisters_own_own_skip_duty_001.json")
    candidate = next(
        (
            offered
            for offered in server.payload["turn_candidates"]
            if any(
                step["kind"] == "edge" and step["value"] == "city->east"
                for step in offered["steps"]
            )
            and any(
                step["kind"] == "edge" and step["value"] == "east->city"
                for step in offered["steps"]
            )
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

    _click_candidate_prefix(
        page, candidate, before_kind="edge", route_toggles=("kogge", "cloisters")
    )
    first = page.query_selector('[data-arrow="city->east"][data-turn-offered="true"]')
    assert first is not None, "city->east was not offered on the opening Kogge step"
    _click_handle_centre(page, first, require_hit=True)
    page.wait_for_timeout(20)

    second = page.query_selector('[data-arrow="east->city"][data-turn-offered="true"]')
    assert second is not None, "route did not continue with east->city after city->east"
    _click_handle_centre(page, second, require_hit=True)
    page.wait_for_timeout(20)
    assert (
        page.locator('[data-board-position-index][data-turn-duty-candidate="true"]').count() > 0
    ), "route using both east-axis directions did not advance to a duty choice"


def test_hired_kogge_arrow_shows_its_cost_pays_on_confirm_and_reset_removes_it(
    page, serve
) -> None:
    """Choosing a hired arrow previews its cost; only Confirm transfers the payment."""
    base_url, server = serve(SCENARIOS / "playtest" / "movement_2p.json")
    page.goto(base_url, wait_until="networkidle")
    turn_start = server.state
    yellow_silver = turn_start.player_state(PlayerId.PLAYER_TWO).resources.silver

    def wait_for_turn_start() -> None:
        page.wait_for_selector(
            '[data-board-position-index="0"][data-turn-start-candidate="true"]'
        )

    def choose_city_and_count_reversed_arrows() -> int:
        city = page.query_selector(
            '[data-board-position-index="0"][data-turn-start-candidate="true"]'
        )
        assert city is not None, "City was not offered as a sow origin"
        _click_handle_centre(page, city, require_hit=True)
        page.wait_for_timeout(20)
        if page.locator('[data-building-id="kogge"]').first.get_attribute(
            "data-turn-family-state"
        ) == "off":
            _toggle_route_building(page, "kogge")
        return sum(
            page.locator(f'[data-arrow="{arrow}"][data-turn-offered="true"]').count()
            for arrow in ("city->east", "city->west", "north->city", "south->city")
        )

    assert choose_city_and_count_reversed_arrows() > 0
    kogge_edge = page.query_selector('[data-arrow="city->east"][data-turn-offered="true"]')
    assert kogge_edge is not None, "Kogge's reversed arrow was not offered from City"
    _click_handle_centre(page, kogge_edge, require_hit=True)
    page.wait_for_timeout(20)
    assert page.locator('[data-turn-hire-fact="true"]').inner_text() == (
        "This route uses Kogge — 1 silver to Yellow."
    )
    assert server.state.player_state(PlayerId.PLAYER_TWO).resources.silver == yellow_silver

    for selector in (
        '[data-board-position-index="3"][data-turn-duty-candidate="true"]',
        '[data-turn-control="action"][data-turn-control-enabled="true"]',
        '[data-resolution-key="produce_wheat"][data-turn-offered="true"]',
    ):
        target = page.query_selector(selector)
        assert target is not None, f"missing Kogge route target {selector}"
        _click_handle_centre(page, target, require_hit=True)
        page.wait_for_timeout(20)

    assert _confirm_enabled(page), "Kogge route did not enable Confirm"
    _click_handle_point(
        page,
        page.locator('[data-turn-control="confirm"]').element_handle(),
        0.5,
        0.2,
    )
    page.wait_for_function(
        """() => Array.from(document.querySelectorAll('.log-event')).some(
          event => event.textContent === 'Red hired Kogge from Yellow and paid 1 silver.'
        )"""
    )

    assert server.state.player_state(PlayerId.PLAYER_TWO).resources.silver == yellow_silver + 1
    assert "Red hired Kogge from Yellow and paid 1 silver." in page.locator(
        ".log-event"
    ).all_inner_texts()
    _click_handle_centre(
        page,
        page.locator('[data-turn-control="reset"]').element_handle(),
        require_hit=True,
    )
    # The committed hire makes Reset replace the document; the old page has no City origin marker.
    wait_for_turn_start()
    assert server.state == turn_start
    assert choose_city_and_count_reversed_arrows() > 0


def test_hired_cloisters_arrow_reveals_its_extension_and_reaches_the_skip_question(
    page, serve
) -> None:
    """A paid Cloisters route stays painted through its extra edge and then asks what to skip."""
    base_url, server = serve(SCENARIOS / "playtest" / "movement_2p.json")
    page.goto(base_url, wait_until="networkidle")
    _pass_movement_red_turn_to_yellow(page)
    red_silver = server.state.player_state(PlayerId.PLAYER_ONE).resources.silver

    origin = page.query_selector(
        '[data-board-position-index="3"][data-turn-start-candidate="true"]'
    )
    assert origin is not None, "east was not offered as the Cloisters route origin"
    _click_handle_centre(page, origin, require_hit=True)
    page.wait_for_timeout(20)
    _toggle_route_building(page, "cloisters")
    edge = page.query_selector('[data-arrow="east->south_east"][data-turn-offered="true"]')
    assert edge is not None, "east->south_east was not offered for the Cloisters route"
    _click_handle_centre(page, edge, require_hit=True)
    page.wait_for_timeout(20)

    extension = page.query_selector('[data-arrow="south->south_west"][data-turn-offered="true"]')
    assert extension is not None, "hired Cloisters did not paint its extra route edge"
    _click_handle_centre(page, extension, require_hit=True)
    page.wait_for_timeout(20)
    assert page.locator('[data-turn-hire-fact="true"]').inner_text() == (
        "This route uses Cloisters — 1 silver to Red."
    )
    assert server.state.player_state(PlayerId.PLAYER_ONE).resources.silver == red_silver
    skip_spaces = page.locator('[data-turn-skip-candidate="true"]').evaluate_all(
        '(spaces) => spaces.map(space => space.getAttribute("data-board-position"))'
    )
    assert {"south_east", "south", "south_west"} <= set(skip_spaces), (
        "walking the Cloisters extension did not reach its skip question"
    )


def test_used_cloisters_route_tile_greys_only_when_the_server_reports_its_effect(
    page, serve
) -> None:
    """A committed owned Cloisters sow gets its in-effect state from the server event."""
    owned_url, _owned_server = serve(SCENARIOS / "playtest" / PLAYTEST_CLOISTERS)
    page.goto(owned_url, wait_until="networkidle")
    tile = page.locator('[data-building-id="cloisters"]').first

    assert tile.get_attribute("data-turn-family-state") == "owned"
    assert tile.get_attribute("data-building-ability-greyed") == "false"

    used_url, server = serve(SCENARIOS / "playtest" / "movement_2p.json")
    page.goto(used_url, wait_until="networkidle")
    tile = page.locator('[data-building-id="cloisters"]').first

    def commit_relocation(building_id: str) -> None:
        building = page.locator(
            f'[data-turn-step-building-id="{building_id}"][data-turn-step-offered="true"]'
        ).first
        _click_handle_centre(page, building.element_handle(), require_hit=True)
        target = page.locator(
            '[data-board-position-index="4"][data-turn-step-relocation-candidate="true"]'
        ).first
        _click_handle_centre(page, target.element_handle(), require_hit=True)
        assert _confirm_enabled(page), f"{building_id} relocation did not settle"
        _click_handle_point(
            page,
            page.locator('[data-turn-control="confirm"]').element_handle(),
            0.5,
            0.2,
        )
        page.wait_for_function(
            f"""() => document.querySelector('[data-turn-step-building-id="{building_id}"]')
              .getAttribute('data-turn-step-used') === 'true'"""
        )

    commit_relocation("inquisition")
    commit_relocation("dormitory")
    candidate = next(
        candidate
        for candidate in server.payload["turn_candidates"]
        if (candidate.get("action_id") or "").endswith(
            "action:give_alms_paid:pay_silver:1:pay_wheat:0:"
            "sow_route_building:cloisters:from:own_active:skip:1"
        )
    )
    for step in candidate["steps"]:
        if _page_matches_auto_advance_family_selection(page, step):
            continue
        if step.get("resource_allocation"):
            _click_alms_silver(page)
            continue
        _click_candidate_step(page, step)
        if step["kind"] == "edge" and step["value"] == "north->north_east":
            assert tile.get_attribute("data-turn-family-state") == "in_effect"
            assert tile.get_attribute("data-building-ability-greyed") == "false"

    assert _confirm_enabled(page), "the exact owned Cloisters sow did not settle"
    _click_handle_point(
        page,
        page.locator('[data-turn-control="confirm"]').element_handle(),
        0.5,
        0.2,
    )
    page.wait_for_function(
        """() => {
          const tile = document.querySelector('[data-building-id="cloisters"]');
          return tile && tile.getAttribute('data-building-ability-greyed') === 'true';
        }"""
    )

    assert "cloisters" not in server.state.turn_progress.used_buildings
    assert tile.get_attribute("data-building-ability-greyed") == "true"
    assert tile.locator(".tile-fill").evaluate(
        "tile => getComputedStyle(tile).fill"
    ) == "rgb(189, 184, 172)"
    tile.hover()
    assert page.locator('[data-building-tooltip-ability="true"]').inner_text() == (
        "In effect for the rest of this turn."
    )


def test_route_tile_toggles_are_off_on_then_in_effect_without_greying(page, serve) -> None:
    base_url, server = serve(SCENARIOS / "playtest" / "movement_2p.json")
    # `i`, not this transport order, is the candidate and automatic-mask identifier.
    server.payload["families"] = tuple(reversed(server.payload["families"]))
    page.goto(base_url, wait_until="networkidle")
    tile = page.locator('[data-building-id="kogge"]').first

    assert tile.get_attribute("data-turn-family-state") == "off"
    assert tile.get_attribute("data-turn-family-available") == "false"
    assert tile.get_attribute("data-building-ability-greyed") == "false"
    assert page.locator('[data-component="duty-wheel"] [data-arrow]').count() == 12
    tile.hover()
    assert page.locator('[data-building-tooltip-ability="true"]').inner_text() == (
        "Pick up acolytes first, then show the routes it opens — "
        "1 silver to Yellow if you use one."
    )

    def offered_route_state() -> dict[str, set[str]]:
        origin_ids = page.locator(
            '[data-board-position-index][data-turn-start-candidate="true"]'
        ).evaluate_all(
            'spaces => spaces.map(space => space.getAttribute("data-board-position-index"))'
        )
        arrow_ids = page.locator('[data-arrow][data-turn-offered="true"]').evaluate_all(
            'arrows => arrows.map(arrow => arrow.getAttribute("data-arrow"))'
        )
        return {
            "origins": set(origin_ids),
            "arrows": set(arrow_ids),
        }

    def take_city() -> set[str]:
        city = page.locator(
            '[data-board-position-index="0"][data-turn-start-candidate="true"]'
        ).first
        _click_handle_centre(page, city.element_handle(), require_hit=True)
        return offered_arrows()

    def offered_arrows() -> set[str]:
        return set(page.locator('[data-arrow][data-turn-offered="true"]').evaluate_all(
            'arrows => arrows.map(arrow => arrow.getAttribute("data-arrow"))'
        ))

    initially_offered = offered_route_state()
    initially_offered_arrows = take_city()
    assert "city->east" not in initially_offered_arrows
    assert page.locator('[data-component="duty-wheel"] [data-arrow]').count() == 12
    tile.hover()
    assert page.locator('[data-building-tooltip-ability="true"]').inner_text() == (
        "After choosing an origin, show the routes it opens — 1 silver to Yellow if you use one."
    )
    _show_hired_route_building_if_available(page, "kogge")
    assert tile.get_attribute("data-turn-family-state") == "on"
    assert tile.get_attribute("data-building-ability-text") == (
        "Routes shown — click to hide and restart your sow. Nothing is paid until you use one."
    )
    tile.hover()
    assert page.locator('[data-building-tooltip-ability="true"]').inner_text() == (
        "Routes shown — click to hide and restart your sow. Nothing is paid until you use one."
    )
    assert page.locator('[data-component="duty-wheel"] [data-arrow]').count() == 16
    first_on = offered_arrows()
    assert "city->east" in first_on

    _toggle_route_building(page, "kogge")
    assert tile.get_attribute("data-turn-family-state") == "off"
    assert tile.get_attribute("data-turn-family-available") == "false"
    assert offered_route_state() == initially_offered
    assert page.locator('[data-component="duty-wheel"] [data-arrow]').count() == 12
    tile.hover()
    assert page.locator('[data-building-tooltip-ability="true"]').inner_text() == (
        "Pick up acolytes first, then show the routes it opens — "
        "1 silver to Yellow if you use one."
    )

    assert take_city() == initially_offered_arrows
    _toggle_route_building(page, "kogge")
    assert offered_arrows() == first_on

    kogge_edge = page.locator('[data-arrow="city->east"][data-turn-offered="true"]').first
    _click_handle_centre(page, kogge_edge.element_handle(), require_hit=True)
    assert tile.get_attribute("data-turn-family-state") == "in_effect"
    assert tile.get_attribute("data-turn-family-available") == "false"
    assert tile.get_attribute("data-building-ability-greyed") == "false"
    tile.hover()
    assert page.locator('[data-building-tooltip-ability="true"]').inner_text() == (
        "In effect for the rest of this turn."
    )


def test_reset_restores_hired_and_owned_route_family_visibility(page, serve) -> None:
    hired_url, _server = serve(SCENARIOS / "playtest" / "movement_2p.json")
    page.goto(hired_url, wait_until="networkidle")
    hired_tile = page.locator('[data-building-id="kogge"]').first

    _click_handle_centre(
        page,
        page.locator('[data-board-position-index="0"][data-turn-start-candidate="true"]')
        .first.element_handle(),
        require_hit=True,
    )
    _toggle_route_building(page, "kogge")
    _click_handle_centre(
        page,
        page.locator('[data-arrow="city->east"][data-turn-offered="true"]').first.element_handle(),
        require_hit=True,
    )
    page.locator('[data-turn-control="reset"]').click()

    assert hired_tile.get_attribute("data-turn-family-state") == "off"
    assert page.locator('[data-component="duty-wheel"] [data-arrow]').count() == 12

    owned_url, _server = serve(SCENARIOS / "playtest" / PLAYTEST_KOGGE_AND_CLOISTERS)
    page.goto(owned_url, wait_until="networkidle")
    owned_tile = page.locator('[data-building-id="kogge"]').first
    _click_handle_centre(
        page,
        page.locator('[data-board-position-index="0"][data-turn-start-candidate="true"]')
        .first.element_handle(),
        require_hit=True,
    )
    _click_handle_centre(
        page,
        page.locator('[data-arrow="city->east"][data-turn-offered="true"]').first.element_handle(),
        require_hit=True,
    )
    page.locator('[data-turn-control="reset"]').click()

    assert owned_tile.get_attribute("data-turn-family-state") == "owned"
    assert page.locator('[data-component="duty-wheel"] [data-arrow]').count() == 16


def test_owned_kogge_keeps_its_spokes_drawn_without_a_clickable_toggle(page, serve) -> None:
    base_url, _server = serve(SCENARIOS / "playtest" / PLAYTEST_KOGGE_AND_CLOISTERS)
    page.goto(base_url, wait_until="networkidle")
    tile = page.locator('[data-building-id="kogge"]').first

    assert tile.get_attribute("data-turn-family-state") == "owned"
    assert tile.get_attribute("data-turn-family-available") == "false"
    assert tile.evaluate("node => getComputedStyle(node).cursor") != "pointer"
    tile.hover()
    assert page.locator('[data-building-tooltip-ability="true"]').inner_text() == (
        "Yours: in effect every turn."
    )
    assert page.locator('[data-component="duty-wheel"] [data-arrow]').count() == 16

    city = page.locator(
        '[data-board-position-index="0"][data-turn-start-candidate="true"]'
    ).first
    _click_handle_centre(page, city.element_handle(), require_hit=True)
    assert tile.get_attribute("data-turn-family-state") == "owned"
    assert tile.get_attribute("data-turn-family-available") == "false"
    assert page.locator('[data-arrow="city->east"][data-turn-offered="true"]').count() == 1

    _click_handle_centre(
        page,
        page.locator('[data-arrow="city->east"][data-turn-offered="true"]').first.element_handle(),
        require_hit=True,
    )
    assert page.locator('[data-turn-hire-fact-active="true"]').count() == 0


def test_route_edge_paints_and_cost_facts_follow_server_metadata(page, serve) -> None:
    base_url, _server = serve(SCENARIOS / "kogge_cloisters_hire_both_market_001.json")
    page.goto(base_url, wait_until="networkidle")
    kogge = page.locator('[data-building-id="kogge"]').first

    def take_city() -> None:
        city = page.locator(
            '[data-board-position-index="0"][data-turn-start-candidate="true"]'
        ).first
        _click_handle_centre(page, city.element_handle(), require_hit=True)

    def paint(arrow) -> dict[str, str]:
        return arrow.evaluate(
            """node => ({
                fill: getComputedStyle(node.querySelector('.arrow-interior')).fill,
                borderWidth: getComputedStyle(node.querySelector('.arrow-border')).strokeWidth,
            })"""
        )

    take_city()
    _toggle_route_building(page, "kogge")
    _toggle_route_building(page, "cloisters")
    assert page.locator('[data-turn-hire-fact-active="true"]').count() == 0
    city_east = page.locator('[data-arrow="city->east"][data-turn-offered="true"]').first
    assert paint(city_east) == {"fill": "rgb(122, 79, 181)", "borderWidth": "6px"}
    _click_handle_centre(page, city_east.element_handle(), require_hit=True)
    assert page.locator('[data-turn-hire-fact="true"]').inner_text() == (
        "This route uses Kogge — 1 wheat to bank."
    )
    _click_handle_centre(
        page,
        page.locator('[data-turn-control="reset"]').element_handle(),
        require_hit=True,
    )
    assert kogge.get_attribute("data-turn-family-state") == "off"
    assert page.locator('[data-arrow="north->city"][data-turn-offered="true"]').count() == 0

    take_city()
    _toggle_route_building(page, "kogge")
    _toggle_route_building(page, "cloisters")
    for edge_name in ("city->north", "north->city"):
        edge = page.locator(f'[data-arrow="{edge_name}"][data-turn-offered="true"]').first
        _click_handle_centre(page, edge.element_handle(), require_hit=True)
    _toggle_route_building(page, "cloisters")
    assert page.locator(
        '[data-board-position-index="0"][data-turn-start-candidate="true"]'
    ).count() == 1
    assert page.locator('[data-arrow][data-turn-offered="true"]').count() == 0

    take_city()
    _toggle_route_building(page, "cloisters")
    for edge_name in ("city->north", "north->city"):
        edge = page.locator(f'[data-arrow="{edge_name}"][data-turn-offered="true"]').first
        _click_handle_centre(page, edge.element_handle(), require_hit=True)
    city_east = page.locator('[data-arrow="city->east"][data-turn-offered="true"]').first
    assert paint(city_east) == {"fill": "rgb(14, 155, 166)", "borderWidth": "8px"}
    _click_handle_centre(page, city_east.element_handle(), require_hit=True)

    assert page.locator('[data-turn-hire-fact="true"]').inner_text() == (
        "This route uses Kogge — 1 wheat to bank.\n"
        "and the Cloisters — 1 wheat to bank."
    )


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
    _show_hired_route_building_if_available(page, "kogge")

    north_to_city = page.query_selector('[data-arrow="north->city"][data-turn-offered="true"]')
    assert north_to_city is not None, "north->city was not offered after reaching North"
    _click_handle_centre(page, north_to_city, require_hit=True)
    page.wait_for_timeout(20)

    city_to_east = page.query_selector('[data-arrow="city->east"][data-turn-offered="true"]')
    assert city_to_east is not None, "city->east was not offered after entering City from North"
    _click_handle_centre(page, city_to_east, require_hit=True)
    page.wait_for_timeout(20)

    assert (
        page.locator('[data-board-position-index][data-turn-duty-candidate="true"]').count() > 0
    ), "route did not advance to duty selection after entering City against arrows"


def test_a_cloisters_skip_target_receives_a_real_centre_click(page, serve) -> None:
    """Catches wheel skip-step regressions where the marked unsown-space target is not clickable."""
    base_url, _server = serve(SCENARIOS / "kogge_cloisters_own_own_skip_duty_001.json")
    page.goto(base_url, wait_until="networkidle")

    _walk_until_skip_step_by_preferring_edges(
        page, target="cloisters skip step", route_toggle="cloisters"
    )

    skip_target = page.query_selector(
        '[data-board-position-index][data-turn-skip-candidate="true"]'
    )
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
    assert (
        page.locator('[data-board-position-index][data-turn-skip-candidate="true"]').count() == 0
    ), "skip click did not advance beyond the skip question"


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
        preferred_control="tithe",
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
    assert (
        page.locator(f'[data-player-seat="{seat_number}"][data-resource-choice="true"]').count()
        == 0
    )


def test_ordination_controls_are_mouse_reachable_and_light_city_then_confirm(page, serve) -> None:
    """Catches Ordination controls that look live but cannot make their encoded selection."""
    base_url, server = serve(SCENARIOS / "ordination_mill_active_three_steps_one_wheat_001.json")
    candidate = next(
        (
            c
            for c in server.payload["turn_candidates"]
            if any(step["kind"] == "ordination" for step in c["steps"])
            and (
                counts := _ordination_counts(
                    next(step["value"] for step in c["steps"] if step["kind"] == "ordination")
                )
            )[0]
            >= 1
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

    ordain_button = page.locator('[data-ordination-action="ordain"][data-turn-offered="true"]')
    assert ordain_button.inner_text() == "Move a serf from the Village to the Abbey"
    mission_button = page.locator('[data-ordination-action="mission"]')
    assert mission_button.inner_text() == "Move an Acolyte from the Abbey to the City"

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

    ordain_button.click()
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
    mission_button = page.locator('[data-ordination-action="mission"][data-turn-offered="true"]')
    mission_button.click()
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

    assert _confirm_enabled(page), (
        f"confirm did not light for ordination outcome {ordination_value}"
    )


def test_unavailable_ordination_controls_stay_visible_with_server_reasons(page, serve) -> None:
    base_url, _server = serve(SCENARIOS / "bank_active_ordination_substitution_001.json")
    page.goto(base_url, wait_until="networkidle")
    _walk_live_dom_until(
        page,
        lambda: page.locator('[data-ordination-choice="true"]').count() == 1,
        target="Bank Ordination step",
        preferred_resolution="ordination",
    )

    ordain = page.locator('[data-ordination-action="ordain"]')
    mission = page.locator('[data-ordination-action="mission"]')
    assert ordain.is_visible() and mission.is_visible()
    assert ordain.is_enabled() and not mission.is_enabled()
    assert mission.evaluate("node => getComputedStyle(node).cursor") == "not-allowed"
    assert mission.evaluate("node => getComputedStyle(node).backgroundColor") != ordain.evaluate(
        "node => getComputedStyle(node).backgroundColor"
    )
    assert page.locator(
        '[data-ordination-unavailable-reason="mission"]'
        '[data-ordination-reason-shown="true"]'
    ).inner_text() == "No acolyte in the Abbey."
    hidden_keys = page.locator(
        '[data-combination-key][data-turn-offered="false"], '
        '[data-resolution-key][data-turn-offered="false"]'
    )
    assert hidden_keys.count() > 0
    assert all(not hidden_keys.nth(index).is_visible() for index in range(hidden_keys.count()))

    # Native disabling is only one layer: remove it and the existing offered-state guard must still
    # reject a synthetic press, leaving the Ordination preview where it was.
    mission.evaluate("node => { node.disabled = false; node.click(); }")
    assert ordain.is_enabled() and not mission.is_enabled()

    ordain.click()
    assert ordain.is_visible() and mission.is_visible()
    assert ordain.is_enabled() and mission.is_enabled()
    assert page.locator('[data-ordination-reason-shown="true"]').count() == 0

    ordain.click()
    disabled_reasons = page.locator('[data-ordination-reason-shown="true"]')
    assert ordain.is_visible() and mission.is_visible()
    assert not ordain.is_enabled() and not mission.is_enabled()
    assert disabled_reasons.all_inner_texts() == [
        "The duty value of 2 is used up.",
        "The duty value of 2 is used up.",
    ]


def test_ordination_control_reports_affordability_from_the_server(page, serve) -> None:
    base_url, _server = serve(SCENARIOS / "ordination_hire_mill_insufficient_resource_001.json")
    page.goto(base_url, wait_until="networkidle")
    _walk_live_dom_until(
        page,
        lambda: page.locator('[data-ordination-choice="true"]').count() == 1,
        target="Mill Ordination step",
        preferred_resolution="ordination",
    )

    page.locator('[data-ordination-action="ordain"][data-turn-offered="true"]').click()
    reason = page.locator(
        '[data-ordination-unavailable-reason="mission"]'
        '[data-ordination-reason-shown="true"]'
    )
    assert reason.inner_text() == "You cannot afford another move."
    assert not page.locator('[data-ordination-action="mission"]').is_enabled()


def test_ordination_preview_only_spends_for_the_serfs_chosen(page, serve) -> None:
    """One ordain is a complete turn even though a second ordain remains available."""
    base_url, server = serve(SCENARIOS / "playtest" / "movement_2p.json")
    candidate = next(
        candidate
        for candidate in server.payload["turn_candidates"]
        if any(
            step["kind"] == "ordination" and step["value"] == "ordain=2"
            for step in candidate["steps"]
        )
    )
    page.goto(base_url, wait_until="networkidle")
    wheat_before = _player_holdings(page)["wheat"]
    _click_candidate_prefix(
        page,
        candidate,
        before_kind="ordination",
        route_toggles=("kogge",),
    )

    assert _player_holdings(page)["wheat"] == wheat_before
    ordain = page.locator('[data-ordination-action="ordain"][data-turn-offered="true"]')
    _click_handle_centre(page, ordain.element_handle(), require_hit=True)
    assert _confirm_enabled(page)
    assert _player_holdings(page)["wheat"] == wheat_before - 1

    second_ordain = page.locator('[data-ordination-action="ordain"][data-turn-offered="true"]')
    _click_handle_centre(page, second_ordain.element_handle(), require_hit=True)
    assert _confirm_enabled(page)
    assert _player_holdings(page)["wheat"] == wheat_before - 2


def test_owned_bank_ordination_requires_an_explicit_payment_choice(page, serve) -> None:
    """A Bank mix remains a question even after ordination narrows its action candidates."""
    base_url, _server = serve(SCENARIOS / "bank_active_ordination_substitution_001.json")

    def reach_ordination() -> None:
        page.goto(base_url, wait_until="networkidle")
        _walk_live_dom_until(
            page,
            lambda: page.locator('[data-ordination-choice="true"]').count() == 1,
            target="Bank ordination step",
            preferred_resolution="ordination",
        )

    reach_ordination()
    ordain = page.locator('[data-ordination-action="ordain"][data-turn-offered="true"]')
    first_ordain_count = ordain.count()
    ordain.click()

    wheat = page.locator('[data-combination-key="wheat=1"][data-turn-offered="true"]')
    silver = page.locator('[data-combination-key="silver=1"][data-turn-offered="true"]')
    wheat_label = wheat.inner_text()
    silver_label = silver.inner_text()
    first_confirm_before_payment = _confirm_enabled(page)

    silver.click()
    first_confirm_after_payment = _confirm_enabled(page)

    reach_ordination()
    page.locator('[data-ordination-action="ordain"][data-turn-offered="true"]').click()
    mission = page.locator('[data-ordination-action="mission"][data-turn-offered="true"]')
    mission_count = mission.count()
    mission.click()

    full_mix = page.locator(
        '[data-combination-key="wheat=1,silver=1"][data-turn-offered="true"]'
    )
    full_mix_count = full_mix.count()
    full_mix_label = full_mix.inner_text()
    second_confirm_before_payment = _confirm_enabled(page)

    full_mix.click()
    second_confirm_after_payment = _confirm_enabled(page)

    assert {
        "ordain_count": first_ordain_count,
        "first_labels": {wheat_label, silver_label},
        "first_confirm_before_payment": first_confirm_before_payment,
        "first_confirm_after_payment": first_confirm_after_payment,
        "mission_count": mission_count,
        "full_mix_count": full_mix_count,
        "full_mix_label": full_mix_label,
        "second_confirm_before_payment": second_confirm_before_payment,
        "second_confirm_after_payment": second_confirm_after_payment,
    } == {
        "ordain_count": 1,
        "first_labels": {"Pay 1 wheat.", "Pay 1 silver."},
        "first_confirm_before_payment": False,
        "first_confirm_after_payment": True,
        "mission_count": 1,
        "full_mix_count": 1,
        "full_mix_label": "Pay 1 wheat and 1 silver.",
        "second_confirm_before_payment": False,
        "second_confirm_after_payment": True,
    }


@pytest.mark.parametrize(
    ("scenario_name", "resolution", "hire_key"),
    [
        ("allocation_hire_infirmary_market_001.json", "allocation", "infirmary:market"),
        ("ordination_hire_mill_market_three_steps_001.json", "ordination", "mill:market"),
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
        button = page.query_selector(f'[data-combination-key="{choice}"][data-turn-offered="true"]')
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


# This fixture opens before any construct candidate is reached, so this checks only that the drawn
# but unoffered building keys have no hit area.  The one-building construct itself is covered by
# the turn-script test that now requires its click.
def test_hidden_building_keys_keep_no_hit_area(page, serve) -> None:
    """Catches hidden-key regressions: in SVG, `pointer-events: all` still applies while hidden."""
    base_url, _server = serve(SCENARIOS / "construct_building_live_only_001.json")
    page.goto(base_url, wait_until="networkidle")

    assert page.locator("[data-building-choice-key]").count() == 4
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

    broken = render_play_view._TURN_SCRIPT.replace(
        "var canLiftNow = !waitingToPlace && canLift;",
        "var canLiftNow = canLift;",
    ).replace(
        "var canPlaceNow = waitingToPlace && canPlace;",
        "var canPlaceNow = canPlace;",
    )
    assert broken != render_play_view._TURN_SCRIPT
    monkeypatch.setattr(render_play_view, "_TURN_SCRIPT", broken)

    base_url, server = serve(SCENARIOS / "allocation_chapter_house_second_acolyte_001.json")
    with pytest.raises(
        AssertionError, match="topmost live at Vestry centre while holding should be the circle"
    ):
        _assert_allocation_vestry_overlap_behaviour(page, base_url, server)


def test_two_active_conversions_commit_from_building_direction_and_amount_clicks(
    page, serve
) -> None:
    base_url, server = serve(SCENARIOS / "two_active_conversions_001.json")
    before = server.state
    page.goto(base_url, wait_until="networkidle")

    _choose_conversion(page, "grain_store", "sell_wheat", 1)
    assert page.locator('[data-turn-step-amount-total="true"]').inner_text() == "1"
    assert _confirm_enabled(page), "a fully narrowed conversion did not enable Confirm"
    page.locator('[data-turn-control="confirm"]').click()
    page.wait_for_timeout(100)

    assert server.state != before, "committing a conversion did not change the position"
    assert server.state.turn_progress.used_buildings == frozenset({"grain_store"})


def test_turn_phase_column_tracks_conversion_sow_and_end_turn(page, serve) -> None:
    """A conversion is outside the Sow answer sequence, so it cannot advance that phase."""
    base_url, server = serve(SCENARIOS / "playtest" / PLAYTEST_CONVERSIONS)
    page.goto(base_url, wait_until="networkidle")

    _assert_painted_turn_phase(page, "beginning")
    _screenshot_turn_prompt(page, SCREENSHOTS / "turn-phase-beginning.png")

    _choose_conversion(page, "grain_store", "sell_wheat", 1)
    assert _confirm_enabled(page)
    page.locator('[data-turn-control="confirm"]').click()
    page.wait_for_timeout(100)

    assert server.state.turn_progress.used_buildings == frozenset({"grain_store"})
    _assert_painted_turn_phase(page, "beginning")

    origin = page.query_selector('[data-board-position-index][data-turn-start-candidate="true"]')
    assert origin is not None, "the next turn never offered an acolyte lift"
    origin_value = int(origin.get_attribute("data-board-position-index"))
    tithe_candidate = next(
        candidate
        for candidate in server.payload["turn_candidates"]
        if candidate["action_id"] is not None
        and any(
            step["kind"] == "origin" and step["value"] == origin_value
            for step in candidate["steps"]
        )
        and any(
            step["kind"] == "resolution" and step["value"] == "tithe" for step in candidate["steps"]
        )
    )
    expected_resolution = apply_action(
        server.state,
        next(
            action
            for action in legal_actions(server.state, server.config)
            if action_id(action) == tithe_candidate["action_id"]
        ),
        server.config,
    ).state
    _click_handle_centre(page, origin, require_hit=True)
    page.wait_for_function(
        """() => document.querySelector('[data-turn-phase="sow"]')
          ?.getAttribute('data-phase-current') === 'true'"""
    )

    _assert_painted_turn_phase(page, "sow")
    assert page.evaluate(
        """() => {
          const tilePaint = (buildingId) => {
            const fill = document.querySelector(
              `.setup-building-fill[data-building-id="${buildingId}"] .tile-fill`
            );
            const label = document.querySelector(
              `.setup-building-label[data-building-id="${buildingId}"] .tile-label`
            );
            return {
              fill: fill && getComputedStyle(fill).fill,
              label: label && getComputedStyle(label).fill,
            };
          };
          const market = document.querySelector('.setup-building-fill[data-building-id="brewery"]');
          const own = document.querySelector(
            '[data-active-seat="true"] [data-player-board-slot][data-building-id="grain_store"]'
          );
          return {
            offered: document.querySelectorAll(
              '[data-turn-step-building-id][data-turn-step-offered="true"]'
            ).length,
            market: {
              greyed: market.getAttribute('data-building-ability-greyed'),
              paint: tilePaint('brewery'),
            },
            own: {
              greyed: own.getAttribute('data-building-ability-greyed'),
              fill: getComputedStyle(own.querySelector('.tile-fill')).fill,
              label: getComputedStyle(own.querySelector('.tile-label')).fill,
            },
          };
        }"""
    ) == {
        "offered": 0,
        "market": {
            "greyed": "true",
            "paint": {"fill": "rgb(189, 184, 172)", "label": "rgb(92, 87, 78)"},
        },
        "own": {
            "greyed": "true",
            "fill": "rgb(189, 184, 172)",
            "label": "rgb(92, 87, 78)",
        },
    }
    _screenshot_turn_prompt(page, SCREENSHOTS / "turn-phase-sow.png")

    for step in tithe_candidate["steps"]:
        if _page_matches_auto_advance_family_selection(page, step):
            continue
        if step["kind"] == "edge":
            selector = f'[data-arrow="{step["value"]}"][data-turn-offered="true"]'
        elif step["kind"] == "duty":
            selector = (
                f'[data-board-position-index="{step["value"]}"][data-turn-duty-candidate="true"]'
            )
        else:
            continue
        handle = page.query_selector(selector)
        assert handle is not None, f"the candidate step {step['value']} was not offered"
        _click_handle_centre(page, handle, require_hit=True)
        page.wait_for_timeout(40)
    tithe = page.query_selector('[data-turn-control="tithe"][data-turn-control-enabled="true"]')
    assert tithe is not None, "the selected candidate did not offer Tithe"
    _click_handle_centre(page, tithe, require_hit=True)
    page.wait_for_timeout(40)

    resource = next(step for step in tithe_candidate["steps"] if step["kind"] == "resource")
    resource_key = page.query_selector(
        f'[data-active-seat="true"] [data-resource-choice-key="{resource["value"]}"]'
        '[data-turn-offered="true"]'
    )
    assert resource_key is not None, "the selected tithe resource was not offered"
    _click_handle_centre(page, resource_key, require_hit=True)
    page.wait_for_timeout(40)
    assert _confirm_enabled(page)
    page.locator('[data-turn-control="confirm"]').click()
    page.wait_for_timeout(120)

    assert server.state == expected_resolution
    assert server.state.turn_progress.resolution_committed is True
    _assert_painted_turn_phase(page, "end")
    _screenshot_turn_prompt(page, SCREENSHOTS / "turn-phase-end.png")


def test_greyed_building_tiles_use_one_palette_across_all_three_level_colours(page, serve) -> None:
    """The server's greying attribute paints every level with the same fill and label colours."""
    base_url, _server = serve(SCENARIOS / "playtest" / PLAYTEST_CONVERSIONS)
    page.goto(base_url, wait_until="networkidle")

    colours = page.evaluate(
        """() => {
          const ids = ['confession_box', 'brewery', 'mill'];
          ids.forEach(id => {
            document.querySelectorAll(`[data-building-id="${id}"]`).forEach(target => {
              target.setAttribute('data-building-ability-greyed', 'true');
            });
          });
          return ids.map(id => {
            const fill = document.querySelector(
              `.setup-building-fill[data-building-id="${id}"] .tile-fill`
            );
            const label = document.querySelector(
              `.setup-building-label[data-building-id="${id}"] .tile-label`
            );
            return {
              fill: getComputedStyle(fill).fill,
              label: getComputedStyle(label).fill,
            };
          });
        }"""
    )
    assert colours == [
        {"fill": "rgb(189, 184, 172)", "label": "rgb(92, 87, 78)"},
        {"fill": "rgb(189, 184, 172)", "label": "rgb(92, 87, 78)"},
        {"fill": "rgb(189, 184, 172)", "label": "rgb(92, 87, 78)"},
    ]


def test_pulpit_questions_and_phase_window_words_follow_the_server_payload(page, serve) -> None:
    """The thin board proves acts remain visible and both phase paint paths agree."""
    base_url, server = serve(SCENARIOS / "playtest" / PLAYTEST_PULPIT)
    server_html = page.request.get(base_url).text()
    assert (
        '<div class="phase-row" data-turn-phase="beginning" data-phase-current="true">'
        "Beginning of Turn</div>"
    ) in server_html
    assert server.payload["phase_column"]["prompts"] == {
        "beginning": "Pick up acolytes for sowing. A building can be hired here."
    }
    assert [
        step["turn_phase"] for step in server.payload["turn_candidates"][0]["steps"][:3]
    ] == ["beginning", "sow", "sow"]

    page.goto(base_url, wait_until="networkidle")
    _assert_painted_turn_phase(page, "beginning")
    assert page.locator('[data-turn-phase-prompt="beginning"]').inner_text() == (
        "Pick up acolytes for sowing. A building can be hired here."
    )

    for selector, prompt in (
        (
            '[data-board-position-index="1"][data-turn-start-candidate="true"]',
            "Red: Choose a space to lift acolytes from.",
        ),
        (
            '[data-board-position-index="2"][data-turn-duty-candidate="true"]',
            "Red: Choose a duty to take.",
        ),
    ):
        assert page.locator('[data-turn-prompt][data-turn-offered="true"]').inner_text() == prompt
        target = page.query_selector(selector)
        assert target is not None, f"the one-answer Pulpit question was not offered: {selector}"
        _click_handle_centre(page, target, require_hit=True)
        page.wait_for_timeout(40)

    _assert_painted_turn_phase(page, "sow")
    assert page.locator('[data-turn-prompt][data-turn-offered="true"]').inner_text() == (
        "Red: Action or Tithe."
    )
    action = page.query_selector('[data-turn-control="action"][data-turn-control-enabled="true"]')
    assert action is not None
    _click_handle_centre(page, action, require_hit=True)
    page.wait_for_timeout(40)
    resolution = page.query_selector(
        '[data-resolution-key="clerical_devotion"][data-turn-offered="true"]'
    )
    assert resolution is not None
    _click_handle_centre(page, resolution, require_hit=True)
    page.wait_for_timeout(40)
    assert _confirm_enabled(page)
    page.locator('[data-turn-control="confirm"]').click()
    page.wait_for_timeout(120)

    assert server.state.turn_progress.resolution_committed is True
    _assert_painted_turn_phase(page, "end")
    assert server.payload["phase_column"]["prompts"] == {}
    assert page.locator('[data-turn-phase-prompt="end"]').count() == 0


def test_merchant_named_hire_states_its_price_without_a_payment_click(page, serve) -> None:
    base_url, _server = serve(SCENARIOS / "playtest" / PLAYTEST_PULPIT)
    page.goto(base_url, wait_until="networkidle")

    pulpit = page.locator('[data-turn-step-building-id="pulpit"][data-turn-step-offered="true"]')
    assert pulpit.count() == 1
    _click_handle_centre(page, pulpit.element_handle(), require_hit=True)

    assert page.locator('[data-turn-step-hire-text="true"]').inner_text() == (
        "Hire Pulpit from market for 1 wheat."
    )
    assert page.locator(
        '[data-turn-step-hire-payment][data-turn-step-hire-offered="true"]'
    ).count() == 0
    assert _confirm_enabled(page)
    assert _confirm_enabled_attribute(page) == "true"


def test_cloisters_reach_skips_only_its_two_unambiguous_route_edges(page, serve) -> None:
    """A continuation arrow is automatic only until a duty or another route can be chosen."""
    base_url, _server = serve(SCENARIOS / "playtest" / PLAYTEST_CLOISTERS)
    page.goto(base_url, wait_until="networkidle")

    origin = page.query_selector(
        '[data-board-position-index="1"][data-turn-start-candidate="true"]'
    )
    assert origin is not None, "Cloisters Reach did not ask the player to lift acolytes"
    cloisters = page.locator('[data-building-id="cloisters"]').first
    assert cloisters.get_attribute("data-turn-family-state") == "owned"
    assert cloisters.get_attribute("data-turn-family-available") == "false"
    _click_handle_centre(page, origin, require_hit=True)
    page.wait_for_timeout(40)

    _assert_painted_turn_phase(page, "sow")
    duties = page.locator('[data-turn-duty-candidate="true"]').evaluate_all(
        "spaces => spaces.map(space => Number(space.getAttribute('data-board-position-index')))"
    )
    arrows = page.locator('[data-arrow][data-turn-offered="true"]').evaluate_all(
        "arrows => arrows.map(arrow => arrow.getAttribute('data-arrow'))"
    )
    assert set(duties) == {2, 3, 4, 7}
    assert set(arrows) == {"east->city", "east->south_east"}


def test_setup_sow_phase_column_stays_dim_after_a_setup_answer(page, serve) -> None:
    """Setup sowing is not a turn, before or after its player has answered a step."""
    base_url, server = serve(SCENARIOS / "setup_sow_2p_001.json")
    page.goto(base_url, wait_until="networkidle")

    _assert_all_turn_phases_dim(page)
    _screenshot_turn_prompt(page, SCREENSHOTS / "turn-phase-setup-sow.png")

    answer = _next_offered_from_dom(page)
    assert answer is not None, "the setup sow offered no answer to click"
    _click_handle_centre(page, answer, require_hit=True)
    page.wait_for_timeout(100)

    assert server.payload["state"]["phase"] == "setup_sow"
    _assert_all_turn_phases_dim(page)


def test_first_player_choice_paints_completed_round_end_steps_and_current_choice(
    page, serve
) -> None:
    """Round-end history is drawn from the pass before the first-player question is painted."""
    base_url, server = serve(SCENARIOS / "indulgences_buy_then_round_end_start_player_001.json")
    settled = next(
        candidate for candidate in server.payload["turn_candidates"] if candidate["action_id"]
    )
    server.apply(settled["action_id"], server.payload["state_token"])
    assert server.state.turn_progress.resolution_committed is True
    server.apply(action_id(EndTurnAction()), server.payload["state_token"])
    assert server.payload["state"]["phase"] == "start_player_selection"

    page.goto(base_url, wait_until="networkidle")

    _assert_painted_round_end_phases(
        page,
        ["round_marker", "merchant", "choose_first_player"],
        "choose_first_player",
    )
    _screenshot_turn_prompt(page, SCREENSHOTS / "round-end-phase-first-player.png")


def test_conversion_resource_pill_reaches_amount_above_six_without_prompt_overflow(
    page, serve
) -> None:
    base_url, server = serve(SCENARIOS / "playtest" / PLAYTEST_CONVERSIONS)
    page.goto(base_url, wait_until="networkidle")
    _choose_conversion(page, "stone_yard", "sell_stone", 7)

    assert page.locator('[data-turn-step-amount-total="true"]').inner_text() == "7"
    assert _confirm_enabled(page)
    assert page.locator('[data-component="play-turn"]').evaluate(
        "node => node.scrollWidth <= node.clientWidth"
    )
    page.locator('[data-turn-control="confirm"]').click()
    page.wait_for_timeout(100)
    assert server.state.turn_progress.used_buildings == frozenset({"stone_yard"})


def test_indulgences_destination_pill_commits_one_click_at_track_distance(page, serve) -> None:
    base_url, server = serve(SCENARIOS / "indulgences_active_sell_piety_001.json")
    page.goto(base_url, wait_until="networkidle")
    before = server.state.player_state(server.state.active_player).piety
    building = page.locator(
        '[data-active-seat="true"] [data-turn-step-building-id="indulgences"]'
        '[data-turn-step-offered="true"]'
    )
    _click_handle_centre(page, building.element_handle(), require_hit=True)
    direction = page.locator(
        '[data-turn-step-direction="sell_piety"][data-turn-step-offered="true"]'
    )
    _click_handle_centre(page, direction.element_handle(), require_hit=True)
    target = 2
    destination = page.locator(
        f'[data-piety-choice-pill][data-piety-choice-destination="{target}"]'
    )
    expected_silver = next(
        step["silver_delta"]
        for step in server.payload["turn_steps"]
        if step["building_id"] == "indulgences"
        and step["direction"] == "sell_piety"
        and step["piety_destination"] == target
    )
    assert (
        destination.locator("[data-piety-choice-silver]").text_content() == f"{expected_silver:+d}"
    )
    assert destination.locator("[data-piety-choice-piety-change]").count() == 0
    _click_handle_centre(page, destination.element_handle(), require_hit=True)
    assert page.locator('[data-turn-step-amount-total="true"]').inner_text() == "1"
    assert _confirm_enabled(page)
    page.locator('[data-turn-control="confirm"]').click()
    page.wait_for_timeout(100)
    assert before - server.state.player_state(server.state.active_player).piety == before - target


def test_illegal_indulgences_destination_has_no_live_pill(page, serve) -> None:
    base_url, _server = serve(SCENARIOS / "indulgences_active_sell_piety_001.json")
    page.goto(base_url, wait_until="networkidle")
    _choose_conversion(page, "indulgences", "sell_piety", 1)
    assert page.locator('[data-piety-choice-pill][data-piety-choice-destination="12"]').count() == 0


def test_piety_pill_silver_delta_is_engine_derived_without_hire_fee(page, serve) -> None:
    base_url, _server = serve(SCENARIOS / "indulgences_hire_opponent_sell_piety_001.json")
    page.goto(base_url, wait_until="networkidle")
    building = page.locator(
        '[data-turn-step-building-id="indulgences"][data-turn-step-offered="true"]'
    )
    _click_handle_centre(page, building.element_handle(), require_hit=True)
    direction = page.locator(
        '[data-turn-step-direction="sell_piety"][data-turn-step-offered="true"]'
    )
    _click_handle_centre(page, direction.element_handle(), require_hit=True)
    offered = page.locator('[data-piety-choice-pill][data-piety-choice-offered="true"]')
    assert offered.count() == 2
    destination = page.locator('[data-piety-choice-pill][data-piety-choice-destination="1"]')
    assert destination.locator("[data-piety-choice-silver]").text_content() == "+1"
    assert destination.locator("[data-piety-choice-piety-change]").count() == 0
    _click_handle_centre(page, destination.element_handle(), require_hit=True)


def test_piety_destination_pills_are_hidden_until_asked_and_overlay_disc_band(page, serve) -> None:
    from tools.ui_debug.render_play_view import render_play_view_from_payload

    base_url, server = serve(SCENARIOS / "indulgences_hire_opponent_sell_piety_001.json")
    page.goto(base_url, wait_until="networkidle")
    panel = page.locator('[data-component="piety-track-v2"]')
    main_page = page.context.new_page()
    main_payload = dict(server.payload, turn_steps=[])
    main_page.set_content(render_play_view_from_payload(main_payload), wait_until="networkidle")
    main_height = main_page.locator('[data-component="piety-track-v2"]').bounding_box()["height"]
    assert page.locator("[data-piety-choice-pill]").count() == 0
    assert panel.bounding_box()["height"] == pytest.approx(main_height, abs=0.1)
    assert page.locator("[data-piety-score-row]").count() == 13
    turn_height = page.locator('[data-component="play-turn"]').bounding_box()["height"]

    building = page.locator(
        '[data-turn-step-building-id="indulgences"][data-turn-step-offered="true"]'
    )
    _click_handle_centre(page, building.element_handle(), require_hit=True)
    direction = page.locator(
        '[data-turn-step-direction="sell_piety"][data-turn-step-offered="true"]'
    )
    _click_handle_centre(page, direction.element_handle(), require_hit=True)
    assert page.locator('[data-turn-step-answer-label="true"]').inner_text() == "Amount"
    hint = page.locator('[data-turn-step-resource-hint="true"]')
    assert not hint.is_visible()
    assert page.locator('[data-component="play-turn"]').bounding_box()["height"] == pytest.approx(
        turn_height, abs=0.1
    )

    lane = page.locator('[data-piety-choice-lane="true"]')
    lane_box = lane.bounding_box()
    pills = page.locator('[data-piety-choice-pill][data-piety-choice-offered="true"]')
    pill_boxes = [pills.nth(index).bounding_box() for index in range(pills.count())]
    assert lane_box is not None and len(pill_boxes) == 2
    for left, right in zip(pill_boxes, pill_boxes[1:]):
        assert left["x"] + left["width"] <= right["x"] + 1

    def intersects(first, second) -> bool:
        return not (
            first["x"] + first["width"] <= second["x"]
            or second["x"] + second["width"] <= first["x"]
            or first["y"] + first["height"] <= second["y"]
            or second["y"] + second["height"] <= first["y"]
        )

    obstacles = page.locator("[data-piety-position-label], [data-piety-score-row]")
    obstacle_boxes = [obstacles.nth(index).bounding_box() for index in range(obstacles.count())]
    assert all(not intersects(pill, obstacle) for pill in pill_boxes for obstacle in obstacle_boxes)

    board_url, _board_server = serve(SCENARIOS / "playtest" / PLAYTEST_CONVERSIONS)
    board_page = page.context.new_page()
    board_page.goto(board_url, wait_until="networkidle")
    board = board_page.locator(
        '[data-active-seat="true"] [data-turn-step-building-id="stone_yard"]'
        '[data-turn-step-offered="true"]'
    )
    _click_handle_centre(board_page, board.element_handle(), require_hit=True)
    board_direction = board_page.locator(
        '[data-turn-step-direction="sell_stone"][data-turn-step-offered="true"]'
    )
    _click_handle_centre(board_page, board_direction.element_handle(), require_hit=True)
    board_frame = board_page.locator(
        '[data-active-seat="true"] [data-resource-choice-key="stone"]'
    ).bounding_box()
    board_frame_style = board_page.locator(
        '[data-active-seat="true"] [data-resource-choice-key="stone"]'
    ).evaluate(
        "e => { const s = getComputedStyle(e); return {fill:s.fill, stroke:s.stroke, "
        "strokeWidth:s.strokeWidth, cursor:s.cursor, visibility:s.visibility}; }"
    )
    board_surface_style = board_page.locator(
        '[data-component="player-board-v2"] rect'
    ).first.evaluate("e => getComputedStyle(e).fill")
    piety_frame = page.locator(
        '[data-piety-choice-pill][data-piety-choice-offered="true"] [data-resource-choice-key]'
    ).first
    piety_frame_box = piety_frame.bounding_box()
    piety_frame_style = piety_frame.evaluate(
        "e => { const s = getComputedStyle(e); return {fill:s.fill, stroke:s.stroke, "
        "strokeWidth:s.strokeWidth, cursor:s.cursor, visibility:s.visibility}; }"
    )
    piety_surface_style = page.evaluate(
        """() => Array.from(document.querySelectorAll('[data-component="piety-track-v2"] rect'))
        .map(node => getComputedStyle(node).fill)
        .find(fill => fill !== 'rgb(0, 0, 0)' && fill !== 'none')"""
    )
    assert board_frame is not None and piety_frame_box is not None
    assert abs(piety_frame_box["width"] - board_frame["width"]) <= 2
    assert abs(piety_frame_box["height"] - board_frame["height"]) <= 2
    assert board_frame_style["fill"] == board_surface_style
    assert piety_frame_style["fill"] == piety_surface_style
    assert board_frame_style["stroke"] != board_frame_style["fill"]
    assert piety_frame_style["stroke"] != piety_frame_style["fill"]

    def rgb(value: str) -> tuple[int, int, int]:
        return tuple(
            int(channel) for channel in value.removeprefix("rgb(").removesuffix(")").split(", ")
        )

    board_fill = rgb(board_frame_style["fill"])
    board_stroke = rgb(board_frame_style["stroke"])
    piety_fill = rgb(piety_frame_style["fill"])
    piety_stroke = rgb(piety_frame_style["stroke"])
    assert all(border < fill for border, fill in zip(board_stroke, board_fill))
    assert all(border < fill for border, fill in zip(piety_stroke, piety_fill))
    board_ratio = sum(border / fill for border, fill in zip(board_stroke, board_fill)) / 3
    piety_ratio = sum(border / fill for border, fill in zip(piety_stroke, piety_fill)) / 3
    assert abs(board_ratio - piety_ratio) <= 0.03
    board_page.close()

    def union(boxes):
        return {
            "x": min(box["x"] for box in boxes),
            "y": min(box["y"] for box in boxes),
            "width": max(box["x"] + box["width"] for box in boxes) - min(box["x"] for box in boxes),
            "height": max(box["y"] + box["height"] for box in boxes)
            - min(box["y"] for box in boxes),
        }

    discs = page.locator("[data-player-disc]")
    stars = page.locator("[data-piety-score-row]")
    assert stars.count() == 13
    disc_row = union([discs.nth(index).bounding_box() for index in range(discs.count())])
    assert all(
        disc_row["y"] - 1 <= box["y"]
        and box["y"] + box["height"] <= disc_row["y"] + disc_row["height"] + 1
        for box in pill_boxes
    )
    assert panel.bounding_box()["height"] == pytest.approx(main_height, abs=0.1)
    main_page.close()


def test_piety_destination_pills_follow_the_chosen_direction(page, serve) -> None:
    base_url, server = serve(SCENARIOS / "playtest" / PLAYTEST_CONVERSIONS)
    page.goto(base_url, wait_until="networkidle")
    building = page.locator(
        '[data-turn-step-building-id="indulgences"][data-turn-step-offered="true"]'
    )
    _click_handle_centre(page, building.element_handle(), require_hit=True)
    payment = page.locator(
        '[data-turn-step-hire-payment="wheat"][data-turn-step-hire-offered="true"]'
    )
    _click_handle_centre(page, payment.element_handle(), require_hit=True)

    sell = page.locator('[data-turn-step-direction="sell_piety"][data-turn-step-offered="true"]')
    _click_handle_centre(page, sell.element_handle(), require_hit=True)
    sell_pills = page.locator('[data-piety-choice-pill][data-piety-choice-offered="true"]')
    expected_sell = {
        step["piety_destination"]
        for step in server.payload["turn_steps"]
        if step["building_id"] == "indulgences" and step["direction"] == "sell_piety"
    }
    assert sell_pills.count() == len(expected_sell)
    assert {
        int(sell_pills.nth(index).get_attribute("data-piety-choice-destination"))
        for index in range(sell_pills.count())
    } == expected_sell
    disc_boxes = [
        page.locator("[data-player-disc]").nth(index).bounding_box()
        for index in range(page.locator("[data-player-disc]").count())
    ]
    disc_top = min(box["y"] for box in disc_boxes)
    disc_bottom = max(box["y"] + box["height"] for box in disc_boxes)
    assert all(
        disc_top - 1 <= sell_pills.nth(index).bounding_box()["y"]
        and sell_pills.nth(index).bounding_box()["y"]
        + sell_pills.nth(index).bounding_box()["height"]
        <= disc_bottom + 1
        for index in range(sell_pills.count())
    )
    assert all(
        sell_pills.nth(index).locator("[data-piety-choice-silver]").text_content()
        for index in range(sell_pills.count())
    )

    page.locator('[data-turn-control="reset"]').click()
    _click_handle_centre(page, building.element_handle(), require_hit=True)
    payment = page.locator(
        '[data-turn-step-hire-payment="wheat"][data-turn-step-hire-offered="true"]'
    )
    _click_handle_centre(page, payment.element_handle(), require_hit=True)
    buy = page.locator('[data-turn-step-direction="buy_piety"][data-turn-step-offered="true"]')
    _click_handle_centre(page, buy.element_handle(), require_hit=True)
    buy_pills = page.locator('[data-piety-choice-pill][data-piety-choice-offered="true"]')
    expected_buy = {
        step["piety_destination"]
        for step in server.payload["turn_steps"]
        if step["building_id"] == "indulgences" and step["direction"] == "buy_piety"
    }
    assert buy_pills.count() == len(expected_buy)
    assert {
        int(buy_pills.nth(index).get_attribute("data-piety-choice-destination"))
        for index in range(buy_pills.count())
    } == expected_buy
    assert all(
        disc_top - 1 <= buy_pills.nth(index).bounding_box()["y"]
        and buy_pills.nth(index).bounding_box()["y"] + buy_pills.nth(index).bounding_box()["height"]
        <= disc_bottom + 1
        for index in range(buy_pills.count())
    )
    assert all(
        buy_pills.nth(index).locator("[data-piety-choice-silver]").text_content()
        for index in range(buy_pills.count())
    )


def test_piety_destination_number_matches_board_typography_and_contrast(page, serve) -> None:
    base_url, _server = serve(SCENARIOS / "indulgences_active_sell_piety_001.json")
    page.goto(base_url, wait_until="networkidle")
    building = page.locator(
        '[data-active-seat="true"] [data-turn-step-building-id="indulgences"]'
        '[data-turn-step-offered="true"]'
    )
    _click_handle_centre(page, building.element_handle(), require_hit=True)
    direction = page.locator(
        '[data-turn-step-direction="sell_piety"][data-turn-step-offered="true"]'
    )
    _click_handle_centre(page, direction.element_handle(), require_hit=True)

    styles = page.evaluate(
        """() => {
          const piety = document.querySelector(
            '[data-piety-choice-pill][data-piety-choice-offered="true"] [data-piety-choice-silver]'
          );
          const board = document.querySelector(
            '[data-component="player-board-v2"] [data-resource="silver"] text'
          );
          const background = Array.from(
            document.querySelectorAll('[data-component="piety-track-v2"] rect')
          ).find(node => getComputedStyle(node).fill === 'rgb(185, 185, 180)');
          const css = node => {
            const style = getComputedStyle(node);
            return {fontSize: style.fontSize, fontWeight: style.fontWeight, fill: style.fill};
          };
          return {piety: css(piety), board: css(board), background: css(background).fill};
        }"""
    )
    assert styles["piety"] == styles["board"]

    def rgb(value: str) -> tuple[int, int, int]:
        return tuple(
            int(channel) for channel in value.removeprefix("rgb(").removesuffix(")").split(", ")
        )

    foreground = rgb(styles["piety"]["fill"])
    background = rgb(styles["background"])

    def relative_luminance(colour: tuple[int, int, int]) -> float:
        channels = [channel / 255 for channel in colour]
        linear = [
            value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
            for value in channels
        ]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    light = relative_luminance(foreground)
    dark = relative_luminance(background)
    contrast = (max(light, dark) + 0.05) / (min(light, dark) + 0.05)
    assert contrast >= 4.5


def test_conversion_prompt_height_is_reserved_before_and_after_activation(page, serve) -> None:
    base_url, _server = serve(SCENARIOS / "two_active_conversions_001.json")
    page.goto(base_url, wait_until="networkidle")
    height_before = page.locator('[data-component="play-turn"]').bounding_box()["height"]
    building = page.locator(
        '[data-active-seat="true"] [data-turn-step-building-id="grain_store"]'
        '[data-turn-step-offered="true"]'
    )
    _click_handle_centre(page, building.element_handle(), require_hit=True)
    height_after = page.locator('[data-component="play-turn"]').bounding_box()["height"]
    assert height_after == height_before


def test_conversion_does_not_render_zero_before_first_resource_click(page, serve) -> None:
    base_url, _server = serve(SCENARIOS / "two_active_conversions_001.json")
    page.goto(base_url, wait_until="networkidle")
    building = page.locator(
        '[data-active-seat="true"] [data-turn-step-building-id="grain_store"]'
        '[data-turn-step-offered="true"]'
    )
    _click_handle_centre(page, building.element_handle(), require_hit=True)
    direction = page.locator(
        '[data-turn-step-direction="sell_wheat"][data-turn-step-offered="true"]'
    )
    _click_handle_centre(page, direction.element_handle(), require_hit=True)
    assert page.locator('[data-turn-step-amount-total="true"]').inner_text() == ""


def test_conversion_playtest_starts_from_setup_and_commits_from_player_board(page, serve) -> None:
    base_url, server = serve(None)
    page.goto(base_url, wait_until="networkidle")
    page.select_option("#test_position", PLAYTEST_CONVERSIONS)
    submit = page.query_selector('button[type="submit"]')
    assert submit is not None
    _click_handle_centre(page, submit, require_hit=True)
    page.wait_for_load_state("networkidle")
    page.wait_for_selector('[data-component="play-log"]')

    _choose_conversion(page, "grain_store", "sell_wheat", 1)
    assert _confirm_enabled(page)
    page.locator('[data-turn-control="confirm"]').click()
    page.wait_for_timeout(100)

    assert server.state.turn_progress.used_buildings == frozenset({"grain_store"})
    assert (
        page.locator(
            '[data-active-seat="true"] [data-turn-step-building-id="stone_yard"]'
            '[data-turn-step-offered="true"]'
        ).count()
        == 1
    )


def test_conversion_playtest_draws_only_owned_buildings_in_player_slots(page, serve) -> None:
    base_url, server = serve(SCENARIOS / "playtest" / PLAYTEST_CONVERSIONS)
    page.goto(base_url, wait_until="networkidle")

    player_ids = ("player_one", "player_two")
    owned = {
        player_id: set(
            server.payload["state"]["players"][index]["player_board_slots"]["active_buildings"]
        )
        for index, player_id in enumerate(player_ids)
    }
    rendered = {}
    for player_id in player_ids:
        rendered[player_id] = set(
            page.locator(
                f'[data-component="player-board-v2"][data-player="{player_id}"] '
                '[data-player-board-slot][data-building-id]:not([data-building-id=""])'
            ).evaluate_all("nodes => nodes.map(node => node.getAttribute('data-building-id'))")
        )
    assert rendered == owned

    conversion_ids = {step["building_id"] for step in server.payload["turn_steps"]}
    market_only = set(server.payload["state"]["building_market"]) - set().union(*owned.values())
    market_only &= conversion_ids
    assert market_only
    for building_id in market_only:
        assert (
            page.locator(
                f'[data-component="player-board-v2"] [data-building-id="{building_id}"]'
            ).count()
            == 0
        )


def test_building_tooltips_use_catalogue_text_glyphs_and_no_layout_space(page, serve) -> None:
    base_url, _server = serve(SCENARIOS / "playtest" / PLAYTEST_CONVERSIONS)
    page.set_viewport_size({"width": 1600, "height": 1100})
    page.goto(base_url, wait_until="networkidle")
    catalogue = {
        entry["id"]: entry
        for entry in json.loads(
            (SCENARIOS.parent / "configs" / "buildings.json").read_text(encoding="utf-8")
        )["catalogue"]
    }
    panel_heights = page.locator(".panel").evaluate_all(
        "nodes => nodes.map(node => node.getBoundingClientRect().height)"
    )
    tooltip = page.locator('[data-building-tooltip="true"]')

    def contrast_ratio(foreground: str, background: str) -> float:
        def channels(value: str) -> tuple[float, float, float]:
            return tuple(
                float(channel) / 255
                for channel in value.removeprefix("rgb(").removesuffix(")").split(", ")
            )

        def luminance(value: tuple[float, float, float]) -> float:
            linear = [
                channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
                for channel in value
            ]
            return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

        first, second = luminance(channels(foreground)), luminance(channels(background))
        return (max(first, second) + 0.05) / (min(first, second) + 0.05)

    def assert_halo_darkens_map_around_tooltip() -> None:
        target = page.locator('.setup-building-label[data-building-id="mill"]').first
        if target.count() == 0:
            target = page.locator('[data-building-id="mill"]').first
        target.hover()
        page.wait_for_timeout(25)
        tooltip_box = tooltip.bounding_box()
        assert tooltip_box is not None
        margin = 24
        clip = {
            "x": max(0, tooltip_box["x"] - margin),
            "y": max(0, tooltip_box["y"] - margin),
            "width": min(page.viewport_size["width"], tooltip_box["width"] + margin * 2),
            "height": min(page.viewport_size["height"], tooltip_box["height"] + margin * 2),
        }
        shown = Image.open(BytesIO(page.screenshot(clip=clip))).convert("RGB")
        page.mouse.move(5, 5)
        page.wait_for_timeout(25)
        hidden = Image.open(BytesIO(page.screenshot(clip=clip))).convert("RGB")

        def luminance(pixel: tuple[int, int, int]) -> float:
            red, green, blue = pixel
            return 0.2126 * red + 0.7152 * green + 0.0722 * blue

        def patch_luminance(image: Image.Image, x: int, y: int) -> float:
            pixels = [
                luminance(image.getpixel((column, row)))
                for column in range(max(0, x - 2), min(image.width, x + 3))
                for row in range(max(0, y - 2), min(image.height, y + 3))
            ]
            return sum(pixels) / len(pixels)

        local_x = tooltip_box["x"] - clip["x"]
        local_y = tooltip_box["y"] - clip["y"]
        sample_points = {
            "top": (round(local_x + tooltip_box["width"] / 2), round(local_y - 4)),
            "bottom": (
                round(local_x + tooltip_box["width"] / 2),
                round(local_y + tooltip_box["height"] + 4),
            ),
            "left": (round(local_x - 4), round(local_y + tooltip_box["height"] / 2)),
            "right": (
                round(local_x + tooltip_box["width"] + 4),
                round(local_y + tooltip_box["height"] / 2),
            ),
        }
        differences = {
            side: patch_luminance(hidden, *point) - patch_luminance(shown, *point)
            for side, point in sample_points.items()
        }
        assert all(difference >= 4.0 for difference in differences.values()), differences

    for building_id in ("stone_yard", "confession_box", "mill", "chapter_house"):
        target = page.locator(f'.setup-building-label[data-building-id="{building_id}"]').first
        if target.count() == 0:
            target = page.locator(f'[data-building-id="{building_id}"]').first
        target.hover()
        page.wait_for_timeout(25)
        entry = catalogue[building_id]
        assert tooltip.get_attribute("data-building-tooltip-visible") == "true"
        assert tooltip.locator(".building-tooltip-name").inner_text() == entry["name"]
        assert tooltip.locator(".building-tooltip-category").text_content() == entry["category"]
        expected_description_text = entry["description"]
        for token in ("{wheat}", "{stone}", "{silver}"):
            expected_description_text = expected_description_text.replace(token, "")
        assert (
            tooltip.locator(".building-tooltip-description").text_content()
            == expected_description_text
        )
        assert tooltip.locator(".building-tooltip-name [data-tooltip-resource]").count() == 0

        tooltip_box = tooltip.bounding_box()
        assert tooltip_box is not None
        viewport = page.evaluate("({width: innerWidth, height: innerHeight})")
        assert tooltip_box["x"] >= 0
        assert tooltip_box["y"] >= 0
        assert tooltip_box["x"] + tooltip_box["width"] <= viewport["width"]
        assert tooltip_box["y"] + tooltip_box["height"] <= viewport["height"]
        assert tooltip.evaluate("node => getComputedStyle(node).position") == "fixed"
        assert tooltip.evaluate("node => node.parentElement === document.body")

        card = tooltip.locator(".building-tooltip-card")
        description = tooltip.locator(".building-tooltip-description")
        card_box = card.bounding_box()
        description_box = description.bounding_box()
        assert card_box is not None and description_box is not None
        assert description_box["x"] >= card_box["x"] + 12
        assert (
            description_box["x"] + description_box["width"]
            <= card_box["x"] + card_box["width"] - 12
        )
        assert description_box["y"] >= card_box["y"] + 12
        assert (
            description_box["y"] + description_box["height"]
            <= card_box["y"] + card_box["height"] - 12
        )
        line_boxes = description.evaluate(
            """node => {
              const range = document.createRange();
              range.selectNodeContents(node);
              return Array.from(range.getClientRects()).map(box => ({
                x: box.x, y: box.y, right: box.right, bottom: box.bottom
              }));
            }"""
        )
        assert line_boxes
        assert all(
            box["x"] >= card_box["x"] + 12
            and box["right"] <= card_box["x"] + card_box["width"] - 12
            and box["y"] >= card_box["y"] + 12
            and box["bottom"] <= card_box["y"] + card_box["height"] - 12
            for box in line_boxes
        )

        name_box = tooltip.locator(".building-tooltip-name").bounding_box()
        category_box = tooltip.locator(".building-tooltip-category").bounding_box()
        assert name_box is not None and category_box is not None
        assert name_box["x"] + name_box["width"] <= category_box["x"]
        assert (
            tooltip.locator(".building-tooltip-category").evaluate(
                "node => getComputedStyle(node).textTransform"
            )
            == "uppercase"
        )
        foreground = description.evaluate("node => getComputedStyle(node).color")
        background = card.evaluate("node => getComputedStyle(node).backgroundColor")
        assert contrast_ratio(foreground, background) >= 4.5

        if building_id == "stone_yard":
            tooltip_glyph = tooltip.locator('[data-tooltip-resource="stone"]')
            board_glyph = page.locator(
                '[data-component="player-board-v2"] [data-resource-choice-glyph="stone"]'
            ).first
            assert tooltip_glyph.count() == 1
            assert tooltip_glyph.locator('[data-resource="stone"]').count() == 1
            assert tooltip_glyph.locator('[data-resource="stone"]').evaluate(
                "node => node.firstElementChild.tagName"
            ) == board_glyph.evaluate("node => node.firstElementChild.tagName")
        elif building_id == "confession_box":
            assert tooltip.locator("[data-tooltip-resource]").count() == 0

        assert (
            page.locator(".panel").evaluate_all(
                "nodes => nodes.map(node => node.getBoundingClientRect().height)"
            )
            == panel_heights
        )
        page.mouse.move(5, 5)

    assert_halo_darkens_map_around_tooltip()


TOOLTIP_MAP_BUILDING = '.setup-building-label[data-building-id="mill"]'
TOOLTIP_BOARD_BUILDING = '[data-component="player-board-v2"] [data-building-id="grain_store"]'
# A flat colour laid over the whole page, under the tooltip's own z-index of 1000. The tooltip is
# untouched; the backdrop only removes the question of what counts as background, so "where does
# the parchment end" is a fact about one channel rather than a guess about hexes and board cream.
TOOLTIP_SILHOUETTE_BACKDROP = """
  const backdrop = document.createElement('div');
  backdrop.id = 'silhouette-backdrop';
  backdrop.style.cssText =
    'position:fixed;inset:0;background:#FF00FF;z-index:999;pointer-events:none';
  document.body.appendChild(backdrop);
"""


def _luminance(pixel: tuple[int, int, int]) -> float:
    red, green, blue = pixel
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _crop_around(page, box: dict, margin: int) -> dict:
    """A screenshot clip around the tooltip, kept inside the viewport so its origin stays known."""
    viewport = page.viewport_size
    x = max(0.0, box["x"] - margin)
    y = max(0.0, box["y"] - margin)
    return {
        "x": x,
        "y": y,
        "width": min(box["x"] + box["width"] + margin, float(viewport["width"])) - x,
        "height": min(box["y"] + box["height"] + margin, float(viewport["height"])) - y,
    }


def _hover_tooltip(page, selector: str):
    """Hover a building wherever it is drawn and hand back the tooltip and its box."""
    assert page.locator(selector).count() >= 1, selector
    target = page.locator(selector).first
    target.scroll_into_view_if_needed()
    target.hover()
    page.wait_for_timeout(60)
    tooltip = page.locator('[data-building-tooltip="true"]')
    assert tooltip.get_attribute("data-building-tooltip-visible") == "true"
    box = tooltip.bounding_box()
    assert box is not None
    return tooltip, box


def _parchment_edges(page, selector: str) -> tuple[list[int], list[int]]:
    """Where the painted parchment starts and stops in every column across the tooltip.

    Against the flat backdrop the parchment is the only thing on the page with green in it, so the
    first and last row carrying green in a column are its top and bottom edge at that x.
    """
    _tooltip, box = _hover_tooltip(page, selector)
    page.evaluate(TOOLTIP_SILHOUETTE_BACKDROP)
    clip = _crop_around(page, box, 8)
    shot = Image.open(BytesIO(page.screenshot(clip=clip))).convert("RGB")
    page.evaluate("document.getElementById('silhouette-backdrop').remove()")

    left = round(box["x"] - clip["x"])
    top = round(box["y"] - clip["y"])
    width, height = round(box["width"]), round(box["height"])
    tops: list[int] = []
    bottoms: list[int] = []
    for step in range(round(width * 0.02), round(width * 0.98)):
        column = left + step
        painted = [
            row
            for row in range(max(0, top - 6), min(shot.height, top + height + 6))
            if shot.getpixel((column, row))[1] > 100
        ]
        if painted:
            tops.append(painted[0] - top)
            bottoms.append(painted[-1] - top)
    assert len(tops) > round(width * 0.9), "the parchment was not found across the tooltip"
    return tops, bottoms


def _halo_darkening(page, selector: str, side: str, depth: int = 32) -> tuple[list[float], float]:
    """How much luminance the tooltip takes out of the background, pixel by pixel outward.

    Measured against the page as it really is, by screenshotting the same clip with the tooltip up
    and with it gone: differencing the two cancels whatever is behind, so a hex border or a board
    edge cannot be mistaken for the halo. Averaging each step over the middle band of rows keeps a
    single dark line in the background from showing up as a notch in the profile.
    """
    _tooltip, box = _hover_tooltip(page, selector)
    clip = _crop_around(page, box, depth + 12)
    shown = Image.open(BytesIO(page.screenshot(clip=clip))).convert("RGB")
    page.mouse.move(5, 5)
    page.wait_for_timeout(60)
    hidden = Image.open(BytesIO(page.screenshot(clip=clip))).convert("RGB")

    left = round(box["x"] - clip["x"])
    right = round(box["x"] + box["width"] - clip["x"])
    top = round(box["y"] - clip["y"])
    height = round(box["height"])
    rows = range(top + round(height * 0.25), top + round(height * 0.75))

    darkening: list[float] = []
    background: list[float] = []
    for distance in range(1, depth + 1):
        column = left - distance if side == "left" else right + distance
        assert 0 <= column < shown.width, "the walk outward left the screenshot"
        behind = [_luminance(hidden.getpixel((column, row))) for row in rows]
        lit = [_luminance(shown.getpixel((column, row))) for row in rows]
        darkening.append(sum(behind) / len(behind) - sum(lit) / len(lit))
        background.append(sum(behind) / len(behind))
    return darkening, sum(background) / len(background)


def test_building_tooltip_parchment_has_torn_top_and_bottom_edges(page, serve) -> None:
    """The parchment is a scrap of vellum, so neither long edge may be a straight line."""
    base_url, _server = serve(SCENARIOS / "playtest" / PLAYTEST_CONVERSIONS)
    page.set_viewport_size({"width": 1600, "height": 1100})
    page.goto(base_url, wait_until="networkidle")

    for where, selector in (
        ("map", TOOLTIP_MAP_BUILDING),
        ("player board", TOOLTIP_BOARD_BUILDING),
    ):
        tops, bottoms = _parchment_edges(page, selector)
        for edge, found in (("top", tops), ("bottom", bottoms)):
            spread = max(found) - min(found)
            assert spread > 2, f"the {edge} edge over the {where} is straight to {spread}px"

        sampled = [tops[round(place * (len(tops) - 1) / 8)] for place in range(9)]
        assert len(set(sampled)) >= 4, f"the top edge over the {where} repeats: {sampled}"
        page.mouse.move(5, 5)


def test_building_tooltip_halo_fades_gradually_outward(page, serve) -> None:
    """The lift is a soft pool that finishes falling off, not a slab that stops somewhere."""
    base_url, _server = serve(SCENARIOS / "playtest" / PLAYTEST_CONVERSIONS)
    page.set_viewport_size({"width": 1600, "height": 1100})
    page.goto(base_url, wait_until="networkidle")

    for where, selector, side in (
        ("map", TOOLTIP_MAP_BUILDING, "right"),
        ("player board", TOOLTIP_BOARD_BUILDING, "right"),
    ):
        darkening, background = _halo_darkening(page, selector, side)
        assert background > 120, (
            f"the walk outward over the {where} runs across page chrome at {background:.0f},"
            " which no darkening could show up against"
        )
        assert darkening[0] >= 10, f"nothing darkens the {where} beside the parchment: {darkening}"

        steps = list(zip(darkening, darkening[1:], strict=False))
        assert all(nearer - further > -2.0 for nearer, further in steps), (
            f"the darkening over the {where} deepens again further out: {darkening}"
        )
        assert max(nearer - further for nearer, further in steps) <= darkening[0] / 2, (
            f"the darkening over the {where} falls off a cliff: {darkening}"
        )
        assert darkening[len(darkening) // 3] >= 4.0, (
            f"the darkening over the {where} is an edge, not a gradient: {darkening}"
        )
        assert darkening[-1] <= 2.0, (
            f"the darkening over the {where} is still {darkening[-1]:.1f} where the walk ends,"
            f" so the blur never finished falling off: {darkening}"
        )


def test_building_tooltip_halo_lifts_a_player_board_as_well_as_the_map(page, serve) -> None:
    """Cream board and yellow hex both need the lift; a halo drawn on only one of them is a bug."""
    base_url, _server = serve(SCENARIOS / "playtest" / PLAYTEST_CONVERSIONS)
    page.set_viewport_size({"width": 1600, "height": 1100})
    page.goto(base_url, wait_until="networkidle")

    over_map, map_background = _halo_darkening(page, TOOLTIP_MAP_BUILDING, "right")
    over_board, board_background = _halo_darkening(page, TOOLTIP_BOARD_BUILDING, "right")

    assert map_background > 120 and board_background > 120, (
        f"map {map_background:.0f} and board {board_background:.0f} must both be lit surfaces"
    )
    assert over_board[0] >= 10, f"the halo does not darken a player board at all: {over_board}"
    assert sum(over_board[:8]) / 8 >= 10, f"the halo barely marks a player board: {over_board[:8]}"
    assert sum(over_board[:8]) / 8 >= sum(over_map[:8]) / 8 * 0.6, (
        f"a player board gets far less lift than the map: board {over_board[:8]},"
        f" map {over_map[:8]}"
    )


def test_building_tooltip_uses_one_anchor_for_map_hex_and_board_slot(page, serve) -> None:
    base_url, _server = serve(SCENARIOS / "playtest" / PLAYTEST_CONVERSIONS)
    page.set_viewport_size({"width": 1600, "height": 1100})
    page.goto(base_url, wait_until="networkidle")
    tooltip = page.locator('[data-building-tooltip="true"]')

    def hover_point(x: float, y: float) -> tuple[float, float]:
        page.mouse.move(0, 0)
        page.mouse.move(x, y)
        page.wait_for_timeout(60)
        assert tooltip.get_attribute("data-building-tooltip-visible") == "true"
        box = tooltip.bounding_box()
        assert box is not None
        return (box["x"], box["y"])

    mill_fill = page.locator('#setup-fills g[data-building-id="mill"]').first
    mill_label = page.locator('#setup-labels g[data-building-id="mill"]').first
    brewery_fill = page.locator('#setup-fills g[data-building-id="brewery"]').first
    brewery_label = page.locator('#setup-labels g[data-building-id="brewery"]').first
    brewery_overlay = page.locator(
        '#conversion-choice-keys [data-turn-step-building-id="brewery"]'
    ).first
    mill_fill_box = mill_fill.bounding_box()
    mill_label_box = mill_label.bounding_box()
    brewery_fill_box = brewery_fill.bounding_box()
    brewery_label_box = brewery_label.bounding_box()
    brewery_overlay_box = brewery_overlay.bounding_box()
    assert (
        mill_fill_box is not None
        and mill_label_box is not None
        and brewery_fill_box is not None
        and brewery_label_box is not None
        and brewery_overlay_box is not None
    )
    mill_points = (
        (
            mill_fill_box["x"] + mill_fill_box["width"] / 2,
            mill_fill_box["y"] + mill_fill_box["height"] * 0.22,
        ),
        (
            mill_fill_box["x"] + mill_fill_box["width"] / 2,
            mill_fill_box["y"] + mill_fill_box["height"] * 0.78,
        ),
        (
            mill_label_box["x"] + mill_label_box["width"] / 2,
            mill_label_box["y"] + mill_label_box["height"] / 2,
        ),
    )
    mill_positions = [hover_point(*point) for point in mill_points]
    assert all(
        abs(position[0] - mill_positions[0][0]) <= 1
        and abs(position[1] - mill_positions[0][1]) <= 1
        for position in mill_positions
    ), mill_positions

    brewery_points = (
        (
            brewery_fill_box["x"] + brewery_fill_box["width"] / 2,
            brewery_fill_box["y"] + brewery_fill_box["height"] * 0.22,
        ),
        (
            brewery_fill_box["x"] + brewery_fill_box["width"] / 2,
            brewery_fill_box["y"] + brewery_fill_box["height"] * 0.78,
        ),
        (
            brewery_label_box["x"] + brewery_label_box["width"] / 2,
            brewery_label_box["y"] + brewery_label_box["height"] / 2,
        ),
        (
            brewery_overlay_box["x"] + brewery_overlay_box["width"] / 2,
            brewery_overlay_box["y"] + brewery_overlay_box["height"] / 2,
        ),
    )
    brewery_positions = [hover_point(*point) for point in brewery_points]
    assert all(
        abs(position[0] - brewery_positions[0][0]) <= 1
        and abs(position[1] - brewery_positions[0][1]) <= 1
        for position in brewery_positions
    ), brewery_positions

    board_slot = page.locator(
        '[data-component="player-board-v2"][data-player="player_one"] '
        '[data-player-board-slot][data-building-id="stone_yard"]'
    ).first
    board_box = board_slot.bounding_box()
    assert board_box is not None
    board_points = (
        (board_box["x"] + board_box["width"] * 0.25, board_box["y"] + board_box["height"] * 0.25),
        (board_box["x"] + board_box["width"] * 0.75, board_box["y"] + board_box["height"] * 0.75),
        (board_box["x"] + board_box["width"] / 2, board_box["y"] + board_box["height"] / 2),
        (board_box["x"] + board_box["width"] * 0.5, board_box["y"] + board_box["height"] * 0.4),
    )
    board_positions = [hover_point(*point) for point in board_points]
    assert all(
        abs(position[0] - board_positions[0][0]) <= 1
        and abs(position[1] - board_positions[0][1]) <= 1
        for position in board_positions
    ), board_positions


def test_every_map_building_has_a_real_hover_tooltip(page, serve) -> None:
    base_url, _server = serve(SCENARIOS / "playtest" / PLAYTEST_CONVERSIONS)
    page.set_viewport_size({"width": 1600, "height": 1100})
    page.goto(base_url, wait_until="networkidle")
    tooltip = page.locator('[data-building-tooltip="true"]')
    map_building_ids = page.locator("#setup-fills g[data-building-id]").evaluate_all(
        "nodes => nodes.map(node => node.getAttribute('data-building-id'))"
    )
    assert map_building_ids
    for building_id in map_building_ids:
        fill = page.locator(f'#setup-fills g[data-building-id="{building_id}"]').first
        box = fill.bounding_box()
        assert box is not None
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        page.wait_for_timeout(60)
        assert tooltip.get_attribute("data-building-tooltip-visible") == "true", building_id


@pytest.mark.parametrize(
    "scenario",
    [PLAYTEST_CONVERSIONS, PLAYTEST_CLOISTERS, PLAYTEST_KOGGE_AND_CLOISTERS],
    ids=["conversions", "cloisters-reach", "kogge-and-cloisters"],
)
def test_every_player_board_building_has_a_real_hover_tooltip(page, serve, scenario: str) -> None:
    base_url, _server = serve(SCENARIOS / "playtest" / scenario)
    page.set_viewport_size({"width": 1600, "height": 1100})
    page.goto(base_url, wait_until="networkidle")
    tooltip = page.locator('[data-building-tooltip="true"]')
    slots = page.locator(
        '[data-component="player-board-v2"][data-seat-taken="true"] '
        '[data-player-board-slot][data-building-id]:not([data-building-id=""])'
    )
    assert slots.count() > 0

    for index in range(slots.count()):
        slot = slots.nth(index)
        building_id = slot.get_attribute("data-building-id")
        box = slot.bounding_box()
        assert building_id and box is not None
        page.mouse.move(0, 0)
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        page.wait_for_timeout(60)
        assert tooltip.get_attribute("data-building-tooltip-visible") == "true", building_id


@pytest.mark.parametrize(
    "scenario",
    [PLAYTEST_CLOISTERS, PLAYTEST_KOGGE_AND_CLOISTERS],
    ids=["cloisters-reach", "kogge-and-cloisters"],
)
def test_an_unoffered_player_board_building_is_hoverable_but_not_clickable(
    page, serve, scenario: str
) -> None:
    base_url, _server = serve(SCENARIOS / "playtest" / scenario)
    page.set_viewport_size({"width": 1600, "height": 1100})
    page.goto(base_url, wait_until="networkidle")
    tooltip = page.locator('[data-building-tooltip="true"]')
    slots = page.locator(
        '[data-component="player-board-v2"][data-seat-taken="true"] '
        '[data-player-board-slot][data-building-id]:not([data-building-id=""])'
    )

    unoffered_slot = None
    unoffered_target = None
    for index in range(slots.count()):
        slot = slots.nth(index)
        target = slot.locator('[data-turn-step-building-id][data-turn-step-click-target="true"]')
        if target.count() and target.get_attribute("data-turn-step-offered") == "false":
            unoffered_slot = slot
            unoffered_target = target
            break
    assert unoffered_slot is not None and unoffered_target is not None

    box = unoffered_slot.bounding_box()
    handle = unoffered_target.element_handle()
    assert box is not None and handle is not None
    page.mouse.move(0, 0)
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.wait_for_timeout(60)
    assert tooltip.get_attribute("data-building-tooltip-visible") == "true"

    before = unoffered_target.get_attribute("data-turn-step-selected")
    x, y = _centre(page, handle)
    assert not _is_hit_target(page, handle, x, y)
    page.mouse.click(x, y)
    page.wait_for_timeout(60)
    assert before == "false"
    assert unoffered_target.get_attribute("data-turn-step-selected") == before


def test_an_offered_player_board_building_still_selects_a_conversion(page, serve) -> None:
    base_url, _server = serve(SCENARIOS / "playtest" / PLAYTEST_CONVERSIONS)
    page.goto(base_url, wait_until="networkidle")
    offered = page.locator(
        '[data-active-seat="true"] [data-turn-step-building-id]'
        '[data-turn-step-click-target="true"][data-turn-step-offered="true"]'
    ).first
    assert offered.count() == 1
    handle = offered.element_handle()
    assert handle is not None
    _click_handle_centre(page, handle, require_hit=True)
    assert offered.get_attribute("data-turn-step-selected") == "true"


def test_brewery_hire_and_convert_click_still_selects_conversion(page, serve) -> None:
    base_url, _server = serve(SCENARIOS / "playtest" / PLAYTEST_CONVERSIONS)
    page.goto(base_url, wait_until="networkidle")

    brewery = page.locator(
        '[data-turn-step-building-id="brewery"][data-turn-step-offered="true"]'
    ).first
    assert brewery.count() == 1
    _click_handle_centre(page, brewery.element_handle(), require_hit=True)
    assert brewery.get_attribute("data-turn-step-selected") == "true"
    hire_pills = page.locator(
        '[data-turn-step-hire-payment][data-turn-step-hire-offered="true"]'
    )
    assert {
        pill.get_attribute("data-turn-step-hire-payment") for pill in hire_pills.all()
    } == {"stone", "silver", "wheat"}
    wheat_payment = page.locator(
        '[data-turn-step-hire-payment="wheat"][data-turn-step-hire-offered="true"]'
    )
    _click_handle_centre(page, wheat_payment.element_handle(), require_hit=True)

    direction = page.locator(
        '[data-turn-step-direction="sell_wheat_for_silver"][data-turn-step-offered="true"]'
    ).first
    assert direction.count() == 1
    _click_handle_centre(page, direction.element_handle(), require_hit=True)
    resource = page.locator('[data-resource-choice-key="wheat"][data-turn-offered="true"]').first
    assert resource.count() == 1
    _click_handle_centre(page, resource.element_handle(), require_hit=True)
    # Brewery is a market hire with three legal hire-payment variants. The payment narrows the
    # conversion before its direction and amount are asked.
    assert page.locator('[data-turn-step-amount-total="true"]').inner_text() == "1"
    assert brewery.get_attribute("data-turn-step-selected") == "true"


def test_cornucopia_hire_payment_is_first_and_every_stone_yard_step_commits(page, serve) -> None:
    """The four concrete payments stay four page-reachable commits, never one stuck frontier."""
    expected_directions = {
        "stone": {"buy_stone"},
        "silver": {"sell_stone"},
        "wheat": {"buy_stone", "sell_stone"},
    }
    paths = (
        ("stone", "buy_stone"),
        ("silver", "sell_stone"),
        ("wheat", "buy_stone"),
        ("wheat", "sell_stone"),
    )

    for payment, direction in paths:
        # Each path needs its own server: a committed step in a shared server can make a later
        # path look good despite no longer starting from the four-way payment frontier.
        base_url, server = serve(SCENARIOS / "playtest" / PLAYTEST_CONVERSIONS)
        server.state = replace(server.state, active_player=PlayerId.PLAYER_TWO)
        server._refresh()
        server._capture_turn_start()
        initial_steps = [
            step for step in server.payload["turn_steps"] if step["building_id"] == "stone_yard"
        ]
        assert len(initial_steps) == 4
        by_path = {
            (step["hire_payment"], step["direction"]): step for step in initial_steps
        }

        page.goto(base_url, wait_until="networkidle")
        assert _confirm_enabled_attribute(page) == "false"
        assert page.get_attribute('[data-turn-control="confirm"]', "data-turn-offered") is None
        building = page.locator(
            '[data-turn-step-building-id="stone_yard"][data-turn-step-offered="true"]'
        ).first
        assert building.count() == 1
        _click_handle_centre(page, building.element_handle(), require_hit=True)

        hire_row = page.locator('[data-turn-step-hire-row="true"]')
        assert hire_row.get_attribute("data-turn-step-row-active") == "true"
        assert page.locator('[data-turn-step-hire-text="true"]').inner_text() == (
            "Hire Stone Yard from Red for 1 resource of your choice."
        )
        assert {
            pill.get_attribute("data-turn-step-hire-payment")
            for pill in page.locator(
                '[data-turn-step-hire-payment][data-turn-step-hire-offered="true"]'
            ).all()
        } == {"stone", "silver", "wheat"}
        assert not _confirm_enabled(page)
        assert _confirm_enabled_attribute(page) == "false"

        hire = page.locator(
            f'[data-turn-step-hire-payment="{payment}"][data-turn-step-hire-offered="true"]'
        )
        _click_handle_centre(page, hire.element_handle(), require_hit=True)
        assert _confirm_enabled_attribute(page) == "false"
        offered_directions = {
            button.get_attribute("data-turn-step-direction")
            for button in page.locator(
                '[data-turn-step-direction][data-turn-step-offered="true"]'
            ).all()
        }
        assert offered_directions == expected_directions[payment]

        direction_button = page.locator(
            f'[data-turn-step-direction="{direction}"][data-turn-step-offered="true"]'
        )
        _click_handle_centre(page, direction_button.element_handle(), require_hit=True)
        assert not _confirm_enabled(page)
        assert _confirm_enabled_attribute(page) == "false"

        amount = page.locator(
            '[data-active-seat="true"] [data-resource-choice-key="stone"]'
            '[data-turn-offered="true"]'
        )
        _click_handle_centre(page, amount.element_handle(), require_hit=True)
        assert _confirm_enabled(page)
        assert _confirm_enabled_attribute(page) == "true"

        page.locator('[data-turn-control="confirm"]').click()
        page.wait_for_selector(
            '[data-turn-step-building-id="stone_yard"][data-turn-step-used="true"]'
        )
        step = by_path[payment, direction]
        hired = next(
            event
            for event in server.state.events
            if event.action_id == step["step_id"] and event.event_type is EventType.BUILDING_HIRED
        )
        assert {
            name: dict(hired.details)[name]
            for name in ("building_id", "resource", "amount", "payee")
        } == {
            "building_id": "stone_yard",
            "resource": payment,
            "amount": 1,
            "payee": "player_one",
        }
        verb = "buy" if direction == "buy_stone" else "sell"
        delta = "Yellow stone +1; silver -1" if verb == "buy" else "Yellow stone -1; silver +1"
        assert page.locator(".log-event").all_inner_texts() == [
            f"Yellow hired Stone Yard from Red and paid 1 {payment}.",
            f"Yellow used the Stone Yard to {verb} 1 stone for 1 silver.",
            delta,
        ]


def test_two_active_conversions_leave_the_other_building_offered(page, serve) -> None:
    base_url, server = serve(SCENARIOS / "two_active_conversions_001.json")
    page.goto(base_url, wait_until="networkidle")

    _choose_conversion(page, "grain_store", "sell_wheat", 1)
    page.locator('[data-turn-control="confirm"]').click()
    page.wait_for_timeout(100)

    assert (
        page.locator(
            '[data-active-seat="true"] [data-turn-step-building-id="grain_store"]'
            '[data-turn-step-offered="true"]'
        ).count()
        == 0
    )
    assert (
        page.locator(
            '[data-active-seat="true"] [data-turn-step-building-id="grain_store"]'
            '[data-turn-step-used="true"]'
        ).count()
        == 1
    )
    assert (
        page.locator(
            '[data-active-seat="true"] [data-turn-step-building-id="stone_yard"]'
            '[data-turn-step-offered="true"]'
        ).count()
        == 1
    )
    assert "grain_store" in server.state.turn_progress.used_buildings


def test_two_active_conversions_do_not_offer_an_absent_amount(page, serve) -> None:
    base_url, _server = serve(SCENARIOS / "two_active_conversions_001.json")
    page.goto(base_url, wait_until="networkidle")

    building = page.query_selector(
        '[data-active-seat="true"] [data-turn-step-building-id="grain_store"]'
        '[data-turn-step-offered="true"]'
    )
    assert building is not None
    _click_handle_centre(page, building, require_hit=True)
    direction = page.query_selector(
        '[data-turn-step-direction="sell_wheat"][data-turn-step-offered="true"]'
    )
    assert direction is not None
    _click_handle_centre(page, direction, require_hit=True)

    resource_key = page.locator(
        '[data-active-seat="true"] [data-resource-choice-key="wheat"][data-turn-offered="true"]'
    )
    assert resource_key.count() == 1
    _click_handle_centre(page, resource_key.element_handle(), require_hit=True)
    assert (
        page.locator(
            '[data-active-seat="true"] [data-resource-choice-key="wheat"][data-turn-offered="true"]'
        ).count()
        == 0
    )
    assert page.locator('[data-turn-step-amount="2"]').count() == 0
    assert page.locator('[data-turn-step-amount-total="true"]').inner_text() == "1"
    assert _confirm_enabled(page), "Confirm did not accept the only engine-offered amount"


def test_two_active_conversions_reset_restores_the_turn_start_position(page, serve) -> None:
    base_url, server = serve(SCENARIOS / "two_active_conversions_001.json")
    initial = server.state
    page.goto(base_url, wait_until="networkidle")

    _choose_conversion(page, "grain_store", "sell_wheat", 1)
    page.locator('[data-turn-control="confirm"]').click()
    page.wait_for_timeout(100)
    assert server.state != initial
    assert server.state.turn_progress.used_buildings == frozenset({"grain_store"})
    assert page.get_attribute('[data-turn-control="reset"]', "data-turn-control-enabled") == "true"

    page.locator('[data-turn-control="reset"]').click()
    page.wait_for_timeout(100)

    assert server.state == initial
    assert server.state.turn_progress.used_buildings == frozenset()
    assert (
        page.locator(
            '[data-active-seat="true"] [data-turn-step-building-id="grain_store"]'
            '[data-turn-step-offered="true"]'
        ).count()
        == 1
    )


def _reach_paid_alms(page) -> None:
    _click_if_offered(page, '[data-board-position-index="0"][data-turn-start-candidate="true"]')
    _click_if_offered(page, '[data-arrow="city->south"][data-turn-offered="true"]')
    _click_if_offered(page, '[data-board-position-index="5"][data-turn-duty-candidate="true"]')
    for selector in (
        '[data-turn-control="action"][data-turn-control-enabled="true"]',
        '[data-resolution-key="give_alms_paid"][data-turn-offered="true"]',
    ):
        handle = page.query_selector(selector)
        assert handle is not None, f"missing Give Alms target {selector}"
        _click_handle_centre(page, handle, require_hit=True)
        page.wait_for_timeout(40)


def _active_board_snapshot(page) -> dict:
    player = page.get_attribute('[data-active-seat="true"]', "data-player")
    assert player is not None
    return _all_board_snapshots(page)[player]


def _all_board_snapshots(page) -> dict[str, dict]:
    return page.evaluate(
        """() => {
          const visible = node => node && node.getAttribute('opacity') !== '0'
            && node.getAttribute('visibility') !== 'hidden';
          const cityCount = player => Array.from(document.querySelectorAll(
            `[data-city-column-player="${player}"][data-city-cube]`
          )).filter(visible).length;
          const result = {};
          document.querySelectorAll('[data-component="player-board-v2"][data-player]').forEach(board => {
            const player = board.getAttribute('data-player');
            const stock = resource => Number(
              board.querySelector(`[data-resource="${resource}"] text`).textContent
            );
            result[player] = {
              resources: Object.fromEntries(['stone', 'silver', 'wheat'].map(resource => [
                resource, stock(resource)
              ])),
              village: Array.from(board.querySelectorAll('[data-token="village"]')).filter(visible).length,
              abbey: Array.from(board.querySelectorAll('[data-token="abbey"]')).filter(visible).length,
              city: cityCount(player)
            };
          });
          return result;
        }"""
    )


def _all_alms_positions(page) -> dict[str, str]:
    return page.evaluate(
        """() => Object.fromEntries(Array.from(
          document.querySelectorAll('[data-player-disc="true"][data-player]')
        ).filter(disc => disc.getAttribute('data-alms-position') !== null).map(disc => [
          disc.getAttribute('data-player'), disc.getAttribute('data-alms-position')
        ]))"""
    )


def _expected_board_snapshot(state, player) -> dict:
    record = state.player_state(player)
    return {
        "resources": {
            resource: getattr(record.resources, resource)
            for resource in ("stone", "silver", "wheat")
        },
        "village": record.workforce.village,
        "abbey": record.workforce.abbey,
        "city": record.workforce.mancala[0],
    }


def _alms_board_snapshot(snapshot: dict) -> dict:
    """The player-board fields settled by an Alms payment, excluding route sowing cubes."""
    return {key: value for key, value in snapshot.items() if key != "city"}


def _alms_payment_action(server: PlayServer, units: int):
    value = f"silver={units},wheat=0"
    candidate = next(
        candidate
        for candidate in server.payload["turn_candidates"]
        if [step["value"] for step in candidate["steps"][:4]]
        == [0, "city->south", 5, "give_alms_paid"]
        and any(
            step.get("resource_allocation_any_total") and step["value"] == value
            for step in candidate["steps"]
        )
    )
    return next(
        action
        for action in legal_actions(server.state, server.config)
        if action_id(action) == candidate["action_id"]
    )


def _click_alms_silver(page) -> None:
    handle = page.query_selector(
        '[data-active-seat="true"] [data-resource-choice-key="silver"][data-turn-offered="true"]'
    )
    assert handle is not None, "silver was not offered as an Alms payment pill"
    _click_handle_centre(page, handle, require_hit=True)
    page.wait_for_timeout(50)


def _screenshot_alms_and_active_board(page, path: Path) -> None:
    boxes = [
        page.locator(".p-alms > svg").bounding_box(),
        page.locator(
            '[data-component="player-board-v2"][data-active-seat="true"] > svg'
        ).bounding_box(),
    ]
    assert all(box is not None for box in boxes)
    valid = [box for box in boxes if box is not None]
    left = min(box["x"] for box in valid)
    top = min(box["y"] for box in valid)
    right = max(box["x"] + box["width"] for box in valid)
    bottom = max(box["y"] + box["height"] for box in valid)
    page.screenshot(
        path=str(path),
        clip={
            "x": max(0, left - 12),
            "y": max(0, top - 12),
            "width": right - max(0, left - 12) + 24,
            "height": bottom - max(0, top - 12) + 24,
        },
    )


def test_give_alms_pills_build_any_payment_preview_reset_and_confirm(page, serve) -> None:
    base_url, server = serve(SCENARIOS / "give_alms_threshold_rewards_two_crossings_001.json")
    initial_state = server.state
    acting_player = initial_state.active_player
    page.goto(base_url, wait_until="networkidle")
    page.locator('[data-component="play-turn"]').screenshot(
        path=str(SCREENSHOTS / "give-alms-payment-prompt-before.png")
    )
    initial_boards = _all_board_snapshots(page)
    initial_positions = _all_alms_positions(page)

    _reach_paid_alms(page)
    assert page.locator('[data-combination-key][data-turn-offered="true"]').count() == 0
    assert (
        page.locator(
            '[data-active-seat="true"] [data-resource-choice-key][data-turn-offered="true"]'
        ).count()
        == 2
    )
    max_units = max(
        action.alms_payment_silver + action.alms_payment_wheat
        for action in legal_actions(server.state, server.config)
        if action.resolution.value == "give_alms_paid"
    )
    assert max_units > 2

    for units in range(1, max_units + 1):
        _click_alms_silver(page)
        action = _alms_payment_action(server, units)
        expected_state = apply_action(initial_state, action, server.config).state
        assert _alms_board_snapshot(_active_board_snapshot(page)) == _alms_board_snapshot(
            _expected_board_snapshot(expected_state, acting_player)
        ), f"preview mismatch at {units} Alms unit(s)"
        if units == max_units:
            assert _active_board_snapshot(page) == _expected_board_snapshot(
                expected_state, acting_player
            )
        assert page.get_attribute(
            f'[data-player-disc="true"][data-player="{acting_player.name.lower()}"]',
            "data-alms-position",
        ) == str(expected_state.player_state(acting_player).alms_position)
        assert _confirm_enabled(page), f"Confirm did not light after {units} Alms unit(s)"
        if units == 1:
            _screenshot_alms_and_active_board(page, SCREENSHOTS / "give-alms-payment-after-one.png")
        if units == 2:
            _screenshot_alms_and_active_board(page, SCREENSHOTS / "give-alms-payment-after-two.png")

    assert (
        page.locator(
            '[data-active-seat="true"] [data-resource-choice-key][data-turn-offered="true"]'
        ).count()
        == 0
    )
    assert server.state == initial_state
    assert {
        player: snapshot
        for player, snapshot in _all_board_snapshots(page).items()
        if player != acting_player.name.lower()
    } == {
        player: snapshot
        for player, snapshot in initial_boards.items()
        if player != acting_player.name.lower()
    }

    page.locator('[data-turn-control="reset"]').click()
    page.wait_for_timeout(100)
    assert _all_board_snapshots(page) == initial_boards
    assert _all_alms_positions(page) == initial_positions
    assert server.state == initial_state

    _reach_paid_alms(page)
    _click_alms_silver(page)
    _click_alms_silver(page)
    expected_state = apply_action(
        initial_state, _alms_payment_action(server, 2), server.config
    ).state
    assert _alms_board_snapshot(_active_board_snapshot(page)) == _alms_board_snapshot(
        _expected_board_snapshot(expected_state, acting_player)
    )
    page.locator('[data-turn-control="confirm"]').click()
    page.wait_for_timeout(140)
    assert server.state == expected_state
    assert _all_alms_positions(page)[acting_player.name.lower()] == str(
        expected_state.player_state(acting_player).alms_position
    )


def test_give_alms_threshold_rewards_preview_in_order_and_match_confirm(page, serve) -> None:
    base_url, server = serve(SCENARIOS / "give_alms_threshold_rewards_two_crossings_001.json")
    initial_state = server.state
    acting_player = initial_state.active_player
    page.goto(base_url, wait_until="networkidle")
    initial_boards = _all_board_snapshots(page)
    _reach_paid_alms(page)

    action = _alms_payment_action(server, 4)
    expected_state = apply_action(initial_state, action, server.config).state
    candidate = next(
        candidate
        for candidate in server.payload["turn_candidates"]
        if candidate["action_id"] == action_id(action)
    )
    step = next(step for step in candidate["steps"] if step.get("resource_allocation_any_total"))
    rewards = step["alms_threshold_reward"]
    assert [reward["threshold"] for reward in rewards] == [2, 4]
    assert [reward["reward"] for reward in rewards] == [
        server.config.alms.threshold_reward_for_row(reward["threshold"]) for reward in rewards
    ]
    assert all(reward["moved"] is True for reward in rewards)
    assert all(
        event.event_type.value != "workforce_move"
        for event in apply_action(initial_state, action, server.config).events
    )

    for _ in range(4):
        _click_alms_silver(page)
    assert _active_board_snapshot(page) == _expected_board_snapshot(expected_state, acting_player)
    assert _all_alms_positions(page)[acting_player.name.lower()] == str(
        expected_state.player_state(acting_player).alms_position
    )
    assert _confirm_enabled(page)
    assert {
        player: snapshot
        for player, snapshot in _all_board_snapshots(page).items()
        if player != acting_player.name.lower()
    } == {
        player: snapshot
        for player, snapshot in initial_boards.items()
        if player != acting_player.name.lower()
    }

    page.locator('[data-turn-control="confirm"]').click()
    page.wait_for_timeout(140)
    assert server.state == expected_state
    assert _all_alms_positions(page)[acting_player.name.lower()] == str(
        expected_state.player_state(acting_player).alms_position
    )


def test_give_alms_row_six_preview_keeps_unavailable_reward_and_matches_confirm(
    page, serve
) -> None:
    base_url, server = serve(SCENARIOS / "give_alms_threshold_reward_row_six_001.json")
    initial_state = server.state
    acting_player = initial_state.active_player
    page.goto(base_url, wait_until="networkidle")
    initial_boards = _all_board_snapshots(page)
    _reach_paid_alms(page)

    action = _alms_payment_action(server, 3)
    expected_state = apply_action(initial_state, action, server.config).state
    result = apply_action(initial_state, action, server.config)
    candidate = next(
        candidate
        for candidate in server.payload["turn_candidates"]
        if candidate["action_id"] == action_id(action)
    )
    step = next(step for step in candidate["steps"] if step.get("resource_allocation_any_total"))
    rewards = step["alms_threshold_reward"]
    assert [reward["threshold"] for reward in rewards] == [4, 6]
    assert rewards[0]["moved"] is False
    assert rewards[1]["moved"] is True
    assert all(event.event_type.value != "workforce_move" for event in result.events)

    for _ in range(3):
        _click_alms_silver(page)
    assert _active_board_snapshot(page) == _expected_board_snapshot(expected_state, acting_player)
    assert _all_alms_positions(page)[acting_player.name.lower()] == str(
        expected_state.player_state(acting_player).alms_position
    )
    before = _expected_board_snapshot(initial_state, acting_player)
    preview = _active_board_snapshot(page)
    assert preview["abbey"] == before["abbey"], "the unavailable row-four reward moved an acolyte"
    assert _confirm_enabled(page)
    assert {
        player: snapshot
        for player, snapshot in _all_board_snapshots(page).items()
        if player != acting_player.name.lower()
    } == {
        player: snapshot
        for player, snapshot in initial_boards.items()
        if player != acting_player.name.lower()
    }

    page.locator('[data-turn-control="confirm"]').click()
    page.wait_for_timeout(140)
    assert server.state == expected_state
    assert _all_alms_positions(page)[acting_player.name.lower()] == str(
        expected_state.player_state(acting_player).alms_position
    )
