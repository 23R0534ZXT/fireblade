"""Additional GUI menu and cross-feature checks, using disposable investigations.

No application fixes are applied. Exit 1 records confirmed destination-protection
findings; exit 2 indicates an unexpected failure in another probe.
"""
import argparse
import copy
import csv
import hashlib
import json
import os
from pathlib import Path
import time
import traceback
import zipfile
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QFileDialog, QInputDialog,
    QLabel, QListWidget, QMessageBox, QPlainTextEdit, QTableWidget, QTextBrowser)

from fireblade.core.case_package import export_package, import_package
from fireblade.core.coverage import audit
from fireblade.core.engine import Case
from fireblade.core.investigation_report import build_report, write_report
from fireblade.core.ioc_hunt import parse_indicators
from fireblade.core.ioc_results import hunt, discover_hunts, HuntStore
from fireblade.core.models import Filter, View
from fireblade.core.workspace_reader import WorkspaceReader
from fireblade.ui.app import Window


def settle(app, window):
    deadline = time.monotonic()+30
    while time.monotonic() < deadline:
        app.processEvents()
        if (not window.jobs and not window.pool.activeThreadCount() and not window.tabs.pending
                and (not window.model or not window.model.jobs)):
            return
        time.sleep(.005)
    raise TimeoutError('GUI did not settle')


def loaded(app, root):
    os.environ['LOCALAPPDATA'] = str(root/'profile')
    window = Window(investigation_root=root/'cases')
    window.resize(1150, 800); window.show(); errors = []
    window.error = lambda value: errors.append(str(value))
    window.create_investigation('Audit fonctionnel 0.2.0')
    source = root/'source.csv'; source.write_text('Timestamp,User,IP,Value\n2026-11-01T12:00:00.000000001Z,alice,192.0.2.1,001\n2026-11-02T12:00:00Z,bob,192.0.2.2,002\n')
    case = Case(root/'analysis.timeline')
    try: case.import_csv(source)
    finally: case.close()
    window.load_case(root/'analysis.timeline'); settle(app, window)
    assert window.case and not errors
    return window, errors


def menu_checks(app, root):
    window, errors = loaded(app, root); results = []; failures = []
    def walk(menu, prefix):
        for action in menu.actions():
            if action.menu(): yield from walk(action.menu(), prefix+[action.text()])
            elif not action.isSeparator(): yield prefix+[action.text()], action
    actions = [item for menu in window.menuBar().actions() for item in walk(menu.menu(), [menu.text()])]
    exceptions = []
    import sys
    original_hook = sys.excepthook
    sys.excepthook = lambda kind, value, tb: exceptions.append(str(value))
    modal_observed = []
    timer = QTimer(); timer.setInterval(15)
    def cancel_modal():
        dialog = app.activeModalWidget()
        if dialog is not None:
            browser = dialog.findChild(QTextBrowser)
            modal_observed.append(dict(title=dialog.windowTitle(), text_length=len(browser.toPlainText()) if browser else None))
            if hasattr(dialog, 'reject'): dialog.reject()
    timer.timeout.connect(cancel_modal); timer.start()
    try:
        with (patch.object(QFileDialog, 'getOpenFileName', return_value=('', '')),
              patch.object(QFileDialog, 'getOpenFileNames', return_value=([], '')),
              patch.object(QFileDialog, 'getSaveFileName', return_value=('', '')),
              patch.object(QFileDialog, 'getExistingDirectory', return_value=''),
              patch.object(QInputDialog, 'getText', return_value=('', False)),
              patch.object(QInputDialog, 'getItem', return_value=('', False)),
              patch.object(QMessageBox, 'question', return_value=QMessageBox.No)):
            for path, action in actions:
                name = action.text(); item = dict(path=path)
                if name in ('Quitter', 'Fermer le case', 'Fermer l’onglet'):
                    item['status'] = 'separate_lifecycle_test'; results.append(item); continue
                if not action.isEnabled():
                    item['status'] = 'disabled_in_current_context'; results.append(item); continue
                prior = action.isChecked() if action.isCheckable() else None
                previous_errors = len(errors); previous_exceptions = len(exceptions)
                try:
                    if window.model and window.model.rowCount():
                        window.tree.setCurrentIndex(window.model.index(0, 1))
                    action.trigger(); settle(app, window)
                    if prior is not None and action.isChecked() != prior:
                        action.trigger(); settle(app, window)
                    if window.case and window.view != View():
                        window.set_view(View()); settle(app, window)
                    item['status'] = 'passed'
                except Exception as error:
                    item.update(status='error', error=repr(error)); failures.append(item)
                item['errors'] = errors[previous_errors:]+exceptions[previous_exceptions:]
                if name == 'Exporter les sources Hayabusa…' and item['errors'] == ['Sources Hayabusa absentes de cette construction.']:
                    item['status'] = 'expected_source_checkout_diagnostic'
                elif item['errors']: item['status'] = 'error'; failures.append(item)
                results.append(item)
        # The three lifecycle commands excluded above are exercised with checks.
        window.close_document(0); settle(app, window); assert not window.documents
        window.reopen_closed(); settle(app, window); assert len(window.documents) == 1
        assert window.close_investigation(); assert window.active_investigation is None
        assert window.open_investigation(window.investigation_library.list()[0][0]['id'])
        settle(app, window); assert len(window.documents) == 1
        assert not failures, failures
        return dict(actions=results, modals=modal_observed, lifecycle='close/reopen tab and case passed',
                    scope='actual QAction dispatch; file pickers cancelled; dialogs opened and cancelled')
    finally:
        timer.stop(); sys.excepthook = original_hook
        settle(app, window); window.close(); app.processEvents()


