"""The defects the Desktop/Host recette found, kept fixed by a red test each.

Every test here names the failure it prevents:

- the window offered action types the core refuses (`containment`), so the New
  action button could never create anything with the type it opened on;
- the export wrote CSV only, while the desktop offers CSV or Excel;
- a session written before an analysis was imported again kept the old
  fingerprint, and packing the case then failed on the whole case;
- importing a portable case answered "0 analysis" for a case holding one;
- the close route the client posted to did not exist (the service exposes
  DELETE on the analysis), so closing a tab answered 404;
- a core refusal reached the English window in French.
"""

import csv
import json
from pathlib import Path

import pytest

from fireblade.core.case_workspace import ACTION_TYPES
from fireblade.core.engine import Case
from fireblade.core.investigations import InvestigationLibrary
from fireblade.core.models import AnalysisSnapshot, View
from fireblade.web.service import Library, ServiceError, _english


def _write_csv(path, rows=None):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Timestamp", "Artifact", "User", "SourceIP"])
        writer.writerows(
            rows
            or [
                ["2026-11-02T10:00:00Z", "EVTX", "alice", "192.0.2.10"],
                ["2026-11-02T10:01:00Z", "EVTX", "bob", "192.0.2.20"],
                ["2026-11-02T10:02:00Z", "Prefetch", "alice", ""],
            ]
        )


@pytest.fixture()
def case_with_analysis(tmp_path):
    root = tmp_path / "cases"
    root.mkdir()
    library = InvestigationLibrary(root)
    data = library.create("Recette case", "Written by the test", "windows")
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


@pytest.fixture()
def service(case_with_analysis):
    root, identifier = case_with_analysis
    library = Library(root)
    try:
        yield library, identifier
    finally:
        library.close()


def test_the_window_reads_the_action_types_from_the_core(service):
    library, _identifier = service
    payload = library.settings()
    assert payload["action_types"] == list(ACTION_TYPES)
    assert "collect" in payload["action_types"]
    # The value the window used to offer first, and the core refused.
    assert "containment" not in payload["action_types"]


@pytest.mark.parametrize("wanted, suffix", [("csv", ".csv"), ("xlsx", ".xlsx")])
def test_export_writes_the_format_the_desktop_offers(service, wanted, suffix):
    library, identifier = service
    target = library.export(identifier, 0, as_xlsx=(wanted == "xlsx"))
    try:
        assert target.suffix == suffix
        if wanted == "xlsx":
            from openpyxl import load_workbook

            book = load_workbook(target, read_only=True)
            try:
                rows = list(book.active.iter_rows(values_only=True))
            finally:
                book.close()
            assert rows[0][0] == "Timestamp"
            assert len(rows) == 4  # the header and three rows
            assert "alice" in [cell for row in rows for cell in row]
        else:
            text = target.read_text(encoding="utf-8-sig")
            assert text.splitlines()[0].startswith("Timestamp")
    finally:
        target.unlink(missing_ok=True)


def test_a_stale_fingerprint_does_not_block_the_portable_case(service):
    """The session predates a re-import: the file is the truth, and the repair is named."""
    library, identifier = service
    folder = library.library.folder(identifier)
    data = library.library.read(identifier)
    session = folder / data["session"]
    payload = json.loads(session.read_text(encoding="utf-8"))
    payload["documents"][0]["source"]["sha256"] = "0" * 64
    session.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    result = library.export_package(identifier, include_sources=False)
    assert result["name"].endswith(".fireblade")
    assert len(result["repaired"]) == 1
    assert Path(result["repaired"][0]["path"]).name == "analysis-1.duckdb"


def test_a_portable_case_reports_the_analyses_it_wrote(case_with_analysis, tmp_path):
    root, identifier = case_with_analysis
    library = Library(root)
    try:
        exported = library.export_package(identifier, include_sources=False)
        package = root / "exports" / exported["name"]
        other = Library(tmp_path / "other")
        try:
            imported = other.import_package(package)
            assert imported["analyses"] == 1
            assert other.case(imported["id"])["analyses"][0]["label"]
        finally:
            other.close()
    finally:
        library.close()


def test_closing_an_analysis_is_a_delete_on_the_analysis():
    """The window posted /analyses/{i}/close, which no route answers: 404, tab kept.

    The contract is read from the two sources rather than from FastAPI itself:
    fastapi is an optional extra of this package, and the suite runs without it.
    """
    root = Path(__file__).resolve().parents[2]
    client = (root / "src/fireblade/web/static/app.js").read_text(encoding="utf-8")
    server = (root / "src/fireblade/web/server.py").read_text(encoding="utf-8")
    assert "/analyses/${index}/close" not in client
    assert 'method: "DELETE"' in client
    assert '@app.delete("/api/cases/{identifier}/analyses/{index}")' in server


def test_closing_an_analysis_moves_it_to_the_closed_list(tmp_path):
    """Two tabs: the closed one goes to the session's own list, the other stays open."""
    root = tmp_path / "cases"
    root.mkdir()
    core = InvestigationLibrary(root)
    data = core.create("Two analyses", "", "windows")
    identifier = data["id"]
    folder = core.folder(identifier)
    source = tmp_path / "rows.csv"
    _write_csv(source)
    snapshots = []
    for number in (1, 2):
        analysis = folder / f"analysis-{number}.duckdb"
        case = Case(analysis)
        try:
            case.import_csv(source)
            info = dict(case.info)
        finally:
            case.close()
        snapshots.append(
            AnalysisSnapshot(path=str(analysis), source_info=info, view=View(), header_state=b"")
        )
    core.save(identifier, snapshots, 0, [], None, data["revision"])
    library = Library(root)
    try:
        result = library.close_analysis(identifier, 1)
        assert result["analyses"] == 1
        assert result["closed"] == 1
        assert library.closed_analyses(identifier)["closed"][0]["label"]
        # The last open analysis is the case: closing it says why, it does not 404.
        with pytest.raises(ServiceError) as refusal:
            library.close_analysis(identifier, 0)
        assert "last open analysis" in str(refusal.value)
    finally:
        library.close()


def test_a_core_refusal_reaches_an_english_window_in_english():
    assert _english("Onglet actif invalide") == "Invalid active tab"
    assert _english("Analyse remplacée : /data/x.timeline") == "Analysis replaced: /data/x.timeline"
    french = "Des preuves originales sont dans le case. Déplacez-les avant de libérer son espace."
    assert _english(french).startswith("Original evidence is still in the case")
