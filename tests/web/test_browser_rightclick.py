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


def test_a_text_expression_filters_like_the_desktop_parser(page):
    total = page.evaluate("state.total")
    page.evaluate("void act('expression-text')")
    page.wait_for_selector("#ask-modal.show")
    page.fill("#ask-input", "Contains([User], 'alice')")
    page.click('#ask-modal [data-act="ask-ok"]')
    page.wait_for_function("state.total < " + str(total) + " && state.total > 0", timeout=30000)
    kept = page.evaluate("state.total")
    page.evaluate("void act('expression-text')")
    page.wait_for_selector("#ask-modal.show")
    page.fill("#ask-input", "Contains([")
    page.click('#ask-modal [data-act="ask-ok"]')
    page.wait_for_function("!document.querySelector('#ask-modal.show')")
    assert page.evaluate("state.total") == kept  # a refused expression changes nothing


def test_reset_the_view_puts_back_filters_sorts_groups_and_hidden_columns(page):
    total = page.evaluate("state.total")
    page.evaluate(
        "state.filters = [{column: 2, operator: 'eq', value: 'alice'}]; state.hidden.add(1); state.groups = [2]"
    )
    page.evaluate("void act('reset-view')")
    page.wait_for_function(
        f"state.total === {total} && state.filters.length === 0 && state.groups.length === 0 && state.hidden.size === 0"
    )


def test_the_search_text_is_highlighted_with_the_highlight_text_like_the_desktop(page):
    """The desktop paints both terms (its highlight and its search) in the cells."""
    page.fill("#search", "alice")
    page.press("#search", "Enter")
    page.wait_for_function("state.search === 'alice' && document.querySelector('#body mark')")
    marks = page.eval_on_selector_all(
        "#body mark", "els => els.map(e => e.textContent.toLowerCase())"
    )
    assert marks and set(marks) == {"alice"}
    page.evaluate("state.highlight = 'PC0'; renderGrid()")
    marks = page.eval_on_selector_all(
        "#body mark", "els => els.map(e => e.textContent.toLowerCase())"
    )
    assert {"alice", "pc0"} <= set(marks)


def _timeline_total(page, **params):
    import httpx

    case = page.evaluate("state.openCase.id")
    base = page.evaluate("location.origin")
    answer = httpx.get(
        f"{base}/api/cases/{case}/timeline",
        params={"include_undated": "true", **params},
        timeout=120,
    )
    assert answer.status_code == 200, answer.text
    return answer.json()["extent"]["rows"]


def test_the_timeline_compares_a_whole_value_or_only_the_bookmarks_like_the_desktop(page):
    everything = _timeline_total(page)
    part = _timeline_total(page, text="ali", kind="user")
    assert 0 < part < everything
    assert _timeline_total(page, text="ali", kind="user", exact="true") == 0
    whole = _timeline_total(page, text="alice", kind="user", exact="true")
    assert whole == part
    assert _timeline_total(page, bookmarks="true") == 0
    row = page.locator("#body tr[data-row]").first.get_attribute("data-row")
    case, analysis = page.evaluate("[state.openCase.id, state.analysis]")
    import httpx

    base = page.evaluate("location.origin")
    httpx.post(
        f"{base}/api/cases/{case}/analyses/{analysis}/bookmark",
        json={"row_id": int(row), "note": "bookmarked"},
    )
    # the index is read again by Build / refresh, as the desktop's Refresh does
    page.evaluate("void loadTimeline(false, true)")
    for _ in range(60):
        if _timeline_total(page, bookmarks="true") == 1:
            break
        page.wait_for_timeout(500)
    assert _timeline_total(page, bookmarks="true") == 1


def test_the_menu_offers_to_edit_the_note_of_a_selection_that_has_one(page):
    cell = page.locator("#body tr[data-row]").first.locator("td[data-cell='1']")
    cell.click()
    cell.click(button="right")
    assert page.locator('#row-menu [data-act="note-selection"]').is_visible()
    assert page.locator('#row-menu [data-act="note-replace"]').is_hidden()
    page.evaluate("document.getElementById('row-menu').hidden = true")
    row = page.locator("#body tr[data-row]").first.get_attribute("data-row")
    page.evaluate(f"state.bookmarks.set('{row}', 'a note')")
    cell.click(button="right")
    assert page.locator('#row-menu [data-act="note-replace"]').is_visible()
    assert page.locator('#row-menu [data-act="note-selection"]').is_hidden()
