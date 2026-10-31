"""Shared, parameterized SQL for filters and per-page format rules. No Qt."""

from fireblade.core.models import Filter, FilterGroup


def compile_condition(condition, column, numeric_expression, depth=0, budget=None):
    budget = [1024] if budget is None else budget
    budget[0] -= 1
    if depth > 24 or budget[0] < 0:
        raise ValueError("Expression limitée à 24 niveaux et 1024 conditions")
    if isinstance(condition, FilterGroup):
        if condition.logic not in ("and", "or", "not"):
            raise ValueError("Logique de filtre invalide")
        if condition.logic == "not" and len(condition.children) != 1:
            raise ValueError("Un groupe NON doit contenir une seule condition ou un seul groupe")
        if not condition.children:
            return ("TRUE" if condition.logic == "and" else "FALSE"), []
        parts, args = [], []
        for child in condition.children:
            sql, values = compile_condition(child, column, numeric_expression, depth + 1, budget)
            parts.append(f"({sql})")
            args.extend(values)
        if condition.logic == "not":
            return f"NOT coalesce({parts[0]}, FALSE)", args
        return (" AND " if condition.logic == "and" else " OR ").join(parts), args
    if not isinstance(condition, Filter):
        raise ValueError("Condition invalide")
    op, value = condition.operator, condition.value
    if op == "expression":
        from fireblade.core.expressions import compile_expression
        owner = getattr(column, '__self__', None)
        headers = getattr(owner, 'headers', None)
        if headers is None:
            raise ValueError("Le schéma des colonnes est nécessaire pour cette expression")
        return compile_expression(value, headers, column, numeric_expression)
    col = column(condition.column)
    if not isinstance(value, str):
        raise ValueError("La valeur d’une condition doit être du texte")
    if op in ("empty", "not_empty"):
        return (f"({col} IS NULL OR {col}='')" if op == "empty" else f"({col} IS NOT NULL AND {col}<>'')"), []
    if op in ("eq", "ne"):
        return f"{col} {'=' if op == 'eq' else 'IS DISTINCT FROM'} ?", [value]
    if op in ("contains", "not_contains", "starts", "ends", "regex"):
        fn = {"contains": "contains", "not_contains": "contains", "starts": "starts_with", "ends": "ends_with", "regex": "regexp_matches"}[op]
        expr = f"{fn}(coalesce({col}, ''), ?)" if op == "regex" else f"{fn}(lower(coalesce({col}, '')), lower(?))"
        return ("NOT " if op == "not_contains" else "") + expr, [value]
    if op in ("gt", "ge", "lt", "le", "after", "before", "date_before", "date_after", "date_eq", "date_ne"):
        comparison = {"gt": ">", "ge": ">=", "lt": "<", "le": "<=", "after": ">=", "before": "<=", "date_before": "<", "date_after": ">", "date_eq": "=", "date_ne": "<>"}[op]
        typ = "TIMESTAMP" if op in ("after", "before", "date_before", "date_after", "date_eq", "date_ne") else "DECIMAL(38,10)"
        if typ == 'TIMESTAMP':
            from fireblade.core.timestamps import timestamp_key
            return f'({timestamp_key(col)}) {comparison} ({timestamp_key("cast(? AS VARCHAR)")})', [value,value]
        return f'{numeric_expression(col)} {comparison} cast(? AS {typ})', [value]

    if op in ("text_gt", "text_ge", "text_lt", "text_le"):
        comparison = {"text_gt": ">", "text_ge": ">=", "text_lt": "<", "text_le": "<="}[op]
        return f"{col} {comparison} ?", [value]
    raise ValueError(f"Opérateur inconnu : {op}")


