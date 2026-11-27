"""The tracking tabs and the hunt window, field by field: actions (every field, every scope),
indicators of every kind, machines and accounts, an indicator list read from a file, a saved hunt
replayed.

Skipped without Playwright and a Chromium; never failed for lack of them.
"""

import datetime

import pytest
from conftest import make_case


def _tab(page, name):
    page.click('.tabs .tab:text-is("Actions & tracking")')
    if name != "actions":
        page.click(f'[data-sub="{name}"]')


def _new_action(page, title, owner="us", priority="medium", kind="analysis"):
    page.fill("#action-title", title)
    page.select_option("#action-owner", owner)
    page.select_option("#action-priority", priority)
    page.select_option("#action-type", kind)
    page.click("#action-add")
    page.wait_for_function(f"document.getElementById('action-rows').innerText.includes({title!r})")


def _row(page, title):
    return page.locator("#action-rows tr[data-action]", has_text=title)


def test_the_editor_changes_every_field_of_an_action(page):
    _tab(page, "actions")
    _new_action(page, "Collect the proxy logs")
    _row(page, "Collect the proxy logs").click()
    page.click("#action-edit")
    page.wait_for_selector("#action-modal.show")
    assert page.input_value("#ae-title") == "Collect the proxy logs"
    assert page.input_value("#ae-status") == "todo"
    page.fill("#ae-title", "Collect the proxy and DNS logs")
    page.select_option("#ae-status", "waiting_client")
    page.select_option("#ae-priority", "critical")
    page.select_option("#ae-type", "coordination")
    page.select_option("#ae-owner", "client")
    page.fill("#ae-person", "R. Martin")
    page.fill("#ae-machine", "PROXY-01")
    page.fill("#ae-date", "2026-11-02")
    page.fill("#ae-due", "2026-11-09")
    page.fill("#ae-reference", "TICKET-4711")
    page.fill("#ae-detail", "Ask the network team for 30 days")
    page.click("#ae-save")
    page.wait_for_function(
        "document.getElementById('action-rows').innerText.includes('Collect the proxy and DNS logs')"
    )
    row = _row(page, "proxy and DNS").inner_text()
    for wanted in (
        "2026-11-02",
        "2026-11-09",
        "Critical",
        "Waiting for the client",
        "Coordination",
        "R. Martin",
    ):
        assert wanted in row, (wanted, row)
    assert "Ask the network team" in page.get_attribute(
        "#action-rows tr[data-action] td[title]", "title"
    )
    # the search reaches the machine, the person and the reference the editor wrote
    for needle in ("PROXY-01", "martin", "TICKET-4711"):
        page.fill("#action-search", needle)
        page.wait_for_function(
            "document.querySelectorAll('#action-rows tr[data-action]').length === 1"
        )
    page.fill("#action-search", "")


def test_a_double_click_opens_the_editor_and_cancel_changes_nothing(page):
    _tab(page, "actions")
    _new_action(page, "Image the laptop")
    _row(page, "Image the laptop").dblclick()
    page.wait_for_selector("#action-modal.show")
    page.fill("#ae-title", "Changed my mind")
    page.click('#action-modal [data-act="settings-close"]')
    page.wait_for_selector("#action-modal", state="hidden")
    assert _row(page, "Image the laptop").count() == 1
    assert _row(page, "Changed my mind").count() == 0


def test_edit_without_a_selection_asks_for_one_and_a_title_is_required(page):
    _tab(page, "actions")
    page.click("#action-edit")
    page.wait_for_function(
        "document.getElementById('status').innerText.includes('Select an action')"
    )
    _new_action(page, "Needs a title")
    _row(page, "Needs a title").click()
    page.click("#action-edit")
    page.fill("#ae-title", "")
    page.click("#ae-save")
    page.wait_for_function("document.getElementById('status').innerText.includes('needs a title')")


def test_an_overdue_action_is_counted_and_a_done_one_is_not(page):
    _tab(page, "actions")
    _new_action(page, "Overdue one")
    _new_action(page, "Done one")
    yesterday = (datetime.date.today() - datetime.timedelta(days=3)).isoformat()
    for title, status, shown in (("Overdue one", "todo", "To do"), ("Done one", "done", "Done")):
        _row(page, title).click()
        page.click("#action-edit")
        page.select_option("#ae-status", status)
        page.fill("#ae-due", yesterday)
        page.click("#ae-save")
        page.wait_for_function(
            f"[...document.querySelectorAll('#action-rows tr')].some(r => r.innerText.includes({title!r}) "
            f"&& r.innerText.includes({yesterday!r}) && r.innerText.includes({shown!r}))"
        )
    page.wait_for_function(
        "document.getElementById('action-summary').innerText.includes('1 overdue')"
    )
    assert "2 action(s) · 1 open" in page.inner_text("#action-summary")


