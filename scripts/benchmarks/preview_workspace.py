"""Capture the current desktop workflows using synthetic evidence only."""
import argparse
import csv
import os
from pathlib import Path
import tempfile
import time

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from fireblade.core.engine import Case
from fireblade.core.models import View
from fireblade.ui.app import Window
from fireblade.ui.investigation_tools import ReportDialog
from fireblade.ui.theme import apply_theme


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='fireblade-docs-') as folder:
        root=Path(folder);os.environ['LOCALAPPDATA']=str(root/'profile');app=QApplication([]);apply_theme(app)
        window=Window(investigation_root=root/'cases');window.resize(1360,900);window.show();errors=[];window.error=lambda value:errors.append(str(value))
        def settle():
            deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                app.processEvents()
                if not window.jobs and not window.pool.activeThreadCount() and not window.tabs.pending and (not window.model or not window.model.jobs):return
                time.sleep(.005)
            raise TimeoutError('Desktop did not settle')
        def capture(name,widget=None):
            app.processEvents()
            if not (widget or window).grab().save(str(args.output/name)):raise RuntimeError('Capture failed')
        try:
            window.create_investigation('Atlas — démonstration Fireblade 0.1.1',environment='mixed')
            for number,name in enumerate(['Proxy — connexions','DNS — résolutions','EVTX — sessions']):
                source=root/(name+'.csv')
                with source.open('w',encoding='utf-8',newline='') as stream:
                    writer=csv.writer(stream);writer.writerow(['Timestamp','User','SourceIP','Destination','Description'])
                    for n in range(40):writer.writerow([f'2026-11-02T08:{n:02d}:00Z','alice' if n%2==0 else 'svc-backup','192.0.2.10' if n%3==0 else '198.51.100.20','api.example.org' if n%2==0 else 'updates.example.net',f'Événement {n+1} — données synthétiques'])
                case=Case(root/f'analysis-{number}.timeline');case.import_csv(source);case.bookmark(1,'Connexion à examiner — démonstration');case.close();window.load_case(root/f'analysis-{number}.timeline');settle()
            window.save_investigation();settle();window.set_view(View(search='alice'));settle();window.save_investigation();settle()
            def capture_recovery():
                if not QApplication.activeModalWidget():raise RuntimeError('Recovery dialog missing')
                capture('fireblade-recovery.png',QApplication.activeModalWidget());QApplication.activeModalWidget().reject()
            QTimer.singleShot(100,capture_recovery);window.recover_investigation();settle()
            window.show_timeline();window.timeline_panel.rebuild();settle()
            dialog=ReportDialog(window,'Atlas — constats et limites');dialog.description.setPlainText('Analyse des connexions observées sur les trois sources.\nLes événements retenus doivent être confrontés aux artefacts originaux.');dialog.timeline.setChecked(True)
            QTimer.singleShot(100,lambda:(capture('fireblade-report-options.png',dialog),dialog.reject()));dialog.exec();dialog.deleteLater();settle()
            panel=window.ioc_panel;window.workbench.setCurrentWidget(panel);panel.input.setPlainText('192.0.2.10\nexample.org\nabsent.example');panel.launch();settle();panel.select_ioc(panel.summary.index(1,0));settle();capture('fireblade-ioc-filtered.png')
            coverage=window.coverage_panel;coverage.open();coverage.record('Import','error','Accès refusé à une source — incident de démonstration.','exemple/collecte/artefact.evtx');coverage.mode.setCurrentIndex(1);coverage.level.setCurrentIndex(2);coverage.filter()
            # Show the error as well as the warnings in this history view.
            coverage.level.setCurrentIndex(0);coverage.filter();index=coverage.model.index(len(coverage.entries)-1,0);coverage.table.selectRow(index.row());coverage.show_details(index);capture('fireblade-coverage-history.png')
            if errors:raise AssertionError(errors)
            print('Four desktop captures generated from synthetic records.')
        finally:settle();window.close();settle()


if __name__=='__main__':main()
