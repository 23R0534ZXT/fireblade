"""JSON workspace snapshots, independent of Qt and database connections."""
import base64
import json
import os
from pathlib import Path
import tempfile

from fireblade.core.models import AnalysisSnapshot, View


def write_session(path, snapshots, active):
    path = Path(path).resolve()
    payload = dict(format="fireblade-session", version=1, active=active, documents=[
        dict(path=s.path, source=s.source_info, view=json.loads(s.view.to_json()),
             header=base64.b64encode(s.header_state).decode("ascii")) for s in snapshots])
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, suffix=".partial", delete=False) as output:
            temporary = Path(output.name)
            json.dump(payload, output, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def read_session(path):
    path = Path(path)
    if path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError("Session limitée à 4 Mo")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("format") != "fireblade-session" or payload.get("version") != 1:
        raise ValueError("Format de session Fireblade inconnu")
    documents = payload.get("documents")
    if not isinstance(documents, list) or not 1 <= len(documents) <= 1000:
        raise ValueError("Une session doit contenir de 1 à 1000 analyses")
    snapshots, seen = [], set()
    for doc in documents:
        target = Path(doc["path"])
        target = (path.parent / target).resolve() if not target.is_absolute() else target.resolve()
        if not target.is_file() or target in seen:
            raise ValueError(f"Analyse absente ou dupliquée : {target}")
        seen.add(target)
        view = View.from_json(json.dumps(doc["view"]))
        snapshots.append(AnalysisSnapshot(str(target), doc["source"], view,
                                         base64.b64decode(doc["header"], validate=True)))
    active = payload.get("active", 0)
    if type(active) is not int or not 0 <= active < len(snapshots):
        raise ValueError("Onglet actif invalide")
    return snapshots, active

