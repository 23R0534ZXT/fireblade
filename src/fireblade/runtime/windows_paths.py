"""Windows user storage; never write runtime data beside the executable."""

import os
from pathlib import Path


def documents_directory():
    """The analyst's Documents folder: where a certificate is expected to land."""
    import os
    from pathlib import Path

    profile = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    candidate = Path(profile) / "Documents"
    return candidate if candidate.is_dir() else Path(profile)


def user_directory():
    base = os.environ.get("LOCALAPPDATA")
    return (Path(base) if base else Path.home() / "AppData" / "Local") / "Fireblade"


def analyses_directory():
    return user_directory() / "Analyses"


def logs_directory():
    return user_directory() / "Journaux"
