"""The Host client carries the surfaces HOST-PARITY.md claims.

A parity claim is only as good as the thing it points at: these tests read the
client files and fail when a menu entry exists without its handler, or when a
handler exists without its entry. They are the cheap half of the proof; the
browser pass is the other half.
"""
from pathlib import Path

WEB = Path(__file__).resolve().parents[2] / "src" / "fireblade" / "web"
APP = WEB / "static" / "app.js"
INDEX = WEB / "static" / "index.html"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_the_row_menu_offers_every_cell_action():
    """One entry in the menu, one handler in the switch, for each action."""
    js, html = _read(APP), _read(INDEX)
    actions = ("cell-json", "copy-value", "copy-row", "filter-value", "exclude-value",
               "sort-asc", "sort-desc", "group-by-column", "pin-column", "hide-column",
               "bookmark-row", "unmark-selection", "rule-from-cell", "pivot")
    for action in actions:
        assert f'data-act="{action}"' in html, f"no menu entry for {action}"
        assert f'case "{action}":' in js, f"no handler for {action}"


def test_the_import_dialog_offers_the_csv_options():
    """The desktop offers a separator and an encoding; so does the Host."""
    js, html = _read(APP), _read(INDEX)
    assert 'id="preview-delimiter"' in html
    assert 'id="preview-encoding"' in html
    for name in ("fillCsvOptions", "csvOptions", "refreshPreviews"):
        assert f"function {name}(" in js, name
    # The choice must reach the service on both preview routes and on the import.
    assert 'body.append("delimiter"' in js and 'body.append("encoding"' in js
    # previewFiles, previewServerPath, refreshPreviews and confirmImport all read them.
    assert js.count("csvOptions()") >= 3


def test_the_grid_selects_a_range_and_a_selection():
    js = _read(APP)
    assert "function selectRow(" in js
    assert "event.shiftKey" in js and "event.ctrlKey" in js
    assert "function selectedIds(" in js
    assert "function markSelection(" in js
    # A mark is a note: the import must not invent a bookmark without one.
    assert "postBookmark(" in js


def test_the_filter_input_keeps_the_operator():
    """A value filtered with "=" must not silently become "contains"."""
    js = _read(APP)
    assert "function filterPrefix(" in js
    assert 'eq: "= "' in js and 'ne: "!= "' in js
