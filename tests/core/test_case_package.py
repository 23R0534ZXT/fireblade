import hashlib
import json
import threading
import zipfile
from pathlib import Path

import pytest

from fireblade.core import case_workspace, destruction, destruction_certificate
from fireblade.core.case_package import export_package, import_package
from fireblade.core.engine import Case
from fireblade.core.errors import OperationCancelled, cancellation_scope
from fireblade.core.investigations import InvestigationLibrary
from fireblade.core.models import AnalysisSnapshot, View
from fireblade.core.sessions import read_session, write_session


def prepared(tmp_path):
    source = tmp_path / "source.csv"
    source.write_text("Timestamp,User,ID\n2026-01-01T00:00:00Z,élève,0009007199254740993\n")
    case = Case(tmp_path / "analysis.timeline")
    info = case.import_csv(source)
    case.bookmark(1, "Note <exacte>")
    document = AnalysisSnapshot(str(case.path), info, View(search="élève"), b"header")
    library = InvestigationLibrary(tmp_path / "cases")
    data = library.create("Case portable", "Contexte")
    data = library.save(data["id"], [document], 0, [], None, data["revision"])
    return library, data, document, case, source


def test_verified_package_moves_sources_annotations_views_and_collection_references(tmp_path):
    library, data, document, case, source = prepared(tmp_path)
    collection = tmp_path / "collection"
    collection.mkdir()
    write_session(collection / "collection.fireblade-session", [document], 0)
    (collection / "collection.json").write_text(
        json.dumps(
            dict(root=str(tmp_path / "evidence"), output=str(collection), documents=[document.path])
        )
    )
    data = library.save(
        data["id"],
        [document],
        0,
        [dict(path=str(collection), name="Collecte")],
        str(collection),
        data["revision"],
    )
    try:
        digest = hashlib.sha256(source.read_bytes()).digest()
        archive = tmp_path / "case.fireblade-case"
        result = export_package(
            library, data, [document], 0, archive, include_sources=True, active_case=case
        )
        assert not result["missing_sources"]
        assert hashlib.sha256(source.read_bytes()).digest() == digest
    finally:
        case.close()
    source.unlink()
    Path(document.path).unlink()
    target = InvestigationLibrary(tmp_path / "another location" / "cases")
    imported = import_package(target, archive)["case"]
    snapshots, active = read_session(target.session_path(imported))
    assert active == 0
    restored = Case(snapshots[0].path)
    try:
        assert restored.info == snapshots[0].source_info
        assert restored.bookmarks() == {1: "Note <exacte>"}
        assert snapshots[0].view.search == "élève" and snapshots[0].header_state == b"header"
        assert Path(restored.info["path"]).read_text().endswith(",élève,0009007199254740993\n")
        assert restored.page(View())[0][-1] == "0009007199254740993"
        nested, _ = read_session(
            Path(imported["active_collection"]) / "collection.fireblade-session"
        )
        assert nested[0].path == snapshots[0].path and nested[0].source_info == restored.info
    finally:
        restored.close()


def test_changed_source_refuses_export_and_keeps_previous_archive(tmp_path):
    library, data, document, case, source = prepared(tmp_path)
    archive = tmp_path / "case.fireblade-case"
    archive.write_bytes(b"previous valid archive")
    source.write_text("Timestamp,User,ID\nchanged,changed,2\n")
    try:
        with pytest.raises(ValueError, match="Empreinte"):
            export_package(
                library, data, [document], 0, archive, include_sources=True, active_case=case
            )
        assert archive.read_bytes() == b"previous valid archive"
        assert not list(tmp_path.glob("*.partial"))
    finally:
        case.close()


def test_import_rejects_tampering_and_publishes_no_case(tmp_path):
    library, data, document, case, source = prepared(tmp_path)
    archive = tmp_path / "good.fireblade-case"
    try:
        export_package(library, data, [document], 0, archive, active_case=case)
    finally:
        case.close()
    bad = tmp_path / "bad.fireblade-case"
    with zipfile.ZipFile(archive) as original, zipfile.ZipFile(bad, "w") as rewritten:
        for item in original.infolist():
            payload = original.read(item)
            if item.filename.endswith(".timeline"):
                payload = payload[:-1] + bytes([payload[-1] ^ 1])
            rewritten.writestr(item, payload)
    target = InvestigationLibrary(tmp_path / "target")
    with pytest.raises(ValueError, match="SHA-256"):
        import_package(target, bad)
    assert target.list() == ([], [])
    assert not list(target.root.glob(".import-*"))


