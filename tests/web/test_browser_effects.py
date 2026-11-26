"""Windows whose controls must change what is on screen, not only open and close.

Each test presses a control and then reads the result against an answer worked out from the data:
the date a format must give, the group an interval must make, the order a summary must impose.
A control that is wired to nothing leaves the screen as it was, and these tests fail on it.
"""

import re

import pytest
from _audit import column_values, command, headers
from conftest import make_case

# 2026-11-03 14:25:36 UTC, written in every format the derived-column window reads
EXACT = "2026-11-03T14:25:36.000000000Z"
DATES = {
    "iso": "2026-11-03T14:25:36Z",
    "mdy": "11/03/2026 14:25:36",
    "dmy": "03/11/2026 14:25:36",
    "invariant": "2026-11-03 14:25:36",
    "unix_s": "1793715936",
    "unix_ms": "1793715936000",
    "unix_us": "1793715936000000",
    "unix_ns": "1793715936000000000",
    "filetime": "134381895360000000",
    "webkit": "13438189536000000",
    "dotnet": "639293127360000000",
}
OLE_NOON = "46329.5"  # 2026-11-03 12:00:00, exactly representable


def _dates_csv():
    names = [*DATES, "ole", "naive", "offset", "day", "clock"]
    values = [
        *DATES.values(),
        OLE_NOON,
        "2026-11-03 14:25:36",
        "2026-11-03T14:25:36+01:00",
        "2026-11-03",
        "14:25:36",
    ]
    return ",".join(names) + "\n" + ",".join(values) + "\n"


@pytest.fixture()
def dates(server, request):
    from _browser import browser_page

    name = "Dates " + request.node.name[:40]
    make_case(server, name, _dates_csv())
    with browser_page(server[0], name) as page:
        yield page


def _derive(page, name, source, fmt="iso", zone=None, time=None):
    command(page, "derived")
    page.wait_for_function("document.querySelectorAll('#derived-format option').length > 1")
    page.fill("#derived-name", name)
    page.select_option("#derived-source", label=source)
    page.select_option("#derived-time", label=time) if time else None
    page.select_option("#derived-format", fmt)
    if zone is not None:
        page.fill("#derived-zone", zone)
    page.click('[data-act="derived-add"]')
    page.wait_for_function(
        "(name) => [...document.querySelectorAll('#head tr:first-child th')]"
        ".some(t => t.innerText.trim().startsWith(name))",
        arg=name,
    )
    page.wait_for_function("document.querySelectorAll('#body tr[data-row]').length > 0")
    return column_values(page, name)


def test_the_derived_window_offers_what_the_core_can_read(dates):
    command(dates, "derived")
    dates.wait_for_function("document.querySelectorAll('#derived-format option').length > 1")
    formats = dates.eval_on_selector_all("#derived-format option", "els => els.map(e => e.value)")
    assert formats == [*DATES, "ole"] or set(formats) == {*DATES, "ole"}, formats
    labels = dates.eval_on_selector_all(
        "#derived-format option", "els => els.map(e => e.innerText)"
    )
    assert not [label for label in labels if re.search(r"[éèàç]|depuis|secondes", label)], labels
    operations = dates.eval_on_selector_all(
        "#derived-operation option", "els => els.map(e => e.value)"
    )
    assert operations == ["timestamp", "expression"], "the other two never had a desktop dialog"
    zones = dates.eval_on_selector_all("#derived-zones option", "els => els.map(e => e.value)")
    assert zones[0] == "UTC" and "Europe/Paris" in zones and "Pacific Standard Time" in zones
    dates.select_option("#derived-operation", "expression")
    assert dates.is_hidden("#derived-zone-row") and dates.is_visible("#derived-expression-row")
    dates.select_option("#derived-operation", "timestamp")
    assert dates.is_visible("#derived-zone-row") and dates.is_hidden("#derived-expression-row")


@pytest.mark.parametrize("fmt", [*DATES])
def test_a_date_is_read_in_the_format_it_was_written_in(dates, fmt):
    assert _derive(dates, "Read", fmt, fmt) == [EXACT]


