"""Every refusal the core raises on a path the Host can reach has an English entry.

The core states its refusals in French; the Host answers in English through ``core.i18n``.
A message added to one of these modules without an entry in ``core/i18n_errors.py`` would
reach the analyst in French, so it fails here, with the message, until it is translated.
"""

import ast
import re
from pathlib import Path

import pytest

from fireblade.core.i18n import english

CORE = Path(__file__).resolve().parents[1] / "src" / "fireblade" / "core"
# The modules whose refusals an analyst can meet in the Host: parsing a filter or an
# expression, importing, exporting, rules, indicators, the case and its session.
MODULES = [
    "expressions",
    "conditions",
    "filter_text",
    "derived",
    "models",
    "sessions",
    "settings",
    "spreadsheets",
    "summaries",
    "timestamps",
    "csv_chunks",
    "engine",
    "investigations",
    "ioc_hunt",
    "rule_store",
    "preferences",
    "collection",
    "case_storage",
    "analysis_storage",
    "layout",
    "layout_images",
    "paths",
    "outline",
    "collection_expressions",
    "collection_organization",
    "criteria_literals",
    "alert_context",
    "hayabusa_rules",
    "disk_destination",
    "plugin_registry",
    "profile_plugins",
    "icon_assets",
    "catscale",
    "parse_pool",
]
FRENCH = re.compile(
    r"[àâçéèêëîïôûùüœÉÈÀÊ]|\b(Aucun|Aucune|doit|invalide|limité|limitée|absente?|trop|attendu|attendue|requis|requise|inconnu|inconnue|refusée?|impossible|dépasse|nécessaire|existe|déjà)\b"
)


def _messages(module):
    tree = ast.parse((CORE / f"{module}.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call) and node.exc.args):
            continue
        first = node.exc.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            yield first.value
        elif isinstance(first, ast.JoinedStr):
            yield "".join(
                part.value if isinstance(part, ast.Constant) else "{}" for part in first.values
            )


@pytest.mark.parametrize("module", MODULES)
def test_a_refusal_raised_by_the_module_reads_in_english(module):
    untranslated = sorted(
        {text for text in _messages(module) if FRENCH.search(text) and english(text) == text}
    )
    assert not untranslated, f"{module}: add these to core/i18n_errors.py\n  " + "\n  ".join(
        untranslated
    )
