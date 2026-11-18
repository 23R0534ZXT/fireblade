"""Build and verify one standalone Fireblade.exe on Windows x64."""
import os
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile

from scripts.windows.verify import verify


def main():
    if os.name != "nt" or struct.calcsize("P") != 8 or not (3, 11) <= sys.version_info[:2] < (3, 14):
        raise SystemExit("Utilisez Python 3.12 64 bits sur Windows (3.11 et 3.13 également prévus).")
    root = Path(__file__).resolve().parents[2]
    os.chdir(root)
    environment = root / ".venv-build"
    subprocess.run([sys.executable, "-m", "venv", "--clear", str(environment)], check=True)
    python = environment / "Scripts" / "python.exe"
    subprocess.run([str(python), "-m", "pip", "install", "--only-binary=:all:",
                    "-r", "requirements/windows-build.txt"], check=True)
    generated = root / "build" / "windows" / "resources"
    if generated.exists():
        shutil.rmtree(generated)
    subprocess.run([str(python), "-m", "scripts.windows.bundle", "--root", str(root),
                    "--destination", str(generated)], check=True)
    from scripts.windows.build_plugin_host import build as build_host
    host=build_host(root,python)
    shutil.copytree(host.parent,generated/"plugin-host",dirs_exist_ok=True)
    shutil.copy2(root/"build/windows/plugin-fixture/Fireblade.PluginFixture.dll",generated/"plugin-host/Fireblade.PluginFixture.dll")
    shutil.copy2(root/"build/windows/plugin-fixture/Fireblade.PluginFunctionsFixture.dll",generated/"plugin-host/Fireblade.PluginFunctionsFixture.dll")
    from scripts.windows.build_forensic_tools import build as build_forensic_tools
    build_forensic_tools(root, generated)
    from scripts.release import application_version
    from scripts.windows.version_info import write_version_file
    version_file=write_version_file(root/"build/windows/version-info.txt",application_version(root))
    staging = root / "build" / "windows" / "output"
    command = [str(python), "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--onedir",
               "--name", "Fireblade", "--version-file", str(version_file), "--paths", str(root / "src"),
               "--distpath", str(staging), "--workpath", str(root / "build" / "windows" / "pyinstaller"),
               "--specpath", str(root / "build" / "windows"), "--collect-all", "duckdb",
               "--collect-all", "lz4", "--collect-all", "zstandard",
               "--collect-all", "dissect.esedb", "--collect-all", "dissect.cstruct", "--collect-all", "dissect.util",
               "--hidden-import", "numpy", "--hidden-import", "decimal", "--hidden-import", "uuid", "--hidden-import", "fractions"]
    for package in ("dissect.target", "dissect.database", "dissect.eventlog", "dissect.evidence",
                    "dissect.hypervisor", "dissect.ntfs", "dissect.regf", "dissect.volume", "dissect.fat", "dissect.extfs", "flow.record"):
        command.extend(["--collect-all", package])
    for source, target in [(generated, "resources"), (root / "config" / "fireblade.toml", "resources/config"),
                           (root / "assets" / "startup", "resources/assets/startup"),
                           (root / "docs" / "guides", "resources/docs/guides"),
                           (root / "examples" / "ioc", "resources/examples/ioc"),
                           (root / "docs" / "assets" / "fireblade-timeline.png", "resources/docs/assets"),
                           (root / "docs" / "assets" / "fireblade-ioc-hunt.png", "resources/docs/assets"),
                           (root / "docs" / "assets" / "fireblade-coverage.png", "resources/docs/assets"),
                           (root / "docs" / "assets" / "fireblade-timeline-correlation.png", "resources/docs/assets"),
                           (root / "docs" / "development", "resources/docs/development"),
                           (root / "docs" / "validation" / "20261101-compatibilite.md", "resources/docs/validation"),
                           (root / "docs" / "validation" / "reports", "resources/docs/validation/reports"),
                           (root / "LICENSE", "resources"),
                           (root / "tests" / "fixtures" / "tle-exports", "resources/qa/tle-exports"),
                           (root / "tests" / "fixtures" / "tle-layouts", "resources/qa/tle-layouts")]:
        command += ["--add-data", f"{source}{os.pathsep}{target}"]
    for source in json.loads((generated.parent / "runtime-binaries.json").read_text(encoding="utf-8")):
        command += ["--add-binary", f"{source}{os.pathsep}."]
    command.append(str(root / "scripts" / "windows" / "entrypoint.py"))
    subprocess.run(command, check=True)
    # PyInstaller --onedir writes a folder: the exe and everything it needs beside it.
    candidate = staging / "Fireblade" / "Fireblade.exe"
    report_path = root / "artifacts" / "windows-bundle.json"
    report_path.unlink(missing_ok=True)
    verify(candidate, report_path)
    destination = root / "dist"
    destination.mkdir(exist_ok=True)
    # A folder build replaces the previous one whole, never file by file.
    bundle = destination / "Fireblade"
    partial = destination / "Fireblade.partial"
    shutil.rmtree(partial, ignore_errors=True)
    shutil.copytree(candidate.parent, partial)
    shutil.rmtree(bundle, ignore_errors=True)
    os.replace(partial, bundle)
    archive = destination / ("Fireblade-%s-win64.zip" % application_version(root))
    partial_zip = archive.with_name(archive.name + ".partial")
    partial_zip.unlink(missing_ok=True)
    import zipfile
    with zipfile.ZipFile(partial_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as stream:
        for path in sorted(bundle.rglob("*")):
            stream.write(path, Path("Fireblade") / path.relative_to(bundle))
    os.replace(partial_zip, archive)
    print(f"Application Windows vérifiée : {bundle}")
    print(f"Archive à distribuer : {archive}")


if __name__ == "__main__":
    main()
