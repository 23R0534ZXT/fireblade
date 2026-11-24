"""A small PDF writer for the Host edition, without a graphics toolkit.

The desktop turns its report into a PDF through Qt; the container has no Qt, and a
report still has to leave the case as a file a client can open. This module writes
the simplest thing that is a real PDF: Helvetica text, one page per screenful, and
the report's own structure (headings, paragraphs, table rows) kept as lines.

Nothing here tries to be a layout engine. A line that does not fit is wrapped; a
page that fills up opens the next one; a character outside WinAnsi is replaced so
the file always opens.
"""

from __future__ import annotations

import html as html_module
import re
from pathlib import Path

PAGE_WIDTH = 595  # A4 at 72 dpi
PAGE_HEIGHT = 842
MARGIN_LEFT = 48
MARGIN_TOP = 56
MARGIN_BOTTOM = 48
FONT_SIZE = 9.5
LEADING = 12.5
CHARS_PER_LINE = 104  # 9.5 pt Helvetica in a 499 pt column

BLOCK_TAGS = re.compile(r"</(p|h1|h2|h3|h4|li|tr|pre|div|table|blockquote)>", re.I)
CELL_TAGS = re.compile(r"</t[dh]>", re.I)
BREAK_TAGS = re.compile(r"<br\s*/?>", re.I)
HEAD_BLOCK = re.compile(r"<head.*?</head>", re.I | re.S)
STYLE_BLOCK = re.compile(r"<style.*?</style>", re.I | re.S)
SCRIPT_BLOCK = re.compile(r"<script.*?</script>", re.I | re.S)
ANY_TAG = re.compile(r"<[^>]+>")


def html_to_lines(markup: str) -> list[str]:
    """The report as plain lines: structure kept, markup gone.

    A table row becomes one line with its cells separated by " | "; a heading or a
    paragraph ends its line; an empty line separates blocks, so the page breathes.
    """
    text = HEAD_BLOCK.sub("", str(markup or ""))
    text = STYLE_BLOCK.sub("", text)
    text = SCRIPT_BLOCK.sub("", text)
    text = BREAK_TAGS.sub("\n", text)
    text = CELL_TAGS.sub(" | ", text)
    text = BLOCK_TAGS.sub("\n", text)
    text = ANY_TAG.sub("", text)
    text = html_module.unescape(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines: list[str] = []
    for raw in text.split("\n"):
        line = " ".join(raw.split())
        if line.endswith(" | "):
            line = line[:-3].rstrip()
        lines.append(line)
    # Squash runs of blank lines: they cost a page for nothing.
    cleaned: list[str] = []
    for line in lines:
        if not line and (not cleaned or not cleaned[-1]):
            continue
        cleaned.append(line)
    while cleaned and not cleaned[-1]:
        cleaned.pop()
    return cleaned


def wrap(line: str, width: int = CHARS_PER_LINE) -> list[str]:
    """Wrap one line on spaces; a word longer than the width is cut, not lost."""
    if not line:
        return [""]
    out, current = [], ""
    for word in line.split(" "):
        while len(word) > width:
            if current:
                out.append(current)
                current = ""
            out.append(word[:width])
            word = word[width:]
        candidate = f"{current} {word}".strip() if current else word
        if len(candidate) <= width:
            current = candidate
        else:
            out.append(current)
            current = word
    if current or not out:
        out.append(current)
    return out


def _escape_pdf(text: str) -> bytes:
    """WinAnsi-safe bytes with the three characters a PDF string cannot hold raw."""
    encoded = text.encode("cp1252", errors="replace")
    return encoded.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def text_pdf(markup: str, target: Path, title: str = "Fireblade", subject: str = "") -> Path:
    """Write `markup` (the report's own HTML) as a PDF at `target`."""
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for line in html_to_lines(markup):
        lines.extend(wrap(line))
    per_page = max(10, int((PAGE_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM) // LEADING))
    pages = [lines[i : i + per_page] for i in range(0, len(lines), per_page)] or [[""]]

    objects: list[bytes] = []

    def add(payload: bytes) -> int:
        objects.append(payload)
        return len(objects)

    catalog_id = add(b"")  # filled at the end
    pages_id = add(b"")
    font_id = add(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
    )
    page_ids = []
    for page_lines in pages:
        content = [
            f"BT /F1 {FONT_SIZE} Tf {LEADING} TL {MARGIN_LEFT} {PAGE_HEIGHT - MARGIN_TOP} Td"
        ]
        for position, line in enumerate(page_lines):
            if position:
                content.append("T*")
            content.append(f"({_escape_pdf(line).decode('latin-1')}) Tj")
        content.append("ET")
        stream = "\n".join(content).encode("latin-1", errors="replace")
        content_id = add(
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
        )
        page_ids.append(
            add(
                f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
                f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>".encode()
            )
        )
    kids = " ".join(f"{page} 0 R" for page in page_ids)
    objects[pages_id - 1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode()
    objects[catalog_id - 1] = f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode()
    info_id = add(
        f"<< /Title ({_escape_pdf(title).decode('latin-1')}) "
        f"/Subject ({_escape_pdf(subject).decode('latin-1')}) "
        f"/Producer (Fireblade Host) >>".encode()
    )

    buffer = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, payload in enumerate(objects, start=1):
        offsets.append(len(buffer))
        buffer += f"{number} 0 obj\n".encode() + payload + b"\nendobj\n"
    start_xref = len(buffer)
    buffer += f"xref\n0 {len(objects) + 1}\n".encode()
    buffer += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        buffer += f"{offset:010d} 00000 n \n".encode()
    buffer += (
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R /Info {info_id} 0 R >>\n"
        f"startxref\n{start_xref}\n%%EOF\n"
    ).encode()
    target.write_bytes(bytes(buffer))
    return target
