"""The new investigation commands are reachable through the regular Host UI."""


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


def test_explore_preview_and_collect_an_e01_file(empty_page, server):
    import hashlib
    import shutil
    from pathlib import Path

    page = empty_page
    image = server[2] / "synthetic-fat.E01"
    shutil.copyfile(Path(__file__).resolve().parents[1] / "data/ewf/synthetic-fat.E01", image)
    original = hashlib.sha256(image.read_bytes()).digest()
    page.locator("#grid-empty").get_by_role("button", name="Explore disk image…").click()
    page.fill("#image-source", str(image))
    page.click("#image-open")
    page.get_by_role("button", name="VAR/", exact=True).click()
    page.get_by_role("button", name="LOG/", exact=True).click()
    page.get_by_role("button", name="Preview", exact=True).click()
    page.locator("#image-preview").get_by_text("Accepted publickey", exact=False).wait_for()
    page.get_by_role("button", name="Collect", exact=True).click()
    page.get_by_text("Collected AUTH.LOG", exact=False).wait_for()
    with page.expect_download() as download:
        page.get_by_role("link", name="Download case copy").click()
    assert download.value.suggested_filename == "AUTH.LOG"
    assert hashlib.sha256(image.read_bytes()).digest() == original
    [copied] = list(server[1].glob("*/Disks/explorer/*/evidence.bin"))
    assert b"Accepted publickey" in copied.read_bytes()


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
    page.locator("#track-suggestion").wait_for()
    assert original.input_value() == "The analyst's original note"
    assert page.locator("#track-suggestion").input_value() == "The revised note"
    page.click("#track-use-suggestion")
    assert original.input_value() == "The revised note"
