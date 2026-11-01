"""Exercise the real helper, not a mock: reflection, UTF-8, import and UDF."""
import hashlib
import os
from pathlib import Path
import tempfile
from fireblade.core.engine import Case
from fireblade.core.models import View,Filter,FilterGroup
from fireblade.core.tle_plugins import inspect_plugin,import_plugin,register_functions


def verify(host,fixture):
    previous=os.environ.get('FIREBLADE_PLUGIN_HOST');previous_storage=os.environ.get('LOCALAPPDATA');os.environ['FIREBLADE_PLUGIN_HOST']=str(host)
    try:
        readers=inspect_plugin(fixture);assert any(r['type']=='FixtureReader' for r in readers)
        with tempfile.TemporaryDirectory(prefix='Fireblade plugin été ') as folder:
            root=Path(folder)
            os.environ['LOCALAPPDATA']=str(root/'user')
            import shutil
            from fireblade.core.reader_detection import reader_directories,detect_reader
            readers_dir=reader_directories()[0];readers_dir.mkdir(parents=True)
            installed=readers_dir/Path(fixture).name;shutil.copy2(fixture,installed)
            fresh=root/'never-selected.csv';fresh.write_text('Text,Identifier\névidence,0001\n',encoding='utf-8')
            assert detect_reader(fresh)==(installed,'FixtureReader')
            # Persisted descriptors must also recognize a different source path.
            second=root/'second.csv';second.write_bytes(fresh.read_bytes())
            assert detect_reader(second)==(installed,'FixtureReader')
            source=root/'source.txt';source.write_text('évidence\n0001',encoding='utf-8',newline='');digest=hashlib.sha256(source.read_bytes()).hexdigest()
            case=Case(root/'case.timeline')
            try:
                import_plugin(case,source,fixture,'FixtureReader')
                rows=case.page(View());assert rows[0][1:3]==('évidence\n0001','0001')
                assert case.info['sha256']==digest and case.info['path']==str(source.resolve())
                assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
                register_functions(case,fixture)
                for expression in ("PluginNumber('FixtureDouble', 21) = 42", "PluginText('FixtureEcho', 'évidence') = 'évidence'", "PluginText('FixtureEcho', Null) Is Null", "FixtureTypes([Time],[LargeId]) = True", "[Details.Name] = 'évidence' And [Details.Children].Sum([Amount]) = 10"):
                    view=View(expression=FilterGroup('and',[Filter(0,'expression',expression)]));assert case.count(view)==1
                import threading
                from fireblade.core.errors import OperationCancelled
                timer=threading.Timer(.15,case.interrupt);timer.start()
                try:
                    try:case.count(View(expression=FilterGroup('and',[Filter(0,'expression',"FixturePause() = 'done'")])) )
                    except OperationCancelled:pass
                    else:raise AssertionError('Plugin query was not cancelled')
                finally:timer.cancel();timer.join()
                assert case.count(View())==1
                register_functions(case,fixture)
                assert case.count(View(expression=FilterGroup('and',[Filter(0,'expression',"FixtureDouble(21)=42")])))==1
                imported_path=case.path
            finally:case.close()
            reopened=Case(imported_path)
            try:
                assert reopened.count(View(expression=FilterGroup('and',[Filter(0,'expression',"FixtureDouble(21)=42")])))==1
            finally:reopened.close()
        return dict(status='passed',checks=['automatic header detection without source binding','cached reader detection for a second source','plugin inspection','typed import','source provenance','exact numeric UDF','Unicode UDF','NULL UDF','UDF cancellation','explicit reload after cancellation','automatic restore on reopen'])
    finally:
        if previous_storage is None:os.environ.pop('LOCALAPPDATA',None)
        else:os.environ['LOCALAPPDATA']=previous_storage
        if previous is None:os.environ.pop('FIREBLADE_PLUGIN_HOST',None)
        else:os.environ['FIREBLADE_PLUGIN_HOST']=previous
