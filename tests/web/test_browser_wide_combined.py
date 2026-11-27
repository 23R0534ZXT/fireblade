"""A heterogeneous collection stays one grid, with bounded cells and real far-field values."""

import csv

import httpx
import pytest
from _browser import browser_page, serving

from fireblade.core.investigations import InvestigationLibrary
from fireblade.web.service import Library


@pytest.fixture()
def wide_case(tmp_path):
    root = tmp_path / "cases"
    root.mkdir()
    source = tmp_path / "evidence"
    source.mkdir()
    for number in range(4):
        with (source / f"source{number}.csv").open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["Timestamp"] + [f"field{number}_{i}" for i in range(800)])
            writer.writerow(
                ["2026-11-01T10:00:00Z"]
                + [
                    ""
                    if number == 2 and i == 798
                    else " \t\r\n"
                    if number == 2 and i == 797
                    else f"value-{number}-{i}"
                    for i in range(800)
                ]
            )
    identifier = InvestigationLibrary(root).create("Wide combined", "", "windows")["id"]
    library = Library(root)
    try:
        library.import_source(identifier, source, organization="combined")
        assert len(library.case(identifier)["analyses"]) == 1
    finally:
        library.close()
    yield root, identifier


def test_wide_rows_are_projected_without_losing_far_fields(wide_case):
    root, identifier = wide_case
    with serving(root) as base:
        endpoint = f"{base}/api/cases/{identifier}/analyses/0/rows"
        page = httpx.get(endpoint).json()
        assert page["total"] == 4
        assert len(page["columns"]) == 3206
        assert len(page["projection"]) == 64
        assert all(len(row) == 64 for row in page["rows"])
        large_window = httpx.get(endpoint, params=[("column", i) for i in range(300)]).json()
        assert large_window["projection"] == list(range(300))
        assert all(len(row) == 300 for row in large_window["rows"])
        far = page["columns"].index("field3_799")
        selected = httpx.get(
            endpoint, params={"column": far, "filter": f"{far - 1}:eq:value-3-799"}
        ).json()
        assert selected["total"] == 1
        assert selected["projection"] == [0, far]
        assert selected["rows"] == [[4, "value-3-799"]]
        full = httpx.get(f"{base}/api/cases/{identifier}/timeline/row/0/4").json()
        assert full["values"][far - 1] == "value-3-799"
        empty = httpx.get(endpoint.rsplit("/", 1)[0] + "/empty-columns").json()
        assert set(empty["columns"]) == {
            page["columns"].index("field2_797"),
            page["columns"].index("field2_798"),
        }
        exported = httpx.post(
            endpoint.rsplit("/", 1)[0] + "/export",
            json={
                "column": list(reversed(range(len(page["columns"]) - 1))),
                "filter": [f"{far - 1}:eq:value-3-799"],
            },
        )
        assert exported.status_code == 200, exported.text[:500]
        import io

        records = list(csv.reader(io.StringIO(exported.content.decode("utf-8-sig"))))
        assert len(records) == 2 and len(records[0]) == len(page["columns"]) - 1
        assert records[0][0] == "field3_799" and records[1][0] == "value-3-799"


def test_wide_grid_scroll_search_details_and_switch_to_narrow(wide_case):
    root, _identifier = wide_case
    with (
        serving(root) as base,
        browser_page(base, "Wide combined", width=1920, height=1080) as page,
    ):
        page.wait_for_function("rowsRequest === null")
        assert page.locator("#head th[data-column]").count() < 30
        assert page.locator("#body td").count() < 160
        page.evaluate("openColumnManager()")
        assert page.locator("#columns-list input[data-col]").count() == 100
        page.fill("#column-search", "field3_799")
        page.click("#columns-list [data-jump-column]")
        page.wait_for_function(
            "rowsRequest === null && state.rows.some(row => row[state.columns.indexOf('field3_799')] === 'value-3-799')"
        )
        far = page.evaluate("state.columns.indexOf('field3_799')")
        assert page.locator(f"#head th[data-column='{far}']").count() == 1
        page.locator(f"#body tr[data-row='4'] td[data-cell='{far - 1}']").click()
        page.wait_for_selector("#details :text-is('value-3-799')")
        assert "undefined" not in page.inner_text("#details")
        page.fill(f"#head input[data-filter='{far - 1}']", "value-3-799")
        page.locator(f"#head input[data-filter='{far - 1}']").press("Enter")
        page.wait_for_function("state.total === 1 && rowsRequest === null")
        assert "value-3-799" in page.inner_text("#body")
        page.locator(f"#body tr[data-row='4'] td[data-cell='{far - 1}']").click()
        page.wait_for_selector("#note-input")
        page.fill("#note-input", "Follow this source record")
        with page.expect_response(lambda response: response.url.endswith("/bookmark")):
            page.click("#note-save")
        with page.expect_response(lambda response: response.url.endswith("/reorganize")):
            page.select_option("#import-layout", "files")
        page.wait_for_function("state.openCase.analyses.length === 4 && rowsRequest === null")
        assert len(page.evaluate("state.columns")) == 802
        assert page.evaluate("state.total") == 1
        assert page.locator("#note-input").count() == 0, (
            "stale note editors must close with the old grid"
        )
        page.locator("#tree [data-analysis]").filter(has_text="source3.csv").click()
        page.wait_for_function("rowsRequest === null")
        page.locator("#body tr[data-row='1'] td[data-cell]").first.click()
        page.wait_for_selector("#note-input")
        assert page.input_value("#note-input") == "Follow this source record"
