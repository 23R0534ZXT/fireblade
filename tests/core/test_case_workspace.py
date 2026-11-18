import json

import pytest

from fireblade.core.case_workspace import (add_action, add_entity, add_ioc, add_iocs, collect,
                                           empty, load, remove_action, save, summary, tag_node,
                                           update_action, validate)
from fireblade.core.investigations import InvestigationLibrary


def make_case(tmp_path, name='Client A'):
    library = InvestigationLibrary(tmp_path/'Cases')
    data = library.create(name)
    return library.folder(data['id']), data['id']


def test_a_new_case_has_an_empty_valid_workspace_that_is_not_written(tmp_path):
    folder, _ = make_case(tmp_path)
    data = load(folder)
    validate(data)
    assert data['actions'] == [] and data['iocs'] == [] and data['client']['name'] == ''
    assert not (folder/'workspace.json').exists()


def test_actions_round_trip_and_are_summarised(tmp_path):
    folder, _ = make_case(tmp_path)
    action = add_action(folder, 'Collecter les journaux du serveur', owner='client',
                        status='waiting_client', priority='high', machine='SRV01',
                        due='2026-12-01')
    data = load(folder)
    assert data['actions'][0]['title'] == 'Collecter les journaux du serveur'
    assert data['actions'][0]['owner'] == 'client'
    assert summary(data)['open_actions'] == 1
    update_action(folder, action['id'], status='done')
    data = load(folder)
    assert data['actions'][0]['status'] == 'done' and data['actions'][0]['closed']
    counts = summary(data)
    assert counts['open_actions'] == 0 and counts['actions'] == 1


def test_removing_an_action_and_a_missing_action_fails_loudly(tmp_path):
    folder, _ = make_case(tmp_path)
    action = add_action(folder, 'Isolement du poste')
    remove_action(folder, action['id'])
    assert load(folder)['actions'] == []
    with pytest.raises(ValueError, match='no longer exists'):
        remove_action(folder, action['id'])


def test_a_stale_revision_refuses_to_overwrite(tmp_path):
    folder, _ = make_case(tmp_path)
    data = empty()
    saved = save(folder, data)
    stale = json.loads(json.dumps(saved))
    with pytest.raises(ValueError, match='changed elsewhere'):
        save(folder, stale, expected_revision='0'*32)
    assert load(folder)['revision'] == saved['revision']


def test_indicators_are_normalised_and_duplicates_refused(tmp_path):
    folder, _ = make_case(tmp_path)
    add_ioc(folder, 'EXEMPLE[.]FR', source='rapport client')
    assert load(folder)['iocs'][0]['value'] == 'exemple.fr'
    with pytest.raises(ValueError, match='already tracked'):
        add_ioc(folder, 'exemple.fr')
    with pytest.raises(ValueError):
        add_ioc(folder, 'pas un domaine !!!')


def test_a_large_indicator_list_is_imported_in_one_write(tmp_path):
    import time
    folder, _ = make_case(tmp_path)
    add_ioc(folder, 'exemple.fr')
    values = ['host%d.example.test' % index for index in range(3000)] + ['exemple.fr', 'pas un domaine !!']
    started = time.monotonic()
    result = add_iocs(folder, values)
    elapsed = time.monotonic() - started
    assert result == dict(added=3000, skipped=2), result
    data = load(folder)
    assert len(data['iocs']) == 3001
    assert elapsed < 10, elapsed
    revision = data['revision']
    # A second import of the same list adds nothing and keeps the same revision.
    again = add_iocs(folder, values)
    assert again['added'] == 0 and load(folder)['revision'] == revision


def test_entities_and_graph_tags_survive_a_reload(tmp_path):
    folder, _ = make_case(tmp_path)
    add_entity(folder, 'machine', 'SRV01', hostname='SRV01.corp.local', ip='10.0.0.5', os='Windows')
    add_entity(folder, 'account', 'j.doe')
    node_id = tag_node(folder, 'Persistance', kind='custom', tags=['persistence', 'T1053'])
    data = load(folder)
    assert [item['kind'] for item in data['entities']] == ['machine', 'account']
    node = next(item for item in data['graph']['nodes'] if item['id'] == node_id)
    assert node['tags'] == ['persistence', 'T1053']
    assert summary(data)['entities'] == 2


def test_collect_aggregates_cases_and_reports_an_unreadable_one(tmp_path):
    first, first_id = make_case(tmp_path, 'Client A')
    second, second_id = make_case(tmp_path, 'Client B')
    add_action(first, 'Action A', owner='us')
    add_action(second, 'Action B', owner='client')
    (second/'workspace.json').write_text('{broken', encoding='utf-8')
    board, errors = collect(tmp_path/'Cases')
    assert {item['case'] for item in board} == {first_id, second_id}
    good = next(item for item in board if item['case'] == first_id)
    assert good['workspace']['actions'][0]['title'] == 'Action A'
    assert errors and 'Client B' in errors[0]


def test_invalid_workspace_values_are_refused(tmp_path):
    folder, _ = make_case(tmp_path)
    with pytest.raises(ValueError):
        add_action(folder, 'x', owner='nobody')
    with pytest.raises(ValueError):
        add_action(folder, 'x'*201)
    with pytest.raises(ValueError):
        add_action(folder, 'x', due='not-a-date')
    data = load(folder)
    data['graph']['edges'].append(dict(source='missing', target='also-missing', label=''))
    with pytest.raises(ValueError, match='unknown node'):
        validate(data)
