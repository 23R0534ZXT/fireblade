"""More of what the desktop offers and the Host now has: the client and mission, the findings level."""

import httpx
from test_browser_findings import GROUPS, findings  # noqa: F401 - the fixture


def test_the_client_and_mission_are_written_and_read_back(page):
    page.click('.tabs .tab:text-is("Actions & tracking")')
    page.click("#client-open")
    page.wait_for_selector("#client-modal.show")
    page.fill("#cm-name", "ACME Corp")
    page.fill("#cm-reference", "IR-2026-14")
    page.fill("#cm-lead", "R. Doe")
    page.fill("#cm-start", "2026-11-01")
    page.fill("#cm-notes", "Scope: finance VLAN")
    page.click("#client-save")
    page.wait_for_function("!document.querySelector('#client-modal.show')")
    case = page.evaluate("state.openCase.id")
    base = page.evaluate("location.origin")
    saved = httpx.get(f"{base}/api/cases/{case}/client", timeout=30).json()
    assert saved["client"]["name"] == "ACME Corp" and saved["client"]["reference"] == "IR-2026-14"
    assert saved["engagement"]["lead"] == "R. Doe" and saved["engagement"]["start"] == "2026-11-01"
    page.click("#client-open")
    page.wait_for_function("document.getElementById('cm-name').value === 'ACME Corp'")


def test_a_bad_date_in_the_mission_is_refused_and_said(page):
    page.click('.tabs .tab:text-is("Actions & tracking")')
    page.click("#client-open")
    page.fill("#cm-start", "not a date")
    page.click("#client-save")
    page.wait_for_function("document.getElementById('cm-result').innerText.length > 0")
    assert page.is_visible("#client-modal.show")


def test_the_findings_can_be_limited_to_a_level_and_above(findings):  # noqa: F811
    page = findings
    assert page.locator("#hayabusa-rows tr").count() == GROUPS
    page.select_option("#finding-level", "critical")
    page.wait_for_function("document.querySelectorAll('#hayabusa-rows tr').length === 1")
    page.select_option("#finding-level", "high")
    page.wait_for_function("document.querySelectorAll('#hayabusa-rows tr').length === 3")
    page.select_option("#finding-level", "medium")
    page.wait_for_function("document.querySelectorAll('#hayabusa-rows tr').length === 4")
    page.select_option("#finding-level", "")
    page.wait_for_function(f"document.querySelectorAll('#hayabusa-rows tr').length === {GROUPS}")


def test_the_preferences_offer_the_desktops_choices_and_keep_them(page):
    page.evaluate("void openPreferences()")
    page.wait_for_selector("#prefs-modal.show")
    for control in (
        "prefs-date-pattern",
        "prefs-details",
        "prefs-right-copy",
        "prefs-pins",
        "prefs-auto-profile",
        "prefs-memory",
        "prefs-query-threads",
        "prefs-parsing-threads",
    ):
        assert page.is_visible(f"#{control}") or page.locator(f"#{control}").count() == 1, control
    page.fill("#prefs-memory", "1536")
    page.press("#prefs-memory", "Tab")
    page.wait_for_timeout(500)
    base = page.evaluate("location.origin")
    assert httpx.get(f"{base}/api/preferences", timeout=30).json()["resource_memory_mb"] == 1536
    httpx.put(f"{base}/api/preferences", json={}, timeout=30)  # automatic again


def test_the_details_can_sit_on_the_right_or_at_the_top(page):
    page.evaluate("void openPreferences()")
    page.select_option("#prefs-details", "right")
    assert "details-right" in page.get_attribute("#analysis-view", "class")
    box = page.locator("#details").bounding_box()
    grid = page.locator("#analysis-view > .gridwrap").bounding_box()
    assert box["x"] >= grid["x"] + grid["width"] - 2, (box, grid)
    page.select_option("#prefs-details", "top")
    assert (
        page.locator("#details").bounding_box()["y"]
        < page.locator("#analysis-view > .gridwrap").bounding_box()["y"]
    )
    page.select_option("#prefs-details", "bottom")
    assert (
        page.locator("#details").bounding_box()["y"]
        > page.locator("#analysis-view > .gridwrap").bounding_box()["y"]
    )


def test_a_right_click_copies_the_cell_when_the_preference_says_so_and_shift_opens_the_menu(page):
    page.evaluate("copyPrefs.rightCopy = true")
    page.locator("#body tr[data-row]").first.locator("td[data-cell='2']").click(button="right")
    page.wait_for_function("document.getElementById('status').innerText.length > 0")
    assert page.locator("#row-menu").is_hidden()
    page.locator("#body tr[data-row]").first.locator("td[data-cell='2']").click(
        button="right", modifiers=["Shift"]
    )
    assert page.locator("#row-menu").is_visible()
    page.evaluate("copyPrefs.rightCopy = false")


