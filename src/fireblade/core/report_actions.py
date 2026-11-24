"""Actions offered on the import report: review, copy aside, remove, export.

Every action here is deliberate and traceable. The report is a record of what was
seized and of what was done to it, so nothing in this module touches a source file
without either writing a copy first, or recording a hash before the file goes away.

The two rules that matter for an examiner:

* a file that could not be read is copied aside, never moved: the evidence stays
  where it was found;
* a source file is only removed after its hash has been checked against the one
  recorded during collection, and the removal is written into the report. If the
  file changed on disk since collection, the removal is refused.
"""

import csv
import hashlib
from pathlib import Path

# States that mean "this file was not turned into analyses".
UNPROCESSED = frozenset({"unsupported", "skipped", "error", "cancelled", "no_output"})

COLUMNS = ("État", "Fichier", "Lecteurs", "Motif", "SHA-256")


def sha256_file(path, block_size=1024 * 1024):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(block_size):
            digest.update(chunk)
    return digest.hexdigest()


def unprocessed(entries):
    """Entries that produced no analysis, in report order."""
    return [entry for entry in entries if entry.get("status") in UNPROCESSED]


def relative_to_root(path, root):
    """Relative form of a path when it lives under the collection root."""
    try:
        return Path(path).resolve().relative_to(Path(root).resolve())
    except (ValueError, OSError):
        return Path(path).name


def export_rows(entries, target, translate=str):
    """Write the visible rows to a CSV an examiner can hand over or keep."""
    target = Path(target)
    with target.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow([translate(column) for column in COLUMNS])
        for entry in entries:
            writer.writerow(
                [
                    translate(entry.get("status", "")),
                    str(entry.get("path", "")),
                    ", ".join(entry.get("tools", [])),
                    entry.get("error", ""),
                    entry.get("sha256", ""),
                ]
            )
    return target


def copy_unprocessed(entries, destination, root=None):
    """Copy every unprocessed file into `destination`, keeping the tree layout.

    Copies, never moves: the evidence must stay readable where it was collected.
    Existing files are left untouched, so the action can be repeated safely.
    """
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    copied, skipped, failed = [], [], []
    for entry in unprocessed(entries):
        source = Path(entry.get("path", ""))
        if not source.is_file():
            failed.append((str(source), "fichier introuvable"))
            continue
        relative = relative_to_root(source, root) if root else Path(source.name)
        target = destination / relative
        if target.exists():
            skipped.append(str(source))
            continue
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil_copy(source, target)
        except OSError as error:
            failed.append((str(source), str(error)))
            continue
        copied.append(str(source))
    return {"copied": copied, "skipped": skipped, "failed": failed, "destination": str(destination)}


def shutil_copy(source, target):
    """Single indirection so tests can inject a failure without a real permission game."""
    from shutil import copy2

    return copy2(source, target)


def remove_source(entry, recorded=None):
    """Remove a source file after proving it is still the one that was collected.

    Removing a file from the evidence tree destroys it, so the recorded hash is
    checked first: if the file changed since collection, the removal is refused and
    the caller has to look at it. The returned record is meant to replace the entry
    in the report, so the file stays visible with the hash it had.
    """
    path = Path(entry.get("path", ""))
    if not path.is_file():
        raise FileNotFoundError(str(path))
    expected = recorded or entry.get("sha256")
    actual = sha256_file(path)
    if expected and actual.casefold() != str(expected).casefold():
        raise ValueError("le fichier a changé depuis la collecte : suppression refusée")
    path.unlink()
    return {
        "path": str(path),
        "sha256": actual,
        "tools": entry.get("tools", []),
        "status": "deleted",
        "error": entry.get("error", ""),
    }


def set_ignored(entry, ignored=True):
    """Park an entry out of the counts without losing it.

    An examiner who decides a file is irrelevant needs the decision to be reversible
    and visible: the entry keeps its state and reason, and only gains the flag.
    """
    if ignored:
        entry["ignored"] = True
    else:
        entry.pop("ignored", None)
    return entry
