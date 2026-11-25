"""What no dedicated reader knows, read anyway: nothing a collection holds is left unread.

A collection from an offline collector holds more than event logs and hives: the binaries of the
running processes, browser profiles (SQLite, Firefox's compressed JSON, key-value stores), command
outputs, configuration. A file that no reader recognises is classified by its content and read by the
generic reader of that kind:

* **SQLite** — every table becomes a table of the analysis (blobs as hex);
* **mozlz4** (Firefox's compressed JSON) and **JSON** — flattened to rows;
* **text** — one row per line;
* **PE** (exe, dll, sys…) and every other **binary** — one row of the *Files inventory*: size, dates,
  SHA-256, type and, for a PE, its machine, compile time, subsystem and whether it carries a signature.

Nothing is decoded that the file does not state, and the source is only ever read.
"""

import csv
import hashlib
import json
import sqlite3
import struct
from datetime import UTC, datetime
from pathlib import Path

TEXT_BYTES = (
    4 * 1024 * 1024
)  # a text file is read to here; the rest is counted, not dropped silently
CELL = 32767

INVENTORY_HEADER = [
    "Path",
    "Name",
    "Extension",
    "Size",
    "Modified (UTC)",
    "SHA-256",
    "Type",
    "Machine",
    "Compiled (UTC)",
    "Subsystem",
    "Sections",
    "Signed",
    "Note",
]
MACHINES = {0x14C: "x86", 0x8664: "x64", 0x1C0: "ARM", 0xAA64: "ARM64", 0x200: "IA-64"}
SUBSYSTEMS = {
    1: "Native",
    2: "Windows GUI",
    3: "Windows console",
    5: "OS/2",
    7: "POSIX",
    9: "Windows CE",
    10: "EFI",
}


def classify(path):
    """The kind of a file, from its first bytes and, failing that, its name."""
    path = Path(path)
    try:
        with path.open("rb") as stream:
            head = stream.read(4096)
    except OSError:
        return "binary"
    if head.startswith(b"SQLite format 3\x00"):
        return "sqlite"
    if head.startswith(b"mozLz40\x00"):
        return "mozlz4"
    if head[:2] == b"MZ":
        return "pe"
    if head.startswith(b"\xef\xbb\xbf") or head.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "text"
    if b"\x00" in head[:2048]:
        return "binary"
    try:
        head.decode("utf-8")
        return (
            "json"
            if head.lstrip()[:1] in (b"{", b"[")
            and path.suffix.casefold() in (".json", ".jsonl", ".js")
            else "text"
        )
    except UnicodeDecodeError:
        return (
            "text"
            if sum(byte < 9 or 13 < byte < 32 for byte in head) < len(head) * 0.02
            else "binary"
        )


def _text(raw):
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16", errors="replace")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def _cell(value):
    if value is None:
        return ""
    if isinstance(value, (bytes, bytearray, memoryview)):
        return "hex:" + bytes(value)[:256].hex()
    return str(value)[:CELL]


def _flatten(value, prefix=""):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _flatten(item, f"{prefix}.{key}" if prefix else str(key))
    elif isinstance(value, list) and not (value and all(isinstance(item, dict) for item in value)):
        yield prefix, json.dumps(value, ensure_ascii=False)[:CELL]
    elif isinstance(value, list):
        for number, item in enumerate(value):
            yield from _flatten(item, f"{prefix}[{number}]")
    else:
        yield prefix, _cell(value)


def pe_fields(path):
    """The few things a PE header says: enough to tell binaries apart without running anything."""
    try:
        with Path(path).open("rb") as stream:
            data = stream.read(4096)
            offset = struct.unpack_from("<I", data, 0x3C)[0]
            if offset > 1 << 20:
                return {}
            stream.seek(offset)
            header = stream.read(4 + 20 + 240)
    except (OSError, struct.error):
        return {}
    if header[:4] != b"PE\x00\x00" or len(header) < 24:
        return {}
    machine, sections, stamp = struct.unpack_from("<HHI", header, 4)
    size_optional = struct.unpack_from("<H", header, 20)[0]
    fields = {
        "Machine": MACHINES.get(machine, hex(machine)),
        "Sections": str(sections),
        "Compiled (UTC)": datetime.fromtimestamp(stamp, UTC).isoformat() if stamp else "",
    }
    optional = header[24 : 24 + size_optional]
    if len(optional) >= 70:
        magic = struct.unpack_from("<H", optional, 0)[0]
        fields["Subsystem"] = SUBSYSTEMS.get(struct.unpack_from("<H", optional, 68)[0], "")
        directories = 96 if magic == 0x10B else 112
        if len(optional) >= directories + 5 * 8:
            security = struct.unpack_from("<II", optional, directories + 4 * 8)
            fields["Signed"] = "yes (Authenticode present)" if security[1] else "no"
    return fields


