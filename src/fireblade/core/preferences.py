"""Small user preferences, separate from evidence and engine resource settings."""

import json
import os
from pathlib import Path
import tempfile
from dataclasses import asdict, dataclass, field

from fireblade.runtime.windows_paths import user_directory


@dataclass
class Preferences:
    theme: str = "light"
    font_family: str = ""
    font_size: int = 10
    copy_headers: bool = True
    right_click_copy: bool = False
    multiline_tabs: bool = False
    date_format: str = "source"
    details_position: str = "bottom"
    custom_date_format: str = "yyyy-MM-dd HH:mm:ss.fffffffK"
    first_pinned_columns: list[str] = field(default_factory=list)

    def validate(self):
        if self.theme not in ("light", "dark") or self.date_format not in (
            "source",
            "iso",
            "iso7",
            "custom",
        ):
            raise ValueError("Thème ou format de date invalide")
        if self.details_position not in ("bottom", "right", "top"):
            raise ValueError("Position du panneau invalide")
        if not isinstance(self.font_family, str) or len(self.font_family) > 200:
            raise ValueError("Police invalide")
        import math

        if (
            type(self.font_size) not in (int, float)
            or not math.isfinite(self.font_size)
            or not 8 <= self.font_size <= 32
        ):
            raise ValueError("La police doit mesurer de 8 à 32 points")
        if any(
            type(getattr(self, key)) is not bool
            for key in ("copy_headers", "right_click_copy", "multiline_tabs")
        ):
            raise ValueError("Préférence booléenne invalide")
        from fireblade.core.timestamps import date_pattern

        date_pattern(self.custom_date_format)
        if (
            not isinstance(self.first_pinned_columns, list)
            or len(self.first_pinned_columns) > 128
            or any(
                not isinstance(h, str) or not 1 <= len(h) <= 300
                for h in self.first_pinned_columns
            )
        ):
            raise ValueError("Liste de colonnes épinglées invalide")
        return self


def load_preferences(path=None):
    path = Path(path) if path else user_directory() / "preferences.json"
    if not path.exists():
        return Preferences()
    if path.stat().st_size > 16384:
        raise ValueError("Préférences trop volumineuses")
    return Preferences(**json.loads(path.read_text(encoding="utf-8"))).validate()


def save_preferences(preferences, path=None):
    preferences.validate()
    path = Path(path) if path else user_directory() / "preferences.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, delete=False
        ) as out:
            temporary = Path(out.name)
            json.dump(asdict(preferences), out, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
