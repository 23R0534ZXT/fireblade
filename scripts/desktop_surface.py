"""Exhaustive inventory of the desktop's user-reachable surface.

The parity inventory (`scripts/parity_inventory.py`) reads `addAction`/`addMenu`
calls with literal labels. That misses `QAction('…')` constructors, buttons,
dialog titles and shortcuts, so the count it gives is a floor, not the surface.
This one walks every Qt widget call with a literal, plus menus, tabs, actions
and window titles, so nothing reachable is left out of the audit.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from collections import Counter
from pathlib import Path

ACTION_CALLS = {"addAction", "addMenu", "addTab", "addItem", "insertAction", "insertMenu"}
BUTTON_CALLS = {"QPushButton", "QToolButton", "QCheckBox", "QRadioButton", "QCommandLinkButton"}
TITLE_CALLS = {"setWindowTitle"}
# A label that only decorates is not a feature: these are captions and chrome.
SKIP = {
    "text",
    "number",
    "timestamp",
    "value",
    "year",
    "month",
    "day",
    "OK",
    "Cancel",
    "Annuler",
    "Valider",
    "Fermer",
    "Close",
    "Ouvrir",
    "Open",
    "Enregistrer",
    "Save",
}


def literals(node: ast.AST) -> list[str]:
    found = []
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            text = child.value.strip()
            if 2 <= len(text) <= 160:
                found.append(text)
        elif isinstance(child, ast.Call) and getattr(child.func, "id", "") == "translate":
            if (
                child.args
                and isinstance(child.args[0], ast.Constant)
                and isinstance(child.args[0].value, str)
            ):
                found.append(child.args[0].value.strip())
    return found


def collect(paths: list[Path]) -> dict:
    surface = {"action": {}, "button": {}, "dialog": {}, "shortcut": {}, "tab": {}}
    for path in paths:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "attr", "") or getattr(node.func, "id", "")
            if name in ACTION_CALLS:
                kind = "tab" if name == "addTab" else "action"
            elif name in BUTTON_CALLS:
                kind = "button"
            elif name in TITLE_CALLS:
                kind = "dialog"
            elif name in ("setShortcut", "QShortcut", "setShortcutContext"):
                kind = "shortcut"
            elif name == "QAction":
                kind = "action"
            else:
                continue
            for label in literals(node):
                if not re.search(r"[A-Za-zÀ-ÿ]", label):
                    continue
                if label.lower() in {item.lower() for item in SKIP}:
                    continue
                surface[kind].setdefault(label, set()).add(path.name)
    return {
        kind: {label: sorted(files) for label, files in sorted(entries.items())}
        for kind, entries in surface.items()
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", type=Path, default=Path("src/fireblade/ui"))
    parser.add_argument("--out", type=Path, default=Path("/tmp/desktop_surface.json"))
    args = parser.parse_args(argv)
    surface = collect(sorted(args.src.glob("*.py")))
    args.out.write_text(json.dumps(surface, ensure_ascii=False, indent=1), encoding="utf-8")
    counts = {kind: len(entries) for kind, entries in surface.items()}
    total = len({label for entries in surface.values() for label in entries})
    print("per kind:", counts)
    print("distinct labels:", total, "-> ", args.out)
    per_file = Counter(
        name for entries in surface.values() for files in entries.values() for name in files
    )
    print(
        "declared in:", ", ".join(f"{name} ({count})" for name, count in per_file.most_common(15))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
