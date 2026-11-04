"""Compare file identity, including Windows UNC/drive aliases and hard links."""
import os
import json
from pathlib import Path


def same_file(first, second):
    first,second=Path(first).resolve(),Path(second).resolve()
    if first==second:return True
    try:return os.path.samefile(first,second)
    except (OSError,ValueError):return False


def protected_destination(target, paths):
    return any(same_file(target,path) for path in paths)


def collection_sources(reports=(), directories=()):
    """Original evidence, including inputs behind parser-generated CSV sources."""
    reports = list(reports)
    for directory in dict.fromkeys(str(p) for p in directories):
        path = Path(directory)/'collection.json'
        # Missing collection reports remain coverage diagnostics; they must not
        # prevent rescuing the remaining analyses into a new portable case.
        if not path.exists():continue
        if path.stat().st_size > 32*1024**2:
            raise ValueError('Inventaire trop volumineux pour vérifier la destination de l’export')
        reports.append(json.loads(path.read_text(encoding='utf-8')))
    paths = set()
    for report in reports:
        if not isinstance(report, dict):raise ValueError('Inventaire de collecte invalide')
        disk = report.get('disk', {})
        files = report.get('files', [])
        if not isinstance(disk, dict) or not isinstance(files, list):
            raise ValueError('Inventaire de collecte invalide')
        for value in (report.get('source'), disk.get('source')):
            if isinstance(value, str) and value:paths.add(value)
        for entry in files:
            if not isinstance(entry, dict) or not isinstance(entry.get('companions', {}), dict):
                raise ValueError('Inventaire de collecte invalide')
            if isinstance(entry.get('path'), str):paths.add(entry['path'])
            paths.update(entry.get('companions', {}))
    return paths


def ensure_export_destination(target, *, documents=(), rule_path=None, case_folder=None,
                              reports=(), collection_directories=()):
    """One policy for every user-selected export, including file-identity aliases."""
    target = Path(target).resolve()
    protected = set()
    for document in documents:
        protected.update((document.path, document.source_info['path']))
    if rule_path is not None:protected.add(rule_path)
    sources = collection_sources(reports, collection_directories)
    protected.update(sources)
    for source in sources:
        path = Path(source).resolve()
        if path.is_dir() and target.is_relative_to(path):
            raise ValueError('Choisissez un fichier distinct des sources de collecte')
    if case_folder is not None:
        folder = Path(case_folder).resolve()
        protected.update(folder/name for name in ('case.json','timeline-state.json','coverage-state.json','coverage-last.json',
                                                  'case.lock','case.active.lock'))
        for name in ('History','IOC-hunts'):
            directory = folder/name
            if target.is_relative_to(directory):
                raise ValueError('Choisissez un fichier distinct des sauvegardes du case')
            if directory.exists():protected.update(p for p in directory.rglob('*') if p.is_file())
        protected.update(folder.glob('session-*.fireblade-session'))
        if target.parent == folder and target.name.startswith('session-') and target.suffix == '.fireblade-session':
            raise ValueError('Choisissez un fichier distinct des sessions internes du case')
    if protected_destination(target, protected):
        raise ValueError('Choisissez un fichier distinct des sources, analyses, règles et sauvegardes du case')
