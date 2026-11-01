from dataclasses import replace
from decimal import Decimal
import csv

import pytest

from fireblade.core.engine import Case
from fireblade.core.models import Filter,Summary,View
from fireblade.core.settings import Settings
from fireblade.core.tle_layout import read_tle_layout


def make_case(tmp_path):
    source=tmp_path/'s.csv';source.write_text('Parent,Child,N\nA,X,2\nA,Y,4\nA,Y,6\nB,X,100\n')
    case=Case(tmp_path/'s.timeline',settings=Settings(page_size=25))
    case.import_csv(source)
    return case


@pytest.mark.parametrize('mode',['expanded','always'])
def test_outline_closes_every_group_after_its_subtree_across_pages(tmp_path,mode):
    case=make_case(tmp_path)
    try:
        view=View(groups=[0,1],group_order='value',group_descending=False,group_footer_mode=mode,
            summaries=[Summary(2,'avg'),Summary(2,'distinct')],total_summaries=[Summary(2,'sum')])
        records=[]
        for offset in range(0,18,3):records+=case.outline_page(view,offset,3)
        assert len(records)==14
        stack=[];footers={};source_ids=[]
        for record in records:
            if record.get('footer'):
                assert stack.pop()==record['path']
                footers[record['path']]=record['values']
            elif record['group']:stack.append(record['path'])
            else:source_ids.append(record['values'][0])
        assert not stack and sorted(source_ids)==[1,2,3,4]
        assert footers[('A',)][2:]==(Decimal(4),3)
        assert footers[('A','Y')][2:]==(Decimal(5),2)
        assert case.total_summary(view)==(4,Decimal(112))
        assert case.db.execute('SELECT count(*),count(DISTINCT position),max(position) FROM __fireblade_outline').fetchone()==(14,14,14)
        # Presentation rows must never be exported as forensic source rows.
        out=tmp_path/'export.csv';case.export(out,view)
        with out.open(encoding='utf-8-sig',newline='') as stream:assert len(list(csv.reader(stream)))==5
        grouped=tmp_path/'groups.csv';case.export(grouped,view,grouped=True)
        with grouped.open(encoding='utf-8-sig',newline='') as stream:assert len(list(csv.reader(stream)))==4
        hidden=replace(view,group_footer_mode='hidden')
        assert not any(record.get('footer') for record in case.outline_page(hidden))
    finally:case.close()


def test_global_totals_use_all_filtered_rows_and_do_not_enter_group_summaries(tmp_path):
    case=make_case(tmp_path)
    try:
        view=View(groups=[0,1],summaries=[Summary(2,'sum')],total_summaries=[Summary(2,'avg'),Summary(0,'rows'),Summary(1,'distinct','text')],filters=[Filter(2,'le','6')])
        assert case.total_summary(view)==(3,Decimal(4),3,2)
        assert len(case.page(view)[0])==3  # group key, count, group sum only
        assert View.from_json(view.to_json())==view
        assert case.total_summary(replace(view,filters=[Filter(2,'gt','1000')]))==(0,None,0,0)
        for invalid in ('sometimes',True,None):
            with pytest.raises(ValueError):case.validate_view(replace(view,group_footer_mode=invalid))
        with pytest.raises(ValueError):case.validate_view(replace(view,total_summaries=[Summary(2,'sum',footer_column=99)]))
    finally:case.close()


def test_xml_import_keeps_total_and_group_definitions_and_styles_separate(tmp_path):
    path=tmp_path/'summary.layout'
    path.write_text('''<XtraSerializer><property name="OptionsView"><property name="GroupFooterShowMode">VisibleAlways</property><property name="ShowFooter">true</property></property>
    <property name="Columns"><property name="Item1"><property name="FieldName">Parent</property><property name="GroupIndex">0</property></property>
    <property name="Item2"><property name="FieldName">Child</property><property name="SummaryItem"><property name="SummaryType">Count</property></property></property>
    <property name="Item3"><property name="FieldName">N</property><property name="Name">amount</property></property></property>
    <property name="GroupSummary"><property name="Item1"><property name="FieldName">N</property><property name="SummaryType">Sum</property><property name="ShowInGroupColumnFooterName">amount</property></property></property>
    <property name="TotalSummary"><property name="Item1"><property name="FieldName">N</property><property name="SummaryType">Average</property></property><property name="Item2"><property name="SummaryType">Count</property></property></property>
    <property name="Appearance"><property name="FooterPanel"><property name="BackColor">Red</property></property><property name="GroupFooter"><property name="BackColor">Blue</property></property></property></XtraSerializer>''')
    view=read_tle_layout(path,['Parent','Child','N']).view
    assert view.group_footer_mode=='always' and view.show_total_footer
    assert view.summaries==[Summary(2,'sum','number',2)]
    assert view.total_summaries==[Summary(2,'avg','number'),Summary(0,'rows','number'),Summary(1,'count','text')]
    assert view.layout_styles['footer_panel']['background']=='#ff0000'
    assert view.layout_styles['group_footer']['background']=='#0000ff'
    assert View.from_json(view.to_json())==view
