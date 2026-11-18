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
STATE_NO_RUNTIME = 'no-runtime'
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
            # utf-8-sig: a manifest written by PowerShell or Notepad carries a BOM,
            # and refusing it turned 'installed' into 'off' for no good reason.
            data = json.loads(self.manifest_path.read_text(encoding='utf-8-sig'))
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

    @property
    def runtime(self):
        return self.root / 'runtime' / 'llama-server.exe'

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
        if not self.runtime.is_file():
            return Status(STATE_NO_RUNTIME, self.model, str(self.root), self.needed_mb(), available,
                          'The weights are installed but the local engine is not; re-run the '
                          'download to fetch it.')
        return Status(STATE_READY, self.model, str(self.root), self.needed_mb(), available,
                      'The local model is installed and ready.')


_SERVERS = {}


def shared_server(root, assistant=None):
    """One engine per installation, started on first use and reused for the next question.

    Loading the weights costs tens of seconds on four cores; paying that again for every
    follow-up would make the chat unusable. The server is stopped by ``close_servers()``
    when the window closes, and by nothing else.
    """
    key = str(Path(root).resolve())
    server = _SERVERS.get(key)
    if server is not None and server.process is not None and server.process.poll() is None:
        return server
    assistant = assistant or Assistant(root)
    server = Server(assistant.runtime, assistant.weights)
    server.start()
    _SERVERS[key] = server
    return server


def close_servers():
    for key, server in list(_SERVERS.items()):
        try:
            server.stop()
        finally:
            _SERVERS.pop(key, None)


def answer(root, pack, question='', memory_mb=None, progress=None, schema=None):
    """Explain a finding with the local model, or say why it cannot.

    This is the one call the interface needs: it starts the engine if it is not
    running, sends the evidence pack, and returns the text with its cost. It holds no
    Qt import, so the panel runs it in a worker thread and the tests drive it with a
    stub server.
    """
    assistant = Assistant(root, memory_mb=memory_mb)
    status = assistant.status()
    if not status.can_answer:
        return dict(ok=False, text=status.detail, seconds=0.0)
    prompt = pack.prompt
    if question.strip():
        prompt += ('\n\nANALYST QUESTION\n' + question.strip() +
                   '\nAnswer the question first in summary, using only the events above.')
    server = shared_server(root, assistant)
    result = ask(server.port, prompt, schema=schema)
    return dict(ok=True, text=result['text'], seconds=result['seconds'],
                prompt_tokens=result.get('prompt_tokens'),
                completion_tokens=result.get('completion_tokens'))


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


# ---------------------------------------------------------------- installation
# Pinned on purpose: a model or a runtime that moves under the installer is a build
# that cannot be reproduced. Update both the tag and the digest in one commit.
RUNTIME_TAG = 'b12483'
RUNTIME_URL = ('https://github.com/ggml-org/llama.cpp/releases/download/%s/'
               'llama-%s-bin-win-cpu-x64.zip') % (RUNTIME_TAG, RUNTIME_TAG)
MODEL_URL = ('https://huggingface.co/openbmb/MiniCPM5-2B-GGUF/resolve/main/'
             'MiniCPM5-2B-Q4_K_M.gguf')
# Measured on the downloaded file: the installer refuses anything else, so a model that
# moves upstream cannot change what this build runs.
MODEL_SHA256 = 'ec2d5801640099e97d8d7e8003ad4d81f336e757811f03a26173dddf386602fd'
MODEL_BYTES = 1_561_318_368


def download(url, target, progress=None, expected_bytes=None, digest=None, chunk=1 << 20):
    """Stream a file to disk, atomically, with a byte count the caller can show.

    A download that dies leaves its ``.part`` behind and nothing else: the caller's
    next attempt overwrites it, and a half-written file never looks installed.
    """
    import hashlib
    import urllib.request
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + '.part')
    hasher = hashlib.sha256()
    received = 0
    request = urllib.request.Request(url, headers={'User-Agent': 'Fireblade'})
    with urllib.request.urlopen(request, timeout=60) as response, temporary.open('wb') as output:
        total = expected_bytes or int(response.headers.get('Content-Length') or 0)
        while True:
            block = response.read(chunk)
            if not block:
                break
            output.write(block)
            hasher.update(block)
            received += len(block)
            if progress is not None:
                progress(received, total)
    if expected_bytes and received != expected_bytes:
        temporary.unlink(missing_ok=True)
        raise ValueError('Téléchargement incomplet : %d octets sur %d' % (received, expected_bytes))
    if digest and hasher.hexdigest().lower() != digest.lower():
        temporary.unlink(missing_ok=True)
        raise ValueError('Empreinte du téléchargement incorrecte')
    target.unlink(missing_ok=True)
    temporary.replace(target)
    return target, hasher.hexdigest()


