"""Fireblade Host: the case library served over HTTP, next to the desktop app."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from fireblade.web import english
from fireblade.web.service import Library, ServiceError, _english, parse_filters
from fireblade.web.updates import Checker

STATIC = Path(__file__).with_name("static")


def _whole(value, name="value") -> int:
    """An integer a client sent, or a ValueError the route turns into a 400.

    ``int(None)`` raises TypeError, which the routes do not catch: a missing or null
    field would reach the analyst as a 500 and a traceback instead of a sentence.
    """
    if isinstance(value, bool) or value is None:
        raise ValueError(f"A whole number is required for the {name}.")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"A whole number is required for the {name}.") from exc


def _store_upload(folder: Path, file: UploadFile, relative: str = "") -> Path:
    """Write the sent file into the case's evidence folder under a free name.

    Overwriting an existing evidence file would change the bytes an earlier import
    recorded a hash for, so a second upload of the same name becomes `name-2.ext`.
    The collection then sees a duplicate by hash and says so, which is the truth.

    With a ``relative`` path — a folder sent from the browser — the tree is kept, because
    a collection is a tree: the readers look for `C/Windows/System32/...`, not for a pile
    of files that lost their path on the way.
    """
    evidence = folder / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    raw = Path(relative.replace("\\", "/")).parts if relative else ()
    if any(part == ".." for part in raw):
        raise HTTPException(status_code=400, detail="Invalid relative path.")
    parts = [part for part in raw if part not in ("", ".", "/")]
    if relative and not parts:
        raise HTTPException(status_code=400, detail="Invalid relative path.")
    if parts:
        target = evidence.joinpath(*parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as stream:
            while chunk := file.file.read(1024 * 1024):
                stream.write(chunk)
        return target
    name = Path(file.filename or "evidence").name
    if not name or name in (".", ".."):
        raise HTTPException(status_code=400, detail="Invalid file name.")
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


def create_app(
    root: str | Path,
    version: str = "",
    tools_root: str | Path | None = None,
    plugins_root: str | Path | None = None,
) -> FastAPI:
    library = Library(root, tools_root=tools_root, plugins_root=plugins_root)
    # One check per process, cached for hours: the page asks once, the registry is not
    # polled, and a failure is reported as a failure.
    updates = Checker(version or "0", os.environ.get("FIREBLADE_EDITION", "host"))
    app = FastAPI(
        title="Fireblade Host",
        version=version or "0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    @app.exception_handler(ServiceError)
    async def _service_error(_request, exc: ServiceError):
        # One shape for every refusal: `detail`, in English; `error` stays for older readers.
        message = english.english_text(str(exc))
        return JSONResponse(status_code=400, content={"detail": message, "error": message})

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
            "update": updates.info(refresh=False),
        }

    @app.get("/api/version")
    def version_check():
        """Is there a newer release? The banner reads this; nothing else depends on it."""
        return updates.info()

    @app.get("/api/cases")
    def cases():
        return library.cases()

    @app.post("/api/cases")
    def create_case(payload: dict):
        payload = payload or {}
        try:
            return library.create_case(
                payload.get("name") or "Untitled case",
                payload.get("description", ""),
                payload.get("environment", "unspecified"),
            )
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
            return library.destroy(
                identifier,
                payload.get("method", "dod3"),
                payload.get("operator", ""),
                payload.get("witness", ""),
                payload.get("reason", ""),
                payload.get("confirmation", ""),
                payload.get("attachments") or [],
                certificate_folder=payload.get("certificate_folder") or "",
            )
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/cases/{identifier}/residue")
    def residue(identifier: str):
        """What the case left outside its folder: shown before the destruction."""
        try:
            return library.residue(identifier)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/cases/{identifier}/session")
    def save_session(identifier: str):
        try:
            return library.save_session(identifier)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/session/open")
    def open_session(identifier: str, payload: dict):
        try:
            return library.open_session(identifier, (payload or {}).get("content") or "")
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/destruction/attachments")
    def destruction_attachments(identifier: str, payload: dict):
        """Photos to embed in the certificate, stored before the case is destroyed."""
        try:
            return library.store_destruction_attachments(
                identifier, (payload or {}).get("sources") or []
            )
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
            # A workbook is a table, not an artefact: the desktop asks which sheet
            # and reads it directly, and so does this route.
            if Path(str(source)).suffix.lower() in library.EXCEL_SUFFIXES:
                return library.import_table(
                    identifier,
                    str(source),
                    sheet=(payload or {}).get("sheet") or "",
                    label=(payload or {}).get("label") or "",
                )
            return library.import_source(
                identifier,
                source,
                tools_root=tools_root,
                organization=(payload or {}).get("organization", "files"),
                delimiter=(payload or {}).get("delimiter") or None,
                encoding=(payload or {}).get("encoding") or None,
            )
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/sheets")
    def sheets(identifier: str, payload: dict):
        """The sheets of a workbook the case already holds."""
        source = (payload or {}).get("path")
        if not source:
            raise HTTPException(status_code=400, detail="A 'path' field is required.")
        try:
            return library.excel_sheets(source)
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
            return library.preview_source(
                source,
                delimiter=(payload or {}).get("delimiter") or None,
                encoding=(payload or {}).get("encoding") or None,
            )
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/preview-upload")
    def preview_upload(
        identifier: str,
        file: UploadFile = File(...),
        delimiter: str | None = Form(None),
        encoding: str | None = Form(None),
    ):
        """The browser hands the file over, the preview reads it, nothing is imported.

        The bytes land in the case's own evidence folder, the same place the import
        reads them from: confirming the preview does not send them a second time.
        """
        folder = library.library.folder(identifier)
        try:
            return library.preview_source(
                _store_upload(folder, file), delimiter=delimiter, encoding=encoding
            )
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/upload-folder")
    def upload_folder(identifier: str, file: UploadFile = File(...), relative: str = Form(...)):
        """One file of a folder the browser sent, at its own path under evidence/.

        The browser can hand over a whole directory (`webkitdirectory`): each file arrives
        with its relative path, the tree is rebuilt in the case, and the folder is then
        previewed and imported exactly as the desktop imports a collection.
        """
        folder = library.library.folder(identifier)
        try:
            target = _store_upload(folder, file, relative=relative)
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        parts = [
            part
            for part in Path(relative.replace("\\", "/")).parts
            if part not in ("", ".", "..", "/")
        ]
        root = folder / "evidence" / parts[0] if parts else target
        return {"path": str(target), "root": str(root)}

    @app.post("/api/cases/{identifier}/upload")
    def upload(
        identifier: str,
        organization: str = "files",
        file: UploadFile = File(...),
        delimiter: str | None = Form(None),
        encoding: str | None = Form(None),
    ):
        """The browser cannot hand over a server path: the file is sent, stored in
        the case's own evidence folder, then read by the same collection."""
        folder = library.library.folder(identifier)
        target = _store_upload(folder, file)
        try:
            return library.import_source(
                identifier,
                target,
                tools_root=tools_root,
                organization=organization,
                delimiter=delimiter,
                encoding=encoding,
            )
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
            return library.add_graph_node(
                identifier,
                label,
                tags=(payload or {}).get("tags") or [],
                kind=(payload or {}).get("kind") or "custom",
            )
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
            return library.cell_notes(
                identifier, index, [_whole(value, "row id") for value in rows]
            )
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/analyses/{index}/cellnote")
    def cell_note(identifier: str, index: int, payload: dict):
        try:
            row_id = _whole((payload or {}).get("row_id"), "row id")
            column = _whole((payload or {}).get("column"), "column")
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="row_id and column are required.") from exc
        try:
            return library.cell_note(
                identifier, index, row_id, column, (payload or {}).get("note", "")
            )
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
            return library.save_view(
                identifier,
                index,
                (payload or {}).get("name", ""),
                (payload or {}).get("view") or {},
            )
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
            row_id = _whole((payload or {}).get("row_id"), "row id")
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
        return Response(
            content=text,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )

    @app.get("/api/cases/{identifier}/workspace")
    def workspace(identifier: str):
        try:
            return library.workspace(identifier)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.patch("/api/cases/{identifier}/entities/{entity_id}")
    def edit_entity(identifier: str, entity_id: str, payload: dict):
        """Change a machine or an account."""
        try:
            return library.edit_entity(identifier, entity_id, payload or {})
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/cases/{identifier}/entities/{entity_id}")
    def remove_entity(identifier: str, entity_id: str):
        try:
            return library.remove_entity(identifier, entity_id)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/cases/{identifier}/actions/{action_id}")
    def remove_action(identifier: str, action_id: str):
        try:
            return library.remove_action(identifier, action_id)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/cases/{identifier}/closed")
    def closed_analyses(identifier: str):
        """The analyses closed and kept: the tree lists them, and they open again."""
        try:
            return library.closed_analyses(identifier)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/closed/{position}/reopen")
    def reopen_analysis(identifier: str, position: int):
        try:
            return library.reopen_analysis(identifier, position)
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
            return library.add_indicator(
                identifier,
                values,
                source=(payload or {}).get("source") or "",
                label=(payload or {}).get("label") or "",
                status=(payload or {}).get("status") or "new",
                tags=(payload or {}).get("tags") or [],
            )
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
            # The core writes its refusals in French; the window is English.
            raise HTTPException(status_code=400, detail=_english(exc)) from exc

    @app.post("/api/cases/{identifier}/restore")
    def restore_case(identifier: str):
        try:
            return library.restore_case(identifier)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=_english(exc)) from exc

    @app.get("/api/settings")
    def settings():
        try:
            return library.settings()
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/package")
    def export_package(identifier: str, payload: dict | None = None):
        try:
            return library.export_package(
                identifier, bool((payload or {}).get("include_sources", True))
            )
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=_english(exc)) from exc

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
            raise HTTPException(
                status_code=400, detail="A case package carries the .fireblade extension."
            )
        staging = Path(tempfile.mkdtemp(prefix="fireblade-import-"))
        target = staging / name
        with target.open("wb") as stream:
            while chunk := file.file.read(1024 * 1024):
                stream.write(chunk)
        try:
            return library.import_package(target)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=_english(exc)) from exc
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
            return library.report(
                identifier,
                payload.get("title") or "Fireblade report",
                payload.get("description", ""),
                bookmarks_only=bool(payload.get("bookmarks_only", True)),
                limit=int(payload.get("limit", 2000)),
            )
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/cases/{identifier}/findings")
    def findings(identifier: str):
        """The detection's findings, grouped by rule and host, as the desktop groups them."""
        try:
            return library.findings_view(identifier)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/client-report")
    def client_report(identifier: str, payload: dict):
        """The document the client receives, from the desktop's own generator."""
        payload = payload or {}
        try:
            return library.client_report(
                identifier,
                title=payload.get("title") or "",
                description=payload.get("description") or "",
                analyst=payload.get("analyst") or "",
                include_findings=payload.get("findings", True) is not False,
                include_coverage=bool(payload.get("coverage")),
                pdf=bool(payload.get("pdf")),
            )
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
            return library.bookmark_finding(
                identifier, index, finding, note=(payload or {}).get("note") or None
            )
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/cases/{identifier}/timeline/row/{index}/{row_id}")
    def timeline_source_row(identifier: str, index: int, row_id: int):
        """The row behind one timeline entry, as its own analysis holds it."""
        try:
            return library.timeline_source_row(identifier, index, row_id)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/cases/{identifier}/timeline/export")
    def timeline_export(
        identifier: str,
        start: int | None = None,
        end: int | None = None,
        text: str = "",
        kind: str = "text",
        dates: str = "",
        include_undated: bool = False,
    ):
        """The timeline as a verified CSV: the receipt rides in the headers."""
        options = None
        if dates:
            try:
                options = json.loads(dates)
            except ValueError as exc:
                raise HTTPException(
                    status_code=400, detail="'dates' must be a JSON object."
                ) from exc
        try:
            data, receipt = library.timeline_export(
                identifier,
                start=start,
                end=end,
                text=text,
                kind=kind,
                dates=options,
                include_undated=include_undated,
            )
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        headers = {
            "Content-Disposition": 'attachment; filename="timeline.csv"',
            "X-Fireblade-Written": str(receipt.get("written", "")),
            "X-Fireblade-Expected": str(receipt.get("expected", "")),
            "X-Fireblade-Sha256": str(receipt.get("sha256", "")),
        }
        return Response(content=data, media_type="text/csv", headers=headers)

    @app.get("/api/cases/{identifier}/analyses/{index}/profile")
    def profile_for(identifier: str, index: int):
        try:
            return library.profiles_for(identifier, index)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/analyses/{index}/profile")
    def apply_profile(identifier: str, index: int):
        try:
            return library.apply_profile(identifier, index)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/save")
    def save_case(identifier: str):
        try:
            return library.save_case(identifier)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/analyses/reorder")
    def reorder_analyses(identifier: str, payload: dict):
        try:
            return library.reorder_analyses(identifier, (payload or {}).get("order") or [])
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/import-jobs")
    def start_import_job(
        identifier: str,
        organization: str = Form("files"),
        delimiter: str | None = Form(None),
        encoding: str | None = Form(None),
        sheet: str = Form(""),
        source: str = Form(""),
        file: UploadFile | None = File(None),
    ):
        """Start an import in the background; the caller polls it and can stop it."""
        library.library.folder(identifier)
        try:
            if file is not None:
                target = _store_upload(library.library.folder(identifier), file)
            elif source:
                target = source
            else:
                raise HTTPException(status_code=400, detail="A file or a 'source' is required.")
            return library.start_import_job(
                identifier,
                target,
                organization=organization,
                delimiter=delimiter,
                encoding=encoding,
                sheet=sheet,
            )
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/disk-jobs")
    def start_disk_job(identifier: str, payload: dict):
        """Analyse a mounted volume or a disk image; the caller polls the same job API."""
        source = str((payload or {}).get("source") or "")
        if not source:
            raise HTTPException(status_code=400, detail="A 'source' is required.")
        try:
            return library.start_disk_job(
                identifier, source, str((payload or {}).get("kind") or "mounted")
            )
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/tasks")
    def start_task(identifier: str, payload: dict | None = None):
        """Run a long command in the background; the window polls its percentage."""
        body = payload or {}
        kind = str(body.get("kind") or "")
        try:
            return library.start_task(identifier, kind, body.get("params") or {})
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=_english(exc)) from exc

    @app.get("/api/tasks/{job}")
    def read_task(job: str):
        try:
            return library.task(job)
        except ServiceError as exc:
            raise HTTPException(status_code=404, detail=_english(exc)) from exc

    @app.post("/api/tasks/{job}/cancel")
    def cancel_task(job: str):
        try:
            return library.cancel_task(job)
        except ServiceError as exc:
            raise HTTPException(status_code=404, detail=_english(exc)) from exc

    @app.get("/api/import-jobs/{job}")
    def import_job(job: str):
        try:
            return library.import_job(job)
        except (ServiceError, ValueError, KeyError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/import-jobs/{job}/cancel")
    def cancel_import_job(job: str):
        try:
            return library.cancel_import_job(job)
        except (ServiceError, ValueError, KeyError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/reports/{name}/pdf")
    def report_pdf(identifier: str, name: str):
        try:
            return library.report_pdf(identifier, name)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/cases/{identifier}/unread")
    def unread_files(identifier: str):
        """The files whose read did not complete, and the readers that can try again."""
        try:
            return library.unread_files(identifier)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/cases/{identifier}/collection-files")
    def collection_files(identifier: str, collection: str = ""):
        """The bilan, file by file: status, reason, hash, and whether it was set aside."""
        try:
            return library.collection_files(identifier, collection=collection)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/collection-files/aside")
    def set_aside_file(identifier: str, payload: dict):
        """Park a file out of the counts without losing it, or bring it back."""
        payload = payload or {}
        for field in ("collection", "path"):
            if not payload.get(field):
                raise HTTPException(status_code=400, detail=f"A '{field}' field is required.")
        try:
            return library.set_aside_file(
                identifier,
                payload["collection"],
                payload["path"],
                bool(payload.get("ignored", True)),
            )
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/collection-files/remove")
    def remove_collection_file(identifier: str, payload: dict):
        """Delete a collected file, after proving its hash is still the collected one."""
        payload = payload or {}
        for field in ("collection", "path"):
            if not payload.get(field):
                raise HTTPException(status_code=400, detail=f"A '{field}' field is required.")
        try:
            return library.remove_collection_file(
                identifier, payload["collection"], payload["path"]
            )
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/collections/{collection_name}/retry")
    def retry_file(identifier: str, collection_name: str, payload: dict):
        try:
            return library.retry_file(
                identifier,
                collection_name,
                str((payload or {}).get("path") or ""),
                str((payload or {}).get("reader") or "text"),
            )
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/cases/{identifier}/history")
    def history(identifier: str):
        try:
            return library.history(identifier)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/cases/{identifier}/history/{name}")
    def history_file(identifier: str, name: str):
        try:
            return library.history_file(identifier, name)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/history/{name}/restore")
    def restore_history(identifier: str, name: str):
        try:
            return library.restore_history(identifier, name)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/date-ranges")
    def date_ranges():
        """Today, Yesterday, ThisWeek… as the core defines them."""
        return library.date_ranges()

    @app.get("/api/cases/{identifier}/coverage")
    def coverage(
        identifier: str,
        expected: str = "observed",
        verify_hashes: bool = False,
        deep_checks: bool = True,
        run: bool = True,
    ):
        """Run the coverage audit, or read the last one kept with the case."""
        try:
            if not run:
                return library.coverage_report(identifier)
            return library.coverage(
                identifier, expected=expected, verify_hashes=verify_hashes, deep_checks=deep_checks
            )
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/cases/{identifier}/coverage/export")
    def coverage_export(identifier: str, csv: bool = False):
        try:
            data = library.coverage_export(identifier, as_csv=csv)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        name = "coverage.csv" if csv else "coverage.json"
        return Response(
            content=data,
            media_type="text/csv" if csv else "application/json",
            headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )

    @app.get("/api/global-rules")
    def global_rules(identifier: str = "", index: int = -1):
        """The colour rules shared by every analysis of this instance."""
        try:
            return library.global_rules(identifier or None, index if index >= 0 else None)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/global-rules")
    def save_global_rules(payload: dict):
        try:
            return library.save_global_rules(
                (payload or {}).get("rules") or [], (payload or {}).get("headers")
            )
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/global-rules/enabled")
    def set_global_rules_enabled(payload: dict):
        return library.set_global_rules_enabled(bool((payload or {}).get("enabled", True)))

    @app.get("/api/global-rules/file")
    def global_rules_file():
        """The file the desktop imports: same format, same rules."""
        try:
            data = library.global_rules_file()
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return Response(
            content=data,
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="global-rules.json"'},
        )

    @app.post("/api/global-rules/import")
    def import_global_rules(file: UploadFile = File(...)):
        try:
            return library.import_global_rules(file.file.read())
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/rules")
    def detection_rules(changed: bool = False):
        """The Hayabusa detection rules this instance would load."""
        try:
            return library.rules_inventory(changed_only=changed)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/rules/{name}")
    def rule_text(name: str):
        try:
            return library.rule_text(name)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.put("/api/rules/{name}")
    def save_rule(name: str, payload: dict):
        try:
            return library.save_rule(name, (payload or {}).get("text", ""))
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/rules/{name}/reset")
    def reset_rule(name: str):
        try:
            return library.reset_rule(name)
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/rules/{name}/enabled")
    def set_rule_enabled(name: str, payload: dict):
        try:
            return library.set_rule_enabled(name, bool((payload or {}).get("enabled", True)))
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

    def _ioc_options(payload: dict) -> dict:
        payload = payload or {}
        return {
            "all_analyses": bool(payload.get("all")),
            "respect_filters": bool(payload.get("filters")),
            "include_subdomains": payload.get("subdomains", True) is not False,
            "declared_format": (payload.get("format") or None),
        }

    @app.post("/api/cases/{identifier}/analyses/{index}/ioc")
    def ioc(identifier: str, index: int, payload: dict):
        text = (payload or {}).get("text", "")
        try:
            return library.ioc_scan(identifier, index, text, **_ioc_options(payload))
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/ioc-scan")
    def ioc_scan(identifier: str, payload: dict):
        """A hunt over one analysis or over every analysis of the case."""
        text = (payload or {}).get("text", "")
        try:
            return library.ioc_scan(
                identifier, (payload or {}).get("index"), text, **_ioc_options(payload)
            )
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cases/{identifier}/ioc-file")
    def ioc_file(
        identifier: str,
        file: UploadFile = File(...),
        all_analyses: bool = Form(False),
        respect_filters: bool = Form(False),
        subdomains: bool = Form(True),
        index: int = Form(0),
    ):
        """A TXT, CSV or TSV list read as the desktop reads it: encoding, then format."""
        raw = file.file.read()
        if len(raw) > 8 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Indicator lists are limited to 8 MiB.")
        text = None
        for encoding in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                text = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            raise HTTPException(status_code=400, detail="This file cannot be read as text.")
        name = (file.filename or "").casefold()
        declared = "tsv" if name.endswith(".tsv") else ("csv" if name.endswith(".csv") else None)
        try:
            return library.ioc_scan(
                identifier,
                index,
                text,
                all_analyses=all_analyses,
                respect_filters=respect_filters,
                include_subdomains=subdomains,
                declared_format=declared,
            )
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/cases/{identifier}/timeline")
    def timeline(
        identifier: str,
        start: int | None = None,
        end: int | None = None,
        offset: int = 0,
        text: str = "",
        kind: str = "text",
        dates: str = "",
        include_undated: bool = False,
        respect_filters: bool = False,
    ):
        options = None
        if dates:
            try:
                options = json.loads(dates)
            except ValueError as exc:
                raise HTTPException(
                    status_code=400, detail="'dates' must be a JSON object."
                ) from exc
        try:
            return library.timeline(
                identifier,
                start=start,
                end=end,
                offset=offset,
                text=text,
                kind=kind,
                dates=options,
                include_undated=include_undated,
                respect_filters=respect_filters,
            )
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/cases/{identifier}/analyses/{index}/bookmarks")
    def bookmarks(identifier: str, index: int):
        return library.bookmarks(identifier, index)

    @app.post("/api/cases/{identifier}/analyses/{index}/bookmark")
    def bookmark(identifier: str, index: int, payload: dict):
        try:
            row_id = _whole((payload or {}).get("row_id"), "row id")
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="row_id is required.") from exc
        column = (payload or {}).get("column")
        return library.bookmark(
            identifier,
            index,
            row_id,
            (payload or {}).get("note", ""),
            None if column in (None, "") else int(column),
        )

    @app.get("/api/cases/{identifier}/analyses/{index}/columns")
    def columns(identifier: str, index: int):
        return {"columns": library.columns(identifier, index)}

    @app.get("/api/cases/{identifier}/analyses/{index}/rows")
    def rows(
        identifier: str,
        index: int,
        offset: int = 0,
        limit: int = 200,
        search: str = "",
        sort: int | None = None,
        descending: bool = False,
        bookmarks_only: bool = False,
        group: list[int] = Query(default=[]),
        path: list[str] = Query(default=[]),
        sortkey: list[str] = Query(default=[]),
        interval: str = "",
        expression_json: str = "",
        summary: list[str] = Query(default=[]),
        order: str = "",
        order_descending: bool = True,
        order_summary: int = 0,
        filter: list[str] = Query(default=[]),
    ):
        # sortkey=3:desc — several keys, applied in the order they are sent.
        sorts = []
        for raw in sortkey:
            column, _, flag = raw.partition(":")
            try:
                sorts.append((int(column), flag == "desc"))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Invalid sort key.") from exc
        # summary=4:distinct:text — one entry per aggregate, in the order shown.
        summaries = []
        for raw in summary:
            parts = raw.split(":")
            try:
                summaries.append(
                    (
                        int(parts[0]),
                        parts[1] if len(parts) > 1 else "count",
                        parts[2] if len(parts) > 2 else "number",
                    )
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Invalid summary.") from exc
        expression = None
        if expression_json:
            try:
                expression = json.loads(expression_json)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Invalid filter expression.") from exc
        return library.rows(
            identifier,
            index,
            offset=offset,
            limit=limit,
            search=search,
            sort=sort,
            descending=descending,
            bookmarks_only=bookmarks_only,
            groups=group,
            path=path,
            sorts=sorts,
            interval=interval,
            expression=expression,
            filters=parse_filters(filter),
            summaries=summaries,
            order=order,
            order_descending=order_descending,
            order_summary=order_summary,
        )

    @app.get("/api/cases/{identifier}/analyses/{index}/export")
    def export(
        identifier: str,
        index: int,
        search: str = "",
        sort: int | None = None,
        descending: bool = False,
        format: str = "csv",
        filter: list[str] = Query(default=[]),
    ):
        wanted = (format or "csv").lower()
        if wanted not in ("csv", "xlsx"):
            raise HTTPException(status_code=400, detail="The export format is csv or xlsx.")
        try:
            target = library.export(
                identifier,
                index,
                search=search,
                sort=sort,
                descending=descending,
                filters=parse_filters(filter),
                as_xlsx=wanted == "xlsx",
            )
        except (ServiceError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=_english(exc)) from exc
        name = f"fireblade-{identifier[:8]}-analysis-{index}.{wanted}"
        media = (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            if wanted == "xlsx"
            else "text/csv"
        )
        return FileResponse(target, media_type=media, filename=name)

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon():
        return FileResponse(STATIC / "favicon.svg", media_type="image/svg+xml")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.exception_handler(StarletteHTTPException)
    async def refusal_in_english(request: Request, exc: StarletteHTTPException):
        """Every refusal an analyst reads is in English, whichever module raised it.

        The core words its refusals in its source language and the routes pass them on as
        they are; translating here, once, means a message added to the core can never reach
        the screen in French by way of a route that forgot to call the translator.
        """
        detail = (
            english.data(exc.detail) if isinstance(exc.detail, (str, list, dict)) else exc.detail
        )
        return JSONResponse(
            {"detail": detail}, status_code=exc.status_code, headers=getattr(exc, "headers", None)
        )

    app.state.library = library
    return app
