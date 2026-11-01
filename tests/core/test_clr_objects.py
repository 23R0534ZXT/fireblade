import os
from pathlib import Path
import threading
import pytest
from fireblade.core.engine import Case
from fireblade.core.models import View
from fireblade.core.filter_text import parse_filter
from fireblade.core.tle_plugins import import_plugin,register_functions

HOST=os.environ.get('FIREBLADE_PLUGIN_HOST')
FIXTURE=os.environ.get('FIREBLADE_PLUGIN_FIXTURE')
pytestmark=pytest.mark.skipif(not HOST or not FIXTURE,reason='Real .NET helper and fixture required')


def count(case,text):return case.count(View(expression=parse_filter(text,case.headers)))


def imported(tmp_path):
    source=tmp_path/'original.txt';source.write_text('original evidence',encoding='utf-8')
    case=Case(tmp_path/'case.timeline');import_plugin(case,source,FIXTURE,'FixtureReader');register_functions(case,FIXTURE)
    return case,source


def test_native_instances_collections_private_state_identity_and_nested_results(tmp_path):
    case,source=imported(tmp_path);before=source.read_bytes()
    try:
        assert case._plugin_object_session is None
        assert count(case,"FixtureDouble(21)=42")==1
        assert case._plugin_object_session is None  # Scalar path remains lightweight.
        for expression in [
            "FixtureSameObject([Details],[Details])=True",
            "FixtureSecret([Details])=37",
            "FixtureChildren([Details.Children])=True",
            "FixtureSameObject(FixturePass([Details]),[Details])=True",
            "FixtureSecret(FixtureMake())=73",
            "FixturePass([Details.Name])='évidence'",
            "FixturePass([Details.Missing]) Is Null",
            "FixtureChildAmount(JsonValue([Details], '$.Children[0]'))=3",
            "FixtureChildAmount([Details.SingleChild].Single())=3",
        ]:assert count(case,expression)==1,expression
        assert source.read_bytes()==before
        assert case._plugin_object_session.reader_loaded
        assert not case._plugin_object_session.handles
        process=case._plugin_object_session.session.process
    finally:case.close()
    assert process.poll() is not None


def test_derived_columns_and_reopening_restore_native_arguments_lazily(tmp_path):
    case,source=imported(tmp_path);path=case.path
    try:
        case.add_derived_columns([dict(name='Secret',operation='expression',expression='FixtureSecret([Details])')])
        assert case.page(View())[0][-1]=='37.0000000000'
    finally:case.close()
    case=Case(path)
    try:
        assert case._plugin_object_session is None
        assert case.page(View())[0][-1]=='37.0000000000' and case._plugin_object_session.reader_loaded
    finally:case.close()


def test_nested_object_results_do_not_require_a_reader_or_accumulate_handles(tmp_path):
    source=tmp_path/'native.csv';source.write_text('Number\n'+''.join(str(i)+'\n' for i in range(6000)))
    case=Case(tmp_path/'native.timeline')
    try:
        case.import_csv(source);register_functions(case,FIXTURE)
        assert count(case,'FixtureSecret(FixtureMake())=73')==6000
        assert not case._plugin_object_session.reader_loaded and not case._plugin_object_session.handles
    finally:case.close()


def test_changed_source_is_rejected_before_reader_graph_is_reloaded(tmp_path):
    case,source=imported(tmp_path)
    try:
        source.write_text('modified evidence')
        with pytest.raises(Exception,match='modifi'):count(case,'FixtureSecret([Details])=37')
        assert case._plugin_object_session is None
        assert count(case,'FixtureDouble(21)=42')==1
    finally:case.close()


def test_cancellation_kills_object_host_and_allows_a_fresh_graph(tmp_path):
    from fireblade.core.errors import OperationCancelled
    case,source=imported(tmp_path)
    try:
        assert count(case,'FixtureSecret([Details])=37')==1
        process=case._plugin_object_session.session.process
        timer=threading.Timer(.15,case.interrupt);timer.start()
        try:
            with pytest.raises(OperationCancelled):count(case,'FixturePauseObject([Details])=True')
        finally:timer.cancel();timer.join()
        assert process.poll() is not None and case._plugin_object_session is None
        assert count(case,'FixtureSecret([Details])=37')==1
    finally:case.close()


def test_foreign_handle_is_rejected_without_deserializing_objects(tmp_path):
    case,source=imported(tmp_path)
    try:
        function=case._plugin_functions['fixturesecret']
        with pytest.raises(ValueError,match='étrangère'):
            function.evaluate('FixtureSecret',[{'$fb_type':'clr_handle','value':'foreign-handle'}])
    finally:case.close()


