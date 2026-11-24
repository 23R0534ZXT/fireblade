"""Importing the log shapes an incident actually hands over.

Each test writes a real file of the format and asserts what Fireblade reads out of it:
the columns it keeps, the rows it counts, and the timestamp it understands. A format
that is silently treated as unstructured text is a defect here, not a preference.
"""

import csv
import json
from pathlib import Path

import pytest

from fireblade.core import linux_logs, textreader
from fireblade.core.collection import Collection, ToolPack
from fireblade.core.engine import Case


def read_output(folder):
    rows, headers = [], []
    for path in Path(folder).glob("*.csv"):
        with path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            headers = reader.fieldnames or []
            rows.extend(reader)
    return headers, rows


def test_iis_w3c_log_is_structured_not_raw(tmp_path):
    source = tmp_path / "iis.log"
    source.write_text(
        "#Software: Microsoft Internet Information Services 10.0\r\n"
        "#Version: 1.0\r\n#Date: 2026-11-17 00:00:00\r\n"
        "#Fields: date time s-ip cs-method cs-uri-stem cs-uri-query s-port cs-username c-ip "
        "cs(User-Agent) sc-status sc-substatus sc-win32-status time-taken\r\n"
        "2026-11-17 10:04:10 10.20.0.10 GET /Default.aspx - 443 - 203.0.113.9 Mozilla/5.0 200 0 0 31\r\n"
        "2026-11-17 10:04:12 10.20.0.10 POST /upload.aspx id=7 443 CORP\\jdoe 203.0.113.9 curl/8.0 500 0 0 120\r\n",
        encoding="utf-8",
        newline="",
    )
    out = tmp_path / "out"
    out.mkdir()
    result = linux_logs.parse(source, out)
    headers, rows = read_output(out)
    data = [row for row in rows if row["Lecture"] == "Structured"]
    assert len(data) == 2, rows
    assert [row["Statut"] for row in data] == ["200", "500"]
    assert data[0]["Adresse distante"] == "203.0.113.9"
    assert data[0]["Chemin"] == "/Default.aspx"
    assert data[0]["Horodatage"] == "2026-11-17 10:04:10"
    assert data[1]["Utilisateur"] == "CORP\\jdoe"
    # The four IIS comment lines describe the log; they are not events and not raw data.
    assert len([row for row in rows if row["Lecture"] == "Raw"]) == 0
    assert len([row for row in rows if row["Lecture"] == "Declaration"]) == 4
    assert result["members"][0]["raw_rows"] == 0


def test_windows_event_viewer_csv_keeps_quoted_commas_and_bom(tmp_path):
    source = tmp_path / "events.csv"
    source.write_text(
        '\ufeff"Log Name","Source","Event ID","Level","Time Created","Computer","Description"\r\n'
        '"Security","Microsoft-Windows-Security-Auditing","4624","Information",'
        '"17/11/2026 10:02:44","SRV-DC01","An account was logged on, LogonType 10"\r\n',
        encoding="utf-8",
        newline="",
    )
    collection = Collection([source], tmp_path / "work", ToolPack(tmp_path / "tools"))
    report = collection.parse()
    assert report["status"] == "complete"
    case = Case(report["documents"][0]["path"])
    try:
        assert list(case.headers)[:2] == ["Log Name", "Source"]
        assert case.db.execute("select count(*) from events").fetchone()[0] == 1
        description = case.db.execute(
            "select " + case.column(list(case.headers).index("Description")) + " from events"
        ).fetchone()[0]
        assert "LogonType 10" in description
    finally:
        case.close()


def test_amcache_csv_header_has_no_bom_and_rows_are_read(tmp_path):
    source = tmp_path / "amcache.csv"
    source.write_text(
        '\ufeff"Application Name","File Path","SHA1","File Size"\r\n'
        '"update.exe","C:\\Temp\\u.exe","aabbccddeeff00112233445566778899aabbccdd","102400"\r\n',
        encoding="utf-8",
        newline="",
    )
    collection = Collection([source], tmp_path / "work", ToolPack(tmp_path / "tools"))
    report = collection.parse()
    case = Case(report["documents"][0]["path"])
    try:
        assert list(case.headers) == ["Application Name", "File Path", "SHA1", "File Size"]
        assert case.db.execute("select count(*) from events").fetchone()[0] == 1
    finally:
        case.close()


def test_tab_separated_log_keeps_its_columns(tmp_path):
    source = tmp_path / "events.tsv"
    source.write_text("Time\tEvent\tUser\n2026-11-17 10:00:00\tlogin\tjdoe\n", encoding="utf-8")
    collection = Collection([source], tmp_path / "work", ToolPack(tmp_path / "tools"))
    report = collection.parse()
    case = Case(report["documents"][0]["path"])
    try:
        assert list(case.headers)[:3] == ["Time", "Event", "User"]
        assert case.db.execute("select count(*) from events").fetchone()[0] == 1
    finally:
        case.close()


def test_a_utf16_powershell_transcript_is_read_by_the_text_reader(tmp_path):
    source = tmp_path / "transcript.txt"
    source.write_text(
        "Windows PowerShell transcript start\nPS C:\\> whoami\ncorp\\jdoe\n",
        encoding="utf-16",
        newline="",
    )
    out = tmp_path / "out"
    out.mkdir()
    result = textreader.write_csv(source, out / "text.csv")
    assert result["rows"] == 3
    with (out / "text.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert "whoami" in json.dumps(rows, ensure_ascii=False)


def test_a_cp1252_log_keeps_its_accents(tmp_path):
    source = tmp_path / "cp1252.txt"
    source.write_bytes(
        "2026-11-17 10:00:00 Utilisateur « administrateur » créé à Paris\r\n".encode("cp1252")
    )
    out = tmp_path / "out"
    out.mkdir()
    result = textreader.write_csv(source, out / "text.csv")
    assert result["rows"] == 1
    text = (out / "text.csv").read_text(encoding="utf-8")
    assert "créé à Paris" in text


def test_json_lines_are_recognised_field_by_field():
    line = json.dumps(
        {
            "__REALTIME_TIMESTAMP": "1763400000000000",
            "MESSAGE": "Failed password",
            "_HOSTNAME": "srv-linux",
            "_SYSTEMD_UNIT": "ssh.service",
        }
    )
    fields = linux_logs.text_fields(line)
    assert fields["Format"] == "JSON Lines"
    assert fields["Détail"] == "Failed password"
    assert fields["Hôte"] == "srv-linux"


def test_an_empty_file_is_refused_rather_than_turned_into_an_analysis(tmp_path):
    source = tmp_path / "empty.csv"
    source.write_bytes(b"")
    collection = Collection([source], tmp_path / "work", ToolPack(tmp_path / "tools"))
    report = collection.parse()
    assert report["documents"] == [], "an empty file must not become an analysis"
    entry = report["files"][0]
    assert entry["status"] in ("empty", "error", "attention")
    assert "vide" in json.dumps(entry, ensure_ascii=False) or entry["status"] == "empty"
