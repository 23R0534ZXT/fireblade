"""Evidence provenance and row review metadata shared by the Host grids."""

import json
import re
from bisect import bisect_right
from collections import defaultdict
from hashlib import sha256
from pathlib import Path

from fireblade.core import case_workspace as ws
from fireblade.core.models import View

LNK_CLOCKS = {
    "sourcecreated": "Creation time of the shortcut file read by the parser.",
    "sourcemodified": "Last modification of the shortcut file read by the parser.",
    "sourceaccessed": "Last access recorded for the shortcut file read by the parser.",
    "targetcreated": "Target creation time recorded inside the shortcut.",
    "targetmodified": "Target modification time recorded inside the shortcut.",
    "targetaccessed": "Target access time recorded inside the shortcut.",
    "trackercreatedon": "Tracker identifier timestamp from the shortcut's tracking block.",
}
RECMD_BATCH_OUTPUT = re.compile(r"(?:\d{14}_)?RECmd_Batch_(.+)_Output\.csv", re.I)


def _recmd_fields(columns):
    if {"category", "description", "hivepath", "keypath"} <= columns.keys():
        fields = {
            "category": "category",
            "rule": "description",
            "hive": "hivepath",
            "key": "keypath",
            "value": "valuename",
        }
    elif {"batchkeypath", "batchvaluename"} <= columns.keys():
        fields = {"hive": "hivepath", "key": "batchkeypath", "value": "batchvaluename"}
    else:
        return {}
    return {role: columns[name] for role, name in fields.items() if name in columns}


def recmd_columns(headers):
    """The raw column indexes in a RECmd batch or plugin export."""
    columns = {}
    for index, name in enumerate(headers):
        columns.setdefault(re.sub(r"[^a-z0-9]", "", name.casefold()), index)
    return _recmd_fields(columns)


def recmd_batch_name(*paths):
    for path in paths:
        name = str(path or "").replace("\\", "/").rsplit("/", 1)[-1]
        if match := RECMD_BATCH_OUTPUT.fullmatch(name):
            return match[1] + ".reb"
    return None


def date_help(headers):
    normalized = [re.sub(r"[^a-z0-9]", "", name.casefold()) for name in headers]
    if not {"sourcecreated", "targetcreated"}.issubset(normalized):
        return {}
    return {name: LNK_CLOCKS[key] for name, key in zip(headers, normalized) if key in LNK_CLOCKS}


def organized(case):
    return (
        case.sparse
        or case.info.get("parser") == "organized"
        or "/results/organisation-" in str(case.info.get("path", "")).replace("\\", "/")
    )


def provenance(case, values):
    info = case.info
    lookup = dict(zip(case.headers, values))
    is_organized = organized(case)
    row_file = values[1] if is_organized and len(values) > 1 else None
    reader = (values[2] if is_organized and len(values) > 2 else None) or info.get("parser")
    by_name = {re.sub(r"[^a-z0-9]", "", key.casefold()): value for key, value in lookup.items()}
    evidence_file = next(
        (
            by_name[key]
            for key in ("hivepath", "sourcefile", "sourcefilename", "firebladeevtxsource")
            if by_name.get(key)
        ),
        None,
    )
    source = row_file or info.get("path") or ""
    batch = recmd_batch_name(info.get("working_path"), source)
    fields = _recmd_fields(by_name)
    recmd_row = (
        reader == "RECmd"
        or bool(batch)
        or (
            bool(fields)
            and reader in (None, "native")
            and (not is_organized or bool(fields.get("hive") and fields.get("key")))
        )
    )
    recmd = {
        field: fields[field]
        for field in ("category", "rule", "hive")
        if recmd_row and fields.get(field)
    }
    return {
        "file": source,
        "recorded_file": evidence_file
        if evidence_file not in (source, recmd.get("hive"))
        else None,
        "reader": "RECmd" if recmd_row else reader,
        "batch": batch or ("Kroll_Batch.reb" if reader == "RECmd" else None),
        "recmd": recmd,
        "working_file": info.get("working_path") if not is_organized else None,
    }


def source_ranges(case):
    """The ranges of original records that make up an analysis."""
    info = case.info
    references = info.get("row_sources") or []
    if case.sparse:
        manifest = Path(str(info.get("path", "")).replace("\\", "/"))
        if not manifest.is_file():
            manifest = case.path.parent.parent / "results" / manifest.parent.name / manifest.name
        references = json.loads(manifest.read_text(encoding="utf-8"))["sources"]
    return references or [{"path": str(case.path), "first_row": 1, "rows": info.get("rows", 0)}]


def record_path(library, folder, case, recorded, aliases=None):
    path = Path(recorded.replace("\\", "/"))
    if not path.is_relative_to(folder):
        member = (aliases or {}).get(recorded)
        moved = (folder / member).resolve() if member else None
        if moved and moved.is_relative_to(folder) and moved.is_file():
            path = moved
        else:
            repaired = library._resolve_analysis(case.path.parent, str(path))
            if repaired and Path(repaired).is_relative_to(folder):
                path = Path(repaired)
    return path.relative_to(folder).as_posix() if path.is_relative_to(folder) else path.name


def portable_aliases(folder):
    manifest = folder / "package-provenance.json"
    if not manifest.is_file():
        return {}
    return json.loads(manifest.read_text(encoding="utf-8")).get("relocation", {})


