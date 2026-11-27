"""One logical union without materializing thousands of absent values per record.

The four common columns are physical; every other original column keeps its stable
integer position in a typed map. SQL filters still address ordinary logical columns
through Case.column(), and portable analyses remain self-contained DuckDB files.
"""

import hashlib
import json
import shutil
import tempfile
import uuid
from pathlib import Path

FORMAT = "sparse-union-v1"
PREFIX = 4
FIELD_COLUMN = "__fireblade_fields"


def sparse(info):
    return info.get("storage_format") == FORMAT


def physical_schema():
    return (
        [("__row_id", "BIGINT")]
        + [(f"c{i}", "VARCHAR") for i in range(PREFIX)]
        + [(FIELD_COLUMN, "MAP(INTEGER, VARCHAR)")]
    )


def column_sql(info, index):
    if sparse(info) and PREFIX <= index < len(info["headers"]):
        return f'map_extract_value("{FIELD_COLUMN}", {index})'
    return f'"c{index}"'


def fields_from_record(case, record):
    """Yield logical column/value pairs, including explicit empty strings."""
    if not case.sparse:
        yield from enumerate(record[1:])
        return
    yield from enumerate(record[1 : PREFIX + 1])
    fields = record[PREFIX + 1] or {}
    base = len(case.info["headers"])
    for index, value in sorted(fields.items()):
        if type(index) is not int or not PREFIX <= index < base:
            raise ValueError("Invalid sparse analysis field index")
        yield index, value
    yield from enumerate(record[PREFIX + 2 :], base)


def expand_record(case, record):
    values = [None] * len(case.headers)
    for index, value in fields_from_record(case, record):
        values[index] = value
    return (record[0], *values)


class ExportCursor:
    """Expand only a bounded batch; never bind a 12,000-expression SQL projection."""

    def __init__(self, case, cursor, selected):
        self.case, self.cursor, self.selected = case, cursor, selected

    def fetchmany(self, size):
        count = PREFIX + 2 + len(self.case.derived)
        result = []
        for record in self.cursor.fetchmany(min(size, 32)):
            fields = dict(fields_from_record(self.case, record[:count]))
            result.append(tuple(fields.get(i) for i in self.selected) + record[count:])
        return result


def values_sql(case, indices=None):
    """A compact SQL list for correlations and full-text indexing."""
    selected = set(range(len(case.headers))) if indices is None else set(indices)
    physical = [
        case.column(i) for i in sorted(selected) if i < PREFIX or i >= len(case.info["headers"])
    ]
    original = sorted(i for i in selected if PREFIX <= i < len(case.info["headers"]))
    prefix = "list_value(" + ",".join(physical) + ")" if physical else "[]::VARCHAR[]"
    if indices is None:
        entries = f'map_values("{FIELD_COLUMN}")'
    elif original:
        keys = ",".join(str(i) for i in original)
        entries = f'list_transform(list_filter(map_entries("{FIELD_COLUMN}"), entry -> entry.key IN ({keys})), entry -> entry.value)'
    else:
        entries = "[]::VARCHAR[]"
    return f"list_concat({prefix}, {entries})"


def _time_sql(case, view):
    from fireblade.core.timeline import DATE_TIME, guess_time_columns, split_date_time

    spec = guess_time_columns(case.headers, view.timestamp_columns)
    if spec == DATE_TIME:
        spec = split_date_time(case.headers)
    if type(spec) is tuple:
        return "concat_ws(' '," + ",".join(case.column(i) for i in spec) + ")"
    return (
        case.column(spec)
        if type(spec) is int and 0 <= spec < len(case.headers)
        else "NULL::VARCHAR"
    )


