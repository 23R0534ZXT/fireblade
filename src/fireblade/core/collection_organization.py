"""Stream heterogeneous collection results into artifact tabs or one grouped table."""
import csv
from pathlib import Path
import uuid

from fireblade.core.engine import Case
from fireblade.core.models import View

ARTIFACTS = {
    'EvtxECmd':'EVTX', 'AmcacheParser':'Amcache', 'AppCompatCacheParser':'AppCompatCache',
    'PECmd':'Prefetch', 'MFTECmd':'MFT et USN', 'RECmd':'Registre', 'LECmd':'Raccourcis LNK',
    'JLECmd':'Jump Lists', 'SrumECmd':'SRUM', 'WxTCmd':'Windows Timeline',
    'RBCmd':'Corbeille', 'RecentFileCacheParser':'RecentFileCache', 'SQLECmd':'SQLite',
    'LinuxLogs':'Journaux Linux', 'native':'Exports CSV', 'Shellbags':'Shellbags', 'WebCache':'WebCache',
}


def artifact_name(tool, output):
    name = Path(output).name.casefold()
    if tool == 'native':
        for token, label in [('shellbag','Shellbags'),('jumplist','Jump Lists'),('jlecmd','Jump Lists'),('amcache','Amcache'),('evtx','EVTX'),('prefetch','Prefetch'),('pecmd','Prefetch'),('srum','SRUM'),('mftecmd','MFT et USN')]:
            if token in name:
                return label
    if tool == 'RECmd' and any(word in Path(output).name.casefold() for word in ('shellbag', 'bagmru')):
        return 'Shellbags'
    return ARTIFACTS.get(tool, tool)


def column_keys(headers):
    occurrences = {}
    keys = []
    for header in headers:
        index = occurrences.get(header, 0)
        keys.append((header, index))
        occurrences[header] = index+1
    return keys


def organize(collection):
    mode = collection.report.get('organization', 'files')
    if mode == 'files' or not collection.report['documents']:
        return
    from fireblade.core.collection import check_cancel
    originals = list(collection.report['documents'])
    origins = {}
    for entry in collection.report['files']:
        for run in entry.get('runs', []):
            for output in run.get('outputs', []):
                if output.get('analysis'):
                    origins[output['analysis']] = (output.get('family') or artifact_name(run['tool'], output['csv']), entry['path'], run['tool'])
    groups = {}
    for document in originals:
        origin = origins.get(document['path'])
        if origin is None:
            raise ValueError('Provenance de résultat absente ; organisation refusée')
        key = origin[0] if mode == 'artifacts' else 'Collecte complète'
        groups.setdefault(key, []).append((document, origin))
    folder = collection.output/'results'/('organisation-'+uuid.uuid4().hex)
    folder.mkdir()
    documents = []
    try:
        for title, sources in groups.items():
            check_cancel()
            collection.progress('Organisation : '+title)
            union, positions, headers = [], {}, []
            used = set()
            for document, _ in sources:
                case = Case(document['path'], settings=collection.settings, read_only=True)
                try:
                    for key in column_keys(case.headers):
                        if key in positions:continue
                        label = key[0]
                        number = 2
                        while label.casefold() in used:
                            label = key[0]+' ('+str(number)+')'
                            number += 1
                        used.add(label.casefold())
                        positions[key] = len(union)
                        union.append(key)
                        headers.append(label)
                finally:case.close()
            metadata = []
            for base in ('Artefact', 'Fichier source', 'Parseur'):
                label, number = base, 2
                while label.casefold() in used:
                    label = base+' (Fireblade '+str(number)+')'
                    number += 1
                used.add(label.casefold())
                metadata.append(label)
            target = folder/(title+'.csv')
            temporary = target.with_suffix('.partial')
            csv.field_size_limit(2**31-1)
            with temporary.open('x', encoding='utf-8', newline='') as stream:
                writer = csv.writer(stream)
                writer.writerow(metadata+headers)
                for document, origin in sources:
                    check_cancel()
                    case = Case(document['path'], settings=collection.settings, read_only=True)
                    with collection._case_lock:
                        collection._active_case = case
                    try:
                        projection = [positions[key] for key in column_keys(case.headers)]
                        with case.operation():
                            cursor = case.db.execute('SELECT '+','.join(case.column(i) for i in range(len(case.headers)))+' FROM events ORDER BY __row_id')
                            while rows := cursor.fetchmany(collection.settings.export_batch_rows if collection.settings else 2048):
                                check_cancel()
                                for row in rows:
                                    values = [None]*len(union)
                                    for index, value in zip(projection, row):values[index] = value
                                    writer.writerow(list(origin)+values)
                    finally:
                        with collection._case_lock:
                            collection._active_case = None
                            case.close()
            temporary.replace(target)
            view = View(groups=[0]) if mode == 'combined' else View()
            document = collection.import_result(target, 'organized', view=view, register=False)
            documents.append(document)
        collection.report['raw_documents'] = originals
        collection.report['documents'] = documents
    except BaseException:
        # Originals remain the active session until the complete organization succeeds.
        for document in documents:
            Path(document['path']).unlink(missing_ok=True)
        raise
