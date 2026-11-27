"""Keep generic configuration shapes out of the main forensic navigation."""

import json


def test_wide_configuration_documents_are_named_and_collapsed_behind_the_artifacts(
    empty_page, server
):
    page = empty_page
    folder = server[2] / "configuration-heavy-collection"
    folder.mkdir()
    (folder / "events.csv").write_text(
        "Time,Host\n2026-11-01T12:00:00Z,PC01\n2026-11-02T12:00:00Z,PC02\n"
    )
    for prefix in ["alpha", "beta"]:
        (folder / f"config-{prefix}.json").write_text(
            json.dumps({f"{prefix}_setting_{i}": i for i in range(1600)})
        )
    page.select_option("#import-layout", "artifacts")
    page.click('.toolbar [data-act="import-file"]')
    page.fill("#preview-server", str(folder))
    page.click('[data-act="preview-path"]')
    page.wait_for_selector("#preview-body .preview-card")
    page.click("#preview-import")
    page.wait_for_function("state.openCase.analyses.length === 3", timeout=60000)
    children = page.locator("#tree .node.child")
    assert children.count() == 1
    assert children.first.inner_text().strip() == "Exports CSV"
    support = page.locator("#tree .node.grp", has_text="Supporting files (2)")
    assert support.get_attribute("aria-expanded") == "false"
    assert page.locator("#tree .node.grp", has_text="Exports CSV").count() == 0
    support.click()
    assert children.count() == 3
    names = children.all_inner_texts()
    assert any("config-alpha.json" in name for name in names)
    assert any("config-beta.json" in name for name in names)
    assert not any("setting_" in name for name in names)
    support.click()
    page.fill("#tree-search", "config-beta.json")
    assert children.count() == 1
    assert "config-beta.json" in children.first.inner_text()
    children.first.click()
    page.wait_for_function("document.getElementById('pageinfo').innerText.includes('/ 1 row')")
    page.fill("#tree-search", "")
    assert children.count() == 1  # searching did not change the analyst's collapsed state
    page.click("#tree-expand")
    assert children.count() == 3
    page.select_option("#tree-mode", "flat")
    assert children.count() == 3
    assert page.locator("#tree .node.grp").count() == 1
    page.select_option("#tree-mode", "families")
    assert children.count() == 3
