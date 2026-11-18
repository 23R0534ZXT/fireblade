"""What a case has already imported, keyed by the evidence's own digest.

Importing the same export twice is the most ordinary mistake in this job: a
folder is re-selected, a sub-folder is dragged in beside its parent, two copies
of one KAPE output land in the same case. The digest of the source file is the
only identifier an examiner can defend, so the index is built on it.

The index lives beside the collections of one case, never inside a collection,
so a second import can ask what the first already read.
"""
import json
import os
from pathlib import Path


NAME = 'import-index.json'


def path_for(folder):
    return Path(folder) / NAME


def load(folder):
    """digest -> what read it. A damaged index costs duplicates, never an import."""
    target = path_for(folder)
    try:
        data = json.loads(target.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict) or data.get('format') != 'fireblade-import-index':
        return {}
    return {str(key): value for key, value in (data.get('files') or {}).items()
            if isinstance(value, dict)}


def update(folder, records):
    """Merge new records atomically, keeping the first sighting of a digest."""
    target = path_for(folder)
    files = load(folder)
    added = 0
    for digest, record in records.items():
        if not digest or digest in files:
            continue
        files[digest] = record
        added += 1
    if not added and target.is_file():
        return added
    payload = dict(format='fireblade-import-index', version=1, files=files)
    temporary = target.with_name(target.name + '.partial')
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(temporary, target)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise
    return added
