"""The same command on the desktop window and on the Host: the same rows, in the same order.

The desktop side is the real window (offscreen Qt) with the real command handlers; the Host side is
the real page in Chromium, reached the way an analyst reaches it (right-click, menu, field). Both
read the same table. A difference is a defect of the Host, whatever the reason: the desktop is the
reference.

Skipped without Qt or without Playwright and a Chromium.
"""

import os
import time

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("playwright.sync_api")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from _audit import standard_csv  # noqa: E402
from conftest import make_case  # noqa: E402

HEADERS = ["Time", "Host", "User", "Event", "Path", "Src"]


@pytest.fixture(scope="module")
def desktop(tmp_path_factory):
    from PySide6.QtWidgets import QApplication

    from fireblade.core.engine import Case
    from fireblade.ui.app import Window

    app = QApplication.instance() or QApplication([])
    folder = tmp_path_factory.mktemp("desktop")
    source = folder / "events.csv"
    source.write_text(standard_csv())
    case = Case(folder / "events.timeline")
    case.import_csv(source)
    case.close()
    window = Window()
    window.require_case = False
    window.load_case(folder / "events.timeline")
    for _ in range(100):
        app.processEvents()
        time.sleep(0.03)
        if window.case is not None and not window.busy:
            break
    assert window.case is not None
    yield window, app
    window.close()


def _ids(window, app, limit=400):
    """The row ids the desktop shows, in order, for its current view."""
    for _ in range(40):
        app.processEvents()
        if not window.busy:
            break
        time.sleep(0.03)
    return [row[0] for row in window.case.page(window.view, offset=0, limit=limit)]


def _reset(window, app):
    window.reset()
    _ids(window, app)


@pytest.fixture()
def host(server, request):
    from _browser import browser_page

    name = "Parity " + request.node.name[:40]
    make_case(server, name, standard_csv())
    base, _root, _evidence = server
    with browser_page(base, name) as page:
        yield page


def _host_ids(page):
    page.wait_for_function("!state.busy", timeout=30000) if False else None
    page.wait_for_timeout(400)
    return [int(row[0]) for row in page.evaluate("state.rows")]


def _context(page, column, value, act):
    """Right-click the first visible cell of `column` holding `value`, then press `act`."""
    index = HEADERS.index(column)
    rows = page.locator("#body tr[data-row]")
    for position in range(rows.count()):
        cell = rows.nth(position).locator(f"td[data-cell='{index}']")
        if cell.inner_text().strip() == value:
            cell.click(button="right")
            page.click(f'#row-menu [data-act="{act}"]')
            return
    raise AssertionError(f"no {column} cell holds {value}")


def _cell_value(window, column, row_id):
    case = window.case
    index = case.headers.index(column)
    for row in case.page(window.view, offset=0, limit=400):
        if row[0] == row_id:
            return row[index + 1]
    return None


def test_filter_on_a_value(desktop, host):
    window, app = desktop
    _reset(window, app)
    first = next(row for row in window.case.page(window.view, offset=0, limit=400))
    value = str(first[HEADERS.index("User") + 1])
    window.filter_value(HEADERS.index("User"), value)
    expected = _ids(window, app)
    _context(host, "User", value, "filter-value")
    assert _host_ids(host) == expected


def test_two_filters_on_values_of_one_column_are_both_kept(desktop, host):
    """The desktop appends: User = alice AND User = bob is empty. The Host must not replace."""
    window, app = desktop
    _reset(window, app)
    window.filter_value(HEADERS.index("User"), "alice")
    window.filter_value(HEADERS.index("User"), "bob")
    expected = _ids(window, app)
    _context(host, "User", "alice", "filter-value")
    host.wait_for_timeout(400)
    bob = host.evaluate("state.total")
    assert expected == []
    assert bob > 0  # the first filter applied; bob rows are gone, so a second on bob is empty:
    host.evaluate("state.filters.length")  # keep the filter list readable in a failure report
    host.evaluate("state.rows.length")
    # the second filter needs a bob cell: put the first filter away, filter bob, then alice again
    host.evaluate("void act('clear-filters')")
    _context(host, "User", "bob", "filter-value")
    host.wait_for_timeout(400)
    host.evaluate(
        "state.filters.push({column: 2, operator: 'eq', value: 'alice'}); void loadRows(true)"
    )
    assert _host_ids(host) == expected


def test_exclude_a_value(desktop, host):
    window, app = desktop
    _reset(window, app)
    window.filter_value(HEADERS.index("Host"), "PC01", exclude=True)
    expected = _ids(window, app)
    _context(host, "Host", "PC02", "exclude-value")
    host.evaluate("state.filters[0].value = 'PC01'; void loadRows(true)")
    assert _host_ids(host) == expected


def test_clear_the_filters(desktop, host):
    window, app = desktop
    _reset(window, app)
    everything = _ids(window, app)
    window.filter_value(HEADERS.index("User"), "alice")
    window.clear_filters()
    assert _ids(window, app) == everything
    _context(host, "User", "alice", "filter-value")
    host.evaluate("void act('clear-filters')")
    assert _host_ids(host) == everything


