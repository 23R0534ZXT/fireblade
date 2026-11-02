"""Cross-feature regression: mixed collections, isolated cases and exact exports."""
import csv
import shutil
import time
from pathlib import Path


def verify_mixed_cases(app,directory,settings=None,pack=None,browser_evidence=None,rounds=6):
    from fireblade.core.collection import Collection,ToolPack,sha256
    from fireblade.core.engine import Case
    from fireblade.core.models import Filter,View
    from fireblade.runtime.resources import resource_path
    from fireblade.ui.app import Window
    from fireblade.validation.catscale import write_corpus
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    pack=pack or ToolPack(resource_path('forensic-tools'))
    linux=write_corpus(directory/'inputs'/'linux')
    windows=directory/'inputs'/'windows';windows.mkdir()
    if browser_evidence is None:
        for tool in ('Shellbags','WebCache'):
            for path in (pack.root/'qa'/'browser'/tool).iterdir():shutil.copy2(path,windows/path.name)
    else:
        for path in Path(browser_evidence).iterdir():
            if path.name in ('UsrClass.dat','WebCacheV01.dat'):shutil.copy2(path,windows/path.name)
    originals={path:sha256(path) for root in (linux,windows) for path in root.rglob('*') if path.is_file()}
    errors=[];window=Window(settings=settings,investigation_root=directory/'cases');window.error=lambda value:errors.append(str(value));window.show()
    def settle():
        deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            app.processEvents()
            if not window.busy and not window.jobs and not window.pool.activeThreadCount() and not getattr(window,'_collection_open_pending',False) and (window.model is None or not window.model.jobs) and not window.tabs.pending:
                if errors:raise AssertionError(str(errors))
                return
            time.sleep(.005)
        raise AssertionError('Mixed case did not settle')
    try:
        first=window.create_investigation('Enquête mixte — Windows et Linux',environment='mixed')
        if first is None:raise AssertionError(str(errors))
        for index,source in enumerate((linux,windows)):
            collection=Collection(source,window.investigation_data_directory('Collectes')/str(index),pack,window.settings,organization='artifacts')
            report=collection.parse();window.collection=collection;window.collection_finished(report);settle()
        if len(window.documents)!=9 or len(window.investigation_collections)!=2:raise AssertionError('Mixed collection tabs or links lost')
        index=next(i for i,doc in enumerate(window.documents) if Path(doc.source_info['path']).name=='WebCache.csv')
        window.switch_document(index);settle()
        url=window.case.headers.index('Url');container=window.case.headers.index('WebCache_Container')
        view=View(filters=[Filter(url,'contains','code.google.com/p/libyal')],groups=[container],pinned_columns=[url])
        window.set_view(view);settle()
        count=window.case.count(view)
        if not count:raise AssertionError('Known WebCache URLs disappeared after CatScale import')
        bookmark=window.case.page(View(filters=view.filters))[0][0]
        note='Contexte mixte\nÉvénement vérifié — 000001'
        window.case.bookmark(bookmark,note)
        first_path=window.case.path
        second=window.create_investigation('Enquête séparée',environment='linux');settle()
        if second is None or window.documents or window.case is not None:raise AssertionError('Case isolation failed')
        source=directory/'isolated.csv';source.write_text('Account,Identifier\nalice,0001\nbob,0002\n',encoding='utf-8')
        path=window.investigation_data_directory('Analyses')/'isolated.timeline'
        case=Case(path,settings=window.settings)
        try:case.import_csv(source)
        finally:case.close()
        window.load_case(path);settle();window.case.bookmark(2,'Autre enquête')
        window.set_view(View(filters=[Filter(0,'eq','bob')],sort_column=1,sort_type='number',descending=True));settle()
        for cycle in range(rounds):
            if not window.open_investigation(first['id']):raise AssertionError('Mixed case reopen failed')
            settle()
            if window.case.path!=first_path or len(window.documents)!=9 or len(window.investigation_collections)!=2:raise AssertionError('Mixed session changed')
            if window.view.filters!=view.filters or window.view.groups!=view.groups or window.view.pinned_columns!=[url]:raise AssertionError('Filters, groups or pins leaked across cases')
            if window.case.bookmarks()!={bookmark:note} or window.case.count(window.view)!=count:raise AssertionError('Mixed case data or notes changed')
            if cycle==0:
                target=directory/'filtered-annotated.csv';window.case.export(target,window.view,include_annotations=True)
                with target.open(encoding='utf-8-sig',newline='') as incoming:exported=list(csv.DictReader(incoming))
                if len(exported)!=count or not any(row.get('Fireblade_Note')==note for row in exported):raise AssertionError('Filtered annotated export changed')
            if not window.open_investigation(second['id']):raise AssertionError('Isolated case reopen failed')
            settle()
            if window.case.path!=path or len(window.documents)!=1 or window.case.bookmarks()!={2:'Autre enquête'}:raise AssertionError('Case data mixed')
            if window.case.count(window.view)!=1 or window.case.page(window.view)[0][2]!='0002':raise AssertionError('Isolated view or identifier changed')
        if not all(sha256(path)==digest for path,digest in originals.items()):raise AssertionError('Evidence changed')
        if not window.close():raise AssertionError('Case close failed')
    finally:window.close();window.deleteLater()
    reopened=Window(settings=settings,investigation_root=directory/'cases');reopened.error=lambda value:errors.append(str(value));reopened.show()
    try:
        if reopened.case is not None or reopened.documents or reopened.active_investigation is not None:raise AssertionError('Restart loaded old analyses')
        if reopened.cases_table.rowCount()!=2:raise AssertionError('Persistent catalogue lost cases')
    finally:reopened.close();reopened.deleteLater()
    return dict(status='passed',case_switches=rounds*2,mixed_analyses=9,collections=2,filtered_export_rows=count,
                annotations_and_views_isolated=True,source_hashes_unchanged=True,unloaded_restart=True)
