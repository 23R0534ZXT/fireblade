"""SRUM on Linux: SrumECmd cannot start there, the native reader takes SRUDB.dat."""

import os
from pathlib import Path

import pytest

SAMPLE = os.environ.get("FIREBLADE_SRUM_SAMPLE", "")


def test_a_srudb_is_read_by_the_native_reader_where_srumecmd_cannot_run(tmp_path, monkeypatch):
    from fireblade.core import collection

    probe = tmp_path / "SRUDB.dat"
    probe.write_bytes(b"\x00" * 64)
    monkeypatch.setattr(collection, "WINDOWS", False)
    assert collection.identify(probe) == ["SRUM"]
    monkeypatch.setattr(collection, "WINDOWS", True)
    assert collection.identify(probe) == ["SrumECmd"]


@pytest.mark.skipif(not SAMPLE, reason="set FIREBLADE_SRUM_SAMPLE to a real SRUDB.dat")
def test_a_real_srudb_becomes_one_table_per_provider_with_its_applications_and_dates(tmp_path):
    from fireblade.core.srum import parse

    result = parse(Path(SAMPLE), tmp_path)
    tables = {item["table"]: item["rows"] for item in result["outputs"]}
    assert tables and all(count > 0 for count in tables.values())
    first = Path(result["outputs"][0]["csv"]).read_text(encoding="utf-8").splitlines()
    assert first[0].startswith("SRUM_Table,SRUM_Record,Timestamp,Application,User")
    assert "T" in first[1].split(",")[2], "the timestamp reads as a date"
