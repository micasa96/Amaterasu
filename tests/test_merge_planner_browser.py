"""Exercise the real planner page (Svelte) against a small browser/API harness."""

import json
import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "web" / "ui"
HTML = ""  # rendered merge_planner.html, set by the module fixture
DIST = None  # private Vite build of the shared Svelte design system


@pytest.fixture(scope="module", autouse=True)
def planner_page(tmp_path_factory):
    """Build the Svelte bundle into a temp dir and render the real template.

    The planner is the merge-planner page of the shared design system
    (web/ui/src/pages/merge-planner), so the browser runs exactly what ships.
    """
    global HTML, DIST
    jinja = pytest.importorskip("jinja2")
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if not npx or not (UI / "node_modules").is_dir():
        pytest.skip("Node/npm or web/ui/node_modules unavailable; run `npm ci` in web/ui")
    out = tmp_path_factory.mktemp("ui-dist")
    build = subprocess.run(
        [npx, "vite", "build", "--outDir", str(out), "--emptyOutDir", "--logLevel", "error"],
        cwd=UI, capture_output=True, text=True, timeout=300,
    )
    if build.returncode:
        pytest.fail(f"Svelte build failed: {build.stdout} {build.stderr}")
    entry = json.loads((out / ".vite" / "manifest.json").read_text(encoding="utf-8"))["src/main.ts"]
    env = jinja.Environment(loader=jinja.FileSystemLoader(ROOT / "web/templates"), autoescape=True)
    env.globals["ui_assets"] = {
        "js": f"/static/dist/{entry['file']}",
        "css": [f"/static/dist/{css}" for css in entry.get("css", [])],
    }
    HTML = env.get_template("merge_planner.html").render(plan_id="proof")
    DIST = out
    yield


def _static(route, path):
    """Serve /static/dist from the private build and /static from web/static."""
    if path.startswith("/static/dist/"):
        file = DIST / path[len("/static/dist/"):]
    else:
        file = ROOT / "web" / path.lstrip("/")
    if file.is_file():
        route.fulfill(path=str(file))
    else:
        route.fulfill(status=404, body="")


def _browser(playwright):
    edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    kwargs = {"headless": True}
    if os.name == "nt" and edge.is_file():
        kwargs["executable_path"] = str(edge)
    try:
        return playwright.chromium.launch(**kwargs)
    except Exception as error:
        pytest.skip(f"No local Playwright Chromium/Edge browser: {error}")


def test_planner_saves_conflicts_keeps_focus_and_locks():
    playwright_api = pytest.importorskip("playwright.sync_api")
    state = {
        "title": "Proof", "status": "downloading", "mode": "copy",
        "profile_name": "", "duration_seconds": None, "subtitle_summary": "",
        "locked": False, "error": "", "inventory_error": "",
        "ready_count": 0, "pending_count": 0, "enumeration_complete": True,
        "order_revision": 1, "revision": 1,
        "items": [
            {"id": value, "name": name, "original_index": index,
             "ready": False, "placeholder": False}
            for index, (value, name) in enumerate(
                (("a", "First"), ("b", "Second"), ("c", "Third")), 1
            )
        ],
    }
    posts = []

    def serve(route):
        request = route.request
        path = urlsplit(request.url).path
        if path.startswith("/static/"):
            _static(route, path)
        elif path == "/api/merge-plan/proof":
            if request.method == "POST":
                payload = json.loads(request.post_data)
                posts.append((request.url, request.headers, payload))
                if state["locked"] or payload["order_revision"] != state["order_revision"]:
                    route.fulfill(status=409, content_type="application/json",
                                  body=json.dumps({"message": "Order changed", "plan": state}))
                    return
                by_id = {item["id"]: item for item in state["items"]}
                state["items"] = [by_id[item_id] for item_id in payload["order"]]
                state["order_revision"] += 1
            route.fulfill(content_type="application/json", body=json.dumps(state))
        else:
            route.fulfill(content_type="text/html", body=HTML)

    with playwright_api.sync_playwright() as playwright:
        browser = _browser(playwright)
        page = browser.new_page()
        page.route("http://merge.test/**", serve)
        page.goto("http://merge.test/app/merge-plan?gid=merge_proof#pin=abcdefghijkl")
        page.locator("#mergeList li").first.wait_for()
        page.get_by_role("button", name="Reverse").click()
        page.wait_for_function("document.querySelector('#saveState').textContent === 'Up to date'")
        assert [item["id"] for item in state["items"]] == ["c", "b", "a"]
        assert posts[-1][1]["x-merge-plan-pin"] == "abcdefghijkl"
        assert "pin=" not in posts[-1][0]

        focus = page.get_by_role("button", name="Move up: Second")
        focus.focus()
        state["ready_count"] = 1
        page.wait_for_function("document.querySelector('#readyCount').textContent === '1'", timeout=7000)
        assert page.evaluate("document.activeElement.getAttribute('aria-label')") == "Move up: Second"

        state["order_revision"] += 1
        page.get_by_role("button", name="Reverse").click()
        page.locator("#saveOrderButton:visible").wait_for()
        page.get_by_role("button", name="Save current order").click()
        page.wait_for_function("document.querySelector('#saveState').textContent === 'Up to date'")
        assert [item["id"] for item in state["items"]] == ["a", "b", "c"]

        state["locked"] = True
        state["status"] = "processing"
        page.wait_for_function("document.querySelector('#planState').dataset.state === 'processing'", timeout=7000)
        assert page.get_by_role("button", name="Reverse").is_disabled()
        browser.close()


