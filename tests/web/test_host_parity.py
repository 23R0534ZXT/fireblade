"""The parity map must not lie: a claim points at a test that exists.

`docs/development/host-parity.json` says what the Host edition does with every
label of the desktop's Qt sources. These tests hold it to three rules — nothing
found in the sources is unaccounted for, nothing in the map is invented, and a
covered claim names a test that really exists in this repository.
"""
import ast
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MAP = ROOT / "docs" / "development" / "host-parity.json"
UI = ROOT / "src" / "fireblade" / "ui"
TESTS = ROOT / "tests"


def _map() -> dict:
    return json.loads(MAP.read_text(encoding="utf-8"))


def _test_names() -> set[str]:
    names: set[str] = set()
    for path in TESTS.rglob("test_*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:  # a half-written file is not this test's business
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                names.add(node.name)
    return names


def _labels_from_sources() -> dict[str, list[str]]:
    ui = UI
    if not ui.is_dir():
        pytest.skip("the Qt sources are not in this tree")
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import parity_inventory
    finally:
        sys.path.pop(0)
    return parity_inventory.collect(sorted(ui.glob("*.py")))


def test_every_label_of_the_desktop_is_accounted_for():
    found = set(_labels_from_sources())
    mapped = {entry["label"] for entry in _map()["commands"]}
    missing = sorted(found - mapped)
    stale = sorted(mapped - found)
    assert not missing, f"labels the map does not cover: {missing}"
    assert not stale, f"labels the Qt sources no longer expose: {stale}"


def test_a_covered_command_names_a_test_that_exists():
    names = _test_names()
    for entry in _map()["commands"]:
        if entry["status"] != "covered":
            continue
        assert entry["where"].strip(), f"{entry['label']} claims coverage with no surface"
        assert entry["test"] in names, f"{entry['label']} names a test that does not exist: {entry['test']}"


def test_a_declared_command_gives_its_reason():
    for entry in _map()["commands"]:
        if entry["kind"] != "command" or entry["status"] != "declared":
            continue
        assert len(entry["reason"].strip()) > 20, f"{entry['label']} is declared without a reason"


def test_a_remaining_command_states_its_plan():
    for entry in _map()["commands"]:
        if entry["status"] != "todo":
            continue
        assert len(entry["plan"].strip()) > 20, f"{entry['label']} is a todo without a plan"


def test_counts_are_computed_from_the_map():
    entries = _map()["commands"]
    commands = [entry for entry in entries if entry["kind"] == "command"]
    assert commands, "the map must classify at least one command"
    covered = [entry for entry in commands if entry["status"] == "covered"]
    declared = [entry for entry in commands if entry["status"] == "declared"]
    todo = [entry for entry in commands if entry["status"] == "todo"]
    assert len(covered) + len(declared) + len(todo) == len(commands)
    # The kinds must partition the map, or the published counts are misleading.
    kinds = {entry["kind"] for entry in entries}
    assert kinds <= {"command", "parameter", "container"}


def test_the_published_page_matches_the_map():
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import host_parity_report
    finally:
        sys.path.pop(0)
    page = ROOT / "docs" / "development" / "HOST-PARITY.md"
    assert page.is_file(), "HOST-PARITY.md is missing"
    assert page.read_text(encoding="utf-8") == host_parity_report.render(_map()), (
        "HOST-PARITY.md is stale: run scripts/host_parity_report.py")


def test_a_covered_row_is_not_marked_todo_in_the_same_breath():
    """A label appears once: a duplicate would let two claims coexist."""
    labels = [entry["label"] for entry in _map()["commands"]]
    assert len(labels) == len(set(labels))
    for entry in _map()["commands"]:
        if entry["status"] == "todo":
            assert not entry["test"], f"{entry['label']} is a todo but names a test"
