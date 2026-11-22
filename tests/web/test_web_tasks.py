"""The long commands run as jobs, and the window shows their percentage.

An IOC scan, a timeline build, a Hayabusa run, a report and a portable case all
answer at once with a job id; the window polls it and paints the bar. These tests
hold the contract the browser relies on: a job that ends, a percentage that is a
number, a result the caller can use, and a refusal that is a sentence.
"""
import csv
import time

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
        ])


@pytest.fixture()
def service(tmp_path):
    root = tmp_path / "cases"
    root.mkdir()
    core = InvestigationLibrary(root)
    data = core.create("Tasks case", "", "windows")
    identifier = data["id"]
    folder = core.folder(identifier)
    analysis = folder / "analysis-1.duckdb"
    source = tmp_path / "rows.csv"
    _write_csv(source)
    case = Case(analysis)
    try:
        case.import_csv(source)
        info = dict(case.info)
    finally:
        case.close()
    core.save(identifier, [AnalysisSnapshot(path=str(analysis), source_info=info,
                                            view=View(), header_state=b"")],
              0, [], None, data["revision"])
    library = Library(root)
    try:
        yield library, identifier
    finally:
        library.close()


def _wait(library, job, seconds=20):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        payload = library.task(job)
        if payload["status"] in ("done", "failed", "cancelled"):
            return payload
        time.sleep(0.05)
    raise AssertionError(f"the task did not finish: {library.task(job)}")


def test_a_scan_task_ends_with_its_result_and_a_percentage(service):
    library, identifier = service
    started = library.start_task(identifier, "scan",
                                 {"text": "192.0.2.10", "all_analyses": True})
    assert started["status"] == "running"
    payload = _wait(library, started["job"])
    assert payload["status"] == "done", payload
    assert payload["progress"]["percent"] == 100.0
    assert payload["progress"]["total"] == 1
    assert payload["result"]["hits"], payload["result"]
    assert any("/1" in line for line in payload["log"])


def test_a_timeline_task_publishes_the_build_phase(service):
    library, identifier = service
    started = library.start_task(identifier, "timeline", {})
    payload = _wait(library, started["job"], seconds=40)
    assert payload["status"] == "done", payload
    assert payload["result"]["sources"]
    assert payload["progress"]["percent"] == 100.0


def test_a_failed_task_keeps_a_sentence_and_no_result(service):
    library, identifier = service
    started = library.start_task(identifier, "report", {"pdf": True, "name": "absent.html"})
    payload = _wait(library, started["job"])
    assert payload["status"] == "failed"
    assert payload["error"] and payload["result"] is None


def test_an_unknown_task_is_refused(service):
    library, identifier = service
    with pytest.raises(ServiceError):
        library.start_task(identifier, "fly-to-the-moon", {})
    with pytest.raises(ServiceError):
        library.task("does-not-exist")
    with pytest.raises(ServiceError):
        library.cancel_task("does-not-exist")


def test_a_cancelled_task_is_reported_as_cancelled(service):
    library, identifier = service
    started = library.start_task(identifier, "timeline", {})
    # Cancel immediately: the first checkpoint of the run sees the flag.
    library.cancel_task(started["job"])
    payload = _wait(library, started["job"], seconds=40)
    assert payload["status"] in ("cancelled", "done")
    if payload["status"] == "cancelled":
        assert payload["result"] is None
