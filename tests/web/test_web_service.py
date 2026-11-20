"""The HTTP service reads a real case written the way the desktop writes it."""
import csv

import pytest

from fireblade.core.engine import Case
from fireblade.core.investigations import InvestigationLibrary
from fireblade.core.models import AnalysisSnapshot, View
from fireblade.web.service import Library, ServiceError


def _write_csv(path):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Timestamp", "Artifact", "User", "SourceIP"])
        writer.writerows([
            ["2026-11-02T10:00:00Z", "EVTX", "alice", "192.0.2.10"],
            ["2026-11-02T10:01:00Z", "EVTX", "bob", "192.0.2.20"],
            ["2026-11-02T10:02:00Z", "Prefetch", "alice", ""],
        ])


@pytest.fixture()
def case_with_analysis(tmp_path):
    """Build a case the same way the desktop does: folder, analysis, session."""
    root = tmp_path / "cases"
    root.mkdir()
    library = InvestigationLibrary(root)
    data = library.create("Test case", "Written by the test", "windows")
    identifier = data["id"]
    folder = library.folder(identifier)
    analysis = folder / "analysis-1.duckdb"
    source = tmp_path / "rows.csv"
    _write_csv(source)
    case = Case(analysis)
    try:
        case.import_csv(source)
        info = dict(case.info)
    finally:
        case.close()
    snapshot = AnalysisSnapshot(path=str(analysis), source_info=info, view=View(), header_state=b"")
    library.save(identifier, [snapshot], 0, [], None, data["revision"])
    return root, identifier


def test_cases_are_listed(case_with_analysis):
    root, identifier = case_with_analysis
    service = Library(root)
    try:
        payload = service.cases()
        assert [item["id"] for item in payload["cases"]] == [identifier]
        assert payload["cases"][0]["name"] == "Test case"
    finally:
        service.close()


def test_analysis_columns_and_rows(case_with_analysis):
    root, identifier = case_with_analysis
    service = Library(root)
    try:
        detail = service.case(identifier)
        assert len(detail["analyses"]) == 1
        payload = service.rows(identifier, 0, limit=50)
        assert payload["columns"][0] == "__row_id"
        assert payload["columns"][1:] == ["Timestamp", "Artifact", "User", "SourceIP"]
        assert payload["total"] == 3
        assert len(payload["rows"]) == 3
        assert payload["rows"][0][2] == "EVTX"
    finally:
        service.close()


def test_search_and_column_filter(case_with_analysis):
    root, identifier = case_with_analysis
    service = Library(root)
    try:
        found = service.rows(identifier, 0, search="alice")
        assert found["total"] == 2
        filtered = service.rows(identifier, 0, filters=[(1, "contains", "Prefetch")])
        assert filtered["total"] == 1
        # Column 0 of a row is the row identifier, so the Artifact header sits at index 2.
        assert filtered["rows"][0][2] == "Prefetch"
        sorted_rows = service.rows(identifier, 0, sort=1, descending=True)
        assert [row[2] for row in sorted_rows["rows"]] == ["Prefetch", "EVTX", "EVTX"]
    finally:
        service.close()


def test_unknown_analysis_is_refused(case_with_analysis):
    root, identifier = case_with_analysis
    service = Library(root)
    try:
        with pytest.raises(ServiceError):
            service.rows(identifier, 7)
        with pytest.raises(ServiceError):
            service.rows(identifier, 0, filters=[(0, "nonsense", "x")])
        with pytest.raises(ServiceError):
            service.rows(identifier, 0, filters=[(99, "contains", "x")])
    finally:
        service.close()


def test_export_writes_a_csv(case_with_analysis):
    root, identifier = case_with_analysis
    service = Library(root)
    try:
        target = service.export(identifier, 0)
        text = target.read_text(encoding="utf-8-sig")
        assert "alice" in text and "192.0.2.20" in text
        assert len(text.strip().splitlines()) >= 4
    finally:
        service.close()
        for path in target.parent.glob("fireblade-*.csv"):
            path.unlink(missing_ok=True)


def _write_profile_csv(path):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["TimeCreated", "EventId", "Level", "Provider", "Channel",
                         "Computer", "MapDescription"])
        writer.writerow(["2026-11-02T10:00:00Z", "4624", "Information",
                         "Microsoft-Windows-Security-Auditing", "Security", "PC-1", "logon"])


def test_preview_shows_columns_and_profile(case_with_analysis, tmp_path):
    """The preview answers before the import: columns, profile, mapping, sample."""
    root, identifier = case_with_analysis
    source = tmp_path / "evtx-export.csv"
    _write_profile_csv(source)
    service = Library(root)
    try:
        before = len(service.case(identifier)["analyses"])
        preview = service.preview_source(source)
        assert preview["kind"] == "table"
        assert preview["profile"] == "EvtxECmd"
        # A UTF-8 BOM must not survive into the first column name.
        assert preview["columns"][0]["name"] == "TimeCreated"
        assert preview["columns"][0]["role"] == "timestamp"
        assert preview["mapping"]["sort"] == "TimeCreated"
        assert preview["mapping"]["timestamps"] == ["TimeCreated"]
        assert preview["rows"][0][1] == "4624"
        # Nothing was read into the case by the preview.
        assert len(service.case(identifier)["analyses"]) == before
    finally:
        service.close()


def test_preview_names_the_reader_of_an_artifact(case_with_analysis, tmp_path):
    root, _identifier = case_with_analysis
    source = tmp_path / "sample.evtx"
    source.write_bytes(b"ElfFile\x00" + b"\x00" * 64)
    service = Library(root)
    try:
        preview = service.preview_source(source)
        assert preview["kind"] == "artifact"
        assert preview["readers"] == ["EvtxECmd"]
        assert preview["columns"] == []
    finally:
        service.close()


def test_actions_export_is_a_csv(case_with_analysis):
    root, identifier = case_with_analysis
    service = Library(root)
    try:
        service.add_action(identifier, {"title": "Ask the client for DNS logs",
                                        "owner": "client", "priority": "high"})
        text = service.actions_csv(identifier)
        lines = [line for line in text.splitlines() if line]
        assert lines[0].startswith("id,title,detail,owner,status,priority")
        assert "Ask the client for DNS logs" in lines[1]
    finally:
        service.close()
