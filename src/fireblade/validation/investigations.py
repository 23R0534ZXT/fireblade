"""Exercise persistent cases with real databases in an isolated catalogue."""
from pathlib import Path
import time


def verify_investigations(app, directory, settings=None):
    from fireblade.core.engine import Case
    from fireblade.core.models import Filter, View
    from fireblade.ui.app import Window
    from fireblade.ui.dialogs import ImportDialog
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    root=directory/'cases'
    errors=[]
    window=Window(require_case=False, settings=settings,investigation_root=root)
    window.error=lambda value:errors.append(str(value))
    window.show()

    def settle(target):
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            app.processEvents()
            if not target.busy and not target.jobs and not target.pool.activeThreadCount() and not getattr(target,'_collection_open_pending',False) and (target.model is None or not target.model.jobs) and not target.tabs.pending:
                if errors:raise AssertionError(str(errors))
                return
            time.sleep(.005)
        raise AssertionError('Case workspace did not settle')

    first=None
    try:
        first=window.create_investigation('Enquête de qualification','Session persistante et annotations','windows')
        if first is None:raise AssertionError(str(errors))
        paths=[]
        for name in ('événements','activité'):
            source=directory/(name+'.csv');source.write_text('User,ID\nalice,0001\nbob,0002\n',encoding='utf-8')
            dialog=ImportDialog(source,window)
            try:
                path=dialog.values()[0]
                if path.parent != window.investigation_library.folder(first['id'])/'Analyses':raise AssertionError('Destination hors du case')
            finally:dialog.deleteLater()
            case=Case(path,settings=window.settings)
            try:case.import_csv(source)
            finally:case.close()
            window.load_case(path);settle(window);paths.append(path)
        window.switch_document(0);settle(window)
        window.case.bookmark(1,'Note conservée')
        window.set_view(View(filters=[Filter(0,'eq','alice')],sort_column=1,sort_type='number',descending=True,pinned_columns=[0]))
        settle(window)
        second=window.create_investigation('Autre enquête',environment='linux');settle(window)
        if second is None or window.case is not None or window.documents:raise AssertionError('Le changement de case conserve des analyses chargées')
        if not window.close():raise AssertionError('Fermeture du case refusée')
    finally:
        window.close();window.deleteLater()
    reopened=Window(require_case=False, settings=settings,investigation_root=root)
    reopened.error=lambda value:errors.append(str(value));reopened.show()
    try:
        if reopened.case is not None or reopened.model is not None or reopened.documents or reopened.active_investigation is not None:
            raise AssertionError('Le démarrage charge une ancienne session')
        if reopened.cases_table.rowCount()!=2:raise AssertionError('Catalogue de cases non conservé')
        if not reopened.open_investigation(first['id']):raise AssertionError(str(errors))
        settle(reopened)
        if len(reopened.documents)!=2 or reopened.active_document!=0 or reopened.case.path!=paths[0]:
            raise AssertionError('Session du case non restaurée')
        if reopened.view.filters!=[Filter(0,'eq','alice')] or reopened.view.pinned_columns!=[0] or not reopened.view.descending:
            raise AssertionError('Filtres ou disposition perdus')
        if reopened.case.bookmarks()!={1:'Note conservée'}:raise AssertionError('Annotations perdues')
        return dict(status='passed',cases=2,restored_analyses=2,unloaded_startup=True,session_and_notes_restored=True)
    finally:
        reopened.close();reopened.deleteLater()
