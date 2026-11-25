"""The workspace around the grid: its pages, the row details and notes, the tree and its search,
the window of analyses (order, close, reopen), closing a case, the display settings and the
update band.

Skipped without Playwright and a Chromium; never failed for lack of them.
"""

import httpx
import pytest
from _audit import answer, command, select
from _browser import browser_page
from conftest import make_case

BIG = 450


def _big_csv():
    lines = ["Id,Host"] + [f"{i},PC{i % 7}" for i in range(BIG)]
    return "\n".join(lines) + "\n"


@pytest.fixture()
def big_page(server, request):
    name = "Big " + request.node.name[:40]
    make_case(server, name, _big_csv())
    with browser_page(server[0], name) as opened:
        opened.context.grant_permissions(["clipboard-read", "clipboard-write"])
        yield opened


def _info(page):
    return page.inner_text("#pageinfo")


def test_the_grid_pages_forward_back_and_to_the_start(big_page):
    page = big_page
    assert _info(page).startswith(f"1–200 / {BIG}")
    page.click("#next")
    page.wait_for_function("document.getElementById('pageinfo').innerText.startsWith('201–400')")
    first = page.locator("#body tr[data-row] td[data-cell='0']").first.inner_text()
    assert first == "200", "the second page starts at the 201st row"
    page.click("#next")
    page.wait_for_function(f"document.getElementById('pageinfo').innerText.startsWith('401–{BIG}')")
    page.click("#next")  # the last page: nothing moves
    page.wait_for_timeout(300)
    assert _info(page).startswith(f"401–{BIG}")
    page.click("#prev")
    page.wait_for_function("document.getElementById('pageinfo').innerText.startsWith('201–400')")
    page.click("#first")
    page.wait_for_function("document.getElementById('pageinfo').innerText.startsWith('1–200')")
    assert page.locator("#body tr[data-row]").count() == 200


def test_the_pages_follow_a_sort_and_a_filter(big_page):
    page = big_page
    page.click("#head tr:first-child th >> text=Host")
    page.fill('#head input[data-filter="1"]', "PC3")
    page.wait_for_function(
        f"document.getElementById('pageinfo').innerText.includes('/ {len([i for i in range(BIG) if i % 7 == 3])}')"
    )
    hosts = page.eval_on_selector_all(
        "#body td[data-cell='1']", "els => [...new Set(els.map(e => e.innerText))]"
    )
    assert hosts == ["PC3"]


# -- row details and notes ---------------------------------------------------------------------


def test_the_details_list_the_columns_of_the_selected_row(page):
    select(page, 3)
    text = page.inner_text("#details")
    for name in ("Time", "Host", "User", "Event", "Path", "Src"):
        assert name in text, name
    assert "PC04" in text and "C:\\Users\\alice\\f3.exe" in text


def test_the_bookmark_note_is_saved_from_the_details_and_removed(page):
    select(page, 1)
    page.fill("#note-input", "suspicious logon")
    page.click("#note-save")
    page.wait_for_function("document.querySelectorAll('#body .cb.marked').length === 1")
    assert page.get_attribute("#body .cb.marked", "title") == "suspicious logon"
    page.click("#note-clear")
    page.wait_for_function("document.querySelectorAll('#body .cb.marked').length === 0")
    page.fill("#note-input", "saved with Enter")
    page.press("#note-input", "Enter")
    page.wait_for_function("document.querySelectorAll('#body .cb.marked').length === 1")


def test_a_note_on_one_cell_is_added_edited_and_removed(page):
    select(page, 2)
    page.locator('[data-cellnote="1"]').click()
    answer(page, "check this host")
    page.wait_for_selector("#details .cellnote")
    assert page.inner_text("#details .cellnote") == "check this host"
    assert page.locator("#body td.noted").count() == 1, "the cell carries a mark in the grid"
    page.locator('[data-cellnote="1"]').click()
    assert page.input_value("#ask-input") == "check this host", "editing starts from the note"
    page.fill("#ask-input", "")
    page.click('[data-act="ask-ok"]')
    page.wait_for_function("document.querySelectorAll('#details .cellnote').length === 0")
    assert page.locator("#body td.noted").count() == 0


