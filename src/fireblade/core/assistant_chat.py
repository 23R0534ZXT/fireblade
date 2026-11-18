"""A conversation with the local model, with the case as its tools.

The 0.5.0 assistant answered one question about one finding: forty rows in, a JSON
object out, no memory and no way to look anything up. This module is the other half of
that idea — a transcript that survives the turn, and a short loop in which the model
asks the case a question before it writes anything.

Two steps per turn, both schema-bound so a small model cannot wander:

1. **plan** — the model picks one tool and its arguments, or says it needs none;
2. **answer** — it writes plain prose from what the tool returned.

Everything here is free of PySide6 and of DuckDB: the tools arrive as a callable the
interface owns, so this module is testable with a stub server and a list of rows.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from fireblade.core import assistant as assistant_module

MAX_STEPS = 3
MAX_HISTORY = 12
PLAN_TOKENS = 160
ANSWER_TOKENS = 700

PLAN_SCHEMA = {
    'type': 'object',
    'properties': {
        'tool': {'type': 'string',
                 'enum': ['none', 'overview', 'search', 'findings', 'artifact']},
        'text': {'type': 'string'},
        'host': {'type': 'string'},
        'event_id': {'type': 'string'},
        'artifact': {'type': 'string'},
        'limit': {'type': 'integer'},
    },
    'required': ['tool', 'text', 'host', 'event_id', 'artifact', 'limit'],
    'additionalProperties': False,
}

TOOLS_MENU = """TOOLS
overview                          what the case contains: hosts, sources, dates, counts
search(text, host, event_id)      events matching a word, a host or an event id
findings(level, host)             the detections, most severe first
artifact(artifact)                rows of one artifact kind, for example Amcache or Prefetch
none                              the question needs no lookup"""


@dataclass
class Step:
    """One lookup the model asked for, kept so the interface can show and audit it."""
    tool: str
    arguments: dict
    rows: int = 0
    text: str = ''


@dataclass
class Turn:
    text: str
    steps: list = field(default_factory=list)
    seconds: float = 0.0
    engine: str = ''


def system_prompt():
    return (
        'You are the assistant inside Fireblade, a forensic case tool used by an analyst.\n'
        'You speak plainly, in short sentences, like a colleague sitting next to them.\n'
        'Never invent a host, a path, a timestamp or an event id: if the case does not '
        'show it, say what is missing and what would settle it.\n'
        'Answer in the language of the question. If the question is in French, answer in '
        'French; technical identifiers, file paths and rule names stay exactly as found.\n'
        'Do what is asked: if the analyst asks for a list, give a list; for a conclusion, '
        'give a conclusion first and the reason after; for a comparison, compare.\n'
        'Do not end with an offer to help further, do not repeat the question back, and '
        'never comment on the question itself or on your own process.')


def plan_prompt(question, history, brief):
    lines = [TOOLS_MENU, '', 'CASE', brief.strip() or '(nothing loaded)', '']
    if history:
        lines.append('CONVERSATION SO FAR')
        for role, text in history[-6:]:
            lines.append(('%s: ' % ('Analyst' if role == 'user' else 'You')) + text[:400])
        lines.append('')
    lines += [
        'QUESTION', question.strip(), '',
        'Pick the single most useful lookup, or "none" if the case cannot answer it.',
        'A question about what happened uses findings; a question about one artefact '
        'uses artifact; a question about a word, a host or an event id uses search.',
        'Use empty strings and 0 for arguments you do not need.']
    return '\n'.join(lines)


def answer_prompt(question, history, brief, results):
    lines = [system_prompt(), '', 'CASE', brief.strip() or '(nothing loaded)', '']
    if history:
        lines.append('CONVERSATION SO FAR')
        for role, text in history[-6:]:
            lines.append(('%s: ' % ('Analyst' if role == 'user' else 'You')) + text[:400])
        lines.append('')
    if results:
        lines += ['WHAT YOU LOOKED UP', results, '']
    lines += [
        'QUESTION', question.strip(), '',
        'Write the answer now: plain prose, at most eight lines, no JSON, no preamble, '
        'no comment about the question itself.',
        'Name only the hosts, rules, times and files that appear above. Never write a '
        'number in square brackets, and never invent one.',
        'Start with a direct answer in one sentence: what happened, and whether it matters. '
        'Then two or three sentences of support that name at most three detections, with '
        'their level. Do not copy the list back: the analyst can read it above.',
        'An answer that names no detection at all, when detections were read, is a failure.',
        'Answer about the case as a whole. The selected finding is context, not the subject, '
        'unless the question is about that finding.',
        'If the lookups above do not answer the question, say what is missing in one '
        'sentence instead of guessing.']
    return '\n'.join(lines)


FRENCH = (' le ', ' la ', ' les ', ' des ', ' une ', ' est ', ' sur ', ' pour ', ' avec ',
          ' dans ', ' pas ', ' que ', ' qui ', ' au ', ' aux ', ' ce ', ' cette ')
ENGLISH = (' the ', ' and ', ' of ', ' is ', ' are ', ' on ', ' with ', ' this ', ' that ',
           ' was ', ' were ', ' for ', ' not ')


def language_of(text):
    """'fr', 'en' or '' — a guess good enough to notice an answer in the wrong one."""
    folded = ' %s ' % ' '.join(str(text or '').casefold().split())
    french = sum(folded.count(word) for word in FRENCH)
    english = sum(folded.count(word) for word in ENGLISH)
    if french > english * 1.2 and french >= 2:
        return 'fr'
    if english > french * 1.2 and english >= 2:
        return 'en'
    return ''


def names_a_finding(answer, steps):
    """Does the answer actually name what was read?"""
    titles = []
    for step in steps:
        for line in step.text.splitlines():
            if line.startswith('- '):
                title = line[2:].split(',')[0].strip()
                if len(title) > 6:
                    titles.append(title.casefold())
    if not titles:
        return True
    folded = str(answer or '').casefold()
    return any(title[:24] in folded for title in titles)


def _parse_plan(raw):
    """A plan the model mangled is not an error: it becomes "no lookup"."""
    import json
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return dict(tool='none', text='', host='', event_id='', artifact='', limit=0)
    if not isinstance(data, dict):
        return dict(tool='none', text='', host='', event_id='', artifact='', limit=0)
    tool = str(data.get('tool') or 'none')
    if tool not in {'overview', 'search', 'findings', 'artifact'}:
        tool = 'none'
    try:
        limit = int(data.get('limit') or 0)
    except (TypeError, ValueError):
        limit = 0
    return dict(tool=tool, text=str(data.get('text') or ''), host=str(data.get('host') or ''),
                event_id=str(data.get('event_id') or ''), artifact=str(data.get('artifact') or ''),
                limit=max(0, min(limit, 200)))


class Chat:
    """One analyst, one case, a transcript, and the model that reads both."""

    def __init__(self, root, tools, memory_mb=None):
        self.root = str(root)
        self.tools = tools
        self.memory_mb = memory_mb
        self.history = []

    def reset(self):
        self.history = []

    def ask(self, question, progress=None):
        question = (question or '').strip()
        if not question:
            return Turn(text='', steps=[], seconds=0.0, engine='')
        assistant = assistant_module.Assistant(self.root, memory_mb=self.memory_mb)
        status = assistant.status()
        if not status.can_answer:
            return Turn(text=status.detail, steps=[], seconds=0.0, engine=status.state)

        steps = []
        results = ''
        elapsed = 0.0
        brief = self.tools.describe()
        server = assistant_module.shared_server(self.root, assistant)
        for _ in range(MAX_STEPS):
            plan = assistant_module.ask(server.port, plan_prompt(question, self.history, brief),
                                        max_tokens=PLAN_TOKENS, schema=PLAN_SCHEMA)
            elapsed += plan['seconds']
            choice = _parse_plan(plan['text'])
            if choice['tool'] == 'search' and not (
                    choice['text'] or choice['host'] or choice['event_id']):
                # Nothing to search for: the detections are what a case is read from.
                choice['tool'] = 'findings' if self.tools.findings() else 'overview'
            if choice['tool'] == 'none':
                break
            if progress is not None:
                progress('Reading the case: %s…' % choice['tool'])
            try:
                text, count = self.tools.call(choice['tool'], choice)
            except (KeyError, ValueError) as error:
                # A tool that cannot answer says so in the transcript instead of failing
                # the turn: the model can still answer from what it already has.
                text, count = 'The lookup failed: %s' % error, 0
            steps.append(Step(tool=choice['tool'], arguments=choice, rows=count, text=text))
            results += text + '\n'
            if count:
                break
            # An empty search answers nothing, and a model given an empty page makes one up.
            if choice['tool'] != 'findings' and self.tools.findings():
                text, count = self.tools.call('findings', dict())
                steps.append(Step(tool='findings', arguments={}, rows=count, text=text))
                results += text + '\n'
                if count:
                    break

        answer = assistant_module.ask(
            server.port, answer_prompt(question, self.history, brief, results),
            max_tokens=ANSWER_TOKENS)
        elapsed += answer['seconds']
        text = answer['text'].strip()

        # Two failures are worth one more question and no more: an answer in the wrong
        # language, and an answer that lists detections without naming one.
        wanted = language_of(question)
        retry = ''
        if wanted and language_of(text) not in ('', wanted):
            retry = ('Answer in %s only, in the same words the analyst used.'
                     % ('French' if wanted == 'fr' else 'English'))
        elif steps and not names_a_finding(text, steps):
            retry = ('Your answer did not name a single detection. Name the detections '
                     'you were given, with their level and their time.')
        if retry:
            if progress is not None:
                progress('Rewriting the answer…')
            again = assistant_module.ask(
                server.port, answer_prompt(question, self.history, brief, results) + '\n' + retry,
                max_tokens=ANSWER_TOKENS)
            elapsed += again['seconds']
            if again['text'].strip():
                text = again['text'].strip()
        self.history.append(('user', question))
        self.history.append(('assistant', text))
        self.history = self.history[-MAX_HISTORY:]
        return Turn(text=text, steps=steps, seconds=round(elapsed, 1), engine='local')
