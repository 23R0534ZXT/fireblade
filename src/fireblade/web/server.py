"""Fireblade Host: the case library served over HTTP, next to the desktop app."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from fireblade.web.service import Library, ServiceError, parse_filters

STATIC = Path(__file__).with_name("static")


def create_app(root: str | Path, version: str = "", tools_root: str | Path | None = None) -> FastAPI:
    library = Library(root, tools_root=tools_root)
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
            raise HTTPException(status_code=400, detail="Champ 'source' attendu.")
        try:
            return library.import_source(identifier, source, tools_root=tools_root,
                                         organization=(payload or {}).get("organization", "files"))
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/upload")
    def upload(identifier: str, organization: str = "files", file: UploadFile = File(...)):
        """The browser cannot hand over a server path: the file is sent, stored in
        the case's own evidence folder, then read by the same collection."""
        folder = library.library.folder(identifier)
        name = Path(file.filename or "evidence").name
        if not name or name in (".", ".."):
            raise HTTPException(status_code=400, detail="Nom de fichier invalide.")
        evidence = folder / "evidence"
        evidence.mkdir(parents=True, exist_ok=True)
        target = evidence / name
        with target.open("wb") as stream:
            while chunk := file.file.read(1024 * 1024):
                stream.write(chunk)
        try:
            return library.import_source(identifier, target, tools_root=tools_root,
                                         organization=organization)
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
            raise HTTPException(status_code=400, detail="row_id et column attendus.") from exc
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
            raise HTTPException(status_code=400, detail="row_id attendu.") from exc
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

    @app.get("/api/cases/{identifier}/workspace")
    def workspace(identifier: str):
        try:
            return library.workspace(identifier)
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
            raise HTTPException(status_code=400, detail="Un paquet de case porte l'extension .fireblade.")
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

    @app.post("/api/cases/{identifier}/analyses/{index}/ioc")
    def ioc(identifier: str, index: int, payload: dict):
        text = (payload or {}).get("text", "")
        try:
            return library.ioc_scan(identifier, index, text)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/cases/{identifier}/timeline")
    def timeline(identifier: str, start: int | None = None, end: int | None = None,
                 offset: int = 0, text: str = "", kind: str = "text"):
        try:
            return library.timeline(identifier, start=start, end=end, offset=offset, text=text, kind=kind)
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
            raise HTTPException(status_code=400, detail="row_id attendu.") from exc
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
                raise HTTPException(status_code=400, detail="Clé de tri invalide.") from exc
        expression = None
        if expression_json:
            try:
                expression = json.loads(expression_json)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Expression de filtre invalide.") from exc
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
