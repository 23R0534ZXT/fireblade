"""Every control the Host client offers, and which of them the tests ever touched.

The browser tests, run with ``FIREBLADE_JS_COVERAGE=<folder>``, record each control an event
reached (see ``tests/web/conftest.py``). This script opens the client, lists every control in it
(buttons, links, fields, menu entries, tabs, toolbar commands) with the same naming, and prints the
ones nothing touched, grouped by the window or the tab they belong to::

    python -m scripts.audit.controls <folder>

The list is taken from the live page, so it holds what a person could press, not what the source
mentions. Controls a script creates later (rows, chips, rule lines) are covered by the JavaScript
coverage instead (``scripts/audit/js_coverage.py``).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SELECTOR = (
    "button, a, input, select, textarea, summary, [role=button], "
    "[data-act], [data-menu], [data-tab], [data-sub]"
)

AREA = r"""
(selector) => {
  const key = window.__fbKey;
  const area = (el) => {
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      if (n.id && /-modal$/.test(n.id)) return "window: " + n.id.replace(/-modal$/, "");
      if (n.id && /-view$/.test(n.id)) return "tab: " + n.id.replace(/-view$/, "");
      if (n.classList && n.classList.contains("menu")) return "menu: " + (n.dataset.for || "");
      if (n.classList && n.classList.contains("menubar")) return "menu bar";
      if (n.classList && n.classList.contains("toolbar")) return "toolbar";
      if (n.classList && n.classList.contains("tabs")) return "tabs";
      if (n.id === "row-menu") return "cell menu";
      if (n.id === "artifacts") return "artifact tree";
      if (n.id === "update-band") return "update band";
    }
    return "page";
  };
  const seen = new Map();
  for (const el of document.querySelectorAll(selector)) {
    const k = key(el);
    if (k && !seen.has(k)) seen.set(k, area(el));
  }
  return [...seen.entries()];
}
"""


def _tracking_script() -> str:
    spec = importlib.util.spec_from_file_location("fb_web_conftest", ROOT / "tests/web/conftest.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.TRACK


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def inventory() -> dict[str, str]:
    """The controls of the page, by name, each with the window or tab that holds it."""
    import uvicorn
    from playwright.sync_api import sync_playwright

    from fireblade.core.investigations import InvestigationLibrary
    from fireblade.web.server import create_app

    root = Path(tempfile.mkdtemp(prefix="fb-controls-"))
    InvestigationLibrary(root).create("Inventory", "", "windows")
    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(create_app(root), host="127.0.0.1", port=port, log_level="warning")
    )
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.05)
    found: dict[str, str] = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get("FIREBLADE_CHROMIUM") or None
        )
        page = browser.new_page(viewport={"width": 1500, "height": 900})
        page.add_init_script(_tracking_script())
        page.goto(f"http://127.0.0.1:{port}/")
        page.wait_for_selector("#menubar")
        page.wait_for_timeout(800)
        for key, area in page.evaluate(AREA, SELECTOR):
            found.setdefault(key, area)
        browser.close()
    server.should_exit = True
    return found


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("folder", help="the FIREBLADE_JS_COVERAGE folder")
    args = parser.parse_args(argv)
    sys.path.insert(0, str(ROOT / "src"))
    touched: set[str] = set()
    for path in sorted(Path(args.folder).glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(document, dict):
            touched.update(document.get("touched", []))
    everything = inventory()
    missing = {key: area for key, area in everything.items() if key not in touched}
    print(f"{len(everything) - len(missing)}/{len(everything)} controls of the page were touched")
    by_area: dict[str, list[str]] = {}
    for key, area in sorted(missing.items()):
        by_area.setdefault(area, []).append(key)
    for area, keys in sorted(by_area.items()):
        print(f"\n{area} — {len(keys)} untouched")
        for key in keys:
            print(f"  {key}")
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
