"""Render every shipped theme through Fireblade, with synthetic evidence."""
import argparse
import csv
import json
import os
from pathlib import Path
import tempfile
import time

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from fireblade.core.engine import Case
from fireblade.core.themes import THEMES
from fireblade.ui.app import Window
from fireblade.ui.preferences_dialog import PreferencesDialog
from fireblade.validation.theme_gallery import check_theme_gallery


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='fireblade-themes-') as folder:
        root=Path(folder);os.environ['LOCALAPPDATA']=str(root/'profile');app=QApplication([])
        window=Window(investigation_root=root/'cases');window.resize(1360,850);window.show();errors=[];window.error=lambda message:errors.append(str(message))
        def settle():
            until=time.monotonic()+30
            while time.monotonic()<until:
                app.processEvents()
                if not window.jobs and not window.pool.activeThreadCount() and not window.tabs.pending and (not window.model or not window.model.jobs):return
                time.sleep(.005)
            raise TimeoutError('Theme preview did not settle')
        try:
            window.create_investigation('Atlas — galerie des thèmes',environment='mixed')
            source=root/'events.csv'
            with source.open('w',encoding='utf-8',newline='') as stream:
                writer=csv.writer(stream);writer.writerow(['Timestamp','User','SourceIP','Destination','EventID','Description'])
                for n in range(48):writer.writerow([f'2026-11-02T08:{n:02d}:00Z',['alice','svc-backup','admin'][n%3],['192.0.2.10','198.51.100.20','203.0.113.30'][n%3],'api.example.org',4624 if n%2==0 else 4688,['Authentification réseau','Exécution de processus','Connexion sortante'][n%3]+' — données synthétiques'])
            case=Case(root/'events.timeline');case.import_csv(source);case.bookmark(1,'Point à examiner — démonstration');case.close();window.load_case(root/'events.timeline');settle()
            window.tree.setCurrentIndex(window.model.index(2,1));app.processEvents()
            result=check_theme_gallery(window,args.output);settle()
            for mode in ('light','dark'):
                window.preferences.theme=mode;window.preferences.theme_preset='';window.preferences.theme_palette={};window.apply_preferences();app.processEvents()
                assert window.grab().save(str(args.output/f'standard-{mode}.png'))
            window.preferences.theme='dark';window.preferences.theme_preset='night-lit';window.apply_preferences();app.processEvents()
            dialog=PreferencesDialog(window.preferences,window);dialog.resize(880,760);dialog.show();app.processEvents()
            assert dialog.grab().save(str(args.output/'theme-preferences.png'));dialog.reject();dialog.deleteLater();settle()
            if errors:raise AssertionError(errors)
            manifest=dict(platform='Linux / Qt offscreen',data='Synthetic documentation records; no real incident',themes={key:dict(name=p.name,mode=p.mode,colors=p.palette(),capture=f'gallery-{key}.png',contrast=result[key]) for key,p in THEMES.items()},standard_modes=['standard-light.png','standard-dark.png'])
            (args.output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
            print(f'{len(THEMES)} preset captures, 2 standard captures and the preferences dialog; rendered contrast checks passed.')
        finally:settle();window.close();settle()


if __name__=='__main__':main()
