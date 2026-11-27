"""The operational record of a case: client, machines, actions, IOCs and graph tags.

``case.json`` is the catalogue manifest and stays small: it is read for every
listing, validated strictly and versioned by history. The work an analyst does
*during* an engagement — who owes what, which machine is being analysed for which
client, which indicator was confirmed, which node of the attack graph carries the
"persistence" tag — belongs to a separate file, written far more often and never
needed to draw the catalogue.

``<case>/workspace.json`` is that file. One format version, bounded sizes, an atomic
replace and a revision that refuses a stale overwrite: two windows on the same case
are already refused by the case lease, so the revision only has to catch a save built
from a copy the analyst has since left behind.

Every writer goes through :func:`save`; the helpers below are conveniences over the
same validated structure, not a second storage path.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock

from fireblade.core.layout import write_json

FORMAT = "fireblade-workspace"
VERSION = 1
FILENAME = "workspace.json"
MAX_BYTES = 8 * 1024 * 1024
_MUTATION_LOCKS = tuple(RLock() for _ in range(64))

OWNERS = ("us", "client", "third_party", "vendor", "unassigned")
STATUSES = ("todo", "in_progress", "waiting_client", "waiting_us", "blocked", "done", "cancelled")
PRIORITIES = ("low", "medium", "high", "critical")
ENTITY_KINDS = ("machine", "account", "domain", "mailbox", "share")
ACTION_TYPES = (
    "collect",
    "analysis",
    "remediation",
    "coordination",
    "meeting",
    "report",
    "destruction",
    "legal",
    "other",
)
IOC_STATUSES = ("new", "confirmed", "benign", "unknown")
NODE_KINDS = ("host", "account", "technique", "stage", "ioc", "custom")

LIMITS = dict(
    actions=2000,
    iocs=5000,
    entities=1000,
    nodes=2000,
    edges=4000,
    tags=20,
    tag_length=40,
    destruction=500,
)


def stamp():
    return datetime.now(UTC).isoformat()


def identifier():
    return uuid.uuid4().hex


def _text(value, field, maximum, *, allow_empty=False):
    if not isinstance(value, str):
        raise ValueError(f"{field} must be text")
    value = value.strip()
    if not value and not allow_empty:
        raise ValueError(f"{field} is required")
    if len(value) > maximum or "\0" in value:
        raise ValueError(f"{field} is limited to {maximum} characters on one line")
    return value


def _choice(value, field, allowed):
    if value not in allowed:
        raise ValueError(f"{field} must be one of: " + ", ".join(allowed))
    return value


def _date(value, field):
    if value in (None, ""):
        return None
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError(f"{field} must be an ISO date")
    try:
        datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO date") from exc
    return value


def _tags(value):
    if value in (None, ""):
        return []
    if not isinstance(value, list) or len(value) > LIMITS["tags"]:
        raise ValueError(f"At most {LIMITS['tags']} tags are allowed")
    result = []
    for item in value:
        tag = _text(item, "Tag", LIMITS["tag_length"])
        if tag.casefold() not in [existing.casefold() for existing in result]:
            result.append(tag)
    return result


def empty(revision=None):
    """A fresh, valid workspace for one case."""
    return dict(
        format=FORMAT,
        version=VERSION,
        revision=revision or identifier(),
        updated=stamp(),
        client=dict(name="", reference="", sector="", contact=""),
        engagement=dict(contract="", lead="", start=None, end=None, notes=""),
        entities=[],
        actions=[],
        iocs=[],
        tags=[],
        graph=dict(nodes=[], edges=[]),
        destruction=[],
    )


def data_folder(folder):
    """Where the case's operational files live.

    A case imported from a portable archive keeps what it did not know how to place under
    ``case-extra/`` (that is the archive's documented layout, and the test suite asserts
    it). The workspace must be read and written there rather than at the top level, or a
    portable case would reopen with its actions and indicators apparently gone.
    """
    folder = Path(folder)
    extra = folder / "case-extra"
    if (
        not (folder / FILENAME).exists()
        and extra.is_dir()
        and not extra.is_symlink()
        and (extra / FILENAME).exists()
    ):
        return extra
    return folder


def path_of(folder):
    return data_folder(folder) / FILENAME


def load(folder):
    """The workspace of a case, or a fresh one when the case has never had one.

    A missing file is not an error: the analyst may have opened a case created by an
    earlier version. A *corrupt* file is an error, because silently starting from an
    empty workspace would hide the actions already recorded.
    """
    path = path_of(folder)
    if not path.exists():
        return empty()
    if path.is_symlink():
        raise ValueError("The case workspace file is a link")
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("The case workspace is limited to 8 MiB")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("The case workspace cannot be read: " + str(exc)) from exc
    validate(data)
    return data


def validate(data):
    if not isinstance(data, dict):
        raise ValueError("Invalid case workspace")
    if data.get("format") != FORMAT or data.get("version") != VERSION:
        raise ValueError("Invalid case workspace format")
    if not isinstance(data.get("revision"), str) or not re.fullmatch(
        r"[0-9a-f]{32}", data["revision"]
    ):
        raise ValueError("Invalid case workspace revision")
    if not isinstance(data.get("updated"), str) or len(data["updated"]) > 50:
        raise ValueError("Invalid case workspace date")
    datetime.fromisoformat(data["updated"])

    client = data.get("client")
    if not isinstance(client, dict):
        raise ValueError("Invalid client record")
    for field, maximum in (("name", 200), ("reference", 120), ("sector", 120), ("contact", 300)):
        _text(client.get(field, ""), "Client " + field, maximum, allow_empty=True)

    engagement = data.get("engagement")
    if not isinstance(engagement, dict):
        raise ValueError("Invalid engagement record")
    _text(engagement.get("contract", ""), "Engagement contract", 120, allow_empty=True)
    _text(engagement.get("lead", ""), "Engagement lead", 200, allow_empty=True)
    _text(engagement.get("notes", ""), "Engagement notes", 8000, allow_empty=True)
    _date(engagement.get("start"), "Engagement start")
    _date(engagement.get("end"), "Engagement end")

    entities = data.get("entities")
    if not isinstance(entities, list) or len(entities) > LIMITS["entities"]:
        raise ValueError("Invalid entity list")
    seen = set()
    for entry in entities:
        if not isinstance(entry, dict):
            raise ValueError("Invalid entity")
        key = _key(entry)
        if key in seen:
            raise ValueError("Duplicate entity identifier")
        seen.add(key)
        _choice(entry.get("kind"), "Entity kind", ENTITY_KINDS)
        _text(entry.get("label"), "Entity label", 200)
        for field, maximum in (("hostname", 200), ("ip", 200), ("os", 120), ("notes", 4000)):
            _text(entry.get(field, ""), "Entity " + field, maximum, allow_empty=True)
        _tags(entry.get("tags"))

    actions = data.get("actions")
    if not isinstance(actions, list) or len(actions) > LIMITS["actions"]:
        raise ValueError("Invalid action list")
    seen.clear()
    for entry in actions:
        if not isinstance(entry, dict):
            raise ValueError("Invalid action")
        key = _key(entry)
        if key in seen:
            raise ValueError("Duplicate action identifier")
        seen.add(key)
        _text(entry.get("title"), "Action title", 200)
        _text(entry.get("detail", ""), "Action detail", 8000, allow_empty=True)
        _choice(entry.get("owner"), "Action owner", OWNERS)
        _choice(entry.get("status"), "Action status", STATUSES)
        _choice(entry.get("priority"), "Action priority", PRIORITIES)
        _choice(entry.get("type", "other"), "Action type", ACTION_TYPES)
        _text(entry.get("intervenant", ""), "Action intervenant", 200, allow_empty=True)
        _date(entry.get("date"), "Action date")
        _date(entry.get("due"), "Action due date")
        for field, maximum in (("case", 32), ("machine", 200), ("reference", 120), ("closed", 50)):
            _text(entry.get(field, "") or "", "Action " + field, maximum, allow_empty=True)
        _tags(entry.get("tags"))
        iocs = entry.get("iocs", [])
        if not isinstance(iocs, list) or len(iocs) > 500:
            raise ValueError("Invalid action indicators")

    iocs = data.get("iocs")
    if not isinstance(iocs, list) or len(iocs) > LIMITS["iocs"]:
        raise ValueError("Invalid indicator list")
    seen.clear()
    for entry in iocs:
        if not isinstance(entry, dict):
            raise ValueError("Invalid indicator")
        key = _key(entry)
        if key in seen:
            raise ValueError("Duplicate indicator identifier")
        seen.add(key)
        if entry.get("kind") not in ("ip", "domain", "url", "md5", "sha1", "sha256", "sha512"):
            raise ValueError("Indicator kind is not supported")
        _text(entry.get("value"), "Indicator value", 8192)
        _text(entry.get("label", ""), "Indicator label", 2000, allow_empty=True)
        _text(entry.get("source", ""), "Indicator source", 200, allow_empty=True)
        _choice(entry.get("status", "new"), "Indicator status", IOC_STATUSES)
        _tags(entry.get("tags"))

    graph = data.get("graph")
    if (
        not isinstance(graph, dict)
        or not isinstance(graph.get("nodes"), list)
        or not isinstance(graph.get("edges"), list)
    ):
        raise ValueError("Invalid attack graph")
    if len(graph["nodes"]) > LIMITS["nodes"] or len(graph["edges"]) > LIMITS["edges"]:
        raise ValueError("The attack graph is too large")
    node_ids = set()
    for node in graph["nodes"]:
        if not isinstance(node, dict):
            raise ValueError("Invalid graph node")
        node_id = _text(node.get("id"), "Graph node identifier", 200)
        if node_id in node_ids:
            raise ValueError("Duplicate graph node identifier")
        node_ids.add(node_id)
        _text(node.get("label"), "Graph node label", 200)
        _choice(node.get("kind"), "Graph node kind", NODE_KINDS)
        _tags(node.get("tags"))
        for field in ("x", "y"):
            value = node.get(field)
            if value is not None and (
                not isinstance(value, (int, float)) or not -100000 <= value <= 100000
            ):
                raise ValueError("Invalid graph node position")
    for edge in graph["edges"]:
        if (
            not isinstance(edge, dict)
            or not isinstance(edge.get("source"), str)
            or not isinstance(edge.get("target"), str)
        ):
            raise ValueError("Invalid graph edge")
        if edge["source"] not in node_ids or edge["target"] not in node_ids:
            raise ValueError("Graph edge refers to an unknown node")
        _text(edge.get("label", ""), "Graph edge label", 120, allow_empty=True)

    destruction = data.get("destruction")
    if not isinstance(destruction, list) or len(destruction) > LIMITS["destruction"]:
        raise ValueError("Invalid destruction record list")
    for entry in destruction:
        if not isinstance(entry, dict):
            raise ValueError("Invalid destruction record")
        _key(entry)
        _text(entry.get("method"), "Destruction method", 40)
        for field in ("started", "finished"):
            _date(entry.get(field), "Destruction " + field)
        if not isinstance(entry.get("files"), list):
            raise ValueError("Invalid destruction file list")
        _tags(entry.get("tags"))

    if len(json.dumps(data, ensure_ascii=False).encode("utf-8")) > MAX_BYTES:
        raise ValueError("The case workspace is limited to 8 MiB")


def _key(entry):
    value = entry.get("id")
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{32}", value):
        raise ValueError("Identifier must be 32 hexadecimal characters")
    return value


def save(folder, data, expected_revision=None):
    """Validate, bump and atomically replace the workspace file."""
    data = json.loads(json.dumps(data))  # snapshot: callers keep their own copy
    if expected_revision is not None and data.get("revision") != expected_revision:
        raise ValueError("This case was changed elsewhere. Reopen it before saving.")
    data["revision"] = identifier()
    data["updated"] = stamp()
    validate(data)
    write_json(path_of(folder), data)
    return data


def mutate(folder, change, expected_revision=None):
    """Read, apply ``change(data)``, validate and save in one step."""
    with _MUTATION_LOCKS[hash(Path(folder).resolve()) % len(_MUTATION_LOCKS)]:
        data = load(folder)
        if (
            expected_revision is not None
            and path_of(folder).exists()
            and data["revision"] != expected_revision
        ):
            raise ValueError("This case was changed elsewhere. Reopen it before saving.")
        change(data)
        return save(folder, data)


# ------------------------------------------------------------------ conveniences
def add_entity(folder, kind, label, **fields):
    entry = dict(
        id=identifier(),
        kind=_choice(kind, "Entity kind", ENTITY_KINDS),
        label=_text(label, "Entity label", 200),
        hostname="",
        ip="",
        os="",
        notes="",
        tags=[],
        created=stamp(),
    )
    entry.update(
        {
            key: value
            for key, value in fields.items()
            if key in ("hostname", "ip", "os", "notes", "tags")
        }
    )
    entry["tags"] = _tags(entry.get("tags"))

    def change(data):
        if len(data["entities"]) >= LIMITS["entities"]:
            raise ValueError("Too many entities in this case")
        data["entities"].append(entry)

    mutate(folder, change)
    return entry


def add_action(folder, title, **fields):
    entry = dict(
        id=identifier(),
        title=_text(title, "Action title", 200),
        detail="",
        owner="us",
        status="todo",
        priority="medium",
        type="other",
        intervenant="",
        date=stamp()[:10],
        due=None,
        machine="",
        reference="",
        case="",
        tags=[],
        iocs=[],
        created=stamp(),
        updated=stamp(),
        closed=None,
    )
    allowed = {
        "detail",
        "owner",
        "status",
        "priority",
        "type",
        "intervenant",
        "date",
        "due",
        "machine",
        "reference",
        "case",
        "tags",
        "iocs",
    }
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError("Unknown action fields: " + ", ".join(sorted(unknown)))
    entry.update(fields)
    entry["owner"] = _choice(entry["owner"], "Action owner", OWNERS)
    entry["status"] = _choice(entry["status"], "Action status", STATUSES)
    entry["priority"] = _choice(entry["priority"], "Action priority", PRIORITIES)
    entry["type"] = _choice(entry.get("type", "other"), "Action type", ACTION_TYPES)
    entry["date"] = _date(entry.get("date") or stamp()[:10], "Action date")
    entry["due"] = _date(entry["due"], "Action due date")
    entry["tags"] = _tags(entry.get("tags"))
    if not isinstance(entry.get("iocs", []), list):
        raise ValueError("Action indicators must be a list")

    def change(data):
        if len(data["actions"]) >= LIMITS["actions"]:
            raise ValueError("Too many actions in this case")
        data["actions"].append(entry)

    mutate(folder, change)
    return entry


def update_action(folder, action_id, **fields):
    allowed = {
        "title",
        "detail",
        "owner",
        "status",
        "priority",
        "type",
        "intervenant",
        "date",
        "due",
        "machine",
        "reference",
        "tags",
        "iocs",
    }
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError("Unknown action fields: " + ", ".join(sorted(unknown)))

    def change(data):
        entry = next((item for item in data["actions"] if item["id"] == action_id), None)
        if entry is None:
            raise ValueError("This action no longer exists")
        if "status" in fields and fields["status"] != entry["status"]:
            entry["closed"] = stamp() if fields["status"] in ("done", "cancelled") else None
        entry.update(fields)
        entry["updated"] = stamp()

    return mutate(folder, change)


def remove_action(folder, action_id):
    def change(data):
        before = len(data["actions"])
        data["actions"][:] = [item for item in data["actions"] if item["id"] != action_id]
        if len(data["actions"]) == before:
            raise ValueError("This action no longer exists")

    return mutate(folder, change)


def add_ioc(folder, value, kind=None, label="", **fields):
    """A tracked indicator, normalised by the same code the hunt uses."""
    from fireblade.core.ioc_hunt import indicator

    parsed = indicator(value, kind or "", label)
    entry = dict(
        id=identifier(),
        kind=parsed.kind,
        value=parsed.value,
        raw=parsed.raw,
        label=parsed.label,
        source="",
        status="new",
        tags=[],
        machine="",
        case="",
        added=stamp(),
    )
    allowed = {"source", "status", "tags", "machine", "case", "label"}
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError("Unknown indicator fields: " + ", ".join(sorted(unknown)))
    entry.update(fields)
    _choice(entry["status"], "Indicator status", IOC_STATUSES)
    entry["tags"] = _tags(entry.get("tags"))

    def change(data):
        if len(data["iocs"]) >= LIMITS["iocs"]:
            raise ValueError("Too many indicators in this case")
        if any(
            item["kind"] == entry["kind"] and item["value"] == entry["value"]
            for item in data["iocs"]
        ):
            raise ValueError("This indicator is already tracked in the case")
        data["iocs"].append(entry)

    mutate(folder, change)
    return entry


def add_iocs(folder, values, source="", case=""):
    """Track many indicators in one write.

    The interactive path saves after every indicator; a list of 50 000 would rewrite the
    workspace file 50 000 times. Here the whole batch is validated, then saved once.
    Existing indicators are skipped rather than refused, so a partially imported list can
    be re-imported without losing what already got in.
    """
    from fireblade.core.ioc_hunt import indicator

    entries, skipped = [], 0
    seen = {(item["kind"], item["value"]) for item in load(folder)["iocs"]}
    for value in values:
        try:
            parsed = indicator(value)
        except (ValueError, UnicodeError):
            skipped += 1
            continue
        key = (parsed.kind, parsed.value)
        if key in seen:
            skipped += 1
            continue
        seen.add(key)
        entries.append(
            dict(
                id=identifier(),
                kind=parsed.kind,
                value=parsed.value,
                raw=parsed.raw,
                label=parsed.label,
                source=source[:200],
                status="new",
                tags=[],
                machine="",
                case=case,
                added=stamp(),
            )
        )
    if entries:

        def change(data):
            if len(data["iocs"]) + len(entries) > LIMITS["iocs"]:
                raise ValueError(f"At most {LIMITS['iocs']} indicators per case")
            data["iocs"].extend(entries)

        mutate(folder, change)
    return dict(added=len(entries), skipped=skipped)


def remove_ioc(folder, ioc_id):
    def change(data):
        before = len(data["iocs"])
        data["iocs"][:] = [item for item in data["iocs"] if item["id"] != ioc_id]
        if len(data["iocs"]) == before:
            raise ValueError("This indicator no longer exists")

    return mutate(folder, change)


def tag_node(folder, label, kind="custom", tags=(), position=None, node_id=None):
    """Add tags to a graph node, creating it when the identifier is new.

    ``node_id`` is the identifier the graph builder gives the node
    (``host:srv01``, ``technique:t1059-001``); without it a free node is created from
    the label, so an analyst can add a node the data does not carry.
    """
    node_id = node_id or "custom-" + re.sub(r"[^a-z0-9]+", "-", label.casefold()).strip("-")[:60]

    def change(data):
        node = next((item for item in data["graph"]["nodes"] if item["id"] == node_id), None)
        if node is None:
            if len(data["graph"]["nodes"]) >= LIMITS["nodes"]:
                raise ValueError("The attack graph is too large")
            node = dict(
                id=node_id,
                label=_text(label, "Graph node label", 200),
                kind=_choice(kind, "Graph node kind", NODE_KINDS),
                tags=[],
            )
            if position:
                node["x"], node["y"] = position
            data["graph"]["nodes"].append(node)
        for tag in _tags(list(tags)):
            if tag.casefold() not in [existing.casefold() for existing in node["tags"]]:
                node["tags"].append(tag)

    mutate(folder, change)
    return node_id


def summary(data):
    """Counts the operations board shows without opening the case."""
    actions = data.get("actions", [])
    return dict(
        actions=len(actions),
        open_actions=sum(1 for item in actions if item["status"] not in ("done", "cancelled")),
        overdue=sum(
            1
            for item in actions
            if item["due"] and item["status"] not in ("done", "cancelled") and _overdue(item["due"])
        ),
        iocs=len(data.get("iocs", [])),
        entities=len(data.get("entities", [])),
        graph=len(data.get("graph", {}).get("nodes", [])),
        destroyed=sum(len(item.get("files", [])) for item in data.get("destruction", [])),
    )


def _overdue(value):
    try:
        due = datetime.fromisoformat(value)
    except ValueError:
        return False
    if due.tzinfo is None:
        due = due.replace(tzinfo=UTC)
    return due < datetime.now(UTC)


def collect(root):
    """Every case's workspace, for the cross-case board. Unreadable ones are reported."""
    from fireblade.core.investigations import InvestigationLibrary

    library = InvestigationLibrary(root)
    cases, errors = library.list()
    board = []
    for case in cases:
        folder = library.folder(case["id"])
        record = dict(
            case=case["id"],
            name=case["name"],
            status=case["status"],
            environment=case["environment"],
            workspace=None,
            error=None,
        )
        try:
            record["workspace"] = load(folder)
        except (OSError, ValueError) as exc:
            record["error"] = str(exc)
            errors.append(case["name"] + " : " + str(exc))
        board.append(record)
    return board, errors
