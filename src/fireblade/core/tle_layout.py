"""Read DevExpress XML data/layout rules without deserializing .NET objects."""

from dataclasses import dataclass, field
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from fireblade.core.models import (
    View,
    SortKey,
    Summary,
    Filter,
    FilterGroup,
    FormatRule,
)
from fireblade.core.filter_text import parse_filter


@dataclass
class TleLayout:
    columns: list
    view: View
    warnings: list[str] = field(default_factory=list)


def properties(node):
    return {c.get("name"): c for c in node if c.tag == "property"}


def text(node, name, default=""):
    child = properties(node).get(name)
    return (child.text or "").strip() if child is not None else default


def color(value, default, warnings):
    if not value or value.lower() in ("transparent", "empty"):
        return default
    numbers = [x.strip() for x in value.split(",")]
    if len(numbers) in (3, 4) and all(
        x.isdigit() and 0 <= int(x) <= 255 for x in numbers
    ):
        rgb = list(map(int, numbers[-3:]))
        if len(numbers) == 4 and int(numbers[0]) != 255:
            alpha = int(numbers[0]) / 255
            rgb = [round(x * alpha + 255 * (1 - alpha)) for x in rgb]
            warnings.append("Couleur ARGB composée sur fond clair")
        return "#" + "".join(f"{x:02x}" for x in rgb)
    if re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        return value
    # QColor accepts the named HTML/.NET colors used by public TLE layouts and
    # does not require a QApplication, a display or a platform plugin.
    from PySide6.QtGui import QColor

    parsed = QColor(value)
    if not parsed.isValid():
        raise ValueError(f"Couleur de layout inconnue : {value}")
    return parsed.name()


