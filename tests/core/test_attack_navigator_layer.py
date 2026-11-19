"""The ATT&CK Navigator layer: the techniques a case saw, in the format MITRE reads.

The layer is what an analyst hands to the graph tool everyone already has open. It must
carry technique identifiers and nothing invented: errors, hosts, tactics from the findings.
"""
import json

from fireblade.core.attack_graph import build, navigator_layer, tactic_slug
from fireblade.core.findings import Group
from datetime import datetime, timezone


def group(title, host, tactics, techniques, level='high'):
    return Group(key=title+'|'+host, title=title, level=level, host=host, channel='Security',
                 event_ids=('4104',), tactics=tactics, techniques=techniques, rule_id='r1',
                 rule_file='f.yml', start=datetime(2026, 11, 10, 9, tzinfo=timezone.utc),
                 end=datetime(2026, 11, 10, 9, 5, tzinfo=timezone.utc), count=2)


def sample_graph():
    return build([
        group('Encoded PowerShell', 'SRV01', 'Execution', 'T1059.001 PowerShell'),
        group('Encoded PowerShell', 'PC-COMPTA', 'Execution', 'T1059.001 PowerShell'),
        group('Service creation', 'SRV01', 'Persistence', 'T1543.003 Windows Service'),
    ])


def test_the_layer_holds_every_technique_with_its_hosts():
    layer = navigator_layer(sample_graph(), name='Fireblade — cas test', case='cas test')
    assert layer['domain'] == 'enterprise-attack'
    assert layer['versions']['layer'] and layer['versions']['attack']
    by_id = {item['techniqueID']: item for item in layer['techniques']}
    assert set(by_id) == {'T1059.001', 'T1543.003'}
    assert by_id['T1059.001']['score'] == 40          # two hosts, twenty each
    assert by_id['T1543.003']['score'] == 20
    assert 'SRV01' in by_id['T1059.001']['metadata'][0]['value']
    assert 'PC-COMPTA' in by_id['T1059.001']['comment']


def test_the_tactic_is_written_the_way_the_navigator_spells_it():
    layer = navigator_layer(sample_graph())
    by_id = {item['techniqueID']: item for item in layer['techniques']}
    assert by_id['T1059.001']['tactic'] == 'execution'
    assert by_id['T1543.003']['tactic'] == 'persistence'
    assert tactic_slug('Command and Control') == 'command-and-control'
    assert tactic_slug('Defense Evasion') == 'defense-evasion'


def test_a_graph_without_techniques_gives_an_empty_layer_not_a_broken_one():
    layer = navigator_layer({'nodes': [], 'edges': []})
    assert layer['techniques'] == []
    assert layer['domain'] == 'enterprise-attack'


def test_the_case_name_travels_in_the_metadata():
    layer = navigator_layer(sample_graph(), case='Affaire Dupont')
    assert {'name': 'Case', 'value': 'Affaire Dupont'} in layer['metadata']


def test_nothing_outside_a_technique_identifier_is_written():
    graph = sample_graph()
    for node in graph['nodes']:
        if node['kind'] == 'technique':
            node['code'] = 'not-a-technique'
    assert navigator_layer(graph)['techniques'] == []


def test_the_layer_is_json_serialisable_without_escaping_surprises():
    text = json.dumps(navigator_layer(sample_graph(), case='cas — test'), ensure_ascii=False)
    assert 'T1059.001' in text and '— test' in text
