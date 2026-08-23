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

from pilgrim.model.actions import action_id
from pilgrim.rules.transition import apply_action, legal_actions
from tools.play_server import PlayServer

pytestmark = pytest.mark.slow

SCENARIOS = Path(__file__).resolve().parents[1] / "scenarios"
SCREENSHOTS = Path(__file__).resolve().parents[1] / "screenshots"
PLAYTEST_CLOISTERS = "cloisters_reach_2p.json"
PLAYTEST_CLOISTERS_LOOP = "cloisters_loop_2p.json"
PLAYTEST_KOGGE_AND_CLOISTERS = "kogge_and_cloisters_2p.json"
PLAYTEST_CONVERSIONS = "conversions_2p.json"


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
        '[data-board-position-index][data-turn-start-relocation-candidate="true"]',
        '[data-board-position-index][data-turn-skip-candidate="true"]',
        '[data-board-position-index][data-turn-end-relocation-candidate="true"]',
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
        clip={"x": left - 10, "y": top - 10, "width": right - left + 20, "height": bottom - top + 20},
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


def test_taxation_step_two_pills_filter_survivors_and_reach_all_six_multisets(
    page, serve
) -> None:
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

        assert page.locator('[data-turn-prompt*="choose 2 resources."]'
                            '[data-turn-offered="true"]').count() == 1
        assert page.locator(
            '[data-active-seat="true"] [data-resource-choice-key][data-turn-offered="true"]'
        ).count() == 3
        if combination == ("stone", "stone"):
            page.screenshot(path=str(SCREENSHOTS / "taxation-six-option-position.png"), full_page=True)

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
        assert page.locator(
            '[data-active-seat="true"] [data-resource-choice-key][data-turn-offered="true"]'
        ).count() > 0
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
        assert page.locator(
            '[data-active-seat="true"] [data-resource-choice-key][data-turn-offered="true"]'
        ).count() == 0
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

    assert page.locator(
        '[data-active-seat="true"] [data-resource-choice-key="wheat"]'
        '[data-turn-offered="true"]'
    ).count() == 0
    assert page.locator(
        '[data-active-seat="true"] [data-resource-choice-key="stone"]'
        '[data-turn-offered="true"]'
    ).count() == 1
    assert page.locator(
        '[data-active-seat="true"] [data-resource-choice-key="silver"]'
        '[data-turn-offered="true"]'
    ).count() == 1
    assert not _confirm_enabled(page)


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
    assert page.locator(
        '[data-active-seat="true"] [data-resource-choice-key][data-turn-offered="true"]'
    ).count() == 3

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
        player: holdings
        for player, holdings in others_before.items()
        if player != active_player_id
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

    for selector in (
        '[data-arrow="city->north"][data-turn-offered="true"]',
    ):
        handle = page.query_selector(selector)
        assert handle is not None, f"missing produce target {selector}"
        _click_handle_centre(page, handle, require_hit=True)
        page.wait_for_timeout(40)
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

    for selector in (
        '[data-arrow="city->north"][data-turn-offered="true"]',
    ):
        handle = page.query_selector(selector)
        assert handle is not None
        _click_handle_centre(page, handle, require_hit=True)
        page.wait_for_timeout(40)
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
        action for action in legal_actions(server.state, server.config)
        if action_id(action) == candidate["action_id"]
    )
    expected_state = apply_action(server.state, action, server.config).state
    expected_player = expected_state.player_state(acting_player)

    _click_if_offered(
        page, '[data-board-position-index="3"][data-turn-start-candidate="true"]'
    )
    _click_if_offered(page, '[data-arrow="east->south_east"][data-turn-offered="true"]')
    action_control = page.query_selector(
        '[data-turn-control="action"][data-turn-control-enabled="true"]'
    )
    assert action_control is not None
    _click_handle_centre(page, action_control, require_hit=True)
    page.wait_for_timeout(40)
    resolution = page.query_selector(
        '[data-resolution-key="construct_building"][data-turn-offered="true"]'
    )
    assert resolution is not None
    _click_handle_centre(page, resolution, require_hit=True)
    page.wait_for_timeout(40)

    _screenshot_active_board(page, SCREENSHOTS / "construction-preview-before.png")
    building = page.query_selector(
        '[data-building-choice-key="well"][data-turn-offered="true"]'
    )
    assert building is not None
    _click_handle_centre(page, building, require_hit=True)
    page.wait_for_timeout(60)
    _screenshot_active_board(page, SCREENSHOTS / "construction-preview-after.png")

    preview = _player_holdings(page)
    assert preview == {
        "stone": expected_player.resources.stone,
        "silver": expected_player.resources.silver,
        "wheat": expected_player.resources.wheat,
    }
    assert page.locator(
        f'[data-player="{active_player_id}"] [data-player-board-slot][data-building-id="well"]'
    ).count() == 1
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
    assert page.locator(
        f'[data-player="{active_player_id}"] [data-player-board-slot][data-building-id="well"]'
    ).count() == 0

    # The first pass already proves reset restored the preview; Confirm must commit exactly that
    # same state, with no arithmetic in the browser to reconstruct it.
    _click_if_offered(
        page, '[data-board-position-index="3"][data-turn-start-candidate="true"]'
    )
    _click_if_offered(page, '[data-arrow="east->south_east"][data-turn-offered="true"]')
    action_control = page.query_selector(
        '[data-turn-control="action"][data-turn-control-enabled="true"]'
    )
    assert action_control is not None
    _click_handle_centre(page, action_control, require_hit=True)
    page.wait_for_timeout(40)
    resolution = page.query_selector(
        '[data-resolution-key="construct_building"][data-turn-offered="true"]'
    )
    assert resolution is not None
    _click_handle_centre(page, resolution, require_hit=True)
    page.wait_for_timeout(40)
    building = page.query_selector(
        '[data-building-choice-key="well"][data-turn-offered="true"]'
    )
    assert building is not None
    _click_handle_centre(page, building, require_hit=True)
    page.wait_for_timeout(60)
    page.locator('[data-turn-control="confirm"]').click()
    page.wait_for_timeout(120)
    assert _player_holdings(page, f'[data-player="{active_player_id}"]') == preview
    assert page.locator(
        f'[data-player="{active_player_id}"] [data-player-board-slot][data-building-id="well"]'
    ).count() == 1
    assert "well" in server.state.player_state(acting_player).player_board_slots.active_buildings


