"""Build an evidence-backed scenario from normalized process and network fields."""

import re

from fireblade.web import tracking

ALIASES = {
    "host": ("host", "hostname", "computer", "computername", "devicename"),
    "process": ("processguid",),
    "parent": ("parentprocessguid",),
    "unique": ("processuniqueid",),
    "parent_unique": ("parentprocessuniqueid",),
    "initiator": ("initiatingprocessuniqueid",),
    "provider": ("provider", "providername", "channel"),
    "event": ("eventid", "eventcode", "eventtype", "actiontype"),
    "file": ("targetfilename", "filepath", "filename"),
    "image": ("image", "processname"),
    "remote": ("destinationip", "remoteip", "dstip"),
}
KINDS = {
    "1": "Process creation",
    "processcreated": "Process creation",
    "3": "Network connection",
    "connectionsuccess": "Network connection",
    "filecreated": "File creation",
    "11": "File creation",
}
LIMIT = 1200


def correlate(library, identifier):
    """Follow validated process IDs scoped to a host, with exact source rows."""
    from fireblade.core.timeline import guess_time_columns

    analyses = library._analyses(library.library.read(identifier))
    found = []
    scanned = 0
    examined = 0
    for item in analyses:
        if not item["found"]:
            continue
        case = library._case_for(identifier, item["index"], entry=item)
        with case.lock, case.operation():
            names = {re.sub(r"[^a-z0-9]", "", h.casefold()): i for i, h in enumerate(case.headers)}
            columns = {
                field: next((names[n] for n in alternatives if n in names), None)
                for field, alternatives in ALIASES.items()
            }
            if any(columns[field] is None for field in ("host", "event")):
                continue
            if all(columns[field] is None for field in ("process", "unique", "initiator")):
                continue
            guessed = 3 if case.sparse else guess_time_columns(case.headers)
            columns["time"] = guessed if isinstance(guessed, int) else None
            fields = ", ".join(
                case.column(index) if index is not None else "NULL" for index in columns.values()
            )
            codes = list(KINDS)
            match = case.column(columns["event"])
            query = (
                f"SELECT __row_id, {fields} FROM events "
                f"WHERE lower(replace(trim(CAST({match} AS VARCHAR)), ' ', '')) "
                "IN (SELECT unnest(?::VARCHAR[])) ORDER BY __row_id LIMIT ?"
            )
            rows = case.db.execute(query, [codes, LIMIT + 1 - examined]).fetchall()
            scanned += 1
        examined += len(rows)
        for row_id, *row in rows:
            values = dict(zip(columns, row, strict=True))
            host = str(values["host"] or "").strip()
            code = str(values["event"]).strip().lower().replace(" ", "")
            if code.isdecimal() and "sysmon" not in str(values["provider"] or "").casefold():
                continue
            kind = KINDS[code]
            creation = kind == "Process creation"
            if code.isdecimal() or values["process"]:
                process = process_identity(values["process"], "guid")
                parent = process_identity(values["parent"], "guid")
            else:
                process = process_identity(
                    values["unique"] if creation else values["initiator"], "unique"
                )
                parent = process_identity(values["parent_unique"] or values["initiator"], "unique")
            if not host or not process:
                continue
            detail = (
                values["file"]
                if kind == "File creation"
                else values["remote"]
                if kind == "Network connection"
                else values["image"]
            )
            found.append(
                {
                    "id": f"{item['index']}:{row_id}",
                    "analysis": item["index"],
                    "row": row_id,
                    "source": item["label"],
                    "host": host,
                    "process": process,
                    "parent": parent if creation else "",
                    "kind": kind,
                    "detail": str(detail or "")[:300],
                    "time": str(values["time"] or ""),
                }
            )
        if examined > LIMIT:
            break

    nodes = found[:LIMIT]
    processes = {}
    for node in nodes:
        if node["kind"] == "Process creation":
            processes.setdefault((node["host"].casefold(), node["process"]), []).append(node)
    edges = []
    for node in nodes:
        creation = node["kind"] == "Process creation"
        key = (node["host"].casefold(), node["parent"] if creation else node["process"])
        candidates = processes.get(key, [])
        if len(candidates) != 1:
            continue
        parent = candidates[0]
        start, end = tracking.event_time(parent["time"]), tracking.event_time(node["time"])
        if start and end and bool(start.tzinfo) == bool(end.tzinfo) and start > end:
            continue
        if parent["id"] != node["id"]:
            edges.append(
                {
                    "source": parent["id"],
                    "target": node["id"],
                    "reason": "Parent process ID" if creation else "Same process ID",
                }
            )
    return {"nodes": nodes, "edges": edges, "scanned": scanned, "limited": examined > LIMIT}


def process_identity(value, namespace):
    value = str(value or "").strip().strip("{}").casefold()
    if not value or len(value) > 160 or not value.strip("0-"):
        return ""
    return f"{namespace}:{value}"
