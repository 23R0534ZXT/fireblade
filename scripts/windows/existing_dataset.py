"""Reuse the published 3-GiB CSV, with byte/hash verification; never generate it."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import zipfile

REPOSITORY = "23R0534ZXT/fireblade"
TAG = "test-data-3gib"
ROOT = Path(__file__).resolve().parents[2]


def sha256(path):
    with Path(path).open("rb") as incoming:
        return hashlib.file_digest(incoming, "sha256").hexdigest()


def prepare(directory, out=None, archive=None, manifest=None, reference=None):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    manifest = manifest or json.loads(
        (ROOT / "docs/validation/datasets/3gib.json").read_text(encoding="utf-8")
    )
    reference = reference or json.loads(
        (ROOT / "docs/validation/datasets/3gib-reference.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        reference["sha256"] != manifest["sha256"]
        or reference["bytes"] != manifest["bytes"]
    ):
        raise ValueError("CSV reference and published manifest differ")
    source = directory / "Fireblade-test-3GiB.csv"
    # Older qualification runs used another filename. Reuse their verified
    # source rather than downloading a second copy of the same dataset.
    previous_spec = directory / "spec.json"
    if not source.exists() and previous_spec.is_file():
        previous = json.loads(previous_spec.read_text(encoding="utf-8"))
        candidate = Path(previous.get("source", source))
        if not candidate.is_absolute():
            candidate = directory / candidate
        if candidate.is_file():
            source = candidate.resolve()
    reused = source.exists()
    started = time.perf_counter()
    if not reused:
        if (
            shutil.disk_usage(directory).free
            < manifest["bytes"] + manifest["archive_bytes"] + 1024**3
        ):
            raise RuntimeError(
                "Not enough disk space to acquire the existing CSV archive"
            )
        selected = (
            Path(archive).resolve() if archive else directory / manifest["archive_name"]
        )
        if not selected.exists():
            if archive:
                raise FileNotFoundError(selected)
            subprocess.run(
                [
                    "gh",
                    "release",
                    "download",
                    TAG,
                    "--repo",
                    REPOSITORY,
                    "--pattern",
                    manifest["archive_name"],
                    "--dir",
                    str(directory),
                ],
                check=True,
            )
        if (
            selected.stat().st_size != manifest["archive_bytes"]
            or sha256(selected) != manifest["archive_sha256"]
        ):
            raise ValueError(
                "Published CSV archive size or SHA-256 mismatch; existing files left intact"
            )
        temporary = None
        try:
            with zipfile.ZipFile(selected) as zipped:
                item = zipped.getinfo("Fireblade-test-3GiB.csv")
                if item.file_size != manifest["bytes"]:
                    raise ValueError("Unexpected CSV size in archive")
                with tempfile.NamedTemporaryFile(
                    "wb", dir=directory, suffix=".partial", delete=False
                ) as output:
                    temporary = Path(output.name)
                    with zipped.open(item) as incoming:
                        shutil.copyfileobj(incoming, output, 4 * 1024 * 1024)
            if sha256(temporary) != manifest["sha256"]:
                raise ValueError("Extracted CSV SHA-256 mismatch")
            os.replace(temporary, source)
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)
        # Keep a caller-owned archive; the cached CSV is sufficient otherwise.
        if not archive:
            selected.unlink(missing_ok=True)
    if (
        source.stat().st_size != manifest["bytes"]
        or sha256(source) != manifest["sha256"]
    ):
        raise ValueError(
            "Existing CSV differs from the published fixture; it was not overwritten"
        )
    spec = dict(
        reference,
        source=str(source),
        acquisition=dict(
            reused_existing_csv=reused,
            source="published-release",
            archive_sha256=manifest["archive_sha256"],
            csv_sha256_verified=True,
            seconds=round(time.perf_counter() - started, 3),
        ),
    )
    spec.pop("generation_seconds", None)
    (directory / "spec.json").write_text(
        json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if out:
        out = Path(out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "dataset.json").write_text(
            json.dumps(
                {k: v for k, v in spec.items() if k not in ("groups", "samples")},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    return spec


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    spec = prepare(args.directory, args.out, args.archive)
    print(
        json.dumps(
            dict(
                source=spec["source"],
                bytes=spec["bytes"],
                sha256=spec["sha256"],
                acquisition=spec["acquisition"],
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
