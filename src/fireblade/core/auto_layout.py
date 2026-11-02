"""Per-format local layouts, independent of evidence files and analysis sessions."""
import hashlib
import json
from pathlib import Path
import re
import sys

from fireblade.core.layout import read_layout, write_json
from fireblade.core.profiles import detect_profile
from fireblade.core.tle_layout import TleLayout, read_tle_layout
from fireblade.runtime.windows_paths import user_directory


LIMIT = 4 * 1024 * 1024


def format_identity(headers, info):
    reader = info.get('plugin', {}).get('type')
    profile = detect_profile(headers)
    name = reader or (profile.name if profile else 'CSV')
    # Positional Qt state must only be reused with the exact same ordered schema.
    value = json.dumps([name, headers], ensure_ascii=False).encode('utf-8')
    digest = hashlib.sha256(value).hexdigest()
    label = re.sub(r'[^a-zA-Z0-9_-]', '_', name.rsplit('.', 1)[-1])[:48] or 'CSV'
    return f'{label}--{digest}'


def local_path(headers, info, local_directory=None):
    directory=Path(local_directory) if local_directory is not None else user_directory() / 'Layouts' / 'Local'
    return directory / (format_identity(headers, info) + '.layout.local')


def layout_directories():
    roots = [user_directory() / 'Layouts']
    if getattr(sys, 'frozen', False):
        roots.append(Path(sys.executable).parent / 'Layouts')
    return [directory for root in roots for directory in (root, root / 'Default')]


def candidates(headers, info, local_directory=None):
    yield local_path(headers, info, local_directory)
    reader = info.get('plugin', {}).get('type')
    profile = detect_profile(headers)
    names = [reader, reader.rsplit('.', 1)[-1] if reader else None,
             profile.name if profile else 'GenericCsv']
    names = list(dict.fromkeys(name for name in names if name))
    # Reader names are metadata, never paths supplied by an analysis.
    names = [name for name in names if not any(c in name for c in '/\\:\x00') and name not in ('.', '..')]
    for suffix in ('.layout.local', '.layout'):
        for directory in layout_directories():
            for name in names:
                yield directory / (name + suffix)


def load_auto_layout(headers, info, local_directory=None):
    for path in candidates(headers, info, local_directory):
        if not path.is_file():
            continue
        if path.stat().st_size > LIMIT:
            raise ValueError(f'Disposition automatique trop volumineuse : {path}')
        with path.open('rb') as stream:
            native = stream.read(64).lstrip(b'\xef\xbb\xbf \t\r\n').startswith(b'{')
        if native:
            return TleLayout([], read_layout(path, headers)), path
        return read_tle_layout(path, headers), path
    return None, None


def save_auto_layout(headers, info, view, local_directory=None):
    payload = dict(format='fireblade-view', version=1, headers=headers,
                   view=json.loads(view.to_json()))
    if len(json.dumps(payload, ensure_ascii=False).encode('utf-8')) > LIMIT:
        raise ValueError('Disposition locale limitée à 4 Mo')
    path = local_path(headers, info, local_directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, payload)
    return path
