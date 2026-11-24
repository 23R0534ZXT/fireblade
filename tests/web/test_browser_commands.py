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
    lines = ["Time,Host,User,Event,Path,Src"]
    for i in range(ROWS):
        lines.append(
            f"2026-11-0{1 + i % 5}T1{i % 10}:{i % 60:02d}:00Z,PC0{i % 4 + 1},{USERS[i % 3]},"
            f"{EVENTS[i % 3]},C:\\Users\\{USERS[i % 3]}\\f{i}.exe,10.0.0.{i % 5}"
        )
    return "\n".join(lines) + "\n"


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    root = tmp_path_factory.mktemp("command-cases")
    with serving(root) as base:
        yield base, root, tmp_path_factory.mktemp("command-evidence")


@pytest.fixture()
def page(server, request):
    """A fresh case for every test: the view an analyst leaves behind (sorts, hidden columns,
    filters) is saved with the case, and one command's effect must not become the next one's."""
    base, root, evidence = server
    name = "Commands " + request.node.name[:40]
    identifier = InvestigationLibrary(root).create(name, "", "windows")["id"]
    (evidence / identifier).mkdir()
    source = evidence / identifier / "events.csv"
    source.write_text(_csv())
    started = httpx.post(
        f"{base}/api/cases/{identifier}/import-jobs",
        data={"source": str(source), "organization": "files"},
        timeout=30,
    )
    assert started.status_code == 200, started.text
    job = started.json()["job"]
    for _ in range(240):
        state = httpx.get(f"{base}/api/import-jobs/{job}").json()
        if state.get("status") not in ("running", "pending", "queued"):
            break
    assert state.get("status") == "complete", state
    with browser_page(base, name) as opened:
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
    """A selection's note is the note of its bookmarks, as in the desktop."""
    mark = "#body tr[data-row] >> nth=3 >> .cb"
    select(page, 3)
    command(page, "note-selection")
    answer(page, "first lead")
    page.wait_for_function("document.querySelectorAll('#body .cb.marked').length === 1")
    assert page.get_attribute(mark, "title") == "first lead"
    command(page, "note-selection")
    answer(page, "second lead")
    page.wait_for_function(
        "document.querySelector('#body .cb.marked').title === 'first lead\\nsecond lead'"
    )
    command(page, "note-replace")
    answer(page, "only this")
    page.wait_for_function("document.querySelector('#body .cb.marked').title === 'only this'")


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
    th = grip.locator("xpath=ancestor::th")
    index = page.evaluate(
        "el => [...el.closest('tr').children].indexOf(el.closest('th'))", grip.element_handle()
    )
    before = th.bounding_box()["width"]
    box = grip.bounding_box()
    page.mouse.move(box["x"] + 2, box["y"] + 5)
    page.mouse.down()
    page.mouse.move(box["x"] + 120, box["y"] + 5, steps=5)
    page.mouse.up()
    assert th.bounding_box()["width"] > before + 60
    command(page, "reset-widths")
    page.wait_for_function(
        f"Math.abs(document.querySelectorAll('#head tr:first-child th')[{index}].getBoundingClientRect().width - {before}) < 4"
    )


# -- The right-click menu of a cell, and the column headers -----------------------------------


def _cell(page, row, column):
    return page.locator("#body tr[data-row]").nth(row).locator(f"td[data-cell='{column}']")


def _context(page, row, column, act):
    _cell(page, row, column).click(button="right")
    page.click(f'#row-menu [data-act="{act}"]')


def test_the_context_menu_copies_the_value_of_the_cell(page):
    _context(page, 1, 2, "copy-value")
    assert page.evaluate("navigator.clipboard.readText()") == "bob"


def test_the_context_menu_filters_on_a_value_and_excludes_it(page):
    _context(page, 0, 2, "filter-value")  # alice
    page.wait_for_function("document.getElementById('pageinfo').innerText.includes('/ 20')")
    assert set(_column_values(page, "User")) == {"alice"}
    command(page, "clear-filters")
    _context(page, 0, 2, "exclude-value")
    page.wait_for_function("document.getElementById('pageinfo').innerText.includes('/ 40')")
    assert "alice" not in set(_column_values(page, "User"))
    command(page, "clear-filters")


def test_the_context_menu_sorts_ascending_and_descending(page):
    _context(page, 0, 3, "sort-asc")
    page.wait_for_function(
        "(() => { const v = [...document.querySelectorAll('#body td[data-cell=\"3\"]')]"
        ".map(e => +e.innerText); return v.length === 60 && v.every((x, i) => !i || v[i - 1] <= x); })()"
    )
    events = [int(v) for v in _column_values(page, "Event")]
    assert events == sorted(events)
    _context(page, 0, 3, "sort-desc")
    page.wait_for_function(
        "document.querySelector('#body tr[data-row] td[data-cell=\"3\"]').innerText === '4688'"
    )
    events = [int(v) for v in _column_values(page, "Event")]
    assert events == sorted(events, reverse=True)