def test_the_details_button_of_the_pager_hides_and_shows_the_panel(page):
    assert page.is_visible("#details")
    page.click("#details-toggle")
    page.wait_for_function("document.querySelector('#details').offsetParent === null")
    page.click("#details-toggle")
    page.wait_for_function("document.querySelector('#details').offsetParent !== null")


def test_more_opens_the_view_menu(page):
    page.click('[data-act="open-view-menu"]')
    page.wait_for_selector('.menu.show[data-for="view"]')
    assert page.locator('.menu.show[data-for="view"] [data-act]').count() > 10


# -- the tree and the analyses ------------------------------------------------------------------


def _three(page, server):
    import time

    base, _root, evidence = server
    case = page.evaluate("state.openCase.id")
    for name, text in (
        ("alpha.csv", "A,B\n1,2\n"),
        ("beta.csv", "A,B\n3,4\n5,6\n"),
    ):
        path = evidence / case / name
        path.write_text(text)
        job = httpx.post(
            f"{base}/api/cases/{case}/import-jobs",
            data={"source": str(path), "organization": "files"},
            timeout=60,
        ).json()["job"]
        for _ in range(120):
            if httpx.get(f"{base}/api/import-jobs/{job}").json().get("status") != "running":
                break
            time.sleep(0.2)
    page.evaluate("openCase(state.openCase.id)")
    page.wait_for_function("document.querySelectorAll('#tree .node.child').length === 3")


def _nodes(page):
    return page.eval_on_selector_all(
        "#tree .node.child:not(.closed)", "els => els.map(e => e.innerText.trim())"
    )


def test_the_tree_search_narrows_the_analyses_by_name(page, server):
    _three(page, server)
    page.fill("#tree-search", "bet")
    page.wait_for_function("document.querySelectorAll('#tree .node.child').length === 1")
    assert _nodes(page) == ["beta.csv"]
    page.fill("#tree-search", "zzz")
    page.wait_for_function(
        "document.getElementById('tree').innerText.includes('No analysis matches')"
    )
    page.fill("#tree-search", "")
    page.wait_for_function("document.querySelectorAll('#tree .node.child').length === 3")


def test_the_window_of_analyses_opens_one_reorders_and_saves_the_order(page, server):
    _three(page, server)
    before = _nodes(page)
    command(page, "open-analyses")
    page.wait_for_selector("#analyses-modal.show")
    assert page.locator("#analyses-list [data-analysis-line]").count() == 3
    page.locator("[data-analysis-up]").nth(2).click()  # beta.csv moves above alpha.csv
    page.wait_for_function("document.getElementById('status').innerText.includes('Order changed')")
    page.click("#analyses-save")
    page.wait_for_function("document.getElementById('status').innerText.startsWith('Order saved')")
    after = _nodes(page)
    assert after != before and sorted(after) == sorted(before)
    command(page, "open-analyses")
    page.locator("[data-analysis-open]").nth(2).click()
    page.wait_for_function("document.getElementById('status').innerText.includes('opened')")


def test_a_closed_analysis_is_kept_in_the_case_and_opens_again(page, server):
    _three(page, server)
    command(page, "open-analyses")
    page.locator("[data-analysis-close]").nth(2).click()
    page.wait_for_function("document.getElementById('status').innerText.includes('closed')")
    page.wait_for_function(
        "document.querySelectorAll('#tree .node.child:not(.closed)').length === 2"
    )
    assert "Closed (kept in the case)" in page.inner_text("#tree")
    closed = page.locator("#tree .node.closed").first
    name = closed.inner_text().strip()
    closed.click()
    page.wait_for_function("document.getElementById('status').innerText.includes('opened again')")
    page.wait_for_function(
        "document.querySelectorAll('#tree .node.child:not(.closed)').length === 3"
    )
    assert name in _nodes(page)