def protection_checks(app, root):
    results = []
    for writer in ('csv', 'session', 'tle_session', 'global_rules'):
        for target_kind in ('case', 'coverage', 'timeline', 'global_rules'):
            folder = root/(writer+'-'+target_kind); folder.mkdir()
            window, errors = loaded(app, folder)
            try:
                assert window.save_investigation()
                case_folder = window.investigation_library.folder(window.active_investigation['id'])
                target = {'case': case_folder/'case.json', 'coverage': case_folder/'coverage-state.json',
                          'timeline': case_folder/'timeline-state.json', 'global_rules': window.rule_store.path}[target_kind]
                if target_kind == 'global_rules': window.rule_store.save(window.rule_book)
                if not target.exists():
                    target.write_text('{"audit_marker":"preserve"}', encoding='utf-8')
                before = target.read_bytes()
                previous_errors = len(errors)
                try:
                    with patch.object(QFileDialog, 'getSaveFileName', return_value=(str(target), '')):
                        if writer == 'csv': window.export_csv()
                        elif writer == 'session': window.save_session(target)
                        elif writer == 'tle_session': window.export_tle_session(target)
                        else: window.export_global_rules(target)
                    settle(app, window)
                    after = target.read_bytes()
                    results.append(dict(writer=writer, target=target_kind, preserved=before == after,
                                        errors=errors[previous_errors:], replacement_format=json.loads(after).get('format')))
                finally:
                    # Restore synthetic internal metadata so the GUI closes cleanly.
                    target.write_bytes(before)
            finally:
                settle(app, window); window.close(); app.processEvents()
    return dict(finding=any(not result['preserved'] for result in results), priority='P2', cases=results,
                trigger='explicitly selecting an internal metadata/configuration filename as an export destination')


