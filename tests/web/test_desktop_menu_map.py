"""Every command of the desktop's menus has its place in the Host, or a reason it has none.

`docs/host/desktop-menu-map.json` lists the 126 commands the desktop window's menus hold (read from
the real window) against the Host's page. The first test checks the page: every mapped command exists
and is wired. The second one (with Qt) checks the map against the desktop itself, so a command added
to the desktop cannot slip by unmapped.
"""

import json
import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MAP = json.loads((ROOT / "docs/host/desktop-menu-map.json").read_text(encoding="utf-8"))["commands"]
STATIC = ROOT / "src/fireblade/web/static"


def test_every_mapped_command_exists_on_the_page_and_is_wired():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    script = (STATIC / "app.js").read_text(encoding="utf-8")
    acts = set(re.findall(r'data-act="([^"]+)"', html))
    ids = set(re.findall(r'id="([^"]+)"', html))
    missing = []
    for command, where in MAP.items():
        if "na" in where:
            assert len(where["na"]) > 20, (command, "give the reason")
        elif "act" in where:
            if where["act"] not in acts or f'case "{where["act"]}"' not in script:
                missing.append((command, where))
        elif "id" in where:
            if where["id"] not in ids and not where.get("dynamic"):
                missing.append((command, where))
        else:
            missing.append((command, where))
    assert not missing, missing


def test_what_the_host_cannot_do_is_only_what_a_browser_or_the_image_cannot():
    reasons = [where["na"] for where in MAP.values() if "na" in where]
    assert len(reasons) <= 30
    for reason in reasons:
        assert any(
            word in reason
            for word in ("browser", ".NET", "queue", "rule book", "panel", "layout", "splash")
        ), reason


DUMP = r"""
import json, os, re, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
app = QApplication([])
from fireblade.core.i18n import english
from fireblade.ui.app import Window
window = Window()
commands = []
def walk(menu, path):
    for action in menu.actions():
        if action.isSeparator():
            continue
        text = english(action.text().replace("&", ""))
        if action.menu():
            walk(action.menu(), path + [text])
        else:
            commands.append(" > ".join(path + [text]))
for action in window.menuBar().actions():
    if action.menu():
        walk(action.menu(), [english(action.text().replace("&", ""))])
print(json.dumps(commands))
"""


def test_the_map_lists_exactly_the_commands_of_the_desktop_window():
    """Read from the real window in a process of its own (the language state of this one is not its)."""
    pytest.importorskip("PySide6")
    import subprocess
    import sys

    done = subprocess.run(
        [sys.executable, "-c", DUMP],
        capture_output=True,
        text=True,
        timeout=120,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
    )
    assert done.returncode == 0, done.stderr[-400:]
    commands = json.loads(done.stdout.strip().splitlines()[-1])
    # The menus' names and some labels are spelled in the window's language; the number of commands of
    # each menu is not: a command added to or removed from the desktop changes one of these counts.
    import unicodedata

    def menu_of(command):
        head = command.partition(" > ")[0]
        head = unicodedata.normalize("NFKD", head).encode("ascii", "ignore").decode().casefold()
        return {
            "affichage": "view",
            "fichier": "case",
            "analyse": "analysis",
            "edition": "edit",
            "filtres": "filters",
            "export": "exporter",
            "aide": "help",
        }.get(head, head)

    def counts(items):
        found = {}
        for item in items:
            found[menu_of(item)] = found.get(menu_of(item), 0) + 1
        return found

    assert len(commands) == len(MAP), (len(commands), len(MAP))
    assert counts(commands) == counts(MAP), (counts(commands), counts(MAP))
