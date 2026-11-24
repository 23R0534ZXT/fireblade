"""A merged family that runs out of memory must not take the collection with it."""

import duckdb

from fireblade.core.collection import Collection, ToolPack


def test_a_family_too_big_for_memory_stays_separate_and_says_why(tmp_path, monkeypatch):
    root = tmp_path / "evidence"
    root.mkdir()
    (root / "a.csv").write_text("User,Value\nalice,1\n", encoding="utf-8")
    (root / "b.csv").write_text("User,Value\nbob,2\n", encoding="utf-8")
    collection = Collection(
        root, tmp_path / "work", ToolPack(tmp_path / "pack"), organization="artifacts"
    )
    original = Collection.import_result

    def out_of_memory(self, csv, kind, view=None, register=True, evidence=None):
        if kind == "organized":
            raise duckdb.OutOfMemoryException(
                "Out of Memory Error: failed to pin block of size 256.0 KiB (60.8 MiB/61.0 MiB used)"
            )
        return original(self, csv, kind, view=view, register=register, evidence=evidence)

    monkeypatch.setattr(Collection, "import_result", out_of_memory)
    report = collection.parse()

    failures = report.get("organization_failures", [])
    assert failures and "Out of Memory" in failures[0]["reason"]
    assert failures[0]["artifact"], "la famille concernée doit être nommée"
    assert report["status"] == "complete", "la collecte reste utilisable"
    assert report["documents"], "les analyses d'origine sont conservées"
    assert report["raw_documents"]


def test_a_collection_that_needs_no_merge_records_no_failure(tmp_path):
    root = tmp_path / "evidence"
    root.mkdir()
    (root / "a.csv").write_text("User,Value\nalice,1\n", encoding="utf-8")
    collection = Collection(
        root, tmp_path / "work", ToolPack(tmp_path / "pack"), organization="artifacts"
    )
    report = collection.parse()
    assert "organization_failures" not in report
    assert report["documents"]
