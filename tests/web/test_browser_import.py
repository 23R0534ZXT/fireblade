"""Every way into a case, pressed in a real browser: the file chooser, a path on the server, the
CSV options, the sheets of a workbook, a folder sent from the browser, and a Stop.

Skipped without Playwright and a Chromium; never failed for lack of them.
"""

import re
from pathlib import Path

import pytest
from _audit import pick_import_source, rows, status

# the hidden controls of the toolbar open the browser's own chooser; a test hands it files


def _open_import(page):
    pick_import_source(page, "import-file")
    page.wait_for_selector("#import-modal.show")


def _case_folder(page, server):
    base, _root, evidence = server
    folder = evidence / page.evaluate("state.openCase.id")
    folder.mkdir(exist_ok=True)
    return folder


def _preview_card(page):
    page.wait_for_selector("#preview-body .preview-card")
    return page.inner_text("#preview-body")


def test_a_path_on_the_server_is_previewed_then_imported(empty_page, server):
    page = empty_page
    source = _case_folder(page, server) / "served.csv"
    source.write_text("Time,Host\n2026-11-01T10:00:00Z,PC01\n2026-11-01T10:01:00Z,PC02\n")
    _open_import(page)
    page.fill("#preview-server", str(source))
    page.click('[data-act="preview-path"]')
    text = _preview_card(page)
    assert "served.csv" in text and "Time" in text and "Host" in text
    assert "Nothing has been read" in page.inner_text("#preview-note")
    page.click("#preview-import")
    page.wait_for_selector("#body tr[data-row]", timeout=30000)
    assert rows(page) == 2


def test_a_path_that_is_not_there_is_refused_with_a_reason(empty_page):
    page = empty_page
    _open_import(page)
    page.click('[data-act="preview-path"]')  # nothing typed
    assert "Give a path" in page.inner_text("#preview-note")
    page.fill("#preview-server", "/no/such/place/evidence.csv")
    page.click('[data-act="preview-path"]')
    page.wait_for_function("document.getElementById('preview-note').classList.contains('err')")
    assert page.inner_text("#preview-note").strip(), "the refusal says why"
    assert page.locator("#preview-import").is_disabled()


def test_choose_a_file_opens_the_browsers_chooser_and_previews_what_it_hands_over(
    empty_page, tmp_path
):
    page = empty_page
    sample = tmp_path / "picked.csv"
    sample.write_text("Time,User\n2026-11-02T08:00:00Z,alice\n")
    _open_import(page)
    with page.expect_file_chooser() as chooser:
        page.click('[data-act="preview-choose"]')
    assert chooser.value.is_multiple(), "several files can be chosen at once"
    chooser.value.set_files(str(sample))
    assert "picked.csv" in _preview_card(page)


def test_dismissing_a_file_preview_stops_the_batch_and_keeps_the_next_dialog_clean(
    empty_page, tmp_path
):
    page = empty_page
    files = [tmp_path / name for name in ("first.csv", "second.csv")]
    for path in files:
        path.write_text("Time,Host\n2026-11-02T08:00:00Z,PC01\n")
    held = []
    page.route("**/preview-upload", lambda route: held.append(route))
    page.evaluate(
        """() => {
            const original = previewFiles;
            previewFiles = async files => {
                try { await original(files); } finally { window.previewFinished = true; }
            };
        }"""
    )
    _open_import(page)
    with page.expect_request("**/preview-upload"):
        page.set_input_files("#preview-input", files)
    page.keyboard.press("Escape")
    _open_import(page)
    held[0].fulfill(status=200, json={"kind": "table", "name": "first.csv", "path": "first.csv"})
    page.wait_for_function("window.previewFinished === true")
    assert len(held) == 1
    assert page.locator("#preview-body .preview-card").count() == 0
    assert page.locator("#preview-import").is_disabled()


