"""Write declarative XtraSerializer layouts; never serialize executable objects.

The writer uses the public layout grammar. Acceptance by an actual TLE build is
an independent qualification, not implied by a Fireblade round trip.
"""
from dataclasses import dataclass
from pathlib import Path
import os
import tempfile
import xml.etree.ElementTree as ET

from fireblade.core.models import Filter, FilterGroup, SortKey, GroupSort


@dataclass
class LayoutExport:
    data: bytes
    warnings: list[str]


def prop(parent, name, value=None, *, container=False, count=None):
    attributes = {'name': name}
    if container:
        attributes.update(isnull='true', iskey='true')
    if count is not None:
        attributes.update(iskey='true', value=str(count))
    child = ET.SubElement(parent, 'property', attributes)
    if value is not None:
        child.text = str(value).lower() if isinstance(value, bool) else str(value)
    return child


def quoted(value):
    return "'" + value.replace("'", "''") + "'"



def condition_key(condition):
    from dataclasses import asdict
    import hashlib,json
    return hashlib.sha256(json.dumps(asdict(condition),sort_keys=True,ensure_ascii=False).encode('utf-8')).hexdigest()

def criteria(condition, headers, source_headers=None, originals=None):
    """Preserve nesting, literal escaping, typed comparisons and empty values."""
    if originals and condition_key(condition) in originals:
        return originals[condition_key(condition)]
    if isinstance(condition, FilterGroup):
        if condition.logic == 'not':
            if len(condition.children) != 1:
                raise ValueError('Un groupe NON doit contenir une seule condition')
            return 'Not (' + criteria(condition.children[0], headers, source_headers, originals) + ')'
        if condition.logic not in ('and', 'or'):
            raise ValueError('Logique de filtre invalide')
        if not condition.children:
            return 'True' if condition.logic == 'and' else 'False'
        return (' And ' if condition.logic == 'and' else ' Or ').join('(' + criteria(c, headers, source_headers, originals) + ')' for c in condition.children)
    if not isinstance(condition, Filter):
        raise ValueError('Condition invalide')
    if condition.operator == 'expression':
        return remap_expression(condition.value,source_headers or headers,headers)
    field = '[' + headers[condition.column].replace(']', ']]') + ']'
    value = quoted(condition.value)
    op = condition.operator
    if op in ('empty', 'not_empty'):
        result = f'IsNullOrEmpty({field})'
        return 'Not (' + result + ')' if op == 'not_empty' else result
    if op in ('eq', 'ne', 'text_gt', 'text_ge', 'text_lt', 'text_le'):
        symbol = {'eq': '=', 'ne': '<>', 'text_gt': '>', 'text_ge': '>=', 'text_lt': '<', 'text_le': '<='}[op]
        # Fireblade's NE includes NULL, while DevExpress comparison alone does not.
        result = f'{field} {symbol} {value}'
        return f'IsNull({field}) Or ({result})' if op == 'ne' else result
    if op in ('contains', 'not_contains', 'starts', 'ends', 'regex'):
        function = {'contains': 'Contains', 'not_contains': 'Contains', 'starts': 'StartsWith', 'ends': 'EndsWith', 'regex': 'RegexIsMatch'}[op]
        result = f'{function}(IsNull({field}, \'\'), {value})'
        return 'Not (' + result + ')' if op == 'not_contains' else result
    if op in ('gt', 'ge', 'lt', 'le'):
        from decimal import Decimal, InvalidOperation
        try:
            number = Decimal(condition.value)
            if not number.is_finite():
                raise ValueError('Comparaison numérique non finie')
        except InvalidOperation as error:
            raise ValueError('Comparaison numérique invalide') from error
        return f'ToDecimal({field}) ' + {'gt': '>', 'ge': '>=', 'lt': '<', 'le': '<='}[op] + ' ' + str(number)
    if op in ('after', 'before', 'date_before', 'date_after', 'date_eq', 'date_ne'):
        # Dates are quoted arguments, never interpolated into a #...# token.
        symbol = {'after': '>=', 'before': '<=', 'date_before': '<', 'date_after': '>', 'date_eq': '=', 'date_ne': '<>'}[op]
        return f'ToDateTime({field}) {symbol} ToDateTime({value})'
    raise ValueError('Filtre non exportable vers TLE : ' + op)