@pytest.mark.parametrize(
    "name",
    ["../outside", "/outside", "C:/outside", "a\\outside", "NUL.csv", "folder/file.", "folder/a?b"],
)
def test_unsafe_archive_paths_are_rejected(tmp_path, name):
    archive = tmp_path / "unsafe.fireblade-case"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr(name, b"bad")
    with pytest.raises(ValueError):
        import_package(InvestigationLibrary(tmp_path / "cases"), archive)
    assert not (tmp_path / "outside").exists()


def test_cancellation_keeps_existing_archive_and_cleans_staging(tmp_path):
    library, data, document, case, source = prepared(tmp_path)
    archive = tmp_path / "case.fireblade-case"
    archive.write_bytes(b"previous")
    cancelled = threading.Event()
    cancelled.set()
    try:
        with cancellation_scope(cancelled), pytest.raises(OperationCancelled):
            export_package(library, data, [document], 0, archive, active_case=case)
        assert archive.read_bytes() == b"previous"
        assert not list(tmp_path.glob("*.partial"))
    finally:
        case.close()


def test_relocation_preserves_source_values_headers_and_filter_literals(tmp_path):
    from fireblade.core.case_package import relocate

    original = "/old/source.csv"
    replacement = "/new/sources/0000.csv"
    value = dict(
        path=original,
        source=dict(path=original, headers=[original]),
        view=dict(search=original, filters=[dict(column=0, operator="eq", value=original)]),
        columns={"/old/analysis.timeline": 2},
        sources=["/old/analysis.timeline"],
    )
    result = relocate(
        value, {original: replacement, "/old/analysis.timeline": "/new/analysis.timeline"}
    )
    assert result["path"] == replacement and result["source"]["path"] == replacement
    assert result["source"]["headers"] == [original] and result["view"] == value["view"]
    assert result["columns"] == {"/new/analysis.timeline": 2} and result["sources"] == [
        "/new/analysis.timeline"
    ]


def test_import_size_budget_prevents_case_creation(tmp_path, monkeypatch):
    import fireblade.core.case_package as module

    library, data, document, case, source = prepared(tmp_path)
    archive = tmp_path / "case.fireblade-case"
    try:
        export_package(library, data, [document], 0, archive, active_case=case)
    finally:
        case.close()
    target = InvestigationLibrary(tmp_path / "target")
    monkeypatch.setattr(module, "MAX_BYTES", 1)
    with pytest.raises(ValueError, match="64 Gio"):
        import_package(target, archive)
    assert target.list() == ([], []) and not list(target.root.glob(".import-*"))


def test_ioc_hunts_survive_portable_case_without_rewriting_observations(tmp_path):
    from fireblade.core.ioc_hunt import parse_indicators
    from fireblade.core.ioc_results import HuntStore, discover_hunts, hunt
    from fireblade.core.workspace_reader import WorkspaceReader

    library, data, document, case, source = prepared(tmp_path)
    source.write_text(source.read_text() + "2026-01-02,example.org,2\n")
    case.close()
    case = Case(tmp_path / "ioc-analysis.timeline")
    case.import_csv(source)
    document = AnalysisSnapshot(str(case.path), case.info, View(), b"")
    store = hunt(
        WorkspaceReader([document], active=case),
        parse_indicators("example.org"),
        library.folder(data["id"]) / "IOC-hunts",
    )
    original = store.page()["rows"][0][6:10]
    store.close()
    archive = tmp_path / "case.fireblade-case"
    try:
        export_package(
            library, data, [document], 0, archive, include_sources=True, active_case=case
        )
    finally:
        case.close()
    target = InvestigationLibrary(tmp_path / "restored")
    result = import_package(target, archive)
    runs, errors = discover_hunts(target.folder(result["case"]["id"]) / "IOC-hunts")
    assert len(runs) == 1 and not errors
    restored = HuntStore(runs[0]["path"])
    try:
        assert restored.page()["rows"][0][6:10] == original
        assert Path(restored.sources()[0]["path"]).is_file()
        assert restored.sources()[0]["path"] != document.path
        assert Path(restored.sources()[0]["info"]["path"]).is_file()
    finally:
        restored.close()


