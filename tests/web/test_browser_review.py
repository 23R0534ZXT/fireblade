"""Review source records, scroll large grids and navigate grouped investigation views."""

import csv

import httpx
from _browser import browser_page, serving
from conftest import make_case

from fireblade.web.service import Library


def review_csv(rows=1200):
    return "Line,Host,Verdict,Empty\n" + "".join(
        f"{i},PC-{i % 3},{'open' if i % 2 else 'review: & hold'},\n" for i in range(rows)
    )


def test_recmd_batch_exports_can_be_grouped_sorted_and_filtered(tmp_path):
    root = tmp_path / "cases"
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    headers = ["HivePath", "HiveType", "Category", "Description", "KeyPath", "ValueName"]
    first_hive = r"C:\Workstation1\NTUSER.DAT"
    second_hive = r"C:\Workstation2\NTUSER.DAT"
    sources = {
        "20261127093000_RECmd_Batch_Kroll_Batch_Output.csv": [
            [first_hive, "NTUSER", "User Activity", "Recent documents", "RecentDocs", "0"],
            [first_hive, "NTUSER", "Autoruns", "Run keys", "Run", "an-app"],
        ],
        "20261127125000_RECmd_Batch_Custom_Registry_Output.csv": [
            [second_hive, "NTUSER", "Autoruns", "Run keys", "Run", "another-app"],
            [second_hive, "NTUSER", "Autoruns", "Startup folder", "Shell Folders", "Startup"],
        ],
    }
    for name, rows in sources.items():
        with (evidence / name).open("w", newline="", encoding="utf-8") as output:
            writer = csv.writer(output)
            writer.writerow(headers)
            writer.writerows(rows)
    library = Library(root)
    try:
        case = library.create_case("Registry exports", "", "windows")["id"]
        library.import_source(case, evidence, organization="combined")
    finally:
        library.close()

    with serving(root) as base, browser_page(base, "Registry exports") as page:
        review = page.locator("#recmd-review")
        dialog = page.locator("#recmd-modal")
        review.click()
        dialog.get_by_role("button", name="Group by category → rule → source hive").click()
        page.locator('#body tr[data-group-depth="0"][data-value="Autoruns"]').click()
        page.locator('#body tr[data-group-depth="1"][data-value="Run keys"]').click()
        hives = page.locator('#body tr[data-group-depth="2"]')
        hives.first.wait_for()
        assert sorted(hives.evaluate_all("rows => rows.map(row => row.dataset.value)")) == [
            first_hive,
            second_hive,
        ]
        page.click("#grid-group-back")
        page.locator('#body tr[data-group-depth="1"][data-value="Startup folder"]').wait_for()

        review.click()
        dialog.get_by_role("button", name="Group by collected file first").click()
        files = page.locator('#body tr[data-group-depth="0"]')
        files.first.wait_for()
        assert sorted(
            files.evaluate_all("rows => rows.map(row => row.dataset.value.split('/').at(-1))")
        ) == sorted(sources)

        review.click()
        dialog.get_by_role("button", name="Sort by category").click()
        page.wait_for_function("!state.grouped && rowsRequest === null")
        assert page.evaluate("state.rows.map(row => row[state.columns.indexOf('Category')])") == [
            "Autoruns",
            "Autoruns",
            "Autoruns",
            "User Activity",
        ]
        review.click()
        dialog.get_by_role("button", name="Filter by rule").click()
        page.locator("#column-values-list").get_by_text("Run keys", exact=True).click()
        page.click("#column-values-apply")
        page.wait_for_function("state.total === 2 && rowsRequest === null")

        review.click()
        dialog.get_by_role("button", name="Filter by collected file").click()
        page.locator("#column-values-list label").filter(has_text="Custom_Registry").click()
        page.click("#column-values-apply")
        page.wait_for_function("state.total === 1 && rowsRequest === null")
        page.locator("#body td[data-cell]").first.click()
        details = page.locator("#details .evidence-origin")
        batch = details.get_by_text("Custom_Registry.reb", exact=True)
        batch.wait_for()
        assert second_hive in details.inner_text()
        assert "Run keys" in details.inner_text()


