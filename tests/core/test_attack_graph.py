from datetime import datetime, timezone
import xml.etree.ElementTree as ElementTree

from fireblade.core.attack_graph import TACTICS, build, layout, tactic_index, tactic_name, to_svg
from fireblade.core.findings import Group


def group(title='Suspicious PowerShell', host='SRV01', tactics='InitialAccess',
          techniques='T1059.001 PowerShell', level='high', start=None):
    return Group(key=title+'|'+host, title=title, level=level, host=host, channel='Security',
                 event_ids=('4104',), tactics=tactics, techniques=techniques, rule_id='r1',
                 rule_file='f.yml', start=start or datetime(2026, 11, 10, 9, tzinfo=timezone.utc),
                 end=start or datetime(2026, 11, 10, 9, 5, tzinfo=timezone.utc), count=3)


def test_tactics_are_recognised_in_hayabusa_writings():
    assert tactic_index('InitialAccess') == 2
    assert tactic_index('TA0002, Execution') == 3
    assert tactic_index('credential-access') == 7
    assert tactic_index('Unknown thing') is None
    assert tactic_name('DefenseEvasion') == 'Defense Evasion'
    assert TACTICS[0] == 'Reconnaissance'


def test_build_links_hosts_techniques_and_stages():
    graph = build([group()])
    kinds = {node['kind'] for node in graph['nodes']}
    assert kinds == {'host', 'technique', 'stage'}
    host = next(node for node in graph['nodes'] if node['kind'] == 'host')
    technique = next(node for node in graph['nodes'] if node['kind'] == 'technique')
    assert host['label'] == 'SRV01' and technique['label'] == 'PowerShell'
    assert technique['code'] == 'T1059.001'
    assert any(edge['source'] == host['id'] and edge['target'] == technique['id'] for edge in graph['edges'])
    assert any(edge['label'] == 'tactic' for edge in graph['edges'])


def test_workspace_tags_survive_a_rebuild():
    workspace = dict(graph=dict(nodes=[dict(id='technique:t1059-001', label='PowerShell',
                                            kind='technique', tags=['persistence', 'à vérifier'])],
                                edges=[]),
                     entities=[dict(id='e'*32, kind='machine', label='Poste de la comptable',
                                    hostname='PC-COMPTA', tags=['chiffré'])],
                     iocs=[dict(id='i'*32, kind='domain', value='exemple.fr', status='confirmed',
                                machine='srv01')])
    graph = build([group()], workspace)
    technique = next(node for node in graph['nodes'] if node['id'] == 'technique:t1059-001')
    assert technique['tags'] == ['persistence', 'à vérifier'] and technique['auto'] is False
    machine = next(node for node in graph['nodes'] if node['label'] == 'Poste de la comptable')
    assert machine['tags'] == ['chiffré']
    ioc = next(node for node in graph['nodes'] if node['kind'] == 'ioc')
    assert any(edge['source'] == ioc['id'] and edge['label'] == 'observed on' for edge in graph['edges'])


def test_layout_is_deterministic_and_ordered_by_the_kill_chain():
    first = layout(build([group(tactics='InitialAccess'), group(title='Lateral', tactics='LateralMovement')]))
    second = layout(build([group(tactics='InitialAccess'), group(title='Lateral', tactics='LateralMovement')]))
    positions = {node['id']: (node['x'], node['y']) for node in first['nodes']}
    assert positions == {node['id']: (node['x'], node['y']) for node in second['nodes']}
    entry = next(node for node in first['nodes'] if node['label'] == 'Initial Access')
    lateral = next(node for node in first['nodes'] if node['label'] == 'Lateral Movement')
    assert entry['x'] < lateral['x']


def test_the_svg_is_well_formed_and_carries_labels_and_tags():
    workspace = dict(graph=dict(nodes=[dict(id='technique:t1059-001', kind='technique',
                                            label='PowerShell', tags=['persistence'])], edges=[]))
    svg = to_svg(build([group()], workspace))
    root = ElementTree.fromstring(svg)
    assert root.tag.endswith('svg')
    text = ''.join(root.itertext())
    assert 'SRV01' in text and 'PowerShell' in text and 'persistence' in text and 'Initial Access' in text


def test_an_empty_graph_says_so_instead_of_drawing_nothing():
    assert 'No node' in to_svg(build([]))


def test_a_declared_machine_does_not_duplicate_the_finding_host():
    workspace = dict(entities=[dict(id='e'*32, kind='machine', label='SRV01', hostname='SRV01',
                                    tags=['critique'])], graph=dict(nodes=[], edges=[]))
    graph = build([group()], workspace)
    hosts = [node for node in graph['nodes'] if node['kind'] == 'host']
    assert len(hosts) == 1, [node['label'] for node in hosts]
    assert hosts[0]['tags'] == ['critique']
