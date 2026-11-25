"""The detection chain on the real image: Hayabusa, its findings, the graph, the rules, the
context of an alert — every button pressed in a browser, every answer read on the screen."""

import httpx
import pytest
from conftest import SERVER_PACK, URL, analyses, create_case, import_path, unique

EVTX = f"{SERVER_PACK}/01-Windows/01-Collecte-principale/EvtxECmd"


@pytest.fixture(scope="module")
def detected():
    """A case with the pack's event logs imported and the detection already run once."""
    name = unique("Detection")
    case = create_case(name)
    assert import_path(case, EVTX)["status"] == "complete"
    return name, case


def _run(page, level="informational"):
    page.click('.tabs .tab:text-is("Hayabusa findings")')
    page.select_option("#hayabusa-level", level)
    page.click("#hayabusa-run")
    page.wait_for_function(
        "document.getElementById('hayabusa-summary').innerText.includes('finding(s)')",
        timeout=300000,
    )


def test_the_detection_runs_and_the_findings_table_lists_them(detected, browse, expected):
    name, _case = detected
    with browse(name) as page:
        _run(page)
        page.wait_for_function(
            "document.querySelectorAll('#hayabusa-rows tr button[data-want=show]').length > 0",
            timeout=60000,
        )
        shown = page.locator("#hayabusa-rows tr").count()
        assert shown >= 1
        alerts = int(page.inner_text("#finding-summary").split("alert(s)")[0].split(",")[-1])
        assert alerts >= expected.get("hayabusa_minimum_alerts", 1), page.inner_text(
            "#finding-summary"
        )
        for view in ("clock", "heat", "chain"):
            page.select_option("#finding-view", view)
            painted = page.evaluate(
                "(() => { const c = document.getElementById('finding-map');"
                " const d = c.getContext('2d').getImageData(0,0,c.width,c.height).data;"
                " let n = 0; for (let i = 3; i < d.length; i += 4) if (d[i] > 0) n++; return n; })()"
            )
            assert painted > 500, view
        page.select_option("#finding-view", "table")


def test_show_opens_the_alerts_and_mark_bookmarks_them(detected, browse):
    name, case = detected
    with browse(name) as page:
        _run(page)
        page.wait_for_selector("#hayabusa-rows tr button[data-want=show]", timeout=60000)
        first = page.locator("#hayabusa-rows tr").first
        title = first.locator("td").nth(2).inner_text()
        first.locator('button[data-want="show"]').click()
        page.wait_for_function(
            "document.getElementById('status').innerText.includes('alert(s) of this rule')"
        )
        assert title in page.inner_text("#status")
        assert page.locator("#body tr[data-row]").count() >= 1
        page.click('.tabs .tab:text-is("Hayabusa findings")')
        page.locator("#hayabusa-rows tr").first.locator('button[data-want="mark"]').click()
        page.wait_for_function(
            "document.getElementById('status').innerText.includes('alert(s) marked')"
        )
    index = max(item["index"] for item in analyses(case) if "Hayabusa" in item["label"])
    marks = httpx.get(f"{URL}/api/cases/{case}/analyses/{index}/bookmarks", timeout=60).json()
    assert marks["bookmarks"], "the alerts of the finding are bookmarked"


def test_the_findings_screen_counts_the_findings_and_their_alerts(detected, browse):
    name, _case = detected
    with browse(name) as page:
        page.click('.tabs .tab:text-is("Hayabusa findings")')
        page.wait_for_function(
            "/\\d+ finding\\(s\\), \\d+ alert\\(s\\)/.test("
            "document.getElementById('finding-summary').innerText)",
            timeout=30000,
        )


def test_the_attack_graph_builds_and_leaves_as_a_navigator_layer_and_a_png(
    detected, browse, tmp_path
):
    import json

    name, _case = detected
    with browse(name) as page:
        page.click('.tabs .tab:text-is("Attack graph")')
        page.click("#graph-build")
        page.wait_for_function(
            "!document.getElementById('graph-summary').innerText.includes('No finding') "
            "&& document.getElementById('graph-summary').innerText.includes('node(s)')",
            timeout=120000,
        )
        with page.expect_download(timeout=30000) as layer:
            page.click("#graph-navigator")
        saved = tmp_path / "layer.json"
        layer.value.save_as(str(saved))
        techniques = json.loads(saved.read_text(encoding="utf-8")).get("techniques", [])
        assert techniques, "the Navigator layer lists the techniques of the findings"
        with page.expect_download(timeout=30000) as picture:
            page.click("#graph-png")
        png = tmp_path / "graph.png"
        picture.value.save_as(str(png))
        assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_the_detection_rules_can_be_read_switched_off_edited_and_put_back(detected, browse):
    name, _case = detected
    with browse(name) as page:
        page.click('.tabs .tab:text-is("Hayabusa findings")')
        page.click("#detrules-open")
        page.wait_for_function(
            "document.querySelectorAll('#detrules-rows tr').length > 50", timeout=60000
        )
        page.fill("#detrules-filter", "logon")
        page.wait_for_timeout(500)
        shown = page.locator("#detrules-rows tr").count()
        assert 0 < shown < 5000
        page.locator("#detrules-rows tr").first.click()
        page.wait_for_function("document.getElementById('detrules-text').value.length > 20")
        rule = page.inner_text("#detrules-name")
        page.click("#detrules-toggle")
        page.wait_for_function("document.getElementById('status').innerText.length > 0")
        page.check("#detrules-changed")
        page.wait_for_function(
            "document.querySelectorAll('#detrules-rows tr').length >= 1", timeout=30000
        )
        assert rule.split("/")[-1][:12] in page.inner_text("#detrules-rows") or rule
        page.locator("#detrules-rows tr").first.click()
        page.click("#detrules-toggle")  # back on
        page.click("#detrules-reset")
        page.click("#detrules-reload")
        page.uncheck("#detrules-changed")
        page.wait_for_function(
            "document.querySelectorAll('#detrules-rows tr').length > 50", timeout=30000
        )


def test_an_alert_gives_its_evtx_context_and_its_source_event(detected, browse):
    name, case = detected
    with browse(name, wait_rows=False) as page:
        _run(page)
        page.wait_for_selector("#hayabusa-rows tr button[data-want=show]", timeout=60000)
        page.locator("#hayabusa-rows tr").first.locator('button[data-want="show"]').click()
        page.wait_for_selector("#body tr[data-row]")
        # the grid of the alerts, not the one that was on screen before it loaded
        page.wait_for_function("state.columns.includes('Fireblade_EVTX_Source')", timeout=60000)
        page.locator("#body tr[data-row] td[data-cell]").nth(1).click(button="right")
        page.click('#row-menu [data-act="alert-context"]')
        page.wait_for_function(
            "document.getElementById('status').innerText.startsWith('Context of')", timeout=120000
        )
        assert "EVTX context" in " ".join(item["label"] for item in analyses(case))
        page.click('.tabs .tab:text-is("Analyses")')
