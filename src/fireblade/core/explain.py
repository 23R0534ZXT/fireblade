"""Turn a group of findings into the one thing a small model can answer reliably.

A 2-billion-parameter model on a laptop cannot read a timeline: it can read a page.
This module builds that page — the group itself, the events that surround it, and the
neighbours Fireblade can prove belong to it — and then refuses to describe anything
that is not in the page.

Two rules come from what was measured on small models and they shape the code:

- **the model is handed identifiers, never asked to invent them.** Every prompt line
  carries an event number that also exists in the tables it is given;
- **a sentence that cites an unknown event is not shown.** ``explain()`` returns text
  only after ``verify()`` has checked every ``[evt N]`` reference against the pack.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from fireblade.core.findings import level_of, rank

# How much context one explanation may carry: a page, not an export.
MAX_CONTEXT_EVENTS = 40
MAX_PROMPT_CHARS = 6000


@dataclass
class EvidenceRow:
    number: int
    stamp: str
    host: str
    source: str
    event_id: str
    text: str


@dataclass
class Pack:
    group_key: str
    title: str
    level: str
    host: str
    channel: str
    event_ids: tuple
    start: str
    end: str
    count: int
    facts: list = field(default_factory=list)        # EvidenceRow
    neighbours: list = field(default_factory=list)   # dicts, other groups nearby
    missing: list = field(default_factory=list)      # what Fireblade could not prove
    prompt: str = ''

    def numbers(self):
        return {row.number for row in self.facts}


def _row_to_evidence(number, row):
    return EvidenceRow(
        number=number,
        stamp=str(row.get('Timestamp') or row.get('TimeCreated') or '')[:19],
        host=str(row.get('Computer') or ''),
        source=str(row.get('EvtxFile') or row.get('SourceFile') or '').rsplit('\\', 1)[-1],
        event_id=str(row.get('EventID') or ''),
        text=str(row.get('Details') or row.get('DetailsShort') or '')[:400],
    )


def build_pack(group, rows, groups, incidents, rows_by_number=None):
    """Assemble the page handed to the model, and to the analyst when the model is off.

    ``rows`` are the alert rows of the selected group, in the order the group recorded
    them. ``groups``/``incidents`` are the full result, used to find neighbours that a
    correlation could reasonably link.
    """
    facts = [_row_to_evidence(number, row) for number, row in enumerate(rows[:MAX_CONTEXT_EVENTS], 1)]
    neighbours = []
    incident = next((item for item in incidents if item.key == group.incident), None)
    if incident is not None:
        for other in incident.groups:
            if other.key == group.key:
                continue
            neighbours.append(dict(key=other.key, title=other.title, level=other.level,
                                   host=other.host, start=other.start.isoformat() if other.start else '',
                                   count=other.count, same_host=other.host.casefold() == group.host.casefold()))
    neighbours.sort(key=lambda item: (not item['same_host'], item['start']))
    missing = []
    if group.count > len(facts):
        missing.append('%d more occurrences of this rule are stored but were not read for this explanation.'
                       % (group.count - len(facts)))
    if group.start is None:
        missing.append('This rule has no usable timestamp, so it cannot be placed in time.')
    if not any(row.text for row in facts):
        missing.append('The stored rows carry no detail text for this rule.')
    pack = Pack(group_key=group.key, title=group.title, level=group.level, host=group.host,
                channel=group.channel, event_ids=tuple(group.event_ids),
                start=group.start.isoformat(sep=' ', timespec='seconds') if group.start else 'unknown',
                end=group.end.isoformat(sep=' ', timespec='seconds') if group.end else 'unknown',
                count=group.count, facts=facts, neighbours=neighbours[:12], missing=missing)
    pack.prompt = render_prompt(pack)
    return pack


def render_prompt(pack, limit=MAX_PROMPT_CHARS):
    """The instruction and the evidence, in the shape a small model reads best.

    Kept deliberately plain: one block of facts, one block of neighbours, an explicit
    list of what is unknown, and the citation format spelled out.
    """
    lines = [
        'You are assisting a forensic analyst. Answer only from the EVIDENCE below.',
        'Write at most 5 short sentences, in English, describing what these events show.',
        'Cite every statement with the event number in brackets, like [evt 3].',
        'Never invent an event, a host, a user, a path or a time that is not listed.',
        'If the evidence is not enough, say what is missing instead of guessing.',
        '',
        'FINDING',
        'rule: %s' % pack.title,
        'severity: %s' % pack.level,
        'host: %s' % (pack.host or 'unknown'),
        'channel: %s' % (pack.channel or 'unknown'),
        'event ids: %s' % (', '.join(pack.event_ids) or 'unknown'),
        'occurrences: %d between %s and %s' % (pack.count, pack.start, pack.end),
        '',
        'EVIDENCE',
    ]
    for row in pack.facts:
        lines.append('[evt %d] %s %s id=%s %s' % (row.number, row.stamp, row.host, row.event_id, row.text))
    if not pack.facts:
        lines.append('(no event rows were stored for this rule)')
    if pack.neighbours:
        lines.append('')
        lines.append('OTHER FINDINGS IN THE SAME WINDOW')
        for item in pack.neighbours:
            lines.append('- %s (%s, %s) at %s, %d occurrence(s)%s'
                         % (item['title'], item['level'], item['host'], item['start'], item['count'],
                            '' if item['same_host'] else ', other host'))
    if pack.missing:
        lines.append('')
        lines.append('NOT AVAILABLE')
        for item in pack.missing:
            lines.append('- ' + item)
    text = '\n'.join(lines)
    return text[:limit]


_CITATION = __import__('re').compile(r'\[evt\s+(\d+)\]')


def citations(text):
    return [int(value) for value in _CITATION.findall(text or '')]


def verify(text, pack):
    """True when every citation names an event that exists in the pack.

    A model that writes a plausible sentence with an invented reference is the failure
    mode this guard exists for: a well-formed answer is not a true one, but an answer
    that points nowhere is certainly unusable.
    """
    cited = citations(text)
    if not cited:
        return False
    known = pack.numbers()
    return all(number in known for number in cited)


def describe_without_model(pack):
    """What the interface shows when no model is installed: facts, counts, and the gaps.

    This is not a fallback nobody reads — it is the same page the model would get, kept
    visible so the analyst is never left in front of an empty panel.
    """
    lines = []
    when = pack.start if pack.start != 'unknown' else 'an unrecorded time'
    lines.append('%s ran %d time(s) on %s from %s to %s.'
                 % (pack.title, pack.count, pack.host or 'an unknown host', when, pack.end))
    if pack.facts:
        first = pack.facts[0]
        lines.append('First stored event: %s, id %s, %s [evt 1].' % (first.stamp, first.event_id, first.text or 'no detail text'))
    if pack.neighbours:
        lines.append('%d other finding(s) fall in the same window, %d on this host.'
                     % (len(pack.neighbours), sum(1 for item in pack.neighbours if item['same_host'])))
    for item in pack.missing:
        lines.append('Not established: ' + item)
    return '\n'.join(lines)


def severity_first(groups, limit=8):
    """The groups worth reading first: most severe, then most frequent."""
    ordered = sorted(groups, key=lambda group: (-rank(level_of(group.level)), -group.count, group.title.casefold()))
    return ordered[:limit]


def window_around(group, minutes=5):
    """The context window a reader expects around a burst: start minus, end plus."""
    if group.start is None:
        return None
    span = timedelta(minutes=max(1, int(minutes)))
    return group.start - span, (group.end or group.start) + span
