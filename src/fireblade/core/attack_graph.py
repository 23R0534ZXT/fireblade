"""Attack graph: what touched what, laid out along the kill chain, and tagged by hand.

The graph is built from three sources that already exist in a case:

- the Hayabusa findings, which carry a host, a rule, a level and MITRE tactics and
  technique identifiers;
- the tracked indicators of the workspace (an IOC observed on a named machine);
- the machines and accounts the analyst recorded for the client.

Nothing is inferred that the data does not say. A rule with a tactic edge points at
the tactic the rule itself declares; a host is linked to a technique because an alert
on that host carries the technique, not because an ordering was guessed. Tags are the
analyst's: they are stored on the node and survive a rebuild, matched by node
identifier.

The layout is deterministic: the kill chain gives the column, the sorted identifier
gives the row. Two builds of the same data draw the same picture, which is what makes
a screenshot in a report reproducible.
"""

from __future__ import annotations

import html
import re

from fireblade.core.case_workspace import NODE_KINDS

# MITRE Enterprise tactics in kill-chain order. Hayabusa writes them as "InitialAccess",
# "PrivilegeEscalation", or with the short form "TA0001"; the normaliser below folds
# case, spaces, hyphens and underscores before matching.
TACTICS = (
    "Reconnaissance",
    "Resource Development",
    "Initial Access",
    "Execution",
    "Persistence",
    "Privilege Escalation",
    "Stealth",
    "Defense Impairment",
    "Defense Evasion",
    "Credential Access",
    "Discovery",
    "Lateral Movement",
    "Collection",
    "Command and Control",
    "Exfiltration",
    "Impact",
)

_TACTIC_KEYS = {re.sub(r"[^a-z]", "", name.casefold()): index for index, name in enumerate(TACTICS)}
# Hayabusa 4.x writes the short names of its config/mitre_tactics.txt ("Exec ¦ DefImpair"),
# not the full ones: a graph that only knew the full names never got a single stage.
_SHORT_NAMES = {
    "recon": "Reconnaissance",
    "resdev": "Resource Development",
    "initaccess": "Initial Access",
    "exec": "Execution",
    "persis": "Persistence",
    "privesc": "Privilege Escalation",
    "defimpair": "Defense Impairment",
    "credaccess": "Credential Access",
    "disc": "Discovery",
    "latmov": "Lateral Movement",
    "collect": "Collection",
    "c2": "Command and Control",
    "exfil": "Exfiltration",
}
for _short, _full in _SHORT_NAMES.items():
    _TACTIC_KEYS[_short] = TACTICS.index(_full)
_TECHNIQUE = re.compile(r"\bT\d{4}(?:\.\d{3})?\b")
MAX_NODES = 2000


def tactic_index(text):
    """Kill-chain position of a tactic written any way Hayabusa writes it, or None."""
    for token in re.split(r"[,;¦|]+", str(text or "")):
        key = re.sub(r"[^a-z0-9]", "", token.casefold())
        if key in _TACTIC_KEYS:
            return _TACTIC_KEYS[key]
    return None


def tactic_name(text):
    index = tactic_index(text)
    return TACTICS[index] if index is not None else ""


def _techniques(text):
    """(identifier, label) pairs from Hayabusa's ``MitreTags``-style strings."""
    result = []
    for chunk in re.split(r"[¦;|]+", str(text or "")):
        chunk = chunk.strip()
        if not chunk:
            continue
        match = _TECHNIQUE.search(chunk)
        if match:
            name = chunk.replace(match.group(0), "").strip(" :-")
            result.append((match.group(0), name or match.group(0)))
        elif len(chunk) <= 120:
            result.append((chunk, chunk))
    return result


def _slug(value):
    return re.sub(r"[^a-z0-9]+", "-", str(value).casefold()).strip("-")[:80] or "node"


def empty_graph():
    return dict(nodes=[], edges=[])


