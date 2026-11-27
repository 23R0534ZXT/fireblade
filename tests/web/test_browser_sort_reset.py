"""Removing all sort keys must restore the evidence order."""

from _audit import column_values, command


def test_removing_every_sort_key_restores_source_order(page):
    page.click('#head tr:first-child th:text-is("User")')
    page.wait_for_function("document.querySelectorAll('#body tr[data-row]').length === 60")
    command(page, "sort-priority")
    while page.locator("[data-sort-remove]").count():
        page.locator("[data-sort-remove]").first.click()
    page.select_option("#sort-header-type", "text")
    page.click("#sort-apply")
    page.wait_for_function("document.getElementById('status').innerText === 'Sorting cleared'")
    assert column_values(page, "User")[:6] == ["alice", "bob", "carol"] * 2
    assert page.locator("#head th.sorted").count() == 0
