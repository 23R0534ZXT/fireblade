"""Stream heterogeneous collection results into artifact tabs or one grouped table."""

import csv
import uuid
from pathlib import Path

import duckdb

from fireblade.core.engine import Case
from fireblade.core.models import View

ARTIFACTS = {
    "EvtxECmd": "EVTX",
    "AmcacheParser": "Amcache",
    "AppCompatCacheParser": "AppCompatCache",
    "PECmd": "Prefetch",
    "MFTECmd": "MFT et USN",
    "RECmd": "Registre",
    "LECmd": "Raccourcis LNK",
    "JLECmd": "Jump Lists",
    "SrumECmd": "SRUM",
    "SRUM": "SRUM",
    "WxTCmd": "Windows Timeline",
    "RBCmd": "Corbeille",
    "RecentFileCacheParser": "RecentFileCache",
    "SQLECmd": "SQLite",
    "LinuxLogs": "Journaux Linux",
    "native": "Exports CSV",
    "Shellbags": "Shellbags",
    "WebCache": "WebCache",
}


def artifact_name(tool, output):
    name = Path(output).name.casefold()
    if tool == "native":
        for token, label in [
            ("shellbag", "Shellbags"),
            ("jumplist", "Jump Lists"),
            ("jlecmd", "Jump Lists"),
            ("amcache", "Amcache"),
            ("evtx", "EVTX"),
            ("prefetch", "Prefetch"),
            ("pecmd", "Prefetch"),
            ("srum", "SRUM"),
            ("mftecmd", "MFT et USN"),
        ]:
            if token in name:
                return label
    if tool == "RECmd" and any(
        word in Path(output).name.casefold() for word in ("shellbag", "bagmru")
    ):
        return "Shellbags"
    return ARTIFACTS.get(tool, tool)


def column_keys(headers):
    occurrences = {}
    keys = []
    for header in headers:
        index = occurrences.get(header, 0)
        keys.append((header, index))
        occurrences[header] = index + 1
    return keys


# A merged table keeps the union of its files' columns. Past this many the native reader needs more
# memory than a machine can give, and the row-by-row path takes hours: the family is laid out as one
# grid per shape instead (files with exactly the same columns), and the import says so.
MAX_COLUMNS = 3000
MAX_SPLIT_GRIDS = 400  # a family with more shapes than this is merged, not split


def _union_width(sources):
    keys = set()
    for document, _origin in sources:
        keys.update(column_keys(list((document.get("source") or {}).get("headers") or ())))
    return len(keys)


def _split_too_wide(groups, mode, notes):
    result, used = {}, set()
    for title, sources in groups.items():
        width = _union_width(sources)
        if width <= MAX_COLUMNS:
            result[title] = sources
            used.add(title.casefold())
            continue
        shapes = {}
        for document, origin in sources:
            columns = tuple((document.get("source") or {}).get("headers") or ())
            shapes.setdefault((origin[0], columns), []).append((document, origin))
        if len(shapes) > MAX_SPLIT_GRIDS:
            # Hundreds of shapes would fill the case with grids: the merge stays, as wide as it is.
            result[title] = sources
            used.add(title.casefold())
            continue
        parts = _named_schemas(shapes)
        for name, members in parts.items():
            base, number = name, 2
            while name.casefold() in used or name in groups:
                name = f"{base} ({number})"
                number += 1
            used.add(name.casefold())
            result[name] = members
        notes.append(
            f"{title}: {width} columns together, laid out as {len(parts)} grid(s) of files "
            "with identical columns"
        )
    return result


def _named_schemas(groups):
    """Give each (family, columns) group a unique, file-safe name: the family and its first columns."""
    per_family = {}
    for family, _columns in groups:
        per_family[family] = per_family.get(family, 0) + 1
    named, used = {}, set()
    for (family, columns), sources in groups.items():
        title = family
        if per_family[family] > 1:
            first = ", ".join(columns[:3]) + (f" +{len(columns) - 3}" if len(columns) > 3 else "")
            title = f"{family} · {first}"
        title = "".join(c if c.isalnum() or c in " ._+,-·" else "_" for c in title)[:100].strip()
        base, number = title or family, 2
        title = base
        while title.casefold() in used:
            title = f"{base} ({number})"
            number += 1
        used.add(title.casefold())
        named[title] = sources
    return named


