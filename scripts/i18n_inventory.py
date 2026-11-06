"""Inventory of the French text Fireblade can show, and what is still untranslated.

The interface is written in French and displayed through `core/i18n.py`. This
script answers one question: which French strings can reach a user interface
without an English entry?

    python -m scripts.i18n_inventory            # summary
    python -m scripts.i18n_inventory --missing  # one string per line
    python -m scripts.i18n_inventory --write-baseline tests/data/untranslated.txt

A string is *on a surface* when it is consumed by something that displays it:
a widget constructor, `setText`, `showMessage`, a menu, a table header, a file
dialog. Logger calls and internal exceptions are not surfaces — nobody reads
them — unless they are also passed to one of those.

`{}` in a table key matches any run of characters, so an f-string
(`f"Analyse absente : {name}"`) is expected in the table as
`"Analyse absente : {}"`.
"""
import argparse
import ast
import json
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "fireblade")

# Calls whose arguments are read by a human.
SURFACE_CALLS = {
    # widgets built with their label
    "QLabel", "QPushButton", "QCheckBox", "QRadioButton", "QGroupBox", "QToolButton",
    "QAction", "QMenu", "QDialog", "QMessageBox", "QInputDialog", "QListWidgetItem",
    "QTreeWidgetItem", "QTableWidgetItem", "QStandardItem", "QProgressDialog",
    # text set after construction
    "setText", "setWindowTitle", "setTitle", "setPlaceholderText", "setToolTip",
    "setStatusTip", "setWhatsThis", "setAccessibleName", "setLabelText", "setMessage",
    "setInformativeText", "setDetailedText", "setButtonText", "setTabText", "addTab",
    "insertTab", "setTabToolTip", "setHorizontalHeaderLabels", "setVerticalHeaderLabels",
    # menus and toolbars
    "addAction", "addMenu", "addSection", "addSeparator", "setShortcutText",
    # status and messages
    "showMessage", "information", "warning", "critical", "question", "about",
    "setWindowFilePath", "progress", "setFormat", "setCommitPageData",
    # lists, combos, tables
    "addItem", "addItems", "addRow", "addRows", "appendRow", "setItemText",
    "setCellWidget", "addWidget", "insertRow", "setColumnCount",
    # file dialogs
    "getOpenFileName", "getSaveFileName", "getExistingDirectory", "getOpenFileNames",
    "getExistingDirectoryUrl",
    # our own helpers that end up on a surface
    "action", "notify", "status", "label", "button", "message", "note", "hint",
    "emit", "emit_status", "setStatusTip", "setWindowFilePath",
    # models built with their column titles
    "Rows", "RowModel", "TableModel", "Model", "QStandardItemModel", "Columns",
    "setHeaderLabels", "addToolBar", "addDockWidget", "setTabBar", "setTitle",
}

# Calls that write text nobody reads in the interface.
INTERNAL_CALLS = {
    "info", "debug", "warning", "error", "exception", "critical", "log", "print",
    "ValueError", "RuntimeError", "TypeError", "KeyError", "ValueError",
    "AssertionError", "OSError", "FileNotFoundError", "Exception", "Error",
}

ACCENTS = re.compile(r"[éèêàçùôîïûœÉÈÊÀÇÙÔÎÏÛŒ]")

# Words that exist in French and not in English. A word both languages share
# (source, note, date, type, version, analyse) is no evidence either way, so it
# stays out: a label identical in both languages needs no entry in the table.
FRENCH_ONLY = {
    "nom", "noms", "prénom", "statut", "état", "états", "hôte", "hôtes", "ligne",
    "lignes", "texte", "textes", "famille", "familles", "collecte", "collectes",
    "gravité", "étape", "étapes", "résumé", "résumés",
    "détail", "détails", "valeur", "valeurs", "règle", "règles", "libellé",
    "conséquence", "correction", "taille", "durée", "chemin", "empreinte",
    "langue", "thème", "police", "recherche", "colonne", "colonnes", "tri",
    "vue", "vues", "groupe", "groupes", "période", "début", "heure",
    "fichier", "fichiers", "dossier", "dossiers", "lecteur", "lecteurs",
    "sortie", "sorties", "résultat", "résultats", "signet", "signets",
    "horodatage", "poids", "incident", "incidents", "alerte", "alertes",
    "détection", "préférence", "préférences", "onglet", "onglets",
    "barre", "barres", "panneau", "panneaux", "espace", "profil", "profils",
    "dépendance", "dépendances", "éléments", "élément", "aucun", "aucune",
    "toutes", "tous", "depuis", "dans", "pour", "avec", "entre", "vers",
    "être", "avoir", "fait", "faire", "impossible", "échec", "déjà",
    "ouvert", "ouverte", "ouverts", "fermé", "fermée", "fermés", "actif",
    "attention", "voulez", "choisir", "choisissez", "importer", "exporter",
    "enregistrer", "ouvrir", "fermer", "supprimer", "ajouter", "rechercher",
    "niveau", "niveaux", "largeur", "hauteur", "couleur", "couleurs", "police",
    "précisé", "précisée", "ignoré", "ignorés", "reconnu", "reconnus", "réussi",
    "réussis", "élevée", "moyenne", "faible", "vérifier", "vérifiés", "créé",
    "créés", "modifié", "dernière", "premier", "première", "suivant", "précédent",
}
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
# Database expressions, file filters and paths are not interface text.
CODE_LIKE = re.compile(r"CASE WHEN|\bSELECT\b|\bINSERT\b|\bUPDATE\b|\bDELETE\b"
                       r"|regexp_|try_cast|::|\bFROM\b|\bWHERE\b|\*/")
