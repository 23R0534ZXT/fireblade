"""Read-only disk triage with progressive, closed analysis databases.

Only supported artifact candidates are copied. This is not disk acquisition or
carving. Every copied artifact retains its disk/partition path and SHA-256.
"""

import copy
import hashlib
import os
import re
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from fireblade.core.collection import Collection, atomic_json, check_cancel
from fireblade.core.errors import OperationCancelled


def candidate(path):
    name = path.name.casefold()
    parts = [str(p).casefold() for p in path.parts]
    if name.endswith((".log1", ".log2")):
        return False  # Copied once alongside the owning registry hive.
    return (
        name
        in {
            "$mft",
            "$j",
            "$boot",
            "$usnjrnl",
            "$logfile",
            "system",
            "software",
            "sam",
            "security",
            "default",
            "srudb.dat",
            "activitiescache.db",
            "recentfilecache.bcf",
            "history",
            "places.sqlite",
            "cookies",
            "web data",
            "login data",
        }
        or "$extend" in parts[:-1]
        or name.startswith(("ntuser.dat", "usrclass.dat", "amcache", "webcache"))
        or name.endswith(
            (".evtx", ".pf", ".lnk", ".automaticdestinations-ms", ".customdestinations-ms")
        )
        or name.startswith("$i")
        and "$recycle.bin" in parts
        or any(parts[i : i + 2] == ["var", "log"] for i in range(len(parts) - 1))
    )


def image_segments(path):
    """Every segment of an EWF set, refusing a hole.

    ``.E01`` is not a single file when the acquisition was split: ``.E02``, ``.E03``…
    continue it. Reading only the first segment would silently truncate the disk, so a
    gap is an error rather than a shorter image.
    """
    path = Path(path)
    match = re.fullmatch(r"(?i)(.*)\.(e[0-9]{2})", path.name)
    if not match or not path.is_file():
        return [path]
    base = match.group(1)

    def segment_number(extension):
        first, second, third = extension.upper()
        if second.isdigit() and third.isdigit():
            return int(second + third) if first == "E" else 0
        return 100 + (ord(first) - ord("E")) * 676 + (ord(second) - 65) * 26 + ord(third) - 65

    files = {}
    for item in path.parent.iterdir():
        found = re.fullmatch(
            r"(?i)" + re.escape(base) + r"\.([e-z](?:[a-z]{2}|[0-9]{2}))", item.name
        )
        if not found or not item.is_file():
            continue
        extension = found.group(1)
        if extension[1:].isalpha():
            # Ordinary files sharing the base name (e.g. image.raw) also fit
            # the rollover naming pattern. Only EWF headers qualify.
            with item.open("rb") as stream:
                if stream.read(8) != b"EVF\x09\x0d\x0a\xff\x00":
                    continue
        index = segment_number(extension)
        if index:
            if index in files:
                raise ValueError("Duplicate disk image segment: " + item.name)
            files[index] = item
    first = segment_number(match.group(2))
    if first and 1 not in files and first != 1:
        raise ValueError(f"Jeu EWF incomplet : le segment {base}.E01 est absent.")
    if 1 not in files:
        return [path]
    for expected, index in enumerate(sorted(files), 1):
        if index != expected:
            missing = f"{base}.E{expected:02d}" if expected <= 99 else f"{base} (#{expected})"
            raise ValueError(
                f"Jeu EWF incomplet : le segment {missing} est absent. "
                "Fournissez tous les segments de l’acquisition."
            )
    return [files[index] for index in sorted(files)]


