"""Archives met inside a collection: a zip, a tar, a compressed tar, nested as deep as they go.

An analyst gives a folder — a ``/var/log`` with sub-folders, and here and there an archive of older
logs — and expects every file of it to be read. An archive is opened into the collection's own work
folder (the evidence is never written to), its members join the inventory like any other file, and an
archive inside an archive is opened in turn. What cannot be opened safely is said, never skipped silently.
"""

import shutil
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

SUFFIXES = (".zip", ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz", ".tar.lzma")
MAX_DEPTH = 8
MAX_MEMBERS = 500_000
MAX_BYTES = 64 * 1024**3  # what one archive may unpack to: a bomb stops here, with its reason


def is_archive(path):
    """A zip or a tar by its name, confirmed by its content (a spreadsheet is a zip and is not one)."""
    path = Path(path)
    name = path.name.casefold()
    if not name.endswith(SUFFIXES):
        return False
    try:
        if name.endswith(".zip"):
            return zipfile.is_zipfile(path)
        return tarfile.is_tarfile(path)
    except OSError:
        return False


def _safe(name):
    parts = PurePosixPath(name.replace("\\", "/")).parts
    if not parts or PurePosixPath(name).is_absolute() or ".." in parts or ":" in parts[0]:
        return None
    return Path(*parts)


def extract(archive, destination, check=lambda: None):
    """Unpack `archive` under `destination`. Returns (files, problems).

    Links, devices, absolute names and names that climb out are refused and reported; the size and
    the member count are bounded.
    """
    archive, destination = Path(archive), Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    files, problems = [], []
    written = 0
    if archive.name.casefold().endswith(".zip"):
        with zipfile.ZipFile(archive) as zipped:
            for number, info in enumerate(zipped.infolist()):
                check()
                if info.is_dir():
                    continue
                target = _safe(info.filename)
                if target is None:
                    problems.append(f"unsafe name refused: {info.filename}")
                    continue
                if number >= MAX_MEMBERS or written + info.file_size > MAX_BYTES:
                    problems.append("archive too large: the rest was not unpacked")
                    break
                out = destination / target
                out.parent.mkdir(parents=True, exist_ok=True)
                try:
                    with zipped.open(info) as incoming, out.open("wb") as outgoing:
                        shutil.copyfileobj(incoming, outgoing)
                except (RuntimeError, zipfile.BadZipFile, OSError) as exc:
                    problems.append(f"{info.filename}: {exc}")
                    out.unlink(missing_ok=True)
                    continue
                written += info.file_size
                files.append(out)
        return files, problems
    with tarfile.open(archive, mode="r:*") as tarred:
        for number, member in enumerate(tarred):
            check()
            if member.isdir():
                continue
            if not member.isfile():
                problems.append(f"{member.name}: a link or a device is not unpacked")
                continue
            target = _safe(member.name)
            if target is None:
                problems.append(f"unsafe name refused: {member.name}")
                continue
            if number >= MAX_MEMBERS or written + member.size > MAX_BYTES:
                problems.append("archive too large: the rest was not unpacked")
                break
            out = destination / target
            out.parent.mkdir(parents=True, exist_ok=True)
            try:
                incoming = tarred.extractfile(member)
                with incoming, out.open("wb") as outgoing:
                    shutil.copyfileobj(incoming, outgoing)
            except (tarfile.TarError, EOFError, OSError) as exc:
                problems.append(f"{member.name}: {exc}")
                out.unlink(missing_ok=True)
                continue
            written += member.size
            files.append(out)
    return files, problems
