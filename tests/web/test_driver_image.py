"""The driver image carries every file the driver imports.

The driver image copies a subset of the sources, and a module added to what ``agency.py`` imports
is missing from the image until the Dockerfile says so: 0.8.1 added the release check, and the
published driver could not start (``No module named 'fireblade.web.updates'``) while every test
passed. This test builds the same file tree the Dockerfile builds, from its COPY lines, and starts
the driver's entry point in it.
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = ROOT / "deploy" / "host" / "Dockerfile.driver"


def _copies():
    """(sources, destination) of every COPY of repository files in the Dockerfile."""
    joined = DOCKERFILE.read_text(encoding="utf-8").replace("\\\n", " ")
    for line in joined.splitlines():
        parts = line.split()
        if parts and parts[0] == "COPY" and not any(p.startswith("--") for p in parts[1:]):
            *sources, destination = parts[1:]
            yield sources, destination


def _build_image_tree(target: Path) -> None:
    for sources, destination in _copies():
        for source in sources:
            path = ROOT / source
            where = target / destination.lstrip("./")
            if path.is_dir():
                shutil.copytree(path, where, dirs_exist_ok=True)
            else:
                if destination.endswith("/"):
                    where.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, where / path.name)
                else:
                    where.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, where)


def test_the_driver_starts_from_the_files_the_dockerfile_copies(tmp_path):
    _build_image_tree(tmp_path)
    code = (
        "import runpy, sys; sys.path.insert(0, 'src'); sys.argv = ['agency', '--help']; "
        "runpy.run_module('fireblade.web.agency', run_name='__main__')"
    )
    # -I: nothing of this repository is on the path but the tree the image would hold.
    run = subprocess.run(
        [sys.executable, "-I", "-c", code],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert run.returncode == 0, run.stderr[-800:]
    assert "one container per case" in run.stdout