def test_the_date_format_preference_rewrites_the_date_columns_the_profile_names(findings):  # noqa: F811
    """The desktop reformats the date columns of the view (a recognised profile names them)."""
    page = findings
    page.click('.tabs .tab:text-is("Analyses")')
    page.wait_for_selector("#body tr[data-row]")
    assert page.evaluate("state.timestamps.includes(0)")  # the Timestamp column of the profile
    cell = "document.querySelector('#body tr[data-row] td[data-cell=\"0\"]')"
    page.wait_for_function(f"{cell}.innerText === '2026-11-02T10:00:00Z'")
    page.evaluate("copyPrefs.dateFormat = 'iso'; void loadRows(false)")
    page.wait_for_function(f"{cell}.innerText === '2026-11-02 10:00:00Z'")
    page.evaluate("copyPrefs.dateFormat = 'iso7'; void loadRows(false)")
    page.wait_for_function(f"{cell}.innerText === '2026-11-02 10:00:00.0000000Z'")
    page.evaluate(
        "copyPrefs.dateFormat = 'custom'; copyPrefs.pattern = 'dd/MM/yyyy HH:mm'; void loadRows(false)"
    )
    page.wait_for_function(f"{cell}.innerText === '02/11/2026 10:00'")
    page.evaluate("copyPrefs.dateFormat = 'source'; void loadRows(false)")
    page.wait_for_function(f"{cell}.innerText === '2026-11-02T10:00:00Z'")


def test_the_columns_can_be_reordered_and_widened_and_the_order_is_kept(page):
    page.evaluate("void openColumnManager()")
    page.wait_for_selector("#columns-modal.show")
    before = page.evaluate("visibleColumns().map(c => c.name)")
    assert before[:3] == ["__row_id", "Time", "Host"], before
    page.click('#columns-list button[data-move="1"][data-dir="1"]')  # Host moves after User
    page.wait_for_function(
        "visibleColumns().map(c => c.name).indexOf('Host') > visibleColumns().map(c => c.name).indexOf('User')"
    )
    head = page.eval_on_selector_all("#head th[data-column]", "els => els.map(e => e.title)")
    assert head.index("Host") > head.index("User"), head
    page.fill('#columns-list input[data-width="1"]', "333")
    page.press('#columns-list input[data-width="1"]', "Tab")
    page.wait_for_function("state.widths[1] === 333")
    page.wait_for_timeout(900)  # the layout is saved a moment after the last change
    base = page.evaluate("location.origin")
    case, analysis = page.evaluate("[state.openCase.id, state.analysis]")
    saved = httpx.get(f"{base}/api/cases/{case}/analyses/{analysis}/display", timeout=30).json()
    assert saved["order"][:3] == [0, 2, 1] and saved["widths"]["1"] == 333, saved
    page.reload()
    page.wait_for_selector("#menubar")


def test_a_rule_can_set_the_font_and_choose_which_parts_it_applies(page):
    css = page.evaluate(
        """() => ruleCss({background: '#ff0000', foreground: '#00ff00', bold: true, italic: true,
                           underline: true, strikeout: true, font_family: 'Georgia', font_size: 12,
                           use_background: true, use_foreground: false, use_font: true})"""
    )
    assert "background:#ff0000" in css and "color:" not in css.replace("background", "")
    assert "font-weight:600" in css and "font-style:italic" in css
    assert "text-decoration:underline line-through" in css
    assert "font-family:Georgia" in css and "font-size:12pt" in css
    plain = page.evaluate(
        "ruleCss({background: '#fff', foreground: '#000', use_font: false, bold: true})"
    )
    assert "font-weight" not in plain


def test_the_extra_rule_fields_are_kept_by_the_server(page):
    import httpx

    base = page.evaluate("location.origin")
    case, analysis = page.evaluate("[state.openCase.id, state.analysis]")
    rule = {
        "column": 2,
        "operator": "eq",
        "value": "alice",
        "background": "#fce2e2",
        "foreground": "#202020",
        "italic": True,
        "underline": True,
        "strikeout": True,
        "font_family": "Georgia",
        "font_size": 11,
        "stop_if_true": False,
        "use_font": False,
        "stat_percent": True,
        "all_source_rows": True,
    }
    answer = httpx.post(
        f"{base}/api/cases/{case}/analyses/{analysis}/rules", json={"rules": [rule]}, timeout=30
    )
    assert answer.status_code == 200, answer.text
    kept = httpx.get(f"{base}/api/cases/{case}/analyses/{analysis}/rules", timeout=30).json()[
        "rules"
    ][0]
    for key in ("italic", "underline", "strikeout", "stat_percent", "all_source_rows"):
        assert kept[key] is True, (key, kept)
    assert kept["stop_if_true"] is False and kept["use_font"] is False
    assert kept["font_family"] == "Georgia" and kept["font_size"] == 11


def test_the_tree_groups_by_collection_and_family_and_can_be_folded(page):
    tree = page.locator("#tree")
    groups = page.locator("#tree .node.grp")
    assert groups.count() == 1  # one analysis needs no redundant family level
    assert "(1)" in groups.first.inner_text()
    assert page.locator("#tree .node.child").count() == 1
    page.click("#tree-collapse")
    assert page.locator("#tree .node.child").count() == 0
    page.click("#tree-expand")
    assert page.locator("#tree .node.child").count() == 1
    page.select_option("#tree-mode", "flat")
    assert page.locator("#tree .node.grp").count() == 1  # the collection only
    assert page.locator("#tree .node.child").count() == 1
    page.select_option("#tree-mode", "families")
    assert tree.inner_text().count("events") >= 1


def test_the_tree_can_sit_on_the_left_or_the_right(page):
    page.evaluate("void openPreferences()")
    pane = page.locator(".pane").bounding_box()
    assert page.locator("#artifacts").bounding_box()["x"] > pane["x"]  # on the right, as it starts
    page.select_option("#prefs-tree", "left")
    assert "tree-left" in page.get_attribute(".work", "class")
    assert (
        page.locator("#artifacts").bounding_box()["x"] < page.locator(".pane").bounding_box()["x"]
    )
    page.select_option("#prefs-tree", "right")
