"""The rules dialog: read a rule, change it, switch it off, come back to the pack's one."""

from pathlib import Path

from fireblade.core import hayabusa_rules

RULE = """title: Suspicious PowerShell Encoded Command
id: 11111111-2222-3333-4444-555555555555
status: test
level: high
logsource:
    product: windows
    service: powershell
detection:
    selection:
        EventID: 4104
    condition: selection
"""


def make_pack(tmp_path):
    folder = tmp_path / "pack" / "rules"
    folder.mkdir(parents=True)
    (folder / "ps.yml").write_text(RULE, encoding="utf-8")
    (folder / "cmd.yml").write_text(
        RULE.replace("PowerShell Encoded Command", "Cmd"), encoding="utf-8"
    )
    return folder


def select(dialog, name):
    index = next(i for i, row in enumerate(dialog.rows) if row["name"] == name)
    dialog.table.selectRow(index)
    return dialog.rows[index]


def build(qt_application, tmp_path):
    from fireblade.ui.hayabusa_rules_dialog import HayabusaRulesDialog

    pack = make_pack(tmp_path)
    dialog = HayabusaRulesDialog(pack, base=tmp_path / "user")
    return dialog, pack, tmp_path / "user"


def test_the_dialog_lists_the_rules_and_shows_the_selected_one(qt_application, tmp_path):
    dialog, _pack, _base = build(qt_application, tmp_path)
    try:
        assert dialog.table.rowCount() == 2
        select(dialog, "ps.yml")
        assert "Suspicious PowerShell Encoded Command" in dialog.editor.toPlainText()
        assert dialog.save_button.isEnabled()
    finally:
        dialog.close()


def test_saving_writes_an_override_and_never_the_pack(qt_application, tmp_path):
    dialog, pack, base = build(qt_application, tmp_path)
    try:
        select(dialog, "ps.yml")
        dialog.editor.setPlainText(
            dialog.editor.toPlainText().replace("level: high", "level: critical")
        )
        dialog.save_rule()
        override = base / "overrides" / "ps.yml"
        assert override.is_file() and "critical" in override.read_text(encoding="utf-8")
        assert "level: high" in (pack / "ps.yml").read_text(encoding="utf-8")
        row = next(
            item for item in hayabusa_rules.inventory(pack, base) if item["name"] == "ps.yml"
        )
        assert row["source"] == "user"
    finally:
        dialog.close()


def test_a_rule_hayabusa_could_not_load_is_refused_in_the_dialog(
    qt_application, tmp_path, monkeypatch
):
    from PySide6.QtWidgets import QMessageBox

    warned = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: warned.append(args[1]))
    dialog, _pack, base = build(qt_application, tmp_path)
    try:
        select(dialog, "ps.yml")
        dialog.editor.setPlainText("title: only this\n")
        dialog.save_rule()
        assert warned, "a broken rule was saved without a word"
        assert not (base / "overrides" / "ps.yml").exists()
    finally:
        dialog.close()


def test_switching_a_rule_off_then_back_on(qt_application, tmp_path):
    dialog, _pack, base = build(qt_application, tmp_path)
    try:
        select(dialog, "ps.yml")
        dialog.toggle_rule()
        assert not next(row for row in dialog.rows if row["name"] == "ps.yml")["enabled"]
        assert hayabusa_rules.has_changes(base)
        select(dialog, "ps.yml")
        dialog.toggle_rule()
        assert next(row for row in dialog.rows if row["name"] == "ps.yml")["enabled"]
    finally:
        dialog.close()