def read_tle_layout(path, headers):
    path = Path(path)
    if path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError("Disposition limitée à 4 Mo")
    raw = path.read_text(encoding="utf-8-sig")
    if "<!DOCTYPE" in raw.upper() or "<!ENTITY" in raw.upper():
        raise ValueError("DTD et entités non prises en charge")
    root = ET.fromstring(raw)

    def normalize(name):
        return re.sub(r"[^a-z0-9]", "", name.casefold())

    from fireblade.core.profiles import detect_profile
    from fireblade.core.profile_aliases import FIELD_ALIASES

    profile = detect_profile(headers)
    field_aliases = dict(FIELD_ALIASES.get(profile.name, {})) if profile else {}
    if profile and profile.name == "SuperTimeline":
        field_aliases.update(SourceDescription="sourcetype", ShortDescription="short")
    if "Fireblade_Category" in headers:
        field_aliases["Color"] = "Fireblade_Category"

    def resolve(name, virtual=False):
        typed_name = name[3:] if name.startswith("col") else name
        if profile and typed_name.casefold() in {
            h.casefold() for h in profile.timestamp
        }:
            normalized = [
                i
                for i, h in enumerate(headers)
                if h.casefold() == ("Fireblade_UTC_" + typed_name).casefold()
            ]
            if len(normalized) == 1:
                return normalized[0]
        if profile and profile.name in ("Sigcheck", "SigcheckTroy", "Autoruns"):
            boolean = [
                i
                for i, h in enumerate(headers)
                if h.casefold() == ("Fireblade_Bool_" + typed_name).casefold()
            ]
            if len(boolean) == 1:
                return boolean[0]
        original = name
        exact = [i for i, h in enumerate(headers) if h.casefold() == name.casefold()]
        if not exact:
            if name.startswith("col"):
                name = name[3:]
            name = field_aliases.get(name, name)
            exact = [
                i for i, h in enumerate(headers) if h.casefold() == name.casefold()
            ]
        matches = exact or [
            i for i, h in enumerate(headers) if normalize(h) == normalize(name)
        ]
        if len(matches) == 1:
            return matches[0]
        if virtual and name.casefold() in ("line", "tag", "color", "note"):
            return None
        raise ValueError(f"Colonne du layout absente ou ambiguë : {original}")

    columns = []
    warnings = []
    if profile:
        from fireblade.core.profiles import profile_view

        types, _ = profile_view(profile, headers)
        view = View(
            boolean_columns=types.boolean_columns,
            timestamp_columns=types.timestamp_columns,
        )
    else:
        view = View()
    container = properties(root).get("Columns")
    if container is None:
        raise ValueError("Disposition sans collection Columns")
    aliases = {}
    for node in container:
        field = text(node, "FieldName") or text(node, "Name")
        if not field:
            continue
        try:
            index = resolve(field, True)
        except ValueError:
            warnings.append(f"Colonne du layout absente de cet export : {field}")
            continue
        if index is None:
            continue
        aliases[text(node, "Name", field)] = index
        visible = int(text(node, "VisibleIndex", str(len(columns))))
        if text(node, "Visible", "true").lower() == "false":
            visible = -1
        width = int(text(node, "Width", "150"))
        if not 20 <= width <= 10000:
            raise ValueError("Largeur de colonne invalide")
        fixed = text(node, "Fixed", "None")
        if fixed not in ("None", "Left", "0", "1", ""):
            raise ValueError(
                "Colonne épinglée à droite : cette disposition nécessite une adaptation"
            )
        group = int(text(node, "GroupIndex", "-1"))
        columns.append(
            dict(
                column=index,
                position=visible,
                width=width,
                pinned=fixed in ("Left", "1"),
                group=group,
                sort=text(node, "SortOrder", "None"),
                sort_index=int(text(node, "SortIndex", "-1")),
            )
        )
        interval = text(node, "GroupInterval", "Value")
        mapping = {
            "Value": "value",
            "Default": "value",
            "DateYear": "year",
            "DateMonth": "month",
            "Date": "day",
            "DateHour": "hour",
            "DateDay": "day",
            "DateWeek": "week",
            "DateQuarter": "quarter",
            "DateMinute": "minute",
            "DateSecond": "second",
        }
        if interval not in mapping:
            raise ValueError(f"Intervalle de groupe non traduit : {interval}")
        if interval not in ("Value", "Default"):
            view.group_intervals[str(index)] = mapping[interval]
        for prop in node.iter("property"):
            if prop.get("name") == "FormatType" and (prop.text or "") == "DateTime":
                if index not in view.timestamp_columns:
                    view.timestamp_columns.append(index)
    if not columns or len({c["column"] for c in columns}) != len(columns):
        raise ValueError("Disposition sans colonnes reconnues ou avec doublons")
    view.groups = [
        c["column"]
        for c in sorted(columns, key=lambda c: c["group"])
        if c["group"] >= 0
    ]
    view.pinned_columns = [c["column"] for c in columns if c["pinned"]]
    view.sorts = [
        SortKey(
            c["column"],
            "timestamp" if c["column"] in view.timestamp_columns else "text",
            c["sort"] == "Descending",
        )
        for c in sorted(columns, key=lambda c: c["sort_index"])
        if c["sort"] in ("Ascending", "Descending")
    ]
    view.group_order = "value"
    view.group_descending = False
    first_group = next((c for c in columns if c["group"] == 0), None)
    if first_group:
        view.group_descending = first_group["sort"] == "Descending"

    # Bind each bracketed name to the *source* header, including colFoo / Foo_Bar
    # aliases. Virtual Line/Tag/Note are handled by the expression compiler.
    def expression(value):
        def replace(token):
            name = token[1:-1].replace("]]", "]")
            if name.casefold() in ("line", "tag", "note") and name.casefold() not in [
                h.casefold() for h in headers
            ]:
                return token
            i = aliases[name] if name in aliases else resolve(name)
            return "[" + headers[i].replace("]", "]]") + "]"

        # Tokenize so a string literal containing '[Foo]' is never rewritten.
        from fireblade.core.expressions import TOKEN

        tokens = []
        offset = 0
        while offset < len(value):
            match = TOKEN.match(value, offset)
            if not match:
                if value[offset:].strip():
                    raise ValueError("Syntaxe de filtre TLE inconnue")
                break
            token = match.group(0)
            if match.group(1):
                token = token[: len(token) - len(match.group(1))] + replace(
                    match.group(1)
                )
            tokens.append(token)
            offset = match.end()
        return parse_filter("".join(tokens), headers)

    if text(root, "ActiveFilterEnabled", "true").lower() != "false":
        active = text(root, "ActiveFilterString") or text(root, "FilterString")
        if active:
            view.expression = expression(active)
    view.search = text(root, "FindFilterText")
    for summary_name in ("GroupSummary", "TotalSummary"):
        collection = properties(root).get(summary_name)
        if collection is None:
            continue
        for item in collection:
            kind = text(item, "SummaryType")
            fieldname = text(item, "FieldName")
            if kind in ("None", ""):
                continue
            if kind == "Count" and not fieldname:
                continue  # built-in group count
            mapping = {
                "Count": "count",
                "Sum": "sum",
                "Average": "avg",
                "Min": "min",
                "Max": "max",
                "DistinctCount": "distinct",
            }
            if kind not in mapping:
                raise ValueError(f"Résumé non traduit : {kind}")
            summary = Summary(
                resolve(fieldname),
                mapping[kind],
                "number" if kind in ("Sum", "Average") else "text",
            )
            if summary not in view.summaries:
                view.summaries.append(summary)
    for name in ("FormatRules", "FormatConditions"):
        collection = properties(root).get(name)
        if collection is None:
            continue
        for item in collection:
            rule_node = properties(item).get("Rule")
            if rule_node is None:
                rule_node = item
            rule_type = text(item, "RuleType", "#FormatConditionRuleExpression")
            enabled = text(item, "Enabled", "true").lower() != "false"
            condition_text = text(rule_node, "Expression") or text(item, "Expression")
            if condition_text:
                condition = expression(condition_text)
            elif rule_type in ("#FormatConditionRuleValue", "FormatConditionRuleValue"):
                colname = text(item, "ColumnName") or text(item, "Column")
                index = aliases[colname] if colname in aliases else resolve(colname)
                op = text(rule_node, "Condition")
                operators = {
                    "Equal": "eq",
                    "NotEqual": "ne",
                    "Greater": "gt",
                    "GreaterOrEqual": "ge",
                    "Less": "lt",
                    "LessOrEqual": "le",
                    "Contains": "contains",
                    "BeginsWith": "starts",
                    "EndsWith": "ends",
                }
                if op in ("Between", "NotBetween"):
                    condition = FilterGroup(
                        "and",
                        [
                            Filter(index, "ge", text(rule_node, "Value1")),
                            Filter(index, "le", text(rule_node, "Value2")),
                        ],
                    )
                    if op == "NotBetween":
                        condition = FilterGroup("not", [condition])
                elif op in operators:
                    condition = FilterGroup(
                        "and", [Filter(index, operators[op], text(rule_node, "Value1"))]
                    )
                else:
                    raise ValueError(f"Condition de couleur non traduite : {op}")
            else:
                raise ValueError(f"Règle de layout non traduite : {rule_type}")
            appearance = properties(rule_node).get("Appearance")
            if appearance is None:
                appearance = rule_node
            background = color(text(appearance, "BackColor"), "#ffffff", warnings)
            rgb = [int(background[i : i + 2], 16) for i in (1, 3, 5)]
            foreground = color(
                text(appearance, "ForeColor"),
                "#202020" if sum(rgb) > 350 else "#ffffff",
                warnings,
            )
            target = None
            if text(item, "ApplyToRow", "true").lower() == "false":
                name = text(item, "ColumnApplyToName") or text(item, "ColumnName")
                target = aliases[name] if name in aliases else resolve(name)
            font = text(appearance, "Font")
            view.format_rules.append(
                FormatRule(
                    condition,
                    background,
                    foreground,
                    "bold" in font.lower(),
                    target,
                    enabled,
                    italic='italic' in font.lower(),
                    underline='underline' in font.lower(),
                    strikeout='strikeout' in font.lower(),
                )
            )
    if text(root, "GroupSummarySortInfoState"):
        warnings.append("Tri de résumés sérialisé TLE : vérifier le tri des groupes")
    if len(view.format_rules) > 32 or len(view.summaries) > 16:
        raise ValueError("Disposition dépassant les limites de règles ou de résumés")
    return TleLayout(columns, view, list(dict.fromkeys(warnings)))
