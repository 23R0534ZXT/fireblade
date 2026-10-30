"""Portable named-column views. Never deserialize executable code."""
from pathlib import Path
import json
import os
import tempfile
from fireblade.core.models import View


def write_json(path, payload):
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, delete=False) as out:
            temporary = Path(out.name)
            json.dump(payload, out, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def read_layout(path, headers):
    path = Path(path)
    if path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError("Disposition limitée à 4 Mo")
    payload = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(payload, dict):
        raise ValueError('Disposition invalide')
    if payload.get('format') != 'fireblade-view' or payload.get('version') != 1:
        raise ValueError("Format de disposition inconnu")
    original = payload['headers']
    if original != headers:
        # A raw Qt header state is positional. Never silently apply it to a
        # different schema and thereby filter/colour the wrong forensic field.
        raise ValueError("Les colonnes de cette disposition diffèrent de l’analyse")
    return View.from_json(json.dumps(payload['view']))
