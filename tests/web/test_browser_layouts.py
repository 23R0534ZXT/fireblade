"""The layout selector: one grid per file, per artifact family, or one for everything.

Two files chosen together in the Import dialog are one collection, and the layout says how that
collection is laid out. They used to be imported one after the other, so the family and the
combined layouts gave two grids where they promise one.

Skipped without Playwright and a Chromium; never failed for lack of them.
"""

import os

import pytest
from _browser import serving  # noqa: E402

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright  # noqa: E402

from fireblade.core.investigations import InvestigationLibrary  # noqa: E402


@pytest.fixture()
def host(tmp_path):
    root = tmp_path / "cases"
    root.mkdir()
    library = InvestigationLibrary(root)
    for layout in ("files", "artifacts", "combined"):
        library.create(f"Layout {layout}", "", "windows")
    with serving(root) as base:
        yield base, tmp_path


@pytest.fixture()
def browser_page(host):
    base, _tmp = host
    try:
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(
            executable_path=os.environ.get("FIREBLADE_CHROMIUM") or None
        )
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"no Chromium available: {exc}")
    page = browser.new_page(viewport={"width": 1400, "height": 850})
    page.errors = []
    page.on("pageerror", lambda error: page.errors.append(str(error)))
    page.goto(base + "/")
    page.wait_for_selector("#menubar")
    yield page
    assert not page.errors, page.errors
    browser.close()
    playwright.stop()


@pytest.mark.parametrize(
    ("layout", "grids", "rows"),
    [("files", ["a.csv", "b.csv"], 4), ("artifacts", 1, 4), ("combined", 1, 4)],
)
def test_two_files_chosen_together_follow_the_layout(browser_page, host, layout, grids, rows):
    _base, tmp = host
    first, second = tmp / "a.csv", tmp / "b.csv"
    first.write_text("Time,Host\n2026-11-01T10:00:00Z,PC01\n2026-11-01T10:01:00Z,PC02\n")
    second.write_text("Time,Host\n2026-11-01T10:02:00Z,PC03\n2026-11-01T10:03:00Z,PC04\n")
    page = browser_page
    page.click('.tabs .tab:text-is("Cases")')
    page.dblclick(f'tr:has(td:text-is("Layout {layout}")) td >> nth=0')
    page.wait_for_function(
        f"document.getElementById('casecombo-label').innerText.includes('Layout {layout}')"
    )
    page.select_option("#import-layout", layout)
    page.click('.toolbar .tb[data-act="import-file"]')
    page.wait_for_selector("#import-modal.show")
    page.set_input_files("#preview-input", [str(first), str(second)])
    page.wait_for_function("!document.getElementById('preview-import').disabled", timeout=15000)
    page.click("#preview-import")
    page.wait_for_selector("#body tr[data-row]", timeout=60000)
    names = page.eval_on_selector_all(
        "#tree .node.child", "els => els.map(e => e.innerText.trim())"
    )
    if isinstance(grids, list):
        assert names == grids
    else:
        assert len(names) == grids, names
    # Whatever the layout, no row is lost: the footer of the first grid plus the others is 4.
    counts = page.evaluate(
        "Promise.all(state.openCase.analyses.map((a) => fetch(url(`/api/cases/${state.openCase.id}`))"
        ".then((r) => r.json()).then((c) => c.analyses.find((x) => x.index === a.index).source_info.rows)))"
    )
    assert sum(counts) == rows, counts


def test_the_layout_changes_on_the_fly_on_what_is_already_imported(browser_page, host):
    """Choosing another layout after the import lays the same rows out again, both ways."""
    _base, tmp = host
    first, second = tmp / "a.csv", tmp / "b.csv"
    first.write_text("Time,Host\n2026-11-01T10:00:00Z,PC01\n2026-11-01T10:01:00Z,PC02\n")
    second.write_text("Time,Host\n2026-11-01T10:02:00Z,PC03\n2026-11-01T10:03:00Z,PC04\n")
    page = browser_page
    page.click('.tabs .tab:text-is("Cases")')
    page.dblclick('tr:has(td:text-is("Layout artifacts")) td >> nth=0')
    page.wait_for_function(
        "document.getElementById('casecombo-label').innerText.includes('Layout artifacts')"
    )
    page.select_option("#import-layout", "artifacts")
    page.click('.toolbar .tb[data-act="import-file"]')
    page.wait_for_selector("#import-modal.show")
    page.set_input_files("#preview-input", [str(first), str(second)])
    page.wait_for_function("!document.getElementById('preview-import').disabled", timeout=15000)
    page.click("#preview-import")
    page.wait_for_selector("#body tr[data-row]", timeout=60000)

    def grids():
        return page.eval_on_selector_all(
            "#tree .node.child", "els => els.map(e => e.innerText.trim())"
        )

    assert len(grids()) == 1, grids()
    for layout, expected in (("files", 2), ("combined", 1), ("artifacts", 1), ("files", 2)):
        page.select_option("#import-layout", layout)
        page.wait_for_function(
            "document.getElementById('status').innerText.match(/Layout changed|Already laid out/)",
            timeout=60000,
        )
        page.wait_for_selector("#body tr[data-row]", timeout=60000)
        assert len(grids()) == expected, (layout, grids())
        total = page.evaluate(
            "fetch(url(`/api/cases/${state.openCase.id}`)).then((r) => r.json())"
            ".then((c) => c.analyses.reduce((n, a) => n + a.source_info.rows, 0))"
        )
        assert total == 4, (layout, total)