def validate_format_rules(rules, column, numeric_expression, limit=32):
    import re
    if len(rules) > limit:
        raise ValueError(f"{limit} règles de coloration au maximum")
    for rule in rules:
        from decimal import Decimal, InvalidOperation
        if rule.icon_set not in ('circles','arrows','signs') or not isinstance(rule.icon_colors,list) or not 3<=len(rule.icon_colors)<=5 or not isinstance(rule.icon_images,list) or len(rule.icon_images)!=len(rule.icon_colors):
            raise ValueError('Jeu d’icônes invalide')
        from fireblade.core.icon_assets import png_bytes
        for encoded in rule.icon_images:
            if encoded:png_bytes(encoded)
            elif encoded!='':raise ValueError('Icône invalide')
        if rule.statistic not in ('','top','bottom','above_avg','below_avg','unique','duplicate'):raise ValueError('Règle statistique inconnue')
        if rule.statistic and rule.value_column is None and rule.target is None:raise ValueError('Champ de valeurs requis pour la règle statistique')
        if rule.statistic in ('top','bottom'):
            try:
                rank=Decimal(rule.stat_rank)
                if not rank.is_finite() or rank<=0 or (rule.stat_percent and rank>100) or (not rule.stat_percent and rank!=rank.to_integral_value()):raise ValueError('Rang positif entier ou pourcentage entre 0 et 100 requis')
            except (InvalidOperation,TypeError):raise ValueError('Rang invalide') from None
        if rule.value_column is not None:column(rule.value_column)
        if rule.visual=='scale3':
            try:
                middle=Decimal(rule.middle_value)
                if not middle.is_finite() or rule.middle_mode not in ('fixed','percent','percentile'):raise ValueError('Point médian invalide')
                if rule.middle_mode!='fixed' and not 0<=middle<=100:raise ValueError('Point médian entre 0 et 100')
            except (InvalidOperation,TypeError):raise ValueError('Point médian invalide') from None
        if rule.maximum_mode not in ('','fixed','auto','percent','percentile') or rule.icon_threshold_mode not in ('number','percent','percentile'):
            raise ValueError('Mode de seuil inconnu')
        if not isinstance(rule.icon_thresholds,list) or len(rule.icon_thresholds) not in (0,len(rule.icon_colors)-1):
            raise ValueError('Nombre de seuils incorrect')
        if not isinstance(rule.icon_comparisons,list) or len(rule.icon_comparisons) not in (0,len(rule.icon_colors)-1) or any(v not in ('>','>=') for v in rule.icon_comparisons):raise ValueError('Comparaisons d’icônes invalides')
        if rule.icon_floor_mode not in ('number','percent','percentile') or rule.icon_floor_comparison not in ('>','>='):raise ValueError('Plancher d’icônes invalide')
        if rule.icon_floor:
            try:
                floor=Decimal(rule.icon_floor)
                if not floor.is_finite() or rule.icon_floor_mode!='number' and not 0<=floor<=100:raise ValueError('Plancher numérique invalide')
            except (InvalidOperation,TypeError):raise ValueError('Plancher numérique invalide') from None
        try:
            thresholds=[Decimal(v) for v in rule.icon_thresholds]
            if any(not v.is_finite() for v in thresholds) or any(a>=b for a,b in zip(thresholds,thresholds[1:])):raise ValueError('Seuils non finis ou non croissants')
            if rule.icon_threshold_mode!='number' and any(not 0<=v<=100 for v in thresholds):raise ValueError('Percentiles et pourcentages entre 0 et 100')
        except (InvalidOperation,TypeError):raise ValueError('Seuils numériques invalides') from None
        if rule.bound_mode not in ('fixed','auto','percent','percentile'):
            raise ValueError('Mode de bornes inconnu')
        if not isinstance(rule.font_family,str) or len(rule.font_family)>256 or type(rule.font_size) not in (int,float) or not 0<=rule.font_size<=96:
            raise ValueError('Police ou taille invalide (0 = héritée, maximum 96 points)')
        if rule.visual not in ('none', 'bar', 'scale', 'scale3', 'icon'):
            raise ValueError('Mode graphique inconnu')
        if rule.visual != 'none':
            if rule.value_column is None and rule.target is None:
                raise ValueError('Choisissez une colonne pour la règle graphique')
            try:
                low, high = Decimal(rule.minimum), Decimal(rule.maximum)
                modes=(rule.bound_mode,rule.maximum_mode or rule.bound_mode)
                for mode,value in zip(modes,(low,high)):
                    if mode!='auto' and not value.is_finite():raise ValueError('Bornes finies requises')
                    if mode in ('percent','percentile') and not 0<=value<=100:raise ValueError('Pourcentages entre 0 et 100')
                if modes[0]==modes[1] and modes[0]!='auto' and low>=high:raise ValueError('Minimum strictement inférieur au maximum requis')
            except (InvalidOperation, TypeError):
                raise ValueError('Bornes numériques invalides') from None
        compile_condition(rule.condition, column, numeric_expression)
        if rule.target is not None:
            column(rule.target)
        if any(type(v) is not bool for v in (rule.enabled, rule.bold, rule.italic, rule.underline, rule.strikeout,rule.stop_if_true,rule.use_background,rule.use_foreground,rule.use_font,rule.show_values,rule.zero_based,rule.draw_axis,rule.stat_percent,rule.stat_ignore_case,rule.stat_include_null)):
            raise ValueError("Activation et gras doivent être des booléens")
        if not all(isinstance(color, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", color) for color in (rule.background, rule.foreground,rule.middle_color,rule.negative_color,rule.axis_color,*rule.icon_colors)):
            raise ValueError("Couleur invalide ; utilisez #RRGGBB")
