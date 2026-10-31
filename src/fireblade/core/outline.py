"""A complete hierarchy indexed on disk with a bounded visible window.

Integer subtree spans give every group and leaf an absolute position. This
avoids sorting a variable-width path array for every source record, which can
exhaust a small DuckDB budget even when ordinary external sorts spill to disk.
"""

import json
import uuid
import duckdb
from dataclasses import replace
from fireblade.core.summaries import group_expression, summary_expressions


def build_outline(case, view, progress=lambda _: None):
    key = (replace(view, expand_all=False).to_json(), case._bookmark_revision)
    if case._outline_key == key:
        return
    prefix = "__outline_" + uuid.uuid4().hex
    owned = []
    stage = "initialisation"
    groupcols = [group_expression(case, view, c) for c in view.groups]
    if not groupcols:
        raise ValueError("Choisissez au moins une colonne de regroupement")
    summaries = summary_expressions(case, view)
    where, args = case.where(view)
    count = len(groupcols)
    preserve = case.db.execute(
        "SELECT current_setting('preserve_insertion_order')"
    ).fetchone()[0]

    def create(suffix, query, parameters=()):
        name = prefix + suffix
        owned.append(name)
        case.check_cancelled()
        case.db.execute(f'CREATE TEMP TABLE "{name}" AS ' + query, parameters)
        return name

    def equal(left, right, depth):
        return " AND ".join(
            f"{left}.g{i} IS NOT DISTINCT FROM {right}.g{i}" for i in range(depth)
        )

    try:
        with case.serial_query_threads():
            # All ordering is explicit in ranks/positions; preserving physical
            # insertion order here only retains unnecessary operator buffers.
            case.db.execute("SET preserve_insertion_order=false")
            for depth in range(1, count + 1):
                stage = f"agrégation du niveau {depth}/{count}"
                progress("Index du dépliage · " + stage + "…")
                fields = ", ".join(
                    f"{col} AS g{i}" for i, col in enumerate(groupcols[:depth])
                )
                aggregates = "".join(
                    f", {expr} AS s{i}" for i, expr in enumerate(summaries)
                )
                query = (
                    f"SELECT {fields}, count(*) AS n{aggregates} FROM events{where} GROUP BY "
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
                create(
                    f"_rank{depth}",
                    f"SELECT *,row_number() OVER ({partition}ORDER BY {order}) AS rank FROM ({query}) grouped",
                    args,
                )
            # A group's span is its own header plus every child subtree. The
            # deepest groups contain source rows directly, so span = n + 1.
            for depth in range(count, 0, -1):
                stage = f"étendue du niveau {depth}/{count}"
                if depth == count:
                    create(
                        f"_span{depth}",
                        f'SELECT *,cast(n+1 AS BIGINT) AS span FROM "{prefix}_rank{depth}"',
                    )
                else:
                    parent_fields = ",".join(f"g{i}" for i in range(depth))
                    children = f'SELECT {parent_fields},sum(span) AS span FROM "{prefix}_span{depth + 1}" GROUP BY {parent_fields}'
                    create(
                        f"_span{depth}",
                        f'SELECT g.*,cast(coalesce(c.span,0)+1 AS BIGINT) AS span FROM "{prefix}_rank{depth}" g LEFT JOIN ({children}) c ON '
                        + equal("g", "c", depth),
                    )
            # Prefix sums operate on group tables, not on a variable-width key
            # duplicated for millions of leaves.
            for depth in range(1, count + 1):
                stage = f"position du niveau {depth}/{count}"
                partition = (
                    "PARTITION BY "
                    + ",".join(f"g.g{i}" for i in range(depth - 1))
                    + " "
                    if depth > 1
                    else ""
                )
                previous = f"coalesce(sum(g.span) OVER ({partition}ORDER BY g.rank ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING),0)"
                base = "0" if depth == 1 else "p.start"
                join = (
                    ""
                    if depth == 1
                    else f' JOIN "{prefix}_pos{depth - 1}" p ON '
                    + equal("g", "p", depth - 1)
                )
                create(
                    f"_pos{depth}",
                    f'SELECT g.*,cast({base}+1+{previous} AS BIGINT) AS start FROM "{prefix}_span{depth}" g'
                    + join,
                )
            stage = "position des enregistrements"
            progress("Index du dépliage · " + stage + "…")
            join = " AND ".join(
                f"p.g{i} IS NOT DISTINCT FROM {col}" for i, col in enumerate(groupcols)
            )
            leaves = f'SELECT cast(p.start+row_number() OVER (PARTITION BY p.start{case.order(view)}) AS BIGINT) AS position,__row_id AS row_id FROM events JOIN "{prefix}_pos{count}" p ON {join}{where}'
            create("_leaves", leaves, args)
            unions = []
            for depth in range(1, count + 1):
                path = ",".join(f"g{i}" for i in range(depth))
                sums = "".join(f",s{i}" for i in range(len(summaries)))
                unions.append(
                    f'SELECT start AS position,{depth} AS depth,NULL::BIGINT AS row_id,to_json([{path}]) AS path,n{sums} FROM "{prefix}_pos{depth}"'
                )
            sums = ",NULL" * len(summaries)
            unions.append(
                f'SELECT position,0 AS depth,row_id,NULL AS path,NULL AS n{sums} FROM "{prefix}_leaves"'
            )
            stage = "assemblage de l’index"
            name = create("_ready", " UNION ALL ".join(unions))
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
    except Exception as exc:
        from fireblade.core.errors import OperationCancelled

        if isinstance(exc, (OperationCancelled, duckdb.InterruptException)):
            raise
        raise RuntimeError(f"Index du dépliage ({stage}) : {exc}") from exc
    finally:
        with case.finalizing_transaction():
            for name in reversed(owned):
                case.db.execute(f'DROP TABLE IF EXISTS "{name}"')
            case.db.execute(
                "SET preserve_insertion_order=" + ("true" if preserve else "false")
            )


def outline_page(case, view, offset=0, limit=None, progress=lambda _: None):
    case.validate_view(view)
    limit = max(1, min(limit or case.settings.page_size, case.settings.page_size))
    offset = max(0, offset)
    with case.operation():
        build_outline(case, view, progress)
        sums = "".join(f",s{i}" for i in range(len(view.summaries)))
        index = case.db.execute(
            f'SELECT depth,path,n{sums},row_id FROM "__fireblade_outline" WHERE position>? AND position<=? ORDER BY position',
            [offset, offset + limit],
        ).fetchall()
        ids = [row[-1] for row in index if row[0] == 0]
        # Fetch only the selected IDs. A wide LEFT JOIN can otherwise build a
        # hash table of evidence payloads before the page limit is applied.
        values = case.rows_by_ids(ids)
        result = []
        for row in index:
            group = bool(row[0])
            path = tuple(json.loads(row[1])) if group else ()
            cells = (path[-1], row[2], *row[3:-1]) if group else values[row[-1]]
            result.append(dict(group=group, path=path, values=cells))
        return result