def build(findings=(), workspace=None, *, max_nodes=MAX_NODES):
    """Merge generated nodes with the analyst's manual nodes.

    ``findings`` is the list of :class:`fireblade.core.findings.Group` produced by the
    Hayabusa panel. ``workspace`` is a case workspace dict; its graph nodes keep their
    tags and any manual edge, and its entities/IOCs add nodes the findings do not
    mention.
    """
    workspace = workspace or {}
    manual = (workspace.get("graph") or {}).get("nodes") or []
    nodes, edges = {}, {}
    order = []

    def node(node_id, label, kind, **extra):
        if node_id in nodes:
            return nodes[node_id]
        if len(nodes) >= max_nodes:
            raise ValueError(
                "The attack graph is too large; filter the findings before building it"
            )
        entry = dict(id=node_id, label=label, kind=kind, tags=[], auto=True)
        entry.update({key: value for key, value in extra.items() if value not in (None, "")})
        nodes[node_id] = entry
        order.append(node_id)
        return entry

    def edge(source, target, label=""):
        key = (source, target, label)
        if source not in nodes or target not in nodes:
            return
        edges[key] = dict(source=source, target=target, label=label)

    stages = {}
    hosts = {}
    for group in findings:
        host_label = str(getattr(group, "host", "") or "").strip() or "unattributed host"
        host = hosts.get(host_label.casefold())
        if host is None:
            host = hosts[host_label.casefold()] = node(
                "host:" + _slug(host_label), host_label, "host"
            )
        stage = tactic_name(getattr(group, "tactics", ""))
        tactic_node = None
        if stage:
            tactic_node = stages.get(stage) or node(
                "stage:" + _slug(stage), stage, "stage", order=TACTICS.index(stage)
            )
            stages[stage] = tactic_node
        for code, label in _techniques(getattr(group, "techniques", "")):
            technique = node("technique:" + _slug(code), label, "technique", code=code)
            if tactic_node is not None:
                edge(technique["id"], tactic_node["id"], "tactic")
            edge(host["id"], technique["id"], "alert")
        if not getattr(group, "techniques", ""):
            edge(host["id"], host["id"], "")  # self edges are never drawn

    for entity in workspace.get("entities") or []:
        kind = entity.get("kind")
        if kind not in ("machine", "account"):
            continue
        # A declared machine is the same node as the host a finding names: one host must
        # not appear twice because the analyst spelled it in the case as well. The label
        # is matched before the hostname, since ``SRV01`` and ``SRV01.corp.local`` are
        # the same machine written two ways.
        prefix = "host" if kind == "machine" else "account"
        label = entity.get("label") or entity.get("hostname") or ""
        existing = None
        for candidate in (entity.get("label"), entity.get("hostname")):
            if candidate and str(candidate).strip().casefold() in hosts:
                existing = hosts[str(candidate).strip().casefold()]
                break
        node_id = existing["id"] if existing is not None else prefix + ":" + _slug(label)
        entry = node(node_id, label, prefix)
        entry["tags"] = list(entity.get("tags") or [])
        entry["auto"] = False

    for ioc in workspace.get("iocs") or []:
        entry = node(
            "ioc:" + _slug(ioc.get("kind") + "-" + ioc.get("value")),
            ioc.get("value"),
            "ioc",
            code=ioc.get("kind"),
        )
        entry["level"] = ioc.get("status")
        machine = str(ioc.get("machine") or "").strip().casefold()
        if machine:
            target = hosts.get(machine) or next(
                (item for key, item in hosts.items() if key == machine), None
            )
            if target is not None:
                edge(entry["id"], target["id"], "observed on")

    # The analyst's own nodes keep their tags, position and kind.
    for entry in manual:
        node_id = entry.get("id")
        if not node_id:
            continue
        current = nodes.get(node_id)
        if current is None:
            if len(nodes) >= max_nodes:
                continue
            current = nodes[node_id] = dict(
                id=node_id,
                label=entry.get("label") or node_id,
                kind=entry.get("kind") if entry.get("kind") in NODE_KINDS else "custom",
                tags=list(entry.get("tags") or []),
                auto=False,
            )
            order.append(node_id)
        else:
            current["tags"] = list(entry.get("tags") or current.get("tags") or [])
            current["auto"] = False
            if entry.get("label"):
                current["label"] = entry["label"]
            if entry.get("kind") in NODE_KINDS:
                current["kind"] = entry["kind"]
        for field in ("x", "y"):
            if entry.get(field) is not None:
                current[field] = entry[field]

    for entry in (workspace.get("graph") or {}).get("edges") or []:
        edge(entry.get("source"), entry.get("target"), entry.get("label") or "")

    return dict(
        nodes=[nodes[item] for item in order],
        edges=[edges[key] for key in sorted(edges, key=lambda item: (item[0], item[1], item[2]))],
    )


