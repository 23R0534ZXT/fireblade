"""The Timeline & correlations tab, control by control, on a case of three sources: seven hundred
dated events, a second dated source, and an inventory that holds no date at all.

Skipped without Playwright and a Chromium; never failed for lack of them.
"""

import re

import pytest
from _audit import status
from conftest import make_case

EVENTS = 700


def _events():
    lines = ["Time,User,SourceIp"]
    for i in range(EVENTS):
        day = 1 + i // 140
        lines.append(
            f"2026-11-{day:02d}T{(i * 7) % 24:02d}:{(i * 13) % 60:02d}:00Z,{['alice', 'bob', 'carol'][i % 3]},10.0.0.{i % 5}"
        )
    return "\n".join(lines) + "\n"


@pytest.fixture()
def timeline(server, request):
    """Three analyses in one case, the timeline tab built and showing everything."""
    import time

    import httpx
    from _browser import browser_page

    base, root, evidence = server
    name = "Timeline " + request.node.name[:40]
    identifier = make_case(server, name, _events())
    folder = evidence / identifier
    (folder / "proxy.csv").write_text(
        "Date,Url\n2026-11-02T08:00:00Z,http://a.example/\n2026-11-03T09:00:00Z,http://b.example/\n"
    )
    (folder / "inventory.csv").write_text("Name,Owner\nlaptop-1,alice\nlaptop-2,bob\n")
    for extra in ("proxy.csv", "inventory.csv"):
        job = httpx.post(
            f"{base}/api/cases/{identifier}/import-jobs",
            data={"source": str(folder / extra), "organization": "files"},
            timeout=60,
        ).json()["job"]
        for _ in range(240):
            if httpx.get(f"{base}/api/import-jobs/{job}").json().get("status") != "running":
                break
            time.sleep(0.2)
    with browser_page(base, name) as page:
        page.click('.tabs .tab:text-is("Timeline & correlations")')
        page.click("#timeline-build")
        try:
            page.wait_for_function(
                "document.getElementById('timeline-info').innerText.includes('/ 704')",
                timeout=60000,
            )
        except Exception as exc:  # noqa: BLE001 - say what the page showed instead
            raise AssertionError(
                "timeline info: " + page.inner_text("#timeline-info") + " | " + status(page)
            ) from exc
        yield page


def _info(page):
    return page.inner_text("#timeline-info")


def _first_row(page):
    return page.locator("#timeline-rows tr").first.inner_text()


def _count(page):
    return int(re.search(r"/\s*(\d+)\s*event", _info(page)).group(1))


def test_the_pages_of_the_timeline_follow_one_another_and_say_when_there_are_no_more(timeline):
    page = timeline
    first = _first_row(page)
    assert "1–250" in _info(page)
    page.click("#timeline-next")
    page.wait_for_function("document.getElementById('timeline-info').innerText.includes('251–500')")
    assert _first_row(page) != first
    page.click("#timeline-prev")
    page.wait_for_function("document.getElementById('timeline-info').innerText.startsWith('1–250')")
    assert _first_row(page) == first
    page.click("#timeline-prev")  # already on the first page: nothing moves, and it says so
    page.wait_for_function("document.getElementById('status').innerText.includes('first page')")
    assert page.inner_text("#timeline-info").startswith("1–250")
    for _ in range(3):
        page.click("#timeline-next")
        page.wait_for_timeout(300)
    page.wait_for_function("document.getElementById('status').innerText.includes('last page')")


def test_a_duration_narrows_the_window_and_back_returns_to_the_one_before(timeline):
    page = timeline
    page.uncheck("#timeline-undated")  # the desktop starts with the undated rows included
    page.click('[data-act="timeline-duration"]')
    page.fill("#ask-input", "2026-11-02T00:30")
    page.click('[data-act="ask-ok"]')
    page.fill("#ask-input", "2026-11-02T23:30")
    page.click('[data-act="ask-ok"]')
    page.wait_for_function("document.getElementById('status').innerText.startsWith('Duration:')")
    page.wait_for_function("!document.getElementById('timeline-info').innerText.includes('/ 704')")
    narrowed = _count(page)
    assert 0 < narrowed < 704
    stamps = page.eval_on_selector_all(
        "#timeline-rows tr", "els => els.map(e => e.children[0].innerText.slice(0, 10))"
    )
    assert set(stamps) == {"2026-11-02"}


