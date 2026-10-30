"""Small, validated resource settings; TOML support is in Python's standard library."""
from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class Settings:
    memory_mb: int = 256
    threads: int = 2
    page_size: int = 250
    max_loaded_rows: int = 1000
    export_batch_rows: int = 2048
    cache_sorted_pages: bool = True

    def __post_init__(self):
        if type(self.cache_sorted_pages) is not bool:
            raise ValueError("cache_sorted_pages doit être un booléen")
        bounds = {
            "memory_mb": (64, 16384), "threads": (1, 32),
            "page_size": (25, 1000), "max_loaded_rows": (25, 10000),
            "export_batch_rows": (1, 10000),
        }
        for name, (low, high) in bounds.items():
            value = getattr(self, name)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"{name} doit être un entier entre {low} et {high}")
        if self.max_loaded_rows % self.page_size:
            raise ValueError("max_loaded_rows doit être un multiple de page_size")


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
