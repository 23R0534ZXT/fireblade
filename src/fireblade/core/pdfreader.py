"""The text layer of a PDF, when there is one: no OCR, and nothing invented.

A PDF in a seizure is often the readable form of the evidence: a signed contract, an
exported mail, a scanned invoice with a text layer left by the scanner. Reading that
layer costs one optional dependency and saves the examiner from opening a second tool.

What this module refuses to do matters as much: a page with no text layer is reported
as a scan, not turned into empty rows, and when the dependency is absent the reader
says so instead of failing halfway through a file.
"""

import csv
from pathlib import Path

HEADERS = ("Source", "Page", "Horodatage", "Texte", "Lien")

# A document is read page by page; the cap keeps a 4000-page bundle from becoming a
# timeline nobody asked for. Lines are capped like every other reader.
LIMIT_PAGES = 2000
LIMIT_LINES = 200000


def backend():
    """The reader class when pypdf is installed, None otherwise."""
    try:
        from pypdf import PdfReader
    except ImportError:
        return None
    return PdfReader


def available():
    return backend() is not None


def rows(path, limit_pages=LIMIT_PAGES, limit_lines=LIMIT_LINES):
    """One row per text line, with the page it came from, and what the file gave."""
    reader_class = backend()
    if reader_class is None:
        return [], dict(kind="pdf", status="missing", pages=0, text_pages=0, warnings=[])
    from fireblade.core.textreader import stamp_of

    path = Path(path)
    source = str(path)
    try:
        document = reader_class(str(path))
        if getattr(document, "is_encrypted", False):
            # Reading it would need a password: say so instead of returning a scan.
            return [], dict(kind="pdf", status="encrypted", pages=0, text_pages=0, warnings=[])
        pages = len(document.pages)
    except Exception as error:  # truncated, empty or not a PDF at all
        return [], dict(
            kind="pdf", status="unreadable", pages=0, text_pages=0, warnings=[str(error)]
        )
    produced, text_pages, warnings = [], 0, []
    if not pages:
        return [], dict(kind="pdf", status="empty", pages=0, text_pages=0, warnings=[])
    read = 0
    try:
        for number, page in enumerate(document.pages[:limit_pages], start=1):
            read += 1
            try:
                text = page.extract_text() or ""
            except Exception as error:  # a damaged page must not lose the readable ones
                warnings.append("Page %d : %s" % (number, error))
                continue
            lines = [line.strip() for line in text.splitlines()]
            lines = [line for line in lines if line]
            if lines:
                text_pages += 1
            for line in lines:
                produced.append((source, number, stamp_of(line), line, ""))
                if len(produced) >= limit_lines:
                    warnings.append("Texte arrêté à %d lignes" % limit_lines)
                    return produced, dict(
                        kind="pdf",
                        status="ok",
                        pages=pages,
                        text_pages=text_pages,
                        warnings=warnings,
                    )
    except Exception as error:
        return produced, dict(
            kind="pdf",
            status="unreadable",
            pages=pages,
            text_pages=text_pages,
            warnings=warnings + [str(error)],
        )
    if text_pages:
        status = "ok"
    elif warnings and len(warnings) >= read:
        status = "unreadable"
    else:
        status = "scanned"
    return produced, dict(
        kind="pdf", status=status, pages=pages, text_pages=text_pages, warnings=warnings
    )


def write_csv(path, target, limit_pages=LIMIT_PAGES):
    """Write the reader's rows to a CSV the importer accepts, and report what it saw."""
    produced, info = rows(path, limit_pages)
    target = Path(target)
    with target.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(HEADERS)
        writer.writerows(produced)
    return dict(rows=len(produced), csv=str(target), **info)
