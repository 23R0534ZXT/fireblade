import pytest
from scripts.update_release_readme import promote


def release():
    return dict(draft=False,tag_name='v0.2.1',body='Commit : abc\nSHA-256 de Fireblade.exe : def',
                html_url='https://example/release',assets=[dict(name='Fireblade.exe',digest='sha256:def',browser_download_url='https://example/Fireblade.exe')])


def test_published_binary_is_linked_with_qualification():
    text='> Download the Windows x64 executable from [GitHub Releases](url).\n'
    result=promote(text,release(),'0.2.1','def','abc','https://example/run')
    assert 'Download Fireblade 0.2.1' in result and 'https://example/run' in result


@pytest.mark.parametrize('field,value',[('draft',True),('tag_name','v0.2.0'),('body','wrong'),('assets',[])])
def test_unverified_release_cannot_be_promoted(field,value):
    data=release();data[field]=value
    with pytest.raises(ValueError):promote('README',data,'0.2.1','def','abc','run')
