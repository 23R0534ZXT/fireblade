"""The HTTP service reads a real case written the way the desktop writes it."""

import csv
import json

import pytest

from fireblade.core.engine import Case
from fireblade.core.investigations import InvestigationLibrary
from fireblade.core.models import AnalysisSnapshot, View
from fireblade.web.service import Library, ServiceError


def _write_csv(path):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Timestamp", "Artifact", "User", "SourceIP"])
        writer.writerows(
            [
                ["2026-11-02T10:00:00Z", "EVTX", "alice", "192.0.2.10"],
                ["2026-11-02T10:01:00Z", "EVTX", "bob", "192.0.2.20"],
                ["2026-11-02T10:02:00Z", "Prefetch", "alice", ""],
            ]
        )


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
        writer.writerow(
            ["TimeCreated", "EventId", "Level", "Provider", "Channel", "Computer", "MapDescription"]
        )
        writer.writerow(
            [
                "2026-11-02T10:00:00Z",
                "4624",
                "Information",
                "Microsoft-Windows-Security-Auditing",
                "Security",
                "PC-1",
                "logon",
            ]
        )


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
        service.add_action(
            identifier,
            {"title": "Ask the client for DNS logs", "owner": "client", "priority": "high"},
        )
        text = service.actions_csv(identifier)
        lines = [line for line in text.splitlines() if line]
        assert lines[0].startswith("id,title,detail,owner,status,priority")
        assert "Ask the client for DNS logs" in lines[1]
    finally:
        service.close()


def _write_french_csv(path, delimiter=";", encoding="cp1252"):
    """A French export: semicolons, and an accent cp1252 alone can decode."""
    with path.open("w", encoding=encoding, newline="") as stream:
        writer = csv.writer(stream, delimiter=delimiter)
        writer.writerow(["Horodatage", "Evenement", "Utilisateur"])
        writer.writerows(
            [
                ["2026-11-02T10:00:00Z", "ouverture de session", "élève"],
                ["2026-11-02T10:01:00Z", "connexion", "bob"],
            ]
        )


def test_preview_reads_the_chosen_encoding_and_separator(case_with_analysis, tmp_path):
    """The desktop offers a separator and an encoding; the preview must honour them."""
    root, _identifier = case_with_analysis
    source = tmp_path / "poste-fr.csv"
    _write_french_csv(source)
    service = Library(root)
    try:
        detected = service.preview_source(source)
        assert detected["delimiter"] == "semicolon"
        assert detected["encoding"] in ("utf-8", "utf-8-sig")
        # Read as UTF-8, the cp1252 accent is a replacement character.
        assert "\ufffd" in detected["rows"][0][2]
        chosen = service.preview_source(source, delimiter=";", encoding="cp1252")
        assert chosen["delimiter"] == "semicolon"
        assert chosen["encoding"] == "cp1252"
        assert chosen["columns"][0]["name"] == "Horodatage"
        assert chosen["rows"][0][2] == "élève"
        # A separator that is not the file's gives one column: the analyst sees it.
        wrong = service.preview_source(source, delimiter=",")
        assert len(wrong["columns"]) == 1
    finally:
        service.close()


def test_import_uses_the_chosen_encoding(case_with_analysis, tmp_path):
    """The option is not only shown: the imported row carries the accent."""
    root, identifier = case_with_analysis
    source = tmp_path / "poste-fr-import.csv"
    _write_french_csv(source)
    service = Library(root)
    try:
        service.import_source(identifier, source, delimiter=";", encoding="cp1252")
        detail = service.case(identifier)
        analyses = detail["analyses"]
        assert len(analyses) == 2
        payload = service.rows(identifier, len(analyses) - 1, limit=20)
        assert "Utilisateur" in payload["columns"]
        column = payload["columns"].index("Utilisateur")
        assert any(row[column] == "élève" for row in payload["rows"])
    finally:
        service.close()


def test_closing_an_analysis_leaves_the_others_and_its_file(case_with_analysis, tmp_path):
    """Closing a view is not deleting: the other analyses and the file survive."""
    root, identifier = case_with_analysis
    extra = tmp_path / "second.csv"
    _write_csv(extra)
    service = Library(root)
    try:
        service.import_source(identifier, extra)
        assert len(service.case(identifier)["analyses"]) == 2
        path = service.case(identifier)["analyses"][0]["path"]
        service.close_analysis(identifier, 0)
        remaining = service.case(identifier)["analyses"]
        assert len(remaining) == 1
        from pathlib import Path as _Path

        assert _Path(path).is_file(), "closing an analysis must not delete its file"
        # The one left is the imported analysis, not a stale copy of the closed one.
        assert remaining[0]["path"] != path
    finally:
        service.close()


