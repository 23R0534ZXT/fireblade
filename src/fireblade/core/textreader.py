"""Read the files a forensic parser ignores: plain text and saved HTML pages.

A seized tree always contains files that matter to the investigation but carry no
artefact: a saved web page, an email exported as text, a note, a printer spool. They
are not evidence of execution, but they are evidence, and leaving them unread means
the examiner has to open another tool and remember what was inside.

This reader turns them into the same shape as every other source: one row per line,
with the file it came from, so the timeline, the search and the report keep working.
It reads, it never interprets: no dates are invented, and a line that cannot be
decoded is kept with its replacement characters rather than dropped.
"""
import codecs
import html
import re
from html.parser import HTMLParser
from pathlib import Path

HEADERS = ('Source', 'Ligne', 'Horodatage', 'Texte', 'Lien')

TEXT_SUFFIXES = ('.txt', '.log', '.md', '.text', '.csv', '.conf', '.ini', '.yaml', '.yml',
                 '.json', '.xml', '.rtf', '.eml', '.msg', '.nfo', '.lst', '.dat.txt')
HTML_SUFFIXES = ('.html', '.htm', '.xhtml', '.mht', '.mhtml')

# Saved pages are read whole, but a page is not supposed to be a disk image.
LIMIT_PAGE_BYTES = 16 * 1024 * 1024
LIMIT_BYTES = 8 * 1024 * 1024
LIMIT_LINES = 200000

# A byte-order mark is a promise about the encoding, not a guess. Windows writes
# UTF-16 with one whenever PowerShell redirects output or Notepad saves "Unicode",
# and a reader that ignores it shows every second byte as a NUL.
BOMS = ((b'\xff\xfe\x00\x00', 'utf-32'), (b'\x00\x00\xfe\xff', 'utf-32'),
        (b'\xff\xfe', 'utf-16'), (b'\xfe\xff', 'utf-16'),
        (b'\xef\xbb\xbf', 'utf-8-sig'))

CHARSET = re.compile(rb'charset\s*=\s*["\']?([\w-]+)', re.IGNORECASE)

# A leading date is worth keeping as a column, but only when it is unambiguous:
# the reader never guesses a year, and never fills a timestamp from the file name.
LEADING_DATE = re.compile(
    r'^\s*\[?(?P<stamp>(?:\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?'
    r'|\d{2}/\d{2}/\d{4} \d{2}:\d{2}(?::\d{2})?'
    r'|\d{2} [A-Z][a-z]{2} \d{4} \d{2}:\d{2}:\d{2}))')


