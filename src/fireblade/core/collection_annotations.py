"""Keep row and cell annotations attached to raw records across grid layouts.

Layout row numbers are temporary. Canonical references use a raw analysis, its
original row number and an original column occurrence (or a common metadata field).
Notes on a field absent from another layout stay in the collection until that
field is displayed again; explicit deletions replace the previous annotation.
"""

import json
from pathlib import Path

from fireblade.core.collection_organization import (
    _split_too_wide,
    column_keys,
    source_groups,
)
from fireblade.core.engine import Case
from fireblade.core.sparse_union import FORMAT, PREFIX

ROW = ("row",)


def _ranges(sources):
    result, first = [], 1
    for source in sources:
        count = source["source"]["rows"]
        result.append(dict(path=source["path"], first_row=first, rows=count))
        first += count
    return result


def _layout(collection, document, raw):
    info = document["source"]
    if document["path"] in raw:
        return _ranges([document]), [("field", *key) for key in column_keys(info["headers"])]
    if info.get("storage_format") == FORMAT:
        manifest = json.loads(Path(info["path"]).read_text(encoding="utf-8"))
        if manifest.get("format") != FORMAT:
            raise ValueError("Invalid combined record references")
        references, prefix = manifest["sources"], PREFIX
    elif info.get("row_sources"):
        references, prefix = info["row_sources"], 3
    else:
        # Legacy materialized CSV layouts use the same deterministic grouping
        # and source order. Refuse an unverifiable mapping rather than move a note
        # to a different record that happens to have the same displayed row ID.
        groups = source_groups(collection.report, list(raw.values()))
        groups = _split_too_wide(groups, collection.report.get("organization"), [])
        sources = groups.get(Path(info["path"]).stem)
        if sources is None:
            raise ValueError("Cannot resolve the original records of this older grid")
        references, prefix = _ranges([source for source, _origin in sources]), 3
    first, keys, known = 1, [("metadata", i) for i in range(prefix)], set()
    for reference in references:
        source = raw.get(reference.get("path"))
        if (
            source is None
            or reference.get("first_row") != first
            or reference.get("rows") != source["source"]["rows"]
        ):
            raise ValueError("Inconsistent original record references")
        first += reference["rows"]
        for key in column_keys(source["source"]["headers"]):
            if key not in known:
                known.add(key)
                keys.append(("field", *key))
    if first - 1 != info["rows"] or len(keys) != len(info["headers"]):
        raise ValueError("The grid's original records or columns do not match")
    return references, keys


def capture(collection):
    """Read the current views before reorganization; never edit their notes."""
    saved = {
        (item["source"], item["row"], tuple(item["field"])): item["note"]
        for item in collection.report.get("row_annotations", [])
    }
    raw = {
        item["path"]: item
        for item in collection.report.get("raw_documents") or collection.report["documents"]
    }
    for document in collection.report["documents"]:
        case = Case(document["path"], settings=collection.settings, read_only=True)
        try:
            columns = {
                row[0]
                for row in case.db.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_name='bookmarks'"
                ).fetchall()
            }
            column = "column_id" if "column_id" in columns else "-1"
            notes = case.db.execute(f"SELECT row_id,{column},note FROM bookmarks").fetchall()
            if not notes and not saved:
                continue
            references, keys = _layout(collection, document, raw)
            keys += [("derived", definition["name"]) for definition in case.derived]
            represented = set(keys) | {ROW}
            paths = {reference["path"] for reference in references}
            saved = {
                key: value
                for key, value in saved.items()
                if key[0] not in paths or key[2] not in represented
            }
            for row, column, note in notes:
                if (
                    type(row) is not int
                    or row < 1
                    or (column != -1 and not 0 <= column < len(keys))
                ):
                    raise ValueError("Invalid annotation record reference")
                reference = next(
                    (
                        item
                        for item in references
                        if item["first_row"] <= row < item["first_row"] + item["rows"]
                    ),
                    None,
                )
                if reference is None:
                    raise ValueError("An annotated record is outside the original sources")
                field = ROW if column == -1 else keys[column]
                saved[reference["path"], row - reference["first_row"] + 1, field] = note
        finally:
            case.close()
    return saved


def restore(collection, annotations):
    """Apply canonical references to the new layout, including deleted notes."""
    raw = {
        item["path"]: item
        for item in collection.report.get("raw_documents") or collection.report["documents"]
    }
    previous = {item["source"] for item in collection.report.get("row_annotations", [])}
    if not annotations and not previous:
        return
    indexed = {}
    for (source, row, field), note in annotations.items():
        indexed.setdefault(source, []).append((row, field, note))
    for document in collection.report["documents"]:
        if (
            document["path"] in raw
            and document["path"] not in indexed
            and document["path"] not in previous
        ):
            continue
        references, keys = _layout(collection, document, raw)
        if document["path"] not in raw and not any(
            reference["path"] in indexed for reference in references
        ):
            continue
        case = Case(document["path"], settings=collection.settings)
        try:
            keys += [("derived", definition["name"]) for definition in case.derived]
            columns = {key: column for column, key in enumerate(keys)} | {ROW: -1}
            records = []
            for reference in references:
                for row, field, note in indexed.get(reference["path"], []):
                    if not 1 <= row <= reference["rows"]:
                        raise ValueError("An annotation is outside its original source")
                    if field in columns:
                        records.append((reference["first_row"] + row - 1, columns[field], note))
            with case.operation():
                case.db.execute("BEGIN")
                try:
                    case.db.execute("DELETE FROM bookmarks")
                    if records:
                        case.db.executemany("INSERT INTO bookmarks VALUES (?,?,?)", records)
                    case.db.execute("COMMIT")
                except BaseException:
                    case.db.execute("ROLLBACK")
                    raise
        finally:
            case.close()
    collection.report["row_annotations"] = [
        dict(source=source, row=row, field=list(field), note=note)
        for (source, row, field), note in sorted(annotations.items())
    ]
