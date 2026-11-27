"""Analyst workflows exercised through the Host's visible controls."""

from _browser import browser_page
from conftest import make_case
from docx import Document


def test_value_checklist_keeps_choices_across_pages_and_search(server):
    name = "Paged column values"
    evidence = "Reference,Host\n" + "".join(f"REF-{n:03},WK-101\n" for n in range(125))
    make_case(server, name, evidence)
    with browser_page(server[0], name) as page:
        open_values = page.get_by_role("button", name="Values in Reference")
        open_values.click()
        choices = page.locator("#column-values-list")
        choices.get_by_text("REF-003", exact=True).click()
        page.click("#column-values-more")
        choices.get_by_text("REF-121", exact=True).click()
        page.click("#column-values-prev")
        assert (
            choices.get_by_text("REF-003", exact=True)
            .locator("..")
            .get_by_role("checkbox")
            .is_checked()
        )
        page.fill("#column-values-search", "REF-121")
        only = choices.get_by_text("REF-121", exact=True)
        only.wait_for()
        assert choices.get_by_role("checkbox").count() == 1
        assert only.locator("..").get_by_role("checkbox").is_checked()
        page.click("#column-values-apply")
        page.wait_for_function("document.querySelectorAll('#body tr[data-row]').length === 2")
        assert set(page.locator("#body td[data-cell='0']").all_text_contents()) == {
            "REF-003",
            "REF-121",
        }
        open_values.click()
        page.click("#column-values-hide")
        open_values.wait_for(state="hidden")
        page.get_by_role("button", name="Values in Host").wait_for()


def test_tagged_connection_can_be_filtered_reopened_and_reported(page):
    description = "Synthetic outbound DNS request"
    page.locator("#grid tr[data-row] td[data-cell]").first.click(button="right")
    page.click('#row-menu [data-act="track-row"]')
    page.fill("#track-time", "2026-11-25T12:04:13Z")
    page.fill("#track-machine", "WK-104")
    page.fill("#track-tags", "DNS, Workstation")
    page.fill("#track-description", description)
    page.select_option("#track-level", "high")
    page.select_option("#track-confidence", "confirmed")
    page.select_option("#track-verdict", "confirmed")
    page.select_option("#track-kind", "connection")
    page.select_option("#track-direction", "outbound")
    page.fill("#track-source-ip", "192.0.2.41")
    page.fill("#track-destination-ip", "192.0.2.53")
    page.fill("#track-comment", "Observed in the synthetic workstation log.")
    page.get_by_role("button", name="Save observation").click()
    page.locator("#tracking-modal").wait_for(state="hidden")
    page.locator("#grid tr[data-row]").nth(1).locator("td[data-cell]").first.click(button="right")
    page.click('#row-menu [data-act="track-row"]')
    page.fill("#track-time", "2026-11-25T12:19:13Z")
    page.fill("#track-machine", "WK-104")
    page.select_option("#track-kind", "file_creation")
    page.fill("#track-file", "C:/Lab/dns.log")
    page.fill("#track-description", "Synthetic file creation")
    page.get_by_role("button", name="Save observation").click()
    page.locator("#tracking-modal").wait_for(state="hidden")
    page.click("#tab-graph")
    page.select_option("#graph-tag-filter", label="DNS")
    nodes = page.locator("#graph-nodes")
    assert nodes.get_by_text("Workstation", exact=True).count() == 0
    nodes.get_by_text("DNS", exact=True).click()
    page.locator("#graph-evidence").get_by_role("button", name="Open observation").click()
    editor = page.get_by_role("dialog", name="Tag observation")
    editor.wait_for()
    assert editor.locator("#track-source-ip").input_value() == "192.0.2.41"
    assert editor.locator("#track-destination-ip").input_value() == "192.0.2.53"
    assert editor.locator("#track-direction").input_value() == "outbound"
    editor.get_by_role("button", name="Cancel", exact=True).click()
    page.select_option("#graph-tag-filter", label="All saved tags")
    nodes.get_by_text("Workstation", exact=True).wait_for()
    page.click("#tab-actions")
    page.click('[data-sub="tracking"]')
    related_file = page.locator("#tracking-network").get_by_role("button", name="C:/Lab/dns.log")
    related_file.wait_for()
    page.fill("#tracking-minutes", "10")
    page.press("#tracking-minutes", "Tab")
    page.locator("#tracking-network").get_by_text("192.0.2.41 → 192.0.2.53 (outbound)").wait_for()
    related_file.wait_for(state="hidden")
    page.select_option("#tracking-tags", "DNS")
    with page.expect_download() as download:
        page.click("#tracking-docx")
    doc = Document(download.value.path())
    content = [p.text for p in doc.paragraphs] + [
        cell.text for table in doc.tables for row in table.rows for cell in row.cells
    ]
    assert any(description in text for text in content)
    observation = page.locator("#tracking-rows").get_by_role("button", name=description)
    observation.click()
    page.select_option("#track-verdict", "false_positive")
    page.get_by_role("button", name="Save observation").click()
    observation.wait_for(state="hidden")
    page.check("#tracking-fp")
    observation.click()
    assert page.locator("#track-verdict").input_value() == "false_positive"
    page.once("dialog", lambda dialog: dialog.accept())
    page.click("#tracking-delete")
    observation.wait_for(state="hidden")


