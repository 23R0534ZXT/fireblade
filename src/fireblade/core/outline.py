"""A fully expanded hierarchy indexed on disk, with a bounded visible window.

The index contains IDs and group summaries, not copied evidence payloads. Every
filtered record and every group is reachable through paging, including groups
beyond the first page. DuckDB owns buffer limits, external sorting and spilling.
"""

import json
import uuid
from dataclasses import replace
from fireblade.core.summaries import group_expression, summary_expressions


def build_outline(case, view, progress=lambda _: None):
    key = (replace(view,expand_all=False).to_json(), case._bookmark_revision)
    if case._outline_key == key:
        return
    prefix = "__outline_" + uuid.uuid4().hex
    owned = []
    groupcols = [group_expression(case, view, c) for c in view.groups]
    if not groupcols:
        raise ValueError("Choisissez au moins une colonne de regroupement")
    summaries = summary_expressions(case, view)
    where, args = case.where(view)
    count = len(groupcols)
    try:
        with case.serial_query_threads():
            for depth in range(1, count + 1):
                case.check_cancelled()
                progress(f"Index du dépliage · niveau {depth}/{count}…")
                name = f"{prefix}_{depth}"
                owned.append(name)
                fields = ", ".join(
                    f"{col} AS g{i}" for i, col in enumerate(groupcols[:depth])
                )
                aggregates = ", ".join(
                    f"{expr} AS s{i}" for i, expr in enumerate(summaries)
                )
                query = (
                    f"SELECT {fields}, count(*) AS n"
                    + (", " + aggregates if aggregates else "")
                    + f" FROM events{where} GROUP BY "
                    + ", ".join(groupcols[:depth])
                )
                primary = (
                    "n"
                    if view.group_order == "count"
                    else f"g{depth - 1}"
                    if view.group_order == "value"
                    else f"s{view.group_summary}"
                )
                order = (
                    primary
                    + (" DESC" if view.group_descending else " ASC")
                    + f" NULLS LAST, g{depth - 1} ASC NULLS LAST"
                )
                partition = (
                    "PARTITION BY " + ",".join(f"g{i}" for i in range(depth - 1)) + " "
                    if depth > 1
                    else ""
                )
                case.db.execute(
                    f'CREATE TEMP TABLE "{name}" AS SELECT *, row_number() OVER ({partition}ORDER BY {order}) AS rank FROM ({query}) aggregate_groups',
                    args,
                )

            def ancestors(depth, leaf=False):
                # Reuse each level's local rank; arrays sort in depth-first order.
                terms = []
                for level in range(1, depth + 1):
                    equal = " AND ".join(
                        f"p{level}.g{i} IS NOT DISTINCT FROM "
                        + (groupcols[i] if leaf else f"p{depth}.g{i}")
                        for i in range(level)
                    )
                    if not leaf and level == depth:
                        continue
                    terms.append(f'JOIN "{prefix}_{level}" p{level} ON {equal}')
                return " ".join(terms)

            unions = []
            for depth in range(1, count + 1):
                ranks = ",".join(f"p{i}.rank" for i in range(1, depth + 1))
                path = ",".join(f"p{depth}.g{i}" for i in range(depth))
                sums = "".join(f",p{depth}.s{i}" for i in range(len(summaries)))
                unions.append(
                    f'SELECT [{ranks}] AS sort_path,{depth} AS depth,NULL::BIGINT AS row_id,to_json([{path}]) AS path,p{depth}.n{sums} FROM "{prefix}_{depth}" p{depth} '
                    + ancestors(depth)
                )
            ranks = ",".join(f"p{i}.rank" for i in range(1, count + 1))
            leaf_rank = (
                "row_number() OVER (PARTITION BY "
                + ",".join(groupcols)
                + case.order(view)
                + ")"
            )
            sums = ",NULL" * len(summaries)
            unions.append(
                f"SELECT [{ranks},{leaf_rank}] AS sort_path,0 AS depth,__row_id AS row_id,NULL AS path,NULL AS n{sums} FROM events "
                + ancestors(count, True)
                + where
            )
            name = prefix + "_ready"
            owned.append(name)
            progress(
                "Index du dépliage · classement de tous les groupes et enregistrements…"
            )
            case.db.execute(
                f'CREATE TEMP TABLE "{name}" AS SELECT row_number() OVER (ORDER BY sort_path) AS position,* EXCLUDE(sort_path) FROM ('
                + " UNION ALL ".join(unions)
                + ") hierarchy",
                args,
            )
            case.check_cancelled()
            case.db.execute("BEGIN")
            try:
                case.db.execute('DROP TABLE IF EXISTS "__fireblade_outline"')
                case.db.execute(f'ALTER TABLE "{name}" RENAME TO "__fireblade_outline"')
                with case.finalizing_transaction():
                    case.check_cancelled()
                    case.db.execute("COMMIT")
            except BaseException:
                with case.finalizing_transaction():
                    case.db.execute("ROLLBACK")
                raise
            case._outline_key = key
    finally:
        with case.finalizing_transaction():
            for name in reversed(owned):
                case.db.execute(f'DROP TABLE IF EXISTS "{name}"')


def outline_page(case, view, offset=0, limit=None, progress=lambda _: None):
    case.validate_view(view)
    limit = max(1, min(limit or case.settings.page_size, case.settings.page_size))
    offset = max(0, offset)
    with case.operation():
        build_outline(case, view, progress)
        sums = "".join(f",o.s{i}" for i in range(len(view.summaries)))
        rows = case.db.execute(
            f'SELECT o.depth,o.path,o.n{sums},e.* FROM "__fireblade_outline" o LEFT JOIN events e ON e.__row_id=o.row_id WHERE o.position>? AND o.position<=? ORDER BY o.position',
            [offset, offset + limit],
        ).fetchall()
        result = []
        start = 3 + len(view.summaries)
        for row in rows:
            group = bool(row[0])
            path = tuple(json.loads(row[1])) if group else ()
            values = (path[-1], row[2], *row[3:start]) if group else row[start:]
            result.append(dict(group=group, path=path, values=values))
        return result