def cross_feature_roundtrip(app, root):
    window, errors = loaded(app, root)
    imported_window = None
    try:
        window.case.add_derived_columns([dict(name='Double', operation='expression', expression='ToInt([Value])*2')])
        window.case.bookmark(1, '<script>literal note</script>')
        view = View(search='alice', pinned_columns=[1], right_pinned_columns=[3], timestamp_columns=[0],
                    filters=[Filter(3, 'ge', '1')], auto_row_height=True)
        window.set_view(view); settle(app, window)
        assert window.model.rowCount() == 1
        window.remember_active(); assert window.save_investigation()
        documents = copy.deepcopy(window.documents)
        expected_view = copy.deepcopy(documents[0].view)
        reader = WorkspaceReader(documents, window.settings, window.case)
        store = hunt(reader, parse_indicators('192.0.2.1\nabsent.example'),
                     window.investigation_library.folder(window.active_investigation['id'])/'IOC-hunts', respect_filters=True)
        try:
            assert store.metadata['matching_fields'] == 1
            for summary in (False, True):
                receipt = store.export(root/('ioc-summary.xlsx' if summary else 'ioc-details.csv'), summary=summary, receipt=True)
                assert receipt['verified_rows'] == (2 if summary else 1)
        finally: store.close()
        coverage = audit(reader, verify_hashes=True)
        assert coverage['counts']['error'] == 0
        report = build_report(reader, 'Rapport <audit>', coverage=coverage)
        assert report['records'] == 1 and '&lt;script&gt;literal note&lt;/script&gt;' in report['html']
        write_report(root/'report.html', report, documents)
        write_report(root/'report.pdf', report, documents, pdf=True)
        assert (root/'report.pdf').read_bytes().startswith(b'%PDF-')
        archive = root/'portable.fireblade-case'
        export_package(window.investigation_library, window.active_investigation, documents, 0, archive,
                       include_sources=True, active_case=window.case)
        from fireblade.core.investigations import InvestigationLibrary
        destination = InvestigationLibrary(root/'imported')
        imported = import_package(destination, archive)['case']
        imported_window = Window(investigation_root=destination.root)
        imported_errors = []; imported_window.error = lambda value: imported_errors.append(str(value))
        assert imported_window.open_investigation(imported['id']); settle(app, imported_window)
        assert imported_window.view == expected_view, {
            key: (json.loads(expected_view.to_json())[key], value)
            for key, value in json.loads(imported_window.view.to_json()).items()
            if value != json.loads(expected_view.to_json())[key]}
        assert imported_window.case.bookmarks() == {1: '<script>literal note</script>'}
        assert imported_window.case.page(View())[0][-1] == '2.0000000000'
        hunts, hunt_errors = discover_hunts(destination.folder(imported['id'])/'IOC-hunts')
        assert len(hunts) == 1 and not hunt_errors
        imported_store = HuntStore(hunts[0]['path'])
        try:
            assert Path(imported_store.sources()[0]['path']).is_relative_to(destination.root)
            assert imported_store.page()['count'] == 1
        finally: imported_store.close()
        imported_window.show_timeline(); imported_window.timeline_panel.rebuild(); settle(app, imported_window)
        assert imported_window.timeline_panel.model.rowCount() == 2
        assert not errors and not imported_errors
        return dict(status='passed', checks=['derived column', 'combined filter', 'pins both sides', 'auto row heights',
                    'notes escaping', 'saved IOC CSV/XLSX', 'coverage', 'HTML/PDF', 'portable archive',
                    'restored view and notes', 'IOC relocation', 'timeline rebuilt after import'])
    finally:
        if imported_window: settle(app, imported_window); imported_window.close()
        settle(app, window); window.close(); app.processEvents()


def source_protection(app, root, source_archive=None):
    window, errors = loaded(app, root)
    try:
        source = Path(window.case.info['path']); before = source.read_bytes()
        hayabusa = dict(source_overwritten=False, status='not_exercised_without_source_archive')
        if source_archive is not None:
            if not source_archive.is_file(): raise FileNotFoundError(source_archive)
            try:
                with (patch('fireblade.ui.collection.resource_path', return_value=source_archive),
                      patch.object(QFileDialog, 'getSaveFileName', return_value=(str(source), 'ZIP (*.zip)'))):
                    window.export_hayabusa_source()
                overwritten = source.read_bytes() != before
                hayabusa = dict(source_overwritten=overwritten, source_became_zip=zipfile.is_zipfile(source), errors=errors[:],
                    sha256_before=hashlib.sha256(before).hexdigest(), sha256_after=hashlib.sha256(source.read_bytes()).hexdigest(),
                    status_message=window.statusBar().currentMessage())
            finally: source.write_bytes(before)
        # A true raw log archive and its generated parser output are distinct.
        from fireblade.core.collection import Collection, ToolPack
        evidence = root/'raw'; evidence.mkdir(); archive = evidence/'var-log.zip'
        with zipfile.ZipFile(archive, 'w') as output:
            output.writestr('var/log/auth.log', '2026-11-01T12:00:00Z host sshd[12]: Accepted password for alice from 192.0.2.1 port 22 ssh2\n')
        original = archive.read_bytes()
        collection = Collection(evidence, root/'parsed', ToolPack(root/'unused'))
        report = collection.parse(); assert report['documents']
        window.collection = collection
        window.load_case(report['documents'][0]['path']); settle(app, window)
        allowed = window.export_destination_is_safe(archive)
        try:
            with patch.object(QFileDialog, 'getSaveFileName', return_value=(str(archive), 'CSV (*.csv)')):
                window.export_csv(); settle(app, window)
            raw = dict(source_overwritten=archive.read_bytes() != original, accepted_by_guard=allowed,
                       original_in_inventory=any(entry['path'] == str(archive) for entry in report['files']),
                       sha256_before=hashlib.sha256(original).hexdigest(), sha256_after=hashlib.sha256(archive.read_bytes()).hexdigest(),
                       status_message=window.statusBar().currentMessage())
        finally: archive.write_bytes(original)
        return dict(finding=hayabusa['source_overwritten'] or raw['source_overwritten'], priority='P1',
                    hayabusa_source_export=hayabusa, raw_collection_export=raw,
                    trigger='explicitly choosing an existing evidence source as output; all originals here are disposable')
    finally:
        settle(app, window); window.close(); app.processEvents()


