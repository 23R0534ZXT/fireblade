"""Colour rules, judged by what the grid paints.

A rule saved is not a rule that works: each test adds a rule through the window, then reads the
colours the cells really have (the computed ones, so a stripe of the table that hides a colour
fails the test) against an answer worked out from the data.
"""

import pytest
from _audit import command
from conftest import make_case

NAMES = [f"n{i}" for i in range(12)]
GROUPS = ["A"] * 4 + ["B"] * 4 + ["C"] * 4
VALUES = [1, 2, 3, 4, 10, 20, 30, 40, 100, 200, 300, 400]
DELTAS = [-5, -1, 0, 3, 7, -20, 15, -3, 8, 0, -9, 12]
KINDS = ["x", "x", "x", "x", "x", "y", "y", "y", "y", "z", "z", "w"]
NOTES = ["", "n", "n", "", "n", "n", "", "n", "n", "", "n", "n"]


@pytest.fixture()
def table(server, request):
    """Twelve known rows: names, groups, values, signed deltas, kinds and a note that is blank on four."""
    from _browser import browser_page

    name = "Rules " + request.node.name[:40]
    lines = ["Name,Group,Value,Delta,Kind,Note"] + [
        f"{NAMES[i]},{GROUPS[i]},{VALUES[i]},{DELTAS[i]},{KINDS[i]},{NOTES[i]}" for i in range(12)
    ]
    make_case(server, name, "\n".join(lines) + "\n")
    with browser_page(server[0], name) as page:
        yield page


def rgb(colour):
    colour = colour.lstrip("#")
    return tuple(int(colour[i : i + 2], 16) for i in (0, 2, 4))


def css(colour):
    return "rgb({}, {}, {})".format(*rgb(colour))


def within(colour, expected, slack=2):
    """True when the computed colour is the expected one, give or take the rounding of a channel."""
    import re

    found = tuple(int(part) for part in re.findall(r"\d+", colour)[:3])
    return all(abs(a - b) <= slack for a, b in zip(found, expected))


def mix(start, end, weight):
    a, b = rgb(start), rgb(end)
    return tuple(round(x + (y - x) * weight) for x, y in zip(a, b))


def add_rule(
    page,
    column,
    operator,
    value="",
    *,
    background="#ffcc00",
    ink="#202020",
    bold=False,
    target="",
    visual="none",
    bound="fixed",
    low=None,
    high=None,
    middle=None,
    middle_colour=None,
    negative=None,
    thresholds=None,
    mode=None,
    icon_colours=None,
    statistic="",
    rank=None,
    logic="single",
    extra=(),
):
    """Fill the colour-rule window the way a person does and press Add the rule."""
    command(page, "rules")
    page.select_option("#rule-column", label=column)
    page.select_option("#rule-operator", operator)
    page.fill("#rule-value", value)
    page.evaluate(
        "([bg, ink]) => { document.getElementById('rule-colour').value = bg;"
        " document.getElementById('rule-ink').value = ink; }",
        [background, ink],
    )
    page.set_checked("#rule-bold", bold)
    page.select_option("#rule-target", target)
    for column_name, op, text in extra:
        page.click("#rule-add-condition")
        row = page.locator("#rule-conditions [data-condition]").last
        row.locator("[data-cond-column]").select_option(label=column_name)
        row.locator("[data-cond-operator]").select_option(op)
        row.locator("[data-cond-value]").fill(text)
    page.select_option("#rule-logic", logic)
    page.select_option("#rule-visual", visual)
    page.select_option("#rule-bound", bound)
    if low is not None:
        page.fill("#rule-min", str(low))
    if high is not None:
        page.fill("#rule-max", str(high))
    if middle is not None:
        page.fill("#rule-middle-value", str(middle))
    if middle_colour:
        page.evaluate(f"document.getElementById('rule-middle-colour').value = '{middle_colour}'")
    if negative:
        page.evaluate(f"document.getElementById('rule-negative').value = '{negative}'")
    if thresholds is not None:
        page.fill("#rule-icon-thresholds", thresholds)
    if mode:
        page.select_option("#rule-icon-mode", mode)
    if icon_colours:
        page.fill("#rule-icon-colours", icon_colours)
    page.select_option("#rule-statistic", statistic)
    if rank is not None:
        page.fill("#rule-stat-rank", str(rank))
    before = page.locator("#rules-list [data-rule-remove]").count()
    page.click('[data-act="rule-add"]')
    page.wait_for_function(
        f"document.querySelectorAll('#rules-list [data-rule-remove]').length === {before + 1}"
    )
    page.click('.modal.show [data-act="settings-close"]')
    page.wait_for_function("!document.querySelector('.modal.show')")
    page.wait_for_timeout(250)


