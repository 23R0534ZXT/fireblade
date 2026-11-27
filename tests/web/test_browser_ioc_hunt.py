"""The IOC hunt, as the desktop's panel runs it: the core's hunt, its counters, its pages, its export."""

import pytest
from _audit import command  # noqa: F401 - the audit's menu helper keeps the hook of the other tests
from conftest import make_case


@pytest.fixture()
def hunted(page):
    page.click('.tabs .tab:text-is("IOC hunting")')
    page.fill("#ioc-input", "10.0.0.1\n10[.]0[.]0[.]2\nhxxp://nowhere[.]example/x\nalice")
    page.click("#ioc-scan")
    page.wait_for_function("iocState.list.length > 0", timeout=60000)
    return page


def test_the_hunt_normalises_each_indicator_and_counts_its_fields_and_rows(hunted):
    page = hunted
    rows = page.eval_on_selector_all(
        "#ioc-list-rows tr", "els => els.map(e => [...e.children].map(c => c.innerText))"
    )
    by_original = {row[1]: row for row in rows}
    assert by_original["10[.]0[.]0[.]2"][2] == "10.0.0.2"  # the defanged form is read as an address
    assert by_original["hxxp://nowhere[.]example/x"][2].startswith("http://nowhere.example")
    assert int(by_original["10.0.0.1"][4]) > 0 and int(by_original["10.0.0.1"][5]) > 0
    assert int(by_original["hxxp://nowhere[.]example/x"][4]) == 0
    summary = page.inner_text("#ioc-summary")
    assert "rows read" in summary and "matching fields" in summary and "details kept" in summary


def test_opening_a_different_case_clears_ioc_results_and_history(hunted, server):
    page = hunted
    other = make_case(server, "Case without IOC hunts")
    assert page.locator("#ioc-rows tr[data-hit]").count() > 0
    page.locator('.toolbar [data-act="refresh-cases"]').click()
    page.locator('[data-tab="cases"]').click()
    page.locator('#cases-body tr:has(td:text-is("Case without IOC hunts")) td').first.dblclick()
    page.wait_for_function(
        "document.getElementById('casecombo-label').textContent === 'Case without IOC hunts'"
    )
    page.locator('[data-tab="ioc"]').click()
    assert page.locator("#ioc-input").input_value() == ""
    assert page.locator("#ioc-rows tr[data-hit]").count() == 0
    with page.expect_response(f"**/api/cases/{other}/hunts") as history:
        page.locator("#ioc-history").focus()
    assert history.value.ok and history.value.json()["hunts"] == []


def test_a_detail_has_its_source_date_its_excerpt_and_its_rule(hunted):
    page = hunted
    first = page.eval_on_selector("#ioc-rows tr", "e => [...e.children].map(c => c.innerText)")
    assert first[0].startswith("2026-")  # the source date
    assert first[6] and first[7]  # the excerpt and the rule
    assert "IP address" in first[7]


def test_choosing_an_indicator_shows_only_its_details_and_all_iocs_shows_them_again(hunted):
    page = hunted
    total = page.evaluate("iocState.count")
    page.click('#ioc-list-rows tr[data-ioc="1"]')
    page.wait_for_function(f"iocState.selected === 1 && iocState.count < {total}")
    assert set(
        page.eval_on_selector_all("#ioc-rows tr", "els => els.map(e => e.children[1].innerText)")
    ) == {"10.0.0.1"}
    page.click("#ioc-all-iocs")
    page.wait_for_function(f"iocState.selected === null && iocState.count === {total}")


def test_details_come_in_pages_of_250(page):
    page.click('.tabs .tab:text-is("IOC hunting")')
    page.fill("#ioc-input", "10.0.0.1\n10.0.0.2\n10.0.0.3")
    page.click("#ioc-scan")
    page.wait_for_function("iocState.list.length > 0", timeout=60000)
    assert page.evaluate("iocState.pageSize") == 250
    assert page.evaluate("iocState.hits.length") <= 250
    assert "details" in page.inner_text("#ioc-status")


def test_a_double_click_opens_the_source_row(hunted):
    page = hunted
    page.locator("#ioc-rows tr").first.dblclick()
    page.wait_for_selector("#source-row-modal.show", timeout=30000)
    page.wait_for_function(
        "document.getElementById('source-row-title').innerText.toLowerCase().includes('row')",
        timeout=30000,
    )


def test_the_hunt_exports_in_english_with_the_desktops_columns(hunted, tmp_path):
    page = hunted
    with page.expect_download(timeout=30000) as download:
        page.evaluate("void exportIocMatches()")
    target = tmp_path / "details.csv"
    download.value.save_as(str(target))
    header = target.read_text(encoding="utf-8-sig").splitlines()[0]
    assert "Normalized_IOC" in header and "Excerpt" in header and "Source_row" in header
    assert "Libellé" not in header and "Extrait" not in header
    with page.expect_download(timeout=30000) as summary:
        page.evaluate("void exportIocSummary()")
    other = tmp_path / "summary.csv"
    summary.value.save_as(str(other))
    text = other.read_text(encoding="utf-8-sig")
    assert "Matching_rows" in text.splitlines()[0] and "Found" in text


def test_importing_a_list_fills_the_box_and_hunts_nothing(page, tmp_path):
    page.click('.tabs .tab:text-is("IOC hunting")')
    source = tmp_path / "list.csv"
    source.write_text("type,value,label\nip,10.0.0.3,jump host\nip,not-an-address,bad\n")
    page.set_input_files("#ioc-file", str(source))
    page.wait_for_function("document.getElementById('ioc-input').value.includes('10.0.0.3')")
    assert page.evaluate("iocState.hunt") is None  # nothing was hunted
    assert "valid IOC" in page.inner_text("#ioc-summary")
    assert "rejected" in page.inner_text("#ioc-summary")


def test_a_short_indicator_list_leaves_room_for_details_and_a_long_list_scrolls(hunted):
    page = hunted
    page.set_viewport_size({"width": 1920, "height": 1080})
    summary = page.locator(".ioc-summary-grid")
    details = page.locator("#ioc-rows").locator("xpath=ancestor::div[@class='gridwrap']")
    assert summary.bounding_box()["height"] < 150
    assert details.bounding_box()["height"] > summary.bounding_box()["height"] * 2
    page.fill("#ioc-input", "\n".join(f"10.0.0.{i}" for i in range(1, 121)))
    page.click("#ioc-scan")
    page.wait_for_function("iocState.list.length === 120", timeout=60000)
    assert summary.locator(".gridbody").evaluate("n => n.scrollHeight > n.clientHeight")
    assert details.bounding_box()["height"] > summary.bounding_box()["height"]
