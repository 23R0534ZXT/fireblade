"""Real public Shellbags/ESE acceptance data in a case and the actual grid."""
from pathlib import Path
import shutil
import time


def verify_browser_artifacts(app,directory,settings=None,pack=None,evidence=None):
    from fireblade.core.collection import Collection,ToolPack
    from fireblade.core.engine import Case
    from fireblade.core.models import Filter,View
    from fireblade.runtime.resources import resource_path
    from fireblade.ui.app import Window
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    pack=pack or ToolPack(resource_path('forensic-tools'))
    source=directory/'evidence';source.mkdir()
    if evidence is None:
        for tool in ('Shellbags','WebCache'):
            for path in (pack.root/'qa'/'browser'/tool).iterdir():shutil.copy2(path,source/path.name)
    else:
        for path in Path(evidence).iterdir():
            if path.name in ('UsrClass.dat','WebCacheV01.dat'):shutil.copy2(path,source/path.name)
    window=Window(settings=settings,investigation_root=directory/'cases');errors=[];window.error=lambda value:errors.append(str(value));window.show()
    def settle():
        deadline=time.monotonic()+45
        while time.monotonic()<deadline:
            app.processEvents()
            if not window.busy and not window.jobs and not window.pool.activeThreadCount() and not getattr(window,'_collection_open_pending',False) and (window.model is None or not window.model.jobs) and not window.tabs.pending:
                if errors:raise AssertionError(str(errors))
                return
            time.sleep(.005)
        raise AssertionError('Shellbags/WebCache display did not settle')
    try:
        investigation=window.create_investigation('Shellbags et WebCache',environment='windows')
        if not investigation:raise AssertionError(str(errors))
        collection=Collection(source,window.investigation_data_directory('Collectes')/'browser',pack,settings,organization='artifacts')
        report=collection.parse()
        results={name:[] for name in ('Shellbags','WebCache')}
        for entry in report['files']:
            for run in entry.get('runs',[]):
                if run['tool'] not in results:continue
                if run['status'] not in ('complete','complete_with_warnings'):raise AssertionError(str(run))
                if run['tool']=='Shellbags' and not any('dirty hive' in warning.lower() for warning in run.get('warnings',[])):
                    raise AssertionError('Dirty public hive warning missing')
                if run['tool']=='WebCache' and run['status']!='complete':raise AssertionError('Unexpected warning on clean public WebCache')
                for output in run['outputs']:
                    case=Case(output['analysis'],settings=settings)
                    try:
                        count=case.count(View());results[run['tool']].append(count)
                        if run['tool']=='Shellbags':
                            if count!=523:raise AssertionError('Shellbags count differs from pinned fixture')
                            if not case.count(View(filters=[Filter(case.headers.index('Path'),'contains','osTriage2')])):raise AssertionError('Missing reconstructed Shellbags path')
                        elif 'Url' in case.headers and 'AccessedTime' in case.headers and count:
                            if 'AccessedTime_UTC' not in case.headers:raise AssertionError('Missing WebCache UTC interpretation')
                    finally:case.close()
        counts={name:sum(values) for name,values in results.items()}
        if counts!={'Shellbags':523,'WebCache':1612}:raise AssertionError(str(counts))
        window.collection=collection;window.collection_finished(report);settle()
        for index in range(len(window.documents)):
            window.switch_document(index);settle()
            if window.model.rowCount()==0:raise AssertionError('Empty browser artifact grid')
            expected=window.case.page(window.view)[0]
            if tuple(window.model.node(window.model.index(0,0)).values)!=expected:raise AssertionError('Browser values changed in grid')
            window.case.bookmark(1,'Note '+str(index))
        if not window.close_investigation() or not window.open_investigation(investigation['id']):raise AssertionError('Browser case save/reopen failed')
        settle()
        for index in range(len(window.documents)):
            window.switch_document(index);settle()
            if window.case.bookmarks()!={1:'Note '+str(index)}:raise AssertionError('Browser annotation lost')
        return dict(status='passed',records=counts,analyses=len(window.documents),case_and_notes_restored=True,
                    dirty_fixture_warning_expected=True,webcache_recovery='not performed')
    finally:window.close();window.deleteLater()
