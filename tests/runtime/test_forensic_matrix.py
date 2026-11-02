import json
from pathlib import Path

import pytest

from fireblade.core.collection import PARSERS
from fireblade.validation.forensic_tools import verify_parser_results


def test_pinned_fixtures_cover_remaining_parsers():
    items = json.loads((Path(__file__).parents[2]/'config/forensic-qa-fixtures.json').read_text())
    # Existing qualification includes EVTX and SYSTEM (AppCompatCacheParser).
    assert {item['tool'] for item in items} | {'EvtxECmd', 'AppCompatCacheParser'} == set(PARSERS)
    for item in items:
        assert len(item['sha256']) == 64
        assert item['url'].startswith('https://')
        assert '/' not in item['name'] and '\\' not in item['name']


def test_missing_or_empty_parser_never_qualifies():
    with pytest.raises(AssertionError, match='sans résultat non vide'):
        verify_parser_results({'files': []})
    with pytest.raises(AssertionError, match='Parsing non validé'):
        verify_parser_results({'files': [{'runs': [{'tool': 'SrumECmd', 'status': 'no_output'}]}]})


def test_system_hive_fixture_preserves_transaction_log_companions():
    items=json.loads((Path(__file__).parents[2]/'config/forensic-qa-fixtures.json').read_text())
    registry={item['name'] for item in items if item['tool']=='RECmd'}
    assert {'SYSTEM','SYSTEM.LOG1','SYSTEM.LOG2'} <= registry


def test_parser_display_keeps_other_workspace_tabs_unchanged(qt_application,tmp_path):
    import time
    from fireblade.core.engine import Case
    from fireblade.core.models import View
    from fireblade.ui.app import Window
    from fireblade.validation.forensic_tools import parser_result_display
    paths=[]
    for name in ['original','parser-one','parser-two']:
        source=tmp_path/(name+'.csv');source.write_text('Name\n'+name+'\n')
        case=Case(tmp_path/(name+'.timeline'))
        try:case.import_csv(source);paths.append((case.path,case.page(View())))
        finally:case.close()
    window=Window();errors=[];window.error=errors.append
    try:
        window.load_case(paths[0][0]);deadline=time.monotonic()+10
        while window.jobs or window.pool.activeThreadCount() or window.model.jobs:
            qt_application.processEvents();time.sleep(.005)
            assert time.monotonic()<deadline
        with parser_result_display(qt_application,window.settings) as display:
            for path,expected in paths[1:]:display(path,expected)
            assert window.case.path==paths[0][0]
            assert len(window.documents)==window.tabs.count()==1
        assert window.case.path==paths[0][0]
        assert len(window.documents)==window.tabs.count()==1
        assert not errors
    finally:window.close()
