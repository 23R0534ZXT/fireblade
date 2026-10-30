"""Explicit readers for TLE session references and column-layout XML.

These readers do not execute plugins, .NET assemblies or serialized objects.
Unsupported layout expressions are rejected instead of being silently discarded.
"""
from pathlib import Path
import json
import shutil
import threading
import uuid
import xml.etree.ElementTree as ET

from fireblade.core.engine import Case
from fireblade.core.errors import OperationCancelled, job_cancelled
from fireblade.core.models import AnalysisSnapshot, View


def read_tle_session(path):
    path = Path(path).resolve()
    if path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError('Session limitée à 4 Mo')
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict):
        raise ValueError('Session TLE invalide')
    files = data.get('SessionFiles')
    if not isinstance(files, dict) or not 1 <= len(files) <= 1000:
        raise ValueError('Session TLE : SessionFiles doit référencer de 1 à 1000 fichiers')
    result = []
    for source, tags in files.items():
        if not isinstance(source, str) or not isinstance(tags, list) or len(tags) > 100000:
            raise ValueError('Référence ou liste de tags invalide (100000 tags maximum par fichier)')
        source = Path(source)
        source = (path.parent/source).resolve() if not source.is_absolute() else source.resolve()
        if not source.is_file() or source.suffix.lower() not in ('.csv','.tsv','.txt','.xlsx','.xls'):
            raise ValueError(f'Fichier de session absent ou non pris en charge : {source}')
        if any(type(tag) is not int or tag < 1 for tag in tags):
            raise ValueError('Les tags doivent être des numéros d’enregistrement positifs')
        result.append((source, tags))
    return result


class TleSessionImport:
    def __init__(self, references, directory, settings):
        self.references, self.directory, self.settings = references, Path(directory), settings
        self.current = None
        self.lock = threading.Lock()
        self.cancelled = threading.Event()

    def interrupt(self):
        self.cancelled.set()
        with self.lock:
            if self.current:
                self.current.interrupt()

    def run(self):
        snapshots, created = [], []
        self.directory.mkdir(parents=True, exist_ok=True)
        try:
            for source, tags in self.references:
                if self.cancelled.is_set() or job_cancelled():
                    raise OperationCancelled()
                target = self.directory/(source.stem + '-' + uuid.uuid4().hex[:12] + '.timeline')
                case = Case(target, settings=self.settings)
                created.append(target)
                try:
                    with self.lock:
                        self.current = case
                    if self.cancelled.is_set():
                        raise OperationCancelled()
                    if source.suffix.lower() in ('.xls','.xlsx'):
                        from fireblade.core.spreadsheets import sheet_names
                        if source.suffix.lower() == '.xls':
                            from fireblade.core.legacy_excel import sheet_names
                        case.import_excel(source, sheet_names(source)[0])
                    else:
                        case.import_csv(source)
                    if tags:
                        case.bookmark_many(tags, '', 'mark')
                    snapshots.append(AnalysisSnapshot(str(target), case.info, View(), b''))
                finally:
                    with self.lock:
                        self.current = None
                        case.close()
            if self.cancelled.is_set() or job_cancelled():
                raise OperationCancelled()
            return snapshots
        except BaseException:
            for target in created:
                target.unlink(missing_ok=True)
                target.with_suffix(target.suffix+'.wal').unlink(missing_ok=True)
                shutil.rmtree(str(target)+'.tmp', ignore_errors=True)
            raise


def read_tle_columns(path, headers):
    path = Path(path)
    if path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError('Disposition limitée à 4 Mo')
    raw = path.read_text(encoding='utf-8-sig')
    if '<!DOCTYPE' in raw.upper() or '<!ENTITY' in raw.upper():
        raise ValueError('DTD et entités non prises en charge')
    root = ET.fromstring(raw)
    known = {header.casefold(): i for i, header in enumerate(headers)}
    columns = []
    for node in root.iter():
        values = {child.attrib.get('name'): child.text or '' for child in node if child.tag == 'property'}
        field = values.get('FieldName')
        if field is None:
            continue
        # Internal TLE line and tag fields have no source-column counterpart.
        if field.casefold() in ('line','tag','color') and field.casefold() not in known:
            continue
        if field.casefold() not in known:
            raise ValueError(f'Colonne du layout absente de la source : {field}')
        index = known[field.casefold()]
        visible = int(values.get('VisibleIndex', len(columns)))
        width = int(values.get('Width', '150'))
        if not 20 <= width <= 10000:
            raise ValueError('Largeur de colonne invalide')
        fixed = values.get('Fixed', 'None')
        if fixed not in ('None','Left','0','1',''):
            raise ValueError('Seules les colonnes épinglées à gauche sont importables')
        columns.append(dict(column=index, position=visible, width=width, pinned=fixed in ('Left','1'),
                            group=int(values.get('GroupIndex','-1')), sort=values.get('SortOrder','None'),
                            sort_index=int(values.get('SortIndex','-1'))))
    if not columns or len({c['column'] for c in columns}) != len(columns):
        raise ValueError('Disposition sans colonnes reconnues ou avec doublons')
    for node in root.iter('property'):
        if node.attrib.get('name') in ('ActiveFilterString','FilterString') and (node.text or '').strip():
            raise ValueError('Ce layout contient un filtre : importez son expression séparément pour vérifier sa traduction')
        if node.attrib.get('name') in ('FormatRules','FormatConditions') and (list(node) or node.attrib.get('value','0') != '0'):
            raise ValueError('Les règles de couleur de ce layout ne sont pas compatibles ; utilisez des règles Fireblade')
    return columns
