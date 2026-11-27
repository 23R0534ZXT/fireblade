"""What the three import layouts actually produce.

A folder of a hundred EVTX files is the case these tests are written for: "one grid per
artifact family" must give one EVTX grid, not a hundred, and "one grid for everything"
must give a single grid whose grouping cannot be removed.
"""

import threading
from pathlib import Path

import pytest

from fireblade.core.collection_organization import organize
from fireblade.core.engine import Case
from fireblade.core.models import View


def analysis(root, name, headers, rows):
    source = root / (name + ".csv")
    source.write_text(
        ",".join(headers) + "\n" + "\n".join(",".join(map(str, row)) for row in rows) + "\n",
        encoding="utf-8",
    )
    case = Case(root / (name + ".timeline"))
    try:
        info = case.import_csv(source)
        return dict(path=str(case.path), source=info)
    finally:
        case.close()


class FakeCollection:
    """The shape organize() needs, without parsing a single byte of evidence."""

    def __init__(self, root, documents, files, organization):
        self.output = root / "collection"
        (self.output / "results").mkdir(parents=True)
        self.settings = None
        self._case_lock = threading.Lock()
        self._active_case = None
        self.report = dict(
            organization=organization, documents=[dict(doc) for doc in documents], files=files
        )

    def progress(self, message):
        pass

    def import_result(self, target, tool, view=None, register=False):
        merged = self.output / "results" / (target.stem + "-.timeline")
        case = Case(merged)
        try:
            info = case.import_csv(target)
        finally:
            case.close()
        return dict(
            path=str(case.path),
            source=dict(info, csv=str(target)),
            view=View(groups=[0]).to_json() if view else View().to_json(),
            header="",
        )


def evidence(root):
    documents = [
        analysis(
            root,
            "evtx-app",
            ["TimeCreated", "EventId", "Channel"],
            [["2026-11-17 10:00", 4624, "Application"]],
        ),
        analysis(
            root,
            "evtx-system",
            ["TimeCreated", "EventId", "Channel"],
            [["2026-11-17 10:01", 7045, "System"]],
        ),
        analysis(
            root,
            "evtx-security",
            ["TimeCreated", "EventId", "Channel"],
            [["2026-11-17 10:02", 4625, "Security"]],
        ),
        analysis(root, "amcache", ["Application Name", "SHA1"], [["update.exe", "aa"]]),
    ]
    files = [
        dict(
            path="C:/evidence/Security.evtx",
            runs=[
                dict(
                    tool="EvtxECmd",
                    outputs=[dict(csv="Security.csv", analysis=documents[2]["path"])],
                )
            ],
        ),
        dict(
            path="C:/evidence/Application.evtx",
            runs=[
                dict(
                    tool="EvtxECmd",
                    outputs=[dict(csv="Application.csv", analysis=documents[0]["path"])],
                )
            ],
        ),
        dict(
            path="C:/evidence/System.evtx",
            runs=[
                dict(
                    tool="EvtxECmd", outputs=[dict(csv="System.csv", analysis=documents[1]["path"])]
                )
            ],
        ),
        dict(
            path="C:/evidence/Amcache.hve",
            runs=[
                dict(
                    tool="AmcacheParser",
                    outputs=[dict(csv="Amcache.csv", analysis=documents[3]["path"])],
                )
            ],
        ),
    ]
    return documents, files