def remap_expression(value, source, target):
    from fireblade.core.expressions import TOKEN
    result=[];offset=0
    while offset<len(value):
        match=TOKEN.match(value,offset)
        if match is None:
            result.append(value[offset:]);break
        rendered=match.group(0)
        if match.group(5) and value[match.end():].lstrip().startswith('(') and (match.group(5).lower().startswith('json') or match.group(5).lower() in ('plugintext','pluginnumber','plugindate','pluginbool')):
            raise ValueError('Expression Fireblade sans texte TLE d’origine : export natif requis pour '+match.group(5))
        if match.group(1):
            token=match.group(1);field=token[1:-1].replace(']]',']')
            matches=[(i,h) for i,h in enumerate(source) if field.casefold()==h.casefold() or field.casefold().startswith(h.casefold()+'.')]
            if matches:
                index,original=max(matches,key=lambda item:len(item[1]))
                replacement=target[index]+field[len(original):]
                rendered=rendered[:-len(token)]+'['+replacement.replace(']',']]')+']'
        result.append(rendered);offset=match.end()
    return ''.join(result)

def appearance(parent, style):
    options = prop(parent, 'Options', container=True)
    for key, name, flag in [('background', 'BackColor', 'UseBackColor'), ('foreground', 'ForeColor', 'UseForeColor'), ('border_color', 'BorderColor', 'UseBorderColor')]:
        if key in style:
            # System.Drawing.ColorConverter's portable ARGB form.
            color = style[key].lstrip('#')
            values = [int(color[i:i + 2], 16) for i in range(0, len(color), 2)]
            prop(parent, name, ', '.join(map(str, values)))
            prop(options, flag, True)
    if 'background2' in style:
        prop(parent, 'BackColor2', style['background2'])
    if 'gradient' in style:
        prop(parent, 'GradientMode', style['gradient'])
    if 'high_priority' in style:
        prop(options, 'HighPriority', style['high_priority'])
    font_keys = ('font_family', 'font_size', 'bold', 'italic', 'underline', 'strikeout')
    if any(key in style for key in font_keys):
        flags = [key.title() for key in font_keys[2:] if style.get(key)]
        font = f"{style.get('font_family') or 'Segoe UI'}, {style.get('font_size') or 9:g}pt"
        if flags:
            font += ', style=' + ', '.join(flags)
        prop(parent, 'Font', font)
        prop(options, 'UseFont', True)
    text_keys = {'horizontal': 'HAlignment', 'vertical': 'VAlignment', 'word_wrap': 'WordWrap', 'trimming': 'Trimming', 'hotkey': 'HotkeyPrefix'}
    if any(key in style for key in text_keys):
        node = prop(parent, 'TextOptions', container=True)
        for key, name in text_keys.items():
            if key in style:
                prop(node, name, ('Wrap' if style[key] else 'NoWrap') if key == 'word_wrap' else style[key])
        prop(options, 'UseTextOptions', True)
    if style.get('image'):
        prop(parent, 'Image', style['image'])
        prop(options, 'UseImage', True)
        if 'image_align' in style:
            prop(parent, 'ImageAlignment', style['image_align'])


