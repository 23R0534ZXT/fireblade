"""Declarative plugins: field names, types and layout; no arbitrary code execution."""

import json
from pathlib import Path

from fireblade.runtime.windows_paths import user_directory

MAX_BYTES = 2 * 1024 * 1024


def plugin_path():
    return user_directory() / "Plugins"


def validate_plugin(data):
    if not isinstance(data, dict) or set(data) - {
        "name",
        "signature",
        "timestamp",
        "booleans",
        "columns",
        "transforms",
    }:
        raise ValueError("Champs de plugin inconnus")
    name = data.get("name")
    if not isinstance(name, str) or not 1 <= len(name) <= 200:
        raise ValueError("Nom de plugin invalide")
    for key in ("signature", "timestamp", "booleans", "columns"):
        values = data.get(key, [])
        if (
            not isinstance(values, list)
            or len(values) > 1024
            or any(not isinstance(v, str) or not 1 <= len(v) <= 300 for v in values)
        ):
            raise ValueError("Liste de champs de plugin invalide")
        if len({v.casefold() for v in values}) != len(values):
            raise ValueError("Champs de plugin dupliqués")
    if not data.get("signature"):
        raise ValueError("Le plugin doit préciser des colonnes de reconnaissance")
    from fireblade.core.derived import validate_definition

    transforms = data.get("transforms", [])
    if not isinstance(transforms, list) or len(transforms) > 64:
        raise ValueError("64 transformations par profil au maximum")
    transforms = [validate_definition(d) for d in transforms]
    return (
        {"transforms": transforms}
        | {
            key: data.get(key, [])
            for key in ("signature", "timestamp", "booleans", "columns")
        }
        | {"name": name}
    )


def load_plugins(directory=None):
    directory = Path(directory) if directory else plugin_path()
    plugins, errors = [], []
    if not directory.exists():
        return plugins, errors
    for path in sorted(directory.glob("*.json"))[:100]:
        try:
            if path.stat().st_size > MAX_BYTES:
                raise ValueError("Plugin limité à 2 Mo")
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            plugins.append(validate_plugin(data))
        except (OSError, ValueError, TypeError) as exc:
            errors.append(f"{path.name} : {exc}")
    return plugins, errors