def organize_sparse(collection, sources):
    """Build a verified, cancellable union through compact Parquet bridges."""
    from fireblade.core.collection import atomic_json, check_cancel
    from fireblade.core.collection_organization import column_keys
    from fireblade.core.engine import Case
    from fireblade.core.models import View

    headers, positions, used = [], {}, set()
    for document, _origin in sources:
        for key in column_keys(document["source"]["headers"]):
            if key in positions:
                continue
            label, number = key[0], 2
            while label.casefold() in used:
                label = f"{key[0]} ({number})"
                number += 1
            used.add(label.casefold())
            positions[key] = len(headers) + PREFIX
            headers.append(label)
    common = []
    for base in ("Artefact", "Fichier source", "Parseur", "Event time"):
        label, number = base, 2
        while label.casefold() in used:
            label = f"{base} (Kagarasu {number})"
            number += 1
        common.append(label)
        used.add(label.casefold())
    headers = common + headers
    folder = collection.output / "results" / ("organisation-" + uuid.uuid4().hex)
    folder.mkdir()
    manifest = folder / "Combined collection.json"
    target = collection.output / "analyses" / (uuid.uuid4().hex + ".timeline")
    case = Case(target, settings=collection.settings)
    with collection._case_lock:
        collection._cases.add(case)
    references, total = [], 0
    state = getattr(collection, "progress_state", None)
    if state is not None:
        state.organize_start(len(sources))
    completed = False
    try:
        case.db.execute(
            "CREATE TABLE events (__row_id BIGINT,"
            + ",".join(f"c{i} VARCHAR" for i in range(PREFIX))
            + f', "{FIELD_COLUMN}" MAP(INTEGER,VARCHAR))'
        )
        for number, (document, origin) in enumerate(sources, 1):
            check_cancel()
            collection.progress(
                f"Combined view: {number}/{len(sources)} analyses — {total} rows written"
            )
            source = Case(document["path"], settings=collection.settings, read_only=True)
            try:
                with collection._case_lock:
                    collection._active_case = source
                with source.operation():
                    if source.info != document["source"]:
                        raise ValueError(
                            "A source analysis changed before the combined view was built"
                        )
                    count, low, high = source.db.execute(
                        "SELECT count(*),min(__row_id),max(__row_id) FROM events"
                    ).fetchone()
                    if count != source.info["rows"] or (count and (low != 1 or high != count)):
                        raise ValueError("A source analysis has inconsistent row identifiers")
                    projection = sorted(
                        (positions[key], source.column(i))
                        for i, key in enumerate(column_keys(source.headers))
                    )
                    keys = ",".join(str(i) for i, _column in projection)
                    values = ",".join(column for _i, column in projection)
                    mapping = f"map_from_entries(list_filter(map_entries(map([{keys}],[{values}])), item -> item.value IS NOT NULL))"
                    stored_view = document.get("view") or {}
                    view = View.from_json(
                        stored_view if isinstance(stored_view, str) else json.dumps(stored_view)
                    )
                    query = f"SELECT (__row_id+{total})::BIGINT, ?::VARCHAR AS c0, ?::VARCHAR AS c1, ?::VARCHAR AS c2, {_time_sql(source, view)} AS c3, {mapping} AS fields FROM events ORDER BY __row_id"
                    spill = Path(str(source.path) + ".tmp")
                    spill.mkdir(exist_ok=True)
                    with tempfile.TemporaryDirectory(prefix=".union-", dir=spill) as temporary:
                        bridge = Path(temporary) / "records.parquet"
                        location = str(bridge).replace("'", "''")
                        source.db.execute(
                            f"COPY ({query}) TO '{location}' (FORMAT PARQUET, COMPRESSION ZSTD)",
                            list(origin),
                        )
                        check_cancel()
                        with collection._case_lock:
                            collection._active_case = case
                        with case.operation():
                            case.db.execute(
                                "INSERT INTO events SELECT * FROM read_parquet(?)", [str(bridge)]
                            )
                references.append(
                    {
                        "path": document["path"],
                        "source_sha256": source.info["sha256"],
                        "first_row": total + 1,
                        "rows": count,
                    }
                )
                total += count
                if state is not None:
                    state.organize_step()
            finally:
                source.close()
        check_cancel()
        actual = case.db.execute("SELECT count(*) FROM events").fetchone()[0]
        if actual != total:
            raise ValueError("The combined view did not retain every source record")
        atomic_json(manifest, {"format": FORMAT, "rows": total, "sources": references})
        info = dict(
            path=str(manifest),
            label="Combined collection",
            size=manifest.stat().st_size,
            sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
            headers=headers,
            rows=total,
            storage_format=FORMAT,
            schema_version=1,
            encoding="utf-8",
            delimiter="auto",
        )
        case.db.execute("CREATE TABLE metadata (key VARCHAR PRIMARY KEY,value VARCHAR)")
        case.db.execute("INSERT INTO metadata VALUES ('source',?)", [json.dumps(info)])
        case.db.execute(
            "CREATE TABLE bookmarks (row_id BIGINT,column_id INTEGER,note VARCHAR,PRIMARY KEY(row_id,column_id))"
        )
        case.db.execute("CREATE TABLE views (name VARCHAR PRIMARY KEY,value VARCHAR)")
        case.db.execute("CHECKPOINT")
        case.db.execute("SET enable_external_access=false")
        document = dict(
            path=str(target),
            source=info,
            view=json.loads(View(groups=[0], timestamp_columns=[3]).to_json()),
            header="",
            verification={"status": "ok", "rows": actual, "expected": total},
        )
        collection.report["raw_documents"] = [source for source, _origin in sources]
        collection.report["documents"] = [document]
        collection.report["organization_notes"] = [
            f"Combined view: one grid, {total} rows and {len(headers)} columns; absent fields use compact storage."
        ]
        completed = True
    finally:
        with collection._case_lock:
            collection._cases.discard(case)
            collection._active_case = None
        case.close()
        if not completed:
            target.unlink(missing_ok=True)
            shutil.rmtree(folder, ignore_errors=True)