def open_device(path):
    """Open a physical device read-only, with an explicit Windows disk length."""
    handle = open(path, "rb", buffering=0)
    try:
        if os.name == "nt":
            import ctypes
            import msvcrt
            from ctypes import wintypes

            ioctl = ctypes.WinDLL("kernel32", use_last_error=True).DeviceIoControl
            ioctl.argtypes = [
                wintypes.HANDLE,
                wintypes.DWORD,
                wintypes.LPVOID,
                wintypes.DWORD,
                wintypes.LPVOID,
                wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD),
                wintypes.LPVOID,
            ]
            ioctl.restype = wintypes.BOOL
            length = ctypes.c_longlong()
            returned = wintypes.DWORD()
            if not ioctl(
                msvcrt.get_osfhandle(handle.fileno()),
                0x7405C,
                None,
                0,
                ctypes.byref(length),
                ctypes.sizeof(length),
                ctypes.byref(returned),
                None,
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            handle.size = length.value
        else:
            handle.seek(0, os.SEEK_END)
            handle.size = handle.tell()
            handle.seek(0)
        if handle.size <= 0:
            raise ValueError("Taille du périphérique indisponible")
        return handle
    except BaseException:
        handle.close()
        raise


class DiskCollection(Collection):
    # Same bytes on two partitions is two artifacts, not one read twice.
    deduplicate_content = False

    def __init__(
        self,
        source,
        workspace,
        pack,
        settings=None,
        progress=lambda _: None,
        ready=lambda _: None,
        source_kind="mounted",
    ):
        if source_kind not in ("mounted", "image", "physical"):
            raise ValueError("Type de source disque inconnu")
        self.disk_source = str(source)
        self.workspace = Path(workspace).resolve()
        if source_kind == "mounted":
            root = Path(source).resolve()
            if not root.is_dir():
                raise ValueError("Volume ou dossier source introuvable")
            if root == self.workspace or root in self.workspace.parents:
                raise ValueError("Le case doit être stocké hors du volume analysé")
        if source_kind == "physical":
            from fireblade.core.disk_destination import check_physical_destination

            check_physical_destination(source, self.workspace)
        self.workspace.mkdir(parents=True, exist_ok=False)
        staging = self.workspace / "collection" / "artifacts"
        staging.mkdir(parents=True, exist_ok=False)
        super().__init__(
            staging, self.workspace / "collection", pack, settings, progress, organization="files"
        )
        self.ready = ready
        self.report["disk"] = dict(
            source=self.disk_source,
            kind=source_kind,
            visited=0,
            extracted=0,
            artifacts=[],
            errors=[],
        )
        self.source_kind = source_kind
        # Report traversal problems separately without manufacturing parsed files.
        self.disk = self.report["disk"]

    def prepare_output(self):
        # This new, private directory was created with the artifact staging area.
        pass

    def publish_results(self, start, entry):
        if entry["status"] not in ("complete", "attention"):
            # Keep diagnostic files, but never load unchecked outputs from a failed source.
            del self.report["documents"][start:]
            return
        # Parser errors may coexist with successful independent outputs.
        documents = self.report["documents"][start:]
        origin = next(
            (item for item in self.disk["artifacts"] if item["extracted"] == entry["path"]), None
        )
        from fireblade.core.collection_organization import artifact_name

        for document in documents:
            artifact = ""
            for run in entry.get("runs", []):
                for output in run.get("outputs", []):
                    if output["analysis"] == document["path"]:
                        artifact = artifact_name(run["tool"], output["csv"])
            document["navigation"] = dict(origin or {}, disk=self.disk_source, artifact=artifact)
        if documents:
            self.ready(copy.deepcopy(documents))

    def copy_artifact(self, source, partition, relative, *, original=None):
        check_cancel()
        parts = PurePosixPath(str(relative).replace("\\", "/")).parts
        if not parts or any(p in ("..", "/", "") or ":" in p for p in parts):
            raise ValueError("Chemin source non sûr")
        target = self.root / partition / Path(*parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".partial")
        digest = hashlib.sha256()
        before = source.stat()
        copied_bytes = 0
        try:
            with source.open("rb") as reader, temporary.open("xb") as writer:
                while block := reader.read(1024 * 1024):
                    check_cancel()
                    writer.write(block)
                    copied_bytes += len(block)
                    digest.update(block)
            after = source.stat()
            if copied_bytes != before.st_size:
                raise ValueError("Copie tronquée : taille différente de la source")
            if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
                raise ValueError("Source modifiée pendant la copie")
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
        self.disk["extracted"] += 1
        self.disk["artifacts"].append(
            dict(
                source=str(source),
                partition=partition,
                relative=original or PurePosixPath(*parts).as_posix(),
                extracted=str(target),
                sha256=digest.hexdigest(),
                size=after.st_size,
                collected=datetime.now(UTC).isoformat(),
                modified=datetime.fromtimestamp(before.st_mtime, UTC).isoformat(),
                created=(
                    datetime.fromtimestamp(before.st_birthtime, UTC).isoformat()
                    if getattr(before, "st_birthtime", None) is not None
                    else None
                ),
            )
        )
        return target

    @staticmethod
    def companion_sources(source):
        with source.open("rb") as stream:
            magic = stream.read(16)
        suffixes = (
            (".log1", ".log2")
            if magic.startswith(b"regf")
            else (("-wal", "-shm", "-journal") if magic == b"SQLite format 3\0" else ())
        )
        expected = {source.name.casefold() + suffix for suffix in suffixes}
        companions = []
        if expected:
            for path in source.parent.iterdir():
                if path.name.casefold() not in expected:
                    continue
                if path.is_symlink() or not path.is_file():
                    raise ValueError("Compagnon inaccessible ou lien non suivi : " + str(path))
                companions.append(path)
        return sorted(companions, key=lambda p: p.name.casefold())

    def copy_artifact_group(self, source, partition, root):
        """Copy SQLite/hive companions together and reject a changing group."""
        companions = self.companion_sources(source)
        originals = [source] + companions
        before = [(p.stat().st_size, p.stat().st_mtime_ns) for p in originals]
        start = len(self.disk["artifacts"])
        try:
            copied = [self.copy_artifact(p, partition, p.relative_to(root)) for p in originals]
            if [p.name for p in self.companion_sources(source)] != [p.name for p in companions]:
                raise ValueError("Compagnons modifiés pendant la copie")
            for original, state, record in zip(originals, before, self.disk["artifacts"][start:]):
                check_cancel()
                digest = hashlib.sha256()
                with original.open("rb") as incoming:
                    while block := incoming.read(1024 * 1024):
                        check_cancel()
                        digest.update(block)
                after = original.stat()
                if (after.st_size, after.st_mtime_ns) != state or digest.hexdigest() != record[
                    "sha256"
                ]:
                    raise ValueError("Source ou compagnon modifié pendant la copie")
            return copied[0]
        except BaseException:
            for record in self.disk["artifacts"][start:]:
                Path(record["extracted"]).unlink(missing_ok=True)
            del self.disk["artifacts"][start:]
            self.disk["extracted"] = len(self.disk["artifacts"])
            raise

    def walk_roots(self, on_error):
        """One walker, and it is the volume: artifacts are copied as it goes.

        The folder import walks one root per selection; a disk has a single source
        whose walker performs the extraction, so it is handed over unchanged.
        """
        return [self.walk_sources(on_error)]

    def walk_sources(self, on_error):
        target = None
        resources = ExitStack()
        try:
            if self.source_kind == "mounted":
                root = Path(self.disk_source).resolve()
                if not root.is_dir():
                    raise ValueError("Volume ou dossier source introuvable")
                if root == self.workspace or root in self.workspace.parents:
                    raise ValueError("Le case doit être stocké hors du volume analysé")
                roots = [("volume", root)]
            else:
                from dissect.target import Target

                self.progress("Ouverture du disque et détection des partitions…")
                if self.source_kind == "physical":
                    from dissect.target.containers.raw import RawContainer

                    target = Target()
                    try:
                        handle = open_device(self.disk_source)
                    except PermissionError as exc:
                        raise ValueError(
                            "Lecture refusée par Windows sur ce disque physique : elle exige des droits "
                            "administrateur. Relancez Fireblade en tant qu’administrateur, ou analysez une "
                            "image acquise (.raw / .E01) avec les droits courants."
                        ) from exc
                    resources.callback(handle.close)
                    disk = RawContainer(handle)
                    target.disks.add(disk)
                    target.apply()
                else:
                    if Path(self.disk_source).suffix.casefold() == ".e01":
                        from fireblade.core.disk_browser import open_image

                        target = resources.enter_context(
                            open_image(
                                self.disk_source,
                                empty_error="Aucun système de fichiers lisible : image sans partition exploitable.",
                            )
                        )
                    else:
                        target = Target.open(self.disk_source)
                        for disk in target.disks:
                            resources.callback(disk.close)
                roots = [
                    (f"partition-{i + 1}", fs.path("/")) for i, fs in enumerate(target.filesystems)
                ]
                if not roots:
                    raise ValueError(
                        "Aucun système de fichiers lisible : le conteneur est reconnu mais aucune "
                        "partition exploitable n’en a été extraite (image sans table de partitions, "
                        "volume chiffré ou format non pris en charge)."
                    )
            for partition, root in roots:

                def failed(error):
                    self.disk["errors"].append(str(error))
                    on_error(error)

                if self.source_kind == "mounted":
                    walker = os.walk(root, followlinks=False, onerror=failed)
                else:
                    walker = root.walk(on_error=failed, follow_symlinks=False)
                for directory, dirs, names in walker:
                    check_cancel()
                    # Dissect paths are POSIX even on Windows; joining another
                    # TargetPath can mix pathlib flavours on Python 3.11.
                    directory = (
                        root / directory.relative_to(root).as_posix()
                        if hasattr(directory, "relative_to")
                        else Path(directory)
                    )
                    for name in list(dirs):
                        child = directory / name
                        # Dissect's NTFS is_symlink includes mount-point reparse
                        # tags. Its pathlib is_junction adapter is broken in 3.25.1.
                        if child.is_symlink() or (
                            self.source_kind == "mounted"
                            and hasattr(child, "is_junction")
                            and child.is_junction()
                        ):
                            dirs.remove(name)
                    for name in names:
                        check_cancel()
                        source = directory / name
                        self.disk["visited"] += 1
                        if self.disk["visited"] % 100 == 0:
                            self.progress(
                                f"Découverte : {self.disk['visited']} fichiers · {self.disk['extracted']} artefacts copiés · {source}"
                            )
                        if not candidate(source):
                            continue
                        try:
                            if source.is_symlink() or not source.is_file():
                                continue
                            # Do not parse a SQLite sidecar independently when
                            # it is already transported with its owning database.
                            suffix = next(
                                (
                                    s
                                    for s in ("-wal", "-shm", "-journal")
                                    if name.casefold().endswith(s)
                                ),
                                None,
                            )
                            if suffix:
                                owner = source.with_name(name[: -len(suffix)])
                                if owner.is_file() and not owner.is_symlink() and candidate(owner):
                                    with owner.open("rb") as stream:
                                        if stream.read(16) == b"SQLite format 3\0":
                                            continue
                            self.progress("Extraction en lecture seule : " + str(source))
                            if (
                                name.casefold() == "$usnjrnl"
                                and getattr(getattr(root, "_fs", None), "__type__", None) == "ntfs"
                            ):
                                from dissect.target.exceptions import (
                                    FileNotFoundError as NtfsMissing,
                                )

                                journal = source.with_name(source.name + ":$J")
                                try:
                                    journal.stat()
                                except NtfsMissing:
                                    pass
                                else:
                                    original = f"{source.relative_to(root).as_posix()}:$J"
                                    staged = (
                                        source.relative_to(root).parent / "$UsnJrnl-streams" / "$J"
                                    )
                                    copied = self.copy_artifact(
                                        journal, partition, staged, original=original
                                    )
                                    yield copied.parent, [], [copied.name]
                            copied = self.copy_artifact_group(source, partition, root)
                            yield copied.parent, [], [copied.name]
                        except Exception as exc:
                            if isinstance(exc, OperationCancelled):
                                raise
                            self.disk["errors"].append(str(source) + ": " + str(exc))
                            self.report["files"].append(
                                dict(path=str(source), status="error", tools=[], error=str(exc))
                            )
        finally:
            resources.close()
            atomic_json(self.output / "disk-source.json", self.disk)
