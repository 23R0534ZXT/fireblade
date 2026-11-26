"""The investigation report takes the desktop dialog's options: selection, limit, chart, coverage."""

import base64
import struct
import zlib

import pytest
from _audit import standard_csv

from fireblade.core.investigations import InvestigationLibrary
from fireblade.web.service import Library, ServiceError


def _png():
    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    raw = zlib.compress(b"\x00\xff\x00\x00")
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", raw)
        + chunk(b"IEND", b"")
    )


@pytest.fixture()
def library(tmp_path):
    root = tmp_path / "cases"
    root.mkdir()
    source = tmp_path / "events.csv"
    source.write_text(standard_csv())
    lib = Library(root)
    identifier = InvestigationLibrary(root).create("Report case", "", "windows")["id"]
    lib.import_source(identifier, source, organization="files")
    yield lib, identifier
    lib.close()


def _html(lib, identifier, result):
    return (lib.library.folder(identifier) / "reports" / result["name"]).read_text(encoding="utf-8")


def test_only_the_rows_selected_in_the_active_grid_are_in_the_report(library):
    lib, identifier = library
    result = lib.report(
        identifier, "Selection", selected={"index": 0, "row_ids": [2, 3, 5]}, bookmarks_only=True
    )
    assert result["records"] == 3


def test_an_empty_selection_is_refused(library):
    lib, identifier = library
    with pytest.raises(ServiceError):
        lib.report(identifier, "Nothing", selected={"index": 0, "row_ids": []})


def test_the_findings_limit_bounds_the_report(library):
    lib, identifier = library
    every = lib.report(identifier, "All", bookmarks_only=False, limit=2000)
    few = lib.report(identifier, "Few", bookmarks_only=False, limit=7)
    assert every["records"] > 7 and few["records"] == 7


def test_the_timeline_chart_and_its_caption_ride_in_the_report(library):
    lib, identifier = library
    png = base64.b64encode(_png()).decode("ascii")
    result = lib.report(
        identifier,
        "Chart",
        selected={"index": 0, "row_ids": [1]},
        timeline={"png": png, "caption": "Visible view of the timeline"},
    )
    text = _html(lib, identifier, result)
    assert png[:40] in text and "Visible view of the timeline" in text


def test_the_last_coverage_check_is_part_of_the_report(library):
    lib, identifier = library
    lib.coverage(identifier)
    result = lib.report(identifier, "Coverage", selected={"index": 0, "row_ids": [1]})
    text = _html(lib, identifier, result).lower()
    assert "coverage" in text or "couverture" in text


def test_the_date_columns_are_written_the_way_preferences_ask_by_the_cores_own_functions(tmp_path):
    from test_browser_findings import _alerts_text

    from fireblade.core.timestamps import display_timestamp, format_timestamp

    root = tmp_path / "cases"
    root.mkdir()
    source = tmp_path / "Alertes Hayabusa.csv"
    source.write_text(_alerts_text(), encoding="utf-8-sig")
    lib = Library(root)
    try:
        identifier = InvestigationLibrary(root).create("Dates", "", "windows")["id"]
        lib.import_source(identifier, source, organization="files")
        plain = lib.rows(identifier, 0, limit=1)
        assert plain["timestamps"], "a recognised profile names its date columns"
        raw = plain["rows"][0][1 + plain["timestamps"][0]]
        iso = lib.rows(identifier, 0, limit=1, date_format="iso")["rows"][0][
            1 + plain["timestamps"][0]
        ]
        iso7 = lib.rows(identifier, 0, limit=1, date_format="iso7")["rows"][0][
            1 + plain["timestamps"][0]
        ]
        custom = lib.rows(
            identifier, 0, limit=1, date_format="custom", date_pattern="dd/MM/yyyy HH:mm"
        )["rows"][0][1 + plain["timestamps"][0]]
        assert iso == display_timestamp(raw, "iso") and iso7 == display_timestamp(raw, "iso7")
        assert custom == format_timestamp(raw, "dd/MM/yyyy HH:mm") and custom != raw
    finally:
        lib.close()


def test_the_resource_preferences_are_kept_and_reach_the_engine(tmp_path):
    lib = Library(tmp_path)
    try:
        assert lib.preferences()["resource_memory_mb"] == 0
        saved = lib.set_preferences(
            {"resource_memory_mb": 1536, "query_threads": 2, "parsing_threads": 3}
        )
        assert (saved["resource_memory_mb"], saved["query_threads"], saved["parsing_threads"]) == (
            1536,
            2,
            3,
        )
        assert lib._settings().memory_mb == 1536 and lib._settings().threads == 2
        assert lib._settings("parsing").threads == 3
        with pytest.raises(ServiceError):
            lib.set_preferences({"query_threads": 99})
    finally:
        lib.close()


def test_the_coverage_plan_the_analyst_adjusts_is_the_one_audited(library):
    lib, identifier = library
    plan = lib.coverage(identifier, "windows", expected_tools=["EvtxECmd"])
    assert "EvtxECmd" in plan["families"]
