"""Persistent investigation catalogue. Listing cases never opens an analysis."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import uuid

from fireblade.core.layout import write_json
from fireblade.core.sessions import write_session

ENVIRONMENTS = {'unspecified': 'Non précisé', 'windows': 'Windows', 'linux': 'Linux', 'mixed': 'Mixte'}
STATUSES = {'open': 'En cours', 'closed': 'Terminé', 'archived': 'Archivé'}


def now():
    return datetime.now(timezone.utc).isoformat()


class InvestigationLibrary:
    def __init__(self, root):
        self.root = Path(root).resolve()

    def folder(self, identifier):
        if not isinstance(identifier, str) or not re.fullmatch(r'[0-9a-f]{32}', identifier):
            raise ValueError('Identifiant de case invalide')
        folder = self.root/identifier
        if folder.is_symlink():
            raise ValueError('Le dossier du case est un lien')
        return folder

    def read(self, identifier):
        path = self.folder(identifier)/'case.json'
        if path.stat().st_size > 256*1024:
            raise ValueError('Fiche de case limitée à 256 Ko')
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or data.get('format') != 'fireblade-case' or data.get('version') != 1 or data.get('id') != identifier:
            raise ValueError('Fiche de case invalide')
        self.validate(data)
        return data

    @staticmethod
    def validate(data):
        name, description = data.get('name'), data.get('description')
        if not isinstance(name, str) or not name.strip() or len(name)>120 or any(c in name for c in '\0\r\n'):
            raise ValueError('Nom de case : 1 à 120 caractères, sur une ligne')
        if not isinstance(description, str) or len(description)>4000 or '\0' in description:
            raise ValueError('Description limitée à 4000 caractères')
        if data.get('environment') not in ENVIRONMENTS or data.get('status') not in STATUSES:
            raise ValueError('Type ou statut de case invalide')
        session = data.get('session')
        if session is not None and (not isinstance(session, str) or not re.fullmatch(r'session-[0-9a-f]{32}\.fireblade-session', session)):
            raise ValueError('Référence de session invalide')
        if type(data.get('analysis_count')) is not int or not 0 <= data['analysis_count'] <= 1000:
            raise ValueError('Nombre d’analyses invalide')
        if (session is None) != (data['analysis_count']==0):
            raise ValueError('Session et nombre d’analyses incohérents')
        for field in ('created', 'updated', 'last_opened'):
            value = data.get(field)
            if value is None and field == 'last_opened':continue
            if not isinstance(value,str) or len(value)>50:
                raise ValueError('Date du case invalide')
            datetime.fromisoformat(value)
        if not isinstance(data.get('revision'),str) or not re.fullmatch(r'[0-9a-f]{32}',data['revision']):
            raise ValueError('Révision du case invalide')
        collections = data.get('collections')
        if not isinstance(collections,list) or len(collections)>1000:
            raise ValueError('Liste des collectes invalide')
        for entry in collections:
            if not isinstance(entry,dict) or not isinstance(entry.get('path'),str) or not entry['path'] or len(entry['path'])>32768 or not isinstance(entry.get('name'),str) or len(entry['name'])>256:
                raise ValueError('Référence de collecte invalide')
        active = data.get('active_collection')
        if active is not None and active not in [item['path'] for item in collections]:
            raise ValueError('Collecte active absente du case')
        if len(json.dumps(data,ensure_ascii=False,indent=2).encode('utf-8'))>256*1024:
            raise ValueError('Fiche de case limitée à 256 Ko')

    def list(self):
        if not self.root.exists():return [], []
        cases, errors = [], []
        for folder in self.root.iterdir():
            if not re.fullmatch(r'[0-9a-f]{32}',folder.name):continue
            try:cases.append(self.read(folder.name))
            except (OSError,ValueError,TypeError,KeyError) as exc:errors.append(f'{folder.name} : {exc}')
        cases.sort(key=lambda item:(item['updated'],item['id']),reverse=True)
        return cases, errors

    @contextmanager
    def lock(self, identifier, _active=False):
        # OS locks are released after a crash; the small lock file may remain.
        path = self.folder(identifier)/('case.active.lock' if _active else 'case.lock')
        if path.is_symlink():raise ValueError('Le verrou du case est un lien')
        with path.open('a+b') as stream:
            if stream.tell()==0:stream.write(b'0');stream.flush()
            stream.seek(0)
            try:
                if os.name=='nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError as exc:
                message='Ce case est déjà ouvert dans une autre fenêtre.' if _active else 'Ce case est en cours d’enregistrement dans une autre fenêtre.'
                raise ValueError(message) from exc
            try:yield
            finally:
                stream.seek(0)
                if os.name=='nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(),fcntl.LOCK_UN)

    def lease(self, identifier):
        return self.lock(identifier,_active=True)

    def create(self, name, description='', environment='unspecified', status='open'):
        identifier = uuid.uuid4().hex
        stamp = now()
        data = dict(format='fireblade-case',version=1,id=identifier,name=name.strip() if isinstance(name,str) else name,description=description,
                    environment=environment,status=status,created=stamp,updated=stamp,last_opened=None,
                    session=None,analysis_count=0,collections=[],active_collection=None,revision=uuid.uuid4().hex)
        self.validate(data)
        folder = self.folder(identifier)
        folder.mkdir(parents=True)
        try:write_json(folder/'case.json',data)
        except BaseException:
            folder.rmdir()
            raise
        return data

    def update(self, identifier, expected_revision=None, **fields):
        if set(fields)-{'name','description','environment','status','last_opened'}:
            raise ValueError('Champs de case non modifiables')
        with self.lock(identifier):
            data = self.read(identifier)
            self.check_revision(data,expected_revision)
            data.update(fields,updated=now(),revision=uuid.uuid4().hex)
            self.validate(data)
            write_json(self.folder(identifier)/'case.json',data)
        return data

    @staticmethod
    def check_revision(data, expected):
        if expected is not None and data['revision'] != expected:
            raise ValueError('Ce case a été modifié ailleurs. Rouvrez-le avant de l’enregistrer.')

    def session_path(self, data):
        return self.folder(data['id'])/data['session'] if data['session'] else None

    def save(self, identifier, snapshots, active, collections, active_collection, expected_revision):
        if len(snapshots)>1000 or (snapshots and (type(active) is not int or not 0 <= active < len(snapshots))) or (not snapshots and active != -1):
            raise ValueError('Session ou onglet actif invalide')
        with self.lock(identifier):
            data = self.read(identifier)
            self.check_revision(data,expected_revision)
            folder = self.folder(identifier)
            session = None
            if snapshots:
                session = folder/('session-'+uuid.uuid4().hex+'.fireblade-session')
                write_session(session,snapshots,active)
                if session.stat().st_size>4*1024*1024:
                    session.unlink()
                    raise ValueError('Session limitée à 4 Mo')
            previous = data['session']
            data.update(session=session.name if session else None,analysis_count=len(snapshots),
                        collections=collections,active_collection=active_collection,updated=now(),revision=uuid.uuid4().hex)
            try:
                self.validate(data)
                write_json(folder/'case.json',data)
            except BaseException:
                if session:session.unlink(missing_ok=True)
                raise
            # Keep the previous valid snapshot; prune only generated session files.
            for old in folder.glob('session-*.fireblade-session'):
                if old.name not in (data['session'],previous):
                    try:old.unlink()
                    except OSError:pass
            return data
