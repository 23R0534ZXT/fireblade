"""Read-only embedded files; user data always lives outside the executable."""
import json
from pathlib import Path
import sys

from fireblade.runtime.windows_paths import user_directory


def resource_root():
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "resources"
    return Path(__file__).resolve().parents[3]


def resource_path(relative):
    return resource_root() / relative


def default_config():
    user_config = user_directory() / "fireblade.toml"
    if user_config.exists():
        return user_config
    # Existing portable configurations remain optional and readable.
    if getattr(sys, "frozen", False):
        for filename in ("fireblade.toml", "timeline-next.toml"):
            legacy = Path(sys.executable).parent / filename
            if legacy.exists():
                return legacy
    bundled = resource_path("config/fireblade.toml")
    return bundled if bundled.exists() else None


def build_info():
    path = resource_path("build/build-info.json")
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    from fireblade import __version__
    return dict(application="Fireblade", version=__version__, maturity="prototype", packaging="source")
