"""Verified portable case archives. No executable plugins are transported."""
import base64
import copy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import zipfile
import re
from contextlib import nullcontext

import duckdb

from fireblade.core.engine import Case
from fireblade.core.errors import OperationCancelled, job_cancelled
from fireblade.core.models import AnalysisSnapshot, View
from fireblade.core.paths import protected_destination

MAX_FILES = 50_000
MAX_BYTES = 64 * 1024**3
MAX_MANIFEST = 16 * 1024**2


def check_cancelled():
    if job_cancelled():
        raise OperationCancelled()


def safe_member(value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value or '\0' in value:
        raise ValueError('Chemin d’archive invalide')
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ('', '.', '..') for part in value.split('/')):
        raise ValueError('Chemin d’archive dangereux')
    if any(part.rstrip(' .') != part or any(ord(c)<32 or c in '<>"|?*' for c in part) or
           re.fullmatch(r'(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?',part) for part in path.parts):
        raise ValueError('Chemin d’archive incompatible avec Windows')
    return str(path)


def relocate(value, mapping, key=None):
    """Only rewrite known filesystem references, never imported evidence rows."""
    if key in ('view','headers','filters','notes'):return copy.deepcopy(value)
    if isinstance(value, dict):
        return {(mapping.get(name,name) if key=='columns' else name): relocate(item,mapping,name)
                for name,item in value.items()}
    if isinstance(value, list):
        if key in ('headers','view','filters','notes'):return copy.deepcopy(value)
        return [relocate(item,mapping,key) for item in value]
    if isinstance(value, str) and key in ('path','source','output','analysis','csv','root','file','directory',
                                         'database','session','context','alert_analysis','source_analysis','documents','sources'):
        if value in mapping:
            return mapping[value]
        for old, new in sorted(mapping.items(), key=lambda pair: len(pair[0]), reverse=True):
            if value.startswith(old + '/') or value.startswith(old + '\\'):
                return new + '/' + value[len(old) + 1:].replace('\\', '/')
    return value