def test_the_delimiter_and_the_encoding_decide_how_a_file_is_read(empty_page, tmp_path):
    page = empty_page
    sample = tmp_path / "accents.csv"
    sample.write_bytes("Nom;Ville\nRené;Genève\n".encode("latin-1"))
    _open_import(page)
    page.set_input_files("#preview-input", str(sample))
    first = _preview_card(page)
    # An unmarked file is read as UTF-8, never guessed at: the preview says what will happen.
    assert "Ren�" in first and "not valid UTF-8" in first, first
    page.select_option("#preview-encoding", "cp1252")
    page.wait_for_function("document.getElementById('preview-body').innerText.includes('René')")
    assert "not valid UTF-8" not in page.inner_text("#preview-body")
    # a comma where the file has semicolons: one column that holds the whole header
    page.select_option("#preview-delimiter", ",")
    page.wait_for_function(
        "document.getElementById('preview-body').innerText.includes('Nom;Ville')"
    )
    page.select_option("#preview-delimiter", ";")
    page.wait_for_function(
        "!document.getElementById('preview-body').innerText.includes('Nom;Ville')"
    )
    # the encoding it was told stays: the accents come back when it is the right one
    page.select_option("#preview-encoding", "latin-1")
    page.wait_for_function("document.getElementById('preview-body').innerText.includes('Genève')")


