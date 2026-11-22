"""What the report says when a reader does not read.

A file Fireblade cannot read must come back with a sentence the analyst can act
on: an empty jump list is not a broken parser, and an engine that only runs on
Windows must say so instead of showing an exit code. These tests hold the words,
because a reason nobody understands is a reason nobody reads.
"""
from pathlib import Path

import pytest

from fireblade.core import i18n
from fireblade.core.collection import _WINDOWS_ONLY, _engine_tail, _no_output_reason


@pytest.fixture(autouse=True)
def english():
    previous = i18n.current_language() if hasattr(i18n, "current_language") else None
    i18n.set_language("en")
    try:
        yield
    finally:
        if previous:
            i18n.set_language(previous)


def test_an_empty_jump_list_is_named_as_such(tmp_path):
    sample = tmp_path / "5a2098e080cf7ac4.automaticDestinations-ms"
    sample.write_bytes(b"\x00" * 32)
    assert _no_output_reason(sample) == "No destination in this jump list"


def test_a_prefetch_without_executable_says_so(tmp_path):
    sample = tmp_path / "EMPTY.PF-00000000.pf"
    sample.write_bytes(b"\x00" * 32)
    assert _no_output_reason(sample) == "No executable in this prefetch file"


def test_an_empty_evtx_is_an_empty_log_not_a_failure(tmp_path):
    sample = tmp_path / "System.evtx"
    sample.write_bytes(b"ElfFile\x00" + b"\x00" * 24)
    assert _no_output_reason(sample) == "Empty log: no entry"


def test_the_engine_tail_is_the_last_line_it_wrote(tmp_path):
    log = tmp_path / "parser.log"
    log.write_text("Starting\nReading the file\nNon-Windows platforms not supported\n",
                   encoding="utf-8")
    assert _engine_tail(log) == "Non-Windows platforms not supported"
    assert _engine_tail(tmp_path / "absent.log") == ""


def test_the_srum_refusal_is_recognised():
    assert _WINDOWS_ONLY.search(
        "Non-Windows platforms not supported due to the need to load ESE specific "
        "Windows libraries! Exiting...")
    assert not _WINDOWS_ONLY.search("Row count written: 1327")


def test_the_windows_only_sentence_is_english_too():
    sentence = i18n.english(
        "Ce lecteur a besoin des bibliothèques ESE de Windows : il ne peut pas "
        "lire ce fichier sous Linux. Importez le CSV produit par l’édition Desktop.")
    assert sentence.startswith("This reader needs the Windows ESE libraries")
    assert i18n.english("Moteur terminé avec le code 1") == "Engine exited with code 1"