def test_an_export_is_named_after_the_case_and_the_analysis(case_with_analysis):
    root, identifier = case_with_analysis
    service = Library(root)
    try:
        name = service.export_name(identifier, 0, "csv")
        assert name.startswith("Test-case_") and name.endswith(".csv"), name
        assert "analysis-0" not in name and identifier[:8] not in name
        assert service.export_name("missing", 3, "xlsx").endswith("analysis-3.xlsx")
    finally:
        service.close()


def test_a_folder_preview_counts_every_file_and_lists_a_bounded_number(tmp_path):
    root = tmp_path / "cases"
    root.mkdir()
    folder = tmp_path / "collection"
    folder.mkdir()
    for number in range(230):
        (folder / f"log-{number:03}.txt").write_text("x\n", encoding="utf-8")
    service = Library(root)
    try:
        preview = service.preview_source(str(folder))
        assert preview["kind"] == "folder"
        assert preview["count"] == 230 and len(preview["files"]) == 200
    finally:
        service.close()


def test_a_disk_walk_speaks_english_and_a_missing_source_is_refused_plainly(tmp_path):
    from fireblade.web.service import _english_disk_message

    assert _english_disk_message("Extraction en lecture seule : /$MFT") == (
        "Read-only extraction: /$MFT"
    )
    assert _english_disk_message("Découverte : 300 fichiers · 4 artefacts copiés · /x/y") == (
        "Discovery: 300 files · 4 artifacts copied · /x/y"
    )
    root = tmp_path / "cases"
    root.mkdir()
    service = Library(root)
    try:
        identifier = InvestigationLibrary(root).create("Disks", "", "windows")["id"]
        with pytest.raises(ServiceError, match="does not exist on the server"):
            service.start_disk_job(identifier, str(tmp_path / "nothing"), "image")
    finally:
        service.close()


def test_a_history_entry_says_what_state_it_holds(case_with_analysis):
    root, identifier = case_with_analysis
    service = Library(root)
    try:
        folder = service.library.folder(identifier) / "History"
        folder.mkdir(exist_ok=True)
        (folder / "c4659be8d603482bba721c8c06a51784.json").write_text(
            json.dumps({"format": "fireblade-case", "analysis_count": 3, "status": "open"}),
            encoding="utf-8",
        )
        entry = next(
            item
            for item in service.history(identifier)["entries"]
            if item["name"].startswith("c4659be8")
        )
        assert entry["label"] == "Case state — 3 analysis(es), status open"
        assert entry["name"].endswith(".json")
    finally:
        service.close()