def test_the_scope_every_case_adds_the_actions_of_the_other_cases_and_marks_their_case(
    page, server
):
    import httpx

    other = make_case(server, "Another investigation")
    httpx.post(
        f"{server[0]}/api/cases/{other}/actions",
        json={"title": "Remote action", "owner": "client"},
        timeout=30,
    )
    page.evaluate("loadCases()")
    _tab(page, "actions")
    _new_action(page, "Local action")
    assert "Remote action" not in page.inner_text("#action-rows")
    page.select_option("#action-scope", "all")
    page.wait_for_function(
        "document.getElementById('action-rows').innerText.includes('Remote action')"
    )
    assert "Another investigation" in _row(page, "Remote action").inner_text()
    assert "every case" in page.inner_text("#action-summary")
    # the action of another case is changed where it lives
    _row(page, "Remote action").locator("[data-action-close]").click()
    page.wait_for_function(
        "[...document.querySelectorAll('#action-rows tr')].some(r => r.innerText.includes('Remote action') && r.innerText.includes('Done'))"
    )
    stored = httpx.get(f"{server[0]}/api/cases/{other}/workspace", timeout=30).json()["actions"]
    assert stored[0]["status"] == "done"
    page.select_option("#action-scope", "case")
    page.wait_for_function(
        "!document.getElementById('action-rows').innerText.includes('Remote action')"
    )


def test_a_late_all_cases_request_cannot_replace_the_current_scope(page, server):
    import httpx

    other = make_case(server, "Delayed investigation")
    remote = f"{server[0]}/api/cases/{other}"
    httpx.post(f"{remote}/actions", json={"title": "Delayed action"}).raise_for_status()
    old_payload = httpx.get(f"{remote}/workspace").raise_for_status().json()
    page.evaluate("loadCases()")
    _tab(page, "actions")
    _new_action(page, "Current action")
    held = []
    page.route(f"{remote}/workspace", lambda route: held.append(route))
    with page.expect_request(f"{remote}/workspace"):
        page.select_option("#action-scope", "all")
    current = page.evaluate("state.openCase.id")
    with page.expect_response(f"**/api/cases/{current}/workspace") as fresh:
        page.select_option("#action-scope", "case")
    fresh.value.finished()
    _row(page, "Current action").wait_for()

    with page.expect_response(f"{remote}/workspace") as stale:
        held[0].fulfill(json=old_payload)
    stale.value.finished()
    page.evaluate(
        "new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))"
    )
    assert _row(page, "Delayed action").count() == 0


def test_the_type_priority_and_owner_of_a_new_action_reach_its_row(page):
    _tab(page, "actions")
    for number, (owner, priority, kind, owner_text, priority_text, kind_text) in enumerate(
        [
            ("vendor", "low", "legal", "Vendor", "Low", "Legal"),
            ("unassigned", "high", "meeting", "Unassigned", "High", "Meeting"),
            ("third_party", "critical", "destruction", "Third party", "Critical", "Destruction"),
        ]
    ):
        _new_action(page, f"Row {number}", owner, priority, kind)
        text = _row(page, f"Row {number}").inner_text()
        for wanted in (owner_text, priority_text, kind_text, "To do"):
            assert wanted in text, (wanted, text)


def test_refresh_reads_the_actions_again(page, server):
    import httpx

    _tab(page, "actions")
    case = page.evaluate("state.openCase.id")
    httpx.post(
        f"{server[0]}/api/cases/{case}/actions", json={"title": "Added elsewhere"}, timeout=30
    )
    assert _row(page, "Added elsewhere").count() == 0
    page.click("#action-refresh")
    page.wait_for_function(
        "document.getElementById('action-rows').innerText.includes('Added elsewhere')"
    )


# -- machines and accounts ---------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["machine", "account", "domain", "mailbox", "share"])
def test_every_kind_of_entity_is_declared_edited_and_removed(page, kind):
    _tab(page, "entities")
    options = page.eval_on_selector_all("#entity-kind option", "els => els.map(e => e.value)")
    assert options == ["machine", "account", "domain", "mailbox", "share"]
    page.select_option("#entity-kind", kind)
    page.fill("#entity-label", f"{kind} one")
    page.fill("#entity-hostname", "HOST-01")
    page.fill("#entity-ip", "10.1.2.3")
    page.fill("#entity-os", "Windows 11")
    page.fill("#entity-notes", "Matched source record 14")
    page.check("#entity-compromised")
    page.click("#entity-add")
    page.wait_for_function(
        f"document.getElementById('entity-rows').innerText.includes('{kind} one')"
    )
    row = page.locator("#entity-rows tr[data-entity]").first.inner_text()
    for wanted in (kind, "HOST-01", "10.1.2.3", "Windows 11"):
        assert wanted in row, (wanted, row)
    page.locator("[data-entity-edit]").first.click()
    assert page.inner_text("#entity-add") == "Save" and page.is_visible("#entity-cancel")
    assert page.input_value("#entity-label") == f"{kind} one"
    assert page.input_value("#entity-notes") == "Matched source record 14"
    assert page.locator("#entity-compromised").is_checked()
    page.fill("#entity-label", f"{kind} renamed")
    page.click("#entity-add")
    page.wait_for_function(
        f"document.getElementById('entity-rows').innerText.includes('{kind} renamed')"
    )
    assert page.inner_text("#entity-add") == "Add"
    page.once("dialog", lambda dialog: dialog.accept())
    page.locator("[data-entity-remove]").first.click()
    page.wait_for_function(
        "document.getElementById('entity-rows').innerText.includes('No machine or account')"
    )