def test_cross_dll_function_receives_same_reader_type_and_function_result(tmp_path):
    other=Path(FIXTURE).with_name('Fireblade.PluginFunctionsFixture.dll')
    if not other.is_file():pytest.skip('Build the second function fixture first')
    case,source=imported(tmp_path)
    try:
        register_functions(case,other)
        assert count(case,'FixtureOtherSecret([Details])=37')==1
        assert count(case,'FixtureOtherSecret(FixtureMake())=73')==1
        assert count(case,'FixtureSecret(FixturePass([Details]))=37')==1
    finally:case.close()


def test_modified_reader_dll_cannot_start_native_object_graph(tmp_path):
    import shutil
    other=Path(FIXTURE).with_name('Fireblade.PluginFunctionsFixture.dll')
    if not other.is_file():pytest.skip('Build the second function fixture first')
    dll=tmp_path/'reader.dll';shutil.copy2(FIXTURE,dll)
    source=tmp_path/'source.txt';source.write_text('evidence')
    case=Case(tmp_path/'changed.timeline')
    try:
        import_plugin(case,source,dll,'FixtureReader');register_functions(case,other)
        with dll.open('ab') as stream:stream.write(b'modified')
        with pytest.raises(Exception,match='modifi'):count(case,'FixtureOtherSecret([Details])=37')
        assert case._plugin_object_session is None
    finally:case.close()


def test_copied_analysis_cannot_reload_reader_without_local_approval(tmp_path):
    import shutil
    other=Path(FIXTURE).with_name('Fireblade.PluginFunctionsFixture.dll')
    if not other.is_file():pytest.skip('Build the second function fixture first')
    case,source=imported(tmp_path);original=case.path;case.close()
    copy=tmp_path/'received.timeline';shutil.copy2(original,copy)
    case=Case(copy)
    try:
        assert case.plugin_restore_errors and not case._plugin_functions
        register_functions(case,other)
        with pytest.raises(Exception,match='approuv'):count(case,'FixtureOtherSecret([Details])=37')
        assert case._plugin_object_session is None
        register_functions(case,FIXTURE)
        assert count(case,'FixtureOtherSecret([Details])=37')==1
    finally:case.close()


def test_parallel_native_calls_share_one_object_process(tmp_path,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from fireblade.core.clr_objects import ObjectSession,evaluate
    created=[];initialize=ObjectSession.__init__
    def track(self,*args):
        initialize(self,*args);created.append(self.session.process.pid)
    monkeypatch.setattr(ObjectSession,'__init__',track)
    case,source=imported(tmp_path)
    try:
        args=[{'$fb_type':'clr_column','row':1,'column':'Details'}]
        with ThreadPoolExecutor(max_workers=8) as pool:
            assert list(pool.map(lambda _:evaluate(case,'FixtureSecret',args),range(16)))==['37']*16
        assert len(created)==1
    finally:case.close()


def test_criteria_typed_literals_keep_native_clr_operand_types(tmp_path):
    case,source=imported(tmp_path)
    try:
        assert count(case,"FixtureLiteralTypes('z'c,{513724e5-17b7-4ec6-abc4-0eae12c72c1f},1s,2b,3m,4f,5d,#!2026-01-01!#,#!12:34:56.1234567!#)=True")==1
        assert case._plugin_object_session is None
    finally:case.close()


def test_dateonly_timeonly_reader_fields_keep_precision_in_criteria(tmp_path):
    source=tmp_path/'temporal.txt';source.write_text('evidence')
    case=Case(tmp_path/'temporal.timeline')
    try:
        import_plugin(case,source,FIXTURE,'FixtureTemporalReader')
        assert case.page(View())[0][1:]==('2026-01-02','12:34:56.1234567')
        assert count(case,'[Day]=#!2026-01-02!# And [Clock]=#!12:34:56.1234567!#')==1
        assert count(case,'GetHour([Clock])=12 And GetTimeOfDay([Clock])=452961234567')==1
    finally:case.close()


def test_nondeterministic_reader_cannot_supply_a_different_graph_for_saved_rows(tmp_path):
    source=tmp_path/'source.txt';source.write_text('unchanged evidence')
    case=Case(tmp_path/'volatile.timeline')
    try:
        import_plugin(case,source,FIXTURE,'FixtureVolatileReader')
        assert len(case.info['plugin']['converted_sha256'])==64
        register_functions(case,FIXTURE)
        original=case.page(View())[0]
        with pytest.raises(Exception,match='déterministe|reproduit'):
            count(case,'FixtureSecret([Details])=37')
        assert case._plugin_object_session is None
        # Persisted scalar evidence remains usable after rejecting reconstruction.
        assert case.page(View())[0]==original
    finally:case.close()
