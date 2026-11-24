"""The case destruction dialog: what it announces, and what it refuses."""

import json
from pathlib import Path
from types import SimpleNamespace

from fireblade.ui.case_destruction_dialog import CaseDestructionDialog, human_size


def fake_window(tmp_path, name="Affaire test"):
    folder = tmp_path / "Cases" / "CASE-1"
    (folder / "analyses").mkdir(parents=True)
    (folder / "case.json").write_text(json.dumps(dict(id="CASE-1", name=name)), encoding="utf-8")
    (folder / "analyses" / "a.timeline").write_bytes(b"x" * 2048)
    library = SimpleNamespace(folder=lambda identifier: folder)
    return SimpleNamespace(
        preferences=SimpleNamespace(analyst_name="Maxime"),
        investigation_library=library,
        active_investigation=dict(id="CASE-1", name=name),
        after_case_destroyed=lambda case: None,
    ), folder


def test_the_dialog_counts_what_will_disappear(qt_application, tmp_path):
    window, folder = fake_window(tmp_path)
    dialog = CaseDestructionDialog(window, None)
    try:
        text = dialog.summary.text()
        assert "2" in text and folder.name not in text
        assert dialog.operator.text() == "Maxime"
        assert str(dialog.certificate.text()).endswith(".pdf")
        assert not dialog.go.isEnabled(), "destruction armed before any confirmation"
    finally:
        dialog.close()


def test_the_confirmation_asks_for_the_case_name(qt_application, tmp_path):
    window, _folder = fake_window(tmp_path)
    dialog = CaseDestructionDialog(window, None)
    try:
        dialog.understood.setChecked(True)
        dialog.phrase.setText("mauvais nom")
        assert not dialog.go.isEnabled()
        dialog.phrase.setText("Affaire test")
        assert dialog.go.isEnabled()
    finally:
        dialog.close()


def test_sizes_are_written_for_a_person(qt_application):
    assert human_size(900) == "900 o"
    assert human_size(2048) == "2.0 Ko".replace(".", ".")
    assert human_size(5_500_000).startswith("5.5 Mo")