def _plan():
    return {"title": "Proof", "status": "downloading", "mode": "copy", "locked": False,
            "duration_seconds": 62, "ready_count": 3, "pending_count": 0,
            "enumeration_complete": True, "revision": 1, "order_revision": 1,
            "items": [{"id": value, "name": name, "original_index": index, "ready": True}
                      for index, (value, name) in enumerate((("a", "First"), ("b", "Second"), ("c", "Third")), 1)]}


def test_newer_reorder_survives_inflight_save():
    playwright_api = pytest.importorskip("playwright.sync_api")
    state = _plan()
    posts = []
    held = []

    def complete(route, payload):
        assert payload["order_revision"] == state["order_revision"]
        by_id = {item["id"]: item for item in state["items"]}
        state["items"] = [by_id[value] for value in payload["order"]]
        state["order_revision"] += 1
        state["revision"] += 1
        route.fulfill(content_type="application/json", body=json.dumps(state))

    def serve(route):
        path = urlsplit(route.request.url).path
        if path.startswith("/static/"):
            _static(route, path)
        elif path == "/api/merge-plan/proof":
            if route.request.method == "POST":
                payload = json.loads(route.request.post_data)
                posts.append(payload)
                if len(posts) == 1:
                    held.append((route, payload))
                else:
                    complete(route, payload)
            else:
                route.fulfill(content_type="application/json", body=json.dumps(state))
        else:
            route.fulfill(content_type="text/html", body=HTML)

    with playwright_api.sync_playwright() as playwright:
        browser = _browser(playwright)
        page = browser.new_page()
        page.route("http://merge.test/**", serve)
        page.goto("http://merge.test/app/merge-plan#pin=abcdefghijkl")
        page.locator("#mergeList li").first.wait_for()
        page.get_by_role("button", name="Reverse").click()
        page.wait_for_function("document.querySelector('#saveState').textContent.startsWith('Saving')", timeout=5000)
        page.get_by_role("button", name="Move down: Third").click()
        complete(*held.pop())
        page.wait_for_function("document.querySelector('#saveState').textContent === 'Up to date'")
        assert [post["order"] for post in posts] == [["c", "b", "a"], ["b", "c", "a"]]
        assert [item["id"] for item in state["items"]] == ["b", "c", "a"]
        assert page.locator("#mergeList li").evaluate_all("rows => rows.map(row => row.dataset.id)") == ["b", "c", "a"]
        browser.close()


