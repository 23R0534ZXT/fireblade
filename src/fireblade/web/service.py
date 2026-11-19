"""HTTP-facing, read-only access to a Fireblade case library.

Nothing here imports Qt: this module is what the container runs. The desktop
keeps its own window and its own copy of the same core calls.

A case on disk keeps the structure the desktop writes: Cases/<32 hex>/case.json,
a session file listing the analyses, and one DuckDB file per analysis. The web
service only reads that structure and never rewrites it, so a case created on
Windows opens here and the other way round.
"""
from __future__ import annotations

import csv
import json
import tempfile
import threading
import uuid
from datetime import date, datetime, time, timezone
from pathlib import Path

from fireblade.core.collection import Collection, ToolPack
from fireblade.core.engine import Case
from fireblade.core.investigations import InvestigationLibrary
from fireblade.core.models import AnalysisSnapshot, Filter, SortKey, View, analysis_label
from fireblade.core.sessions import read_session
from fireblade.core.timeline import TimelineStore
from fireblade.core.workspace_reader import WorkspaceReader

# Columns the grid always shows before the analysis own columns, in display order.
META_COLUMNS = ["__row_id"]

OPERATORS = {
    "contains", "starts", "ends", "eq", "ne", "empty", "not_empty",
    "gt", "ge", "lt", "le", "date_after", "date_eq", "date_ne", "date_before",
}


class ServiceError(Exception):
    """A request the service refuses, with a message meant for a human."""