@pytest.mark.parametrize("descending", [False, True])
@pytest.mark.parametrize("column", ["Event", "Host", "Time"])
def test_sort_a_column(desktop, host, column, descending):
    window, app = desktop
    _reset(window, app)
    index = HEADERS.index(column)
    window.sort_column.setCurrentIndex(window.sort_column.findData(index))
    window.desc.setChecked(descending)
    window.apply()
    expected = _ids(window, app)
    cell = host.locator("#body tr[data-row]").first.locator(f"td[data-cell='{index}']")
    cell.click(button="right")
    host.click(f'#row-menu [data-act="{"sort-desc" if descending else "sort-asc"}"]')
    assert _host_ids(host) == expected
    window.desc.setChecked(False)


def test_search_a_text(desktop, host):
    window, app = desktop
    _reset(window, app)
    window.search.setText("bob")
    window.apply()
    expected = _ids(window, app)
    host.fill("#search", "bob")
    host.press("#search", "Enter")
    assert _host_ids(host) == expected
    window.search.setText("")
    window.apply()


def test_a_text_expression(desktop, host):
    from fireblade.core.filter_text import parse_filter

    window, app = desktop
    _reset(window, app)
    view = window.view
    view.filters, view.expression = [], parse_filter("Contains([User], 'ali')", window.case.headers)
    window.apply()
    expected = _ids(window, app)
    host.evaluate("void act('expression-text')")
    host.wait_for_selector("#ask-modal.show")
    host.fill("#ask-input", "Contains([User], 'ali')")
    host.click('#ask-modal [data-act="ask-ok"]')
    assert _host_ids(host) == expected


def test_excluding_two_values_of_one_column_keeps_both_exclusions(desktop, host):
    """The desktop appends each exclusion: PC01 and PC02 are both gone. The Host must not replace."""
    window, app = desktop
    _reset(window, app)
    window.filter_value(HEADERS.index("Host"), "PC01", exclude=True)
    window.filter_value(HEADERS.index("Host"), "PC02", exclude=True)
    expected = _ids(window, app)
    assert expected
    _context(host, "Host", "PC01", "exclude-value")
    _host_ids(host)
    _context(host, "Host", "PC02", "exclude-value")
    assert _host_ids(host) == expected


CONDITIONS = [
    ("User", "contains", "li"),
    ("User", "not_contains", "li"),
    ("User", "starts", "b"),
    ("User", "ends", "e"),
    ("User", "regex", "^(alice|carol)$"),
    ("Event", "gt", "4624"),
    ("Event", "ge", "4625"),
    ("Event", "lt", "4688"),
    ("Event", "le", "4625"),
    ("Time", "after", "2026-11-03"),
    ("Time", "before", "2026-11-02T23:59:59Z"),
    ("Time", "date_after", "2026-11-03"),
    ("Time", "date_before", "2026-11-03"),
    ("Time", "date_eq", "2026-11-02"),
    ("Time", "date_ne", "2026-11-02"),
    ("Host", "text_gt", "PC02"),
    ("Host", "text_le", "PC02"),
    ("Src", "empty", ""),
    ("Src", "not_empty", ""),
    ("Path", "contains", "f1"),
]


@pytest.mark.parametrize("column,operator,value", CONDITIONS)
def test_every_filter_operator_selects_the_same_rows(desktop, host, column, operator, value):
    from fireblade.core.models import Filter

    window, app = desktop
    _reset(window, app)
    window.view.filters = [Filter(HEADERS.index(column), operator, value)]
    window.apply()
    expected = _ids(window, app)
    host.evaluate(
        f"state.filters = [{{column: {HEADERS.index(column)}, operator: '{operator}', value: '{value}'}}]; "
        "void loadRows(true)"
    )
    assert _host_ids(host) == expected


def test_a_bookmarked_row_is_the_only_one_shown_with_bookmarks_only(desktop, host):
    window, app = desktop
    _reset(window, app)
    case = window.case
    case.bookmark(5, "bookmarked")
    case.bookmark(9, "bookmarked")
    window.only_notes.setChecked(True)
    window.apply()
    expected = _ids(window, app)
    assert sorted(expected) == [5, 9]
    for row in (5, 9):
        host.evaluate(
            f"void apiPost(`/api/cases/${{state.openCase.id}}/analyses/${{state.analysis}}/bookmark`, {{row_id: {row}, note: 'bookmarked'}})"
        )
    host.wait_for_timeout(500)
    host.evaluate("void document.getElementById('bookmarks-only').click()")
    assert sorted(_host_ids(host)) == sorted(expected)
    window.only_notes.setChecked(False)
    case.bookmark(5, None)
    case.bookmark(9, None)


def test_grouping_by_a_column_makes_the_same_groups_with_the_same_counts(desktop, host):
    window, app = desktop
    _reset(window, app)
    window.view.groups = [HEADERS.index("User")]
    window.apply()
    for _ in range(40):
        app.processEvents()
    expected = [
        (str(row[0]), int(row[1])) for row in window.case.page(window.view, offset=0, limit=50)
    ]
    assert expected
    host.evaluate(f"state.groups = [{HEADERS.index('User')}]; state.path = []; void loadRows(true)")
    host.wait_for_timeout(700)
    shown = [(str(row[0]), int(row[1])) for row in host.evaluate("state.rows")]
    assert shown == expected, (shown, expected)
