"""Render a 75-second captioned tour from real Qt views and synthetic data.

Requires the source runtime and ffmpeg. No Windows qualification is implied by
an offscreen Linux capture. Output/report paths must be new.
"""
import argparse
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        raise RuntimeError('Install ffmpeg to generate the video and GIF')
    with tempfile.TemporaryDirectory(prefix='fireblade-demo-') as temporary:
        root = Path(temporary)
        os.environ['LOCALAPPDATA'] = str(root / 'profile')
        from PySide6.QtCore import Qt, QTimer
        from PySide6.QtGui import QColor, QFont, QImage, QPainter
        from PySide6.QtWidgets import QApplication, QDialog, QFileDialog
        from fireblade.ui.app import Window
        from fireblade.ui.dialogs import ImportDialog
        from fireblade.ui.investigation_tools import ReportDialog
        from fireblade.core.models import Filter, View
        from fireblade.core.sessions import read_session

        app = QApplication.instance() or QApplication([])
        window = Window(investigation_root=root / 'cases', rule_path=root / 'rules.json')
        window.resize(1280, 720)
        errors = []
        window.error = lambda error: errors.append(str(error))
        window.show()
        chapters = []

        def settle():
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                app.processEvents()
                if errors:
                    raise RuntimeError('; '.join(errors))
                if (not window.jobs and not window.pool.activeThreadCount()
                        and not window.tabs.pending
                        and (window.model is None or not window.model.jobs)):
                    app.processEvents()
                    return
                time.sleep(.005)
            raise TimeoutError('Demo operation did not settle')

        def capture(title, caption, seconds, widget=None):
            settle()
            canvas = QImage(1280, 900, QImage.Format_RGB32)
            canvas.fill(QColor('#112238'))
            painter = QPainter(canvas)
            painter.setPen(QColor('#ffffff'))
            painter.setFont(QFont('DejaVu Sans', 22, QFont.Bold))
            painter.drawText(24, 40, title)
            grab = (widget or window).grab()
            painter.drawPixmap(0, 70, grab.scaled(1280, 720, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            painter.setFont(QFont('DejaVu Sans', 13))
            painter.drawText(24, 804, 1230, 50, Qt.TextWordWrap, caption)
            painter.setPen(QColor('#b8c7d9'))
            painter.setFont(QFont('DejaVu Sans', 10))
            painter.drawText(24, 882, 'Données synthétiques · vues réelles automatisées · Linux / Qt hors écran · vidéo montée, sans mesure de performance')
            painter.end()
            name = f'{len(chapters):02}.png'
            assert canvas.save(str(out / name))
            chapters.append(dict(frame=name, title=title, caption=caption, seconds=seconds))

        try:
            settle()
            capture('Fireblade — un parcours d’investigation', 'Un EXE Windows, des données locales et un pack public pour commencer. Voici un exemple synthétique dans la véritable interface.', 8)
            window.create_investigation('Démonstration — activité de connexion', 'Exercice synthétique, aucune enquête réelle.', 'windows')
            source = root / 'activite-demo.csv'
            with source.open('w', encoding='utf-8-sig', newline='') as stream:
                writer = csv.writer(stream)
                writer.writerow(['Timestamp', 'Artifact', 'User', 'Computer', 'SourceIP', 'Description'])
                for row in [
                    ['10:00:00', 'EVTX', 'alice', 'PC-LAB-01', '192.0.2.10', 'Connexion de démonstration'],
                    ['10:01:00', 'EVTX', 'bob', 'PC-LAB-02', '192.0.2.20', 'Échec de connexion de démonstration'],
                    ['10:02:00', 'Prefetch', 'alice', 'PC-LAB-01', '', 'Exécution de démonstration'],
                    ['10:03:00', 'EVTX', 'alice', 'PC-LAB-01', '192.0.2.10', 'Nouvelle connexion de démonstration'],
                    ['10:04:00', 'MFT', 'bob', 'PC-LAB-02', '', 'Création de fichier de démonstration'],
                    ['10:05:00', 'EVTX', 'alice', 'PC-LAB-01', '192.0.2.10', 'Fin de session de démonstration'],
                ]:
                    writer.writerow(['2026-11-02T' + row[0] + 'Z', *row[1:]])

            def accept_import():
                dialog = app.activeModalWidget()
                if not isinstance(dialog, ImportDialog):
                    raise RuntimeError('Expected the import dialog')
                dialog.target.setText(str(root / 'activite.timeline'))
                dialog.accept()
            QTimer.singleShot(30, accept_import)
            window.import_file(source)
            settle()
            assert window.case.count(View()) == 6
            capture('1. Ouvrir un export dans un dossier d’enquête', 'Les valeurs, les dates et les références de source restent consultables. Ces six lignes sont fabriquées pour la démonstration.', 10)
            window.set_view(View(filters=[Filter(2, 'eq', 'alice')]))
            settle()
            assert window.case.count(window.view) == 4
            capture('2. Filtrer les données', 'Le filtre sur l’utilisateur alice retrouve quatre lignes. Les filtres portent sur toute l’analyse, même quand la grille est paginée.', 10)
            window.case.bookmark(1, 'À examiner : connexion issue de 192.0.2.10 (démonstration).')
            window.apply()
            settle()
            capture('3. Garder une piste avec un signet et une note', 'La note est enregistrée dans la base d’analyse. Un indicateur observé est une piste à vérifier, pas une preuve de compromission.', 10)
            window.set_view(View())
            settle()
            window.show_timeline()
            window.timeline_panel.rebuild()
            settle()
            assert window.timeline_panel.store
            capture('4. Replacer l’activité dans le temps', 'La chronologie conserve le lien vers les lignes sources. Les dates UTC de cet exemple sont explicites.', 10)
            window.workbench.setCurrentWidget(window.ioc_panel)
            window.ioc_panel.input.setPlainText('192.0.2.10')
            window.ioc_panel.launch()
            settle()
            assert window.ioc_panel.store
            capture('5. Rechercher un IOC dans les analyses', 'L’adresse 192.0.2.10 appartient à une plage de documentation. La recherche s’effectue localement, sans requête vers cette adresse.', 12)
            window.persist_investigation()
            snapshots, _ = read_session(window.investigation_library.session_path(window.active_investigation))
            assert len(snapshots) == 1
            report_path = root / 'rapport-demo.html'
            original_exec, original_save = ReportDialog.exec, QFileDialog.getSaveFileName
            def accept_report(dialog):
                dialog.description.setPlainText('Exercice synthétique : vérifier la connexion annotée. Aucune conclusion de compromission.')
                return QDialog.Accepted
            ReportDialog.exec = accept_report
            QFileDialog.getSaveFileName = lambda *args, **kwargs: (str(report_path), 'HTML')
            try:
                window.export_investigation_report()
                settle()
            finally:
                ReportDialog.exec, QFileDialog.getSaveFileName = original_exec, original_save
            assert report_path.is_file() and '192.0.2.10' in report_path.read_text(encoding='utf-8')
            window.workbench.setCurrentIndex(window.cases_tab_index)
            capture('6. Enregistrer et produire un rapport HTML', 'Le dossier a été sauvegardé et un rapport contenant la note a réellement été généré pendant ce parcours.', 10)
            capture('À vous d’essayer — 15 minutes suffisent pour un retour', 'Téléchargez Fireblade.exe et le pack de test depuis le README. Partagez vos impressions dans l’issue #6, ou ouvrez une issue pour un bug précis.', 5)
        finally:
            window.close()
            settle()
        assert sum(item['seconds'] for item in chapters) == 75
        (out / 'chapters.json').write_text(json.dumps(dict(duration_seconds=75, source='real Qt source application', platform='Linux offscreen', data='synthetic', chapters=chapters), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        playlist = out / 'frames.txt'
        playlist.write_text(''.join(f"file '{item['frame']}'\nduration {item['seconds']}\n" for item in chapters) + f"file '{chapters[-1]['frame']}'\n", encoding='utf-8')
        subprocess.run([ffmpeg, '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', str(playlist), '-t', '75', '-r', '10', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '25', '-movflags', '+faststart', str(out / 'fireblade-demo.mp4')], check=True)
        # A small animated preview; the MP4 is the full 75-second tour.
        subprocess.run([ffmpeg, '-y', '-loglevel', 'error', '-framerate', '1/2', '-i', str(out / '%02d.png'), '-filter_complex', '[0:v]scale=800:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96[p];[b][p]paletteuse', '-loop', '0', str(out / 'fireblade-demo.gif')], check=True)


if __name__ == '__main__':
    main()
