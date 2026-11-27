"""The attack graph states nothing it cannot show: every card and link opens its evidence.

The detection engine is not run here (the image tests do that); its alerts are. Each claim of the
graph is checked against the rows it names: the row an evidence item points at must be the very
alert the claim is about.
"""

import time

import httpx
import pytest
from _audit import status  # noqa: F401 - keeps the audit hook of the other browser tests
from conftest import make_case
from test_browser_findings import ALERTS, _alerts_text


@pytest.fixture()
def graph(server, request):
    """A case whose alert analysis, one machine, one indicator and one free node feed the graph."""
    from _browser import browser_page

    from fireblade.core import case_workspace

    base, root, evidence = server
    name = "Graph " + request.node.name[:40]
    identifier = make_case(server, name)
    source = evidence / identifier / "Alertes Hayabusa.csv"
    source.write_text(_alerts_text(), encoding="utf-8-sig")
    job = httpx.post(
        f"{base}/api/cases/{identifier}/import-jobs",
        data={"source": str(source), "organization": "files"},
        timeout=60,
    ).json()["job"]
    for _ in range(240):
        if httpx.get(f"{base}/api/import-jobs/{job}").json().get("status") != "running":
            break
        time.sleep(0.2)
    case_workspace.add_ioc(root / identifier, "203.0.113.7", machine="PC-2")
    httpx.post(
        f"{base}/api/cases/{identifier}/graph/nodes",
        json={"label": "Phishing mail", "tags": "T1566"},
    )
    with browser_page(base, name, wait_rows=False) as page:
        page.click('.tabs .tab:text-is("Attack graph")')
        page.wait_for_function(
            "document.querySelectorAll('#graph-nodes > .gnode').length >= 8", timeout=30000
        )
        page.identifier = identifier
        page.base = base
        yield page


def _card(page, text):
    return page.locator("#graph-nodes > .gnode", has_text=text).first


def test_nothing_is_open_until_a_card_or_a_link_is_asked_about(graph):
    page = graph
    assert page.locator("#graph-evidence").is_hidden()
    assert "Click a card or a link" in page.inner_text("#graph-legend")


def test_a_graph_request_for_the_previous_case_cannot_repaint_the_current_case(graph, server):
    page = graph
    empty_case = make_case(server, "Empty graph case")
    old_graph = httpx.get(f"{page.base}/api/cases/{page.identifier}/graph").json()
    held = []
    old_url = f"**/api/cases/{page.identifier}/graph"
    page.route(old_url, lambda route: held.append(route))
    with page.expect_request(old_url):
        page.locator("#graph-build").click()

    page.locator('.toolbar [data-act="refresh-cases"]').click()
    page.locator('[data-tab="cases"]').click()
    page.locator('#cases-body tr:has(td:text-is("Empty graph case")) td').first.dblclick()
    page.wait_for_function(
        "document.getElementById('casecombo-label').innerText === 'Empty graph case'"
    )
    with page.expect_response(f"**/api/cases/{empty_case}/graph"):
        page.locator('[data-tab="graph"]').click()
    page.wait_for_function("document.querySelectorAll('#graph-nodes .gnode').length === 0")

    with page.expect_response(old_url) as response:
        held[0].fulfill(json=old_graph)
    response.value.finished()
    page.evaluate(
        "new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))"
    )
    assert page.locator("#graph-nodes .gnode").count() == 0


def test_a_card_says_what_it_is_how_it_was_read_and_which_alerts_it_rests_on(graph):
    page = graph
    _card(page, "PC-2").click()
    panel = page.locator("#graph-evidence")
    panel.wait_for(state="visible")
    text = panel.inner_text()
    assert "what this is" in text.lower() and "how kagarasu got it" in text.lower()
    assert "Computer column" in text and "Hayabusa alerts" in text
    assert "Suspicious Logon" in text  # the rule behind PC-2's alerts
    assert "2 alert" in text


def test_a_row_chip_shows_the_exact_line_the_engine_wrote(graph):
    page = graph
    _card(page, "PC-3").click()
    page.locator('#graph-evidence [data-act="graph-line"]').first.click()
    page.wait_for_selector("#graph-evidence .gline table")
    line = page.inner_text("#graph-evidence .gline")
    rows = [item for item in ALERTS if item[3] == "PC-3"]
    assert any(item[1] in line and item[0] in line for item in rows), line
    assert "PC-3" in line and "Computer" in line and "MitreTags" in line


def test_a_link_opens_the_alerts_it_rests_on(graph):
    page = graph
    page.locator("#graph-edges .gpill").first.click()
    panel = page.locator("#graph-evidence")
    panel.wait_for(state="visible")
    assert "→" in panel.locator("h3").inner_text()
    assert "link" in panel.inner_text().lower()
    assert page.locator('#graph-evidence [data-act="graph-line"]').count() >= 1


def test_the_selection_lights_its_links_and_dims_the_rest(graph):
    page = graph
    _card(page, "PC-3").click()
    assert page.locator(".gedge.hot").count() >= 1
    assert page.locator(".gnode.dim").count() >= 1
    assert "selected" in _card(page, "PC-3").get_attribute("class")
    page.click('#graph-evidence [data-act="graph-close"]')
    assert page.locator("#graph-evidence").is_hidden()
    assert page.locator(".gnode.dim").count() == 0


def test_what_the_analyst_entered_says_so_and_has_no_source_row(graph):
    page = graph
    _card(page, "203.0.113.7").click()
    text = page.inner_text("#graph-evidence")
    assert "recorded by the analyst" in text.lower() and "tracked" in text.lower()
    assert page.locator('#graph-evidence [data-act="graph-line"]').count() == 0
    _card(page, "Phishing mail").click()
    text = page.inner_text("#graph-evidence")
    assert "Added by hand" in text and "no source row" in text


def test_show_in_the_grid_opens_the_alerts_of_that_rule_on_that_host(graph):
    page = graph
    _card(page, "PC-3").click()
    page.locator('#graph-evidence [data-act="graph-show"]').first.click()
    page.wait_for_function(
        "document.getElementById('status').innerText.includes('alert(s) of this rule')",
        timeout=30000,
    )
    assert page.locator("#body tr[data-row]").count() >= 1


def test_every_claim_of_the_graph_names_rows_that_say_the_same_thing(graph):
    """The proof: each evidence row is the alert of the rule and host the claim is about."""
    page = graph
    payload = httpx.get(f"{page.base}/api/cases/{page.identifier}/graph", timeout=60).json()
    analysis = payload["source"]["analysis"]
    assert analysis is not None
    checked = 0
    for entity in payload["nodes"] + payload["edges"]:
        evidence = entity["evidence"]
        assert evidence["what"] and evidence["how"], entity
        for item in evidence["items"]:
            for row in item["rows"]:
                line = httpx.get(
                    f"{page.base}/api/cases/{page.identifier}/timeline/row/{analysis}/{row}",
                    timeout=60,
                ).json()
                values = dict(zip(line["columns"], line["values"], strict=False))
                assert values["RuleTitle"] == item["title"], (entity["id"], values)
                assert values["Computer"] == item["host"], (entity["id"], values)
                checked += 1
    assert checked >= len(ALERTS)
    for edge in payload["edges"]:
        if edge["label"] == "alert":
            host = edge["source"].split(":", 1)[1]
            for item in edge["evidence"]["items"]:
                assert item["host"].casefold().replace(" ", "-") == host
