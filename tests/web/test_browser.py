"""The Host client, driven by a real browser and a real mouse.

The contract tests read app.js as text and call the API directly, which is how a menu that
no mouse could ever operate shipped: the item's click handler worked when a script called
it, and never when a hand pressed it. These tests press.

They need Playwright and its Chromium; without them the file is skipped, never failed.
"""

import httpx
import pytest
from _browser import browser_page, serving  # noqa: E402

from fireblade.core.investigations import InvestigationLibrary


@pytest.fixture(scope="module")
def host(tmp_path_factory):
    root = tmp_path_factory.mktemp("browser-cases")
    InvestigationLibrary(root).create("Browser case", "driven by a test", "windows")
    with serving(root) as base:
        identifier = httpx.get(f"{base}/api/cases").json()["cases"][0]["id"]
        csv_text = "Time,Host,User,Event\n2026-11-01T10:00:00Z,PC01,alice,4624\n2026-11-01T10:05:00Z,PC01,bob,4625\n"
        sent = httpx.post(
            f"{base}/api/cases/{identifier}/upload",
            params={"organization": "files"},
            files={"file": ("events.csv", csv_text.encode(), "text/csv")},
        )
        assert sent.status_code == 200, sent.text
        yield base


@pytest.fixture()
def page(host):
    with browser_page(host, "Browser case") as opened:
        yield opened


def _press(page, selector):
    """Mouse down and mouse up on the element: what a hand does, not element.click()."""
    box = page.locator(selector).first.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.mouse.up()


def test_a_menu_command_runs_when_it_is_pressed_with_the_mouse(page):
    _press(page, '.menubar .m[data-menu="view"]')
    assert page.locator(".menu.show").count() == 1
    _press(page, '.menu.show [data-act="messages"]')
    page.wait_for_selector("#messages-modal.show")
    assert page.locator(".menu.show").count() == 0, "the menu closes once its command ran"


def test_every_menu_opens_and_lists_its_commands(page):
    names = page.eval_on_selector_all(".menubar .m", "els => els.map(e => e.dataset.menu)")
    assert len(names) >= 8
    for name in names:
        _press(page, f'.menubar .m[data-menu="{name}"]')
        assert page.locator(f'.menu[data-for="{name}"].show [data-act]').count() > 0, name
        page.mouse.click(700, 500)
        assert page.locator(".menu.show").count() == 0, name


def test_narrow_menus_fit_the_window_and_are_operable_by_keyboard(page):
    page.set_viewport_size({"width": 390, "height": 640})
    trigger = page.get_by_role("button", name="Exporter", exact=True)
    trigger.focus()
    page.keyboard.press("Enter")
    popup = page.locator('.menu[data-for="exporter"]')
    popup.wait_for()
    bounds = popup.bounding_box()
    assert 0 <= bounds["x"] and bounds["x"] + bounds["width"] <= 391
    assert trigger.get_attribute("aria-expanded") == "true"
    assert popup.locator(":focus").count() == 1
    page.keyboard.press("Escape")
    assert popup.is_hidden()
    assert trigger.evaluate("el => el === document.activeElement")
    assert trigger.get_attribute("aria-expanded") == "false"


def test_narrow_workspaces_keep_their_controls_and_artifact_drawer(page):
    page.set_viewport_size({"width": 390, "height": 760})
    drawer = page.locator("#artifacts")
    toggle = page.get_by_role("button", name="Artifacts", exact=True)
    drawer.wait_for(state="hidden")
    toggle.click()
    assert drawer.is_visible()
    close = drawer.get_by_role("button", name="Close artifacts panel")
    close.click()
    assert drawer.is_hidden()

    page.locator('[data-tab="cases"]').click()
    assert drawer.is_hidden()
    page.locator('[data-tab="timeline"]').click()
    for selector in ("#timeline-build", "#timeline-export", '[data-act="tl-isolate"]'):
        bounds = page.locator(selector).bounding_box()
        assert 0 <= bounds["x"] and bounds["x"] + bounds["width"] <= 391
    page.locator('[data-tab="analyses"]').click()
    assert drawer.is_hidden()


def test_the_last_workspace_tab_is_reachable_in_a_narrow_window(page):
    page.set_viewport_size({"width": 680, "height": 580})
    strip = page.locator("#doctabs")
    tabs = strip.locator("[data-tab]")
    assert strip.evaluate("(el) => el.scrollWidth > el.clientWidth")
    tabs.first.focus()
    for _ in range(tabs.count() - 1):
        page.keyboard.press("Tab")
    graph_tab = tabs.last
    assert graph_tab.evaluate("(el) => el === document.activeElement")
    box = graph_tab.bounding_box()
    assert 0 <= box["x"] and box["x"] + box["width"] <= 680
    page.keyboard.press("Enter")
    graph = page.locator("#graph-view")
    assert graph.is_visible()
    export = graph.get_by_role("button", name="Export PNG")
    export_box = export.bounding_box()
    graph_box = graph.bounding_box()
    assert export_box["x"] + export_box["width"] <= graph_box["x"] + graph_box["width"]
    export.click(trial=True)


