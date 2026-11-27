"""Destroying a whole case: the evidence, the analyses, the register, and the folder.

Destroying one evidence file and destroying a case are different decisions. A case is
closed when the incident is over: what must go is everything the case holds — the copies of
evidence, the analyses built from them, the tracking, the sessions, the history of the
register — and then the folder itself, so nothing is left to reopen by mistake.

The certificate cannot live inside the case it describes, since that folder is what
disappears: the caller gives a destination outside, and the document is written there before
the folder is removed. A failure on one file does not stop the others; the record says which
files were overwritten, verified and removed, and which were not, and the case folder is only
removed when nothing is left inside it.

A case also leaves things outside its folder: the portable packages it exported, its archive,
the annex of a certificate. `outside_entries` names them, and `destroy_case(..., extras=...)`
overwrites and removes them in the same pass, so the folder is not the only thing that
disappears.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from fireblade.core import destruction as basis
from fireblade.core.destruction_certificate import build as build_certificate
from fireblade.core.destruction_certificate import write as write_certificate

CASE_MARKERS = ("case.json", "workspace.json", "collection.json", "manifest.json")
MAX_CASE_FILES = 200_000


def looks_like_case(folder):
    """A folder is a case when it carries the register, not merely a name."""
    folder = Path(folder)
    if not folder.is_dir():
        return False
    if any((folder / name).is_file() for name in CASE_MARKERS):
        return True
    if (folder / "analyses").is_dir():
        return True
    return any(folder.glob("*.fireblade-session"))


def collect(folder, *, limit=MAX_CASE_FILES):
    """Every regular file under the case folder, in a stable order, with its size."""
    root = Path(folder)
    if root.is_symlink():
        raise ValueError("Le dossier du case est un lien ; il n’est jamais suivi")
    root = root.resolve()
    if not root.is_dir():
        raise ValueError("Le dossier du case n’existe pas")
    if not looks_like_case(root):
        raise ValueError("Ce dossier ne ressemble pas à un case Fireblade ; destruction refusée")
    files, folders, links = [], [], []
    for current, directories, names in os.walk(root, followlinks=False):
        current_path = Path(current)
        folders.append(current_path)
        for name in list(directories):
            candidate = current_path / name
            if candidate.is_symlink():
                links.append(str(candidate.relative_to(root).as_posix()))
                directories.remove(name)
        for name in names:
            path = current_path / name
            if path.is_symlink():
                links.append(str(path.relative_to(root).as_posix()))
                continue
            try:
                size = path.stat().st_size
            except OSError:
                size = 0
            files.append(
                dict(path=str(path), relative=path.relative_to(root).as_posix(), size=size)
            )
            if len(files) > limit:
                raise ValueError(
                    f"Le case dépasse {limit:,} fichiers ; destruction refusée".replace(",", " ")
                )
    return files, folders, links


def outside_entries(root, case_id):
    """The library files that belong to this case but live outside its folder.

    Exports, archives and the certificate annex carry the case's eight-character
    prefix, which is what the library uses to name what it writes on a case's behalf.
    A name that does not start with that prefix is somebody else's: it is never
    returned, so a mistyped identifier cannot reach another case's files.
    """
    root = Path(root)
    prefix = (case_id or "").strip()
    if len(prefix) < 8:
        return []
    prefix = prefix[:8]
    found = []
    for name in ("exports", "archives"):
        folder = root / name
        if folder.is_dir():
            found.extend(sorted(path for path in folder.iterdir() if path.name.startswith(prefix)))
    annex = root / "certificates" / f"annex-{prefix}"
    if annex.is_dir():
        found.append(annex)
    return found


def _outside_files(paths):
    """Every regular file behind the given paths, following no link."""
    files = []
    for value in paths:
        path = Path(value)
        if path.is_symlink():
            continue
        if path.is_dir():
            for current, _directories, names in os.walk(path, followlinks=False):
                for name in sorted(names):
                    item = Path(current) / name
                    if not item.is_symlink():
                        files.append(str(item))
        elif path.is_file():
            files.append(str(path))
    return files


def _attachment_images(attachments, case_folder):
    """The photos themselves, read before the annex that holds them is destroyed.

    A certificate annex lives outside the case folder, so it goes with the residue; the
    document is built afterwards and would find nothing to embed. Keys are the recorded
    SHA-256 values, which is how the certificate names them.
    """
    images = {}
    for item in attachments or []:
        digest = item.get("sha256") or ""
        candidates = []
        if item.get("path"):
            candidates.append(Path(item["path"]))
        if case_folder and item.get("relative"):
            candidates.append(Path(case_folder) / item["relative"])
        for source in candidates:
            try:
                data = source.read_bytes()
            except OSError:
                continue
            if digest and hashlib.sha256(data).hexdigest() != digest:
                continue
            images[digest or hashlib.sha256(data).hexdigest()] = data
            break
    return images


def destroy_case(
    folder,
    method,
    *,
    operator="",
    witness="",
    reason="",
    progress=None,
    cancel=lambda: False,
    certificate_path,
    case_name="",
    case_id="",
    attachments=(),
    extras=(),
    on_certificate=None,
):
    """Overwrite every file of a case, remove the folders, and write the certificate outside.

    Returns the certificate record. The victim folder is removed only when it is empty, so an
    incomplete destruction keeps what is left and says so instead of pretending.
    """
    progress = progress or (lambda _message: None)
    certificate_path = Path(certificate_path)
    root = Path(folder).resolve()
    if certificate_path.resolve() == root or root in certificate_path.resolve().parents:
        raise ValueError("Le procès-verbal doit être écrit hors du case, puisque le case disparaît")
    files, folders, links = collect(root)
    if not files:
        raise ValueError("Le case ne contient aucun fichier à détruire")
    total = sum(item["size"] for item in files)
    progress(f"Destruction du case : {len(files)} fichier(s), {total / 1e6:.1f} Mo")
    entries = basis.plan([item["path"] for item in files], root, limit=MAX_CASE_FILES)

    def report(done, total, path=None):
        # The engine counts bytes; the analyst wants to know which file is going.
        name = Path(path).name if path else ""
        progress(f"Destruction : {done}/{total} · {name}".rstrip(" ·"))

    record = basis.destroy(
        entries,
        method,
        operator=operator,
        witness=witness,
        reason=reason,
        progress=report,
        cancel=cancel,
    )
    record["scope"] = "case"
    record["case_name"] = case_name
    record["case_id"] = case_id
    if attachments:
        # Photos of the media and of the witness, already fingerprinted by
        # store_attachments: the certificate embeds them as data URIs.
        record["attachments"] = list(attachments)
    images = _attachment_images(record.get("attachments"), root)
    if links:
        record["skipped_links"] = links[:200]
    failed = [item for item in record["files"] if not item.get("deleted")]
    removed_folders = 0
    if not failed:
        # Deepest first: a folder disappears only once what it held is gone.
        for path in sorted(folders, key=lambda item: len(item.parts), reverse=True):
            try:
                path.rmdir()
                removed_folders += 1
            except OSError:
                if path == root:
                    raise
    record["removed_folders"] = removed_folders
    record["folder_removed"] = not root.exists()
    # What the case left outside its folder goes too: a portable package or an
    # archive of the case is the case, and a certificate annex holds its photos.
    paths = _outside_files(extras)
    outside = []
    if paths:
        progress(f"Résidus du case : {len(paths)} fichier(s) hors du dossier")
        plan_root = Path(os.path.commonpath([str(Path(path).resolve()) for path in paths]))
        if not plan_root.is_dir():
            plan_root = plan_root.parent
        extra_entries = basis.plan(paths, plan_root, limit=MAX_CASE_FILES)
        extra_record = basis.destroy(
            extra_entries,
            method,
            operator=operator,
            witness=witness,
            reason=reason,
            progress=report,
            cancel=cancel,
        )
        for item in extra_record["files"]:
            item["outside"] = True
        outside = extra_record["files"]
        if extra_record["status"] != "complete":
            record["status"] = "partial"
        # Only a folder this case owns disappears; exports/ and archives/ belong
        # to the library and stay once they are empty.
        for value in extras:
            path = Path(value)
            if path.is_dir() and path.exists():
                for current, directories, _names in os.walk(path, topdown=False):
                    for name in directories:
                        try:
                            (Path(current) / name).rmdir()
                        except OSError:
                            pass
                try:
                    path.rmdir()
                except OSError:
                    pass
        record["files"] = outside + record["files"]
    record["outside"] = len(outside)
    progress("Procès-verbal : " + str(certificate_path))
    document = build_certificate(
        record,
        case_name=case_name,
        case_id=case_id,
        case_folder=None if record["folder_removed"] else root,
        images=images,
    )
    write_certificate(certificate_path, document, pdf=certificate_path.suffix.casefold() == ".pdf")
    record["certificate"] = str(certificate_path)
    if on_certificate is not None:
        on_certificate(record, images)
    return record
