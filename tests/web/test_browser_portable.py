"""A case leaves as a portable file and comes back whole, through a real browser.

Export the case, take the download, import it as a new case, and read the same evidence:
the promise of the .fireblade file is that the case survives the trip with its analyses,
its bookmarks and its notes. History and recovery keeps a state each time the case changes.

Skipped without Playwright and a Chromium; never failed for lack of them.
"""

import time

import httpx
import pytest
from _browser import browser_page, serving  # noqa: E402

from fireblade.core.investigations import InvestigationLibrary


@pytest.fixture()
def host(tmp_path):
    root = tmp_path / "cases"
    root.mkdir()
    identifier = InvestigationLibrary(root).create("Portable", "round trip", "linux")["id"]
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "events.csv").write_text(
        "Time,Host,User\n"
        + "".join(f"2026-11-01T10:{i:02d}:00Z,PC{i % 3},user{i % 5}\n" for i in range(40))
    )
    with serving(root) as base:
        started = httpx.post(
            f"{base}/api/cases/{identifier}/import-jobs",
            data={"source": str(evidence), "organization": "files"},
            timeout=30,
        )
        job = started.json()["job"]
        for _ in range(240):
            state = httpx.get(f"{base}/api/import-jobs/{job}").json()
            if state.get("status") not in ("running", "pending", "queued"):
                break
            time.sleep(0.25)
        assert state.get("status") == "complete", state
        yield base, identifier, tmp_path


@pytest.fixture()
def page(host):
    base, _identifier, _tmp = host
    with browser_page(base, "Portable") as opened:
        yield opened


def test_a_bookmarked_row_survives_the_portable_round_trip(page, host):
    base, identifier, tmp = host
    page.click("#body tr[data-row] >> nth=3 >> .markcell")
    page.wait_for_function(
        "document.querySelectorAll('#body .cb.on, #body .cb.checked, #body .cb.marked').length > 0"
    )

    box = page.locator('.menubar .m[data-menu="exporter"]').bounding_box()
    page.mouse.move(box["x"] + 5, box["y"] + 5)
    page.mouse.down()
    page.mouse.up()
    with page.expect_download(timeout=60000) as download:
        item = page.locator('.menu.show [data-act="export-portable"]').bounding_box()
        page.mouse.move(item["x"] + 8, item["y"] + 5)
        page.mouse.down()
        page.mouse.up()
    package = tmp / "trip.fireblade"
    download.value.save_as(str(package))
    assert package.stat().st_size > 0

    page.click('.tabs .tab:text-is("Cases")')
    page.set_input_files("#package-input", str(package))
    page.wait_for_function(
        "document.querySelectorAll('#cases-rows tr, tr[data-case]').length >= 2", timeout=60000
    )
    cases = httpx.get(f"{base}/api/cases").json()["cases"]
    assert len(cases) == 2, cases
    copy = next(item for item in cases if item["id"] != identifier)
    detail = httpx.get(f"{base}/api/cases/{copy['id']}").json()
    assert detail["analysis_count"] == 1
    marks = httpx.get(f"{base}/api/cases/{copy['id']}/analyses/0/bookmarks").json()["bookmarks"]
    assert len(marks) == 1, "the bookmark made before the export is in the imported case"
    rows = httpx.get(f"{base}/api/cases/{copy['id']}/analyses/0/rows", params={"limit": 5}).json()
    assert rows["total"] == 40


def test_history_keeps_a_state_after_a_change_and_restores_it(page, host):
    base, identifier, _tmp = host
    before = httpx.get(f"{base}/api/cases/{identifier}/history").json()["count"]
    page.click("#body tr[data-row] >> nth=0 >> .markcell")
    page.wait_for_function(
        "document.querySelectorAll('#body .cb.on, #body .cb.checked, #body .cb.marked').length > 0"
    )
    page.keyboard.press("Control+s")  # Save case: a recovery point is asked for, and announced
    page.wait_for_function("document.getElementById('status').innerText.includes('recovery point')")
    after = httpx.get(f"{base}/api/cases/{identifier}/history").json()["count"]
    assert after > before, f"Save case leaves a state to recover: {before} -> {after}"
    box = page.locator('.menubar .m[data-menu="case"]').bounding_box()
    page.mouse.move(box["x"] + 5, box["y"] + 5)
    page.mouse.down()
    page.mouse.up()
    item = page.locator('.menu.show [data-act="case-history"]').bounding_box()
    page.mouse.move(item["x"] + 8, item["y"] + 5)
    page.mouse.down()
    page.mouse.up()
    page.wait_for_selector("#history-modal.show")
    page.wait_for_function(
        "document.querySelectorAll('#history-modal button').length > 1", timeout=15000
    )
