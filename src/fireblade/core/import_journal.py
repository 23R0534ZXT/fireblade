"""Append-only journal for one import operation.

An import is a forensic act: every file it touched, every decision it took and
every reason it gave has to survive the window that showed it. Each event is one
JSON object on its own line, written and flushed as it happens, so a run that
dies still explains itself afterwards.

The journal never fails an import. It records its own failure instead, and the
report shows that the record is incomplete -- silence is what this module exists
to prevent.
"""

import json
import threading
from datetime import UTC, datetime
from pathlib import Path

NAME = "journal.jsonl"


def _now():
    return datetime.now(UTC)


class ImportJournal:
    """One file, one writer, one line per event."""

    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self.started = _now()
        self.error = ""
        self.count = 0

    def event(self, kind, **fields):
        """Append one event. Fields that are None are omitted, not written as null."""
        stamp = _now()
        record = dict(
            time=stamp.isoformat(timespec="milliseconds"),
            kind=kind,
            elapsed=round((stamp - self.started).total_seconds(), 3),
        )
        record.update({key: value for key, value in fields.items() if value is not None})
        line = json.dumps(record, ensure_ascii=False, default=str)
        with self._lock:
            try:
                with self.path.open("a", encoding="utf-8", newline="\n") as stream:
                    stream.write(line + "\n")
                self.count += 1
            except OSError as exc:
                # A read-only folder, a full disk: the import still runs, and the
                # report says in words that its record could not be written.
                self.error = str(exc)
        return record


def read(path):
    """Every complete event, oldest first. A torn last line is skipped, not fatal."""
    events = []
    try:
        with Path(path).open(encoding="utf-8", errors="replace") as stream:
            for line in stream:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return events


def summary(path):
    """What the journal proves, in the few numbers a report can show."""
    events = read(path)
    counts = {}
    for event in events:
        kind = str(event.get("kind", ""))
        counts[kind] = counts.get(kind, 0) + 1
    return dict(
        events=len(events),
        counts=counts,
        first=events[0].get("time") if events else None,
        last=events[-1].get("time") if events else None,
    )
