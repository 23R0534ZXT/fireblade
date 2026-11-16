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
import html
import re
from html.parser import HTMLParser
from pathlib import Path

HEADERS = ('Source', 'Ligne', 'Horodatage', 'Texte', 'Lien')

TEXT_SUFFIXES = ('.txt', '.log', '.md', '.text', '.csv', '.conf', '.ini', '.yaml', '.yml',
                 '.json', '.xml', '.rtf', '.eml', '.msg', '.nfo', '.lst', '.dat.txt')
HTML_SUFFIXES = ('.html', '.htm', '.xhtml', '.mht', '.mhtml')

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
    lowered = head.lower()
    if b'<html' in lowered or b'<!doctype html' in lowered:
        return 'html'
    if b'\0' in head:
        return None
    return 'text' if decodes(head) else None


def decodes(data):
    """True when the bytes look like text: UTF-8, or the French code page."""
    for encoding in ('utf-8', 'cp1252'):
        try:
            data.decode(encoding)
            return True
        except UnicodeDecodeError:
            continue
    return False


def read_text(path, encoding=None, limit_bytes=8 * 1024 * 1024):
    """Lines of a text file, decoded for real: bad bytes stay visible as bad bytes."""
    path = Path(path)
    with path.open('rb') as stream:
        data = stream.read(limit_bytes)
    for candidate in ([encoding] if encoding else []) + ['utf-8', 'cp1252']:
        try:
            decoded = data.decode(candidate)
            return decoded.splitlines(), candidate, len(data)
        except UnicodeDecodeError:
            continue
    return data.decode('utf-8', 'replace').splitlines(), 'utf-8/replace', len(data)


def rows(path, kind=None, limit_lines=200000):
    """Rows in the same shape as every other source, ready for the importer."""
    path = Path(path)
    kind = kind or sniff(path)
    if kind is None:
        return []
    source = str(path)
    produced = []
    if kind == 'html':
        parser = PageText()
        try:
            parser.feed(path.read_text(encoding='utf-8', errors='replace'))
        except OSError:
            return []
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

    produced = rows(path, kind)
    target = Path(target)
    with target.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(HEADERS)
        writer.writerows(produced)
    return {'rows': len(produced), 'csv': str(target), 'kind': kind or sniff(path)}
