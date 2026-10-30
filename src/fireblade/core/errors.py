"""Cancellation state shared by the engine and job runner, without Qt imports."""
from contextlib import contextmanager
from contextvars import ContextVar


_job_cancellation = ContextVar("timeline_job_cancellation", default=None)


@contextmanager
def cancellation_scope(event):
    """Keep a job's cancellation request across entry into a new DB operation."""
    token = _job_cancellation.set(event)
    try:
        yield
    finally:
        _job_cancellation.reset(token)


def job_cancelled():
    event = _job_cancellation.get()
    return event is not None and event.is_set()


class OperationCancelled(RuntimeError):
    def __init__(self, message="Opération annulée"):
        super().__init__(message)
