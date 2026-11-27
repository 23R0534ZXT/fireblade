"""Contracts for gaps in the desktop Host's interaction inventory."""

from _audit import command
from test_browser_findings import GROUPS, findings  # noqa: F401 - shared browser fixture
from test_browser_timeline import timeline  # noqa: F401 - shared browser fixture


def test_preferences_are_changed_by_their_controls_and_survive_reload(page):
    command(page, "preferences")
    page.wait_for_function("document.getElementById('prefs-query-threads').value !== ''")
    page.select_option("#prefs-date-format", "custom")
    page.fill("#prefs-date-pattern", "dd/MM/yyyy HH:mm")
    page.press("#prefs-date-pattern", "Tab")
    page.check("#prefs-right-copy")
    page.fill("#prefs-pins", "User\nHost")
    page.press("#prefs-pins", "Tab")
    for control, value in [("prefs-query-threads", "2"), ("prefs-parsing-threads", "3")]:
        page.fill("#" + control, value)
        with page.expect_response(
            lambda r: r.url.endswith("/api/preferences") and r.request.method == "PUT"
        ):
            page.press("#" + control, "Tab")
    with page.expect_response(
        lambda r: r.url.endswith("/api/preferences") and r.request.method == "PUT"
    ):
        page.uncheck("#prefs-auto-profile")
    saved = page.request.get(page.url.rstrip("/") + "/api/preferences").json()
    assert saved["query_threads"] == 2 and saved["parsing_threads"] == 3
    assert saved["auto_profiles"] is False
    page.reload()
    page.wait_for_selector("#menubar")
    command(page, "preferences")
    assert page.input_value("#prefs-date-pattern") == "dd/MM/yyyy HH:mm"
    assert page.is_checked("#prefs-right-copy")
    assert page.input_value("#prefs-pins") == "User\nHost"
    page.wait_for_function("document.getElementById('prefs-parsing-threads').value === '3'")
    page.locator('#prefs-modal [data-act="compat-open"]').click()
    page.wait_for_selector("#compat-modal.show")
    page.click('[data-act="compat-reload"]')
    page.wait_for_function("document.getElementById('compat-modal').innerText.includes('profile')")


def test_all_client_fields_are_saved_and_reopened(page):
    page.click('[data-tab="actions"]')
    page.click("#client-open")
    wanted = {
        "cm-sector": "Energy",
        "cm-contact": "Review contact",
        "cm-contract": "IR-123",
        "cm-end": "2026-11-30",
    }
    for control, value in wanted.items():
        page.fill("#" + control, value)
    page.click("#client-save")
    page.wait_for_selector("#client-modal.show", state="hidden")
    page.click("#client-open")
    for control, value in wanted.items():
        page.wait_for_function(
            "([id,value])=>document.getElementById(id).value === value", arg=[control, value]
        )


def test_an_ask_can_be_cancelled_without_changing_the_note(page):
    page.locator("#body tr[data-row] td[data-cell]").first.click(button="right")
    page.locator('#row-menu [data-act="cell-note"]').click()
    page.wait_for_selector("#ask-modal.show")
    page.fill("#ask-input", "must not be saved")
    page.click('[data-act="ask-cancel"]')
    page.wait_for_selector("#ask-modal.show", state="hidden")
    assert page.locator("#body td.noted").count() == 0


def test_filter_and_palette_fields_can_be_found_by_their_accessible_names(page):
    command(page, "expression-andor")
    page.get_by_role("combobox", name="Filter logic", exact=True).select_option("and")
    page.get_by_role("combobox", name="Condition column", exact=True).select_option(label="User")
    page.get_by_role("combobox", name="Condition operator", exact=True).select_option("eq")
    page.locator("[data-expr-value]").first.fill("bob")
    page.click('[data-act="expr-apply"]')
    page.wait_for_function("document.getElementById('pageinfo').innerText.includes('/ 20')")
    assert set(page.locator('#body td[data-cell="2"]').all_text_contents()) == {"bob"}
    command(page, "display-settings")
    page.select_option("#palette-theme", "custom")
    for name in ["window", "text", "grid", "alternate rows", "selection", "selected text"]:
        assert page.get_by_label(name, exact=True).is_visible()


