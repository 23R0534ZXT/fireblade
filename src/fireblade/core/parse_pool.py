"""A small pool of parsing processes.

Every Linux log is read by a child interpreter: the reader is Python, and threads
that share a GIL cannot use a second core. The pool is long-lived, so a collection
pays the interpreter start once, and it can be terminated when the analyst stops.
"""
import json
import os
import subprocess
import sys
import threading


class ParsePool:
    def __init__(self, workers=1):
        self.size = max(1, min(int(workers or 1), 8))
        self._mutex = threading.Lock()
        self._free = []
        self._idle = threading.Semaphore(0)
        self._closed = False

    def _command(self):
        # A frozen executable re-launches itself and answers the flag in bootstrap;
        # a source checkout starts the worker module directly.
        if getattr(sys, 'frozen', False):
            return [sys.executable, '--parse-worker']
        return [sys.executable, '-m', 'fireblade.core.linux_worker']

    def _spawn(self):
        environment = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
        return subprocess.Popen(self._command(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, text=True, encoding='utf-8',
                                bufsize=1, env=environment)

    def start(self):
        with self._mutex:
            if self._free or self._closed:
                return self
            for _ in range(self.size):
                self._free.append(self._spawn())
            self._idle.release(len(self._free))
        return self

    def run(self, source, output):
        """Parse one file in a child process and return its report."""
        self.start()
        self._idle.acquire()
        with self._mutex:
            worker = self._free.pop() if self._free else None
        if worker is None:
            raise RuntimeError('Bassin de lecture fermé')
        try:
            worker.stdin.write(json.dumps(dict(source=str(source), output=str(output))) + '\n')
            worker.stdin.flush()
            answer = worker.stdout.readline()
        except (OSError, ValueError) as exc:
            worker = self._replace(worker)
            raise RuntimeError('Lecture interrompue : %s' % exc) from exc
        if not answer:
            self._replace(worker)
            raise RuntimeError('Le processus de lecture s\'est arrêté')
        with self._mutex:
            if not self._closed:
                self._free.append(worker)
        self._idle.release()
        payload = json.loads(answer)
        if payload.get('status') != 'ok':
            raise RuntimeError(payload.get('error') or 'Lecture échouée')
        return payload['result']

    def _replace(self, worker):
        try:
            worker.kill()
        except OSError:
            pass
        replacement = None
        if not self._closed:
            try:
                replacement = self._spawn()
            except OSError:
                replacement = None
        if replacement is not None:
            with self._mutex:
                self._free.append(replacement)
            self._idle.release()
        return replacement

    def close(self):
        with self._mutex:
            if self._closed:
                return
            self._closed = True
            workers, self._free = self._free, []
        for worker in workers:
            try:
                worker.stdin.write(json.dumps(dict(stop=True)) + '\n')
                worker.stdin.flush()
            except (OSError, ValueError):
                pass
        for worker in workers:
            try:
                worker.wait(timeout=5)
            except subprocess.TimeoutExpired:
                worker.kill()
            except OSError:
                pass