def layout(graph, *, column=260, row=66, margin=30):
    """Deterministic positions: kill chain across, identifier order down.

    A tactic owns one column and its technique nodes sit above its stage node, so the
    picture reads left to right like the chain and each column is one step of it.
    Nodes an analyst moved keep their stored position.
    """
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    stages = sorted(
        [item for item in nodes if item.get("kind") == "stage"],
        key=lambda item: (item.get("order", 99), item["id"]),
    )
    stage_column = {item["id"]: index for index, item in enumerate(stages)}
    technique_stage = {}
    for edge in edges:
        if edge.get("target") in stage_column and str(edge.get("source", "")).startswith(
            "technique:"
        ):
            technique_stage[edge["source"]] = stage_column[edge["target"]]
    counters = {}
    for entry in sorted(nodes, key=lambda item: (item.get("kind") != "stage", item["id"])):
        if entry.get("x") is not None and entry.get("y") is not None:
            continue
        kind = entry.get("kind")
        if kind == "ioc":
            column_index = -1
        elif kind in ("host", "account"):
            column_index = 0
        elif kind == "stage":
            column_index = 1 + stage_column.get(entry["id"], len(stages))
        elif kind == "technique":
            column_index = 1 + technique_stage.get(entry["id"], len(stages))
        else:
            column_index = 1 + len(stages)
        row_index = counters.get(column_index, 0)
        counters[column_index] = row_index + 1
        entry["x"] = margin + column_index * column
        entry["y"] = margin + row_index * row
    return graph


NAVIGATOR_VERSIONS = dict(attack="16", navigator="4.9.1", layer="4.5")


def tactic_slug(name):
    """The spelling the Navigator uses: 'Command and Control' becomes command-and-control."""
    return re.sub(r"[^a-z0-9]+", "-", str(name or "").casefold()).strip("-")


def navigator_layer(graph, *, name="Fireblade", description="", case=""):
    """A MITRE ATT&CK Navigator layer holding the techniques this case actually saw.

    Only what the findings declare goes in: a technique identifier and the hosts an alert
    named for it. The score is the number of hosts, so the layer's colour says how widely
    a technique spread rather than how often a rule fired. A node that is not a technique
    is never written: the Navigator reads technique identifiers and nothing else.
    """
    nodes = {node["id"]: node for node in graph.get("nodes", [])}
    hosts_of, stages = {}, {}
    for edge in graph.get("edges", []):
        source, target = nodes.get(edge.get("source")), nodes.get(edge.get("target"))
        if not source or not target:
            continue
        if edge.get("label") == "alert" and target.get("kind") == "technique":
            hosts_of.setdefault(target["id"], {"code": target.get("code", ""), "hosts": set()})
            if source.get("kind") in ("host", "account"):
                hosts_of[target["id"]]["hosts"].add(source.get("label", ""))
        elif edge.get("label") == "tactic" and source.get("kind") == "technique":
            stages[source["id"]] = tactic_slug(target.get("label", ""))
    techniques = []
    for node_id, found in hosts_of.items():
        code = found["code"]
        if not code or not _TECHNIQUE.fullmatch(code):
            continue
        hosts = sorted(host for host in found["hosts"] if host)
        entry = dict(
            techniqueID=code,
            enabled=True,
            score=min(100, max(20, len(hosts) * 20)),
            comment="Seen on: "
            + (", ".join(hosts[:12]) + ("…" if len(hosts) > 12 else "") or "no host named"),
            metadata=[dict(name="Hosts", value=", ".join(hosts))],
        )
        if stages.get(node_id):
            entry["tactic"] = stages[node_id]
        techniques.append(entry)
    techniques.sort(key=lambda item: (item.get("tactic", ""), item["techniqueID"]))
    highest = max((item["score"] for item in techniques), default=20)
    layer = dict(
        name=name,
        versions=dict(NAVIGATOR_VERSIONS),
        domain="enterprise-attack",
        description=description or "Techniques observed in the case, as Fireblade read them.",
        techniques=techniques,
        gradient=dict(colors=["#ffe8cc", "#8b320c"], minValue=20, maxValue=highest),
        legendItems=[dict(label="Hosts an alert named for the technique", color="#8b320c")],
        hideDisabled=True,
        showTacticRowBackground=False,
        metadata=[dict(name="Source", value="Fireblade")],
    )
    if case:
        layer["metadata"].append(dict(name="Case", value=str(case)))
    return layer


