import csv
import pytest
from fireblade.core.engine import Case
from fireblade.core.models import View,Summary,GroupSort
from fireblade.core.tle_layout import read_tle_layout


def record(column,direction,tag):
    value=f'{column},{direction},{tag}'
    return str(len(value.encode('utf-16-le'))//2)+':'+value


def layout_file(tmp_path,state,summaries):
    columns=''.join(f'<property name="Item{i}"><property name="Name">col{name}</property><property name="FieldName">{name}</property><property name="GroupIndex">{i if i<2 else -1}</property><property name="SortOrder">Ascending</property></property>' for i,name in enumerate(['Parent','Child','Value']))
    path=tmp_path/'sort.layout'
    path.write_text(f'<XtraSerializer><property name="Columns">{columns}</property><property name="GroupSummary">{summaries}</property><property name="GroupSummarySortInfoState">{state}</property></XtraSerializer>')
    return path


def summary(kind='Sum',field='Value',tag=''):
    return f'<property name="Item"><property name="SummaryType">{kind}</property><property name="FieldName">{field}</property><property name="Tag">{tag}</property></property>'


def test_summary_sort_levels_match_paged_outline_export_and_persistence(tmp_path):
    path=layout_file(tmp_path,record('colParent','Descending','#0')+record('colChild','Ascending','child-total'),summary()+summary(tag='child-total'))
    source=tmp_path/'s.csv';source.write_text('Parent,Child,Value\nA,a,10\nA,b,2\nB,a,8\nB,b,7\n')
    case=Case(tmp_path/'s.timeline')
    try:
        case.import_csv(source);view=read_tle_layout(path,case.headers).view;case.validate_view(view)
        assert [r[0] for r in case.page(view)]==['B','A']
        assert [r[0] for r in case.page(view,('B',))]==['b','a']
        assert View.from_json(view.to_json())==view
        from fireblade.core.outline import outline_page
        expanded=View.from_json(view.to_json());expanded.expand_all=True
        groups=[(r['path'],r['values'][0]) for r in outline_page(case,expanded) if r['group']]
        assert [path for path,_ in groups]==[('B',),('B','b'),('B','a'),('A',),('A','b'),('A','a')]
        out=tmp_path/'export.csv';case.export(out,view,grouped=True)
        with out.open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.reader(stream))
        assert [row[:2] for row in rows[1:]]==[['B','b'],['B','a'],['A','b'],['A','a']]
    finally:case.close()


def test_count_without_field_preserves_original_summary_index_and_tags(tmp_path):
    path=layout_file(tmp_path,record('colParent','Descending','#0')+record('colChild','Descending','#1'),summary('Count','')+summary())
    view=read_tle_layout(path,['Parent','Child','Value']).view
    assert [(key.kind,key.summary) for key in view.group_sorts[:2]]==[('count',0),('summary',0)]
    assert view.summaries==[Summary(2,'sum','number')]


def test_utf16_lengths_and_tag_with_commas_are_preserved(tmp_path):
    tag='total,évidence 🚀'
    path=layout_file(tmp_path,record('colParent','Ascending',tag),summary(tag=tag))
    assert read_tle_layout(path,['Parent','Child','Value']).view.group_sorts[0]==GroupSort(0,'summary',0,False)


@pytest.mark.parametrize('state',['garbage','-1:abc','999:short','3:abc','0:','12:broken','29:colParent,Unknown,#0'])
def test_malformed_state_is_rejected_instead_of_silently_changing_sort(tmp_path,state):
    with pytest.raises(ValueError):read_tle_layout(layout_file(tmp_path,state,summary()),['Parent','Child','Value'])


def test_missing_summary_tag_and_duplicate_tags_are_explicit_errors(tmp_path):
    for summaries,state in [(summary(),record('colParent','Ascending','#3')),(summary(),record('colParent','Ascending','missing')),(summary(tag='same')+summary(tag='same'),record('colParent','Ascending','same'))]:
        with pytest.raises(ValueError):read_tle_layout(layout_file(tmp_path,state,summaries),['Parent','Child','Value'])


def test_multiple_summary_keys_for_one_level_have_stable_priority(tmp_path):
    state=record('colParent','Descending','#0')+record('colParent','Descending','#1')
    path=layout_file(tmp_path,state,summary()+summary('Count'))
    source=tmp_path/'s.csv';source.write_text('Parent,Child,Value\nA,x,10\nB,x,6\nB,y,4\n')
    case=Case(tmp_path/'s.timeline')
    try:
        case.import_csv(source);view=read_tle_layout(path,case.headers).view
        assert [row[0] for row in case.page(view)]==['B','A']
    finally:case.close()


def test_tag_whitespace_and_disabled_summary_sort_are_preserved(tmp_path):
    tag=' leading and trailing '
    path=layout_file(tmp_path,record('colParent','Ascending',tag)+record('colChild','None','#0'),summary(tag=tag))
    view=read_tle_layout(path,['Parent','Child','Value']).view
    assert view.group_sorts[0]==GroupSort(0,'summary',0,False)
    assert [key.kind for key in view.group_sorts if key.column==1]==['value']
