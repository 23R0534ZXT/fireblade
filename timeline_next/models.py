"""Plain data structures shared by the engine and interface. No Qt imports."""
import json
from dataclasses import asdict, dataclass, field


@dataclass
class Filter:
    column: int
    operator: str
    value: str = ""


@dataclass
class View:
    search: str = ""
    filters: list[Filter] = field(default_factory=list)
    groups: list[int] = field(default_factory=list)
    sort_column: int | None = None
    descending: bool = False
    sort_type: str = "text"
    bookmarks_only: bool = False
    highlight: str = ""

    def to_json(self):
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, value):
        data = json.loads(value)
        data["filters"] = [Filter(**f) for f in data.get("filters", [])]
        return cls(**data)


@dataclass
class AnalysisSnapshot:
    """Small UI state for reopening the current case after a failed import."""
    path: str
    source_info: dict
    view: View
    header_state: bytes



OPERATORS = [("Contient", "contains"), ("Ne contient pas", "not_contains"),
    ("Égal à (exact)", "eq"), ("Différent de (exact)", "ne"),
    ("Commence par", "starts"), ("Expression régulière RE2", "regex"),
    ("Vide / NULL", "empty"), ("Non vide", "not_empty"),
    ("Nombre >", "gt"), ("Nombre ≥", "ge"), ("Nombre <", "lt"),
    ("Nombre ≤", "le"), ("Date ≥ (ISO)", "after"), ("Date ≤ (ISO)", "before")]