def accepted_dialogs(app, root):
    window, errors = loaded(app, root)
    checks = []
    try:
        from fireblade.ui.cross_search import SearchDialog
        from fireblade.ui.investigations import InvestigationDialog
        from fireblade.core.sessions import read_session
        dialog = SearchDialog(window); dialog.show(); dialog.text.setText('bob'); dialog.start()
        settle(app, window)
        assert len(dialog.results) == 1 and dialog.results[0].count == 1
        dialog.open_result(0, 0); settle(app, window)
        assert window.view.search == 'bob' and window.model.rowCount() == 1
        dialog.deleteLater(); window.workspace_search = None
        checks.append('cross-analysis search: run, count and open filtered result')
        window.set_view(View()); settle(app, window)
        # Exercise the render signal of the cell dialog with good and bad data.
        values = [('{"name":"évidence","items":[1,2]}', 1, False),
                  ('<root><item>évidence</item></root>', 2, False),
                  ('{malformed', 1, True), ('<!DOCTYPE x [<!ENTITY a "x">]><x>&a;</x>', 2, True)]
        source = root/'structured.csv'
        with source.open('w', newline='', encoding='utf-8') as stream:
            writer = csv.writer(stream); writer.writerow(['Payload']); writer.writerows([[v[0]] for v in values])
        case = Case(root/'structured.timeline')
        try: case.import_csv(source)
        finally: case.close()
        window.load_case(root/'structured.timeline'); settle(app, window)
        formats = []
        for number, (_, mode, invalid) in enumerate(values):
            window.tree.setCurrentIndex(window.model.index(number, 1))
            def inspect(dialog, mode=mode, invalid=invalid):
                dialog.findChild(QComboBox).setCurrentIndex(mode)
                messages = [label.text() for label in dialog.findChildren(QLabel)]
                error = any('non formatable' in value for value in messages)
                assert error == invalid, messages
                formats.append(dict(mode=mode, rejected=error, text=dialog.findChild(QPlainTextEdit).toPlainText()))
                return QDialog.Rejected
            with patch.object(QDialog, 'exec', inspect): window.cell_details()
        checks.append('JSON/XML rendering and explicit rejection of malformed JSON and XML DTD')
        window.show_timeline()
        def configure(dialog):
            table = dialog.findChild(QTableWidget)
            assert table and table.rowCount() == 2
            table.cellWidget(0, 1).setCurrentIndex(table.cellWidget(0, 1).findData(0))
            table.cellWidget(1, 1).setCurrentIndex(0)
            return QDialog.Accepted
        with patch.object(QDialog, 'exec', configure): window.timeline_panel.configure()
        settle(app, window)
        assert window.timeline_panel.store and window.timeline_panel.model.rowCount() == 6
        checks.append('timeline source/date chooser accepted; undated source retained')
        window.switch_document(0); settle(app, window)
        window.set_view(View(search='alice')); settle(app, window); assert window.save_investigation()
        window.case.bookmark(1, 'current note must survive recovery')
        window.set_view(View(search='bob')); settle(app, window); assert window.save_investigation()
        identifier = window.active_investigation['id']
        def recover(dialog):
            choices = dialog.findChild(QListWidget)
            for n in range(choices.count()):
                version = choices.item(n).data(Qt.UserRole)
                session = window.investigation_library.session_path(version)
                if session and read_session(session)[0][0].view.search == 'alice':
                    choices.setCurrentRow(n); return QDialog.Accepted
            raise AssertionError('Expected saved version absent')
        with patch.object(QDialog, 'exec', recover): window.recover_investigation()
        settle(app, window)
        assert window.view.search == 'alice'
        assert window.case.bookmarks() == {1: 'current note must survive recovery'}
        checks.append('UI recovery restores old view and retains current annotations')
        window.show_investigations(); window.cases_table.selectRow(0)
        def edit(dialog):
            dialog.name.setText('Renamed audit case'); dialog.description.setPlainText('Edited through the case dialog')
            dialog.environment.setCurrentIndex(dialog.environment.findData('mixed'))
            return QDialog.Accepted
        with patch.object(InvestigationDialog, 'exec', edit): window.edit_selected_investigation()
        assert window.active_investigation['name'] == 'Renamed audit case'
        window.cases_table.selectRow(0); window.archive_selected_investigation()
        assert window.active_investigation is None
        assert window.investigation_library.read(identifier)['status'] == 'archived'
        window.cases_archived.setChecked(True); window.cases_table.selectRow(0); window.archive_selected_investigation()
        assert window.investigation_library.read(identifier)['status'] == 'open'
        assert window.open_investigation(identifier); settle(app, window)
        checks.append('UI case metadata edit, archive, reactivate and reopen')
        assert not errors, errors
        return dict(checks=checks, formats=formats)
    finally:
        settle(app, window); window.close(); app.processEvents()


