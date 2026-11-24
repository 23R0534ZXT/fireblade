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
    facts: list = field(default_factory=list)  # EvidenceRow
    neighbours: list = field(default_factory=list)  # dicts, other groups nearby
    missing: list = field(default_factory=list)  # what Fireblade could not prove
    prompt: str = ""

    def numbers(self):
        return {row.number for row in self.facts}


def _row_to_evidence(number, row):
    return EvidenceRow(
        number=number,
        stamp=str(row.get("Timestamp") or row.get("TimeCreated") or "")[:19],
        host=str(row.get("Computer") or ""),
        source=str(row.get("EvtxFile") or row.get("SourceFile") or "").rsplit("\\", 1)[-1],
        event_id=str(row.get("EventID") or ""),
        text=str(row.get("Details") or row.get("DetailsShort") or "")[:400],
    )


def build_pack(group, rows, groups, incidents, rows_by_number=None, style="plain"):
    """Assemble the page handed to the model, and to the analyst when the model is off.

    ``rows`` are the alert rows of the selected group, in the order the group recorded
    them. ``groups``/``incidents`` are the full result, used to find neighbours that a
    correlation could reasonably link.
    """
    facts = [
        _row_to_evidence(number, row) for number, row in enumerate(rows[:MAX_CONTEXT_EVENTS], 1)
    ]
    neighbours = []
    incident = next((item for item in incidents if item.key == group.incident), None)
    if incident is not None:
        for other in incident.groups:
            if other.key == group.key:
                continue
            neighbours.append(
                dict(
                    key=other.key,
                    title=other.title,
                    level=other.level,
                    host=other.host,
                    start=other.start.isoformat() if other.start else "",
                    count=other.count,
                    same_host=other.host.casefold() == group.host.casefold(),
                )
            )
    neighbours.sort(key=lambda item: (not item["same_host"], item["start"]))
    missing = []
    if group.count > len(facts):
        missing.append(
            "%d more occurrences of this rule are stored but were not read for this explanation."
            % (group.count - len(facts))
        )
    if group.start is None:
        missing.append("This rule has no usable timestamp, so it cannot be placed in time.")
    if not any(row.text for row in facts):
        missing.append("The stored rows carry no detail text for this rule.")
    pack = Pack(
        group_key=group.key,
        title=group.title,
        level=group.level,
        host=group.host,
        channel=group.channel,
        event_ids=tuple(group.event_ids),
        start=group.start.isoformat(sep=" ", timespec="seconds") if group.start else "unknown",
        end=group.end.isoformat(sep=" ", timespec="seconds") if group.end else "unknown",
        count=group.count,
        facts=facts,
        neighbours=neighbours[:12],
        missing=missing,
    )
    pack.prompt = render_prompt(pack, style=style)
    return pack


EXAMPLE = """WORKED EXAMPLE (shape only, not your data)
FINDING rule: Suspicious service installed, severity: high
EVIDENCE
[evt 1] 09:14:02 HOST-1 id=7045 ServiceName: updater | ImagePath: C:\\Temp\\u.exe
[evt 2] 09:14:30 HOST-1 id=3 Image: C:\\Temp\\u.exe | DestinationIp: 203.0.113.9
ANSWER
{"summary": "A service pointing at a temporary binary starts and then opens an outbound connection.",
 "facts": [{"text": "The service updater is installed from C:\\Temp.", "events": [1]},
           {"text": "The same binary connects out 28 s later.", "events": [2]}],
 "links": [{"from": 1, "to": 2, "why": "same binary, cause then effect"}],
 "missing": ["the binary contents"]}"""


def render_prompt(pack, limit=MAX_PROMPT_CHARS, style="plain"):
    """The instruction and the evidence, in the shape a small model reads best.

    Kept deliberately plain: one block of facts, one block of neighbours, an explicit
    list of what is unknown, and the citation format spelled out.
    """
    lines = [
        "You assist a forensic analyst. Answer only from the EVIDENCE below.",
        "Return JSON with these keys:",
        "Keep it short: at most 3 facts of one sentence each, at most 2 links, at most 2",
        "missing items. An answer that runs long is cut off and becomes unreadable.",
        "  summary   - at most 2 short sentences describing what these events show;",
        '  facts     - each item is {"text": one statement, "events": [event numbers it rests on]};',
        '  links     - each item is {"from": n, "to": n, "why": short reason}, joining two',
        "              events where the second follows from the first: same process or path,",
        "              cause then effect. Add at least one link whenever two events are in",
        "              order on the same host; for example from a protection being disabled to",
        "              the command that runs right after it;",
        "  missing   - what the evidence does not establish.",
        "The only valid event numbers are the ones printed in brackets at the start of an",
        "EVIDENCE line: they run from 1 to %d for this finding. A number outside that range"
        % len(pack.facts),
        "does not exist, and the other findings listed below carry no numbers at all.",
        "Never invent an event, a host, a user, a path or a time. If the evidence is thin,",
        "say so in missing instead of guessing, and leave facts or links empty.",
        "",
        "FINDING",
        "rule: %s" % pack.title,
        "severity: %s" % pack.level,
        "host: %s" % (pack.host or "unknown"),
        "channel: %s" % (pack.channel or "unknown"),
        "event ids: %s" % (", ".join(pack.event_ids) or "unknown"),
        "occurrences: %d between %s and %s" % (pack.count, pack.start, pack.end),
        "",
        "EVIDENCE",
    ]
    for row in pack.facts:
        lines.append(
            "[evt %d] %s %s id=%s %s" % (row.number, row.stamp, row.host, row.event_id, row.text)
        )
    if not pack.facts:
        lines.append("(no event rows were stored for this rule)")
    if pack.neighbours:
        lines.append("")
        lines.append("OTHER FINDINGS IN THE SAME WINDOW")
        for item in pack.neighbours:
            lines.append(
                "- %s (%s, %s) at %s, %d occurrence(s)%s"
                % (
                    item["title"],
                    item["level"],
                    item["host"],
                    item["start"],
                    item["count"],
                    "" if item["same_host"] else ", other host",
                )
            )
    if pack.missing:
        lines.append("")
        lines.append("NOT AVAILABLE")
        for item in pack.missing:
            lines.append("- " + item)
    if style == "fewshot":
        lines.insert(0, EXAMPLE)
        lines.insert(1, "")
    text = "\n".join(lines)
    return text[:limit]


