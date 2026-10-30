"""Read the documented TLE_settings.xml DataContract; never execute .NET data."""

import copy
from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET
from fireblade.core.preferences import Preferences
from fireblade.core.timestamps import date_pattern


@dataclass
class TleSettings:
    preferences: Preferences
    warnings: list[str]


def read_tle_settings(path, current=None):
    path = Path(path)
    if path.stat().st_size > 128 * 1024:
        raise ValueError("Préférences TLE limitées à 128 Ko")
    raw = path.read_text(encoding="utf-8-sig")
    if "<!DOCTYPE" in raw.upper() or "<!ENTITY" in raw.upper():
        raise ValueError("DTD et entités non prises en charge")
    root = ET.fromstring(raw)
    local = lambda tag: tag.rsplit("}", 1)[-1]
    if local(root.tag) != "Settings":
        raise ValueError("Ce fichier ne contient pas les préférences TLE")
    preferences = copy.deepcopy(current or Preferences())
    warnings = []
    seen = set()
    booleans = {
        "CopyColumnHeaders": "copy_headers",
        "CopyRightClick": "right_click_copy",
        "MultilineTabs": "multiline_tabs",
    }
    for child in root:
        name = local(child.tag)
        value = (child.text or "").strip()
        if name in seen:
            raise ValueError("Préférence TLE dupliquée : " + name)
        seen.add(name)
        if name in booleans or name == "DetailsOnTop":
            if value.lower() not in ("true", "false"):
                raise ValueError("Booléen TLE invalide : " + name)
            flag = value.lower() == "true"
            if name == "DetailsOnTop":
                preferences.details_position = "top" if flag else "bottom"
            else:
                setattr(preferences, booleans[name], flag)
        elif name == "FontName":
            preferences.font_family = value
        elif name == "FontSize":
            preferences.font_size = float(value)
        elif name == "DateTimeFormat":
            date_pattern(value)
            preferences.date_format = "custom"
            preferences.custom_date_format = value
        elif name == "Theme":
            preferences.theme = (
                "dark"
                if any(
                    t in value.casefold() for t in ("black", "dark", "noir", "sombre")
                )
                else "light"
            )
            warnings.append(
                f"Thème {value} adapté au thème {preferences.theme} de Fireblade"
            )
        elif name == "FirstPinnedColumns":
            if all(local(c.tag) == "string" for c in child):
                preferences.first_pinned_columns = [
                    (c.text or "").strip() for c in child
                ]
            else:
                warnings.append(
                    "FirstPinnedColumns structuré non traduit : épinglage actuel conservé"
                )
        else:
            warnings.append("Préférence TLE non traduite : " + name)
    return TleSettings(preferences.validate(), warnings)