def export_package(library, data, documents, active, target, *, include_sources=False,
                   active_case=None, settings=None):
    target = Path(target).resolve()
    protected = [Path(doc.path) for doc in documents] + [Path(doc.source_info['path']) for doc in documents]
    protected.append(library.folder(data['id']) / 'case.json')
    if data['session']:protected.append(library.session_path(data))
    if protected_destination(target, protected):
        raise ValueError('L’archive ne peut pas remplacer une analyse ou une source')
    for entry in data['collections']:
        folder = Path(entry['path']).resolve()
        if target.is_relative_to(folder):
            raise ValueError('Enregistrez l’archive hors du dossier de collecte')
    hunt_root = library.folder(data['id']) / 'IOC-hunts'
    if target.is_relative_to(hunt_root.resolve()):raise ValueError('Enregistrez l’archive hors du dossier des chasses IOC')
    mapping, files, missing = {}, [], []
    temporary = None
    total_bytes = 0
    def add(archive, source, member, expected=None):
        nonlocal total_bytes
        source = Path(source)
        if source.is_symlink():
            raise ValueError('Un fichier à transporter est un lien : ' + str(source))
        member = safe_member(member)
        before = source.stat()
        if len(files) >= MAX_FILES or total_bytes + before.st_size > MAX_BYTES:
            raise ValueError('Archive limitée à 50000 fichiers et 64 Gio')
        sha = hashlib.sha256()
        with source.open('rb') as incoming, archive.open(member, 'w', force_zip64=True) as outgoing:
            while block := incoming.read(1024 * 1024):
                check_cancelled(); sha.update(block); outgoing.write(block)
        after = source.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError('Un fichier a changé pendant la sauvegarde : ' + str(source))
        if expected and sha.hexdigest() != expected:
            raise ValueError('Empreinte source différente de celle de l’import : ' + str(source))
        files.append(dict(path=member, size=before.st_size, sha256=sha.hexdigest()))
        total_bytes += before.st_size
        mapping[str(source.resolve())] = member
        return member
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, suffix='.partial', delete=False) as stream:
            temporary = Path(stream.name)
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as archive:
            packed = []
            for number, document in enumerate(documents):
                check_cancelled()
                own = active_case is None or str(active_case.path) != document.path
                case = Case(document.path, settings=settings) if own else active_case
                try:
                    with case.operation():
                        if case.info != document.source_info:
                            raise ValueError('Analyse remplacée : ' + document.path)
                        case.db.execute('CHECKPOINT')
                        member = add(archive, case.path, f'analyses/{number:04}.timeline')
                    packed.append(dict(database=member, source=copy.deepcopy(case.info),
                                       view=json.loads(document.view.to_json()),
                                       header=base64.b64encode(document.header_state).decode('ascii')))
                finally:
                    if own:case.close()
                source = Path(document.source_info['path'])
                if include_sources and source.is_file():
                    if str(source.resolve()) not in mapping:
                        add(archive, source, f'sources/{number:04}{source.suffix.lower()}', document.source_info.get('sha256'))
                else:
                    missing.append(str(source))
            collections = []
            for number, entry in enumerate(data['collections']):
                folder = Path(entry['path']).resolve()
                if not folder.is_dir() or folder.is_symlink() or not (folder/'collection.json').is_file():
                    missing.append(str(folder));continue
                base = f'collections/{number:04}'
                mapping[str(folder)] = base
                collections.append(dict(path=base, name=entry['name']))
                for directory, dirs, names in os.walk(folder, followlinks=False):
                    check_cancelled()
                    missing.extend(str(Path(directory)/d) for d in dirs if (Path(directory)/d).is_symlink())
                    dirs[:] = [d for d in dirs if not (Path(directory)/d).is_symlink() and not d.endswith('.tmp')]
                    for name in names:
                        path = Path(directory)/name
                        if path.is_symlink():missing.append(str(path));continue
                        if path.is_symlink() or name.lower().endswith(('.wal', '.partial', '.lock', '.dll', '.exe', '.so', '.dylib', '.pdb')):
                            continue
                        if str(path.resolve()) in mapping:
                            continue
                        if path.suffix.lower()=='.timeline':
                            connection=duckdb.connect(str(path))
                            try:connection.execute('CHECKPOINT')
                            finally:connection.close()
                        if (name=='collection.json' or name.endswith('.fireblade-session')) and path.stat().st_size>MAX_MANIFEST:
                            raise ValueError('Références de collecte trop volumineuses pour le transport (16 Mio maximum)')
                        add(archive, path, base + '/' + path.relative_to(folder).as_posix())
            from fireblade.core.ioc_results import discover_hunts,HuntStore
            saved_hunts,hunt_errors=discover_hunts(hunt_root)
            if hunt_errors:raise ValueError('Chasse IOC illisible : '+' ; '.join(hunt_errors))
            for saved in saved_hunts:
                check_cancelled()
                path=Path(saved['path'])
                if saved.get('status') not in ('complete','partial'):
                    missing.append(str(path));continue
                store=HuntStore(path)
                try:
                    for source in store.sources():
                        reference=Path(source['path'])
                        if str(reference.resolve()) not in mapping:missing.append(str(reference))
                    add(archive,path,'IOC-hunts/'+path.parent.name+'/results.sqlite')
                finally:store.close()
            state = library.folder(data['id']) / 'timeline-state.json'
            if state.is_file():add(archive, state, 'timeline-state.json')
            by_member={item['path']:item for item in files}
            for document in documents:
                member=mapping.get(str(Path(document.source_info['path']).resolve()))
                if member and document.source_info.get('sha256') and by_member[member]['sha256']!=document.source_info['sha256']:
                    raise ValueError('Empreinte source différente de celle de l’import : '+document.source_info['path'])
            missing=[path for path in missing if Path(path).is_symlink() or str(Path(path).resolve()) not in mapping]
            manifest = dict(format='fireblade-case-package', version=1, case=data, documents=packed,
                            active=active, files=files, collections=collections,
                            relocation=mapping, missing_sources=sorted(set(missing)))
            encoded = json.dumps(manifest, ensure_ascii=False, indent=2).encode('utf-8')
            if len(encoded) > MAX_MANIFEST:raise ValueError('Manifeste limité à 16 Mio')
            archive.writestr('manifest.json', encoded)
        verify_package(temporary)
        check_cancelled()
        os.replace(temporary, target)
        return dict(path=str(target), files=len(files), missing_sources=manifest['missing_sources'])
    finally:
        if temporary:temporary.unlink(missing_ok=True)


