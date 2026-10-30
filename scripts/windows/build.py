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
    staging = root / "build" / "windows" / "output"
    command = [str(python), "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--onefile",
               "--name", "Fireblade", "--paths", str(root / "src"),
               "--distpath", str(staging), "--workpath", str(root / "build" / "windows" / "pyinstaller"),
               "--specpath", str(root / "build" / "windows"), "--collect-all", "duckdb",
               "--hidden-import", "decimal", "--hidden-import", "uuid", "--hidden-import", "fractions"]
    for source, target in [(generated, "resources"), (root / "config" / "fireblade.toml", "resources/config"),
                           (root / "docs" / "guides" / "UTILISATION.md", "resources/docs/guides"),
                           (root / "LICENSE", "resources")]:
        command += ["--add-data", f"{source}{os.pathsep}{target}"]
    for source in json.loads((generated.parent / "runtime-binaries.json").read_text(encoding="utf-8")):
        command += ["--add-binary", f"{source}{os.pathsep}."]
    command.append(str(root / "scripts" / "windows" / "entrypoint.py"))
    subprocess.run(command, check=True)
    candidate = staging / "Fireblade.exe"
    report_path = root / "artifacts" / "windows-single-file.json"
    report_path.unlink(missing_ok=True)
    verify(candidate, report_path)
    destination = root / "dist"
    destination.mkdir(exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination, suffix=".partial", delete=False) as output:
            temporary = Path(output.name)
        shutil.copy2(candidate, temporary)
        os.replace(temporary, destination / "Fireblade.exe")
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
    print(f"Exécutable Windows autonome vérifié : {destination / 'Fireblade.exe'}")


if __name__ == "__main__":
    main()
