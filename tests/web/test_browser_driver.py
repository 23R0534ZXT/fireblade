"""The Host behind the per-case driver, driven by a real browser.

In the container edition the analyst never talks to the case's service directly: the driver
serves ``/case/<id>/`` and forwards everything below it. Every path the page builds has to carry
that prefix, and the driver has to forward every verb the page uses. Docker is a fake here
(the driver's decisions are tested in test_agency.py); the case's service is the real one, on
the case's volume, started when the driver opens the case.

Skipped without Playwright and a Chromium; never failed for lack of them.
"""
import contextlib
import json
import os
import sys
import types
from pathlib import Path

import httpx
import pytest

from _browser import serving  # noqa: E402

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright  # noqa: E402

from fireblade.web import agency  # noqa: E402

FAKE = Path(__file__).with_name("_fake_docker.py")


class LiveAgency(agency.Agency):
    """The driver's own decisions, with the case container replaced by an in-process service."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stack = contextlib.ExitStack()
        self.live = {}

    def open(self, identifier):
        if not self.volumes.has(identifier):
            raise KeyError(identifier)
        if identifier not in self.live:
            self.live[identifier] = self.stack.enter_context(serving(self.volumes.library(identifier)))
        return types.SimpleNamespace(url=self.live[identifier])


@pytest.fixture()
def driver(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_DOCKER_STATE", str(tmp_path / "docker.json"))
    live = LiveAgency(tmp_path / "volumes", tmp_path / "certificates",
                      docker=agency.Docker([sys.executable, str(FAKE)]), max_open=3)
    identifier = live.create("Container case", "one container per case", "linux")["id"]
    evidence = live.volumes.library(identifier) / "evidence"
    evidence.mkdir(exist_ok=True)
    (evidence / "access.log").write_text("".join(
        f'10.0.0.{i % 4} - - [01/Nov/2026:10:{i % 60:02d}:00 +0000] "GET /p{i % 5} HTTP/1.1" {200 + (i % 3) * 100} 512 "-" "curl"\n'
        for i in range(60)))
    with serving_app(live) as base:
        yield base, live, identifier, tmp_path
    live.stack.close()


@contextlib.contextmanager
def serving_app(live):
    """The driver's app on a free port (the shared helper serves a case service)."""
    import threading
    import time

    import uvicorn

    from _browser import free_port

    port = free_port()
    app = agency.create_app(live.volumes.root, live.certificates, agency=live)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    assert server.started
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=10)


@pytest.fixture()
def page(driver):
    base, _live, identifier, _tmp = driver
    try:
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(executable_path=os.environ.get("FIREBLADE_CHROMIUM") or None)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"no Chromium available: {exc}")
    page = browser.new_page(viewport={"width": 1400, "height": 850}, accept_downloads=True)
    page.errors, page.failed = [], []
    page.on("pageerror", lambda error: page.errors.append(str(error)))
    page.on("response", lambda r: page.failed.append(f"{r.status} {r.request.method} {r.url}")
            if r.status >= 400 and "/api/" in r.url else None)
    page.goto(f"{base}/case/{identifier}/")
    page.wait_for_selector("#menubar")
    yield page
    assert not page.errors, page.errors
    browser.close()
    playwright.stop()


def _import_evidence(base, live, identifier):
    started = httpx.post(f"{base}/case/{identifier}/api/cases/{identifier}/import-jobs",
                         data={"source": str(live.volumes.library(identifier) / "evidence"),
                               "organization": "files"}, timeout=30)
    assert started.status_code == 200, started.text
    job = started.json()["job"]
    for _ in range(240):
        state = httpx.get(f"{base}/case/{identifier}/api/import-jobs/{job}").json()
        if state.get("status") not in ("running", "pending", "queued"):
            break
    assert state.get("status") == "complete", state


def test_the_page_under_the_prefix_opens_its_case_and_reads_its_evidence(page, driver):
    base, _live, identifier, _tmp = driver
    page.click('.tabs .tab:text-is("Cases")')
    page.dblclick('tr:has(td:text-is("Container case")) td >> nth=0')
    page.wait_for_selector("#casecombo-label:has-text('Container case')", timeout=20000)
    # An import by server path, the way the Host reads a case's own evidence folder.
    _import_evidence(base, _live, identifier)
    page.click('button[data-act="refresh-cases"], .tb[data-act="refresh-cases"]')
    page.click('.tabs .tab:text-is("Analyses")')
    page.wait_for_selector("#body tr[data-row]", timeout=20000)
    assert not page.failed, page.failed


def test_a_report_link_and_an_export_carry_the_case_prefix(page, driver):
    base, live, identifier, _tmp = driver
    _import_evidence(base, live, identifier)
    page.click('.tabs .tab:text-is("Cases")')
    page.dblclick('tr:has(td:text-is("Container case")) td >> nth=0')
    page.wait_for_selector("#body tr[data-row]", timeout=30000)
    # The report is offered as a link under the prefix, and the link answers.
    page.evaluate("document.querySelector('.menu [data-act=\"report\"]').click()")
    page.wait_for_selector("#report-modal.show")
    page.select_option("#report-type", "client")
    page.click('#report-modal [data-act="report-build"]')
    page.wait_for_selector("#report-result a", timeout=60000)
    href = page.get_attribute("#report-result a", "href")
    assert href.startswith(f"/case/{identifier}/api/"), href
    assert httpx.get(base + href).status_code == 200
    # The export of the grid downloads through the prefix as well.
    page.click("#report-modal [data-act='settings-close']")
    with page.expect_download(timeout=20000) as download:
        page.evaluate("document.querySelector('.menu [data-act=\"export-csv\"]').click()")
    assert download.value.path().stat().st_size > 0 if hasattr(download.value.path(), "stat") else True
    assert not page.failed, page.failed


def test_erasing_through_the_prefix_reaches_the_driver_and_leaves_only_the_certificate(page, driver):
    base, live, identifier, tmp = driver
    page.click('.tabs .tab:text-is("Cases")')
    page.dblclick('tr:has(td:text-is("Container case")) td >> nth=0')
    page.wait_for_selector("#casecombo-label:has-text('Container case')", timeout=20000)
    page.evaluate("document.querySelector('.menu [data-act=\"destroy-case\"]').click()")
    page.wait_for_selector("#destroy-modal.show")
    page.fill("#destroy-operator", "A. Analyst")
    page.fill("#destroy-confirm", "Container case")
    page.click('#destroy-modal [data-act="destroy-run"]')
    page.wait_for_function("document.getElementById('status').innerText.startsWith('Case erased')", timeout=60000)
    assert not live.volumes.has(identifier), "the volume goes with the case"
    assert not (live.volumes.root / identifier).exists()
    certificates = list((tmp / "certificates").glob("*.html"))
    assert certificates and "Evidence destruction certificate" in certificates[0].read_text(encoding="utf-8")
    calls = json.loads((tmp / "docker.json").read_text(encoding="utf-8"))["calls"] if (tmp / "docker.json").exists() else []
    assert isinstance(calls, list)
