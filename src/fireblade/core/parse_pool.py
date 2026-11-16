"""A small pool of parsing processes.

Every Linux log is read by a child interpreter: the reader is Python, and threads
that share a GIL cannot use a second core. The pool is long-lived, so a collection
pays the interpreter start once, and it can be terminated when the analyst stops.

A single file larger than the rest is split by `linux_slices` into ranges that are
read together: `run_many` exists for that case, because a batch that waits for
several workers while holding some of them deadlocks against a second batch doing
the same. A batch therefore takes every worker at once, and one batch runs at a
time.
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
        self._batch = threading.Lock()
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

    def run(self, source, output, span=None):
        """Parse one file in a child process and return its report."""
        self.start()
        self._idle.acquire()
        with self._mutex:
            worker = self._free.pop() if self._free else None
        if worker is None:
            self._idle.release()
            raise RuntimeError('Bassin de lecture fermé')
        job = dict(source=str(source), output=str(output), span=span)
        try:
            result = self._send(worker, job)
        except BaseException:
            self._replace(worker)
            raise
        self._release(worker)
        return result

    def run_many(self, jobs):
        """Read several ranges of one file at once, answering in the order given.

        The caller hands every job the same file with a different span. The batch
        waits for the whole pool, holds it, then runs one job per worker: taking the
        pool in one gesture is what keeps two big files from each holding half of it
        and waiting for ever.
        """
        jobs = list(jobs)
        if not jobs:
            return []
        with self._batch:
            workers = self._take_all()
            if not workers:
                raise RuntimeError('Aucun processus de lecture disponible')
            broken = set()
            try:
                return self._dispatch(workers, jobs, broken)
            finally:
                for worker in workers:
                    if worker in broken:
                        self._replace(worker)
                    else:
                        self._release(worker)

    def _send(self, worker, job):
        """One job on one worker: the result, or the reason it failed."""
        try:
            worker.stdin.write(json.dumps(job) + '\n')
            worker.stdin.flush()
            answer = worker.stdout.readline()
        except (OSError, ValueError) as exc:
            raise RuntimeError('Lecture interrompue : %s' % exc) from exc
        if not answer:
            raise RuntimeError("Le processus de lecture s'est arrêté")
        payload = json.loads(answer)
        if payload.get('status') != 'ok':
            raise RuntimeError(payload.get('error') or 'Lecture échouée')
        return payload['result']

    def _take_all(self):
        """Every free worker at once, waiting for the busy ones to finish."""
        self.start()
        taken = []
        for _ in range(self.size):
            if not self._idle.acquire(timeout=120):
                break
            with self._mutex:
                worker = self._free.pop() if self._free else None
            if worker is None:
                self._idle.release()
                break
            taken.append(worker)
        return taken

    def _dispatch(self, workers, jobs, broken):
        results = [None] * len(jobs)
        pending = list(range(len(jobs)))
        lock = threading.Lock()
        failures = []

        def work(worker):
            while True:
                with lock:
                    if not pending or failures:
                        return
                    index = pending.pop(0)
                try:
                    results[index] = self._send(worker, jobs[index])
                except BaseException as exc:  # noqa: BLE001 - reported to the caller
                    with lock:
                        failures.append(exc)
                        broken.add(worker)
                        pending.clear()
                    return

        threads = [threading.Thread(target=work, args=(worker,), daemon=True)
                   for worker in workers[:len(jobs)]]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        if failures:
            raise failures[0]
        if any(result is None for result in results):
            raise RuntimeError('Tranches inachevées')
        return results

    def _release(self, worker):
        with self._mutex:
            if not self._closed:
                self._free.append(worker)
                self._idle.release()
                return
        self._kill(worker)

    def _kill(self, worker):
        try:
            worker.kill()
        except OSError:
            pass

    def _replace(self, worker):
        self._kill(worker)
        replacement = None
        if not self._closed:
            try:
                replacement = self._spawn()
            except OSError:
                replacement = None
        if replacement is not None:
            self._release(replacement)

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
