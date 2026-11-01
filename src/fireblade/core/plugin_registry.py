"""User-approved DLLs and source bindings, separate from imported analyses."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
from fireblade.runtime.windows_paths import user_directory


def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def location():return user_directory()/'tle-plugins.json'


def read():
    path=location()
    if not path.exists():return []
    if path.stat().st_size>2*1024**2:raise ValueError('Registre de plugins trop volumineux')
    data=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data,list) or len(data)>256:raise ValueError('Registre de plugins invalide')
    for entry in data:
        if not isinstance(entry,dict) or not isinstance(entry.get('path'),str) or len(entry.get('sha256',''))!=64:raise ValueError('Entrée de plugin invalide')
    return data


def save(entries):
    path=location();path.parent.mkdir(parents=True,exist_ok=True);temporary=None
    try:
        with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=path.parent,delete=False) as f:
            temporary=Path(f.name);json.dump(entries,f,ensure_ascii=False,indent=2)
        if temporary.stat().st_size>2*1024**2:raise ValueError('Registre de plugins trop volumineux')
        os.replace(temporary,path)
    finally:
        if temporary:temporary.unlink(missing_ok=True)


def approve(path,*,analysis=None,source=None,reader=None):
    path=Path(path).resolve();sha=digest(path);entries=read()
    entry=next((e for e in entries if e['path']==str(path)),None)
    if entry is None:
        if len(entries)>=256:raise ValueError('256 DLL enregistrées au maximum')
        entry=dict(path=str(path),sha256=sha,analyses=[],readers=[]);entries.append(entry)
    elif entry['sha256']!=sha:
        entry.update(sha256=sha,analyses=[],readers=[])
        entry.pop('reader_catalog',None)
    if analysis:
        name=str(Path(analysis).resolve())
        if name not in entry.setdefault('analyses',[]):entry['analyses'].append(name)
    if source and reader:
        binding=dict(source=str(Path(source).resolve()),type=reader)
        entry['readers']=[b for b in entry.setdefault('readers',[]) if b['source']!=binding['source']]+[binding]
    save(entries);return sha


def approved_for_analysis(analysis,sha):
    name=str(Path(analysis).resolve())
    for entry in read():
        if name in entry.get('analyses',[]) and entry['sha256']==sha:
            path=Path(entry['path'])
            if not path.is_file() or digest(path)!=sha:raise ValueError('DLL enregistrée absente ou modifiée : '+str(path))
            return path
    raise ValueError('DLL non approuvée sur ce poste pour cette analyse')


def reader_for_source(source):
    name=str(Path(source).resolve())
    found=[]
    for entry in read():
        for binding in entry.get('readers',[]):
            if binding['source']==name:
                path=Path(entry['path'])
                if not path.is_file() or digest(path)!=entry['sha256']:raise ValueError('Lecteur de session absent ou modifié : '+str(path))
                found.append((path,binding['type']))
    if len(found)>1:raise ValueError('Plusieurs lecteurs enregistrés pour la même source')
    return found[0] if found else None


def remember_functions(case,path):
    sha=approve(path,analysis=case.path)
    row=case.db.execute("SELECT value FROM metadata WHERE key='dotnet_functions'").fetchone();items=json.loads(row[0]) if row else []
    session=case._plugin_sessions[-1];names={n.casefold() for n in session.names}
    items=[i for i in items if not names.intersection(i.get('types',{}))]
    items.append(dict(sha256=sha,types={n:session.types.get(n,'text') for n in names}))
    case.db.execute("INSERT OR REPLACE INTO metadata VALUES ('dotnet_functions', ?)",[json.dumps(items)])


def restore_functions(case):
    row=case.db.execute("SELECT value FROM metadata WHERE key='dotnet_functions'").fetchone()
    if not row:return
    items=json.loads(row[0])
    if not isinstance(items,list) or len(items)>256:raise ValueError('Références de fonctions invalides')
    from fireblade.core.tle_plugins import register_functions,ensure_udf
    from fireblade.core.expressions import register_function_metadata
    import re
    for item in items:
        if not isinstance(item,dict) or not isinstance(item.get('sha256'),str) or len(item['sha256'])!=64 or not isinstance(item.get('types'),dict) or len(item['types'])>4096:raise ValueError('Référence de fonctions invalide')
        if any(not isinstance(n,str) or not 1<=len(n)<=128 or '\x00' in n or k not in ('text','number','date','boolean') for n,k in item['types'].items()):raise ValueError('Types de fonctions invalides')
        case._saved_function_types.update(item['types']);register_function_metadata(item['types'])
    ensure_udf(case)
    for item in items:
        try:register_functions(case,approved_for_analysis(case.path,item['sha256']),remember=False)
        except (ValueError,OSError,TimeoutError) as exc:case.plugin_restore_errors.append(str(exc))
