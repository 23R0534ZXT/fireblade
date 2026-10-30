"""Run the Windows portable from a relocated Unicode path, without host Python DLLs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def verify(executable, report_path, timeout=120):
    if os.name != "nt":
        raise RuntimeError("Ce contrôle doit être exécuté sur Windows.")
    executable, report_path = Path(executable).resolve(), Path(report_path).resolve()
    if not executable.is_file() or report_path.exists():
        raise ValueError("Choisissez un exécutable existant et un nouveau fichier de rapport.")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    original_hash = hashlib.sha256(executable.read_bytes()).hexdigest()
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "windows"
    environment["PYTHONUTF8"] = "1"
    for key in ("PYTHONHOME", "PYTHONPATH", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH", "QML2_IMPORT_PATH"):
        environment.pop(key, None)
    system_root = Path(environment.get("SystemRoot", r"C:\Windows"))
    environment["PATH"] = os.pathsep.join(map(str, [system_root / "System32", system_root]))
    with tempfile.TemporaryDirectory(prefix="Portable Windows déplacé ") as temporary:
        copied = Path(temporary) / "Application été"
        shutil.copytree(executable.parent, copied)
        target = copied / executable.name
        try:
            completed = subprocess.run([str(target), "--self-test-report", str(report_path)],
                                       env=environment, cwd=temporary, timeout=timeout, check=False)
            code = completed.returncode
        except subprocess.TimeoutExpired:
            code = -1
        if not report_path.is_file():
            report = dict(status="failed", error="Le processus n’a pas produit de rapport.", exit_code=code)
        else:
            raw_report = report_path.read_text(encoding="utf-8")
            try:
                report = json.loads(raw_report)
            except json.JSONDecodeError:
                report = dict(status="failed", error="Le rapport du processus est incomplet.",
                              report_tail=raw_report[-3000:], exit_code=code)
        valid = (code == 0 and report.get("status") == "passed" and report.get("frozen") is True
                 and report.get("platform") == "win32" and report.get("pointer_bits") == 64
                 and report.get("qt_platform") == "windows" and len(report.get("checks", [])) >= 10
                 and all(item.get("status") == "passed" for item in report.get("checks", [])))
        report["bundle_verification"] = dict(status="passed" if valid else "failed", exit_code=code,
                                             executable_sha256=original_hash,
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
    report = verify(args.exe, args.report)
    print(f"Windows : {len(report['checks'])} contrôles du portable réussis. Rapport : {args.report}")


if __name__ == "__main__":
    main()
