"""Exercise the real helper, not a mock: reflection, UTF-8, import and UDF."""
import hashlib
import os
from pathlib import Path
import tempfile
from fireblade.core.engine import Case
from fireblade.core.models import View,Filter,FilterGroup
from fireblade.core.tle_plugins import inspect_plugin,import_plugin,register_functions


def verify(host,fixture):
    previous=os.environ.get('FIREBLADE_PLUGIN_HOST');os.environ['FIREBLADE_PLUGIN_HOST']=str(host)
    try:
        readers=inspect_plugin(fixture);assert any(r['type']=='FixtureReader' for r in readers)
        with tempfile.TemporaryDirectory(prefix='Fireblade plugin été ') as folder:
            root=Path(folder);source=root/'source.txt';source.write_text('évidence\n0001',encoding='utf-8',newline='');digest=hashlib.sha256(source.read_bytes()).hexdigest()
            case=Case(root/'case.timeline')
            try:
                import_plugin(case,source,fixture,'FixtureReader')
                rows=case.page(View());assert rows[0][1:3]==('évidence\n0001','0001')
                assert case.info['sha256']==digest and case.info['path']==str(source.resolve())
                assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
                register_functions(case,fixture)
                for expression in ("PluginNumber('FixtureDouble', 21) = 42", "PluginText('FixtureEcho', 'évidence') = 'évidence'", "PluginText('FixtureEcho', Null) Is Null", "FixtureTypes([Time],[LargeId]) = True"):
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
            finally:case.close()
        return dict(status='passed',checks=['plugin inspection','typed import','source provenance','exact numeric UDF','Unicode UDF','NULL UDF','UDF cancellation','explicit reload after cancellation'])
    finally:
        if previous is None:os.environ.pop('FIREBLADE_PLUGIN_HOST',None)
        else:os.environ['FIREBLADE_PLUGIN_HOST']=previous
