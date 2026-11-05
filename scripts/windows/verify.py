"""Run only the EXE from an empty folder, isolated from host Python and Qt."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def verify(executable, report_path, timeout=360):
    if os.name != "nt":
        raise RuntimeError("Ce contrôle doit être exécuté sur Windows.")
    executable, report_path = Path(executable).resolve(), Path(report_path).resolve()
    if not executable.is_file() or report_path.exists():
        raise ValueError("Choisissez un exécutable existant et un nouveau fichier de rapport.")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    from scripts.release import application_version
    from scripts.windows.version_info import read_version_resource,version_tuple
    version=application_version(Path(__file__).resolve().parents[2])
    resource=read_version_resource(executable)
    expected=list(version_tuple(version))
    if resource["file_version"]!=expected or resource["product_version"]!=expected or resource["FileVersion"]!=version or resource["ProductVersion"]!=version:
        raise ValueError("Windows PE version and application version must match")
    original_hash = hashlib.sha256(executable.read_bytes()).hexdigest()
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "windows"
    environment["PYTHONUTF8"] = "1"
    environment["PYTHONNOUSERSITE"] = "1"
    for key in ("PYTHONHOME", "PYTHONPATH", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH", "QML2_IMPORT_PATH"):
        environment.pop(key, None)
    system_root = Path(environment.get("SystemRoot", r"C:\Windows"))
    environment["PATH"] = os.pathsep.join(map(str, [system_root / "System32", system_root]))
    with tempfile.TemporaryDirectory(prefix="Fireblade fichier unique ") as temporary:
        temporary = Path(temporary)
        copied = temporary / "Application été"
        copied.mkdir()
        target = copied / executable.name
        shutil.copy2(executable, target)  # Deliberately copy no directory, DLL or config.
        extraction = temporary / "Cache Windows"
        extraction.mkdir()
        environment["TEMP"] = environment["TMP"] = str(extraction)
        environment["LOCALAPPDATA"] = str(temporary / "Profil utilisateur")
        process=subprocess.Popen([str(target), "--self-test-report", str(report_path)],env=environment,cwd=temporary)
        try:
            code=process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            # A onefile launcher owns another process. Killing only its parent
            # leaves the real application alive and locks the relocated EXE.
            subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,timeout=10,check=False)
            if process.poll() is None:process.kill()
            process.wait(timeout=10)
            code=-1
        if report_path.is_file():
            raw = report_path.read_text(encoding="utf-8")
            try:
                report = json.loads(raw)
            except json.JSONDecodeError:
                report = dict(status="failed", error="Rapport incomplet", report_tail=raw[-3000:])
        else:
            report = dict(status="failed", error="Le processus n’a pas produit de rapport.")
        adjacent = sorted(p.name for p in copied.iterdir())
        extraction_cleaned = not list(extraction.glob("_MEI*"))
        # The executable runs 47 checks. The threshold is a floor, not the count:
        # it must stay high enough that removing a whole check family (the ten
        # completion checks, which run the .NET hosts for real) fails the build.
        valid = (code == 0 and report.get("status") == "passed" and report.get("frozen") is True
                 and report.get("platform") == "win32" and report.get("pointer_bits") == 64
                 and report.get("qt_platform") == "windows" and report.get("packaging") == "onefile"
                 and len(report.get("checks", [])) >= 40 and adjacent == [executable.name] and extraction_cleaned
                 and all(item.get("status") == "passed" for item in report.get("checks", [])))
        report["bundle_verification"] = dict(status="passed" if valid else "failed", exit_code=code,
                                             executable_sha256=original_hash, application_version=version, windows_version_resource=resource, single_file_distribution=True,
                                             adjacent_files=adjacent, extraction_cleaned=extraction_cleaned,
                                             relocated_unicode_path=True, host_python_paths_removed=True)
        if not valid:
            report["status"] = "failed"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False), flush=True)
    if not valid:
        raise RuntimeError(f"La vérification Windows a échoué. Rapport : {report_path}")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    verify(args.exe, args.report)


if __name__ == "__main__":
    main()
