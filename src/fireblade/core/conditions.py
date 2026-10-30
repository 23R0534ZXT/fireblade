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
        compile_condition(rule.condition, column, numeric_expression)
        if rule.target is not None:
            column(rule.target)
        if type(rule.enabled) is not bool or type(rule.bold) is not bool:
            raise ValueError("Activation et gras doivent être des booléens")
        if not all(isinstance(color, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", color) for color in (rule.background, rule.foreground)):
            raise ValueError("Couleur invalide ; utilisez #RRGGBB")