def test_report_scope_and_limits_reach_the_generated_document(page):
    command(page, "report")
    page.fill("#report-description", "Review description <must be escaped>")
    page.select_option("#report-bookmarks", "false")
    page.uncheck("#report-filters")
    page.fill("#report-limit", "3")
    page.click('[data-act="report-build"]')
    page.wait_for_selector("#report-result a", timeout=60000)
    assert "3 finding(s)" in page.inner_text("#report-result")
    html = page.request.get(
        page.url.rstrip("/") + page.get_attribute("#report-result a", "href")
    ).text()
    assert "Review description &lt;must be escaped&gt;" in html
    page.select_option("#report-type", "client")
    page.fill("#client-title", "Client coverage review")
    page.fill("#client-analyst", "Review analyst")
    page.uncheck("#client-findings")
    page.check("#client-coverage")
    page.click('[data-act="report-build"]')
    page.wait_for_function(
        "document.getElementById('report-result').innerText.includes('Client report:')",
        timeout=60000,
    )
    html = page.request.get(
        page.url.rstrip("/") + page.get_attribute("#report-result a", "href")
    ).text()
    assert "Client coverage review" in html and "Review analyst" in html


def test_custom_coverage_plan_preserves_the_selected_families(page):
    command(page, "coverage-open")
    page.click("#coverage-plan")
    page.wait_for_selector("#coverage-plan-list input[data-family]")
    choices = page.locator("#coverage-plan-list input[data-family]")
    for control in choices.all():
        control.uncheck()
    chosen = choices.first.get_attribute("data-family")
    choices.first.check()
    page.click("#coverage-plan-apply")
    page.click("#coverage-plan")
    page.wait_for_selector("#coverage-plan-list input[data-family]")
    assert page.locator("#coverage-plan-list input:checked").count() == 1
    assert page.locator("#coverage-plan-list input:checked").get_attribute("data-family") == chosen


def test_global_summary_is_correct_and_can_be_hidden(page):
    command(page, "summaries")
    page.click("#total-add")
    page.locator("#total-rows [data-summary-column]").select_option(label="Event")
    page.locator("#total-rows [data-summary-operation]").select_option("rows")
    page.select_option("#summary-footer-mode", "always")
    page.click("#summary-apply")
    page.wait_for_selector("#body .gtotal")
    assert "rows 60" in page.inner_text("#body .gtotal")
    command(page, "summaries")
    page.uncheck("#summary-show-total")
    page.click("#summary-apply")
    page.wait_for_function("!document.querySelector('#body .gtotal')")


def test_ioc_details_page_and_limit_are_observable(server):
    from _browser import browser_page
    from conftest import make_case

    make_case(
        server,
        "IOC pagination contract",
        "Time,IP\n" + "".join("2026-11-01T12:00:00Z,192.0.2.1\n" for i in range(950)),
    )
    with browser_page(server[0], "IOC pagination contract") as opened:
        opened.click('[data-tab="ioc"]')
        opened.fill("#ioc-input", "192.0.2.1")
        opened.fill("#ioc-limit", "950")
        opened.click("#ioc-scan")
        opened.wait_for_function(
            "document.getElementById('ioc-summary').innerText.includes('950 details kept')",
            timeout=60000,
        )
        first = opened.locator("#ioc-rows tr").first.inner_text()
        opened.click("#ioc-next")
        opened.wait_for_function("document.getElementById('ioc-status').innerText.includes('251')")
        assert opened.locator("#ioc-rows tr").first.inner_text() != first
        opened.click("#ioc-prev")
        opened.wait_for_function(
            "document.getElementById('ioc-status').innerText.includes('1–250')"
        )
        assert opened.locator("#ioc-rows tr").first.inner_text() == first
        opened.fill("#ioc-limit", "5")
        opened.click("#ioc-scan")
        opened.wait_for_function(
            "document.getElementById('ioc-summary').innerText.includes('5 details kept')",
            timeout=60000,
        )
        assert opened.locator("#ioc-rows tr").count() == 5


def test_client_report_toggles_include_the_actual_findings_and_coverage(findings):  # noqa: F811
    page = findings
    command(page, "coverage-open")
    page.click("#coverage-run")
    page.wait_for_selector("#import-progress-modal.show", state="hidden", timeout=60000)
    page.wait_for_function(
        "document.getElementById('coverage-summary').innerText.length > 0", timeout=60000
    )
    page.keyboard.press("Escape")
    command(page, "report")
    page.select_option("#report-type", "client")
    page.check("#client-findings")
    page.check("#client-coverage")
    page.click('[data-act="report-build"]')
    page.wait_for_function(
        "document.getElementById('report-result').innerText.includes('Client report:')",
        timeout=60000,
    )
    assert f"{GROUPS} finding(s)" in page.inner_text("#report-result")
    html = page.request.get(
        page.url.rstrip("/") + page.get_attribute("#report-result a", "href")
    ).text()
    assert "Collection coverage" in html
    page.uncheck("#client-findings")
    page.uncheck("#client-coverage")
    page.click('[data-act="report-build"]')
    page.wait_for_function(
        "document.getElementById('report-result').innerText.includes('Client report: 0 finding(s)')",
        timeout=60000,
    )
    html = page.request.get(
        page.url.rstrip("/") + page.get_attribute("#report-result a", "href")
    ).text()
    assert "Collection coverage" not in html


