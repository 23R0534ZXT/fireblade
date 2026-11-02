import csv
import json
from pathlib import Path
import shutil

import pytest
from fireblade.core.alert_context import build_context
from fireblade.core.collection import Collection,ToolPack
from fireblade.core.engine import Case
from fireblade.core.models import View


@pytest.fixture
def context_collection(tmp_path):
    root=tmp_path/'evidence';root.mkdir()
    output=tmp_path/'work';output.mkdir();(output/'results').mkdir();(output/'analyses').mkdir()
    collection=Collection(root,output,ToolPack(tmp_path/'pack'))
    rows_by_file={
        'System.evtx':[
            ['1','2026-11-02 10:00:00','7001','PC01','System','Before','{"before":true}'],
            ['2','2026-11-02 10:01:00.1234567','104','PC01','System','Log cleared','{"proof":"full value"}'],
            ['3','2026-11-02 10:02:00','7040','PC01','System','Service disabled','after'],
            ['2','2026-11-02 10:01:00','104','PC02','System','Other host','excluded'],
        ],
        'Security.evtx':[
            ['2','2026-11-02 10:01:00.1234567','4624','PC01','Security','Logon','neighbor, not anchor'],
            ['7','2026-11-02 10:03:00','4688','PC01','Security','Process started','process context'],
            ['8','2026-11-02 10:02:00','4624','PC02','Security','Other host','excluded'],
            ['9','2026-11-02 12:00:00','4624','PC01','Security','Outside window','excluded'],
        ],
    }
    for name,rows in rows_by_file.items():
        artifact=root/name;artifact.write_bytes(b'ElfFile\0')
        source=output/'results'/(name+'.csv')
        with source.open('w',newline='',encoding='utf-8') as stream:
            writer=csv.writer(stream);writer.writerow(['EventRecordId','TimeCreated','EventId','Computer','Channel','MapDescription','Payload']);writer.writerows(rows)
        analysis=collection.import_result(source,'EvtxECmd')
        collection.report['files'].append(dict(path=str(artifact),tools=['EvtxECmd'],status='complete',runs=[dict(tool='EvtxECmd',status='complete',outputs=[dict(csv=str(source),analysis=analysis)])]))
    collection.save()
    alert=dict(RuleTitle='Log cleared',RuleID='rule-1',Level='high',RecordID='2',EventID='104',Computer='PC01',
               Timestamp='2026-11-02T10:01:00.1234567Z',Fireblade_EVTX_Source=str(root/'System.evtx'))
    return collection,alert


def context_rows(result):
    case=Case(result['analysis'])
    try:return [dict(zip(case.headers,row[1:])) for row in case.page(View())]
    finally:case.close()


def test_alert_links_to_file_and_record_with_same_host_cross_log_context(context_collection):
    collection,alert=context_collection
    result=build_context(collection,alert,'alerts.timeline',1)
    assert result['references']==1 and result['events']==5 and result['association']=='exact'
    rows=context_rows(result)
    anchors=[r for r in rows if r['Relation à l’alerte']=='Événement de l’alerte']
    assert len(anchors)==1 and anchors[0]['EventId']=='104'
    assert anchors[0]['TimeCreated']=='2026-11-02 10:01:00.1234567'
    assert anchors[0]['Payload']=='{"proof":"full value"}'
    same_id_other_file=next(r for r in rows if r['EventId']=='4624')
    assert same_id_other_file['Relation à l’alerte']=='Proximité temporelle'
    assert {r['Computer'] for r in rows}=={'PC01'}
    assert {r['EventRecordId'] for r in rows}=={'1','2','3','7'}
    assert collection.report['contexts'][-1]['analysis']==result['analysis']


def test_neighbor_cap_keeps_anchor_and_reports_truncation(context_collection):
    collection,alert=context_collection
    result=build_context(collection,alert,'alerts.timeline',1,max_events=2)
    assert result['truncated'] and result['events']==2
    assert any(r['Relation à l’alerte']=='Événement de l’alerte' for r in context_rows(result))


@pytest.mark.parametrize('record', ['999', '999 ¦ 1000'])
def test_unknown_record_is_never_marked_as_matched(context_collection, record):
    collection,alert=context_collection
    alert['RecordID']=record
    result=build_context(collection,alert,'alerts.timeline',1)
    assert result['association']=='unresolved' and result['references']==0
    assert all(r['Relation à l’alerte']=='Proximité temporelle' for r in context_rows(result))
    assert any('non retrouvé' in note for note in result['notes'])


def test_aggregate_references_are_explicit_candidates(context_collection):
    collection,alert=context_collection
    alert.update(Fireblade_EVTX_Source=json.dumps([str(collection.root/'System.evtx'),str(collection.root/'Security.evtx')]),RecordID='1 ¦ 2',EventID='')
    result=build_context(collection,alert,'alerts.timeline',1)
    assert result['association']=='candidate' and result['references']==3
    assert sum(r['Relation à l’alerte']=='Référence candidate (agrégation)' for r in context_rows(result))==3


def test_context_uses_original_evtx_bases_after_artifact_organization(context_collection):
    collection,alert=context_collection
    collection.report['raw_documents']=list(collection.report['documents'])
    collection.report['documents']=[]
    collection.report['organization']='combined'
    result=build_context(collection,alert,'alerts.timeline',1)
    assert result['events']==5 and result['references']==1


def test_context_can_reopen_without_original_raw_files(context_collection):
    collection,alert=context_collection
    shutil.rmtree(collection.root)
    restored=Collection.reopen(collection.output,collection.pack)
    assert build_context(restored,alert,'alerts.timeline',1)['references']==1


def test_untrusted_identifiers_are_bound_not_executed(context_collection):
    collection,alert=context_collection
    alert.update(RecordID="2); DROP TABLE events;--",Computer="PC01' OR 1=1 --")
    result=build_context(collection,alert,'alerts.timeline',1)
    assert result['references']==0 and result['events']==0
    case=Case(collection.report['documents'][0]['path'])
    try:assert case.count(View())==4
    finally:case.close()


def test_missing_time_and_machine_do_not_mix_unrelated_neighbors(context_collection):
    collection,alert=context_collection
    alert.update(RecordID='999',Computer='',Timestamp='invalid')
    result=build_context(collection,alert,'alerts.timeline',1)
    assert result['events']==0 and result['association']=='unresolved'
    assert any('Horodatage' in note for note in result['notes'])
    assert any('Machine inconnue' in note for note in result['notes'])
