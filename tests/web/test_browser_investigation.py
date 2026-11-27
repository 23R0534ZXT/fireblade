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
    page.locator('.tb[data-act="disk-open"]').click()
    page.click("#disk-browse")
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
