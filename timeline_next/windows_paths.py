"""Windows user storage; never write runtime data beside the executable."""
import os
from pathlib import Path


def user_directory():
    base = os.environ.get("LOCALAPPDATA")
    return (Path(base) if base else Path.home() / "AppData" / "Local") / "TimelineNext"


def analyses_directory():
    return user_directory() / "Analyses"


def logs_directory():
    return user_directory() / "Journaux"
