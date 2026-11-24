"""The Host client, driven by a real browser and a real mouse.

The contract tests read app.js as text and call the API directly, which is how a menu that
no mouse could ever operate shipped: the item's click handler worked when a script called
it, and never when a hand pressed it. These tests press.

They need Playwright and its Chromium; without them the file is skipped, never failed.
"""
import os
import socket
import threading
import time

import pytest

pytest.importorskip("playwright.sync_api")
uvicorn = pytest.importorskip("uvicorn")

from playwright.sync_api import sync_playwright  # noqa: E402

from fireblade.core.investigations import InvestigationLibrary  # noqa: E402
from fireblade.web.server import create_app  # noqa: E402


def _free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture(scope="module")
def host(tmp_path_factory):
    root = tmp_path_factory.mktemp("browser-cases")
    InvestigationLibrary(root).create("Browser case", "driven by a test", "windows")
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(create_app(root), host="127.0.0.1", port=port,
                                           log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    assert server.started, "the Host did not start"
    yield f"http://127.0.0.1:{port}/"
    server.should_exit = True
    thread.join(timeout=10)


@pytest.fixture()
def page(host):
    try:
        playwright = sync_playwright().start()
        # FIREBLADE_CHROMIUM points at a browser Playwright did not download itself.
        executable = os.environ.get("FIREBLADE_CHROMIUM") or None
        browser = playwright.chromium.launch(executable_path=executable)
    except Exception as exc:  # noqa: BLE001 - no browser installed here
        pytest.skip(f"no Chromium available: {exc}")
    page = browser.new_page(viewport={"width": 1400, "height": 850})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(host)
    page.wait_for_selector("#menubar")
    yield page
    assert not errors, errors
    browser.close()
    playwright.stop()


def _press(page, selector):
    """Mouse down and mouse up on the element: what a hand does, not element.click()."""
    box = page.locator(selector).first.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.mouse.up()


def test_a_menu_command_runs_when_it_is_pressed_with_the_mouse(page):
    _press(page, '.menubar .m[data-menu="view"]')
    assert page.locator(".menu.show").count() == 1
    _press(page, '.menu.show [data-act="messages"]')
    page.wait_for_selector("#messages-modal.show")
    assert page.locator(".menu.show").count() == 0, "the menu closes once its command ran"


def test_every_menu_opens_and_lists_its_commands(page):
    names = page.eval_on_selector_all(".menubar .m", "els => els.map(e => e.dataset.menu)")
    assert len(names) >= 8
    for name in names:
        _press(page, f'.menubar .m[data-menu="{name}"]')
        assert page.locator(f'.menu[data-for="{name}"].show [data-act]').count() > 0, name
        page.mouse.click(700, 500)
        assert page.locator(".menu.show").count() == 0, name


def test_a_dialog_is_moved_by_its_title_and_resized_from_its_corner(page):
    page.evaluate("document.getElementById('settings-modal').classList.add('show')")
    dialog = page.locator("#settings-modal .dialog")
    page.wait_for_function("document.querySelector('#settings-modal .dialog').dataset.free === '1'")
    start = dialog.bounding_box()
    title = page.locator("#settings-modal .dialog h3").bounding_box()
    page.mouse.move(title["x"] + 20, title["y"] + 8)
    page.mouse.down()
    page.mouse.move(title["x"] - 160, title["y"] + 90, steps=5)
    page.mouse.up()
    moved = dialog.bounding_box()
    assert moved["x"] < start["x"] - 100 and moved["y"] > start["y"] + 60
    page.mouse.move(moved["x"] + moved["width"] - 4, moved["y"] + moved["height"] - 4)
    page.mouse.down()
    page.mouse.move(moved["x"] + moved["width"] + 90, moved["y"] + moved["height"] + 60, steps=5)
    page.mouse.up()
    resized = dialog.bounding_box()
    assert resized["width"] > moved["width"] + 50 and resized["height"] > moved["height"] + 30


def test_the_splitters_resize_the_tree_and_the_details_and_reset_on_double_click(page):
    tree = page.locator("#artifacts")
    before = tree.bounding_box()["width"]
    bar = page.locator(".splitter.vsplit").bounding_box()
    page.mouse.move(bar["x"] + 2, bar["y"] + 150)
    page.mouse.down()
    page.mouse.move(bar["x"] - 140, bar["y"] + 150, steps=5)
    page.mouse.up()
    assert tree.bounding_box()["width"] > before + 100
    page.locator(".splitter.vsplit").dblclick()
    assert abs(tree.bounding_box()["width"] - before) < 2
