"""Verified cold storage: retain a small catalogue entry and remove generated work."""
import hashlib
import json
from pathlib import Path
import shutil
import uuid

from fireblade.core.case_package import export_package, import_package
from fireblade.core.investigations import now
from fireblade.core.layout import write_json
from fireblade.core.sessions import read_session


def archive_and_release(library, identifier, target, settings=None):
    folder=library.folder(identifier).resolve();target=Path(target).resolve()
    if target.is_relative_to(folder):raise ValueError('Choisissez une archive hors du dossier du case.')
    from fireblade.core.paths import same_file
    records,_ = library.list()
    if any(item.get('storage_archive') and same_file(target,item['storage_archive']['path']) for item in records):
        raise ValueError('Cette destination contient déjà une archive de case à conserver.')
    with library.lease(identifier):
        data=library.read(identifier)
        if data.get('storage_archive'):raise ValueError('Ce case est déjà conservé en archive.')
        # Original acquisition folders must never be removed with generated work.
        for entry in data['collections']:
            report=Path(entry['path'])/'collection.json'
            if report.is_file():
                info=json.loads(report.read_text(encoding='utf-8'))
                if not info.get('disk') and Path(info['source']).resolve().is_relative_to(folder):
                    raise ValueError('Des preuves originales sont dans le case. Déplacez-les avant de libérer son espace.')
        session=library.session_path(data)
        documents,active=read_session(session) if session else ([],0)
        collections=[Path(entry['path']).resolve() for entry in data['collections']]
        for document in documents:
            source=Path(document.source_info['path']).resolve()
            if source.is_relative_to(folder) and not any(source.is_relative_to(p) for p in collections):
                raise ValueError('Une source originale est dans le case. Conservez-la hors du dossier de travail.')
        result=export_package(library,data,documents,active,target,include_sources=True,settings=settings,include_case_files=True,max_bytes=4*1024**4)
        # export_package reads back every SHA-256 and ZIP CRC before publishing.
        with target.open('rb') as stream:archive_hash=hashlib.file_digest(stream,'sha256').hexdigest()
        removed=0
        stub=dict(data,status='archived',session=None,analysis_count=0,collections=[],active_collection=None,
                  revision=uuid.uuid4().hex,updated=now(),storage_archive=dict(path=str(target),sha256=archive_hash,
                  bytes=target.stat().st_size,analyses=data['analysis_count']))
        from fireblade.core.case_package import check_cancelled
        check_cancelled()
        library.validate(stub)
        write_json(folder/'case.json',stub)
        for path in folder.iterdir():
            if path.name in ('case.json','case.active.lock'):continue
            if path.is_symlink():path.unlink();continue
            if path.is_dir():
                removed+=sum(p.stat().st_size for p in path.rglob('*') if p.is_file() and not p.is_symlink())
                shutil.rmtree(path)
            else:removed+=path.stat().st_size;path.unlink()
        return dict(result,removed_bytes=removed,archive_bytes=target.stat().st_size)


def restore_archive(library, identifier):
    data=library.read(identifier);archive=data['storage_archive'];path=Path(archive['path'])
    if not path.is_file() or path.stat().st_size!=archive['bytes']:
        raise ValueError('Archive absente ou taille modifiée.')
    with path.open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=archive['sha256']:
            raise ValueError('L’empreinte de l’archive ne correspond plus.')
    result=import_package(library,path,max_bytes=4*1024**4)
    result['case']=library.update(result['case']['id'],status='open')
    return result
