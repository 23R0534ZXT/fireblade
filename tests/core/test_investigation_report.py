from pathlib import Path

import pytest

from fireblade.core.engine import Case
from fireblade.core.investigation_report import build_report, write_report
from fireblade.core.models import AnalysisSnapshot, Filter, View
from fireblade.core.workspace_reader import WorkspaceReader


@pytest.fixture
def evidence(tmp_path):
    source=tmp_path/'source.csv';source.write_text('User,ID,Description\nalice,0009007199254740993,<script>alert(1)</script>\nbob,002,other\nalice,003,last\n')
    case=Case(tmp_path/'analysis.timeline');case.import_csv(source);case.bookmark(1,'<img src=x onerror=bad>');case.bookmark(3,'Note élève')
    doc=AnalysisSnapshot(str(case.path),case.info,View(),b'')
    yield case,doc
    case.close()


def test_report_has_exact_values_notes_source_references_and_escaped_html(evidence,tmp_path):
    case,doc=evidence
    report=build_report(WorkspaceReader([doc],active=case),'<Titre>','Contexte & limites')
    assert report['records']==2 and not report['errors']
    assert '0009007199254740993' in report['html'] and case.info['sha256'] in report['html']
    assert '<script>' not in report['html'] and '&lt;script&gt;' in report['html']
    assert '<img ' not in report['html'] and '&lt;img ' in report['html']
    assert 'Note élève' in report['html'] and 'Enregistrement source nº 3' in report['html']
    html=tmp_path/'report.html';pdf=tmp_path/'report.pdf'
    write_report(html,report,[doc]);write_report(pdf,report,[doc],pdf=True)
    assert html.read_text()==report['html']
    assert pdf.read_bytes().startswith(b'%PDF-')


def test_report_respects_selection_filters_and_explicit_truncation(evidence):
    case,doc=evidence;doc.view.filters=[Filter(0,'eq','alice')]
    reader=WorkspaceReader([doc],active=case)
    result=build_report(reader,'Selection',bookmarks_only=False,row_ids={doc.path:[3]},limit=1)
    assert result['records']==1 and 'Enregistrement source nº 3' in result['html'] and 'nº 1</h3>' not in result['html']
    limited=build_report(reader,'Limit',limit=1)
    assert limited['records']==1 and 'Résultats partiels' in limited['html']
    with pytest.raises(ValueError,match='écraser'):write_report(case.path,limited,[doc])


def test_missing_analysis_is_explicit_in_report(evidence,tmp_path):
    case,doc=evidence
    missing=AnalysisSnapshot(str(tmp_path/'missing.timeline'),{'path':'missing.csv'},View(),b'')
    result=build_report(WorkspaceReader([doc,missing],active=case),'Partiel')
    assert result['records']==2 and len(result['errors'])==1
    assert 'Analyse non incluse' in result['html']


def test_failed_pdf_render_releases_file_and_preserves_previous_report(evidence,tmp_path,monkeypatch):
    from PySide6.QtGui import QTextDocument
    case,doc=evidence
    report=build_report(WorkspaceReader([doc],active=case),'Failure')
    target=tmp_path/'report.pdf';target.write_bytes(b'previous report')
    def broken(*args):raise OSError('simulated render failure')
    monkeypatch.setattr(QTextDocument,'print_',broken)
    with pytest.raises(OSError,match='simulated'):write_report(target,report,[doc],pdf=True)
    assert target.read_bytes()==b'previous report' and not list(tmp_path.glob('*.partial'))


def test_silently_incomplete_pdf_does_not_replace_existing_file(evidence,tmp_path,monkeypatch):
    from PySide6.QtGui import QTextDocument
    case,doc=evidence
    report=build_report(WorkspaceReader([doc],active=case),'Incomplete')
    target=tmp_path/'report.pdf';target.write_bytes(b'previous report')
    def incomplete(*args):next(tmp_path.glob('*.partial')).write_bytes(b'%PDF-1.7\ntruncated')
    monkeypatch.setattr(QTextDocument,'print_',incomplete)
    with pytest.raises(ValueError,match='incomplet'):write_report(target,report,[doc],pdf=True)
    assert target.read_bytes()==b'previous report' and not list(tmp_path.glob('*.partial'))
