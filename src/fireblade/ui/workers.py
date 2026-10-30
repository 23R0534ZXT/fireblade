"""Minimal Qt background jobs; no engine or window dependency."""
import threading
from PySide6.QtCore import QObject, QRunnable, Signal
from fireblade.core.errors import OperationCancelled, cancellation_scope


class Signals(QObject):
    done = Signal(object)
    error = Signal(str)
    progress = Signal(str)
    cancelled = Signal()


class Job(QRunnable):
    def __init__(self, function):
        super().__init__()
        self.function, self.signals = function, Signals()
        self.cancelled = threading.Event()

    def cancel(self):
        """Skip a queued task; an already running query keeps its normal completion."""
        self.cancelled.set()

    def run(self):
        if self.cancelled.is_set():
            self.signals.cancelled.emit()
            return
        try:
            with cancellation_scope(self.cancelled):
                result = self.function()
            self.signals.done.emit(result)
        except OperationCancelled:
            self.signals.cancelled.emit()
        except Exception as exc:
            self.signals.error.emit(str(exc))

