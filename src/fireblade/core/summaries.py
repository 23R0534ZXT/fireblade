"""Validated grouping expressions. Only generated identifiers enter SQL."""

OPERATIONS = ("count", "distinct", "sum", "avg", "min", "max")
INTERVALS = {
    "year": "%Y",
    "month": "%Y-%m",
    "day": "%Y-%m-%d",
    "hour": "%Y-%m-%d %H:00",
    "week": "%G-W%V",
    "minute": "%Y-%m-%d %H:%M",
    "second": "%Y-%m-%d %H:%M:%S",
}


def group_expression(case, view, column):
    col = case.column(column)
    interval = view.group_intervals.get(str(column), "value")
    if interval == "value":
        return col
    if interval == "quarter":
        return f"strftime(cast(try_cast({col} AS TIMESTAMPTZ) AT TIME ZONE 'UTC' AS TIMESTAMP), '%Y') || '-Q' || cast(quarter(cast(try_cast({col} AS TIMESTAMPTZ) AT TIME ZONE 'UTC' AS TIMESTAMP)) AS VARCHAR)"
    if interval not in INTERVALS:
        raise ValueError("Intervalle inconnu : année, mois, jour ou heure attendu")
    return f"strftime(cast(try_cast({col} AS TIMESTAMPTZ) AT TIME ZONE 'UTC' AS TIMESTAMP), '{INTERVALS[interval]}')"


def summary_expressions(case, view):
    if len(view.summaries) > 16:
        raise ValueError("16 résumés au maximum")
    expressions = []
    for summary in view.summaries:
        col = case.column(summary.column)
        if summary.operation not in OPERATIONS or summary.kind not in (
            "text",
            "number",
            "timestamp",
        ):
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
            from fireblade.core.timestamps import timestamp_key
            from fireblade.core.derived import timestamp_sql

            aggregate = f"{summary.operation}({timestamp_key(col)})"
            expressions.append(
                timestamp_sql(f"cast(({aggregate}) AS VARCHAR)", "unix_ns",suppress_input_errors=False)
            )
            continue
        expressions.append(f"{summary.operation}({col})")
    return expressions


def group_sort_terms(view, column=None):
    if view.group_order not in ('count','value','summary') or type(view.group_descending) is not bool:
        raise ValueError('Tri des groupes invalide')
    if not isinstance(view.group_sorts,list) or len(view.group_sorts)>128:
        raise ValueError('128 tris de groupes au maximum')
    for key in view.group_sorts:
        if type(key.column) is not int or key.column<0 or key.kind not in ('count','value','summary') or type(key.descending) is not bool:
            raise ValueError('Tri de groupe importé invalide')
        if key.kind=='summary' and (type(key.summary) is not int or not 0<=key.summary<len(view.summaries)):
            raise ValueError('Résumé du tri de groupe absent')
    keys=[(key.kind,key.summary,key.descending) for key in view.group_sorts if key.column==column]
    if keys:
        return keys
    if view.group_order=='summary' and (type(view.group_summary) is not int or not 0<=view.group_summary<len(view.summaries)):
        raise ValueError('Choisissez un résumé pour trier les groupes')
    return [(view.group_order,view.group_summary,view.group_descending)]


def group_order(case, view, value, include_tie=True, group_column=None):
    expressions=summary_expressions(case,view)
    terms=[]
    for kind,summary,descending in group_sort_terms(view,group_column):
        primary='count(*)' if kind=='count' else value if kind=='value' else expressions[summary]
        terms.append(f"{primary} {'DESC' if descending else 'ASC'} NULLS LAST")
    if include_tie:terms.append(f'{value} ASC NULLS LAST')
    return ', '.join(terms)


def grouped_export_query(case,view,where,args):
    """Rank each hierarchy level using its own aggregates, including parent sums."""
    cols=[group_expression(case,view,c) for c in view.groups]
    sums=summary_expressions(case,view);ctes=[];order=[];joins=[]
    for level,column in enumerate(view.groups):
        fields=', '.join(f'{col} AS g{i}' for i,col in enumerate(cols[:level+1]))
        extra=''.join(f', {expr} AS s{i}' for i,expr in enumerate(sums))
        ctes.append(f'd{level} AS (SELECT {fields}, count(*) AS n{extra} FROM events{where} GROUP BY '+', '.join(cols[:level+1])+')')
        for kind,summary,descending in group_sort_terms(view,column):
            value=f'd{level}.n' if kind=='count' else f'd{level}.g{level}' if kind=='value' else f'd{level}.s{summary}'
            order.append(value+(' DESC' if descending else ' ASC')+' NULLS LAST')
        order.append(f'd{level}.g{level} ASC NULLS LAST')
        if level<len(cols)-1:
            joins.append(f'JOIN d{level} ON '+' AND '.join(f'd{level}.g{i} IS NOT DISTINCT FROM d{len(cols)-1}.g{i}' for i in range(level+1)))
    last=f'd{len(cols)-1}'
    select=', '.join([f'{last}.g{i}' for i in range(len(cols))]+[f'{last}.n']+[f'{last}.s{i}' for i in range(len(sums))])
    return 'WITH '+', '.join(ctes)+f' SELECT {select} FROM {last} '+' '.join(joins)+' ORDER BY '+', '.join(order), args*len(cols)
