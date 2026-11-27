"""Read-only navigation of supported disk images."""

from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime
from itertools import islice
from pathlib import Path

from fireblade.core.disk import image_segments


@contextmanager
def open_image(source, *, empty_error="No supported file system was found in this image."):
    from dissect.target import Target, container

    source = Path(source)
    segments = image_segments(source)
    if not source.is_file():
        raise ValueError("The image must be a file mounted inside Host.")
    is_ewf = source.suffix.casefold() == ".e01"
    if not is_ewf and len(segments) > 1:
        raise ValueError("Select the first EWF segment (.E01).")
    with ExitStack() as resources:
        handles = [resources.enter_context(segment.open("rb")) for segment in segments]
        disk = container.open(handles if len(handles) > 1 else handles[0])
        resources.callback(disk.close)
        if is_ewf:
            if disk.__type__ != "ewf":
                raise ValueError("The selected file is not an EWF image.")
            ewf = disk.ewf
            total = 0
            for index in range(len(segments)):
                segment = ewf.segment(index)
                expected = b"done" if index == len(segments) - 1 else b"next"
                if (
                    segment.ewfheader.segment_number != index + 1
                    or segment.sections[-1].type != expected
                ):
                    raise ValueError("Invalid or incomplete EWF segment sequence.")
                total += segment.chunk_count
            if total != ewf.volume.chunk_count:
                raise ValueError("The EWF segments do not contain the full image.")
        target = Target()
        target.disks.add(disk)
        target.apply()
        if not target.filesystems:
            raise ValueError(empty_error)
        yield target


def image_entry(target, partition, path):
    if not 1 <= partition <= len(target.filesystems):
        raise ValueError("Unknown file system.")
    node = target.filesystems[partition - 1].path("/")
    if path == "/":
        return node
    if not path.startswith("/") or "\\" in path or "\x00" in path:
        raise ValueError("Invalid image path.")
    for name in path[1:].split("/"):
        if name in ("", ".", ".."):
            raise ValueError("Invalid image path.")
        node = node / name
        if node.is_symlink():
            raise ValueError("Links and reparse points cannot be followed.")
    return node


def entry_info(node):
    if node.is_symlink():
        return {"name": node.name, "kind": "link"}
    info = node.stat()

    def date(field):
        value = getattr(info, field, None)
        return datetime.fromtimestamp(value, UTC).isoformat() if value is not None else None

    return {
        "name": node.name,
        "kind": "directory" if node.is_dir() else "file" if node.is_file() else "special",
        "size": info.st_size,
        "created": date("st_birthtime"),
        "modified": date("st_mtime"),
    }


def browse(source, partition=0, path="/", offset=0):
    if offset < 0:
        raise ValueError("Invalid directory offset.")
    with open_image(source) as target:
        partitions = [
            {"index": index, "type": fs.__type__} for index, fs in enumerate(target.filesystems, 1)
        ]
        if partition == 0:
            return {"partitions": partitions, "entries": []}
        directory = image_entry(target, partition, path)
        if not directory.is_dir():
            raise ValueError("Select a directory.")
        # Keep file-system order stable across pages, and bound returned metadata.
        entries = []
        for node in islice(directory.iterdir(), offset, offset + 201):
            try:
                entries.append(entry_info(node))
            except (OSError, ValueError, OverflowError):
                entries.append({"name": node.name, "kind": "unreadable"})
        return {
            "partitions": partitions,
            "entries": entries[:200],
            "next": offset + 200 if len(entries) > 200 else None,
        }
