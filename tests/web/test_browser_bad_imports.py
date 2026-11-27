"""Malformed evidence must be refused with a useful result, never called imported."""


def test_empty_file_is_refused_before_import(empty_page, tmp_path):
    page = empty_page
    source = tmp_path / "invalid.csv"
    source.write_bytes(b"")
    page.click('.toolbar [data-act="import-file"]')
    page.set_input_files("#preview-input", str(source))
    page.wait_for_selector("#preview-body .preview-bad")
    assert page.locator("#preview-import").is_disabled()
    assert page.evaluate("state.openCase.analyses.length") == 0


def test_a_late_csv_parse_failure_is_not_reported_as_import_success(empty_page, tmp_path):
    page = empty_page
    source = tmp_path / "late-broken.csv"
    source.write_bytes(
        b"Time,User\n" + b"2026-11-01T12:00:00Z,alice\n" * 100000 + b"2026-11-01T12:00:00Z,\xff\n"
    )
    page.click('.toolbar [data-act="import-file"]')
    page.set_input_files("#preview-input", str(source))
    page.wait_for_selector("#preview-body .preview-card")
    page.click("#preview-import")
    try:
        page.wait_for_function(
            "document.getElementById('status').innerText.startsWith('Import failed')", timeout=10000
        )
    except Exception as exc:
        raise AssertionError(
            page.inner_text("#status") + " | " + str(page.evaluate("state.openCase.analyses"))
        ) from exc
    assert page.evaluate("state.openCase.analyses.length") == 0
    assert "file(s) imported" not in page.inner_text("#status")


def test_truncated_final_quote_does_not_silently_drop_the_last_row(empty_page, tmp_path):
    page = empty_page
    source = tmp_path / "truncated.csv"
    source.write_text(
        "Time,User\n"
        + "2026-11-01T12:00:00Z,alice\n" * 100000
        + '2026-11-01T12:00:00Z,"unfinished\n'
    )
    page.click('.toolbar [data-act="import-file"]')
    page.set_input_files("#preview-input", str(source))
    page.wait_for_selector("#preview-body .preview-card")
    page.click("#preview-import")
    page.wait_for_function(
        "document.getElementById('status').innerText.startsWith('Import failed')", timeout=10000
    )
    assert page.evaluate("state.openCase.analyses.length") == 0


def test_a_partly_read_folder_counts_only_read_files_and_reports_failure(empty_page, server):
    page = empty_page
    folder = server[2] / "mixed-failure"
    folder.mkdir()
    (folder / "good.csv").write_text("Time,User\n2026-11-01T12:00:00Z,bob\n")
    (folder / "broken.csv").write_bytes(b"Time,User\n2026-11-01T12:00:00Z,\xff\n")
    page.click('.toolbar [data-act="import-file"]')
    page.fill("#preview-server", str(folder))
    page.click('[data-act="preview-path"]')
    page.wait_for_selector("#preview-body .preview-card")
    page.click("#preview-import")
    page.wait_for_function(
        "document.getElementById('status').innerText.startsWith('Import finished with errors')",
        timeout=15000,
    )
    assert "1 file(s) imported" in page.inner_text("#status")
    assert page.evaluate("state.openCase.analyses.length") == 1
    page.click('[data-tab="imports"]')
    page.wait_for_function(
        "document.getElementById('imports-summary').innerText.includes('1 file(s) read, 1 not read')"
    )
    good = page.locator("#imports-rows tr[data-import]", has_text="good.csv")
    assert good.locator("td").nth(4).inner_text().strip(), "The produced analysis must be listed"
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.click('[data-act="import-copy-unread"]')
    page.wait_for_function(
        "document.getElementById('status').innerText.includes('1 unprocessed path')"
    )
    copied = page.evaluate("navigator.clipboard.readText()")
    assert "broken.csv" in copied and "good.csv" not in copied
