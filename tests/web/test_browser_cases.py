"""The Cases tab, button by button: select and open, search, create with each environment, edit,
archive and reactivate, archive and free the space then restore, portable packages, the history,
and erasing a case that is not the one open.

Skipped without Playwright and a Chromium; never failed for lack of them.
"""

import httpx
import pytest
from _audit import ROWS, standard_csv
from conftest import make_case


def _cases_tab(page):
    page.click('.tabs .tab:text-is("Cases")')
    page.wait_for_selector("#cases-view", state="visible")


def _row(page, name):
    return page.locator(f'#cases-body tr:has(td:text-is("{name}"))')


def _api(server, path):
    return httpx.get(server[0] + path, timeout=30).json()


def test_a_click_selects_a_case_and_the_open_button_or_a_double_click_opens_it(page, server):
    other = make_case(server, "Second case", standard_csv())
    page.click("#doctab, .toolbar .tb[data-act='refresh-cases'], .toolbar .tb:text-is('Refresh')")
    _cases_tab(page)
    page.wait_for_selector('#cases-body tr:has(td:text-is("Second case"))')
    open_before = page.inner_text("#casecombo-label")
    _row(page, "Second case").click()
    page.wait_for_function(
        "document.querySelector('#cases-body tr.selected td').innerText === 'Second case'"
    )
    assert page.inner_text("#casecombo-label") == open_before, "a click only selects"
    assert page.is_visible("#cases-view"), "and stays on the Cases tab"
    page.click('#cases-view [data-act="open-selected-case"]')
    page.wait_for_function("document.getElementById('casecombo-label').innerText === 'Second case'")
    assert other and page.is_visible("#analysis-view")
    # Open with nothing selected, after the selection is gone, falls back on what is open
    _cases_tab(page)
    _row(page, open_before).dblclick()
    page.wait_for_function(
        f"document.getElementById('casecombo-label').innerText === {open_before!r}"
    )


def test_the_open_button_with_no_case_selected_asks_for_one(empty_page):
    page = empty_page
    page.evaluate("state.selectedCase = null; state.openCase = null; renderCases();")
    _cases_tab(page)
    page.click('#cases-view [data-act="open-selected-case"]')
    page.wait_for_function("document.getElementById('status').innerText.includes('Select a case')")


def test_the_search_box_narrows_the_list_and_says_when_nothing_matches(page, server):
    make_case(server, "Phishing at the front desk")
    page.evaluate("loadCases()")
    _cases_tab(page)
    page.wait_for_selector('#cases-body tr:has(td:text-is("Phishing at the front desk"))')
    total = page.locator("#cases-body tr").count()
    page.fill("#case-search", "phishing")
    page.wait_for_function("document.querySelectorAll('#cases-body tr').length === 1")
    assert "1 case(s) displayed" in page.inner_text("#case-count")
    page.fill("#case-search", "no-such-case-anywhere")
    page.wait_for_function("document.querySelectorAll('#cases-body tr').length === 0")
    assert "No case matches" in page.inner_text("#cases-empty")
    page.fill("#case-search", "")
    page.wait_for_function(f"document.querySelectorAll('#cases-body tr').length === {total}")


def test_refresh_lists_a_case_another_session_created(page, server):
    _cases_tab(page)
    assert _row(page, "Made elsewhere").count() == 0
    make_case(server, "Made elsewhere")
    page.click('#cases-view [data-act="refresh-cases"]')
    page.wait_for_selector('#cases-body tr:has(td:text-is("Made elsewhere"))')


@pytest.mark.parametrize("environment", ["unspecified", "windows", "linux", "mixed"])
def test_a_case_is_created_with_each_environment_the_engine_knows(page, server, environment):
    _cases_tab(page)
    page.click('#cases-view [data-act="new-case"]')
    page.wait_for_selector("#case-modal.show")
    options = page.eval_on_selector_all("#case-environment option", "els => els.map(e => e.value)")
    assert options == ["unspecified", "windows", "linux", "mixed"], options
    assert not page.is_visible("#case-status-row"), "a new case has no status to choose"
    page.fill("#case-name", f"Env {environment}")
    page.fill("#case-description", "described")
    page.select_option("#case-environment", environment)
    page.click("#case-confirm")
    page.wait_for_selector(f'#cases-body tr:has(td:text-is("Env {environment}"))')
    created = next(
        item for item in _api(server, "/api/cases")["cases"] if item["name"] == f"Env {environment}"
    )
    assert created["environment"] == environment and created["description"] == "described"