def test_a_duration_that_is_not_one_is_refused(timeline):
    page = timeline
    page.click('[data-act="timeline-duration"]')
    page.fill("#ask-input", "2026-11-04T00:00")
    page.click('[data-act="ask-ok"]')
    page.fill("#ask-input", "2026-11-02T00:00")
    page.click('[data-act="ask-ok"]')
    page.wait_for_function(
        "document.getElementById('status').innerText.includes('do not make a duration')"
    )
    assert _count(page) == 704


def test_zoom_out_fit_and_back_move_the_window(timeline):
    page = timeline
    window = lambda: page.inner_text("#timeline-window")  # noqa: E731
    assert "whole extent" in window()
    page.click('[data-act="tl-zoom-in"]')
    page.wait_for_function(
        "!document.getElementById('timeline-window').innerText.includes('whole extent')"
    )
    zoomed = window()
    page.click('[data-act="tl-zoom-in"]')
    page.wait_for_function(f"document.getElementById('timeline-window').innerText !== {zoomed!r}")
    page.click('[data-act="tl-back"]')
    page.wait_for_function(f"document.getElementById('timeline-window').innerText === {zoomed!r}")
    page.click('[data-act="tl-zoom-out"]')
    page.wait_for_function(f"document.getElementById('timeline-window').innerText !== {zoomed!r}")
    page.click('[data-act="tl-fit"]')
    page.wait_for_function(
        "document.getElementById('timeline-window').innerText.includes('whole extent')"
    )


def test_the_lane_shows_one_source_alone_and_all_sources_again(timeline):
    page = timeline
    lanes = page.eval_on_selector_all("#timeline-lane option", "els => els.map(e => e.innerText)")
    assert lanes[0] == "All lanes" and any("proxy.csv" in lane for lane in lanes), lanes
    proxy = next(
        value
        for value in page.eval_on_selector_all(
            "#timeline-lane option", "els => els.map(e => e.value)"
        )
        if value
    )
    page.select_option("#timeline-lane", label=next(lane for lane in lanes if "proxy.csv" in lane))
    page.wait_for_function("document.querySelectorAll('#timeline-rows tr').length === 2")
    assert proxy
    page.select_option("#timeline-lane", "")
    page.wait_for_function("document.querySelectorAll('#timeline-rows tr').length > 2")


def test_a_legend_chip_hides_a_source_and_show_all_sources_brings_it_back(timeline):
    page = timeline
    chips = page.locator("#timeline-legend > *")
    assert chips.count() >= 2
    chips.first.click()
    page.wait_for_timeout(500)
    page.click('[data-act="tl-isolate"]')
    page.wait_for_function(
        "document.getElementById('status').innerText.includes('Every source is shown')"
    )


def test_rows_without_a_date_stay_in_a_duration_only_when_asked(timeline):
    """Without a duration every row is listed; with one, the undated rows follow the checkbox."""
    page = timeline
    page.uncheck("#timeline-undated")  # the desktop starts with them included
    page.click('[data-act="timeline-duration"]')
    page.fill("#ask-input", "2026-11-02T00:00")
    page.click('[data-act="ask-ok"]')
    page.fill("#ask-input", "2026-11-03T00:00")
    page.click('[data-act="ask-ok"]')
    page.wait_for_function("!document.getElementById('timeline-info').innerText.includes('/ 704')")
    without = _count(page)
    page.check("#timeline-undated")
    page.wait_for_function(
        f"!document.getElementById('timeline-info').innerText.includes('/ {without} ')",
        timeout=30000,
    )
    assert _count(page) == without + 2, "the two rows of the inventory join the duration"
    page.uncheck("#timeline-undated")
    page.wait_for_function(
        f"document.getElementById('timeline-info').innerText.includes('/ {without} ')",
        timeout=30000,
    )


