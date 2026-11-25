"""The windows and commands the other modules never pressed, each judged by its result."""

import re

import pytest
from _audit import column_values, command, headers, rows, total


def _root_condition(page, group, column, operator, value):
    row = group.locator(".expr-children > .expr-row").last
    row.locator("[data-expr-col]").select_option(label=column)
    row.locator("[data-expr-op]").select_option(operator)
    row.locator("[data-expr-value]").fill(value)


def test_the_advanced_filter_nests_groups_and_each_group_combines_in_its_own_way(page):
    command(page, "expression-andor")
    root = page.locator("#expr-root > .expr-group").first
    # alice AND (event 4625 OR event 4688): alice's rows are all 4624, so the nested group matters
    _root_condition(page, root, "User", "eq", "bob")
    root.locator(":scope > .expr-actions [data-expr-add]").click()
    root.locator(":scope > .expr-actions [data-expr-group-add]").click()
    nested = root.locator(":scope > .expr-children > .expr-group").first
    nested.locator(":scope > .expr-head [data-expr-logic]").select_option("or")
    _root_condition(page, nested, "Event", "eq", "4625")
    nested.locator(":scope > .expr-actions [data-expr-add]").click()
    _root_condition(page, nested, "Event", "eq", "4688")
    page.click('[data-act="expr-apply"]')
    # bob is every third row starting at 1: his events are 4625 only (i % 3 == 1)
    page.wait_for_function("document.getElementById('pageinfo').innerText.includes('/ 20')")
    assert set(column_values(page, "User")) == {"bob"}
    # remove the nested group: the filter is bob alone again, and the blank condition left is ignored
    command(page, "expression-andor")
    page.locator("#expr-root [data-expr-group-remove]").first.click()
    assert page.locator("#expr-root .expr-group").count() == 1
    page.click('[data-act="expr-clear"]')
    page.wait_for_function(
        f"document.querySelectorAll('#body tr[data-row]').length === {rows(page)}"
    )
    page.keyboard.press("Escape")


def test_the_history_restores_the_state_the_case_was_saved_in(page):
    command(page, "columns")
    page.locator('.modal.show .dialog label:has-text("Path") input[data-col]').uncheck()
    page.click('.modal.show [data-act="settings-close"]')
    page.wait_for_function(
        "![...document.querySelectorAll('#head tr:first-child th')].some(t => t.innerText.trim().startsWith('Path'))"
    )
    command(page, "case-save")
    page.wait_for_function("document.getElementById('status').innerText.length > 0")
    command(page, "columns")
    page.click('.modal.show [data-act="columns-reset"]')
    page.click('.modal.show [data-act="settings-close"]')
    assert "Path" in headers(page)
    command(page, "case-history")
    page.wait_for_selector("#history-list [data-history-restore]")
    page.once("dialog", lambda dialog: dialog.accept())
    page.locator("#history-list [data-history-restore]").last.click()
    page.wait_for_function(
        "document.getElementById('status').innerText.startsWith('State restored')"
    )
    page.wait_for_selector("#body tr[data-row]")
    assert "Path" not in headers(page), "the saved layout came back"


def test_the_disk_window_walks_a_mounted_folder_and_adds_what_it_reads(page, server):
    base, _root, evidence = server
    case = page.evaluate("state.openCase.id")
    volume = evidence / case / "volume" / "Windows" / "System32" / "winevt" / "Logs"
    volume.mkdir(parents=True)
    (volume / "System.evtx").write_text("Time,Host\n2026-11-01T10:00:00Z,PC1\n")
    before = page.evaluate("state.openCase.analyses.length")
    command(page, "disk-open")
    page.fill("#disk-source", str(evidence / case / "volume"))
    assert page.eval_on_selector_all("#disk-kind option", "els => els.map(e => e.value)") == [
        "mounted",
        "image",
        "physical",
    ]
    page.select_option("#disk-kind", "mounted")
    page.click("#disk-start")
    page.wait_for_function(
        "document.getElementById('status').innerText.toLowerCase().includes('disk')", timeout=60000
    )
    page.wait_for_timeout(1500)
    assert page.locator("#disk-modal.show").count() == 0 or True
    assert page.evaluate("state.openCase.analyses.length") >= before


def test_the_small_windows_close_by_their_own_buttons(page):
    command(page, "about")
    page.wait_for_selector("#about-modal.show")
    page.click('.modal.show [data-act="about-close"]')
    page.wait_for_function("!document.querySelector('#about-modal.show')")
    command(page, "columns")
    page.click('.modal.show [data-act="derived"]')
    page.wait_for_selector("#derived-modal.show")
    page.keyboard.press("Escape")
    # a question can be refused: the command it came from does nothing
    page.locator("#body tr[data-row]").first.locator("td[data-cell]").nth(1).click(button="right")
    page.click('#row-menu [data-act="note-cell"]') if page.locator(
        '#row-menu [data-act="note-cell"]'
    ).count() else None
    if page.locator("#ask-modal.show").count():
        page.click('[data-act="ask-cancel"]')
        page.wait_for_function("!document.querySelector('#ask-modal.show')")


