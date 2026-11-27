"""Host routes for analyst observations, workbook exports and disk navigation."""

import hashlib
import json
import shutil
from pathlib import Path
from typing import Annotated

from dissect.evidence.exception import EWFError
from dissect.target.exceptions import Error as DiskError
from fastapi import HTTPException, Query, Response
from fastapi.responses import FileResponse

from fireblade.core import case_workspace as ws
from fireblade.core.disk import image_segments
from fireblade.core.disk_browser import browse, entry_info, image_entry, open_image
from fireblade.core.timeline import guess_time_columns
from fireblade.web import incident_documents, scenario, tracking
from fireblade.web.service import ServiceError, _case_operation


def register(app, library):
    base = "/api/cases/{identifier}"

    def operation(fn):
        from functools import wraps

        guarded = _case_operation(fn)

        @wraps(fn)
        def call(identifier, *args, **kwargs):
            try:
                return guarded(library, identifier, *args, **kwargs)
            except (OSError, ValueError, KeyError, TypeError, DiskError, EWFError) as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        # FastAPI sees the public parameters, excluding the bound library.
        from inspect import signature

        signature_ = signature(fn)
        call.__signature__ = signature_.replace(parameters=list(signature_.parameters.values())[1:])
        return call

    @app.get(base + "/incident-context")
    @operation
    def get_incident_context(library, identifier: str):
        data = ws.load(library.library.folder(identifier))
        return {"fields": incident_documents.FIELDS, "values": data.get("incident_context", {})}

    @app.put(base + "/incident-context")
    @operation
    def save_incident_context(library, identifier: str, payload: dict):
        folder = library.library.folder(identifier)
        if set(payload) - set(incident_documents.FIELDS):
            raise ValueError("Unknown incident context field.")
        context = {
            key: ws._text(value, incident_documents.FIELDS[key], 4000, allow_empty=True)
            for key, value in payload.items()
        }
        if context.get("discovered"):
            ws._date(context["discovered"], "Incident discovery")
        ws.mutate(folder, lambda data: data.setdefault("incident_context", {}).update(context))
        return get_incident_context(identifier)

    @app.get(base + "/incident-context.docx")
    @operation
    def export_incident_context(library, identifier: str):
        data = ws.load(library.library.folder(identifier))
        content = incident_documents.intake(library.library.read(identifier)["name"], data)
        return Response(
            content,
            media_type=incident_documents.DOCX,
            headers={
                "Content-Disposition": f'attachment; filename="incident-{identifier[:8]}.docx"',
            },
        )

    @app.get(base + "/scenario")
    @operation
    def get_scenario(library, identifier: str):
        return scenario.correlate(library, identifier)

    @app.get(base + "/tracking")
    @operation
    def get_tracking(
        library,
        identifier: str,
        tag: Annotated[list[str] | None, Query()] = None,
        fp: bool = False,
        minutes: int = 30,
    ):
        data = ws.load(library.library.folder(identifier))
        events = tracking.selected_events(data, tag or (), fp)
        return {
            "events": events,
            "tags": sorted(
                {tag for event in data.get("evidence_events", []) for tag in event["tags"]},
                key=str.casefold,
            ),
            "connections": tracking.relationships(events, minutes),
        }

    @app.get(base + "/tracking/export/{format}")
    @operation
    def export_tracking(
        library,
        identifier: str,
        format: str,
        tag: Annotated[list[str] | None, Query()] = None,
        fp: bool = False,
    ):
        folder = library.library.folder(identifier)
        data = ws.load(folder)
        events = tracking.selected_events(data, tag or (), fp)
        evidence = [*tracking.inventory(folder), *data.get("disk_files", [])]
        sections = tracking.tables(data, events, evidence)
        if format == "xlsx":
            body = tracking.workbook(sections)
            media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif format == "docx":
            body = tracking.word_report(library.library.read(identifier)["name"], data, sections)
            media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif format == "html":
            body = tracking.report(library.library.read(identifier)["name"], data, sections)
            media = "text/html; charset=utf-8"
        else:
            raise ValueError("Unknown tracking export format.")
        return Response(
            body,
            media_type=media,
            headers={
                "Content-Disposition": f'attachment; filename="investigation-{identifier[:8]}.{format}"'
            },
        )

    @app.post(base + "/tracking/events")
    @operation
    def save_event(library, identifier: str, payload: dict):
        folder = library.library.folder(identifier)
        fields = tracking.event_fields(payload)
        existing = payload.get("id")
        if existing:

            def edit(data):
                entry = next(
                    (e for e in data.get("evidence_events", []) if e["id"] == existing), None
                )
                if entry is None:
                    raise ValueError("This observation no longer exists.")
                entry.update(fields)
                entry["origin"]["machine"] = fields["machine"]
                return entry

            return update_workspace(folder, edit)

        origin, values, info = source_record(
            library,
            identifier,
            int(payload["analysis"]),
            int(payload["row"]),
            payload.get("column"),
        )
        if "time" not in payload:
            fields["time"] = row_time(values, info)
        if "machine" not in payload:
            fields["machine"] = origin["machine"]
        origin["machine"] = fields["machine"]
        fields["description"] = fields["description"] or origin.get("value", "")

        def save(data):
            events = data.setdefault("evidence_events", [])
            entry = next(
                (
                    e
                    for e in events
                    if e["origin"]["record"] == origin["record"]
                    and e["origin"]["line"] == origin["line"]
                ),
                None,
            )
            if entry is None:
                entry = {"id": ws.identifier(), "added": ws.stamp()}
                events.append(entry)
            entry.update(fields, origin=origin)
            return entry

        return update_workspace(folder, save)

    @app.post(base + "/tracking/bookmarks")
    @operation
    def import_bookmarks(library, identifier: str, payload: dict):
        folder = library.library.folder(identifier)
        index = int(payload["analysis"])
        case = library._case_for(identifier, index)
        with case.lock, case.operation():
            marks = case.db.execute(
                "SELECT row_id,note FROM bookmarks WHERE column_id=? ORDER BY row_id LIMIT 501",
                [case.ROW_NOTE],
            ).fetchall()
        if len(marks) > 500:
            raise ValueError("This grid has more than 500 bookmarks. Tag selected rows instead.")
        new_events = []
        for row, note in marks:
            origin, values, info = source_record(library, identifier, index, row, case=case)
            fields = tracking.event_fields(
                {
                    "description": (note or "")[:4000] if note != "bookmarked" else "",
                    "machine": origin["machine"],
                    "time": row_time(values, info),
                    "tags": ["Bookmark"],
                }
            )
            new_events.append(dict(fields, id=ws.identifier(), added=ws.stamp(), origin=origin))

        def save(data):
            events = data.setdefault("evidence_events", [])
            keys = {(e["origin"]["record"], e["origin"]["line"]) for e in events}
            added = [
                e for e in new_events if (e["origin"]["record"], e["origin"]["line"]) not in keys
            ]
            events.extend(added)
            return {"added": len(added), "already_tagged": len(new_events) - len(added)}

        return update_workspace(folder, save)

    @app.get(base + "/tracking/rewrite")
    def rewrite_settings(identifier: str):
        library.library.folder(identifier)
        return {"enabled": tracking.rewrite_configured()}

    @app.post(base + "/tracking/rewrite")
    def rewrite_description(identifier: str, payload: dict):
        library.library.folder(identifier)
        try:
            return {"description": tracking.rewrite(payload.get("description"))}
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get(base + "/tracking/row")
    @operation
    def get_record(library, identifier: str, analysis: int, row: int, column: int | None = None):
        origin, values, info = source_record(library, identifier, analysis, row, column)
        data = ws.load(library.library.folder(identifier))
        existing = next(
            (
                e
                for e in data.get("evidence_events", [])
                if (e["origin"]["record"], e["origin"]["line"])
                == (origin["record"], origin["line"])
            ),
            None,
        )
        return {
            "origin": origin,
            "time": row_time(values, info),
            "event": existing,
            "selection": origin.get("value") or "",
            "suggestions": tracking.suggest_fields(values),
        }

    @app.delete(base + "/tracking/events/{event_id}")
    @operation
    def delete_event(library, identifier: str, event_id: str):
        def remove(data):
            data["evidence_events"] = [
                event for event in data.get("evidence_events", []) if event["id"] != event_id
            ]

        ws.mutate(library.library.folder(identifier), remove)
        return {"removed": event_id}

    @app.post(base + "/tracking/indicator")
    @operation
    def indicator_from_cell(library, identifier: str, payload: dict):
        from fireblade.core.ioc_hunt import indicator

        folder = library.library.folder(identifier)
        origin, _, _ = source_record(
            library,
            identifier,
            int(payload["analysis"]),
            int(payload["row"]),
            int(payload["column"]),
        )
        parsed = indicator(str(origin.pop("value")), "ip", "")
        if parsed.kind != "ip":
            raise ValueError("Choose a cell containing an IP address.")
        if not payload.get("declare"):
            return {"value": parsed.value}
        if payload.get("machine"):
            origin["machine"] = ws._text(payload["machine"], "Machine", 200)
        entry = {
            "id": ws.identifier(),
            "kind": "ip",
            "value": parsed.value,
            "label": "",
            "status": "new",
            "added": ws.stamp(),
            "source": "Analysis grid",
        }

        def save(data):
            found = next(
                (i for i in data["iocs"] if i["kind"] == "ip" and i["value"] == parsed.value), None
            )
            if found is None:
                data["iocs"].append(entry)
                found = entry
            observations = found.setdefault("observations", [])
            if origin not in observations:
                observations.append(origin)
            return found

        return update_workspace(folder, save)

    @app.get(base + "/disk-images")
    @operation
    def list_images(library, identifier: str):
        return {
            "images": [
                public_image(image)
                for image in ws.load(library.library.folder(identifier)).get("disk_images", [])
            ]
        }

    @app.post(base + "/disk-images")
    @operation
    def register_image(library, identifier: str, payload: dict):
        folder = library.library.folder(identifier)
        given = ws._text(payload.get("source"), "Image path", 4096)
        source = Path(given).expanduser().resolve()
        if source == folder or folder in source.parents:
            raise ValueError("Mount the original image separately from the case folder.")
        if source.suffix.casefold() not in (".e01", ".raw", ".dd", ".img"):
            raise ValueError("Select an E01 or raw disk image.")
        segments = image_state(source)
        partitions = browse(source)["partitions"]
        if image_state(source) != segments:
            raise ValueError("The disk image changed while opening it.")
        image = {
            "id": ws.identifier(),
            "source": str(source),
            "name": source.name,
            "partitions": partitions,
            "segments": segments,
            "registered": ws.stamp(),
        }

        def save(data):
            images = data.setdefault("disk_images", [])
            existing = next(
                (i for i in images if i["source"] == image["source"] and i["segments"] == segments),
                None,
            )
            if existing:
                return existing
            images.append(image)
            return image

        return public_image(update_workspace(folder, save))

    @app.get(base + "/disk-files/{record_id}")
    @operation
    def download_collected_file(library, identifier: str, record_id: str):
        folder = library.library.folder(identifier)
        ws._key({"id": record_id})
        captured = next(
            (item for item in ws.load(folder).get("disk_files", []) if item["id"] == record_id),
            None,
        )
        if captured is None:
            raise HTTPException(status_code=404, detail="This file is not in the case.")
        relative = Path("Disks") / "explorer" / record_id / "evidence.bin"
        path = folder / relative
        if not path.is_file():
            path = folder / "case-extra" / relative
        if not path.is_file() or not path.resolve().is_relative_to(folder):
            raise HTTPException(status_code=404, detail="The case copy is unavailable.")
        return FileResponse(path, media_type="application/octet-stream", filename=captured["name"])

    @app.get(base + "/disk-images/{image_id}/files")
    @operation
    def list_image_files(
        library, identifier: str, image_id: str, partition: int, path: str = "/", offset: int = 0
    ):
        image = get_image(library.library.folder(identifier), image_id)
        result = browse(image["source"], partition, path, offset)
        verify_image(image)
        return result

    @app.get(base + "/disk-images/{image_id}/preview")
    @operation
    def preview_image_file(library, identifier: str, image_id: str, partition: int, path: str):
        image = get_image(library.library.folder(identifier), image_id)
        with open_image(image["source"]) as target:
            node = image_entry(target, partition, path)
            if not node.is_file():
                raise ValueError("Select a regular file.")
            with node.open("rb") as source:
                sample = source.read(4097)
        verify_image(image)
        text = sample[:4096].decode("utf-8", errors="replace")
        binary = "\0" in text or text.count("\ufffd") > 4
        return {
            "content": sample[:4096].hex(" ") if binary else text,
            "truncated": len(sample) > 4096,
            "binary": binary,
        }

    @app.post(base + "/disk-images/{image_id}/files")
    @operation
    def collect_image_file(library, identifier: str, image_id: str, payload: dict):
        folder = library.library.folder(identifier)
        image = get_image(folder, image_id)
        partition, path = int(payload["partition"]), payload["path"]
        data = ws.load(folder)
        for captured in data.get("disk_files", []):
            if (captured["image"], captured["partition"], captured["file"]) == (
                image_id,
                partition,
                path,
            ):
                return captured
        record_id = ws.identifier()
        destination = folder / "Disks" / "explorer" / record_id
        destination.mkdir(parents=True)
        try:
            with open_image(image["source"]) as target:
                node = image_entry(target, partition, path)
                meta = entry_info(node)
                if meta["kind"] != "file":
                    raise ValueError("Only regular files can be collected.")
                if meta["size"] > 2 * 1024**3:
                    raise ValueError("The explorer collects individual files up to 2 GiB.")
                digest, copied = hashlib.sha256(), 0
                # Keep the in-image name as metadata. It cannot become a host path.
                with (
                    node.open("rb") as incoming,
                    (destination / "evidence.bin").open("xb") as output,
                ):
                    while block := incoming.read(1024 * 1024):
                        copied += len(block)
                        if copied > meta["size"]:
                            raise ValueError("The file exceeds its in-image size.")
                        output.write(block)
                        digest.update(block)
                if copied != meta["size"]:
                    raise ValueError("The extracted file is truncated.")
            verify_image(image)
            captured = dict(
                meta,
                id=record_id,
                image=image_id,
                disk=image["name"],
                file=path,
                partition=partition,
                sha256=digest.hexdigest(),
                collected=ws.stamp(),
            )
            ws.mutate(folder, lambda data: data.setdefault("disk_files", []).append(captured))
            return captured
        except BaseException:
            shutil.rmtree(destination)
            raise


