"""Shared plumbing for the tests that drive the Host client in a real browser."""

import contextlib
import os
import socket
import threading
import time

import pytest

pytest.importorskip("playwright.sync_api")
uvicorn = pytest.importorskip("uvicorn")

from playwright.sync_api import sync_playwright  # noqa: E402

from fireblade.web.server import create_app  # noqa: E402


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@contextlib.contextmanager
def serving(root):
    """The Host over a cases folder, on a free port, for the length of the block."""
    port = free_port()
    server = uvicorn.Server(
        uvicorn.Config(create_app(root), host="127.0.0.1", port=port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    assert server.started, "the Host did not start"
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=10)


@contextlib.contextmanager
def browser_page(url, case_name, width=1400, height=850, wait_rows=True):
    """A page on the Host with `case_name` open on its Analyses tab; errors are collected.

    FIREBLADE_CHROMIUM points at a browser Playwright did not download itself.
    """
    try:
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(
            executable_path=os.environ.get("FIREBLADE_CHROMIUM") or None
        )
    except Exception as exc:  # noqa: BLE001 - no browser installed here
        pytest.skip(f"no Chromium available: {exc}")
    page = browser.new_page(viewport={"width": width, "height": height})
    page.errors = []
    page.failed = []
    page.on("pageerror", lambda error: page.errors.append(str(error)))
    page.on(
        "response",
        lambda r: page.failed.append(f"{r.status} {r.request.method} {r.url}")
        if r.status >= 400 and "/api/" in r.url
        else None,
    )
    try:
        page.goto(url + "/")
        page.wait_for_selector("#menubar")
        page.click('.tabs .tab:text-is("Cases")')
        page.dblclick(f'tr:has(td:text-is("{case_name}")) td >> nth=0')
        if wait_rows:
            page.wait_for_selector("#body tr[data-row]", timeout=20000)
        else:
            page.wait_for_function(
                "document.getElementById('casecombo-label').innerText.includes("
                + repr(case_name)
                + ")",
                timeout=20000,
            )
        page.click('.tabs .tab:text-is("Analyses")')
        yield page
        assert not page.errors, page.errors
    finally:
        browser.close()
        playwright.stop()