def test_tracking_projects_tagged_records_into_office_exports(case_with_analysis):
    from io import BytesIO

    from fastapi.testclient import TestClient
    from openpyxl import load_workbook

    from fireblade.web.server import create_app

    root, identifier = case_with_analysis
    base = f"/api/cases/{identifier}/tracking"
    with TestClient(create_app(root)) as client:
        row = client.get(base + "/row", params={"analysis": 0, "row": 1, "column": 3})
        assert row.status_code == 200, row.text
        assert row.json()["selection"] == "192.0.2.10"
        assert row.json()["time"] == "2026-11-02T10:00:00+00:00"
        event = client.post(
            base + "/events",
            json={
                "analysis": 0,
                "row": 1,
                "column": 3,
                "machine": "host-a",
                "tags": ["Network"],
                "kind": "connection",
                "direction": "inbound",
                "source_ip": "192.0.2.10",
                "destination_ip": "192.0.2.20",
                "description": "=1+1",
            },
        )
        assert event.status_code == 200, event.text
        launched = client.post(
            base + "/events",
            json={
                "analysis": 0,
                "row": 2,
                "machine": "HOST-A",
                "tags": ["Network"],
                "kind": "file_creation",
                "file": "example.txt",
                "description": "File created",
            },
        )
        assert launched.status_code == 200, launched.text
        assert (
            client.post(
                base + "/events",
                json={
                    "analysis": 0,
                    "row": 3,
                    "machine": "host-a",
                    "tags": ["Other"],
                    "verdict": "false_positive",
                },
            ).status_code
            == 200
        )
        payload = client.get(base, params={"tag": "network"}).json()
        assert len(payload["events"]) == 2
        assert payload["connections"][0]["followed_by"] == [launched.json()["id"]]
        assert len(client.get(base, params={"fp": "true"}).json()["events"]) == 3
        assert client.get(base, params={"tag": "absent"}).json()["events"] == []

        indicator = {"analysis": 0, "row": 1, "column": 3, "declare": True, "machine": "host-a"}
        for _ in range(2):
            response = client.post(base + "/indicator", json=indicator)
            assert response.status_code == 200, response.text
        origins = client.get(base.removesuffix("tracking") + "workspace").json()["iocs"][0][
            "observations"
        ]
        assert len(origins) == 1
        assert origins[0]["column"] == "SourceIP"
        assert origins[0]["line"] == 1

        xlsx = client.get(base + "/export/xlsx", params={"tag": "Network"})
        assert xlsx.status_code == 200, xlsx.text
        workbook = load_workbook(BytesIO(xlsx.content))
        assert workbook.sheetnames == [
            "Actions",
            "Chronologie",
            "Eléments récoltés",
            "IoCs",
            "Postes compromis",
            "Comptes compromis",
        ]
        assert workbook["Chronologie"]["D2"].value == "=1+1 · 192.0.2.10 → 192.0.2.20 (inbound)"
        assert workbook["Chronologie"]["D2"].data_type == "s"
        assert "SourceIP" in workbook["IoCs"]["C2"].value

        from docx import Document

        report = client.get(base + "/export/docx", params={"tag": "Network"})
        assert report.status_code == 200, report.text
        doc = Document(BytesIO(report.content))
        assert "Résumé exécutif" in [paragraph.text for paragraph in doc.paragraphs]
        assert any(
            cell.text == "File created · example.txt"
            for table in doc.tables
            for row in table.rows
            for cell in row.cells
        )


def test_tracking_keeps_the_original_row_across_layouts(tmp_path):
    from fastapi.testclient import TestClient

    from fireblade.web.server import create_app

    root = tmp_path / "cases"
    identifier = InvestigationLibrary(root).create("Layouts", "", "windows")["id"]
    source = tmp_path / "input"
    source.mkdir()
    for name, value in (("a", "first"), ("b", "second")):
        (source / f"{name}.csv").write_text(
            f"Timestamp,Host,Event\n2026-11-02T10:00:00Z,PC1,{value}\n"
        )
    base = f"/api/cases/{identifier}"
    with TestClient(create_app(root)) as client:
        imported = client.post(
            base + "/import", json={"source": str(source), "organization": "combined"}
        )
        assert imported.status_code == 200, imported.text
        event = client.post(
            base + "/tracking/events",
            json={
                "analysis": 0,
                "row": 2,
                "description": "Kept through layout change",
                "tags": ["Test"],
            },
        )
        assert event.status_code == 200, event.text
        saved = event.json()
        assert saved["origin"]["line"] == 1
        assert saved["origin"]["file"].endswith("b.csv")

        change = client.post(base + "/reorganize", json={"mode": "files"})
        assert change.status_code == 200, change.text
        analysis = next(e for e in client.get(base).json()["analyses"] if "b.csv" in e["label"])
        marked = client.post(
            base + f"/analyses/{analysis['index']}/bookmark",
            json={"row_id": 1, "note": "Added note"},
        )
        assert marked.status_code == 200, marked.text
        with_existing = client.post(
            base + "/tracking/bookmarks", json={"analysis": analysis["index"]}
        )
        assert with_existing.status_code == 200, with_existing.text
        assert with_existing.json() == {"added": 0, "already_tagged": 1}
        found = client.get(base + "/tracking/row", params={"analysis": analysis["index"], "row": 1})
        assert found.status_code == 200, found.text
        assert found.json()["event"]["id"] == saved["id"]


