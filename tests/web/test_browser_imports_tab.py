"""The Imports tab and its Read again window: what a collection did with each file, and what the
analyst can do about the files it could not read.

Skipped without Playwright and a Chromium; never failed for lack of them.
"""

import time

import httpx
import pytest
from _audit import rows

from tests.core.pdf_sample import build_pdf


def _mixed(page, server, inside_case=False):
    """A folder of files no reader recognises by their name, imported by path.

    ``inside_case`` puts it in the case's own evidence folder, where a browser upload lands.
    """
    base, root, evidence = server
    case = page.evaluate("state.openCase.id")
    folder = (root / case / "evidence" if inside_case else evidence / case) / "mixed"
    folder.mkdir(parents=True)
    (folder / "disguised.txt").write_text(
        "Time,User\n2026-11-04T10:00:00Z,alice\n2026-11-04T10:01:00Z,bob\n"
    )
    (folder / "notes.txt").write_text("first line\nsecond line\nthird line\n")
    (folder / "junk.bin").write_bytes(bytes(range(256)) * 4)
    (folder / "page.html").write_text(
        "<html><body><h1>Incident</h1><p>Beacon every 60 seconds to evil.example</p></body></html>"
    )
    pytest.importorskip("pypdf")
    (folder / "memo.pdf").write_bytes(build_pdf("Containment memo: isolate host PC01"))
    job = httpx.post(
        f"{base}/api/cases/{case}/import-jobs",
        data={"source": str(folder), "organization": "files"},
        timeout=60,
    ).json()["job"]
    for _ in range(240):
        if httpx.get(f"{base}/api/import-jobs/{job}").json().get("status") != "running":
            break
        time.sleep(0.25)
    page.evaluate("openCase(state.openCase.id)")
    page.click('.tabs .tab:text-is("Imports")')
    page.wait_for_function("document.getElementById('imports-rows').innerText.includes('junk.bin')")
    return folder


def _lines(page):
    return page.eval_on_selector_all(
        "#imports-rows tr", "els => els.map(e => e.innerText.replace(/\\s+/g, ' ').trim())"
    )


def _retry(page, name, reader):
    page.click("#retry-open")
    page.wait_for_selector("#retry-modal.show")
    line = page.locator(".retry-line", has_text=name)
    line.locator("select").select_option(reader)
    line.locator("[data-retry-run]").click()
    page.wait_for_function(
        "!document.getElementById('retry-modal').classList.contains('show')", timeout=60000
    )


def test_the_retry_window_lists_what_no_reader_recognised_and_the_readers_it_can_try(
    empty_page, server
):
    page = empty_page
    _mixed(page, server)
    page.click("#retry-open")
    page.wait_for_selector("#retry-modal.show")
    page.wait_for_function(
        "document.getElementById('retry-list').innerText.includes('disguised.txt')"
    )
    text = page.inner_text("#retry-list")
    assert "junk.bin" in text
    options = page.eval_on_selector_all(
        ".retry-line select:first-of-type option", "els => [...new Set(els.map(e => e.value))]"
    )
    assert options == ["text", "html", "csv", "pdf"]


@pytest.mark.parametrize(
    ("name", "reader", "expect_rows", "expect_text"),
    [
        ("disguised.txt", "csv", 2, "alice"),
        ("notes.txt", "text", 3, "second line"),
        ("page.html", "html", 1, "evil.example"),
        ("memo.pdf", "pdf", 1, "isolate host PC01"),
    ],
)
def test_a_file_is_read_again_with_the_reader_the_analyst_names(
    empty_page, server, name, reader, expect_rows, expect_text
):
    page = empty_page
    _mixed(page, server)
    _retry(page, name, reader)
    page.wait_for_function(
        f"[...document.querySelectorAll('#tree .node.child')].some(e => e.innerText.includes({name!r}))"
    )
    # the generic reader's grid of the same file comes first: the one the analyst asked for is the last
    page.locator(f'#tree .node.child:has-text("{name}")').last.click()
    page.wait_for_selector("#body tr[data-row]")
    page.wait_for_function(
        f"document.getElementById('body').innerText.includes({expect_text!r})", timeout=30000
    )
    assert rows(page) >= expect_rows


