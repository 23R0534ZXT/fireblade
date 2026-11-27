"""Observable behavior of the remaining report, statistics and navigation controls."""

from _audit import command
from test_browser_effects import numbers  # noqa: F401


def test_statistical_population_and_percent_rank_apply_to_source_rows(numbers):  # noqa: F811
    page = numbers
    command(page, "rules")
    page.select_option("#rule-column", label="Value")
    page.select_option("#rule-operator", "not_empty")
    page.select_option("#rule-target", "cell")
    page.select_option("#rule-statistic", "top")
    page.fill("#rule-stat-rank", "25")
    for field in ["rule-stat-percent", "rule-stat-null", "rule-stat-all"]:
        page.check("#" + field)
    page.select_option("#rule-visual", "scale3")
    for field in ["rule-middle-colour", "rule-ink"]:
        page.focus("#" + field)
        page.press("#" + field, "Tab")
    page.select_option("#rule-visual", "bar")
    page.fill("#rule-min", "0")
    page.fill("#rule-max", "400")
    page.uncheck("#rule-axis")
    for field in ["rule-negative", "rule-axis-colour"]:
        page.focus("#" + field)
        page.press("#" + field, "Tab")
    page.click('[data-act="rule-add"]')
    page.wait_for_function("document.querySelectorAll('#body td.vbar').length === 3")
    assert set(page.locator("#body td.vbar").all_text_contents()) == {"200", "300", "400"}
    page.fill('#head input[data-filter="0"]', "=n0")
    page.wait_for_function("document.getElementById('pageinfo').innerText.includes('/ 1 ')")
    assert page.locator("#body td.vbar").count() == 0


def test_tracking_subtabs_and_report_filter_show_the_expected_content(page):
    page.click('[data-tab="actions"]')
    page.click('[data-sub="entities"]')
    assert page.locator("#sub-entities").is_visible()
    page.click('[data-sub="actions"]')
    assert page.locator("#sub-actions").is_visible()
    page.click('[data-tab="imports"]')
    page.click("#retry-open")
    page.select_option("#report-filter", "all")
    page.wait_for_selector("#retry-list .retry-line")
    assert page.locator("#retry-list .retry-line").count() == 1
    page.select_option("#report-filter", "duplicate")
    assert page.locator("#retry-list .retry-line").count() == 0
    page.select_option("#report-filter", "imported")
    assert page.locator("#retry-list .retry-line").count() == 1


def test_interrupt_stops_a_running_hunt_without_publishing_incomplete_results(server):
    from _browser import browser_page
    from conftest import make_case

    make_case(
        server,
        "Interruptible hunt",
        "Time,IP,User\n" + "2026-11-01T12:00:00Z,192.0.2.1,alice\n" * 500000,
    )
    with browser_page(server[0], "Interruptible hunt") as page:
        page.click('[data-tab="ioc"]')
        page.fill("#ioc-input", "192.0.2.1\nalice")
        page.fill("#ioc-limit", "1000000")
        page.click("#ioc-scan")
        page.wait_for_function("taskState.job !== null")
        page.keyboard.press("Escape")
        with page.expect_response(lambda r: r.url.endswith("/ioc-stop")) as stopped:
            page.click("#ioc-stop")
        assert stopped.value.json()["stopped"] is True
        page.wait_for_function("taskState.job === null", timeout=60000)
        assert page.evaluate("iocState.count") == 0
        identifier = page.evaluate("state.openCase.id")
        assert (
            page.request.get(page.url.rstrip("/") + f"/api/cases/{identifier}/hunts").json()[
                "hunts"
            ]
            == []
        )
