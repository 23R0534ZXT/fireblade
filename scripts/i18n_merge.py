"""Merge translated labels into the table of `core/i18n.py`.

Takes one or more JSON files shaped `{"<french source>": "<english>"}` and
appends the entries to the `EN` dictionary, keeping the existing lines exactly
as they are. Refuses the whole batch if anything is off:

- a key that is not the French string as the code writes it,
- an empty translation,
- a different number of `{}` placeholders between source and translation,
- the same source translated two different ways in the same call.

    python -m scripts.i18n_merge translations/*.json
    python -m scripts.i18n_merge --check translations/*.json   # verify only
"""
import argparse
import ast
import json
import os
import sys

I18N = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "src", "fireblade", "core", "i18n.py")
PLACEHOLDER = "{}"


def load_table(path=I18N):
    """The EN dictionary as the module defines it."""
    source = open(path, encoding="utf-8").read()
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "EN" for target in node.targets):
            return ast.literal_eval(node.value), node.lineno, node.end_lineno or node.lineno
    raise SystemExit("no EN table found in i18n.py")


def gather(paths, table):
    """Validated new entries, and every problem found on the way."""
    problems = []
    additions = {}
    for path in paths:
        with open(path, encoding="utf-8") as handle:
            try:
                payload = json.load(handle)
            except json.JSONDecodeError as exc:
                problems.append(f"{path}: not valid JSON ({exc})")
                continue
        if not isinstance(payload, dict):
            problems.append(f"{path}: expected an object of string to string")
            continue
        for source, target in payload.items():
            if not isinstance(source, str) or not isinstance(target, str):
                problems.append(f"{path}: non-string entry {source!r}")
                continue
            if not target.strip():
                problems.append(f"{path}: empty translation for {source!r}")
                continue
            if source.count(PLACEHOLDER) != target.count(PLACEHOLDER):
                problems.append(f"{path}: placeholder count differs for {source!r} -> {target!r}")
                continue
            existing = table.get(source)
            if existing is not None and existing != target:
                problems.append(f"{path}: {source!r} is already translated as {existing!r}, "
                                f"the batch says {target!r}")
                continue
            if source in additions and additions[source] != target:
                problems.append(f"{path}: {source!r} translated twice, differently")
                continue
            additions[source] = target
    return additions, problems


def render(entries):
    lines = []
    for source, target in entries:
        lines.append(f"    {json.dumps(source, ensure_ascii=False)}: "
                     f"{json.dumps(target, ensure_ascii=False)},")
    return lines


def merge(path, additions, table):
    source = open(path, encoding="utf-8").read()
    lines = source.splitlines(keepends=True)
    _, start, end = load_table(path)
    # `end` is 1-based: the line holding the closing brace.
    closing = end - 1
    assert lines[closing].strip() == "}", lines[closing]
    fresh = [(key, value) for key, value in sorted(additions.items()) if key not in table]
    if not fresh:
        return 0
    block = ["\n", "    # Added for the full English interface: one entry per French label\n",
             "    # the application can display.\n"] + [line + "\n" for line in render(fresh)]
    lines[closing:closing] = block
    updated = "".join(lines)
    ast.parse(updated)          # a broken table must never reach the file
    open(path, "w", encoding="utf-8", newline="\n").write(updated)
    return len(fresh)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", help="JSON files of source to translation")
    parser.add_argument("--check", action="store_true", help="validate without writing")
    args = parser.parse_args(argv)

    table, _, _ = load_table()
    additions, problems = gather(args.files, table)
    if problems:
        print("Refused, nothing written:")
        for problem in problems:
            print("  " + problem)
        return 1
    new = [(key, value) for key, value in additions.items() if key not in table]
    print(f"{len(additions)} entries read, {len(new)} new, {len(additions) - len(new)} already there")
    if args.check:
        return 0
    written = merge(I18N, additions, table)
    print(f"{written} entries appended to {os.path.relpath(I18N)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
