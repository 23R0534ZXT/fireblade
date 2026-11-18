"""Questions worth asking next, read from the case instead of invented by a model.

The 0.6.1 assistant answers well when it is asked well, and a small local model asked
"what should I look at" tends to invent a priority. These suggestions are pure functions
of the data already on screen: the worst finding, the busiest host, the first tracked
indicator. They are spoken in the analyst's language by the interface, never by the model,
and clicking one only fills the question box — nothing is sent on its own.

A suggestion names a host, a rule or an indicator the case really contains; a case with
none of those gets the three questions that make sense on an empty case.
"""
from __future__ import annotations

from collections import Counter

MAX_QUESTION = 240


def _clean(value, limit=80):
    text = ' '.join(str(value or '').split())
    return text[:limit]


def suggest(groups=(), workspace=None, limit=4):
    """Up to ``limit`` distinct questions, most useful first, as French source strings."""
    workspace = workspace or {}
    questions = []

    def add(text):
        text = text[:MAX_QUESTION]
        if text not in questions:
            questions.append(text)

    findings = [group for group in groups if getattr(group, 'title', '')]
    if findings:
        worst = sorted(findings, key=lambda group: (-getattr(group, 'severity', 0),
                                                    str(getattr(group, 'start', ''))))[0]
        host = _clean(getattr(worst, 'host', '')) or 'cet hôte'
        add('Qu\'est-ce qui s\'est passé autour de « ' + _clean(worst.title, 120)
            + ' » sur ' + host + ' ?')
        add('Quelle explication bénigne tient pour « ' + _clean(worst.title, 120) + ' » ?')
        hosts = Counter(_clean(getattr(group, 'host', '')) for group in findings
                        if getattr(group, 'host', ''))
        if hosts:
            busiest, count = hosts.most_common(1)[0]
            add('Que fait ' + busiest + ' dans cette affaire, heure par heure ?')
            if len(hosts) > 1:
                others = [name for name, _ in hosts.most_common(3) if name != busiest]
                add('Y a-t-il eu un mouvement latéral entre ' + busiest + ' et '
                    + ', '.join(others) + ' ?')
    indicators = [item for item in (workspace.get('iocs') or []) if item.get('value')]
    if indicators:
        add('Où apparaît ' + _clean(indicators[0]['value'], 120)
            + ' et qu\'est-ce qui l\'a contacté ?')
    actions = [item for item in (workspace.get('actions') or [])
               if item.get('status') not in ('done', 'cancelled')]
    if actions:
        open_machines = _clean(actions[0].get('machine', ''))
        if open_machines:
            add('Que reste-t-il à vérifier sur ' + open_machines + ' avant de clore ?')
    if not questions:
        add('Que contient ce case et par quoi commencer ?')
        add('Quels artefacts ont été importés et combien de lignes ?')
        add('Où l\'activité est-elle la plus dense ?')
    return questions[:limit]
