"""Declarative graphical/statistical rules for XtraSerializer layouts."""
from fireblade.core.tle_layout_export import prop, appearance


def write_rule(parent, ordinal, rule, names, headers, warnings):
    if rule.condition.children:
        raise ValueError('Une règle graphique/statistique conditionnelle doit être simplifiée avant son export TLE')
    column = rule.value_column if rule.value_column is not None else rule.target
    if column is None:
        raise ValueError('Colonne de valeurs absente')
    if rule.all_source_rows or rule.stat_ignore_case or rule.stat_include_null:
        raise ValueError('Population/casse/NULL de règle sans équivalent TLE vérifié ; export natif requis')
    item = prop(parent, f'Item{ordinal}', container=True)
    kind = {'bar': 'DataBar', 'scale': '2ColorScale', 'scale3': '3ColorScale', 'icon': 'IconSet'}.get(rule.visual)
    if rule.statistic:
        if rule.visual != 'none':
            raise ValueError('Combinaison de règle statistique et graphique non exportable')
        kind = 'TopBottom' if rule.statistic in ('top', 'bottom') else 'AboveBelowAverage' if 'avg' in rule.statistic else 'UniqueDuplicate'
    if kind is None:
        raise ValueError('Type de règle non exportable')
    prop(item, 'RuleType', '#FormatConditionRule' + kind)
    prop(item, 'ColumnName', names[column])
    prop(item, 'ApplyToRow', rule.target is None)
    if rule.target is not None:
        prop(item, 'ColumnApplyToName', names[rule.target])
    prop(item, 'Enabled', rule.enabled)
    prop(item, 'StopIfTrue', rule.stop_if_true)
    node = prop(item, 'Rule', container=True)
    if rule.statistic:
        if kind == 'TopBottom':
            prop(node, 'TopBottom', rule.statistic.title())
            prop(node, 'Rank', rule.stat_rank)
            prop(node, 'RankType', 'Percent' if rule.stat_percent else 'Number')
        elif kind == 'AboveBelowAverage':
            prop(node, 'AverageType', {'above_avg': 'Above', 'below_avg': 'Below', 'above_eq_avg': 'EqualOrAbove', 'below_eq_avg': 'EqualOrBelow'}[rule.statistic])
        else:
            prop(node, 'FormatType', rule.statistic.title())
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
        appearance(prop(node, 'Appearance', container=True), style)
        return
    modes = {'fixed': 'Number', 'number': 'Number', 'auto': 'Automatic', 'percent': 'Percent', 'percentile': 'Percentile'}
    for name, value in [('Minimum', rule.minimum), ('Maximum', rule.maximum), ('MinimumType', modes[rule.bound_mode]), ('MaximumType', modes[rule.maximum_mode or rule.bound_mode]), ('MinimumColor', rule.background), ('MaximumColor', rule.foreground), ('ShowValues', rule.show_values), ('AutomaticType', 'ZeroBased' if rule.zero_based else 'Default')]:
        prop(node, name, value)
    if rule.visual == 'bar':
        prop(prop(node, 'AppearancePositive', container=True), 'BackColor', rule.background)
        prop(prop(node, 'AppearanceNegative', container=True), 'BackColor', rule.negative_color)
        prop(node, 'AxisColor', rule.axis_color)
        prop(node, 'DrawAxis', rule.draw_axis)
    elif rule.visual == 'scale3':
        prop(node, 'MiddleColor', rule.middle_color)
        prop(node, 'Middle', rule.middle_value)
        prop(node, 'MiddleType', modes[rule.middle_mode])
    elif rule.visual == 'icon':
        icon_set = prop(node, 'IconSet', container=True)
        prop(icon_set, 'Name', rule.icon_set)
        prop(icon_set, 'ValueType', modes[rule.icon_threshold_mode])
        icons = prop(icon_set, 'Icons', count=len(rule.icon_colors))
        thresholds = rule.icon_thresholds or [str(i * 100 / len(rule.icon_colors)) for i in range(1, len(rule.icon_colors))]
        units = rule.icon_threshold_modes or [rule.icon_threshold_mode] * len(thresholds)
        comparisons = rule.icon_comparisons or ['>='] * len(thresholds)
        entries = [(rule.icon_floor or '0', rule.icon_floor_mode, rule.icon_floor_comparison)] + list(zip(thresholds, units, comparisons))
        # DevExpress precedence is high to low, including mixed units.
        for ordinal, index in enumerate(reversed(range(len(entries))), 1):
            value, unit, comparison = entries[index]
            entry = prop(icons, f'Item{ordinal}', container=True)
            prop(entry, 'Value', value)
            prop(entry, 'ValueType', modes[unit])
            prop(entry, 'ValueComparison', 'Greater' if comparison == '>' else 'GreaterOrEqual')
            prop(entry, 'Color', rule.icon_colors[index])
            if rule.icon_images[index]:
                prop(entry, 'Image', rule.icon_images[index])
            else:
                warnings.append('Pictogramme adapté à qualifier dans TLE : ' + rule.icon_set)
