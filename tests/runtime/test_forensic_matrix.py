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
