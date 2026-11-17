"""The Resources tab reads out what "automatic" resolves to, not a sentinel word."""
import re

from fireblade.core.machine import from_settings
from fireblade.core.preferences import Preferences
from fireblade.ui.preferences_dialog import PreferencesDialog


def numbers(text):
    return [int(found) for found in re.findall(r"\d+", text)]


def test_the_automatic_memory_reads_as_the_resolved_megabytes(qt_application):
    dialog = PreferencesDialog(Preferences())
    try:
        expected = from_settings(0, 0).memory_mb
        text = dialog.memory.specialValueText()
        assert "MB" in text
        assert expected in numbers(text), text
        # The engine never promises more than 2 GB here, nor less than 512 MB.
        assert 512 <= expected <= 2048
        assert dialog.memory.value() == 0, "the field still stores 0"
    finally:
        dialog.close(); dialog.deleteLater()


def test_both_thread_fields_read_as_the_resolved_thread_count(qt_application):
    dialog = PreferencesDialog(Preferences())
    try:
        expected = from_settings(0, 0).threads
        # auto_threads stops at the disk knee (8) and never drops below one.
        assert 1 <= expected <= 8
        for spin in (dialog.query_threads, dialog.parsing_threads):
            text = spin.specialValueText()
            assert "threads" in text
            assert expected in numbers(text), text
            assert spin.value() == 0, "the field still stores 0"
    finally:
        dialog.close(); dialog.deleteLater()


def test_a_rebuilt_dialog_recomputes_the_numbers_from_the_machine(qt_application, monkeypatch):
    import fireblade.ui.preferences_dialog as module
    monkeypatch.setattr(module.machine, "cores", lambda: 3)
    monkeypatch.setattr(module.machine, "memory_mb", lambda: 2048)
    dialog = PreferencesDialog(Preferences())
    try:
        assert dialog.parsing_threads.specialValueText() == "Automatic \u00b7 3 threads"
        assert dialog.query_threads.specialValueText() == "Automatic \u00b7 3 threads"
        assert dialog.memory.specialValueText() == "Automatic \u00b7 682 MB"
    finally:
        dialog.close(); dialog.deleteLater()


def test_an_explicit_memory_still_round_trips(qt_application):
    dialog = PreferencesDialog(Preferences())
    try:
        dialog.memory.setValue(512)
        assert dialog.memory.value() == 512
        assert dialog.memory.text().startswith("512"), dialog.memory.text()
        assert dialog.query_threads.value() == 0 and dialog.parsing_threads.value() == 0
    finally:
        dialog.close(); dialog.deleteLater()
