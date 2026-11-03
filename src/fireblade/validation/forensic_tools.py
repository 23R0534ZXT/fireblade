"""Run the actual embedded engines from the relocated one-file Windows EXE."""
import gzip
import shutil
import json
from contextlib import contextmanager
import time
from pathlib import Path

from fireblade.core.collection import Collection, PARSERS, ToolPack, execute
from fireblade.runtime.resources import resource_path


@contextmanager
def parser_result_display(app, settings=None):
    """Render parser outputs without adding documents to other validation windows."""
    from fireblade.ui.app import Window
    window = Window(require_case=False, settings=settings)
    errors = []
    window.error = errors.append
    window.show()

    def settle():
        deadline = time.monotonic()+30
        while time.monotonic() < deadline:
            app.processEvents()
            if not window.jobs and not window.pool.activeThreadCount() and (window.model is None or not window.model.jobs):
                return
            time.sleep(.005)
        raise TimeoutError('Affichage des résultats des parseurs non terminé')

    def display(path, expected):
        window.load_case(path)
        settle()
        if errors:
            raise AssertionError(str(errors))
        if window.case is None or str(window.case.path) != str(path):
            raise AssertionError('Résultat du parseur non ouvert : '+str(path))
        if window.model.rowCount() != len(expected):
            raise AssertionError('Nombre de lignes affichées incorrect : '+str(path))
        if expected and tuple(window.model.node(window.model.index(0, 0)).values) != expected[0]:
            raise AssertionError('Valeurs affichées altérées : '+str(path))

    def preview_context(collection, alert_row, events):
        window.collection=collection
        window.load_case(collection.report['detection']['analysis']);settle()
        window.workbench.setCurrentIndex(0)
        number=next(i for i in range(window.model.rowCount()) if window.model.node(window.model.index(i,0)).values[0]==alert_row)
        window.tree.setCurrentIndex(window.model.index(number,1))
        before=len(window.documents);registered=len(collection.report['documents'])
        window.context_open.click();settle()
        preview=window.context_preview
        if preview is None or not preview.isVisible() or preview.model.rowCount()!=events:
            raise AssertionError('Aperçu EVTX latéral incomplet : '+str(errors))
        if len(window.documents)!=before or len(collection.report['documents'])!=registered:
            raise AssertionError('Un aperçu ne doit pas ajouter un onglet ou modifier la session')
        preview.keep.click();settle()
        if window.context_metadata() is None or not window.context_return.isVisibleTo(window):
            raise AssertionError('Le contexte conservé ne permet pas le retour aux alertes')
        if errors:raise AssertionError(str(errors))
        return True

    display.preview_context=preview_context

    try:
        yield display
    finally:
        settle()
        window.close()
        window.deleteLater()


def verify_embedded_engines(directory, display=None):
    directory=Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    pack=ToolPack(resource_path('forensic-tools'))
    manifest=json.loads((pack.root/'manifest.json').read_text(encoding='utf-8'))
    if {tool['name'] for tool in manifest['parsers']} != set(PARSERS):
        raise AssertionError('Pack de parseurs incomplet')
    for tool in (*PARSERS, 'Shellbags'):
        execute(pack.command(tool)+['--help'],pack.root/tool,directory/(tool+'-help.log'),timeout=60)
    execute(pack.command('Hayabusa')+['dfir-timeline','--help'],pack.root/'Hayabusa',directory/'Hayabusa-help.log',timeout=60)
    source=pack.root/'qa'/'System.evtx'
    if not source.is_file():raise AssertionError('EVTX de qualification absent')
    evidence=directory/'evidence'
    evidence.mkdir()
    shutil.copy2(source,evidence/'System.evtx')
    for compressed in (pack.root/'qa'/'registry').glob('*.gz'):
        with gzip.open(compressed,'rb') as incoming,(evidence/compressed.stem).open('wb') as outgoing:
            shutil.copyfileobj(incoming,outgoing)
    collection=Collection(evidence,directory/'forensic-collection',pack)
    shutil.copytree(pack.root/'qa'/'matrix', evidence/'matrix')
    report=collection.parse()
    matrix = verify_parser_results(report, display)
    event=next(entry for entry in report['files'] if Path(entry['path']).name=='System.evtx')
    if event['status']!='complete':raise AssertionError(str(event))
    system=next(entry for entry in report['files'] if Path(entry['path']).name=='SYSTEM')
    if system['status']!='complete':raise AssertionError(str(system))
    report=collection.analyze()
    if report['detection']['status']!='complete' or report['detection']['alerts']<2:
        raise AssertionError(str(report['detection']))
    from fireblade.core.alert_context import build_context
    from fireblade.core.engine import Case
    from fireblade.core.models import View
    alerts=Case(report['detection']['analysis'])
    try:
        row=alerts.page(View())[0]
        alert=dict(zip(alerts.headers,row[1:]))
    finally:alerts.close()
    context=build_context(collection,alert,report['detection']['analysis'],row[0])
    if context['references']!=1 or context['events']<=context['references']:
        raise AssertionError('Le contexte ne relie pas l’alerte aux événements EVTX voisins : '+str(context))
    preview_rendered=display.preview_context(collection,row[0],context['events']) if display is not None and hasattr(display,'preview_context') else False
    return dict(parser_matrix=matrix,context_events=context['events'],context_references=context['references'],context_preview_rendered=preview_rendered,parsers=len(PARSERS),registry_plugins=len(manifest['registry_plugins']['included']),registry_fixture_passed=True,alerts=report['detection']['alerts'])



def verify_parser_results(report, display=None):
    from fireblade.core.engine import Case
    from fireblade.core.models import View
    results = {name: dict(files=0, outputs=0, rows=0) for name in PARSERS}
    for entry in report['files']:
        for run in entry.get('runs', []):
            name = run['tool']
            if name not in results:
                continue
            if run['status'] != 'complete':
                raise AssertionError('Parsing non validé : '+str(run))
            result = results[name]
            result['files'] += 1
            for output in run['outputs']:
                case = Case(output['analysis'])
                try:
                    count = case.count(View())
                    page = case.page(View())
                    if count and not page:
                        raise AssertionError('Résultats illisibles : '+output['analysis'])
                finally:
                    case.close()
                if display is not None:
                    display(output['analysis'], page)
                result['outputs'] += 1
                result['rows'] += count
    missing = [name for name, result in results.items() if not result['outputs'] or not result['rows']]
    if missing:
        raise AssertionError('Parseurs sans résultat non vide vérifié : '+', '.join(missing))
    return results