def cells(page, column):
    """{name: computed look of the cell in `column`} for the twelve rows."""
    return page.evaluate(
        """(column) => {
          const out = {};
          for (const tr of document.querySelectorAll('#body tr[data-row]')) {
            const name = tr.querySelector('td[data-cell="0"]').innerText.trim();
            const td = tr.querySelector(`td[data-cell="${column}"]`);
            const style = getComputedStyle(td);
            out[name] = {
              background: style.backgroundColor, color: style.color, weight: style.fontWeight,
              text: td.innerText.trim(), inline: td.getAttribute('style') || '',
              row: tr.getAttribute('style') || '',
            };
          }
          return out;
        }""",
        column,
    )


def painted(page, colour, column=0):
    """The names of the rows whose cell in `column` shows `colour`."""
    wanted = css(colour)
    return sorted(
        (name for name, look in cells(page, column).items() if look["background"] == wanted),
        key=lambda name: int(name[1:]),
    )


def names(indices):
    return [NAMES[i] for i in indices]


def test_a_rule_paints_every_row_it_matches_in_its_colours_odd_rows_and_even_rows_alike(table):
    add_rule(table, "Name", "starts", "n1", background="#ff0000", ink="#ffffff", bold=True)
    look = cells(table, 2)
    for name in ("n1", "n10", "n11"):
        assert look[name]["background"] == css("#ff0000"), (name, look[name])
        assert look[name]["color"] == css("#ffffff")
        assert int(look[name]["weight"]) >= 600
    for name in ("n0", "n2", "n3", "n9"):
        assert look[name]["background"] != css("#ff0000"), name
        assert int(look[name]["weight"]) < 600
    assert painted(table, "#ff0000", column=3) == ["n1", "n10", "n11"], "every cell of the row"


OPERATORS = [
    ("Name", "contains", "1", [1, 10, 11]),
    ("Name", "not_contains", "1", [0, 2, 3, 4, 5, 6, 7, 8, 9]),
    ("Group", "ne", "A", [4, 5, 6, 7, 8, 9, 10, 11]),
    ("Group", "eq", "B", [4, 5, 6, 7]),
    ("Group", "eq", "b", []),  # an exact comparison is exact: case counts
    ("Name", "regex", "^n(1|9)$", [1, 9]),
    ("Value", "text_gt", "3", [3, 6, 7, 10, 11]),  # compared as text: "30" > "3", "4" > "3"
    ("Name", "starts", "n1", [1, 10, 11]),
    ("Name", "ends", "0", [0, 10]),
    ("Value", "gt", "100", [9, 10, 11]),
    ("Value", "ge", "100", [8, 9, 10, 11]),
    ("Value", "lt", "10", [0, 1, 2, 3]),
    ("Value", "le", "10", [0, 1, 2, 3, 4]),
    ("Note", "empty", "", [0, 3, 6, 9]),
    ("Note", "not_empty", "", [1, 2, 4, 5, 7, 8, 10, 11]),
]


@pytest.mark.parametrize(("column", "operator", "value", "rows"), OPERATORS)
def test_each_operator_paints_the_rows_its_name_says(table, column, operator, value, rows):
    add_rule(table, column, operator, value, background="#00aaff")
    assert painted(table, "#00aaff") == names(rows)


COMBINATIONS = [
    ("and", [3], ("Group", "eq", "A"), [("Value", "ge", "3")]),
    ("or", [0, 1, 2, 3, 8, 9, 10, 11], ("Group", "eq", "A"), [("Value", "ge", "100")]),
    ("not", [4, 5, 6, 7], ("Group", "eq", "A"), [("Group", "eq", "C")]),  # none of A, C
]


@pytest.mark.parametrize(("logic", "expected", "first", "others"), COMBINATIONS)
def test_conditions_are_combined_the_way_the_logic_says(table, logic, expected, first, others):
    add_rule(
        table,
        first[0],
        first[1],
        first[2],
        background="#aa00ff",
        logic=logic,
        extra=[(c, o, v) for c, o, v in others],
    )
    rows = painted(table, "#aa00ff")
    if logic == "and":
        # group A and a value of at least 3: rows 2 (value 3) and 3 (value 4)
        assert rows == names([2, 3])
    else:
        assert rows == names(expected), rows


