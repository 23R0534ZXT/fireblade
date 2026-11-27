"""A case from creation to erasure, driven by a real browser.

Create, save, import a file through the dialog, rename, and erase with its certificate: the
whole life of a case as the analyst lives it, and what is left on disk at the end.

Skipped without Playwright and a Chromium; never failed for lack of them.
"""

import os

import pytest
from _audit import pick_import_source
from _browser import serving  # noqa: E402

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright  # noqa: E402


@pytest.fixture()
def host(tmp_path):
    root = tmp_path / "cases"
    root.mkdir()
    with serving(root) as base:
        yield base, root, tmp_path


@pytest.fixture()
def page(host):
    base, _root, _tmp = host
    try:
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(
            executable_path=os.environ.get("FIREBLADE_CHROMIUM") or None
        )
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"no Chromium available: {exc}")
    page = browser.new_page(viewport={"width": 1400, "height": 850})
    page.errors = []
    page.on("pageerror", lambda error: page.errors.append(str(error)))
    page.goto(base + "/")
    page.wait_for_selector("#menubar")
    page.click('.tabs .tab:text-is("Cases")')
    yield page
    assert not page.errors, page.errors
    browser.close()
    playwright.stop()


def _status(page):
    return page.inner_text("#status")


def test_a_case_is_created_saved_imported_renamed_and_erased(page, host):
    _base, root, tmp = host
    # Create -------------------------------------------------------------------------
    library = page.locator("#cases-view")
    assert library.get_by_role("heading", name="Your case library is empty").is_visible()
    assert library.get_by_role("button", name="Import a portable case…").is_visible()
    assert library.get_by_role("button", name="Erase the case…").count() == 0
    library.get_by_role("button", name="New case…").click()
    page.wait_for_selector("#case-modal.show")
    page.fill("#case-name", "Lifecycle")
    page.select_option("#case-environment", "linux")
    page.click("#case-confirm")
    # The new case opens at once, as in the desktop; the library still lists it.
    page.wait_for_function("document.getElementById('casecombo-label').innerText === 'Lifecycle'")
    page.click('.tabs .tab:text-is("Cases")')
    page.wait_for_selector('tr:has(td:text-is("Lifecycle"))')
    assert len([p for p in root.iterdir() if p.is_dir() and len(p.name) == 32]) == 1

    # Saving is its own command: the menu entry keeps its name after the dialog was used.
    page.click('.menubar .m[data-menu="case"]')
    assert page.inner_text('.menu.show [data-act="case-save"]').startswith("Save case")
    page.mouse.click(700, 600)

    # Open, then save -------------------------------------------------------------------
    page.dblclick('tr:has(td:text-is("Lifecycle")) td >> nth=0')
    page.wait_for_function(
        "document.getElementById('casecombo-label').innerText.includes('Lifecycle')"
    )
    page.wait_for_selector("#analysis-view", state="visible")
    page.locator("#grid-empty").get_by_role("button", name="Import evidence…").wait_for()
    with page.expect_response(
        lambda response: response.url.endswith("/save") and response.request.method == "POST"
    ) as saved:
        page.keyboard.press("Control+s")
    assert saved.value.ok
    page.wait_for_function(
        "document.getElementById('status').innerText.startsWith('Case saved at')"
    )

    # Import a file through the dialog ------------------------------------------------
    pick_import_source(page, "import-file")
    page.wait_for_selector("#import-modal.show")
    sample = tmp / "events.csv"
    sample.write_text(
        "Time,Host,User\n2026-11-01T10:00:00Z,PC01,alice\n2026-11-01T10:05:00Z,PC02,bob\n"
    )
    page.set_input_files("#preview-input", str(sample))
    page.wait_for_function("!document.getElementById('preview-import').disabled", timeout=15000)
    page.click("#preview-import")
    page.wait_for_selector("#body tr[data-row]", timeout=30000)
    assert page.locator("#body tr[data-row]").count() == 2
    assert "events.csv" in page.inner_text("#pane-tabs")

    # Rename --------------------------------------------------------------------------
    page.click('.tabs .tab:text-is("Cases")')
    page.click('button[data-act="rename-case"]')
    page.wait_for_selector("#case-modal.show")
    assert "Save" in page.inner_text("#case-confirm")
    page.fill("#case-name", "Lifecycle renamed")
    page.click("#case-confirm")
    page.wait_for_selector('tr:has(td:text-is("Lifecycle renamed"))')

    # Erase: the case, its evidence and its folder go; the certificate stays outside ------------
    page.click('.menubar .m[data-menu="case"]')
    page.click('.menu.show [data-act="destroy-case"]')
    page.wait_for_selector("#destroy-modal.show")
    page.fill("#destroy-operator", "A. Analyst")
    page.fill("#destroy-confirm", "Lifecycle renamed")
    page.click('#destroy-modal [data-act="destroy-run"]')
    page.wait_for_function(
        "document.getElementById('status').innerText.startsWith('Case erased')", timeout=60000
    )
    assert not [p for p in root.iterdir() if p.is_dir() and len(p.name) == 32], (
        "no folder of the case is left"
    )
    certificates = [p for p in tmp.rglob("*.html") if "pv-" in p.name]
    assert certificates, "the certificate is written outside the case"
    text = certificates[0].read_text(encoding="utf-8")
    assert "Evidence destruction certificate" in text and "A. Analyst" in text
    assert "Procès-verbal" not in text
