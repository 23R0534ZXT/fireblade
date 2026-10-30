"""Build and verify Windows x64; host Python needs only its standard library."""
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys
from zipfile import ZipFile, ZIP_DEFLATED

from scripts.verify_windows import verify


def main():
    if os.name != "nt" or struct.calcsize("P") != 8 or not (3, 11) <= sys.version_info[:2] < (3, 14):
        raise SystemExit("Utilisez Python 3.12 64 bits sur Windows (3.11 et 3.13 également prévus).")
    root = Path(__file__).resolve().parent.parent
    os.chdir(root)
    environment = root / ".venv-build"
    subprocess.run([sys.executable, "-m", "venv", "--clear", str(environment)], check=True)
    python = environment / "Scripts" / "python.exe"
    subprocess.run([str(python), "-m", "pip", "install", "--only-binary=:all:",
                    "-r", "requirements.txt", "pyinstaller>=6,<7"], check=True)
    subprocess.run([str(python), "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
                    "--onedir", "--name", "TimelineNext", "--collect-all", "duckdb",
                    # DuckDB's native bindings load these value types dynamically.
                    "--hidden-import", "decimal", "--hidden-import", "uuid",
                    "--hidden-import", "fractions", "launch.py"], check=True)
    destination = root / "dist" / "TimelineNext"
    for source, name in [("timeline-next.toml", "timeline-next.toml"),
                         ("Verifier-Windows.cmd", "Verifier-Windows.cmd"),
                         ("docs/DEMARRAGE-WINDOWS.txt", "LIRE-MOI.txt"),
                         ("examples/demo.csv", "exemple.csv"), ("LICENSE", "LICENSE")]:
        shutil.copy2(root / source, destination / name)
    build_info = dict(platform="Windows x64", python=sys.version.split()[0], machine=platform.machine(),
                      source_commit=os.environ.get("GITHUB_SHA"), maturity="prototype")
    (destination / "build-info.json").write_text(json.dumps(build_info, indent=2), encoding="utf-8")
    report_path = root / "artifacts" / "windows-portable.json"
    if report_path.exists():
        report_path.unlink()
    verify(destination / "TimelineNext.exe", report_path)
    shutil.copy2(report_path, destination / "verification-windows.json")
    archive_path = root / "dist" / "TimelineNext-Windows-x64.zip"
    with ZipFile(archive_path, "w", ZIP_DEFLATED) as archive:
        for file in sorted(destination.rglob("*")):
            if file.is_file():
                archive.write(file, Path("TimelineNext") / file.relative_to(destination))
    print(f"Portable Windows vérifié : {archive_path}")


if __name__ == "__main__":
    main()
