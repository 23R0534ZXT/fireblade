import threading
import time

import pytest

from fireblade.core.engine import Case
from fireblade.core.errors import OperationCancelled
from fireblade.core.models import View


def test_running_duckdb_query_can_be_interrupted_and_reused(tmp_path):
    case = Case(tmp_path / "interrupt.timeline")
    started = threading.Event()
    failures = []
    def query():
        try:
            with case.operation():
                started.set()
                case.db.execute("SELECT sum(sqrt(i::DOUBLE)) FROM range(1000000000) t(i)").fetchone()
        except Exception as exc:
            failures.append(exc)
    thread = threading.Thread(target=query, daemon=True)
    try:
        thread.start()
        assert started.wait(2)
        deadline = time.monotonic() + 5
        while thread.is_alive() and time.monotonic() < deadline:
            case.interrupt()
            thread.join(.01)
        assert not thread.is_alive()
        assert len(failures) == 1 and isinstance(failures[0], OperationCancelled)
        with case.operation():
            assert case.db.execute("SELECT 42").fetchone() == (42,)
    finally:
        if thread.is_alive():
            case.interrupt()
            thread.join(5)
        if not thread.is_alive():
            case.close()


def test_cancelled_streaming_export_preserves_target_and_allows_retry(tmp_path, monkeypatch):
    import fireblade.core.engine as engine
    source = tmp_path / "source.csv"
    source.write_text("ID,Value\n" + "".join(f"{i},value\n" for i in range(5000)))
    case = Case(tmp_path / "export.timeline")
    case.import_csv(source)
    target = tmp_path / "result.csv"
    target.write_bytes(b"original export")
    writer = engine.csv.writer
    class InterruptWriter:
        def __init__(self, *args, **kwargs):
            self.native = writer(*args, **kwargs)
        def writerow(self, row):
            return self.native.writerow(row)
        def writerows(self, rows):
            self.native.writerows(rows)
            case.interrupt()
    try:
        with monkeypatch.context() as patch:
            patch.setattr(engine.csv, "writer", InterruptWriter)
            with pytest.raises(OperationCancelled):
                case.export(target, View())
        assert target.read_bytes() == b"original export"
        assert not target.with_name(target.name + ".partial").exists()
        assert case.count(View()) == 5000
        case.export(target, View())
        assert len(target.read_text(encoding="utf-8-sig").splitlines()) == 5001
    finally:
        case.close()


def test_failed_export_does_not_remove_another_writers_partial(tmp_path, monkeypatch):
    from pathlib import Path
    source = tmp_path / "source.csv"
    source.write_text("ID\n001\n")
    case = Case(tmp_path / "race.timeline")
    case.import_csv(source)
    target = tmp_path / "result.csv"
    target.write_bytes(b"original")
    temporary = target.with_name(target.name + ".partial")
    native_open = Path.open
    def open_with_competing_file(path, mode="r", *args, **kwargs):
        if path == temporary and mode == "x":
            temporary.write_bytes(b"another writer")
        return native_open(path, mode, *args, **kwargs)
    try:
        with monkeypatch.context() as patch:
            patch.setattr(Path, "open", open_with_competing_file)
            with pytest.raises(FileExistsError):
                case.export(target, View())
        assert temporary.read_bytes() == b"another writer"
        assert target.read_bytes() == b"original"
    finally:
        case.close()
