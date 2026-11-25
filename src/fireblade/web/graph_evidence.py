"""What each node and each edge of the attack graph rests on.

A professional graph states nothing it cannot show. Every node and every edge carries:

- ``what``  — what it represents, in a sentence;
- ``how``   — how Fireblade obtained it, naming the column or the record it was read from;
- ``items`` — the evidence itself: the alert groups behind it, each with the identifiers of
  the exact rows of the alert analysis (``analysis`` + ``rows``), so a click opens the line
  the detection engine wrote;
- ``declared`` — for what the analyst entered by hand (a machine, an indicator, a free node):
  the record as it is stored, because there is no source row to show.

Nothing here infers anything: the graph builder links a host to a technique because an alert
on that host carries the technique, and the evidence lists exactly those alerts.
"""

from __future__ import annotations

from fireblade.core import attack_graph as ag

MAX_ITEMS = 25  # alert groups kept per node or edge
MAX_ROWS = 12  # row identifiers kept per group (the group itself says how many there are)
LEVEL_ORDER = ("critical", "high", "medium", "low", "informational")


def _item(group, analysis):
    return {
        "title": group.title,
        "level": group.level,
        "host": group.host,
        "channel": group.channel,
        "event_ids": list(group.event_ids),
        "rule_id": group.rule_id,
        "rule_file": group.rule_file,
        "tactics": group.tactics,
        "techniques": group.techniques,
        "start": group.start.isoformat() if group.start else None,
        "end": group.end.isoformat() if group.end else None,
        "count": int(group.count),
        "analysis": analysis,
        "rows": [int(row) for row in list(group.samples)[:MAX_ROWS]],
        "rows_total": len(group.samples),
    }


def _worst(groups):
    levels = {str(group.level or "").lower() for group in groups}
    return next((level for level in LEVEL_ORDER if level in levels), "")


def _bundle(groups, analysis, **fields):
    """The evidence block for a set of alert groups."""
    ordered = sorted(groups, key=lambda item: (-item.severity, item.title, item.host))
    return {
        "items": [_item(group, analysis) for group in ordered[:MAX_ITEMS]],
        "items_total": len(ordered),
        "alerts": sum(int(group.count) for group in ordered),
        "rules": len({group.rule_id or group.title for group in ordered}),
        "hosts": len({group.host.casefold() for group in ordered if group.host}),
        "level": _worst(ordered),
        "first": min((g.start for g in ordered if g.start), default=None),
        "last": max((g.end for g in ordered if g.end), default=None),
        **fields,
    }


def _plural(count, word):
    return f"{count} {word}" + ("" if count == 1 else "s")


def _where(source):
    if source.get("analysis") is not None:
        return (
            f"the alert analysis “{source.get('label') or 'Hayabusa alerts'}” of this case "
            f"(its {source.get('rows', 0)} row(s) are the detection engine's own output)"
        )
    return f"the detection output file {source.get('file') or 'hayabusa.csv'}"