def test_guild_merchant_preview_waits_for_agreement_and_matches_confirm(page, serve) -> None:
    base_url, server = serve(SCENARIOS / "guild_active_move_merchant_001.json")
    page.goto(base_url, wait_until="networkidle")
    acting_player = server.state.active_player
    active_player_id = page.get_attribute('[data-active-seat="true"]', "data-player")
    before_position = server.state.merchant_board_position
    after_action = next(
        action
        for action in legal_actions(server.state, server.config)
        if action.merchant_advance_building_id == "guild"
    )
    expected_position = apply_action(server.state, after_action, server.config).state.merchant_board_position
    before_others = _all_player_holdings(page)

    def merchant_visible_at(position: int) -> bool:
        return bool(page.evaluate(
            """
            position => Array.from(document.querySelectorAll(
              '[data-component=\"duty-wheel\"] [data-token=\"merchant\"]'
            )).some(token => {
              const space = token.closest('[data-board-position-index]');
              return space && Number(space.getAttribute('data-board-position-index')) === position
                && token.getAttribute('opacity') !== '0';
            })
            """,
            position,
        ))

    _click_if_offered(page, '[data-arrow="north->north_east"][data-turn-offered="true"]')
    action_control = page.query_selector(
        '[data-turn-control="action"][data-turn-control-enabled="true"]'
    )
    assert action_control is not None
    _click_handle_centre(page, action_control, require_hit=True)
    page.wait_for_timeout(40)
    resolution = page.query_selector(
        '[data-resolution-key="clerical_devotion"][data-turn-offered="true"]'
    )
    assert resolution is not None
    _click_handle_centre(page, resolution, require_hit=True)
    page.wait_for_timeout(40)

    # The surviving no-Guild and Guild actions disagree, so no Merchant move is shown yet.
    assert merchant_visible_at(before_position)
    guild = page.query_selector(
        '[data-combination-key="guild:own_active"][data-turn-offered="true"]'
    )
    assert guild is not None
    _click_handle_centre(page, guild, require_hit=True)
    page.wait_for_timeout(60)
    assert merchant_visible_at(expected_position)
    assert {
        player: holdings
        for player, holdings in _all_player_holdings(page).items()
        if player != active_player_id
    } == {
        player: holdings
        for player, holdings in before_others.items()
        if player != active_player_id
    }
    assert _confirm_enabled(page)

    page.locator('[data-turn-control="reset"]').click()
    page.wait_for_timeout(100)
    assert merchant_visible_at(before_position)

    # Pick Guild again and confirm; the committed state must be the same state the marker previewed.
    _click_if_offered(page, '[data-arrow="north->north_east"][data-turn-offered="true"]')
    action_control = page.query_selector(
        '[data-turn-control="action"][data-turn-control-enabled="true"]'
    )
    assert action_control is not None
    _click_handle_centre(page, action_control, require_hit=True)
    page.wait_for_timeout(40)
    resolution = page.query_selector(
        '[data-resolution-key="clerical_devotion"][data-turn-offered="true"]'
    )
    assert resolution is not None
    _click_handle_centre(page, resolution, require_hit=True)
    page.wait_for_timeout(40)
    guild = page.query_selector(
        '[data-combination-key="guild:own_active"][data-turn-offered="true"]'
    )
    assert guild is not None
    _click_handle_centre(page, guild, require_hit=True)
    page.wait_for_timeout(60)
    page.locator('[data-turn-control="confirm"]').click()
    page.wait_for_timeout(120)
    assert server.state.merchant_board_position == expected_position
    assert merchant_visible_at(expected_position)
    assert server.state.active_player != acting_player


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