def test_the_context_menu_groups_by_the_column_of_the_cell(page):
    _context(page, 0, 1, "group-by-column")
    page.wait_for_selector("#body tr[data-group]")
    assert page.locator("#body tr[data-group]").count() == 4
    command(page, "group-column")
    page.click('[data-act="group-remove"]')


def test_the_context_menu_hides_a_column_and_pins_another(page):
    _context(page, 0, 4, "hide-column")
    page.wait_for_function(
        "![...document.querySelectorAll('#head tr:first-child th')].some(t => t.innerText.trim() === 'Path')"
    )
    _context(page, 0, 1, "pin-column")
    page.wait_for_function("document.querySelectorAll('#head th.pinned-left').length > 0")
    _context(page, 0, 1, "pin-column")
    page.wait_for_function("document.querySelectorAll('#head th.pinned-left').length === 0")
    _context(page, 0, 3, "pin-column-right")
    page.wait_for_function("document.querySelectorAll('#head th.pinned-right').length > 0")
    _context(page, 0, 3, "pin-column-right")
    command(page, "columns")
    page.click('[data-act="columns-reset"]')
    page.click('.modal.show [data-act="settings-close"]')


def test_the_context_menu_marks_a_row_and_a_colour_rule_paints_what_it_matches(page):
    _cell(page, 2, 0).click()
    _context(page, 2, 0, "bookmark-row")
    page.wait_for_function("document.querySelectorAll('#body .cb.marked').length === 1")
    _context(page, 2, 0, "unmark-selection")
    page.wait_for_function("document.querySelectorAll('#body .cb.marked').length === 0")
    _context(page, 1, 2, "rule-from-cell")  # bob
    page.wait_for_function(
        "[...document.querySelectorAll('#body tr[data-row]')].some(r => r.style.background)"
    )
    painted = page.eval_on_selector_all(
        "#body tr[data-row]",
        "rows => rows.filter(r => r.style.background).map(r => r.querySelector('td[data-cell=\"2\"]').innerText)",
    )
    assert painted and set(painted) == {"bob"}


def test_clicking_a_header_sorts_by_it_and_a_second_click_reverses(page):
    head = page.locator("#head tr:first-child th", has_text="Host")
    head.click()
    page.wait_for_function("document.querySelector('#head th.sorted') !== null")
    hosts = _column_values(page, "Host")
    assert hosts == sorted(hosts)
    page.locator("#head tr:first-child th", has_text="Host").click()
    page.wait_for_timeout(600)
    hosts = _column_values(page, "Host")
    assert hosts == sorted(hosts, reverse=True)


def test_a_column_filter_box_filters_that_column_only(page):
    page.fill('#head input[data-filter="2"]', "carol")
    page.wait_for_function("document.getElementById('pageinfo').innerText.includes('/ 20')")
    assert set(_column_values(page, "User")) == {"carol"}
    page.fill('#head input[data-filter="2"]', "")
    page.wait_for_function(f"document.getElementById('pageinfo').innerText.includes('/ {ROWS}')")


def test_the_search_box_searches_every_column_and_clear_resets_it(page):
    page.fill("#search", "C:\\Users\\bob\\f4.exe")
    page.press("#search", "Enter")
    page.wait_for_function("document.getElementById('pageinfo').innerText.includes('/ 1 ')")
    page.click('button:text-is("Clear the filters")')
    page.wait_for_function(f"document.getElementById('pageinfo').innerText.includes('/ {ROWS}')")
    assert page.input_value("#search") == ""


# -- Analysis --------------------------------------------------------------------------------


def test_highlight_text_marks_the_matches_in_the_cells(page):
    command(page, "highlight-text")
    answer(page, "alice")
    page.wait_for_selector("#body mark")
    marks = page.eval_on_selector_all(
        "#body mark", "els => [...new Set(els.map(e => e.innerText.toLowerCase()))]"
    )
    assert marks == ["alice"]


def test_a_date_condition_keeps_the_rows_of_that_day(page):
    command(page, "date-filter")
    page.select_option("#date-column", label="Time")
    page.select_option("#date-mode", "day")
    page.fill("#date-day", "2026-11-02")
    page.click("#date-add")
    page.wait_for_function("document.getElementById('pageinfo').innerText.includes('/ 12')")
    days = {v[:10] for v in _column_values(page, "Time")}
    assert days == {"2026-11-02"}
    command(page, "clear-filters")


