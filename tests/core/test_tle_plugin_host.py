import os
from pathlib import Path
import pytest

HOST=os.environ.get('FIREBLADE_PLUGIN_HOST')
FIXTURE=os.environ.get('FIREBLADE_PLUGIN_FIXTURE')
pytestmark=pytest.mark.skipif(not HOST or not FIXTURE,reason='Build the real .NET helper and QA reader first')


def test_real_helper_preserves_source_and_evaluates_custom_functions(tmp_path):
    from fireblade.validation.plugin_checks import verify
    assert verify(Path(HOST),Path(FIXTURE))['status']=='passed'


def test_custom_function_name_and_shared_metadata_roundtrip(tmp_path):
    from fireblade.core.engine import Case
    from fireblade.core.tle_plugins import register_functions
    from fireblade.core.models import View,Filter,FilterGroup,FormatRule
    from fireblade.core.filter_text import parse_filter
    from fireblade.core.rule_store import RuleBook
    source=tmp_path/'s.csv';source.write_text('Number\n21\n22\n')
    case=Case(tmp_path/'s.timeline')
    try:
        case.import_csv(source);register_functions(case,FIXTURE)
        for text in ("FixtureDouble(ToInt([Number]))=42", "Custom('FixtureDouble',21)=42"):
            view=View(expression=parse_filter(text,case.headers));assert case.count(view)==(1 if '[Number]' in text else 2)
        rule=FormatRule(FilterGroup('and',[Filter(0,'expression',"FixtureDouble(ToInt([Number]))=42")]))
        book=RuleBook(case.headers,[rule],case.expression_functions);encoded=book.to_bytes();restored=RuleBook.from_bytes(encoded)
        assert restored.functions==book.functions
        assert restored.adapt(case.headers,{})[0]==[]
        assert restored.adapt(case.headers,case.expression_functions)[0]==[rule]
    finally:case.close()