def build(graph, groups, workspace, source):
    """Attach ``evidence`` to every node and edge of ``graph`` (in place) and return it."""
    analysis = source.get("analysis")
    by_host, by_technique, by_stage, by_pair = {}, {}, {}, {}
    for group in groups:
        host_id = "host:" + ag._slug(str(group.host or "").strip() or "unattributed host")
        stage = ag.tactic_name(group.tactics)
        stage_id = "stage:" + ag._slug(stage) if stage else None
        by_host.setdefault(host_id, []).append(group)
        if stage_id:
            by_stage.setdefault(stage_id, []).append(group)
        for code, _label in ag._techniques(group.techniques):
            technique_id = "technique:" + ag._slug(code)
            by_technique.setdefault(technique_id, []).append(group)
            by_pair.setdefault(("alert", host_id, technique_id), []).append(group)
            if stage_id:
                by_pair.setdefault(("tactic", technique_id, stage_id), []).append(group)

    declared_entities = {
        "host:" + ag._slug(entity.get("label") or entity.get("hostname") or ""): entity
        for entity in workspace.get("entities") or []
        if entity.get("kind") in ("machine", "account")
    }
    declared_iocs = {
        "ioc:" + ag._slug(f"{ioc.get('kind')}-{ioc.get('value')}"): ioc
        for ioc in workspace.get("iocs") or []
    }
    manual = {item.get("id"): item for item in (workspace.get("graph") or {}).get("nodes") or []}
    where = _where(source)

    for node in graph["nodes"]:
        kind, identifier = node.get("kind"), node["id"]
        label = node.get("label") or identifier
        if kind == "host" and identifier in by_host:
            groups_of = by_host[identifier]
            block = _bundle(groups_of, analysis)
            block["what"] = (
                f"The machine {label}: the Computer of {_plural(block['alerts'], 'alert')} "
                f"from {_plural(block['rules'], 'detection rule')}."
            )
            block["how"] = (
                f"Read from the Computer column of {where}. The rows behind each group are "
                "listed below: open one to see the line exactly as the engine wrote it."
            )
        elif kind == "technique":
            groups_of = by_technique.get(identifier, [])
            block = _bundle(groups_of, analysis)
            block["what"] = (
                f"The ATT&CK technique {node.get('code') or label}: tagged by "
                f"{_plural(block['rules'], 'detection rule')} on "
                f"{_plural(block['hosts'], 'machine')}, {_plural(block['alerts'], 'alert')} in all."
            )
            block["how"] = (
                f"Read from the MitreTags column of {where}. The tag is the rule's own: "
                "Fireblade does not infer a technique from behaviour."
            )
        elif kind == "stage":
            groups_of = by_stage.get(identifier, [])
            block = _bundle(groups_of, analysis)
            block["what"] = (
                f"The ATT&CK tactic {label}: the declared goal of "
                f"{_plural(block['rules'], 'detection rule')} that fired "
                f"{_plural(block['alerts'], 'alert')}."
            )
            block["how"] = (
                f"Read from the MitreTactics column of {where}, which comes from the rule "
                "definition. Techniques sit in the column of the tactic their rule declares."
            )
        else:
            groups_of = by_host.get(identifier, []) if kind in ("host", "account") else []
            block = _bundle(groups_of, analysis)
            if kind == "ioc" and identifier in declared_iocs:
                record = declared_iocs[identifier]
                block["what"] = (
                    f"The indicator {record.get('value')} ({record.get('kind')}), "
                    f"status {record.get('status') or 'new'}"
                    + (f", observed on {record.get('machine')}" if record.get("machine") else "")
                    + "."
                )
                block["how"] = (
                    "Tracked by the analyst in Actions & tracking › Indicators. It is a lead the "
                    "analyst recorded, not something the detection concluded."
                )
                block["declared"] = {
                    key: record.get(key)
                    for key in ("kind", "value", "label", "source", "status", "machine", "added")
                    if record.get(key)
                }
            elif identifier in declared_entities or kind in ("host", "account"):
                record = declared_entities.get(identifier) or {}
                block["what"] = f"The {kind} {label}, declared in the case."
                block["how"] = (
                    "Declared by the analyst in Actions & tracking › Machines and accounts."
                    + (
                        f" Alerts naming it as Computer are listed below ({where})."
                        if groups_of
                        else " No alert names it: there is no source row to show."
                    )
                )
                block["declared"] = {
                    key: record.get(key)
                    for key in ("kind", "label", "hostname", "ip", "os", "notes", "created")
                    if record.get(key)
                }
            else:
                entry = manual.get(identifier) or {}
                block["what"] = f"A free node, “{label}”."
                block["how"] = (
                    "Added by hand with Tag…: it records the analyst's own reading and has no "
                    "source row."
                )
                block["declared"] = {
                    "tags": list(entry.get("tags") or node.get("tags") or []),
                    "kind": entry.get("kind") or kind,
                }
        block["first"] = block["first"].isoformat() if block["first"] else None
        block["last"] = block["last"].isoformat() if block["last"] else None
        node["evidence"] = block
        node["level"] = node.get("level") if kind == "ioc" else block["level"]
        node["alerts"] = block["alerts"]

    names = {node["id"]: node.get("label") or node["id"] for node in graph["nodes"]}
    for edge in graph["edges"]:
        label = edge.get("label") or ""
        key = (label or "alert", edge["source"], edge["target"])
        groups_of = by_pair.get(key, [])
        block = _bundle(groups_of, analysis)
        origin, target = names.get(edge["source"], ""), names.get(edge["target"], "")
        if label == "alert" or (not label and groups_of):
            block["what"] = (
                f"{origin} → {target}: {_plural(block['alerts'], 'alert')} on {origin} "
                f"carry the technique {target}."
            )
            block["how"] = (
                f"Both ends are read from the same rows of {where}: the Computer column names "
                "the host and the MitreTags column names the technique. The link exists only "
                "because those rows exist."
            )
        elif label == "tactic":
            block["what"] = (
                f"{origin} → {target}: the rules that tag {origin} declare {target} as their "
                "tactic."
            )
            block["how"] = f"Read from the MitreTactics and MitreTags columns of {where}."
        elif label == "observed on":
            record = declared_iocs.get(edge["source"]) or {}
            block["what"] = f"{origin} was recorded as observed on {target}."
            block["how"] = (
                "From the machine named on the tracked indicator in Actions & tracking: "
                "declared by the analyst, not derived from an alert."
            )
            block["declared"] = {
                key: record.get(key)
                for key in ("value", "kind", "machine", "added")
                if record.get(key)
            }
        else:
            block["what"] = f"{origin} → {target}" + (f" ({label})" if label else "") + "."
            block["how"] = "A link the analyst recorded by hand: there is no source row."
        block["first"] = block["first"].isoformat() if block["first"] else None
        block["last"] = block["last"].isoformat() if block["last"] else None
        edge["evidence"] = block
        edge["alerts"] = block["alerts"]
        edge["id"] = f"{edge['source']}>{edge['target']}>{label}"
    return graph