def test_an_ole_date_is_read_to_the_second(dates):
    assert _derive(dates, "OleRead", "ole", "ole") == ["2026-11-03T12:00:00.000000000Z"]


@pytest.mark.parametrize(
    ("zone", "expected"),
    [
        ("UTC", "14:25:36"),
        ("Europe/Paris", "13:25:36"),
        ("America/New_York", "19:25:36"),
        ("Pacific Standard Time", "22:25:36"),
        ("+02:00", "12:25:36"),
    ],
)
def test_a_date_without_an_offset_is_read_in_the_zone_that_was_chosen(dates, zone, expected):
    shown = _derive(dates, "Zoned", "naive", "iso", zone)
    assert shown == [f"2026-11-03T{expected}.000000000Z"], shown


def test_a_date_with_an_offset_keeps_its_own_zone_whatever_zone_is_chosen(dates):
    assert _derive(dates, "Own", "offset", "iso", "America/New_York") == [
        "2026-11-03T13:25:36.000000000Z"
    ]


def test_a_separate_time_column_is_joined_to_the_date(dates):
    assert _derive(dates, "Joined", "day", "iso", "Europe/Paris", time="clock") == [
        "2026-11-03T13:25:36.000000000Z"
    ]


def test_a_zone_that_does_not_exist_is_refused_and_leaves_the_analysis_readable(dates):
    before = headers(dates)
    command(dates, "derived")
    dates.wait_for_function("document.querySelectorAll('#derived-format option').length > 1")
    dates.fill("#derived-name", "Nowhere")
    dates.select_option("#derived-source", label="naive")
    dates.fill("#derived-zone", "Mars/Olympus")
    dates.click('[data-act="derived-add"]')
    dates.wait_for_function(
        "document.getElementById('status').innerText.includes('Unknown time zone: Mars/Olympus')",
        timeout=15000,
    )
    assert headers(dates) == before, "no column was added"
    # the analysis still answers: a second page of rows, a derived column that is valid
    assert _derive(dates, "Later", "naive", "iso", "Europe/Paris") == [
        "2026-11-03T13:25:36.000000000Z"
    ]


# -- Grouping a date by an interval --------------------------------------------------------------

# The standard case: sixty rows, twelve a day on 2026-11-01..05, the first of each day at 10:00.
INTERVALS = [
    ("", 60, "2026-11-01T10:00:00Z"),
    ("year", 1, "2026"),
    ("quarter", 1, "2026-Q4"),
    ("month", 1, "2026-11"),
    ("week", 2, "2026-W45"),  # Monday 2 to Thursday 5 November: 48 rows; Sunday 1st: 12
    ("day", 5, "2026-11-01"),
    ("hour", 10, "2026-11-01 10:00"),
    ("minute", 60, "2026-11-01 10:00"),
    ("second", 60, "2026-11-01 10:00:00"),
]


@pytest.mark.parametrize(("interval", "groups", "first"), INTERVALS)
def test_a_date_is_grouped_by_the_interval_chosen(page, interval, groups, first):
    command(page, "group-column")
    page.locator("#group-levels").get_by_role("checkbox", name="Time", exact=True).check()
    page.select_option("#group-interval", interval)
    page.click('[data-act="group-apply"]')
    page.wait_for_function(
        f"document.getElementById('pageinfo').innerText.includes('/ {groups} group')"
    )
    assert "60 row(s)" in page.inner_text("#pageinfo")
    labels = page.eval_on_selector_all(
        "#body tr[data-group]", "els => els.map(e => e.dataset.value)"
    )
    assert first in labels, labels
    counts = page.eval_on_selector_all(
        "#body tr[data-group]", "els => els.map(e => Number(e.lastElementChild.innerText))"
    )
    assert sum(counts) == 60


def test_the_weeks_of_the_standard_case_hold_the_rows_of_their_days(page):
    command(page, "group-column")
    page.locator("#group-levels").get_by_role("checkbox", name="Time", exact=True).check()
    page.select_option("#group-interval", "week")
    page.click('[data-act="group-apply"]')
    page.wait_for_selector("#body tr[data-group]")
    held = page.eval_on_selector_all(
        "#body tr[data-group]",
        "els => Object.fromEntries(els.map(e => [e.dataset.value, Number(e.lastElementChild.innerText)]))",
    )
    assert held == {"2026-W44": 12, "2026-W45": 48}, held