def verify_package(source, staging=None):
    """Read back hashes and ZIP CRCs, optionally extracting into private staging."""
    with zipfile.ZipFile(source) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_FILES + 1 or len({i.filename.casefold() for i in infos}) != len(infos):
            raise ValueError('Archive trop grande ou entrées dupliquées')
        for info in infos:
            safe_member(info.filename)
            if stat.S_ISLNK(info.external_attr >> 16) or info.is_dir():
                raise ValueError('Liens et entrées de dossier interdits dans l’archive')
        info = archive.getinfo('manifest.json')
        if info.file_size > MAX_MANIFEST:raise ValueError('Manifeste limité à 16 Mio')
        manifest = json.loads(archive.read(info).decode('utf-8'))
        if manifest.get('format') != 'fireblade-case-package' or manifest.get('version') != 1:
            raise ValueError('Format d’archive de case inconnu')
        files = manifest['files']
        if not isinstance(files, list) or len(files) > MAX_FILES:
            raise ValueError('Liste de fichiers invalide')
        members = {safe_member(item['path']) for item in files}
        if len(members) != len(files) or members != {i.filename for i in infos} - {'manifest.json'}:
            raise ValueError('Fichiers absents, dupliqués ou non déclarés')
        total = 0
        for item in files:
            check_cancelled()
            info = archive.getinfo(item['path'])
            if type(item['size']) is not int or info.file_size != item['size'] or info.file_size < 0:
                raise ValueError('Taille de fichier incohérente')
            total += info.file_size
            if total > MAX_BYTES:raise ValueError('Archive décompressée limitée à 64 Gio')
            if staging is not None:
                path = staging / item['path'];path.parent.mkdir(parents=True, exist_ok=True)
            sha = hashlib.sha256();written = 0
            with archive.open(info) as incoming, (path.open('xb') if staging is not None else nullcontext()) as outgoing:
                while block := incoming.read(1024 * 1024):
                    check_cancelled();written += len(block)
                    if written > item['size']:raise ValueError('Fichier décompressé trop grand')
                    sha.update(block)
                    if outgoing is not None:outgoing.write(block)
            if written != item['size'] or sha.hexdigest() != item['sha256']:
                raise ValueError('Échec de vérification SHA-256 : ' + item['path'])
    return manifest


