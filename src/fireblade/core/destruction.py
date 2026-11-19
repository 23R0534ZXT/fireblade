"""Irreversible destruction of collected evidence, and the record of it.

An incident-response engagement ends with evidence that must not leave the premises.
This module overwrites each file with the selected multi-pass scheme, verifies the
result by reading the file back, then removes it — and returns a record that the
certificate is built from.

What it does **not** claim: overwriting a file through the operating system rewrites
the logical blocks the filesystem hands back. On flash storage with wear levelling,
on a copy-on-write filesystem or on a journaling device, other physical copies of the
same bytes may survive. The certificate says so in as many words; a claim of physical
sanitisation needs the medium destroyed, not a program.

The schemes are the ones an analyst asks for by name:

``dod3``  0x00, 0xFF, random          (DoD 5220.22-M, three passes)
``dod7``  0x00, 0xFF, random, 0x00, 0xFF, random, 0x00   (seven passes)

The final pass is verified: the file is read back, its content must equal what was
written and its SHA-256 is recorded next to the one taken before the first pass.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import uuid

METHODS = {
    'dod3': dict(label='DoD 5220.22-M — 3 passes', passes=('zero', 'one', 'random')),
    'dod7': dict(label='DoD 5220.22-M — 7 passes', passes=('zero', 'one', 'random', 'zero', 'one', 'random', 'zero')),
}
CHUNK = 4 * 1024 * 1024
MAX_FILES = 5000

LIMITATIONS = ('This certificate records the overwrite and removal performed by Fireblade on the '
               'files listed below. Overwriting through the operating system rewrites the logical '
               'blocks reported by the filesystem; on flash storage with wear levelling, on '
               'copy-on-write filesystems and on journaling devices, other physical copies of the '
               'same bytes may persist. Physical sanitisation of a medium therefore requires its '
               'destruction or the sanitisation procedure of its manufacturer; this document is '
               'not a NIST SP 800-88 certification.')


def stamp():
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path, progress=None):
    digest = hashlib.sha256()
    done = 0
    with open(path, 'rb') as stream:
        while block := stream.read(CHUNK):
            digest.update(block)
            done += len(block)
            if progress:
                progress(done)
    return digest.hexdigest()


def plan(paths, root, limit=None):
    """Validate what is about to be destroyed, and fingerprint it first.

    ``root`` is the case folder: nothing outside it can be listed, which is what keeps
    a mistyped path from reaching the analyst's collection source or a system file.
    A directory, a symbolic link or a hard-linked file is refused with the reason,
    because in each case "the file" is not a single unambiguous object.
    """
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError('The case folder does not exist')
    entries, seen = [], set()
    for value in paths:
        ceiling = limit or MAX_FILES
        if len(entries) >= ceiling:
            raise ValueError(f'At most {ceiling} files can be destroyed in one operation')
        path = Path(value)
        if path.is_symlink():
            raise ValueError(f'{path} is a symbolic link; links are never followed')
        try:
            resolved = path.resolve(strict=True)
        except OSError as exc:
            raise ValueError(f'{path} cannot be read: {exc}') from exc
        if resolved != root and root not in resolved.parents:
            raise ValueError(f'{resolved} is outside the case folder; only evidence stored in the case can be destroyed')
        if resolved.is_dir():
            raise ValueError(f'{resolved} is a folder; list its files explicitly')
        if not resolved.is_file():
            raise ValueError(f'{resolved} is not a regular file')
        if resolved in seen:
            continue
        seen.add(resolved)
        status = resolved.stat()
        if status.st_nlink and status.st_nlink > 1:
            raise ValueError(f'{resolved} has {status.st_nlink} hard links; overwriting it would affect every link')
        if status.st_size < 0:
            raise ValueError(f'{resolved} has an invalid size')
        entries.append(dict(path=str(resolved),
                            relative=resolved.relative_to(root).as_posix(),
                            size=status.st_size,
                            sha256_before=sha256_file(resolved)))
    if not entries:
        raise ValueError('No file was selected for destruction')
    return entries


def _unit(pattern):
    return b'\x00' if pattern == 'zero' else b'\xff'


def _write_pass(stream, pattern, size, tick):
    """One full overwrite; returns the digest of what was actually written."""
    stream.seek(0)
    digest = hashlib.sha256()
    written = 0
    if pattern == 'random':
        while written < size:
            block = os.urandom(min(CHUNK, size - written))
            stream.write(block)
            digest.update(block)
            written += len(block)
            tick(written)
    else:
        unit = _unit(pattern)
        while written < size:
            block = unit * min(CHUNK, size - written)
            stream.write(block)
            digest.update(block)
            written += len(block)
            tick(written)
    stream.flush()
    os.fsync(stream.fileno())
    return digest.hexdigest()


def _verify(stream, size, expected_digest, pattern, tick):
    """Read the file back: same digest as the final pass, and the pattern when it has one."""
    stream.seek(0)
    digest = hashlib.sha256()
    unit = _unit(pattern) if pattern != 'random' else None
    read = 0
    while read < size:
        block = stream.read(min(CHUNK, size - read))
        if not block:
            break
        digest.update(block)
        read += len(block)
        if unit is not None and block != unit * len(block):
            return False, digest.hexdigest()
        tick(read)
    return read == size and digest.hexdigest() == expected_digest, digest.hexdigest()


def _tick(progress, base, span, path=None):
    """A per-bite callback; the file being overwritten rides along for the interface."""
    if progress is None:
        return lambda done: None
    return lambda done: progress(base + done, span, path)


def destroy(entries, method, *, operator='', witness='', reason='', progress=None, cancel=lambda: False):
    """Overwrite, verify and remove each planned file; return the certificate record.

    Cancellation is honoured between files only: once a file's first pass has begun,
    its whole scheme runs, so no file is left in a state whose remaining passes are
    unknown. A failure on one file does not stop the others; it is recorded.
    """
    if method not in METHODS:
        raise ValueError('Unknown destruction method')
    for field_name, value in (('operator', operator), ('witness', witness)):
        if not isinstance(value, str) or len(value) > 200 or '\0' in value:
            raise ValueError(f'{field_name} must be text of at most 200 characters')
    if not isinstance(reason, str) or len(reason) > 4000 or '\0' in reason:
        raise ValueError('reason must be text of at most 4000 characters')
    scheme = METHODS[method]['passes']
    per_byte = len(scheme) + 1  # every pass, then the verification read
    total = sum(entry['size'] for entry in entries) * per_byte
    record = dict(id=uuid.uuid4().hex, method=method, label=METHODS[method]['label'],
                  passes=len(scheme), operator=operator.strip(), witness=witness.strip(),
                  reason=reason.strip(), started=stamp(), finished=None, status='complete',
                  files=[], bytes=sum(entry['size'] for entry in entries),
                  limitations=LIMITATIONS, attachments=[])
    base = 0
    span = total or 1
    for entry in entries:
        if cancel():
            record['status'] = 'partial'
            record['files'].append(dict(entry, passes_done=0, sha256_after=None, verified=False,
                                        deleted=False, state='cancelled', error=None,
                                        started=None, finished=stamp()))
            continue
        item = dict(entry, passes_done=0, sha256_after=None, verified=False, deleted=False,
                    state='pending', error=None, started=stamp(), finished=None)
        path = Path(entry['path'])
        try:
            _make_writable(path)
            with open(path, 'r+b', buffering=0) as stream:
                written_digest = None
                for index, pattern in enumerate(scheme, 1):
                    written_digest = _write_pass(stream, pattern, entry['size'],
                                                 _tick(progress, base + entry['size'] * (index - 1),
                                                       span, entry['path']))
                    item['passes_done'] = index
                verified, digest = _verify(stream, entry['size'], written_digest, scheme[-1],
                                           _tick(progress, base + entry['size'] * len(scheme),
                                                 span, entry['path']))
                item['verified'], item['sha256_after'] = verified, digest
                stream.truncate(0)
                stream.flush()
                os.fsync(stream.fileno())
            base += entry['size'] * per_byte
            if progress:
                progress(base, span, entry['path'])
            if not item['verified']:
                item['state'] = 'failed'
                item['error'] = 'The final pass could not be verified; the file was left in place.'
            else:
                path.unlink()
                item['deleted'] = True
                item['state'] = 'destroyed'
        except PermissionError as exc:
            base += entry['size'] * per_byte
            item.update(state='failed', error='Write access refused: ' + str(exc))
        except OSError as exc:
            base += entry['size'] * per_byte
            item.update(state='failed', error=str(exc))
        item['finished'] = stamp()
        if item['state'] == 'failed':
            record['status'] = 'partial'
        record['files'].append(item)
    record['finished'] = stamp()
    return record


def _make_writable(path):
    """A read-only evidence file is the normal case; clear the flag before writing."""
    try:
        mode = path.stat().st_mode
        if os.name == 'nt':
            os.chmod(path, 0o666 if mode & 0o200 == 0 else mode)
        elif mode & 0o200 == 0:
            os.chmod(path, mode | 0o200)
    except OSError:
        pass


def store_record(case_folder, record):
    """Write the full record under ``<case>/destruction/`` and return its path."""
    from fireblade.core.case_workspace import data_folder
    folder = data_folder(case_folder) / 'destruction'
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / (record['id'] + '.json')
    from fireblade.core.layout import write_json
    write_json(target, record)
    return target


def load_records(case_folder):
    from fireblade.core.case_workspace import data_folder
    folder = data_folder(case_folder) / 'destruction'
    records = []
    if not folder.is_dir() or folder.is_symlink():
        return records
    for path in sorted(folder.glob('*.json')):
        try:
            if path.is_symlink() or path.stat().st_size > 16 * 1024 * 1024:
                continue
            records.append(json.loads(path.read_text(encoding='utf-8')))
        except (OSError, ValueError):
            continue
    return records
