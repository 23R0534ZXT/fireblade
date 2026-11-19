"""Fireblade Host: the case library served over HTTP, next to the desktop app."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from fireblade.web.service import Library, ServiceError, parse_filters

STATIC = Path(__file__).with_name("static")


def create_app(root: str | Path, version: str = "", tools_root: str | Path | None = None) -> FastAPI:
    library = Library(root)
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
    def upload(identifier: str, file: UploadFile = File(...)):
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
            return library.import_source(identifier, target, tools_root=tools_root)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

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
             filter: list[str] = Query(default=[])):
        # sortkey=3:desc — several keys, applied in the order they are sent.
        sorts = []
        for raw in sortkey:
            column, _, flag = raw.partition(":")
            try:
                sorts.append((int(column), flag == "desc"))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Clé de tri invalide.") from exc
        return library.rows(identifier, index, offset=offset, limit=limit, search=search,
                            sort=sort, descending=descending, bookmarks_only=bookmarks_only,
                            groups=group, path=path, sorts=sorts, filters=parse_filters(filter))

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
