"""Removing all sort keys must restore the evidence order."""

from _audit import column_values, command
from conftest import make_case


def test_removing_every_sort_key_restores_source_order(page):
    sort = page.get_by_role("button", name="Sort by User", exact=True)
    sort.focus()
    sort.press("Enter")
    page.locator('#head th[aria-sort="ascending"]').wait_for()
    assert sort.evaluate("(button) => button === document.activeElement")
    assert column_values(page, "User") == sorted(column_values(page, "User"))
    command(page, "sort-priority")
    while page.locator("[data-sort-remove]").count():
        page.locator("[data-sort-remove]").first.click()
    page.select_option("#sort-header-type", "text")
    page.click("#sort-apply")
    page.wait_for_function("document.getElementById('status').innerText === 'Sorting cleared'")
    assert column_values(page, "User")[:6] == ["alice", "bob", "carol"] * 2
    assert page.locator("#head th.sorted").count() == 0


def test_numeric_header_sort_orders_source_values_as_numbers(page, server):
    make_case(server, "Numeric sort", "Amount,Source\n11,first\n2,second\n30,third\n")
    page.click('.toolbar [data-act="refresh-cases"]')
    page.click("#tab-cases")
    page.get_by_text("Numeric sort", exact=True).dblclick()
    sort = page.get_by_role("button", name="Sort by Amount", exact=True)
    sort.wait_for()
    command(page, "sort-priority")
    page.select_option("#sort-header-type", "number")
    page.click("#sort-apply")
    sort.click()
    page.locator('#head th[aria-sort="ascending"]').wait_for()
    assert column_values(page, "Amount") == ["2", "11", "30"]
