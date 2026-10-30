import json

import pytest

from fireblade.core.engine import Case
from fireblade.core.models import View
from fireblade.core.settings import Settings
from fireblade.core.tle_compat import read_tle_session, TleSessionImport, read_tle_columns


def test_tle_session_translates_sources_and_tags_without_changing_sources(tmp_path):
    source=tmp_path/'évidence.csv'
    source.write_text('Type,ID\nMFT,001\nEVTX,9007199254740993\n')
    original=source.read_bytes()
    session=tmp_path/'case.tle_sess'
    session.write_text(json.dumps({'SessionFiles':{'évidence.csv':[2]}}))
    references=read_tle_session(session)
    snapshots=TleSessionImport(references,tmp_path/'Analyses',Settings()).run()
    assert len(snapshots)==1
    case=Case(snapshots[0].path)
    try:
        assert case.bookmarks()=={2:''}
        assert case.page(View())[0][2]=='001'
    finally:case.close()
    assert source.read_bytes()==original


def test_failed_or_cancelled_tle_import_removes_its_new_analyses(tmp_path):
    source=tmp_path/'data.csv';source.write_text('ID\n1\n')
    task=TleSessionImport([(source,[99])],tmp_path/'Analyses',Settings())
    with pytest.raises(ValueError):task.run()
    assert not list((tmp_path/'Analyses').glob('*.timeline'))
    task=TleSessionImport([(source,[])],tmp_path/'Analyses',Settings())
    task.interrupt()
    from fireblade.core.errors import OperationCancelled
    with pytest.raises(OperationCancelled):task.run()
    assert not list((tmp_path/'Analyses').glob('*.timeline'))


def test_devexpress_column_layout_reads_order_width_pinning_group_and_sort(tmp_path):
    path=tmp_path/'test.layout'
    path.write_text('''<XtraSerializer><property name="Columns" iskey="true" value="2">
      <property name="Item1"><property name="FieldName">User</property><property name="VisibleIndex">0</property><property name="Width">180</property><property name="Fixed">Left</property><property name="GroupIndex">0</property></property>
      <property name="Item2"><property name="FieldName">ID</property><property name="VisibleIndex">1</property><property name="SortOrder">Descending</property><property name="SortIndex">0</property></property>
    </property></XtraSerializer>''')
    columns=read_tle_columns(path,['ID','User'])
    assert columns[0]['column']==1 and columns[0]['pinned'] and columns[0]['group']==0
    assert columns[1]['sort']=='Descending'
    path.write_text('<!DOCTYPE x [<!ENTITY x "foo">]><x/>')
    with pytest.raises(ValueError):read_tle_columns(path,['ID','User'])


@pytest.mark.parametrize('payload',[[],None,True,'unexpected'])
def test_non_object_session_and_layout_fail_as_normal_input_errors(tmp_path,payload):
    path=tmp_path/'invalid.json';path.write_text(json.dumps(payload))
    from fireblade.core.layout import read_layout
    with pytest.raises(ValueError):read_tle_session(path)
    with pytest.raises(ValueError):read_layout(path,['ID'])
