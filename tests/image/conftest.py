"""Tests that drive a *running Fireblade image* in a real browser, over a real pack of evidence.

The other browser tests start the Host in their own process; these start nothing. They talk to the
container the user would run, with its .NET readers and its Hayabusa, so a reader that does not
start, a rule set that is missing or a column that arrives in French cannot hide behind a fake.

    FIREBLADE_IMAGE_URL          the running image                       http://127.0.0.1:8080
    FIREBLADE_IMAGE_PACK         the test pack, as the container sees it /pack
    FIREBLADE_IMAGE_PACK_LOCAL   the same pack, as this process sees it  artifacts/pack/Fireblade-Test-Pack-v1
    FIREBLADE_IMAGE_DISK         an NTFS image, as the container sees it (optional: one test needs it)

Without ``FIREBLADE_IMAGE_URL`` every test here is skipped, never failed.
"""

import json
import os
import time
import uuid
from pathlib import Path

import httpx
import pytest

URL = os.environ.get("FIREBLADE_IMAGE_URL", "").rstrip("/")
SERVER_PACK = os.environ.get("FIREBLADE_IMAGE_PACK", "/pack").rstrip("/")
LOCAL_PACK = os.environ.get("FIREBLADE_IMAGE_PACK_LOCAL", "")
DISK = os.environ.get("FIREBLADE_IMAGE_DISK", "")
CHROMIUM = os.environ.get("FIREBLADE_CHROMIUM") or None


def pytest_collection_modifyitems(config, items):
    if URL:
        return
    skip = pytest.mark.skip(
        reason="FIREBLADE_IMAGE_URL is not set: these tests drive a running image"
    )
    for item in items:
        if "/tests/image/" in str(item.fspath).replace("\\", "/"):
            item.add_marker(skip)


@pytest.fixture(scope="session")
def base():
    return URL


@pytest.fixture(scope="session")
def expected():
    """What the pack states about itself (RESULTATS-ATTENDUS.json), or nothing."""
    if not LOCAL_PACK:
        return {}
    for candidate in Path(LOCAL_PACK).rglob("RESULTATS-ATTENDUS.json"):
        return json.loads(candidate.read_text(encoding="utf-8"))
    return {}


def create_case(name, environment="windows"):
    answer = httpx.post(
        f"{URL}/api/cases",
        json={"name": name, "description": "image tests", "environment": environment},
        timeout=60,
    )
    answer.raise_for_status()
    return answer.json()["id"]


def import_path(case_id, path, organization="files", timeout=900):
    """Import a path the container can see, wait for the job, return its final state."""
    started = httpx.post(
        f"{URL}/api/cases/{case_id}/import-jobs",
        data={"source": path, "organization": organization},
        timeout=60,
    )
    started.raise_for_status()
    job = started.json()["job"]
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = httpx.get(f"{URL}/api/import-jobs/{job}", timeout=60).json()
        if state["status"] not in ("running", "cancelling"):
            return state
        time.sleep(1)
    raise AssertionError(f"the import of {path} did not end in {timeout}s")


def run_task(case_id, kind, params=None, timeout=900):
    """A long command (detection, graph, hunt…) run the way the page runs it."""
    started = httpx.post(
        f"{URL}/api/cases/{case_id}/tasks", json={"kind": kind, "params": params or {}}, timeout=60
    )
    started.raise_for_status()
    job = started.json()["job"]
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = httpx.get(f"{URL}/api/tasks/{job}", timeout=60).json()
        if state["status"] in ("done", "failed", "cancelled"):
            return state
        time.sleep(1)
    raise AssertionError(f"the task {kind} did not end in {timeout}s")


def analyses(case_id):
    return httpx.get(f"{URL}/api/cases/{case_id}", timeout=60).json()["analyses"]


def rows_of(case_id, index):
    return httpx.get(f"{URL}/api/cases/{case_id}/analyses/{index}/rows?limit=1", timeout=60).json()[
        "total"
    ]


def unique(prefix):
    return f"{prefix} {uuid.uuid4().hex[:6]}"


@pytest.fixture()
def browse():
    """Open a case of the running image in a real browser: ``with browse(case_name) as page``."""
    import contextlib

    from playwright.sync_api import sync_playwright

    @contextlib.contextmanager
    def opened(case_name, tab="Analyses", wait_rows=True):
        playwright = sync_playwright().start()
        try:
            browser = playwright.chromium.launch(executable_path=CHROMIUM)
        except Exception as exc:  # noqa: BLE001 - no browser here
            playwright.stop()
            pytest.skip(f"no Chromium available: {exc}")
        page = browser.new_page(viewport={"width": 1400, "height": 850})
        page.errors = []
        page.on("pageerror", lambda error: page.errors.append(str(error)))
        try:
            page.goto(URL + "/")
            page.wait_for_selector("#menubar")
            page.click('.tabs .tab:text-is("Cases")')
            page.dblclick(f'tr:has(td:text-is("{case_name}")) td >> nth=0')
            page.wait_for_function(
                "(name) => document.getElementById('casecombo-label').innerText.includes(name)",
                arg=case_name,
                timeout=30000,
            )
            if wait_rows:
                page.wait_for_selector("#body tr[data-row]", timeout=30000)
            page.click(f'.tabs .tab:text-is("{tab}")')
            yield page
            assert not page.errors, page.errors
        finally:
            browser.close()
            playwright.stop()

    return opened
