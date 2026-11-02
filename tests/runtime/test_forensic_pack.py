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