def organize(collection):
    mode = collection.report.get("organization", "files")
    if mode == "files" or not collection.report["documents"]:
        return
    from fireblade.core.collection import check_cancel

    originals = list(collection.report["documents"])
    origins = {}
    for entry in collection.report["files"]:
        for run in entry.get("runs", []):
            for output in run.get("outputs", []):
                if output.get("analysis"):
                    origins[output["analysis"]] = (
                        output.get("family") or artifact_name(run["tool"], output["csv"]),
                        entry["path"],
                        run["tool"],
                    )
    groups = {}
    for document in originals:
        origin = origins.get(document["path"])
        if origin is None:
            raise ValueError("Provenance de résultat absente ; organisation refusée")
        if mode == "schemas":
            # Files of one family with exactly the same columns make one grid, whatever their
            # number: the table does not get wider, and a thousand files rarely have a thousand
            # different shapes.
            columns = tuple((document.get("source") or {}).get("headers") or ())
            key = (origin[0], columns)
        else:
            key = origin[0] if mode == "artifacts" else "Collecte complète"
        groups.setdefault(key, []).append((document, origin))
    if mode == "schemas":
        groups = _named_schemas(groups)
    notes = []
    if mode in ("artifacts", "combined"):
        groups = _split_too_wide(groups, mode, notes)
    folder = collection.output / "results" / ("organisation-" + uuid.uuid4().hex)
    folder.mkdir()
    documents = []
    failures = []
    try:
        for title, sources in groups.items():
            check_cancel()
            collection.progress("Organisation : " + title)
            union, positions, headers = [], {}, []
            used = set()
            for position, (document, _) in enumerate(sources, 1):
                check_cancel()
                if position % 20 == 0 or position == len(sources):
                    collection.progress(f"Organisation : {title} — {position}/{len(sources)}")
                # The analysis states its own columns: opening it (about 35 ms) only to read them
                # doubled the time of this step on a collection of a thousand files.
                known = list((document.get("source") or {}).get("headers") or [])
                if not known:
                    case = Case(document["path"], settings=collection.settings, read_only=True)
                    try:
                        known = list(case.headers)
                    finally:
                        case.close()
                for key in column_keys(known):
                    if key in positions:
                        continue
                    label = key[0]
                    number = 2
                    while label.casefold() in used:
                        label = key[0] + " (" + str(number) + ")"
                        number += 1
                    used.add(label.casefold())
                    positions[key] = len(union)
                    union.append(key)
                    headers.append(label)
            metadata = []
            for base in ("Artefact", "Fichier source", "Parseur"):
                label, number = base, 2
                while label.casefold() in used:
                    label = base + " (Fireblade " + str(number) + ")"
                    number += 1
                used.add(label.casefold())
                metadata.append(label)
            target = folder / (title + ".csv")
            temporary = target.with_suffix(".partial")
            csv.field_size_limit(2**31 - 1)
            with temporary.open("x", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(metadata + headers)
                for position, (document, origin) in enumerate(sources, 1):
                    check_cancel()
                    if position % 20 == 0 or position == len(sources):
                        collection.progress(f"Organisation : {title} — {position}/{len(sources)}")
                    case = Case(document["path"], settings=collection.settings, read_only=True)
                    with collection._case_lock:
                        collection._active_case = case
                    try:
                        projection = [positions[key] for key in column_keys(case.headers)]
                        with case.operation():
                            cursor = case.db.execute(
                                "SELECT "
                                + ",".join(case.column(i) for i in range(len(case.headers)))
                                + " FROM events ORDER BY __row_id"
                            )
                            while rows := cursor.fetchmany(
                                collection.settings.export_batch_rows
                                if collection.settings
                                else 2048
                            ):
                                check_cancel()
                                for row in rows:
                                    values = [None] * len(union)
                                    for index, value in zip(projection, row):
                                        values[index] = value
                                    writer.writerow(list(origin) + values)
                    finally:
                        with collection._case_lock:
                            collection._active_case = None
                            case.close()
            temporary.replace(target)
            view = View(groups=[0]) if mode == "combined" else View()
            try:
                document = collection.import_result(target, "organized", view=view, register=False)
            except duckdb.OutOfMemoryException as exc:
                # A merged family can need more memory than the collection's budget.
                # Keep this family as its original analyses rather than losing the
                # whole collection on the last step, and record why.
                target.unlink(missing_ok=True)
                failures.append(dict(artifact=title, reason=str(exc)))
                documents.extend(document for document, _origin in sources)
                continue
            documents.append(document)
        collection.report["raw_documents"] = originals
        collection.report["documents"] = documents
        if notes:
            collection.report["organization_notes"] = notes
        if failures:
            collection.report["organization_failures"] = failures
    except BaseException:
        # Originals remain the active session until the complete organization succeeds.
        for document in documents:
            Path(document["path"]).unlink(missing_ok=True)
        raise