# -- Group summaries ---------------------------------------------------------------------------------

VALUES = [1, 2, 3, 4, 10, 20, 30, 40, 100, 200, 300, 400]


@pytest.fixture()
def numbers(server, request):
    """Three groups of four numbers: A holds 1-4, B 10-40, C 100-400."""
    from _browser import browser_page

    name = "Numbers " + request.node.name[:40]
    lines = ["Name,Group,Value"] + [f"n{i},{'ABC'[i // 4]},{VALUES[i]}" for i in range(12)]
    make_case(server, name, "\n".join(lines) + "\n")
    with browser_page(server[0], name) as page:
        yield page


def _group_by(page, column):
    command(page, "group-column")
    page.locator("#group-levels").get_by_role("checkbox", name=column, exact=True).check()
    page.click('[data-act="group-apply"]')
    page.wait_for_selector("#body tr[data-group]")


def _summarise(page, *operations, order=None, which=None, descending=True):
    command(page, "summaries")
    while page.locator("#summary-rows [data-summary-remove]").count():
        page.locator("#summary-rows [data-summary-remove]").first.click()
    for operation in operations:
        page.click("#summary-add")
        row = page.locator("#summary-rows tr").last
        row.locator("[data-summary-column]").select_option(label="Value")
        row.locator("[data-summary-operation]").select_option(operation)
    if order is not None:
        page.select_option("#summary-order", order)
    if which is not None:
        page.select_option("#summary-which", str(which))
    page.set_checked("#summary-desc", descending)
    page.evaluate("document.getElementById('status').innerText = ''")
    page.click("#summary-apply")
    page.wait_for_function("document.getElementById('status').innerText.includes('group summar')")
    page.wait_for_selector("#body tr[data-group]")


def _group_table(page):
    """{group: [summary values as numbers]} as the grouped grid shows them."""
    page.wait_for_selector("#body tr[data-group]")
    table = {}
    for row in page.locator("#body tr[data-group]").all():
        cells = [cell.inner_text() for cell in row.locator("td").all()]
        table[row.get_attribute("data-value")] = [float(value) for value in cells[3:]]
    return table


def test_a_group_summary_computes_what_it_says_for_each_group(numbers):
    _group_by(numbers, "Group")
    _summarise(numbers, "rows", "count", "distinct", "sum", "avg", "min", "max")
    names = headers(numbers)
    assert names[-7:] == [
        "rows Value",
        "count Value",
        "distinct Value",
        "sum Value",
        "avg Value",
        "min Value",
        "max Value",
    ]
    table = _group_table(numbers)
    for group, low in (("A", 1), ("B", 10), ("C", 100)):
        values = [value * low for value in (1, 2, 3, 4)]
        assert table[group][-7:] == [4, 4, 4, sum(values), sum(values) / 4, low, 4 * low], table


def test_the_groups_are_ordered_by_a_summary_in_both_directions(numbers):
    _group_by(numbers, "Group")
    _summarise(numbers, "sum", order="summary", which=0, descending=True)
    order = numbers.eval_on_selector_all(
        "#body tr[data-group]", "els => els.map(e => e.dataset.value)"
    )
    assert order == ["C", "B", "A"], order
    _summarise(numbers, "sum", order="summary", which=0, descending=False)
    order = numbers.eval_on_selector_all(
        "#body tr[data-group]", "els => els.map(e => e.dataset.value)"
    )
    assert order == ["A", "B", "C"], order


def test_the_groups_are_ordered_by_their_value_when_asked(numbers):
    _group_by(numbers, "Group")
    _summarise(numbers, "sum", order="value", descending=False)
    assert numbers.eval_on_selector_all(
        "#body tr[data-group]", "els => els.map(e => e.dataset.value)"
    ) == ["A", "B", "C"]
    _summarise(numbers, "sum", order="value", descending=True)
    assert numbers.eval_on_selector_all(
        "#body tr[data-group]", "els => els.map(e => e.dataset.value)"
    ) == ["C", "B", "A"]


