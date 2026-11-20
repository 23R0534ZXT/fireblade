"""Lay out the artifact readers the way ToolPack expects them.

The desktop edition ships a Windows pack (dotnet.exe, <Tool>/<Tool>.dll,
manifest.json). This script builds the same layout from the .NET 10 builds, so
the container runs exactly the same tools with the distribution runtime.

    python scripts/fetch_readers.py --dest /opt/fireblade/tools

Downloads are pinned by the toolchain manifest's tool names; the versions come
from the publisher, one directory per tool, and the manifest is copied next to
them so the case records which toolchain read the evidence.
"""
from __future__ import annotations

import argparse
import io
import json
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

BASE = "https://download.ericzimmermanstools.com/net10/{tool}.zip"
RECMD_BATCH = ("https://raw.githubusercontent.com/EricZimmerman/RECmd/master/"
               "BatchExamples/Kroll_Batch.reb")
# Hayabusa ships its rules inside the release archive, one folder below the binary.
HAYABUSA_VERSION = "4.3.1"
HAYABUSA_URL = ("https://github.com/Yamato-Security/hayabusa/releases/download/"
                f"v{HAYABUSA_VERSION}/hayabusa-{HAYABUSA_VERSION}-lin-x64-gnu.zip")
DEFAULT_TOOLS = (
    "EvtxECmd", "AmcacheParser", "AppCompatCacheParser", "PECmd", "MFTECmd",
    "RECmd", "LECmd", "JLECmd", "SrumECmd", "WxTCmd", "RBCmd",
    "RecentFileCacheParser", "SQLECmd",
)


def fetch(url: str, timeout: int = 120) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "fireblade-readers"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def install(tool: str, dest: Path) -> Path:
    """Extract one tool and keep the folder that holds its dll."""
    payload = fetch(BASE.format(tool=tool))
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            archive.extractall(root)
        matches = list(root.rglob(f"{tool}.dll"))
        if not matches:
            raise SystemExit(f"{tool}: {tool}.dll not found in the published archive")
        source = matches[0].parent
        target = dest / tool
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
    return target


def install_hayabusa(dest: Path) -> Path:
    """The Linux detection engine, with its rules, in the layout ToolPack expects."""
    payload = fetch(HAYABUSA_URL, timeout=600)
    target = dest / "Hayabusa"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            archive.extractall(root)
        binary = next((path for path in root.iterdir() if path.is_file() and path.name.startswith("hayabusa-")), None)
        if binary is None:
            raise SystemExit("Hayabusa: the release archive holds no binary")
        shutil.copyfile(binary, target / "hayabusa")
        (target / "hayabusa").chmod(0o755)
        for folder in ("rules", "config"):
            source = root / folder
            if source.is_dir():
                shutil.copytree(source, target / folder)
    return target


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=Path("config/forensic-toolchain.json"))
    parser.add_argument("--tools", nargs="*", default=list(DEFAULT_TOOLS))
    parser.add_argument("--hayabusa", action="store_true",
                        help="also fetch the Hayabusa Linux build and its rules")
    args = parser.parse_args(argv)

    args.dest.mkdir(parents=True, exist_ok=True)
    for tool in args.tools:
        target = install(tool, args.dest)
        print(f"{tool}: {len(list(target.glob('*')))} file(s) in {target}", flush=True)

    batch = args.dest / "RECmd" / "BatchExamples"
    batch.mkdir(parents=True, exist_ok=True)
    (batch / "Kroll_Batch.reb").write_bytes(fetch(RECMD_BATCH))
    print(f"RECmd batch: {(batch / 'Kroll_Batch.reb').stat().st_size} bytes", flush=True)

    if args.hayabusa:
        target = install_hayabusa(args.dest)
        print(f"Hayabusa: {target} ({len(list((target / 'rules').glob('*.yml')))} rule file(s))", flush=True)

    if args.manifest.is_file():
        shutil.copyfile(args.manifest, args.dest / "manifest.json")
        print(f"manifest: {args.manifest} -> {args.dest / 'manifest.json'}", flush=True)
    else:
        print(f"manifest: {args.manifest} not found, the pack will not record its toolchain",
              file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
