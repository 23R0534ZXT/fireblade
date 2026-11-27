"""Shared plumbing for the tests that drive the Host client in a real browser."""

import contextlib
import os
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid

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
    image = os.environ.get("FIREBLADE_TEST_IMAGE")
    if image:
        with container_serving(root, image) as url:
            yield url
        return
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
def container_serving(root, image):
    """Run the same browser contracts against a built image, with real on-disk cases.

    Tests create sibling evidence folders; keep their absolute paths valid in Docker too.
    Only that test's temporary parent is mounted, never the Docker socket.
    """
    root = root.resolve()
    port = free_port()
    name = "kagarasu-browser-" + uuid.uuid4().hex[:12]
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            name,
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "-p",
            f"127.0.0.1:{port}:8080",
            "-v",
            f"{root.parent}:{root.parent}",
            "-e",
            "FIREBLADE_UPDATE_CHECK=off",
            image,
            "python",
            "-m",
            "fireblade.web",
            "serve",
            "--root",
            str(root),
            "--plugins",
            str(root.parent / "plugins"),
            "--host",
            "0.0.0.0",
            "--port",
            "8080",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 60
        while True:
            try:
                with urllib.request.urlopen(url + "/health", timeout=2) as response:
                    if response.status == 200:
                        break
            except (OSError, urllib.error.URLError):
                pass
            if time.monotonic() >= deadline:
                logs = subprocess.run(["docker", "logs", name], capture_output=True, text=True)
                raise AssertionError("Container did not start: " + logs.stdout + logs.stderr)
            time.sleep(0.1)
        yield url
    finally:
        subprocess.run(["docker", "rm", "-f", name], check=True, capture_output=True, timeout=30)


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
        snapshots = os.environ.get("FIREBLADE_SCREENSHOTS")
        if snapshots and not page.is_closed():
            from pathlib import Path

            destination = Path(snapshots)
            destination.mkdir(parents=True, exist_ok=True)
            safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in case_name)
            page.screenshot(path=str(destination / f"{safe}-{uuid.uuid4().hex[:8]}.png"))
        assert not page.errors, page.errors
    finally:
        browser.close()
        playwright.stop()
