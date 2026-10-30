"""Plain data structures shared by the engine and interface. No Qt imports."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field


@dataclass
class Filter:
    column: int
    operator: str
    value: str = ""


@dataclass
class FilterGroup:
    logic: str = "and"
    children: list[Filter | FilterGroup] = field(default_factory=list)


def condition_from_dict(data, depth=0):
    if depth > 24 or not isinstance(data, dict):
        raise ValueError("Expression de filtre trop profonde ou invalide")
    if "children" not in data:
        return Filter(**data)
    if data.get("logic", "and") not in ("and", "or", "not"):
        raise ValueError("Logique de filtre invalide")
    children = data["children"]
    if not isinstance(children, list) or len(children) > 256:
        raise ValueError("Trop de conditions dans un groupe")
    return FilterGroup(data.get("logic", "and"), [condition_from_dict(c, depth + 1) for c in children])


@dataclass
class FormatRule:
    condition: FilterGroup = field(default_factory=FilterGroup)
    background: str = "#fce2e2"
    foreground: str = "#202020"
    bold: bool = False
    target: int | None = None
    enabled: bool = True


@dataclass
class SortKey:
    column: int
    kind: str = "text"
    descending: bool = False


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
    expression: FilterGroup | None = None
    format_rules: list[FormatRule] = field(default_factory=list)
    header_state: str = ""
    sorts: list[SortKey] = field(default_factory=list)
    global_rules_enabled: bool = True

    def to_json(self):
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, value):
        data = json.loads(value)
        data["filters"] = [Filter(**f) for f in data.get("filters", [])]
        if data.get("expression") is not None:
            data["expression"] = condition_from_dict(data["expression"])
        rules = data.get("format_rules", [])
        if len(rules) > 32:
            raise ValueError("32 règles de coloration au maximum")
        data["format_rules"] = [FormatRule(**{**r, "condition": condition_from_dict(r["condition"])}) for r in rules]
        data["sorts"] = [SortKey(**key) for key in data.get("sorts", [])]
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

