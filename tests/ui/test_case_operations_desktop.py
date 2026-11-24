import time

from fireblade.core import case_workspace
from fireblade.core.findings import Group
from fireblade.ui.app import Window


def settle(app, window):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        app.processEvents()
        if not window.jobs and not window.busy and not window.pool.activeThreadCount():
            return
        time.sleep(0.005)
    raise AssertionError("workspace did not settle")


def headers(table):
    return [table.horizontalHeaderItem(index).text() for index in range(table.columnCount())]


def test_the_action_table_has_the_six_requested_columns(qt_application, tmp_path):
    window = Window(require_case=False, investigation_root=tmp_path / "Cases")
    try:
        case = window.create_investigation("Affaire A")
        panel = window.operations_panel
        assert headers(panel.actions_table) == [
            "Date",
            "Priorité",
            "État de l'action",
            "Type d'action",
            "Intervenant",
            "Détails",
        ]
        case_workspace.add_action(
            window.investigation_library.folder(case["id"]),
            "Réinitialiser les comptes",
            date="2026-11-18",
            priority="high",
            status="waiting_client",
            type="remediation",
            intervenant="Direction SI",
            machine="SRV01",
            detail="Comptes à réinitialiser avant vendredi",
        )
        panel.refresh()
        assert panel.actions_table.rowCount() == 1
        values = [panel.actions_table.item(0, column).text() for column in range(6)]
        assert values[0] == "2026-11-18" and values[1] == "Haute"
        assert values[2] == "En attente du client" and values[3] == "Remédiation"
        assert values[4] == "Direction SI" and "Réinitialiser les comptes" in values[5]
        panel.scope.setCurrentIndex(panel.scope.findData("all"))
        panel.refresh()
        assert headers(panel.actions_table)[0] == "Case"
        assert panel.actions_table.item(0, 0).text() == "Affaire A"
    finally:
        window.close()


def test_an_action_can_be_closed_and_reopened_from_the_table(qt_application, tmp_path):
    window = Window(require_case=False, investigation_root=tmp_path / "Cases")
    try:
        case = window.create_investigation("Affaire B")
        panel = window.operations_panel
        folder = window.investigation_library.folder(case["id"])
        case_workspace.add_action(folder, "Collecter les journaux", status="in_progress")
        panel.refresh()
        panel.actions_table.selectRow(0)
        panel.complete_action()
        assert case_workspace.load(folder)["actions"][0]["status"] == "done"
        assert panel.actions_table.item(0, 2).text() == "Terminée"
        panel.actions_table.selectRow(0)
        panel.reopen_action()
        assert case_workspace.load(folder)["actions"][0]["status"] == "in_progress"
        panel.open_only.setChecked(True)
        panel.refresh()
        assert panel.actions_table.rowCount() == 1
        panel.complete_action()
        panel.refresh()
        assert panel.actions_table.rowCount() == 0
    finally:
        window.close()


def test_indicators_and_machines_are_listed_and_removable(qt_application, tmp_path):
    window = Window(require_case=False, investigation_root=tmp_path / "Cases")
    try:
        case = window.create_investigation("Affaire C")
        folder = window.investigation_library.folder(case["id"])
        case_workspace.add_ioc(
            folder, "exemple.fr", status="confirmed", machine="SRV01", label="C2 suspecté"
        )
        case_workspace.add_entity(folder, "machine", "SRV01", hostname="SRV01", ip="10.0.0.5")
        panel = window.operations_panel
        panel.refresh()
        assert panel.ioc_table.rowCount() == 1
        assert panel.ioc_table.item(0, 1).text() == "exemple.fr"
        assert panel.ioc_table.item(0, 2).text() == "Confirmé"
        assert panel.entity_table.rowCount() == 1
        assert panel.entity_table.item(0, 1).text() == "SRV01"
        panel.ioc_table.selectRow(0)
        panel.remove_indicator()
        assert case_workspace.load(folder)["iocs"] == []
    finally:
        window.close()


def group(title="Encoded PowerShell", host="SRV01"):
    return Group(
        key=title,
        title=title,
        level="high",
        host=host,
        channel="PowerShell",
        event_ids=("4104",),
        tactics="Execution",
        techniques="T1059.001 PowerShell",
        rule_id="r",
        rule_file="f",
        start=None,
        end=None,
        count=4,
    )


def test_the_graph_tab_builds_tags_and_keeps_them(qt_application, tmp_path):
    window = Window(require_case=False, investigation_root=tmp_path / "Cases")
    try:
        case = window.create_investigation("Affaire D")
        folder = window.investigation_library.folder(case["id"])
        window.hayabusa_panel.groups = [group()]
        panel = window.graph_panel
        panel.reload()
        assert panel.canvas.graph["nodes"], panel.status.text()
        technique = next(
            node for node in panel.canvas.graph["nodes"] if node["kind"] == "technique"
        )
        panel.canvas.selected = technique["id"]
        case_workspace.tag_node(
            folder,
            technique["label"],
            kind="technique",
            tags=["persistance"],
            node_id=technique["id"],
        )
        panel.reload()
        technique = next(
            node for node in panel.canvas.graph["nodes"] if node["kind"] == "technique"
        )
        assert technique["tags"] == ["persistance"]
        assert panel.canvas.render_png().startswith(b"\x89PNG")
    finally:
        window.close()


def test_destroying_evidence_lists_the_case_but_never_its_record(qt_application, tmp_path):
    from fireblade.ui.destruction_dialog import DestructionDialog, evidence_files

    window = Window(require_case=False, investigation_root=tmp_path / "Cases")
    try:
        case = window.create_investigation("Affaire E")
        folder = window.investigation_library.folder(case["id"])
        (folder / "collection").mkdir()
        (folder / "collection" / "Security.evtx").write_bytes(b"evidence" * 100)
        (folder / "assistant").mkdir()
        (folder / "assistant" / "conversation.json").write_text("{}")
        (folder / "destruction").mkdir()
        (folder / "destruction" / "PV.html").write_text("pv")
        case_workspace.save(folder, case_workspace.load(folder))
        listed = {path.name for path, _size in evidence_files(folder)}
        assert "Security.evtx" in listed and "conversation.json" in listed
        assert (
            "case.json" not in listed and "workspace.json" not in listed and "PV.html" not in listed
        )
        dialog = DestructionDialog(window)
        try:
            assert dialog.list.count() == 2
            assert not dialog.go.isEnabled()
            dialog.set_all(True)
            dialog.understood.setChecked(True)
            dialog.phrase.setText("DETRUIRE")
            dialog.operator.setText("M. Martin")
            dialog.reason.setPlainText("Fin de mission")
            dialog.update_total()
            assert dialog.go.isEnabled()
        finally:
            dialog.deleteLater()
    finally:
        window.close()


def test_a_corrupt_workspace_is_reported_in_the_panel_not_in_a_dialog(qt_application, tmp_path):
    window = Window(require_case=False, investigation_root=tmp_path / "Cases")
    errors = []
    window.error = errors.append
    try:
        case = window.create_investigation("Affaire F")
        (window.investigation_library.folder(case["id"]) / "workspace.json").write_text(
            "{broken", encoding="utf-8"
        )
        panel = window.operations_panel
        panel.refresh()
        assert "illisible" in panel.status.text() or "cannot be read" in panel.status.text()
        assert not errors
    finally:
        window.close()
