"""These tests require Windows filesystem/locking semantics; never substitute POSIX."""
import os
import stat

import pytest
from PySide6.QtWidgets import QApplication

from fireblade.ui.dialogs import ImportDialog
from fireblade.core.engine import Case
from fireblade.core.models import View
from fireblade.runtime.windows_paths import analyses_directory

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows natif requis")


def test_default_case_directory_is_user_local_appdata(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Profil été"))
    source = tmp_path / "preuves" / "CSV en lecture seule.csv"
    source.parent.mkdir()
    source.write_text("User,ID\nélève,0001\n", encoding="utf-8")
    source.chmod(stat.S_IREAD)
    try:
        dialog = ImportDialog(source)
        target, delimiter, encoding = dialog.values()
        assert target.parent == analyses_directory()
        assert target.parent != source.parent
        case = Case(target)
        try:
            case.import_csv(source, delimiter, encoding)
            assert case.page(View())[0][1:] == ("élève", "0001")
        finally:
            case.close()
    finally:
        source.chmod(stat.S_IREAD | stat.S_IWRITE)


def test_windows_locked_export_keeps_existing_file(tmp_path):
    source = tmp_path / "source.csv"
    source.write_text("ID\n0001\n")
    case = Case(tmp_path / "analysis.timeline")
    case.import_csv(source)
    target = tmp_path / "export.csv"
    target.write_bytes(b"previous export")
    try:
        with target.open("rb"):
            with pytest.raises(PermissionError):
                case.export(target, View())
        assert target.read_bytes() == b"previous export"
        assert not (tmp_path / "export.csv.partial").exists()
        case.export(target, View())
        assert "0001" in target.read_text(encoding="utf-8-sig")
    finally:
        case.close()