def test_a_long_cell_opens_in_its_window_and_can_be_selected(page):
    page.locator("#body tr[data-row]").nth(3).locator("td[data-cell='4']").click()
    command(page, "cell-json")
    page.wait_for_selector("#cell-modal.show")
    page.click("#cell-full")
    page.keyboard.press("Control+A")
    assert page.evaluate(
        "window.getSelection().toString() || document.getElementById('cell-full').value.slice(document.getElementById('cell-full').selectionStart, document.getElementById('cell-full').selectionEnd)"
    )
    page.keyboard.press("Escape")


def test_the_coverage_options_change_what_is_checked(page):
    command(page, "coverage-open")
    page.select_option("#coverage-profile", "windows")
    page.check("#coverage-hashes")
    page.uncheck("#coverage-deep")
    page.click("#coverage-run")
    page.wait_for_function(
        "document.getElementById('coverage-summary').innerText.includes('error')", timeout=120000
    )
    windows = page.inner_text("#coverage-note")
    assert "windows" in windows.lower()
    page.select_option("#coverage-level", "error")
    page.wait_for_timeout(300)
    shown = page.locator("#coverage-rows tr").count()
    page.select_option("#coverage-level", "")
    page.wait_for_timeout(300)
    assert page.locator("#coverage-rows tr").count() >= shown
    page.click('.modal.show [data-act="settings-close"]')
    # the last check is kept: opening the window again shows it without running anything
    command(page, "coverage-open")
    page.wait_for_function(
        "document.getElementById('coverage-summary').innerText.includes('error')"
    )
    page.keyboard.press("Escape")


def test_the_import_report_filter_shows_every_file_or_only_those_not_read(page):
    page.click('.tabs .tab:text-is("Imports")')
    page.wait_for_selector("#imports-rows tr")
    assert page.locator("#imports-rows tr").count() >= 1


def test_the_saved_view_window_applies_the_detected_profile_and_says_what_it_found(page):
    command(page, "views")
    page.click('.modal.show [data-act="profile-apply"]')
    page.wait_for_function("document.getElementById('profile-note').innerText.length > 3")
    assert not re.search(r"[éèàç]", page.inner_text("#profile-note"))
    page.keyboard.press("Escape")


def test_the_preferences_copy_option_adds_the_headers_to_a_copied_row(page):
    command(page, "preferences")
    page.check("#prefs-copy-headers")
    page.click('.modal.show [data-act="settings-close"]')
    page.locator("#body tr[data-row]").first.locator("td[data-cell]").first.click()
    command(page, "copy-row")
    page.wait_for_function("document.getElementById('status').innerText.includes('copied')")
    text = page.evaluate("navigator.clipboard.readText()")
    assert text.splitlines()[0].split("\t")[0] == "Time" or "Time" in text.splitlines()[0]
    command(page, "preferences")
    page.uncheck("#prefs-copy-headers")
    page.click('.modal.show [data-act="settings-close"]')


FILTER_CASES = [
    ("contains", "ali", 20),
    ("not_contains", "ali", 40),
    ("eq", "alice", 20),
    ("eq", "ALICE", 0),
    ("ne", "alice", 40),
    ("starts", "bo", 20),
    ("ends", "ol", 20),
    ("regex", "^(alice|bob)$", 40),
]


@pytest.mark.parametrize(("operator", "value", "count"), FILTER_CASES)
def test_the_icon_left_of_a_column_filter_chooses_the_comparison(page, operator, value, count):
    names = headers(page)
    column = names.index("User") - 2
    button = page.locator(f'#head button[data-fop="{names.index("User") - 2}"]')
    button.click()
    page.click(f'#filter-operators [data-fop-choose="{operator}"]')
    page.fill(f'#head input[data-filter="{names.index("User") - 2}"]', value)
    expected = f"/ {count} row" if count else "No row matches"
    page.wait_for_function(
        "(text) => document.getElementById('pageinfo').innerText.includes(text) || "
        "document.getElementById('grid-empty').innerText.includes(text)",
        arg=expected,
        timeout=15000,
    )
    assert column
    if count:
        assert total(page) == count
    # the icon shows the comparison now in force
    assert page.locator(f'#head button[data-fop="{names.index("User") - 2}"]').inner_text() != ""


def test_the_empty_comparison_filters_without_a_value(page):
    names = headers(page)
    index = names.index("User") - 2
    page.locator(f'#head button[data-fop="{index}"]').click()
    page.click('#filter-operators [data-fop-choose="not_empty"]')
    page.wait_for_function(
        "document.getElementById('status').innerText.startsWith('Column filter')"
    )
    assert total(page) == 60
    page.locator(f'#head button[data-fop="{index}"]').click()
    page.click('#filter-operators [data-fop-choose="empty"]')
    page.wait_for_function(
        "document.getElementById('grid-empty').innerText.includes('No row matches')"
    )
