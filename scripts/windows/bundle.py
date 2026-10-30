"""Collect embedded metadata and installed license notices from the build venv."""
import argparse
from importlib.metadata import distribution
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import tomllib

DISTRIBUTIONS = ("duckdb", "PySide6-Essentials", "shiboken6", "openpyxl", "et-xmlfile", "pyinstaller")
RUNTIME_DLLS = ("vcruntime140.dll", "vcruntime140_1.dll", "msvcp140.dll")


def runtime_binaries():
    directories = [Path(sys.base_prefix), Path(sys.prefix),
                   Path(distribution("PySide6-Essentials").locate_file("PySide6")),
                   Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"]
    binaries = []
    for name in RUNTIME_DLLS:
        source = next((directory / name for directory in directories if (directory / name).is_file()), None)
        if source is None:
            raise RuntimeError(f"Bibliothèque Windows nécessaire à intégrer introuvable : {name}")
        binaries.append(str(source))
    return binaries


def stage_resources(root, destination):
    root, destination = Path(root).resolve(), Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    legal = destination / "legal"
    shutil.copytree(root / "licenses", legal, dirs_exist_ok=True)
    packages = []
    for name in DISTRIBUTIONS:
        installed = distribution(name)
        notices = []
        for file in installed.files or []:
            license_file = (any(part.casefold() in ("licenses", "licences") for part in file.parts)
                            or file.name.casefold().startswith(("license", "licence", "copying", "copyright", "notice")))
            source = installed.locate_file(file)
            if license_file and source.is_file():
                safe_parts = [part for part in file.parts if part not in ("..", ".")]
                target = legal / name / Path(*safe_parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                notices.append(str(target.relative_to(legal)).replace("\\", "/"))
        packages.append(dict(name=name, version=installed.version,
                             license=installed.metadata.get("License-Expression") or installed.metadata.get("License"),
                             notices=notices))
    for name in ("LICENSE.txt", "LICENSE"):
        source = Path(sys.base_prefix) / name
        if source.is_file():
            shutil.copy2(source, legal / "PYTHON-LICENSE.txt")
            break
    else:
        raise RuntimeError("La licence de l’interpréteur Python est introuvable dans son installation.")
    (legal / "DEPENDENCIES.json").write_text(json.dumps(packages, ensure_ascii=False, indent=2), encoding="utf-8")
    version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    info = dict(application="Fireblade", version=version, platform="Windows x64", packaging="onefile",
                python=sys.version.split()[0], machine=platform.machine(), source_commit=os.environ.get("GITHUB_SHA"),
                maturity="prototype", dependencies=[dict(name=p["name"], version=p["version"]) for p in packages])
    (destination / "build").mkdir(exist_ok=True)
    (destination / "build" / "build-info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    (destination.parent / "runtime-binaries.json").write_text(json.dumps(runtime_binaries(), indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    stage_resources(args.root, args.destination)


if __name__ == "__main__":
    main()