def test_closing_the_case_leaves_no_case_open(page):
    command(page, "close-case")
    page.wait_for_function(
        "document.getElementById('casecombo-label').innerText === 'No case open'"
    )
    assert page.locator("#body tr[data-row]").count() == 0
    assert "No case open" in page.inner_text("#tree")


def test_the_toolbar_closes_the_case_too(page):
    page.click('.toolbar .tb:text-is("Close case")')
    page.wait_for_function(
        "document.getElementById('casecombo-label').innerText === 'No case open'"
    )


# -- display settings --------------------------------------------------------------------------


def test_the_display_settings_change_the_density_and_the_palette(page):
    page.click('.toolbar .tb[data-act="display-settings"]')
    page.wait_for_selector("#settings-modal.show")
    assert page.locator("#row-height").count() == 0, (
        "the row height has one window: View > Row height"
    )
    background = lambda: page.evaluate("getComputedStyle(document.body).backgroundColor")  # noqa: E731
    light = background()
    page.select_option("#palette-theme", "dark")
    page.wait_for_function(f"getComputedStyle(document.body).backgroundColor !== {light!r}")
    page.select_option("#palette-theme", "custom")
    page.wait_for_selector("#palette-colours", state="visible")
    page.eval_on_selector(
        '[data-colour="window"]',
        "e => { e.value = '#223344'; e.dispatchEvent(new Event('input', {bubbles: true})); e.dispatchEvent(new Event('change', {bubbles: true})); }",
    )
    page.wait_for_function("getComputedStyle(document.body).backgroundColor === 'rgb(34, 51, 68)'")
    page.click("#palette-reset")
    page.wait_for_function("getComputedStyle(document.body).backgroundColor !== 'rgb(34, 51, 68)'")
    page.select_option("#palette-theme", "light")
    page.wait_for_function(f"getComputedStyle(document.body).backgroundColor === {light!r}")
    page.select_option("#scale", "1.25")
    page.wait_for_function("getComputedStyle(document.querySelector('.app')).zoom === '1.25'")
    page.select_option("#scale", "1")


# -- the update band ---------------------------------------------------------------------------


def _with_update(page, available=True):
    page.route(
        "**/api/version",
        lambda route: route.fulfill(
            json={
                "available": available,
                "latest": "9.9.9",
                "current": "0.8.3",
                "command": [
                    "docker pull ghcr.io/example/fireblade:9.9.9 && docker rm -f fireblade"
                ],
                "note": "Your cases stay in their folder.",
                "url": "https://example.test/releases/9.9.9",
            }
        ),
    )
    page.evaluate("localStorage.removeItem('fb-update-dismissed')")
    page.reload()
    page.wait_for_selector("#menubar")


def test_the_update_band_names_the_version_and_gives_the_command(page):
    _with_update(page)
    page.wait_for_selector("#update-bar", state="visible")
    assert "9.9.9" in page.inner_text("#update-text") and "0.8.3" in page.inner_text("#update-text")
    assert "docker pull" in page.inner_text("#update-command")
    assert "cases stay" in page.get_attribute("#update-command", "title")
    page.click("#update-copy")
    page.wait_for_function("document.getElementById('status').innerText.includes('copied')")
    assert "docker pull" in page.evaluate("navigator.clipboard.readText()")


def test_the_update_link_opens_the_release_and_dismiss_hides_the_band_for_that_version(page):
    _with_update(page)
    page.wait_for_selector("#update-bar", state="visible")
    page.evaluate(
        "(() => { window.__opened = []; window.open = (url) => { window.__opened.push(url); }; })()"
    )
    page.click("#update-link")
    assert page.evaluate("window.__opened") == ["https://example.test/releases/9.9.9"]
    page.click("#update-dismiss")
    page.wait_for_selector("#update-bar", state="hidden")
    page.reload()
    page.wait_for_selector("#menubar")
    page.wait_for_timeout(800)
    assert not page.is_visible("#update-bar"), "a dismissed version stays dismissed"


def test_no_band_when_there_is_nothing_newer(page):
    _with_update(page, available=False)
    page.wait_for_timeout(800)
    assert not page.is_visible("#update-bar")
