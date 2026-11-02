import gzip
import os
from pathlib import Path

import pytest

from fireblade.core.collection import ToolPack
from fireblade.validation.browser_artifacts import verify_browser_artifacts


def test_actual_shellbags_and_webcache_render_and_restore_in_case(qt_application,tmp_path):
    host=os.environ.get('FIREBLADE_SHELLBAGS_HOST');dotnet=os.environ.get('FIREBLADE_DOTNET')
    if not host or not dotnet:pytest.skip('Actual Shellbags host required; frozen Windows acceptance covers this workflow')
    root=tmp_path/'pack';(root/'Shellbags').mkdir(parents=True)
    class LocalPack(ToolPack):
        def command(self,name):
            if name=='Shellbags':return [dotnet,host]
            return super().command(name)
    source=tmp_path/'evidence';source.mkdir()
    fixtures=Path(__file__).parents[1]/'fixtures/browser-artifacts'
    for name in ['UsrClass.dat','WebCacheV01.dat']:(source/name).write_bytes(gzip.decompress((fixtures/(name+'.gz')).read_bytes()))
    report=verify_browser_artifacts(qt_application,tmp_path/'verification',pack=LocalPack(root),evidence=source)
    assert report['records']=={'Shellbags':523,'WebCache':1612}
    assert report['case_and_notes_restored'] and report['analyses']==2
