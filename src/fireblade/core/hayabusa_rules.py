"""Editing Hayabusa detection rules without ever touching the delivered pack.

The pack ships 5019 rules under ``resources/forensic-tools/Hayabusa/rules``. An analyst who
wants a rule to fire on their environment must change it *for this machine*, and the next
run must use the change — without editing a file that the next update overwrites.

The model is a copy-on-write one:

- a user folder holds the rules the analyst edited, as overrides by file name;
- a state file holds the rules the analyst switched off;
- before each run, Fireblade builds an effective rules folder out of hard links to the pack,
  replaces the overridden files and leaves the disabled ones out, then hands that folder to
  Hayabusa with ``-r``. The pack itself is never written.

A rule is validated for the keys Hayabusa needs before it is accepted; the full YAML
grammar is Hayabusa's job, and a rule it refuses is reported by the run like any other
failure.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

RULE_SUFFIXES = (".yml", ".yaml")
REQUIRED_KEYS = ("title", "logsource", "detection")
KNOWN_KEYS = (
    "title",
    "id",
    "status",
    "description",
    "author",
    "date",
    "modified",
    "level",
    "tags",
    "logsource",
    "detection",
    "falsepositives",
    "references",
    "ruletype",
    "details",
    "related",
)


def user_root(base=None):
    """Where the analyst's overrides live; never inside the installed pack."""
    if base is not None:
        return Path(base)
    root = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~/.local/share")
    return Path(root) / "Fireblade" / "Rules" / "Hayabusa"


def overrides_dir(base=None):
    return user_root(base) / "overrides"


def state_path(base=None):
    return user_root(base) / "state.json"


def _state(base=None):
    path = state_path(base)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return dict(disabled=[str(name) for name in data.get("disabled") or []])
    except (OSError, ValueError):
        return dict(disabled=[])


def _write_state(state, base=None):
    path = state_path(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def header_of(text):
    """The few scalar keys a rule announces at the top of the file, read without a parser."""
    result = {}
    for line in str(text or "").splitlines()[:40]:
        if not line or line[:1] in (" ", "\t", "#"):
            continue
        key, _, value = line.partition(":")
        key = key.strip().casefold()
        if key in KNOWN_KEYS and key not in result:
            result[key] = value.strip().strip('"').strip("'")
    return result


def validate(text):
    """Refuse a rule Hayabusa cannot load, before it reaches a run."""
    text = str(text or "")
    if not text.strip():
        raise ValueError("Une règle vide ne peut pas être enregistrée")
    header = header_of(text)
    missing = [key for key in REQUIRED_KEYS if key not in header]
    if missing:
        raise ValueError("Règle incomplète : " + ", ".join(missing))
    if "\t" in text.split("\n", 1)[0]:
        raise ValueError("Indentation par tabulation en tête de fichier")
    return header


def rule_files(pack_rules):
    pack_rules = Path(pack_rules)
    if not pack_rules.is_dir():
        return []
    return sorted(path for path in pack_rules.rglob("*") if path.suffix.casefold() in RULE_SUFFIXES)


def inventory(pack_rules, base=None):
    """Every rule the next run would load, with where it comes from and whether it is on."""
    pack_rules = Path(pack_rules)
    overrides = (
        {
            path.name.casefold(): path
            for path in overrides_dir(base).glob("*")
            if path.suffix.casefold() in RULE_SUFFIXES
        }
        if overrides_dir(base).is_dir()
        else {}
    )
    disabled = {name.casefold() for name in _state(base)["disabled"]}
    rows = []
    seen = set()
    for path in rule_files(pack_rules):
        name = path.name
        key = name.casefold()
        seen.add(key)
        source = "user" if key in overrides else "pack"
        target = overrides.get(key, path)
        try:
            header = header_of(target.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            header = {}
        rows.append(
            dict(
                name=name,
                path=str(target),
                source=source,
                title=header.get("title") or path.stem,
                level=(header.get("level") or "").casefold(),
                status=(header.get("status") or "").casefold(),
                enabled=key not in disabled,
            )
        )
    for key, path in overrides.items():
        if key in seen:
            continue
        try:
            header = header_of(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            header = {}
        rows.append(
            dict(
                name=path.name,
                path=str(path),
                source="user",
                title=header.get("title") or path.stem,
                level=(header.get("level") or "").casefold(),
                status=(header.get("status") or "").casefold(),
                enabled=key not in disabled,
            )
        )
    return rows


def read_rule(pack_rules, name, base=None):
    """The text the analyst edits: the override when there is one, the pack's rule otherwise."""
    name = Path(str(name)).name
    override = overrides_dir(base) / name
    if override.is_file():
        return override.read_text(encoding="utf-8", errors="replace")
    for path in rule_files(pack_rules):
        if path.name.casefold() == name.casefold():
            return path.read_text(encoding="utf-8", errors="replace")
    raise ValueError("Règle introuvable : " + name)


def save_rule(pack_rules, name, text, base=None):
    """Store an override, keeping the pack intact and validating before writing."""
    name = Path(str(name)).name
    if Path(name).suffix.casefold() not in RULE_SUFFIXES:
        raise ValueError("Une règle doit être un fichier .yml")
    validate(text)
    folder = overrides_dir(base)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / name
    temporary = target.with_suffix(target.suffix + ".partial")
    temporary.write_text(text, encoding="utf-8", newline="")
    os.replace(temporary, target)
    return target


def reset_rule(name, base=None):
    """Drop the override: the next run uses the pack's rule again."""
    target = overrides_dir(base) / Path(str(name)).name
    removed = target.exists()
    target.unlink(missing_ok=True)
    return removed


def set_enabled(name, enabled, base=None):
    state = _state(base)
    key = Path(str(name)).name.casefold()
    disabled = {item.casefold() for item in state["disabled"]}
    if enabled:
        disabled.discard(key)
    else:
        disabled.add(key)
    state["disabled"] = sorted(disabled)
    _write_state(state, base)
    return enabled


def effective_rules(pack_rules, target, base=None):
    """A folder Hayabusa can be pointed at: the pack, minus the disabled, plus the overrides.

    Hard links keep the cost near zero on the same volume; anything that cannot be linked is
    copied. Nothing here writes inside the delivered pack.
    """
    pack_rules, target = Path(pack_rules), Path(target)
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True, exist_ok=True)
    overrides = (
        {
            path.name.casefold(): path
            for path in overrides_dir(base).glob("*")
            if path.suffix.casefold() in RULE_SUFFIXES
        }
        if overrides_dir(base).is_dir()
        else {}
    )
    disabled = {name.casefold() for name in _state(base)["disabled"]}
    linked = copied = skipped = 0
    for path in rule_files(pack_rules):
        key = path.name.casefold()
        if key in disabled:
            skipped += 1
            continue
        if key in overrides:
            continue  # written below, once, from the override
        destination = target / path.name
        try:
            os.link(path, destination)
            linked += 1
        except OSError:
            shutil.copy2(path, destination)
            copied += 1
    for key, path in overrides.items():
        if key in disabled:
            skipped += 1
            continue
        shutil.copy2(path, target / path.name)
    return dict(
        path=str(target),
        linked=linked,
        copied=copied,
        skipped=skipped,
        overrides=len([key for key in overrides if key not in disabled]),
    )


def has_changes(base=None):
    """True when an override or a switched-off rule exists: the run must use a merged folder."""
    overrides = overrides_dir(base)
    if overrides.is_dir() and any(
        path.suffix.casefold() in RULE_SUFFIXES for path in overrides.iterdir()
    ):
        return True
    return bool(_state(base)["disabled"])