def record_keys(library, folder, case, row_ids):
    """Map grid positions to original analysis paths and row numbers."""
    references = source_ranges(case)
    starts = [item["first_row"] for item in references]
    paths = {}
    aliases = portable_aliases(folder)
    result = {}
    for row in row_ids:
        position = bisect_right(starts, row) - 1
        if position < 0 or row >= starts[position] + references[position]["rows"]:
            continue
        recorded = references[position]["path"]
        if recorded not in paths:
            paths[recorded] = record_path(library, folder, case, recorded, aliases)
        result[row] = paths[recorded], row - starts[position] + 1
    return result


def marks(library, folder, case, row_ids):
    if not ws.path_of(folder).is_file():
        return {}
    saved = ws.load(folder).get("row_marks", {})
    if not saved:
        return {}
    return {
        row: mark
        for row, (record, line) in record_keys(library, folder, case, row_ids).items()
        if (mark := saved.get(record, {}).get(str(line)))
    }


def save_mark(library, folder, case, row, code, label, expected):
    if type(row) is not int or not 1 <= row <= case.info.get("rows", 0):
        raise ValueError("Choose an evidence row.")
    code = ws._text(code, "Mark code", 8, allow_empty=True)
    label = ws._text(label, "Mark label", 80, allow_empty=True)
    keys = record_keys(library, folder, case, [row])
    if row not in keys:
        raise ValueError("The original record could not be located.")
    record, line = keys[row]

    def change(data):
        bucket = data.setdefault("row_marks", {})
        current = bucket.get(record, {}).get(str(line), {})
        if current.get("code", "") != expected:
            return
        if code:
            with case.operation():
                values = case.rows_by_ids([row])[row][1:]
            origin = provenance(case, values)
            machines = {"computer", "computername", "hostname", "host", "machine", "devicename"}
            machine = next(
                (
                    str(value)[:200]
                    for field, value in zip(case.headers, values)
                    if field.casefold() in machines and value
                ),
                "",
            )
            mark = {
                "code": code,
                "label": label or code,
                "file": origin["file"],
                "machine": machine,
            }
            bucket.setdefault(record, {})[str(line)] = mark
            return
        if record in bucket:
            bucket[record].pop(str(line), None)
            if not bucket[record]:
                del bucket[record]

    saved = ws.mutate(folder, change)
    return saved.get("row_marks", {}).get(record, {}).get(str(line), {})


def facets(case, column, view=None, path=(), text="", offset=0):
    if not 0 <= column < len(case.headers):
        raise ValueError("Choose a column in this analysis.")
    value = f"coalesce(CAST({case.column(column)} AS VARCHAR), '')"
    where, args = case.where(view or View(), path)
    if text:
        where += (" AND " if where else " WHERE ") + f"contains(lower({value}), lower(?))"
        args.append(text)
    offset = max(0, int(offset))
    with case.operation():
        rows = case.db.execute(
            f"SELECT {value} AS value, count(*) AS hits FROM events{where} "
            "GROUP BY 1 ORDER BY hits DESC, value LIMIT 101 OFFSET ?",
            [*args, offset],
        ).fetchall()
    return {"values": rows[:100], "next": offset + 100 if len(rows) > 100 else None}


def graph_tags(graph, workspace):
    """Group saved observations and grid marks by their analyst-assigned labels."""
    groups = defaultdict(list)
    for event in workspace.get("evidence_events", []):
        for tag in event["tags"]:
            origin = event["origin"]
            groups[tag].append(
                {
                    "description": event["description"],
                    "file": origin["file"],
                    "line": origin["line"],
                    "machine": event["machine"],
                    "event": event["id"],
                }
            )
    for record, entries in workspace.get("row_marks", {}).items():
        for row, mark in entries.items():
            label = mark["label"]
            tag = mark["code"] if label == mark["code"] else f"{mark['code']} · {label}"
            groups[tag].append(
                {
                    "record": record,
                    "file": mark["file"],
                    "line": int(row),
                    "machine": mark.get("machine", ""),
                }
            )
    hosts = {
        node["label"].casefold(): node["id"] for node in graph["nodes"] if node["kind"] == "host"
    }
    limit = 200
    for tag, items in sorted(
        groups.items(), key=lambda entry: (-len(entry[1]), entry[0].casefold())
    )[:limit]:
        identifier = "tag:" + sha256(tag.encode()).hexdigest()[:24]
        graph["nodes"].append(
            {
                "id": identifier,
                "kind": "tag",
                "label": tag,
                "tags": [tag],
                "auto": False,
                "records": len(items),
                "evidence": {
                    "what": f"{len(items)} record(s) with this saved tag or mark.",
                    "how": "Recorded by the analyst on evidence rows.",
                    "records": items[:50],
                    "records_total": len(items),
                },
            }
        )
        targets = {hosts.get(item.get("machine", "").casefold()) for item in items}
        for target in sorted(targets - {None}):
            graph["edges"].append(
                {
                    "id": f"{identifier}>{target}",
                    "source": identifier,
                    "target": target,
                    "label": "tagged on",
                    "evidence": {"what": tag, "how": "The saved observation names this machine."},
                }
            )
    return max(0, len(groups) - limit)