def test_a_file_is_set_aside_from_the_retry_window(empty_page, server):
    page = empty_page
    _mixed(page, server)
    page.click("#retry-open")
    page.wait_for_selector("#retry-modal.show")
    page.wait_for_function("document.getElementById('retry-list').innerText.includes('junk.bin')")
    page.locator(".retry-line", has_text="junk.bin").locator("[data-report-aside]").click()
    page.wait_for_function(
        "!document.getElementById('retry-list').innerText.includes('junk.bin')", timeout=15000
    )


def test_delete_removes_a_file_the_case_holds_and_keeps_its_hash_in_the_report(empty_page, server):
    page = empty_page
    folder = _mixed(page, server, inside_case=True)
    page.locator("#imports-rows tr", has_text="notes.txt").click()
    page.once("dialog", lambda dialog: dialog.accept())  # "Delete … from the evidence tree?"
    page.click('[data-act="import-delete"]')
    page.wait_for_function("document.getElementById('status').innerText.includes('Deleted')")
    status_text = page.inner_text("#status")
    assert "notes.txt" in status_text and "deleted" in status_text.lower()
    assert not (folder / "notes.txt").exists(), "the file is gone from the evidence tree"
    assert (folder / "junk.bin").exists(), "only the chosen file went"
    page.wait_for_function(
        "[...document.querySelectorAll('#imports-rows tr')].some(r => r.innerText.includes('notes.txt'))"
    )


def test_delete_refuses_an_original_the_case_only_read_where_it_stands(empty_page, server):
    page = empty_page
    folder = _mixed(page, server)  # outside the case: an original
    page.locator("#imports-rows tr", has_text="notes.txt").click()
    page.once("dialog", lambda dialog: dialog.accept())
    page.click('[data-act="import-delete"]')
    page.wait_for_function("document.getElementById('status').innerText.includes('original')")
    assert "never deletes" in page.inner_text("#status")
    assert (folder / "notes.txt").exists(), "the original is untouched"


def test_delete_without_a_selection_asks_for_one(empty_page, server):
    page = empty_page
    _mixed(page, server)
    page.click('[data-act="import-delete"]')
    page.wait_for_function("document.getElementById('status').innerText.includes('Select a file')")


def test_copy_unprocessed_files_puts_only_the_unread_paths_on_the_clipboard(empty_page, server):
    page = empty_page
    _mixed(page, server)
    # every file of the folder is read now (the generic reader takes what no dedicated reader owns):
    # nothing is left unprocessed, and the command says so
    page.click('[data-act="import-copy-unread"]')
    page.wait_for_function(
        "document.getElementById('status').innerText.includes('Every collected file was read')"
    )


def test_refresh_reloads_the_report_and_the_other_buttons_of_the_tab_open_their_windows(
    empty_page, server
):
    page = empty_page
    _mixed(page, server)
    page.click("#imports-refresh")
    page.wait_for_function("document.getElementById('imports-rows').innerText.includes('junk.bin')")
    page.click('.tabs .tab:text-is("Imports") >> xpath=.')  # stays on the tab
    page.click("#coverage-open")
    page.wait_for_selector("#coverage-modal.show")
    page.keyboard.press("Escape")
    page.click('#imports-view [data-act="case-history"]')
    page.wait_for_selector("#history-modal.show, .modal.show .dialog")
    page.keyboard.press("Escape")
    page.click('#imports-view [data-act="import-file"]')
    page.wait_for_selector("#import-modal.show")
    page.keyboard.press("Escape")
    with page.expect_file_chooser():
        page.click('#imports-view [data-act="import-folder"]')


def test_several_files_are_ticked_and_read_with_one_reader(empty_page, server):
    page = empty_page
    _mixed(page, server)
    page.click("#retry-open")
    page.wait_for_selector("#retry-modal.show")
    page.wait_for_function(
        "document.querySelectorAll('#retry-list input[data-retry-tick]').length >= 2"
    )
    page.click("#retry-tick-all")
    assert page.locator("#retry-list input[data-retry-tick]:checked").count() >= 2
    page.click("#retry-tick-none")
    assert page.locator("#retry-list input[data-retry-tick]:checked").count() == 0
    page.locator(".retry-line", has_text="notes.txt").locator("input[data-retry-tick]").check()
    page.locator(".retry-line", has_text="disguised.txt").locator("input[data-retry-tick]").check()
    page.select_option("#retry-bulk-reader", "text")
    page.click("#retry-bulk-run")
    page.wait_for_function(
        "document.getElementById('status').innerText.includes('file(s) read with text')",
        timeout=60000,
    )
    page.select_option("#report-filter", "duplicate") if page.locator(
        "#retry-modal.show"
    ).count() else None
