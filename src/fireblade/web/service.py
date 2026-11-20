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
import io
import json
import re
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

    def __init__(self, root: str | Path, tools_root: str | Path | None = None,
                 plugins_root: str | Path | None = None):
        self.root = Path(root).resolve()
        self.tools_root = Path(tools_root).resolve() if tools_root else None
        # Presentation profiles live outside the cases: an instance-level setting,
        # which a container must mount or lose on the next run.
        self.plugins_root = Path(plugins_root).resolve() if plugins_root else None
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
            raise ServiceError("The session file is too large.")
        payload = json.loads(Path(session).read_text(encoding="utf-8"))
        if payload.get("format") != "fireblade-session" or payload.get("version") != 1:
            raise ServiceError("Unknown Fireblade session format.")
        documents = payload.get("documents") or []
        if not isinstance(documents, list) or len(documents) > 1000:
            raise ServiceError("Invalid Fireblade session.")
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


    # -- attack graph ------------------------------------------------------

    def graph(self, identifier: str, navigator: bool = False) -> dict:
        """The kill-chain graph, built from the detection findings and the case record."""
        from fireblade.core import attack_graph as ag
        from fireblade.core.case_workspace import load as load_workspace
        from fireblade.core.findings import Group

        folder = self.library.folder(identifier)
        data = self.library.read(identifier)
        groups = {}
        for csv_path in sorted((folder / "collections").glob("import-*/results/hayabusa-*/hayabusa.csv")):
            with csv_path.open(encoding="utf-8", errors="replace", newline="") as stream:
                for record in csv.DictReader(stream):
                    host = (record.get("Computer") or "").strip()
                    title = (record.get("RuleTitle") or "").strip()
                    if not host or not title:
                        continue
                    key = f"{host}|{title}"
                    group = groups.get(key)
                    if group is None:
                        groups[key] = Group(key=key, title=title, level=(record.get("Level") or "").strip(),
                                            host=host, channel=(record.get("Channel") or "").strip(),
                                            event_ids=((record.get("EventID") or "").strip(),),
                                            tactics=(record.get("MitreTactics") or "").strip(),
                                            techniques=(record.get("MitreTags") or "").strip(),
                                            rule_id=(record.get("RuleID") or "").strip(),
                                            rule_file=(record.get("RuleFile") or "").strip(),
                                            start=None, end=None, count=1)
                    else:
                        group.count += 1
        try:
            workspace = load_workspace(folder)
        except (OSError, ValueError):
            workspace = {}
        if not groups and not (workspace.get("entities")):
            raise ServiceError("No finding and no entity: run a detection or declare a machine in the case first.")
        graph = ag.build(list(groups.values()), workspace)
        if navigator:
            layer = ag.navigator_layer(graph, name=data.get("name") or "Fireblade",
                                       description=data.get("description") or "",
                                       case=data.get("name") or "")
            target = self.root / "exports" / (identifier[:8] + "-attack-layer.json")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(layer, ensure_ascii=False, indent=2), encoding="utf-8")
            return {"layer": str(target), "bytes": target.stat().st_size,
                    "techniques": len((layer.get("techniques") or []))}
        positioned = ag.layout(graph)
        return {"nodes": positioned.get("nodes", []), "edges": positioned.get("edges", []),
                "groups": len(groups)}

    # -- Hayabusa ----------------------------------------------------------

    def detect(self, identifier: str, min_level: str = "low") -> dict:
        """Run the detection engine over the case's verified EVTX copies.

        `Collection.reopen` restores the import record — the files, their hashes
        and the toolchain — and `analyze()` is the desktop's own run: same rule
        folder, same command, same cross-file context.
        """
        if min_level not in ("informational", "low", "medium", "high", "critical"):
            raise ServiceError("Invalid Hayabusa level.")
        data = self.library.read(identifier)
        reports = sorted((self.library.folder(identifier) / "collections").glob("import-*"))
        pack = ToolPack(Path(self.tools_root)) if self.tools_root else ToolPack(Path(tempfile.gettempdir()) / "pack")
        results = []
        for entry in reports:
            if not (entry / "collection.json").is_file():
                continue
            self.close_case(identifier)
            collection = Collection.reopen(entry, pack)
            has_evtx = any("EvtxECmd" in (item.get("tools") or []) for item in collection.report.get("files") or [])
            if not has_evtx:
                continue
            collection.analyze(min_level)
            detection = collection.report.get("detection") or {}
            # The run imports its alerts as an analysis and saves the collection's
            # session: adding it here puts the alerts in the case's workspace, so
            # "show the alerts in the grid" has something to open.
            analysis_index = None
            try:
                self._merge_session(identifier, entry / "collection.fireblade-session")
                alerts = (detection.get("analysis")
                          or ((detection.get("outputs") or [{}])[0].get("analysis")))
                analysis_index = self._analysis_index_of(identifier, alerts or "")
            except (OSError, ValueError, ServiceError):
                analysis_index = None
            rows = []
            outputs = [Path(str(item)) for item in (detection.get("outputs") or []) if Path(str(item)).is_file()]
            if not outputs:
                # The run writes its CSV beside its inputs; the detection record
                # only names it when the caller asked for per-file outputs.
                outputs = sorted((entry / "results").glob("hayabusa-*/hayabusa.csv"))
            for path in outputs:
                if not path.is_file():
                    continue
                with path.open(encoding="utf-8", errors="replace", newline="") as stream:
                    for record in csv.DictReader(stream):
                        rows.append({key: record.get(key, "") for key in
                                     ("Timestamp", "RuleTitle", "Level", "Computer", "Channel",
                                      "EventID", "MitreTactics", "MitreTags", "Details")})
            # The engine writes one line per rule that fired on the same event: the
            # grid shows the event once, with the first rule that named it.
            seen = set()
            unique = []
            for row in rows:
                key = (row.get("Timestamp"), row.get("RuleTitle"), row.get("Computer"), row.get("EventID"))
                if key in seen:
                    continue
                seen.add(key)
                unique.append(row)
            rows = unique
            outputs = [dict(item) for item in (detection.get("outputs") or [])
                       if isinstance(item, dict)]
            results.append({"collection": entry.name, "status": detection.get("status"),
                            "summary": detection.get("summary") or {},
                            "warnings": (detection.get("warnings") or [])[:20],
                            "findings": rows[:2000], "total": len(rows),
                            "analysis": analysis_index,
                            "sources": str(outputs[0].get("csv") or "") if outputs else ""})
        if not results:
            raise ServiceError("No import of this case carries an EVTX journal to analyse.")
        merged = [finding for item in results for finding in item["findings"]]
        return {"runs": results, "findings": merged[:2000], "total": sum(item["total"] for item in results)}
    FINDING_COLUMNS = (("Timestamp", "TimeCreated"), ("Computer", "Hostname"),
                       ("EventID", "EventId"), ("RuleTitle",))

    def _analysis_index_of(self, identifier: str, path: str | Path) -> int | None:
        """Where a document sits in the case session, or None when it is not open."""
        if not path:
            return None
        want = str(Path(str(path)))
        data = self.library.read(identifier)
        session = data.get("session")
        if not session:
            return None
        try:
            snapshots, _active = read_session(self.library.folder(identifier) / session)
        except (OSError, ValueError):
            return None
        for position, snapshot in enumerate(snapshots):
            if str(Path(str(snapshot.path))) == want:
                return position
        return None

    def bookmark_finding(self, identifier: str, index: int, finding: dict,
                         note: str | None = None) -> dict:
        """Mark every row of an alert analysis that the finding names.

        The desktop marks the alerts of a finding in one gesture; this is the same
        gesture over HTTP. The match is on the fields the finding carries, so a
        rule that fired on the same event is marked once.
        """
        case = self._case_for(identifier, index)
        headers = [str(name).casefold() for name in case.headers]
        filters = []
        for names in self.FINDING_COLUMNS:
            value = ""
            for name in names:
                if finding.get(name):
                    value = str(finding.get(name))
                    break
            if not value:
                continue
            column = next((position for position, name in enumerate(headers)
                           if name in {item.casefold() for item in names}), None)
            if column is not None:
                filters.append(Filter(column, "eq", value))
        view = View(filters=filters)
        label = str(finding.get("RuleTitle") or "Hayabusa finding").strip()[:120]
        text = (note or f"Hayabusa: {label}").strip()
        with case.lock:
            total = int(case.count(view))
            page = case.page(view, offset=0, limit=min(total, 2000)) if total else []
            for row in page:
                case.bookmark(int(row[0]), text)
        return {"matched": total, "marked": min(total, 2000), "note": text}

    def _row_values(self, case, row_id: int) -> dict:
        """One row of an open analysis, by the identifier the grid shows.

        The table stores the raw columns (`c0`, `c1`…) and the analysis keeps the
        displayed names beside them: the mapping is positional, never by name.
        """
        with case.lock:
            cursor = case.db.execute("SELECT * FROM events WHERE __row_id = ?", [int(row_id)])
            row = cursor.fetchone()
            names = [item[0] for item in cursor.description]
        if row is None:
            raise ServiceError("This row does not exist in the analysis.")
        offset = names.index("__row_id") + 1 if "__row_id" in names else 0
        values = {}
        for position, header in enumerate(case.headers):
            index = offset + position
            values[str(header)] = row[index] if index < len(row) else None
        return values

    def _collection_of(self, analysis_path: str | Path) -> Path:
        """The collection folder that wrote an analysis, two levels above it."""
        folder = Path(analysis_path).parent.parent
        if not (folder / "collection.json").is_file():
            raise ServiceError("The collection that produced this alert is not beside it.")
        return folder

    def alert_context(self, identifier: str, index: int, row_id: int, minutes: int = 5) -> dict:
        """The EVTX events around an alert, built by the core's own builder.

        The desktop opens this as a new tab holding the alert's event and its
        temporal neighbours; the Host opens it as a new analysis of the case.
        """
        from fireblade.core.alert_context import build_context
        from fireblade.core.collection import Collection

        if not 1 <= int(minutes) <= 1440:
            raise ServiceError("The context window is 1 to 1440 minutes.")
        case = self._case_for(identifier, index)
        alert = {key: ("" if value is None else str(value))
                 for key, value in self._row_values(case, row_id).items()}
        if not alert.get("Fireblade_EVTX_Source"):
            raise ServiceError("This row is not an alert: it carries no source EVTX reference.")
        folder = self._collection_of(case.path)
        pack = (ToolPack(Path(self.tools_root)) if self.tools_root
                else ToolPack(Path(tempfile.gettempdir()) / "pack"))
        # DuckDB refuses two connections with different configurations on one file.
        self.close_case(identifier)
        collection = Collection.reopen(folder, pack)
        result = build_context(collection, alert, str(case.path), int(row_id),
                              minutes=int(minutes))
        self._merge_session(identifier, folder / "collection.fireblade-session")
        position = self._analysis_index_of(identifier, result.get("analysis"))
        if position is None:
            raise ServiceError("The context was built but the case could not open it.")
        summary = {key: result[key] for key in
                   ("rule", "level", "minutes", "references", "events", "truncated",
                    "association", "machines", "timestamp") if key in result}
        summary["analysis"] = position
        summary["notes"] = list(result.get("notes") or [])
        return summary

    def alert_source_event(self, identifier: str, index: int, row_id: int) -> dict:
        """Where the event an alert came from lives, and how to filter on it."""
        case = self._case_for(identifier, index)
        alert = {key: ("" if value is None else str(value))
                 for key, value in self._row_values(case, row_id).items()}
        raw = alert.get("Fireblade_EVTX_Source") or ""
        try:
            paths = json.loads(raw) if raw.startswith("[") else [raw]
        except ValueError as exc:
            raise ServiceError("The EVTX reference of this alert is invalid.") from exc
        wanted = {str(Path(str(item))) for item in paths if item}
        if not wanted:
            raise ServiceError("This row is not an alert: it carries no source EVTX reference.")
        record = alert.get("RecordID") or alert.get("EventRecordId") or ""
        analyses = self._analyses(self.library.read(identifier))
        for position, entry in enumerate(analyses):
            if position == index:
                continue
            source = str((entry.get("source_info") or {}).get("path") or "")
            if not source or str(Path(source)) not in wanted:
                continue
            target = self._case_for(identifier, position)
            headers = [str(name) for name in target.headers]
            for name in ("EventRecordId", "RecordNumber", "RecordID"):
                column = next((item for item in headers if item.casefold() == name.casefold()), None)
                if column is None or not record:
                    continue
                view = View(filters=[Filter(headers.index(column), "eq", record)])
                with target.lock:
                    total = int(target.count(view))
                if total:
                    return {"analysis": position, "column": column, "value": record,
                            "matches": total, "source": source}
        raise ServiceError("The source event of this alert is not in any open analysis.")

    def detection_sources(self, identifier: str, collection: str) -> Path:
        """The alert CSV a detection run wrote, for the analyst to take away."""
        folder = self.library.folder(identifier) / "collections" / Path(str(collection)).name
        if not folder.is_dir():
            raise ServiceError("This collection does not exist in the case.")
        for pattern in ("results/hayabusa-*/Alertes Hayabusa.csv", "results/hayabusa-*/hayabusa.csv"):
            for path in sorted(folder.glob(pattern)):
                if path.is_file():
                    return path
        raise ServiceError("This collection carries no Hayabusa output.")

    # -- archive and release -----------------------------------------------

    def archive_case(self, identifier: str) -> dict:
        """Pack the case into an archive outside its folder, then free the folder."""
        from fireblade.core.case_storage import archive_and_release

        target = self.root / "archives" / (identifier[:8] + ".fireblade-archive.zip")
        target.parent.mkdir(parents=True, exist_ok=True)
        self.close_case(identifier)
        result = archive_and_release(self.library, identifier, target)
        return {"archive": str(target), "bytes": target.stat().st_size,
                "removed_bytes": int(result.get("removed_bytes") or 0)}

    def restore_case(self, identifier: str) -> dict:
        """Re-open an archive as a new case: the archive is the retained copy, and
        the emptied folder stays as the catalogue entry that points at it."""
        from fireblade.core.case_storage import restore_archive

        if not self.library.read(identifier).get("storage_archive"):
            raise ServiceError("This case is not archived: there is nothing to restore.")
        result = restore_archive(self.library, identifier)
        case = result.get("case") or {}
        restored = self.library.case(case.get("id")) if case.get("id") else {}
        return {"id": case.get("id"), "name": case.get("name"),
                "analyses": len(restored.get("analyses") or [])}

    # -- settings ----------------------------------------------------------

    def settings(self) -> dict:
        """What this instance runs with, and which readers are actually present."""
        from fireblade.core.collection import PARSERS

        pack = ToolPack(self.tools_root) if self.tools_root else None
        readers = {}
        for name in PARSERS:
            try:
                readers[name] = bool(pack and pack.available(name))
            except Exception:
                readers[name] = False
        hayabusa = bool(pack and Path(self.tools_root or "") / "Hayabusa" / "hayabusa" and
                        (Path(self.tools_root or "") / "Hayabusa" / "hayabusa").is_file())
        return {
            "cases_root": str(self.root),
            "tools_root": str(self.tools_root or ""),
            "page_size": Case.PAGE_SIZE,
            "readers": readers,
            "readers_ready": sum(1 for value in readers.values() if value),
            "hayabusa": hayabusa,
            "csv_encodings": list(self.CSV_ENCODINGS),
            "csv_delimiters": list(self.CSV_DELIMITERS),
        }

    # -- import profiles ---------------------------------------------------

    def profiles(self) -> dict:
        """The import profiles this instance recognises, plugins included."""
        from fireblade.core.profiles import all_profiles

        entries = []
        for profile in all_profiles():
            entries.append({
                "name": profile.name,
                "signature": list(profile.signature),
                "timestamps": list(profile.timestamp),
                "booleans": list(profile.booleans),
                "columns": list(profile.columns),
            })
        entries.sort(key=lambda item: item["name"].casefold())
        return {"profiles": entries, "count": len(entries)}

    def _plugins_dir(self) -> Path:
        from fireblade.core.profile_plugins import plugin_path

        return Path(self.plugins_root) if self.plugins_root else Path(plugin_path())

    def plugins(self) -> dict:
        """The presentation plugins this instance loads, and the ones it refuses.

        A presentation plugin declares columns and their types; the source values
        stay untouched. An invalid file is listed with its reason rather than
        silently skipped, so an analyst can repair it.
        """
        from fireblade.core.profile_plugins import load_plugins

        directory = self._plugins_dir()
        loaded, errors = load_plugins(directory if directory.exists() else None)
        files = sorted(path.name for path in directory.glob("*.json"))[:100] if directory.exists() else []
        return {"directory": str(directory), "exists": directory.exists(),
                "plugins": loaded, "errors": errors, "files": files}

    def install_plugin(self, payload: dict) -> dict:
        """Validate a presentation plugin and store it where the core will read it."""
        import hashlib

        from fireblade.core.layout import write_json
        from fireblade.core.profile_plugins import MAX_BYTES, validate_plugin

        data = validate_plugin(payload if isinstance(payload, dict) else {})
        encoded = json.dumps(data, ensure_ascii=False).encode("utf-8")
        if len(encoded) > MAX_BYTES:
            raise ServiceError("A presentation plugin is limited to 2 MB.")
        directory = self._plugins_dir()
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / (hashlib.sha256(data["name"].encode("utf-8")).hexdigest()[:24] + ".json")
        write_json(target, data)
        return {"name": data["name"], "path": str(target),
                "fields": {key: len(data.get(key) or [])
                           for key in ("signature", "columns", "timestamp", "booleans", "transforms")}}

    def create_profile(self, identifier: str, index: int, name: str) -> dict:
        """Build a profile from an open analysis, as the desktop's dialog does.

        The signature is the first three columns, the date column is the one the
        core would guess, and every column of the analysis is kept: a profile is a
        presentation, it never rewrites a value.
        """
        clean = (name or "").strip()
        if not clean:
            raise ServiceError("Give the profile a name.")
        from fireblade.core.timeline import guess_time_column

        case = self._case_for(identifier, index)
        headers = list(case.headers)
        if not headers:
            raise ServiceError("This analysis has no column to describe.")
        stamp = guess_time_column(headers)
        payload = {"name": clean,
                   "signature": headers[:min(3, len(headers))],
                   "columns": headers,
                   "timestamp": [headers[stamp]] if stamp is not None else [],
                   "booleans": [],
                   "transforms": []}
        return self.install_plugin(payload)

    # -- portable case -----------------------------------------------------

    def export_package(self, identifier: str, include_sources: bool = True) -> dict:
        """Write the case as a portable .fireblade archive and hand back a URL."""
        from fireblade.core.case_package import export_package

        data = self.library.read(identifier)
        # The snapshots come from the repaired path resolution, so a case written
        # on Windows packs here even though its session stores C:\… paths.
        documents = self._snapshots(identifier)
        active = 0 if documents else -1
        # The archive is written outside the case folder: a file inside it would
        # change while it is being packed, and the packer refuses that.
        target = self.root / "exports" / (identifier[:8] + ".fireblade")
        target.parent.mkdir(parents=True, exist_ok=True)
        self.close_case(identifier)
        result = export_package(self.library, data, documents, active, target,
                                include_sources=include_sources, include_case_files=True,
                                max_bytes=4 * 1024**4)
        return {"name": target.name, "bytes": target.stat().st_size,
                "url": f"/api/cases/{identifier}/package/download",
                "result": {k: str(v)[:120] for k, v in (result or {}).items()}}

    def package_file(self, identifier: str) -> Path:
        target = self.root / "exports" / (identifier[:8] + ".fireblade")
        if not target.is_file():
            raise ServiceError("No package has been exported for this case yet.")
        return target

    def import_package(self, source: str | Path) -> dict:
        """Open a .fireblade archive as a new case, every byte verified first."""
        from fireblade.core.case_package import import_package

        result = import_package(self.library, Path(source), max_bytes=4 * 1024**4)
        case = result.get("case") or {}
        return {"id": case.get("id"), "name": case.get("name"),
                "analyses": len(result.get("documents") or [])}

    # -- cell notes --------------------------------------------------------

    def cell_notes(self, identifier: str, index: int, row_ids: list[int] | None = None) -> dict:
        """Cell notes grouped by row, for the page on screen or a single row."""
        case = self._case_for(identifier, index)
        with case.lock:
            notes = case.cell_notes([int(value) for value in row_ids] if row_ids else None)
        grouped: dict[str, dict[str, str]] = {}
        for (row, column), note in notes.items():
            grouped.setdefault(str(row), {})[str(column)] = note
        return {"notes": grouped}

    def cell_note(self, identifier: str, index: int, row_id: int, column: int, note: str) -> dict:
        case = self._case_for(identifier, index)
        clean = (note or "").strip()
        with case.lock:
            case.set_cell_note(int(row_id), int(column), clean or None)
        return {"row_id": int(row_id), "column": int(column), "note": clean}

    # -- column layout -----------------------------------------------------

    DISPLAY_VIEW = "__fireblade_display__"

    def display(self, identifier: str, index: int) -> dict:
        """Widths, hidden and pinned columns, kept in the analysis like a view."""
        case = self._case_for(identifier, index)
        with case.lock:
            stored = case.views().get(self.DISPLAY_VIEW)
        if stored is None or not stored.header_state:
            return {"widths": {}, "hidden": [], "pinned": [], "pinned_right": []}
        try:
            layout = json.loads(stored.header_state)
        except ValueError:
            return {"widths": {}, "hidden": [], "pinned": [], "pinned_right": []}
        layout.setdefault("pinned_right", [])
        return layout

    def save_display(self, identifier: str, index: int, layout: dict) -> dict:
        clean = {
            "widths": {str(key): int(value) for key, value in (layout.get("widths") or {}).items()
                       if str(key).isdigit() and int(value) > 0},
            "hidden": [int(value) for value in layout.get("hidden") or [] if int(value) >= 0],
            "pinned": [int(value) for value in layout.get("pinned") or [] if int(value) >= 0],
            "pinned_right": [int(value) for value in layout.get("pinned_right") or [] if int(value) >= 0],
        }
        case = self._case_for(identifier, index)
        view = View(header_state=json.dumps(clean))
        with case.lock:
            case.save_view(self.DISPLAY_VIEW, view)
        return clean

    # -- saved views -------------------------------------------------------

    def views(self, identifier: str, index: int) -> dict:
        case = self._case_for(identifier, index)
        with case.lock:
            stored = case.views()
        return {"views": sorted(name for name in stored if not name.startswith("__"))}

    def save_view(self, identifier: str, index: int, name: str, view: dict) -> dict:
        """Keep the grid state under a name, with the core's own View object."""
        clean = (name or "").strip()
        if not clean or len(clean) > 120:
            raise ServiceError("Invalid view name (1 to 120 characters).")
        saved = View(
            search=str(view.get("search") or ""),
            filters=[Filter(int(item["column"]), str(item["operator"]), str(item.get("value", "")))
                     for item in view.get("filters") or []
                     if str(item.get("operator")) in OPERATORS],
            groups=[int(value) for value in view.get("groups") or []],
            sort_column=(int(view["sort"]) if view.get("sort") is not None else None),
            descending=bool(view.get("descending")),
            bookmarks_only=bool(view.get("bookmarks_only")),
        )
        case = self._case_for(identifier, index)
        with case.lock:
            case.save_view(clean, saved)
        return {"name": clean}

    def view(self, identifier: str, index: int, name: str) -> dict:
        case = self._case_for(identifier, index)
        with case.lock:
            stored = case.views().get(name)
        if stored is None:
            raise ServiceError("View not found.")
        return {"name": name, "search": stored.search,
                "filters": [{"column": f.column, "operator": f.operator, "value": f.value} for f in stored.filters],
                "groups": list(stored.groups), "sort": stored.sort_column,
                "descending": stored.descending, "bookmarks_only": stored.bookmarks_only}

    # -- colour rules ------------------------------------------------------

    RULES_VIEW = "__fireblade_rules__"

    def rules(self, identifier: str, index: int) -> dict:
        """The colour rules of this analysis, kept in its own views table."""
        case = self._case_for(identifier, index)
        with case.lock:
            stored = case.views().get(self.RULES_VIEW)
        rules = []
        if stored is not None:
            for rule in stored.format_rules:
                condition = getattr(rule, "condition", None)
                first = condition.children[0] if getattr(condition, "children", None) else None
                rules.append({
                    "column": getattr(first, "column", None),
                    "operator": getattr(first, "operator", "contains"),
                    "value": getattr(first, "value", ""),
                    "background": rule.background,
                    "foreground": rule.foreground,
                    "bold": bool(rule.bold),
                    "target": rule.target,
                    "enabled": bool(rule.enabled),
                })
        return {"rules": rules}

    def save_rules(self, identifier: str, index: int, rules: list) -> dict:
        """Store the rules with the core's own FormatRule/FilterGroup objects."""
        from fireblade.core.models import Filter, FilterGroup, FormatRule

        cleaned = []
        for item in rules or []:
            column = item.get("column")
            if not isinstance(column, int) or column < 0:
                raise ServiceError("Invalid rule column.")
            operator = item.get("operator", "contains")
            if operator not in OPERATORS:
                raise ServiceError(f"Unknown rule operator: {operator}")
            cleaned.append(FormatRule(
                condition=FilterGroup("and", [Filter(column, operator, str(item.get("value", "")))]),
                background=str(item.get("background") or "#fce2e2"),
                foreground=str(item.get("foreground") or "#202020"),
                bold=bool(item.get("bold")),
                target=item.get("target"),
                enabled=bool(item.get("enabled", True)),
            ))
        case = self._case_for(identifier, index)
        view = View(format_rules=cleaned)
        with case.lock:
            case.save_view(self.RULES_VIEW, view)
        return {"rules": rules, "saved": len(cleaned)}

    # -- process pivot -----------------------------------------------------

    def pivot(self, identifier: str, index: int, row_id: int) -> dict:
        """What launched this process: the anchor the desktop derives from one row,
        then the events around it across the case.

        The anchor is read by column name, then by what the value looks like, and
        nothing is concluded: the rows come back, the reading stays the analyst's.
        """
        from fireblade.core.pivot import anchor_of

        case = self._case_for(identifier, index)
        with case.lock:
            rows = case.rows_by_ids([int(row_id)])
            headers = list(case.headers)
        values = None
        if rows:
            row = rows.get(int(row_id)) or next(iter(rows.values()))
            values = list(row[1:]) if len(row) == len(headers) + 1 else list(row)
        anchor = anchor_of(headers, values) if values else None
        # EvtxECmd also fills a generic Payload column: a JSON blob is not a
        # process, and searching it would return noise. The pivot is offered only
        # when the row really names one.
        if anchor and str(anchor.get("token", "")).lstrip().startswith(("{", "[")):
            anchor = None
        if not anchor and values:
            # EvtxECmd keeps the process in PayloadData1..6 rather than in a named
            # column: the first value that looks like an executable names it.
            for value in values:
                text = str(value or "")
                found = re.search(r"[A-Za-z]:\\[^\"<>|\r\n]{1,240}?\.exe", text) or re.search(r"\b[\w.-]{1,80}\.exe\b", text, re.I)
                if not found:
                    continue
                raw = found.group(0)
                name = re.split(r"[\\/]", raw)[-1]
                moment = ""
                host = ""
                for index, column in enumerate(headers):
                    lowered = column.lower()
                    if not moment and lowered in ("timecreated", "timestamp", "date", "datetime"):
                        moment = str(values[index] or "")
                    if not host and lowered in ("computer", "computername", "hostname"):
                        host = str(values[index] or "")
                anchor = {"token": name, "host": host, "parent": "", "moment": moment,
                          "process": name, "command": text[:400]}
                break
        if not anchor:
            raise ServiceError("This row names neither a process nor a command to look for.")
        matches = []
        for entry in self._analyses(self.library.read(identifier)):
            if not entry["found"]:
                continue
            other = self._case_for(identifier, entry["index"])
            with other.lock:
                columns = list(other.headers)
                process_index = next((i for i, name in enumerate(columns)
                                      if name.lower() in ("image", "newprocessname", "processname",
                                                          "parentprocessname", "creatorprocessname")), None)
                search_view = View(search=anchor["token"])
                found = other.page(search_view, offset=0, limit=200)
                for row in found:
                    pieces = row[1:]
                    moment = str(pieces[process_index]) if process_index is not None and process_index < len(pieces) else ""
                    matches.append({
                        "analysis": entry["label"],
                        "row_id": json_value(row[0]),
                        "cells": [json_value(value) for value in pieces],
                    })
        return {"anchor": anchor, "matches": matches[:200], "total": len(matches)}

    # -- derived columns ---------------------------------------------------

    def add_derived(self, identifier: str, index: int, definition: dict) -> dict:
        """Add a computed column the way the desktop does: a validated definition,
        compiled to SQL over the raw rows, stored in the analysis itself."""
        from fireblade.core.derived import validate_definition

        clean = validate_definition(definition or {})
        case = self._case_for(identifier, index)
        with case.lock:
            case.add_derived_columns([clean])
        return {"columns": META_COLUMNS + list(case.headers), "added": clean.get("name")}

    def derived_columns(self, identifier: str, index: int) -> dict:
        case = self._case_for(identifier, index)
        with case.lock:
            return {"derived": list(getattr(case, "derived", []) or []),
                    "columns": META_COLUMNS + list(case.headers)}

    # -- import history ----------------------------------------------------

    def imports(self, identifier: str) -> dict:
        """Every import of the case, file by file, with its verdict and its reason.

        This is the desktop's Imports panel: an analyst who sees a folder half
        read must be able to say which file was not, and why.
        """
        folder = self.library.folder(identifier)
        collections = []
        for entry in sorted((folder / "collections").glob("import-*")) if (folder / "collections").is_dir() else []:
            report = entry / "collection.json"
            if not report.is_file():
                continue
            try:
                data = json.loads(report.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            files = []
            for item in data.get("files") or []:
                files.append({
                    "name": Path(str(item.get("path", ""))).name,
                    "path": str(item.get("path", "")),
                    "status": str(item.get("status", "")),
                    "reason": str(item.get("reason") or item.get("error") or ""),
                    "tools": list(item.get("tools") or []),
                })
            counts = {}
            for item in files:
                counts[item["status"]] = counts.get(item["status"], 0) + 1
            collections.append({
                "name": entry.name,
                "status": str(data.get("status", "")),
                "organization": data.get("organization", ""),
                "source": str(data.get("source", "")),
                "analyses": len(data.get("documents") or []),
                "files": files,
                "counts": counts,
            })
        return {"collections": collections}

    # -- import preview ----------------------------------------------------

    PREVIEW_BYTES = 256 * 1024
    PREVIEW_ROWS = 6
    # What the desktop's import dialog offers, and in the same order: the analyst
    # may override what the reader detects. `auto` and `None` keep the detection.
    CSV_ENCODINGS = ("auto", "utf-8", "utf-16", "utf-32", "cp1252", "latin-1")
    CSV_DELIMITERS = (",", "\t", ";", "|")

    @staticmethod
    def _decode_head(raw: bytes, encoding: str) -> str:
        """Decode the first block the way the import will read the file.

        A byte-order mark is stripped: the import's reader is handed UTF-8 without
        the BOM, so a header must not arrive as '\\ufeffTimestamp'. A truncated
        multi-byte character at the end of the block is a window boundary, not a
        corrupt file.
        """
        if raw.startswith(b"\xef\xbb\xbf") and encoding == "utf-8":
            encoding = "utf-8-sig"
        try:
            return raw.decode(encoding, errors="replace")
        except LookupError:
            return raw.decode("utf-8", errors="replace")

    @classmethod
    def _delimiter(cls, text: str, forced: str | None = None) -> tuple[str, list[list[str]]]:
        """The delimiter that gives a consistent table, and its first records.

        The import sniffs the schema itself; the preview must not contradict it.
        Every candidate is parsed and the one that yields the most columns with
        the same count on the sample lines wins. A comma file is never read as
        one semicolon column.
        """
        best = None
        csv.field_size_limit(max(csv.field_size_limit(), 16 * 1024 * 1024))
        candidates = (forced,) if forced in cls.CSV_DELIMITERS else cls.CSV_DELIMITERS
        for delimiter in candidates:
            try:
                records = [record for record in csv.reader(text.splitlines(), delimiter=delimiter)
                           if record and any(field.strip() for field in record)]
            except csv.Error:
                continue
            if not records:
                continue
            width = len(records[0])
            # A forced separator that yields one column is what the analyst asked
            # for: show it instead of claiming the file has no readable header.
            if width < (1 if forced else 2):
                continue
            consistent = sum(1 for record in records[1:8] if len(record) == width)
            score = (consistent, width)
            if best is None or score > best[0]:
                best = (score, delimiter, records)
        if best is None:
            return ",", []
        return best[1], best[2]

    def preview_source(self, source: str | Path, delimiter: str | None = None,
                       encoding: str | None = None) -> dict:
        """What reading this file would produce, before anything is written.

        The desktop lets the analyst look at the columns and the recognised profile
        before confirming an import; the Host edition answers the same question over
        HTTP. The profile lookup is the core's own `detect_profile`, and the mapping
        is the one `profile_view` would apply, so the preview cannot drift from the
        import. Nothing is copied, hashed or written here.
        """
        from fireblade.core.collection import identify

        path = Path(source).resolve()
        if not path.exists():
            raise ServiceError("The file to preview does not exist.")
        if path.is_dir():
            entries = []
            for item in sorted(path.rglob("*")):
                if len(entries) >= 200:
                    break
                if item.is_file():
                    try:
                        tools = identify(item)
                    except (OSError, ValueError):
                        tools = []
                    entries.append({"name": str(item.relative_to(path)), "readers": tools})
            return {"kind": "folder", "name": path.name, "path": str(path),
                    "files": entries, "count": len(entries),
                    "note": "A folder is inventoried file by file: each format is read by its own reader."}

        size = path.stat().st_size
        try:
            tools = identify(path)
        except (OSError, ValueError) as exc:
            raise ServiceError(f"The file could not be identified: {exc}") from exc
        preview = {"kind": "unknown", "name": path.name, "path": str(path), "size": size,
                   "readers": tools, "profile": None, "columns": [], "rows": []}
        if not tools:
            preview["note"] = "No reader recognises this file: it would be recorded as not imported, with its reason."
            return preview
        if tools != ["native"]:
            preview["kind"] = "artifact"
            preview["note"] = ("The reader runs on import and writes its own columns; "
                               "there is no profile to confirm before it reads.")
            return preview

        from fireblade.core.csv_preamble import preamble_lines
        from fireblade.core.encodings import bom_encoding

        detected = bom_encoding(path)
        chosen = encoding if encoding and encoding != "auto" else detected
        with path.open("rb") as stream:
            raw = stream.read(self.PREVIEW_BYTES)
        text = self._decode_head(raw, chosen)
        lines = text.splitlines(keepends=True)
        skip = 0
        try:
            skip = preamble_lines(io.StringIO(text))
        except (csv.Error, ValueError):
            skip = 0
        body = "".join(lines[skip:])
        delimiter, records = self._delimiter(body, delimiter)
        if not records:
            preview["kind"] = "table"
            preview["note"] = "The file carries no readable header."
            return preview
        headers = [str(name).strip() for name in records[0]]
        rows = [[str(value)[:400] for value in record[:len(headers)]]
                for record in records[1:1 + self.PREVIEW_ROWS]]
        from fireblade.core.profiles import detect_profile, profile_view, profile_transformations

        profile = detect_profile(headers)
        columns = [{"index": index, "name": name, "role": "column"}
                   for index, name in enumerate(headers)]
        mapping = {"order": list(headers), "timestamps": [], "booleans": [],
                   "derived": [], "sort": None, "format_rules": 0, "matched": [], "missing": []}
        if profile is not None:
            view, order = profile_view(profile, headers)
            in_file = {name.casefold() for name in headers}
            mapping["order"] = [headers[index] for index in order]
            mapping["timestamps"] = [headers[index] for index in view.timestamp_columns]
            mapping["booleans"] = [headers[index] for index in view.boolean_columns]
            mapping["sort"] = headers[view.sort_column] if view.sort_column is not None else None
            mapping["format_rules"] = len(view.format_rules)
            mapping["matched"] = [name for name in profile.signature if name.casefold() in in_file]
            mapping["missing"] = [name for name in profile.columns if name.casefold() not in in_file]
            mapping["derived"] = [
                {"name": item.get("name"), "operation": item.get("operation"),
                 "columns": list(item.get("columns") or []), "format": item.get("format", "")}
                for item in profile_transformations(profile, [h for h in headers if not h.startswith("Fireblade_")])
            ]
            roles = {name.casefold(): "timestamp" for name in mapping["timestamps"]}
            roles.update({name.casefold(): "boolean" for name in mapping["booleans"]})
            for column in columns:
                column["role"] = roles.get(column["name"].casefold(), "column")
            preview["kind"] = "table"
            preview["profile"] = profile.name
            preview["note"] = (f"Recognised profile: {profile.name}. "
                               "The same mapping the import will apply is shown below.")
        else:
            preview["kind"] = "table"
            preview["note"] = ("No declared profile matches these headers: the file is read as a "
                               "plain table, with no timestamp or boolean mapping.")
        preview["delimiter"] = {"\t": "tab", ",": "comma", ";": "semicolon", "|": "pipe"}[delimiter]
        preview["encoding"] = chosen
        preview["encoding_detected"] = detected
        preview["columns"] = columns
        preview["rows"] = rows
        preview["mapping"] = mapping
        return preview

    # -- global search -----------------------------------------------------

    def search(self, identifier: str, text: str, limit: int = 50) -> dict:
        """Search every analysis of the case, and say where the hits are."""
        needle = (text or "").strip()
        if not needle:
            raise ServiceError("Type some text to search for.")
        results = []
        total = 0
        for entry in self._analyses(self.library.read(identifier)):
            if not entry["found"]:
                continue
            case = self._case_for(identifier, entry["index"])
            with case.lock:
                view = View(search=needle)
                count = int(case.count(view))
                total += count
                rows = []
                if count:
                    for row in case.page(view, offset=0, limit=min(limit, 50)):
                        rows.append({
                            "row_id": json_value(row[0]),
                            "cells": [json_value(value) for value in row[1:]],
                        })
            results.append({"index": entry["index"], "label": entry["label"],
                            "count": count, "rows": rows})
        return {"text": needle, "total": total, "analyses": results}

    # -- actions and tracking ----------------------------------------------

    ACTION_COLUMNS = ("id", "title", "detail", "owner", "status", "priority", "type",
                      "intervenant", "date", "due", "machine", "reference", "tags", "closed")

    def actions_csv(self, identifier: str) -> str:
        """The action tracking as a spreadsheet, one row per action.

        The desktop exports the same columns; the order is the one the tracking
        panel shows, so a manager can open the file and read it without a legend.
        """
        from fireblade.core.case_workspace import load

        data = load(self.library.folder(identifier))
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer)
        writer.writerow(self.ACTION_COLUMNS)
        for item in data.get("actions", []):
            row = []
            for key in self.ACTION_COLUMNS:
                value = item.get(key)
                if isinstance(value, (list, tuple)):
                    value = "; ".join(str(part) for part in value)
                row.append("" if value is None else str(value))
            writer.writerow(row)
        return buffer.getvalue()

    def workspace(self, identifier: str) -> dict:
        """The operational record of the case: actions, entities, noted indicators."""
        from fireblade.core.case_workspace import load

        folder = self.library.folder(identifier)
        data = load(folder)
        return {
            "revision": data.get("revision"),
            "actions": [{key: item.get(key) for key in
                         ("id", "title", "detail", "owner", "status", "priority", "type",
                          "intervenant", "date", "due", "machine", "reference", "tags", "closed")}
                        for item in data.get("actions", [])],
            "entities": [{key: item.get(key) for key in ("id", "kind", "label", "hostname", "ip", "os", "notes", "tags")}
                         for item in data.get("entities", [])],
            "iocs": [{key: item.get(key) for key in ("id", "value", "kind", "label", "status")}
                     for item in data.get("iocs", [])],
        }

    def add_action(self, identifier: str, fields: dict) -> dict:
        from fireblade.core.case_workspace import add_action

        title = (fields or {}).get("title", "").strip()
        if not title:
            raise ServiceError("An action title is required.")
        allowed = {key: value for key, value in (fields or {}).items()
                   if key in ("detail", "owner", "status", "priority", "type", "intervenant",
                              "date", "due", "machine", "reference", "tags") and value not in (None, "")}
        return add_action(self.library.folder(identifier), title, **allowed)

    def update_action(self, identifier: str, action_id: str, fields: dict) -> dict:
        from fireblade.core.case_workspace import update_action

        allowed = {key: value for key, value in (fields or {}).items()
                   if key in ("title", "detail", "owner", "status", "priority", "type",
                              "intervenant", "date", "due", "machine", "reference") and value is not None}
        if not allowed:
            raise ServiceError("Nothing to change.")
        update_action(self.library.folder(identifier), action_id, **allowed)
        return self.workspace(identifier)

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
            raise ServiceError("Nothing to change.")
        data = self.library.update(identifier, **fields)
        return self._summary(data)

    def destroy(self, identifier: str, method: str = "dod3", operator: str = "",
                witness: str = "", reason: str = "", confirmation: str = "") -> dict:
        """Destroy the case the way the desktop does, and keep the certificate outside."""
        from fireblade.core.case_destruction import destroy_case

        data = self.library.read(identifier)
        if (confirmation or "").strip() != data.get("name", ""):
            raise ServiceError("The confirmation must repeat the case name exactly.")
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
            raise ServiceError("This case holds no analysis.")
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
            raise ServiceError("Invalid report name.")
        path = self.library.folder(identifier) / "reports" / name
        if not path.is_file():
            raise ServiceError("Report not found.")
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
            raise ServiceError("No indicator was recognised in this text.")
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
        result = {"indicators": len(indicators), "scanned": scanned, "hits": hits,
                  "by_kind": summary, "truncated": len(hits) >= limit}
        # A hunt leaves a record: the same indicators can be replayed on the case
        # later, which is what the desktop's saved hunts list is.
        hunts = self.library.folder(identifier) / "hunts"
        hunts.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        record = dict(started=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                      status="complete" if not result["truncated"] else "truncated",
                      text=(text or "")[:20000], **result)
        (hunts / f"{stamp}.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        result["saved"] = f"{stamp}.json"
        return result

    def hunts(self, identifier: str) -> dict:
        folder = self.library.folder(identifier) / "hunts"
        entries = []
        if folder.is_dir():
            for path in sorted(folder.glob("*.json"), reverse=True):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                entries.append({"name": path.name, "started": data.get("started", ""),
                                "status": data.get("status", ""),
                                "indicators": data.get("indicators", 0),
                                "hits": len(data.get("hits") or [])})
        return {"hunts": entries[:50]}

    def hunt(self, identifier: str, name: str) -> dict:
        if "/" in name or "\\" in name or not name.endswith(".json"):
            raise ServiceError("Invalid hunt name.")
        path = self.library.folder(identifier) / "hunts" / name
        if not path.is_file():
            raise ServiceError("Hunt not found.")
        return json.loads(path.read_text(encoding="utf-8"))

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
                raise ServiceError("This case holds no analysis.")
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

    def _merge_session(self, identifier: str, session_path: Path, collections=None,
                       active_collection=None) -> tuple[int, int]:
        """Add a collection's documents to the case session; return (first index, count).

        `InvestigationLibrary.save` writes the list it is given: appending is the
        caller's job. Every import and every detection goes through here, so a
        second import or a run after an import never drops what was already open.
        """
        data = self.library.read(identifier)
        folder = self.library.folder(identifier)
        earlier: list = []
        previous = data.get("session")
        if previous:
            try:
                earlier, _earlier_active = read_session(folder / previous)
            except (OSError, ValueError):
                earlier = []
        incoming, active = ([], -1)
        if Path(session_path).is_file():
            incoming, active = read_session(Path(session_path))
        if not incoming:
            return len(earlier), 0
        # A collection's session names every document it ever produced, so a second
        # run of the same collection would add the same analyses again. The path is
        # the identity of an analysis file.
        known = {str(Path(str(item.path))) for item in earlier}
        fresh = [(position, item) for position, item in enumerate(incoming)
                 if str(Path(str(item.path))) not in known]
        if not fresh:
            return len(earlier), 0
        combined = list(earlier) + [item for _position, item in fresh]
        new_active = next((len(earlier) + number for number, (position, _item)
                           in enumerate(fresh) if position == active), len(combined) - 1)
        active_index = new_active if 0 <= new_active < len(combined) else len(combined) - 1
        known = ([entry for entry in (data.get("collections") or []) if isinstance(entry, dict)]
                 if collections is None else collections)
        # Indexes shift: no cached handle may survive the rewrite.
        self.close_case(identifier)
        self.library.save(identifier, combined, active_index, known,
                          active_collection if active_collection is not None
                          else data.get("active_collection"),
                          data.get("revision"))
        return len(earlier), len(incoming)

    def import_source(self, identifier: str, source: str | Path, tools_root: str | Path | None = None,
                      organization: str = "files", progress=None, delimiter: str | None = None,
                      encoding: str | None = None) -> dict:
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
            raise ServiceError("The source to import is missing.")
        output = folder / "collections" / ("import-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"))
        if output.exists():
            output = folder / "collections" / ("import-" + uuid.uuid4().hex[:8])
        output.parent.mkdir(parents=True, exist_ok=True)
        pack = ToolPack(Path(tools_root or self.tools_root)) if (tools_root or self.tools_root) else ToolPack(Path(tempfile.gettempdir()) / "fireblade-pack")
        collection = Collection(source, output, pack, progress=progress or (lambda _text: None),
                                organization=organization,
                                delimiter=delimiter if delimiter in self.CSV_DELIMITERS else None,
                                encoding=encoding if encoding in self.CSV_ENCODINGS else "auto")
        report = collection.parse()
        session = output / "collection.fireblade-session"
        if not session.is_file():
            return {"status": report.get("status"), "analyses": 0, "files": len(report.get("files") or []),
                    "collection": str(output), "message": "No analysis produced: the format was not recognised."}
        # The session is the workspace: an import adds its analyses to the ones
        # already loaded, exactly as the desktop does.
        collections = [entry for entry in (data.get("collections") or []) if isinstance(entry, dict)]
        collections.append({"path": str(output), "name": output.name,
                            "imported": datetime.now(timezone.utc).isoformat()})
        first, added = self._merge_session(identifier, session, collections=collections,
                                           active_collection=str(output))
        return {
            "status": report.get("status", "complete"),
            "analyses": added,
            "first_analysis": first,
            "files": len(report.get("files") or []),
            "collection": str(output),
        }

    # -- one analysis ------------------------------------------------------

    def close_analysis(self, identifier: str, index: int) -> dict:
        """Take one analysis out of the workspace; its file stays in the case.

        The desktop closes a tab the same way: the session is rewritten without
        that entry and the `.timeline` file keeps living in the case folder, so
        nothing is destroyed by closing a view.
        """
        data = self.library.read(identifier)
        folder = self.library.folder(identifier)
        snapshots, active = ([], -1)
        session = data.get("session")
        if session:
            snapshots, active = read_session(folder / session)
        if not 0 <= index < len(snapshots):
            raise ServiceError("This analysis does not exist in the case.")
        remaining = [item for position, item in enumerate(snapshots) if position != index]
        if not remaining:
            new_active = -1
        elif active <= index:
            new_active = max(0, min(active, len(remaining) - 1))
        else:
            new_active = active - 1
        collections = [entry for entry in (data.get("collections") or []) if isinstance(entry, dict)]
        # Indexes shift: no cached handle may survive the rewrite.
        self.close_case(identifier)
        self.library.save(identifier, remaining, new_active, collections,
                          data.get("active_collection"), data.get("revision"))
        return {"analyses": len(remaining), "active": new_active}

    def _case_for(self, identifier: str, index: int) -> Case:
        key = (identifier, index)
        with self._lock:
            existing = self._open.get(key)
            if existing is not None:
                return existing
            data = self.library.read(identifier)
            analyses = self._analyses(data)
            if not 0 <= index < len(analyses):
                raise ServiceError("This analysis does not exist in the case.")
            entry = analyses[index]
            if not entry["found"]:
                raise ServiceError(
                    "The analysis file is missing from the case "
                    f"(recorded path: {entry['recorded_path']}).")
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
             path: list[str] | None = None, sorts: list[tuple[int, bool]] | None = None,
             interval: str = "", expression: dict | None = None) -> dict:
        case = self._case_for(identifier, index)
        view = View(search=search or "", filters=[], bookmarks_only=bool(bookmarks_only))
        for column, operator, value in filters or ():
            if operator not in OPERATORS:
                raise ServiceError(f"Unknown filter operator: {operator}")
            if not 0 <= column < len(case.headers):
                raise ServiceError("Filter column outside the analysis.")
            view.filters.append(Filter(column, operator, value))
        if expression:
            from fireblade.core.models import condition_from_dict
            view.expression = condition_from_dict(expression)
        keys = list(sorts or ())
        if not keys and sort is not None:
            keys = [(sort, bool(descending))]
        for column, _descending in keys:
            if not 0 <= int(column) < len(case.headers):
                raise ServiceError("Sort column outside the analysis.")
        if keys:
            view.sort_column, view.descending = int(keys[0][0]), bool(keys[0][1])
            view.sort_type = "text"
            view.sorts = [SortKey(int(column), "text", bool(flag)) for column, flag in keys]
        if groups:
            for column in groups:
                if not 0 <= int(column) < len(case.headers):
                    raise ServiceError("Grouping column outside the analysis.")
            view.groups = [int(column) for column in groups]
            if interval:
                if interval not in ("value", "year", "quarter", "month", "week", "day", "hour", "minute", "second"):
                    raise ServiceError("Unknown grouping interval.")
                view.group_intervals = {str(column): interval for column in view.groups}
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
            raise ServiceError("Expected filter format: column:operator:value")
        try:
            column = int(parts[0])
        except ValueError as exc:
            raise ServiceError("Invalid column index.") from exc
        filters.append((column, parts[1], parts[2]))
    return filters


def read_rows_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        yield from csv.reader(stream)