def test_workspace_zoom_keeps_the_status_and_uses_the_available_width(page):
    page.set_viewport_size({"width": 850, "height": 700})
    page.locator('.toolbar [data-act="display-settings"]').click()
    page.locator("#scale").select_option("1.75")
    page.locator('#settings-modal [data-act="settings-close"]').click()
    status = page.locator(".statusbar").bounding_box()
    assert abs(status["y"] + status["height"] - 700) < 2
    assert page.locator("#artifacts").is_hidden()
    trigger = page.get_by_role("button", name="Exporter", exact=True)
    trigger.focus()
    page.keyboard.press("Enter")
    bounds = page.locator('.menu[data-for="exporter"]').bounding_box()
    assert 0 <= bounds["x"] and bounds["x"] + bounds["width"] <= 851
    assert 0 <= bounds["y"] and bounds["y"] + bounds["height"] <= 701


def test_a_narrow_toolbar_keeps_case_controls_and_the_view_menu_keeps_workspace(page):
    page.set_viewport_size({"width": 680, "height": 580})
    toolbar = page.locator(".toolbar")
    assert toolbar.evaluate("el => el.scrollWidth === el.clientWidth")
    for control in ("#import-layout", "#casecombo", '[data-act="close-case"]'):
        assert toolbar.locator(control).is_visible()
    assert toolbar.locator('[data-act="display-settings"]').is_hidden()
    page.locator('#groupbar [data-act="open-view-menu"]').click()
    page.locator('.menu.show [data-act="display-settings"]').click()
    assert page.locator("#settings-modal").is_visible()


def test_the_case_indicator_opens_the_case_list_by_keyboard(page):
    button = page.get_by_role("button", name="Open case list")
    button.focus()
    page.keyboard.press("Enter")
    assert page.locator("#cases-view").is_visible()
    assert page.locator("#cases-body").get_by_text("Browser case", exact=True).is_visible()


def test_row_details_scroll_without_covering_cell_note_buttons(page):
    page.locator("#body tr[data-row] td[data-cell]").first.click()
    fields = page.locator(".detail-fields")
    editor = page.get_by_role("textbox", name="Bookmark note")
    assert editor.is_visible()
    last_note = fields.get_by_role("button", name="Add note for Event")
    last_note.click()
    assert page.locator("#ask-modal").is_visible()
    assert editor.is_visible()


def test_a_dialog_is_moved_by_its_title_and_resized_from_its_corner(page):
    page.evaluate("document.getElementById('settings-modal').classList.add('show')")
    dialog = page.locator("#settings-modal .dialog")
    page.wait_for_function("document.querySelector('#settings-modal .dialog').dataset.free === '1'")
    start = dialog.bounding_box()
    title = page.locator("#settings-modal .dialog h3").bounding_box()
    page.mouse.move(title["x"] + 20, title["y"] + 8)
    page.mouse.down()
    page.mouse.move(title["x"] - 160, title["y"] + 90, steps=5)
    page.mouse.up()
    moved = dialog.bounding_box()
    assert moved["x"] < start["x"] - 100 and moved["y"] > start["y"] + 60
    page.mouse.move(moved["x"] + moved["width"] - 4, moved["y"] + moved["height"] - 4)
    page.mouse.down()
    page.mouse.move(moved["x"] + moved["width"] + 90, moved["y"] + moved["height"] + 60, steps=5)
    page.mouse.up()
    resized = dialog.bounding_box()
    assert resized["width"] > moved["width"] + 50 and resized["height"] > moved["height"] + 30


def test_the_splitters_resize_the_tree_and_the_details_and_reset_on_double_click(page):
    tree = page.locator("#artifacts")
    before = tree.bounding_box()["width"]
    bar = page.locator(".splitter.vsplit").bounding_box()
    page.mouse.move(bar["x"] + 2, bar["y"] + 150)
    page.mouse.down()
    page.mouse.move(bar["x"] - 140, bar["y"] + 150, steps=5)
    page.mouse.up()
    assert tree.bounding_box()["width"] > before + 100
    page.locator(".splitter.vsplit").dblclick()
    assert abs(tree.bounding_box()["width"] - before) < 2


def test_splitters_follow_the_tree_on_the_left_and_details_above_the_grid(page):
    page.evaluate(
        "copyPrefs.tree = 'left'; applyTreePosition(); "
        "copyPrefs.details = 'top'; applyDetailsPosition()"
    )
    tree = page.locator("#artifacts")
    details = page.locator("#details")
    bar = page.locator(".splitter.vsplit").bounding_box()
    row_bar = page.locator(".splitter.hsplit").bounding_box()
    grid = page.locator("#analysis-view > .gridwrap").bounding_box()
    tree_bounds = tree.bounding_box()
    details_bounds = details.bounding_box()
    assert tree_bounds["x"] + tree_bounds["width"] <= bar["x"] < grid["x"]
    assert details_bounds["y"] + details_bounds["height"] <= row_bar["y"] < grid["y"]
    page.mouse.move(bar["x"] + 2, bar["y"] + 100)
    page.mouse.down()
    page.mouse.move(bar["x"] + 42, bar["y"] + 100, steps=5)
    page.mouse.up()
    assert tree.bounding_box()["width"] > tree_bounds["width"] + 30
    page.mouse.move(row_bar["x"] + 300, row_bar["y"] + 2)
    page.mouse.down()
    page.mouse.move(row_bar["x"] + 300, row_bar["y"] + 42, steps=5)
    page.mouse.up()
    assert details.bounding_box()["height"] > details_bounds["height"] + 30


