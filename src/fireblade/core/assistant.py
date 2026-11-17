"""A switch on the local assistant: off by default, and honest about what it cannot do.

The prototype in 0.5.0 is deliberately narrow. What it contains is the plumbing —
where the model lives, whether it can run on this machine, and how a finding is
handed to it — because that plumbing is what the rest of the feature depends on.
What it does **not** contain yet is an inference engine: Fireblade ships no model and
no runtime for one, so ``status()`` says so in plain words instead of failing later
with a stack trace in the status bar.

Keep this module free of PySide6: it is imported by the panel, by the tests and by a
possible command-line probe, and none of them should need a window.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from fireblade.core.settings import physical_memory_mb

DEFAULT_MODEL = 'MiniCPM5-2B'
# What the model needs before it is allowed to answer: weights at Q4_K_M (1.56 GB on
# disk for MiniCPM5-2B), a KV cache for 8k tokens, and room for the runtime itself.
WEIGHTS_MB = 1600
RUNTIME_MB = 900
CONTEXT_TOKENS = 8192
KV_CACHE_MB = 400

STATE_OFF = 'off'
STATE_MISSING = 'missing'
STATE_NO_MEMORY = 'no-memory'
STATE_READY = 'ready'


def model_directory(root=None):
    """Where the assistant's files live: beside the user's cases, never in the repository."""
    if root is not None:
        return Path(root)
    base = os.environ.get('LOCALAPPDATA') or str(Path.home())
    return Path(base) / 'Fireblade' / 'Assistant'


@dataclass(frozen=True)
class Status:
    state: str
    model: str
    path: str
    needed_mb: int
    available_mb: int
    detail: str

    @property
    def can_answer(self):
        return self.state == STATE_READY

    @property
    def enabled(self):
        """Switched on by the analyst, whatever the machine can actually do with it."""
        return self.state != STATE_OFF


class Assistant:
    """Read the configured model and decide whether it can be used on this machine."""

    def __init__(self, root=None, memory_mb=None):
        self.root = model_directory(root)
        self.manifest_path = self.root / 'assistant.json'
        self.manifest_error = ''
        self.manifest = self._read_manifest()
        self._memory_mb = memory_mb

    def _read_manifest(self):
        if not self.manifest_path.is_file():
            return {}
        try:
            data = json.loads(self.manifest_path.read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            self.manifest_error = str(exc)
            return {}
        if not isinstance(data, dict):
            self.manifest_error = 'assistant.json is not an object'
            return {}
        return data

    @property
    def enabled(self):
        return bool(self.manifest.get('enabled'))

    @property
    def model(self):
        return str(self.manifest.get('model') or DEFAULT_MODEL)

    @property
    def weights(self):
        name = self.manifest.get('weights')
        return self.root / str(name) if name else None

    def memory_mb(self):
        return self._memory_mb if self._memory_mb is not None else physical_memory_mb()

    def needed_mb(self):
        return WEIGHTS_MB + RUNTIME_MB + KV_CACHE_MB

    def status(self):
        available = self.memory_mb()
        # A manifest that cannot be parsed is a missing install, not 'off': reporting
        # 'off' would tell the analyst to switch on something that is already on.
        if self.manifest_error:
            return Status(STATE_MISSING, self.model, str(self.root), self.needed_mb(), available,
                          'assistant.json could not be read: ' + self.manifest_error)
        if not self.enabled:
            return Status(STATE_OFF, self.model, str(self.root), self.needed_mb(), available,
                          'The local assistant is off. Fireblade works without it.')
        weights = self.weights
        if weights is None or not weights.is_file():
            return Status(STATE_MISSING, self.model, str(self.root), self.needed_mb(), available,
                          'No model file yet. Put the GGUF in %s and set "weights" in assistant.json.'
                          % self.root)
        if available < self.needed_mb():
            return Status(STATE_NO_MEMORY, self.model, str(self.root), self.needed_mb(), available,
                          'This machine has %d MB and the model needs about %d MB; the assistant stays off.'
                          % (available, self.needed_mb()))
        return Status(STATE_READY, self.model, str(self.root), self.needed_mb(), available,
                      'The model is in place. Generating an explanation is not available in this build.')


def write_manifest(root, enabled, model=DEFAULT_MODEL, weights=None):
    """Create or update assistant.json. Called by the installer, never by the UI thread."""
    directory = model_directory(root)
    directory.mkdir(parents=True, exist_ok=True)
    data = dict(version=1, enabled=bool(enabled), model=str(model), context=CONTEXT_TOKENS)
    if weights:
        data['weights'] = str(weights)
    target = directory / 'assistant.json'
    temporary = target.with_suffix('.json.part')
    temporary.write_text(json.dumps(data, indent=2), encoding='utf-8')
    os.replace(temporary, target)
    return target