def test_shared_rule_styles_can_be_disabled_exported_and_reimported(page):
    import json

    command(page, "rules")
    page.locator('.subtab[data-scope="global"]').click()
    page.wait_for_function("document.querySelector('#rule-column option[value=User]') !== null")
    page.select_option("#rule-column", "User")
    page.select_option("#rule-operator", "eq")
    page.fill("#rule-value", "alice")
    for name in ["italic", "underline", "strikeout"]:
        page.check("#rule-" + name)
    page.fill("#rule-font-family", "monospace")
    page.fill("#rule-font-size", "14")
    for name in ["use-background", "use-foreground", "use-font", "stop"]:
        page.uncheck("#rule-" + name)
        page.check("#rule-" + name)
    page.click('[data-act="rule-add"]')
    page.wait_for_function(
        "document.querySelectorAll('#body tr[data-row][style*=italic]').length === 20"
    )
    with page.expect_download() as downloaded:
        page.click("#rule-global-export")
    data = json.loads(downloaded.value.path().read_text())
    assert "monospace" in json.dumps(data) and "alice" in json.dumps(data)
    page.uncheck("#rule-global-enabled")
    page.wait_for_function(
        "document.querySelectorAll('#body tr[data-row][style*=italic]').length === 0"
    )
    page.check("#rule-global-enabled")
    page.wait_for_function(
        "document.querySelectorAll('#body tr[data-row][style*=italic]').length === 20"
    )
    page.locator("#rules-list [data-rule-remove]").first.click()
    page.wait_for_function(
        "document.querySelectorAll('#rules-list [data-rule-remove]').length === 0"
    )
    with page.expect_file_chooser() as chooser:
        page.click("#rule-global-import")
    chooser.value.set_files(str(downloaded.value.path()))
    page.wait_for_function(
        "document.querySelectorAll('#body tr[data-row][style*=italic]').length === 20"
    )
    styled = page.locator("#body tr[data-row][style*=italic]").first
    assert "underline" in styled.get_attribute("style") and "line-through" in styled.get_attribute(
        "style"
    )
    page.locator("#rules-list [data-rule-remove]").first.click()
    page.wait_for_function(
        "document.querySelectorAll('#rules-list [data-rule-remove]').length === 0"
    )


def test_disabled_rule_appearance_flags_leave_matching_rows_unstyled(page):
    command(page, "rules")
    page.select_option("#rule-column", label="User")
    page.select_option("#rule-operator", "eq")
    page.fill("#rule-value", "bob")
    page.check("#rule-italic")
    for name in ["use-background", "use-foreground", "use-font"]:
        page.uncheck("#rule-" + name)
    page.click('[data-act="rule-add"]')
    page.wait_for_function(
        "document.querySelectorAll('#rules-list [data-rule-remove]').length === 1"
    )
    assert page.locator("#body tr[data-row][style*=italic]").count() == 0


def test_timeline_correlation_button_and_report_selection_chart(timeline):  # noqa: F811
    page = timeline
    page.select_option("#timeline-kind", "ip")
    page.fill("#timeline-search", "10.0.0.1")
    page.check("#timeline-exact")
    page.click("#timeline-correlate")
    page.wait_for_function("timelineState.payload.count === 140", timeout=60000)
    assert all("10.0.0.1" in x for x in page.locator("#timeline-rows tr").all_text_contents())
    page.click('[data-tab="analyses"]')
    from _audit import select

    select(page, 0, 1)
    command(page, "report")
    page.select_option("#report-bookmarks", "false")
    page.check("#report-selection")
    page.check("#report-timeline")
    page.click('[data-act="report-build"]')
    page.wait_for_selector("#report-result a", timeout=60000)
    assert "2 finding(s)" in page.inner_text("#report-result")
    html = page.request.get(
        page.url.rstrip("/") + page.get_attribute("#report-result a", "href")
    ).text()
    assert "data:image/png;base64," in html
