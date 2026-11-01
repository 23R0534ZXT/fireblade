import copy
import hashlib
import json
import os
from pathlib import Path

import pytest

from fireblade.core.engine import Case
from fireblade.core.errors import OperationCancelled
from fireblade.core.models import AnalysisSnapshot,Filter,View
from fireblade.core.settings import Settings
from fireblade.core.tle_compat import read_tle_session,TleSessionImport
from fireblade.core.tle_session_export import TleSessionExport


def snapshot(case):
    return AnalysisSnapshot(str(case.path),copy.deepcopy(case.info),View(filters=[Filter(0,'eq','hidden')]),b'')


def create(tmp_path,name='données'):
    source=tmp_path/(name+'.csv');source.write_text('User,Value\nalice,001\nbob,2\n',encoding='utf-8')
    case=Case(tmp_path/(name+'.timeline'));case.import_csv(source);case.bookmark_many([2],'une note','replace')
    return case,source


def test_export_active_and_inactive_sources_tags_and_import_roundtrip(tmp_path):
    active,source=create(tmp_path)
    other,second=create(tmp_path,'second');docs=[snapshot(active),snapshot(other)];other.close()
    untouched=hashlib.sha256(Path(docs[1].path).read_bytes()).hexdigest()
    try:
        target=tmp_path/'échange.tle_sess'
        task=TleSessionExport(docs,Settings(),active)
        assert task.run(target)==2
        assert json.loads(target.read_text())=={'SessionFiles':{str(source):[2],str(second):[2]}}
        assert hashlib.sha256(Path(docs[1].path).read_bytes()).hexdigest()==untouched
        assert active.bookmarks()=={2:'une note'}
        refs=read_tle_session(target)
        imported=TleSessionImport(refs,tmp_path/'converted',Settings(),auto_profiles=False).run()
        assert len(imported)==2
        for doc in imported:
            case=Case(doc.path,read_only=True)
            try:
                assert case.bookmarks()=={2:''}
                assert case.page(View())==[(1,'alice','001'),(2,'bob','2')]
            finally:case.close()
    finally:active.close()


@pytest.mark.parametrize('failure',['changed','missing','duplicate','snapshot','missing_analysis'])
def test_invalid_sources_leave_existing_destination_untouched(tmp_path,failure):
    case,source=create(tmp_path);docs=[snapshot(case)];target=tmp_path/'session.tle_sess';target.write_bytes(b'keep previous session')
    try:
        if failure=='changed':source.write_text('User,Value\nalice,001\nbob,3\n')  # same length
        elif failure=='missing':source.unlink()
        elif failure=='duplicate':docs.append(copy.deepcopy(docs[0]))
        elif failure=='snapshot':docs[0].source_info['sha256']='changed'
        elif failure=='missing_analysis':docs[0].path=str(tmp_path/'absent.timeline')
        with pytest.raises(ValueError):TleSessionExport(docs,Settings(),case).run(target)
        assert target.read_bytes()==b'keep previous session'
        assert not list(tmp_path.glob('*.partial'))
    finally:case.close()


def test_no_overwriting_sources_or_database_and_cancel_before_replace(tmp_path,monkeypatch):
    case,source=create(tmp_path)
    try:
        docs=[snapshot(case)];task=TleSessionExport(docs,Settings(),case)
        for path in (case.path,source):
            with pytest.raises(ValueError,match='remplacer'):task.run(path)
        target=tmp_path/'session.tle_sess';target.write_bytes(b'old')
        check=task.check_cancelled
        def cancel_when_partial_exists():
            if list(tmp_path.glob('*.partial')):task.interrupt()
            check()
        monkeypatch.setattr(task,'check_cancelled',cancel_when_partial_exists)
        with pytest.raises(OperationCancelled):task.run(target)
        assert target.read_bytes()==b'old' and not list(tmp_path.glob('*.partial'))
    finally:case.close()


