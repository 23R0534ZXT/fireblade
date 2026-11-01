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
    GroupSort,
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
    style_columns = []
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
        style_columns.append((index,node))
        visible = int(text(node, "VisibleIndex", str(len(columns))))
        if text(node, "Visible", "true").lower() == "false":
            visible = -1
        width = int(text(node, "Width", "150"))
        if not 20 <= width <= 10000:
            raise ValueError("Largeur de colonne invalide")
        fixed = text(node, "Fixed", "None")
        if fixed not in ("None", "Left", "Right", "0", "1", "2", ""):
            raise ValueError(
                "Côté d’épinglage non traduit : " + fixed
            )
        group = int(text(node, "GroupIndex", "-1"))
        columns.append(
            dict(
                column=index,
                position=visible,
                width=width,
                pinned=fixed in ("Left", "Right", "1", "2"),
                pin_side="right" if fixed in ("Right", "2") else "left" if fixed in ("Left", "1") else None,
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
    view.pinned_columns = [c["column"] for c in columns if c["pin_side"] == "left" and c["position"] >= 0]
    view.right_pinned_columns = [c["column"] for c in columns if c["pin_side"] == "right" and c["position"] >= 0]
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
    summary_indices=[];summary_tags={}
    for summary_name in ("GroupSummary", "TotalSummary"):
        collection = properties(root).get(summary_name)
        if collection is None:
            continue
        for item in collection:
            kind = text(item, "SummaryType")
            fieldname = text(item, "FieldName")
            mapped='unsupported'
            if summary_name=='GroupSummary':summary_indices.append(mapped)
            if kind in ("None", ""):
                continue
            if kind == "Count" and not fieldname:
                if summary_name=='GroupSummary':
                    summary_indices[-1]=None
                    tag_node=properties(item).get('Tag')
                    tag=(tag_node.text or '') if tag_node is not None else ''
                    if tag:
                        if tag in summary_tags:raise ValueError('Tag de résumé TLE ambigu : '+tag)
                        summary_tags[tag]=None
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
            resolved=resolve(fieldname)
            column_node=next((node for index,node in style_columns if index==resolved),None)
            declared=text(column_node,'UnboundType') if column_node is not None else ''
            display=properties(column_node).get('DisplayFormat') if column_node is not None else None
            numeric=declared in ('Integer','Decimal','Double') or (display is not None and text(display,'FormatType')=='Numeric')
            summary = Summary(resolved,mapping[kind],
                'number' if kind in ('Sum','Average') or numeric else 'timestamp' if resolved in view.timestamp_columns else 'text')
            if summary not in view.summaries:
                view.summaries.append(summary)
            if summary_name=='GroupSummary':
                mapped=view.summaries.index(summary);summary_indices[-1]=mapped
                tag_node=properties(item).get('Tag')
                tag=(tag_node.text or '') if tag_node is not None else ''
                if tag:
                    if tag in summary_tags:raise ValueError('Tag de résumé TLE ambigu : '+tag)
                    summary_tags[tag]=mapped
    from fireblade.core.tle_summary_sort import read_summary_sorts
    state_node=properties(root).get('GroupSummarySortInfoState')
    view.group_sorts=read_summary_sorts((state_node.text or '') if state_node is not None else '',lambda name:aliases[name] if name in aliases else resolve(name),summary_indices,summary_tags)
    for c in sorted(columns,key=lambda item:item['group']):
        if c['group']>=0:
            view.group_sorts.append(GroupSort(c['column'],'value',descending=c['sort']=='Descending'))
    if view.groups:
        first=next((key for key in view.group_sorts if key.column==view.groups[0]),None)
        if first:
            view.group_order,view.group_summary,view.group_descending=first.kind,first.summary,first.descending
    from fireblade.core.tle_appearance import read_layout_styles,validate_styles
    view.layout_styles=read_layout_styles(root,style_columns,text,properties,color,warnings)
    validate_styles(view.layout_styles,len(headers))
    for name in ("FormatRules", "FormatConditions"):
        collection = properties(root).get(name)
        if collection is None:
            continue
        for item in collection:
            rule_node = properties(item).get("Rule")
            if rule_node is None:
                rule_node = item
            rule_type = text(item, "RuleType") or text(rule_node,"Type") or rule_node.get("Type") or "#FormatConditionRuleExpression"
            enabled = text(item, "Enabled", "true").lower() != "false"
            from fireblade.core.tle_graphics import read_graphic
            graphic=read_graphic(item,rule_node,rule_type,text,properties,color,resolve,aliases,warnings)
            if graphic is not None:
                view.format_rules.append(graphic)
                continue
            condition_text = text(rule_node, "Expression") or text(item, "Expression")
            statistic='';stat_rank='10';stat_percent=False;value_column=None
            normalized_type=rule_type.lstrip('#').split(',')[0].split('.')[-1]
            if normalized_type in ('FormatConditionRuleTopBottom','FormatConditionRuleAboveBelowAverage','FormatConditionRuleUniqueDuplicate'):
                name=text(item,'ColumnName') or text(item,'Column')
                value_column=aliases[name] if name in aliases else resolve(name)
                if normalized_type=='FormatConditionRuleTopBottom':
                    rank_side=text(rule_node,'TopBottom','Top');rank_type=text(rule_node,'RankType','Automatic')
                    if rank_side not in ('Top','Bottom') or rank_type not in ('Automatic','Number','Percent'):raise ValueError('Type de classement non traduit')
                    statistic='bottom' if rank_side=='Bottom' else 'top'
                    stat_rank=text(rule_node,'Rank','10');stat_percent=text(rule_node,'RankType','Number')=='Percent'
                elif normalized_type=='FormatConditionRuleAboveBelowAverage':
                    average=text(rule_node,'AverageType','Above')
                    if average not in ('Above','Below','EqualOrAbove','EqualOrBelow'):raise ValueError('Type de moyenne non traduit : '+average)
                    statistic={'Above':'above_avg','Below':'below_avg','EqualOrAbove':'above_eq_avg','EqualOrBelow':'below_eq_avg'}[average]
                else:
                    unique_type=text(rule_node,'FormatType') or text(rule_node,'UniqueDuplicate','Duplicate')
                    if unique_type not in ('Unique','Duplicate'):raise ValueError('Type de doublon non traduit')
                    statistic='unique' if unique_type=='Unique' else 'duplicate'
                condition=FilterGroup()
            elif normalized_type in ('FormatConditionRuleDateOccuring','FormatConditionRuleDateOccurring'):
                name=text(item,'ColumnName') or text(item,'Column');col=aliases[name] if name in aliases else resolve(name)
                field=headers[col].replace(']',']]');dates=[v.strip() for v in text(rule_node,'DateType','Yesterday').replace('|',',').split(',')]
                condition=FilterGroup('or',[Filter(col,'expression',f"InDateRange([{field}], '{date}')") for date in dates])
                warnings.append('Dates relatives adaptées à UTC ; semaine commençant le lundi')
            elif normalized_type=='FormatConditionRuleContains':
                name=text(item,'ColumnName') or text(item,'Column');col=aliases[name] if name in aliases else resolve(name)
                values=properties(rule_node).get('Values')
                if values is None:raise ValueError('Liste de valeurs de format absente')
                condition=FilterGroup('or',[Filter(col,'eq',v.text or '') for v in values])
            elif condition_text:
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
                if op=="None":condition=FilterGroup()
                elif op in ("Between", "NotBetween"):
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
            target = None
            if text(item, "ApplyToRow", "true").lower() == "false":
                name = text(item, "ColumnApplyToName") or text(item, "ColumnName")
                target = aliases[name] if name in aliases else resolve(name)
            predefined=text(rule_node,'PredefinedName')
            from fireblade.core.tle_styles import style
            from fireblade.core.tle_appearance import appearance as read_appearance
            defaults=style(predefined) if predefined else {}
            adapted=read_appearance(appearance,text,properties,color,warnings,defaults)
            view.format_rules.append(
                FormatRule(
                    condition,
                    adapted.get("background","#ffffff"),
                    adapted.get("foreground","#202020"),
                    adapted.get("bold",False),
                    target,
                    enabled,
                    italic=adapted.get('italic',False),
                    underline=adapted.get('underline',False),
                    strikeout=adapted.get('strikeout',False),
                    font_family=adapted.get('font_family',''),font_size=adapted.get('font_size',0),
                    appearance={key:value for key,value in adapted.items() if key in ('background2','gradient','horizontal','vertical')},
                    statistic=statistic,stat_rank=stat_rank,stat_percent=stat_percent,value_column=value_column,
                    stop_if_true=text(item,'StopIfTrue','false').lower()=='true',
                    use_background='background' in adapted,use_foreground='foreground' in adapted,use_font=any(key in adapted for key in ('font_family','font_size','bold','italic','underline','strikeout')),
                )
            )
    if len(view.format_rules) > 32 or len(view.summaries) > 16:
        raise ValueError("Disposition dépassant les limites de règles ou de résumés")
    return TleLayout(columns, view, list(dict.fromkeys(warnings)))
