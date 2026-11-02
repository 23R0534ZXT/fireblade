import json
from pathlib import Path
import re
import zipfile

import pytest
from fireblade.core.collection import PARSERS
from scripts.windows.build_forensic_tools import unpack


def test_toolchain_lock_matches_runtime_adapters_and_pins_sources():
    root=Path(__file__).resolve().parents[2]
    lock=json.loads((root/'config/forensic-toolchain.json').read_text())
    assert {tool['name'] for tool in lock['parsers']} == set(PARSERS)
    for tool in lock['parsers']:
        assert tool['repository'].startswith('https://github.com/EricZimmerman/')
        assert re.fullmatch('[0-9a-f]{40}',tool['commit'])
        assert tool['project']==tool['name']+'/'+tool['name']+'.csproj'
    assert re.fullmatch('[0-9a-f]{40}',lock['registry_plugins']['commit'])
    assert lock['registry_plugins']['repository']=='https://github.com/EricZimmerman/RegistryPlugins.git'
    assert lock['hayabusa']['version']=='4.3.1'
    for key in ('sha256','source_sha256'):
        assert re.fullmatch('[0-9a-f]{64}',lock['hayabusa'][key])


def test_engine_archive_cannot_escape_staging_directory(tmp_path):
    archive=tmp_path/'bad.zip'
    with zipfile.ZipFile(archive,'w') as stream:
        stream.writestr('../outside.exe','unexpected')
    with pytest.raises(ValueError):unpack(archive,tmp_path/'unpacked')
    assert not (tmp_path/'outside.exe').exists()


def test_evtx_fixture_uses_pinned_raw_content_and_checks_digest(monkeypatch):
    import hashlib
    import io
    from scripts.windows.build_forensic_tools import load_evtx_fixture
    root=Path(__file__).parents[2]
    spec=json.loads((root/'config/forensic-toolchain.json').read_text())['evtx_fixture']
    assert spec['url'].startswith('https://raw.githubusercontent.com/Yamato-Security/hayabusa-sample-evtx/')
    assert re.search(r'/[0-9a-f]{40}/',spec['url']) and len(spec['sha256'])==64
    calls=[]
    data=b'public pinned fixture bytes'
    def download(url,timeout):calls.append(url);return io.BytesIO(data)
    monkeypatch.setattr('scripts.windows.build_forensic_tools.urllib.request.urlopen',download)
    assert load_evtx_fixture(dict(url=spec['url'],sha256=hashlib.sha256(data).hexdigest()))==data
    with pytest.raises(ValueError,match='EVTX de qualification incorrect'):load_evtx_fixture(spec)
    assert calls==[spec['url'],spec['url']]