def contextual_actions(app, root):
    from fireblade.ui.menus import header_menu, cell_menu
    window, errors = loaded(app, root); results = []; os_calls = []
    timer = QTimer(); timer.setInterval(15)
    def cancel():
        dialog = app.activeModalWidget()
        if dialog is not None and hasattr(dialog, 'reject'): dialog.reject()
    timer.timeout.connect(cancel); timer.start()
    def leaves(menu, prefix):
        for action in menu.actions():
            if action.menu(): yield from leaves(action.menu(), prefix+[action.text()])
            elif not action.isSeparator(): yield prefix+[action.text()], action
    try:
        with (patch.object(QInputDialog, 'getText', return_value=('', False)),
              patch.object(QFileDialog, 'getOpenFileName', return_value=('', '')),
              patch.object(QMessageBox, 'question', return_value=QMessageBox.No),
              patch.object(QDesktopServices, 'openUrl', side_effect=lambda url: os_calls.append(url.toString()) or True)):
            for family in ('header', 'cell', 'grouped_header', 'pinned_header'):
                window.set_view(View(groups=[0]) if family == 'grouped_header' else View(pinned_columns=[0]) if family == 'pinned_header' else View())
                settle(app, window); window.tree.setCurrentIndex(window.model.index(0, 1))
                menu = cell_menu(window, window.model.index(0, 1)) if family == 'cell' else header_menu(window, 1)
                assert menu is not None
                for path, action in list(leaves(menu, [family])):
                    if not action.isEnabled(): continue
                    prior_errors = len(errors)
                    action.trigger(); settle(app, window)
                    actual_errors = errors[prior_errors:]
                    assert all(value == 'Ce chemin n’existe pas sur ce poste.' for value in actual_errors), actual_errors
                    results.append(dict(path=path, status='expected_non_path_diagnostic' if actual_errors else 'passed'))
                    window.set_view(View()); settle(app, window)
                    window.tree.setCurrentIndex(window.model.index(0, 1))
                menu.deleteLater(); app.processEvents()
            evidence = Path(window.case.info['path'])
            window.open_external(str(evidence)); window.open_external(str(evidence), directory=True)
            assert len(os_calls) == 2 and all(str(evidence.parent) in value for value in os_calls)
        return dict(actions=results, operating_system_calls_intercepted=os_calls,
                    scope='context action dispatch and state changes; OS launches intercepted, modal editors cancelled')
    finally:
        timer.stop(); settle(app, window); window.close(); app.processEvents()


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--hayabusa-source', type=Path, help='Verified source ZIP extracted from the published EXE')
    parser.add_argument('--only', nargs='+', choices=['menus', 'protection', 'roundtrip', 'source_protection', 'dialogs', 'context'])
    args = parser.parse_args(); args.directory.mkdir(parents=True, exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(args.directory/'profile')
    app = QApplication.instance() or QApplication([])
    report = dict(format='fireblade-functional-audit', checks=[])
    for name, function in [('menus', menu_checks), ('protection', protection_checks),
                           ('roundtrip', cross_feature_roundtrip),
                           ('source_protection', lambda app, root: source_protection(app, root, args.hayabusa_source)),
                           ('dialogs', accepted_dialogs), ('context', contextual_actions)]:
        if args.only and name not in args.only: continue
        root = args.directory/name; root.mkdir(); started = time.monotonic()
        try:
            details = function(app, root)
            item = dict(name=name, status='finding' if details.get('finding') else 'passed', details=details)
        except Exception as error:
            item = dict(name=name, status='error', error=repr(error), traceback=traceback.format_exc())
        item['seconds'] = round(time.monotonic()-started, 3); report['checks'].append(item)
        (args.directory/'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(item, ensure_ascii=False), flush=True)
    if any(item['status'] == 'error' for item in report['checks']): raise SystemExit(2)
    if any(item['status'] == 'finding' for item in report['checks']): raise SystemExit(1)


if __name__ == '__main__': main()
