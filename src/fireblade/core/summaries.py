"""Validated grouping expressions. Only generated identifiers enter SQL."""

OPERATIONS = ("count", "distinct", "sum", "avg", "min", "max")
INTERVALS = {"year": "%Y", "month": "%Y-%m", "day": "%Y-%m-%d", "hour": "%Y-%m-%d %H:00"}


def group_expression(case, view, column):
    col = case.column(column)
    interval = view.group_intervals.get(str(column), "value")
    if interval == "value":
        return col
    if interval not in INTERVALS:
        raise ValueError("Intervalle inconnu : année, mois, jour ou heure attendu")
    return f"strftime(try_cast({col} AS TIMESTAMP), '{INTERVALS[interval]}')"


def summary_expressions(case, view):
    if len(view.summaries) > 16:
        raise ValueError("16 résumés au maximum")
    expressions = []
    for summary in view.summaries:
        col = case.column(summary.column)
        if summary.operation not in OPERATIONS or summary.kind not in ("text", "number", "timestamp"):
            raise ValueError("Résumé invalide")
        if summary.operation == "distinct":
            expressions.append(f"count(DISTINCT {col})")
            continue
        if summary.operation == "count":
            expressions.append(f"count({col})")
            continue
        if summary.operation in ("sum", "avg") and summary.kind != "number":
            raise ValueError("Somme et moyenne nécessitent un type numérique")
        if summary.kind == "number":
            col = case.numeric_expression(col)
        elif summary.kind == "timestamp":
            col = f"try_cast({col} AS TIMESTAMP)"
        expressions.append(f"{summary.operation}({col})")
    return expressions


def group_order(case, view, value, include_tie=True):
    if view.group_order not in ("count", "value", "summary") or type(view.group_descending) is not bool:
        raise ValueError("Tri des groupes invalide")
    direction = "DESC" if view.group_descending else "ASC"
    primary = "count(*)" if view.group_order == "count" else value
    if view.group_order == "summary":
        expressions = summary_expressions(case, view)
        if type(view.group_summary) is not int or not 0 <= view.group_summary < len(expressions):
            raise ValueError("Choisissez un résumé pour trier les groupes")
        primary = expressions[view.group_summary]
    return f"{primary} {direction} NULLS LAST" + (f", {value} ASC NULLS LAST" if include_tie else "")