def test_disk_explorer_paginates_and_resets_to_root_when_switching_image(empty_page, server):
    from hashlib import sha256
    from pathlib import Path

    from tests.core.test_disk import fat_image, two_partition_image

    folder = server[2]
    volume = fat_image(folder / "volume.img").read_bytes()
    fat = bytearray(volume)
    # The fixture's FAT12 root directory has 224 slots. Slot zero contains VAR.
    for n in range(205):
        start = 19 * 512 + (n + 1) * 32
        fat[start : start + 11] = f"FILE{n:04d}TXT".encode("ascii")
        fat[start + 11] = 0x20
    image = two_partition_image(folder / "two-volumes.raw", (volume, fat))
    original = sha256(image.read_bytes()).digest()
    other = Path(__file__).resolve().parents[1] / "data/ewf/synthetic-fat.E01"
    page = empty_page
    page.locator("#grid-empty").get_by_role("button", name="Import evidence…").click()
    page.click('#import-source-modal [data-act="disk-open"]')
    page.click("#disk-browse")
    for source in (other, image):
        page.fill("#image-source", str(source))
        page.click("#image-open")
        page.get_by_role("button", name="VAR/", exact=True).wait_for()
    page.select_option("#image-partition", "2")
    page.click("#image-next")
    entries = page.locator("#image-entries")
    entries.get_by_text("FILE0204.TXT", exact=True).wait_for()
    assert entries.locator("tr").count() == 6
    page.click("#image-prev")
    entries.get_by_text("FILE0000.TXT", exact=True).wait_for()
    assert entries.locator("tr").count() == 200
    page.get_by_role("button", name="VAR/", exact=True).click()
    page.get_by_role("button", name="LOG/", exact=True).wait_for()
    page.click("#image-up")
    entries.get_by_text("FILE0000.TXT", exact=True).wait_for()
    page.select_option("#image-list", label=other.name)
    page.get_by_role("button", name="VAR/", exact=True).wait_for()
    assert entries.locator("tr").count() == 1
    assert not page.locator("#image-next").is_visible()
    assert sha256(image.read_bytes()).digest() == original


def test_case_toolbar_saves_and_exports_the_open_analysis(page):
    import csv

    toolbar = page.get_by_role("group", name="Case tools")
    toolbar.get_by_role("button", name="Save case").click()
    page.locator("#status").get_by_text("recovery point", exact=False).wait_for()
    with page.expect_download() as download:
        toolbar.locator('[data-act="export-csv"]').click()
    with download.value.path().open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    assert len(rows) == 60
    assert rows[0]["User"] == "alice"
    toolbar.get_by_role("button", name="Rules", exact=True).click()
    page.locator("#rules-modal.show").wait_for()
    page.keyboard.press("Escape")
    toolbar.get_by_role("button", name="Plugins", exact=True).click()
    page.locator(".modal.show").get_by_text("Profiles and compatibility", exact=True).wait_for()
