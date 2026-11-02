import csv
import gzip
import json
import os
from pathlib import Path
import subprocess

import pytest

from fireblade.core.collection import identify,sha256,ToolPack


def test_usrclass_and_ntuser_routing_preserves_registry_parser(tmp_path):
    for name in ['UsrClass.dat','NTUSER.DAT','UsrClass-copy.dat','ntuser.hiv']:
        source=tmp_path/name;source.write_bytes(b'regf'+b'\0'*32)
        assert identify(source)==['RECmd','Shellbags']
    source=tmp_path/'SYSTEM';source.write_bytes(b'regf'+b'\0'*32)
    assert identify(source)==['AppCompatCacheParser','RECmd']
    log=tmp_path/'UsrClass.dat.LOG1';log.write_bytes(b'log')
    assert identify(log)==['companion']


def test_shellbags_host_contract_and_mit_library_versions_are_locked():
    root=Path(__file__).parents[2];config=json.loads((root/'config/forensic-toolchain.json').read_text())['shellbags']
    lock=json.loads((root/'src/fireblade/shellbags_host/packages.lock.json').read_text())
    for library,version in config['library_versions'].items():assert lock['dependencies']['net10.0'][library]['resolved']==version
    assert (root/config['project']).is_file()
    assert (root/'src/fireblade/shellbags_host/Program.cs').is_file()


def test_actual_shellbags_host_parses_public_hive_without_modifying_it(tmp_path):
    host=os.environ.get('FIREBLADE_SHELLBAGS_HOST')
    dotnet=os.environ.get('FIREBLADE_DOTNET')
    if not host or not dotnet:pytest.skip('Actual .NET Shellbags host required; frozen Windows acceptance is mandatory')
    fixtures=Path(__file__).parents[1]/'fixtures/browser-artifacts'
    source=tmp_path/'UsrClass.dat';source.write_bytes(gzip.decompress((fixtures/'UsrClass.dat.gz').read_bytes()));before=sha256(source)
    result=subprocess.run([dotnet,host,'-f',str(source),'--csv',str(tmp_path/'results')],capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stdout+result.stderr
    with (tmp_path/'results/Shellbags.csv').open(encoding='utf-8') as stream:rows=list(csv.DictReader(stream))
    assert len(rows)==523 and all(row['Status']=='Parsed' for row in rows)
    assert any('osTriage2' in row['Path'] for row in rows)
    assert all(row['RegistryKey'] and row['ValueName'] and row['RawHex'] for row in rows)
    assert any(row['ShellItemCreated'] for row in rows)
    assert '[WRN]' in result.stdout and sha256(source)==before
    invalid=tmp_path/'invalid.dat';invalid.write_bytes(b'invalid')
    result=subprocess.run([dotnet,host,'-f',str(invalid),'--csv',str(tmp_path/'invalid-results')],capture_output=True,text=True,timeout=20)
    assert result.returncode!=0
