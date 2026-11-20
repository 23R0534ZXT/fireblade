"""Fireblade Host: the case library served over HTTP, next to the desktop app."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from fireblade.web.service import Library, ServiceError, parse_filters

STATIC = Path(__file__).with_name("static")


def _store_upload(folder: Path, file: UploadFile) -> Path:
    """Write the sent file into the case's evidence folder under a free name.

    Overwriting an existing evidence file would change the bytes an earlier import
    recorded a hash for, so a second upload of the same name becomes `name-2.ext`.
    The collection then sees a duplicate by hash and says so, which is the truth.
    """
    name = Path(file.filename or "evidence").name
    if not name or name in (".", ".."):
        raise HTTPException(status_code=400, detail="Invalid file name.")
    evidence = folder / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    target = evidence / name
    if target.exists():
        stem, suffix = Path(name).stem, Path(name).suffix
        index = 2
        while target.exists():
            target = evidence / f"{stem}-{index}{suffix}"
            index += 1
    with target.open("wb") as stream:
        while chunk := file.file.read(1024 * 1024):
            stream.write(chunk)
    return target


def create_app(root: str | Path, version: str = "", tools_root: str | Path | None = None,
               plugins_root: str | Path | None = None) -> FastAPI:
    library = Library(root, tools_root=tools_root, plugins_root=plugins_root)
    app = FastAPI(title="Fireblade Host", version=version or "0", docs_url="/api/docs", openapi_url="/api/openapi.json")

    @app.exception_handler(ServiceError)
    async def _service_error(_request, exc: ServiceError):
        return JSONResponse(status_code=400, content={"error": str(exc)})

    @app.on_event("shutdown")
    def _shutdown():
        library.close()

    @app.get("/health")
    def health():
        catalogue = library.cases()
        return {
            "status": "ok",
            "version": version or "0",
            "root": catalogue["root"],
            "cases": len(catalogue["cases"]),
            "errors": len(catalogue["errors"]),
        }

    @app.get("/api/cases")
    def cases():
        return library.cases()

    @app.post("/api/cases")
    def create_case(payload: dict):
        payload = payload or {}
        try:
            return library.create_case(payload.get("name") or "Untitled case",
                                       payload.get("description", ""),
                                       payload.get("environment", "unspecified"))
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.patch("/api/cases/{identifier}")
    def update_case(identifier: str, payload: dict):
        payload = payload or {}
        try:
            return library.update_case(identifier, payload.get("name"), payload.get("description"))
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/destroy")
    def destroy(identifier: str, payload: dict):
        payload = payload or {}
        try:
            return library.destroy(identifier, payload.get("method", "dod3"),
                                   payload.get("operator", ""), payload.get("witness", ""),
                                   payload.get("reason", ""), payload.get("confirmation", ""))
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/cases/{identifier}")
    def case(identifier: str):
        try:
            return library.case(identifier)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/import")
    def import_source(identifier: str, payload: dict):
        source = (payload or {}).get("source")
        if not source:
            raise HTTPException(status_code=400, detail="A 'source' field is required.")
        try:
            return library.import_source(identifier, source, tools_root=tools_root,
                                         organization=(payload or {}).get("organization", "files"),
                                         delimiter=(payload or {}).get("delimiter") or None,
                                         encoding=(payload or {}).get("encoding") or None)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/cases/{identifier}/analyses/{index}")
    def close_analysis(identifier: str, index: int):
        """Close one analysis of the workspace; the file stays in the case."""
        try:
            return library.close_analysis(identifier, index)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/preview")
    def preview_source(identifier: str, payload: dict):
        """What an import of this server path would produce, before it runs."""
        source = (payload or {}).get("source")
        if not source:
            raise HTTPException(status_code=400, detail="A 'source' field is required.")
        library.library.folder(identifier)  # the case must exist
        try:
            return library.preview_source(source,
                                          delimiter=(payload or {}).get("delimiter") or None,
                                          encoding=(payload or {}).get("encoding") or None)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/preview-upload")
    def preview_upload(identifier: str, file: UploadFile = File(...),
                       delimiter: str | None = Form(None), encoding: str | None = Form(None)):
        """The browser hands the file over, the preview reads it, nothing is imported.

        The bytes land in the case's own evidence folder, the same place the import
        reads them from: confirming the preview does not send them a second time.
        """
        folder = library.library.folder(identifier)
        try:
            return library.preview_source(_store_upload(folder, file), delimiter=delimiter,
                                          encoding=encoding)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/upload")
    def upload(identifier: str, organization: str = "files", file: UploadFile = File(...),
               delimiter: str | None = Form(None), encoding: str | None = Form(None)):
        """The browser cannot hand over a server path: the file is sent, stored in
        the case's own evidence folder, then read by the same collection."""
        folder = library.library.folder(identifier)
        target = _store_upload(folder, file)
        try:
            return library.import_source(identifier, target, tools_root=tools_root,
                                         organization=organization, delimiter=delimiter,
                                         encoding=encoding)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/cases/{identifier}/search")
    def search(identifier: str, text: str = "", limit: int = 50):
        try:
            return library.search(identifier, text, limit=limit)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/cases/{identifier}/hunts")
    def hunts(identifier: str):
        return library.hunts(identifier)

    @app.get("/api/cases/{identifier}/hunts/{name}")
    def hunt(identifier: str, name: str):
        try:
            return library.hunt(identifier, name)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/graph/nodes")
    def add_graph_node(identifier: str, payload: dict):
        """A free node: a machine or a step the findings do not carry."""
        label = (payload or {}).get("label")
        try:
            return library.add_graph_node(identifier, label,
                                          tags=(payload or {}).get("tags") or [],
                                          kind=(payload or {}).get("kind") or "custom")
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/cases/{identifier}/graph")
    def graph(identifier: str, navigator: bool = False):
        try:
            return library.graph(identifier, navigator=navigator)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/detect")
    def detect(identifier: str, payload: dict):
        try:
            return library.detect(identifier, (payload or {}).get("min_level", "low"))
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/analyses/{index}/cellnotes")
    def cell_notes(identifier: str, index: int, payload: dict):
        rows = (payload or {}).get("row_ids") or []
        try:
            return library.cell_notes(identifier, index, [int(value) for value in rows])
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/analyses/{index}/cellnote")
    def cell_note(identifier: str, index: int, payload: dict):
        try:
            row_id = int((payload or {}).get("row_id"))
            column = int((payload or {}).get("column"))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="row_id and column are required.") from exc
        try:
            return library.cell_note(identifier, index, row_id, column, (payload or {}).get("note", ""))
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/cases/{identifier}/analyses/{index}/display")
    def display(identifier: str, index: int):
        return library.display(identifier, index)

    @app.post("/api/cases/{identifier}/analyses/{index}/display")
    def save_display(identifier: str, index: int, payload: dict):
        try:
            return library.save_display(identifier, index, payload or {})
        except (ServiceError, ValueError, OSError, KeyError, TypeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/cases/{identifier}/analyses/{index}/views")
    def views(identifier: str, index: int):
        return library.views(identifier, index)

    @app.post("/api/cases/{identifier}/analyses/{index}/views")
    def save_view(identifier: str, index: int, payload: dict):
        try:
            return library.save_view(identifier, index, (payload or {}).get("name", ""),
                                     (payload or {}).get("view") or {})
        except (ServiceError, ValueError, OSError, KeyError, TypeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/cases/{identifier}/analyses/{index}/views/{name}")
    def view(identifier: str, index: int, name: str):
        try:
            return library.view(identifier, index, name)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/cases/{identifier}/analyses/{index}/rules")
    def rules(identifier: str, index: int):
        return library.rules(identifier, index)

    @app.post("/api/cases/{identifier}/analyses/{index}/rules")
    def save_rules(identifier: str, index: int, payload: dict):
        try:
            return library.save_rules(identifier, index, (payload or {}).get("rules", []))
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/analyses/{index}/pivot")
    def pivot(identifier: str, index: int, payload: dict):
        try:
            row_id = int((payload or {}).get("row_id"))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="row_id is required.") from exc
        try:
            return library.pivot(identifier, index, row_id)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/cases/{identifier}/analyses/{index}/derived")
    def derived_columns(identifier: str, index: int):
        return library.derived_columns(identifier, index)

    @app.post("/api/cases/{identifier}/analyses/{index}/derived")
    def add_derived(identifier: str, index: int, payload: dict):
        try:
            return library.add_derived(identifier, index, payload or {})
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/cases/{identifier}/imports")
    def imports(identifier: str):
        try:
            return library.imports(identifier)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/plugins")
    def plugins():
        """The presentation plugins this instance loads, with their errors."""
        try:
            return library.plugins()
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/plugins")
    def install_plugin(payload: dict):
        """Install a presentation plugin: declared columns and types, no values."""
        plugin = (payload or {}).get("plugin", payload)
        try:
            return library.install_plugin(plugin)
        except (ServiceError, ValueError, TypeError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/analyses/{index}/profiles")
    def create_profile(identifier: str, index: int, payload: dict):
        """Turn the columns of an open analysis into a named presentation profile."""
        name = (payload or {}).get("name")
        if not name:
            raise HTTPException(status_code=400, detail="A 'name' field is required.")
        try:
            return library.create_profile(identifier, index, name)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/profiles")
    def profiles():
        """The declared import profiles: read-only, the same list the desktop edits."""
        return library.profiles()

    @app.get("/api/cases/{identifier}/actions/export")
    def export_actions(identifier: str):
        try:
            text = library.actions_csv(identifier)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        name = f"fireblade-{identifier[:8]}-actions.csv"
        return Response(content=text, media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{name}"'})

    @app.get("/api/cases/{identifier}/workspace")
    def workspace(identifier: str):
        try:
            return library.workspace(identifier)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/entities")
    def add_entity(identifier: str, payload: dict):
        """Declare a machine or an account: the graph and the report read them."""
        try:
            return library.add_entity(identifier, payload)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/iocs")
    def add_indicators(identifier: str, payload: dict):
        """Track one indicator, or a pasted list, in the case."""
        values = (payload or {}).get("values") or (payload or {}).get("value") or ""
        try:
            return library.add_indicator(identifier, values,
                                         source=(payload or {}).get("source") or "",
                                         label=(payload or {}).get("label") or "",
                                         status=(payload or {}).get("status") or "new",
                                         tags=(payload or {}).get("tags") or [])
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/cases/{identifier}/iocs/{ioc_id}")
    def remove_indicator(identifier: str, ioc_id: str):
        try:
            return library.remove_indicator(identifier, ioc_id)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/actions")
    def add_action(identifier: str, payload: dict):
        try:
            return library.add_action(identifier, payload or {})
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.patch("/api/cases/{identifier}/actions/{action_id}")
    def update_action(identifier: str, action_id: str, payload: dict):
        try:
            return library.update_action(identifier, action_id, payload or {})
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/archive")
    def archive_case(identifier: str):
        try:
            return library.archive_case(identifier)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/restore")
    def restore_case(identifier: str):
        try:
            return library.restore_case(identifier)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/settings")
    def settings():
        try:
            return library.settings()
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/package")
    def export_package(identifier: str, payload: dict | None = None):
        try:
            return library.export_package(identifier, bool((payload or {}).get("include_sources", True)))
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/cases/{identifier}/package/download")
    def package_file(identifier: str):
        try:
            path = library.package_file(identifier)
        except ServiceError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return FileResponse(path, media_type="application/zip", filename=path.name)

    @app.post("/api/cases/import-package")
    def import_package(file: UploadFile = File(...)):
        name = Path(file.filename or "case.fireblade").name
        if not name.endswith(".fireblade"):
            raise HTTPException(status_code=400, detail="A case package carries the .fireblade extension.")
        staging = Path(tempfile.mkdtemp(prefix="fireblade-import-"))
        target = staging / name
        with target.open("wb") as stream:
            while chunk := file.file.read(1024 * 1024):
                stream.write(chunk)
        try:
            return library.import_package(target)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        finally:
            try:
                target.unlink(missing_ok=True)
                staging.rmdir()
            except OSError:
                pass

    @app.post("/api/cases/{identifier}/report")
    def report(identifier: str, payload: dict):
        payload = payload or {}
        try:
            return library.report(identifier, payload.get("title") or "Fireblade report",
                                  payload.get("description", ""),
                                  bookmarks_only=bool(payload.get("bookmarks_only", True)),
                                  limit=int(payload.get("limit", 2000)))
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/cases/{identifier}/reports/{name}")
    def report_file(identifier: str, name: str):
        try:
            path = library.report_file(identifier, name)
        except ServiceError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return FileResponse(path, media_type="text/html", filename=name)

    @app.post("/api/cases/{identifier}/analyses/{index}/rows/{row_id}/context")
    def alert_context(identifier: str, index: int, row_id: int, minutes: int = 5):
        """The EVTX events around an alert, as a new analysis of the case."""
        try:
            return library.alert_context(identifier, index, row_id, minutes=minutes)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/analyses/{index}/rows/{row_id}/source")
    def alert_source_event(identifier: str, index: int, row_id: int):
        """Which analysis holds the event an alert came from, and how to filter on it."""
        try:
            return library.alert_source_event(identifier, index, row_id)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/analyses/{index}/bookmark-finding")
    def bookmark_finding(identifier: str, index: int, payload: dict):
        """Mark every alert of a finding in one gesture."""
        finding = (payload or {}).get("finding")
        if not isinstance(finding, dict):
            raise HTTPException(status_code=400, detail="A 'finding' object is required.")
        try:
            return library.bookmark_finding(identifier, index, finding,
                                            note=(payload or {}).get("note") or None)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/cases/{identifier}/detection/{collection}/sources")
    def detection_sources(identifier: str, collection: str):
        """The alert CSV a detection run wrote."""
        try:
            path = library.detection_sources(identifier, collection)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return FileResponse(path, media_type="text/csv", filename=path.name)

    @app.post("/api/cases/{identifier}/analyses/{index}/ioc")
    def ioc(identifier: str, index: int, payload: dict):
        text = (payload or {}).get("text", "")
        try:
            return library.ioc_scan(identifier, index, text)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/cases/{identifier}/timeline")
    def timeline(identifier: str, start: int | None = None, end: int | None = None,
                 offset: int = 0, text: str = "", kind: str = "text", dates: str = ""):
        options = None
        if dates:
            try:
                options = json.loads(dates)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="'dates' must be a JSON object.") from exc
        try:
            return library.timeline(identifier, start=start, end=end, offset=offset, text=text,
                                    kind=kind, dates=options)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/cases/{identifier}/analyses/{index}/bookmarks")
    def bookmarks(identifier: str, index: int):
        return library.bookmarks(identifier, index)

    @app.post("/api/cases/{identifier}/analyses/{index}/bookmark")
    def bookmark(identifier: str, index: int, payload: dict):
        try:
            row_id = int((payload or {}).get("row_id"))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="row_id is required.") from exc
        column = (payload or {}).get("column")
        return library.bookmark(identifier, index, row_id,
                                (payload or {}).get("note", ""),
                                None if column in (None, "") else int(column))

    @app.get("/api/cases/{identifier}/analyses/{index}/columns")
    def columns(identifier: str, index: int):
        return {"columns": library.columns(identifier, index)}

    @app.get("/api/cases/{identifier}/analyses/{index}/rows")
    def rows(identifier: str, index: int, offset: int = 0, limit: int = 200,
             search: str = "", sort: int | None = None, descending: bool = False,
             bookmarks_only: bool = False, group: list[int] = Query(default=[]),
             path: list[str] = Query(default=[]), sortkey: list[str] = Query(default=[]),
             interval: str = "", expression_json: str = "",
             filter: list[str] = Query(default=[])):
        # sortkey=3:desc — several keys, applied in the order they are sent.
        sorts = []
        for raw in sortkey:
            column, _, flag = raw.partition(":")
            try:
                sorts.append((int(column), flag == "desc"))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Invalid sort key.") from exc
        expression = None
        if expression_json:
            try:
                expression = json.loads(expression_json)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Invalid filter expression.") from exc
        return library.rows(identifier, index, offset=offset, limit=limit, search=search,
                            sort=sort, descending=descending, bookmarks_only=bookmarks_only,
                            groups=group, path=path, sorts=sorts, interval=interval,
                            expression=expression, filters=parse_filters(filter))

    @app.get("/api/cases/{identifier}/analyses/{index}/export")
    def export(identifier: str, index: int, search: str = "", sort: int | None = None,
               descending: bool = False, filter: list[str] = Query(default=[])):
        target = library.export(identifier, index, search=search, sort=sort,
                                descending=descending, filters=parse_filters(filter))
        name = f"fireblade-{identifier[:8]}-analysis-{index}.csv"
        return FileResponse(target, media_type="text/csv", filename=name)

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    app.state.library = library
    return app