def import_package(library, source):
    """Verify every byte before publishing a new case; never overwrite a case."""
    source = Path(source)
    library.root.mkdir(parents=True, exist_ok=True)
    created = None
    try:
        with tempfile.TemporaryDirectory(prefix='.import-', dir=library.root) as scratch:
            staging = Path(scratch)
            manifest = verify_package(source, staging)
            files = manifest['files'];members = {item['path'] for item in files}
            documents = manifest['documents']
            if not isinstance(documents, list) or len(documents) > 1000:
                raise ValueError('Nombre d’analyses invalide')
            if len({doc['database'] for doc in documents}) != len(documents):
                raise ValueError('Analyses dupliquées dans l’archive')
            if documents and (type(manifest['active']) is not int or not 0 <= manifest['active'] < len(documents)):
                raise ValueError('Onglet actif invalide')
            original = manifest['case']
            created = library.create(original['name'] + ' (import)' if len(original['name']) <= 111 else original['name'],
                                     original['description'], original['environment'], original['status'])
            destination = library.folder(created['id'])
            mapping = {}
            for old, member in manifest['relocation'].items():
                member = safe_member(member)
                if member not in members and not any(m.startswith(member + '/') for m in members):
                    raise ValueError('Référence de déplacement non déclarée')
                mapping[old] = str(destination/member)
            for child in staging.iterdir():shutil.move(str(child), destination/child.name)
            # Rebind each copied database, including inactive collection outputs.
            original_infos = {}
            for path in destination.rglob('*.timeline'):
                connection = duckdb.connect(str(path))
                try:
                    info = json.loads(connection.execute("SELECT value FROM metadata WHERE key='source'").fetchone()[0])
                    original_infos[str(path)] = copy.deepcopy(info)
                    info['path'] = mapping.get(info['path'], info['path'])
                    connection.execute("UPDATE metadata SET value=? WHERE key='source'", [json.dumps(info)])
                finally:connection.close()
            from fireblade.core.ioc_results import HuntStore
            for path in (destination/'IOC-hunts').glob('*/results.sqlite'):
                store=HuntStore(path)
                try:store.rebind(mapping)
                finally:store.close()
            # Workspaces are JSON references; original event values stay untouched.
            for path in (destination/'collections').rglob('*') if (destination/'collections').exists() else []:
                if path.name=='collection.json' or path.suffix=='.fireblade-session':
                    if path.stat().st_size>MAX_MANIFEST:raise ValueError('Références de collecte trop volumineuses')
                    from fireblade.core.layout import write_json
                    original_report=json.loads(path.read_text(encoding='utf-8'))
                    rebound=relocate(original_report,mapping)
                    if path.name=='collection.json':
                        aliases={old:mapping.get(new,new) for old,new in original_report.get('portable_relocation',{}).items()}
                        aliases.update({old:new for old,new in mapping.items() if new.lower().endswith('.timeline')})
                        rebound['portable_relocation']=aliases
                    write_json(path,rebound)
            state = destination/'timeline-state.json'
            if state.exists():
                from fireblade.core.layout import write_json
                write_json(state, relocate(json.loads(state.read_text(encoding='utf-8')), mapping))
            snapshots = []
            for document in documents:
                member = safe_member(document['database'])
                if member not in members or not member.startswith('analyses/'):
                    raise ValueError('Analyse non déclarée')
                path = destination/member
                connection = duckdb.connect(str(path))
                try:
                    info = json.loads(connection.execute("SELECT value FROM metadata WHERE key='source'").fetchone()[0])
                    if original_infos[str(path)] != document['source']:raise ValueError('Métadonnées d’analyse incohérentes')
                finally:connection.close()
                snapshots.append(AnalysisSnapshot(str(path), info, View.from_json(json.dumps(document['view'])),
                                                  base64.b64decode(document['header'], validate=True)))
            collections = [dict(path=str(destination/safe_member(c['path'])), name=c['name']) for c in manifest['collections']]
            for collection in collections:
                for name in ('results','analyses'):(Path(collection['path'])/name).mkdir(parents=True,exist_ok=True)
            active_collection = mapping.get(original['active_collection']) if original['active_collection'] else None
            if active_collection not in [c['path'] for c in collections]:active_collection = None
            check_cancelled()
            from fireblade.core.layout import write_json
            write_json(destination/'package-provenance.json', manifest)
            result = library.save(created['id'], snapshots, manifest['active'] if snapshots else -1,
                                  collections, active_collection, created['revision'])
            return dict(case=result, missing_sources=manifest['missing_sources'], files=len(files))
    except BaseException:
        if created is not None:shutil.rmtree(library.folder(created['id']), ignore_errors=True)
        raise
