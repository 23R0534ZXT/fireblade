import ast

import pytest

from scripts.windows.version_info import version_tuple,write_version_file


def test_version_resource_contains_matching_numeric_and_text_versions(tmp_path):
    path=write_version_file(tmp_path/'windows'/'version-info.txt','0.1.1')
    tree=ast.parse(path.read_text(encoding='utf-8'))
    fixed=next(n for n in ast.walk(tree) if isinstance(n,ast.Call) and getattr(n.func,'id','')=='FixedFileInfo')
    arguments={n.arg:ast.literal_eval(n.value) for n in fixed.keywords}
    assert arguments['filevers']==arguments['prodvers']==(0,1,1,0)
    assert arguments['flags']==2
    strings={ast.literal_eval(n.args[0]):ast.literal_eval(n.args[1]) for n in ast.walk(tree)
             if isinstance(n,ast.Call) and getattr(n.func,'id','')=='StringStruct'}
    assert strings['FileVersion']==strings['ProductVersion']=='0.1.1'
    assert strings['OriginalFilename']=='Fireblade.exe' and strings['ProductName']=='Fireblade'


@pytest.mark.parametrize('value',['0.1','v0.1.1','0.1.-1','0.1.1-beta','65536.1.1'])
def test_invalid_windows_resource_versions_are_refused(value):
    with pytest.raises(ValueError):version_tuple(value)