def build_tle_layout(headers, view, columns):
    from fireblade.core.tle_appearance import validate_styles
    validate_styles(view.layout_styles, len(headers))
    if not headers or len(set(headers)) != len(headers):
        raise ValueError('Schéma absent ou ambigu')
    if len(columns) != len(headers) or {c['column'] for c in columns} != set(range(len(headers))):
        raise ValueError('La disposition doit décrire chaque colonne une seule fois')
    original_headers=headers
    headers=[view.tle_fields.get(str(i),{}).get('field',h) for i,h in enumerate(headers)]
    if len({h.casefold() for h in headers})!=len(headers):
        raise ValueError('Plusieurs colonnes Fireblade ciblent le même champ TLE ; export XML ambigu')
    for column in columns:
        if type(column.get('width')) is not int or not 1<=column['width']<=1048575 or type(column.get('position')) is not int or column['position'] < -1:
            raise ValueError('Géométrie de colonne invalide')
    root = ET.Element('XtraSerializer', version='1.0', application='View')
    prop(root, '#LayoutVersion')
    warnings = ['Ouverture dans Timeline Explorer à qualifier pour sa version et son lecteur.']
    styles=list(view.layout_styles.values())
    for rule in view.format_rules:
        if rule.use_font:
            styles.append(dict(rule.appearance, font_family=rule.font_family, font_size=rule.font_size, bold=rule.bold,italic=rule.italic,underline=rule.underline,strikeout=rule.strikeout))
    if any(any(key in style for key in ('bold','italic','underline','strikeout','font_family','font_size')) and (not style.get('font_family') or not style.get('font_size')) for style in styles):
        warnings.append('Polices partielles complétées à l’export XML : famille Segoe UI et taille 9 pt pour les valeurs héritées absentes ; export natif pour préserver cet héritage.')
    if view.bookmarks_only:
        raise ValueError('Le filtre de signets nécessite aussi les tags TLE ; exporter une session ou désactiver ce filtre')
    for feature, active in [ ('règles globales Fireblade', view.global_rules_enabled), ('surlignage de recherche', bool(view.highlight)), ('dépliage complet', view.expand_all)]:
        if active:
            warnings.append('Option Fireblade non exportée : ' + feature)
    root_options = prop(root, 'OptionsView', container=True)
    for name, value in [('ColumnAutoWidth', False), ('RowAutoHeight', view.auto_row_height), ('ShowFooter', view.show_total_footer), ('EnableAppearanceOddRow', 'odd_row' in view.layout_styles), ('EnableAppearanceEvenRow', 'even_row' in view.layout_styles), ('GroupFooterShowMode', {'hidden': 'Hidden', 'expanded': 'VisibleIfExpanded', 'always': 'VisibleAlways'}[view.group_footer_mode])]:
        prop(root_options, name, value)
    for name, value in [('RowHeight', view.row_height), ('GroupRowHeight', view.group_row_height), ('ColumnPanelRowHeight', view.header_height)]:
        prop(root, name, value or -1)
    expressions = [*view.filters]
    if view.expression is not None:
        expressions.append(view.expression)
    prop(root, 'ActiveFilterEnabled', True)
    prop(root, 'ActiveFilterString', criteria(FilterGroup('and', expressions), headers, original_headers, view.tle_expressions) if expressions else '')
    prop(root, 'FindFilterText', view.search)
    sorts = view.sorts or ([SortKey(view.sort_column, view.sort_type, view.descending)] if view.sort_column is not None else [])
    sort_map = {key.column: (i, key) for i, key in enumerate(sorts)}
    groups = {key.column: key for key in view.group_sorts}
    collection = prop(root, 'Columns', count=len(columns))
    names = [view.tle_fields.get(str(i),{}).get('name','col'+header) for i,header in enumerate(headers)]
    interval_names = {'value': 'Value', 'year': 'DateYear', 'quarter': 'DateQuarter', 'month': 'DateMonth', 'week': 'DateWeek', 'day': 'Date', 'hour': 'DateHour', 'minute': 'DateMinute', 'second': 'DateSecond'}
    for ordinal, column in enumerate(columns, 1):
        index = column['column']
        node = prop(collection, f'Item{ordinal}', container=True)
        group = view.groups.index(index) if index in view.groups else -1
        key = sort_map.get(index, (-1, None))[1]
        group_key = groups.get(index)
        descending = (group_key.descending if group_key else view.group_descending) if group >= 0 else key.descending if key else False
        for name, value in [('Name', names[index]), ('FieldName', headers[index]), ('VisibleIndex', column['position']), ('Visible', column['position'] >= 0), ('Width', column['width']), ('Fixed', 'Left' if index in view.pinned_columns else 'Right' if index in view.right_pinned_columns else 'None'), ('GroupIndex', group), ('SortIndex', sort_map.get(index, (-1, None))[0]), ('SortOrder', ('Descending' if descending else 'Ascending') if key or group >= 0 else 'None'), ('GroupInterval', interval_names[view.group_intervals.get(str(index), 'value')])]:
            prop(node, name, value)
        summary_kinds={summary.kind for summary in [*view.summaries,*view.total_summaries] if summary.column==index and summary.operation in ('sum','avg','min','max')}
        if len(summary_kinds)>1:
            raise ValueError('Résumés de types incompatibles sur un même champ TLE : '+headers[index])
        kind = key.kind if key else 'timestamp' if index in view.timestamp_columns else next(iter(summary_kinds),'text')
        if kind in ('timestamp', 'number'):
            display = prop(node, 'DisplayFormat', container=True)
            prop(display, 'FormatType', 'DateTime' if kind == 'timestamp' else 'Numeric')
            if kind == 'number':
                warnings.append('Le type numérique dépend du lecteur TLE pour tri et résumés : ' + headers[index])
        for role, name in [('cell', 'AppearanceCell'), ('header', 'AppearanceHeader')]:
            if f'{role}:{index}' in view.layout_styles:
                appearance(prop(node, name, container=True), view.layout_styles[f'{role}:{index}'])
    roles = {'row': 'Row', 'odd_row': 'OddRow', 'even_row': 'EvenRow', 'group_row': 'GroupRow', 'group_footer': 'GroupFooter', 'selected_row': 'SelectedRow', 'focused_row': 'FocusedRow', 'focused_cell': 'FocusedCell', 'header': 'HeaderPanel', 'group_panel': 'GroupPanel', 'footer_panel': 'FooterPanel', 'view_caption': 'ViewCaption', 'preview': 'Preview', 'empty': 'Empty', 'filter_panel': 'FilterPanel', 'find_panel': 'FindPanel'}
    all_appearance = prop(root, 'Appearance', container=True)
    for role, style in view.layout_styles.items():
        if role in roles:
            appearance(prop(all_appearance, roles[role], container=True), style)
    summaries = list(view.summaries)
    # The implicit count is a real GroupSummary in DevExpress and is needed by
    # group-count sort references, independently of explicit field summaries.
    count_index = len(summaries)
    for name, values in [('GroupSummary', [*summaries, None]), ('TotalSummary', view.total_summaries)]:
        items = prop(root, name, count=len(values))
        for ordinal, summary in enumerate(values, 1):
            node = prop(items, f'Item{ordinal}', container=True)
            operation = 'rows' if summary is None else summary.operation
            prop(node, 'SummaryType', {'rows': 'Count', 'count': 'Count', 'distinct': 'DistinctCount', 'sum': 'Sum', 'avg': 'Average', 'min': 'Min', 'max': 'Max'}[operation])
            prop(node, 'FieldName', '' if operation == 'rows' else headers[summary.column])
            if summary is not None and name == 'GroupSummary' and summary.footer_column != -1:
                prop(node, 'ShowInGroupColumnFooterName', names[summary.column if summary.footer_column is None else summary.footer_column])
    state = []
    for index in view.groups:
        group = groups.get(index, GroupSort(index, view.group_order, view.group_summary, view.group_descending))
        if group.kind in ('count', 'summary'):
            record = names[index] + ',' + ('Descending' if group.descending else 'Ascending') + ',#' + str(count_index if group.kind == 'count' else group.summary)
            state.append(str(len(record.encode('utf-16-le')) // 2) + ':' + record)
    prop(root, 'GroupSummarySortInfoState', ''.join(state))
    rules = prop(root, 'FormatRules', count=len(view.format_rules))
    for ordinal, rule in enumerate(view.format_rules, 1):
        if rule.visual != 'none' or rule.statistic:
            from fireblade.core.tle_rule_export import write_rule
            write_rule(rules, ordinal, rule, names, headers, warnings)
            continue
        item = prop(rules, f'Item{ordinal}', container=True)
        prop(item, 'RuleType', '#FormatConditionRuleExpression')
        prop(item, 'ApplyToRow', rule.target is None)
        if rule.target is not None:
            prop(item, 'ColumnName', names[rule.target])
            prop(item, 'ColumnApplyToName', names[rule.target])
        prop(item, 'Enabled', rule.enabled)
        prop(item, 'StopIfTrue', rule.stop_if_true)
        child = prop(item, 'Rule', container=True)
        prop(child, 'Expression', criteria(rule.condition, headers, original_headers, view.tle_expressions))
        style = dict(rule.appearance)
        if rule.use_background:
            style['background'] = rule.background
        if rule.use_foreground:
            style['foreground'] = rule.foreground
        if rule.use_font:
            style.update({key: getattr(rule, key) for key in ('bold', 'italic', 'underline', 'strikeout')})
            if rule.font_family:
                style['font_family'] = rule.font_family
            if rule.font_size:
                style['font_size'] = rule.font_size
        appearance(prop(child, 'Appearance', container=True), style)
    ET.indent(root, space='  ')
    data = ET.tostring(root, encoding='utf-8', xml_declaration=True)
    if len(data) > 4 * 1024 * 1024:
        raise ValueError('Disposition limitée à 4 Mo')
    return LayoutExport(data, list(dict.fromkeys(warnings)))


def write_tle_layout(path, headers, view, columns):
    result = build_tle_layout(headers, view, columns)
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('wb', dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(result.data)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return result.warnings
