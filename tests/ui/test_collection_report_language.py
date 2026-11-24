"""The Imports report is written in the interface language, not in the source one."""

import time

from PySide6.QtCore import Qt

from fireblade.core.collection import Collection, ToolPack
from fireblade.core.i18n import set_language
from fireblade.ui.app import Window


def settle(app, window):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        app.processEvents()
        if (
            window.case
            and not window.jobs
            and not window.pool.activeThreadCount()
            and not window.model.jobs
        ):
            return
        time.sleep(0.01)
    raise AssertionError("Collection session did not open")


def test_the_full_report_is_written_in_the_interface_language(qt_application, tmp_path):
    """'Full report' used to dump the whole text in French under an English interface."""
    root = tmp_path / "evidence"
    root.mkdir()
    (root / "users.csv").write_text("User,Value\nalice,1\n", encoding="utf-8")
    window = Window(require_case=False)
    errors = []
    window.error = errors.append
    try:
        set_language("en")
        window.collection = Collection(
            root, tmp_path / "results", ToolPack(tmp_path / "missing"), window.settings
        )
        window.start_collection_job(window.collection.parse)
        settle(qt_application, window)
        text = window.collection_report.toPlainText()
        assert "Terminé" not in text, text
        assert "Windows engines available" in text, text
        assert "Source folder:" in text, text
        headers = [
            window.collection_report.model.headerData(column, Qt.Horizontal) for column in range(5)
        ]
        assert headers[2] == "Readers" and headers[3] == "Reason", headers
        assert not errors
    finally:
        set_language("fr")
        if window.jobs:
            window.interrupt_queries()
        window.close()
