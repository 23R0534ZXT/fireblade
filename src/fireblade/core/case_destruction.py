"""Destroying a whole case: the evidence, the analyses, the register, and the folder.

Destroying one evidence file and destroying a case are different decisions. A case is
closed when the incident is over: what must go is everything the case holds — the copies of
evidence, the analyses built from them, the tracking, the sessions, the history of the
register — and then the folder itself, so nothing is left to reopen by mistake.

The certificate cannot live inside the case it describes, since that folder is what
disappears: the caller gives a destination outside, and the document is written there before
the folder is removed. A failure on one file does not stop the others; the record says which
files were overwritten, verified and removed, and which were not, and the case folder is only
removed when nothing is left inside it.
"""
from __future__ import annotations

import os
from pathlib import Path

from fireblade.core import destruction as basis
from fireblade.core.destruction_certificate import build as build_certificate
from fireblade.core.destruction_certificate import write as write_certificate

CASE_MARKERS = ('case.json', 'workspace.json', 'collection.json', 'manifest.json')
MAX_CASE_FILES = 200_000


def looks_like_case(folder):
    """A folder is a case when it carries the register, not merely a name."""
    folder = Path(folder)
    if not folder.is_dir():
        return False
    if any((folder/name).is_file() for name in CASE_MARKERS):
        return True
    if (folder/'analyses').is_dir():
        return True
    return any(folder.glob('*.fireblade-session'))


def collect(folder, *, limit=MAX_CASE_FILES):
    """Every regular file under the case folder, in a stable order, with its size."""
    root = Path(folder)
    if root.is_symlink():
        raise ValueError('Le dossier du case est un lien ; il n’est jamais suivi')
    root = root.resolve()
    if not root.is_dir():
        raise ValueError('Le dossier du case n’existe pas')
    if not looks_like_case(root):
        raise ValueError('Ce dossier ne ressemble pas à un case Fireblade ; destruction refusée')
    files, folders, links = [], [], []
    for current, directories, names in os.walk(root, followlinks=False):
        current_path = Path(current)
        folders.append(current_path)
        for name in list(directories):
            candidate = current_path/name
            if candidate.is_symlink():
                links.append(str(candidate.relative_to(root).as_posix()))
                directories.remove(name)
        for name in names:
            path = current_path/name
            if path.is_symlink():
                links.append(str(path.relative_to(root).as_posix()))
                continue
            try:
                size = path.stat().st_size
            except OSError:
                size = 0
            files.append(dict(path=str(path), relative=path.relative_to(root).as_posix(), size=size))
            if len(files) > limit:
                raise ValueError(f'Le case dépasse {limit:,} fichiers ; destruction refusée'.replace(',', ' '))
    return files, folders, links


def destroy_case(folder, method, *, operator='', witness='', reason='', progress=None,
                 cancel=lambda: False, certificate_path, case_name='', case_id=''):
    """Overwrite every file of a case, remove the folders, and write the certificate outside.

    Returns the certificate record. The victim folder is removed only when it is empty, so an
    incomplete destruction keeps what is left and says so instead of pretending.
    """
    progress = progress or (lambda _message: None)
    certificate_path = Path(certificate_path)
    root = Path(folder).resolve()
    if certificate_path.resolve() == root or root in certificate_path.resolve().parents:
        raise ValueError('Le procès-verbal doit être écrit hors du case, puisque le case disparaît')
    files, folders, links = collect(root)
    if not files:
        raise ValueError('Le case ne contient aucun fichier à détruire')
    total = sum(item['size'] for item in files)
    progress(f'Destruction du case : {len(files)} fichier(s), {total/1e6:.1f} Mo')
    entries = basis.plan([item['path'] for item in files], root, limit=MAX_CASE_FILES)

    def report(done, total, path=None):
        # The engine counts bytes; the analyst wants to know which file is going.
        name = Path(path).name if path else ''
        progress(f'Destruction : {done}/{total} · {name}'.rstrip(' ·'))

    record = basis.destroy(entries, method, operator=operator, witness=witness, reason=reason,
                           progress=report, cancel=cancel)
    record['scope'] = 'case'
    record['case_name'] = case_name
    record['case_id'] = case_id
    if links:
        record['skipped_links'] = links[:200]
    failed = [item for item in record['files'] if not item.get('deleted')]
    removed_folders = 0
    if not failed:
        # Deepest first: a folder disappears only once what it held is gone.
        for path in sorted(folders, key=lambda item: len(item.parts), reverse=True):
            try:
                path.rmdir()
                removed_folders += 1
            except OSError:
                if path == root:
                    raise
    record['removed_folders'] = removed_folders
    record['folder_removed'] = not root.exists()
    progress('Procès-verbal : '+str(certificate_path))
    document = build_certificate(record, case_name=case_name, case_id=case_id,
                                 case_folder=None if record['folder_removed'] else root)
    write_certificate(certificate_path, document, pdf=certificate_path.suffix.casefold() == '.pdf')
    record['certificate'] = str(certificate_path)
    return record