def test_incident_context_and_verified_destruction_word_documents(tmp_path):
    from io import BytesIO
    from pathlib import Path

    from docx import Document
    from fastapi.testclient import TestClient

    from fireblade.web.server import create_app

    root = tmp_path / "cases"
    identifier = InvestigationLibrary(root).create("Synthetic intake", "", "windows")["id"]
    base = f"/api/cases/{identifier}"
    with TestClient(create_app(root)) as client:
        updated = client.put(
            base + "/incident-context",
            json={
                "discovered": "2026-11-27T13:00:00Z",
                "description": "Synthetic report narrative.",
            },
        )
        assert updated.status_code == 200, updated.text
        invalid = client.put(base + "/incident-context", json={"discovered": "yesterday"})
        assert invalid.status_code == 400
        exported = client.get(base + "/incident-context.docx")
        assert exported.status_code == 200, exported.text
        intake = Document(BytesIO(exported.content))
        assert any(
            "Synthetic report narrative." in cell.text
            for table in intake.tables
            for row in table.rows
            for cell in row.cells
        )

        erased = client.post(
            base + "/destroy",
            json={
                "confirmation": "Synthetic intake",
                "operator": "Examiner",
                "witness": "Witness",
                "certificate_folder": str(tmp_path / "certificates"),
            },
        )
        assert erased.status_code == 200, erased.text
        payload = erased.json()
        assert Path(payload["certificate"]).exists()
        word = Document(payload["certificate_word"])
        assert any(
            "Vérifié et supprimé" == cell.text
            for table in word.tables
            for row in table.rows
            for cell in row.cells
        )


def test_scenario_links_exact_process_identity_between_artifacts(tmp_path):
    from fastapi.testclient import TestClient

    from fireblade.web.server import create_app

    root = tmp_path / "cases"
    identifier = InvestigationLibrary(root).create("Synthetic correlation", "", "windows")["id"]
    files = tmp_path / "evidence"
    files.mkdir()
    (files / "sysmon-process.csv").write_text(
        "Timestamp,Host,Provider,EventID,ProcessGuid,Image\n"
        "2026-11-27T13:00:00Z,PC1,Microsoft-Windows-Sysmon,1,{a123},program.exe\n"
        "2026-11-27T13:00:00Z,PC2,Microsoft-Windows-Sysmon,1,{a123},elsewhere.exe\n"
    )
    (files / "edr-network.csv").write_text(
        "Timestamp,DeviceName,ActionType,ProcessGuid,RemoteIP\n"
        "2026-11-27T13:01:00Z,PC1,ConnectionSuccess,A123,192.0.2.4\n"
    )
    (files / "edr-file.csv").write_text(
        "Timestamp,DeviceName,ActionType,ProcessGuid,FileName\n"
        "2026-11-27T13:02:00Z,PC1,FileCreated,A123,note.txt\n"
        "2026-11-27T12:55:00Z,PC1,FileCreated,A123,older.txt\n"
    )
    (files / "unrelated-namespace.csv").write_text(
        "Timestamp,DeviceName,ActionType,InitiatingProcessUniqueId,FileName\n"
        "2026-11-27T13:02:00Z,PC1,FileCreated,A123,different-id-space.txt\n"
    )
    base = f"/api/cases/{identifier}"
    with TestClient(create_app(root)) as client:
        imported = client.post(
            base + "/import", json={"source": str(files), "organization": "files"}
        )
        assert imported.status_code == 200, imported.text
        response = client.get(base + "/scenario")
        assert response.status_code == 200, response.text
        result = response.json()
        nodes = {node["id"]: node for node in result["nodes"]}
        assert result["scanned"] == 4
        assert len(result["edges"]) == 2
        assert {nodes[e["target"]]["detail"] for e in result["edges"]} == {"192.0.2.4", "note.txt"}
        assert {nodes[e["source"]]["host"] for e in result["edges"]} == {"PC1"}


def test_rewrite_rejects_a_proposal_that_changes_identifiers(monkeypatch):
    import httpx

    from fireblade.web import tracking

    service = "http://local-model/v1/chat/completions"
    monkeypatch.setenv("FIREBLADE_REWRITE_URL", service)
    monkeypatch.setenv("FIREBLADE_REWRITE_MODEL", "example")
    draft = "A log showed a connection from 192.0.2.17 to SRV-01 at 14:05 UTC."
    suggestion = "The log recorded a connection from 192.0.2.17 to SRV-01 at 14:05 UTC."
    output = [suggestion, suggestion.replace("SRV-01", "SRV-02"), draft]

    def infer(url, *, json, **kwargs):
        assert url == service
        assert json["messages"][-1]["content"] == draft
        return httpx.Response(
            200,
            request=httpx.Request("POST", service),
            json={"choices": [{"message": {"content": output.pop(0)}}]},
        )

    monkeypatch.setattr(httpx, "post", infer)
    assert tracking.rewrite(draft) == suggestion
    with pytest.raises(ValueError, match="changed protected"):
        tracking.rewrite(draft)
    with pytest.raises(ValueError, match="original draft"):
        tracking.rewrite(draft)


