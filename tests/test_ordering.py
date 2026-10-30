import csv
import random

import pytest

from timeline_next.engine import Case
from timeline_next.errors import OperationCancelled
from timeline_next.models import Filter, View
from timeline_next.settings import Settings


@pytest.fixture
def case(tmp_path):
    source = tmp_path / "numbers.csv"
    values = [None, "", "bad", "001", "-0", "+12", "  -9007199254740993  ",
              "9007199254740992", "9007199254740993", "1.234567890123",
              "1e3", "2.0", ".5", "1,234", "-1e-12",
              "9999999999999999999999999999", "10000000000000000000000000000",
              "99999999999999999999999999999999999999999999999999",
              "000000000000000000000000000000000000000000000000001",
              "\t-123\n", "--2", "3.14", "NaN", "Infinity"]
    rng = random.Random(234)
    values += [str(rng.randrange(-10**26, 10**26)) for _ in range(400)]
    with source.open("w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(["Value", "Group", "Date"])
        for i, value in enumerate(values):
            writer.writerow([value, "A" if i % 2 else "B", f"2026-01-{i % 28 + 1:02d}"])
    c = Case(tmp_path / "numbers.timeline", settings=Settings(max_loaded_rows=250))
    c.import_csv(source)
    yield c
    c.close()


def test_integer_path_matches_native_decimal_conversion(case):
    # Compare independent native conversion for overflow, precision, whitespace,
    # exponent syntax, invalid values and deterministic random 26-digit integers.
    fast = case.numeric_expression('"c0"')
    mismatches = case.db.execute(
        f'SELECT c0 FROM events WHERE ({fast}) IS DISTINCT FROM try_cast(c0 AS DECIMAL(38,10))'
    ).fetchall()
    assert mismatches == []


def test_first_window_does_not_materialize_a_full_order(case):
    view = View(sort_column=0, sort_type="number")
    case.page(view)
    case.page(view, offset=25)
    assert not case.db.execute("SELECT count(*) FROM information_schema.tables WHERE table_name='__timeline_order'").fetchone()[0]


@pytest.mark.parametrize("sort_type,column", [("text", 0), ("number", 0), ("timestamp", 2)])
@pytest.mark.parametrize("descending", [False, True])
def test_cached_pages_match_native_order(case, sort_type, column, descending):
    view = View(sort_column=column, sort_type=sort_type, descending=descending)
    expression = {"text": f"c{column}", "number": f"try_cast(c{column} AS DECIMAL(38,10))",
                  "timestamp": f"try_cast(c{column} AS TIMESTAMP)"}[sort_type]
    direction = "DESC" if descending else "ASC"
    expected = case.db.execute(f"SELECT * FROM events ORDER BY {expression} {direction} NULLS LAST, __row_id").fetchall()
    actual = []
    for offset in (0, 250):
        actual += case.page(view, offset=offset)
    assert actual == expected
    assert case.page(view, offset=999999) == []
    assert case.page(view) == expected[:250]  # Backwards navigation uses the same order.


def test_cache_changes_with_filters_groups_and_bookmarks(case):
    view = View(sort_column=0, sort_type="number")
    case.page(view, offset=250)
    view.filters = [Filter(1, "eq", "A")]
    case.page(view, offset=250)
    where, args = case.where(view)
    expected = case.db.execute(f"SELECT * FROM events{where}{case.order(view)}", args).fetchall()
    assert case.page(view, offset=25) == expected[25:275]
    view.filters = []
    view.groups = [1]
    case.page(view, path=("B",), offset=250)
    assert all(row[2] == "B" for row in case.page(view, path=("B",), offset=25))
    view.groups = []
    view.bookmarks_only = True
    case.bookmark(1, "one")
    case.bookmark(4, "four")
    case.page(view, offset=250)
    case.bookmark(4, None)
    case.bookmark(5, "five")
    case.page(view, offset=250)
    expected = case.db.execute(
        "SELECT * FROM events WHERE __row_id IN (1,5)" + case.order(view)).fetchall()
    assert case.page(view, offset=1) == expected[1:]
    assert case.db.execute("SELECT count(*) FROM information_schema.tables WHERE table_name='__timeline_order'").fetchone()[0] == 1


def test_cancelled_cache_build_is_not_reused(case):
    native = case.db
    class CancelAfterBuild:
        def execute(self, sql, *args):
            result = native.execute(sql, *args)
            if sql.startswith("CREATE OR REPLACE TEMP TABLE"):
                case.interrupt()
            return result
        def __getattr__(self, name):
            return getattr(native, name)
    case.db = CancelAfterBuild()
    view = View(sort_column=0, sort_type="number")
    try:
        with pytest.raises(OperationCancelled):
            case.page(view, offset=250)
    finally:
        case.db = native
    expected = native.execute("SELECT * FROM events" + case.order(view) + " LIMIT 250 OFFSET 250").fetchall()
    assert case.page(view, offset=250) == expected
    assert case.count(View()) == 424


def test_order_cache_can_be_disabled(tmp_path):
    source = tmp_path / "no-cache.csv"
    source.write_text("ID\n003\n001\n002\n")
    case = Case(tmp_path / "no-cache.timeline", settings=Settings(cache_sorted_pages=False))
    try:
        case.import_csv(source)
        view = View(sort_column=0, sort_type="number")
        assert [row[1] for row in case.page(view, offset=1)] == ["002", "003"]
        assert case.page(view, offset=1000) == []
        assert not case.db.execute("SELECT count(*) FROM information_schema.tables WHERE table_name='__timeline_order'").fetchone()[0]
    finally:
        case.close()