def test_a_derived_column_from_an_expression_joins_the_grid(page):
    command(page, "derived")
    page.fill("#derived-name", "HostLower")
    page.select_option("#derived-operation", "expression")
    page.fill("#derived-expression", "lower(Host)")
    page.click('[data-act="derived-add"]')
    page.wait_for_function(
        "[...document.querySelectorAll('#head tr:first-child th')].some(t => t.innerText.startsWith('HostLower'))"
    )
    assert set(_column_values(page, "HostLower")) == {"pc01", "pc02", "pc03", "pc04"}
    command(page, "derived-check")
    page.wait_for_selector(".modal.show .dialog")
    assert "HostLower" in page.inner_text(".modal.show .dialog")


def test_a_derived_column_converts_a_date_into_the_chosen_format(page):
    command(page, "derived")
    page.fill("#derived-name", "Day")
    page.select_option("#derived-operation", "timestamp")
    page.select_option("#derived-source", label="Time")
    page.click('[data-act="derived-add"]')
    page.wait_for_function(
        "[...document.querySelectorAll('#head tr:first-child th')].some(t => t.innerText.startsWith('Day'))"
    )
    values = _column_values(page, "Day")
    assert len(values) == ROWS and all(v for v in values)


def test_the_cell_window_shows_the_whole_value_and_copies_it(page):
    _cell(page, 3, 4).click()
    command(page, "cell-json")
    page.wait_for_selector("#cell-modal.show")
    assert page.input_value("#cell-full") == "C:\\Users\\alice\\f3.exe"
    page.click('[data-act="cell-copy"]')
    page.wait_for_function("document.getElementById('status').innerText.includes('Cell copied')")
    assert page.evaluate("navigator.clipboard.readText()") == "C:\\Users\\alice\\f3.exe"


def test_provenance_gives_the_sha256_of_the_source_file(page, server):
    import hashlib

    _base, _root, evidence = server
    command(page, "integrity")
    page.wait_for_selector(".modal.show .dialog")
    page.wait_for_function(
        "/[0-9a-f]{64}/.test(document.querySelector('.modal.show .dialog').innerText)"
    )
    shown = set(__import__("re").findall(r"[0-9a-f]{64}", page.inner_text(".modal.show .dialog")))
    hashes = {hashlib.sha256(path.read_bytes()).hexdigest() for path in evidence.glob("*/*.csv")}
    assert shown & hashes, (shown, hashes)


def test_reload_and_stop_keep_the_analysis_as_it_was(page):
    command(page, "stop-query")
    page.wait_for_function("document.getElementById('status').innerText.includes('No query')")
    command(page, "reload-analysis")
    page.wait_for_function(f"document.getElementById('pageinfo').innerText.includes('/ {ROWS}')")
    assert rows(page) == ROWS


def test_the_layout_leaves_as_a_file_and_comes_back(page, tmp_path):
    grip = page.locator("#head tr:first-child th .grip").nth(2)
    th = grip.locator("xpath=ancestor::th")
    index = page.evaluate(
        "el => [...el.closest('tr').children].indexOf(el.closest('th'))", grip.element_handle()
    )
    box = grip.bounding_box()
    page.mouse.move(box["x"] + 2, box["y"] + 5)
    page.mouse.down()
    page.mouse.move(box["x"] + 140, box["y"] + 5, steps=5)
    page.mouse.up()
    widened = th.bounding_box()["width"]
    with page.expect_download() as download:
        command(page, "layout-export")
    saved = tmp_path / "layout.json"
    download.value.save_as(str(saved))
    assert saved.stat().st_size > 2
    command(page, "reset-widths")
    page.wait_for_function(
        f"document.querySelectorAll('#head th')[{index}].getBoundingClientRect().width < {widened} - 40"
    )
    reset = th.bounding_box()["width"]
    with page.expect_file_chooser() as chooser:
        command(page, "layout-import")
    chooser.value.set_files(str(saved))
    # The table is laid out to fit its pane, so the stored width is a target, not a pixel count:
    # what the file brings back is a column wider than the default.
    page.wait_for_function(
        f"document.querySelectorAll('#head th')[{index}].getBoundingClientRect().width > {reset} + 40"
    )


def test_the_advanced_filter_offers_the_engines_operators_by_name(page):
    command(page, "expression-andor")
    options = page.eval_on_selector_all(
        ".modal.show [data-expr-op] option", "els => els.map(e => e.innerText)"
    )
    for wanted in (
        "Does not contain",
        "Regular expression (RE2)",
        "Date ≥ (ISO)",
        "Date < (ISO)",
        "Text >",
        "Named expression",
    ):
        assert wanted in options, options
    assert "contains" not in options, "the operators are named, not shown as codes"