def tags_of(graph, node_id):
    return next(
        (list(item.get("tags") or []) for item in graph.get("nodes", []) if item["id"] == node_id),
        [],
    )


def to_svg(graph, *, width=960, height=None, background="#ffffff"):
    """A standalone SVG of the graph, for a report or an export that is not a screenshot."""
    layout(graph)
    nodes = graph.get("nodes", [])
    if not nodes:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="120" '
            f'viewBox="0 0 {width} 120"><rect width="100%" height="100%" fill="{background}"/>'
            '<text x="20" y="60" font-family="Segoe UI,Arial" font-size="14" fill="#4f6074">'
            "No node in the attack graph.</text></svg>"
        )
    min_x = min(item.get("x", 0) for item in nodes) - 30
    min_y = min(item.get("y", 0) for item in nodes) - 30
    max_x = max(item.get("x", 0) for item in nodes) + 260
    max_y = max(item.get("y", 0) for item in nodes) + 70
    height = height or max(160, int(max_y - min_y + 30))
    scale = min(1.0, width / max(1, max_x - min_x))
    positions = {
        item["id"]: ((item.get("x", 0) - min_x) * scale, (item.get("y", 0) - min_y) * scale)
        for item in nodes
    }
    colours = {
        "host": "#174b73",
        "account": "#2f6f8f",
        "technique": "#8b320c",
        "stage": "#3f6b3f",
        "ioc": "#6b3f8b",
        "custom": "#4f6074",
    }
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="Segoe UI,Arial" font-size="11">',
        f'<rect width="100%" height="100%" fill="{background}"/>',
    ]
    for edge in graph.get("edges", []):
        start, end = positions.get(edge["source"]), positions.get(edge["target"])
        if not start or not end or start == end:
            continue
        parts.append(
            f'<line x1="{start[0]:.0f}" y1="{start[1]:.0f}" x2="{end[0]:.0f}" y2="{end[1]:.0f}" '
            f'stroke="#b8c6d4" stroke-width="1"/>'
        )
    for item in nodes:
        x, y = positions[item["id"]]
        colour = colours.get(item.get("kind"), "#4f6074")
        label = html.escape(str(item.get("label", ""))[:48])
        tags = item.get("tags") or []
        box_width = 150 if item.get("kind") == "stage" else 170
        parts.append(
            f'<rect x="{x:.0f}" y="{y - 20:.0f}" width="{box_width}" height="{34 if not tags else 46}" '
            f'rx="6" fill="#ffffff" stroke="{colour}" stroke-width="1.5"/>'
        )
        parts.append(
            f'<text x="{x + 8:.0f}" y="{y - 4:.0f}" fill="{colour}" font-weight="bold">{label}</text>'
        )
        if tags:
            parts.append(
                f'<text x="{x + 8:.0f}" y="{y + 14:.0f}" fill="#4f6074" font-size="9">'
                + html.escape(", ".join(tags)[:40])
                + "</text>"
            )
    parts.append("</svg>")
    return "".join(parts)
