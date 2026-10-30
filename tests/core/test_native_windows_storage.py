"""Actual Windows filesystem integration; SMB is opt-in for disposable runners."""

import csv
import hashlib
import os
from pathlib import Path
import subprocess
import uuid
import pytest
from fireblade.core.engine import Case
from fireblade.core.models import View, Filter
from fireblade.core.paths import same_file


def test_hardlink_alias_never_overwrites_evidence(tmp_path):
    source = tmp_path / "proof.csv"
    source.write_text("ID\n001\n")
    alias = tmp_path / "alias.csv"
    os.link(source, alias)
    case = Case(tmp_path / "case.timeline")
    try:
        case.import_csv(source)
        with pytest.raises(ValueError):
            case.export(alias, View())
        assert source.read_bytes() == alias.read_bytes()
    finally:
        case.close()


@pytest.mark.skipif(os.name != "nt", reason="Native Windows long-path integration")
def test_windows_extended_long_unicode_paths(tmp_path):
    base = tmp_path
    for i in range(7):
        base = base / ("preuve été numéro " + str(i) + "_" + "x" * 32)
    long = Path("\\\\?\\" + str(base.resolve()))
    long.mkdir(parents=True)
    source = long / "source.csv"
    source.write_text("ID,Text\n001,évidence\n", encoding="utf-8")
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    case = Case(long / "analysis.timeline")
    try:
        case.import_csv(source)
        assert case.page(View()) == [(1, "001", "évidence")]
        case.export(long / "export.csv", View())
        assert (
            len(list(csv.reader((long / "export.csv").open(encoding="utf-8-sig")))) == 2
        )
        assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    finally:
        case.close()


@pytest.mark.skipif(
    os.name != "nt" or os.environ.get("FIREBLADE_TEST_SMB") != "1",
    reason="Requires an explicitly enabled disposable Windows SMB runner",
)
def test_actual_unc_import_export_reopen_and_source_alias_protection(tmp_path):
    name = "FirebladeQA" + uuid.uuid4().hex[:12]
    # Paths are passed as argv, never interpolated into PowerShell code.
    create = tmp_path / "share.ps1"
    create.write_text("""param([string]$Share,[string]$Directory)
$ErrorActionPreference='Stop'
Start-Service LanmanServer
$account=[Security.Principal.WindowsIdentity]::GetCurrent().Name
New-SmbShare -Name $Share -Path $Directory -FullAccess $account | Out-Null
""")
    source = tmp_path / "source.csv"
    source.write_text("ID,User\n001,alice\n002,bob\n")
    original = hashlib.sha256(source.read_bytes()).hexdigest()
    created = False
    case = None
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-File", str(create), name, str(tmp_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        created = True
        unc = Path("\\\\localhost\\" + name)
        assert same_file(source, unc / "source.csv")
        case = Case(tmp_path / "case.timeline")
        case.import_csv(unc / "source.csv")
        assert case.count(View()) == 2
        with pytest.raises(ValueError):
            case.export(source, View())
        case.export(unc / "export.csv", View(filters=[Filter(1, "eq", "alice")]))
        assert list(
            csv.reader((tmp_path / "export.csv").open(encoding="utf-8-sig"))
        ) == [["ID", "User"], ["001", "alice"]]
        case.close()
        case = None
        case = Case(tmp_path / "case.timeline")
        assert case.info["path"].startswith("\\\\localhost\\")
        assert hashlib.sha256(source.read_bytes()).hexdigest() == original
    finally:
        if case:
            case.close()
        if created:
            cleanup = tmp_path / "remove-share.ps1"
            cleanup.write_text(
                "param([string]$Share)\n$ErrorActionPreference='Stop'\nRemove-SmbShare -Name $Share -Force\n"
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-File", str(cleanup), name],
                check=True,
                capture_output=True,
                text=True,
            )
