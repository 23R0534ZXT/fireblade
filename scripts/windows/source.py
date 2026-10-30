"""Windows source launcher: standard library only until the environment is ready."""
import os
from pathlib import Path
import struct
import subprocess
import sys


def main():
    if os.name != "nt" or struct.calcsize("P") != 8 or not (3, 11) <= sys.version_info[:2] < (3, 14):
        raise SystemExit("Python 3.12 64 bits sur Windows est recommandé.")
    root = Path(__file__).resolve().parents[2]
    os.chdir(root)
    if len(sys.argv) > 1 and sys.argv[1] == "build":
        from scripts.windows.build import main as build
        build()
        return
    arguments = sys.argv[2:] if len(sys.argv) > 1 and sys.argv[1] == "run" else sys.argv[1:]
    python = root / ".venv" / "Scripts" / "python.exe"
    if not python.exists():
        subprocess.run([sys.executable, "-m", "venv", str(root / ".venv")], check=True)
    probe = "import importlib.metadata as m; assert m.version('duckdb') == '1.5.6'; assert m.version('PySide6-Essentials') == '6.12.0'; assert m.version('openpyxl') == '3.1.5'"
    if subprocess.run([str(python), "-c", probe], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
        subprocess.run([str(python), "-m", "pip", "install", "--only-binary=:all:", "-r", "requirements/runtime.txt"], check=True)
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    environment["PYTHONPATH"] = str(root / "src")
    raise SystemExit(subprocess.call([str(python), "-m", "fireblade", *arguments], env=environment))


if __name__ == "__main__":
    main()
