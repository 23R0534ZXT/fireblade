"""Actual Windows CLR4 reader/function check, using an assembly requiring System.Web."""
import os
from pathlib import Path
import tempfile
from fireblade.core.engine import Case
from fireblade.core.models import View
from fireblade.core.filter_text import parse_filter
from fireblade.core.tle_plugins import inspect_plugin,import_plugin,register_functions,command_for_plugin


def verify(host,legacy,fixture):
    saved={k:os.environ.get(k) for k in ('FIREBLADE_PLUGIN_HOST','FIREBLADE_LEGACY_PLUGIN_HOST')}
    os.environ['FIREBLADE_PLUGIN_HOST']=str(host);os.environ['FIREBLADE_LEGACY_PLUGIN_HOST']=str(legacy)
    try:
        assert Path(command_for_plugin(fixture)[0]).resolve()==Path(legacy).resolve()
        assert any(r['type']=='LegacyReader' for r in inspect_plugin(fixture))
        with tempfile.TemporaryDirectory(prefix='Fireblade CLR4 été ') as folder:
            root=Path(folder);source=root/'source.log';source.write_text('<preuve>',encoding='utf-8')
            case=Case(root/'s.timeline')
            try:
                import_plugin(case,source,fixture,'LegacyReader');assert case.page(View())[0][1]=='&lt;preuve&gt;'
                register_functions(case,fixture)
                assert case.count(View(expression=parse_filter("LegacyEncode('<x>') = '&lt;x&gt;'",case.headers)))==1
                assert case.count(View(expression=parse_filter("LegacyNative([Details]) = 91",case.headers)))==1
            finally:case.close()
            case=Case(root/'s.timeline')
            try:
                assert case.count(View(expression=parse_filter("LegacyEncode('<x>') = '&lt;x&gt;'",case.headers)))==1
                assert case.count(View(expression=parse_filter("LegacyNative([Details]) = 91",case.headers)))==1
            finally:case.close()
        return dict(status='passed',checks=['CLR4 automatic selection','real System.Web dependency','reader','custom function','automatic reopen','native CLR4 complex object'])
    finally:
        for k,v in saved.items():
            if v is None:os.environ.pop(k,None)
            else:os.environ[k]=v