def test_the_advanced_filter_applies_a_regular_expression_and_a_date_operator(page):
    command(page, "expression-andor")
    dialog = page.locator(".modal.show .dialog")
    dialog.locator("select").nth(1).select_option(label="Path")
    dialog.locator("[data-expr-op]").first.select_option("regex")
    dialog.locator("input").first.fill(r"\\bob\\f\d+\.exe$")
    dialog.locator('[data-act="expr-apply"]').click()
    page.wait_for_function("document.getElementById('pageinfo').innerText.includes('/ 20')")
    assert set(_column_values(page, "User")) == {"bob"}
    command(page, "expression-andor")
    dialog = page.locator(".modal.show .dialog")
    dialog.locator("[data-expr-op]").first.select_option("date_before")
    dialog.locator("select").nth(1).select_option(label="Time")
    dialog.locator("input").first.fill("2026-11-02")
    dialog.locator('[data-act="expr-apply"]').click()
    page.wait_for_function("document.getElementById('pageinfo').innerText.includes('/ 12')")
    assert {v[:10] for v in _column_values(page, "Time")} == {"2026-11-01"}


# -- Exporter --------------------------------------------------------------------------------


def _download(page, act, tmp_path, name):
    with page.expect_download(timeout=30000) as download:
        command(page, act)
    saved = tmp_path / name
    download.value.save_as(str(saved))
    return saved


def test_export_csv_gives_the_rows_the_grid_shows_with_the_names_on_screen(page, tmp_path):
    import csv

    command(page, "add-filter")
    answer(page, "User")
    answer(page, "bob")
    page.wait_for_function("document.getElementById('pageinfo').innerText.includes('/ 20')")
    saved = _download(page, "export-csv", tmp_path, "grid.csv")
    with open(saved, encoding="utf-8-sig", newline="") as handle:
        table = list(csv.reader(handle))
    # The export carries the grid's columns, then the desktop's three provenance columns.
    assert table[0][:6] == ["Time", "Host", "User", "Event", "Path", "Src"], table[0]
    assert table[0][6:] == ["Fireblade_SourceRecord", "Fireblade_Bookmarked", "Fireblade_Note"]
    assert len(table) == 21, len(table)
    assert {row[2] for row in table[1:]} == {"bob"}
    assert table[1][4].startswith("C:\\Users\\bob\\"), "a value is exported as it is in the source"


