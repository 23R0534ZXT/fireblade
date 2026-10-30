import hashlib
import zipfile
import pytest
from scripts.windows.existing_dataset import prepare


def fixture(tmp_path):
    content = b"ID,Text\r\n001,first\r\n2,second\r\n"
    sha = hashlib.sha256(content).hexdigest()
    archive = tmp_path / "published.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("Fireblade-test-3GiB.csv", content)
    manifest = dict(
        bytes=len(content),
        rows=2,
        sha256=sha,
        archive_name="published.zip",
        archive_bytes=archive.stat().st_size,
        archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
    )
    return (
        content,
        archive,
        manifest,
        dict(bytes=len(content), rows=2, sha256=sha, groups=[], samples={}),
    )


def test_reuses_existing_csv_without_generator_or_download(tmp_path, monkeypatch):
    content, archive, manifest, reference = fixture(tmp_path)
    directory = tmp_path / "data"
    directory.mkdir()
    csv = directory / "Fireblade-test-3GiB.csv"
    csv.write_bytes(content)
    monkeypatch.setattr(
        "subprocess.run",
        lambda *a, **k: pytest.fail(
            "Existing CSV must never be downloaded or regenerated"
        ),
    )
    spec = prepare(directory, manifest=manifest, reference=reference)
    assert spec["acquisition"]["reused_existing_csv"] and csv.read_bytes() == content


def test_extracts_known_archive_once_and_reuses_it(tmp_path):
    content, archive, manifest, reference = fixture(tmp_path)
    spec = prepare(
        tmp_path / "data", archive=archive, manifest=manifest, reference=reference
    )
    assert not spec["acquisition"]["reused_existing_csv"]
    assert archive.exists()
    assert prepare(tmp_path / "data", manifest=manifest, reference=reference)[
        "acquisition"
    ]["reused_existing_csv"]
    source = tmp_path / "data/Fireblade-test-3GiB.csv"
    source.write_bytes(b"changed")
    with pytest.raises(ValueError):
        prepare(tmp_path / "data", manifest=manifest, reference=reference)
    assert source.read_bytes() == b"changed"


def test_reuses_previous_qualification_filename(tmp_path, monkeypatch):
    import json

    content, archive, manifest, reference = fixture(tmp_path)
    source = tmp_path / "artefacts variés 3GiB.csv"
    source.write_bytes(content)
    (tmp_path / "spec.json").write_text(
        json.dumps(dict(source=str(source))), encoding="utf-8"
    )
    monkeypatch.setattr(
        "subprocess.run", lambda *a, **k: pytest.fail("Must reuse the old CSV")
    )
    spec = prepare(tmp_path, manifest=manifest, reference=reference)
    assert spec["source"] == str(source.resolve())
    assert spec["acquisition"]["reused_existing_csv"]
    assert not (tmp_path / "Fireblade-test-3GiB.csv").exists()


def test_refuses_changed_archive_without_extracting(tmp_path):
    content, archive, manifest, reference = fixture(tmp_path)
    archive.write_bytes(b"corrupted archive")
    directory = tmp_path / "data"
    with pytest.raises(ValueError, match="archive size or SHA-256"):
        prepare(directory, archive=archive, manifest=manifest, reference=reference)
    assert not list(directory.iterdir())


def test_refuses_wrong_csv_hash_and_removes_partial(tmp_path):
    content, archive, manifest, reference = fixture(tmp_path)
    manifest["sha256"] = reference["sha256"] = "0" * 64
    directory = tmp_path / "data"
    with pytest.raises(ValueError, match="Extracted CSV SHA-256"):
        prepare(directory, archive=archive, manifest=manifest, reference=reference)
    assert not list(directory.iterdir())
    assert archive.exists()
