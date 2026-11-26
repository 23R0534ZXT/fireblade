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
    header = first[0]
    if header.startswith("Id,Timestamp,ExeInfo"):  # a provider SrumECmd also writes
        assert "T" in first[1].split(",")[1], "the timestamp reads as a date"
    else:
        assert header.startswith("SRUM_Table,SRUM_Record,Timestamp,Application,User")
        assert "T" in first[1].split(",")[2], "the timestamp reads as a date"


def _catalog():
    from fireblade.core import profiles

    return {profile.name: list(profile.signature) for profile in profiles.all_profiles()}


def test_the_native_columns_are_srumecmds_for_every_provider_it_also_writes():
    from fireblade.core.srum import SRUMECMD, srumecmd_header, srumecmd_layout

    catalog = _catalog()
    for provider, (name, wanted, aliases) in SRUMECMD.items():
        columns = ["AutoIncId", "TimeStamp", "AppId", "UserId"] + [
            aliases.get(column, column) for column in wanted
        ]
        layout = srumecmd_layout(provider, columns)
        assert layout is not None, provider
        assert srumecmd_header(layout) == catalog[name], (name, srumecmd_header(layout))


def test_a_provider_the_database_cannot_fill_keeps_its_own_columns():
    from fireblade.core.srum import srumecmd_layout

    assert srumecmd_layout("NetworkUsage", ["AutoIncId", "TimeStamp", "BytesSent"]) is None
    assert srumecmd_layout("SdpCpuProvider", ["ProcessorTime"]) is None, "not a SrumECmd table here"


def test_a_native_row_reads_like_a_srumecmd_row_and_the_desktop_profile_applies():
    from fireblade.core import profiles
    from fireblade.core.srum import srumecmd_header, srumecmd_layout, srumecmd_row

    columns = [
        "AutoIncId", "TimeStamp", "AppId", "UserId", "InterfaceLuid", "L2ProfileId",
        "L2ProfileFlags", "BytesSent", "BytesRecvd",
    ]  # fmt: skip
    layout = srumecmd_layout("NetworkUsage", columns)
    header = srumecmd_header(layout)
    row = srumecmd_row(
        layout,
        7,
        {
            "AutoIncId": 41,
            "AppId": 5,
            "UserId": 9,
            "InterfaceLuid": 71 << 48,
            "BytesSent": 1200,
            "BytesRecvd": 3400,
            "L2ProfileId": 268435456,
            "L2ProfileFlags": 0,
        },
        "2026-11-01T10:00:00",
        r"\Device\HarddiskVolume3\Windows\System32\svchost.exe",
        "S-1-5-18",
    )
    got = dict(zip(header, row))
    assert got["Id"] == "41" and got["Timestamp"] == "2026-11-01T10:00:00"
    assert got["ExeInfo"].endswith("svchost.exe") and got["Sid"] == "S-1-5-18"
    assert got["UserName"] == "LOCAL SYSTEM" and got["SidType"] == "WellKnown"
    assert got["BytesReceived"] == "3400" and got["BytesSent"] == "1200"
    assert got["InterfaceType"] == "IEEE80211"
    assert got["ProfileName"] == "" and got["ExeInfoDescription"] == "", "not guessed"
    assert profiles.detect_profile(header).name == "NetworkUsage"


def test_an_unknown_sid_is_kept_as_a_sid_and_its_name_is_not_invented():
    from fireblade.core.srum import srumecmd_header, srumecmd_layout, srumecmd_row

    layout = srumecmd_layout(
        "PushNotifications",
        [
            "AutoIncId",
            "TimeStamp",
            "AppId",
            "UserId",
            "NetworkType",
            "NotificationType",
            "PayloadSize",
        ],
    )
    got = dict(
        zip(
            srumecmd_header(layout),
            srumecmd_row(
                layout,
                1,
                {"NotificationType": 4, "PayloadSize": 10},
                "",
                "app",
                "S-1-5-21-1-2-3-1001",
            ),
        )
    )
    assert got["Sid"] == "S-1-5-21-1-2-3-1001" and got["SidType"] == "UnknownOrUserSid"
    assert got["UserName"] == "" and got["NotificationType"] == "4"
