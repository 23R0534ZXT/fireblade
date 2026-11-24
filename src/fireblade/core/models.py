"""Plain data structures shared by the engine and interface. No Qt imports."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


def analysis_label(source_info):
    """What one analysis is called on screen: the evidence file it came from.

    A Linux collection imports an intermediate CSV per log, so every analysis used
    to be called "Linux - journaux-fireblade.csv". The label recorded at collection
    time names the real file; the fallback keeps older analyses readable.

    A parser CSV is named by the artefact it holds, never by the tool's word for it:
    "amcache.csv" reads "Amcache", and a bare "export.csv" takes the family its rows
    carry. The file's own stem stays when it adds something ("Amcache · amcache-01").
    """
    info = source_info or {}
    label = info.get("label")
    if label:
        return str(label)
    path = str(info.get("path", ""))
    if not path:
        return ""
    from fireblade.core.artifact_names import GENERIC_STEMS, csv_kind
    # The separator belongs to the machine that collected the evidence, not to the one
    # reading the case: a Windows path must be split on "\\" inside a Linux container.
    parts = _path_parts(path)
    name = parts[-1] if parts else ""
    stem = Path(name).stem
    if name.casefold().endswith((".csv", ".tsv", ".jsonl")):
        kind = csv_kind(path)
        generic = stem.casefold() in GENERIC_STEMS
        if kind:
            if generic or kind.casefold() in stem.casefold():
                return kind
            return kind+" · "+stem
        if generic:
            family = str(info.get("artifact") or info.get("parser") or "").strip()
            if family:
                return family
            parent = parts[-2] if len(parts) > 1 else ""
            if parent and len(parent) > 2:
                return parent
    return name


def _path_parts(path):
    """Path components with the file name last, whatever the separator.

    Evidence paths reach the interface from Windows collections as often as from
    Linux ones, so both separators split; the drive or the root stays a component.
    """
    text = str(path or "").replace("\\", "/")
    return tuple(part for part in text.split("/") if part not in ("", "."))


def _suffix_depth(parts, index, indexes):
    """How many trailing folders tell one path apart from its neighbours.

    Zero when every other document carries the same folders: there only the
    position in the strip can separate them.
    """
    depth = 0
    mine = parts[index]
    for other in indexes:
        if other == index or parts[other] == mine:
            continue
        shared = 0
        while (shared < len(mine) and shared < len(parts[other])
               and mine[-1 - shared] == parts[other][-1 - shared]):
            shared += 1
        if shared + 1 > depth:
            depth = shared + 1
    return depth


def _with_suffix(label, suffix):
    return label + " · " + suffix if label else suffix


def analysis_tab_labels(documents):
    """Tab titles for the open analyses, unique inside the strip.

    Three CarsDB.db produced by SQLECmd in different folders used to give three
    identical tabs. A name shared by several analyses keeps analysis_label() as its
    base and gains the shortest run of trailing folders that tells it apart; two
    analyses of the very same file fall back to " (2)", " (3)" in tab order. A label
    no other document uses is returned exactly as analysis_label() gives it.
    """
    documents = list(documents)
    labels = [analysis_label(getattr(item, "source_info", None)) for item in documents]
    groups = {}
    for index, label in enumerate(labels):
        groups.setdefault(label, []).append(index)
    taken = set(label for label, indexes in groups.items() if len(indexes) < 2)
    for label, indexes in groups.items():
        if len(indexes) < 2:
            continue
        parts = {}
        for index in indexes:
            info = getattr(documents[index], "source_info", None) or {}
            full = _path_parts(info.get("path", ""))
            parts[index] = full[:-1] if len(full) > 1 else ()
        seen, proposals = {}, {}
        for index in indexes:
            rank = seen.get(parts[index], 0) + 1
            seen[parts[index]] = rank
            depth = _suffix_depth(parts, index, indexes)
            suffix = "/".join(parts[index][-depth:]) if depth and parts[index] else ""
            title = _with_suffix(label, suffix) if suffix else label
            if rank > 1:
                title = title + " (%d)" % rank if title else "(%d)" % rank
            proposals[index] = title
        for index in indexes:
            title, number = proposals[index], 2
            while title in taken:
                title = "%s (%d)" % (proposals[index], number)
                number += 1
            proposals[index] = title
            taken.add(title)
        for index in indexes:
            labels[index] = proposals[index]
    return labels


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
    visual: str = "none"
    minimum: str = "0"
    maximum: str = "100"
    italic: bool = False
    underline: bool = False
    strikeout: bool = False
    bound_mode: str = "fixed"
    font_family: str = ""
    font_size: float = 0.0
    statistic: str = ""
    stat_rank: str = "10"
    stat_percent: bool = False
    stat_ignore_case: bool = False
    stat_include_null: bool = False
    all_source_rows: bool = False
    zero_based: bool = False
    negative_color: str = "#d64c4c"
    axis_color: str = "#777777"
    draw_axis: bool = True
    stop_if_true: bool = True
    use_background: bool = True
    use_foreground: bool = True
    use_font: bool = True
    show_values: bool = True
    value_column: int | None = None
    middle_color: str = "#ffffbf"
    middle_value: str = "50"
    middle_mode: str = "percent"
    maximum_mode: str = ""
    icon_comparisons: list[str] = field(default_factory=list)
    icon_floor: str = ""
    icon_floor_mode: str = "number"
    icon_floor_comparison: str = ">="
    icon_thresholds: list[str] = field(default_factory=list)
    icon_threshold_mode: str = "percent"
    icon_threshold_modes: list[str] = field(default_factory=list)
    icon_set: str = "circles"
    icon_colors: list[str] = field(default_factory=lambda:["#c62828","#c58b00","#218739"])
    icon_images: list[str] = field(default_factory=lambda:["","",""])
    appearance: dict = field(default_factory=dict)


@dataclass
class SortKey:
    column: int
    kind: str = "text"
    descending: bool = False


@dataclass
class Summary:
    column: int
    operation: str = "count"
    kind: str = "number"
    footer_column: int | None = -1


@dataclass
class GroupSort:
    column: int
    kind: str = "value"
    summary: int = 0
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
    summaries: list[Summary] = field(default_factory=list)
    group_order: str = "count"
    group_descending: bool = True
    group_summary: int = 0
    expand_all: bool = False
    group_intervals: dict[str, str] = field(default_factory=dict)
    pinned_columns: list[int] = field(default_factory=list)
    pinned_widths: dict[str, int] = field(default_factory=dict)
    boolean_columns: list[int] = field(default_factory=list)
    timestamp_columns: list[int] = field(default_factory=list)
    right_pinned_columns: list[int] = field(default_factory=list)
    group_sorts: list[GroupSort] = field(default_factory=list)
    layout_styles: dict = field(default_factory=dict)
    tle_fields: dict[str,dict[str,str]] = field(default_factory=dict)
    tle_expressions: dict[str,str] = field(default_factory=dict)
    group_footer_mode: str = "hidden"
    total_summaries: list[Summary] = field(default_factory=list)
    show_total_footer: bool = True
    auto_row_height: bool = False
    row_height: int = 0
    group_row_height: int = 0
    header_height: int = 0

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
        data["summaries"] = [Summary(**item) for item in data.get("summaries", [])]
        data["total_summaries"] = [Summary(**item) for item in data.get("total_summaries", [])]
        data["group_sorts"] = [GroupSort(**item) for item in data.get("group_sorts", [])]
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
    ("Commence par", "starts"), ("Finit par", "ends"), ("Expression régulière RE2", "regex"),
    ("Vide / NULL", "empty"), ("Non vide", "not_empty"),
    ("Nombre >", "gt"), ("Nombre ≥", "ge"), ("Nombre <", "lt"),
    ("Nombre ≤", "le"), ("Date ≥ (ISO)", "after"), ("Date ≤ (ISO)", "before"), ("Date < (ISO)", "date_before"), ("Date > (ISO)", "date_after"), ("Date égale", "date_eq"), ("Date différente", "date_ne"),
    ("Texte >", "text_gt"), ("Texte ≥", "text_ge"), ("Texte <", "text_lt"), ("Texte ≤", "text_le"), ("Expression nommée", "expression")]

