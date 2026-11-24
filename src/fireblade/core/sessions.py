"""JSON workspace snapshots, independent of Qt and database connections."""

import base64
import json
import os
import tempfile
from pathlib import Path

from fireblade.core.models import AnalysisSnapshot, View

MAX_SESSION_BYTES = 4 * 1024 * 1024
MAX_SESSION_DOCUMENTS = 1000


def _entry(snapshot):
    return dict(
        path=snapshot.path,
        source=snapshot.source_info,
        view=json.loads(snapshot.view.to_json()),
        header=base64.b64encode(snapshot.header_state).decode("ascii"),
    )


def write_session(path, snapshots, active, closed=()):
    """Open tabs, and the analyses closed but kept in the case.

    A closed tab is not a deleted analysis: it stays in the session so the navigation
    tree can list it and open it again. A session may therefore hold no open tab at all
    while still describing the case, which is why an empty tab list is allowed when
    closed analyses are present.
    """
    if len(snapshots) > MAX_SESSION_DOCUMENTS or len(closed) > MAX_SESSION_DOCUMENTS:
        raise ValueError("Une session doit contenir de 1 à 1000 analyses")
    if not snapshots and not closed:
        raise ValueError("Une session doit contenir de 1 à 1000 analyses")
    if type(active) is not int or not (
        0 <= active < len(snapshots) or (not snapshots and active == -1)
    ):
        raise ValueError("Onglet actif invalide")
    path = Path(path).resolve()
    payload = dict(
        format="fireblade-session",
        version=1,
        active=active,
        documents=[_entry(s) for s in snapshots],
        closed=[_entry(s) for s in closed],
    )
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, suffix=".partial", delete=False
        ) as output:
            temporary = Path(output.name)
            json.dump(payload, output, ensure_ascii=False, indent=2)
        if temporary.stat().st_size > MAX_SESSION_BYTES:
            raise ValueError("Session limitée à 4 Mo")
        os.replace(temporary, path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def read_session(path, with_closed=False):
    path = Path(path)
    if path.stat().st_size > MAX_SESSION_BYTES:
        raise ValueError("Session limitée à 4 Mo")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("format") != "fireblade-session" or payload.get("version") != 1:
        raise ValueError("Format de session Fireblade inconnu")
    documents = payload.get("documents")
    if not isinstance(documents, list) or not 0 <= len(documents) <= MAX_SESSION_DOCUMENTS:
        raise ValueError("Une session doit contenir de 0 à 1000 analyses")
    snapshots, seen = _snapshots(path, documents, set())
    closed = []
    if with_closed:
        entries = payload.get("closed") or []
        if not isinstance(entries, list) or len(entries) > MAX_SESSION_DOCUMENTS:
            raise ValueError("Une session doit contenir de 0 à 1000 analyses fermées")
        closed, _ = _snapshots(path, entries, seen)
    if not snapshots and not closed:
        raise ValueError("Une session doit contenir de 1 à 1000 analyses")
    active = payload.get("active", 0)
    if type(active) is not int or not (
        0 <= active < len(snapshots) or (not snapshots and active == -1)
    ):
        raise ValueError("Onglet actif invalide")
    return (snapshots, active, closed) if with_closed else (snapshots, active)


def _snapshots(path, documents, seen):
    """Session entries to snapshots, refusing a missing or repeated analysis."""
    snapshots = []
    for doc in documents:
        target = Path(doc["path"])
        target = (path.parent / target).resolve() if not target.is_absolute() else target.resolve()
        if not target.is_file() or target in seen:
            raise ValueError(f"Analyse absente ou dupliquée : {target}")
        seen.add(target)
        view = View.from_json(json.dumps(doc["view"]))
        snapshots.append(
            AnalysisSnapshot(
                str(target), doc["source"], view, base64.b64decode(doc["header"], validate=True)
            )
        )
    return snapshots, seen
