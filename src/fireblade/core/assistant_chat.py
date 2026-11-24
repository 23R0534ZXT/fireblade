"""A forensic assistant: it looks before it speaks, and it says what it cannot settle.

The 0.5.0 assistant explained one finding from forty rows. This one works the way an
analyst works on a case: a first pass that always happens (what is in the case, what was
detected, what else happened in the minutes around the worst detection), then one or two
lookups it chooses itself once it has seen that, then an answer written under a method
that forces it to separate observation from inference.

Everything is free of PySide6 and of DuckDB: the case arrives as a callable, so the loop
is tested with stub tools and a stub engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fireblade.core import assistant as assistant_module

MAX_HISTORY = 12
MAX_EXTRA_LOOKUPS = 2
PLAN_TOKENS = 160
ANSWER_TOKENS = 700
MAX_ANSWER_LINES = 10
REVIEW_TOKENS = 90
REVIEW_CHECKLIST = (
    "You review one draft answer before an analyst reads it. Reply on one line, in these "
    'words only: "OK" if the draft opens with a verdict, names the evidence it rests on, '
    "gives the benign explanation it could not rule out, and ends with one next check. "
    'Otherwise reply "FIX: " and the one thing to change, in twelve words.'
)
MAX_STEP_CHARS = 1600
MAX_EVIDENCE_CHARS = 6500

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "tool": {
            "type": "string",
            "enum": [
                "none",
                "done",
                "overview",
                "search",
                "findings",
                "artifact",
                "around",
                "sequence",
                "timeline",
                "entity",
                "rare",
                "stats",
            ],
        },
        "reason": {"type": "string"},
        "text": {"type": "string"},
        "host": {"type": "string"},
        "event_id": {"type": "string"},
        "artifact": {"type": "string"},
        "column": {"type": "string"},
        "time": {"type": "string"},
        "minutes": {"type": "integer"},
        "limit": {"type": "integer"},
    },
    "required": [
        "tool",
        "reason",
        "text",
        "host",
        "event_id",
        "artifact",
        "column",
        "time",
        "minutes",
        "limit",
    ],
    "additionalProperties": False,
}

TOOLS_MENU = """LOOKUPS YOU MAY ASK FOR (every one of them only reads the case)
overview                            what the case contains
findings(host)                      the detections, most severe first
search(text, host, event_id)        events matching a word, a host or an event id
artifact(artifact)                  one artifact family, for example Amcache or Prefetch
around(time, host, minutes)         what else happened in those minutes, after a detection
sequence(time, host, minutes)       the same window, in time order: cause before effect
timeline(host)                      the busiest hours, to see where the activity sits
entity(text)                        everything one host, account, path or binary touches
rare(column)                        the least frequent values: a process that ran once
stats(column)                       one column at a glance: distinct, filled, range
done                                you have enough to answer"""

METHOD = """You are the forensic assistant inside Fireblade. You work one case with one analyst.

WHAT YOU ARE
A second pair of eyes on the evidence: you read what was collected, you look for what
does not fit, and you say what it would take to settle it. You never decide for the
analyst, and you never dress a guess as a fact.
You never change a case: every lookup reads, none writes, none acts. You analyse.

METHOD
1. Turn the question into the decision it feeds: is this host compromised, did this binary
   run, what did this account do, is this alert worth the analyst's morning.
2. Observation and inference are different sentences. "The service points to C:\\\\Temp" is
   an observation. "The binary was staged there" is an inference, and says so.
3. A timestamp alone means nothing. When a detection matters, the minutes around it, the
   same path on another host and the same account elsewhere are where the case is decided.
4. Name the benign explanation that fits the same rows (patch cycle, admin script, backup
   agent) and say whether the evidence rules it out. An alert with no benign story
   considered is an alert the analyst cannot trust.
