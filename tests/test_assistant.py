"""The assistant says what it can and cannot do, and never pretends to have a model."""
import json

from fireblade.core.assistant import (Assistant, STATE_MISSING, STATE_NO_MEMORY, STATE_NO_RUNTIME,
                                      STATE_OFF, STATE_READY, model_directory, write_manifest)


def test_off_by_default_and_that_is_not_an_error(tmp_path):
    status = Assistant(tmp_path, memory_mb=16384).status()
    assert status.state == STATE_OFF
    assert not status.can_answer
    assert 'works without it' in status.detail


def test_enabled_without_weights_says_where_to_put_them(tmp_path):
    write_manifest(tmp_path, enabled=True)
    status = Assistant(tmp_path, memory_mb=16384).status()
    assert status.state == STATE_MISSING
    assert str(tmp_path) in status.detail


def test_enabled_with_weights_but_no_memory_stays_off(tmp_path):
    weights = tmp_path / 'model.gguf'
    weights.write_bytes(b'\x00' * 8)
    write_manifest(tmp_path, enabled=True, weights='model.gguf')
    status = Assistant(tmp_path, memory_mb=2048).status()
    assert status.state == STATE_NO_MEMORY
    assert not status.can_answer


def test_weights_without_an_engine_say_the_engine_is_missing(tmp_path):
    (tmp_path / 'model.gguf').write_bytes(b'\x00' * 8)
    write_manifest(tmp_path, enabled=True, weights='model.gguf')
    status = Assistant(tmp_path, memory_mb=16384).status()
    assert status.state == STATE_NO_RUNTIME
    assert 'engine' in status.detail
    assert not status.can_answer


def test_weights_and_engine_together_are_ready(tmp_path):
    (tmp_path / 'model.gguf').write_bytes(b'\x00' * 8)
    (tmp_path / 'runtime').mkdir()
    (tmp_path / 'runtime' / 'llama-server.exe').write_bytes(b'MZ')
    write_manifest(tmp_path, enabled=True, weights='model.gguf')
    status = Assistant(tmp_path, memory_mb=16384).status()
    assert status.state == STATE_READY
    assert status.can_answer


def test_a_broken_manifest_is_reported_not_raised(tmp_path):
    (tmp_path / 'assistant.json').write_text('{not json', encoding='utf-8')
    status = Assistant(tmp_path, memory_mb=16384).status()
    assert status.state == STATE_MISSING
    assert 'could not be read' in status.detail


def test_manifest_round_trip_keeps_the_model_name(tmp_path):
    write_manifest(tmp_path, enabled=True, model='MiniCPM5-2B', weights='model.gguf')
    data = json.loads((tmp_path / 'assistant.json').read_text(encoding='utf-8'))
    assert data['model'] == 'MiniCPM5-2B'
    assert data['enabled'] is True
    assert data['version'] == 1


def test_the_directory_follows_the_user_profile(monkeypatch, tmp_path):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    assert model_directory() == tmp_path / 'Fireblade' / 'Assistant'