def test_coverage_history_and_last_audit_are_transported_with_references(tmp_path):
    from fireblade.core.coverage import (
        FORMAT,
        audit,
        event,
        load_report,
        load_state,
        save_report,
        save_state,
    )
    from fireblade.core.workspace_reader import WorkspaceReader

    library, data, document, case, source = prepared(tmp_path)
    folder = library.folder(data["id"])
    save_state(
        folder / "coverage-state.json",
        dict(
            format=FORMAT,
            version=1,
            events=[
                event(
                    "Import", "info", "Original " + str(source), document.path, source=str(source)
                )
            ],
            dropped=0,
        ),
    )
    report = audit(WorkspaceReader([document], active=case))
    save_report(folder / "coverage-last.json", report)
    archive = tmp_path / "case.fireblade-case"
    try:
        export_package(
            library, data, [document], 0, archive, include_sources=True, active_case=case
        )
    finally:
        case.close()
    target = InvestigationLibrary(tmp_path / "new-cases")
    result = import_package(target, archive)
    restored = target.folder(result["case"]["id"])
    state = load_state(restored / "coverage-state.json")
    last = load_report(restored / "coverage-last.json")
    assert state["events"][0]["reason"] == "Original " + str(source)
    assert (
        Path(state["events"][0]["path"]).is_file() and state["events"][0]["path"] != document.path
    )
    assert Path(last["sources"][0]["path"]).is_file() and last["stale"]


def test_export_snapshots_locked_database_and_preserves_derived_columns(tmp_path, monkeypatch):
    library, data, document, case, source = prepared(tmp_path)
    archive = tmp_path / "snapshot.fireblade-case"
    original_open = Path.open

    def reject_live_database_read(path, mode="r", *args, **kwargs):
        if path.resolve() == case.path.resolve() and "r" in mode:
            raise PermissionError("Simulated Windows DuckDB file lock")
        return original_open(path, mode, *args, **kwargs)

    try:
        case.add_derived_columns(
            [dict(name="UserCopy", operation="expression", expression="[User]")]
        )
        expected = case.page(View())
        monkeypatch.setattr(Path, "open", reject_live_database_read)
        export_package(library, data, [document], 0, archive, active_case=case)
        assert case.page(View()) == expected
        case.bookmark(1, "Still writable after snapshot")
        assert case.bookmarks()[1] == "Still writable after snapshot"
    finally:
        case.close()
    imported_library = InvestigationLibrary(tmp_path / "imported")
    imported = import_package(imported_library, archive)["case"]
    snapshots, _ = read_session(imported_library.session_path(imported))
    restored = Case(snapshots[0].path)
    try:
        assert restored.page(View()) == expected
        assert restored.headers[-1] == "UserCopy"
        assert restored.bookmarks()[1] == "Note <exacte>"
    finally:
        restored.close()


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"\x00" * 13 + b"\x00" * 20


def test_the_workspace_and_the_destruction_certificate_travel_with_the_case(tmp_path):
    library, data, document, case, source = prepared(tmp_path)
    folder = library.folder(data["id"])
    case_workspace.add_action(
        folder,
        "Réinitialiser les comptes",
        owner="client",
        status="waiting_client",
        intervenant="Direction SI",
        machine="SRV-DC01",
    )
    case_workspace.add_ioc(folder, "evil.example", status="confirmed", machine="SRV-DC01")

    def client(workspace):
        workspace["client"].update(name="ACME", reference="REF-1")

    case_workspace.mutate(folder, client)
    evidence = folder / "preuves"
    evidence.mkdir()
    victim = evidence / "journal.txt"
    victim.write_text("preuve" * 40)
    record = destruction.destroy(destruction.plan([victim], folder), "dod3", operator="op")
    photo = tmp_path / "photo.png"
    photo.write_bytes(PNG)
    record["attachments"] = destruction_certificate.store_attachments(folder, [photo], ["Capture"])
    destruction.store_record(folder, record)
    try:
        archive = tmp_path / "case.fireblade-case"
        export_package(
            library,
            data,
            [document],
            0,
            archive,
            include_sources=True,
            active_case=case,
            include_extra_files=True,
        )
    finally:
        case.close()

    target = InvestigationLibrary(tmp_path / "ailleurs" / "cases")
    imported = import_package(target, archive)["case"]
    restored_folder = target.folder(imported["id"])
    restored = case_workspace.load(restored_folder)
    assert restored["client"]["name"] == "ACME" and restored["client"]["reference"] == "REF-1"
    assert restored["actions"][0]["title"] == "Réinitialiser les comptes"
    assert restored["actions"][0]["intervenant"] == "Direction SI"
    assert restored["iocs"][0]["value"] == "evil.example"
    records = destruction.load_records(restored_folder)
    assert records and records[0]["files"][0]["sha256_before"]
    attachment = (
        case_workspace.data_folder(restored_folder) / records[0]["attachments"][0]["relative"]
    )
    assert attachment.is_file(), "the photo did not travel with the case"
    html = destruction_certificate.build(records[0], case_folder=restored_folder)["html"]
    assert "data:image/png;base64," in html
