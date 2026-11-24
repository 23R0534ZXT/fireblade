"""The assistant says what it can and cannot do, and never pretends to have a model."""

import json

import types

from fireblade.core import assistant as assistant_module
from fireblade.core.assistant import (
    Assistant,
    STATE_MISSING,
    STATE_NO_MEMORY,
    STATE_NO_RUNTIME,
    STATE_OFF,
    STATE_READY,
    answer,
    model_directory,
    write_manifest,
)


def test_off_by_default_and_that_is_not_an_error(tmp_path):
    status = Assistant(tmp_path, memory_mb=16384).status()
    assert status.state == STATE_OFF
    assert not status.can_answer
    assert "works without it" in status.detail


def test_enabled_without_weights_says_where_to_put_them(tmp_path):
    write_manifest(tmp_path, enabled=True)
    status = Assistant(tmp_path, memory_mb=16384).status()
    assert status.state == STATE_MISSING
    assert str(tmp_path) in status.detail


def test_enabled_with_weights_but_no_memory_stays_off(tmp_path):
    weights = tmp_path / "model.gguf"
    weights.write_bytes(b"\x00" * 8)
    write_manifest(tmp_path, enabled=True, weights="model.gguf")
    status = Assistant(tmp_path, memory_mb=2048).status()
    assert status.state == STATE_NO_MEMORY
    assert not status.can_answer


def test_weights_without_an_engine_say_the_engine_is_missing(tmp_path):
    (tmp_path / "model.gguf").write_bytes(b"\x00" * 8)
    write_manifest(tmp_path, enabled=True, weights="model.gguf")
    status = Assistant(tmp_path, memory_mb=16384).status()
    assert status.state == STATE_NO_RUNTIME
    assert "engine" in status.detail
    assert not status.can_answer


def test_weights_and_engine_together_are_ready(tmp_path):
    (tmp_path / "model.gguf").write_bytes(b"\x00" * 8)
    (tmp_path / "runtime").mkdir()
    (tmp_path / "runtime" / "llama-server.exe").write_bytes(b"MZ")
    write_manifest(tmp_path, enabled=True, weights="model.gguf")
    status = Assistant(tmp_path, memory_mb=16384).status()
    assert status.state == STATE_READY
    assert status.can_answer


def test_a_broken_manifest_is_reported_not_raised(tmp_path):
    (tmp_path / "assistant.json").write_text("{not json", encoding="utf-8")
    status = Assistant(tmp_path, memory_mb=16384).status()
    assert status.state == STATE_MISSING
    assert "could not be read" in status.detail


def test_manifest_round_trip_keeps_the_model_name(tmp_path):
    write_manifest(tmp_path, enabled=True, model="MiniCPM5-2B", weights="model.gguf")
    data = json.loads((tmp_path / "assistant.json").read_text(encoding="utf-8"))
    assert data["model"] == "MiniCPM5-2B"
    assert data["enabled"] is True
    assert data["version"] == 1


def test_the_directory_follows_the_user_profile(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert model_directory() == tmp_path / "Fireblade" / "Assistant"


def _ready(tmp_path, monkeypatch):
    (tmp_path / "model.gguf").write_bytes(b"\x00" * 8)
    (tmp_path / "runtime").mkdir()
    (tmp_path / "runtime" / "llama-server.exe").write_bytes(b"MZ")
    write_manifest(tmp_path, enabled=True, weights="model.gguf")
    monkeypatch.setattr(
        Assistant, "status", lambda self: types.SimpleNamespace(can_answer=True, detail="ready")
    )


def test_an_engine_that_dies_mid_answer_is_started_again_once(tmp_path, monkeypatch):
    """The engine did die on an eight-gigabyte machine; the answer must survive it."""
    _ready(tmp_path, monkeypatch)
    calls = []

    def fake_shared(root, assistant=None):
        calls.append("start")
        return types.SimpleNamespace(port=1, stop=lambda: calls.append("stop"))

    refused = [ConnectionRefusedError(10061, "refused"), None]

    def fake_ask(port, prompt, max_tokens=480, timeout=600, schema=None):
        if refused.pop(0):
            raise ConnectionRefusedError(10061, "refused")
        return dict(text="{}", seconds=0.1, finish="stop")

    monkeypatch.setattr(assistant_module, "shared_server", fake_shared)
    monkeypatch.setattr(assistant_module, "ask", fake_ask)
    monkeypatch.setitem(assistant_module._SERVERS, str(tmp_path.resolve()), "stale")
    result = answer(tmp_path, types.SimpleNamespace(prompt="p"), memory_mb=16384)
    assert result["ok"] and result["restarted"] is True
    assert calls.count("start") == 2 and "stop" in calls


def test_a_second_failure_is_reported_to_the_caller(tmp_path, monkeypatch):
    """One retry, not an endless loop: a broken install must surface as an error."""
    _ready(tmp_path, monkeypatch)
    monkeypatch.setattr(
        assistant_module,
        "shared_server",
        lambda root, assistant=None: types.SimpleNamespace(port=1, stop=lambda: None),
    )

    def always_refused(*_a, **_k):
        raise ConnectionRefusedError(10061, "refused")

    monkeypatch.setattr(assistant_module, "ask", always_refused)
    try:
        answer(tmp_path, types.SimpleNamespace(prompt="p"), memory_mb=16384)
    except ConnectionRefusedError:
        pass
    else:
        raise AssertionError("the second failure was swallowed")
