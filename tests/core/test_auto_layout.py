import json
from pathlib import Path
import pytest

from fireblade.core.auto_layout import candidates,load_auto_layout,local_path,save_auto_layout
from fireblade.core.models import View
from fireblade.runtime.windows_paths import user_directory


XML='''<XtraSerializer><property name="Columns"><property name="Item1"><property name="FieldName">User</property><property name="VisibleIndex">0</property><property name="Width">287</property><property name="Fixed">Right</property></property></property></XtraSerializer>'''
HEADERS=['EventId','Provider','Channel','User']


def named_layout(name, content=XML):
    path=user_directory()/'Layouts'/'Default'/name
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content,encoding='utf-8')
    return path


def test_local_xml_precedes_default_and_deletion_restores_default():
    default=named_layout('EvtxECmd.layout')
    local=named_layout('EvtxECmd.layout.local',XML.replace('287','349'))
    layout,path=load_auto_layout(HEADERS,{})
    assert path==local and layout.columns[0]['width']==349
    local.unlink()
    layout,path=load_auto_layout(HEADERS,{})
    assert path==default and layout.columns[0]['width']==287


def test_saved_format_view_precedes_named_xml_and_does_not_depend_on_source_path():
    named_layout('EvtxECmd.layout.local')
    view=View(groups=[3],right_pinned_columns=[3],search='alice')
    saved=save_auto_layout(HEADERS,{'path':'one.csv'},view)
    layout,path=load_auto_layout(HEADERS,{'path':'two.csv'})
    assert path==saved and layout.view==view and not layout.columns
    assert saved.name.endswith('.layout.local')
    assert local_path(list(reversed(HEADERS)),{})!=saved
    assert local_path(HEADERS+['Extra'],{})!=saved
    saved.unlink()
    assert load_auto_layout(HEADERS,{})[1].name=='EvtxECmd.layout.local'


def test_unknown_csv_does_not_reuse_another_schema():
    save_auto_layout(['User','Path'],{},View(groups=[0]))
    assert load_auto_layout(['Path','User'],{})==(None,None)
    assert load_auto_layout(['User','Other'],{})==(None,None)
    assert load_auto_layout(['User','Path'],{})[0].view.groups==[0]


def test_plugin_reader_name_selects_default():
    path=named_layout('CustomReader.layout.local')
    info={'plugin':{'type':'Company.CustomReader'}}
    assert load_auto_layout(['User'],info)[1]==path
    assert local_path(['User'],info)!=local_path(['User'],{'plugin':{'type':'Other.Reader'}})


def test_plugin_metadata_cannot_escape_layout_directory():
    info={'plugin':{'type':'../../outside'}}
    assert all('..' not in p.parts for p in candidates(['User'],info))


def test_corrupted_or_foreign_native_layout_is_reported():
    path=local_path(HEADERS,{})
    path.parent.mkdir(parents=True);path.write_text('{broken')
    with pytest.raises(ValueError):load_auto_layout(HEADERS,{})
    path.write_text(json.dumps(dict(format='fireblade-view',version=1,headers=['Other'],view={})))
    with pytest.raises(ValueError,match='colonnes'):load_auto_layout(HEADERS,{})


def test_portable_layouts_are_read_but_user_local_override_wins(tmp_path,monkeypatch):
    import sys
    monkeypatch.setattr(sys,'frozen',True,raising=False)
    monkeypatch.setattr(sys,'executable',str(tmp_path/'Fireblade.exe'))
    path=tmp_path/'Layouts'/'Default'/'EvtxECmd.layout.local'
    path.parent.mkdir(parents=True);path.write_text(XML)
    assert load_auto_layout(HEADERS,{})[1]==path
    save_auto_layout(HEADERS,{},View(search='local'))
    assert load_auto_layout(HEADERS,{})[0].view.search=='local'


def test_native_local_layout_accepts_utf8_bom():
    path=save_auto_layout(['User'],{},View(search='évidence'))
    path.write_bytes(b'\xef\xbb\xbf'+path.read_bytes())
    assert load_auto_layout(['User'],{})[0].view.search=='évidence'


def test_generic_csv_named_default_is_available():
    path=named_layout('GenericCsv.layout')
    assert load_auto_layout(['User'],{})[1]==path