def _turn_state_snapshot(page) -> dict[str, object]:
    """A compact view of what the page currently offers and enables in the turn UI."""
    return {
        "origins": page.locator('[data-board-position-index][data-turn-start-candidate="true"]').count(),
        "start_relocation_spaces": page.locator(
            '[data-board-position-index][data-turn-start-relocation-candidate="true"]'
        ).count(),
        "skips": page.locator('[data-board-position-index][data-turn-skip-candidate="true"]').count(),
        "end_relocation_spaces": page.locator(
            '[data-board-position-index][data-turn-end-relocation-candidate="true"]'
        ).count(),
        "end_relocation_abbey": page.locator(
            '[data-active-seat="true"][data-end-relocation-choice="true"] [data-token="abbey"][opacity="1"]'
        ).count(),
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
    assert any(option["value"] == PLAYTEST_CONVERSIONS for option in option_values), (
        "conversion playtest scenario is missing from dropdown"
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


def test_inquisition_start_turn_move_is_asked_before_origin_and_unlocks_more_origins(page, serve) -> None:
    base_url, _server = serve(SCENARIOS / "inquisition_active_city_to_duty_001.json")
    page.goto(base_url, wait_until="networkidle")

    opening = _turn_state_snapshot(page)
    prompts = [str(prompt).lower() for prompt in opening["prompts"]]
    assert opening["origins"] == 0, opening
    assert any("before-sow move" in prompt for prompt in prompts), prompts

    inquisition_locator = page.locator(
        '[data-combination-key][data-turn-offered="true"]'
    ).filter(has_text="Inquisition")
    assert inquisition_locator.count() >= 1, "Inquisition option was not offered first"
    inquisition = inquisition_locator.first.element_handle()
    assert inquisition is not None
    _click_handle_centre(page, inquisition, require_hit=True)
    page.wait_for_timeout(20)

    before_target = _turn_state_snapshot(page)
    assert before_target["origins"] == 0, before_target

    relocation_targets = page.locator(
        '[data-board-position-index][data-turn-start-relocation-candidate="true"]'
    )
    assert relocation_targets.count() == 8, "Inquisition did not offer all duty-space relocation targets"
    relocation_target = relocation_targets.first.element_handle()
    assert relocation_target is not None
    chosen_target = int(relocation_target.get_attribute("data-board-position-index"))
    _click_handle_centre(page, relocation_target, require_hit=True)
    page.wait_for_timeout(20)

    after_move = _turn_state_snapshot(page)
    assert after_move["start_relocation_spaces"] == 0, after_move
    assert after_move["origins"] == 2, after_move
    offered_origins = {
        int(value)
        for value in page.eval_on_selector_all(
            '[data-board-position-index][data-turn-start-candidate="true"]',
            "nodes => nodes.map(node => node.getAttribute('data-board-position-index'))",
        )
        if value is not None
    }
    assert offered_origins == {0, chosen_target}, offered_origins


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

    if page.locator('[data-board-position-index][data-turn-start-candidate="true"]').count() == 0:
        move_none = page.locator(
            '[data-combination-key="none"][data-turn-offered="true"]'
        )
        assert move_none.count() == 1, "the relocation choice was not offered as Move no one"
        move_none_handle = move_none.first.element_handle()
        assert move_none_handle is not None
        _click_handle_centre(page, move_none_handle, require_hit=True)
        page.wait_for_timeout(20)

    # The relocation answer can force the city origin; agreed steps are then
    # auto-advanced, so there may be no origin control left to click.
    city = page.query_selector('[data-board-position-index="0"][data-turn-start-candidate="true"]')
    if city is not None:
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


def test_two_active_conversions_commit_from_building_direction_and_amount_clicks(page, serve) -> None:
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


def test_conversion_resource_pill_reaches_amount_above_six_without_prompt_overflow(page, serve) -> None:
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
    assert destination.locator('[data-piety-choice-silver]').text_content() == f"{expected_silver:+d}"
    assert destination.locator('[data-piety-choice-piety-change]').count() == 0
    _click_handle_centre(page, destination.element_handle(), require_hit=True)
    assert page.locator('[data-turn-step-amount-total="true"]').inner_text() == ""
    assert _confirm_enabled(page)
    page.locator('[data-turn-control="confirm"]').click()
    page.wait_for_timeout(100)
    assert before - server.state.player_state(server.state.active_player).piety == before - target


def test_illegal_indulgences_destination_has_no_live_pill(page, serve) -> None:
    base_url, _server = serve(SCENARIOS / "indulgences_active_sell_piety_001.json")
    page.goto(base_url, wait_until="networkidle")
    _choose_conversion(page, "indulgences", "sell_piety", 1)
    assert page.locator(
        '[data-piety-choice-pill][data-piety-choice-destination="12"]'
    ).count() == 0


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
    offered = page.locator(
        '[data-piety-choice-pill][data-piety-choice-offered="true"]'
    )
    assert offered.count() == 2
    destination = page.locator(
        '[data-piety-choice-pill][data-piety-choice-destination="1"]'
    )
    assert destination.locator('[data-piety-choice-silver]').text_content() == "+1"
    assert destination.locator('[data-piety-choice-piety-change]').count() == 0
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
    assert page.locator('[data-piety-choice-pill]').count() == 0
    assert panel.bounding_box()["height"] == pytest.approx(main_height, abs=0.1)
    assert page.locator('[data-piety-score-row]').count() == 13
    turn_height = page.locator('[data-component="play-turn"]').bounding_box()["height"]

    building = page.locator(
        '[data-turn-step-building-id="indulgences"][data-turn-step-offered="true"]'
    )
    _click_handle_centre(page, building.element_handle(), require_hit=True)
    direction = page.locator(
        '[data-turn-step-direction="sell_piety"][data-turn-step-offered="true"]'
    )
    _click_handle_centre(page, direction.element_handle(), require_hit=True)
    assert page.locator('[data-turn-step-answer-label="true"]').inner_text() == "Destination"
    assert page.locator('[data-turn-step-resource-hint="true"]').inner_text() == ""
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

    obstacles = page.locator('[data-piety-position-label], [data-piety-score-row]')
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
        return tuple(int(channel) for channel in value.removeprefix("rgb(").removesuffix(")").split(", "))

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
            "width": max(box["x"] + box["width"] for box in boxes)
            - min(box["x"] for box in boxes),
            "height": max(box["y"] + box["height"] for box in boxes)
            - min(box["y"] for box in boxes),
        }

    discs = page.locator('[data-player-disc]')
    stars = page.locator('[data-piety-score-row]')
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

    sell = page.locator(
        '[data-turn-step-direction="sell_piety"][data-turn-step-offered="true"]'
    )
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
        page.locator('[data-player-disc]').nth(index).bounding_box()
        for index in range(page.locator('[data-player-disc]').count())
    ]
    disc_top = min(box["y"] for box in disc_boxes)
    disc_bottom = max(box["y"] + box["height"] for box in disc_boxes)
    assert all(
        disc_top - 1 <= sell_pills.nth(index).bounding_box()["y"]
        and sell_pills.nth(index).bounding_box()["y"]
        + sell_pills.nth(index).bounding_box()["height"] <= disc_bottom + 1
        for index in range(sell_pills.count())
    )
    assert all(
        sell_pills.nth(index).locator('[data-piety-choice-silver]').text_content()
        for index in range(sell_pills.count())
    )

    page.locator('[data-turn-control="reset"]').click()
    _click_handle_centre(page, building.element_handle(), require_hit=True)
    buy = page.locator(
        '[data-turn-step-direction="buy_piety"][data-turn-step-offered="true"]'
    )
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
        and buy_pills.nth(index).bounding_box()["y"]
        + buy_pills.nth(index).bounding_box()["height"] <= disc_bottom + 1
        for index in range(buy_pills.count())
    )
    assert all(
        buy_pills.nth(index).locator('[data-piety-choice-silver]').text_content()
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
        return tuple(int(channel) for channel in value.removeprefix("rgb(").removesuffix(")").split(", "))

    foreground = rgb(styles["piety"]["fill"])
    background = rgb(styles["background"])

    def relative_luminance(colour: tuple[int, int, int]) -> float:
        channels = [channel / 255 for channel in colour]
        linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
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
    assert page.locator(
        '[data-active-seat="true"] [data-turn-step-building-id="stone_yard"]'
        '[data-turn-step-offered="true"]'
    ).count() == 1


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
        assert page.locator(
            f'[data-component="player-board-v2"] [data-building-id="{building_id}"]'
        ).count() == 0


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

        assert page.locator(".panel").evaluate_all(
            "nodes => nodes.map(node => node.getBoundingClientRect().height)"
        ) == panel_heights
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
        ("map", TOOLTIP_MAP_BUILDING, "left"),
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

    over_map, map_background = _halo_darkening(page, TOOLTIP_MAP_BUILDING, "left")
    over_board, board_background = _halo_darkening(page, TOOLTIP_BOARD_BUILDING, "right")

    assert map_background > 120 and board_background > 120, (
        f"map {map_background:.0f} and board {board_background:.0f} must both be lit surfaces"
    )
    assert over_board[0] >= 10, f"the halo does not darken a player board at all: {over_board}"
    assert sum(over_board[:8]) / 8 >= 10, (
        f"the halo barely marks a player board: {over_board[:8]}"
    )
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
        (mill_fill_box["x"] + mill_fill_box["width"] / 2, mill_fill_box["y"] + mill_fill_box["height"] * 0.22),
        (mill_fill_box["x"] + mill_fill_box["width"] / 2, mill_fill_box["y"] + mill_fill_box["height"] * 0.78),
        (mill_label_box["x"] + mill_label_box["width"] / 2, mill_label_box["y"] + mill_label_box["height"] / 2),
    )
    mill_positions = [hover_point(*point) for point in mill_points]
    assert all(
        abs(position[0] - mill_positions[0][0]) <= 1
        and abs(position[1] - mill_positions[0][1]) <= 1
        for position in mill_positions
    ), mill_positions

    brewery_points = (
        (brewery_fill_box["x"] + brewery_fill_box["width"] / 2, brewery_fill_box["y"] + brewery_fill_box["height"] * 0.22),
        (brewery_fill_box["x"] + brewery_fill_box["width"] / 2, brewery_fill_box["y"] + brewery_fill_box["height"] * 0.78),
        (brewery_label_box["x"] + brewery_label_box["width"] / 2, brewery_label_box["y"] + brewery_label_box["height"] / 2),
        (brewery_overlay_box["x"] + brewery_overlay_box["width"] / 2, brewery_overlay_box["y"] + brewery_overlay_box["height"] / 2),
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

    direction = page.locator(
        '[data-turn-step-direction="sell_wheat_for_silver"][data-turn-step-offered="true"]'
    ).first
    assert direction.count() == 1
    _click_handle_centre(page, direction.element_handle(), require_hit=True)
    resource = page.locator(
        '[data-resource-choice-key="wheat"][data-turn-offered="true"]'
    ).first
    assert resource.count() == 1
    _click_handle_centre(page, resource.element_handle(), require_hit=True)
    # Brewery is a market hire with three legal hire-payment variants.  The
    # building and conversion are selected, but confirmation correctly waits
    # for the separate hire-payment answer.
    assert page.locator('[data-turn-step-amount-total="true"]').inner_text() == "1"
    assert brewery.get_attribute("data-turn-step-selected") == "true"


def test_two_active_conversions_leave_the_other_building_offered(page, serve) -> None:
    base_url, server = serve(SCENARIOS / "two_active_conversions_001.json")
    page.goto(base_url, wait_until="networkidle")

    _choose_conversion(page, "grain_store", "sell_wheat", 1)
    page.locator('[data-turn-control="confirm"]').click()
    page.wait_for_timeout(100)

    assert page.locator(
        '[data-active-seat="true"] [data-turn-step-building-id="grain_store"]'
        '[data-turn-step-offered="true"]'
    ).count() == 0
    assert page.locator(
        '[data-active-seat="true"] [data-turn-step-building-id="grain_store"]'
        '[data-turn-step-used="true"]'
    ).count() == 1
    assert page.locator(
        '[data-active-seat="true"] [data-turn-step-building-id="stone_yard"]'
        '[data-turn-step-offered="true"]'
    ).count() == 1
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
        '[data-active-seat="true"] [data-resource-choice-key="wheat"]'
        '[data-turn-offered="true"]'
    )
    assert resource_key.count() == 1
    _click_handle_centre(page, resource_key.element_handle(), require_hit=True)
    assert page.locator(
        '[data-active-seat="true"] [data-resource-choice-key="wheat"]'
        '[data-turn-offered="true"]'
    ).count() == 0
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
    assert page.get_attribute(
        '[data-turn-control="reset"]', "data-turn-control-enabled"
    ) == "true"

    page.locator('[data-turn-control="reset"]').click()
    page.wait_for_timeout(100)

    assert server.state == initial
    assert server.state.turn_progress.used_buildings == frozenset()
    assert page.locator(
        '[data-active-seat="true"] [data-turn-step-building-id="grain_store"]'
        '[data-turn-step-offered="true"]'
    ).count() == 1