def test_the_search_kinds_read_the_same_text_as_a_user_an_address_or_a_path(timeline):
    page = timeline
    options = page.eval_on_selector_all("#timeline-kind option", "els => els.map(e => e.value)")
    assert options == ["text", "user", "ip", "path", "hash"]
    page.select_option("#timeline-kind", "ip")
    page.fill("#timeline-search", "10.0.0.3")
    page.press("#timeline-search", "Enter")
    page.wait_for_function("!document.getElementById('timeline-info').innerText.includes('/ 704')")
    assert _count(page) == EVENTS // 5
    page.select_option("#timeline-kind", "user")
    page.fill("#timeline-search", "alice")
    page.press("#timeline-search", "Enter")
    page.wait_for_function(
        f"document.getElementById('timeline-info').innerText.includes('/ {len([i for i in range(EVENTS) if i % 3 == 0])}')"
    )


def test_each_analysis_can_be_read_with_another_date_column_or_none_at_all(timeline):
    page = timeline
    first = page.locator("#timeline-dates select[data-source]").first
    options = first.locator("option").evaluate_all("els => els.map(e => e.value)")
    assert options[:2] == ["auto", "none"] and "Time" in options, options
    assert "702 dated" in _info(page)
    first.select_option("none")  # the 700 events are read as having no date: only proxy.csv has any
    page.wait_for_function(
        "document.getElementById('timeline-info').innerText.includes('— 2 dated')", timeout=30000
    )
    assert _count(page) == 704, "they stay listed: they are no longer placed in time"
    first.select_option("Time")
    page.wait_for_function(
        "document.getElementById('timeline-info').innerText.includes('— 702 dated')", timeout=30000
    )


def test_the_overview_and_the_chart_answer_the_mouse(timeline):
    page = timeline
    canvas = page.locator("#timeline-overview-canvas")
    box = canvas.bounding_box()
    # click in the overview: the window moves there
    page.mouse.click(box["x"] + box["width"] * 0.25, box["y"] + box["height"] / 2)
    page.wait_for_timeout(500)
    chart = page.locator("#timeline-hist")
    area = chart.bounding_box()
    # drag on the chart: a duration is selected
    page.mouse.move(area["x"] + area["width"] * 0.3, area["y"] + area["height"] * 0.5)
    page.mouse.down()
    page.mouse.move(area["x"] + area["width"] * 0.6, area["y"] + area["height"] * 0.5, steps=6)
    page.mouse.up()
    page.wait_for_timeout(800)
    # the wheel zooms, a double click fits
    page.mouse.wheel(0, -300)
    page.wait_for_timeout(500)
    chart.dblclick()
    page.wait_for_function(
        "document.getElementById('timeline-window').innerText.includes('whole extent')"
    )
    assert status(page)


def test_a_preset_duration_is_centred_and_the_window_slides_with_the_arrows(timeline):
    page = timeline
    page.select_option("#timeline-preset", "86400")
    page.wait_for_function("timelineState.start !== null && timelineState.end !== null")
    assert page.evaluate("timelineState.end - timelineState.start") == 86400 * 10**9
    page.click('[data-act="tl-fit"]')
    page.click('[data-act="tl-zoom-in"]')
    page.click('[data-act="tl-zoom-in"]')
    before = page.evaluate("timelineState.window[0]")
    page.click('[data-act="tl-pan-right"]')
    assert page.evaluate("timelineState.window[0]") > before
    page.click('[data-act="tl-pan-left"]')
    page.click('[data-act="tl-pan-left"]')
    assert page.evaluate("timelineState.window[0]") < before


def test_the_exact_value_and_bookmarks_options_are_offered_and_the_undated_rows_start_included(
    timeline,
):
    page = timeline
    assert page.is_checked("#timeline-undated")
    assert not page.is_checked("#timeline-exact") and not page.is_checked("#timeline-bookmarks")
    page.check("#timeline-bookmarks")
    page.wait_for_function(
        "document.getElementById('timeline-info').innerText.includes('/ 0 ')", timeout=30000
    )