def test_initial_connection_failure_recovers_and_missing_pin_does_not_poll():
    playwright_api = pytest.importorskip("playwright.sync_api")
    calls = []

    def serve(route):
        path = urlsplit(route.request.url).path
        if path.startswith("/static/"):
            _static(route, path)
        elif path == "/api/merge-plan/proof":
            calls.append(route.request.url)
            if len(calls) == 1:
                route.abort()
            else:
                route.fulfill(content_type="application/json", body=json.dumps(_plan()))
        else:
            route.fulfill(content_type="text/html", body=HTML)

    with playwright_api.sync_playwright() as playwright:
        browser = _browser(playwright)
        page = browser.new_page()
        page.route("http://merge.test/**", serve)
        page.goto("http://merge.test/app/merge-plan")
        page.locator("#authPanel:visible").wait_for()
        assert not calls
        page.goto("http://merge.test/app/merge-plan?retry=1#pin=abcdefghijkl")
        page.locator("#errorPanel:visible").wait_for()
        page.locator("#mergeList li").first.wait_for(timeout=8000)
        assert len(calls) == 2
        assert page.locator("#planner").is_visible()
        browser.close()


def test_real_planner_layout_desktop_and_mobile_without_icon_cdn():
    playwright_api = pytest.importorskip("playwright.sync_api")
    root = ROOT
    html = HTML
    state = _plan()
    state["items"][0]["name"] = "Season 01 / Episode 02 — A very long video filename with 日本語 and বাংলা subtitles.mkv"
    state["subtitle_summary"] = "2 selectable subtitle tracks. Compatible tracks continue across episodes."

    def serve(route):
        url = urlsplit(route.request.url)
        if url.hostname != "merge.test":
            route.abort()
        elif url.path == "/api/merge-plan/proof":
            route.fulfill(content_type="application/json", body=json.dumps(state))
        elif url.path.startswith("/static/"):
            _static(route, url.path)
        else:
            route.fulfill(content_type="text/html", body=html)

    with playwright_api.sync_playwright() as playwright:
        browser = _browser(playwright)
        for name, width, height in (("desktop", 1440, 1000), ("mobile", 390, 844)):
            page = browser.new_page(viewport={"width": width, "height": height})
            page.route("**/*", serve)
            page.goto("http://merge.test/app/merge-plan#pin=abcdefghijkl")
            page.locator("#mergeList li").first.wait_for()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert page.locator(".merge-row-actions svg").count() == 6
            assert page.locator(".merge-row-actions button").first.bounding_box()["width"] >= 44
            screenshot = root / ".runtime" / f"merge-ui-{name}.png"
            screenshot.parent.mkdir(exist_ok=True)
            page.screenshot(path=str(screenshot), full_page=True)
            page.close()
        browser.close()


def test_failed_save_preserves_order_and_locked_conflict_stops_retries():
    playwright_api = pytest.importorskip("playwright.sync_api")
    state = _plan()
    posts = []

    def serve(route):
        path = urlsplit(route.request.url).path
        if path.startswith("/static/"):
            _static(route, path)
        elif path == "/api/merge-plan/proof":
            if route.request.method == "POST":
                posts.append(json.loads(route.request.post_data))
                if len(posts) == 1:
                    route.fulfill(status=500, content_type="application/json", body=json.dumps({"message": "Disk unavailable"}))
                else:
                    state["locked"] = True
                    state["status"] = "processing"
                    route.fulfill(status=409, content_type="application/json", body=json.dumps({"message": "Merge started", "plan": state}))
            else:
                route.fulfill(content_type="application/json", body=json.dumps(state))
        else:
            route.fulfill(content_type="text/html", body=HTML)

    with playwright_api.sync_playwright() as playwright:
        browser = _browser(playwright)
        page = browser.new_page()
        page.route("http://merge.test/**", serve)
        page.goto("http://merge.test/app/merge-plan#pin=abcdefghijkl")
        page.locator("#mergeList li").first.wait_for()
        page.get_by_role("button", name="Reverse").click()
        page.locator("#saveOrderButton:visible").wait_for()
        assert page.locator("#saveState").inner_text() == "Not saved"
        assert page.locator("#mergeList li").evaluate_all("rows => rows.map(row => row.dataset.id)") == ["c", "b", "a"]
        page.get_by_role("button", name="Save current order").click()
        page.wait_for_function("document.querySelector('#saveState').textContent === 'Order locked'")
        assert page.get_by_role("button", name="Reverse").is_disabled()
        assert page.locator("#mergeList li").evaluate_all("rows => rows.map(row => row.dataset.id)") == ["a", "b", "c"]
        assert len(posts) == 2
        browser.close()