def test_export_xlsx_is_a_workbook_with_the_same_rows(page, tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    saved = _download(page, "export-xlsx", tmp_path, "grid.xlsx")
    sheet = openpyxl.load_workbook(saved).active
    rows = list(sheet.iter_rows(values_only=True))
    assert list(rows[0])[:6] == ["Time", "Host", "User", "Event", "Path", "Src"], rows[0]
    assert len(rows) == ROWS + 1
    assert {row[2] for row in rows[1:]} == {"alice", "bob", "carol"}


def test_export_annotations_lists_the_bookmarks_and_the_notes(page, tmp_path):
    select(page, 0, 1)
    command(page, "mark-selection")
    page.wait_for_function("document.querySelectorAll('#body .cb.marked').length === 2")
    select(page, 2)
    command(page, "note-selection")
    answer(page, "check this one")
    page.wait_for_function("document.querySelectorAll('#body .cb.marked').length === 3")
    saved = _download(page, "export-annotations", tmp_path, "annotations.out")
    text = saved.read_text(encoding="utf-8-sig")
    assert "check this one" in text
    assert text.count("check this one") == 1 and text.count("bookmarked") == 2, text[:600]


def test_a_session_is_saved_and_opened_again(page, tmp_path):
    saved = _download(page, "session-save", tmp_path, "case.fireblade-session")
    import json

    document = json.loads(saved.read_text(encoding="utf-8"))
    assert document["format"] == "fireblade-session"
    assert document["documents"], "the session names the analyses"
    with page.expect_file_chooser() as chooser:
        command(page, "session-open")
    chooser.value.set_files(str(saved))
    page.wait_for_function("document.getElementById('status').innerText.length > 0")
    page.wait_for_function(f"document.getElementById('pageinfo').innerText.includes('/ {ROWS}')")


def test_the_portable_case_is_a_package_the_host_can_import_back(page, server, tmp_path):
    import zipfile

    saved = _download(page, "export-portable", tmp_path, "case.fireblade")
    assert zipfile.is_zipfile(saved)
    with zipfile.ZipFile(saved) as package:
        names = package.namelist()
    assert any(name.endswith("case.json") or "manifest" in name for name in names), names[:10]
    base, _root, _evidence = server
    answer = httpx.post(
        f"{base}/api/cases/import-package",
        files={"file": ("case.fireblade", saved.read_bytes(), "application/octet-stream")},
        timeout=60,
    )
    assert answer.status_code == 200, answer.text


# -- Timeline & correlations -------------------------------------------------------------------


def _timeline(page):
    page.click('.tabs .tab:text-is("Timeline & correlations")')
    page.click("#timeline-build")
    page.wait_for_function(
        "document.getElementById('timeline-view').innerText.includes('60 dated / 60 row(s)')",
        timeout=60000,
    )


def _timeline_rows(page):
    return page.locator("#timeline-rows tr").count()


def test_the_timeline_dates_every_row_of_the_analysis(page):
    _timeline(page)
    assert "detected: Time" in page.inner_text("#timeline-view")
    assert _timeline_rows(page) > 0
    first = page.locator("#timeline-rows tr").first.inner_text()
    assert "2026-11-01" in first and "events.csv" in first


def test_the_timeline_search_keeps_the_matching_events(page):
    _timeline(page)
    before = _timeline_rows(page)
    page.fill("#timeline-search", "carol")
    page.press("#timeline-search", "Enter")
    page.wait_for_function(
        "document.getElementById('timeline-view').innerText.includes('20 dated') "
        "|| document.getElementById('timeline-view').innerText.includes('/ 20')"
    )
    texts = page.eval_on_selector_all("#timeline-rows tr", "els => els.map(e => e.innerText)")
    assert texts and all("carol" in text for text in texts), texts[:3]
    assert len(texts) < before


def test_the_timeline_exports_its_events(page, tmp_path):
    _timeline(page)
    with page.expect_download(timeout=30000) as download:
        page.click("#timeline-export")
    saved = tmp_path / "timeline.csv"
    download.value.save_as(str(saved))
    lines = saved.read_text(encoding="utf-8-sig").splitlines()
    assert lines[0].startswith("Date_UTC,Analysis,Source,Source_row"), lines[0]
    assert "é" not in lines[0], "the header is English"
    assert len(lines) - 1 == ROWS, len(lines)


def test_zooming_the_timeline_narrows_the_window_and_fit_restores_it(page):
    _timeline(page)
    assert "whole extent" in page.inner_text("#timeline-view")
    page.click('[data-act="tl-zoom-in"]')
    page.wait_for_function(
        "!document.getElementById('timeline-view').innerText.includes('whole extent')"
    )
    page.click('[data-act="tl-fit"]')
    page.wait_for_function(
        "document.getElementById('timeline-view').innerText.includes('whole extent')"
    )


def test_a_timeline_row_opens_its_source_line_with_every_column(page):
    _timeline(page)
    page.locator("#timeline-rows tr").nth(3).click()
    page.click('[data-act="timeline-open-row"]')
    page.wait_for_selector("#source-row-modal.show")
    page.wait_for_function("document.getElementById('source-row-list').innerText.includes('Path')")
    text = page.inner_text("#source-row-list")
    for name in ("Time", "Host", "User", "Event", "Path", "Src"):
        assert name in text, text
    assert "C:\\Users\\" in text


# -- IOC hunting -----------------------------------------------------------------------------


def _hunt(page, text):
    page.click('.tabs .tab:text-is("IOC hunting")')
    page.fill("#ioc-input", text)
    page.click("#ioc-scan")
    page.wait_for_function(
        "!document.getElementById('ioc-summary').innerText.includes('Nothing scanned yet')",
        timeout=60000,
    )


def test_an_indicator_hunt_finds_every_row_that_holds_it(page):
    _hunt(page, "10.0.0.2")
    summary = page.inner_text("#ioc-summary")
    assert "12" in summary, summary
    page.wait_for_selector("#ioc-rows tr")
    assert page.locator("#ioc-rows tr").count() >= 1
    assert "10.0.0.2" in page.inner_text("#ioc-view")


def test_an_indicator_that_is_nowhere_matches_nothing(page):
    _hunt(page, "203.0.113.99")
    page.wait_for_function(
        "document.getElementById('ioc-summary').innerText.includes('0')", timeout=30000
    )
    assert page.locator("#ioc-rows tr").count() == 0 or "0" in page.inner_text("#ioc-summary")


def test_the_hunt_exports_its_matches_and_its_summary(page, tmp_path):
    _hunt(page, "10.0.0.1\n10.0.0.3")
    page.wait_for_selector("#ioc-rows tr")
    with page.expect_download(timeout=30000) as matches:
        page.click('[data-act="ioc-export-matches"]')
    saved = tmp_path / "matches.csv"
    matches.value.save_as(str(saved))
    text = saved.read_text(encoding="utf-8-sig")
    assert "10.0.0.1" in text and "10.0.0.3" in text
    assert "10.0.0.2" not in text, "only what was hunted"
    with page.expect_download(timeout=30000) as summary:
        page.click('[data-act="ioc-export-summary"]')
    other = tmp_path / "summary.csv"
    summary.value.save_as(str(other))
    assert "10.0.0.1" in other.read_text(encoding="utf-8-sig")


def test_a_hunt_can_be_limited_to_the_filtered_rows(page):
    command(page, "add-filter")
    answer(page, "User")
    answer(page, "alice")
    page.wait_for_function("document.getElementById('pageinfo').innerText.includes('/ 20')")
    page.click('.tabs .tab:text-is("IOC hunting")')
    page.fill("#ioc-input", "10.0.0.0")
    page.check("#ioc-filters")
    page.click("#ioc-scan")
    page.wait_for_function("document.getElementById('ioc-summary').innerText.includes('4 hit')")
    page.uncheck("#ioc-filters")
    page.click("#ioc-scan")
    page.wait_for_function("document.getElementById('ioc-summary').innerText.includes('12 hit')")


def test_the_reason_a_value_matched_is_in_english(page):
    _hunt(page, "10.0.0.4")
    page.wait_for_selector("#ioc-rows tr")
    assert "Normalised IP address" in page.inner_text("#ioc-rows")
    assert "Adresse" not in page.inner_text("#ioc-view")


def _import_more(page, server, name, content):
    """A second analysis in the open case, imported by path the way a collection is."""
    import time

    base, _root, evidence = server
    case = page.evaluate("state.openCase.id")
    source = evidence / case / name
    source.write_text(content)
    job = httpx.post(
        f"{base}/api/cases/{case}/import-jobs",
        data={"source": str(source), "organization": "files"},
        timeout=30,
    ).json()["job"]
    for _ in range(120):
        if httpx.get(f"{base}/api/import-jobs/{job}").json().get("status") != "running":
            break
        time.sleep(0.25)
    page.evaluate("openCase(state.openCase.id)")
    page.wait_for_function(f"state.openCase.analyses.some(a => a.label === '{name}')")


def test_a_hunt_over_every_analysis_reads_them_all(page, server):
    _import_more(
        page, server, "proxy.csv", "Time,Url\n2026-11-01T10:00:00Z,http://evil.example/a\n"
    )
    page.click('.tabs .tab:text-is("IOC hunting")')
    page.fill("#ioc-input", "evil.example\n10.0.0.1")
    page.click("#ioc-scan")
    page.wait_for_function(
        "document.getElementById('ioc-summary').innerText.includes('this analysis')", timeout=60000
    )
    assert "1 hit" not in page.inner_text("#ioc-summary") or "12" in page.inner_text("#ioc-summary")
    first = page.inner_text("#ioc-summary")
    page.check("#ioc-all")
    page.click("#ioc-scan")
    page.wait_for_function(
        "document.getElementById('ioc-summary').innerText.includes('every analysis')", timeout=60000
    )
    everywhere = page.inner_text("#ioc-summary")
    assert "every analysis" in everywhere and everywhere != first
    assert "proxy.csv" in page.inner_text("#ioc-view")


def test_the_subdomain_option_decides_whether_a_parent_domain_matches_its_children(page, server):
    _import_more(page, server, "dns.csv", "Time,Query\n2026-11-01T10:00:00Z,mail.evil.example\n")
    page.click('.tabs .tab:text-is("Analyses")')
    page.click('#tree .node:has-text("dns.csv")')
    page.wait_for_function("document.getElementById('pageinfo').innerText.includes('/ 1')")
    page.click('.tabs .tab:text-is("IOC hunting")')
    page.fill("#ioc-input", "evil.example")
    page.check("#ioc-subdomains")
    page.click("#ioc-scan")
    page.wait_for_function("document.getElementById('ioc-summary').innerText.includes('1 hit')")
    page.uncheck("#ioc-subdomains")
    page.click("#ioc-scan")
    page.wait_for_function("document.getElementById('ioc-summary').innerText.includes('0 hit')")


def test_the_timeline_can_respect_the_filter_on_screen(page):
    command(page, "add-filter")
    answer(page, "User")
    answer(page, "alice")
    page.wait_for_function("document.getElementById('pageinfo').innerText.includes('/ 20')")
    page.click('.tabs .tab:text-is("Timeline & correlations")')
    page.click("#timeline-build")
    page.wait_for_function(
        "document.getElementById('timeline-view').innerText.includes('60 dated / 60 row(s)')",
        timeout=60000,
    )
    page.check("#timeline-filters")
    page.wait_for_function(
        "document.getElementById('timeline-view').innerText.includes('20 dated / 20 row(s)')",
        timeout=60000,
    )
    texts = page.eval_on_selector_all("#timeline-rows tr", "els => els.map(e => e.innerText)")
    assert texts and all("alice" in text for text in texts)


def test_the_timeline_export_follows_the_same_filter(page, tmp_path):
    command(page, "add-filter")
    answer(page, "User")
    answer(page, "bob")
    page.wait_for_function("document.getElementById('pageinfo').innerText.includes('/ 20')")
    page.click('.tabs .tab:text-is("Timeline & correlations")')
    page.click("#timeline-build")
    page.wait_for_function(
        "document.getElementById('timeline-view').innerText.includes('60 dated / 60 row(s)')",
        timeout=60000,
    )
    page.check("#timeline-filters")
    page.wait_for_function(
        "document.getElementById('timeline-view').innerText.includes('20 dated / 20 row(s)')",
        timeout=60000,
    )
    with page.expect_download(timeout=30000) as download:
        page.click("#timeline-export")
    saved = tmp_path / "t.csv"
    download.value.save_as(str(saved))
    lines = saved.read_text(encoding="utf-8-sig").splitlines()
    assert len(lines) - 1 == 20, len(lines)


# -- Actions & tracking ------------------------------------------------------------------------


def _new_action(page, title, owner="us", priority="medium"):
    page.fill("#action-title", title)
    page.select_option("#action-owner", owner)
    page.select_option("#action-priority", priority)
    page.click("#action-add")
    page.wait_for_function(f"document.getElementById('action-rows').innerText.includes({title!r})")


def test_actions_are_searched_closed_hidden_and_deleted(page):
    page.click('.tabs .tab:text-is("Actions & tracking")')
    _new_action(page, "Collect the proxy logs")
    _new_action(page, "Reset the admin password", "client", "critical")
    assert page.locator("#action-rows tr[data-action]").count() == 2
    page.fill("#action-search", "proxy")
    page.press("#action-search", "Enter")
    page.wait_for_function("document.querySelectorAll('#action-rows tr[data-action]').length === 1")
    assert "proxy" in page.inner_text("#action-rows")
    page.fill("#action-search", "")
    page.press("#action-search", "Enter")
    page.wait_for_function("document.querySelectorAll('#action-rows tr[data-action]').length === 2")
    page.locator("#action-rows tr[data-action]", has_text="proxy").locator(
        "[data-action-close]"
    ).click()
    page.wait_for_function("document.querySelector('#action-rows').innerText.includes('Done')")
    page.check("#action-open-only")
    page.wait_for_function("document.querySelectorAll('#action-rows tr[data-action]').length === 1")
    assert "admin password" in page.inner_text("#action-rows")
    page.uncheck("#action-open-only")
    page.locator("#action-rows tr[data-action]", has_text="admin").click()
    page.once("dialog", lambda dialog: dialog.accept())  # "Remove … from the case?"
    page.click("#action-delete")
    page.wait_for_function("document.querySelectorAll('#action-rows tr[data-action]').length === 1")
    assert "admin password" not in page.inner_text("#action-rows")


def test_an_action_without_a_title_is_refused_with_a_reason(page):
    page.click('.tabs .tab:text-is("Actions & tracking")')
    page.click("#action-add")
    page.wait_for_function("document.getElementById('status').innerText.includes('needs a title')")
    assert page.locator("#action-rows tr[data-action]").count() == 0


def test_the_actions_leave_as_a_csv_in_english(page, tmp_path):
    page.click('.tabs .tab:text-is("Actions & tracking")')
    _new_action(page, "Image the laptop", "third_party", "high")
    with page.expect_download(timeout=30000) as download:
        page.click("#action-export")
    saved = tmp_path / "actions.csv"
    download.value.save_as(str(saved))
    text = saved.read_text(encoding="utf-8-sig")
    assert "Image the laptop" in text
    assert "Third party" in text or "third_party" in text
    for french in ("Priorité", "Responsable", "À faire", "Titre"):
        assert french not in text, text[:300]


def test_indicators_are_tracked_and_removed(page):
    page.click('.tabs .tab:text-is("Actions & tracking")')
    page.click('[data-sub="indicators"]')
    page.fill("#indicator-values", "203.0.113.7\nevil.example")
    page.fill("#indicator-label", "C2 seen in the proxy")
    page.click("#indicator-add")
    page.wait_for_function(
        "document.getElementById('indicator-rows').innerText.includes('evil.example')"
    )
    assert "203.0.113.7" in page.inner_text("#indicator-rows")
    page.locator("#indicator-rows tr", has_text="evil.example").click()
    page.click("#indicator-remove")
    page.wait_for_function(
        "!document.getElementById('indicator-rows').innerText.includes('evil.example')"
    )
    assert "203.0.113.7" in page.inner_text("#indicator-rows")


def test_a_machine_and_an_account_are_recorded(page):
    page.click('.tabs .tab:text-is("Actions & tracking")')
    page.click('[data-sub="entities"]')
    page.fill("#entity-label", "Finance laptop")
    page.fill("#entity-hostname", "FIN-LT-04")
    page.fill("#entity-ip", "10.0.0.44")
    page.click("#entity-add")
    page.wait_for_function("document.getElementById('entity-rows').innerText.includes('FIN-LT-04')")
    assert "Finance laptop" in page.inner_text("#entity-rows")


# -- Imports ---------------------------------------------------------------------------------


def _mixed_folder(page, server):
    """A folder of one readable file and two that no reader recognises, imported by path."""
    import time

    base, _root, evidence = server
    case = page.evaluate("state.openCase.id")
    folder = evidence / case / "mixed"
    folder.mkdir()
    (folder / "good.csv").write_text("A,B\n1,2\n3,4\n")
    (folder / "junk.bin").write_bytes(bytes(range(256)) * 4)
    (folder / "notes.txt").write_text("hello analyst\n")
    job = httpx.post(
        f"{base}/api/cases/{case}/import-jobs",
        data={"source": str(folder), "organization": "files"},
        timeout=30,
    ).json()["job"]
    for _ in range(120):
        if httpx.get(f"{base}/api/import-jobs/{job}").json().get("status") != "running":
            break
        time.sleep(0.25)
    page.evaluate("openCase(state.openCase.id)")
    page.click('.tabs .tab:text-is("Imports")')
    page.wait_for_function("document.getElementById('imports-rows').innerText.includes('junk.bin')")


def _import_lines(page):
    return page.eval_on_selector_all(
        "#imports-rows tr", "els => els.map(e => e.innerText.replace(/\\s+/g, ' ').trim())"
    )


def test_the_imports_table_says_which_files_were_read_and_why_one_was_not(page, server):
    _mixed_folder(page, server)
    lines = _import_lines(page)
    assert any(line.startswith("complete good.csv") for line in lines), lines
    assert any("junk.bin" in line and "No reader recognised" in line for line in lines), lines
    assert "not read" in page.inner_text("#imports-view")


def test_the_imports_filter_by_status_and_by_text(page, server):
    _mixed_folder(page, server)
    page.select_option("#imports-status", "unsupported")
    page.wait_for_function(
        "!document.getElementById('imports-rows').innerText.includes('good.csv')"
    )
    assert len(_import_lines(page)) == 2
    page.select_option("#imports-status", "")
    page.fill("#imports-search", "notes")
    page.wait_for_function(
        "document.querySelectorAll('#imports-rows tr').length === 1 "
        "&& document.getElementById('imports-rows').innerText.includes('notes.txt')"
    )


def test_a_file_is_viewed_from_the_imports_table(page, server):
    _mixed_folder(page, server)
    page.locator("#imports-rows tr", has_text="good.csv").click()
    page.click('[data-act="import-view-file"]')
    page.wait_for_selector("#preview-modal.show, .modal.show .dialog")
    page.wait_for_function(
        "document.querySelector('.modal.show .dialog').innerText.includes('good.csv')"
    )


def test_the_list_of_imports_is_exported(page, server, tmp_path):
    _mixed_folder(page, server)
    with page.expect_download(timeout=30000) as download:
        page.click('[data-act="import-export-list"]')
    saved = tmp_path / "imports.csv"
    download.value.save_as(str(saved))
    text = saved.read_text(encoding="utf-8-sig")
    assert "good.csv" in text and "junk.bin" in text and "notes.txt" in text
    assert "Aucun lecteur" not in text, "the reasons are in English"


def test_a_file_parked_from_the_report_leaves_the_list_and_is_found_under_parked(page, server):
    _mixed_folder(page, server)
    page.locator("#imports-rows tr", has_text="notes.txt").click()
    page.click('[data-act="import-park"]')
    page.wait_for_function(
        "!document.getElementById('imports-rows').innerText.includes('notes.txt')"
    )
    page.select_option("#imports-status", "ignored")
    page.wait_for_function(
        "document.querySelectorAll('#imports-rows tr').length === 1 "
        "&& document.getElementById('imports-rows').innerText.includes('notes.txt')"
    )
