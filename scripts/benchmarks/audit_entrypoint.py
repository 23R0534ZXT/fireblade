"""Run the real bootstrap and startup-file flow with an automated Qt event loop."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication

from fireblade.core.preferences import Preferences, save_preferences
from fireblade.runtime.bootstrap import main as bootstrap
from fireblade.ui.app import Window
from fireblade.ui.dialogs import ImportDialog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--no-animation', action='store_true')
    args = parser.parse_args(); args.directory.mkdir(parents=True, exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(args.directory/'profile')
    prefs = Preferences(); prefs.startup_animation = not args.no_animation; save_preferences(prefs)
    source = args.directory/'startup.csv'; source.write_text('ID,Value\n001,évidence\n002,other\n', encoding='utf-8')
    before = source.read_bytes(); report = dict(animation=not args.no_animation)
    errors = []
    def event_loop(app):
        window = next(widget for widget in app.topLevelWidgets() if isinstance(widget, Window))
        window.error = lambda value: errors.append(str(value))
        assert window.active_investigation is None and not window.documents
        assert not window.workbench.isTabEnabled(0)
        assert window._startup_file == source
        deadline = time.monotonic()+15
        while not window.isVisible():
            app.processEvents(); time.sleep(.005)
            if time.monotonic() > deadline: raise TimeoutError('Startup window remained hidden')
        assert window.create_investigation('Case created after real startup')
        while True:
            app.processEvents()
            idle = not window.jobs and not window.pool.activeThreadCount() and (not window.model or not window.model.jobs)
            if window.case and window.model and window.model.rowCount() == 2 and idle: break
            if errors: raise AssertionError(errors)
            if time.monotonic() > deadline: raise TimeoutError('Deferred startup file was not imported')
            time.sleep(.005)
        assert window.workbench.isTabEnabled(0) and window._startup_file is None
        assert window.case.page(window.view) == [(1, '001', 'évidence'), (2, '002', 'other')]
        assert source.read_bytes() == before
        report.update(status='passed', case_gate=True, deferred_import=True, rows=2, source_unchanged=True)
        window.grab().save(str(args.directory/'startup.png'))
        assert window.close()
        return 0
    def confirm(dialog):
        dialog.accept()
        return dialog.result()
    with (patch.object(sys, 'argv', ['fireblade', str(source)]),
          patch.object(QApplication, 'exec', event_loop), patch.object(ImportDialog, 'exec', confirm)):
        try: bootstrap()
        except SystemExit as result: assert result.code == 0
    assert not errors
    (args.directory/'results.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__': main()
