"""An analyst's session on Linux logs, driven by a real browser.

One case, three logs, and the work of an investigation: filter, search, group, mark, hunt an
indicator, build the timeline, track an action, write the reports, export. Each step checks
what the analyst would read on screen, not only that no request failed.

Skipped without Playwright and a Chromium (FIREBLADE_CHROMIUM names one Playwright did not
download); never failed for lack of them.
"""
import re

import httpx
import pytest

from fireblade.core.investigations import InvestigationLibrary

from _browser import browser_page, serving  # noqa: E402

IPS = ["10.0.0.5", "10.0.0.9", "203.0.113.7", "198.51.100.23", "192.0.2.44"]
PATHS = ["/", "/login", "/admin", "/wp-login.php", "/api/v1/users", "/.env"]
STATUS = [200, 200, 200, 301, 403, 404, 500]


def _nginx():
    lines = []
    for i in range(400):
        lines.append(f'{IPS[i % 5]} - - [01/Nov/2026:{i % 24:02d}:{i % 60:02d}:{(i * 3) % 60:02d} +0000] '
                     f'"GET {PATHS[i % 6]} HTTP/1.1" {STATUS[i % 7]} {100 + i * 7} "-" "curl/7.88"')
    return "\n".join(lines) + "\n"


def _auth():
    lines = []
    for i in range(120):
        verb = "Failed password" if i % 3 else "Accepted publickey"
        lines.append(f"Nov  1 {i % 24:02d}:{i % 60:02d}:{(i * 7) % 60:02d} srv sshd[{1000 + i}]: "
                     f"{verb} for {['root', 'alice', 'bob'][i % 3]} from {IPS[i % 5]} port {20000 + i} ssh2")
    return "\n".join(lines) + "\n"


@pytest.fixture(scope="module")
def host(tmp_path_factory):
    root = tmp_path_factory.mktemp("scenario-cases")
    identifier = InvestigationLibrary(root).create("Linux scenario", "three logs", "linux")["id"]
    evidence = tmp_path_factory.mktemp("scenario-evidence")
    (evidence / "var" / "log" / "nginx").mkdir(parents=True)
    (evidence / "var" / "log" / "nginx" / "access.log").write_text(_nginx())
    (evidence / "var" / "log" / "auth.log").write_text(_auth())
    with serving(root) as base:
        started = httpx.post(f"{base}/api/cases/{identifier}/import-jobs",
                             data={"source": str(evidence), "organization": "files"}, timeout=30)
        assert started.status_code == 200, started.text
        job = started.json()["job"]
        for _ in range(240):
            state = httpx.get(f"{base}/api/import-jobs/{job}").json()
            if state.get("status") not in ("running", "pending", "queued"):
                break
            httpx.get(f"{base}/health")
        assert state.get("status") == "complete", state
        yield base


@pytest.fixture()
def page(host):
    with browser_page(host, "Linux scenario") as opened:
        yield opened


def _open(page, artifact, rows=None):
    """Open an analysis from the tree and wait until the grid shows *that* analysis."""
    rows = rows or {"access.log": 400, "auth.log": 120}[artifact]
    page.click(f'#tree .node:has-text("{artifact}")')
    page.wait_for_function(f"document.getElementById('pageinfo').innerText.includes('/ {rows}')")
    page.wait_for_function("document.querySelectorAll('#body tr[data-row]').length > 0")


def _total(page):
    """The row count the footer announces: '1-200 / 400 row(s)' -> 400."""
    page.wait_for_function("document.getElementById('pageinfo').innerText.includes('/')")
    return int(re.search(r"/\s*([\d\s ,]+)\s*row", page.inner_text("#pageinfo")).group(1)
               .replace(",", "").replace(" ", "").replace(" ", ""))


def _column(page, label):
    """The data index of a column by the name on screen (filter inputs are keyed by it)."""
    return page.evaluate("""(label) => {
        const heads = [...document.querySelectorAll('#head tr:first-child th')];
        const at = heads.findIndex(th => th.innerText.replace(/[▲▼]/g, '').trim() === label);
        const inputs = [...document.querySelectorAll('#head input[data-filter]')];
        return at < 0 ? null : inputs[at - 2] ? inputs[at - 2].dataset.filter : null;
    }""", label)


