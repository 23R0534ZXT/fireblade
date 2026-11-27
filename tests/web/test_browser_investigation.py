"""The new investigation commands are reachable through the regular Host UI."""

import pytest


def test_tag_a_grid_row_and_download_the_follow_up(page):
    page.locator("#grid tr[data-row] td[data-cell]").first.click(button="right")
    page.locator('#row-menu [data-act="track-row"]').click()
    page.wait_for_function(
        "document.querySelector('#tracking-modal.show') || document.querySelector('#status.err')"
    )
    assert page.locator("#tracking-modal.show").count(), page.locator("#status").inner_text()
    page.fill("#track-tags", "Initial access")
    page.fill("#track-description", "A synthetic observation")
    page.locator('#tracking-form button[type="submit"]').click()
    page.locator("#tracking-modal.show").wait_for(state="hidden")
    page.click('[data-tab="actions"]')
    page.click('[data-sub="tracking"]')
    page.get_by_role("button", name="A synthetic observation").wait_for()
    page.select_option("#tracking-tags", "Initial access")
    with page.expect_download() as download:
        page.click("#tracking-xlsx")
    assert download.value.suggested_filename.endswith(".xlsx")


@pytest.mark.parametrize(
    ("image_name", "directories", "filename", "preview", "digest"),
    [
        (
            "synthetic-fat.E01",
            ["VAR/", "LOG/"],
            "AUTH.LOG",
            "Accepted publickey",
            "b331160b2d3288f57ef1b1bf94774745523631fa61328db4d64339e1f4db03c0",
        ),
        (
            "synthetic-ntfs.E01",
            ["$Extend/"],
            "$UsnJrnl:$J",
            "60 00 00 00",
            "43dfb03180d6d6e00c2c8f36279d09e34c6e424fe138ca2488ff6b753f5f44e6",
        ),
    ],
    ids=["fat-log", "ntfs-journal-stream"],
)
def test_explore_preview_and_collect_an_e01_file(
    empty_page, server, image_name, directories, filename, preview, digest
):
    import hashlib
    import shutil
    from pathlib import Path

    page = empty_page
    image = server[2] / image_name
    shutil.copyfile(Path(__file__).resolve().parents[1] / "data/ewf" / image_name, image)
    original = hashlib.sha256(image.read_bytes()).digest()
    page.locator("#grid-empty").get_by_role("button", name="Import evidence…").click()
    page.click('#import-source-modal [data-act="disk-open"]')
    page.click("#disk-browse")
    page.fill("#image-source", str(image))
    page.click("#image-open")
    for directory in directories:
        page.get_by_role("button", name=directory, exact=True).click()
    row = page.get_by_role("row").filter(has=page.get_by_role("cell", name=filename, exact=True))
    row.get_by_role("button", name="Preview").click()
    page.locator("#image-preview").get_by_text(preview, exact=False).wait_for()
    assert filename in page.locator("#image-preview-title").inner_text()
    if filename == "$UsnJrnl:$J":
        lines = page.locator("#image-preview").inner_text().splitlines()
        assert [line[:8] for line in lines] == [f"{offset:08x}" for offset in range(0, 96, 16)]
        assert lines[5].endswith("f.i.l.e...t.x.t.")
    row.get_by_role("button", name="Collect").click()
    page.get_by_text(f"Collected {filename} · SHA-256 {digest}", exact=False).wait_for()
    with page.expect_download() as download:
        page.get_by_role("link", name="Download case copy").click()
    assert hashlib.sha256(download.value.path().read_bytes()).hexdigest() == digest
    assert hashlib.sha256(image.read_bytes()).digest() == original


def test_new_analyst_can_save_and_export_incident_intake(empty_page):
    from docx import Document

    page = empty_page
    page.click('[data-tab="actions"]')
    page.click('[data-sub="tracking"]')
    page.click("#incident-open")
    page.get_by_label("What happened?").fill("Test case intake from the browser.")
    page.get_by_label("Discovery time (ISO date/time)").fill("2026-11-27T13:00:00Z")
    with page.expect_download() as download:
        page.get_by_role("button", name="Save and download Word").click()
    document = Document(download.value.path())
    assert any(
        cell.text == "Test case intake from the browser."
        for table in document.tables
        for row in table.rows
        for cell in row.cells
    )
    page.click("#incident-open")
    assert page.get_by_label("What happened?").input_value() == "Test case intake from the browser."


def test_process_links_open_source_records(server):
    from _browser import browser_page
    from conftest import make_case

    name = "Source-backed scenario in Chromium"
    make_case(
        server,
        name,
        "Timestamp,Host,Provider,EventID,ProcessGuid,Image,DestinationIp\n"
        "2026-11-27T13:00:00Z,PC1,Microsoft-Windows-Sysmon,1,{abc},program.exe,\n"
        "2026-11-27T13:00:01Z,PC1,Microsoft-Windows-Sysmon,3,{abc},program.exe,192.0.2.4\n",
    )
    with browser_page(server[0], name, width=1100, height=720) as page:
        page.click('[data-tab="actions"]')
        page.click('[data-sub="tracking"]')
        page.get_by_text("Correlate process, network and file records").click()
        page.get_by_role("button", name="Network connection", exact=False).click()
        page.locator("#scenario-edges .gline").get_by_text("192.0.2.4", exact=True).wait_for()
        page.select_option("#import-layout", "combined")
        page.wait_for_function(
            "document.getElementById('status').innerText.match(/Layout changed|Already laid out/)",
            timeout=60000,
        )
        page.click('[data-tab="actions"]')
        page.click('[data-sub="tracking"]')
        assert page.locator("#scenario-panel").get_attribute("open") is None
        assert page.locator("#scenario-edges").inner_text() == ""
        page.get_by_text("Correlate process, network and file records").click()
        page.get_by_role("button", name="Network connection", exact=False).click()
        page.locator("#scenario-edges .gline").get_by_text("192.0.2.4", exact=True).wait_for()


def test_rewrite_suggestion_is_reviewed_before_replacing_the_description(page):
    def model(route):
        if route.request.method == "GET":
            route.fulfill(json={"enabled": True})
        else:
            assert route.request.post_data_json == {"description": "The analyst's original note"}
            route.fulfill(json={"description": "The revised note"})

    page.route("**/tracking/rewrite", model)
    page.locator("#grid tr[data-row] td[data-cell]").first.click(button="right")
    page.locator('#row-menu [data-act="track-row"]').click()
    original = page.locator("#track-description")
    original.fill("The analyst's original note")
    page.click("#track-rewrite")
    suggestion = page.get_by_role("textbox", name="Suggested description")
    suggestion.wait_for()
    assert not suggestion.is_editable()
    suggestion.click()
    suggestion.press("Control+a")
    suggestion.press("Control+c")
    assert page.evaluate("navigator.clipboard.readText()") == "The revised note"
    assert original.input_value() == "The analyst's original note"
    page.click("#track-use-suggestion")
    assert original.input_value() == "The revised note"
    page.get_by_role("button", name="Save observation").click()
    page.locator("#tracking-modal").wait_for(state="hidden")
    page.get_by_role("tab", name="Attack graph").click()
    page.get_by_role("button", name="Tagged connections").click()
    page.locator("#tracking-rows").get_by_role("button", name="The revised note").click()
    assert original.input_value() == "The revised note"