5. Say what is missing when the evidence stops short, and which artifact would settle it."""

SHAPE = """HOW TO ANSWER
First line: the verdict, in one sentence, in the language the analyst used.
Then the evidence, one item per line, each naming its host, its time and its rule or event
id exactly as the case spells them.
Then, only if it exists, the explanation you could not rule out, in one sentence.
Then, one concrete next check.
Ten lines at most. No JSON, no square brackets, no preamble, no restating the question,
no offer to help further, no comment about the question or about your own process."""

FRENCH = (
    " le ",
    " la ",
    " les ",
    " des ",
    " une ",
    " est ",
    " sur ",
    " pour ",
    " avec ",
    " dans ",
    " pas ",
    " que ",
    " qui ",
    " au ",
    " aux ",
    " ce ",
    " cette ",
)
ENGLISH = (
    " the ",
    " and ",
    " of ",
    " is ",
    " are ",
    " on ",
    " with ",
    " this ",
    " that ",
    " was ",
    " were ",
    " for ",
    " not ",
)


@dataclass
class Step:
    tool: str
    arguments: dict
    rows: int = 0
    text: str = ""
    reason: str = ""


@dataclass
class Turn:
    text: str
    steps: list = field(default_factory=list)
    seconds: float = 0.0
    engine: str = ""
    conversation: str = ""


def _clip_page(text):
    """One lookup never becomes the whole prompt: the head of it, and what was left out."""
    text = str(text or "")
    if len(text) <= MAX_STEP_CHARS:
        return text
    lines = text.splitlines()
    kept, used = [], 0
    for line in lines:
        if used + len(line) + 1 > MAX_STEP_CHARS:
            break
        kept.append(line)
        used += len(line) + 1
    return "\n".join(kept) + "\n… %d line(s) not shown" % max(0, len(lines) - len(kept))


def _clip_evidence(text):
    """The dossier the model reads is bounded too: a case can hold more than a context."""
    text = str(text or "")
    if len(text) <= MAX_EVIDENCE_CHARS:
        return text
    return text[:MAX_EVIDENCE_CHARS] + "\n… the rest of the evidence was not sent"


def language_of(text):
    """'fr', 'en' or '' — a guess good enough to notice an answer in the wrong one."""
    folded = " %s " % " ".join(str(text or "").casefold().split())
    french = sum(folded.count(word) for word in FRENCH)
    english = sum(folded.count(word) for word in ENGLISH)
    if french > english * 1.2 and french >= 2:
        return "fr"
    if english > french * 1.2 and english >= 2:
        return "en"
    return ""


def named_detections(steps):
    """The detections that were actually read, by title."""
    titles = []
    for step in steps:
        for line in step.text.splitlines():
            if line.startswith("- "):
                title = line[2:].split(",")[0].strip()
                if len(title) > 6:
                    titles.append(title)
    return titles


def names_a_detection(answer, steps):
    folded = str(answer or "").casefold()
    return any(title.casefold()[:24] in folded for title in named_detections(steps))


def system_prompt():
    return METHOD + "\n\n" + SHAPE


def history_block(pairs):
    if not pairs:
        return ""
    lines = ["CONVERSATION SO FAR"]
    for role, text in pairs[-6:]:
        lines.append(("%s: " % ("Analyst" if role == "user" else "You")) + str(text)[:400])
    return "\n".join(lines)


def plan_prompt(question, pairs, brief, evidence=""):
    lines = [METHOD, "", TOOLS_MENU, "", "CASE", brief.strip() or "(nothing loaded)", ""]
    if evidence:
        lines += ["WHAT YOU HAVE ALREADY READ", evidence.strip(), ""]
    block = history_block(pairs)
    if block:
        lines += [block, ""]
    lines += [
        "QUESTION",
        question.strip(),
        "",
        'Name the one lookup that would most change your answer, or "done" if the evidence '
        "above is enough. Explain the reason in one short sentence.",
        "Use empty strings and 0 for arguments you do not need.",
    ]
    return "\n".join(lines)


def answer_prompt(question, pairs, brief, evidence=""):
    lines = [system_prompt(), "", "CASE", brief.strip() or "(nothing loaded)", ""]
    if evidence:
        lines += ["EVIDENCE READ FOR THIS QUESTION", evidence.strip(), ""]
    block = history_block(pairs)
    if block:
        lines += [block, ""]
    lines += [
        "QUESTION",
        question.strip(),
        "",
        "Write the answer now, following HOW TO ANSWER. Name only hosts, rules, times and "
        "files that appear above. Never write a number in square brackets.",
        "If the evidence does not answer the question, say so in one sentence and name what would.",
    ]
    return "\n".join(lines)


def _parse_plan(raw):
    """A plan the model mangled is not an error: it becomes "no lookup"."""
    import json

    empty = dict(
        tool="none",
        reason="",
        text="",
        host="",
        event_id="",
        artifact="",
        column="",
        time="",
        minutes=0,
        limit=0,
    )
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return empty
    if not isinstance(data, dict):
        return empty
    tool = str(data.get("tool") or "none")
    if tool not in {
        "done",
        "overview",
        "search",
        "findings",
        "artifact",
        "around",
        "sequence",
        "timeline",
        "entity",
        "rare",
        "stats",
    }:
        tool = "none"

    def number(key, ceiling):
        try:
            return max(0, min(int(data.get(key) or 0), ceiling))
        except (TypeError, ValueError):
            return 0

    return dict(
        tool=tool,
        reason=str(data.get("reason") or "")[:200],
        text=str(data.get("text") or ""),
        host=str(data.get("host") or ""),
        event_id=str(data.get("event_id") or ""),
        artifact=str(data.get("artifact") or ""),
        column=str(data.get("column") or ""),
        time=str(data.get("time") or ""),
        minutes=number("minutes", 240),
        limit=number("limit", 200),
    )


class Chat:
    """One analyst, one case, one conversation, and the model that reads both."""

    def __init__(self, root, tools, history=None, conversation=None, memory_mb=None):
        self.root = str(root)
        self.tools = tools
        self.history = history
        self.conversation = conversation
        self.memory_mb = memory_mb
        self.history_pairs = list(conversation.pairs(MAX_HISTORY)) if conversation else []

    def reset(self):
        self.conversation = None
        self.history_pairs = []

    def attach(self, conversation):
        """Reopen a conversation that is already on disk."""
        self.conversation = conversation
        self.history_pairs = list(conversation.pairs(MAX_HISTORY)) if conversation else []

    # ------------------------------------------------------------------ the turn
    def ask(self, question, progress=None):
        question = (question or "").strip()
        if not question:
            return Turn(text="", steps=[], seconds=0.0, engine="")
        assistant = assistant_module.Assistant(self.root, memory_mb=self.memory_mb)
        status = assistant.status()
        if not status.can_answer:
            return Turn(text=status.detail, steps=[], seconds=0.0, engine=status.state)

        if self.history is not None and self.conversation is None:
            self.conversation = self.history.start(question)
        if self.history is not None and self.conversation is not None:
            self.history.append(self.conversation, "user", question, question=question)

        steps, evidence, elapsed = self.investigate(question, progress)
        server = assistant_module.shared_server(self.root, assistant)
        brief = self.tools.describe()
        answer = assistant_module.ask(
            server.port,
            answer_prompt(question, self.history_pairs, brief, evidence),
            max_tokens=ANSWER_TOKENS,
        )
        elapsed += answer["seconds"]
        text = answer["text"].strip()

        retry = self._critique(question, text, steps)
        if not retry:
            retry = self._review(server.port, question, text, evidence, status.model)
        if retry:
            if progress is not None:
                progress("Rewriting the answer…")
            again = assistant_module.ask(
                server.port,
                answer_prompt(question, self.history_pairs, brief, evidence) + "\n" + retry,
                max_tokens=ANSWER_TOKENS,
            )
            elapsed += again["seconds"]
            if again["text"].strip():
                text = again["text"].strip()

        self.history_pairs.append(("user", question))
        self.history_pairs.append(("assistant", text))
        self.history_pairs = self.history_pairs[-MAX_HISTORY:]
        identifier = ""
        if self.history is not None and self.conversation is not None:
            self.history.append(self.conversation, "assistant", text, steps=steps)
            identifier = self.conversation.identifier
        return Turn(
            text=text,
            steps=steps,
            seconds=round(elapsed, 1),
            engine="local",
            conversation=identifier,
        )

    # ------------------------------------------------------------------ the work
    def investigate(self, question, progress=None):
        """First the pass every analyst makes, then what the question asks for.

        The order is not left to the model: a small model asked "what next" before it has
        seen the detections opens the wrong door. So the case is always read the same way
        — its shape, its detections, the minutes around the worst of them — and only then
        does the model choose where to dig.
        """
        steps, evidence, elapsed = [], [], 0.0

        def read(tool, arguments, reason=""):
            if progress is not None:
                progress("Reading the case: %s…" % tool)
            try:
                text, count = self.tools.call(tool, arguments)
            except (KeyError, ValueError) as error:
                text, count = "The lookup failed: %s" % error, 0
            steps.append(Step(tool=tool, arguments=arguments, rows=count, text=text, reason=reason))
            evidence.append("--- %s ---\n%s" % (tool, _clip_page(text)))
            return steps[-1]

        read("overview", {})
        read("findings", {"limit": 20})
        worst = self.worst_detection(steps)
        if worst:
            read(
                "around",
                {"host": worst.get("host", ""), "time": worst.get("start", ""), "minutes": 5},
                "the minutes around the worst detection",
            )
            read(
                "sequence",
                {"host": worst.get("host", ""), "time": worst.get("start", ""), "minutes": 15},
                "the same window in time order",
            )

        assistant = assistant_module.Assistant(self.root, memory_mb=self.memory_mb)
        server = assistant_module.shared_server(self.root, assistant)
        brief = self.tools.describe()
        for _ in range(MAX_EXTRA_LOOKUPS):
            plan = assistant_module.ask(
                server.port,
                plan_prompt(question, self.history_pairs, brief, "\n\n".join(evidence)),
                max_tokens=PLAN_TOKENS,
                schema=PLAN_SCHEMA,
            )
            elapsed += plan["seconds"]
            choice = _parse_plan(plan["text"])
            if choice["tool"] in ("none", "done"):
                break
            if choice["tool"] == "search" and not (
                choice["text"] or choice["host"] or choice["event_id"]
            ):
                break
            if choice["tool"] == "around" and not choice["time"]:
                if not worst:
                    break
                choice["time"] = worst.get("start", "")
                choice["host"] = choice["host"] or worst.get("host", "")
            step = read(choice["tool"], choice, choice.get("reason", ""))
            if not step.rows:
                break
        return steps, _clip_evidence("\n\n".join(evidence)), elapsed

    def worst_detection(self, steps):
        """The first detection of the list, which the tool already ordered by severity."""
        for step in steps:
            if step.tool != "findings":
                continue
            for line in step.text.splitlines():
                if not line.startswith("- "):
                    continue
                parts = [part.strip() for part in line[2:].split(",")]
                if len(parts) >= 4:
                    host = parts[2][3:] if parts[2].lower().startswith("on ") else parts[2]
                    stamp = parts[3][3:] if parts[3].lower().startswith("at ") else parts[3]
                    return dict(title=parts[0], level=parts[1], host=host, start=stamp)
        return None

    # ------------------------------------------------------------------ the check
    def _review(self, port, question, text, evidence, model):
        """A second reader for the draft, skipped where it would only add latency.

        A two-billion-parameter model cannot audit its own answer usefully; a four-billion
        one can, and the checklist is what turns a plausible paragraph into an answer the
        analyst can act on. The review never rewrites by itself: it returns a fix.
        """
        if "2B" in str(model) or not str(text).strip():
            return ""
        prompt = "\n".join(
            [
                REVIEW_CHECKLIST,
                "",
                "DRAFT",
                text.strip(),
                "",
                "EVIDENCE IT HAD",
                str(evidence)[:2500],
                "",
                "QUESTION",
                question.strip(),
            ]
        )
        try:
            verdict = assistant_module.ask(port, prompt, max_tokens=REVIEW_TOKENS)["text"].strip()
        except Exception:  # noqa: BLE001 - a review that fails must not cost the answer
            return ""
        folded = verdict.casefold()
        if folded.startswith("fix") or "fix:" in folded:
            fix = verdict.split(":", 1)[-1].strip()
            return (
                "Your draft was reviewed: %s. Rewrite it with that change, keeping "
                "the same facts." % (fix or "it missed the method")
            )
        return ""

    def _critique(self, question, text, steps):
        """One retry, never a loop: the failures that make an answer useless."""
        wanted = language_of(question)
        if wanted and language_of(text) not in ("", wanted):
            return "Answer in %s only, in the same words the analyst used." % (
                "French" if wanted == "fr" else "English"
            )
        if steps and named_detections(steps) and not names_a_detection(text, steps):
            return (
                "Your answer named no detection. Name the detections you were given, "
                "with their level and their time."
            )
        if len([line for line in text.splitlines() if line.strip()]) > MAX_ANSWER_LINES + 6:
            return "Your answer is too long. Keep it to ten lines."
        return ""
