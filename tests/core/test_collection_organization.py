"""What the three import layouts actually produce.

A folder of a hundred EVTX files is the case these tests are written for: "one grid per
artifact family" must give one EVTX grid, not a hundred, and "one grid for everything"
must give a single grid whose grouping cannot be removed.
"""

import threading
from pathlib import Path

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

    with open(path, encoding="utf-8", newline="") as stream:
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
