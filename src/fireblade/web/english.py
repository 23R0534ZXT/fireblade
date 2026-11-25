"""The Host speaks English: documents and data the core wrote in its source language.

The core writes its sentences in French and the interface translates them through
``core.i18n``. A report, a certificate or a diagnostic leaves the interface: it is a file or
an API answer, never drawn by a window that translates for it. This module is the one door
those take on the way out.

Only wording changes. Values the analyst or the evidence supplied (names, paths, hashes,
dates, the text of a log line) are carried through exactly as they were.
"""

from __future__ import annotations

import html as htmllib
import re
from pathlib import Path

from fireblade.core.i18n import english_text, lookup

_TAG = re.compile(r"(<[^>]*>)")
_ATTRIBUTE = re.compile(r'\b(alt|title)="([^"]*)"')
_QUOTED = ("pre", "code", "script", "style")


def _cell(plain: str) -> str:
    """A table cell: only a whole label, or a list of whole labels, is translated.

    A cell holds what the evidence said as often as what the generator said, so a sentence
    is never rewritten inside one; a level, a status or a type that the generator wrote there
    (alone, or joined by commas) reads in English.
    """
    whole = lookup(plain)
    if whole != plain:
        return whole
    sized = re.fullmatch(r"([\d\s\u00a0\u202f.,]+) octets?", plain)
    if sized:  # a size the generator wrote: a number and its unit, nothing the evidence said
        return f"{sized.group(1)} bytes"
    if ", " in plain:
        parts = plain.split(", ")
        translated = [lookup(part) for part in parts]
        if translated != parts:
            return ", ".join(translated)
    return plain


# What a core generator writes inside a <pre>, where nothing is translated because evidence lives
# there. Each fragment carries the generator's own punctuation or markup, so it is never a value.
_GENERATED = (
    ('<pre class="note">Note : ', '<pre class="note">Note: '),
    (
        "[Valeur abrégée dans le rapport ; valeur complète dans l’analyse.]",
        "[Value shortened in the report; the complete value is in the analysis.]",
    ),
)

# The "Filters applied" row of the investigation report describes the view the analyst had; its
# words (and, or, not, the operators) are the generator's, its names and values are not.
_VIEW_ROW = re.compile(r"(<th>Filters applied</th><td><pre>)(.*?)(</pre>)", re.S)
_VIEW_WORDS = (
    ("Signets uniquement", "Bookmarked rows only"),
    ("Aucun filtre", "No filter"),
    ("Recherche : ", "Search: "),
    ("Ligne source", "Source row"),
    ("Signet", "Bookmark"),
    (" ET ", " AND "),
    (" OU ", " OR "),
    ("NON (", "NOT ("),
)


def _view(match) -> str:
    body = match.group(2)
    from fireblade.core.models import OPERATORS

    for label, _code in OPERATORS:
        english = lookup(label)
        if english != label:
            body = body.replace(f" {label} ", f" {english} ")
    for french, english in _VIEW_WORDS:
        if french in ("Ligne source", "Signet"):
            continue  # a column name, which may be the analyst's own
        body = body.replace(french, english)
    return match.group(1) + body + match.group(3)


def _generated(text: str) -> str:
    for french, english in _GENERATED:
        text = text.replace(french, english)
    return _VIEW_ROW.sub(_view, text)


def document(text: str) -> str:
    """An HTML document with its sentences in English; markup and values untouched.

    Nothing inside <pre>, <code>, <script> or <style> is touched: that is where the evidence
    and the page's own code live.
    """
    text = text.replace('<html lang="fr">', '<html lang="en">')
    out = []
    quoted = 0
    cell = 0
    for piece in _TAG.split(text):
        if piece.startswith("<") and piece.endswith(">"):
            name = re.match(r"</?\s*([a-zA-Z0-9]+)", piece)
            tag = name.group(1).lower() if name else ""
            closing = piece.startswith("</")
            if tag in _QUOTED:
                quoted = max(0, quoted + (-1 if closing else 1))
            elif tag in ("td", "th"):
                cell = 0 if closing else (1 if tag == "td" else 0)
            if not quoted:
                piece = _ATTRIBUTE.sub(_attribute, piece)
            out.append(piece)
            continue
        if quoted or not piece.strip():
            out.append(piece)
            continue
        plain = htmllib.unescape(piece)
        lead = plain[: len(plain) - len(plain.lstrip())]
        core = plain.strip()
        if cell:
            translated = lead + _cell(core) + plain[len(plain.rstrip()) :]
        else:
            translated = english_text(plain)
        out.append(piece if translated == plain else htmllib.escape(translated, quote=False))
    return _generated("".join(out))


def _attribute(match):
    plain = htmllib.unescape(match.group(2))
    translated = english_text(plain)
    if translated == plain:
        return match.group(0)
    return f'{match.group(1)}="{htmllib.escape(translated)}"'


def rewrite(path) -> None:
    """Translate an HTML file in place; the original is replaced only once the copy is whole."""
    path = Path(path)
    source = path.read_text(encoding="utf-8")
    translated = document(source)
    if translated == source:
        return
    partial = path.with_name(path.name + ".partial")
    partial.write_text(translated, encoding="utf-8")
    partial.replace(path)


def data(value):
    """A JSON-shaped value with every string it holds in English (keys are left alone)."""
    if isinstance(value, str):
        return english_text(value)
    if isinstance(value, list):
        return [data(item) for item in value]
    if isinstance(value, dict):
        return {key: data(item) for key, item in value.items()}
    return value
