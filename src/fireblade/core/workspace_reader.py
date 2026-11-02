"""Read a workspace sequentially, without retaining inactive connections."""
import copy
from contextlib import contextmanager
import threading
from pathlib import Path

from fireblade.core.engine import Case
from fireblade.core.errors import OperationCancelled, job_cancelled


class WorkspaceReader:
    def __init__(self, documents, settings=None, active=None):
        self.documents = copy.deepcopy(documents)
        self.settings, self.active = settings, active
        self.cancelled = threading.Event()
        self.lock = threading.Lock()
        self.current = None

    def check(self):
        if self.cancelled.is_set() or job_cancelled():raise OperationCancelled()

    def interrupt(self):
        self.cancelled.set()
        with self.lock:
            if self.current:self.current.interrupt()

    @contextmanager
    def open(self, document):
        self.check()
        if not Path(document.path).is_file():raise FileNotFoundError('Analyse introuvable : '+document.path)
        own = self.active is None or str(self.active.path) != document.path
        case = Case(document.path, settings=self.settings, read_only=True) if own else self.active
        try:
            with self.lock:
                self.current = case
            with case.operation():
                self.check()
                if case.info != document.source_info:raise ValueError('Analyse remplacée : ' + document.path)
                yield case
                self.check()
        finally:
            with self.lock:self.current = None
            if own:case.close()
