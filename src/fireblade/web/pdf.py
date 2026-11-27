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
from html.parser import HTMLParser
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


_NARROW = set("iljtfI.,:;'|!() ")
_WIDE = set("MWmw@%")


def _width(text: str, size: float) -> float:
    """Helvetica width by class of glyph: close enough to never overrun a column."""
    total = 0.0
    for char in text:
        if char in _NARROW:
            total += 0.3
        elif char in _WIDE:
            total += 0.85
        elif char.isupper():
            total += 0.7
        elif char.isdigit():
            total += 0.56
        else:
            total += 0.54
    return total * size


def wrap_width(text: str, points: float, size: float) -> list[str]:
    """Wrap on spaces so that no line is wider than `points`; a long token is cut."""
    if not text:
        return [""]
    out, current = [], ""
    for word in text.split(" "):
        while _width(word, size) > points and len(word) > 1:
            if current:
                out.append(current)
                current = ""
            cut = len(word)
            while cut > 1 and _width(word[:cut], size) > points:
                cut -= 1
            out.append(word[:cut])
            word = word[cut:]
        candidate = f"{current} {word}" if current else word
        if _width(candidate, size) <= points:
            current = candidate
        else:
            out.append(current)
            current = word
    out.append(current)
    return out


def _escape_pdf(text: str) -> bytes:
    """WinAnsi-safe bytes with the three characters a PDF string cannot hold raw."""
    text = text.replace("\u2192", "->").replace("\u2190", "<-").replace("\u2194", "<->")
    encoded = text.encode("cp1252", errors="replace")
    return encoded.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