def test_the_summary_menu_offers_one_choice_per_summary(numbers):
    _group_by(numbers, "Group")
    command(numbers, "summaries")
    numbers.click("#summary-add")
    numbers.click("#summary-add")
    numbers.select_option("#summary-order", "summary")
    options = numbers.eval_on_selector_all(
        "#summary-which option", "els => els.map(e => e.innerText)"
    )
    assert len(options) == numbers.locator("#summary-rows tr").count() >= 3
    numbers.locator("#summary-rows [data-summary-remove]").last.click()
    assert numbers.locator("#summary-which option").count() == len(options) - 1
    numbers.select_option("#summary-order", "")
    assert numbers.is_hidden("#summary-which")
    numbers.click('.modal.show [data-act="settings-close"]')


# -- The named windows of the date filter ------------------------------------------------------------


def _reference_windows(today):
    """Every named window as [low, high) over dates, worked out here from the calendar alone."""
    from datetime import date, timedelta

    def month(day, shift):
        index = day.year * 12 + day.month - 1 + shift
        return date(index // 12, index % 12 + 1, 1)

    week = today - timedelta(days=today.weekday())
    this_month = month(today, 0)
    year = date(today.year, 1, 1)
    day = timedelta(days=1)
    windows = {
        "Today": (today, today + day),
        "Yesterday": (today - day, today),
        "Tomorrow": (today + day, today + 2 * day),
        "ThisWeek": (week, week + timedelta(weeks=1)),
        "LastWeek": (week - timedelta(weeks=1), week),
        "NextWeek": (week + timedelta(weeks=1), week + timedelta(weeks=2)),
        "EarlierThisWeek": (week, today - day),
        "LaterThisWeek": (today + 2 * day, week + timedelta(weeks=1)),
        "ThisMonth": (this_month, month(today, 1)),
        "EarlierThisMonth": (this_month, week - timedelta(weeks=1)),
        "LaterThisMonth": (week + timedelta(weeks=2), month(today, 1)),
        "EarlierThisYear": (year, this_month),
        "LaterThisYear": (month(today, 1), date(today.year + 1, 1, 1)),
        "PriorThisYear": (None, year),
        "BeyondThisYear": (date(today.year + 1, 1, 1), None),
        "Beyond": (month(today, 3), None),
        "Earlier": (None, month(today, -6)),
    }
    for step in (1, 2):
        windows[f"MonthAfter{step}"] = (month(today, step), month(today, step + 1))
    for step in range(1, 7):
        windows[f"MonthAgo{step}"] = (month(today, -step), month(today, 1 - step))
    return windows


@pytest.fixture()
def calendar(server, request):
    """One row for every few days from a year and a half ago to a year and a half ahead."""
    from datetime import UTC, datetime, timedelta

    from _browser import browser_page

    today = datetime.now(UTC).date()
    offsets = sorted({*range(-560, 561, 7), *range(-14, 15), -1, 1, 2, 31, -31})
    name = "Calendar " + request.node.name[:40]
    lines = ["Label,When"] + [
        f"d{offset:+d},{(today + timedelta(days=offset)).isoformat()}T12:00:00Z"
        for offset in offsets
    ]
    make_case(server, name, "\n".join(lines) + "\n")
    with browser_page(server[0], name) as page:
        page.today = today
        page.offsets = offsets
        yield page


def test_every_named_date_window_keeps_exactly_the_days_it_names(calendar):
    page = calendar
    windows = _reference_windows(page.today)
    for name, (low, high) in windows.items():
        command(page, "date-filter")
        page.wait_for_function("document.querySelectorAll('#date-range option').length > 20")
        page.select_option("#date-column", label="When")
        page.select_option("#date-mode", "range")
        page.select_option("#date-range", name)
        page.click("#date-add")
        page.wait_for_function(
            "document.getElementById('status').innerText.includes('Date filter')", timeout=15000
        )
        page.wait_for_timeout(250)
        shown = set(column_values(page, "Label"))
        wanted = {
            f"d{offset:+d}"
            for offset in page.offsets
            if (low is None or page.today.toordinal() + offset >= low.toordinal())
            and (high is None or page.today.toordinal() + offset < high.toordinal())
        }
        # a window that holds no row leaves an empty grid, which has no column to read
        assert shown == wanted, f"{name}: {sorted(shown ^ wanted)[:6]}"
        command(page, "clear-filters")
        page.wait_for_function(
            "document.querySelectorAll('#body tr[data-row]').length > 20", timeout=15000
        )


def test_the_named_windows_read_as_words(calendar):
    command(calendar, "date-filter")
    calendar.wait_for_function("document.querySelectorAll('#date-range option').length > 20")
    labels = calendar.eval_on_selector_all("#date-range option", "els => els.map(e => e.innerText)")
    assert "Earlier this week" in labels and "3 months ago" in labels and "In 2 months" in labels
    assert not [
        label for label in labels if re.search(r"[a-z][A-Z]|\d$", label) and "month" not in label
    ]


# -- Row height -----------------------------------------------------------------------------------------


def _height(page, selector):
    return page.evaluate(
        f"Math.round(document.querySelector({selector!r}).getBoundingClientRect().height)"
    )


def test_the_row_height_window_sets_the_three_heights(page):
    command(page, "row-height")
    page.fill("#rowheight-rows", "40")
    page.fill("#rowheight-groups", "36")
    page.fill("#rowheight-headers", "34")
    page.click('[data-act="rowheight-apply"]')
    page.wait_for_function("document.getElementById('status').innerText.includes('Row height: 40')")
    assert _height(page, "#body tr[data-row]") == 40
    assert _height(page, "#head tr:first-child th") == 34
    _group_by(page, "User")
    assert _height(page, "#body tr[data-group]") == 36
    command(page, "row-height")
    assert page.input_value("#rowheight-rows") == "40", "the choice is kept"
    page.fill("#rowheight-rows", "5")
    page.click('[data-act="rowheight-apply"]')
    page.wait_for_function("document.getElementById('status').innerText.includes('Row height: 14')")
    assert _height(page, "#body tr[data-group]") == 36


@pytest.fixture()
def prose(server, request):
    """A case whose one column holds a sentence far wider than the column."""
    from _browser import browser_page

    name = "Prose " + request.node.name[:40]
    sentence = " ".join(["the quick brown fox jumps over the lazy dog"] * 6)
    make_case(server, name, "Id,Text\n" + "\n".join(f"{i},{sentence}" for i in range(5)) + "\n")
    with browser_page(server[0], name) as page:
        yield page


def _row_height(page, rows=20, wrap=False, fit=False):
    command(page, "row-height")
    page.set_checked("#rowheight-wrap", wrap)
    page.set_checked("#rowheight-fit", fit)
    page.fill("#rowheight-rows", str(rows))
    page.click('[data-act="rowheight-apply"]')
    page.wait_for_function("document.getElementById('status').innerText.startsWith('Row height')")
    page.wait_for_timeout(200)
    return _height(page, "#body tr[data-row]")


def test_a_long_value_is_cut_by_default_wrapped_inside_the_row_or_fitted_by_growing_it(prose):
    assert _row_height(prose) == 20
    assert (
        prose.evaluate(
            "getComputedStyle(document.querySelector('#body td[data-cell=\"1\"]')).whiteSpace"
        )
        == "nowrap"
    )
    # wrapped, not fitted: the row keeps its height and the text breaks inside it
    assert _row_height(prose, wrap=True) == 20
    clip = prose.locator('#body td[data-cell="1"] .clip').first
    assert prose.evaluate("el => el.scrollHeight > el.clientHeight", clip.element_handle()), (
        "the text is wrapped on several lines and the box cuts it"
    )
    # a taller row shows more of the lines
    assert _row_height(prose, rows=60, wrap=True) == 60
    shown = prose.evaluate(
        "el => el.clientHeight",
        prose.locator('#body td[data-cell="1"] .clip').first.element_handle(),
    )
    assert 40 <= shown <= 57, shown
    # fitted: the row grows to hold every line of the text
    fitted = _row_height(prose, fit=True)
    assert fitted > 60, fitted
    assert prose.locator("#body .clip").count() == 0
    # and back to the plain row
    assert _row_height(prose) == 20
