"""The Hayabusa findings tab, control by control, on a case that holds one alert analysis.

The detection engine itself is not run here (it needs the Hayabusa binary: the image-based tests
do that); the alerts it writes are. Each finding is one rule on one host, its alerts are rows of
the alert analysis, and Show / Mark must act on exactly those rows.

Skipped without Playwright and a Chromium; never failed for lack of them.
"""

import time

import httpx
import pytest
from _audit import status
from conftest import make_case

HEADER = "Timestamp,RuleTitle,Level,Computer,Channel,EventID,MitreTactics,MitreTags,Details\n"
ALERTS = [
    (
        "2026-11-02T10:00:00Z",
        "Suspicious Logon",
        "high",
        "PC-1",
        "Security",
        "4624",
        "Credential Access",
        "T1003",
    ),
    (
        "2026-11-02T10:05:00Z",
        "Suspicious Logon",
        "high",
        "PC-2",
        "Security",
        "4624",
        "Credential Access",
        "T1003",
    ),
    (
        "2026-11-02T10:06:00Z",
        "Suspicious Logon",
        "high",
        "PC-2",
        "Security",
        "4624",
        "Credential Access",
        "T1003",
    ),
    (
        "2026-11-02T11:00:00Z",
        "LSASS access",
        "critical",
        "PC-1",
        "Security",
        "4656",
        "Credential Access",
        "T1003.001",
    ),
    (
        "2026-11-03T09:00:00Z",
        "Service installed",
        "medium",
        "PC-3",
        "System",
        "7045",
        "Persistence",
        "T1543.003",
    ),
    (
        "2026-11-03T09:30:00Z",
        "Clock changed",
        "low",
        "PC-3",
        "Security",
        "4616",
        "Defense Evasion",
        "T1070.006",
    ),
]
GROUPS = 5  # Suspicious Logon on PC-2 is one finding of two alerts


def _alerts_text():
    lines = [HEADER.rstrip("\n")]
    for stamp, rule, level, computer, channel, event, tactic, technique in ALERTS:
        lines.append(
            f"{stamp},{rule},{level},{computer},{channel},{event},{tactic},{technique},details"
        )
    return "\n".join(lines) + "\n"


@pytest.fixture()
def findings(server, request):
    """A case whose only analysis is a Hayabusa alert file, open on the findings tab."""
    from _browser import browser_page

    base, _root, evidence = server
    name = "Findings " + request.node.name[:40]
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
    with browser_page(base, name, wait_rows=False) as page:
        page.click('.tabs .tab:text-is("Hayabusa findings")')
        page.wait_for_function(
            "document.querySelectorAll('#hayabusa-rows tr button[data-want=show]').length > 0",
            timeout=30000,
        )
        page.identifier = identifier
        page.base = base
        yield page


def _rows(page):
    return page.locator("#hayabusa-rows tr")


def test_the_table_lists_one_finding_per_rule_and_host_with_its_counts(findings):
    page = findings
    assert _rows(page).count() == GROUPS
    summary = page.inner_text("#finding-summary")
    assert f"{GROUPS} finding(s), {len(ALERTS)} alert(s)" in summary, summary
    first = _rows(page).nth(0).inner_text()
    assert "Suspicious Logon" in first or "LSASS" in first
    counts = page.inner_text("#finding-counts")
    assert "critical 1" in counts and "high 2" in counts, counts
    assert "medium 1" in counts and "low 1" in counts, counts
    assert f"showing {GROUPS} of {GROUPS}" in counts


def test_the_filter_reads_the_rule_the_host_and_the_event_ids(findings):
    page = findings
    seen = {}
    for text in ("lsass", "pc-3", "4624", "persistence", "zzz"):
        page.fill("#finding-search", text)
        page.wait_for_function(
            "(text) => document.getElementById('finding-search').value === text", arg=text
        )
        page.wait_for_timeout(250)
        seen[text] = page.locator("#hayabusa-rows tr button[data-want=show]").count()
    assert seen == {"lsass": 1, "pc-3": 2, "4624": 2, "persistence": 1, "zzz": 0}, seen
    assert "showing 0 of" in page.inner_text("#finding-counts")
    assert "No finding matches" in page.inner_text("#hayabusa-rows")
    page.fill("#finding-search", "")
    page.wait_for_function(
        f"document.querySelectorAll('#hayabusa-rows tr button[data-want=show]').length === {GROUPS}"
    )