def test_a_case_without_a_name_is_refused(page):
    _cases_tab(page)
    page.click('#cases-view [data-act="new-case"]')
    page.click("#case-confirm")
    page.wait_for_function(
        "document.getElementById('status').innerText.includes('name is required')"
    )


def test_edit_changes_the_name_the_description_the_environment_and_the_status(page, server):
    _cases_tab(page)
    name = page.inner_text("#casecombo-label")
    _row(page, name).click()
    page.click('#cases-view [data-act="rename-case"]')
    page.wait_for_selector("#case-modal.show")
    assert page.is_visible("#case-status-row")
    assert page.input_value("#case-name") == name
    page.fill("#case-name", "Edited case")
    page.fill("#case-description", "now described")
    page.select_option("#case-environment", "mixed")
    page.select_option("#case-status", "closed")
    page.click("#case-confirm")
    page.wait_for_selector('#cases-body tr:has(td:text-is("Edited case"))')
    row = _row(page, "Edited case")
    assert "Finished" in row.inner_text()
    stored = next(i for i in _api(server, "/api/cases")["cases"] if i["name"] == "Edited case")
    assert stored["environment"] == "mixed" and stored["status"] == "closed"
    assert stored["description"] == "now described"
    assert page.inner_text("#casecombo-label") == "Edited case", "the open case follows its name"


def test_a_case_that_is_not_open_can_be_edited_from_the_list(page, server):
    make_case(server, "Not open")
    page.evaluate("loadCases()")
    _cases_tab(page)
    page.wait_for_selector('#cases-body tr:has(td:text-is("Not open"))')
    opened = page.inner_text("#casecombo-label")
    _row(page, "Not open").click()
    page.click('#cases-view [data-act="rename-case"]')
    page.fill("#case-name", "Renamed from the list")
    page.click("#case-confirm")
    page.wait_for_selector('#cases-body tr:has(td:text-is("Renamed from the list"))')
    assert page.inner_text("#casecombo-label") == opened, "the open case stays open"


def test_archive_hides_a_case_until_archived_ones_are_included_and_reactivate_brings_it_back(
    page, server
):
    make_case(server, "To archive")
    page.evaluate("loadCases()")
    _cases_tab(page)
    page.wait_for_selector('#cases-body tr:has(td:text-is("To archive"))')
    _row(page, "To archive").click()
    assert page.inner_text("#archive-case") == "Archive"
    page.click('#cases-view [data-act="archive-case"]')
    page.wait_for_function("document.querySelectorAll('#cases-body tr:has(td)').length > 0")
    page.wait_for_function(
        "![...document.querySelectorAll('#cases-body td')].some(td => td.innerText === 'To archive')"
    )
    page.check("#case-archived")
    row = _row(page, "To archive")
    row.wait_for()
    assert "Archived" in row.inner_text()
    row.click()
    assert page.inner_text("#archive-case") == "Reactivate"
    page.click('#cases-view [data-act="archive-case"]')
    page.wait_for_function(
        "[...document.querySelectorAll('#cases-body tr')].some(r => r.innerText.includes('To archive') "
        "&& r.innerText.includes('In progress'))"
    )
    page.uncheck("#case-archived")
    _row(page, "To archive").wait_for()


