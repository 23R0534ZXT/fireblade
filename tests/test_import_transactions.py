import hashlib
import threading
import time

import duckdb
import pytest

from timeline_next.engine import Case
from timeline_next.errors import OperationCancelled
from timeline_next.models import View


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "source.csv"
    path.write_text("ID,User\n001,alice\n002,bob\n", encoding="utf-8")
    return path


def assert_empty_and_retry(case, source):
    assert case.headers == [] and case.info == {}
    assert case.db.execute("SHOW TABLES").fetchall() == []
    case.import_csv(source)
    assert case.page(View()) == [(1, "001", "alice"), (2, "002", "bob")]


def test_cancel_immediately_before_commit_rolls_back(tmp_path, source):
    before = source.read_bytes()
    case = Case(tmp_path / "before-commit.timeline")
    try:
        def cancel(message):
            if message == "Validation de l’analyse…":
                case.interrupt()
        with pytest.raises(OperationCancelled):
            case.import_csv(source, progress=cancel)
        assert_empty_and_retry(case, source)
        assert source.read_bytes() == before
    finally:
        case.close()


def test_begin_interrupted_before_a_transaction_is_active(tmp_path, source):
    case = Case(tmp_path / "begin.timeline")
    native = case.db
    class InterruptBegin:
        def execute(self, sql, *args):
            if sql == "BEGIN":
                raise duckdb.InterruptException("Interrupted before BEGIN")
            return native.execute(sql, *args)
        def __getattr__(self, name):
            return getattr(native, name)
    try:
        case.db = InterruptBegin()
        with pytest.raises(OperationCancelled):
            case.import_csv(source)
        case.db = native
        assert_empty_and_retry(case, source)
    finally:
        case.db = native
        case.close()


def test_repeated_cancel_during_rollback_does_not_interrupt_cleanup(tmp_path, source):
    case = Case(tmp_path / "rollback.timeline")
    native = case.db
    native_interrupts = []
    class CancelDuringRollback:
        def execute(self, sql, *args):
            if sql == "ROLLBACK":
                case.interrupt()  # A second click while rollback is already running.
            return native.execute(sql, *args)
        def interrupt(self):
            native_interrupts.append(True)
            native.interrupt()
        def __getattr__(self, name):
            return getattr(native, name)
    try:
        case.db = CancelDuringRollback()
        def cancel(message):
            if message == "Validation de l’analyse…":
                case.interrupt()
        with pytest.raises(OperationCancelled):
            case.import_csv(source, progress=cancel)
        assert len(native_interrupts) == 1
        case.db = native
        assert_empty_and_retry(case, source)
    finally:
        case.db = native
        case.close()


def test_cancel_after_commit_started_finishes_a_valid_analysis(tmp_path, source):
    case = Case(tmp_path / "committing.timeline")
    native = case.db
    native_interrupts = []
    class CancelDuringCommit:
        def execute(self, sql, *args):
            if sql == "COMMIT":
                case.interrupt()
            return native.execute(sql, *args)
        def interrupt(self):
            native_interrupts.append(True)
            native.interrupt()
        def __getattr__(self, name):
            return getattr(native, name)
    try:
        case.db = CancelDuringCommit()
        assert case.import_csv(source)["rows"] == 2
        assert native_interrupts == []
        assert case.page(View())[0] == (1, "001", "alice")
    finally:
        case.db = native
        case.close()
    reopened = Case(tmp_path / "committing.timeline")
    try:
        assert reopened.count(View()) == 2
        assert reopened.info["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    finally:
        reopened.close()


def test_callback_base_exception_also_rolls_back(tmp_path, source):
    case = Case(tmp_path / "callback.timeline")
    try:
        def stop(message):
            if message == "Validation de l’analyse…":
                raise KeyboardInterrupt()
        with pytest.raises(KeyboardInterrupt):
            case.import_csv(source, progress=stop)
        assert_empty_and_retry(case, source)
    finally:
        case.close()


def test_invalid_utf16_cleans_transcoding_file_and_can_retry(tmp_path, source):
    malformed = tmp_path / "bad-utf16.csv"
    malformed.write_bytes(b"\xff\xfe\x00")
    before = malformed.read_bytes()
    case = Case(tmp_path / "encoding.timeline")
    try:
        with pytest.raises(UnicodeDecodeError):
            case.import_csv(malformed, encoding="utf-16")
        assert not list(tmp_path.glob("tmp*.csv"))
        assert malformed.read_bytes() == before
        assert_empty_and_retry(case, source)
    finally:
        case.close()


def test_ambiguous_detection_does_not_flatten_a_bad_csv(tmp_path, source):
    malformed = tmp_path / "ambiguous.csv"
    malformed.write_text("a,b\n1,2\n3,4,5\n")
    case = Case(tmp_path / "ambiguous.timeline")
    try:
        with pytest.raises(ValueError, match="séparateur"):
            case.import_csv(malformed)
        assert_empty_and_retry(case, source)
    finally:
        case.close()


def test_valid_single_column_with_quoted_delimiters_is_preserved(tmp_path):
    source = tmp_path / "single.csv"
    source.write_text('"Event, description; more|text"\n"all, ; | values"\n', encoding="utf-8")
    case = Case(tmp_path / "single.timeline")
    try:
        case.import_csv(source)
        assert case.headers == ["Event, description; more|text"]
        assert case.page(View()) == [(1, "all, ; | values")]
    finally:
        case.close()


def test_native_csv_scan_can_be_cancelled_and_retried(tmp_path, source):
    """Interrupt the real CSV scanner, after its query reports being active."""
    large = tmp_path / "larger.csv"
    row = b"0001,alice," + b"artifact detail " * 20 + b"\n"
    block = row * 10000
    with large.open("wb") as out:
        out.write(b"ID,User,Description\n")
        for _ in range(20):
            out.write(block)
    with large.open("rb") as incoming:
        original_hash = hashlib.file_digest(incoming, "sha256").hexdigest()
    case = Case(tmp_path / "native-cancel.timeline", threads=1)
    case.db.execute("SET enable_progress_bar=true")
    case.db.execute("SET enable_progress_bar_print=false")
    writing = threading.Event()
    failures = []
    def progress(message):
        if message == "Écriture des enregistrements sur disque…":
            writing.set()
    def work():
        try:
            case.import_csv(large, progress=progress)
        except Exception as exc:
            failures.append(exc)
    thread = threading.Thread(target=work, daemon=True)
    try:
        thread.start()
        assert writing.wait(10)
        deadline = time.monotonic() + 5
        observed_active = False
        while thread.is_alive() and time.monotonic() < deadline:
            if case.db.query_progress() >= 0:
                observed_active = True
                break
            time.sleep(.001)
        assert observed_active, "The CSV scanner finished before it could be observed"
        case.interrupt()
        thread.join(10)
        assert not thread.is_alive()
        assert len(failures) == 1 and isinstance(failures[0], OperationCancelled)
        assert isinstance(failures[0].__cause__, duckdb.InterruptException)
        assert_empty_and_retry(case, source)
        with large.open("rb") as incoming:
            assert hashlib.file_digest(incoming, "sha256").hexdigest() == original_hash
    finally:
        if thread.is_alive():
            case.interrupt()
            thread.join(10)
        if not thread.is_alive():
            case.close()