def test_cancel_leaves_the_entity_as_it_was(page):
    _tab(page, "entities")
    page.fill("#entity-label", "Keep me")
    page.click("#entity-add")
    page.wait_for_function("document.getElementById('entity-rows').innerText.includes('Keep me')")
    page.locator("[data-entity-edit]").first.click()
    page.fill("#entity-label", "Never saved")
    page.click("#entity-cancel")
    assert page.input_value("#entity-label") == ""
    assert page.inner_text("#entity-add") == "Add"
    assert "Keep me" in page.inner_text("#entity-rows")


# -- indicators --------------------------------------------------------------------------------


def test_indicators_are_recognised_by_kind(page):
    _tab(page, "indicators")
    page.fill(
        "#indicator-values",
        "203.0.113.7\nevil.example\nhttps://evil.example/payload.bin\n"
        + "d41d8cd98f00b204e9800998ecf8427e\n"
        + "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )
    page.click("#indicator-add")
    page.wait_for_function(
        "document.querySelectorAll('#indicator-rows tr[data-indicator]').length === 5"
    )
    kinds = page.eval_on_selector_all(
        "#indicator-rows tr[data-indicator]",
        "els => els.map(e => e.children[0].innerText.toLowerCase())",
    )
    assert sorted(kinds) == ["domain", "ip", "md5", "sha256", "url"], kinds
    assert "5 indicator(s) tracked" in page.inner_text("#indicator-summary")


# -- the hunt window ---------------------------------------------------------------------------


def test_an_indicator_list_is_read_from_a_text_file(page, tmp_path):
    listing = tmp_path / "iocs.txt"
    listing.write_text("10.0.0.2\n10.0.0.4\nnot an indicator\n10.0.0.2\n")
    page.click('.tabs .tab:text-is("IOC hunting")')
    with page.expect_file_chooser() as chooser:
        page.click("#ioc-file-open")
    chooser.value.set_files(str(listing))
    page.wait_for_function(
        "!document.getElementById('ioc-summary').innerText.includes('Nothing scanned yet')",
        timeout=30000,
    )
    summary = page.inner_text("#ioc-summary")
    assert "2 valid IOC(s)" in summary, summary
    assert "1 line(s) rejected" in summary and "1 duplicate(s)" in summary, summary
    # the import reads the list; the hunt is a gesture of its own
    page.click("#ioc-scan")
    page.wait_for_function(
        "document.getElementById('ioc-summary').innerText.includes('24 details kept')",
        timeout=60000,
    )


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("list.csv", "indicator,label\n10.0.0.1,first\n"),
        ("list.tsv", "indicator\tlabel\n10.0.0.1\tfirst\n"),
    ],
)
def test_a_csv_or_tsv_list_is_read_by_its_own_format(page, tmp_path, name, content):
    listing = tmp_path / name
    listing.write_text(content)
    page.click('.tabs .tab:text-is("IOC hunting")')
    page.set_input_files("#ioc-file", str(listing))
    page.wait_for_function("document.getElementById('ioc-input').value.includes('10.0.0.1')")
    page.click("#ioc-scan")
    page.wait_for_function(
        "document.getElementById('ioc-summary').innerText.includes('12 details kept')",
        timeout=60000,
    )


def test_a_saved_hunt_is_listed_and_replayed(page):
    page.click('.tabs .tab:text-is("IOC hunting")')
    page.fill("#ioc-input", "10.0.0.2")
    page.click("#ioc-scan")
    page.wait_for_function(
        "document.getElementById('ioc-summary').innerText.includes('12 details kept')"
    )
    page.fill("#ioc-input", "")
    page.focus("#ioc-history")
    page.wait_for_function("document.querySelectorAll('#ioc-history option').length > 1")
    value = page.eval_on_selector("#ioc-history option:nth-child(2)", "e => e.value")
    page.select_option("#ioc-history", value)
    page.wait_for_function("document.getElementById('ioc-input').value.includes('10.0.0.2')")
    assert "10.0.0.2" in page.input_value("#ioc-input")
    assert page.locator("#ioc-rows tr").count() >= 1