def test_a_workbook_offers_its_sheets_and_imports_the_one_chosen(empty_page, tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.Workbook()
    first = workbook.active
    first.title = "Summary"
    first.append(["Quarter", "Total"])
    first.append(["Q1", 10])
    second = workbook.create_sheet("Logins")
    second.append(["Time", "User"])
    second.append(["2026-11-03T09:00:00Z", "alice"])
    second.append(["2026-11-03T09:05:00Z", "bob"])
    path = tmp_path / "book.xlsx"
    workbook.save(path)
    page = empty_page
    _open_import(page)
    page.set_input_files("#preview-input", str(path))
    page.wait_for_function("document.getElementById('preview-sheet-row').style.display !== 'none'")
    options = page.eval_on_selector_all("#preview-sheet option", "els => els.map(e => e.value)")
    assert options == ["Summary", "Logins"]
    page.select_option("#preview-sheet", "Logins")
    page.click("#preview-import")
    page.wait_for_selector("#body tr[data-row]", timeout=30000)
    assert rows(page) == 2
    assert "Logins" in page.inner_text("#pane-tabs, #tree")


def test_a_folder_sent_from_the_browser_is_rebuilt_in_the_case_and_imported(empty_page, tmp_path):
    folder = tmp_path / "evidence-folder"
    (folder / "logs").mkdir(parents=True)
    (folder / "a.csv").write_text("Time,Host\n2026-11-01T10:00:00Z,PC01\n")
    (folder / "logs" / "b.csv").write_text("Time,Host\n2026-11-01T10:01:00Z,PC02\n")
    page = empty_page
    pick_import_source(page, "import-folder")
    page.set_input_files("#folder-input", str(folder))
    page.wait_for_function(
        "document.getElementById('preview-note').innerText.includes('file(s) ready')", timeout=30000
    )
    assert "2 file(s)" in page.inner_text("#preview-note")
    first = page.evaluate("previewState.items[0].payload.path")
    page.click("#preview-import")
    page.wait_for_function(
        "document.getElementById('status').innerText.includes('imported')", timeout=60000
    )
    page.wait_for_function("document.querySelectorAll('#tree .node.child').length === 2")
    labels = page.eval_on_selector_all(
        "#tree .node.child", "els => els.map(e => e.innerText.trim())"
    )
    assert sorted(labels) == ["a.csv", "b.csv"]

    # Another acquisition can carry the same directory and file names.
    # Both staged sources must stay available with their respective contents.
    original = (folder / "a.csv").read_bytes()
    replacement = b"Time,Host\n2026-11-02T12:00:00Z,PC03\n"
    (folder / "a.csv").write_bytes(replacement)
    pick_import_source(page, "import-folder")
    page.set_input_files("#folder-input", str(folder))
    page.wait_for_function("document.querySelector('#preview-note').textContent.includes('ready')")
    second = page.evaluate("previewState.items[0].payload.path")
    assert first != second
    assert (Path(first) / "a.csv").read_bytes() == original
    assert (Path(second) / "a.csv").read_bytes() == replacement
    assert (Path(second) / "logs" / "b.csv").read_bytes() == (
        folder / "logs" / "b.csv"
    ).read_bytes()


def test_stopping_an_import_ends_it_and_keeps_what_was_written(empty_page, server):
    page = empty_page
    folder = _case_folder(page, server) / "many"
    folder.mkdir()
    for number in range(400):
        (folder / f"f{number:03d}.csv").write_text(
            "Time,Host\n" + "".join(f"2026-11-01T10:{n:02d}:00Z,PC{n}\n" for n in range(40))
        )
    _open_import(page)
    page.fill("#preview-server", str(folder))
    page.click('[data-act="preview-path"]')
    _preview_card(page)
    page.click("#preview-import")
    page.wait_for_selector("#import-progress-modal.show")
    page.click("#import-progress-stop")
    page.wait_for_function(
        "!document.getElementById('import-progress-modal').classList.contains('show')",
        timeout=120000,
    )
    page.wait_for_function(
        "document.getElementById('status').innerText.startsWith('Import stopped — ')",
        timeout=60000,
    )
    message = status(page)
    # said as what it is: a stop, with what stays in the case — never "N file(s) imported"
    assert message.startswith("Import stopped — "), message
    assert re.search(
        r"nothing had been written yet|analysis\(es\) written before the stop kept", message
    ), message
    if "nothing had been written yet" in message:
        return
    # the case still opens and lists whatever was written before the stop
    page.click('.tabs .tab:text-is("Imports")')
    page.wait_for_function("document.getElementById('imports-rows').innerText.length > 0")


def test_sqlite_databases_import_with_a_read_only_reader_installation(empty_page, server):
    import sqlite3

    page = empty_page
    folder = _case_folder(page, server) / "databases"
    folder.mkdir()
    for name, count in [("first.sqlite", 3), ("second.sqlite", 5)]:
        with sqlite3.connect(folder / name) as connection:
            connection.execute("CREATE TABLE evidence (Id INTEGER, Marker TEXT)")
            connection.executemany(
                "INSERT INTO evidence VALUES (?, ?)",
                [(index, "synthetic-browser-record") for index in range(count)],
            )
    _open_import(page)
    page.fill("#preview-server", str(folder))
    page.click('[data-act="preview-path"]')
    _preview_card(page)
    page.click("#preview-import")
    page.wait_for_function(
        "document.getElementById('status').innerText.includes('file(s) imported')", timeout=30000
    )
    assert page.evaluate("state.openCase.analyses.length") == 2
    observed = []
    for index in range(2):
        with page.expect_response(lambda response: "/rows?" in response.url) as loaded:
            page.locator("#tree .node.child:not(.closed)").nth(index).click()
        expected = loaded.value.json()["total"]
        page.wait_for_function(
            "count => document.getElementById('pageinfo').innerText.includes('/ ' + count + ' row')",
            arg=expected,
        )
        observed.append(rows(page))
    assert sorted(observed) == [3, 5]


def test_committed_sqlite_wal_records_survive_generic_fallback_in_the_gui(
    empty_page, server, tmp_path
):
    import shutil
    import sqlite3

    folder = _case_folder(empty_page, server) / "wal-collection"
    folder.mkdir()
    live = tmp_path / "live.sqlite"
    connection = sqlite3.connect(live)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("CREATE TABLE evidence (Id INTEGER, Marker TEXT)")
        connection.commit()
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        connection.execute("INSERT INTO evidence VALUES (1, 'committed-only-in-wal')")
        connection.commit()
        source = folder / "collected.sqlite"
        shutil.copyfile(live, source)
        wal = source.with_name(source.name + "-wal")
        shutil.copyfile(live.with_name(live.name + "-wal"), wal)
    finally:
        connection.close()
    before = {path: path.read_bytes() for path in [source, wal]}
    page = empty_page
    _open_import(page)
    page.fill("#preview-server", str(folder))
    page.click('[data-act="preview-path"]')
    _preview_card(page)
    page.click("#preview-import")
    page.wait_for_function(
        "document.getElementById('status').innerText.includes('file(s) imported')", timeout=30000
    )
    page.locator("#tree .node.child", has_text="collected.sqlite").click()
    page.wait_for_function(
        "document.getElementById('body').innerText.includes('committed-only-in-wal')"
    )
    assert rows(page) == 1
    assert all(path.read_bytes() == data for path, data in before.items())
    assert not source.with_name(source.name + "-shm").exists()


def test_import_thread_choices_are_sent_for_folder_and_disk(empty_page, server):
    page = empty_page
    folder = _case_folder(page, server) / "thread-test"
    folder.mkdir()
    (folder / "event.csv").write_text("Time,Host\n2026-11-01T10:00:00Z,PC01\n")
    page.route(
        "**/api/import-capacity",
        lambda route: route.fulfill(
            json={"max_threads": 4, "recommended_threads": 2, "cpu_threads": 8, "memory_mb": 8192}
        ),
    )
    page.click('.toolbar [data-act="import-evidence"]')
    page.click('#import-source-modal [data-act="import-file"]')
    assert page.locator("#import-capacity").is_hidden()
    page.locator('#import-modal [data-act="settings-close"]').click()
    pick_import_source(page, "import-folder")
    assert page.get_by_role("button", name="Choose a folder…").is_visible()
    slider = page.get_by_role("slider", name="Import threads")
    page.wait_for_function("document.querySelector('#import-threads').value === '2'")
    assert "2 of 4" in page.locator("#import-thread-count").inner_text()
    slider.press("Home")
    assert "1 of 4" in page.locator("#import-thread-count").inner_text()
    page.fill("#preview-server", str(folder))
    page.click('[data-act="preview-path"]')
    with page.expect_request(lambda request: request.url.endswith("/import-jobs")) as started:
        page.click("#preview-import")
    assert 'name="parsing_threads"\r\n\r\n1\r\n' in started.value.post_data
    page.wait_for_selector("#body tr[data-row]")

    page.route(
        "**/disk-jobs",
        lambda route: route.fulfill(status=400, json={"detail": "Synthetic disk response"}),
    )
    page.click('.toolbar [data-act="import-evidence"]')
    page.click('#import-source-modal [data-act="disk-open"]')
    page.fill("#disk-source", str(folder))
    page.wait_for_function("document.querySelector('#disk-threads').value === '2'")
    page.get_by_role("slider", name="Import threads").press("End")
    assert "4 of 4" in page.locator("#disk-thread-count").inner_text()
    with page.expect_request(lambda request: request.url.endswith("/disk-jobs")) as started:
        page.click("#disk-start")
    assert started.value.post_data_json == {
        "source": str(folder),
        "kind": "mounted",
        "parsing_threads": 4,
    }


def test_folder_and_disk_show_space_estimates_before_parsing(empty_page, tmp_path):
    page = empty_page
    folder = tmp_path / "space-check"
    folder.mkdir()
    source = folder / "event.csv"
    source.write_text("Time,Host\n2026-11-01T10:00:00Z,PC01\n")
    requests = []
    gib = 1024**3

    def estimate(route):
        fields = route.request.post_data_json
        requests.append(fields)
        route.fulfill(
            json={
                "free": 8 * gib,
                "recommended": (9 * gib if fields.get("kind") == "image" else 3 * gib)
                if "source" in fields or "size" in fields
                else None,
                "basis": "image-logical" if fields.get("kind") == "image" else "upload",
                "status": "tight" if fields.get("kind") == "image" else "ok",
            }
        )

    def observe_upload(route):
        assert requests[-1] == {"kind": "folder", "size": source.stat().st_size, "files": 1}
        route.continue_()

    page.route("**/import-space", estimate)
    page.route("**/upload-folder", observe_upload)
    pick_import_source(page, "import-folder")
    page.wait_for_function("document.querySelector('#import-space').textContent.includes('8 GiB')")
    page.set_input_files("#folder-input", str(folder))
    page.wait_for_function("document.querySelector('#preview-note').textContent.includes('ready')")
    assert {"kind": "folder", "size": source.stat().st_size, "files": 1} in requests
    page.locator('#import-modal [data-act="settings-close"]').click()

    pick_import_source(page, "disk-open")
    page.wait_for_function("document.querySelector('#disk-space').textContent.includes('8 GiB')")
    page.fill("#disk-source", "/images/evidence.E01")
    page.select_option("#disk-kind", "image")
    page.wait_for_function("document.querySelector('#disk-space').textContent.includes('9 GiB')")
    assert "Based on the full logical image size" in page.locator("#disk-space").inner_text()
    assert "Below the recommendation" in page.locator("#disk-space").inner_text()
    assert requests[-1] == {"kind": "image", "source": "/images/evidence.E01"}