def test_rejected_save_pin_can_be_corrected_without_losing_local_edits():
    playwright_api = pytest.importorskip("playwright.sync_api")
    state = _plan()
    posts = []

    def serve(route):
        path = urlsplit(route.request.url).path
        if path.startswith("/static/"):
            _static(route, path)
        elif path == "/api/merge-plan/proof":
            if route.request.method == "POST":
                payload = json.loads(route.request.post_data)
                posts.append(payload)
                if len(posts) == 1:
                    route.fulfill(status=403, content_type="application/json", body=json.dumps({"message": "Code rejected"}))
                    return
                by_id = {item["id"]: item for item in state["items"]}
                state["items"] = [by_id[value] for value in payload["order"]]
                state["order_revision"] += 1
                state["revision"] += 1
            route.fulfill(content_type="application/json", body=json.dumps(state))
        else:
            route.fulfill(content_type="text/html", body=HTML)

    with playwright_api.sync_playwright() as playwright:
        browser = _browser(playwright)
        page = browser.new_page()
        page.route("http://merge.test/**", serve)
        page.goto("http://merge.test/app/merge-plan#pin=abcdefghijkl")
        page.locator("#mergeList li").first.wait_for()
        page.get_by_role("button", name="Reverse").click()
        page.locator("#authPanel:visible").wait_for()
        page.locator("#pinInput").fill("mnopqrstuvwx")
        page.locator("#pinForm").evaluate("form => form.requestSubmit()")
        page.locator("#planner:visible").wait_for()
        assert page.locator("#mergeList li").evaluate_all("rows => rows.map(row => row.dataset.id)") == ["c", "b", "a"]
        page.get_by_role("button", name="Save current order").click()
        page.wait_for_function("document.querySelector('#saveState').textContent === 'Up to date'")
        assert len(posts) == 2
        assert [item["id"] for item in state["items"]] == ["c", "b", "a"]
        browser.close()


def test_real_mobile_touch_drag_saves_the_new_order():
    playwright_api = pytest.importorskip("playwright.sync_api")
    root = ROOT
    html = HTML
    state = _plan()
    posts = []

    def serve(route):
        url = urlsplit(route.request.url)
        if url.hostname != "merge.test":
            route.abort()
        elif url.path == "/api/merge-plan/proof":
            if route.request.method == "POST":
                payload = json.loads(route.request.post_data)
                posts.append(payload)
                by_id = {item["id"]: item for item in state["items"]}
                state["items"] = [by_id[value] for value in payload["order"]]
                state["order_revision"] += 1
                state["revision"] += 1
            route.fulfill(content_type="application/json", body=json.dumps(state))
        elif url.path.startswith("/static/"):
            _static(route, url.path)
        else:
            route.fulfill(content_type="text/html", body=html)

    with playwright_api.sync_playwright() as playwright:
        browser = _browser(playwright)
        page = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        page.route("**/*", serve)
        page.goto("http://merge.test/app/merge-plan#pin=abcdefghijkl")
        page.locator("#mergeList li").first.wait_for()
        page.locator("#mergeList").scroll_into_view_if_needed()
        handle = page.locator(".merge-handle").first.bounding_box()
        destination = page.locator("#mergeList li").last.bounding_box()
        session = page.context.new_cdp_session(page)
        x, y = handle["x"] + handle["width"] / 2, handle["y"] + handle["height"] / 2
        end = destination["y"] + destination["height"] * 0.8
        session.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y}]})
        for fraction in (0.25, 0.5, 0.75, 1):
            session.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x, "y": y + (end - y) * fraction}]})
        with page.expect_request(lambda request: request.method == "POST" and "/api/merge-plan/" in request.url, timeout=5000):
            session.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        page.wait_for_function("document.querySelector('#mergeList').firstElementChild.dataset.id === 'b' && document.querySelector('#saveState').textContent === 'Up to date'")
        assert posts[-1]["order"] == ["b", "c", "a"]
        assert [item["id"] for item in state["items"]] == ["b", "c", "a"]
        browser.close()
