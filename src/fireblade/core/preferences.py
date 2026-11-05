"""Small user preferences, separate from evidence and engine resource settings."""

import json
import os
from pathlib import Path
import tempfile
from dataclasses import asdict, dataclass, field

from fireblade.runtime.windows_paths import user_directory


@dataclass
class Preferences:
    navigation_grouping: str = "families"
    resource_memory_mb: int = 0
    query_threads: int = 0
    parsing_threads: int = 1
    navigation_visible: bool = True
    navigation_position: str = "left"
    workspace_details_visible: bool = True
    main_toolbar_visible: bool = True
    collection_toolbar_visible: bool = True
    startup_animation: bool = True
    theme: str = "light"
    theme_preset: str = ""
    theme_palette: dict[str,str] = field(default_factory=dict)
    font_family: str = ""
    font_size: int = 10
    copy_headers: bool = True
    right_click_copy: bool = False
    auto_profiles: bool = True
    multiline_tabs: bool = False
    case_autosave: bool = True
    date_format: str = "source"
    language: str = field(default_factory=lambda: os.environ.get("FIREBLADE_LANGUAGE", "en"))
    details_position: str = "bottom"
    custom_date_format: str = "yyyy-MM-dd HH:mm:ss.fffffffK"
    first_pinned_columns: list[str] = field(default_factory=list)
    pinned_columns_by_format: dict[str,list[str]] = field(default_factory=dict)

    def validate(self):
        for name, low, high in (("resource_memory_mb", 0, 16384), ("query_threads", 0, 32), ("parsing_threads", 1, 32)):
            value = getattr(self, name)
            if type(value) is not int or not low <= value <= high or name == "resource_memory_mb" and 0 < value < 64:
                raise ValueError("Ressources invalides : " + name)
        if self.navigation_grouping not in ("folders", "families", "flat") or self.navigation_position not in ("left", "right"):
            raise ValueError("Organisation de navigation invalide")
        if any(type(getattr(self, name)) is not bool for name in ("navigation_visible", "startup_animation", "workspace_details_visible", "main_toolbar_visible", "collection_toolbar_visible")):
            raise ValueError("Préférence de navigation invalide")
        if self.theme not in ("light", "dark") or self.date_format not in (
            "source",
            "iso",
            "iso7",
            "custom",
        ):
            raise ValueError("Thème ou format de date invalide")
        if self.language not in ("en", "fr"):
            raise ValueError("Langue invalide")
        from fireblade.core.themes import THEMES
        if not isinstance(self.theme_preset,str) or self.theme_preset and self.theme_preset not in THEMES:
            raise ValueError('Thème de galerie inconnu')
        import re
        if not isinstance(self.theme_palette,dict) or set(self.theme_palette)-{'window','text','base','alternate','highlight','selection_text'} or any(not isinstance(c,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',c) for c in self.theme_palette.values()):raise ValueError('Palette de thème invalide')
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
            for key in (
                "copy_headers",
                "right_click_copy",
                "multiline_tabs",
                "auto_profiles",
                "case_autosave",
            )
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
        if not isinstance(self.pinned_columns_by_format,dict) or len(self.pinned_columns_by_format)>128:
            raise ValueError('Épinglages par format invalides')
        seen=set()
        for name,columns in self.pinned_columns_by_format.items():
            if not isinstance(name,str) or not 1<=len(name)<=300 or name.casefold() in seen:
                raise ValueError('Nom de format absent ou ambigu')
            seen.add(name.casefold())
            if not isinstance(columns,list) or len(columns)>128 or any(not isinstance(h,str) or not 1<=len(h)<=300 for h in columns):
                raise ValueError('Colonnes par format invalides')
        return self


def load_preferences(path=None):
    path = Path(path) if path else user_directory() / "preferences.json"
    if not path.exists():
        return Preferences()
    if path.stat().st_size > 128*1024:
        raise ValueError("Préférences trop volumineuses")
    return Preferences(**json.loads(path.read_text(encoding="utf-8"))).validate()


def save_preferences(preferences, path=None):
    preferences.validate()
    if len(json.dumps(asdict(preferences),ensure_ascii=False,indent=2).encode('utf-8'))>128*1024:
        raise ValueError('Préférences limitées à 128 Ko')
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


def default_pinned_columns(preferences, headers, info):
    """Specific reader overrides, then recognised profile, then generic defaults."""
    from fireblade.core.profiles import detect_profile
    reader=info.get('plugin',{}).get('type','')
    profile=detect_profile(headers)
    candidates=[reader,reader.rsplit('.',1)[-1] if reader else '',profile.name if profile else 'GenericCsv']
    mapping={name.casefold():columns for name,columns in preferences.pinned_columns_by_format.items()}
    selected=preferences.first_pinned_columns
    for candidate in candidates:
        if candidate and candidate.casefold() in mapping:
            selected=mapping[candidate.casefold()];break
    # Preserve configured order; absent columns do not alter another field.
    result=[]
    for name in selected:
        matches=[i for i,h in enumerate(headers) if h.casefold()==name.casefold()]
        if len(matches)==1 and matches[0] not in result:result.append(matches[0])
    return result
