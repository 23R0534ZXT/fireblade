import hashlib
import shutil
from pathlib import Path

import pytest

from fireblade.core.collection import ToolPack
from fireblade.core.disk import DiskCollection, image_segments

FIXTURE = Path(__file__).resolve().parents[1] / "data/ewf/image.E01"
EXPECTED_SHA256 = "fbc3da213475f9692be6bf00fb68eb87adaab3195c204f21ea42efc3b2b35097"
EXPECTED_SIZE = 4 * 1024**2 + 16


def test_the_e01_fixture_is_the_pinned_public_sample():
    assert FIXTURE.is_file(), "the E01 fixture is missing from tests/data"
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == EXPECTED_SHA256


def test_dissect_opens_an_e01_segment_as_a_disk():
    from dissect.target import Target

    target = Target.open(FIXTURE)
    try:
        assert len(target.disks) == 1
        assert target.disks[0].size == EXPECTED_SIZE
        assert len(target.filesystems) == 0
    finally:
        for disk in target.disks:
            disk.close()


def test_an_e01_without_a_filesystem_fails_with_a_readable_reason(tmp_path):
    before = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    collection = DiskCollection(
        FIXTURE, tmp_path / "work", ToolPack(tmp_path / "tools"), source_kind="image"
    )
    with pytest.raises(ValueError, match="Aucun système de fichiers lisible"):
        collection.parse()
    assert collection.report["status"] == "error"
    assert collection.report["disk"]["kind"] == "image"
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == before


def test_a_lowercase_e01_extension_is_recognised_as_an_image(tmp_path):
    """Windows keeps the case in the name; the file picker offers both spellings."""
    copy = tmp_path / "image.e01"
    shutil.copyfile(FIXTURE, copy)
    collection = DiskCollection(
        copy, tmp_path / "work", ToolPack(tmp_path / "tools"), source_kind="image"
    )
    with pytest.raises(ValueError, match="Aucun système de fichiers lisible"):
        collection.parse()
    assert collection.report["disk"]["source"].endswith("image.e01")


def test_a_split_e01_set_is_collected_in_order_and_a_hole_is_refused(tmp_path):
    for index in (1, 2, 3):
        (tmp_path / f"poste.E{index:02d}").write_bytes(b"E" * 16)
    segments = image_segments(tmp_path / "poste.E01")
    assert [item.name for item in segments] == ["poste.E01", "poste.E02", "poste.E03"]
    (tmp_path / "poste.E02").unlink()
    with pytest.raises(ValueError, match="incomplet"):
        image_segments(tmp_path / "poste.E01")
    assert image_segments(tmp_path / "autre.raw")[0].name == "autre.raw"
