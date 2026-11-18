"""A conversation belongs to a case, not to the window that happens to be open.

Every turn is appended to a file inside the case folder the moment it is written, so a
crash, a closed window or a resumed investigation leaves the exchange where it was. One
file per conversation, one JSON object per line: a half-written answer costs one line,
never the whole thread.
"""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

FOLDER = 'assistant'
MAX_TITLE = 70


def conversations_folder(case_path):
    """Beside the analysis, inside the case: never in the repository, never in a temp dir."""
    return Path(case_path).resolve().parent / FOLDER


@dataclass
class Message:
    role: str
    text: str
    time: str = ''
    steps: list = field(default_factory=list)


@dataclass
class Conversation:
    identifier: str
    title: str
    updated: str
    messages: list = field(default_factory=list)

    def pairs(self, limit=12):
        """(role, text) as the model reads it, oldest first, tail bounded."""
        return [(item.role, item.text) for item in self.messages if item.text][-limit:]

    def question_count(self):
        return sum(1 for item in self.messages if item.role == 'user')


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _slug(text):
    cleaned = ' '.join(str(text or '').split())
    return (cleaned[:MAX_TITLE] or 'Untitled conversation')


class History:
    """The conversations of one case, on disk, readable while the case is closed."""

    def __init__(self, case_path, folder=None):
        self.folder = Path(folder) if folder else conversations_folder(case_path)
        self.case_path = str(case_path)

    # ------------------------------------------------------------------ reading
    def _files(self):
        if not self.folder.is_dir():
            return []
        return sorted(self.folder.glob('conversation-*.jsonl'), key=lambda path: path.stat().st_mtime,
                      reverse=True)

    def conversations(self):
        found = []
        for path in self._files():
            conversation = self._read(path)
            if conversation and conversation.messages:
                found.append(conversation)
        return found

    def _read(self, path):
        messages, title, updated = [], '', ''
        try:
            lines = path.read_text(encoding='utf-8').splitlines()
        except OSError:
            return None
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except ValueError:
                # A truncated last line is a turn that never finished: skip it, keep the rest.
                continue
            if not isinstance(record, dict) or not isinstance(record.get('text'), str):
                continue
            message = Message(role=str(record.get('role') or 'assistant'),
                              text=record['text'], time=str(record.get('time') or ''),
                              steps=record.get('steps') or [])
            messages.append(message)
            if not title and message.role == 'user':
                title = _slug(message.text)
            updated = message.time or updated
        if not messages:
            return None
        return Conversation(identifier=path.stem, title=title or _slug(path.stem),
                            updated=updated, messages=messages)

    def latest(self):
        found = self.conversations()
        return found[0] if found else None

    def load(self, identifier):
        path = self.folder / (str(identifier) + '.jsonl')
        return self._read(path) if path.is_file() else None

    # ------------------------------------------------------------------ writing
    def start(self, question=''):
        self.folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
        identifier = 'conversation-%s-%s' % (stamp, uuid.uuid4().hex[:6])
        conversation = Conversation(identifier=identifier, title=_slug(question), updated=_now())
        (self.folder / (identifier + '.jsonl')).write_text('', encoding='utf-8')
        return conversation

    def append(self, conversation, role, text, steps=None, question=''):
        """Write one turn, then hand it back: the caller never keeps state the disk lacks."""
        self.folder.mkdir(parents=True, exist_ok=True)
        path = self.folder / (conversation.identifier + '.jsonl')
        record = dict(role=role, text=str(text), time=_now())
        if steps:
            record['steps'] = [dict(tool=getattr(step, 'tool', ''), rows=getattr(step, 'rows', 0),
                                    arguments=getattr(step, 'arguments', {})) for step in steps]
        line = json.dumps(record, ensure_ascii=False)
        with path.open('a', encoding='utf-8', newline='') as handle:
            handle.write(line + '\n')
            handle.flush()
            os.fsync(handle.fileno())
        message = Message(role=role, text=str(text), time=record['time'], steps=record.get('steps', []))
        conversation.messages.append(message)
        conversation.updated = record['time']
        if role == 'user' and (not conversation.title or conversation.title == 'Untitled conversation'):
            conversation.title = _slug(question or text)
        return message

    def forget(self, identifier):
        """Remove one conversation. Never called from the UI without a confirmation."""
        path = self.folder / (str(identifier) + '.jsonl')
        if path.is_file():
            path.unlink()
            return True
        return False
