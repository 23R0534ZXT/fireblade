"""The right-click menu of a cell, command by command: the desktop's cell menu, in the browser."""

import httpx
from _audit import context


def _first(page, column=1):
    return page.locator("#body tr[data-row]").first.locator(f"td[data-cell='{column}']")


def test_a_cell_note_is_written_from_the_menu_and_kept_with_the_case(page):
    row = page.locator("#body tr[data-row]").first.get_attribute("data-row")
    context(page, 0, 1, "cell-note")
    page.wait_for_selector("#ask-modal.show")
    page.fill("#ask-modal input, #ask-modal textarea", "seen on the jump host")
    page.click('#ask-modal [data-act="ask-ok"]')
    page.wait_for_function("!document.querySelector('#ask-modal.show')")
    base = page.evaluate("location.origin")
    case, analysis = page.evaluate("[state.openCase.id, state.analysis]")
    notes = httpx.post(
        f"{base}/api/cases/{case}/analyses/{analysis}/cellnotes", json={"row_ids": [int(row)]}
    ).json()["notes"]
    assert "seen on the jump host" in str(notes), notes


def test_a_note_on_the_selection_marks_the_row_with_it(page):
    _first(page).click()
    context(page, 0, 1, "note-selection")
    page.wait_for_selector("#ask-modal.show")
    page.fill("#ask-modal input, #ask-modal textarea", "to review")
    page.click('#ask-modal [data-act="ask-ok"]')
    page.wait_for_function("!document.querySelector('#ask-modal.show')")
    row = page.locator("#body tr[data-row]").first.get_attribute("data-row")
    page.wait_for_function(
        f"(state.bookmarks.get('{row}') || '').includes('to review')", timeout=15000
    )


def test_searching_a_value_everywhere_runs_the_global_search_on_it(page):
    value = _first(page).inner_text().strip()
    context(page, 0, 1, "search-value")
    page.wait_for_selector("#search-modal.show")
    assert page.input_value("#global-text") == value
    page.wait_for_function(
        "document.getElementById('global-summary').innerText.includes('hit')", timeout=30000
    )


def test_correlating_a_value_opens_the_timeline_on_it(page):
    value = _first(page).inner_text().strip()
    context(page, 0, 1, "correlate-value")
    page.wait_for_function(
        "document.getElementById('timeline-view').style.display !== 'none'", timeout=30000
    )
    assert page.input_value("#timeline-search") == value