def test_folder_import_applies_profiles_in_one_case_save(tmp_path, monkeypatch):
    from fireblade.core.sessions import read_session

    root = tmp_path / "cases"
    library = Library(root)
    identifier = library.library.create("Profile batch", "", "windows")["id"]
    source = tmp_path / "inputs"
    source.mkdir()
    for name, event in (("event-a.csv", 17), ("event-b.csv", 18)):
        (source / name).write_text(
            f"EventId,Provider,Channel,TimeCreated\n{event},Example,Example,2026-11-27T13:00:00Z\n"
        )
    (source / "file.csv").write_text("Field,Number\nvalue,12345\n")
    (source / "timeline.csv").write_text(
        "date,time,timezone,MACB,sourcetype\n11/27/2026,13:00:00,UTC,MACB,Example\n"
    )

    calls = []
    original = library.library.save

    def save(*args, **kwargs):
        calls.append(args[0])
        return original(*args, **kwargs)

    def open_analysis(*args, **kwargs):
        pytest.fail("Profile detection should use the verified headers of the import.")

    try:
        with monkeypatch.context() as patch:
            patch.setattr(library.library, "save", save)
            patch.setattr(library, "_case_for", open_analysis)
            imported = library.import_source(identifier, source)
        assert imported["analyses"] == 4
        assert calls == [identifier]
        data = library.library.read(identifier)
        snapshots, _active = read_session(library.library.session_path(data))
        assert [item.view.timestamp_columns for item in snapshots] == [[3], [3], [], []]
        assert [item.view.sort_type for item in snapshots] == [
            "timestamp",
            "timestamp",
            "text",
            "text",
        ]
        assert "Fireblade_MACBMask" in library.columns(identifier, 3)
    finally:
        library.close()


def test_folder_and_disk_jobs_use_local_thread_choices(tmp_path, monkeypatch):
    import time

    from fastapi.testclient import TestClient

    from fireblade.core import settings
    from fireblade.core.collection import Collection
    from fireblade.web.server import create_app

    monkeypatch.setattr(settings, "cpu_threads", lambda: 12)
    monkeypatch.setattr(settings, "available_memory_mb", lambda: 4096)
    cases = tmp_path / "cases"
    library = InvestigationLibrary(cases)
    identifier = library.create("Thread choices", "", "windows")["id"]
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    source = inputs / "records.csv"
    source.write_text("Host,Message\nHost-A,Record\n")
    seen = []
    parse = Collection.parse

    def capture(collection):
        seen.append(collection.settings.threads)
        return parse(collection)

    monkeypatch.setattr(Collection, "parse", capture)
    with TestClient(create_app(cases)) as client:
        capacity = client.get("/api/import-capacity")
        assert capacity.json() == {
            "max_threads": 8,
            "recommended_threads": 6,
            "cpu_threads": 12,
            "memory_mb": 4096,
        }
        base = f"/api/cases/{identifier}"
        prior = client.get("/api/preferences").json()

        def complete(response):
            assert response.status_code == 200, response.text
            job = response.json()["job"]
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                state = client.get(f"/api/import-jobs/{job}").json()
                if state["status"] != "running":
                    assert state["status"] == "complete", state
                    return
                time.sleep(0.02)
            pytest.fail("The import job did not finish.")

        complete(
            client.post(
                base + "/import-jobs",
                data={"source": str(inputs), "parsing_threads": "5"},
            )
        )
        complete(
            client.post(
                base + "/disk-jobs",
                json={"source": str(inputs), "kind": "mounted", "parsing_threads": 3},
            )
        )
        assert seen == [5, 3]
        assert client.get("/api/preferences").json() == prior

        capped = client.post(
            base + "/import-jobs", data={"source": str(inputs), "parsing_threads": "9"}
        )
        assert capped.status_code == 400
        assert "between 1 and 8" in capped.json()["detail"]
        wrong_source = client.post(
            base + "/import-jobs",
            data={"source": str(source), "parsing_threads": "2"},
        )
        assert wrong_source.status_code == 400
        assert "folders only" in wrong_source.json()["detail"]
        uploaded = client.post(
            base + "/import-jobs",
            data={"parsing_threads": "2"},
            files={"file": ("not-uploaded.csv", b"Host\nHost-A\n", "text/csv")},
        )
        assert uploaded.status_code == 400
        assert not (library.folder(identifier) / "evidence" / "not-uploaded.csv").exists()
        for value in (True, "3", 1.5, 0, 9):
            refused = client.post(
                base + "/disk-jobs",
                json={"source": str(inputs), "kind": "mounted", "parsing_threads": value},
            )
            assert refused.status_code == 400
