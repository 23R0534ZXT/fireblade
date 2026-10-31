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


def test_functions_restore_on_reopen_and_unapproved_copy_never_executes(tmp_path,monkeypatch):
    import shutil
    from fireblade.core.engine import Case
    from fireblade.core.models import View
    from fireblade.core.tle_plugins import register_functions
    from fireblade.core.plugin_registry import location
    source=tmp_path/'s.csv';source.write_text('Number\n21\n');path=tmp_path/'s.timeline'
    case=Case(path)
    try:
        case.import_csv(source);register_functions(case,FIXTURE)
        case.add_derived_columns([dict(name='Double',operation='expression',expression='FixtureDouble(ToInt([Number]))')])
    finally:case.close()
    case=Case(path)
    try:assert case.page(View())[0][-1]=='42.0000000000' and case._plugin_sessions and not case.plugin_restore_errors
    finally:case.close()
    copied=tmp_path/'unapproved.timeline';shutil.copy2(path,copied)
    case=Case(copied)
    try:
        assert not case._plugin_sessions and case.plugin_restore_errors
        register_functions(case,FIXTURE)
        assert case.page(View())[0][-1]=='42.0000000000'
    finally:case.close()


def test_session_automatically_uses_registered_reader(tmp_path):
    import json
    from fireblade.core.engine import Case
    from fireblade.core.tle_plugins import import_plugin
    from fireblade.core.tle_compat import TleSessionImport,read_tle_session
    from fireblade.core.settings import Settings
    from fireblade.core.models import View
    source=tmp_path/'evidence.custom';source.write_text('évidence originale')
    original=source.read_bytes();case=Case(tmp_path/'first.timeline')
    try:import_plugin(case,source,FIXTURE,'FixtureReader')
    finally:case.close()
    session=tmp_path/'s.tle_sess';session.write_text(json.dumps({'SessionFiles':{str(source):[1]}}))
    snapshots=TleSessionImport(read_tle_session(session),tmp_path/'sessions',Settings()).run()
    case=Case(snapshots[0].path)
    try:
        assert case.info['format']=='tle-plugin' and case.page(View())[0][1]=='évidence originale'
        assert case.bookmarks()=={1:''} and source.read_bytes()==original
    finally:case.close()
