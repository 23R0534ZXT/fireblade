"""Optional V8 coverage of the Host client, collected over the browser tests.

``FIREBLADE_JS_COVERAGE=<folder>`` makes every page a browser test opens record which parts of
the client's scripts ran; each page writes one JSON file when its browser closes. The files are
merged and read by ``scripts/audit/js_coverage.py``, which lists the functions no test ever ran.
Without the variable nothing changes.

The same pages also keep the list of controls the test touched (a click, a change, a key, a
right click): ``scripts/audit/controls.py`` compares it with every control the client offers.
"""

import json
import os
import uuid
from pathlib import Path

import httpx
import pytest

FOLDER = os.environ.get("FIREBLADE_JS_COVERAGE")

# The control an event reached: its nearest interactive ancestor, named by tag and by id, by
# data-act (or another data- name) or by its first class. Same naming as the audit's inventory.
TRACK = r"""
(() => {
  if (window.__fbTouched) return;
  // A reload must not forget what was already touched in this tab.
  let stored = [];
  try { stored = JSON.parse(sessionStorage.getItem("__fbTouched") || "[]"); } catch (_) { /* no storage */ }
  const touched = (window.__fbTouched = new Set(stored));
  const interactive = (n) => n.matches &&
    n.matches("button, a, input, select, textarea, summary, [role=button], [data-act], [data-menu], [data-tab], [data-sub]");
  const key = (el) => {
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      if (!interactive(n)) continue;
      const tag = n.tagName.toLowerCase();
      if (n.id) return tag + "#" + n.id;
      for (const name of ["data-act", "data-menu", "data-tab", "data-sub"]) {
        if (n.hasAttribute(name)) return tag + "[" + name + "=" + n.getAttribute(name) + "]";
      }
      const extra = n.getAttributeNames().find((a) => a.startsWith("data-"));
      if (extra) return tag + "[" + extra + "]";
      return tag + "." + (n.className || "").toString().split(" ")[0];
    }
    return null;
  };
  window.__fbKey = key;
  for (const type of ["click", "dblclick", "change", "input", "keydown", "contextmenu", "mousedown"]) {
    document.addEventListener(type, (event) => {
      const k = key(event.target);
      if (k && !touched.has(k)) {
        touched.add(k);
        try { sessionStorage.setItem("__fbTouched", JSON.stringify([...touched])); } catch (_) { /* no storage */ }
      }
    }, true);
  }
})();
"""

if FOLDER:
    try:
        from playwright.sync_api import Browser, BrowserContext
    except ImportError:  # no Playwright here: the browser tests are skipped anyway
        Browser = BrowserContext = None

    _recording: list = []

    def _record(page):
        """Start V8's precise block coverage on the page (Playwright for Python has no wrapper)."""
        try:
            page.add_init_script(TRACK)
            session = page.context.new_cdp_session(page)
            session.send("Profiler.enable")
            session.send("Profiler.startPreciseCoverage", {"callCount": True, "detailed": True})
            _recording.append((page, session))
        except Exception:  # noqa: BLE001 - coverage is a measure, never a reason to fail a test
            pass

    def _dump_all():
        out = Path(FOLDER)
        out.mkdir(parents=True, exist_ok=True)
        while _recording:
            page, session = _recording.pop()
            try:
                touched = page.evaluate("[...(window.__fbTouched || [])]")
            except Exception:  # noqa: BLE001 - a page that is closed or still loading
                touched = []
            try:
                entries = session.send("Profiler.takePreciseCoverage")["result"]
            except Exception:  # noqa: BLE001 - the page is already gone
                continue
            kept = [
                {"url": entry["url"], "functions": entry["functions"]}
                for entry in entries
                if "/static/" in entry["url"]
            ]
            if kept or touched:
                document = {"scripts": kept, "touched": touched}
                (out / f"{uuid.uuid4().hex}.json").write_text(
                    json.dumps(document), encoding="utf-8"
                )

    if Browser is not None:
        _new_page = Browser.new_page
        _browser_close = Browser.close
        _context_new_page = BrowserContext.new_page
        _context_close = BrowserContext.close

        def new_page(self, *args, **kwargs):
            page = _new_page(self, *args, **kwargs)
            _record(page)
            return page

        def context_new_page(self, *args, **kwargs):
            page = _context_new_page(self, *args, **kwargs)
            _record(page)
            return page

        def browser_close(self, *args, **kwargs):
            _dump_all()
            return _browser_close(self, *args, **kwargs)

        def context_close(self, *args, **kwargs):
            _dump_all()
            return _context_close(self, *args, **kwargs)

        Browser.new_page = new_page
        BrowserContext.new_page = context_new_page
        Browser.close = browser_close
        BrowserContext.close = context_close


# -- The fixtures every browser test of the audit shares -------------------------------------------


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    """A Host over an empty cases folder, for the length of a module: (url, cases, evidence)."""
    from _browser import serving

    root = tmp_path_factory.mktemp("audit-cases")
    with serving(root) as base:
        yield base, root, tmp_path_factory.mktemp("audit-evidence")


def make_case(server, name, csv_text=None, organization="files"):
    """A case in the server's library, holding ``events.csv`` imported when ``csv_text`` is given."""
    from fireblade.core.investigations import InvestigationLibrary

    base, root, evidence = server
    identifier = InvestigationLibrary(root).create(name, "", "windows")["id"]
    (evidence / identifier).mkdir()
    if csv_text is not None:
        source = evidence / identifier / "events.csv"
        source.write_text(csv_text)
        started = httpx.post(
            f"{base}/api/cases/{identifier}/import-jobs",
            data={"source": str(source), "organization": organization},
            timeout=30,
        )
        assert started.status_code == 200, started.text
        job = started.json()["job"]
        for _ in range(240):
            state = httpx.get(f"{base}/api/import-jobs/{job}").json()
            if state.get("status") not in ("running", "pending", "queued"):
                break
        assert state.get("status") == "complete", state
    return identifier


@pytest.fixture()
def page(server, request):
    """A fresh case of sixty rows for every test, open on its Analyses tab.

    The view an analyst leaves behind (sorts, hidden columns, filters) is saved with the case, and
    one command's effect must not become the next one's.
    """
    from _audit import standard_csv
    from _browser import browser_page

    name = "Audit " + request.node.name[:44]
    make_case(server, name, standard_csv())
    with browser_page(server[0], name) as opened:
        opened.context.grant_permissions(["clipboard-read", "clipboard-write"])
        yield opened


@pytest.fixture()
def empty_page(server, request):
    """A fresh case with nothing imported yet, open on its Analyses tab."""
    from _browser import browser_page

    name = "Empty " + request.node.name[:44]
    make_case(server, name)
    with browser_page(server[0], name, wait_rows=False) as opened:
        opened.context.grant_permissions(["clipboard-read", "clipboard-write"])
        yield opened