# -- Visual formats ---------------------------------------------------------------------------------


def looks(page, column):
    return cells(page, column)


def bar_fraction(inline):
    import re

    found = re.search(r"transparent (\d+)%", inline)
    return int(found.group(1)) if found else None


def test_a_data_bar_fills_each_cell_in_proportion_to_its_value_between_the_bounds(table):
    add_rule(table, "Value", "not_empty", visual="bar", bound="fixed", low=0, high=400)
    look = looks(table, 2)
    for index, value in enumerate(VALUES):
        assert bar_fraction(look[NAMES[index]]["inline"]) == int(value / 400 * 100 + 0.5), (
            NAMES[index],
            look[NAMES[index]]["inline"],
        )


def test_a_data_bar_over_the_automatic_bounds_runs_from_the_smallest_value_to_the_largest(table):
    add_rule(table, "Value", "not_empty", visual="bar", bound="auto")
    look = looks(table, 2)
    assert bar_fraction(look["n0"]["inline"]) == 0
    assert bar_fraction(look["n11"]["inline"]) == 100
    assert bar_fraction(look["n8"]["inline"]) == int((100 - 1) / (400 - 1) * 100 + 0.5)


def test_a_negative_number_takes_the_negative_colour_on_a_bar(table):
    add_rule(
        table,
        "Delta",
        "not_empty",
        visual="bar",
        bound="fixed",
        low=-20,
        high=20,
        negative="#00ff00",
    )
    look = looks(table, 3)
    assert "#00ff00" in look["n0"]["inline"]  # -5
    assert "#00ff00" not in look["n6"]["inline"]  # 15


def test_a_two_colour_scale_mixes_the_background_into_the_text_colour(table):
    add_rule(
        table,
        "Value",
        "not_empty",
        visual="scale2",
        bound="fixed",
        low=0,
        high=400,
        background="#ff0000",
        ink="#0000ff",
    )
    look = looks(table, 2)
    for index in (0, 5, 8, 11):
        expected = "rgb({}, {}, {})".format(*mix("#ff0000", "#0000ff", VALUES[index] / 400))
        assert look[NAMES[index]]["background"] == expected, (index, look[NAMES[index]])


def test_a_three_colour_scale_goes_through_its_middle_colour(table):
    add_rule(
        table,
        "Value",
        "not_empty",
        visual="scale3",
        bound="fixed",
        low=0,
        high=400,
        middle=50,
        middle_colour="#ffff00",
        background="#ff0000",
        ink="#00ff00",
    )
    look = looks(table, 2)
    # 200 is the middle of 0..400: exactly the middle colour; 400 the last colour; 100 half-way
    assert within(look["n9"]["background"], (255, 255, 0))
    assert within(look["n11"]["background"], (0, 255, 0))
    assert within(look["n8"]["background"], mix("#ff0000", "#ffff00", 0.5))


def test_icons_follow_the_thresholds_in_numbers(table):
    add_rule(
        table,
        "Value",
        "not_empty",
        visual="icon",
        bound="auto",
        thresholds="20, 100",
        mode="number",
        icon_colours="#ff0000,#ffaa00,#00aa00",
    )
    icons = table.evaluate(
        "Object.fromEntries([...document.querySelectorAll('#body tr[data-row]')].map(tr => "
        "[tr.querySelector('td[data-cell=\"0\"]').innerText.trim(), "
        "(tr.querySelector('td[data-cell=\"2\"] .vicon') || {}).innerText || '']))"
    )
    # below 20: the low icon; from 20 up to 99: the middle one; from 100: the high one
    for index, value in enumerate(VALUES):
        expected = "▼" if value < 20 else ("●" if value < 100 else "▲")
        assert icons[NAMES[index]] == expected, (value, icons[NAMES[index]])


# -- Statistics -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("column", "statistic", "rank", "rows"),
    [
        ("Value", "top", 1, [11]),
        ("Value", "top", 3, [9, 10, 11]),
        ("Value", "bottom", 2, [0, 1]),
        ("Kind", "unique", None, [11]),
        ("Kind", "duplicate", None, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]),
        ("Value", "above_avg", None, [8, 9, 10, 11]),  # the average is 92.5
        ("Value", "below_avg", None, [0, 1, 2, 3, 4, 5, 6, 7]),
    ],
)
def test_a_statistic_selects_the_rows_it_names(table, column, statistic, rank, rows):
    add_rule(table, column, "not_empty", background="#12ab34", statistic=statistic, rank=rank)
    assert painted(table, "#12ab34") == names(rows)