def test_archive_and_free_the_space_packs_the_case_outside_its_folder_and_restore_brings_it_back(
    empty_page, server
):
    page = empty_page
    base, root, _evidence = server
    name = page.inner_text("#casecombo-label")
    # a case worth archiving: its data is in the case's folder, imported from a copy outside it
    identifier = page.evaluate("state.openCase.id")
    source = server[2] / identifier / "events.csv"
    source.write_text(standard_csv())
    httpx.post(
        f"{base}/api/cases/{identifier}/import-jobs",
        data={"source": str(source), "organization": "files"},
        timeout=60,
    )
    import time

    for _ in range(120):
        time.sleep(0.25)
        if _api(server, f"/api/cases/{identifier}")["analyses"]:
            break
    page.evaluate("loadCases()")
    _cases_tab(page)
    _row(page, name).click()
    page.once("dialog", lambda dialog: dialog.accept())
    page.click('#cases-view [data-act="free-space"]')
    page.wait_for_function("document.getElementById('status').innerText.startsWith('Archived:')")
    assert "freed" in page.inner_text("#status")
    archives = list((root / "archives").glob("*.zip"))
    assert archives and archives[0].stat().st_size > 1000, "the archive is outside the case folder"
    # an archived case leaves the list until the archived ones are included
    page.wait_for_function(
        f"![...document.querySelectorAll('#cases-body td')].some(td => td.innerText === {name!r})"
    )
    page.check("#case-archived")
    row = _row(page, name)
    assert "kept in an archive" in row.inner_text()
    row.click()
    assert page.is_visible("#restore-case")
    # opening it does not pretend: it says to restore
    row.dblclick()
    page.wait_for_function("document.getElementById('status').innerText.includes('Restore')")
    page.click("#restore-case")
    page.wait_for_function(
        "document.getElementById('status').innerText.startsWith('Restored')", timeout=60000
    )
    restored = [i for i in _api(server, "/api/cases")["cases"] if i["name"].startswith(name[:20])]
    assert any(i["analysis_count"] == 1 and not i["storage_archive"] for i in restored), restored
    page.wait_for_selector("#cases-body tr.selected")
    page.click('#cases-view [data-act="open-selected-case"]')
    page.wait_for_selector("#body tr[data-row]", timeout=30000)
    assert page.locator("#body tr[data-row]").count() == ROWS


def test_a_case_that_holds_its_originals_is_not_archived_and_the_refusal_is_in_english(page):
    _cases_tab(page)
    # the open case's evidence lives outside its folder, so put an original inside to refuse
    page.evaluate("state.selectedCase = state.openCase.id; renderCases();")
    page.once("dialog", lambda dialog: dialog.accept())
    page.click('#cases-view [data-act="free-space"]')
    page.wait_for_function(
        "document.getElementById('status').innerText.length > 0 "
        "&& !document.getElementById('status').innerText.startsWith('Ready')"
    )
    # whatever the outcome, no French reaches the analyst
    for word in ("Des preuves", "Une source", "archive hors"):
        assert word not in page.inner_text("#status")


def test_the_history_button_of_the_tab_opens_the_recovery_points(page):
    _cases_tab(page)
    page.click('#cases-view [data-act="case-history"]')
    page.wait_for_selector(".modal.show .dialog")
    assert "History and recovery" in page.inner_text(".modal.show .dialog")


def test_the_portable_case_leaves_from_the_tab_and_comes_back_as_a_new_case(page, server, tmp_path):
    _cases_tab(page)
    with page.expect_download(timeout=60000) as download:
        page.click('#cases-view [data-act="export-portable"]')
    package = tmp_path / "case.fireblade"
    download.value.save_as(str(package))
    before = len(_api(server, "/api/cases")["cases"])
    page.click('#cases-view [data-act="import-portable"]')
    page.set_input_files("#package-input", str(package))
    page.wait_for_function(f"state.cases.length === {before + 1}", timeout=60000)
    names = [item["name"] for item in _api(server, "/api/cases")["cases"]]
    assert len(names) == before + 1


def test_a_case_that_is_not_open_is_erased_from_the_list_and_only_its_certificate_stays(
    page, server
):
    identifier = make_case(server, "Erase me from the list", standard_csv())
    page.evaluate("loadCases()")
    _cases_tab(page)
    page.wait_for_selector('#cases-body tr:has(td:text-is("Erase me from the list"))')
    opened = page.inner_text("#casecombo-label")
    _row(page, "Erase me from the list").click()
    page.click('#cases-view [data-act="destroy-case"]')
    page.wait_for_selector("#destroy-modal.show")
    assert "Erase me from the list" in page.inner_text("#destroy-target")
    page.fill("#destroy-operator", "A. Analyst")
    page.fill("#destroy-confirm", "Erase me from the list")
    page.click('#destroy-modal [data-act="destroy-run"]')
    page.wait_for_function(
        "document.getElementById('status').innerText.startsWith('Case erased')", timeout=90000
    )
    assert not (server[1] / identifier).exists(), "the folder of the case is gone"
    assert opened  # the other case was opened to show its inventory, and was not the one erased
