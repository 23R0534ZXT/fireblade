"""Every command the Host offers, run with a real mouse, judged by what it does to the grid.

A command that opens without an error is not a command that works. Each test below presses a
command on a case with known rows and asserts the effect an analyst would see: the rows that are
left, the marks, the notes, the order, the columns, the groups.

Skipped without Playwright and a Chromium; never failed for lack of them.
"""

import httpx
import pytest
from _browser import browser_page, serving  # noqa: E402

from fireblade.core.investigations import InvestigationLibrary

USERS = ["alice", "bob", "carol"]
EVENTS = [4624, 4625, 4688]
ROWS = 60


def _csv():
    lines = ["Time,Host,User,Event,Path"]
    for i in range(ROWS):
        lines.append(
            f"2026-11-0{1 + i % 5}T1{i % 10}:{i % 60:02d}:00Z,PC0{i % 4 + 1},{USERS[i % 3]},"
            f"{EVENTS[i % 3]},C:\\Users\\{USERS[i % 3]}\\f{i}.exe"
        )
    return "\n".join(lines) + "\n"


@pytest.fixture(scope="module")
def host(tmp_path_factory):
    root = tmp_path_factory.mktemp("command-cases")
    identifier = InvestigationLibrary(root).create("Commands", "", "windows")["id"]
    evidence = tmp_path_factory.mktemp("command-evidence")
    (evidence / "events.csv").write_text(_csv())
    with serving(root) as base:
        started = httpx.post(
            f"{base}/api/cases/{identifier}/import-jobs",
            data={"source": str(evidence / "events.csv"), "organization": "files"},
            timeout=30,
        )
        assert started.status_code == 200, started.text
        job = started.json()["job"]
        for _ in range(240):
            state = httpx.get(f"{base}/api/import-jobs/{job}").json()
            if state.get("status") not in ("running", "pending", "queued"):
                break
        assert state.get("status") == "complete", state
        yield base


@pytest.fixture()
def page(host):
    with browser_page(host, "Commands") as opened:
        opened.context.grant_permissions(["clipboard-read", "clipboard-write"])
        yield opened


def command(page, act):
    """Press a command in its menu, with the mouse."""
    menu = page.evaluate(
        f"document.querySelector('.menu [data-act=\"{act}\"]').closest('.menu').dataset.for"
    )
    page.click(f'.menubar .m[data-menu="{menu}"]')
    page.click(f'.menu.show [data-act="{act}"]')


def rows(page):
    return page.locator("#body tr[data-row]").count()


def total(page):
    page.wait_for_function("document.getElementById('pageinfo').innerText.includes('/')")
    import re

    return int(re.search(r"/\s*(\d+)\s*(?:group|row)", page.inner_text("#pageinfo")).group(1))


def status(page):
    return page.inner_text("#status")


def select(page, *positions):
    """Click the rows at these positions: the first plainly, the others with Ctrl."""
    for index, position in enumerate(positions):
        page.locator("#body tr[data-row]").nth(position).locator("td[data-cell]").first.click(
            modifiers=["Control"] if index else []
        )


def answer(page, *texts):
    """Fill the one-line question dialogs, in order."""
    for text in texts:
        page.wait_for_selector("#ask-input:visible")
        page.fill("#ask-input", text)
        page.click('[data-act="ask-ok"]')


# -- Edit ------------------------------------------------------------------------------------


def test_mark_and_unmark_the_selection(page):
    select(page, 0, 1, 2)
    command(page, "mark-selection")
    page.wait_for_function("document.querySelectorAll('#body .cb.marked').length === 3")
    command(page, "unmark-selection")
    page.wait_for_function("document.querySelectorAll('#body .cb.marked').length === 0")


def test_the_bookmarks_button_keeps_only_the_marked_rows(page):
    select(page, 0, 1)
    command(page, "mark-selection")
    page.wait_for_function("document.querySelectorAll('#body .cb.marked').length === 2")
    page.click('button:text-is("Bookmarks")')
    page.wait_for_function("document.querySelectorAll('#body tr[data-row]').length === 2")
    page.click('button:text-is("Bookmarks")')
    page.wait_for_function("document.querySelectorAll('#body tr[data-row]').length > 2")
    select(page, 0, 1)
    command(page, "unmark-selection")


