"""Small, validated resource settings; TOML support is in Python's standard library."""

import os
from dataclasses import dataclass
from pathlib import Path
import tomllib


def auto_threads(cpu=None):
    """What an automatic thread count means: the measured knee, capped by the machine.

    Eight files at once is where the parsers stop gaining on a shared disk, so the
    value never promises more than that, and never more than the machine has.
    """
    cpu = cpu or os.cpu_count() or 1
    return max(1, min(8, cpu))


@dataclass(frozen=True)
class Settings:
    memory_mb: int = 1024
    threads: int = 1
    page_size: int = 250
    max_loaded_rows: int = 1000
    export_batch_rows: int = 2048
    cache_sorted_pages: bool = True

    def __post_init__(self):
        if type(self.cache_sorted_pages) is not bool:
            raise ValueError("cache_sorted_pages doit être un booléen")
        bounds = {
            "memory_mb": (64, 16384),
            "threads": (0, 32),
            "page_size": (25, 1000),
            "max_loaded_rows": (25, 10000),
            "export_batch_rows": (1, 10000),
        }
        for name, (low, high) in bounds.items():
            value = getattr(self, name)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"{name} doit être un entier entre {low} et {high}")
        if self.max_loaded_rows % self.page_size:
            raise ValueError("max_loaded_rows doit être un multiple de page_size")

    @property
    def effective_threads(self):
        """Zero means automatic; it has to be resolved before it reaches DuckDB."""
        return self.threads if self.threads > 0 else auto_threads()


def load_settings(path: str | Path | None = None) -> Settings:
    if path is None:
        return Settings()
    with Path(path).open("rb") as source:
        data = tomllib.load(source)
    if set(data) - {"resources"}:
        raise ValueError("Seule la section [resources] est reconnue")
    resources = data.get("resources", {})
    if not isinstance(resources, dict):
        raise ValueError("[resources] doit être une section TOML")
    unknown = set(resources) - Settings.__dataclass_fields__.keys()
    if unknown:
        raise ValueError("Paramètres inconnus : " + ", ".join(sorted(unknown)))
    return Settings(**resources)


def physical_memory_mb():
    """Total RAM in megabytes, without pulling in a dependency."""
    try:
        if os.name == "nt":
            import ctypes

            class Status(ctypes.Structure):
                _fields_ = [
                    ("length", ctypes.c_ulong),
                    ("load", ctypes.c_ulong),
                    ("total_physical", ctypes.c_ulonglong),
                    ("available_physical", ctypes.c_ulonglong),
                    ("total_page_file", ctypes.c_ulonglong),
                    ("available_page_file", ctypes.c_ulonglong),
                    ("total_virtual", ctypes.c_ulonglong),
                    ("available_virtual", ctypes.c_ulonglong),
                    ("available_extended", ctypes.c_ulonglong),
                ]

            status = Status()
            status.length = ctypes.sizeof(Status)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
            return max(512, int(status.total_physical // (1024 * 1024)))
        return max(
            512, int(os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") // (1024 * 1024))
        )
    except Exception:
        return 4096


def grown_memory(current, factor=4, ceiling_mb=None):
    """A larger budget for a step that cannot spill, bounded by the machine itself.

    DuckDB can spill sorts and joins to disk, but a bulk CSV insert has to hold its
    vectors: when the budget is too small for the file, more memory is the only cure.
    The ceiling is half the physical RAM, so a huge import cannot swap the analyst's
    whole desktop out; None means "no room left, report the failure".
    """
    current = int(current or 0)
    ceiling = int(ceiling_mb or max(1024, physical_memory_mb() // 2))
    target = min(ceiling, max(current * factor, current + 512), 16384)
    return target if target > current else None
