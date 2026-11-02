import pytest

from fireblade.core import sessions
from fireblade.core.models import AnalysisSnapshot, View


def snapshot(tmp_path, name='analysis', search=''):
    path = tmp_path / f'{name}.timeline'
    path.touch()
    return AnalysisSnapshot(str(path), {}, View(search=search), b'header')


@pytest.mark.parametrize('count', [0, 1001])
def test_invalid_document_count_preserves_previous_session(tmp_path, count):
    document = snapshot(tmp_path)
    target = tmp_path / 'workspace.fireblade-session'
    sessions.write_session(target, [document], 0)
    before = target.read_bytes()
    with pytest.raises(ValueError, match='1 à 1000'):
        sessions.write_session(target, [document] * count, 0)
    assert target.read_bytes() == before
    assert sessions.read_session(target)[0] == [document]
    assert not list(tmp_path.glob('*.partial'))


@pytest.mark.parametrize('active', [-1, 1, True, '0'])
def test_invalid_active_tab_preserves_previous_session(tmp_path, active):
    document = snapshot(tmp_path)
    target = tmp_path / 'workspace.fireblade-session'
    sessions.write_session(target, [document], 0)
    before = target.read_bytes()
    with pytest.raises(ValueError, match='Onglet actif'):
        sessions.write_session(target, [document], active)
    assert target.read_bytes() == before


@pytest.mark.parametrize('existing', [False, True])
def test_oversized_utf8_session_is_rejected_and_temporary_removed(tmp_path, existing):
    document = snapshot(tmp_path)
    target = tmp_path / 'workspace.fireblade-session'
    if existing:
        sessions.write_session(target, [document], 0)
    before = target.read_bytes() if existing else None
    document.view.search = '😀' * (sessions.MAX_SESSION_BYTES // 4)
    with pytest.raises(ValueError, match='4 Mo'):
        sessions.write_session(target, [document], 0)
    assert (target.read_bytes() if target.exists() else None) == before
    assert not list(tmp_path.glob('*.partial'))


def test_exact_byte_limit_roundtrips_and_one_extra_byte_is_rejected(tmp_path, monkeypatch):
    document = snapshot(tmp_path, search='é')
    target = tmp_path / 'workspace.fireblade-session'
    sessions.write_session(target, [document], 0)
    before = target.read_bytes()
    monkeypatch.setattr(sessions, 'MAX_SESSION_BYTES', len(before))
    sessions.write_session(target, [document], 0)
    assert sessions.read_session(target) == ([document], 0)
    document.view.search += 'a'
    with pytest.raises(ValueError, match='4 Mo'):
        sessions.write_session(target, [document], 0)
    assert target.read_bytes() == before
    assert not list(tmp_path.glob('*.partial'))


def test_1000_distinct_analyses_roundtrip(tmp_path):
    documents = [snapshot(tmp_path, str(index)) for index in range(1000)]
    target = tmp_path / 'workspace.fireblade-session'
    sessions.write_session(target, documents, 999)
    assert sessions.read_session(target) == (documents, 999)