def test_a_note_is_added_then_replaced(page):
    select(page, 3)
    command(page, "note-selection")
    answer(page, "first lead")
    page.wait_for_selector("#body td.noted")
    assert "first lead" in page.get_attribute("#body td.noted", "title")
    command(page, "note-selection")
    answer(page, "second lead")
    page.wait_for_function("document.querySelector('#body td.noted').title.includes('second lead')")
    assert "first lead" in page.get_attribute("#body td.noted", "title")
    command(page, "note-replace")
    answer(page, "only this")
    page.wait_for_function("document.querySelector('#body td.noted').title === 'only this'")


def test_copy_the_rows_puts_them_on_the_clipboard(page):
    select(page, 0, 1)
    command(page, "copy-row")
    page.wait_for_function("document.getElementById('status').innerText.length > 0")
    text = page.evaluate("navigator.clipboard.readText()")
    assert "PC01" in text and "alice" in text and "bob" in text
    assert len(text.strip().splitlines()) >= 2


# -- Filters ---------------------------------------------------------------------------------


def test_add_a_filter_keeps_the_rows_that_contain_the_value_and_clear_brings_them_back(page):
    assert total(page) == ROWS
    command(page, "add-filter")
    answer(page, "User")
    answer(page, "bob")
    page.wait_for_function("document.getElementById('pageinfo').innerText.includes('/ 20')")
    assert rows(page) == 20
    command(page, "clear-filters")
    page.wait_for_function(f"document.getElementById('pageinfo').innerText.includes('/ {ROWS}')")


def test_filter_on_the_active_cell_keeps_that_value(page):
    page.locator("#body tr[data-row] td[data-cell='2']").first.click()
    value = page.locator("#body tr[data-row] td[data-cell='2']").first.inner_text()
    command(page, "filter-active-cell")
    page.wait_for_function("document.getElementById('pageinfo').innerText.includes('/ 20')")
    cells = page.eval_on_selector_all(
        "#body td[data-cell='2']", "els => [...new Set(els.map(e => e.innerText))]"
    )
    assert cells == [value]
    command(page, "clear-filters")


def test_the_advanced_filter_combines_conditions(page):
    command(page, "expression-andor")
    page.wait_for_selector("#expr-modal.show, .modal.show .dialog")
    dialog = page.locator(".modal.show .dialog")
    selects = dialog.locator("select")
    selects.nth(1).select_option(label="User")
    selects.nth(2).select_option("eq")
    dialog.locator("input").first.fill("alice")
    dialog.locator('[data-act="expr-apply"]').click()
    page.wait_for_function("document.getElementById('pageinfo').innerText.includes('/ 20')")
    command(page, "expression-andor")
    page.locator('.modal.show [data-act="expr-clear"]').click()
    page.wait_for_function(f"document.getElementById('pageinfo').innerText.includes('/ {ROWS}')")


def test_ctrl_click_adds_a_row_and_a_second_ctrl_click_takes_it_out(page):
    select(page, 0, 1, 2)
    assert page.locator("#body tr.sel").count() == 3
    page.locator("#body tr[data-row]").nth(1).locator("td[data-cell]").first.click(
        modifiers=["Control"]
    )
    assert page.locator("#body tr.sel").count() == 2
    page.locator("#body tr[data-row]").nth(4).locator("td[data-cell]").first.click(
        modifiers=["Shift"]
    )
    assert page.locator("#body tr.sel").count() == 4  # the range runs from the anchor


# -- View ------------------------------------------------------------------------------------


def _headers(page):
    """The column names as read on screen, without the sort arrow or the sort rank."""
    return page.eval_on_selector_all(
        "#head tr:first-child th",
        "els => els.map(e => e.innerText.replace(/[▲▼]/g, '').replace(/\\d+$/, '').trim())",
    )


def _column_values(page, name):
    names = _headers(page)
    at = names.index(name)
    return page.eval_on_selector_all(
        f"#body tr[data-row] td:nth-child({at + 1})", "els => els.map(e => e.innerText)"
    )


def test_group_by_lists_the_values_with_their_counts_and_back_returns(page):
    command(page, "group-column")
    page.select_option("#group-select", label="User")
    page.click('[data-act="group-apply"]')
    page.wait_for_selector("#body tr[data-group]")
    groups = page.eval_on_selector_all(
        "#body tr[data-group]", "els => els.map(e => [e.dataset.group, e.children[3].innerText])"
    )
    assert sorted(groups) == [["alice", "20"], ["bob", "20"], ["carol", "20"]]
    page.click('#body tr[data-group="bob"]')
    page.wait_for_function("document.querySelectorAll('#body tr[data-row]').length === 20")
    assert set(_column_values(page, "User")) == {"bob"}
    command(page, "group-column")
    page.click('[data-act="group-remove"]')
    page.wait_for_function(f"document.querySelectorAll('#body tr[data-row]').length === {ROWS}")