def test_plugin_source_line_mapping_and_ambiguous_partial_tags(tmp_path):
    source=tmp_path/'reader.csv';source.write_text('Name,TLE_SourceLine\nfirst,10\nsecond,20\nthird,20\n')
    case=Case(tmp_path/'plugin.timeline');case.import_csv(source)
    case.info['format']='tle-plugin'
    try:
        case.bookmark_many([2,3],'','mark')
        assert TleSessionExport([snapshot(case)],Settings(),case).run(tmp_path/'s.tle_sess')==1
        assert read_tle_session(tmp_path/'s.tle_sess')==[(source,[20])]
        case.bookmark_many([3],'','remove')
        with pytest.raises(ValueError,match='partagent'):TleSessionExport([snapshot(case)],Settings(),case).run(tmp_path/'bad.tle_sess')
        case.bookmark_many([2],'','remove');case.bookmark_many([1],'','mark')
        with case.operation():case.db.execute("UPDATE events SET c1='1.5' WHERE __row_id=1")
        with pytest.raises(ValueError,match='invalide'):TleSessionExport([snapshot(case)],Settings(),case).run(tmp_path/'bad.tle_sess')
    finally:case.close()


def test_non_first_excel_sheet_is_not_exported_as_first_sheet(tmp_path):
    from openpyxl import Workbook
    source=tmp_path/'workbook.xlsx';workbook=Workbook();workbook.active.title='First';workbook.active.append(['Value']);workbook.active.append(['a'])
    sheet=workbook.create_sheet('Second');sheet.append(['Value']);sheet.append(['b']);workbook.save(source);workbook.close()
    case=Case(tmp_path/'sheet.timeline')
    try:
        case.import_excel(source,'Second')
        with pytest.raises(ValueError,match='première feuille'):TleSessionExport([snapshot(case)],Settings(),case).run(tmp_path/'s.tle_sess')
    finally:case.close()


def test_source_changed_after_verification_does_not_replace_destination(tmp_path,monkeypatch):
    case,source=create(tmp_path);target=tmp_path/'s.tle_sess';target.write_bytes(b'old')
    task=TleSessionExport([snapshot(case)],Settings(),case)
    check=task.check_cancelled
    def change_after_partial():
        if list(tmp_path.glob('*.partial')):source.write_text('User,Value\nchanged,001\nbob,2\n')
        check()
    monkeypatch.setattr(task,'check_cancelled',change_after_partial)
    try:
        with pytest.raises(ValueError,match='pendant'):task.run(target)
        assert target.read_bytes()==b'old' and not list(tmp_path.glob('*.partial'))
    finally:case.close()


@pytest.mark.skipif(os.name=='nt',reason='Creating symbolic links requires optional Windows privileges')
def test_symlink_destination_cannot_overwrite_source(tmp_path):
    case,source=create(tmp_path)
    try:
        alias=tmp_path/'alias.tle_sess';alias.symlink_to(source)
        with pytest.raises(ValueError,match='remplacer'):TleSessionExport([snapshot(case)],Settings(),case).run(alias)
        assert source.read_text().startswith('User,Value')
    finally:case.close()


def test_session_size_limit_preserves_previous_file(tmp_path,monkeypatch):
    import fireblade.core.tle_session_export as module
    case,source=create(tmp_path);target=tmp_path/'s.tle_sess';target.write_bytes(b'old')
    monkeypatch.setattr(module,'MAX_SESSION_BYTES',64)
    try:
        with pytest.raises(ValueError,match='4 Mo'):TleSessionExport([snapshot(case)],Settings(),case).run(target)
        assert target.read_bytes()==b'old' and not list(tmp_path.glob('*.partial'))
    finally:case.close()


def test_hard_link_destination_is_also_protected(tmp_path):
    case,source=create(tmp_path)
    try:
        alias=tmp_path/'alias.tle_sess';os.link(source,alias)
        with pytest.raises(ValueError,match='remplacer'):TleSessionExport([snapshot(case)],Settings(),case).run(alias)
        assert alias.read_bytes()==source.read_bytes()
    finally:case.close()
