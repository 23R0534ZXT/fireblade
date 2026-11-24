"""A collection that dies says why, in a window, and the report keeps the reason."""

from types import SimpleNamespace

from fireblade.ui import start_workflow
from fireblade.ui.app import Window

DUCKDB = (
    "Out of Memory Error: failed to pin block of size 256.0 KiB (60.8 MiB/61.0 MiB used)\n\n"
    "Possible solutions:\n* Increasing the memory limit (SET memory_limit='...GB')"
)


class FakeBox:
    captured = {}
    Warning = 1

    def __init__(self, parent=None):
        pass

    def setIcon(self, *args):
        pass

    def setWindowTitle(self, title):
        FakeBox.captured["title"] = title

    def setText(self, text):
        FakeBox.captured["text"] = text

    def setDetailedText(self, text):
        FakeBox.captured["detail"] = text

    def exec(self):
        FakeBox.captured["shown"] = True


def test_a_collection_failure_is_explained_in_a_window(qt_application, monkeypatch):
    FakeBox.captured = {}
    monkeypatch.setattr(start_workflow, "QMessageBox", FakeBox)
    window = Window(require_case=False)
    try:
        window.disk_collection = SimpleNamespace(settings=SimpleNamespace(memory_mb=64))
        window.report_collection_failure(DUCKDB)
        captured = FakeBox.captured
        assert captured.get("shown"), "l'échec doit s'afficher, pas seulement dans la barre d'état"
        assert captured["title"] == "Collection interrupted"
        assert "Not enough memory" in captured["text"] and "64" in captured["text"]
        assert "Preferences → Resources" in captured["text"]
        assert "failed to pin" in captured["detail"], "le détail technique reste consultable"
    finally:
        window.close()


def test_the_report_names_a_family_that_could_not_be_merged(qt_application, tmp_path):
    window = Window(require_case=False)
    try:
        report = dict(
            format="fireblade-collection",
            version=1,
            source=str(tmp_path),
            output=str(tmp_path),
            organization="artifacts",
            status="complete",
            files=[],
            documents=[],
            organization_failures=[
                dict(artifact="EVTX", reason="Out of Memory Error: failed to pin block")
            ],
        )
        window.show_collection_report(report)
        text = window.collection_report.toPlainText()
        assert "EVTX" in text and "not merged" in text and "Out of Memory" in text
    finally:
        window.close()
