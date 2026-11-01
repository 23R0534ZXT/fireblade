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
        channels = list(map(int, numbers))
        if len(channels) == 4 and channels[0] == 255:
            channels = channels[1:]
        return "#" + "".join(f"{x:02x}" for x in channels)
    if re.fullmatch(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})", value):
        return value
    # QColor accepts the named HTML/.NET colors used by public TLE layouts and
    # does not require a QApplication, a display or a platform plugin.
    from PySide6.QtGui import QColor

    parsed = QColor(value)
    if not parsed.isValid():
        raise ValueError(f"Couleur de layout inconnue : {value}")
    return parsed.name(QColor.HexArgb) if parsed.alpha()!=255 else parsed.name()


def read_tle_layout(path, headers):
    path = Path(path)
    if path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError("Disposition limitée à 4 Mo")
    raw = path.read_text(encoding="utf-8-sig")
    if "<!DOCTYPE" in raw.upper() or "<!ENTITY" in raw.upper():
        raise ValueError("DTD et entités non prises en charge")
    root = ET.fromstring(raw)
    from fireblade.core.tle_styles import custom_styles
    named_styles=custom_styles(path)

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
        from fireblade.core.tle_criteria import migrate
        return parse_filter(migrate(value,headers,aliases,resolve),headers)

    if text(root, "ActiveFilterEnabled", "true").lower() != "false":
        active = text(root, "ActiveFilterString") or text(root, "FilterString")
        if active:
            view.expression = expression(active)
    view.search = text(root, "FindFilterText")
    summary_indices=[];summary_tags={}
    def summary_tag(item):
        node=properties(item).get('Tag')
        return (node.text or '') if node is not None else ''
    collections=[]
    for name in ("GroupSummary","TotalSummary"):
        collection=properties(root).get(name)
        if collection is not None:collections.append((name,list(collection),None))
    for index,column_node in style_columns:
        for name in ('Summary','SummaryItem'):
            collection=properties(column_node).get(name)
            if collection is not None:
                items=[collection] if 'SummaryType' in properties(collection) else list(collection)
                collections.append(('TotalSummary',items,index))
    for summary_name,items,default_column in collections:
        for item in items:
            kind=text(item,'SummaryType')
            fieldname=text(item,'FieldName')
            if summary_name=='GroupSummary':summary_indices.append('unsupported')
            if kind in ('None',''):continue
            footer_name=text(item,'ShowInGroupColumnFooterName') or text(item,'ShowInGroupColumnFooter')
            footer_column=(aliases[footer_name] if footer_name in aliases else resolve(footer_name)) if footer_name else -1
            if kind=='Count' and not fieldname and default_column is None:
                if summary_name=='GroupSummary':
                    summary_indices[-1]=None
                    tag=summary_tag(item)
                    if tag:
                        if tag in summary_tags:raise ValueError('Tag de résumé TLE ambigu : '+tag)
                        summary_tags[tag]=None
                    if footer_column!=-1:
                        summary=Summary(0,'rows','number',footer_column)
                        if summary not in view.summaries:view.summaries.append(summary)
                else:
                    summary=Summary(0,'rows','number')
                    if summary not in view.total_summaries:view.total_summaries.append(summary)
                continue
            mapping={'Count':'count','Sum':'sum','Average':'avg','Min':'min','Max':'max','DistinctCount':'distinct'}
            if kind not in mapping:raise ValueError(f"Résumé non traduit : {kind}")
            resolved=(aliases[fieldname] if fieldname in aliases else resolve(fieldname)) if fieldname else default_column
            column_node=next((node for index,node in style_columns if index==resolved),None)
            declared=text(column_node,'UnboundType') if column_node is not None else ''
            display=properties(column_node).get('DisplayFormat') if column_node is not None else None
            numeric=declared in ('Integer','Decimal','Double') or (display is not None and text(display,'FormatType')=='Numeric')
            summary=Summary(resolved,mapping[kind],
                'number' if kind in ('Sum','Average') or numeric else 'timestamp' if resolved in view.timestamp_columns else 'text',
                footer_column)
            destination=view.summaries if summary_name=='GroupSummary' else view.total_summaries
            if summary not in destination:destination.append(summary)
            if summary_name=='GroupSummary':
                summary_indices[-1]=view.summaries.index(summary)
                tag=summary_tag(item)
                if tag:
                    if tag in summary_tags:raise ValueError('Tag de résumé TLE ambigu : '+tag)
                    summary_tags[tag]=summary_indices[-1]
    options_view=properties(root).get('OptionsView')
    def view_option(name,default=''):
        return (text(options_view,name) if options_view is not None else '') or text(root,'OptionsView.'+name,default)
    mode=view_option('GroupFooterShowMode')
    if mode:
        modes={'Hidden':'hidden','VisibleIfExpanded':'expanded','VisibleAlways':'always'}
        if mode not in modes:raise ValueError('Mode de pied de groupe non traduit : '+mode)
        view.group_footer_mode=modes[mode]
    elif any(summary.footer_column!=-1 for summary in view.summaries):
        view.group_footer_mode='expanded'
    show=view_option('ShowFooter','true')
    if show.lower() not in ('true','false'):raise ValueError('Visibilité du pied global invalide')
    view.show_total_footer=show.lower()=='true'
    auto=view_option('RowAutoHeight','false')
    if auto.lower() not in ('true','false'):raise ValueError('Hauteur automatique de ligne invalide')
    view.auto_row_height=auto.lower()=='true'
    for name,key in [('RowHeight','row_height'),('GroupRowHeight','group_row_height'),('ColumnPanelRowHeight','header_height')]:
        height=int(text(root,name,'-1'))
        if height!=-1 and not 1<=height<=10000:raise ValueError('Hauteur de layout invalide : '+name)
        setattr(view,key,0 if height==-1 else height)

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
                # Some serializers put appearance values directly on the rule.
                # Rule metadata (Expression/PredefinedName/etc.) is not appearance data.
                appearance=ET.Element('property')
                for name,child in properties(rule_node).items():
                    if name in {'BackColor','BackColor2','ForeColor','GradientMode','Font','TextOptions','Options','BorderColor','Image','ImageOptions','ImageAlignment'} or name.startswith('Options.'):
                        appearance.append(child)
            target = None
            if text(item, "ApplyToRow", "true").lower() == "false":
                name = text(item, "ColumnApplyToName") or text(item, "ColumnName")
                target = aliases[name] if name in aliases else resolve(name)
            predefined=text(rule_node,'PredefinedName')
            from fireblade.core.tle_styles import style
            from fireblade.core.tle_appearance import appearance as read_appearance, EXTRA
            defaults=style(predefined,named_styles) if predefined else {}
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
                    appearance={key:value for key,value in adapted.items() if key in ('background2','gradient','horizontal','vertical','border_color')+EXTRA},
                    statistic=statistic,stat_rank=stat_rank,stat_percent=stat_percent,value_column=value_column,
                    stop_if_true=text(item,'StopIfTrue','false').lower()=='true',
                    use_background='background' in adapted,use_foreground='foreground' in adapted,use_font=any(key in adapted for key in ('font_family','font_size','bold','italic','underline','strikeout')),
                )
            )
    if len(view.format_rules) > 32 or len(view.summaries) > 16 or len(view.total_summaries)>16:
        raise ValueError("Disposition dépassant les limites de règles ou de résumés")
    return TleLayout(columns, view, list(dict.fromkeys(warnings)))