def test_every_dialog_a_menu_opens_keeps_its_buttons_on_screen(page):
    """A dialog that fills in after it opens must not slide its buttons below the page.

    Every command of every menu is run; whichever dialog it opens, each of its visible
    buttons has to lie inside the viewport (or inside the dialog's own scrolling body).
    """
    page.set_viewport_size({"width": 1400, "height": 760})
    menus = page.eval_on_selector_all(".menubar .m", "els => els.map(e => e.dataset.menu)")
    seen = set()
    for name in menus:
        count = page.locator(f'.menu[data-for="{name}"] [data-act]').count()
        for position in range(count):
            _press(page, f'.menubar .m[data-menu="{name}"]')
            item = page.locator(".menu.show [data-act]").nth(position)
            label = item.inner_text().strip()
            if any(word in label for word in ("Erase", "Close the case")):
                page.mouse.click(700, 500)
                continue
            action = item.get_attribute("data-act")
            item.click()
            page.wait_for_timeout(350)
            geometry = page.locator(".modal.show .dialog").evaluate_all(
                """dialogs => {
                  if (dialogs.length !== 1) return null;
                  const dialog = dialogs[0];
                  const bounds = dialog.getBoundingClientRect();
                  return {
                    top: bounds.top, bottom: bounds.bottom,
                    buttons: [...dialog.querySelectorAll(".foot button, button.close")]
                      .filter(button => button.getClientRects().length && getComputedStyle(button).visibility !== "hidden")
                      .map(button => [button.innerText, button.getBoundingClientRect().bottom])
                  };
                }"""
            )
            if geometry is not None and action not in seen:
                seen.add(action)
                assert geometry["top"] >= 0 and geometry["bottom"] <= 761, (label, geometry)
                for text, bottom in geometry["buttons"]:
                    assert bottom <= 761, (label, text)
            page.evaluate(
                "document.querySelectorAll('.modal.show').forEach(m => m.classList.remove('show'))"
            )
    assert len(seen) >= 25, "too few dialogs were reached: " + ", ".join(sorted(seen))


def test_every_shortcut_a_menu_announces_is_wired(page):
    """A hint that does nothing is a lie: each announced combination opens what it says."""
    hints = page.eval_on_selector_all(
        ".menu .item .key",
        "els => els.map(e => [e.closest('.item').dataset.act, e.textContent.trim()])",
    )
    announced = {act: keys for act, keys in hints}
    # What each combination opens, by the command it is announced beside.
    expected = {
        "import-file": ("Control+o", "#import-modal.show"),
        "import-folder": ("Control+Shift+I", None),  # opens the browser's own folder chooser
        "global-search": ("Control+f", "#search-modal.show"),
        "palette": ("Control+k", "#palette-modal.show"),
        "help-guide": ("F1", "#help-modal.show"),
    }
    for act, (combination, result) in expected.items():
        assert act in announced, f"{act} no longer announces its shortcut"
        if result is None:
            with page.expect_file_chooser(timeout=5000):
                page.keyboard.press(combination)
            continue
        page.keyboard.press(combination)
        page.wait_for_selector(result, timeout=5000)
        page.keyboard.press("Escape")
        page.wait_for_selector(".modal.show", state="detached", timeout=5000)
    # Nothing is announced that no handler owns.
    assert set(announced) <= set(expected) | {
        "export-csv",
        "copy-row",
        "mark-selection",
        "case-save",
    }, announced


def test_no_menu_offers_the_same_command_twice_or_under_two_names(page):
    for name in page.eval_on_selector_all(".menubar .m", "els => els.map(e => e.dataset.menu)"):
        items = page.eval_on_selector_all(
            f'.menu[data-for="{name}"] .item',
            "els => els.map(e => [e.dataset.act, e.textContent.replace(/Ctrl.*$/, '').trim()])",
        )
        acts = [act for act, _ in items]
        assert len(acts) == len(set(acts)), (name, [a for a in acts if acts.count(a) > 1])
        labels = [label for _, label in items]
        assert len(labels) == len(set(labels)), (name, labels)


def test_analysis_menu_detection_rules_opens_the_detection_rules_not_the_colour_rules(page):
    box = page.locator('.menubar .m[data-menu="analysis"]').bounding_box()
    page.mouse.move(box["x"] + 5, box["y"] + 5)
    page.mouse.down()
    page.mouse.up()
    item = page.locator('.menu.show [data-act="detrules-open"]').bounding_box()
    page.mouse.move(item["x"] + 8, item["y"] + 5)
    page.mouse.down()
    page.mouse.up()
    page.wait_for_selector("#detrules-modal.show", timeout=10000)
    assert page.locator("#rules-modal.show").count() == 0, "not the colour-rule editor"
