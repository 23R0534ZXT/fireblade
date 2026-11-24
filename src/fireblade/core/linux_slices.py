"""Read one large log across several processes.

A folder of logs already parses on every core, one process per file; but one file
larger than the rest stays on a single core. Measured on a 250 MB access.log: 11.7
MB/s alone, while four files reached 34.7 MB/s together. This module cuts such a
file into line-aligned byte ranges, one per worker, and glues the CSVs back in
order, so a 40 GB log costs one slice instead of all of them in a row.

Only plain text is split. A compressed file, an archive, a UTF-16 file, a journal
and a header-driven format (Zeek TSV, W3C) are refused: a range that starts in the
middle of a file has no header to read, and a wrongly split record is a wrong
analysis, silently.
"""

import re
from pathlib import Path

MIN_SLICE_BYTES = 64 << 20
BLOCK = 8 << 20
CHUNK = 4 << 20
MAGIC = (
    b"\x1f\x8b",
    b"BZh",
    b"\xfd7zXZ\x00",
    b"\x04\x22\x4d\x18",
    b"\x28\xb5\x2f\xfd",
    b"PK\x03\x04",
    b"PK\x05\x06",
    b"LPKSHHRH",
)
BINARY_NAMES = re.compile(r"(?:pacct|acct|utmp|wtmp|btmp|lastlog)(?:[.-].*)?$")


def refusal(path, size):
    """Why this file must not be split, or None when it may be."""
    path = Path(path)
    if size < MIN_SLICE_BYTES:
        return "small file"
    if BINARY_NAMES.fullmatch(path.name) or path.name.endswith((".journal", ".journal~")):
        return "binary or journal format"
    try:
        with path.open("rb") as stream:
            head = stream.read(65536)
    except OSError:
        return "unreadable"
    for magic in MAGIC:
        if head.startswith(magic):
            return "compressed or archived"
    if head[257:262] == b"ustar":
        return "archived"
    if b"\0" in head:
        return "binary or UTF-16"
    if head.startswith(b"\xef\xbb\xbf"):
        return "byte-order mark"
    first = head.split(b"\n", 1)[0].decode("utf-8", "replace").lstrip("\ufeff")
    if first.startswith(("#separator", "#fields", "#Fields:")):
        return "header-driven format"
    return None


def plan(path, parts):
    """The ranges to read, each starting on a line boundary with its line number."""
    path = Path(path)
    try:
        size = path.stat().st_size
    except OSError:
        return []
    parts = int(parts or 1)
    if parts < 2 or refusal(path, size):
        return []
    targets = [size * index // parts for index in range(1, parts)]
    boundaries = [(0, 1)]
    position = lines = pending = 0
    with path.open("rb") as stream:
        while True:
            block = stream.read(BLOCK)
            if not block:
                break
            end = position + len(block)
            while pending < len(targets) and targets[pending] <= end:
                cut = block.find(b"\n", max(0, targets[pending] - position))
                if cut < 0:
                    break
                boundaries.append((position + cut + 1, lines + block[:cut].count(b"\n") + 2))
                pending += 1
            lines += block.count(b"\n")
            position = end
    if len(boundaries) < 2:
        return []
    spans = []
    for index, (start, line) in enumerate(boundaries):
        end = boundaries[index + 1][0] if index + 1 < len(boundaries) else size
        if end > start:
            spans.append(dict(start=start, line=line, end=end))
    return spans


def read_in_slices(pool, source, output, spans, progress=lambda _: None):
    """Read every range in its own process, then put the CSVs back in order."""
    output = Path(output)
    folder = output / "slices"
    folder.mkdir(parents=True, exist_ok=True)
    jobs = []
    for index, span in enumerate(spans):
        destination = folder / ("%02d" % index)
        destination.mkdir(parents=True, exist_ok=True)
        jobs.append(dict(source=str(source), output=str(destination), span=dict(span)))
    progress("Reading %s in %d slices" % (Path(source).name, len(jobs)))
    return merge(output, source, pool.run_many(jobs))


def merge(output, source, results):
    """One analysis out of several ranges: rows in order, one report entry."""
    target = None
    for result in results:
        outputs = result.get("outputs") or []
        if outputs:
            target = Path(output) / Path(outputs[0]["csv"]).name
            break
    if target is None:
        raise RuntimeError("Aucune tranche n’a produit d’analyse")
    produced = [Path(result["outputs"][0]["csv"]) for result in results if result.get("outputs")]
    _concatenate(target, produced)

    members = [member for result in results for member in result.get("members") or []]
    rows = sum(int(member.get("rows") or 0) for member in members)
    raw_rows = sum(int(member.get("raw_rows") or 0) for member in members)
    reasons = [member["reason"] for member in members if member.get("reason")]
    status = "complete" if rows and not reasons else ("error" if reasons else "empty")
    entry = dict(path=str(source), status=status, rows=rows, raw_rows=raw_rows)
    if reasons:
        entry["reason"] = "; ".join(sorted(set(reasons)))
    warnings = []
    for result in results:
        for warning in result.get("warnings") or []:
            if warning not in warnings:
                warnings.append(warning)
    return dict(
        outputs=[dict(csv=str(target), family="Journaux Linux", rows=rows)],
        members=[entry],
        warnings=warnings,
        structured=sum(int(result.get("structured") or 0) for result in results),
        raw=sum(int(result.get("raw") or 0) for result in results),
        expanded_bytes=sum(int(result.get("expanded_bytes") or 0) for result in results),
    )


def _concatenate(target, sources):
    """The slice CSVs in order, one header: byte copies, never a row-by-row pass."""
    with target.open("xb") as destination:
        for index, source in enumerate(sources):
            with Path(source).open("rb") as stream:
                if index:
                    while True:
                        header = stream.readline()
                        if not header or header.endswith(b"\n"):
                            break
                while True:
                    block = stream.read(CHUNK)
                    if not block:
                        break
                    destination.write(block)