def json_value(value):
    """DuckDB cells are typed; the wire is JSON."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).hex()
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    return str(value)


class Library:
    """Case catalogue plus one open analysis at a time per (case, index)."""

    MAX_OPEN = 4

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.library = InvestigationLibrary(self.root)
        self._open: dict[tuple[str, int], Case] = {}
        self._timelines: dict[tuple[str, str | None], TimelineStore] = {}
        self._timeline_dir = tempfile.mkdtemp(prefix="fireblade-timelines-")
        self._lock = threading.RLock()

    # -- catalogue ---------------------------------------------------------

    def cases(self) -> dict:
        records, errors = self.library.list()
        return {
            "root": str(self.root),
            "cases": [self._summary(item) for item in records],
            "errors": list(errors),
        }

    def _summary(self, data: dict) -> dict:
        return {
            "id": data.get("id"),
            "name": data.get("name", ""),
            "description": data.get("description", ""),
            "environment": data.get("environment", ""),
            "status": data.get("status", ""),
            "updated": data.get("updated", ""),
            "created": data.get("created", ""),
            "analysis_count": data.get("analysis_count", len(data.get("analyses") or [])),
            "recovery_needed": bool(data.get("recovery_needed")),
        }

    def case(self, identifier: str) -> dict:
        data = self.library.read(identifier)
        summary = self._summary(data)
        summary["analyses"] = self._analyses(data)
        summary["collections"] = [
            {"name": Path(entry.get("path", "")).name, "path": entry.get("path", "")}
            for entry in data.get("collections") or []
            if isinstance(entry, dict)
        ]
        return summary

    def _analyses(self, data: dict) -> list[dict]:
        """The session's analyses, with the recorded path repaired when the case moved.

        A session written on Windows stores absolute paths such as
        C:\\Users\\...\\analysis.duckdb. Once the folder is copied to Linux the
        file is there but the path is not, so the recorded path is tried first and
        the case folder is searched by file name. Nothing on disk is rewritten.
        """
        session = self.library.session_path(data)
        if not session or not Path(session).is_file():
            return []
        folder = Path(session).parent
        if Path(session).stat().st_size > 4 * 1024 * 1024:
            raise ServiceError("Fichier de session trop volumineux.")
        payload = json.loads(Path(session).read_text(encoding="utf-8"))
        if payload.get("format") != "fireblade-session" or payload.get("version") != 1:
            raise ServiceError("Format de session Fireblade inconnu.")
        documents = payload.get("documents") or []
        if not isinstance(documents, list) or len(documents) > 1000:
            raise ServiceError("Session Fireblade invalide.")
        active = payload.get("active", 0)
        entries = []
        for index, document in enumerate(documents):
            if not isinstance(document, dict) or "path" not in document:
                continue
            recorded = str(document["path"])
            resolved = self._resolve_analysis(folder, recorded)
            source = document.get("source") or {}
            entries.append({
                "index": index,
                "source_info": source if isinstance(source, dict) else {},
                "label": self._label(source, resolved or recorded),
                "path": str(resolved or ""),
                "recorded_path": recorded,
                "found": resolved is not None,
                "source": str(source.get("path", "")) if isinstance(source, dict) else "",
                "active": index == active,
            })
        return entries

    @staticmethod
    def _label(source, fallback) -> str:
        """The tab label the desktop would show: the source file name, not its path."""
        if isinstance(source, dict):
            raw = str(source.get("path", "") or "")
            if raw:
                name = Path(raw.replace("\\", "/")).name
                if name:
                    return name
        return Path(str(fallback).replace("\\", "/")).stem or "analysis"

    @staticmethod
    def _resolve_analysis(folder: Path, recorded: str) -> Path | None:
        # A Windows session stores backslashes; on Linux they are ordinary characters,
        # not separators, so the separator is normalised before anything else.
        candidate = Path(recorded.replace("\\", "/"))
        if candidate.is_file():
            return candidate.resolve()
        if not candidate.is_absolute():
            relative = (folder / candidate)
            if relative.is_file():
                return relative.resolve()
        name = candidate.name
        if not name or name in (".", ".."):
            return None
        local = folder / name
        if local.is_file():
            return local.resolve()
        matches = []
        for path in folder.rglob(name):
            if path.is_file() and not path.is_symlink():
                matches.append(path)
            if len(matches) > 1:
                break
        return matches[0].resolve() if len(matches) == 1 else None


    # -- case lifecycle ----------------------------------------------------

    def create_case(self, name: str, description: str = "", environment: str = "unspecified") -> dict:
        data = self.library.create(name, description, environment)
        return self._summary(data)

    def update_case(self, identifier: str, name: str | None = None,
                    description: str | None = None) -> dict:
        fields = {}
        if name is not None:
            fields["name"] = name
        if description is not None:
            fields["description"] = description
        if not fields:
            raise ServiceError("Rien à modifier.")
        data = self.library.update(identifier, **fields)
        return self._summary(data)

    def destroy(self, identifier: str, method: str = "dod3", operator: str = "",
                witness: str = "", reason: str = "", confirmation: str = "") -> dict:
        """Destroy the case the way the desktop does, and keep the certificate outside."""
        from fireblade.core.case_destruction import destroy_case

        data = self.library.read(identifier)
        if (confirmation or "").strip() != data.get("name", ""):
            raise ServiceError("La confirmation doit reprendre le nom du case à l'identique.")
        folder = self.library.folder(identifier)
        certificates = self.root / "certificates"
        certificates.mkdir(parents=True, exist_ok=True)
        # The generator writes HTML unless the target ends in .pdf.
        certificate = certificates / (datetime.now(timezone.utc).strftime("pv-%Y%m%d-%H%M%S-")
                                      + identifier[:8] + ".html")
        self.close_case(identifier)
        record = destroy_case(folder, method, operator=operator, witness=witness, reason=reason,
                              certificate_path=certificate, case_name=data.get("name", ""),
                              case_id=identifier)
        return {"id": record.get("id"), "method": record.get("method"),
                "files": len(record.get("files") or []),
                "certificate": str(certificate),
                "bytes": sum(int(item.get("size") or 0) for item in (record.get("files") or []))}

    def close_case(self, identifier: str) -> None:
        """Release every handle the service holds on one case."""
        with self._lock:
            for key in [item for item in self._open if item[0] == identifier]:
                try:
                    self._open.pop(key).close()
                except Exception:
                    pass
            for key in [item for item in self._timelines if item[0] == identifier]:
                try:
                    self._timelines.pop(key).close()
                except Exception:
                    pass

    # -- reports -----------------------------------------------------------

    def report(self, identifier: str, title: str, description: str = "",
               bookmarks_only: bool = True, limit: int = 2000) -> dict:
        """Build the client report with the desktop's own generator.

        Bookmarks are the default selection: a report is a set of explicit
        findings, not a dump of the grid.
        """
        from fireblade.core.investigation_report import build_report, write_report

        snapshots = self._snapshots(identifier)
        if not snapshots:
            raise ServiceError("Ce case ne contient aucune analyse.")
        with self._lock:
            for open_key in [item for item in self._open if item[0] == identifier]:
                try:
                    self._open.pop(open_key).close()
                except Exception:
                    pass
        reader = WorkspaceReader(snapshots)
        report = build_report(reader, title, description, bookmarks_only=bookmarks_only, limit=limit)
        folder = self.library.folder(identifier)
        target = folder / "reports" / (datetime.now(timezone.utc).strftime("report-%Y%m%d-%H%M%S") + ".html")
        target.parent.mkdir(parents=True, exist_ok=True)
        write_report(target, report, snapshots)
        return {"name": target.name, "records": report.get("records", 0),
                "errors": report.get("errors", []), "url": f"/api/cases/{identifier}/reports/{target.name}"}

    def report_file(self, identifier: str, name: str) -> Path:
        if "/" in name or "\\" in name or name.startswith("."):
            raise ServiceError("Nom de rapport invalide.")
        path = self.library.folder(identifier) / "reports" / name
        if not path.is_file():
            raise ServiceError("Rapport introuvable.")
        return path

    # -- IOC hunting -------------------------------------------------------

    def ioc_scan(self, identifier: str, index: int, text: str, limit: int = 2000) -> dict:
        """Match a pasted indicator list against one analysis, offline.

        Same parser and same matcher as the desktop: an observation is never a
        verdict, and the evidence values are left untouched.
        """
        from fireblade.core.ioc_hunt import IndicatorMatcher, parse_indicators

        batch = parse_indicators(text or "")
        indicators = batch.indicators if hasattr(batch, "indicators") else list(batch)
        if not indicators:
            raise ServiceError("Aucun indicateur reconnu dans ce texte.")
        matcher = IndicatorMatcher(indicators)
        case = self._case_for(identifier, index)
        hits, scanned = [], 0
        view = View()
        with case.lock:
            offset = 0
            while True:
                page = case.page(view, offset=offset, limit=1000)
                if not page:
                    break
                for row in page:
                    scanned += 1
                    row_id = row[0]
                    for column, value in enumerate(row[1:], start=1):
                        if value is None:
                            continue
                        cell = str(value)
                        if len(cell) > 4000:
                            cell = cell[:4000]
                        for number, observed, at, rule in matcher.matches(cell):
                            item = indicators[number - 1]
                            hits.append({"row_id": json_value(row_id), "column": column - 1,
                                         "indicator": item.value, "kind": item.kind,
                                         "observed": observed, "rule": rule})
                            if len(hits) >= limit:
                                break
                        if len(hits) >= limit:
                            break
                    if len(hits) >= limit:
                        break
                if len(hits) >= limit:
                    break
                offset += len(page)
        summary = {}
        for hit in hits:
            summary[hit["kind"]] = summary.get(hit["kind"], 0) + 1
        return {"indicators": len(indicators), "scanned": scanned, "hits": hits,
                "by_kind": summary, "truncated": len(hits) >= limit}

    # -- timeline ----------------------------------------------------------

    def _snapshots(self, identifier: str):
        """The case's analyses as snapshots, with the source record the timeline needs."""
        data = self.library.read(identifier)
        snapshots = []
        for entry in self._analyses(data):
            if not entry["found"]:
                continue
            snapshots.append(AnalysisSnapshot(entry["path"], entry.get("source_info") or {},
                                              View(), b""))
        return snapshots

    def timeline(self, identifier: str, start: int | None = None, end: int | None = None,
                 offset: int = 0, text: str = "", kind: str = "text") -> dict:
        """Counts the case's rows over time with the desktop's own TimelineStore."""
        key = (identifier, self.library.read(identifier).get("revision"))
        store = self._timelines.get(key)
        if store is None:
            snapshots = self._snapshots(identifier)
            if not snapshots:
                raise ServiceError("Ce case ne contient aucune analyse.")
            # DuckDB refuses a second connection with another configuration: the
            # grid's open handles are closed before the timeline opens the files
            # read-only, and they reopen on the next grid request.
            with self._lock:
                for open_key in [item for item in self._open if item[0] == identifier]:
                    try:
                        self._open.pop(open_key).close()
                    except Exception:
                        pass
            store = TimelineStore(self._timeline_dir)
            reader = WorkspaceReader(snapshots)
            store.build(reader, columns={})
            for old in list(self._timelines):
                if old[0] == identifier:
                    try:
                        self._timelines.pop(old).close()
                    except Exception:
                        pass
            self._timelines[key] = store
        filters = {}
        if text:
            filters.update(text=text, kind=kind)
        low, high, total, dated = store.extent(**filters)
        page = store.page(offset, **(filters if filters else {}))
        payload = {
            "sources": [{k: item.get(k) for k in ("id", "name", "original", "rows", "dated", "undated", "column", "error")}
                        for item in store.sources],
            "extent": {"start": low, "end": high, "rows": int(total or 0), "dated": int(dated or 0)},
            "count": int(page["count"]),
            "page_size": store.PAGE_SIZE,
            "offset": int(offset),
            "rows": [[int(row[0]), int(row[1]), int(row[2]) if row[2] is not None else None,
                      row[3], row[4], row[5] or "", bool(row[6]), bool(row[7])] for row in page["rows"]],
        }
        if low is not None and high is not None:
            window_start = int(start if start is not None else low)
            window_end = int(end if end is not None else high)
            histogram = store.histogram(window_start, window_end, 120, **(filters if filters else {}))
            payload["histogram"] = {"start": histogram["start"], "end": histogram["end"],
                                    "width": histogram["width"], "bins": histogram["bins"],
                                    "rows": [[int(a), int(b), int(c), int(d)]
                                                                          for a, b, c, d in histogram["rows"]]}
            payload["window"] = {"start": window_start, "end": window_end}
        return payload

    # -- importing ---------------------------------------------------------

    def import_source(self, identifier: str, source: str | Path, tools_root: str | Path | None = None,
                      organization: str = "files", progress=None) -> dict:
        """Read a file or a folder into the case, the way the desktop does it.

        The orchestration is `fireblade.core.collection.Collection`: the same
        reader selection, the same CSV, the same verification. Only the interface
        around it is different. The collection writes its own session file, and
        that file becomes the case session — so an import done here opens in the
        desktop edition unchanged.
        """
        data = self.library.read(identifier)
        folder = self.library.folder(identifier)
        source = Path(source).resolve()
        if not source.exists():
            raise ServiceError("La source à importer est absente.")
        output = folder / "collections" / ("import-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"))
        if output.exists():
            output = folder / "collections" / ("import-" + uuid.uuid4().hex[:8])
        output.parent.mkdir(parents=True, exist_ok=True)
        pack = ToolPack(Path(tools_root)) if tools_root else ToolPack(Path(tempfile.gettempdir()) / "fireblade-pack")
        collection = Collection(source, output, pack, progress=progress or (lambda _text: None),
                                organization=organization)
        report = collection.parse()
        session = output / "collection.fireblade-session"
        if not session.is_file():
            return {"status": report.get("status"), "analyses": 0, "files": len(report.get("files") or []),
                    "collection": str(output), "message": "Aucune analyse produite : format non reconnu."}
        snapshots, active = read_session(session)
        collections = [entry for entry in (data.get("collections") or []) if isinstance(entry, dict)]
        collections.append({"path": str(output), "name": output.name,
                            "imported": datetime.now(timezone.utc).isoformat()})
        self.library.save(identifier, snapshots, active if snapshots else -1, collections,
                          str(output), data.get("revision"))
        self._open.pop((identifier, 0), None)
        return {
            "status": report.get("status", "complete"),
            "analyses": len(snapshots),
            "files": len(report.get("files") or []),
            "collection": str(output),
        }

    # -- one analysis ------------------------------------------------------

    def _case_for(self, identifier: str, index: int) -> Case:
        key = (identifier, index)
        with self._lock:
            existing = self._open.get(key)
            if existing is not None:
                return existing
            data = self.library.read(identifier)
            analyses = self._analyses(data)
            if not 0 <= index < len(analyses):
                raise ServiceError("Cette analyse n'existe pas dans le case.")
            entry = analyses[index]
            if not entry["found"]:
                raise ServiceError(
                    "Le fichier d'analyse est absent du case "
                    f"(chemin enregistré : {entry['recorded_path']}).")
            path = Path(entry["path"])
            if len(self._open) >= self.MAX_OPEN:
                oldest = next(iter(self._open))
                try:
                    self._open.pop(oldest).close()
                except Exception:  # a broken handle must not block the new one
                    pass
            # Writable: the analyst books rows and writes notes from the grid, and
            # DuckDB refuses two connections with different configurations on the
            # same file, so one handle serves reads and writes.
            case = Case(path, read_only=False)
            self._open[key] = case
            return case

    def close(self):
        with self._lock:
            for case in self._open.values():
                try:
                    case.close()
                except Exception:
                    pass
            self._open.clear()
            for store in self._timelines.values():
                try:
                    store.close()
                except Exception:
                    pass
            self._timelines.clear()

    def columns(self, identifier: str, index: int) -> list[str]:
        case = self._case_for(identifier, index)
        return META_COLUMNS + list(case.headers)

    def rows(self, identifier: str, index: int, offset: int = 0, limit: int = 200,
             search: str = "", sort: int | None = None, descending: bool = False,
             filters: list[tuple[int, str, str]] | None = None,
             bookmarks_only: bool = False, groups: list[int] | None = None,
             path: list[str] | None = None, sorts: list[tuple[int, bool]] | None = None) -> dict:
        case = self._case_for(identifier, index)
        view = View(search=search or "", filters=[], bookmarks_only=bool(bookmarks_only))
        for column, operator, value in filters or ():
            if operator not in OPERATORS:
                raise ServiceError(f"Opérateur de filtre inconnu : {operator}")
            if not 0 <= column < len(case.headers):
                raise ServiceError("Colonne de filtre hors de l'analyse.")
            view.filters.append(Filter(column, operator, value))
        keys = list(sorts or ())
        if not keys and sort is not None:
            keys = [(sort, bool(descending))]
        for column, _descending in keys:
            if not 0 <= int(column) < len(case.headers):
                raise ServiceError("Colonne de tri hors de l'analyse.")
        if keys:
            view.sort_column, view.descending = int(keys[0][0]), bool(keys[0][1])
            view.sort_type = "text"
            view.sorts = [SortKey(int(column), "text", bool(flag)) for column, flag in keys]
        if groups:
            for column in groups:
                if not 0 <= int(column) < len(case.headers):
                    raise ServiceError("Colonne de groupement hors de l'analyse.")
            view.groups = [int(column) for column in groups]
        limit = max(1, min(int(limit), 1000))
        offset = max(0, int(offset))
        depth = tuple(path or ())
        with case.lock:
            total = case.count(view)
            page = case.page(view, path=depth, offset=offset, limit=limit)
            rows = [[json_value(value) for value in row] for row in page]
        grouped = len(depth) < len(view.groups)
        return {
            "columns": META_COLUMNS + list(case.headers),
            "rows": rows,
            "total": int(total),
            "offset": offset,
            "limit": limit,
            "grouped": grouped,
            "path": list(depth),
        }

    def bookmarks(self, identifier: str, index: int) -> dict:
        case = self._case_for(identifier, index)
        with case.lock:
            notes = case.bookmarks()
        return {"bookmarks": [{"row_id": int(row_id), "note": note or ""}
                              for row_id, note in notes.items()]}

    def bookmark(self, identifier: str, index: int, row_id: int, note: str = "",
                 column: int | None = None) -> dict:
        """Mark a row, or one cell, with a note. An empty note removes the mark."""
        case = self._case_for(identifier, index)
        clean = (note or "").strip()
        with case.lock:
            # An empty note removes the mark; the core speaks None for removal.
            case.bookmark(int(row_id), clean or None, None if column is None else int(column))
        return {"row_id": int(row_id), "column": column, "note": clean}

    def export(self, identifier: str, index: int, search: str = "",
               sort: int | None = None, descending: bool = False,
               filters: list[tuple[int, str, str]] | None = None) -> Path:
        """Write a CSV next to the OS temporary directory and return its path."""
        case = self._case_for(identifier, index)
        view = View(search=search or "", filters=[])
        for column, operator, value in filters or ():
            if operator in OPERATORS and 0 <= column < len(case.headers):
                view.filters.append(Filter(column, operator, value))
        if sort is not None and 0 <= sort < len(case.headers):
            view.sort_column, view.descending = sort, bool(descending)
            view.sorts = [SortKey(sort, "text", bool(descending))]
        target = Path(tempfile.gettempdir()) / f"fireblade-{uuid.uuid4().hex}.csv"
        with case.lock:
            case.export(str(target), view, include_annotations=True)
        return target


def parse_filters(values) -> list[tuple[int, str, str]]:
    """`column:operator:value` triples, as the grid sends them."""
    filters = []
    for raw in values or ():
        parts = raw.split(":", 2)
        if len(parts) != 3:
            raise ServiceError("Format de filtre attendu : colonne:opérateur:valeur")
        try:
            column = int(parts[0])
        except ValueError as exc:
            raise ServiceError("Indice de colonne invalide.") from exc
        filters.append((column, parts[1], parts[2]))
    return filters


def read_rows_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        yield from csv.reader(stream)