FILE_LIKE = re.compile(r"\*\.[A-Za-z]|^[.\\/]|[A-Za-z]:\\")


def looks_french(text):
    """French enough to need a translation: an accent, or a French-only word."""
    text = text.strip()
    if len(text) < 2 or IDENTIFIER.match(text):
        return False
    if CODE_LIKE.search(text) or FILE_LIKE.search(text):
        return False
    if ACCENTS.search(text):
        return True
    words = re.findall(r"[a-zà-ÿ]+", text.lower())
    return any(word in FRENCH_ONLY for word in words)


def _call_name(node):
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Attribute):
            return func.attr
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Attribute):
            return func.attr
    return ""


def _text_of(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        pieces = []
        for value in node.values:
            pieces.append(value.value if isinstance(value, ast.Constant) else "{}")
        return "".join(pieces)
    return None


def strings_in(path):
    """Every French (source, surface) pair a module can display."""
    source = open(path, encoding="utf-8", errors="ignore").read()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                docstrings.add(id(body[0].value))

    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) in docstrings:
            continue
        # A literal piece of an f-string is not a label of its own: the whole
        # f-string is handled below, as a template with {} holes.
        if isinstance(node, ast.Constant) and isinstance(parents.get(node), ast.JoinedStr):
            continue
        text = _text_of(node)
        if text is None and isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            # `"Lecture du filtre : " + value` is a template with a hole.
            pieces = []
            for side in (node.left, node.right):
                piece = _text_of(side)
                pieces.append(piece if piece is not None else "{}")
            text = "".join(pieces)
        if text is None:
            continue
        text = text.strip()
        if not looks_french(text):
            continue
        # The nearest enclosing call decides what reads this string.
        current, caller, depth = node, None, 0
        while current in parents and depth < 6:
            current = parents[current]
            depth += 1
            if isinstance(current, ast.Call):
                caller = _call_name(current)
                break
        if caller in INTERNAL_CALLS:
            continue
        if caller is not None and caller not in SURFACE_CALLS:
            continue
        found.append(text)
    return found


def inventory():
    """{source text: [files]} for every French string on a surface."""
    seen = {}
    for directory, _, files in os.walk(ROOT):
        if "__pycache__" in directory:
            continue
        for name in sorted(files):
            if not name.endswith(".py") or name == "i18n.py":
                continue
            path = os.path.join(directory, name)
            relative = os.path.relpath(path, ROOT)
            for text in strings_in(path):
                seen.setdefault(text, set()).add(relative)
    return {text: sorted(files) for text, files in seen.items()}


def missing():
    """Surface strings with no English entry, templates included."""
    from fireblade.core.i18n import EN, has_english
    result = {}
    for text, files in inventory().items():
        if has_english(text):
            continue
        result[text] = files
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--missing", action="store_true", help="one untranslated string per line")
    parser.add_argument("--by-file", action="store_true", help="count per source file")
    parser.add_argument("--write-baseline", metavar="PATH", help="record what is still untranslated")
    args = parser.parse_args(argv)

    from fireblade.core.i18n import EN
    everything = inventory()
    absent = missing()

    if args.write_baseline:
        # One JSON string per line: a label may itself contain a newline.
        with open(args.write_baseline, "w", encoding="utf-8", newline="\n") as handle:
            for text in sorted(absent):
                handle.write(json.dumps(text, ensure_ascii=False) + "\n")
        print(f"{len(absent)} strings written to {args.write_baseline}")
        return 0
    if args.missing:
        print("\n".join(sorted(absent)))
        return 0
    if args.by_file:
        counts = {}
        for text, files in absent.items():
            for name in files:
                counts[name] = counts.get(name, 0) + 1
        for name, count in sorted(counts.items(), key=lambda item: -item[1]):
            print(f"{count:4d}  {name}")
        return 0

    print(f"table entries        : {len(EN)}")
    print(f"French on a surface  : {len(everything)}")
    print(f"translated           : {len(everything) - len(absent)}")
    print(f"still untranslated   : {len(absent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