def test_group_summaries_add_a_column_of_counts_per_group(page):
    command(page, "group-column")
    page.select_option("#group-select", label="Host")
    page.click('[data-act="group-apply"]')
    page.wait_for_selector("#body tr[data-group]")
    command(page, "summaries")
    page.click("#summary-add")
    page.click("#summary-apply")
    page.wait_for_function("document.querySelectorAll('#head tr:first-child th').length > 4")
    command(page, "group-column")
    page.click('[data-act="group-remove"]')


def test_columns_hides_and_shows_a_column(page):
    assert "Path" in _headers(page)
    command(page, "columns")
    box = page.locator('.modal.show .dialog label:has-text("Path") input[data-col]')
    box.uncheck()
    page.click('.modal.show [data-act="settings-close"]')
    page.wait_for_function(
        "![...document.querySelectorAll('#head tr:first-child th')].some(t => t.innerText.trim().startsWith('Path'))"
    )
    command(page, "columns")
    page.click('[data-act="columns-reset"]')
    page.click('.modal.show [data-act="settings-close"]')
    page.wait_for_function(
        "[...document.querySelectorAll('#head tr:first-child th')].some(t => t.innerText.trim().startsWith('Path'))"
    )


def test_multi_column_sort_orders_by_each_key_in_turn(page):
    command(page, "sort-priority")
    page.click("#sort-add")
    page.click("#sort-add")
    columns = page.locator(".modal.show select[data-sort-column]")
    directions = page.locator(".modal.show select[data-sort-direction]")
    columns.nth(0).select_option(label="User")
    directions.nth(0).select_option("asc")
    columns.nth(1).select_option(label="Event")
    directions.nth(1).select_option("desc")
    page.click("#sort-apply")
    page.wait_for_function("document.querySelectorAll('#body tr[data-row]').length > 0")
    page.wait_for_timeout(500)
    users = _column_values(page, "User")
    events = _column_values(page, "Event")
    pairs = list(zip(users, events, strict=True))
    assert users == sorted(users)
    for user in set(users):
        mine = [int(e) for u, e in pairs if u == user]
        assert mine == sorted(mine, reverse=True), (user, mine)


def test_row_details_and_the_artifact_panel_toggle(page):
    visible = lambda selector: page.evaluate(  # noqa: E731
        f"(() => {{ const e = document.querySelector('{selector}'); "
        "return !!e && e.offsetParent !== null && e.getBoundingClientRect().height > 0; })()"
    )
    assert visible("#artifacts")
    command(page, "toggle-artifacts")
    page.wait_for_function("document.querySelector('#artifacts').offsetParent === null")
    command(page, "toggle-artifacts")
    page.wait_for_function("document.querySelector('#artifacts').offsetParent !== null")
    assert visible("#details")
    command(page, "details-toggle")
    page.wait_for_function("document.querySelector('#details').offsetParent === null")
    command(page, "details-toggle")
    page.wait_for_function("document.querySelector('#details').offsetParent !== null")


def test_row_height_changes_the_height_of_the_rows(page):
    before = page.locator("#body tr[data-row]").first.bounding_box()["height"]
    command(page, "row-height")
    page.fill("#rowheight-rows", "60")
    page.click('[data-act="rowheight-apply"]')
    page.wait_for_function(
        f"document.querySelector('#body tr[data-row]').getBoundingClientRect().height > {before} + 10"
    )
    command(page, "row-height")
    page.fill("#rowheight-rows", "0")
    page.click('[data-act="rowheight-apply"]')


def test_reset_widths_restores_the_default_width_of_a_column(page):
    grip = page.locator("#head tr:first-child th .grip").nth(2)
    th = page.locator("#head tr:first-child th").nth(2)
    before = th.bounding_box()["width"]
    box = grip.bounding_box()
    page.mouse.move(box["x"] + 2, box["y"] + 5)
    page.mouse.down()
    page.mouse.move(box["x"] + 120, box["y"] + 5, steps=5)
    page.mouse.up()
    assert th.bounding_box()["width"] > before + 60
    command(page, "reset-widths")
    page.wait_for_function(
        f"Math.abs(document.querySelectorAll('#head tr:first-child th')[2].getBoundingClientRect().width - {before}) < 4"
    )


def test_next_and_previous_analysis_switch_the_open_analysis(host):
    # Needs two analyses: a second file is imported through the service.
    from _browser import browser_page  # noqa: F401
