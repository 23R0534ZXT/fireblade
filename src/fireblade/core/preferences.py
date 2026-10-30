"""Small user preferences, separate from evidence and engine resource settings."""
import json
import os
from pathlib import Path
import tempfile
from dataclasses import asdict, dataclass

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

    def validate(self):
        if self.theme not in ("light", "dark") or self.date_format not in ("source", "iso", "iso7"):
            raise ValueError("Thème ou format de date invalide")
        if self.details_position not in ("bottom", "right"):
            raise ValueError("Position du panneau invalide")
        if not isinstance(self.font_family, str) or len(self.font_family) > 200:
            raise ValueError("Police invalide")
        if type(self.font_size) is not int or not 8 <= self.font_size <= 32:
            raise ValueError("La police doit mesurer de 8 à 32 points")
        if any(type(getattr(self, key)) is not bool for key in ("copy_headers", "right_click_copy", "multiline_tabs")):
            raise ValueError("Préférence booléenne invalide")
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
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, delete=False) as out:
            temporary = Path(out.name)
            json.dump(asdict(preferences), out, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