def test_each_map_draws_and_the_table_comes_back(findings):
    page = findings
    for view in ("clock", "heat", "chain"):
        page.select_option("#finding-view", view)
        page.wait_for_function("document.getElementById('finding-table').style.display === 'none'")
        painted = page.evaluate(
            """() => {
              const canvas = document.getElementById('finding-map');
              const data = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
              let ink = 0;
              for (let i = 3; i < data.length; i += 4) if (data[i] > 0) ink++;
              return ink;
            }"""
        )
        assert painted > 500, f"the {view} map is blank"
        for group in ("level", "host", "title", "channel"):
            page.select_option("#finding-group", group)
            page.wait_for_timeout(100)
    page.select_option("#finding-view", "table")
    page.wait_for_function("document.getElementById('finding-map-box').style.display === 'none'")
    assert _rows(page).count() == GROUPS
    assert not page.errors, page.errors


def _row_of(page, rule, host):
    return page.locator("#hayabusa-rows tr").filter(has_text=rule).filter(has_text=host)


def test_show_opens_the_alerts_of_this_rule_on_this_host_in_the_grid(findings):
    page = findings
    _row_of(page, "Suspicious Logon", "PC-2").locator('button[data-want="show"]').click()
    page.wait_for_function(
        "document.getElementById('status').innerText.includes('alert(s) of this rule')"
    )
    assert "2 alert(s) of this rule — Suspicious Logon" in status(page)
    assert page.locator(".tabs .tab.active").inner_text() == "Analyses"
    page.wait_for_function("document.querySelectorAll('#body tr').length === 2")
    text = page.inner_text("#body")
    assert "PC-2" in text and "PC-1" not in text, text


def test_mark_bookmarks_every_alert_of_the_finding_and_only_those(findings):
    page = findings
    _row_of(page, "Suspicious Logon", "PC-2").locator('button[data-want="mark"]').click()
    page.wait_for_function(
        "document.getElementById('status').innerText.includes('alert(s) marked')"
    )
    assert "2 alert(s) marked" in status(page)
    page.evaluate("renderGrid()")
    assert "2 alert(s) marked" in status(page)
    marks = httpx.get(f"{page.base}/api/cases/{page.identifier}/analyses/0/bookmarks").json()
    notes = [item["note"] for item in marks["bookmarks"]]
    assert notes == ["Hayabusa: Suspicious Logon"] * 2, notes
    # the other rule of the same event, and the same rule on the other host, stay unmarked
    _row_of(page, "LSASS", "PC-1").locator('button[data-want="mark"]').click()
    page.wait_for_function(
        "document.getElementById('status').innerText.startsWith('1 alert(s) marked')"
    )
    marks = httpx.get(f"{page.base}/api/cases/{page.identifier}/analyses/0/bookmarks").json()
    assert len(marks["bookmarks"]) == 3


def test_findings_are_reloaded_for_the_new_case(findings, server):
    page = findings
    identifier = make_case(server, "Without findings")
    page.locator('.toolbar [data-act="refresh-cases"]').click()
    page.locator('[data-tab="cases"]').click()
    page.locator('#cases-body tr:has(td:text-is("Without findings")) td').first.dblclick()
    page.wait_for_function(
        "document.getElementById('casecombo-label').innerText === 'Without findings'"
    )
    with page.expect_response(f"**/api/cases/{identifier}/findings") as response:
        page.locator('[data-tab="hayabusa"]').click()
    assert response.value.ok
    page.wait_for_function(
        "document.getElementById('finding-summary').innerText.includes('no finding yet')"
    )
    assert _rows(page).inner_text() == "No finding matches this filter."
