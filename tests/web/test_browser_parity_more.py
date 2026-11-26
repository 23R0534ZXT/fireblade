"""More of what the desktop offers and the Host now has: the client and mission, the findings level."""

import httpx
from test_browser_findings import GROUPS, findings  # noqa: F401 - the fixture


def test_the_client_and_mission_are_written_and_read_back(page):
    page.click('.tabs .tab:text-is("Actions & tracking")')
    page.click("#client-open")
    page.wait_for_selector("#client-modal.show")
    page.fill("#cm-name", "ACME Corp")
    page.fill("#cm-reference", "IR-2026-14")
    page.fill("#cm-lead", "R. Doe")
    page.fill("#cm-start", "2026-11-01")
    page.fill("#cm-notes", "Scope: finance VLAN")
    page.click("#client-save")
    page.wait_for_function("!document.querySelector('#client-modal.show')")
    case = page.evaluate("state.openCase.id")
    base = page.evaluate("location.origin")
    saved = httpx.get(f"{base}/api/cases/{case}/client", timeout=30).json()
    assert saved["client"]["name"] == "ACME Corp" and saved["client"]["reference"] == "IR-2026-14"
    assert saved["engagement"]["lead"] == "R. Doe" and saved["engagement"]["start"] == "2026-11-01"
    page.click("#client-open")
    page.wait_for_function("document.getElementById('cm-name').value === 'ACME Corp'")


def test_a_bad_date_in_the_mission_is_refused_and_said(page):
    page.click('.tabs .tab:text-is("Actions & tracking")')
    page.click("#client-open")
    page.fill("#cm-start", "not a date")
    page.click("#client-save")
    page.wait_for_function("document.getElementById('cm-result').innerText.length > 0")
    assert page.is_visible("#client-modal.show")


def test_the_findings_can_be_limited_to_a_level_and_above(findings):  # noqa: F811
    page = findings
    assert page.locator("#hayabusa-rows tr").count() == GROUPS
    page.select_option("#finding-level", "critical")
    page.wait_for_function("document.querySelectorAll('#hayabusa-rows tr').length === 1")
    page.select_option("#finding-level", "high")
    page.wait_for_function("document.querySelectorAll('#hayabusa-rows tr').length === 3")
    page.select_option("#finding-level", "medium")
    page.wait_for_function("document.querySelectorAll('#hayabusa-rows tr').length === 4")
    page.select_option("#finding-level", "")
    page.wait_for_function(f"document.querySelectorAll('#hayabusa-rows tr').length === {GROUPS}")


def test_the_preferences_offer_the_desktops_choices_and_keep_them(page):
    page.evaluate("void openPreferences()")
    page.wait_for_selector("#prefs-modal.show")
    for control in (
        "prefs-date-pattern",
        "prefs-details",
        "prefs-right-copy",
        "prefs-pins",
        "prefs-auto-profile",
        "prefs-memory",
        "prefs-query-threads",
        "prefs-parsing-threads",
    ):
        assert page.is_visible(f"#{control}") or page.locator(f"#{control}").count() == 1, control
    page.fill("#prefs-memory", "1536")
    page.press("#prefs-memory", "Tab")
    page.wait_for_timeout(500)
    base = page.evaluate("location.origin")
    assert httpx.get(f"{base}/api/preferences", timeout=30).json()["resource_memory_mb"] == 1536
    httpx.put(f"{base}/api/preferences", json={}, timeout=30)  # automatic again


def test_the_details_can_sit_on_the_right_or_at_the_top(page):
    page.evaluate("void openPreferences()")
    page.select_option("#prefs-details", "right")
    assert "details-right" in page.get_attribute("#analysis-view", "class")
    box = page.locator("#details").bounding_box()
    grid = page.locator("#analysis-view > .gridwrap").bounding_box()
    assert box["x"] >= grid["x"] + grid["width"] - 2, (box, grid)
    page.select_option("#prefs-details", "top")
    assert (
        page.locator("#details").bounding_box()["y"]
        < page.locator("#analysis-view > .gridwrap").bounding_box()["y"]
    )
    page.select_option("#prefs-details", "bottom")
    assert (
        page.locator("#details").bounding_box()["y"]
        > page.locator("#analysis-view > .gridwrap").bounding_box()["y"]
    )


def test_a_right_click_copies_the_cell_when_the_preference_says_so_and_shift_opens_the_menu(page):
    page.evaluate("copyPrefs.rightCopy = true")
    page.locator("#body tr[data-row]").first.locator("td[data-cell='2']").click(button="right")
    page.wait_for_function("document.getElementById('status').innerText.length > 0")
    assert page.locator("#row-menu").is_hidden()
    page.locator("#body tr[data-row]").first.locator("td[data-cell='2']").click(
        button="right", modifiers=["Shift"]
    )
    assert page.locator("#row-menu").is_visible()
    page.evaluate("copyPrefs.rightCopy = false")


def test_the_date_format_preference_rewrites_the_date_columns_the_profile_names(findings):  # noqa: F811
    """The desktop reformats the date columns of the view (a recognised profile names them)."""
    page = findings
    page.click('.tabs .tab:text-is("Analyses")')
    page.wait_for_selector("#body tr[data-row]")
    assert page.evaluate("state.timestamps.includes(0)")  # the Timestamp column of the profile
    cell = "document.querySelector('#body tr[data-row] td[data-cell=\"0\"]')"
    page.wait_for_function(f"{cell}.innerText === '2026-11-02T10:00:00Z'")
    page.evaluate("copyPrefs.dateFormat = 'iso'; void loadRows(false)")
    page.wait_for_function(f"{cell}.innerText === '2026-11-02 10:00:00Z'")
    page.evaluate("copyPrefs.dateFormat = 'iso7'; void loadRows(false)")
    page.wait_for_function(f"{cell}.innerText === '2026-11-02 10:00:00.0000000Z'")
    page.evaluate(
        "copyPrefs.dateFormat = 'custom'; copyPrefs.pattern = 'dd/MM/yyyy HH:mm'; void loadRows(false)"
    )
    page.wait_for_function(f"{cell}.innerText === '02/11/2026 10:00'")
    page.evaluate("copyPrefs.dateFormat = 'source'; void loadRows(false)")
    page.wait_for_function(f"{cell}.innerText === '2026-11-02T10:00:00Z'")
