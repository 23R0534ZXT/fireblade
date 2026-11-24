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


def explain_failure(error, memory_mb=None):
    """A failure a person can act on: a sentence, the remedies, and the raw text.

    DuckDB reports an out-of-memory as a five-line block that ends in a documentation
    link; the status bar shows forty characters of it, which is how a collection can
    die without ever saying why. The two families met in practice — memory and a file
    modified during the import — get a plain sentence and a next step; everything else
    keeps its first line and the detail.
    """
    text = str(error)
    lowered = text.casefold()
    if (
        "out of memory" in lowered
        or "cannot allocate" in lowered
        or "failed to pin block" in lowered
    ):
        limit = (" (%d MB available)" % memory_mb) if memory_mb else ""
        return dict(
            kind="memory",
            summary="Not enough memory for this step%s." % limit,
            advice=[
                "Raise the memory in Preferences → Resources, then run again.",
                "Or work on the folder in smaller batches.",
            ],
            detail=text,
        )
    if "changed during" in lowered or ("chang" in lowered and "import" in lowered):
        return dict(
            kind="source_changed",
            summary="The source file changed during the import; the result is refused.",
            advice=["Close whatever writes into that folder, then run again."],
            detail=text,
        )
    first = next((line for line in text.splitlines() if line.strip()), text)
    return dict(kind="other", summary=first.strip()[:300], advice=[], detail=text)