def inventory_row(path):
    path = Path(path)
    stat = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    kind = classify(path)
    row = {
        "Path": str(path),
        "Name": path.name,
        "Extension": path.suffix.casefold(),
        "Size": str(stat.st_size),
        "Modified (UTC)": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
        "SHA-256": digest.hexdigest(),
        "Type": {"pe": "PE executable or library", "binary": "binary"}.get(kind, kind),
    }
    if kind == "pe":
        row.update(pe_fields(path))
    if not stat.st_size:
        row["Note"] = "empty file"
    return row


def write_inventory(paths, target, label=lambda path: str(path), check=lambda: None):
    """One CSV for every file given: the inventory of what has no richer reader."""
    rows = 0
    with Path(target).open("x", encoding="utf-8", newline="") as outgoing:
        writer = csv.writer(outgoing)
        writer.writerow(INVENTORY_HEADER)
        for path in paths:
            check()
            try:
                row = inventory_row(path)
            except OSError as exc:
                row = {"Path": str(path), "Name": Path(path).name, "Note": f"unreadable: {exc}"}
            row["Path"] = label(path)
            writer.writerow([row.get(name, "") for name in INVENTORY_HEADER])
            rows += 1
    return rows


def _write_rows(target, header, rows):
    count = 0
    with Path(target).open("x", encoding="utf-8", newline="") as outgoing:
        writer = csv.writer(outgoing)
        writer.writerow(header)
        for row in rows:
            writer.writerow(row)
            count += 1
    return count


def parse(source, output, progress=lambda _: None, kind=None):
    """Read one file as what it is. Returns {"outputs": [{"csv", "rows", "table"}], "warnings"}."""
    source, output = Path(source), Path(output)
    kind = kind or classify(source)
    outputs, warnings = [], []
    name = source.name

    if kind == "sqlite":
        connection = sqlite3.connect(f"file:{source}?mode=ro&immutable=1", uri=True)
        connection.text_factory = lambda raw: raw.decode("utf-8", errors="replace")
        try:
            tables = [
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                )
            ]
            for number, table in enumerate(tables):
                progress(f"{name} : {table}")
                try:
                    cursor = connection.execute(
                        f'SELECT * FROM "{table.replace(chr(34), chr(34) * 2)}"'
                    )
                    header = [item[0] for item in cursor.description]
                    target = output / f"{number:03d}-{table}.csv"
                    count = _write_rows(
                        target, header, ([_cell(value) for value in row] for row in cursor)
                    )
                except sqlite3.Error as exc:
                    warnings.append(f"{table}: {exc}")
                    continue
                if count:
                    outputs.append(dict(csv=str(target), rows=count, table=table))
        finally:
            connection.close()
    elif kind in ("mozlz4", "json"):
        raw = source.read_bytes()
        if kind == "mozlz4":
            import lz4.block

            raw = lz4.block.decompress(
                raw[12:], uncompressed_size=struct.unpack_from("<I", raw, 8)[0]
            )
        text = _text(raw)
        try:
            documents = [json.loads(text)]
        except ValueError:
            documents = [json.loads(line) for line in text.splitlines() if line.strip()]
        records = (
            documents[0]
            if len(documents) == 1
            and isinstance(documents[0], list)
            and all(isinstance(i, dict) for i in documents[0])
            else documents
        )
        flat = [
            dict(_flatten(record)) if isinstance(record, (dict, list)) else {"Value": _cell(record)}
            for record in records
        ]
        header = []
        for record in flat:
            header += [key for key in record if key not in header]
        target = output / "records.csv"
        count = _write_rows(
            target,
            header or ["Value"],
            ([record.get(key, "") for key in header] for record in flat),
        )
        outputs.append(dict(csv=str(target), rows=count, table=name))
    elif kind == "text":
        with source.open("rb") as stream:
            raw = stream.read(TEXT_BYTES + 1)
        if len(raw) > TEXT_BYTES:
            warnings.append(f"read the first {TEXT_BYTES} bytes of a larger file")
        lines = _text(raw[:TEXT_BYTES]).splitlines()
        target = output / "lines.csv"
        count = _write_rows(
            target,
            ["Line", "Text"],
            ((number, line[:CELL]) for number, line in enumerate(lines, 1)),
        )
        outputs.append(dict(csv=str(target), rows=count, table=name))
    else:
        target = output / "inventory.csv"
        count = write_inventory([source], target)
        outputs.append(dict(csv=str(target), rows=count, table=name))
    return dict(outputs=outputs, warnings=warnings, kind=kind)