# The shape the model must produce. A schema is not a truth guarantee, but it turns an
# invented reference into a value this code can reject before anything is drawn.
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "facts", "links", "missing"],
    "properties": {
        "summary": {"type": "string"},
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["text", "events"],
                "properties": {
                    "text": {"type": "string"},
                    "events": {"type": "array", "items": {"type": "integer"}},
                },
            },
        },
        "links": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["from", "to", "why"],
                "properties": {
                    "from": {"type": "integer"},
                    "to": {"type": "integer"},
                    "why": {"type": "string"},
                },
            },
        },
        "missing": {"type": "array", "items": {"type": "string"}},
    },
}


def read_answer(text, pack):
    """Parse the model's JSON, keep only what the pack can support, and say what was cut.

    Returns ``dict(structured=..., dropped=..., valid=bool)``. A link is kept only when
    both of its ends are events the pack really contains; a fact with a fabricated
    reference is dropped whole rather than shown with the reference stripped, because a
    claim without its evidence is exactly what this feature refuses to display.
    """
    import json

    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1] if len(raw.split("```")) > 1 else raw
        raw = raw[4:] if raw.lower().startswith("json") else raw
    try:
        data = json.loads(raw)
    except ValueError:
        return dict(structured=None, dropped=["the answer was not valid JSON"], valid=False)
    if not isinstance(data, dict):
        return dict(structured=None, dropped=["the answer was not an object"], valid=False)
    known = pack.numbers()
    dropped = []
    facts = []
    for item in data.get("facts") or []:
        if not isinstance(item, dict):
            continue
        cited = [int(value) for value in (item.get("events") or []) if isinstance(value, int)]
        unknown = [value for value in cited if value not in known]
        if unknown:
            dropped.append(
                "a claim cited events that are not in this finding: %s"
                % ", ".join(str(value) for value in unknown)
            )
            continue
        if not cited:
            dropped.append("a claim was dropped because it cited no event at all")
            continue
        facts.append(dict(text=str(item.get("text") or "").strip(), events=cited))
    links = []
    for item in data.get("links") or []:
        if not isinstance(item, dict):
            continue
        source, target = item.get("from"), item.get("to")
        if (
            type(source) is not int
            or type(target) is not int
            or source not in known
            or target not in known
        ):
            dropped.append("a link joined events that are not in this finding")
            continue
        if source == target:
            continue
        links.append(dict(source=source, target=target, why=str(item.get("why") or "").strip()))
    missing = [str(item).strip() for item in (data.get("missing") or []) if str(item).strip()]
    structured = dict(
        summary=str(data.get("summary") or "").strip(), facts=facts, links=links, missing=missing
    )
    valid = bool(structured["summary"] or facts)
    return dict(structured=structured, dropped=dropped, valid=valid)


def render_structured(structured):
    """The text the panel shows: the model's sentences, then its links, then the gaps."""
    lines = []
    if structured.get("summary"):
        lines.append(structured["summary"])
    for fact in structured.get("facts") or []:
        references = " ".join("[evt %d]" % value for value in fact["events"])
        lines.append("· %s %s" % (fact["text"], references))
    for link in structured.get("links") or []:
        lines.append("→ evt %d → evt %d : %s" % (link["source"], link["target"], link["why"]))
    if structured.get("missing"):
        lines.append("Not established: " + "; ".join(structured["missing"]))
    return "\n".join(lines)


_CITATION = __import__("re").compile(r"\[evt\s+(\d+)\]")


def citations(text):
    return [int(value) for value in _CITATION.findall(text or "")]


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
    when = pack.start if pack.start != "unknown" else "an unrecorded time"
    lines.append(
        "%s ran %d time(s) on %s from %s to %s."
        % (pack.title, pack.count, pack.host or "an unknown host", when, pack.end)
    )
    if pack.facts:
        first = pack.facts[0]
        lines.append(
            "First stored event: %s, id %s, %s [evt 1]."
            % (first.stamp, first.event_id, first.text or "no detail text")
        )
    if pack.neighbours:
        lines.append(
            "%d other finding(s) fall in the same window, %d on this host."
            % (len(pack.neighbours), sum(1 for item in pack.neighbours if item["same_host"]))
        )
    for item in pack.missing:
        lines.append("Not established: " + item)
    return "\n".join(lines)


def severity_first(groups, limit=8):
    """The groups worth reading first: most severe, then most frequent."""
    ordered = sorted(
        groups,
        key=lambda group: (-rank(level_of(group.level)), -group.count, group.title.casefold()),
    )
    return ordered[:limit]


def window_around(group, minutes=5):
    """The context window a reader expects around a burst: start minus, end plus."""
    if group.start is None:
        return None
    span = timedelta(minutes=max(1, int(minutes)))
    return group.start - span, (group.end or group.start) + span