class _Blocks(HTMLParser):
    """The report's HTML as blocks: headings, paragraphs and tables with their cells."""

    HEADINGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4}
    BLOCKS = {"p", "div", "li", "pre", "blockquote", "section", "article", "ul", "ol", "tr"}
    SKIPPED = {"head", "style", "script", "title"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks: list[tuple] = []
        self._text: list[str] = []
        self._kind = "p"
        self._skip = 0
        self._table: list | None = None
        self._row: list | None = None
        self._cell_open = False
        self._cell_head = False
        self._cell_width: float | None = None

    def _flush(self):
        text = " ".join("".join(self._text).split())
        self._text = []
        if text:
            self.blocks.append((self._kind, text))
        self._kind = "p"

    @staticmethod
    def _width(attrs):
        match = re.search(r"width:\s*([\d.]+)%", dict(attrs).get("style") or "")
        return float(match.group(1)) if match else None

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIPPED:
            self._skip += 1
        elif self._skip:
            return
        elif tag == "table" and self._table is None:
            self._flush()
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._text, self._cell_open = [], True
            self._cell_head, self._cell_width = tag == "th", self._width(attrs)
        elif self._cell_open:
            if tag == "br":
                self._text.append(" ")
        elif tag in self.HEADINGS:
            self._flush()
            self._kind = f"h{self.HEADINGS[tag]}"
        elif tag == "br":
            self._flush()
        elif tag in self.BLOCKS:
            self._flush()
            if tag == "li":
                self._text.append("\u2022 ")

    def handle_endtag(self, tag):
        if tag in self.SKIPPED:
            self._skip = max(0, self._skip - 1)
        elif self._skip:
            return
        elif tag in ("td", "th") and self._cell_open and self._row is not None:
            text = " ".join("".join(self._text).split())
            self._row.append((text, self._cell_head, self._cell_width))
            self._text, self._cell_open = [], False
        elif tag == "tr" and self._row is not None:
            if self._row:
                self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None and not self._cell_open:
            if self._table:
                self.blocks.append(("table", self._table))
            self._table = None
        elif self._cell_open:
            return
        elif tag in self.HEADINGS or tag in self.BLOCKS:
            self._flush()

    def handle_data(self, data):
        if not self._skip:
            self._text.append(data)

    def close(self):
        super().close()
        self._flush()


TEXT_WIDTH = PAGE_WIDTH - 2 * MARGIN_LEFT
HEADING_STYLE = {"h1": (16, 20, 8), "h2": (13, 17, 8), "h3": (11, 15, 6), "h4": (10, 13, 4)}
TABLE_SIZE, TABLE_LEADING, CELL_PAD = 8.5, 11, 3


class _Page:
    """One page being laid out: a list of PDF operators and a cursor."""

    def __init__(self):
        self.ops: list[str] = []
        self.y = PAGE_HEIGHT - MARGIN_TOP

    def text(self, x, y, value, size, bold=False, gray=0.0):
        font = "F2" if bold else "F1"
        self.ops.append(
            f"BT /{font} {size} Tf {gray} g {x:.1f} {y:.1f} Td "
            f"({_escape_pdf(value).decode('latin-1')}) Tj ET"
        )

    def fill(self, x, y, width, height, gray):
        self.ops.append(f"{gray} g {x:.1f} {y:.1f} {width:.1f} {height:.1f} re f 0 g")

    def rule(self, x1, y, x2, gray=0.8):
        self.ops.append(f"{gray} G 0.5 w {x1:.1f} {y:.1f} m {x2:.1f} {y:.1f} l S 0 G")


def _column_widths(rows):
    count = max(len(row) for row in rows)
    declared = [None] * count
    for position, cell in enumerate(rows[0]):
        declared[position] = cell[2]
    if all(width for width in declared):
        total = sum(declared)
        return [TEXT_WIDTH * width / total for width in declared]
    weights = []
    for position in range(count):
        longest = max((len(row[position][0]) for row in rows if position < len(row)), default=4)
        weights.append(min(max(longest, 5), 42))
    total = sum(weights)
    return [TEXT_WIDTH * weight / total for weight in weights]


def _layout(blocks):
    pages = [_Page()]

    def page():
        return pages[-1]

    def need(height):
        if page().y - height < MARGIN_BOTTOM + 14:
            pages.append(_Page())

    for block in blocks:
        kind = block[0]
        if kind in HEADING_STYLE:
            size, leading, after = HEADING_STYLE[kind]
            lines = wrap_width(block[1], TEXT_WIDTH, size)
            need(leading * len(lines) + after + 2 * LEADING)
            page().y -= 4
            for line in lines:
                page().y -= leading
                page().text(MARGIN_LEFT, page().y, line, size, bold=True)
            page().y -= after
        elif kind == "p":
            for line in wrap_width(block[1], TEXT_WIDTH, FONT_SIZE):
                need(LEADING)
                page().y -= LEADING
                page().text(MARGIN_LEFT, page().y, line, FONT_SIZE)
            page().y -= 3
        else:
            rows = block[1]
            widths = _column_widths(rows)
            header = rows[0] if all(cell[1] for cell in rows[0]) else None
            body = rows[1:] if header else rows

            def draw(row, head=False, widths=widths, header=header):
                cells = [
                    wrap_width(row[i][0], widths[i] - 2 * CELL_PAD, TABLE_SIZE)
                    if i < len(row)
                    else [""]
                    for i in range(len(widths))
                ]
                height = max(len(c) for c in cells) * TABLE_LEADING + 4
                if page().y - height < MARGIN_BOTTOM + 14:
                    pages.append(_Page())
                    if header and not head:
                        draw(header, True)
                top = page().y
                if head:
                    page().fill(MARGIN_LEFT, top - height, TEXT_WIDTH, height, 0.92)
                x = MARGIN_LEFT
                for width, lines in zip(widths, cells, strict=True):
                    for offset, line in enumerate(lines):
                        page().text(
                            x + CELL_PAD,
                            top - 2 - TABLE_LEADING * (offset + 1) + 2.5,
                            line,
                            TABLE_SIZE,
                            bold=head,
                        )
                    x += width
                page().rule(MARGIN_LEFT, top - height, MARGIN_LEFT + TEXT_WIDTH)
                page().y = top - height

            page().y -= 2
            if header:
                need(40)
                draw(header, True)
            for row in body:
                draw(row)
            page().y -= 8
    return pages


def text_pdf(markup: str, target: Path, title: str = "", subject: str = "") -> Path:
    """Write `markup` (the report's own HTML) as a PDF at `target`.

    Headings are bold, a table keeps its columns (the header's own widths when it declares
    them) and repeats its header on the next page, and every page says where it is.
    """
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    parser = _Blocks()
    parser.feed(str(markup or ""))
    parser.close()
    if not title:
        title = next((value for kind, value in parser.blocks if kind == "h1"), "Kagarasu")
    pages = _layout(parser.blocks)

    objects: list[bytes] = []

    def add(payload: bytes) -> int:
        objects.append(payload)
        return len(objects)

    catalog_id = add(b"")  # filled at the end
    pages_id = add(b"")
    font_id = add(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
    )
    bold_id = add(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"
    )
    page_ids = []
    for number, page in enumerate(pages, start=1):
        page.text(MARGIN_LEFT, 28, f"{title[:70]}  -  page {number} / {len(pages)}", 8, gray=0.45)
        stream = "\n".join(page.ops).encode("latin-1", errors="replace")
        content_id = add(
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
        )
        page_ids.append(
            add(
                f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
                f"/Resources << /Font << /F1 {font_id} 0 R /F2 {bold_id} 0 R >> >> "
                f"/Contents {content_id} 0 R >>".encode()
            )
        )
    kids = " ".join(f"{page} 0 R" for page in page_ids)
    objects[pages_id - 1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode()
    objects[catalog_id - 1] = f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode()
    info_id = add(
        f"<< /Title <FEFF{title.encode('utf-16-be').hex()}> "
        f"/Subject <FEFF{subject.encode('utf-16-be').hex()}> "
        f"/Producer (Kagarasu Host) >>".encode()
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