def test_the_grid_filters_searches_and_clears(page):
    _open(page, "access.log")
    assert _total(page) == 400
    status = _column(page, "Status")
    assert status is not None, "the Status column is on screen, in English"
    page.fill(f'#head input[data-filter="{status}"]', "404")
    page.wait_for_function("document.getElementById('pageinfo').innerText.includes('/ 57')")
    shown = page.eval_on_selector_all("#body tr[data-row]", "rows => rows.length")
    assert 0 < shown <= 57
    page.click("#clear")
    page.wait_for_function("document.getElementById('pageinfo').innerText.includes('/ 400')")
    page.fill("#search", "wp-login")
    page.press("#search", "Enter")
    page.wait_for_function("!document.getElementById('pageinfo').innerText.includes('/ 400')")
    assert 0 < _total(page) < 400
    page.click("#clear")
    page.wait_for_function("document.getElementById('pageinfo').innerText.includes('/ 400')")


def test_bookmarking_a_row_makes_it_the_only_row_of_the_bookmark_view(page):
    _open(page, "access.log")
    page.click("#body tr[data-row] >> nth=2 >> .markcell")
    page.wait_for_function("document.querySelectorAll('#body .cb.on, #body .cb.checked, #body .cb.marked').length > 0",
                           timeout=8000)
    page.click("#bookmarks-only")
    page.wait_for_function("document.getElementById('pageinfo').innerText.includes('/ 1')")
    assert _total(page) == 1
    page.click("#bookmarks-only")


def test_grouping_by_a_column_lists_its_values_and_drills_down(page):
    _open(page, "access.log")
    page.click('.groupbar [data-act="group-column"]')
    page.wait_for_selector("#group-modal.show")
    labels = page.eval_on_selector_all("#group-modal select option", "o => o.map(x => x.textContent.trim())")
    assert "Status" in labels
    page.select_option("#group-modal select >> nth=0", label="Status")
    page.click("#group-modal button:has-text('Group')")
    page.wait_for_selector("#body tr[data-group]")
    assert page.locator("#body tr[data-group]").count() >= 5
    page.locator("#body tr[data-group]").first.click()
    page.wait_for_selector("#body tr[data-row]")


def test_an_indicator_hunt_reports_its_matches(page):
    page.click('.tabs .tab:text-is("IOC hunting")')
    page.fill("#ioc-input", "203.0.113.7\nnot-in-the-logs.example")
    page.check("#ioc-all")
    page.click("#ioc-scan")
    page.wait_for_function("document.querySelectorAll('#ioc-rows tr').length > 0", timeout=20000)
    assert "203.0.113.7" in page.inner_text("#ioc-list-rows")
    assert page.locator("#ioc-rows tr").count() >= 1


def test_the_timeline_dates_the_access_log_and_leaves_the_year_less_log_undated(page):
    page.click('.tabs .tab:text-is("Timeline & correlations")')
    page.click("#timeline-build")
    page.wait_for_function("document.getElementById('timeline-info').innerText.includes('dated')", timeout=30000)
    legend = page.inner_text("#timeline-legend")
    assert re.search(r"access\.log\s*—\s*400 dated", legend), legend
    assert re.search(r"auth\.log\s*—\s*0 dated", legend), legend
    options = page.eval_on_selector_all("#timeline-dates select option", "o => o.map(x => x.textContent)")
    assert not any("Horodatage" in text for text in options), "columns are named in English"


def test_an_action_is_tracked_with_english_words_and_closed(page):
    page.click('.tabs .tab:text-is("Actions & tracking")')
    page.fill("#action-title", "Review the failed ssh logins")
    page.select_option("#action-owner", "third_party")
    page.select_option("#action-priority", "high")
    page.click("#action-add")
    page.wait_for_selector("#action-rows tr[data-action]")
    row = page.inner_text("#action-rows tr[data-action]")
    assert "Third party" in row and "High" in row and "To do" in row, row
    page.click("#action-rows [data-action-close]")
    page.wait_for_function("document.querySelector('#action-rows').innerText.includes('Done')")


def test_the_reports_are_written_in_english(page, host):
    identifier = httpx.get(f"{host}/api/cases").json()["cases"][0]["id"]
    for route in ("report", "client-report"):
        written = httpx.post(f"{host}/api/cases/{identifier}/{route}", json={}, timeout=60)
        assert written.status_code == 200, written.text
        document = httpx.get(host + written.json()["url"]).text
        for french in ("Synthèse", "Aucun constat", "Périmètre", "Généré le", "Aucune action"):
            assert french not in document, (route, french)
