"""Which functions of the Host client did the browser tests never run?

Run the browser tests with ``FIREBLADE_JS_COVERAGE=<folder>``, then::

    python -m scripts.audit.js_coverage <folder>

Every page the tests opened left the V8 coverage of the client's scripts. They are merged here (a
character is covered when any page ran it), and the report names each function that no page ever
entered, then the share of executable lines that ran. A function nobody ran is a feature nobody
pressed, or dead code: either way it is a line in the audit's to-do list.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

STATIC = Path(__file__).resolve().parents[2] / "src/fireblade/web/static"


def _covered(length: int, functions: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    """(executable, ran) per character: the innermost range that holds a character decides."""
    count = np.full(length, -1, dtype=np.int64)
    ranges = [item for fn in functions for item in fn["ranges"]]
    ranges.sort(key=lambda r: (r["startOffset"], -r["endOffset"]))
    for item in ranges:
        count[item["startOffset"] : min(item["endOffset"], length)] = item["count"]
    return count >= 0, count > 0


def touched(folder: Path) -> set[str]:
    """The controls any page touched, by the audit's naming (see tests/web/conftest.py)."""
    keys: set[str] = set()
    for path in sorted(folder.glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(document, dict):
            keys.update(document.get("touched", []))
    return keys


def merge(folder: Path) -> dict[str, dict]:
    """One merged record per script file name: its source, its ran-mask and its functions."""
    merged: dict[str, dict] = {}
    for path in sorted(folder.glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        scripts = document["scripts"] if isinstance(document, dict) else document
        for entry in scripts:
            name = entry["url"].rsplit("/static/", 1)[-1]
            source_path = STATIC / name
            if not source_path.is_file():
                continue
            source = source_path.read_text(encoding="utf-8")
            length = len(source)
            executable, ran = _covered(length, entry["functions"])
            slot = merged.setdefault(
                name,
                {
                    "source": source,
                    "executable": np.zeros(length, dtype=bool),
                    "ran": np.zeros(length, dtype=bool),
                    "functions": {},
                },
            )
            if len(slot["ran"]) != length:  # a page served another version of the file
                continue
            slot["executable"] |= executable
            slot["ran"] |= ran
            for fn in entry["functions"]:
                first = fn["ranges"][0]
                key = (fn["functionName"], first["startOffset"], first["endOffset"])
                slot["functions"][key] = slot["functions"].get(key, False) or first["count"] > 0
    return merged


def report(merged: dict[str, dict], show: int) -> int:
    lines_missed = 0
    for name, slot in merged.items():
        source = slot["source"]
        starts = [0]
        for index, char in enumerate(source):
            if char == "\n":
                starts.append(index + 1)

        def line_of(offset: int, starts=starts) -> int:
            return int(np.searchsorted(starts, offset, side="right"))

        executable = slot["executable"]
        ran = slot["ran"]
        total = missed = 0
        for number, start in enumerate(starts, start=1):
            end = starts[number] if number < len(starts) else len(source)
            text = source[start:end].strip()
            if not text or text in ("{", "}", "});", "}", "},", ");") or text.startswith("//"):
                continue
            span = slice(start, end)
            if not executable[span].any():
                continue
            total += 1
            if not ran[span].any():
                missed += 1
        lines_missed += missed
        never = sorted(
            (
                (line_of(start), end - start, fn_name or "(anonymous)")
                for (fn_name, start, end), ok in slot["functions"].items()
                if not ok and fn_name
            ),
        )
        print(
            f"{name}: {total - missed}/{total} executable lines ran "
            f"({100 * (total - missed) / max(total, 1):.1f} %); "
            f"{len(never)} named function(s) never entered"
        )
        for line, size, fn_name in never[:show]:
            print(f"  line {line:5d}  {size:5d} chars  {fn_name}")
        if len(never) > show:
            print(f"  … {len(never) - show} more")
    return lines_missed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("folder", help="the FIREBLADE_JS_COVERAGE folder")
    parser.add_argument("--show", type=int, default=400, help="functions to list per script")
    args = parser.parse_args(argv)
    merged = merge(Path(args.folder))
    if not merged:
        print("no coverage found: run the browser tests with FIREBLADE_JS_COVERAGE set")
        return 2
    report(merged, args.show)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