def read_rows(path):
    import csv

    with open(path, encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def test_by_artifact_merges_every_evtx_into_one_grid(tmp_path):
    documents, files = evidence(tmp_path)
    collection = FakeCollection(tmp_path, documents, files, "artifacts")
    organize(collection)
    merged = collection.report["documents"]
    assert len(merged) == 2, [Path(doc["path"]).name for doc in merged]
    names = {Path(doc["source"]["csv"]).stem: doc for doc in merged}
    assert set(names) == {"EVTX", "Amcache"}
    rows = read_rows(names["EVTX"]["source"]["csv"])
    assert len(rows) == 3
    assert {row["Channel"] for row in rows} == {"Application", "System", "Security"}
    assert all(row["Parseur"] == "EvtxECmd" for row in rows)
    assert len(collection.report["raw_documents"]) == 4


def test_one_grid_for_everything_keeps_a_fixed_grouping(tmp_path):
    documents, files = evidence(tmp_path)
    collection = FakeCollection(tmp_path, documents, files, "combined")
    organize(collection)
    merged = collection.report["documents"]
    assert len(merged) == 1
    assert Path(merged[0]["path"]).name.startswith("Collecte complète")
    rows = read_rows(merged[0]["source"]["csv"])
    assert len(rows) == 4
    assert {row["Artefact"] for row in rows} == {"EVTX", "Amcache"}


def test_the_per_file_layout_organizes_nothing(tmp_path):
    documents, files = evidence(tmp_path)
    collection = FakeCollection(tmp_path, documents, files, "files")
    organize(collection)
    assert len(collection.report["documents"]) == 4
    assert "raw_documents" not in collection.report


def test_wide_combined_collection_is_one_queryable_portable_grid(tmp_path, monkeypatch):
    from fireblade.core import collection_organization
    from fireblade.core.models import Filter

    documents, files = evidence(tmp_path)
    collection = FakeCollection(tmp_path, documents, files, "combined")
    collection._cases = set()
    (collection.output / "analyses").mkdir()
    monkeypatch.setattr(collection_organization, "MAX_COLUMNS", 3)
    organize(collection)
    merged = collection.report["documents"]
    assert len(merged) == 1
    assert len(collection.report["raw_documents"]) == 4
    case = Case(merged[0]["path"])
    try:
        assert case.info["rows"] == 4
        assert case.sparse
        assert len(case.headers) == 9
        event = case.headers.index("EventId")
        rows = case.page(View(filters=[Filter(event, "eq", "4625")]))
        assert len(rows) == 1
        assert rows[0][event + 1] == "4625"
        assert case.page(View(search="update.exe"))[0][-2:] == ("update.exe", "aa")
        assert case.count(View()) == 4
        assert merged[0]["view"]["groups"] == [0]
        from fireblade.core.models import SortKey

        ordered = case.page(View(sorts=[SortKey(event, "number", True)]))
        assert [row[event + 1] for row in ordered] == ["7045", "4625", "4624", None]
        assert sorted(case.page(View(groups=[0]))) == [("Amcache", 1), ("EVTX", 3)]
        case.bookmark(3, "reviewed")
        assert case.page(View(bookmarks_only=True))[0][0] == 3
        target = tmp_path / "selected.csv"
        case.export(target, View(filters=[Filter(event, "eq", "4625")]), columns=[0, event])
        assert list(read_rows(target)) == [{"Artefact": "EVTX", "EventId": "4625"}]
        case.export(target, View(bookmarks_only=True), include_annotations=True)
        exported = list(read_rows(target))
        assert len(exported) == 1 and exported[0]["EventId"] == "4625"
        assert exported[0]["Fireblade_Note"] == "reviewed"
        case.add_derived_columns(
            [{"name": "Event copy", "operation": "expression", "expression": "[EventId]"}]
        )
        assert case.page(View(filters=[Filter(event, "eq", "4625")]))[0][-1] == "4625"
    finally:
        case.close()
    reopened = Case(merged[0]["path"])
    try:
        assert reopened.rows_by_ids([3])[3][event + 1] == "4625"
        assert reopened.page(View(search="update.exe"))[0][-3:] == ("update.exe", "aa", None)
        assert reopened.bookmarks() == {3: "reviewed"}
    finally:
        reopened.close()


def test_sparse_combined_chronology_and_ioc_keep_original_fields(tmp_path, monkeypatch):
    import json

    from fireblade.core import collection_organization
    from fireblade.core.ioc_hunt import parse_indicators
    from fireblade.core.ioc_results import hunt
    from fireblade.core.models import AnalysisSnapshot
    from fireblade.core.timeline import TimelineStore
    from fireblade.core.workspace_reader import WorkspaceReader

    documents, files = evidence(tmp_path)
    collection = FakeCollection(tmp_path, documents, files, "combined")
    collection._cases = set()
    (collection.output / "analyses").mkdir()
    monkeypatch.setattr(collection_organization, "MAX_COLUMNS", 3)
    organize(collection)
    item = collection.report["documents"][0]
    doc = AnalysisSnapshot(
        item["path"], item["source"], View.from_json(json.dumps(item["view"])), b""
    )
    from fireblade.core.investigation_report import build_report

    report = build_report(
        WorkspaceReader([doc]), "Sparse evidence", bookmarks_only=False, row_ids={doc.path: [4]}
    )
    assert report["records"] == 1 and not report["errors"]
    assert "<th>Application Name</th><td><pre>update.exe</pre>" in report["html"]
    assert "<th>SHA1</th><td><pre>aa</pre>" in report["html"]
    timeline = TimelineStore(memory_mb=128)
    try:
        sources = timeline.build(WorkspaceReader([doc]), {})
        assert [(source["rows"], source["dated"]) for source in sources] == [(4, 3)]
        assert timeline.page(text="Security")["count"] == 1
    finally:
        timeline.close()
    store = hunt(WorkspaceReader([doc]), parse_indicators("update.exe"), tmp_path / "hunts")
    try:
        assert store.metadata["scanned_rows"] == 4
        assert store.metadata["matching_fields"] == 1
        assert store.page()["count"] == 1
    finally:
        store.close()
    from fireblade.core.case_package import export_package, import_package
    from fireblade.core.investigations import InvestigationLibrary
    from fireblade.core.sessions import read_session

    library = InvestigationLibrary(tmp_path / "cases")
    data = library.create("Sparse portable", "")
    data = library.save(data["id"], [doc], 0, [], None, data["revision"])
    package = tmp_path / "combined.fireblade-case"
    export_package(library, data, [doc], 0, package, include_sources=True)
    destination = InvestigationLibrary(tmp_path / "restored")
    restored = import_package(destination, package)["case"]
    snapshots, active = read_session(destination.session_path(restored))
    assert active == 0 and len(snapshots) == 1
    portable = Case(snapshots[0].path)
    try:
        assert portable.sparse and portable.count(View()) == 4
        assert portable.page(View(search="update.exe"))[0][-2:] == ("update.exe", "aa")
    finally:
        portable.close()


def test_cancelled_sparse_build_keeps_sources_and_publishes_nothing(tmp_path, monkeypatch):
    from fireblade.core import collection as collection_module
    from fireblade.core import collection_organization
    from fireblade.core.errors import OperationCancelled

    documents, files = evidence(tmp_path)
    collection = FakeCollection(tmp_path, documents, files, "combined")
    collection._cases = set()
    (collection.output / "analyses").mkdir()
    monkeypatch.setattr(collection_organization, "MAX_COLUMNS", 3)
    before = {doc["path"]: Path(doc["path"]).read_bytes() for doc in documents}
    checks = 0

    def cancel_after_copy():
        nonlocal checks
        checks += 1
        if checks == 2:
            raise OperationCancelled()

    monkeypatch.setattr(collection_module, "check_cancel", cancel_after_copy)
    with pytest.raises(OperationCancelled):
        organize(collection)
    assert collection.report["documents"] == documents
    assert "raw_documents" not in collection.report
    assert not collection._cases and collection._active_case is None
    assert not list((collection.output / "analyses").iterdir())
    assert not list((collection.output / "results").iterdir())
    assert before == {doc["path"]: Path(doc["path"]).read_bytes() for doc in documents}


def test_combined_timeline_uses_common_time_when_an_original_timestamp_is_not_a_date(
    tmp_path, monkeypatch
):
    from fireblade.core import collection_organization
    from fireblade.core.models import AnalysisSnapshot
    from fireblade.core.timeline import TimelineStore
    from fireblade.core.workspace_reader import WorkspaceReader

    documents, files = evidence(tmp_path)
    telemetry = analysis(
        tmp_path, "configuration", ["Timestamp", "Setting"], [["not-a-date", "true"]]
    )
    documents.append(telemetry)
    files.append(
        dict(
            path="configuration.csv",
            runs=[
                dict(
                    tool="native",
                    outputs=[dict(csv="configuration.csv", analysis=telemetry["path"])],
                )
            ],
        )
    )
    event_time = "2026-11-17T10:03:00Z"
    network = analysis(
        tmp_path, "network", ["TimeCreated", "SourceIP"], [[event_time, "192.0.2.21"]]
    )
    documents.append(network)
    files.append(
        dict(
            path="network.csv",
            runs=[dict(tool="native", outputs=[dict(csv="network.csv", analysis=network["path"])])],
        )
    )
    collection = FakeCollection(tmp_path, documents, files, "combined")
    collection._cases = set()
    (collection.output / "analyses").mkdir()
    monkeypatch.setattr(collection_organization, "MAX_COLUMNS", 3)
    organize(collection)
    item = collection.report["documents"][0]
    # Ignoring grid filters must not make an unrelated Timestamp column the
    # clock of every file in the combined collection.
    document = AnalysisSnapshot(item["path"], item["source"], View(), b"")
    store = TimelineStore(memory_mb=128)
    try:
        sources = store.build(WorkspaceReader([document]), {})
        assert sources[0]["rows"] == 6 and sources[0]["dated"] == 4
        assert sources[0]["column"] == 3
        explicit = item["source"]["headers"].index("Timestamp")
        sources = store.build(WorkspaceReader([document]), {document.path: explicit})
        assert sources[0]["column"] == explicit and sources[0]["dated"] == 0
    finally:
        store.close()
    from fireblade.core.ioc_hunt import parse_indicators
    from fireblade.core.ioc_results import hunt

    hunted = hunt(WorkspaceReader([document]), parse_indicators("192.0.2.21"), tmp_path / "hunts")
    try:
        assert hunted.page()["rows"][0][8] == event_time
    finally:
        hunted.close()


@pytest.mark.parametrize("storage_format", ["sparse-union-v1", "unrecognized"])
def test_received_analysis_cannot_claim_an_incompatible_storage_format(tmp_path, storage_format):
    import json

    document = analysis(tmp_path, "source", ["Field", "Value"], [["a", "b"]])
    case = Case(document["path"])
    info = dict(case.info, storage_format=storage_format)
    case.db.execute("UPDATE metadata SET value=? WHERE key='source'", [json.dumps(info)])
    case.close()
    with pytest.raises(ValueError, match="stockage|Schéma"):
        Case(document["path"])