def test_continuous_columns_group_parents_and_marks(server):
    title = "Analyst grid review"
    make_case(server, title, review_csv())
    with browser_page(server[0], title) as page:
        assert page.locator("#recmd-review").is_hidden()
        page.click("#grid-scroll-mode")
        assert not page.locator("#next").is_visible()
        page.eval_on_selector("#gridbody", "box => {box.scrollTop = box.scrollHeight}")
        page.wait_for_function("state.rows.at(-1)?.[1] === '1199' && rowsRequest === null")
        page.wait_for_function("document.querySelectorAll('#body tr[data-row]').length <= 200")
        position = page.locator("#body tr[data-row]").last
        assert position.locator("td[data-cell='0']").inner_text() == "1199"
        page.click("#grid-scroll-mode")
        assert page.locator("#next").is_visible()
        page.click("#first")
        page.click("#grid-hide-empty")
        page.wait_for_function("state.hidden.has(4)")
        page.click("#grid-hidden-columns")
        assert page.locator("#columns-hidden-only").is_checked()
        page.locator("#columns-list input[data-col='4']").click()
        page.locator("#columns-modal [data-act='settings-close']").click()
        assert page.locator("#head [data-column='4']").is_visible()

        page.get_by_role("button", name="Values in Verdict").click()
        values = page.locator("#column-values-list")
        values.get_by_text("review: & hold", exact=True).click()
        page.click("#column-values-apply")
        page.wait_for_function("state.total === 600 && rowsRequest === null")
        assert set(page.locator("#body td[data-cell='2']").all_text_contents()) == {
            "review: & hold"
        }

        page.locator("#groupbar [data-act='group-column']").click()
        page.locator("#group-levels [data-group-level='1']").check()
        page.locator("#group-levels [data-group-level='2']").check()
        page.locator("#group-modal [data-act='group-apply']").click()
        page.locator("#body tr[data-group-depth='0']").first.click()
        page.locator("#body tr[data-group-depth='1']").first.click()
        page.wait_for_function("state.path.length === 2 && !state.grouped && rowsRequest === null")
        page.click("#grid-group-back")
        page.wait_for_function("state.path.length === 1 && state.grouped && rowsRequest === null")
        page.locator("#body tr[data-group]").first.click()
        mark = page.locator("#body .markcell button").first
        mark.click()
        page.get_by_role("button", name="Mark row 1, High").wait_for()
        page.get_by_role("button", name="Configure row marks").click()
        page.fill("#quick-marks-text", "H = High\nV = Verify")
        page.click("#quick-marks-save")
        mark.click()
        page.get_by_role("button", name="Mark row 1, Verify").wait_for()
        page.click("#tab-graph")
        page.locator("#graph-nodes").get_by_text("V · Verify", exact=True).click()
        page.locator("#graph-evidence").get_by_role("button", name="Open source row").click()
        page.wait_for_selector("#source-row-modal.show")
        page.locator("#source-row-modal [data-act='settings-close']").click()
        page.click("#workspace-back")
        page.wait_for_function("state.path.length === 2 && !state.grouped && rowsRequest === null")
        assert mark.inner_text() == "V"


def test_sources_and_family_layout_follow_the_artifact(tmp_path):
    root = tmp_path / "cases"
    library = Library(root)
    try:
        for name in ("First collection", "Later collection"):
            evidence = tmp_path / name
            evidence.mkdir()
            for source in ["one.csv", "two.csv"]:
                (evidence / source).write_text("Host,Detail\nPC-1,record in " + source + "\n")
            identifier = library.create_case(name, "", "windows")["id"]
            library.import_source(identifier, evidence, organization="artifacts")
    finally:
        library.close()
    with serving(root) as base, browser_page(base, "First collection") as page:
        assert page.locator(".grid-preferences.first-visit").is_visible()
        page.locator(".grid-preferences").click()
        page.get_by_text("Detail", exact=True).last.wait_for()
        checkbox = page.locator(
            "#columns-list label:has([data-column-label]:text-is('Detail')) input[data-col]"
        )
        checkbox.uncheck()
        page.click("#family-save")
        page.locator("#columns-modal [data-act='settings-close']").click()
        page.locator("#tree [data-analysis]").first.click(button="right")
        page.click("#tree-expose-sources")
        page.get_by_role("button", name="two.csv 1").click()
        page.wait_for_function("state.total === 1 && rowsRequest === null")
        page.locator("#body tr[data-row] td[data-cell]").first.click()
        assert "two.csv" in page.locator("#details .evidence-origin").inner_text()
        page.click("#tab-cases")
        page.get_by_text("Later collection", exact=True).dblclick()
        page.wait_for_function("state.openCase.name === 'Later collection' && rowsRequest === null")
        detail = page.evaluate("state.columns.indexOf('Detail')")
        assert page.locator(f"#head [data-column='{detail}']").count() == 0
        assert not page.locator(".grid-preferences.first-visit").count()


def test_scoped_search_and_lnk_timeline(server):
    name = "Shortcut clock"
    base = server[0]
    identifier = make_case(
        server,
        name,
        "SourceFile,SourceCreated,SourceModified,SourceAccessed,TargetCreated,TargetModified,TargetAccessed,Host\n"
        "demo.lnk,2026-11-02T08:00:00Z,2026-11-03T09:00:00Z,,2026-11-01T07:00:00Z,,,PC-LINK\n",
    )
    other = make_case(server, "Search other case", "Name,Host\nBoundaryCaseNeedle,PC2\n")
    with browser_page(base, name) as page:
        page.locator("#body tr[data-row] td[data-cell]").first.click()
        dates = page.locator("#details .lnk-dates")
        assert "Target creation" in dates.inner_text()
        dates.locator("tr").filter(has_text="Target creation").get_by_role("button").click()
        page.wait_for_function("timelineState.payload?.rows[0]?.[3] === '2026-11-01T07:00:00Z'")
        page.click("#timeline-group")
        page.locator("#table-group-levels input[value='analysis']").check()
        page.locator("#table-group-levels input[value='day']").check()
        page.click("#table-group-apply")
        page.locator("[data-timeline-group][data-group-depth='0']").first.click()
        page.locator("[data-timeline-group][data-group-depth='1']").first.click()
        page.wait_for_selector("#timeline-rows [data-tl-row]")
        page.get_by_role("button", name="All groups", exact=True).click()
        page.wait_for_function(
            "timelineGrouping.path.length === 0 && timelineState.payload.groups?.length === 1"
        )
        page.click("#workspace-back")
        page.select_option("#search-scope", "library")
        page.fill("#search", "BoundaryCaseNeedle")
        page.click("#search-submit")
        page.locator("#global-results h4").get_by_text("Search other case", exact=True).wait_for()
        page.locator(f"#global-results [data-review-case='{other}'][data-review-row]").click()
        page.wait_for_selector("#source-row-modal :text-is('BoundaryCaseNeedle')")
        assert page.evaluate("state.openCase.id") == other
    response = httpx.get(f"{base}/api/cases/{identifier}/timeline", params={"groups": "day"})
    assert response.status_code == 200
    assert response.json()["groups"] == [["2026-11-03", 1]]
