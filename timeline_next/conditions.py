"""Shared, parameterized SQL for filters and per-page format rules. No Qt."""

from .models import Filter, FilterGroup


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
    col, op, value = column(condition.column), condition.operator, condition.value
    if op in ("empty", "not_empty"):
        return (f"({col} IS NULL OR {col}='')" if op == "empty" else f"({col} IS NOT NULL AND {col}<>'')"), []
    if op in ("eq", "ne"):
        return f"{col} {'=' if op == 'eq' else 'IS DISTINCT FROM'} ?", [value]
    if op in ("contains", "not_contains", "starts", "regex"):
        fn = {"contains": "contains", "not_contains": "contains", "starts": "starts_with", "regex": "regexp_matches"}[op]
        expr = f"{fn}(coalesce({col}, ''), ?)" if op == "regex" else f"{fn}(lower(coalesce({col}, '')), lower(?))"
        return ("NOT " if op == "not_contains" else "") + expr, [value]
    if op in ("gt", "ge", "lt", "le", "after", "before"):
        comparison = {"gt": ">", "ge": ">=", "lt": "<", "le": "<=", "after": ">=", "before": "<="}[op]
        typ = "TIMESTAMP" if op in ("after", "before") else "DECIMAL(38,10)"
        expr = f"try_cast({col} AS {typ})" if typ == "TIMESTAMP" else numeric_expression(col)
        return f"{expr} {comparison} cast(? AS {typ})", [value]
    raise ValueError(f"Opérateur inconnu : {op}")
