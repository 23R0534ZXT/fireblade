"""Render a reproducible synthetic chronology through the actual desktop UI."""
import argparse
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import time

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from fireblade.core.engine import Case
from fireblade.core.models import View
from fireblade.ui.app import Window
from fireblade.ui.theme import apply_theme


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,required=True)
    args=parser.parse_args();args.directory.mkdir(parents=True,exist_ok=False)
    os.environ['LOCALAPPDATA']=str(args.directory/'profile')
    app=QApplication([]);apply_theme(app)
    window=Window(investigation_root=args.directory/'cases');window.resize(1440,1000);window.show()
    errors=[];window.error=lambda message:errors.append(str(message))
    def settle():
        deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            app.processEvents()
            if not window.jobs and not window.pool.activeThreadCount() and not window.tabs.pending and (window.model is None or not window.model.jobs):return
            time.sleep(.005)
        raise TimeoutError('Timeline UI did not settle')
    try:
        window.create_investigation('Incident Atlas — chronologie de démonstration',environment='mixed')
        names=['EVTX — authentifications','Sysmon — processus','Linux — connexions','MFT — fichiers','Navigateur — WebCache','Alertes — Hayabusa']
        base=datetime(2026,10,26,tzinfo=timezone.utc)
        for source,name in enumerate(names):
            path=args.directory/(name+'.csv')
            with path.open('w',encoding='utf-8',newline='') as stream:
                writer=csv.writer(stream);writer.writerow(['Timestamp','User','SourceIP','Path','SHA256','Description'])
                for n in range(700):
                    minute=(n*71+source*43)%(5*24*60)
                    if n%3==0:minute=2*24*60+10*60+(n%120)
                    date=base+timedelta(minutes=minute,seconds=n%59)
                    writer.writerow([date.isoformat(),['alice','svc-backup','admin'][n%3],['10.23.4.17','192.0.2.41','10.0.0.12'][n%3],
                                     f'C:/Users/alice/AppData/Temp/artifact-{n%20}.exe',f'{n%9:064x}',
                                     ['Authentification réseau','Exécution de processus','Écriture de fichier','Connexion sortante'][n%4]])
            case=Case(args.directory/f'{source}.timeline');case.import_csv(path)
            for row in (1,22,100):case.bookmark(row,'Point d’investigation à vérifier — démonstration synthétique')
            case.close();window.load_case(args.directory/f'{source}.timeline');settle()
        window.show_timeline();window.timeline_panel.rebuild();settle()
        if errors:raise AssertionError(errors)
        for theme in ('light','dark'):
            apply_theme(app,theme);app.processEvents();window.grab().save(str(args.directory/f'timeline-{theme}.png'))
        window.timeline_panel.query.setText('10.23.4.17');window.timeline_panel.kind.setCurrentIndex(window.timeline_panel.kind.findData('ip'))
        window.timeline_panel.exact.setChecked(True);window.timeline_panel.apply_query();settle()
        window.timeline_panel.zoom(.18);settle()
        window.grab().save(str(args.directory/'timeline-correlation.png'))
        window.timeline_panel.export_csv(args.directory/'correlation.csv');settle()
        print('Synthetic timeline: 4200 events, 6 sources, light/dark/correlation captures and filtered CSV passed.')
    finally:
        settle();window.close();settle()


if __name__=='__main__':main()