def update_workspace(folder, change):
    result = None

    def apply(data):
        nonlocal result
        result = change(data)

    ws.mutate(folder, apply)
    return result


def source_record(library, identifier, index, row, column=None, *, case=None):
    case = case if case is not None else library._case_for(identifier, index)
    folder = library.library.folder(identifier)
    with case.lock, case.operation():
        columns = list(case.headers)
        result = case.rows_by_ids([row]).get(row)
        if result is None:
            raise ServiceError("This record no longer exists.")
        values = dict(zip(columns, result[1:]))
        info = case.info
        references = info.get("row_sources") or []
        source = str(info.get("path") or "")
        if case.sparse:
            manifest = Path(source)
            if not manifest.is_file():
                manifest = (
                    case.path.parent.parent / "results" / manifest.parent.name / manifest.name
                )
            if not manifest.is_file():
                raise ServiceError("The combined grid source references are unavailable.")
            else:
                references = json.loads(manifest.read_text(encoding="utf-8"))["sources"]
        match = next(
            (
                source
                for source in references
                if source["first_row"] <= row < source["first_row"] + source["rows"]
            ),
            None,
        )
        path = Path(match["path"] if match else case.path)
        if not path.is_relative_to(folder):
            repaired = library._resolve_analysis(case.path.parent, str(path))
            if repaired and Path(repaired).is_relative_to(folder):
                path = Path(repaired)
        record = path.relative_to(folder).as_posix() if path.is_relative_to(folder) else path.name
        raw_row = row - match["first_row"] + 1 if match else row
        if references and match is None:
            raise ServiceError("The original row could not be located.")
        file = str(values.get(columns[1]) or source) if references else source
        machine = next(
            (
                str(value)
                for key, value in values.items()
                if value
                and key.casefold()
                in (
                    "computer",
                    "computername",
                    "hostname",
                    "host",
                    "machine",
                    "devicename",
                    "device_name",
                )
            ),
            "",
        )
        origin = {
            "record": record,
            "line": raw_row,
            "file": file,
            "machine": machine[:200],
            "artifact": str(values.get(columns[0]) or "")
            if references
            else library._label(info, case.path),
        }
        if column is not None:
            if not 0 <= column < len(columns):
                raise ServiceError("Choose an evidence cell.")
            value = result[column + 1]
            origin.update(
                column=columns[column], value=str(value if value is not None else "")[:4000]
            )
        if case.sparse:
            info = dict(info, event_clock=columns[3])
        return origin, values, info


def row_time(values, info):
    column = info.get("event_clock")
    if column is not None:
        raw = values.get(column)
    else:
        headers = list(values)
        guess = guess_time_columns(headers)
        if isinstance(guess, tuple):
            raw = "T".join(str(values.get(headers[index]) or "") for index in guess)
        else:
            raw = values.get(headers[guess]) if guess is not None else None
    if raw is None:
        return None
    text = str(raw).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return text if len(text) <= 40 and tracking.event_time(text) else None


def image_state(source):
    result = []
    for path in image_segments(source):
        if not path.is_file() or path.is_symlink():
            raise ValueError("Every disk image segment must be a regular file.")
        stat = path.stat()
        result.append([path.name, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns])
    return result


def verify_image(image):
    if image_state(image["source"]) != image["segments"]:
        raise ValueError("The disk image or its segments changed. Register the image again.")


def get_image(folder, image_id):
    for image in ws.load(folder).get("disk_images", []):
        if image["id"] == image_id:
            verify_image(image)
            return image
    raise ValueError("This case has no such disk image.")


def public_image(image):
    return {key: image[key] for key in ("id", "name", "partitions", "registered")}