class PageText(HTMLParser):
    """Visible text and links of a saved page, without a browser or a dependency."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.links = []
        self.title = ''
        self._in_title = False
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag in ('script', 'style'):
            self._skip += 1
        elif tag == 'title':
            self._in_title = True
        elif tag == 'a':
            href = attributes.get('href')
            if href:
                self.links.append(href.strip())
            self.parts.append(' ')
        elif tag in ('p', 'br', 'div', 'li', 'tr', 'h1', 'h2', 'h3', 'h4', 'td'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style') and self._skip:
            self._skip -= 1
        elif tag == 'title':
            self._in_title = False

    def handle_data(self, data):
        if self._skip:
            return
        if self._in_title:
            self.title += data
        self.parts.append(data)

    def text(self):
        raw = html.unescape(''.join(self.parts))
        lines = (' '.join(line.split()) for line in raw.splitlines())
        return [line for line in lines if line]


def sniff(path):
    """What the file is, by suffix first and by content when the suffix lies."""
    path = Path(path)
    suffix = path.suffix.casefold()
    if suffix in HTML_SUFFIXES:
        return 'html'
    if suffix in TEXT_SUFFIXES:
        return 'text'
    try:
        with path.open('rb') as stream:
            head = stream.read(2048)
    except OSError:
        return None
    probe = head
    declared = bom_encoding(head)
    if declared:
        text, _ = decode_bytes(head, declared)
        probe = text.encode('utf-8', 'ignore')
    lowered = probe.lower()
    if b'<html' in lowered or b'<!doctype html' in lowered:
        return 'html'
    if b'\0' in probe:
        return None
    return 'text' if decodes(head) else None


def bom_encoding(data):
    """The encoding a byte-order mark declares, or None."""
    for mark, encoding in BOMS:
        if data.startswith(mark):
            return encoding
    return None


def page_encoding(data):
    """The charset a saved page declares, when it declares a usable one."""
    match = CHARSET.search(data[:4096])
    if not match:
        return None
    name = match.group(1).decode('ascii', 'ignore').lower()
    try:
        codecs.lookup(name)
    except LookupError:
        return None
    return name


def decode_bytes(data, encoding=None):
    """Text and the encoding it took: BOM, then the declared one, UTF-8, cp1252."""
    for candidate in [encoding, bom_encoding(data), 'utf-8', 'cp1252']:
        if not candidate:
            continue
        try:
            return data.decode(candidate), candidate
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode('utf-8', 'replace'), 'utf-8/replace'


def decodes(data):
    """True when the bytes look like text: a BOM, UTF-8, or the French code page."""
    if bom_encoding(data):
        return True
    for encoding in ('utf-8', 'cp1252'):
        try:
            data.decode(encoding)
            return True
        except UnicodeDecodeError:
            continue
    return False


def read_text(path, encoding=None, limit_bytes=None):
    """Lines of a text file, decoded for real: bad bytes stay visible as bad bytes."""
    path = Path(path)
    with path.open('rb') as stream:
        data = stream.read(LIMIT_BYTES if limit_bytes is None else limit_bytes)
    text, used = decode_bytes(data, encoding)
    return text.splitlines(), used, len(data)


def rows(path, kind=None, limit_lines=None):
    """Rows in the same shape as every other source, ready for the importer."""
    limit_lines = LIMIT_LINES if limit_lines is None else limit_lines
    path = Path(path)
    kind = kind or sniff(path)
    if kind is None:
        return []
    source = str(path)
    produced = []
    if kind == 'html':
        parser = PageText()
        try:
            with path.open('rb') as stream:
                page_bytes = stream.read(LIMIT_PAGE_BYTES)
        except OSError:
            return []
        # A page saved by a French machine is often cp1252, and one printed by a
        # Windows tool can be UTF-16: decode it for real instead of replacing.
        body, _ = decode_bytes(page_bytes, page_encoding(page_bytes))
        parser.feed(body)
        lines = parser.text()
        for index, line in enumerate(lines[:limit_lines], start=1):
            stamp = stamp_of(line)
            produced.append((source, index, stamp, line, ''))
        for link in parser.links[:limit_lines]:
            produced.append((source, '', '', '', link))
        return produced
    lines, _, _ = read_text(path)
    for index, line in enumerate(lines[:limit_lines], start=1):
        produced.append((source, index, stamp_of(line), line, ''))
    return produced


def stamp_of(line):
    match = LEADING_DATE.match(line)
    return match.group('stamp') if match else ''


def write_csv(path, target, kind=None):
    """Write the reader's rows to a CSV the importer accepts, and report the counts."""
    import csv

    resolved = kind or sniff(path)
    produced = rows(path, resolved)
    target = Path(target)
    with target.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(HEADERS)
        writer.writerows(produced)
    size = Path(path).stat().st_size
    limit = LIMIT_PAGE_BYTES if resolved == 'html' else LIMIT_BYTES
    # A file bigger than a limit is read in part: the analyst has to be told,
    # otherwise the analysis looks complete when half the file is missing.
    truncated = size > limit or len(produced) >= LIMIT_LINES
    return {'rows': len(produced), 'csv': str(target), 'kind': resolved,
            'size': size, 'truncated': truncated}
