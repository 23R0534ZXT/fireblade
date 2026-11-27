"""What the command audit shares: its data, its helpers and the way it presses a command.

The audit's pages hold a case of sixty known rows (``standard_csv``): three users, three event
ids, four hosts, five days, five source addresses. Every assertion of the audit can be worked out
from those rules, so a test states what a command must leave on screen instead of copying what it
happened to leave.
"""

import re
import time

import httpx

USERS = ["alice", "bob", "carol"]
EVENTS = [4624, 4625, 4688]
ROWS = 60


def standard_csv():
    lines = ["Time,Host,User,Event,Path,Src"]
    for i in range(ROWS):
        lines.append(
            f"2026-11-0{1 + i % 5}T1{i % 10}:{i % 60:02d}:00Z,PC0{i % 4 + 1},{USERS[i % 3]},"
            f"{EVENTS[i % 3]},C:\\Users\\{USERS[i % 3]}\\f{i}.exe,10.0.0.{i % 5}"
        )
    return "\n".join(lines) + "\n"


def command(page, act):
    """Press a command in its menu, with the mouse."""
    menu = page.evaluate(
        f"document.querySelector('.menu [data-act=\"{act}\"]').closest('.menu').dataset.for"
    )
    page.click(f'.menubar .m[data-menu="{menu}"]')
    page.click(f'.menu.show [data-act="{act}"]')


def pick_import_source(page, action, *, entry=".toolbar"):
    """Open the evidence chooser from the given surface and select its source."""
    if entry == "menu":
        command(page, "import-evidence")
    else:
        page.click(f'{entry} [data-act="import-evidence"]')
    page.click(f'#import-source-modal [data-act="{action}"]')


def rows(page):
    return page.locator("#body tr[data-row]").count()


def total(page):
    page.wait_for_function("document.getElementById('pageinfo').innerText.includes('/')")
    return int(re.search(r"/\s*(\d+)\s*(?:group|row)", page.inner_text("#pageinfo")).group(1))


def status(page):
    return page.inner_text("#status")


def select(page, *positions):
    """Click the rows at these positions: the first plainly, the others with Ctrl."""
    for index, position in enumerate(positions):
        page.locator("#body tr[data-row]").nth(position).locator("td[data-cell]").first.click(
            modifiers=["Control"] if index else []
        )


def answer(page, *texts):
    """Fill the one-line question dialogs, in order."""
    for text in texts:
        page.wait_for_selector("#ask-input:visible")
        page.fill("#ask-input", text)
        page.click('[data-act="ask-ok"]')


def headers(page):
    """The column names as read on screen, without the sort arrow or the sort rank."""
    return page.eval_on_selector_all(
        "#head tr:first-child th",
        "els => els.map(e => e.innerText.replace(/[▲▼]/g, '').replace(/\\d+$/, '').trim())",
    )


def column_values(page, name):
    names = headers(page)
    at = names.index(name)
    return page.eval_on_selector_all(
        f"#body tr[data-row] td:nth-child({at + 1})", "els => els.map(e => e.innerText)"
    )


def cell(page, row, column):
    return page.locator("#body tr[data-row]").nth(row).locator(f"td[data-cell='{column}']")


def context(page, row, column, act):
    cell(page, row, column).click(button="right")
    page.click(f'#row-menu [data-act="{act}"]')


def import_more(page, server, name, content):
    """A second analysis in the open case, imported by path the way a collection is."""
    base, _root, evidence = server
    case = page.evaluate("state.openCase.id")
    source = evidence / case / name
    source.write_text(content)
    job = httpx.post(
        f"{base}/api/cases/{case}/import-jobs",
        data={"source": str(source), "organization": "files"},
        timeout=30,
    ).json()["job"]
    for _ in range(120):
        if httpx.get(f"{base}/api/import-jobs/{job}").json().get("status") != "running":
            break
        time.sleep(0.25)
    page.evaluate("openCase(state.openCase.id)")
    page.wait_for_function(f"state.openCase.analyses.some(a => a.label === '{name}')")