def install_runtime(root, progress=None):
    """Fetch the CPU build of llama.cpp and keep the server and its DLLs only."""
    import zipfile
    root = model_directory(root)
    archive = root / ('llama-%s.zip' % RUNTIME_TAG)
    download(RUNTIME_URL, archive, progress)
    runtime = root / 'runtime'
    runtime.mkdir(parents=True, exist_ok=True)
    # Every DLL the archive ships, not a guessed list: the CPU backend is named after the
    # instruction set (ggml-cpu-haswell.dll), and a whitelist that misses one produces an
    # executable that dies with STATUS_DLL_NOT_FOUND before writing a single line.
    copied = []
    with zipfile.ZipFile(archive) as zipped:
        for item in zipped.infolist():
            name = Path(item.filename).name
            if name.endswith('.dll') or name == 'llama-server.exe':
                with zipped.open(item) as source, (runtime / name).open('wb') as output:
                    output.write(source.read())
                copied.append(name)
    archive.unlink(missing_ok=True)
    server = runtime / 'llama-server.exe'
    if not server.is_file():
        raise ValueError('Le binaire llama-server est absent de l\'archive téléchargée')
    if not any(name.startswith('ggml-cpu') for name in copied):
        raise ValueError('Le moteur téléchargé ne contient aucun backend CPU')
    return server


def install_model(root, progress=None):
    """Fetch the weights, verify their size, and record their digest in the manifest."""
    root = model_directory(root)
    weights = root / 'MiniCPM5-2B-Q4_K_M.gguf'
    if weights.is_file() and weights.stat().st_size == MODEL_BYTES:
        return weights
    target, digest = download(MODEL_URL, weights, progress, expected_bytes=MODEL_BYTES,
                              digest=MODEL_SHA256 or None)
    return target, digest


class Server:
    """llama-server on a local port, with the health check and the stop it deserves."""

    def __init__(self, server_path, model_path, context=CONTEXT_TOKENS, threads=None, port=None):
        self.server_path = Path(server_path)
        self.model_path = Path(model_path)
        self.context = int(context)
        self.threads = int(threads or max(1, (os.cpu_count() or 4) // 2))
        self.port = int(port or free_port())
        self.process = None
        self.log_path = model_directory() / 'llama-server.log'

    def command(self):
        return [str(self.server_path), '-m', str(self.model_path), '--port', str(self.port),
                '--ctx-size', str(self.context), '--threads', str(self.threads), '--threads-batch',
                str(self.threads), '--no-webui', '--jinja', '--log-file', str(self.log_path)]

    def start(self, timeout=180):
        import subprocess
        if self.process is not None:
            return self
        creation = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        self.process = subprocess.Popen(self.command(), cwd=str(self.server_path.parent),
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                        creationflags=creation)
        if not self.wait_ready(timeout):
            self.stop()
            raise TimeoutError('Le moteur local n\'a pas répondu en %d s' % timeout)
        return self

    def wait_ready(self, timeout=180):
        import time
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.process is not None and self.process.poll() is not None:
                return False
            try:
                with __import__('urllib.request', fromlist=['urlopen']).urlopen(
                        'http://127.0.0.1:%d/health' % self.port, timeout=2) as response:
                    if response.status == 200:
                        return True
            except Exception:
                time.sleep(0.5)
        return False

    def stop(self):
        if self.process is None:
            return
        try:
            self.process.terminate()
            self.process.wait(timeout=10)
        except Exception:
            try:
                self.process.kill()
            except Exception:
                pass
        finally:
            self.process = None

    def __enter__(self):
        return self.start()

    def __exit__(self, *_):
        self.stop()


def free_port():
    import socket
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


def ask(port, prompt, max_tokens=400, timeout=600, schema=None):
    """One completion from the local server, with the answer text and its timing."""
    import json
    import time
    import urllib.request
    # This model thinks by default: it writes its reasoning into a separate field and
    # leaves the answer empty until the budget runs out. Extraction is not reasoning, and
    # on four cores the thinking tripled the latency for nothing measurable.
    body = dict(messages=[dict(role='user', content=prompt)], max_tokens=int(max_tokens),
                temperature=0.0, top_p=1.0, stream=False,
                chat_template_kwargs=dict(enable_thinking=False))
    if schema is not None:
        body['response_format'] = dict(type='json_schema',
                                       json_schema=dict(name='finding', schema=schema, strict=True))
    request = urllib.request.Request('http://127.0.0.1:%d/v1/chat/completions' % int(port),
                                     data=json.dumps(body).encode('utf-8'),
                                     headers={'Content-Type': 'application/json'})
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode('utf-8'))
    elapsed = time.monotonic() - started
    choice = (payload.get('choices') or [{}])[0]
    message = choice.get('message') or {}
    text = message.get('content') or ''
    if not text.strip() and message.get('reasoning_content'):
        # Never silently hand back an empty string: the caller has to know the model spent
        # its budget thinking instead of answering.
        raise ValueError('Le modèle a raisonné sans conclure : augmentez la limite de '
                         'jetons ou vérifiez que le modèle supporte enable_thinking=False')
    usage = payload.get('usage') or {}
    return dict(text=text.strip(), seconds=round(elapsed, 1),
                prompt_tokens=usage.get('prompt_tokens'), completion_tokens=usage.get('completion_tokens'))
