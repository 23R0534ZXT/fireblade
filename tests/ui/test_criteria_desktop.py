import csv
import json
import time
import pytest
from PySide6.QtWidgets import QApplication
from fireblade.ui.app import Window
from fireblade.core.models import View,FormatRule,Filter,FilterGroup
from fireblade.core.filter_text import parse_filter
from fireblade.validation.windows_check import accept_import_when_ready


def settle(app,w):
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        app.processEvents()
        if not w.jobs and not w.pool.activeThreadCount() and (not w.model or not w.model.jobs):return
        time.sleep(.005)
    pytest.fail('Background operations did not finish')


def test_real_import_dialog_waits_for_metadata_then_advanced_filters_and_coloring_work(qt_application,tmp_path,monkeypatch):
    source=tmp_path/'nested.csv'
    with source.open('w',newline='') as stream:
        out=csv.writer(stream);out.writerow(['Name','Limit','Items']);out.writerow(['alice',10,json.dumps([{'Amount':3},{'Amount':12}])]);out.writerow(['bob',20,'[]'])
    from fireblade.core import reader_detection
    detect=reader_detection.detect_reader
    def delayed(path):time.sleep(.04);return detect(path)
    monkeypatch.setattr(reader_detection,'detect_reader',delayed)
    w=Window();errors=[];w.error=errors.append
    try:
        accept_import_when_ready(qt_application,tmp_path/'nested.timeline',errors)
        w.import_file(source);settle(qt_application,w)
        assert w.case is not None and not errors
        criterion='[Items][[Amount]>[^.Limit]].Count()=1 And InRange(Limit,10m,20m)'
        rule=FormatRule(FilterGroup('and',[Filter(0,'expression',criterion)]),background='#ff0000')
        w.set_view(View(format_rules=[rule],expression=parse_filter(criterion,w.case.headers)));settle(qt_application,w)
        assert w.case.count(w.view)==1 and w.model.rowCount()==1
        from PySide6.QtCore import Qt
        assert w.model.index(0,1).data(Qt.BackgroundRole).name()=='#ff0000'
        assert not errors
    finally:settle(qt_application,w);w.close()
